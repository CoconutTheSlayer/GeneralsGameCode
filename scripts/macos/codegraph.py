#!/usr/bin/env python3
"""Build a local compiler-dependency graph and a focused clangd renderer call graph.

No guessed call edges: dependency edges come from Ninja's compiler depfiles;
function edges come from clangd's call-hierarchy API. Unresolved virtual dispatch
and code outside the selected build are explicitly outside static coverage.
"""
import argparse
import collections
import hashlib
import html
import json
from pathlib import Path
import queue
import re
import subprocess
import threading
from urllib.parse import unquote, urlsplit

ROOT = Path(__file__).resolve().parents[2]
FOCUS = {
    'GeneralsMD/Code/GameEngineDevice/Source/W3DDevice/GameClient/W3DScene.cpp': ['Render', 'Flush', 'renderOneObject', 'flushOccludedObjectsIntoStencil'],
    'Core/Libraries/Source/WWVegas/WW3D2/dx8renderer.cpp': ['Render', 'Flush'],
    'Core/Libraries/Source/WWVegas/WW3D2/dx8polygonrenderer.cpp': ['Render'],
    'Core/Libraries/Source/WWVegas/WW3D2/dx8polygonrenderer.h': ['Render'],
    'Core/Libraries/Source/WWVegas/WW3D2/dx8wrapper.cpp': ['Draw_Triangles', 'Apply_Render_State_Changes'],
    'Dependencies/D3D8Metal/src/draw.mm': ['issueDraw', 'execDraw', 'beginDraw', 'DrawIndexedPrimitive', 'flushModelBatch', 'execModelBatch'],
    'Dependencies/D3D8Metal/src/frontend.mm': ['syncState', 'applyState', 'runRecords', 'commitRecord'],
    'Dependencies/D3D8Metal/src/device.mm': ['Present', 'SetTransform', 'SetLight', 'execFlush'],
}

class Clangd:
    def __init__(self, build, log):
        self.log = log.open('w')
        self.p = subprocess.Popen(['/usr/bin/clangd', f'--compile-commands-dir={build}',
            '--background-index=false', '--log=error', '--tweaks='], stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=self.log)
        self.messages, self.next_id, self.opened = queue.Queue(), 0, set()
        threading.Thread(target=self.reader, daemon=True).start()
        self.request('initialize', dict(processId=None, rootUri=ROOT.as_uri(), capabilities={
            'textDocument': {'documentSymbol': {'hierarchicalDocumentSymbolSupport': True}}}))
        self.notify('initialized', {})

    def reader(self):
        while True:
            headers = {}
            while line := self.p.stdout.readline():
                if line == b'\r\n': break
                k, v = line.decode().split(':', 1); headers[k.lower()] = v.strip()
            if not headers: return
            self.messages.put(json.loads(self.p.stdout.read(int(headers['content-length']))))

    def send(self, message):
        data = json.dumps(dict(jsonrpc='2.0', **message)).encode()
        self.p.stdin.write(f'Content-Length: {len(data)}\r\n\r\n'.encode() + data); self.p.stdin.flush()

    def notify(self, method, params): self.send(dict(method=method, params=params))

    def request(self, method, params):
        self.next_id += 1; request_id = self.next_id
        self.send(dict(id=request_id, method=method, params=params))
        while True:
            response = self.messages.get(timeout=120)
            if response.get('id') != request_id: continue
            if 'error' in response: raise RuntimeError(response['error'])
            return response.get('result')

    def open(self, path):
        uri = path.as_uri()
        if uri not in self.opened:
            self.notify('textDocument/didOpen', dict(textDocument=dict(uri=uri,
                languageId='objective-cpp' if path.suffix == '.mm' else 'cpp', version=1, text=path.read_text(errors='replace'))))
            self.opened.add(uri)
        return uri

    def close(self):
        self.p.terminate(); self.p.wait(timeout=10); self.log.close()

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', type=Path, default=ROOT/'build/macos')
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--profile', type=Path)
    args = parser.parse_args(); build = args.build.resolve(); out = args.output.resolve(); out.mkdir(parents=True, exist_ok=True)
    cdb_path = build/'compile_commands.json'; cdb = json.loads(cdb_path.read_text())
    objects = {str(Path(c['output']).resolve()): c['file'] for c in cdb}
    nodes, edges = {}, set()
    def file_node(path):
        path = Path(path).resolve()
        if not path.is_relative_to(ROOT): return None
        key = str(path.relative_to(ROOT)); nodes[key] = dict(id=key, kind='file', name=key, file=key)
        return key
    for command in cdb: file_node(command['file'])
    deps = subprocess.run(['ninja', '-C', str(build), '-t', 'deps'], check=True, capture_output=True, text=True).stdout
    source, dependency_objects = None, 0
    for line in deps.splitlines():
        if line and not line.startswith(' '):
            obj = line.split(': #deps ', 1)[0]
            source = objects.get(str((build/obj).resolve()))
            if source: source = file_node(source); dependency_objects += 1
        elif source and line.startswith('    '):
            dep = Path(line.strip()); target = file_node(dep if dep.is_absolute() else build/dep)
            if target and target != source: edges.add((source, target, 'compiler_dependency'))
    compiler_files = len(nodes); compiler_edges = len(edges)
    compiler_graph = dict(nodes=list(nodes.values()), edges=[list(e) for e in sorted(edges)])
    (out/'dependencies.json').write_text(json.dumps(compiler_graph, separators=(',', ':')))
    nodes, edges = {}, set(); errors, roots = [], []
    server = Clangd(build, out/'clangd.log')
    def symbol_node(item):
        path = Path(unquote(urlsplit(item['uri']).path))
        if not path.is_relative_to(ROOT): return None
        file = str(path.relative_to(ROOT)); line = item['selectionRange']['start']['line']+1
        # clangd may spell the same declaration as Device::draw or draw depending
        # on the request. Source location is its stable identity here.
        key = f'{file}:{line}:{item["selectionRange"]["start"]["character"]}'
        nodes[key] = dict(id=key, kind='function', name=item.get('detail') or item['name'], file=file, line=line,
                          detail=item.get('detail', ''), uri=item['uri'])
        return key
    def flatten(symbols):
        for symbol in symbols:
            yield symbol
            yield from flatten(symbol.get('children', []))
    try:
        for name in FOCUS:
            if (ROOT/name).exists(): server.open(ROOT/name)
        for name, wanted in FOCUS.items():
            path = ROOT/name
            if not path.exists(): errors.append(f'Missing focus file: {name}'); continue
            uri = path.as_uri()
            symbols = server.request('textDocument/documentSymbol', dict(textDocument=dict(uri=uri))) or []
            for symbol in flatten(symbols):
                label = symbol['name'].split('(', 1)[0].split('::')[-1]
                if label not in wanted: continue
                position = symbol.get('selectionRange', symbol.get('range'))['start']
                items = server.request('textDocument/prepareCallHierarchy', dict(textDocument=dict(uri=uri), position=position)) or []
                for item in items:
                    if symbol_node(item): roots.append(item)
        visited = set()
        for item in roots:
            src = symbol_node(item)
            if src in visited: continue
            visited.add(src)
            try:
                calls = server.request('callHierarchy/outgoingCalls', dict(item=item)) or []
                for call in calls:
                    target = symbol_node(call['to'])
                    if target: edges.add((src, target, 'clangd_call'))
            except Exception as error: errors.append(f'{src}: {error}')
    finally: server.close()
    profile = json.loads(args.profile.read_text()) if args.profile else []
    if isinstance(profile, list) and profile: profile = profile[-1]['summary']
    scopes = profile.get('cpu_scopes', []) if isinstance(profile, dict) else []
    metadata = dict(compile_commands=len(cdb), unique_compiled_sources=len({c['file'] for c in cdb}),
        compiler_dependency_objects=dependency_objects, dependency_files=compiler_files, dependency_edges=compiler_edges,
        call_roots=len(visited), function_nodes=len(nodes), call_edges=len(edges), errors=errors,
        compilation_database_sha256=hashlib.sha256(cdb_path.read_bytes()).hexdigest(),
        coverage='Build-wide compiler dependencies (transitive); focused renderer calls from clangd. Headers/declarations can have separate nodes from definitions. Virtual targets and queued callbacks are not exhaustively resolved. Other platforms, disabled targets and the launcher are outside this native build graph.',
        focus_hashes={p: hashlib.sha256((ROOT/p).read_bytes()).hexdigest() for p in FOCUS if (ROOT/p).exists()})
    graph = dict(metadata=metadata, nodes=list(nodes.values()), edges=[list(e) for e in sorted(edges)], cpu_scopes=scopes)
    (out/'graph.json').write_text(json.dumps(graph, indent=2)+'\n')
    data = json.dumps(graph).replace('<', '\\u003c')
    dep_names = [n['id'] for n in compiler_graph['nodes']]
    dep_ids = {name: i for i, name in enumerate(dep_names)}
    dep_data = json.dumps(dict(nodes=dep_names, edges=[[dep_ids[a], dep_ids[b]] for a, b, _ in compiler_graph['edges']]), separators=(',', ':')).replace('<', '\\u003c')
    document = '''<!doctype html><meta charset="utf-8"><title>Generals renderer code graph</title><style>
body{background:#101923;color:#edf4ff;font:16px/1.55 system-ui;margin:30px auto;max-width:1250px;padding:0 24px}a{color:#8fceff}input,select{font:inherit;padding:10px;background:#1b2d41;color:white;border:1px solid #52677d;border-radius:6px}button{font:inherit;background:#254b65;color:white;border:0;padding:10px;cursor:pointer}td,th{text-align:left;padding:9px;border-bottom:1px solid #33465a}table{width:100%;border-collapse:collapse;font-size:14px}small{color:#aac0d5}.panels{display:grid;grid-template-columns:1fr 1fr;gap:24px}.box{background:#172637;padding:20px;border-radius:12px}#nodes{max-height:540px;overflow:auto}#nodes button{display:block;width:100%;text-align:left;margin:3px 0}h1{font-size:36px}pre{white-space:pre-wrap}@media(max-width:800px){.panels{grid-template-columns:1fr}}
</style><h1>Renderer code graph</h1><p id="counts"></p><p id="coverage"></p><p><a href="dependencies.json">Build-wide compiler dependency graph</a> · <a href="graph.json">Function graph and measured CPU costs</a></p>
<p>Search a function, then select it to see its direct callers and callees. These are compiler-resolved relationships; queued execution and virtual dispatch require runtime evidence.</p>
<p><button id="functionsTab">Renderer calls</button> <button id="filesTab">Source dependencies</button></p><div id="neighborhood" style="overflow:auto"></div><input id="search" placeholder="Find a function or file…"><div class="panels"><section class="box"><h2>Functions / source files</h2><div id="nodes"></div></section><section class="box"><h2 id="selected">Select a function</h2><div id="relations" style="max-height:600px;overflow:auto"></div></section></div><h2>Measured CPU costs</h2><p>Saved profile attribution, milliseconds per rendered frame. Parent scopes include children and must not be added together.</p><table><thead><tr><th>Scope</th><th>Total CPU</th><th>Own CPU</th></tr></thead><tbody id="costs"></tbody></table><script>const functionGraph=__FUNCTION_GRAPH_JSON__;const deps=__DEPENDENCIES_JSON__;
const dependencyGraph={nodes:deps.nodes.map(id=>({id,kind:'file',name:id.split('/').slice(-2).join('/'),file:id})),edges:deps.edges.map(([a,b])=>[deps.nodes[a],deps.nodes[b],'compiler_dependency'])};
let graph=functionGraph;
const esc=x=>String(x).replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));let byId=new Map(graph.nodes.map(n=>[n.id,n]));
document.getElementById('counts').textContent=`${graph.metadata.unique_compiled_sources} compiled source files · ${graph.metadata.dependency_edges.toLocaleString()} compiler dependency edges · ${graph.metadata.function_nodes} function nodes · ${graph.metadata.call_edges} focused call edges`;
document.getElementById('coverage').textContent=graph.metadata.coverage;
function drawNeighborhood(id){
let incoming=graph.edges.filter(e=>e[1]===id).map(e=>e[0]),outgoing=graph.edges.filter(e=>e[0]===id).map(e=>e[1]);
let a=[...new Set(incoming)].slice(0,8),b=[...new Set(outgoing)].slice(0,8),height=Math.max(a.length,b.length,1)*58+50,cy=height/2;
let svg=`<svg viewBox="0 0 1200 ${height}" style="min-width:850px;width:100%" aria-label="Selected function and direct call relationships"><defs><marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="4" orient="auto"><path d="M0,0 L8,4 L0,8" fill="#80b7d4"/></marker></defs>`;
function node(key,x,y){let label=byId.get(key).name;return `<g data-id="${esc(key)}" role="button" tabindex="0" style="cursor:pointer"><title>${esc(label)}</title><rect x="${x}" y="${y-19}" width="340" height="38" rx="8" fill="${key===id?'#285e70':'#20354c'}" stroke="#658da5"/><text x="${x+12}" y="${y+5}" fill="white" font-size="13">${esc(label.length>43?label.slice(0,40)+'…':label)}</text></g>`;}
a.forEach((key,i)=>{let y=40+i*58;svg+=`<path d="M355 ${y} L425 ${cy}" stroke="#80b7d4" marker-end="url(#arrow)"/>`+node(key,15,y)});
b.forEach((key,i)=>{let y=40+i*58;svg+=`<path d="M765 ${cy} L835 ${y}" stroke="#80b7d4" marker-end="url(#arrow)"/>`+node(key,835,y)});
svg+=node(id,425,cy)+'</svg>';document.getElementById('neighborhood').innerHTML=svg;
document.querySelectorAll('#neighborhood g[data-id]').forEach(g=>{g.onclick=()=>select(g.dataset.id);g.onkeydown=e=>{if(e.key==='Enter')select(g.dataset.id)}});
}
function select(id){drawNeighborhood(id);let n=byId.get(id);document.getElementById('selected').textContent=n.name;let box=document.getElementById('relations');box.innerHTML=`<small>${esc(n.file)}${n.line?':'+n.line:''}</small>`;for(let [title,index,other] of [[graph===functionGraph?'Calls':'Depends on',0,1],[graph===functionGraph?'Called by':'Used by',1,0]]){let heading=document.createElement('h3');heading.textContent=title;box.append(heading);let links=graph.edges.filter(e=>e[index]===id);if(!links.length)box.append(document.createTextNode('No edge recorded in this focused graph.'));for(let e of links){let b=document.createElement('button');b.textContent=byId.get(e[other]).name;b.onclick=()=>select(e[other]);box.append(b,document.createElement('br'));}}}
function search(){let q=document.getElementById('search').value.toLowerCase();let box=document.getElementById('nodes');box.replaceChildren();for(let n of graph.nodes.filter(n=>(n.name+' '+n.file).toLowerCase().includes(q)).sort((a,b)=>a.name.localeCompare(b.name))){let b=document.createElement('button');b.innerHTML=esc(n.name)+'<br><small>'+esc(n.file)+(n.line?':'+n.line:'')+'</small>';b.onclick=()=>select(n.id);box.append(b);}}document.getElementById('search').oninput=search;search();select(graph.nodes.find(n=>n.name.includes('issueDraw'))?.id??graph.nodes[0].id);
function switchGraph(next){graph=next;byId=new Map(graph.nodes.map(n=>[n.id,n]));document.getElementById('search').value='';search();select(graph.nodes.find(n=>n.name.includes('issueDraw')||n.file.endsWith('/dx8renderer.cpp'))?.id??graph.nodes[0].id);}
document.getElementById('functionsTab').onclick=()=>switchGraph(functionGraph);document.getElementById('filesTab').onclick=()=>switchGraph(dependencyGraph);
document.getElementById('costs').innerHTML=functionGraph.cpu_scopes.sort((a,b)=>b.cpu_ms.mean-a.cpu_ms.mean).map(s=>`<tr><td>${esc(s.name)}</td><td>${s.cpu_ms.mean.toFixed(3)}</td><td>${s.self_cpu_ms?.mean.toFixed(3)??'—'}</td></tr>`).join('');</script>'''.replace('__FUNCTION_GRAPH_JSON__', data).replace('__DEPENDENCIES_JSON__', dep_data)
    (out/'index.html').write_text(document)
    print(json.dumps(metadata, indent=2))
    if not visited or not edges: raise RuntimeError('No compiler call graph was generated')

if __name__ == '__main__': main()

"""Validate exported faction models without launching Blender or importing generators."""
from pathlib import Path
import argparse
import hashlib
import json
import math
import struct
from PIL import Image

ROOT=Path(__file__).resolve().parents[3]
ART=ROOT/'resources/macos/GameData/Art'
PREFIXES={'israel':'IL','russia':'RU','ukraine':'UA'}

def chunks(data):
    pos=0
    while pos<len(data):
        assert pos+8<=len(data),'Truncated W3D chunk'
        kind,flags=struct.unpack_from('<II',data,pos)
        size=flags&0x7fffffff
        assert pos+8+size<=len(data),'Invalid W3D chunk size'
        yield kind,data[pos+8:pos+8+size],bool(flags>>31)
        pos+=8+size

def cstr(data):return data.split(b'\0',1)[0].decode('latin1')

def walk(data):
    for kind,body,nested in chunks(data):
        yield kind,body
        if nested:yield from walk(body)

def model(path,texture_paths):
    raw=path.read_bytes();meshes=set();bones=[];refs=[];textures=set();triangles=0
    for kind,body,nested in chunks(raw):
        if kind==0:
            parts={k:b for k,b,_ in chunks(body)}
            h=parts[31];name=(cstr(h[24:40])+'.'+cstr(h[8:24])).upper()
            assert name not in meshes,(path.name,'duplicate truncated mesh',name)
            meshes.add(name)
            nt,nv=struct.unpack_from('<II',h,40)
            assert len(parts[2])==nv*12,(path.name,'vertex count')
            assert len(parts[32])==nt*32,(path.name,'triangle count')
            assert all(math.isfinite(v) for v in struct.unpack('<'+'f'*(len(parts[2])//4),parts[2])),path.name
            for off in range(0,len(parts[32]),32):assert max(struct.unpack_from('<III',parts[32],off))<nv,path.name
            triangles+=nt
        if kind==0x740:meshes.add(cstr(body[8:40]).upper())
        if kind==0x100:
            for k,b,_ in chunks(body):
                if k==0x102:
                    bones=[cstr(b[i:i+16]).upper() for i in range(0,len(b),60)]
                    assert len(bones)==len(set(bones)),(path.name,'duplicate bones')
                    for i in range(len(bones)):assert struct.unpack_from('<i',b,i*60+16)[0]<i,path.name
        if kind==0x700:
            for k,b in walk(body):
                if k==0x704:refs.append((struct.unpack_from('<I',b)[0],cstr(b[4:]).upper()))
    for bone,name in refs:
        assert name in meshes,(path.name,'unresolved mesh',name)
        if bones:assert bone<len(bones),(path.name,'unresolved bone')
    for kind,body in walk(raw):
        if kind==0x32:textures.add(cstr(body).lower())
    for name in textures:
        assert name in texture_paths,(path.name,'missing texture',name)
        with Image.open(texture_paths[name]) as im:
            if texture_paths[name].suffix.lower()=='.tga':
                assert im.format=='TGA',(path.name,'non-TGA payload behind TGA extension',name,im.format)
            assert all(n>0 and not n&(n-1) for n in im.size),(name,'texture dimensions',im.size)
    # Animation-only W3Ds are valid, but model files need visible geometry.
    animated=any(k in (0x200,0x280) for k,_ in walk(raw))
    assert triangles or animated,(path.name,'empty asset')
    return {'model':path.stem,'triangles':triangles,'meshes':len(meshes),'bones':bones,'textures':sorted(textures),'animation':animated,'sha256':hashlib.sha256(raw).hexdigest()}

def main():
    parser=argparse.ArgumentParser();parser.add_argument('factions',nargs='*',default=list(PREFIXES));args=parser.parse_args()
    textures={p.name.lower():p for folder in ('TexturesHD','Textures') for p in (ART/folder).glob('*') if p.is_file()}
    results={}
    for faction in args.factions:
        prefix=PREFIXES[faction];paths=sorted((ART/'W3D').glob(prefix+'*.w3d'))
        assert paths,('Missing exports',faction)
        results[faction]=[model(p,textures) for p in paths]
        print(f'{faction}: {len(paths)} exports, {sum(r["triangles"] for r in results[faction])} triangles across variants')
    out=ROOT/'build/new-factions';out.mkdir(parents=True,exist_ok=True)
    (out/'assets-validation.json').write_text(json.dumps({'status':'passed','factions':results},indent=2)+'\n')

if __name__=='__main__':main()

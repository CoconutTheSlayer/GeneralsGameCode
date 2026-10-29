"""Validate the original Israel W3D family and create review sheets / portraits."""
from pathlib import Path
import hashlib,json,math,struct
from PIL import Image,ImageDraw,ImageFont,ImageOps
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).parent
DATA=ROOT/'resources/macos/GameData/Art';BUILD=ROOT/'build/faction-assets/israel'
def chunks(data):
    p=0
    while p<len(data):
        cid,size=struct.unpack_from('<II',data,p);length=size&0x7fffffff
        assert p+8+length<=len(data),'chunk outside file'
        yield cid,data[p+8:p+8+length],bool(size>>31)
        p+=length+8
    assert p==len(data)
def cstr(data):return data.split(b'\0')[0].decode('ascii')
def walk(data):
    for c,b,n in chunks(data):
        yield c,b
        if n:yield from walk(b)
def check(path):
    meshes=set();refs=[];bones=[];textures=set();triangles=0;animations=[]
    for cid,body,nested in chunks(path.read_bytes()):
        if cid==0:
            parts={c:b for c,b,_ in chunks(body)};h=parts[31];ntri,nvert=struct.unpack_from('<II',h,40)
            mesh=cstr(h[24:40])+'.'+cstr(h[8:24]);assert mesh not in meshes,(path,'duplicate mesh',mesh);meshes.add(mesh)
            assert len(parts[2])==nvert*12 and len(parts[3])==nvert*12
            assert all(math.isfinite(x) for x in struct.unpack('<'+'f'*(len(parts[2])//4),parts[2])),path
            assert all(math.isfinite(x) for x in struct.unpack('<'+'f'*(len(parts[3])//4),parts[3])),path
            for i in range(ntri):assert max(struct.unpack_from('<3I',parts[32],i*32))<nvert
            triangles+=ntri
        if cid==0x100:
            for c,b,_ in chunks(body):
                if c==0x102:
                    bones=[cstr(b[i:i+16]) for i in range(0,len(b),60)]
                    assert len(bones)==len(set(bones)),(path,'duplicate bone')
                    for i in range(len(bones)):assert struct.unpack_from('<i',b,i*60+16)[0]<i
        for c,b in walk(body) if nested else []:
            if c==0x32:textures.add(cstr(b))
            if c==0x704:refs.append((struct.unpack_from('<I',b)[0],cstr(b[4:])))
            if c==0x201:animations.append(dict(name=cstr(b[4:20]),hierarchy=cstr(b[20:36]),frames=struct.unpack_from('<I',b,36)[0]))
            if c==0x4A:assert all(math.isfinite(x) for x in struct.unpack('<'+'f'*(len(b)//4),b))
    for bone,mesh in refs:assert bone<len(bones) and mesh in meshes,(path,'broken HLOD',bone,mesh)
    for tex in textures:
        assert tex.startswith('il'),(path,'foreign texture',tex)
        im=Image.open(DATA/'TexturesHD'/tex)
        assert im.format=='TGA',(path,'non-TGA payload',tex,im.format)
        assert all(n>0 and n&(n-1)==0 for n in im.size)
    return dict(model=path.stem,triangles=triangles,meshes=len(meshes),bones=bones,textures=sorted(textures),animations=animations,sha256=hashlib.sha256(path.read_bytes()).hexdigest())
def main():
    manifest=json.loads((HERE/'manifest.json').read_text());assets=manifest['assets'];assert len(assets)==25,len(assets)
    report=[];thumbs=[]
    for entry in assets:
        for model in entry['variants']:
            row=check(DATA/'W3D'/(model+'.w3d'));assert row['triangles']>0
            assert set(entry['bones'])<=set(row['bones']),(model,'missing expected bones');report.append(row)
        assert (DATA/'TexturesHD'/(entry['model'].lower()+'_paint.tga')).read_bytes()!=(DATA/'TexturesHD'/(entry['model'].lower()+'_paint_d.tga')).read_bytes()
        for suffix,animation in entry['animations'].items():
            row=check(DATA/'W3D'/(entry['model']+suffix+'.w3d'))
            assert len(row['animations'])==1 and row['animations'][0]['hierarchy']==entry['model'],row
            assert row['animations'][0]['name']==animation.split('.')[1],row
            assert row['animations'][0]['hierarchy']==animation.split('.')[0],row
            report.append(row)
        # High-resolution portraits use the same illustrated masters as the
        # runtime command buttons. Geometry review sheets still show the meshes.
        im=Image.open(entry['preview']).convert('RGB')
        source=HERE/'portraits'/(entry['key'].lower()+'.png')
        assert source.is_file(),('Missing illustrated portrait',source)
        canvas=ImageOps.fit(Image.open(source).convert('RGB'),(256,256),method=Image.Resampling.LANCZOS)
        d=ImageDraw.Draw(canvas);d.rectangle((0,0,255,255),outline=(46,57,66),width=2)
        try:font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial Bold.ttf',15)
        except OSError:font=ImageFont.load_default()
        filename=entry['model'].lower()+'_icon.tga';canvas.save(DATA/'TexturesHD'/filename);canvas.save(BUILD/(entry['model']+'_portrait.png'))
        entry['portrait_texture']=filename;entry['portrait_preview']=str(BUILD/(entry['model']+'_portrait.png'))
        entry['portrait_source']=str(source.relative_to(ROOT));thumbs.append((entry,im))
    for label,items in [('all',thumbs),('units',[p for p in thumbs if p[0]['category']!='building']),('buildings',[p for p in thumbs if p[0]['category']=='building'])]:
        cols=5 if label=='all' else 4;rows=math.ceil(len(items)/cols);sheet=Image.new('RGB',(cols*320,rows*275),(36,41,43));d=ImageDraw.Draw(sheet)
        for i,(entry,im) in enumerate(items):
            x=(i%cols)*320;y=(i//cols)*275;sheet.paste(im.resize((320,240),Image.Resampling.LANCZOS),(x,y));d.text((x+12,y+249),entry['display_name'],font=font,fill=(234,225,201))
        sheet.save(BUILD/('contact-'+label+'.png'))
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    provenance={'tool':'Built-in image_gen','prompt_files':['scripts/models/israel/'+p for p in ['texture-polish-prompt.txt','texture-polish-damage-prompt.txt','infantry-atlas-v2-prompt.txt','aviation-atlas-v2-prompt.txt','portraits/rifleman-prompt.txt','portraits/spike-prompt.txt','portraits/commando-prompt.txt','portraits/illustrated-prompts.json']],
      'geometry':'Original authored Blender geometry with layered armour, sensors and stowage; EU mathematical primitives reused; no stock game art',
      'polish_source':'scripts/models/israel/polish_geometry.py','bake_source':'scripts/models/israel/polished_bake.py',
      'source_atlas':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in [HERE/'atlas_polished.png',HERE/'atlas_polished_d.png',HERE/'infantry_atlas_v2.png',HERE/'aviation_atlas_v2.png']},
      'illustrated_portraits':{p.name:hashlib.sha256(p.read_bytes()).hexdigest() for p in (HERE/'portraits').glob('*.png')},
      'portrait_sources':'scripts/models/israel/portraits/illustrated-sources.json',
      'infantry_geometry':'scripts/models/israel/infantry_v2.py','aircraft_geometry':'scripts/models/israel/aircraft_v2.py','icon_builder':'scripts/factions/israel/build_faction.py'}
    (HERE/'provenance.json').write_text(json.dumps(provenance,indent=2)+'\n')
    result={'status':'passed','faction':'Israel','assets':len(assets),'model_and_animation_exports':len(report),'portraits':len(thumbs),'exports':report}
    (BUILD/'validation.json').write_text(json.dumps(result,indent=2)+'\n');print(json.dumps({k:v for k,v in result.items() if k!='exports'},indent=2))
if __name__=='__main__':main()

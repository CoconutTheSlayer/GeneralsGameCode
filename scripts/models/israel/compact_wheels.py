"""Merge each original wheel hub into its tyre mesh, retaining its animation bone."""
from pathlib import Path
import json,struct,sys
HERE=Path(__file__).parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE.parent))
import w3d
from validate import chunks,cstr,walk
def optimize(path,wreck_of=None):
    source=(wreck_of or path).read_bytes();top=list(chunks(source));bone_rows=[];refs={};animation=None
    for cid,body,_ in top:
        if cid==w3d.HIERARCHY:
            for c,b,_ in chunks(body):
                if c==w3d.PIVOTS:
                    for i in range(0,len(b),60):bone_rows.append((cstr(b[i:i+16]),struct.unpack_from('<i',b,i+16)[0],struct.unpack_from('<3f',b,i+20),struct.unpack_from('<4f',b,i+44)))
        if cid==w3d.HLOD:
            for c,b in walk(body):
                if c==w3d.HLOD_SUB_OBJECT:refs[cstr(b[4:]).split('.')[-1]]=struct.unpack_from('<I',b)[0]
        if cid==w3d.ANIMATION:animation=w3d.chunk(cid,body,True)
    groups={};changed=False
    for cid,body,_ in top:
        if cid!=w3d.MESH:continue
        parts={c:b for c,b,_ in chunks(body)};h=parts[w3d.HEADER3];name=cstr(h[8:24]);bone=refs[name]
        texture=next(cstr(b) for c,b in walk(body) if c==w3d.TEXTURE_NAME)
        merged_name=bone_rows[bone][0] if bone_rows[bone][0].startswith('TIRE') else name
        key=(merged_name,bone,texture);changed|=key in groups
        uvblob=next(b for c,b in walk(body) if c==w3d.STAGE_TEXCOORDS)
        row=groups.setdefault(key,dict(verts=[],normals=[],uvs=[],tris=[],shadow=bool(struct.unpack_from('<I',h,4)[0]&w3d.CAST_SHADOW),shader=parts[w3d.SHADERS]))
        offset=len(row['verts']);row['verts']+=list(struct.iter_unpack('<3f',parts[w3d.VERTICES]));row['normals']+=list(struct.iter_unpack('<3f',parts[w3d.NORMALS]));row['uvs']+=list(struct.iter_unpack('<2f',uvblob))
        row['tris'] += [tuple(i+offset for i in struct.unpack_from('<3I',parts[w3d.TRIANGLES],p)) for p in range(0,len(parts[w3d.TRIANGLES]),32)]
        mapper=next((cstr(b) for c,b in walk(body) if c==w3d.MAPPER_ARGS0),None)
        if mapper is not None:row['mapper_args']=mapper
    if not changed and not wreck_of:return False
    model=w3d.Model(path.stem)
    world_z=[]
    for n,parent,at,q in bone_rows:world_z.append(at[2]+(world_z[parent] if parent>=0 else 0))
    flatten=lambda z:z if z<2 else 2+(z-2)*.18
    for idx,(n,parent,at,q) in enumerate(bone_rows[2:],2):
        if wreck_of:at=(at[0],at[1],flatten(world_z[idx])-flatten(world_z[parent]))
        model.bone(n,parent,at,rotation=q)
    for (name,bone,texture),row in groups.items():
        if wreck_of:
            row['verts']=[(x,y,flatten(z+world_z[bone])-flatten(world_z[bone])) for x,y,z in row['verts']]
            if texture==wreck_of.stem.lower()+'_paint.tga':texture=texture.replace('.tga','_dn.tga' if path.stem.endswith('_EN') else '_d.tga')
        model.mesh(name,bone,texture=texture,**row)
    if animation:model.animation=True;model._animation=lambda:animation
    model.save(str(path));return True
if __name__=='__main__':
    manifest=json.loads((HERE/'manifest.json').read_text());count=0
    for asset in manifest['assets']:
        for name in asset['variants']:count+=optimize(ROOT/'resources/macos/GameData/Art/W3D'/(name+'.w3d'))
        if asset['category']=='building':
            for suffix in ('_E','_EN'):optimize(ROOT/'resources/macos/GameData/Art/W3D'/(asset['model']+suffix+'.w3d'),ROOT/'resources/macos/GameData/Art/W3D'/(asset['model']+'.w3d'))
    print('Compacted wheel exports:',count)

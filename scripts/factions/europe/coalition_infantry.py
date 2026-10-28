"""Reuse installed infantry rigs/animations, replacing weapons and repainting uniforms.

Run with Python 3 after install_textures.py. Skinned vertex influences and the stock
animation hierarchy remain untouched. New rigid equipment rides the original gun
bone, so movement, firing, garrisoning, parachuting and deaths still animate.
"""
from pathlib import Path
import io
import math
import struct
import sys
import numpy as np
from PIL import Image, ImageDraw

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE.parent.parent/'models'))
import w3d
from stock_data import asset

ROOT=HERE.parents[2]
OUT=ROOT/'resources/macos/GameData/Art/W3D'
TEX=ROOT/'resources/macos/GameData/Art/TexturesHD'


def chunks(data):
    p=0
    while p < len(data):
        cid,size=struct.unpack_from('<II',data,p);n=size&0x7fffffff
        yield cid,data[p+8:p+8+n],bool(size>>31)
        p+=8+n


def cstr(data):return data.split(b'\0')[0].decode('latin1')


class Gear:
    def __init__(self):self.verts=[];self.normals=[];self.uvs=[];self.tris=[]
    def face(self,points,uv=(.3,.3)):
        start=len(self.verts);v=np.asarray(points);n=np.cross(v[1]-v[0],v[2]-v[0]);n=n/(np.linalg.norm(n) or 1)
        self.verts.extend(points);self.normals.extend([tuple(n)]*len(points));self.uvs.extend([uv]*len(points))
        self.tris.extend([(start,start+i,start+i+1) for i in range(1,len(points)-1)])
    def box(self,lo,hi,uv=(.3,.3)):
        x,y,z=lo;X,Y,Z=hi
        for p in [[(x,y,z),(x,y,Z),(x,Y,Z),(x,Y,z)],[(X,y,z),(X,Y,z),(X,Y,Z),(X,y,Z)],
                  [(x,y,z),(X,y,z),(X,y,Z),(x,y,Z)],[(x,Y,z),(x,Y,Z),(X,Y,Z),(X,Y,z)],
                  [(x,y,z),(x,Y,z),(X,Y,z),(X,y,z)],[(x,y,Z),(X,y,Z),(X,Y,Z),(x,Y,Z)]]:self.face(p,uv)
    def tube(self,x0,x1,r,y=0,z=0,uv=(.3,.3)):
        for i in range(8):
            p,q=i*math.pi/4,(i+1)*math.pi/4
            self.face([(x0,y+r*math.cos(p),z+r*math.sin(p)),(x1,y+r*math.cos(p),z+r*math.sin(p)),
                       (x1,y+r*math.cos(q),z+r*math.sin(q)),(x0,y+r*math.cos(q),z+r*math.sin(q))],uv)
        for x in (x0,x1):self.face([(x,y+r*math.cos(i*math.pi/4),z+r*math.sin(i*math.pi/4)) for i in range(8)],(.8,.2))
    def data(self):return {k:getattr(self,k) for k in ['verts','normals','uvs','tris']}


def gun(kind):
    g=Gear()
    if kind in ('milan','mistral','atgl'):
        g.tube(-2,7.6,.62 if kind=='atgl' else .8,uv=(.25,.75))
        if kind=='atgl':g.tube(5,7.3,1.02,uv=(.25,.75))
        else:g.box((-1,-1.4,-.5),(1,-.6,.7));g.box((1,-.45,-1.1),(2,.45,-.6))
        return g
    if kind in ('eod','sar'):
        g.box((-.5,-.8,-.8),(2.5,.8,.8),(.75,.75));g.box((.2,-.4,.8),(1.8,.4,1.1));return g
    bullpup=kind in ('aug','famas')
    g.box((-2.2,-.44,-.35),(2.8,.44,.35),(.25,.75))
    g.box((-1.7 if bullpup else .5,-.27,-1.2),(-.8 if bullpup else 1.3,.27,-.25))
    g.tube(2.3,7.35,.17)
    g.box((2,-.37,-.28),(5.1,.37,.28))
    if kind in ('sako','aug','hk','lynx','minimi'):
        g.tube(-.2,2.7,.23,z=.8);g.box((.3,-.15,.25),(.7,.15,.85))
    if kind=='famas':g.box((-.7,-.2,.65),(3.8,.2,.9));g.box((-.8,-.2,.25),(-.45,.2,.75));g.box((3.5,-.2,.25),(3.8,.2,.75))
    if kind=='sako':g.tube(3,7.6,.24);g.box((4.5,-.12,-1.2),(4.7,.12,-.2))
    if kind=='minimi':g.box((.2,-.8,-1.3),(2.3,.55,-.25),(.25,.75));g.tube(3,7.6,.28)
    if kind=='lynx':g.box((-2.3,-.6,-.5),(3.5,.6,.5));g.tube(3,7.6,.34);g.box((6.7,-.55,-.5),(7.6,.55,.5))
    return g


ROSTER=[
    ('EULEGION','AIRNGR',14,'famas','France'),('EUAUG','AIRNGR',14,'aug','Austria'),
    ('EUPARA','AIRNGR',14,'g3','Portugal'),('EUIRISH','AIRNGR',14,'hk','Ireland'),
    ('EUEOD','AIRNGR',14,'eod','Malta'),('EUSAR','AIRNGR',14,'sar','Iceland'),
    ('EUMILAN','NITHNT',25,'milan','France'),('EUMISTR','NITHNT',25,'mistral','Cyprus'),
    ('EUATGL','NITHNT',25,'atgl','Bulgaria'),('EUSAKO','AIPFDR',33,'sako','Finland'),
    ('EUGROM','AIHERO',None,'hk','Poland'),('EUMINIM','AIRNGR',14,'minimi','Belgium'),
    ('EULYNX','AIPFDR',33,'lynx','Hungary')]


def texture(source,name,kind):
    base=Path(source).stem.lower()
    local=TEX/('eu_'+base+'.tga')
    if local.exists():im=Image.open(local).convert('RGBA')
    else:
        for ext in ('.dds','.tga'):
            try:im=Image.open(io.BytesIO(asset(base+ext,'textures'))).convert('RGBA');break
            except StopIteration:continue
        else:raise FileNotFoundError(source)
    # Retain skin, boots, folds and the original painted lighting. Shift olive/tan
    # cloth towards the shared muted coalition palette, leaving near-greys alone.
    arr=np.array(im).astype(float);rgb=arr[:,:,:3];lum=rgb@np.array([.299,.587,.114])
    cloth=(rgb[:,:,1]>rgb[:,:,2]*1.10)&(rgb[:,:,0]<rgb[:,:,1]*1.55)
    tone=np.array([.75,.89,1.02]) if kind!='sar' else np.array([1.25,.75,.25])
    rgb[cloth]=np.clip(lum[cloth,None]*tone,0,255)
    arr[:,:,:3]=rgb;Image.fromarray(arr.astype('uint8')).save(TEX/name)


def make(name,parent,bone,kind,country):
    src=asset(parent+'_SKN.w3d');old=parent+'_SKN'
    render_objects=set()
    for c,b,_ in chunks(src):
        if c==0:
            h=dict((cc,dd) for cc,dd,_ in chunks(b))[31]
            render_objects.add((cstr(h[24:40])+'.'+cstr(h[8:24])).upper())
        elif c==0x740:render_objects.add(cstr(b[8:40]).upper())
    if bone is None:
        for c,b,_ in chunks(asset(parent+'_SKL.w3d')):
            if c==w3d.HIERARCHY:
                for c2,b2,_ in chunks(b):
                    if c2==w3d.PIVOTS:
                        bone=next((i//60 for i in range(0,len(b2),60) if 'GUN' in cstr(b2[i:i+16])),None)
    out=[];texture_map={}
    def rewrite(data):
        records=[]
        for c,b,children in chunks(data):
            if c==w3d.HEADER3:b=b[:24]+w3d.name(name)+b[40:]
            elif c==w3d.HLOD_HEADER:b=b[:8]+w3d.name(name)+b[24:]
            elif c==w3d.HLOD_SUB_OBJECT:
                ref=cstr(b[4:]);b=b[:4]+w3d.name(name+'.'+ref.split('.',1)[-1],32)
            elif c==w3d.TEXTURE_NAME:
                source=cstr(b)
                if not source.lower().startswith('ex'):
                    new=texture_map.setdefault(source,f'{name.lower()}_{len(texture_map)}.tga')
                    texture(source,new,kind);b=w3d.cstring(new)
            elif children:b=rewrite(b)
            records.append(w3d.chunk(c,b,children))
        return b''.join(records)
    gear=gun(kind);m=w3d.Model(name)
    for c,b,children in chunks(src):
        if c==w3d.MESH:
            parts=list(chunks(b));lookup={c:d for c,d,_ in parts}
            if 14 in lookup and bone is not None:
                # Remove original weapon triangles, retaining body vertices and rig weights.
                weights=lookup[14];tri=lookup[w3d.TRIANGLES];kept=[]
                for i in range(0,len(tri),32):
                    ids=struct.unpack_from('<3I',tri,i)
                    if not all(struct.unpack_from('<H',weights,v*8)[0]==bone for v in ids):kept.append(tri[i:i+32])
                fixed=[]
                for c2,b2,kids in parts:
                    if c2==w3d.TRIANGLES:b2=b''.join(kept)
                    if c2==w3d.HEADER3:b2=b2[:40]+struct.pack('<I',len(kept))+b2[44:]
                    fixed.append(w3d.chunk(c2,b2,kids))
                b=b''.join(fixed)
            out.append(w3d.chunk(c,rewrite(b),True))
        elif c==w3d.HLOD:
            new=[]
            for c2,b2,kids in chunks(b):
                if c2==w3d.HLOD_LOD_ARRAY:
                    items=[];header=None;count=0
                    for c3,b3,k3 in chunks(b2):
                        if c3==w3d.HLOD_SUB_OBJECT_ARRAY_HEADER:
                            header=b3;continue
                        if c3==w3d.HLOD_SUB_OBJECT:
                            # Some stock files retain dangling collision helpers
                            # (notably the Pathfinder's toe boxes). Omit those.
                            if cstr(b3[4:]).upper() not in render_objects:continue
                            count+=1
                        items.append(w3d.chunk(c3,b3,k3))
                    items.append(w3d.chunk(w3d.HLOD_SUB_OBJECT,struct.pack('<I',bone or 0)+w3d.name(name+'.EUGEAr',32)))
                    b2=w3d.chunk(w3d.HLOD_SUB_OBJECT_ARRAY_HEADER,struct.pack('<I',count+1)+header[4:])+b''.join(items)
                new.append(w3d.chunk(c2,b2,kids))
            out.append(w3d.chunk(c,rewrite(b''.join(new)),True))
        elif c==0x740:
            # Collision helpers are render objects too. Rename their containers
            # along with the meshes so infantry remain selectable in the game.
            ref=cstr(b[8:40]);b=b[:8]+w3d.name(name+'.'+ref.split('.',1)[-1],32)+b[40:]
            out.append(w3d.chunk(c,b,children))
        else:out.append(w3d.chunk(c,b,children))
    out.insert(0,m._mesh('EUGEAR',**gear.data(),texture='eucoal_gear.tga',shadow=True,shader=w3d.OPAQUE_SHADER,mapper_args=None))
    (OUT/(name+'.w3d')).write_bytes(b''.join(out))
    print(name,country,'rig',parent,'equipment bone',bone)


def main():
    im=Image.new('RGB',(32,32),(45,50,53));d=ImageDraw.Draw(im)
    d.rectangle((0,16,15,31),fill=(98,111,102));d.rectangle((16,16,31,31),fill=(36,83,105));d.rectangle((16,0,31,15),fill=(17,22,27))
    im.save(TEX/'eucoal_gear.tga')
    for row in ROSTER:make(*row)


if __name__=='__main__':main()

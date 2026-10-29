"""Complete original Russia faction assets. Blender -b -t 2 -P scripts/models/russia/build.py.
All visible geometry is authored here; common EU code provides mathematical mesh,
UV baking and W3D serialization only. No stock visible meshes are imported.
"""
from pathlib import Path
import sys,math,json,struct,hashlib
import bpy,bmesh
from mathutils import Matrix,Vector,Quaternion
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];sys.path.insert(0,str(HERE.parent));sys.path.insert(0,str(HERE))
import original_compacts as oc
import engineer as kit
import w3d,tiger,puls
from baking import bake_paint as russia_bake
from blender_kit import box,cylinder,new_object,mesh_data,textured,load_image
from coalition_ground import shell
BUILD=ROOT/'build/faction-assets/russia';TEX=ROOT/'resources/macos/GameData/Art/TexturesHD';OUT=ROOT/'resources/macos/GameData/Art/W3D'
oc.ATLAS='ruatlas.tga';oc.TRACK='rutrack.tga'
STEEL,PLATE,VENT,LOCKER,HATCH,HUB,RUBBER,TREAD,IRON,GLASS,TUBE,TARP,CONCRETE,CAUTION,LAMP,DOOR=range(16)
ATLAS='ruatlas.tga';HOUSE='ruhouse.tga'
REGISTRY={}

class Asset(oc.Vehicle):
 bake_paint=russia_bake
 def __init__(self,name,role,parent,building=False):
  super().__init__(name);self.role=role;self.parent=parent;self.building=building;self.spin_axes={};self.skeleton=None;self.required=[]
 def mesh(self,name,bm,tile=STEEL,bone='CHASSIS',cap_axis=None,cap_tile=None,recalc=True):
  if self.building and name=='SLAB' and tile==CONCRETE:tile=TARP
  obj=super().mesh(name,bm,tile,bone,cap_axis,cap_tile,recalc)
  obj['russia_material_tile']=tile
  if self.building:
   n,b,o,t,k=self.parts[-1];self.parts[-1]=(n,b,o,'rubuild_atlas.tga',k)
  # Broad painted surfaces receive continuous projection, without miniature panels.
  if tile==STEEL:
   uv=obj.data.uv_layers.active;vs=[v.co for v in obj.data.vertices];lo=[min(p[i] for p in vs) for i in range(3)];hi=[max(p[i] for p in vs) for i in range(3)]
   for poly in obj.data.polygons:
    drop=max(range(3),key=lambda i:abs(poly.normal[i]));axes=[i for i in range(3) if i!=drop]
    for li in poly.loop_indices:
     co=obj.data.vertices[obj.data.loops[li].vertex_index].co
     uv.data[li].uv=(.003+(co[axes[0]]-lo[axes[0]])/max(.01,hi[axes[0]]-lo[axes[0]])*.244,.753+(co[axes[1]]-lo[axes[1]])/max(.01,hi[axes[1]]-lo[axes[1]])*.244)
  if tile==GLASS and name=='CANOPY' and self.name in ('RUSU35','RUSU25','RUMI28'):
   lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
   for poly in obj.data.polygons:
    for li in poly.loop_indices:
     co=obj.data.vertices[obj.data.loops[li].vertex_index].co
     u=(co.x-lo[0])/max(.001,hi[0]-lo[0]);v=(co.z-lo[2])/max(.001,hi[2]-lo[2])
     obj.data.uv_layers.active.data[li].uv=((1+.12+.76*u)/4,1-(2+.88-.76*v)/4)
  return obj
 def beam(self,name,a,b,width=.18,tile=IRON,bone='CHASSIS'):
  bm=bmesh.new();a,b=Vector(a),Vector(b);direction=b-a
  bmesh.ops.create_cube(bm,size=1,matrix=Matrix.Translation((a+b)/2)@direction.to_track_quat('X','Z').to_matrix().to_4x4()@Matrix.Diagonal((direction.length,width*2,width*2,1)))
  return self.mesh(name,bm,tile,bone)
 def house(self,name,corners,bone='CHASSIS'):
  o=self.patch(name,corners,STEEL,bone);n,b,o,t,k=self.parts[-1];self.parts[-1]=(n,b,o,HOUSE,'house')
  for uv in o.data.uv_layers.active.data:uv.uv=(.5,.5)
 def prism(self,name,profile,y0,y1,tile=STEEL,bone='CHASSIS'):
  bm=bmesh.new();kit.prism_xz(bm,profile,y0,y1);return self.mesh(name,bm,tile,bone)
 def loft(self,name,stations,tile=STEEL,bone='CHASSIS',axis='X',segments=12):
  aircraft=self.name in ('RUSU35','RUSU25','RUMI28')
  bm=bmesh.new();tiger.loft(bm,stations,axis,max(20,segments) if aircraft else segments);obj=self.mesh(name,bm,tile,bone)
  if aircraft:
   for poly in obj.data.polygons:poly.use_smooth=True
  return obj
 def gun(self,length=13,r=.4,at=(0,0,0),bone='BARREL'):
  x,y,z=at;self.cyl('GUN',(x+length/2,y,z),r,length,STEEL,'X',bone,IRON)
  self.cyl('EVAC',(x+length*.57,y,z),r*1.6,1.8,PLATE,'X',bone,IRON)
  self.cyl('MUZZLE',(x+length,y,z),r*1.23,.8,IRON,'X',bone,IRON)
  self.cyl('BORE',(x+length+.42,y,z),r*.78,.03,IRON,'X',bone,IRON)
  self.bone('MUZZLE01',(x+length+.5,y,z),bone);self.bone('MUZZLEFX01',(x+length+.5,y,z),bone)
 def add_smoke(self):
  present={b[0] for b in self.bones}
  for i,p in enumerate(((-4,0,6),(1,2,4),(0,-2,4)),1):
   if f'SMOKE0{i}' not in present:self.bone(f'SMOKE0{i}',p)
 def finish(self):
  polish(self);self.add_smoke();world={'CHASSIS':Matrix.Identity(4)}
  for n,p,at,q in self.bones:world[n]=world[p]@Matrix.Translation(at)@(Quaternion((q[3],*q[:3])) if q else Quaternion()).to_matrix().to_4x4()
  for n,b,o,t,k in self.parts:o.matrix_world=world[b]
  # Bake one assembled object per bone/material, avoiding hundreds of tiny
  # per-object bake passes while retaining wheel/supply/hide mesh contracts.
  gathered={}
  for n,b,o,t,k in self.parts:
   unique=n if n.startswith(('TREADS','TIRE','MISSILEUPGRADE','SUPPLY')) else ''
   material=int(o.get('russia_material_tile',-1))
   gathered.setdefault((b,t,k,unique,material),[]).append((n,o))
  combined=[]
  for (b,t,k,unique,material),items in gathered.items():
   n=items[0][0];o=kit.join([o for _,o in items],n) if len(items)>1 else items[0][1]
   o['russia_material_tile']=material;combined.append((n,b,o,t,k))
  self.parts=combined
  self.bake_paint()
  groups={}
  for n,b,o,t,k in self.parts:
   unique=n if n.startswith(('TREADS','TIRE','MISSILEUPGRADE','SUPPLY')) else ''
   groups.setdefault((b,t,k,unique),[]).append((n,o))
  parts=[];used=set()
  for (b,t,k,_),items in groups.items():
   base=('HOUSECOLOR' if k=='house' else items[0][0].upper())[:12];n=base;i=1
   while n in used:n=base[:10]+str(i);i+=1
   used.add(n);o=kit.join([o for _,o in items],n) if len(items)>1 else items[0][1];o.name=n;parts.append((n,b,o,t,k))
  self.parts=parts;variants=[];triangles=0
  suffixes=('','_D','_E','_N','_DN','_EN') if self.building else ('','_D')
  for suffix in suffixes:
   m=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
   for n,p,at,q in self.bones:ids[n]=m.bone(n,ids[p],at,rotation=q)
   for n,b,o,t,k in parts:
    tex=t.replace('.tga','_d.tga') if ('D' in suffix or 'E' in suffix) and t==self.name.lower()+'_paint.tga' else t
    kw={}
    if k in ('house','decal'):kw=dict(shadow=False,shader=w3d.ALPHA_TEST_SHADER)
    if k=='track':kw=dict(shadow=False,mapper_args=puls.TREAD_MAPPER)
    data=mesh_data(o)
    if 'E' in suffix:
     # Settled wreck silhouette, distinguishable from a functioning base.
     data['verts']=[(x,y,z*.38) for x,y,z in data['verts']]
    m.mesh(n,ids[b],**data,texture=tex,**kw)
    if not suffix:triangles+=len(data['tris'])
   if self.spins:m.animate(21,30,{ids[b]:tiger.spin(21,turns) for b,turns in self.spins.items()})
   m.save(str(OUT/(self.name+suffix+'.w3d')));variants.append(self.name+suffix)
  for n,b,o,t,k in parts:
   o.matrix_world=world[b]
   if k=='house':kit.team_colour([o])
   else:textured(o,load_image(str(TEX/t)));o.active_material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.95
  bpy.context.view_layer.update();points=[o.matrix_world@Vector(p) for _,_,o,_,_ in parts for p in o.bound_box]
  dims=[max(v[i] for v in points)-min(v[i] for v in points) for i in range(3)]
  bpy.ops.wm.save_as_mainfile(filepath=str(BUILD/(self.name+'.blend')))
  render(self.name,parts)
  record={'model':self.name,'role':self.role,'suggested_inherited_object':self.parent,'variants':variants,'bones':[{'name':n,'parent':p,'position':at,'rotation':q} for n,p,at,q in self.bones],'animations':[self.name+'.'+self.name] if self.spins else [],'dimensions':dims,'triangles':triangles,'meshes':len(parts),'texture_files':sorted({p[3] for p in parts}|{self.name.lower()+'_paint_d.tga'}),'preview':str((BUILD/(self.name+'.png')).relative_to(ROOT)),'blend':str((BUILD/(self.name+'.blend')).relative_to(ROOT)),'generation_command':f'/Applications/Blender.app/Contents/MacOS/Blender -b -t 2 -P scripts/models/russia/build.py -- {self.name}','geometry':'Original authored visible geometry; mathematical mesh primitives only.'}
  REGISTRY[self.name]=record;(BUILD/(self.name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print('RUSSIA_ASSET',self.name,triangles,len(parts),flush=True)

def render(name,parts):
 scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=720;scene.render.resolution_y=540;scene.render.resolution_percentage=100
 scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-.2
 world=bpy.data.worlds.new('Russian faction review');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.20,.21,.18,1);world.node_tree.nodes['Background'].inputs[1].default_value=.9;scene.world=world
 sun=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN'));sun.data.energy=2.4;sun.rotation_euler=(.65,.15,.5);scene.collection.objects.link(sun)
 cam=bpy.data.objects.new('camera',bpy.data.cameras.new('camera'));cam.data.type='ORTHO';scene.collection.objects.link(cam);scene.camera=cam;bpy.context.view_layer.update()
 points=[o.matrix_world@Vector(c) for _,_,o,_,_ in parts for c in o.bound_box];lo=Vector([min(v[i] for v in points) for i in range(3)]);hi=Vector([max(v[i] for v in points) for i in range(3)]);mid=(lo+hi)/2;size=max(hi-lo)
 cam.location=mid+Vector((1,1.25,.95)).normalized()*size*3;cam.rotation_euler=(mid-cam.location).to_track_quat('-Z','Y').to_euler();local=[cam.rotation_euler.to_quaternion().inverted()@(p-mid) for p in points]
 cam.data.ortho_scale=max(max(v.x for v in local)-min(v.x for v in local),(max(v.y for v in local)-min(v.y for v in local))*4/3)*1.16
 scene.render.filepath=str(BUILD/(name+'.png'));bpy.ops.render.render(write_still=True)

# Common original chassis details; each vehicle supplies its own proportions and silhouette.
def tracked(a,L=13,Y=5.8,H=4.2,n=6):
 profile=[(-L+.8,.4),(L-1.5,.4),(L,2.2),(L-.8,H-.35),(-L+1,H),(-L-.2,2.0)]
 for side in (-1,1):
  band=puls.tread_band('TREADSL' if side>0 else 'TREADSR',side,profile,(Y-1.05,Y+1.05));a.parts.append((band.name,'CHASSIS',band,'rutrack.tga','track'))
  for i in range(n):
   x=-L+2+(2*L-4)*i/(n-1);a.cyl('ROADWHEEL',(x,side*Y,2.0),1.6,1.76,IRON,'Y',cap=HUB);a.cyl('WHEELHUB',(x,side*(Y+1.03),2),.72,.22,STEEL,'Y',cap=HUB)
  a.prism('FENDER',[(-L, H), (L,H),(L-1,H+.7),(-L+1,H+.7)],side*(Y-1.25),side*(Y+1.22),STEEL)

def wheel(a,n,at,r=2.3,w=1.6):
 oc.tire(a,n,at,r,w);x,y,z=at;a.cyl(f'HUB{n}',(0,math.copysign(w*.52,y),0),r*.47,.22,STEEL,'Y',f'TIRE{n:02}',HUB)

def armoured_hull(a,L=13,W=5.7,z=4.3,roof=6.5):
 a.body('HULL',[(-L,2.4,3.2,roof-.8,roof, W*.7,W,W*.82),(-L+3,2,3.1,roof-.5,roof+.15,W*.75,W,W*.85),(L-5,2.2,3.4,roof-.6,roof+.1,W*.72,W,W*.82),(L,3.3,3.7,z,z+.25,W*.6,W*.83,W*.7)])
 for s in (-1,1):
  a.house('HOUSECOLOR', [(-L+1,s*(W+.02),4.2),(-L+5,s*(W+.02),4.2),(-L+5,s*(W+.02),5.25),(-L+1,s*(W+.02),5.25)])
 a.patch('ENGINE',[(-L+1,-W*.7,roof+.17),(-L+5,-W*.7,roof+.17),(-L+5,W*.7,roof+.17),(-L+1,W*.7,roof+.17)],VENT)
 oc.lamps(a,L-.3,4.4,W*.64)

def turret(a,pos=(0,0,6.2),L=5,W=4.4,H=3):
 t=a.bone('TURRET',pos);a.cyl('TURRETRING',(0,0,.1),W,.5,IRON,bone=t)
 bm=bmesh.new();shell(bm,[(-L,.2,.5,H*.65,H,W*.6,W*.75,W*.48),(-L*.4,.2,.5,H*.9,H+.3,W*.65,W,W*.72),(L*.6,.3,.6,H*.6,H*.8,W*.6,W*.85,W*.62),(L,.65,.75,H*.45,H*.55,W*.45,W*.5,W*.32)]);a.mesh('TURRET',bm,STEEL,t)
 a.cyl('HATCH',(-1,-W*.35,H+.45),1.2,.25,HATCH,bone=t)
 for s in (-1,1):
  for i in range(3):a.box('ERA',(-L*.2+i*1.6,s*(W*.9)-.45,H*.55),(1-L*.2+i*1.6,s*(W*.9)+.45,H*.55+.4),PLATE,t,bevel=.08)
 a.box('OPTIC',(1.3,-1,H*.7),(2.2,1,H+.5),GLASS,t)
 return t

def t90():
 a=Asset('RUT90','Main battle tank','ChinaTankBattleMaster');tracked(a);armoured_hull(a);t=turret(a,(-.3,0,6.1),5.5,4.8,2.8)
 b=a.bone('BARREL',(4.6,0,1.9),t);a.gun(14,.38,bone=b)
 for s in (-1,1):
  for x in range(-9,9,3):a.box('SKIRT',(x,s*6.9,3.2),(x+2.7,s*7.18,5.1),PLATE)
  for i in range(3):a.cyl('SMOKETUBE',(.3+i*.7,s*4.2,1.5),.32,1.25,IRON,'X',t,IRON)
 a.cyl('CUPOLA',(-2,1.6,3.15),1.15,.5,STEEL,bone=t);a.beam('AERIAL',(-3.5,-2.5,2.6),(-3.7,-2.5,8),.07,IRON,t)
 return a

def bmp3():
 a=Asset('RUBMP3','Autocannon infantry carrier','AmericaVehicleHumvee');tracked(a,L=12.5,Y=5.6,H=3.8);armoured_hull(a,L=12.5,W=5.5,z=4.8,roof=6.3);t=turret(a,(1,0,6.4),3.5,3.2,1.9);b=a.bone('BARREL',(2.4,0,1.2),t);a.gun(10,.34,bone=b)
 a.cyl('COAX',(6,1,1.2),.19,8,IRON,'X',t);a.bone('MUZZLE02',(10,1,1.2),t)
 for s in (-1,1):
  for x in (-8,-4):a.box('ROOFHATCH',(x,s*.4,6.35),(x+2.6,s*3.8,6.63),HATCH)
  a.box('SKIRT',(-11,s*6.6,3.45),(10.5,s*6.8,4.35),STEEL)
 a.bone('EXITSTART',(-8,0,1));a.bone('EXITEND',(-18,0,0));return a

def bmpt():
 # Original T-90 running gear reused beneath a narrow unmanned twin-cannon turret.
 a=Asset('RUBMPT','BMPT twin-cannon assault support','AmericaTankCrusader')
 tracked(a);armoured_hull(a)
 t=a.bone('TURRET',(-.6,0,6.4));a.cyl('TURRETRING',(0,0,.1),3.2,.5,IRON,bone=t)
 a.prism('GUNHOUSE',[(-4,.2),(2.5,.2),(3,1.7),(1.2,3.4),(-3.2,3.1)],-2.8,2.8,STEEL,t)
 b=a.bone('BARREL',(2.4,0,1.7),t)
 for side in (-1,1):
  y=side*.72
  a.box('BREECH',(-2.8,y-.34,-.35),(.5,y+.34,.5),PLATE,b,bevel=.08)
  a.cyl('AUTOCANNON',(5.5,y,.18),.19,11,IRON,'X',b,IRON)
  a.cyl('MUZZLEBRAKE',(11,y,.18),.29,.8,IRON,'X',b,IRON)
  a.box('AMMOBOX',(-3.5,side*3.1-.55,.6),(-.2,side*3.1+.55,2.1),LOCKER,t,bevel=.1)
  for x in (-9,-5,-1,3,7):a.box('SIDEERA',(x,side*6.5-.35,3.9),(x+3,side*6.5+.35,5.25),PLATE,bevel=.12)
  a.cyl('GLLAUNCHER',(8,side*3.8,6.1),.36,3.5,IRON,'X',cap=IRON)
 a.bone('MUZZLE01',(11.4,.72,.18),b);a.bone('MUZZLE02',(11.4,-.72,.18),b);a.bone('MUZZLEFX01',(11.4,0,.18),b)
 a.bone('GRENADE01',(9.8,3.8,6.1))
 a.box('SENSOR',(-2,-.7,3.1),(-.5,.7,4.5),PLATE,t,bevel=.15)
 a.box('SENSORGLASS',(-.49,-.5,3.6),(-.45,.5,4.25),GLASS,t)
 a.beam('AERIAL',(-3,2,2.8),(-3.2,2,7.0),.065,IRON,t)
 return a

def rocket():
 a=Asset('RUROCKET','Original unguided rocket projectile','GenericTankShell')
 a.cyl('BODY',(0,0,0),.22,3.2,STEEL,'X',cap=IRON)
 a.cyl('NOSE',(1.7,0,0),.18,.3,IRON,'X',cap=IRON)
 for side in (-1,1):
  a.box('FIN',(-1.6,side*.35-.04,-.15),(-.9,side*.35+.04,.15),IRON)
  a.box('FINV',(-1.6,-.15,side*.35-.04),(-.9,.15,side*.35+.04),IRON)
 return a

def msta():
 a=Asset('RUMSTA','Long-range self-propelled artillery','ChinaVehicleInfernoCannon');tracked(a,L=15,Y=6,H=4.5,n=7);armoured_hull(a,L=15,W=6,z=5,roof=6.8)
 t=a.bone('TURRET',(-3,0,6.7));a.cyl('TURRETRING',(0,0,.2),5.1,.6,IRON,bone=t)
 a.prism('GUNHOUSE',[(-7,.5),(5,.5),(5,5.6),(2.8,7.8),(-6.2,7.8)],-5.3,5.3,STEEL,t)
 b=a.bone('BARREL',(4.9,0,4.6),t);a.gun(23,.57,bone=b)
 a.box('GUNSHIELD',(3.8,-1.7,3),(5.9,1.7,6.2),PLATE,t,bevel=.3)
 for s in (-1,1):
  a.box('LOCKER',(-5.5,s*5.25,2.2),(-.2,s*5.7,5.5),LOCKER,t,bevel=.15)
  a.beam('RAIL',(-5.6,s*4.6,8.2),(1.8,s*4.6,8.2),.12,IRON,t)
 a.cyl('HATCH',(-1.5,1.8,7.95),1.45,.35,HATCH,bone=t);return a

def tos():
 a=Asset('RUTOS','Short-range assault barrage','ChinaVehicleNukeLauncher');tracked(a,L=13,Y=6,H=4.3);armoured_hull(a,L=13,W=5.9,z=4.7,roof=6.1)
 t=a.bone('TURRET',(-1,0,6));a.cyl('TURRETRING',(0,0,.2),3.6,.5,IRON,bone=t)
 b=a.bone('BARREL',(0,0,2.6),t,rotation=(0,math.sin(-.08),0,math.cos(-.08)))
 a.box('CRADLE',(-2,-3,.1),(2,3,2.8),PLATE,t,bevel=.25)
 a.box('LAUNCHER',(-6.5,-5,-1),(6.5,5,4),STEEL,b,bevel=.35)
 a.box('LAUNCHFACE',(6.52,-4.7,-.7),(6.68,4.7,3.7),IRON,b)
 for row in range(3):
  for col in range(8):
   y=-4.1+col*1.17;z=-.15+row*1.36;a.cyl('ROCKETRIM',(6.77,y,z),.49,.2,STEEL,'X',b,IRON);a.cyl('BORE',(6.89,y,z),.37,.035,IRON,'X',b)
   a.bone(f'WEAPONA{row*8+col+1:02}',(7.1,y,z),b)
 a.bone('MUZZLE01',(7.1,0,1),b);a.bone('MUZZLEFX01',(7.1,0,1),b)
 return a

def tunguska():
 a=Asset('RUTUNG','Gun and missile air defence','ChinaTankGattling');tracked(a,L=13.5,Y=5.8,H=4.4,n=6);armoured_hull(a,L=13.5,W=5.7,z=4.9,roof=6.8)
 t=turret(a,(0,0,6.8),4.2,3.8,3);b=a.bone('BARREL',(2.8,0,2.6),t)
 for s in (-1,1):
  a.box('GUNPOD',(-2,s*4.7-.8,-.6),(2,s*4.7+.8,.65),PLATE,b,bevel=.2)
  for z in (-.18,.26):a.cyl('AA_BARREL',(5,s*4.7,z),.23,7,IRON,'X',b)
  a.box('MISSILERACK',(-3.5,s*5.2-.5,1.2),(2,s*5.2+.5,1.8),IRON,b)
  for z in (1.8,2.7):
   for y in (s*4.9,s*5.7):a.cyl('MISSILE',(0,y,z),.36,7,STEEL,'X',b,IRON)
  a.bone('MUZZLE0'+('1' if s==1 else '2'),(8.6,s*4.7,0),b);a.bone('WEAPONA0'+('1' if s==1 else '2'),(3.6,s*5.2,2.3),b)
 a.bone('MUZZLEFX01',(8.6,4.7,0),b);a.cyl('TRACKRADAR',(4.1,0,2.8),1.3,1,PLATE,'X',t)
 r=a.bone('RADAR',(-3,0,5),t);a.box('RADARPOST',(-.35,-.35,-1),(.35,.35,1.7),IRON,r);a.box('RADARPANEL',(-.45,-3,1),(.45,3,3.5),PLATE,r,bevel=.2);a.spins[r]=1
 return a

def truck_base(a,supply=False):
 L=15 if supply else 10
 for i,x in enumerate((9,-4,-10) if supply else (6.4,-6.4)):
  for j,s in enumerate((-1,1)):wheel(a,i*2+j+1,(x,s*4.8,2.6),2.6,1.7)
 a.box('FRAME',(-L,-3.7,2.5),(L,3.7,3.6),IRON)
 if supply:
  a.prism('CAB',[(5.7,3.5),(14,3.5),(13.3,9.1),(11.3,10.1),(6,10.1)],-4.4,4.4,STEEL)
  a.box('BED',(-15,-4.6,4),(5,4.6,5),STEEL,bevel=.15)
  for s in (-1,1):a.box('BEDWALL',(-15,s*4.5,4.8),(5,s*4.85,7.4),PLATE)
  for i,x in enumerate((-12,-6,0)):
   a.box(f'SUPPLY{i+1:02}',(x-2,-3.7,5),(x+2,3.7,8.2),TARP,bevel=.18)
   for y in (-3,3):a.beam('STRAP',(x-2,y,8.3),(x+2,y,8.3),.09,IRON)
  a.patch('WINDSCREEN',[(13.81,-3.9,6.1),(13.81,3.9,6.1),(13.46,3.9,8.8),(13.46,-3.9,8.8)],GLASS)
 else:
  a.prism('BODY',[(-9,3.5),(9.6,3.5),(9,5.7),(5.1,6.7),(3,9),(-7.8,9),(-9,7.5)],-4.1,4.1,STEEL)
  a.patch('WINDSCREEN',[(5.21,-3.68,6.75),(5.21,3.68,6.75),(3.35,3.68,8.75),(3.35,-3.68,8.75)],GLASS)
 for s in (-1,1):
  if supply:a.patch('SIDEGLASS',[(6.9,s*4.43,6.7),(11.8,s*4.43,6.7),(11.1,s*4.43,9.4),(6.9,s*4.43,9.4)],GLASS)
  else:
   for x in (-6,-2):a.patch('SIDEGLASS',[(x,s*4.13,6.3),(x+2.5,s*4.13,6.3),(x+2.5,s*4.13,8.3),(x,s*4.13,8.3)],GLASS)
  a.house('HOUSECOLOR',[(6 if supply else -7,s*(4.46 if supply else 4.14),4.6),(10 if supply else -3,s*(4.46 if supply else 4.14),4.6),(10 if supply else -3,s*(4.46 if supply else 4.14),5.4),(6 if supply else -7,s*(4.46 if supply else 4.14),5.4)])
  a.box('STEP',(-6,s*4.2,2.8),(4,s*5,3.1),IRON)
  for x in ((9,-4,-10) if supply else (6.4,-6.4)):a.prism('FENDER',[(x-3.1,4.1),(x-2.2,5.4),(x+2.2,5.4),(x+3.1,4.1),(x+3.1,4.5),(x+2.2,5.75),(x-2.2,5.75),(x-3.1,4.5)],s*4.0,s*5.8,STEEL)
 oc.lamps(a,14 if supply else 9.4,5,3.3);a.box('BUMPER',((14 if supply else 9.4),-4.5,3.1),((15 if supply else 10.4),4.5,3.8),IRON)

def tigr():
 a=Asset('RUTIGR','Armed reconnaissance vehicle','AmericaVehicleHumvee');truck_base(a);t=a.bone('TURRET',(-1,0,9));a.cyl('RING',(0,0,.2),1.7,.4,IRON,bone=t);a.box('GUNCRADLE',(-.7,-.5,.4),(.5,.5,1.9),PLATE,t,bevel=.12);b=a.bone('BARREL',(.4,0,1.5),t);a.gun(4.5,.17,bone=b)
 a.beam('ANTENNA',(-7,-3.8,8.8),(-7.5,-3.8,13),.045)
 a.cyl('RADARMAST',(-5,0,10.0),.24,2.0,IRON)
 a.box('RADARPANEL',(-5.4,-2.5,10.7),(-4.9,2.5,12.4),PLATE,bevel=.1)
 a.patch('RADARFACE',[(-4.88,-2.3,10.85),(-4.88,2.3,10.85),(-4.88,2.3,12.25),(-4.88,-2.3,12.25)],VENT)
 a.bone('EXITSTART',(-6,0,1));a.bone('EXITEND',(-14,0,0));return a

def supply():
 a=Asset('RUSUP','Supply collection truck','ChinaVehicleSupplyTruck');truck_base(a,True);a.bone('SUPPLYDOCK',(9,0,0));return a

def engineer():
 a=Asset('RUENG','Armoured engineer vehicle','ChinaVehicleDozer');tracked(a,L=11,Y=5.3,H=3.9);armoured_hull(a,L=11,W=5.2,z=4.6,roof=5.7)
 a.prism('CAB',[(-6,5.7),(1,5.7),(1,9),(-1,10),(-6,10)],-.2,4.5,STEEL);a.box('CABGLASS',(.99,.5,7.1),(1.05,3.8,8.7),GLASS)
 for s in (-1,1):a.beam('BLADEARM',(3,s*4,3),(13,s*5,2),.45)
 a.prism('BLADE',[(11.7,.4),(13.2,.4),(12.9,1.3),(11.9,3.9),(10.6,5.3),(9.9,5.3),(11.3,2.5)],-8,8,STEEL)
 a.box('CUTTINGEDGE',(12.9,-8.1,.2),(13.6,8.1,.75),IRON)
 a.beam('CRANE',(-7,-3.2,5.8),(-2,-3.2,14),.6,PLATE);a.beam('CRANEBOOM',(-2,-3.2,14),(7,-3.2,13),.4,PLATE);a.beam('CABLE',(7,-3.2,13),(7,-3.2,9),.05);a.bone('FXBUILD',(13,0,1));return a

def wing(a,name,outline,z=.4,thickness=.35,tile=STEEL,bone='CHASSIS'):
 bm=bmesh.new();lo=[bm.verts.new((x,y,z-thickness/2)) for x,y in outline];hi=[bm.verts.new((x,y,z+thickness/2)) for x,y in outline];bm.faces.new(list(reversed(lo)));bm.faces.new(hi)
 for i in range(len(lo)):j=(i+1)%len(lo);bm.faces.new((lo[i],lo[j],hi[j],hi[i]))
 return a.mesh(name,bm,tile,bone)

def jet(attack=False):
 a=Asset('RUSU25' if attack else 'RUSU35','Ground-attack aircraft' if attack else 'Air-superiority fighter','AmericaJetRaptor')
 if attack:
  stations=[(-18,0,4,1.5,1.3,2.5),(-10,0,4.4,2,2,2.5),(0,0,4.7,2.2,2.5,2.5),(8,0,4.6,2.1,2.2,2.4),(15,0,4.3,.75,1,2),(17.3,0,4.1,.1,.15,2)]
 else:stations=[(-22,0,4,1.5,1.1,2.5),(-14,0,4.4,3.4,1.8,2.5),(-3,0,4.9,3.5,2,2.5),(8,0,4.9,2.2,1.9,2.5),(18,0,4.3,.8,.8,2),(22,0,4.2,.08,.08,2)]
 a.loft('FUSELAGE',stations)
 for s in (-1,1):
  if attack:outline=[(7,s*1.4),(3,s*6),(-2,s*18),(-7,s*18),(-6,s*3)]
  else:outline=[(6,s*2),(0,s*9),(-9,s*18.5),(-14,s*17.5),(-11,s*3)]
  wing(a,'WING',outline,4.7,.5)
  wing(a,'TAILPLANE',[(-12,s*1),(-14,s*(9 if attack else 11)),(-20,s*10),(-18,s*1)],4.7,.35)
  a.loft('ENGINE',[(-19,s*(2.8 if attack else 3.5),3.1,1.1,1.15,2),(-9,s*(2.9 if attack else 3.5),3.3,1.6,1.55,2),(2 if attack else 5,s*(2.9 if attack else 3.5),3.9,1.25,1.3,2)],STEEL)
  a.cyl('EXHAUST',(-19.2,s*(2.8 if attack else 3.5),3.1),1.06,.6,IRON,'X',cap=IRON)
  a.cyl('INTAKE',((2.1 if attack else 5.1),s*(2.9 if attack else 3.5),3.9),1.13,.2,IRON,'X',cap=IRON)
  for i,y in enumerate((7,11,15)):
   yy=s*y;x=-2 if attack else -6;a.box('PYLON',(x-2,yy-.3,3),(x+1.5,yy+.3,4.5),IRON)
   a.cyl('WEAPON',(x,yy,2.7),.35 if attack else .26,5.5,PLATE,'X',cap=IRON)
   for b in ('WEAPONA','WEAPONB'):a.bone(f'{b}{(0 if s==1 else 3)+i+1:02}',(x+2.8,yy,2.7))
  if attack:a.house('HOUSECOLOR',[(-4.9,s*9,5.01),(-2.0,s*9,5.01),(-2.6,s*13,5.01),(-5.5,s*13,5.01)])
  else:a.house('HOUSECOLOR', [(-8,s*11,5.01),(-5,s*11,5.01),(-8,s*15,5.01),(-11,s*15,5.01)])
 if attack:a.prism('TAILFIN',[(-21,4.4),(-14,4.4),(-15,11.5),(-18,12.5)],-.24,.24,STEEL)
 else:
  for s in (-1,1):a.prism('TAILFIN',[(-20,4.5),(-10,4.5),(-12,12.5),(-16,13.6)],s*3.2-.22,s*3.2+.22,STEEL)
 a.loft('CANOPY',[(2,0,6,1.45,.1,2),(4,0,7,1.4,1.5,2),(7,0,7.15,1.15,1.25,2),(10,0,6.2,.55,.1,2)],GLASS)
 a.beam('CANOPYFRAME',(5.5,-1.44,6.6),(5.5,1.44,6.6),.075,IRON)
 a.bone('MUZZLE01',(13,1,4));a.bone('MUZZLEFX01',(13,1,4));a.bone('EXHAUST01',(-19,-3,3));a.bone('EXHAUST02',(-19,3,3))
 for i,p in enumerate(((8,0,1.6),(-5,-3,1.6),(-5,3,1.6)),1):
  a.beam('GEAR',(p[0],p[1],3),p,.13);a.cyl('GEARWHEEL',p,.65,.45,RUBBER,'Y',cap=HUB)
 return a

def mi28():
 a=Asset('RUMI28','Heavy attack helicopter','AmericaVehicleComanche')
 a.loft('FUSELAGE',[(-13,0,4.6,.7,1,2.5),(-8,0,4.7,2.2,2.4,2.6),(-2,0,4.7,3,3.0,2.6),(7,0,4.3,2.6,2.8,2.6),(13,0,3.6,1.4,1.6,2.5),(15,0,3.1,.5,.7,2)])
 a.loft('TAILBOOM',[(-29,0,7.1,.5,.6,2),(-12,0,4.7,.9,1.3,2.5),(-7,0,4.7,1.4,1.5,2.5)])
 a.prism('TAILFIN',[(-29,6),(-24,6),(-25,12),(-28,14)],-.4,.4,STEEL)
 wing(a,'TAILPLANE',[(-22,-7),(-20,-7),(-18,7),(-20,7)],7.3,.25)
 for s in (-1,1):
  a.loft('ENGINE',[(-8,s*3,6.3,1,1,2.5),(-3,s*3,6.8,1.5,1.5,2.5),(2,s*3,6.8,1.1,1.1,2.5)],STEEL)
  a.cyl('ENGINEEXH',(-8.2,s*3,6.3),.95,.45,IRON,'X',cap=IRON)
  wing(a,'STUBWING',[(2,s*2),(1,s*9),(-3,s*9),(-4,s*2)],4.7,.4)
  for i,y in enumerate((5.4,8)):
   yy=s*y;a.cyl('ROCKETPOD',(0,yy,3.4),.8,4.7,PLATE,'X',cap=IRON)
   for j in range(4):
    ang=j*math.pi/2;a.cyl('TUBEBORE',(2.39,yy+math.cos(ang)*.39,3.4+math.sin(ang)*.39),.2,.05,IRON,'X')
   a.bone(f'WEAPONA{1+i+(0 if s==1 else 2):02}',(2.5,yy,3.4));a.bone(f'WEAPONB{1+i+(0 if s==1 else 2):02}',(2.5,yy,3.4))
  a.beam('GEARSTRUT',(-2,s*2.2,3),(-3,s*4.8,1.1),.18);a.cyl('GEARWHEEL',(-3,s*4.8,1.1),1,.8,RUBBER,'Y',cap=HUB)
  a.house('HOUSECOLOR',[(-6,s*2.8,4),(-3,s*3.04,4),(-3,s*3.04,5),(-6,s*2.8,5)])
 for start,end,z in ((3,7,7.3),(8,11.8,6)):
  a.loft('CANOPY',[(start,0,z-.7,1.4,.3,2),(start+.8,0,z,1.4,1.1,2),(end-.4,0,z-.25,1.1,.9,2),(end,0,z-.7,.8,.15,2)],GLASS)
 a.cyl('ROTORMAST',(-1,0,9.8),.35,4,IRON);r=a.bone('PROPELLER01',(-1,0,11.8));a.cyl('ROTORHUB',(0,0,0),1.5,.7,IRON,bone=r)
 for i in range(5):
  ang=i*2*math.pi/5;c,s=math.cos(ang),math.sin(ang);outline=[(x*c-y*s,x*s+y*c) for x,y in ((1,-.35),(20,-.65),(20,.6),(3,.9))];wing(a,'ROTOR',outline,0,.09,IRON,r)
 a.spins[r]=1;q=(math.sin(math.pi/4),0,0,math.cos(math.pi/4));tail=a.bone('PROPELLER02',(-27,-.8,8),rotation=q)
 for ang in (0,math.pi/2):
  c,s=math.cos(ang),math.sin(ang);wing(a,'TAILROTOR',[(x*c-y*s,x*s+y*c) for x,y in ((-3,-.25),(3,-.25),(3,.25),(-3,.25))],0,.1,IRON,tail)
 a.spins[tail]=2;t=a.bone('TURRET',(12,0,1.8));a.cyl('CHINGUN',(0,0,0),1,.5,IRON,bone=t);b=a.bone('BARREL',(.4,0,-.3),t);a.gun(4,.22,bone=b);a.bone('TURRETFX01',(4.8,0,-.3),t)
 a.bone('FLARE01',(-7,-2,5));a.bone('FLARE02',(-7,2,5));a.bone('MISSILEUPGRADE',(0,0,0));return a

# Industrial concrete and steel architecture, shared modular construction language.
def slab(a,x,y,L,W,z=0,h=.5,tile=CONCRETE):a.box('SLAB',(x-L/2,y-W/2,z),(x+L/2,y+W/2,z+h),tile)
def hall(a,x,y,L,W,H,doors=False):
 # Gabled industrial hall, projecting buttresses and deep front opening.
 if doors:
  for side in (-1,1):a.prism('WALL',[(x-L/2,.5),(x+L/2,.5),(x+L/2,H),(x,H+5),(x-L/2,H)],y+side*(W/2-2),y+side*W/2,CONCRETE)
  a.box('BACKWALL',(x-L/2,y-W/2,.5),(x-L/2+2,y+W/2,H),CONCRETE)
  a.box('INTERIOR',(x-L/2+2.05,y-W/2+2,.5),(x-L/2+2.1,y+W/2-2,H),IRON)
  slab(a,x,y,L-4,W-4,.5,.1,IRON)
 else:a.prism('HALL',[(x-L/2,.5),(x+L/2,.5),(x+L/2,H),(x,H+5),(x-L/2,H)],y-W/2,y+W/2,CONCRETE)
 a.prism('ROOF',[(x-L/2-1,H),(x,H+5.7),(x+L/2+1,H),(x+L/2+1,H+.6),(x,H+6.4),(x-L/2-1,H+.6)],y-W/2-1,y+W/2+1,STEEL)
 for s in (-1,1):
  for k in range(5):
   xx=x-L/2+3+k*(L-6)/4;a.box('RIB',(xx-.6,y+s*W/2-.5,.5),(xx+.6,y+s*W/2+.5,H+1),STEEL)
  for k in range(4):
   xx=x-L/2+5+k*(L-10)/4;a.box('WINDOW',(xx,y+s*(W/2+.05),H*.55),(xx+4,y+s*(W/2+.15),H*.75),GLASS)
 if doors:
  # Exits face +X. Opening is only a dark façade on these purpose-built game scale shells.
  for sy in (-1,1):a.box('SLIDEDOOR',(x+L/2+.03,y+sy*W*.42-W*.07,.55),(x+L/2+.8,y+sy*W*.42+W*.07,H*.72),DOOR)
  a.box('DOORLINTEL',(x+L/2+.2,y-W*.37,H*.72),(x+L/2+1.2,y+W*.37,H*.72+1.2),CAUTION)
  for sy in (-1,1):a.box('DOORJAMB',(x+L/2+.2,y+sy*W*.36-1,.5),(x+L/2+1.1,y+sy*W*.36+1,H*.73),STEEL)
  # Visible service doors slide outside an empty centre aperture in implementation.
 else:a.box('DOOR',(x+L/2+.1,y-2,.5),(x+L/2+.25,y+2,7),DOOR)
 a.house('HOUSECOLOR',[(x+L/2+.3,y-W*.38,H*.79),(x+L/2+.3,y+W*.38,H*.79),(x+L/2+.3,y+W*.38,H*.91),(x+L/2+.3,y-W*.38,H*.91)])

def bunker(a,x,y,L,W,H):
 a.prism('BUNKER',[(x-L/2-3,.5),(x+L/2+3,.5),(x+L/2,H),(x-L/2,H)],y-W/2,y+W/2,CONCRETE)
 slab(a,x,y,L+2,W+2,H,.8,STEEL)
 for s in (-1,1):
  for xx in (x-L/3,x,x+L/3):a.box('SLIT',(xx-2,y+s*(W/2+.08),H*.6),(xx+2,y+s*(W/2+.17),H*.75),GLASS)
 a.box('DOOR',(x+L/2+1.1,y-2,.5),(x+L/2+1.3,y+2,6.5),DOOR)
 a.house('HOUSECOLOR',[(x-L/3,y-W/2-.19,H*.25),(x+L/3,y-W/2-.19,H*.25),(x+L/3,y-W/2-.19,H*.37),(x-L/3,y-W/2-.19,H*.37)])

def mast(a,x,y,z=0,H=24,radar=True):
 a.cyl('MASTBASE',(x,y,z+1),2,2,IRON);a.cyl('MAST',(x,y,z+H/2),.32,H,IRON)
 for sx,sy in ((-3,-3),(-3,3),(3,-3),(3,3)):a.beam('MASTBRACE',(x+sx,y+sy,z),(x,y,z+H*.75),.12)
 if radar:a.box('RADAR',(x-.5,y-4,z+H-3),(x+.5,y+4,z+H+1),PLATE,bevel=.2)
 else:
  for zz in (.5,.7,.9):a.beam('ANTENNA',(x-4*zz,y,z+H*zz),(x+4*zz,y,z+H*zz),.11)

def tanks(a,x,y,n=2,r=5,H=12):
 for i in range(n):
  xx=x+i*(r*2+2);a.cyl('TANK',(xx,y,H/2+.5),r,H,PLATE,segments=16);a.cyl('TANKLIP',(xx,y,H+.6),r+ .3,.4,IRON,segments=16);a.cyl('PIPE',(xx,y,H+1.5),.7,2,IRON)
  a.box('TANKLABEL',(xx+r+.05,y-1.5,H*.4),(xx+r+.2,y+1.5,H*.65),CAUTION)

def roof_vents(a,x,y,z,n=3):
 for i in range(n):a.box('VENT',(x+i*5,y,z),(x+3.2+i*5,y+4,z+1.8),VENT,bevel=.2)

def building(role):
 defs={'command':('RUCC','Command centre','AmericaCommandCenter'), 'power':('RUPWR','Power station','AmericaPowerPlant'),'barracks':('RUBARR','Barracks','AmericaBarracks'),'supply':('RUSUPPLY','Supply centre','ChinaSupplyCenter'),'factory':('RUFACT','War factory','AmericaWarFactory'),'airfield':('RUAIR','Airfield','AmericaAirfield'),'tech':('RUTECH','Military institute','AmericaStrategyCenter'),'income':('RUINCOME','Logistics ministry','AmericaSupplyDropZone'),'ground':('RUGDEF','Cannon emplacement','ChinaBunker'),'aa':('RUADEF','Radar missile defence','AmericaPatriotBattery'),'super':('RUSUPER','Strategic missile silo','ChinaNuclearMissileLauncher')}
 name,title,parent=defs[role];a=Asset(name,title,parent,True)
 if role=='command':
  slab(a,0,0,96,88);bunker(a,-12,-5,56,44,18);hall(a,-17,29,38,21,15,True);bunker(a,17,-8,18,25,32);mast(a,17,-8,33,25);roof_vents(a,-34,-16,19)
  a.bone('EXITSTART',(-18.8,34.5,.3));a.bone('EXITEND',(50.9,34.5,.3));tanks(a,-34,-31,2,4,10)
 elif role=='power':
  slab(a,0,0,62,58);hall(a,-11,0,29,39,15);tanks(a,12,-11,2,7,21);roof_vents(a,-20,-10,21)
  for x,y,H in ((-18,15,42),(-8,15,34)):a.cyl('STACK',(x,y,H/2),2,H,CONCRETE,segments=12);a.cyl('STACKBAND',(x,y,H*.7),2.15,3,STEEL,segments=12)
 elif role=='barracks':
  slab(a,0,0,76,66);hall(a,-13,-8,44,31,15);hall(a,-12,22,37,20,11);mast(a,-32,18,0,22,False)
  for y in (-18,-10,-2):a.box('BARRIER',(18,y,.6),(29,y+2,2.4),CONCRETE)
  a.bone('EXITSTART',(10,0,.3));a.bone('EXITEND',(43,0,.3))
 elif role=='supply':
  slab(a,0,0,100,84);hall(a,-24,6,44,53,19,True);slab(a,20,-20,45,35,.52,.08,CAUTION)
  for x,y,z in ((-32,-28,1),(-19,-28,1),(-32,-28,7),(-35,36,1),(-23,36,1)):
   a.box('CARGO',(x-5,y-4,z),(x+5,y+4,z+6),LOCKER,bevel=.2)
  for n,p in [('DOCKSTART',(47,-20,.3)),('DOCKACTION',(22,-20,.3)),('DOCKEND',(48,-20,.3)),('EXITSTART',(20,20,.3)),('EXITEND',(55,20,.3))]:a.bone(n,p)
  for i,(x,y) in enumerate(((67,-35),(67,0),(67,35),(35,57),(0,57),(-35,57),(-67,25),(-67,-15),(-40,-60)),1):a.bone(f'DOCKWAITING{i:02}',(x,y,.3))
 elif role=='factory':
  slab(a,0,0,112,124);hall(a,-11,-28,72,54,26,True);hall(a,-20,34,53,38,20);roof_vents(a,-38,22,27);tanks(a,20,35,2,6,16)
  for n,p in [('EXITSTART',(-10,-30,.3)),('EXITEND',(53,-30,.3)),('DOCKSTART',(66.9,16.2,.3)),('DOCKACTION',(46.5,16.2,.3)),('DOCKEND',(73.1,16.2,.3))]:a.bone(n,p)
  for i,p in enumerate(((116,45),(116,99),(68,99),(14,99),(-39,99),(-96,99),(-94,40),(-94,-18),(-94,-66)),1):a.bone(f'DOCKWAITING{i:02}',(*p,.3))
 elif role=='airfield':
  slab(a,0,0,224,148,.05,.35)
  for y in (-49,-13):
   slab(a,27,y,168,23,.42,.08,IRON)
   for x in range(-38,105,18):slab(a,x,y,8,.85,.52,.03,LAMP)
  # Four original hardened open shelters at established USA parking slots.
  for x,y,front in ((-87,-49,'X'),(-87,-13,'X'),(-21,52,'Y'),(9,52,'Y')):
   if front=='X':
    for s in (-1,1):a.prism('SHELTER',[(-107,.5),(-69,.5),(-69,12),(-107,12)],y+s*12,y+s*15,CONCRETE)
    a.prism('SHELTERROOF',[(-107,10),(-69,10),(-69,14),(-107,14)],y-12,y+12,CONCRETE);a.box('SHELTERBACK',(-108,y-15,.5),(-105,y+15,14),CONCRETE)
    a.house('HOUSECOLOR',[(-68.8,y-10,10),(-68.8,y+10,10),(-68.8,y+10,11.5),(-68.8,y-10,11.5)])
   else:
    for s in (-1,1):a.prism('SHELTER',[(x+s*12,.5),(x+s*15,.5),(x+s*15,12),(x+s*12,12)],35,70,CONCRETE)
    slab(a,x,52,27,37,11,3,CONCRETE);a.box('SHELTERBACK',(x-15,68,.5),(x+15,71,12),CONCRETE)
    a.house('HOUSECOLOR',[(x-10,34.8,10),(x+10,34.8,10),(x+10,34.8,11.5),(x-10,34.8,11.5)])
  bunker(a,-82,42,34,26,11);a.cyl('TOWER',(-91,50,22),3,40,CONCRETE,segments=8);a.cyl('TOWERCAB',(-91,50,43),7,7,GLASS,segments=8);a.cyl('TOWERROOF',(-91,50,47),8,.9,STEEL,segments=8);mast(a,-91,50,47,12)
  slab(a,66.7,41.6,28,28,.48,.03,IRON);slab(a,60.7,41.6,2,18,.55,.04,LAMP);slab(a,72.7,41.6,2,18,.55,.04,LAMP);slab(a,66.7,41.6,14,2,.55,.04,LAMP)
  import air_base
  for n,p,yaw in air_base.BONES:a.bone(n,p,rotation=w3d._yaw_quaternion(yaw))
 elif role=='tech':
  slab(a,0,0,96,86);bunker(a,-17,2,52,54,21);bunker(a,20,12,24,30,31);roof_vents(a,-34,-12,22);mast(a,20,12,32,25)
  a.cyl('DISHBASE',(-12,10,25),5,5,STEEL,segments=12);a.cyl('DISH',(-12,10,29),10,1.8,PLATE,segments=16);a.beam('DISHFEED',(-12,10,29),(-10,10,36),.22)
  tanks(a,-30,-32,3,4,9)
 elif role=='income':
  slab(a,0,0,86,76);hall(a,-12,4,55,44,19,True);hall(a,-23,-27,31,17,12)
  for x,y in ((28,-20),(28,0),(24,24)):a.box('CONTAINER',(x-6,y-7,.5),(x+6,y+7,9),LOCKER,bevel=.3)
  mast(a,-28,12,25,16,False);a.bone('SUPPLY', (0,0,0))
 elif role=='ground':
  slab(a,0,0,28,28);bunker(a,0,0,18,18,5);t=turret(a,(0,0,6),3.7,3.6,2.4);b=a.bone('BARREL',(3,0,1.5),t);a.gun(9,.5,bone=b)
 elif role=='aa':
  slab(a,0,0,38,34);bunker(a,-5,0,18,22,7);t=a.bone('TURRET',(3,0,7));b=a.bone('BARREL',(0,0,2),t,rotation=(0,math.sin(-.4),0,math.cos(-.4)))
  a.cyl('MOUNT',(0,0,0),3,3,IRON,bone=t)
  for i,(y,z) in enumerate(((-2,0),(2,0),(-2,3),(2,3)),1):a.cyl('TUBE',(0,y,z),1.2,12,STEEL,'X',b,IRON);a.bone(f'WEAPONA{i:02}',(6.2,y,z),b)
  a.bone('MUZZLE01',(6.5,0,1.5),b);a.bone('MUZZLEFX01',(6.5,0,1.5),b);mast(a,-11,0,7,18)
 elif role=='super':
  slab(a,0,0,114,114);a.cyl('SILO',(5,0,2),29,4,CONCRETE,segments=20);a.cyl('SILORIM',(5,0,4.2),24,1.2,IRON,segments=20);a.cyl('SILOCOVER',(5,0,5.1),22,1,STEEL,segments=20)
  for s in (-1,1):a.box('COVERRAIL',(-22,s*26,3),(44,s*28,5),IRON)
  slab(a,5,0,2,41,5.64,.05,CAUTION);bunker(a,-35,-27,25,35,17);mast(a,-37,-27,18,27);tanks(a,25,40,2,6,15)
  for n,p in [('WEAPONA01',(5,0,7)),('MUZZLE01',(5,0,7)),('NUKE',(5,0,7)),('ROCKPOS',(5,0,7)),('STEAM01',(-15,0,6)),('STEAM02',(25,0,6)),('SMOKE01',(5,0,6))]:a.bone(n,p)
 return a

BUILDERS={'RUBMPT':bmpt,'RUROCKET':rocket,'RUTIGR':tigr,'RUT90':t90,'RUBMP3':bmp3,'RUTUNG':tunguska,'RUMSTA':msta,'RUTOS':tos,'RUENG':engineer,'RUSUP':supply,'RUSU35':lambda:jet(False),'RUSU25':lambda:jet(True),'RUMI28':mi28}
for _key,_name in {'command':'RUCC','power':'RUPWR','barracks':'RUBARR','supply':'RUSUPPLY','factory':'RUFACT','airfield':'RUAIR','tech':'RUTECH','income':'RUINCOME','ground':'RUGDEF','aa':'RUADEF','super':'RUSUPER'}.items():BUILDERS[_name]=lambda key=_key:building(key)


def polish(a):
 """Large readable surface details, kept original and cheap in mass battles."""
 if a.name in ('RUSU35','RUSU25','RUMI28'):
  from aviation_v2 import apply
  apply(a)
 if a.name in ('RUTIGR','RUSUP'):
  truck=a.name=='RUSUP'
  for side in (-1,1):
   y=side*(4.47 if truck else 4.16)
   spans=((6.4,12.0),) if truck else ((-7.1,-3.15),(-2.65,2.0))
   for left,right in spans:
    for z in (4.3,8.8 if not truck else 9.6):a.beam('DOORSEAM',(left,y,z),(right,y,z),.042,IRON)
    for x in (left,right):a.beam('DOORSEAM',(x,y,4.3),(x,y,8.8 if not truck else 9.6),.042,IRON)
    a.box('HANDLE',(left+.45,y-side*.08,5.84),(left+1.45,y+side*.13,6.02),IRON)
    for z in (4.9,7.9):a.box('HINGE',(right-.25,y-side*.08,z),(right+.1,y+side*.15,z+.24),PLATE)
   x=12.3 if truck else 3.8
   a.beam('MIRRORARM',(x,side*4.1,7),(x,side*5.7,7.7),.10)
   a.box('MIRROR',(x-.25,side*5.7-.35,7.1),(x+.25,side*5.7+.35,8.5),IRON,bevel=.1)
   if not truck:
    a.beam('ROOFRAIL',(-7.4,side*3.5,9.15),(1.7,side*3.5,9.15),.075)
    a.beam('WINDFRAME',(5.22,side*3.8,6.75),(3.28,side*3.8,8.85),.075)
  if truck:
   a.beam('WINDSCREENBAR',(13.87,0,6.1),(13.51,0,8.8),.09)
   a.patch('GRILLE',[(14.03,-2.8,4),(14.03,2.8,4),(13.89,2.8,5.8),(13.89,-2.8,5.8)],VENT)
  else:
   a.beam('WINDSCREENBAR',(5.24,0,6.76),(3.39,0,8.77),.10)
   a.beam('WINDFRAME',(5.23,-3.8,6.73),(5.23,3.8,6.73),.07)
   a.beam('WINDFRAME',(3.29,-3.8,8.87),(3.29,3.8,8.87),.07)
   a.patch('GRILLE',[(9.50,-2.5,4.1),(9.50,2.5,4.1),(9.17,2.5,5.35),(9.17,-2.5,5.35)],VENT)
   for side in (-1,1):
    a.beam('HOODSEAM',(8.9,side*2.7,5.83),(5.4,side*2.7,6.65),.04,IRON)
    a.patch('HOODVENT',[(5.65,side*1.7,6.59),(6.9,side*1.7,6.30),(6.9,side*.45,6.30),(5.65,side*.45,6.59)],VENT)
   a.cyl('SPARETIRE',(-9.2,0,6.3),2.1,1.1,RUBBER,'X',cap=HUB)
   a.cyl('SPAREHUB',(-9.8,0,6.3),.8,.2,STEEL,'X',cap=HUB)
 if a.name in ('RUT90','RUBMPT','RUBMP3','RUTUNG','RUMSTA','RUTOS'):
  L={'RUT90':13,'RUBMPT':13,'RUBMP3':12.5,'RUTUNG':13.5,'RUMSTA':15,'RUTOS':13}[a.name]
  W={'RUT90':5.7,'RUBMPT':5.7,'RUBMP3':5.5,'RUTUNG':5.7,'RUMSTA':6,'RUTOS':5.9}[a.name]
  roof={'RUT90':6.5,'RUBMPT':6.5,'RUBMP3':6.3,'RUTUNG':6.8,'RUMSTA':6.8,'RUTOS':6.1}[a.name]
  for side in (-1,1):
   for x in (-L+2,-L+5):a.box('DECKLOCKER',(x,side*(W-1.5)-.45,roof+.17),(x+2.5,side*(W-1.5)+.45,roof+.70),LOCKER,bevel=.08)
   a.beam('TOWCABLE',(-L+.6,side*(W+.15),4.5),(-L+6,side*(W+.15),4.5),.095)
   for x in (L-1,-L+.2):
    a.cyl('TOWEYE',(x,side*W*.6,3.5),.40,.25,IRON,'Y',cap=IRON)
   a.beam('FENDEREDGE',(-L+.8,side*(W+1.05),4.7),(L-1,side*(W+1.05),4.7),.055,PLATE)
  # Hand-authored broad glacis seams and raised driver periscope.
  a.beam('GLACISSEAM',(L-4.9,-W*.7,roof+.14),(L-4.9,W*.7,roof+.14),.06,IRON)
  a.box('DRIVERSCOPE',(L-6,-.8,roof+.17),(L-4.8,.8,roof+.53),GLASS)
 if a.name=='RUT90':
  for side in (-1,1):
   for x in (4.5,7.0):a.box('GLACISERA',(x,side*2.9-.75,5.15),(x+1.8,side*2.9+.75,5.46),PLATE,bevel=.08)
   a.cyl('FUELDRUM',(-13.2,side*3.4,5.5),1.2,3.8,STEEL,'Y',cap=HATCH)
   for y in (side*2.4,side*4.4):a.cyl('DRUMBAND',(-13.2,y,5.5),1.23,.15,IRON,'Y')
 if a.name in ('RUSU35','RUSU25'):
  # Control surface separations remain visible from the game camera.
  for side in (-1,1):
   if a.name=='RUSU35':a.beam('FLAPSEAM',(-11,side*5,4.98),(-10,side*13,4.98),.035,IRON)
   a.beam('TAILSEAM',(-17,side*3,4.9),(-18,side*8,4.9),.035,IRON)

 # The bounded final ground/architecture detail pass keeps every prior bone.
 from ground_building_detail import apply as ground_detail
 ground_detail(a)

def main():
 BUILD.mkdir(parents=True,exist_ok=True)
 selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(BUILDERS)
 for name in selected:
  bpy.ops.wm.read_factory_settings(use_empty=True);BUILDERS[name]().finish()
if __name__=='__main__':main()

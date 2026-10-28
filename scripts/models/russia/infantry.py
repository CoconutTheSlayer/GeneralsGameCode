"""Russia infantry entry point; current exports use the original articulated rig.
The old stock-rig builder is retained below as source history only. Its rigid
limbs cannot track translated stock hand/foot bones and must not be exported.
"""
from pathlib import Path
import sys,math,json,struct
import bpy,bmesh
from mathutils import Matrix,Vector,Quaternion
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE));sys.path.insert(0,str(ROOT/'scripts/factions/europe'))
from build import *
from stock_data import asset
def chunks(data):
 p=0
 while p<len(data):
  c,s=struct.unpack_from('<II',data,p);n=s&0x7fffffff
  yield c,data[p+8:p+8+n],bool(s>>31)
  p+=8+n
def cstr(data):return data.split(b'\0')[0].decode('latin1')

class Infantry(Asset):
 def mesh(self,name,bm,tile=STEEL,bone='CHASSIS',cap_axis=None,cap_tile=None,recalc=True):
  obj=super().mesh(name,bm,tile,bone,cap_axis,cap_tile,recalc)
  if tile in (CONCRETE,CAUTION):
   lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
   for p in obj.data.polygons:
    axis=max(range(3),key=lambda i:abs(p.normal[i]));axes=[i for i in range(3) if i!=axis]
    for li in p.loop_indices:
     co=obj.data.vertices[obj.data.loops[li].vertex_index].co;u=(co[axes[0]]-lo[axes[0]])/max(.001,hi[axes[0]]-lo[axes[0]]);v=(co[axes[1]]-lo[axes[1]])/max(.001,hi[axes[1]]-lo[axes[1]])
     obj.data.uv_layers.active.data[li].uv=((tile%4+.07+.86*u)/4,1-(tile//4+.93-.86*v)/4)
  return obj
 def __init__(self,name,role,parent):
  super().__init__(name,role,parent)
  self.rig=[];self.ids={};self.world={};self.skeleton_name='AIRNGR_SKL'
  for cid,data,_ in chunks(asset('AIRNGR_SKL.w3d')):
   if cid==w3d.HIERARCHY:
    for c,b,_ in chunks(data):
     if c==w3d.PIVOTS:
      for i in range(0,len(b),60):
       n=cstr(b[i:i+16]);parent,*at=struct.unpack_from('<i3f',b,i+16);q=struct.unpack_from('<4f',b,i+44);idx=len(self.rig)
       self.rig.append((n,parent,at,q));self.ids[n]=idx
       transform=Matrix.Translation(at)@Quaternion((q[3],*q[:3])).to_matrix().to_4x4();self.world[n]=(self.world[self.rig[parent][0]]@transform if parent>=0 else transform)
 def global_shape(self,name,bm,tile,bone):
  bmesh.ops.transform(bm,matrix=self.world[bone].inverted(),verts=bm.verts)
  obj=self.mesh(name,bm,tile,bone)
  if name in ('JACKET','HEAD','NOSE','EAR','HELMET','NECK'):
   for p in obj.data.polygons:p.use_smooth=True
  return obj
 def sphere(self,name,centre,scale,tile,bone):
  bm=bmesh.new();bmesh.ops.create_uvsphere(bm,u_segments=20,v_segments=12,radius=1,matrix=Matrix.Translation(centre)@Matrix.Diagonal((*scale,1)));return self.global_shape(name,bm,tile,bone)
 def loft(self,name,stations,tile=STEEL,bone='CHASSIS',axis='X',segments=16):
  obj=super().loft(name,stations,tile,bone,axis,segments)
  for poly in obj.data.polygons:poly.use_smooth=True
  return obj
 def posed_world(self,animation,frame=0):
  translations={};rotations={}
  for cid,data,_ in chunks(asset(animation+'.w3d')):
   if cid==w3d.ANIMATION:
    for c,b,_ in chunks(data):
     if c==w3d.ANIMATION_CHANNEL:
      first,last,dim,kind,bone,_=struct.unpack_from('<6H',b)
      selected=max(first,min(frame,last));values=struct.unpack_from('<'+'f'*dim,b,12+(selected-first)*dim*4)
      if kind<=2:translations.setdefault(bone,[0,0,0])[kind]=values[0]
      elif kind==6:rotations[bone]=values
  result={}
  for idx,(name,parent,at,q) in enumerate(self.rig):
   base=Matrix.Translation(at)@Quaternion((q[3],*q[:3])).to_matrix().to_4x4()
   rq=rotations.get(idx,(0,0,0,1));anim=Matrix.Translation(translations.get(idx,(0,0,0)))@Quaternion((rq[3],*rq[:3])).to_matrix().to_4x4()
   result[name]=(result[self.rig[parent][0]] if parent>=0 else Matrix.Identity(4))@base@anim
  return result
 def finish(self):
  for _,b,o,_,_ in self.parts:o.matrix_world=self.world[b]
  self.bake_paint();groups={}
  for n,b,o,t,k in self.parts:groups.setdefault((b,t,k),[]).append((n,o))
  parts=[];used=set()
  for (b,t,k),items in groups.items():
   n=items[0][0][:12].upper();i=1;original=n
   while n in used:n=original[:10]+str(i);i+=1
   used.add(n);o=kit.join([o for _,o in items],n) if len(items)>1 else items[0][1];o.name=n;parts.append((n,b,o,t,k))
  self.parts=parts;triangles=0
  for suffix in ('','_D'):
   name=self.name+suffix;m=w3d.Model(name);data=[]
   for n,b,o,t,k in parts:
    tex=t.replace('.tga','_d.tga') if suffix and t==self.name.lower()+'_paint.tga' else t
    kw=dict(shadow=False,shader=w3d.ALPHA_TEST_SHADER) if k in ('house','decal') else {}
    md=mesh_data(o);m.mesh(n,self.ids[b],**md,texture=tex,**kw)
    if not suffix:triangles+=len(md['tris'])
   for n,b,verts,normals,uvs,tris,tex,shadow,shader,*mapper in m.meshes:data.append(m._mesh(n,verts,normals,uvs,tris,tex,shadow,shader,*mapper))
   header=struct.pack('<II',w3d.HLOD_VERSION,1)+w3d.name(name)+w3d.name(self.skeleton_name)
   subs=w3d.chunk(w3d.HLOD_SUB_OBJECT_ARRAY_HEADER,struct.pack('<If',len(m.meshes),3.4028234663852886e38))
   for n,b,*_ in m.meshes:subs+=w3d.chunk(w3d.HLOD_SUB_OBJECT,struct.pack('<I',b)+w3d.name(name+'.'+n,32))
   data.append(w3d.chunk(w3d.HLOD,w3d.chunk(w3d.HLOD_HEADER,header)+w3d.chunk(w3d.HLOD_LOD_ARRAY,subs,True),True));(OUT/(name+'.w3d')).write_bytes(b''.join(data))
  self.world=self.posed_world('AIRNGR_STA',0)
  for n,b,o,t,k in parts:
   o.matrix_world=self.world[b]
   if k=='house':kit.team_colour([o])
   else:
    textured(o,load_image(str(TEX/t)))
    o.active_material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=.95
  bpy.context.view_layer.update();points=[o.matrix_world@Vector(p) for _,_,o,_,_ in parts for p in o.bound_box];dims=[max(v[i] for v in points)-min(v[i] for v in points) for i in range(3)]
  bpy.ops.wm.save_as_mainfile(filepath=str(BUILD/(self.name+'.blend')));render(self.name,parts)
  record={'model':self.name,'role':self.role,'suggested_inherited_object':self.parent,'variants':[self.name,self.name+'_D'],'bones':[{'name':n,'parent':self.rig[p][0] if p>=0 else None,'position':at,'rotation':q} for n,p,at,q in self.rig],'external_skeleton':'AIRNGR_SKL','animations':['AIRNGR_SKL.AIRNGR_IDA','AIRNGR_SKL.AIRNGR_RNA','AIRNGR_SKL.AIRNGR_ATA','AIRNGR_SKL.AIRNGR_DTA'],'animation_contract':'Use stock AmericaInfantryRanger draw animation mappings; every visible body and weapon mesh is original, rigid-bound to the unchanged installed Ranger hierarchy. All three infantry share this animation skeleton. Parent gameplay inheritance can differ only if Draw is replaced with Ranger animation mappings.','dimensions':dims,'triangles':triangles,'meshes':len(parts),'texture_files':sorted({p[3] for p in parts}|{self.name.lower()+'_paint_d.tga'}),'preview':str((BUILD/(self.name+'.png')).relative_to(ROOT)),'blend':str((BUILD/(self.name+'.blend')).relative_to(ROOT)),'generation_command':f'/Applications/Blender.app/Contents/MacOS/Blender -b -t 2 -P scripts/models/russia/infantry.py -- {self.name}','geometry':'Entirely original visible geometry; installed stock skeleton transforms only.'}
  (BUILD/(self.name+'.json')).write_text(json.dumps(record,indent=2)+'\n');print('RUSSIA_INFANTRY',self.name,triangles,len(parts),flush=True)

def soldier(name):
 kind={'RURIFLE':'rifle','RUKORNET':'kornet','RUCMDO':'commando'}[name]
 a=Infantry(name,{'rifle':'Rifle infantry','kornet':'Anti-tank missile team','commando':'Commando'}[kind],{'rifle':'AmericaInfantryRanger','kornet':'AmericaInfantryMissileDefender','commando':'AmericaInfantryColonelBurton'}[kind])
 pelvis=a.world['AIRNGR'].translation;spine=a.world['AIRNGR SPINE1'].translation;head=a.world['AIRNGR HEAD'].translation
 # Original continuous jacket and compact tactical vest, constructed in bind space.
 bm=bmesh.new();tiger.loft(bm,[(pelvis.z-.6,pelvis.x,pelvis.y,1.10,1.2,2.4),(pelvis.z+.1,pelvis.x,pelvis.y,1.20,1.3,2.4),(pelvis.z+1.6,pelvis.x,pelvis.y,1.10,1.64,2.3),(spine.z+.6,spine.x,spine.y,1.04,1.82,2.3),(spine.z+1.25,spine.x,spine.y,.80,1.24,2.2)],axis='Z',segments=16);a.global_shape('JACKET',bm,CONCRETE,'AIRNGR SPINE1')
 bm=bmesh.new();box(bm,(pelvis.x-.7,pelvis.y-1.35,pelvis.z-.6),(pelvis.x+.8,pelvis.y+1.35,pelvis.z+.45));a.global_shape('BELT',bm,IRON,'AIRNGR')
 bm=bmesh.new();box(bm,(spine.x+.75,spine.y-1.38,spine.z-.9),(spine.x+1.3,spine.y+1.38,spine.z+1));a.global_shape('VEST',bm,TARP,'AIRNGR SPINE1')
 for sy in (-1,0,1):
  bm=bmesh.new();box(bm,(spine.x+1.25,spine.y+sy*.84-.33,spine.z-.75),(spine.x+1.65,spine.y+sy*.84+.33,spine.z+.3));kit.bevel_sharp(bm,.1);a.global_shape('POUCH',bm,TARP,'AIRNGR SPINE1')
 bm=bmesh.new();box(bm,(spine.x-1.65,spine.y-1.1,spine.z-1),(spine.x-.7,spine.y+1.1,spine.z+1));kit.bevel_sharp(bm,.2);a.global_shape('BACKPACK',bm,TARP,'AIRNGR SPINE1')
 # Stock one-segment thigh / arm rig retains all installed locomotion animation.
 for side in ('L','R'):
  thigh=f'AIRNGR {side} THIGH';foot=f'AIRNGR {side} FOOT';upper=f'AIRNGR {side} UPPERA';hand=f'AIRNGR {side} HAND'
  L=(a.world[foot].translation-a.world[thigh].translation).length
  a.loft('TROUSER',[(.0,0,0,.79,.87,2.2),(L*.25,.06,0,.77,.79,2.2),(L*.45,-.05,0,.63,.65,2.2),(L*.51,-.1,0,.67,.65,2.2),(L*.70,0,0,.61,.61,2.2),(L-.3,0,0,.46,.49,2.3)],CONCRETE,thigh)
  a.box('THIGHPOCKET',(L*.18,-.30,.61),(L*.38,.39,.86),TARP,thigh,bevel=.14)
  a.box('KNEEPAD',(L*.46,-.77,-.48),(L*.61,-.57,.48),RUBBER,thigh,bevel=.16)
  a.loft('BOOT',[(0,0,0,.51,.54,2.5),(.65,.10,0,.63,.60,2.5),(1.04,.30,0,.77,.60,2.5)],IRON,foot)
  a.box('BOOTSOLE',(.96,-.42,-.65),(1.14,1.04,.65),RUBBER,foot,bevel=.12)
  for xx in (.25,.43,.61):a.beam('LACES',(xx,-.49,-.35),(xx,-.49,.35),.04,IRON,foot)
  L=(a.world[hand].translation-a.world[upper].translation).length
  a.loft('SLEEVE',[(0,0,0,.77,.77,2.2),(L*.2,0,0,.73,.72,2.2),(L*.48,.03,0,.59,.58,2.2),(L*.55,.02,0,.63,.63,2.2),(L*.76,0,0,.51,.51,2.2),(L-.10,0,0,.40,.42,2.3)],CONCRETE,upper)
  a.loft('CUFF',[(L-.25,0,0,.43,.45,2.3),(L-.02,0,0,.42,.44,2.3)],TARP,upper)
  a.loft('GLOVE',[(0,0,0,.42,.42,2.4),(.5,0,0,.41,.40,2.4),(1,0,0,.29,.32,2.3)],IRON,hand)
 # Helmet and face are independently authored ellipsoids; dark goggles read at RTS scale.
 centre=head+Vector((.1,0,.45));a.sphere('NECK',centre+Vector((-.10,0,-.92)),(.49,.48,.55),CAUTION,'AIRNGR HEAD')
 bm=bmesh.new();tiger.loft(bm,[(centre.z-1.08,centre.x+.1,centre.y,.38,.45,2),(centre.z-.82,centre.x+.1,centre.y,.65,.61,2),(centre.z-.25,centre.x,centre.y,.81,.79,2),(centre.z+.38,centre.x-.07,centre.y,.85,.79,2),(centre.z+.89,centre.x-.13,centre.y,.55,.54,2),(centre.z+1.04,centre.x-.13,centre.y,.17,.20,2)],axis='Z',segments=20);a.global_shape('HEAD',bm,CAUTION,'AIRNGR HEAD')
 a.sphere('HELMET',centre+Vector((-.13,0,.63)),(1.02,1.04,.68),STEEL,'AIRNGR HEAD')
 a.sphere('NOSE',centre+Vector((.84,0,.03)),(.26,.21,.30),CAUTION,'AIRNGR HEAD')
 for s in (-1,1):a.sphere('EAR',centre+Vector((-.05,s*.79,-.04)),(.20,.11,.35),CAUTION,'AIRNGR HEAD')
 bm=bmesh.new();box(bm,(centre.x+.72,centre.y-.69,centre.z+.15),(centre.x+.94,centre.y+.69,centre.z+.55));a.global_shape('GOGGLES',bm,GLASS,'AIRNGR HEAD')
 # Flexible chin strap, collar, shoulder webbing and field radio remain attached to the body rig.
 for s in (-1,1):
  for x0,x1,z0,z1 in ((-.2,.55,.20,-.72),(.55,.5,-.72,-.82)):
   bm=bmesh.new();start=centre+Vector((x0,s*.82,z0));end=centre+Vector((x1,s*.56,z1));direction=end-start
   bmesh.ops.create_cone(bm,cap_ends=True,segments=6,radius1=.065,radius2=.065,depth=direction.length,matrix=Matrix.Translation((start+end)/2)@direction.to_track_quat('Z','Y').to_matrix().to_4x4());a.global_shape('CHINSTRAP',bm,IRON,'AIRNGR HEAD')
  bm=bmesh.new();box(bm,(spine.x-.55,spine.y+s*1.05-.15,spine.z+.7),(spine.x+1.3,spine.y+s*1.05+.15,spine.z+.98));kit.bevel_sharp(bm,.07);a.global_shape('WEBBING',bm,TARP,'AIRNGR SPINE1')
 bm=bmesh.new();box(bm,(spine.x-1.6,spine.y+.9,spine.z+.1),(spine.x-.85,spine.y+1.45,spine.z+1.1));kit.bevel_sharp(bm,.07);a.global_shape('RADIO',bm,IRON,'AIRNGR SPINE1')
 # Original AK-family silhouette or shoulder-fired guided launcher.
 gun='BONE-GUN'
 if kind=='kornet':
  a.cyl('LAUNCHER',(2,0,.2),.71,9,STEEL,'X',gun,IRON);a.cyl('LAUNCHRIM',(6.45,0,.2),.88,.48,IRON,'X',gun,IRON)
  a.box('SIGHT',(-1,.7,.1),(1.2,1.3,1.4),PLATE,gun,bevel=.1);a.box('SIGHTLENS',(1.23,.78,.5),(1.3,1.2,1.1),GLASS,gun)
 else:
  a.box('RECEIVER',(-1.6,-.36,-.25),(2.5,.36,.42),IRON,gun,bevel=.08);a.prism('STOCK',[(-3.5,-.15),(-.9,-.15),(-.9,.35),(-3.5,.6)],-.3,.3,STEEL,gun)
  a.prism('MAGAZINE',[(.4,-.3),(1.2,-.3),(1.5,-1.7),(.7,-1.5)],-.26,.26,IRON,gun)
  a.cyl('BARREL',(4.5,0,.2),.17,4.8,IRON,'X',gun);a.box('HANDGUARD',(2.2,-.32,-.12),(4.6,.32,.52),STEEL,gun)
  if kind=='commando':a.cyl('SUPPRESSOR',(6.7,0,.2),.26,1.6,IRON,'X',gun);a.cyl('SCOPE',(.7,0,.94),.25,2.5,IRON,'X',gun);a.box('SCOPEMOUNT',(.1,-.2,.35),(.9,.2,.9),IRON,gun)
 # Small player-colour shoulder tabs, using the stock upper-arm bone transforms.
 for side in ('L','R'):
  b=f'AIRNGR {side} UPPERA';a.house('HOUSECOLOR',[(.3,-.77,-.38),(1.3,-.77,-.38),(1.3,-.77,.38),(.3,-.77,.38)],b)
 return a

if __name__=='__main__':
 import articulated as current
 selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['RURIFLE','RUKORNET','RUCMDO']
 for name in selected:
  bpy.ops.wm.read_factory_settings(use_empty=True)
  current.create(current,{'RURIFLE':'Rifleman','RUKORNET':'Spike','RUCMDO':'Commando'}[name]).finish()

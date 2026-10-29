"""Original Ukraine faction art. Run in Blender, no stock mesh imports.
Blender -b -t 4 -P scripts/models/ukraine/generate.py -- [MODEL ...]
Units face +X; bones are local to parents; all dimensions are game units.
"""
from pathlib import Path
import sys,math,json,hashlib
import bpy,bmesh
from mathutils import Vector,Matrix,Quaternion
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE))
sys.path.insert(0,str(HERE.parent))
import w3d,engineer as kit
from blender_kit import box,cylinder,new_object,mesh_data,textured,load_image
from coalition_ground import shell
TEX=ROOT/'resources/macos/GameData/Art/TexturesHD'
OUT=ROOT/'resources/macos/GameData/Art/W3D'
BUILD=ROOT/'build/faction-assets/ukraine'
for d in (TEX,OUT,BUILD):d.mkdir(parents=True,exist_ok=True)
COLORS={'airpaint':(.20,.235,.21,1),'paint':(.25,.29,.14,1),'darkpaint':(.13,.18,.095,1),'steel':(.14,.155,.12,1),'rubber':(.032,.035,.03,1),'glass':(.027,.090,.106,1),'lamp':(.82,.76,.49,1),'red':(.4,.045,.016,1),'concrete':(.33,.335,.30,1),'roof':(.18,.205,.17,1),'sand':(.37,.34,.19,1),'canvas':(.19,.23,.095,1),'skin':(.47,.31,.18,1),'uniform':(.205,.255,.12,1),'blue':(.10,.31,.58,1),'yellow':(.62,.5,.12,1),'white':(.65,.66,.55,1)}
class Asset:
 def __init__(self,name,key,label,role,base,building=False):
  self.name=name;self.key=key;self.label=label;self.role=role;self.base=base;self.building=building
  self.parts=[];self.bones=[];self.spins={};self.extra_animations={};self.notes=[]
 def bone(self,n,at=(0,0,0),parent='CHASSIS',yaw=0):
  self.bones.append((n.upper(),parent.upper(),at,yaw));return n.upper()
 def mesh(self,n,bm,s='paint',bone='CHASSIS',kind='solid'):
  if kind=='solid':bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
  obj=new_object(n,bm)
  if s=='paint' and self.name in ('UAF16','UATB2','UAMI24'):s='airpaint'
  import materials_v2
  materials_v2.project(self,obj,s,n)
  self.parts.append((n.upper(),bone.upper(),obj,s,kind));return obj
 def box(self,n,lo,hi,s='paint',bone='CHASSIS',bevel=0):
  bm=bmesh.new();box(bm,lo,hi)
  if bevel:kit.bevel_sharp(bm,bevel)
  return self.mesh(n,bm,s,bone)
 def cyl(self,n,at,r,length,s='steel',axis='Z',bone='CHASSIS',segments=12,r2=None):
  bm=bmesh.new()
  rot={'X':Matrix.Rotation(math.pi/2,4,'Y'),'Y':Matrix.Rotation(math.pi/2,4,'X'),'Z':Matrix.Identity(4)}[axis]
  bmesh.ops.create_cone(bm,cap_ends=True,segments=segments,radius1=r,radius2=r if r2 is None else r2,depth=length,matrix=Matrix.Translation(at)@rot)
  return self.mesh(n,bm,s,bone)
 def beam(self,n,a,b,r=.15,s='steel',bone='CHASSIS',square=False):
  a,b=Vector(a),Vector(b);delta=b-a
  bm=bmesh.new();rot=delta.to_track_quat('Z','Y').to_matrix().to_4x4()
  m=Matrix.Translation((a+b)*.5)@rot
  if square:bmesh.ops.create_cube(bm,size=1,matrix=m@Matrix.Diagonal((r*2,r*2,delta.length,1)))
  else:bmesh.ops.create_cone(bm,cap_ends=True,segments=8,radius1=r,radius2=r,depth=delta.length,matrix=m)
  return self.mesh(n,bm,s,bone)
 def prism(self,n,profile,y0,y1,s='paint',bone='CHASSIS'):
  bm=bmesh.new();kit.prism_xz(bm,profile,y0,y1);return self.mesh(n,bm,s,bone)
 def hull(self,n,sections,s='paint',bone='CHASSIS'):
  bm=bmesh.new();shell(bm,sections);return self.mesh(n,bm,s,bone)
 def patch(self,n,p,s='glass',bone='CHASSIS',house=False):
  bm=bmesh.new();bm.faces.new([bm.verts.new(a) for a in p]);bm.faces.new([bm.verts.new(a) for a in reversed(p)])
  return self.mesh(n,bm,s,bone,'house' if house else 'decal')
 def team(self,x0,x1,y,z,h=.7,bone='CHASSIS'):
  for sign in ((1,) if self.building else (-1,1)):self.patch('HOUSECOLOR',[(x0,sign*y,z),(x1,sign*y,z),(x1,sign*y,z+h),(x0,sign*y,z+h)],bone=bone,house=True)
 def flag(self,x,y,z,bone='CHASSIS'):
  for i,s in enumerate(('yellow','blue')):self.patch('IDENT',[(x,y,z+i*.35),(x+1.3,y,z+i*.35),(x+1.3,y,z+(i+1)*.35),(x,y,z+(i+1)*.35)],s,bone)
 def wheel(self,i,at,r=2.3,w=1.5):
  b=self.bone('TIRE%02d'%i,at);bm=bmesh.new();rings=[]
  for y,rr in [(-w*.5,r*.8),(-w*.32,r),(w*.32,r),(w*.5,r*.8)]:
   rings.append([bm.verts.new((math.cos(j*math.tau/12)*rr,y,math.sin(j*math.tau/12)*rr)) for j in range(12)])
  bm.faces.new(list(reversed(rings[0])));bm.faces.new(rings[-1])
  for a,c in zip(rings,rings[1:]):
   for j in range(12):bm.faces.new((a[j],a[(j+1)%12],c[(j+1)%12],c[j]))
  self.mesh(b,bm,'rubber',b)
  for sign in (-1,1):
   self.cyl(b,(0,sign*w*.51,0),r*.52,.13,'paint',axis='Y',bone=b)
   self.cyl(b,(0,sign*w*.57,0),r*.22,.22,'steel',axis='Y',bone=b,segments=8)
  # Discrete tread shoulders read at game distance without high-poly tyre meshes.
  for j in range(12):
   a=j*math.tau/12;dx,dz=math.cos(a)*r,math.sin(a)*r
   self.beam(b,(dx,-w*.34,dz),(dx,w*.34,dz),.10,'steel',b,square=True)
 def tracks(self,L=12,Y=5.4,W=2,H=3.5):
  profile=[(-L+.6,.35),(L-.9,.35),(L,1.6),(L-.6,H),(-L+.4,H),(-L-.4,1.7)]
  # Hollow track bands, with actual inset gap and visible wheels.
  for sign in (-1,1):
   bm=bmesh.new();outer=profile;inner=[(x*.96,1.8+(z-1.8)*.76) for x,z in profile]
   rings=[]
   for y,p in ((sign*Y-W/2,outer),(sign*Y+W/2,outer),(sign*Y-W/2,inner),(sign*Y+W/2,inner)):
    rings.append([bm.verts.new((x,y,z)) for x,z in p])
   n=len(profile)
   for k in range(n):
    j=(k+1)%n
    for a,b in ((0,1),(2,3),(0,2),(1,3)):bm.faces.new((rings[a][k],rings[a][j],rings[b][j],rings[b][k]))
   self.mesh('TREADSL' if sign>0 else 'TREADSR',bm,'rubber')
   for x in (-L*.79,-L*.47,-L*.14,L*.19,L*.52,L*.82):
    self.cyl('ROADWHEEL',(x,sign*(Y+W*.4),1.8),1.25,W*.5,'darkpaint',axis='Y')
    self.cyl('ROADHUB',(x,sign*(Y+W*.67),1.8),.48,.13,'steel',axis='Y',segments=8)
   for i in range(int(L*1.9)):
    x=-L+.6+i*1.0;self.box('TREADLINK',(x,sign*Y-W*.5,H-.12),(x+.21,sign*Y+W*.5,H+.11),'steel')
   self.prism('FENDER',[(-L+.4,H),(-L+.4,H+.55),(L-1,H+.55),(L,H+.1)],sign*Y-W*.56,sign*Y+W*.56)
 def hatch(self,at,r=1.1,bone='CHASSIS'):
  self.cyl('HATCHRIM',at,r+.1,.15,'steel',bone=bone);x,y,z=at
  self.cyl('HATCH',(x,y,z+.15),r,.20,'paint',bone=bone)
  self.beam('HANDLE',(x-.35,y,z+.35),(x+.35,y,z+.35),.11,'steel',bone)
 def lamps(self,x,z,y):
  for sign in (-1,1):
   self.box('LAMPGUARD',(x-.2,sign*y-.6,z-.4),(x+.2,sign*y+.6,z+.4),'steel')
   self.box('LIGHT',(x+.21,sign*y-.42,z-.27),(x+.25,sign*y+.42,z+.25),'lamp')
 def antenna(self,x,y,z,h=5):self.beam('ANTENNA',(x,y,z),(x-.3,y,z+h),.045)
 def world(self):
  world={'CHASSIS':Matrix.Identity(4)}
  for n,p,at,yaw in self.bones:world[n]=world[p]@Matrix.Translation(at)@(Matrix.Rotation(math.pi/2,4,'Y') if n=='PROPELLER' else Matrix.Rotation(math.pi/2,4,'X') if n=='TAILROTOR' else Matrix.Rotation(math.radians(yaw),4,'Z'))
  for _,b,o,_,_ in self.parts:o.matrix_world=world[b]
  return world
 def bake(self):
  import materials_v2
  return materials_v2.bake(self)
 def _bake_legacy(self):
  self.world();objects=[o for _,_,o,s,k in self.parts if k!='house']
  bpy.ops.object.select_all(action='DESELECT')
  for o in objects:o.select_set(True);o.data.uv_layers.new(name='PaintUV')
  bpy.context.view_layer.objects.active=objects[0];bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT');bpy.ops.uv.smart_project(angle_limit=.83,island_margin=.007);bpy.ops.object.mode_set(mode='OBJECT')
  scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.samples=6;scene.render.bake.margin=4
  scene.cycles.device='CPU';targets=[];damage=[];night=[]
  for name,b,o,s,k in self.parts:
   if k=='house':
    uv=o.data.uv_layers.new(name='PaintUV')
    for loop in uv.data:loop.uv=(.5,.5)
    continue
   mat=bpy.data.materials.new(name+'_paint');mat.use_nodes=True;t=mat.node_tree;t.nodes.clear();n=t.nodes;link=t.links.new
   geom=n.new('ShaderNodeNewGeometry')
   col=n.new('ShaderNodeRGB');col.outputs[0].default_value=COLORS[s]
   if s in ('paint','uniform','canvas'):
    grid=n.new('ShaderNodeVectorMath');grid.operation='SCALE';grid.inputs[3].default_value=(.85 if self.name in ('UAKOZAK','UADRONE') else 1.1) if not self.building else .12;link(geom.outputs['Position'],grid.inputs[0])
    snap=n.new('ShaderNodeVectorMath');snap.operation='FLOOR';link(grid.outputs[0],snap.inputs[0])
    tex=n.new('ShaderNodeTexNoise');tex.inputs['Scale'].default_value=.75;tex.inputs['Detail'].default_value=0;link(snap.outputs[0],tex.inputs['Vector'])
    ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
    ramp.color_ramp.elements[0].position=.32;ramp.color_ramp.elements[0].color=(.105,.15,.065,1)
    ramp.color_ramp.elements[1].position=.67;ramp.color_ramp.elements[1].color=(.345,.35,.19,1)
    ramp.color_ramp.elements.new(.46).color=COLORS[s]
    if self.name in ('UAKOZAK','UADRONE'):
     ramp.color_ramp.elements[0].color=(.18,.225,.13,1);ramp.color_ramp.elements[1].color=(.25,.29,.165,1);ramp.color_ramp.elements[2].color=(.305,.34,.215,1)
    link(tex.outputs['Fac'],ramp.inputs[0]);col=ramp
   noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.36 if self.name=='UACMD' else 9;noise.inputs['Detail'].default_value=3 if self.name=='UACMD' else 2;link(geom.outputs['Position'],noise.inputs['Vector'])
   grain=n.new('ShaderNodeMapRange');grain.inputs['To Min'].default_value=.58 if self.name=='UACMD' and s in ('concrete','roof','steel') else .85;grain.inputs['To Max'].default_value=1.20 if self.name=='UACMD' and s in ('concrete','roof','steel') else 1.09;link(noise.outputs['Fac'],grain.inputs[0])
   ao=n.new('ShaderNodeAmbientOcclusion');ao.samples=4 if self.name=='UACMD' else 16;ao.inputs['Distance'].default_value=3 if not self.building else 9
   shade=n.new('ShaderNodeMapRange');shade.inputs['To Min'].default_value=.4 if k!='decal' else .95;shade.inputs['To Max'].default_value=1.2;link(ao.outputs[0],shade.inputs[0])
   mult=n.new('ShaderNodeMath');mult.operation='MULTIPLY';link(shade.outputs[0],mult.inputs[0]);link(grain.outputs[0],mult.inputs[1])
   shadecol=n.new('ShaderNodeMixRGB');shadecol.blend_type='MULTIPLY';shadecol.inputs[0].default_value=1;link(col.outputs[0],shadecol.inputs[1]);link(mult.outputs[0],shadecol.inputs[2])
   scar=n.new('ShaderNodeMixRGB');scar.blend_type='MULTIPLY';scar.inputs[0].default_value=0;link(shadecol.outputs[0],scar.inputs[1]);scar.inputs[2].default_value=(.36,.32,.26,1);damage.append(scar)
   glow=n.new('ShaderNodeMixRGB');glow.inputs[0].default_value=0;link(scar.outputs[0],glow.inputs[1]);glow.inputs[2].default_value=(.75,.58,.20,1)
   if s in ('glass','lamp'):night.append(glow)
   emit=n.new('ShaderNodeEmission');link(glow.outputs[0],emit.inputs[0]);output=n.new('ShaderNodeOutputMaterial');link(emit.outputs[0],output.inputs[0]);target=n.new('ShaderNodeTexImage');n.active=target;targets.append(target)
   o.data.materials.clear();o.data.materials.append(mat)
   for p in o.data.polygons:p.material_index=0
  size=1024 if self.building or self.name in ('UAOPLOT','UABOHD','UAMI24','UABUK') else 512
  variants=['','_d']+(['_n','_dn'] if self.building else [])
  for suffix in variants:
   for node in damage:node.inputs[0].default_value=.82 if 'd' in suffix else 0
   for node in night:node.inputs[0].default_value=1 if 'n' in suffix else 0
   dest=bpy.data.images.new(self.name.lower()+suffix,size,size,alpha=False)
   for node in targets:node.image=dest
   bpy.ops.object.bake(type='EMIT',use_clear=True)
   dest.filepath_raw=str(TEX/(self.name.lower()+suffix+'.tga'));dest.file_format='TARGA';dest.save()
  return variants
 def finish(self):
  import polish_ground
  polish_ground.apply(self)
  for n,at in [('SMOKE01',(-3,0,4)),('SMOKE02',(0,2,3)),('SMOKE03',(1,-2,3))]:
   if n not in [b[0] for b in self.bones]:self.bone(n,at)
  self.bake();groups={}
  for n,b,o,s,k in self.parts:
   unique=b if b.startswith('TIRE') else n if n.startswith('TREADS') else ''
   groups.setdefault((b,k,unique),[]).append((n,o))
  self.parts=[(items[0][0] if k!='house' else 'HOUSECOLOR',b,kit.join([o for _,o in items],items[0][0]) if len(items)>1 else items[0][1],'house' if k=='house' else 'paint',k) for (b,k,u),items in groups.items()]
  self.world();triangles=0;variants=['','_D']+(['_E','_N','_DN','_EN'] if self.building else [])
  for suffix in variants:
   model=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
   for n,p,at,yaw in self.bones:
    position=(at[0],at[1],at[2]*.38) if suffix.startswith('_E') else at
    ids[n]=model.bone(n,ids[p],position,yaw=yaw,rotation=(0,math.sin(math.pi/4),0,math.cos(math.pi/4)) if n=='PROPELLER' else (math.sin(math.pi/4),0,0,math.cos(math.pi/4)) if n=='TAILROTOR' else None)
   used=set()
   for n,b,o,s,k in self.parts:
    n=n[:15]
    if n in used:n=n[:12]+str(len(used))
    used.add(n);data=mesh_data(o)
    if suffix=='':triangles+=len(data['tris'])
    if suffix.startswith('_E'):
     data['verts']=[(x,y,z*.38) for x,y,z in data['verts']]
     data['normals']=[tuple(Vector((x,y,z/.38)).normalized()) for x,y,z in data['normals']]
    tsuffix=('_dn' if 'N' in suffix else '_d') if ('D' in suffix or 'E' in suffix) else ('_n' if 'N' in suffix else '')
    texture='uahouse.tga' if k=='house' else self.name.lower()+tsuffix+'.tga'
    model.mesh(n,ids[b],**data,texture=texture,shadow=k=='solid',shader=w3d.ALPHA_TEST_SHADER if k in ('house','decal') else w3d.OPAQUE_SHADER)
   rotations={}
   for bone,turns in self.spins.items():
    rotations[ids[bone]]=[(0,0,math.sin(math.pi*turns*f/20),math.cos(math.pi*turns*f/20)) for f in range(21)]
   if rotations:model.animate(21,30,rotations)
   model.save(str(OUT/(self.name+suffix+'.w3d')))
  # Skeletal animation-only W3D files; visible geometry stays original.
  animnames=[]
  for suffix,channels in self.extra_animations.items():
   model=w3d.Model(self.name);ids={'CHASSIS':w3d.CHASSIS}
   for n,p,at,yaw in self.bones:ids[n]=model.bone(n,ids[p],at,yaw=yaw)
   model.animate(21,30,{ids[b]:q for b,q in channels.items()})
   # Header's clip name differs from hierarchy name, as expected by W3DModelDraw.
   raw=model._animation();old=w3d.name(self.name);new=w3d.name(self.name+suffix)
   raw=raw[:20]+new+raw[36:]
   (OUT/(self.name+suffix+'.w3d')).write_bytes(raw)
   animnames.append(self.name+'.'+self.name+suffix)
  self.world()
  for _,_,o,s,k in self.parts:
   textured(o,load_image(str(TEX/('uahouse.tga' if k=='house' else self.name.lower()+'.tga'))))
   bs=o.active_material.node_tree.nodes.get('Principled BSDF');bs.inputs['Roughness'].default_value=1
   if k=='house':bs.inputs['Base Color'].default_value=(.08,.32,.85,1);o.active_material.node_tree.links.remove(next(iter(bs.inputs['Base Color'].links)))
  bpy.ops.wm.save_as_mainfile(filepath=str(BUILD/(self.name+'.blend')))
  self.render()
  bpy.context.view_layer.update();pts=[o.matrix_world@Vector(c) for _,_,o,_,_ in self.parts for c in o.bound_box]
  lo=[min(p[i] for p in pts) for i in range(3)];hi=[max(p[i] for p in pts) for i in range(3)]
  entry={'key':self.key,'display_name':self.label,'role':self.role,'model':self.name,'variants':[self.name+s for s in variants],'bones':[{'name':n,'parent':p,'position':at,'yaw':yaw} for n,p,at,yaw in self.bones],'animations':([self.name+'.'+self.name,self.name+'_D.'+self.name+'_D'] if self.spins else [])+animnames,'suggested_inherited_object':self.base,'dimensions':{'min':lo,'max':hi,'size':[b-a for a,b in zip(lo,hi)]},'textures':sorted(p.name for p in TEX.glob(self.name.lower()+'*.tga'))+['uahouse.tga'],'preview':str((BUILD/(self.name+'.png')).relative_to(ROOT)),'portrait':'uaicon_'+self.name.lower()+'.tga','triangles':triangles,'meshes':len(self.parts),'notes':self.notes,'source':'scripts/models/ukraine/generate.py','generation_command':'/Applications/Blender.app/Contents/MacOS/Blender -b -t 4 -P scripts/models/ukraine/generate.py -- '+self.name}
  entry['art_revision']='ukraine-v3-ground' if getattr(self,'_ukraine_ground_polished',False) else 'ukraine-v2'
  if getattr(self,'_ukraine_ground_polished',False):entry['detail_source']='scripts/models/ukraine/polish_ground.py'
  entry['material_source']='scripts/models/ukraine/materials_v2.py'
  entry['geometry_source']='scripts/models/ukraine/'+('infantry_v2.py' if self.name in ('UARIFL','UASTUG','UACOMM','UAMANP') else 'aircraft_v2.py' if self.name in ('UAF16','UATB2','UAMI24') else 'generate.py')
  (BUILD/(self.name+'.json')).write_text(json.dumps(entry,indent=2)+'\n');print('UKRAINE_ASSET',self.name,triangles,flush=True)
 def render(self):
  scene=bpy.context.scene;scene.render.engine='BLENDER_EEVEE';scene.render.resolution_x=640;scene.render.resolution_y=480;scene.render.resolution_percentage=100
  scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-.1
  world=bpy.data.worlds.new('Ukraine review');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.075,.085,.065,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8;scene.world=world
  sun=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN'));sun.data.energy=2.6;sun.rotation_euler=(.6,.3,.5);scene.collection.objects.link(sun)
  cam=bpy.data.objects.new('camera',bpy.data.cameras.new('camera'));cam.data.type='ORTHO';scene.collection.objects.link(cam);scene.camera=cam
  bpy.context.view_layer.update();points=[o.matrix_world@Vector(c) for _,_,o,_,_ in self.parts for c in o.bound_box];lo=Vector([min(v[i] for v in points) for i in range(3)]);hi=Vector([max(v[i] for v in points) for i in range(3)]);mid=(lo+hi)/2;size=max(hi-lo)
  cam.location=mid+Vector((1,1.3,.95)).normalized()*size*3;cam.rotation_euler=(mid-cam.location).to_track_quat('-Z','Y').to_euler()
  local=[cam.rotation_euler.to_quaternion().inverted()@(p-mid) for p in points];cam.data.ortho_scale=max(max(v.x for v in local)-min(v.x for v in local),(max(v.y for v in local)-min(v.y for v in local))*4/3)*1.15
  scene.render.filepath=str(BUILD/(self.name+'.png'));bpy.ops.render.render(write_still=True)

def truck(a,L=12,axles=(7,-7),cab=5,wide=4.4,bonnet=False):
 a.box('FRAME',(-L,-wide*.65,2.7),(L,wide*.65,3.5),'steel')
 for i,x in enumerate(axles):
  for j,s in enumerate((1,-1)):a.wheel(i*2+j+1,(x,s*wide,2.25),2.25,1.55)
 cabfront=L-5.2 if bonnet else L-2
 a.hull('CAB',[(cab,3.4,4.5,7.7,8.1,wide*.7,wide,wide*.83),(cabfront,3.4,4.5,7.5,8.1,wide*.7,wide,wide*.83),(cabfront+1.8,3.5,4.6,5.6,6.1,wide*.65,wide*.92,wide*.75),(L,3.5,4.6,5.4,5.8,wide*.65,wide*.92,wide*.75)])
 for s in (-1,1):
  a.patch('WINDSCREEN',[(cabfront+.12,s*.4,8.0),(cabfront+.12,s*wide*.7,8.0),(cabfront+1.63,s*wide*.7,6.45),(cabfront+1.63,s*.4,6.45)])
  a.patch('SIDEWINDOW',[(cab+.5,s*(wide+.025),6),(cab+2.3,s*(wide+.025),6),(cab+2.1,s*(wide*.90),7.65),(cab+.5,s*(wide*.90),7.65)])
  a.box('DOORHANDLE',(cab+.65,s*wide-.06,5.55),(cab+1.45,s*wide+.06,5.74),'steel')
  a.beam('MIRROR',(L-2,s*wide,6.4),(L-2,s*(wide+1),7.2),.11)
  a.box('MIRROR',(L-2.25,s*(wide+1)-.16,6.8),(L-1.75,s*(wide+1)+.16,7.65),'steel')
  a.box('STEP',(cab,s*(wide+.15)-.35,2.8),(cab+3,s*(wide+.15)+.35,3.15),'steel')
  for x in axles:a.prism('MUDGUARD',[(x-2.7,3.9),(x-1.9,4.85),(x+1.9,4.85),(x+2.7,3.9)],s*wide-.9,s*wide+.9)
 a.box('BUMPER',(L-.2,-wide,3.2),(L+.45,wide,3.8),'steel');a.lamps(L+.48,4.55,wide*.7)
 for k in range(5):a.box('GRILLE',(L+.03,-1.8,4.5+k*.2),(L+.10,1.8,4.58+k*.2),'rubber')
 a.team(cab+.4,cab+2.7,wide+.06,4.9,.6);a.flag(cab+.6,wide+.065,5.7)

def light_details(a,L,Y,axles,door_specs):
 for sign in (-1,1):
  for x0,x1,z0,z1,wx0,wx1,wz0,wz1,y in door_specs:
   # Seams lie on the vertical outer armour; glass never disappears into roof chamfers.
   face=sign*(y+.035)
   for x in (x0,x1):a.box('DOORSEAM',(x-.045,face-.016,z0),(x+.045,face+.016,z1),'steel')
   for z in (z0,z1):a.box('DOORSEAM',(x0,face-.016,z-.045),(x1,face+.016,z+.045),'steel')
   a.patch('WINDOWFRAME',[(wx0-.12,sign*(y+.06),wz0-.12),(wx1+.12,sign*(y+.06),wz0-.12),(wx1+.12,sign*(y+.06),wz1+.12),(wx0-.12,sign*(y+.06),wz1+.12)],'rubber')
   a.patch('SIDEGLASS',[(wx0,sign*(y+.09),wz0),(wx1,sign*(y+.09),wz0),(wx1,sign*(y+.09),wz1),(wx0,sign*(y+.09),wz1)],'glass')
   a.box('HANDLEBASE',(x1-.95,sign*(y+.10)-.06,wz0-.52),(x1-.15,sign*(y+.10)+.06,wz0-.22),'darkpaint')
   a.beam('DOORHANDLE',(x1-.87,sign*(y+.24),wz0-.34),(x1-.23,sign*(y+.24),wz0-.34),.075)
   for z in (z0+.45,z1-.3):a.box('DOORHINGE',(x0-.12,sign*(y+.11)-.055,z),(x0+.17,sign*(y+.11)+.055,z+.22),'steel')
  for x in axles:
   a.prism('ARCHTRIM',[(x-2.85,3.7),(x-2.1,5.03),(x+2.1,5.03),(x+2.85,3.7),(x+2.54,3.7),(x+1.91,4.72),(x-1.91,4.72),(x-2.54,3.7)],sign*(Y+.93)-.065,sign*(Y+.93)+.065,'steel')
  a.beam('TOWEYE',(L+.35,sign*Y*.55,3.3),(L+.7,sign*Y*.55,3.8),.15)
 a.box('GRILLERECESS',(L+.10,-1.9,4.37),(L+.17,1.9,5.6),'rubber')
 for z in (4.55,4.83,5.11,5.39):a.box('GRILLESLOT',(L+.18,-1.72,z),(L+.23,1.72,z+.065),'steel')
 a.box('GRILLEEDGE',(L+.11,-2.02,4.3),(L+.21,-1.91,5.7),'steel');a.box('GRILLEEDGE',(L+.11,1.91,4.3),(L+.21,2.02,5.7),'steel')

def kozak():
 a=Asset('UAKOZAK','Kozak','Kozak','Scout and early infantry transport','AmericaVehicleHumvee')
 truck(a,L=10,axles=(6,-6),cab=-4,wide=4,bonnet=True)
 # Patrol rear is integrated into a single sloped cabin, lower bonnet at the front.
 a.hull('REARCAB',[(-9.6,3.5,4.5,7.5,8.2,3,4,3.45),(-4,3.5,4.5,7.6,8.2,3,4,3.45)])
 for s in (-1,1):
  a.patch('REARWINDOW',[(-8.8,s*4.03,6.1),(-5,s*4.03,6.1),(-5,s*3.62,7.65),(-8.8,s*3.62,7.65)])
 a.hatch((-3,0,8.35),1.4);t=a.bone('TURRET',(-3,0,8.5))
 a.box('GUNSHIELD',(-.5,-1.6,0),(.15,1.6,1.6),bone=t,bevel=.12);a.beam('MACHINEGUN',(0,0,1.5),(4,0,1.5),.19,bone=t)
 a.bone('MUZZLE01',(4,0,1.5),t);a.bone('MUZZLEFX01',(4,0,1.5),t);a.antenna(-8,-3,8.3)
 light_details(a,10,4,(6,-6),[(-8.7,-3.3,4.55,7.5,-8.0,-4.0,6.0,7.22,4.0),(-2.8,4.2,4.55,7.5,-2.0,3.5,6.0,7.22,4.0)])
 a.cyl('SPARETYRE',(-9.85,0,5.6),1.6,.6,'rubber',axis='X');a.cyl('SPAREHUB',(-10.19,0,5.6),.65,.12,'steel',axis='X',segments=10)
 for y in (-2.4,2.4):a.box('BONNETVENT',(7.1,y-.48,6.04),(8.55,y+.48,6.12),'steel')
 return a

def oplot():
 a=Asset('UAOPLOT','Oplot','Oplot','Main battle tank','AmericaTankCrusader');a.tracks(12,5.2,2.1,3.8)
 a.hull('HULL',[(-12,2.5,4,5,5.7,4,5.1,4.4),(-7,2.2,4,5.3,5.8,4,5.2,4.55),(5,2.4,4,5.3,5.8,4,5.2,4.45),(12,3.4,4,4.4,4.65,3.8,5,4.6)])
 for s in (-1,1):
  for i in range(6):a.prism('SKIRT',[(-11+i*3.5,2.5),(-7.7+i*3.5,2.5),(-7.7+i*3.5,4.8),(-11+i*3.5,4.8)],s*6.4,s*6.55)
 a.hatch((7,-1.8,5.35));a.team(-10,-4,6.58,3.7,.75)
 t=a.bone('TURRET',(0,0,5.8));a.hull('TURRET',[(-5,0,.3,1.8,2.3,3,4,3.6),(-1,-.1,.4,2.2,2.6,3.2,4.6,3.5),(4,.1,.7,1.8,2.1,2,3.2,2.5)],bone=t)
 for s in (-1,1):
  for i in range(3):a.prism('ERA',[(-1+i*1.7,.8),(.4+i*1.7,.8),(.2+i*1.7,2.5),(-1.4+i*1.7,2.5)],s*3.1,s*4.65,bone=t)
  for i in range(3):a.cyl('SMOKETUBE',(-3+i*.55,s*4.2,1.65),.25,1.3,'steel',axis='X',bone=t,segments=8)
 a.bone('BARREL',(3,0,1.2),t);a.cyl('GUN',(7.8,0,1.2),.39,12,'steel',axis='X',bone=t);a.cyl('EVAC',(7,0,1.2),.54,2,'paint',axis='X',bone=t)
 a.cyl('BORE',(13.81,0,1.2),.3,.035,'rubber',axis='X',bone=t);a.hatch((-2,1.5,2.6),1.2,t)
 a.box('SIGHT',(0,-1.9,2.35),(1.4,-.8,3.3),bone=t,bevel=.12);a.box('LENS',(1.41,-1.73,2.6),(1.44,-.98,3.1),'glass',bone=t)
 for n in ('MUZZLE01','MUZZLEFX01','TURRETMS','TURRETFX'):a.bone(n,(13.9,0,1.2),t)
 a.antenna(-8,3,5.8);a.lamps(11.9,4.35,3.8);return a

def btr4():
 a=Asset('UABTR4','BTR4','BTR-4','Autocannon infantry carrier','AmericaVehicleHumvee')
 a.hull('HULL',[(-13,3,4.3,7.5,8.3,3.7,5.4,4.4),(-7,2.8,4.2,7.6,8.4,4,5.5,4.7),(6,3,4.3,7,7.7,4,5.3,4.5),(13,3.8,4.4,5.1,5.7,3.5,4.9,4.1)])
 for i,x in enumerate((8.8,3,-4,-10)):
  for j,s in enumerate((1,-1)):a.wheel(i*2+j+1,(x,s*5.55,2.5),2.5,1.6)
 for s in (-1,1):
  a.box('FENDER',(-12.5,s*5.4-.7,4.5),(11,s*5.4+.7,4.88),bevel=.15)
  a.patch('DRIVERGLASS',[(6.1,s*.5,7.65),(6.1,s*3.65,7.65),(8.7,s*3.65,6.89),(8.7,s*.5,6.89)])
 a.team(-11,-5,5.53,6.0,1);a.hatch((4,2,7.95));a.lamps(12.8,5,3.6)
 t=a.bone('TURRET',(-2,0,8.3));a.hull('TURRET',[(-2.5,0,.4,2,2.35,1.5,2.3,1.8),(1,.0,.5,2.1,2.6,1.4,2,1.6),(2.5,.2,.6,1.3,1.5,.9,1.2,1)],bone=t)
 a.cyl('CANNON',(5,0,1.2),.21,8,'steel',axis='X',bone=t,segments=8);a.box('MISSILES',(-1,-3,.55),(3,-2,1.7),'darkpaint',bone=t,bevel=.15)
 a.box('OPTICS',(-.7,1.3,2),(.65,2,3),'steel',bone=t);a.box('OPTICLENS',(.66,1.42,2.2),(.69,1.9,2.85),'glass',bone=t)
 a.bone('BARREL',parent=t)
 for n in ('MUZZLE01','MUZZLEFX01','TURRETMS','TURRETFX'):a.bone(n,(9,0,1.2),t)
 a.antenna(-11,-3,8.3);return a

def buk():
 a=Asset('UABUK','Buk','Buk','Mobile missile air defence','ChinaVehicleGattlingTank');a.tracks(12,5.3,2.1,3.8)
 a.hull('HULL',[(-12,2.6,4,5.6,6.2,4,5.1,4.3),(-6,2.4,4,5.8,6.4,4,5.2,4.3),(8,2.5,4,5.3,5.8,4,5.1,4.2),(12,3.5,4,4.7,5,3.8,4.8,4.3)])
 a.team(-10,-4,6.42,3.6,.9);t=a.bone('TURRET',(-1,0,6.3));a.box('LAUNCHER',(-4,-4,0),(3,4,1.4),bone=t,bevel=.3)
 a.beam('RADARMAST',(2.2,0,1),(2.2,0,5),.6,bone=t)
 a.cyl('RADAR',(3,0,4.3),2,1.0,'darkpaint',axis='X',bone=t,segments=12)
 for i,y in enumerate((-3.6,-1.2,1.2,3.6)):
  a.beam('RAIL',(-6,y,1.1),(6,y,3.2),.18,bone=t)
  a.beam('MISSILE',(-5,y,2.1),(7,y,4.2),.42,'white',t)
  a.cyl('NOSE',(7.5,y,4.3),.43,1.2,'paint',axis='X',bone=t,r2=.03)
  for sign in (-1,1):a.box('FIN',(-4,y+sign*.4,1.7),(-2.5,y+sign*1.0,2.3),'darkpaint',bone=t)
  a.bone('MUZZLE%02d'%(i+1),(7.5,y,4.4),t)
 a.bone('MUZZLEFX01',(7.5,-3.6,4.4),t);a.lamps(12,4.8,3.4);return a

def bohdana():
 a=Asset('UABOHD','Bohdana','Bohdana','Mobile long-range howitzer','ChinaVehicleInfernoCannon');truck(a,L=17,axles=(12,5,-6,-13),cab=9,wide=4.7)
 a.box('GUNDECK',(-16,-4.8,4.1),(6,4.8,4.8),bevel=.15)
 for s in (-1,1):
  a.box('AMMOLOCKER',(-3,s*3.6-.8,4.8),(5,s*3.6+.8,7.2),bevel=.18)
  a.beam('STABILISER',(-14,s*3.6,4.8),(-16,s*6.1,.7),.3)
  a.box('FOOT',(-17,s*6.1-1,.4),(-15,s*6.1+1,.8),'steel')
 t=a.bone('TURRET',(-8,0,5));a.cyl('TURNTABLE',(0,0,.15),2.4,.4,'steel',bone=t)
 for s in (-1,1):a.prism('GUNYOKE',[(-2,0),(2,0),(1.4,3.5),(-1.4,3.5)],s*.8,s*1.5,bone=t)
 a.bone('BARREL',(0,0,3),t);a.cyl('BREECH',(-1,0,3),.85,4,'steel',axis='X',bone=t);a.cyl('BARREL',(12,0,3),.47,24,'steel',axis='X',bone=t)
 a.box('MUZZLEBRAKE',(23.6,-.9,2.3),(25, .9,3.7),'steel',bone=t)
 for x in (23.9,24.5):a.box('BAFFLE',(x,-.95,2.8),(x+.2,.95,3.2),'rubber',bone=t)
 for n in ('MUZZLE01','MUZZLEFX01','TURRETMS','TURRETFX'):a.bone(n,(25,0,3),t)
 a.notes.append('Gun is forward-facing in transport and turns automatically through TURRET; outriggers are compact static silhouette details.');return a

def dronevan():
 a=Asset('UADRONE','DroneController','Drone Controller','Remote attack-drone support vehicle','AmericaVehicleAvenger');truck(a,L=11.5,axles=(7,-7),cab=5,wide=4.3)
 a.hull('CABIN',[(-11.3,3.5,4.4,8.4,9.1,3.4,4.25,3.6),(4.5,3.5,4.4,8.4,9.1,3.4,4.25,3.6)])
 for s in (-1,1):
  for x in (-9,-6,-3):a.box('VENT',(x,s*4.29,6),(x+1.5,s*4.35,7.2),'steel')
  a.flag(-9,s*4.37,7.7)
 a.team(-10,-5,4.38,4.8,1.0)
 a.beam('MAST',(-8,0,9.1),(-8,0,16),.15);a.cyl('DISH',(-7.6,0,15),1.5,.4,'white',axis='X')
 t=a.bone('TURRET',(-2,0,9.2));a.box('LAUNCHBOX',(-2,-2,0),(2,2,1.2),bone=t,bevel=.2)
 for y in (-1.1,1.1):a.beam('RAIL',(-2,y,1.2),(3,y,2),.12,'steel',t)
 a.bone('MUZZLE01',(3,0,2.1),t);a.bone('MUZZLEFX01',(3,0,2.1),t)
 light_details(a,11.5,4.3,(7,-7),[(5.35,9.05,4.6,7.5,5.8,8.55,6.05,7.23,4.3),(-2.6,2.75,4.15,8.2,-1.85,1.9,7.0,8.0,4.25)])
 for x in (-10,-6):
  a.box('ACCESSPANEL',(x,4.295,4.65),(x+2.75,4.37,5.8),'darkpaint',bevel=.055)
  a.beam('PANELHANDLE',(x+.5,4.52,5.4),(x+1.35,4.52,5.4),.075)
 return a

def supply():
 a=Asset('UASUPLY','SupplyTruck','Supply Truck','Resource collection','ChinaVehicleSupplyTruck');truck(a,L=14,axles=(9,-5,-10),cab=7,wide=4.6)
 a.box('BED',(-13.8,-4.7,3.9),(5,4.7,4.5),'steel')
 for s in (-1,1):
  a.box('SIDERAIL',(-13.5,s*4.65-.15,4.5),(4.8,s*4.65+.15,6.2))
  for x in (-12,-8,-4,0,4):a.box('UPRIGHT',(x,s*4.7-.18,4.5),(x+.22,s*4.7+.18,6.8),'steel')
 for x in (-10,-5,0):
  a.box('SUPPLIES',(x-1.8,-3.6,4.6),(x+1.8,3.6,7.5),'canvas',bevel=.15)
  a.box('STRAP',(x-.12,-3.7,7.5),(x+.12,3.7,7.65),'sand')
 for n,at in [('SUPPLY01',(-10,0,6)),('SUPPLY02',(-5,0,6)),('SUPPLY03',(0,0,6)),('DOCKPOINT',(-14,0,3))]:a.bone(n,at)
 a.notes.append('SupplyTruckAIUpdate can inherit ChinaVehicleSupplyTruck; original SUPPLY01..03 bones locate cargo. Truck faces +X.');return a

def dozer():
 a=Asset('UADOZR','EngineeringVehicle','Engineering Vehicle','Construction and repair','AmericaVehicleDozer');a.tracks(9,4.4,2.2,3.6)
 a.hull('HULL',[(-8,2.5,3.5,5.4,5.9,3,4,3.5),(1,2.5,3.5,5.4,5.9,3,4,3.5),(8,3,3.5,4.5,4.8,3,4,3.5)])
 a.prism('CAB',[(-5,5.5),(1,5.5),(.3,9),(-4,9)],-2.7,2.7)
 for s in (-1,1):a.patch('CABGLASS',[(-3.6,s*2.72,6.1),(.4,s*2.72,6.1),(-.2,s*2.72,8.5),(-3.6,s*2.72,8.5)])
 a.box('CABROOF',(-5,-3,9),(1,3,9.4),bevel=.15)
 for s in (-1,1):a.beam('BLADEARM',(0,s*4,3),(10,s*4,2),.45)
 a.bone('BLADE',(9,0,1.1));a.prism('BLADE',[(0,0),(2,.4),(2,4),(.8,4.5),(.3,2)],-7,7,'steel',bone='BLADE')
 a.team(-7,-3,5.55,3.6,.8);a.cyl('EXHAUST',(-6,-2,7),.25,4,'steel');return a

def wing(a,n,xy,z,thick=.18,s='paint',bone='CHASSIS'):
 bm=bmesh.new();low=[bm.verts.new((x,y,z-thick)) for x,y in xy];high=[bm.verts.new((x,y,z+thick)) for x,y in xy];bm.faces.new(list(reversed(low)));bm.faces.new(high)
 for i in range(len(xy)):j=(i+1)%len(xy);bm.faces.new((low[i],low[j],high[j],high[i]))
 return a.mesh(n,bm,s,bone)
def fuselage(a,sections):
 # Elliptical airframe rings, +X nose; hand-defined station profiles.
 bm=bmesh.new();rings=[]
 for x,y,z,h in sections:rings.append([bm.verts.new((x,math.cos(i*math.tau/12)*y,z+math.sin(i*math.tau/12)*h)) for i in range(12)])
 bm.faces.new(list(reversed(rings[0])));bm.faces.new(rings[-1])
 for one,two in zip(rings,rings[1:]):
  for i in range(12):bm.faces.new((one[i],one[(i+1)%12],two[(i+1)%12],two[i]))
 a.mesh('FUSELAGE',bm)
def aircraft(kind):
 import aircraft_v2
 return aircraft_v2.create(sys.modules[__name__],kind)
def aircraft_legacy(kind):
 if kind=='f16':
  a=Asset('UAF16','F16','F-16','Multirole fighter','AmericaJetRaptor');fuselage(a,[(-13,1.7,1.9,1.5),(-8,2,2,1.9),(0,2.1,2,2.1),(6,1.7,2,1.6),(11,.9,2,1),(16,.05,2,.06)])
  for s in (-1,1):
   wing(a,'MAINWING',[(-7,s*1.4),(-7,s*12),(-4,s*12),(6,s*1.5)],1.3)
   wing(a,'TAILPLANE',[(-13,s*1.4),(-14,s*6),(-11,s*6),(-7,s*1.4)],2)
   a.cyl('MISSILE',(-3,s*9,.3),.25,6,'white',axis='X',segments=8)
   a.bone('MUZZLE%02d'%(1 if s>0 else 2),(.5,s*9,.3))

   if s>0:a.team(-7,-3,2.15,2.3,.65)
  a.prism('TAILFIN',[(-13,2),(-11,8),(-8,8),(-6,2)],-.17,.17)
  a.cyl('EXHAUST',(-13.2,0,1.9),1.45,.3,'rubber',axis='X')
  a.cyl('NOZZLERIM',(-13.1,0,1.9),1.63,.23,'steel',axis='X',segments=16)
  a.cyl('NOZZLEBORE',(-13.24,0,1.9),1.31,.04,'rubber',axis='X',segments=16)
  # Characteristic ventral intake, dorsal spine, underwing tanks and pylons.
  a.hull('INTAKE',[(-2,-.9,-.6,.2,.5,.8,1.4,1.2),(4,-.65,-.5,.25,.7,.8,1.2,.9)])
  a.cyl('INTAKEBORE',(4.04,0,.1),.76,.05,'rubber',axis='X',segments=10)
  a.hull('SPINE',[(-8,3,3.1,3.6,3.75,.4,.7,.3),(0,3.5,3.6,3.8,4,.4,.6,.3)])
  for sign in (-1,1):
   a.prism('PYLON',[(-5,-.7),(1,-.7),(0,.8),(-4,.8)],sign*5-.2,sign*5+.2)
   a.cyl('TANK',(-2,sign*5,-.8),.7,7,'airpaint',axis='X',segments=12)
   a.cyl('TANKNOSE',(2.1,sign*5,-.8),.7,1.2,'airpaint',axis='X',segments=12,r2=.04)
   for xx in (-4,0):wing(a,'MISSILEFIN',[(xx,sign*8.5),(xx-1,sign*9.8),(xx+.3,sign*9.8),(xx+.5,sign*8.5)],.3,.055,'white')
   a.beam('PITOT',(11,sign*.4,2),(14,sign*.4,2),.045,'steel')
   # Leading-edge flap and aileron seams keep the wing readable at native zoom.
   a.beam('WINGSEAM',(3.9,sign*3.2,1.50),(-4.3,sign*10.9,1.50),.045,'steel')
   a.beam('AILERON',(-6.2,sign*4.2,1.50),(-6.2,sign*10.6,1.50),.055,'steel')
   a.beam('WINGTIP',(-6.9,sign*12,1.4),(-4.1,sign*12,1.4),.12,'steel')
  a.hull('CANOPY',[(1,3.5,3.5,4.7,5,.8,1.2,.6),(5,3.4,3.5,4.3,4.8,.7,1,.5),(7,3.2,3.3,3.5,3.6,.6,.8,.5)],'glass')
  a.bone('ENGINE01',(-14,0,1.9));a.bone('MUZZLEFX01',(.5,9,.3));return a
 if kind=='tb2':
  a=Asset('UATB2','TB2','TB2','Armed aerial scout','AmericaJetRaptor');fuselage(a,[(-8,.7,1,1),(-3,1.4,1,1.2),(4,1.1,1,1.0),(9,.1,1,.15)])
  for s in (-1,1):
   wing(a,'WING',[(-3,s*.7),(-4,s*16),(-1.7,s*16),(1.4,s*.7)],1.5,.12)
   a.beam('TAILBOOM',(-1,s*2,1.4),(-12,s*3,1.2),.20)
   wing(a,'VTAIL',[(-12,s*3),(-12,s*7),(-10,s*7),(-9,s*3)],2.1,.12)
   a.cyl('BOMB',(-.5,s*6,0),.35,3,'darkpaint',axis='X',segments=8)
  a.cyl('CAMERA',(5,0,-.3),.8,1.0,'glass');p=a.bone('PROPELLER',(-8.2,0,1));a.spins[p]=1
  for s in (-1,1):a.box('PROP',(s*.2,-.2,-.1),(s*3,.2,.1),'steel',bone=p)
  for s in (-1,1):a.patch('HOUSECOLOR',[(-2,s*8,1.64),(-3,s*8,1.64),(-3,s*11,1.64),(-2,s*11,1.64)],house=True)
  a.bone('MUZZLE01',(0,6,0));a.bone('MUZZLE02',(0,-6,0));a.notes.append('Pusher propeller uses X-oriented PROPELLER bone and native looping rotation clip.');return a
 a=Asset('UAMI24','Mi24','Mi-24','Heavy assault helicopter','AmericaVehicleComanche');fuselage(a,[(-12,.65,4,1),(-7,1.7,3.5,2.4),(-2,2.9,3.2,2.8),(6,2.3,3.1,2.3),(11,1.1,2.9,1.5),(13,.2,2.9,.4)])
 # Two distinct tandem bubble canopies, native geometry only.
 for x,z,r in ((8,4.3,1.8),(3.9,5.5,1.95)):
  a.hull('CANOPY',[(x-r,z-.7,z,z+r*.6,z+r*.85,.6,r,r*.55),(x+r,z-.7,z,z+r*.5,z+r*.65,.4,r*.8,r*.45)],'glass')
 a.beam('TAILBOOM',(-8,0,4),(-23,0,7),.65,'paint');a.prism('TAILFIN',[(-23,6),(-24,10),(-21.7,10),(-20,6)],-.22,.22)
 for s in (-1,1):
  wing(a,'STUBWING',[(-4,s*2),(-5,s*8),(0,s*8),(2,s*2)],3.4,.22)
  a.cyl('ROCKETPOD',(-1,s*6.2,2),.85,4,'darkpaint',axis='X')
  for y,z in ((-.3,-.3),(.3,-.3),(-.3,.3),(.3,.3)):a.cyl('ROCKETBORE',(1.02,s*6.2+y,2+z),.19,.03,'rubber',axis='X',segments=6)
  a.cyl('ENGINE',(-3,s*1.7,6.3),1.1,5,'steel',axis='X')
  a.beam('GEAR',(-1,s*2.4,2),(-1,s*4,.3),.16);a.cyl('WHEEL',(-1,s*4,.3),.55,.4,'rubber',axis='Y')
  a.team(-6,-1,2.95,3.2,.9)
 r=a.bone('ROTOR',(0,0,7.7));a.spins[r]=1;a.cyl('HUB',(0,0,0),.5,1.1,'steel',bone=r)
 for i in range(5):
  angle=i*math.tau/5;xy=[(math.cos(angle)*r-math.sin(angle)*y,math.sin(angle)*r+math.cos(angle)*y) for r,y in ((1,-.25),(16,-.4),(16,.4),(1,.25))];wing(a,'BLADE',xy,.3,.055,'steel',r)
 tr=a.bone('TAILROTOR',(-22.5,.6,7.2));a.spins[tr]=1
 for i in range(3):
  angle=i*math.tau/3;xy=[(math.cos(angle)*rad-math.sin(angle)*yy,math.sin(angle)*rad+math.cos(angle)*yy) for rad,yy in ((.2,-.2),(3.1,-.22),(3.1,.22),(.2,.2))];wing(a,'TAILBLADE',xy,0,.05,'steel',tr)
 a.cyl('TAILHUB',(0,0,.1),.3,.3,'steel',bone=tr,segments=8)
 a.bone('MUZZLE01',(1,6,2));a.bone('MUZZLE02',(1,-6,2));a.bone('MUZZLEFX01',(11,0,2));return a

def fpv():
 a=Asset('UAFPV','AttackDrone','Attack Drone','Drone controller projectile','GenericTankShell')
 a.box('BODY',(-1,-.7,-.3),(1,.7,.3),'darkpaint',bevel=.15);a.cyl('WARHEAD',(1,0,-.4),.38,1.3,'sand',axis='X')
 for x in (-1.5,1.5):
  for y in (-1.5,1.5):
   a.beam('ARM',(0,0,0),(x,y,0),.1);a.cyl('MOTOR',(x,y,.1),.19,.4,'steel');a.box('PROP',(x-1,y-.1,.35),(x+1,y+.1,.40),'rubber')
 a.bone('MUZZLE01',(2,0,0));return a

def infantry(kind):
 import infantry_v2
 return infantry_v2.create(sys.modules[__name__],kind)
def infantry_legacy(kind):
 cfg={'rifle':('UARIFL','Rifleman','Rifleman','AmericaInfantryRanger'),'stugna':('UASTUG','Stugna','Stugna Team','AmericaInfantryMissileDefender'),'commando':('UACOMM','Commando','Commando','AmericaInfantryColonelBurton')}
 name,key,label,base=cfg[kind];a=Asset(name,key,label,'Infantry',base)
 root=a.bone('BODYROOT');pelvis=a.bone('PELVIS',(0,0,3.25),root);a.box('HIPS',(-.55,-.75,-.3),(.55,.75,.4),'uniform',bone=pelvis,bevel=.18)
 chest=a.bone('TORSO',(0,0,.45),pelvis);a.hull('TORSO',[(-.58,0,.25,1.6,1.8,.65,.85,.62),(.5,0,.25,1.6,1.8,.65,.85,.62)],'uniform',chest)
 a.box('VEST',(.5,-.7,.35),(.7,.7,1.55),'darkpaint',bone=chest,bevel=.1)
 for y in (-.43,.02,.45):a.box('POUCH',(.7,y-.17,.3),(.87,y+.17,.86),'canvas',bone=chest,bevel=.05)
 a.box('BACKPACK',(-1,-.6,.3),(-.55,.6,1.6),'canvas',bone=chest,bevel=.15)
 head=a.bone('HEAD',(0,0,2.1),chest);a.cyl('HEAD',(.05,0,.1),.46,.7,'skin',bone=head,segments=10)
 a.cyl('HELMET',(0,0,.47),.59,.35,'darkpaint',bone=head,segments=10,r2=.48);a.box('GOGGLES',(.45,-.4,.16),(.54,.4,.35),'glass',bone=head)
 a.box('NOSE',(.48,-.09,-.08),(.60,.09,.14),'skin',bone=head)
 for sign,b in ((1,'L'),(-1,'R')):
  leg=a.bone('LEG'+b,(0,sign*.43,0),pelvis);a.beam('TROUSER',(0,0,-.1),(.12,0,-1.5),.33,'uniform',leg)
  shin=a.bone('SHIN'+b,(.12,0,-1.5),leg);a.beam('SHIN',(0,0,0),(-.12,0,-1.2),.29,'uniform',shin)
  a.box('BOOT',(-.38,-.32,-1.58),(.45,.32,-1.05),'rubber',bone=shin,bevel=.07)
  arm=a.bone('ARM'+b,(0,sign*.86,1.5),chest);a.beam('SLEEVE',(0,0,0),(.2,sign*.2,-.8),.26,'uniform',arm)
  fore=a.bone('FORE'+b,(.2,sign*.2,-.8),arm);a.beam('SLEEVE',(0,0,0),(.95,-sign*.55,.25),.22,'uniform',fore)
  a.cyl('HAND',(.95,-sign*.55,.25),.22,.4,'skin',axis='X',bone=fore,segments=8)
 muzzle=(3.3,-.65,5.4) if kind=='stugna' else (4.15,0,4.52) if kind=='commando' else (3.6,0,4.52)
 for n in ('MUZZLE01','MUZZLEFX01','Muzzle'):a.bone(n,muzzle)
 a.box('RIFLE',(.7,-.19,.65),(2.4,.19,.95),'steel',bone=chest);a.beam('BARREL',(2.4,0,.82),(3.6,0,.82),.08,bone=chest);a.box('MAGAZINE',(1.6,-.15,.1),(1.9,.15,.7),'rubber',bone=chest)
 if kind=='stugna':
  a.cyl('LAUNCHTUBE',(1.5,-.65,1.7),.40,3.4,'darkpaint',axis='X',bone=chest);a.cyl('LENS',(3.21,-.65,1.7),.28,.04,'rubber',axis='X',bone=chest)
  a.box('SIGHT',(1,-1.1,2),(2,-.7,2.5),'steel',bone=chest);a.notes.append('Original shoulder-carry Stugna caricature; deliberately portable infantry gameplay role, not literal deployed tripod crew simulation.')
 if kind=='commando':
  a.box('RADIO',(-.9,-.7,1.3),(-.5,-.25,2.1),'steel',bone=chest);a.beam('ANTENNA',(-.8,-.5,2),(-.8,-.5,3),.045,bone=chest)
  a.cyl('SUPPRESSOR',(3.65,0,.82),.16,.95,'steel',axis='X',bone=chest,segments=8);a.cyl('SCOPE',(1.7,0,1.1),.19,1,'rubber',axis='X',bone=chest,segments=8)
 # Native rigid-joint original animation clips.
 for suff,mode in (('_W','walk'),('_I','idle'),('_F','fire'),('_DIE','die')):
  channels={}
  for bone in ('LEGL','LEGR','ARML','ARMR'):
   phase=0 if bone.endswith('L') else math.pi;qs=[]
   for f in range(21):
    angle=(math.sin(f*math.tau/20+phase)*(.62 if bone.startswith('LEG') else .12)) if mode=='walk' else (.018*math.sin(f*math.tau/20) if mode=='idle' else 0)
    qs.append((0,math.sin(angle/2),0,math.cos(angle/2)))
   channels[bone]=qs
  if mode=='walk':
   for side in ('L','R'):
    phase=0 if side=='L' else math.pi;channels['SHIN'+side]=[(0,math.sin(max(0,math.sin(f*math.tau/20+phase))*.45),0,math.cos(max(0,math.sin(f*math.tau/20+phase))*.45)) for f in range(21)]
  if mode=='die':channels['BODYROOT']=[(0,math.sin(-min(f/14,1)*math.pi/4),0,math.cos(-min(f/14,1)*math.pi/4)) for f in range(21)]
  a.extra_animations[suff]=channels
 a.team(-.45,.45,.88,.65,.4,chest);a.notes.append('Entire visible mesh original, no stock infantry model or skeleton import. Rigid-joint walk/idle/fire/death clips provided; fire clip holds aiming posture.');return a

BUILDINGS={
 'command':('UACMD','CommandCenter','Command Centre','AmericaCommandCenter',(58,58)),
 'power':('UAPOWER','PowerPlant','Diesel Power Station','AmericaPowerPlant',(28,28)),
 'barracks':('UABARR','Barracks','Barracks','AmericaBarracks',(42,32)),
 'supply':('UASUPP','SupplyCenter','Supply Centre','ChinaSupplyCenter',(48,42)),
 'factory':('UAFACT','WarFactory','Vehicle Factory','AmericaWarFactory',(62,50)),
 'airfield':('UAAIR','Airfield','Drone Workshop','AmericaBarracks',(45,34)),
 'tech':('UATECH','TechCenter','Signals Centre','AmericaStrategyCenter',(48,38)),
 'income':('UAINCOM','IncomeCenter','Equipment Workshop','AmericaSupplyDropZone',(38,32)),
 'ground':('UAGUARD','GroundDefense','Autocannon Emplacement','AmericaPatriotBattery',(20,20)),
 'aa':('UAAA','AADefense','Air Defence Emplacement','AmericaPatriotBattery',(22,22)),
 'super':('UASUPER','Superweapon','Long-Range Strike Complex','AmericaParticleCannonUplink',(53,45)),
}
def roof(a,x0,x1,y0,y1,z,rise=5,s='roof'):
 # Pitched corrugated roof, authored shape with readable ridge and seams.
 ym=(y0+y1)/2;a.hull('ROOF',[(x0,z,z,z+.2,z+rise,(y1-y0)*.49,(y1-y0)*.52,.12),(x1,z,z,z+.2,z+rise,(y1-y0)*.49,(y1-y0)*.52,.12)],s)
 # hull centered on y=0; offset its object vertices to actual building centre
 o=a.parts[-1][2]
 for v in o.data.vertices:v.co.y+=ym
 for x in range(int(x0)+2,int(x1),6):
  a.beam('ROOFRIB',(x,y0,z+.35),(x,ym,z+rise+.2),.15,'steel');a.beam('ROOFRIB',(x,ym,z+rise+.2),(x,y1,z+.35),.15,'steel')
def hall(a,x0,x1,y0,y1,h=16,door=True):
 a.box('WALL',(x0,y0,1),(x1,y1,h),'concrete',bevel=.3);roof(a,x0-.8,x1+.8,y0-.8,y1+.8,h,4)
 for y in (y0,y1):
  for x in range(int(x0)+6,int(x1)-3,9):
   a.box('WINDOWFRAME',(x-.4,y-.25,h*.5-.4),(x+4.5,y+.25,h*.7+.4),'steel')
   a.box('WINDOW',(x,y-.28,h*.5),(x+4.1,y+.28,h*.7),'glass')
  for x in (x0,x1):a.box('PILASTER',(x-.5,y-.6,1),(x+.5,y+.6,h),'sand')
 if door:
  a.box('ENTRANCE',(x1+.05,(y0+y1)/2-3.5,1),(x1+.25,(y0+y1)/2+3.5,9),'steel')
  a.box('DOOR',(x1+.28,(y0+y1)/2-2.9,1),(x1+.35,(y0+y1)/2+2.9,8.5),'darkpaint')
  a.box('CANOPY',(x1-1,(y0+y1)/2-5,9),(x1+4,(y0+y1)/2+5,9.5),'roof')
def tower(a,x,y,z,h=28):
 a.box('TOWER',(x-4,y-4,z),(x+4,y+4,z+h),'concrete',bevel=.4)
 a.box('TOWERCAB',(x-6,y-6,z+h-3),(x+6,y+6,z+h+4),'steel',bevel=.4)
 for axis in (0,1):
  for sign in (-1,1):
   lo=[x-5,y-5,z+h-1];hi=[x+5,y+5,z+h+2.5];lo[axis]=(x if axis==0 else y)+sign*6.02;hi[axis]=lo[axis]+.05
   a.box('GLASS',lo,hi,'glass')
 a.box('TOWERROOF',(x-7,y-7,z+h+4),(x+7,y+7,z+h+4.8),'roof')
 a.antenna(x,y,z+h+4.8,9)
def dish(a,x,y,z,r=5):
 a.beam('DISHSTAND',(x,y,z),(x,y,z+7),.55,'steel');a.cyl('DISH',(x+1,y,z+7),r,1.0,'sand',axis='X',segments=16,r2=r*.82)
 a.beam('DISHFEED',(x+1,y,z+7),(x+5,y,z+7),.12);a.cyl('DISHFEED',(x+5,y,z+7),.6,1,'steel',axis='X')
def crate(a,x,y,z=1,size=5):
 a.box('CRATE',(x-size/2,y-size/2,z),(x+size/2,y+size/2,z+size*.8),'canvas',bevel=.1)
 for yy in (-size*.3,size*.3):a.box('STRAP',(x-size/2-.03,y+yy-.12,z),(x+size/2+.03,y+yy+.12,z+size*.8+.1),'sand')
def building(kind):
 name,key,label,base,(X,Y)=BUILDINGS[kind];a=Asset(name,key,label,'Building',base,True)
 a.box('FOUNDATION',(-X,-Y,-.25),(X,Y,1),'concrete',bevel=.5)
 # Standard USA-style emergence / smoke contract; clear front-side spawn corridor.
 for n,at in [('EXITSTART',(X*.05,Y*.45,1)),('EXITEND',(X+12,Y*.45,1)),('RALLYPOINT',(X+25,Y*.45,0)),('SMOKE01',(-X*.4,0,16)),('SMOKE02',(0,-Y*.4,12)),('SMOKE03',(-X*.3,Y*.3,18))]:a.bone(n,at)
 if kind=='command':
  hall(a,-48,13,-42,9,18)
  a.box('GARAGEREAR',(-40,22,1),(-38,47,13),'concrete');a.box('GARAGEWALL',(-40,22,1),(18,24,13),'concrete');a.box('GARAGEWALL',(-40,45,1),(18,47,13),'concrete');roof(a,-41,19,21,48,13,4)
  a.box('GARAGEHEADER',(17,24,11),(20,45,13),'steel')
  a.bones=[b for b in a.bones if b[0] not in ('EXITSTART','EXITEND')]
  a.bone('EXITSTART',(-10,34.5,1));a.bone('EXITEND',(70,34.5,1))
  tower(a,-32,-27,22,25);dish(a,0,-23,22,7)
  a.box('ANNEX',(-48,12,1),(-10,22,12),'darkpaint',bevel=.4)
  a.box('RAMP',(18,25,.9),(48,45,1.2),'steel')
  for i in range(3):crate(a,30,-40+i*8)
  a.team(-30,0,47.2,8,2.4)
 elif kind=='power':
  hall(a,-23,8,-20,15,13);a.box('GENERATOR',(-17,-15,17),(2,12,22),'darkpaint',bevel=.6)
  for y in (-9,5):
   a.cyl('TURBINE',(-8,y,23),4,15,'steel',axis='X',segments=12)
   a.cyl('EXHAUST',(-18,y,29),1.4,20,'steel',segments=10);a.cyl('CAP',(-18,y,39),1.9,.8,'steel',segments=10)
  for x in (15,23):
   a.cyl('TRANSFORMER',(x,-9,8),2.2,14,'darkpaint',segments=10)
   for z in (13,15,17):a.cyl('INSULATOR',(x,-9,z),2.6,.6,'sand',segments=10)
  for y in range(-16,13,4):a.box('COOLINGFIN',(8,y,3),(12,y+.7,12),'steel')
  a.team(-18,0,15.2,7,2.5)
 elif kind=='barracks':
  hall(a,-36,20,-25,6,13);hall(a,-36,-2,12,26,10)
  a.box('TRAININGPAD',(5,10,1.1),(33,25,1.2),'sand')
  for x in (10,22):
   a.beam('TARGETPOST',(x,22,1),(x,22,6),.3);a.box('TARGET',(x-.8,21.8,4),(x+.8,22.2,7),'darkpaint')
  for x in (9,20,30):crate(a,x,-17,1,4)
  a.team(-25,-4,26.2,6,2.4)
 elif kind=='supply':
  hall(a,-42,-8,-33,32,15);a.box('OPENBAY',(-8,-33,1),(18,0,2.3),'steel')
  for x,y in ((0,-23),(11,-23),(0,-10),(11,-10),(-32,38),(-20,38)):crate(a,x,y,2.4,8)
  # Crane spans the storage apron, leaving docking lane at +X clear.
  for x,y in ((-4,-32),(20,-32),(-4,1),(20,1)):a.beam('GANTRY',(x,y,2),(x,y,22),.45,'steel')
  a.box('GANTRY',(-5,-33,22),(21,2,23),'darkpaint');a.beam('HOOK',(8,-15,22),(8,-15,14),.11)
  a.notes.append('China-style truck workflow: DOCKSTART=(65,20,0), DOCKACTION=(42,20,0), DOCKEND=(66,20,0), all outside the warehouse. Queue bones DOCKWAITING01..09. EXITSTART=(15,20,1), EXITEND=(60,20,1).')
  # Replace generic emergence for resource trucks.
  a.bones=[b for b in a.bones if b[0] not in ('EXITSTART','EXITEND')]
  for n,at in [('EXITSTART',(15,20,1)),('EXITEND',(60,20,1)),('DOCKSTART',(65,20,0)),('DOCKACTION',(42,20,0)),('DOCKEND',(66,20,0))]:a.bone(n,at)
  for i,(x,y) in enumerate(((85,35),(85,65),(50,65),(15,65),(-20,65),(-60,60),(-70,20),(-70,-20),(-50,-65)),1):a.bone('DOCKWAITING%02d'%i,(x,y,0))
  a.team(-30,-10,32.2,8,2.5)
 elif kind=='factory':
  # Open assembly hall: side walls + rear wall, free exit through +X.
  a.box('REARWALL',(-53,-43,1),(-50,7,22),'concrete');a.box('SIDEWALL',(-53,-43,1),(30,-39,22),'concrete');a.box('SIDEWALL',(-53,3,1),(30,7,22),'concrete')
  roof(a,-54,31,-44,8,22,6)
  a.box('DOORHEADER',(28,-40,16),(32,4,22),'steel')
  for y in (-38,2):a.box('DOORJAMB',(28,y-1,1),(32,y+1,17),'steel')
  hall(a,-49,-10,15,44,14)
  for x in (-35,-15,5):a.box('SKYLIGHT',(x,-25,25),(x+10,-10,25.5),'glass')
  a.box('GANTRY',(-42,-37,14),(22,-34,15),'yellow');a.box('GANTRY',(-42,-1,14),(22,2,15),'yellow')
  for x,y in ((43,30),(53,30),(43,42)):crate(a,x,y)
  a.bones=[b for b in a.bones if b[0] not in ('EXITSTART','EXITEND')]
  for n,at in [('EXITSTART',(-12,-18,1)),('EXITEND',(70,-18,1)),('DOCKSTART',(78,22,0)),('DOCKACTION',(52,22,0)),('DOCKEND',(82,22,0))]:a.bone(n,at)
  for i,(x,y) in enumerate(((95,35),(95,75),(50,75),(5,75),(-45,75),(-85,65),(-90,15),(-90,-35),(-55,-75)),1):a.bone('DOCKWAITING%02d'%i,(x,y,0))
  a.notes.append('Vehicle emergence EXITSTART (-12,-18,1) -> EXITEND (70,-18,1), open front bay. Separate repair dock at +X,+Y. No animated garage door is required.');a.team(-38,-15,44.2,7,3)
 elif kind=='airfield':
  # Compact assembly shed and launch apron; no runway/parking dependency.
  hall(a,-37,2,-27,25,15)
  a.box('OPENBAY',(3,-25,1),(42,6,1.3),'roof')
  roof(a,0,37,10,28,11,3)
  for x in (3,34):a.beam('AWNINGPOST',(x,12,1),(x,12,11),.35)
  a.box('CATAPULT',(4,-17,1.4),(39,-14,2.2),'steel')
  a.beam('RAIL',(3,-17,2.4),(40,-17,2.4),.14)
  a.box('WORKBENCH',(6,17,1),(29,24,5),'darkpaint')
  a.box('DRONEWING',(10,10,5.2),(16,29,5.4),'airpaint')
  a.box('DRONEBODY',(5,19,5.3),(27,21,5.9),'airpaint',bevel=.2)
  dish(a,-18,9,20,5)
  for x,y in ((-27,-18),(-17,-18),(26,18)):crate(a,x,y,1.3,5)
  a.bones=[b for b in a.bones if b[0] not in ('EXITSTART','EXITEND')]
  a.bone('EXITSTART',(18,-14,3));a.bone('EXITEND',(60,-14,35))
  a.notes.append('Compact UAV workshop; default production exit launches persistent reconnaissance UAVs without runway reservations or rearming.')
  a.team(-29,-6,25.2,7,2.5)
 elif kind=='tech':
  hall(a,-40,21,-31,8,18);hall(a,-38,5,15,31,13)
  dish(a,-24,-12,23,8);dish(a,6,-12,23,5)
  tower(a,-30,22,17,17)
  for x in (29,39):a.box('SERVERBOX',(x,-27,1),(x+6,7,10),'darkpaint',bevel=.3)
  for y in (-22,-13,-4):a.box('VENT',(28.9,y,3),(29.1,y+6,8),'steel')
  a.team(-25,0,31.2,6,3)
 elif kind=='income':
  hall(a,-31,12,-25,14,13);a.box('WORKPAD',(10,14,1.1),(32,27,1.3),'roof')
  for x,y in ((20,20),(28,20),(-24,24),(-15,24)):crate(a,x,y,1.3,6)
  a.box('SOLARPANEL',(-24,-17,18),(5,8,18.6),'glass')
  for x in range(-23,5,5):a.box('SOLARGRID',(x,-17,18.62),(x+.15,8,18.67),'steel')
  for y in (-12,-7,-2,3):a.box('SOLARGRID',(-24,y,18.62),(5,y+.15,18.67),'steel')
  a.beam('CRANE',(24,-18,1),(24,-18,19),.4);a.beam('CRANE',(24,-18,19),(9,-18,19),.4);a.beam('HOOK',(10,-18,19),(10,-18,12),.08)
  a.team(-24,0,14.2,6,2.5);a.notes.append('Generic periodic-income workshop, no helicopter unloading animation contract. INI should implement SupplyDropZone-style income without stock delivery props.')
 elif kind in ('ground','aa'):
  a.cyl('BUNKER',(0,0,3.5),13,5,'concrete',segments=8,r2=11)
  for s in (-1,1):
   for i in range(4):a.box('SANDBAG',(-13+i*7,s*15-2,1),(-7+i*7,s*15+2,3),'sand',bevel=.6)
  t=a.bone('TURRET',(0,0,6.4));a.cyl('BEARING',(0,0,0),5,.5,'steel',bone=t)
  a.hull('TURRET',[(-4,0,.8,3.5,4,2.3,4,3),(3,.5,1.1,2.5,3.2,2.1,3,2.3)],bone=t)
  if kind=='ground':
   for y in (-1,1):a.cyl('CANNON',(8,y,2.3),.32,13,'steel',axis='X',bone=t)
   a.bone('MUZZLE01',(14.5,-1,2.3),t);a.bone('MUZZLE02',(14.5,1,2.3),t)
  else:
   for y in (-4.6,4.6):
    for z in (1.2,3):a.box('LAUNCHBOX',(-4,y-.85,z-.65),(7,y+.85,z+.65),'darkpaint',bone=t,bevel=.15)
    a.box('LAUNCHFACE',(7.01,y-.6,.85),(7.04,y+.6,3.4),'rubber',bone=t)
   a.bone('MUZZLE01',(7,-4.6,3),t);a.bone('MUZZLE02',(7,4.6,3),t);a.cyl('RADAR',(-2,0,6),2,.5,'steel',axis='X',bone=t)
  a.bone('MUZZLEFX01',(14 if kind=='ground' else 7,0,2.3),t);a.team(-8,5,13.2,3.5,1.8)
 elif kind=='super':
  hall(a,-45,-10,-37,32,15);tower(a,-28,-18,19,21)
  a.box('LAUNCHPAD',(-4,-35,1),(44,33,2.5),'roof',bevel=.4)
  # Original fixed cruise-missile launch racks, four distinct hatches.
  for x in (9,31):
   for y in (-20,16):
    a.box('SILO',(x-8,y-11,2.5),(x+8,y+11,7),'concrete',bevel=.6)
    a.prism('LID',[(x-7,7),(x+7,7),(x+6,9),(x-6,9)],y-10,y+10,'darkpaint')
    for yy in (y-7,y+7):a.box('LIDHINGE',(x-6,yy-.4,8.9),(x+6,yy+.4,9.3),'steel')
  dish(a,-27,18,20,5);a.bone('WEAPONLAUNCH01',(10,-20,10));a.bone('WEAPONLAUNCH02',(31,16,10));a.bone('PARTICLE01',(10,-20,10));a.team(-38,-15,32.2,6,3)
 # Foundation expansion joints, painted warning stripes and grounded utility equipment.
 if kind not in ('ground','aa'):
  for yy in range(int(-Y)+10,int(Y),18):a.box('PADSEAM',(-X+1,yy,1.01),(X-1,yy+.13,1.03),'steel')
  for i in range(5):a.box('HAZARD',(X-12+i*2,-Y+2,1.035),(X-11+i*2,-Y+9,1.06),'yellow' if i%2==0 else 'steel')
  a.box('UTILITY',(-X+2,-Y+2,1.1),(-X+8,-Y+9,6),'darkpaint',bevel=.25)
  for z in (2,3,4,5):a.box('UTILITYVENT',(-X+8.02,-Y+3,z),(-X+8.06,-Y+8,z+.2),'steel')
  # National pennant and upper player-colour guidon on a grounded pole.
  a.beam('FLAGPOLE',(-X+5,Y-5,1),(-X+5,Y-5,20),.18,'steel')
  for i,color in enumerate(('yellow','blue')):a.patch('FLAG',[(-X+5,Y-5,14+i*2),(-X+14,Y-5,14+i*2),(-X+14,Y-5,16+i*2),(-X+5,Y-5,16+i*2)],color)
  a.patch('HOUSECOLOR',[(-X+5,Y-5,18.3),(-X+12,Y-5,18.3),(-X+12,Y-5,20),(-X+5,Y-5,20)],house=True)
 return a

def sapper_mine():
 a=Asset('UAMINE','Mine','Sapper Mine','Projectile','ChinaStandardMine')
 a.cyl('MINEBODY',(0,0,.4),1.5,.65,'darkpaint',segments=16)
 a.cyl('PRESSUREPLATE',(0,0,.82),.9,.2,'steel',segments=16)
 a.box('HANDLE',(-.5,-1.85,.22),(.5,-1.43,.45),'steel',bevel=.04)
 return a

JOBS={'UAMINE':sapper_mine,'UAKOZAK':kozak,'UAOPLOT':oplot,'UABTR4':btr4,'UABUK':buk,'UABOHD':bohdana,'UADRONE':dronevan,'UASUPLY':supply,'UADOZR':dozer,'UAF16':lambda:aircraft('f16'),'UATB2':lambda:aircraft('tb2'),'UAMI24':lambda:aircraft('mi24'),'UAFPV':fpv,'UARIFL':lambda:infantry('rifle'),'UASTUG':lambda:infantry('stugna'),'UACOMM':lambda:infantry('commando'),'UAMANP':lambda:infantry('manpads')}
JOBS.update({info[0]:lambda k=key:building(k) for key,info in BUILDINGS.items()})

def main():
 # Generated, unbaked Blender images may save PNG despite their requested TGA format.
 # Write this constant white native texture explicitly, so the game never sees a missing-texture red.
 (TEX/'uahouse.tga').write_bytes(bytes([0,0,2,0,0,0,0,0,0,0,0,0,8,0,8,0,24,0])+bytes([255])*(8*8*3))
 selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(JOBS)
 for name in selected:
  bpy.ops.wm.read_factory_settings(use_empty=True)
  JOBS[name]().finish()
 # Manifest is rebuilt from finished artifacts so interrupted batch runs remain resumable.
 entries=[]
 for name in JOBS:
  p=BUILD/(name+'.json')
  if not p.exists():continue
  e=json.loads(p.read_text());e['category']='building' if name in [v[0] for v in BUILDINGS.values()] else 'infantry' if name in ('UARIFL','UASTUG','UACOMM','UAMANP') else 'aircraft' if name in ('UAF16','UATB2','UAMI24') else 'projectile' if name in ('UAFPV','UAMINE') else 'vehicle'
  e['parent']=e.pop('suggested_inherited_object');e['bone_contract']=e['bones'];e['bones']=[b['name'] for b in e['bone_contract']];e['preview']=str(ROOT/e['preview']);entries.append(e)
 (HERE/'manifest.json').write_text(json.dumps({'faction':'Ukraine','style':'Original olive/digital-camouflage military vehicles and industrial buildings, with broad baked AO and readable house-colour panels.','geometry_origin':'Original mathematical meshes; no stock visual models imported. Existing authored geometry helper functions reused.','assets':entries},indent=2)+'\n')
if __name__=='__main__':main()

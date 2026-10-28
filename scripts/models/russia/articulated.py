"""Russia's original articulated soldier exporter. No stock rig or visible meshes.
Authored infantry geometry shares our original Israel construction approach;
Russia supplies its own AK weapon, textures, equipment colours and full-size rig.
"""
from pathlib import Path
import sys,json,math
import bpy,bmesh
from mathutils import Matrix,Vector,Quaternion
HERE=Path(__file__).resolve().parent;sys.path.insert(0,str(HERE))
from build import *
from infantry_articulated import create

class Articulated(Asset):
 def __init__(self,name,role,parent):
  super().__init__(name,role,parent);self.animations={}
 def mesh(self,name,bm,tile=0,bone='CHASSIS',cap_axis=None,cap_tile=None,recalc=True):
  mapping={0:0,1:11,3:11,4:10,5:8,6:6,7:8,8:8,9:9,10:13,11:12,12:11,13:12,14:13}
  tile=mapping.get(tile,tile);cap_tile=mapping.get(cap_tile,cap_tile)
  obj=super().mesh(name,bm,tile,bone,cap_axis,cap_tile,recalc)
  if tile in (12,13):
   lo=[min(v.co[i] for v in obj.data.vertices) for i in range(3)];hi=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
   for poly in obj.data.polygons:
    drop=max(range(3),key=lambda i:abs(poly.normal[i]));axes=[i for i in range(3) if i!=drop]
    for li in poly.loop_indices:
     co=obj.data.vertices[obj.data.loops[li].vertex_index].co;u=(co[axes[0]]-lo[axes[0]])/max(.001,hi[axes[0]]-lo[axes[0]]);v=(co[axes[1]]-lo[axes[1]])/max(.001,hi[axes[1]]-lo[axes[1]])
     obj.data.uv_layers.active.data[li].uv=((tile%4+.07+.86*u)/4,1-(tile//4+.93-.86*v)/4)
  return obj
 def ellipsoid(self,name,at,radii,tile=11,bone='CHASSIS'):
  bm=bmesh.new();bmesh.ops.create_uvsphere(bm,u_segments=12,v_segments=8,radius=1,matrix=Matrix.Translation(at)@Matrix.Diagonal((*radii,1)))
  return self.mesh(name,bm,tile,bone)
 def finish(self):
  super().finish()
  for suffix,rotations in self.animations.items():
   model=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
   for n,p,at,q in self.bones:ids[n]=model.bone(n,ids[p],at,rotation=q)
   model.animate(21,30,{ids[n]:seq for n,seq in rotations.items()})
   blob=model._animation();blob=blob.replace(w3d.name(model.name)+w3d.name(model.name),w3d.name(model.name)+w3d.name(self.name),1)
   (OUT/(self.name+suffix+'.w3d')).write_bytes(blob)
  meta=json.loads((BUILD/(self.name+'.json')).read_text())
  meta.update(animations={s:self.name+'.'+self.name+s for s in self.animations},art_revision=self.art_revision,
   animation_contract='Original skeleton. Explicit _I stationary LOOP resets joints; _R MOVING LOOP; _F FIRING/ATTACKING LOOP; _X DYING ONCE. No AIRNGR dependency. World-size geometry at ModelScale=1.',
   generation_command=f'/Applications/Blender.app/Contents/MacOS/Blender -b -t 4 -P scripts/models/russia/articulated.py -- {self.name}',
   geometry='Original articulated anatomy, clothing and Russian weapon geometry. Authored knee/ankle rig and clips; no stock visible meshes or stock animation dependency.')
  (BUILD/(self.name+'.json')).write_text(json.dumps(meta,indent=2)+'\n')
  render_poses(self)

def render_poses(v):
 for label,suffix,frame in [('idle','_I',0),('running','_R',5),('firing','_F',2)]:
  for obj in list(bpy.data.objects):
   if obj.type in ('CAMERA','LIGHT'):bpy.data.objects.remove(obj,do_unlink=True)
  world={'CHASSIS':Matrix.Identity(4)};rots=v.animations[suffix]
  if 'CHASSIS' in rots:
   q=rots['CHASSIS'][frame];world['CHASSIS']=Quaternion((q[3],*q[:3])).to_matrix().to_4x4()
  for n,p,at,q in v.bones:
   qr=rots.get(n,[(0,0,0,1)]*21)[frame]
   world[n]=world[p]@Matrix.Translation(at)@(Quaternion((q[3],*q[:3])) if q else Quaternion()).to_matrix().to_4x4()@Quaternion((qr[3],*qr[:3])).to_matrix().to_4x4()
  for _,b,o,_,_ in v.parts:o.matrix_world=world[b]
  render(v.name+'_'+label,v.parts)

if __name__=='__main__':
 selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['RURIFLE','RUKORNET','RUCMDO']
 for name in selected:
  bpy.ops.wm.read_factory_settings(use_empty=True)
  create(sys.modules[__name__],{'RURIFLE':'Rifleman','RUKORNET':'Spike','RUCMDO':'Commando'}[name]).finish()

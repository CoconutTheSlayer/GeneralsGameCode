"""Coalition vehicles, built with original EU geometry and painted textures.

Blender -b -P scripts/models/coalition.py [-- EUDANA EUPATRIA ...]
The light vehicles delegate to original_compacts.py. The larger models reuse
the existing EU Blender kit; no original game models enter the compact builder.
All export dimensions are game scale, deliberately exaggerated for RTS readability.
"""
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import bpy
import bmesh
from mathutils import Matrix, Vector

HERE=Path(__file__).resolve().parent
sys.path.insert(0,str(HERE))
import engineer as kit
import tiger
import w3d
from blender_kit import box,cylinder,new_object,mesh_data,textured,load_image
from engineer_paint import Layout


class Asset:
    def __init__(self,name):
        self.name=name; self.pieces=[];self.painted=[];self.bones=[];self.spins={}
    def bone(self,name,parent='CHASSIS',at=(0,0,0),rotation=0):
        self.bones.append((name,parent,at,rotation));return name
    def mesh(self,name,bm,part=None,bone='CHASSIS',at=(0,0,0),texture=None,kind='solid'):
        bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
        obj=new_object(name,bm,at)
        self.pieces.append((name,bone,obj,texture or self.name.lower()+'.tga',kind))
        if part:self.painted.append((obj,part))
        elif not obj.data.uv_layers:obj.data.uv_layers.new(name='UVMap')
        return obj
    def colours(self,x0,x1,z0,z1,y):
        for obj in kit.side_panels('HOUSECOLOR01','HOUSECOLOR02',x0,x1,z0,z1,y):
            bm=bmesh.new();bm.from_mesh(obj.data);bm.normal_update()
            for face in bm.faces:
                if face.normal.y*face.calc_center_median().y<0:face.normal_flip()
            bm.to_mesh(obj.data);bm.free()
            self.pieces.append((obj.name,'CHASSIS',obj,w3d.HOUSE_COLOUR_TEXTURE,'house'))
    def wheel(self,n,at,r=2.2,w=1.6):
        name=f'TIRE{n:02}';self.bone(name,at=at)
        obj=kit.wheel(name,at,r,w)
        self.pieces.append((name,name,obj,'euboxer_tire.tga','solid'))
    def boxmesh(self,name,lo,hi,texture='eucoal_metal.tga',bone='CHASSIS'):
        bm=bmesh.new();box(bm,lo,hi);return self.mesh(name,bm,bone=bone,texture=texture)
    def finish(self):
        parts={}
        for obj,part in self.painted:
            vs=[v.co for v in obj.data.vertices]
            bounds=tuple(v for i in range(3) for v in (min(p[i] for p in vs)-.05,max(p[i] for p in vs)+.05))
            if part in parts:
                bounds=tuple(min(parts[part][i],v) if i%2==0 else max(parts[part][i],v) for i,v in enumerate(bounds))
            parts[part]=bounds
        refined=self.name in ('EUWIEST','EUMV4','EUVALUK','EUPATRIA')
        layout=Layout(parts,size=1024 if refined else 512,
                      weights={'running':.65,'fittings':.8} if refined else None)
        for obj,part in self.painted:kit.panel_unwrap(obj,layout,part)
        out=Path(kit.BUILD);out.mkdir(parents=True,exist_ok=True)
        path=out/(self.name+'_layout.json')
        path.write_text(json.dumps(dict(layout=layout.to_json(),faces=kit.layout_faces(self.painted,layout))))
        # Bake in the assembled pose: turret geometry is local to its bone when exported.
        matrices={'CHASSIS':Matrix.Identity(4)}
        from mathutils import Quaternion
        for name,parent,at,rot in self.bones:
            q=w3d._yaw_quaternion(rot)
            matrices[name]=matrices[parent]@Matrix.Translation(at)@Quaternion((q[3],*q[:3])).to_matrix().to_4x4()
        for _,bone,obj,_,_ in self.pieces:obj.matrix_world=matrices[bone]
        paint_args=[]
        if refined:
            ao=out/(self.name+'_ao.png')
            kit.bake_occlusion([obj for obj,_ in self.painted],str(ao),layout.size)
            paint_args=[str(ao)]
        subprocess.run(['/usr/bin/env','python3',str(HERE/'coalition_paint.py'),str(path),kit.TEXTURES,*paint_args],check=True)
        kit.apply_textures(self.pieces);kit.team_colour([p[2] for p in self.pieces if p[4]=='house'])
        for _,_,obj,texture,kind in self.pieces:
            if kind=='rotor':tiger.blur_material(obj,load_image(str(Path(kit.TEXTURES)/texture)))
        if refined:
            # Keep massed armies cheap to draw. Static fittings sharing a texture
            # and bone become one mesh; wheels and tread sides remain articulated.
            groups={}
            for name,bone,obj,texture,kind in self.pieces:
                separate=name if name.startswith(('TREADS','TIRE')) else ''
                groups.setdefault((bone,texture,kind,separate),[]).append((name,obj))
            compact=[]
            for (bone,texture,kind,_),group in groups.items():
                name=group[0][0]
                obj=kit.join([o for _,o in group],name) if len(group)>1 else group[0][1]
                compact.append((name,bone,obj,texture,kind))
            self.pieces=compact
        for suffix in ('','_D'):
            m=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
            for name,parent,at,rot in self.bones:ids[name]=m.bone(name,ids[parent],at,yaw=rot)
            for name,bone,obj,texture,kind in self.pieces:
                tex=texture.replace('.tga','_d.tga') if suffix and texture==self.name.lower()+'.tga' else texture
                kwargs={}
                if kind=='house':kwargs=dict(shadow=False,shader=w3d.ALPHA_TEST_SHADER)
                if kind=='rotor':kwargs=dict(shadow=False,shader=w3d.ALPHA_BLEND_SHADER)
                if texture=='euwie_tread.tga':
                    import wiesel
                    kwargs=dict(shadow=False,shader=w3d.ALPHA_TEST_SHADER,mapper_args=wiesel.TREAD_MAPPER)
                data=mesh_data(obj)
                # Geometry built in world space for chassis parts, local for rotating pieces.
                m.mesh(name,ids[bone],**data,texture=tex,**kwargs)
            if self.spins:m.animate(21,30,{ids[b]:tiger.spin(21,turns) for b,turns in self.spins.items()})
            m.save(str(Path(kit.DATA)/'Art/W3D'/f'{self.name}{suffix}.w3d'))
        # Pose local meshes on their hierarchy for the Blender project / preview.
        matrices={'CHASSIS':Matrix.Identity(4)}
        for name,parent,at,rot in self.bones:
            q=w3d._yaw_quaternion(rot)
            from mathutils import Quaternion
            matrices[name]=matrices[parent]@Matrix.Translation(at)@Quaternion((q[3],*q[:3])).to_matrix().to_4x4()
        for _,bone,obj,_,_ in self.pieces:obj.matrix_world=matrices[bone]
        bpy.ops.wm.save_as_mainfile(filepath=str(out/(self.name+'.blend')))
        render(self.name,self.pieces)
        print('COALITION_ASSET',self.name,flush=True)


def render(name,pieces):
    scene=bpy.context.scene
    scene.render.engine='BLENDER_EEVEE'
    scene.render.resolution_x=720;scene.render.resolution_y=540;scene.render.resolution_percentage=100
    scene.view_settings.view_transform='Standard';scene.view_settings.look='None';scene.view_settings.exposure=-.35
    world=bpy.data.worlds.new('Coalition review');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.19,.21,.24,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.8;scene.world=world
    sun=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN'));sun.data.energy=2.4
    sun.rotation_euler=(.65,.15,.5);scene.collection.objects.link(sun)
    cam=bpy.data.objects.new('camera',bpy.data.cameras.new('camera'));cam.data.type='ORTHO';scene.collection.objects.link(cam);scene.camera=cam
    bpy.context.view_layer.update()
    points=[obj.matrix_world@Vector(c) for _,_,obj,_,_ in pieces for c in obj.bound_box]
    lo=Vector([min(v[i] for v in points) for i in range(3)]);hi=Vector([max(v[i] for v in points) for i in range(3)])
    mid=(lo+hi)/2;size=max(hi-lo)
    cam.location=mid+Vector((1,1.25,.95)).normalized()*size*3
    cam.rotation_euler=(mid-cam.location).to_track_quat('-Z','Y').to_euler()
    local=[cam.rotation_euler.to_quaternion().inverted()@(p-mid) for p in points]
    cam.data.ortho_scale=max(max(v.x for v in local)-min(v.x for v in local),(max(v.y for v in local)-min(v.y for v in local))*4/3)*1.14
    scene.render.filepath=str(Path(kit.BUILD)/(name+'_0.png'));bpy.ops.render.render(write_still=True)


def dana():
    a=Asset('EUDANA');bm=bmesh.new()
    kit.prism_xz(bm,[(-17,3),(16,3),(18,5),(15,6),(-17,6)],-5.8,5.8)
    # The DANA's split, slab-sided forward cab and long 8x8 chassis.
    for side in (-1,1):
        y0,y1=sorted((side*.7,side*6.2))
        kit.prism_xz(bm,[(7,6),(17,6),(16,10.2),(10,11.8),(7,11.8)],y0,y1)
    box(bm,(-17,-5.8,6),(-9,5.8,8.7));a.mesh('HULL',bm,'hull')
    for i,x in enumerate((12,5,-6,-13)):
        for j,s in enumerate((1,-1)):a.wheel(i*2+j+1,(x,s*5.9,2.5),2.5,1.8)
    a.bone('Turret',at=(-2,0,7.2));bm=bmesh.new()
    kit.prism_xz(bm,[(-7,0),(6,0),(5,5.8),(-6,5.8)],-5.2,5.2)
    for s in (-1,1):box(bm,(-7,s*5.1,1),(-1,s*5.6,4.8))
    cylinder(bm,(1.5,0,6),2,.35)
    # Long centreline howitzer, visible recoil part and double-baffle muzzle brake.
    cylinder(bm,(13,0,5.1),.8,21,axis='X',segments=10)
    box(bm,(21.8,-1.2,4.1),(24,1.2,6.1));box(bm,(22.2,-1.3,4.5),(22.7,1.3,5.7))
    a.mesh('TURRET',bm,'turret',bone='Turret')
    a.bone('Muzzle','Turret',(24,0,5.1));a.bone('TurretMS','Turret',(24,0,5.1))
    a.bone('Barrel','Turret');a.bone('TurretFX','Turret',(24,0,5.1))
    # Black forward glazing is geometry, so it survives damage / camouflage variants.
    for s in (-1,1):a.boxmesh('GLASS'+str(s),(16.12,min(s*1,s*5.1),8.0),(16.25,max(s*1,s*5.1),9.7),'eucoal_glass.tga')
    a.colours(-15,-9,6.5,7.5,5.85);return a


def carrier(name,ambulance):
    from coalition_ground import carrier as build_carrier
    return build_carrier(Asset,name,ambulance)


def tracked(name,mv4=False):
    from coalition_ground import tracked as build_tracked
    return build_tracked(Asset,name,mv4)


def rotor(a,name,at,radius,blades,rotation=0):
    a.bone(name,at=at,rotation=rotation);a.spins[name]=1
    bm=bmesh.new();cylinder(bm,(0,0,0),.6,1.2,segments=10)
    for i in range(blades):
        r=bmesh.new();box(r,(.5,-.38,0),(radius,.38,.12));bmesh.ops.rotate(r,verts=r.verts,cent=(0,0,0),matrix=Matrix.Rotation(i*2*math.pi/blades,3,'Z'))
        me=bpy.data.meshes.new('rotortmp');r.to_mesh(me);r.free();bm.from_mesh(me);bpy.data.meshes.remove(me)
    a.mesh(name,bm,bone=name,texture='eucoal_metal.tga')
    obj=tiger.blur_disc('PROPS'+name[-2:],radius,blades)
    a.pieces.append((obj.name,name,obj,'eutig_rotor.tga','rotor'))


def puma():
    a=Asset('EUPUMA');bm=bmesh.new()
    tiger.loft(bm,[tiger.fuselage_station(*s) for s in [(17,2.5,5,.4),(15,1.5,7.5,3),(9,1,9,4),(-5,1,9,4),
        (-10,3,8,2.7),(-24,5.5,7,.7),(-26,6,7,.3)]],segments=12)
    for s in (-1,1):
        cylinder(bm,(-3,s*2.1,10),1.3,8,axis='X',segments=10)
        box(bm,(-9,s*4,2),(-4,s*7,3.3))
    kit.prism_xz(bm,[(-26,6),(-22,7),(-24,15),(-27,15)],-.4,.4)
    box(bm,(-22,-6,7.5),(-18,6,7.8));a.mesh('BODY',bm,'body')
    rotor(a,'PROPELLER01',(-1,0,12),23,4);rotor(a,'PROPELLER02',(-25,-.8,12),4,5,(.70710678,0,0,.70710678))
    for s in (-1,1):
        a.boxmesh('COCKPIT'+str(s),(9,s*3.72,5.2),(13,s*3.82,7.8),'eucoal_glass.tga')
        for x in (3,-1,-5):a.boxmesh('WINDOW'+str(s)+str(x),(x,s*4.02,5),(x+2,s*4.12,7.2),'eucoal_glass.tga')
        a.wheel(1 if s==1 else 2,(-6,s*6,1.2),1.2,.7)
    a.bone('WeaponA01',at=(-8,0,1));a.bone('Smoke01',at=(-4,0,9));a.colours(-7,-3,3.4,4.4,4.08);return a


def a400m():
    a=Asset('EUA400M');bm=bmesh.new()
    tiger.loft(bm,[tiger.fuselage_station(*s) for s in [(34,3,5,.4),(31,1,8,3),(25,-1,11,6),(-15,-1,11,6),
        (-28,4,10,3),(-38,8,11,.4)]],segments=14)
    import typhoon
    for s in (1,-1):
        poly=[(10,5),(-2,43),(-12,43),(-14,5)]
        typhoon.slab(bm,poly if s==1 else typhoon.mirrored(poly),1.3,mid=lambda x,y:8.5)
        tail=[(-28,.2),(-33,14),(-38,14),(-36,.2)]
        typhoon.slab(bm,tail if s==1 else typhoon.mirrored(tail),.8,mid=lambda x,y:23)
        for i,y in enumerate((15,29)):
            tiger.loft(bm,[tiger.fuselage_station(x,4.5,10,2.2,y=s*y) for x in (4,-3,-11)],segments=12)
            rotor(a,f'PROPELLER{(0 if s==1 else 2)+i+1:02}',(5,s*y,7.2),8.2,8,(0,.70710678,0,.70710678))
    typhoon.slab(bm,[(-22,9),(-31,25),(-37,25),(-38,10)],1,plane='xz')
    a.mesh('BODY',bm,'body')
    for s in (-1,1):a.boxmesh('COCKPIT'+str(s),(25,s*4.5,7),(30,s*4.9,9),'eucoal_glass.tga')
    a.bone('WeaponA01',at=(-23,0,0));a.bone('Smoke01',at=(0,0,10));a.colours(-10,8,4.5,6,6.05);return a


def gripen():
    a=Asset('EUGRIPEN');bm=bmesh.new();import typhoon
    typhoon.loft(bm,[(20,0,.2,.3,2),(15,1,-.5,1.3,2),(8,1.8,-.9,2,2.7),(-8,1.9,-.8,1.5,3),(-16,1,-.7,1,2)])
    typhoon.loft(bm,[(13.5,0,1.5,1.6,2),(11.5,.8,1.3,3.1,2),(7,.8,1.3,2.9,2),(5,0,1.8,1.9,2)])
    for s in (-1,1):
        wing=[(2,1.8),(-9,13),(-13,13),(-14,1.8)];canard=[(10,1.7),(7,5.6),(5,5.6),(6,1.7)]
        typhoon.slab(bm,wing if s==1 else typhoon.mirrored(wing),.5)
        typhoon.slab(bm,canard if s==1 else typhoon.mirrored(canard),.25,mid=lambda x,y:1)
        box(bm,(2,s*1.7,-.7),(6,s*2.6,1));
        for i,y in enumerate((4,7.5,11)):
            store=bmesh.new();cylinder(store,(-4,s*y,-1),.28,6,axis='X',segments=8)
            a.mesh(f'MISSILE{(0 if s==1 else 3)+i+1:02}',store,texture='eucoal_metal.tga')
            a.bone(f'WeaponA{(0 if s==1 else 3)+i+1:02}',at=(-1,s*y,-1))
    typhoon.slab(bm,[(-5,1),(-12,8),(-15,8),(-16,1)],.5,plane='xz')
    cylinder(bm,(-16,0,.2),1.1,1.8,axis='X',segments=12);a.mesh('BODY',bm,'body')
    # Canopy as a separate coloured surface.
    glass=bmesh.new();typhoon.loft(glass,[(13,0,1.7,1.8,2),(11,.75,1.5,3.16,2),(7,.75,1.5,2.96,2),(5.8,0,2,2.1,2)])
    a.mesh('CANOPY',glass,texture='eucoal_glass.tga')
    for bone,at in [('Engine01',(-17,0,.2)),('Engine02',(-17,0,.2)),('Wingtip01',(-12,13,0)),('Wingtip02',(-12,-13,0)),('Smoke01',(-7,0,1))]:a.bone(bone,at=at)
    a.colours(-14,-11,4.5,5.2,.28);return a


def apache():
    # Tiger's proven rotor, gun and rocket animation contract, with a new Apache fuselage silhouette.
    bpy.ops.wm.open_mainfile(filepath=str(Path(kit.BUILD)/'EUTIGR.blend'))
    parts={k:bpy.data.objects[n] for k,n in [('chassis','CHASSIS'),('pods','MISSILEUPGRADE'),('head','PROPELLER01'),
        ('tail','PROPELLER02'),('blur','PROPS01'),('flash','TURRETFX01'),('colour','HOUSECOLOR01')]}
    for obj in list(bpy.data.objects):
        if obj not in parts.values():bpy.data.objects.remove(obj,do_unlink=True)
    bm=bmesh.new()
    for s in (-1,1):
        tiger.loft(bm,[tiger.fuselage_station(x,5.8,9.3,w,y=s*3.3) for x,w in [(3,1.6),(-4,1.8),(-9,1.2)]],segments=10)
        box(bm,(-2,min(s*3,s*10),4),(2,max(s*3,s*10),4.6))
        for y in (5,7,9):
            cylinder(bm,(3,s*y,3.1),.35,6,axis='X',segments=8)
    cylinder(bm,(.5,0,13),2.4,1.5,segments=12)
    box(bm,(16.5,-1.3,2),(19,1.3,4.6))
    extra=new_object('APACHEKIT',bm)
    layout=Layout({'body':(-10,20,-10.5,10.5,1.5,15)},size=512)
    kit.panel_unwrap(extra,layout,'body')
    path=Path(kit.BUILD)/'EUAPACHE_layout.json'
    path.write_text(json.dumps(dict(layout=layout.to_json(),faces=kit.layout_faces([(extra,'body')],layout))))
    subprocess.run(['/usr/bin/env','python3',str(HERE/'coalition_paint.py'),str(path),kit.TEXTURES],check=True)
    textured(extra,load_image(str(Path(kit.TEXTURES)/'euapache.tga')))
    # Preserve the original Tiger texture on the shared cockpit, canopy and underside;
    # append kit geometry as its own mesh by wrapping the exporter, without duplicating animations.
    original=w3d.Model.save
    def save(model,path):
        model.mesh('APACHEKIT',w3d.CHASSIS,**mesh_data(extra),texture='euapache_d.tga' if model.name.endswith('_D') else 'euapache.tga')
        original(model,path)
    w3d.Model.save=save
    try:
        tiger.export(parts,'EUAPACHE',tiger.BODY);tiger.export(parts,'EUAPACHE_D',tiger.BODY_D)
    finally:w3d.Model.save=original
    parts['flash'].hide_render=True
    bpy.ops.wm.save_as_mainfile(filepath=str(Path(kit.BUILD)/'EUAPACHE.blend'))
    render('EUAPACHE',[(o.name,'',o,'','') for o in list(parts.values())+[extra] if not o.hide_render])


def main():
    jobs={'EUDANA':dana,'EUVALUK':lambda:carrier('EUVALUK',True),'EUPATRIA':lambda:carrier('EUPATRIA',False),
          'EUWIEST':lambda:tracked('EUWIEST'),'EUMV4':lambda:tracked('EUMV4',True),'EUPUMA':puma,'EUA400M':a400m,'EUGRIPEN':gripen}
    selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(jobs)+['EUAPACHE']
    for name in selected:
        if name in ('EUWIEST','EUVALUK','EUPATRIA','EUMV4','EUDRONE'):
            from original_compacts import build
            build(name)
            continue
        bpy.ops.wm.read_factory_settings(use_empty=True)
        if name=='EUAPACHE':apache()
        else:jobs[name]().finish()


if __name__=='__main__':main()

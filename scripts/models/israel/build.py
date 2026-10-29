"""Israel's original Generals-scale model set. Run Blender -b -t 2 -P this_file -- [IDs].

All hulls, wings, infantry and architecture are generated from authored geometry.
Shared EU mathematical primitives and baking code are reused, not stock game art.
Only IL-prefixed runtime files are written. +X is forward, Z up.
"""
from pathlib import Path
import sys, math, json, hashlib, subprocess
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
sys.path.insert(0,str(HERE.parent))
import bpy,bmesh
from mathutils import Matrix,Vector,Quaternion
import original_compacts as oc
import engineer as kit
import w3d,puls,tiger
sys.path.insert(0,str(HERE))
import polished_bake
from blender_kit import box,cylinder,new_object,mesh_data,textured,load_image
TEX=ROOT/'resources/macos/GameData/Art/TexturesHD'
OUT=ROOT/'resources/macos/GameData/Art/W3D'
BUILD=ROOT/'build/faction-assets/israel'
oc.ATLAS='il_atlas.tga';oc.TRACK='il_track.tga';oc.TEX=TEX;oc.BUILD=BUILD
w3d.HOUSE_COLOUR_TEXTURE='ilhouse.tga'
SAND,PLATE,VENT,LOCKER,HATCH,HUB,RUBBER,TREAD,IRON,GLASS,TUBE,TARP,CONCRETE,CAUTION,LAMP,DOOR=range(16)

class Asset(oc.Vehicle):
    def __init__(self,name,key,label,role,inherit,category='vehicle'):
        super().__init__(name);self.key=key;self.label=label;self.role=role;self.inherit=inherit;self.category=category;self.animations={}
    def mesh(self,name,bm,tile=SAND,bone='CHASSIS',cap_axis=None,cap_tile=None,recalc=True):
        obj=super().mesh(name,bm,tile,bone,cap_axis,cap_tile,recalc)
        obj['israel_material_tile']=tile
        if self.category in ('infantry','aircraft'):
            n,b,o,_,k=self.parts[-1]
            self.parts[-1]=(n,b,o,'il_'+self.category+'_atlas.tga',k)
            # Map across each whole component, never restart cloth folds at
            # every narrow polygon of a smooth limb or fuselage.
            low=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
            high=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
            for p in obj.data.polygons:
                axis=max(range(3),key=lambda i:abs(p.normal[i]));axes={0:(1,2),1:(0,2),2:(0,1)}[axis]
                face_tile=cap_tile if axis==cap_axis and abs(p.normal[axis])>.99 and cap_tile is not None else tile
                if self.category=='aircraft' and tile==SAND and p.normal.z<-.4:face_tile=CONCRETE
                for li in p.loop_indices:
                    co=obj.data.vertices[obj.data.loops[li].vertex_index].co
                    u=(co[axes[0]]-low[axes[0]])/max(.001,high[axes[0]]-low[axes[0]])
                    vv=(co[axes[1]]-low[axes[1]])/max(.001,high[axes[1]]-low[axes[1]])
                    inset=.16 if self.category=='infantry' and face_tile==TARP else .06
                    obj.data.uv_layers.active.data[li].uv=((face_tile%4+inset+(1-2*inset)*u)/4,1-(face_tile//4+1-inset-(1-2*inset)*vv)/4)
            return obj
        if name=='RUNWAY':obj['israel_surface']='asphalt'
        # Broad plate geometry shares a continuous projection: bevels never become tiny repeated panels.
        if tile in (SAND,CONCRETE,TARP,IRON):
            low=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
            high=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
            for p in obj.data.polygons:
                axis=max(range(3),key=lambda i:abs(p.normal[i]));ax={0:(1,2),1:(0,2),2:(0,1)}[axis]
                if axis==cap_axis and abs(p.normal[axis])>.99 and cap_tile is not None and cap_tile!=tile:
                    continue
                for li in p.loop_indices:
                    co=obj.data.vertices[obj.data.loops[li].vertex_index].co
                    u=(co[ax[0]]/50+.5)%1;v=(co[ax[1]]/50+.5)%1
                    if tile==SAND or (self.category=='building' and tile==CONCRETE) or name=='RUNWAY':
                        # Fill the material patch for each component. A fixed
                        # 50-unit projection left short armour faces sampling
                        # only a handful of source pixels, producing blurry paint.
                        u=(co[ax[0]]-low[ax[0]])/max(.001,high[ax[0]]-low[ax[0]])
                        v=(co[ax[1]]-low[ax[1]])/max(.001,high[ax[1]]-low[ax[1]])
                    if tile==SAND:
                        # Keep the painted anti-slip area, with enough texel
                        # span to retain its wear and grit after the diffuse bake.
                        obj.data.uv_layers.active.data[li].uv=((.035+.93*u)/4,1-(.39+.56*v)/4)
                    else:obj.data.uv_layers.active.data[li].uv=((tile%4+.08+.84*u)/4,1-(tile//4+.92-.84*v)/4)
        if tile==GLASS and name in ('CANOPY','GOGGLES'):
            # Cockpit lofts use uninterrupted glass, not a repeated framed window per polygon.
            for li,loop in enumerate(obj.data.loops):
                co=obj.data.vertices[loop.vertex_index].co
                obj.data.uv_layers.active.data[li].uv=((1+.30+.36*((co.x/30+.5)%1))/4,1-(2+.30+.36*((co.y/12+.5)%1))/4)
        return obj
    def bake_paint(self):
        polished_bake.bake_paint(self)
    def beam(self,name,a,b,width=.18,tile=IRON,bone='CHASSIS'):
        a,b=Vector(a),Vector(b);delta=b-a
        bm=bmesh.new();m=Matrix.Translation((a+b)/2)@delta.to_track_quat('X','Z').to_matrix().to_4x4()@Matrix.Diagonal((delta.length,width*2,width*2,1))
        bmesh.ops.create_cube(bm,size=1,matrix=m)
        return self.mesh(name,bm,tile,bone)
    def profile(self,name,points,y0,y1,tile=SAND,bone='CHASSIS'):
        bm=bmesh.new();kit.prism_xz(bm,points,y0,y1);return self.mesh(name,bm,tile,bone)
    def ellipsoid(self,name,at,radii,tile=SAND,bone='CHASSIS'):
        bm=bmesh.new();bmesh.ops.create_uvsphere(bm,u_segments=10,v_segments=6,radius=1,matrix=Matrix.Translation(at)@Matrix.Diagonal((*radii,1)))
        return self.mesh(name,bm,tile,bone)
    def export_animations(self):
        for suffix,rots in self.animations.items():
            m=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
            for n,p,at,q in self.bones:ids[n]=m.bone(n,ids[p],at,rotation=q)
            m.animate(21,30,{ids[n]:seq for n,seq in rots.items()})
            # Animation hierarchy must name the base model to bind the original skeleton.
            m._hierarchy=lambda:b''
            original=m._animation
            def anim(original=original,m=m):
                blob=original();old=w3d.name(m.name);base=w3d.name(self.name)
                return blob.replace(old+old,old+base,1)
            m._animation=anim;m._hlod=lambda:b'';m.save(str(OUT/(self.name+suffix+'.w3d')))

    def finish(self):
        from polish_geometry import apply
        apply(self)
        for n,at in [('SMOKE01',(-4,0,5)),('SMOKE02',(1,2,4)),('SMOKE03',(0,-2,4))]:
            if n not in {b[0] for b in self.bones}:self.bone(n,at)
        world={'CHASSIS':Matrix.Identity(4)}
        for n,p,at,q in self.bones:
            rot=Quaternion((q[3],*q[:3])) if q else Quaternion()
            world[n]=world[p]@Matrix.Translation(at)@rot.to_matrix().to_4x4()
        for _,b,o,_,_ in self.parts:o.matrix_world=world[b]
        self.bake_paint()
        if self.category=='building':
            light_faces=[]
            for _,_,o,_,_ in self.parts:
                if 'AtlasUV' not in o.data.uv_layers:continue
                source=o.data.uv_layers['AtlasUV'];dest=o.data.uv_layers['PaintUV']
                for poly in o.data.polygons:
                    uv=source.data[poly.loop_start].uv;tile=int(min(3,uv.x*4))+4*int(min(3,(1-uv.y)*4))
                    if tile in (GLASS,LAMP):light_faces.append([[float(dest.data[li].uv.x),float(dest.data[li].uv.y)] for li in poly.loop_indices])
            (BUILD/(self.name+'_lights.json')).write_text(json.dumps(light_faces))
            subprocess.run(['/usr/bin/env','python3',str(HERE/'night.py'),self.name],check=True)
        groups={}
        for n,b,o,t,k in self.parts:
            unique=b if b.startswith('TIRE') else n if n.startswith('TREADS') else ''
            groups.setdefault((b,t,k,unique),[]).append((n,o))
        self.parts=[]
        for idx,((b,t,k,unique),items) in enumerate(groups.items()):
            n=unique or ('HOUSECOLOR' if k=='house' else 'MESH')+str(idx)
            o=kit.join([o for _,o in items],n) if len(items)>1 else items[0][1];o.name=n
            self.parts.append((n,b,o,t,k))
        variants=['','_D']+(['_E','_N','_DN','_EN'] if self.category=='building' else [])
        meta=[];runtime_textures=set()
        for suffix in variants:
            model=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
            flatten=lambda z:z if z<2 else 2+(z-2)*.18
            for n,p,at,q in self.bones:
                export_at=(at[0],at[1],flatten(world[n].translation.z)-flatten(world[p].translation.z)) if 'E' in suffix else at
                ids[n]=model.bone(n,ids[p],export_at,rotation=q)
            tri=0
            for n,b,o,t,k in self.parts:
                damaged=('D' in suffix or 'E' in suffix)
                tex=t.replace('.tga','_d.tga') if damaged and t==self.name.lower()+'_paint.tga' else t
                if 'N' in suffix and t==self.name.lower()+'_paint.tga':tex=self.name.lower()+'_paint'+('_dn' if damaged else '_n')+'.tga'
                runtime_textures.add(tex)
                data=mesh_data(o)
                if 'E' in suffix:
                    # Original flattened rubble geometry, retaining the footing and connection bones.
                    pivot_z=world[b].translation.z
                    data['verts']=[(x,y,flatten(z+pivot_z)-flatten(pivot_z)) for x,y,z in data['verts']]
                kw={}
                if k in ('house','decal'):kw=dict(shadow=False,shader=w3d.ALPHA_TEST_SHADER)
                if k=='track':kw=dict(shadow=False,mapper_args=puls.TREAD_MAPPER)
                model.mesh(n,ids[b],**data,texture=tex,**kw);tri+=len(data['tris'])
            if self.spins:
                rotations={ids[b]:tiger.spin(21,turns) for b,turns in self.spins.items()}
                if 'PROPELLER02' in self.spins:rotations[ids['PROPELLER02']]=[(0,math.sin(i*math.tau*self.spins['PROPELLER02']/20/2),0,math.cos(i*math.tau*self.spins['PROPELLER02']/20/2)) for i in range(21)]
                model.animate(21,30,rotations)
            model.save(str(OUT/(self.name+suffix+'.w3d')));meta.append({'model':self.name+suffix,'triangles':tri})
        self.export_animations()
        for n,b,o,t,k in self.parts:
            o.matrix_world=world[b]
            if k=='house':kit.team_colour([o])
            else:
                textured(o,load_image(str(TEX/t)))
                o.active_material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=1
        render(self)
        bpy.ops.wm.save_as_mainfile(filepath=str(BUILD/(self.name+'.blend')))
        points=[o.matrix_world@Vector(c) for _,_,o,_,_ in self.parts for c in o.bound_box]
        bounds=[[min(v[i] for v in points),max(v[i] for v in points)] for i in range(3)]
        entry=dict(key=self.key,display_name=self.label,role=self.role,category=self.category,model=self.name,variants=[m['model'] for m in meta],variant_statistics=meta,
          parent=self.inherit,suggested_inherited_object=self.inherit,dimensions=[b-a for a,b in bounds],bounds=bounds,scale=1,
          bones=[b[0] for b in self.bones],bone_transforms=[dict(name=n,parent=p,position=list(at),rotation=q) for n,p,at,q in self.bones],
          animations={s:self.name+'.'+self.name+s for s in self.animations},textures=sorted(runtime_textures),
          preview=str(BUILD/(self.name+'.png')),blend=str(BUILD/(self.name+'.blend')),
          source='scripts/models/israel/build.py',generation_command='/Applications/Blender.app/Contents/MacOS/Blender -b -t 2 -P scripts/models/israel/build.py -- '+self.name,
          polish_source='scripts/models/israel/'+('infantry_v2.py' if self.category=='infantry' else 'aircraft_v2.py' if self.name in ('ILF16','ILF15') else 'polish_geometry.py'),
          material_source='scripts/models/israel/'+('infantry_atlas_v2.png' if self.category=='infantry' else 'aviation_atlas_v2.png' if self.category=='aircraft' else 'atlas_polished.png'),
          art_revision=getattr(self,'art_revision','armour-v1'),
          geometry='Original authored geometry, no stock model or texture import',limitations=[])
        (BUILD/(self.name+'.json')).write_text(json.dumps(entry,indent=2)+'\n')
        print('ISRAEL_ASSET',self.name,meta[0]['triangles'],flush=True)

def render(v):
    sc=bpy.context.scene;sc.render.engine='BLENDER_EEVEE'
    sc.render.resolution_x=640;sc.render.resolution_y=480;sc.render.resolution_percentage=100
    sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.view_settings.exposure=-.45
    world=bpy.data.worlds.new('Israel art review');world.use_nodes=True;world.node_tree.nodes['Background'].inputs[0].default_value=(.18,.20,.22,1);world.node_tree.nodes['Background'].inputs[1].default_value=.8;sc.world=world
    sun=bpy.data.objects.new('sun',bpy.data.lights.new('sun','SUN'));sun.data.energy=2.5;sun.rotation_euler=(.6,.2,.5);sc.collection.objects.link(sun)
    cam=bpy.data.objects.new('camera',bpy.data.cameras.new('camera'));cam.data.type='ORTHO';sc.collection.objects.link(cam);sc.camera=cam
    bpy.context.view_layer.update();points=[o.matrix_world@Vector(c) for _,_,o,_,_ in v.parts for c in o.bound_box]
    lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)]);mid=(lo+hi)/2
    cam.location=mid+Vector((1,1.25,.9)).normalized()*max(hi-lo)*3;cam.rotation_euler=(mid-cam.location).to_track_quat('-Z','Y').to_euler()
    local=[cam.rotation_euler.to_quaternion().inverted()@(p-mid) for p in points]
    cam.data.ortho_scale=max(max(p.x for p in local)-min(p.x for p in local),(max(p.y for p in local)-min(p.y for p in local))*4/3)*1.12
    sc.render.filepath=str(BUILD/(v.name+'.png'));bpy.ops.render.render(write_still=True)

def tread(v,L=12,Y=6.8,width=2.8,H=4.3):
    profile=[(-L+.9,.25),(L-1,.25),(L+1,2.4),(L-.8,H),(-L+.5,H),(-L-1,2)]
    for s in (-1,1):
        v.profile('TRACKCORE',[(-L+.7,.7),(L-.4,.7),(L+.5,2.5),(L-1,H-.4),(-L+.7,H-.4),(-L-.4,2)],s*Y-width*.39,s*Y+width*.39,IRON)
        band=puls.tread_band('TREADSL' if s>0 else 'TREADSR',s,profile,(Y-width/2,Y+width/2));v.parts.append((band.name,'CHASSIS',band,'il_track.tga','track'))
        for x in [(-L+1)+i*(2*L-2)/6 for i in range(7)]:
            v.cyl('WHEEL',(x,s*(Y+width*.48),2),1.6,.42,RUBBER,'Y',cap=HUB,segments=12)
            v.cyl('HUB',(x,s*(Y+width*.59),2),.57,.22,HUB,'Y',segments=8)
        v.box('FENDER',(-L-.25,s*Y-width*.62,H+.1),(L+.5,s*Y+width*.62,H+.5),SAND,bevel=.18)
        for i in range(5):
            x=-L+1+i*(2*L-2)/5
            v.box('SKIRT',(x,s*(Y+width*.63)-.12,H-.75),(x+(2*L-2)/5-.16,s*(Y+width*.63)+.12,H+1.05),PLATE,bevel=.1)
def wheels(v,xs,y=5.2,r=2.4):
    for i,x in enumerate(xs):
        for j,s in enumerate((1,-1)):
            n=i*2+j+1;oc.tire(v,n,(x,s*y,r),r,1.45)
            v.cyl('WHEELHUB',(0,s*.83,0),r*.48,.22,HUB,'Y',bone=f'TIRE{n:02}',segments=10)
            v.box('FENDER',(x-r-.35,s*y-.95,r*1.75),(x+r+.35,s*y+.95,r*2.12),SAND,bevel=.18)
def detail(v,L=11,W=5.6,Z=6):
    v.hatch('HATCH',(-L*.65,0,Z+.2),1.2)
    for s in (-1,1):
        v.box('LIGHT', (L-.2,s*(W-.9)-.48,Z-.65),(L+.12,s*(W-.9)+.48,Z+.05),LAMP)
        v.beam('GRAB',(-L+1,s*W,Z+.25),(-L+4,s*W,Z+.25),.15)
        v.house('HOUSE',[(2,s*(W+.03),Z-.9),(5,s*(W+.03),Z-.9),(5,s*(W+.03),Z-.1),(2,s*(W+.03),Z-.1)])
    v.box('GRILLE',(-L+1,-2.2,Z+.02),(-L+5,2.2,Z+.14),VENT)
    v.cyl('AERIAL',(-L+1,W-1,Z+3),.065,6,IRON,segments=6)
def tankbase(v):
    tread(v);v.profile('HULL',[(-13,3.2),(12.2,3.2),(14,4.7),(9.5,6.7),(-11.5,6.7),(-13,5.5)],-6.2,6.2,SAND)
    detail(v,12,6.2,6.7)
def gun(v,at=(0,0,7),length=17,turret=True):
    v.bone('TURRET',at);v.bone('BARREL',(3,0,2.3),'TURRET')
    v.cyl('GUNJACKET',(length*.3,0,0),.73,length*.6,SAND,'X','BARREL',segments=10)
    v.cyl('BARREL',(length*.72,0,0),.39,length*.55,IRON,'X','BARREL',segments=10)
    v.cyl('BORE',(length,0,0),.44,.45,IRON,'X','BARREL',segments=10)
    for n in ('MUZZLE','MUZZLE01','TURRETMS','TURRETFX','MUZZLEFX01'):v.bone(n,(length+.25,0,0),'BARREL')
def rws(v,at,missile=False):
    v.bone('TURRET',at);v.cyl('RWSBASE',(0,0,.25),1.7,.5,IRON,bone='TURRET')
    v.box('RWS',(-1.2,-1.1,.3),(1.6,1.1,2),SAND,'TURRET',.2)
    v.cyl('MG',(3.2,0,1.25),.22,4,IRON,'X','TURRET',segments=8)
    v.box('OPTIC',(1.4,.5,1.4),(1.65,1.05,2),GLASS,'TURRET')
    for n in ('MUZZLE','MUZZLE01','MUZZLEFX01','TURRETMS','TURRETFX'):v.bone(n,(5.2,0,1.25),'TURRET')
def truck(v,cargo='bed'):
    wheels(v,(9,0,-8),5,2.5)
    v.box('FRAME',(-13,-3.5,2.8),(13,3.5,3.8),IRON)
    v.profile('CAB',[(5,3.8),(12,3.8),(13,5.4),(11.2,10.3),(5,10.3)],-4.4,4.4,SAND)
    v.box('GRILLE',(12.62,-3.4,5),(12.82,3.4,6.5),VENT)
    v.patch('WINDSCREEN',[(12.50,-3.7,7.1),(12.50,3.7,7.1),(11.57,3.7,9.8),(11.57,-3.7,9.8)],GLASS)
    v.beam('SCREENFRAME',(12.54,0,7.08),(11.61,0,9.82),.13,SAND)
    for s in (-1,1):
        v.box('WINDOW',(6,s*4.43-.04,7.4),(10.1,s*4.43+.04,9.7),GLASS)
        v.box('STEP',(4.9,s*4.8-.5,3.3),(7,s*4.8+.5,3.7),IRON)
        v.house('HOUSE',[(6.2,s*4.5,5),(9,s*4.5,5),(9,s*4.5,6.1),(6.2,s*4.5,6.1)])
        v.box('LIGHT',(12.9,s*3.5-.4,4.9),(13.05,s*3.5+.4,5.6),LAMP)
        v.beam('MIRROR',(8,s*4.7,9.2),(8,s*5.7,9.2),.12);v.box('MIRROR',(7.7,s*5.7-.2,8.7),(8.4,s*5.7+.2,9.9),IRON)
    v.box('BED',(-13,-4.8,3.9),(4.5,4.8,4.4),SAND)

def sandcat():
    v=Asset('ILSAND','SandCat','SandCat','Scout / light transport','AmericaVehicleHumvee')
    wheels(v,(6.6,-6),4.3,2.3)
    profile=[(-9,2.5)]
    for centre in (-6,6.6):
        profile.extend([(centre+2.7*math.cos(math.pi-i*math.pi/10),2.3+2.7*math.sin(math.pi-i*math.pi/10)) for i in range(11)])
    profile.extend([(10,4.6),(6,5.4),(3.5,9),(-7,9),(-9,6)])
    v.profile('HULL',profile,-3.8,3.8)
    v.patch('SCREEN',[(6.02,-3.25,5.65),(6.02,3.25,5.65),(3.75,3.25,8.6),(3.75,-3.25,8.6)],GLASS)
    for a,b in [((6.05,-3.35,5.61),(6.05,3.35,5.61)),((3.73,-3.35,8.67),(3.73,3.35,8.67)),((6.05,-3.35,5.61),(3.73,-3.35,8.67)),((6.05,3.35,5.61),(3.73,3.35,8.67)),((6.07,0,5.61),(3.75,0,8.67))]:v.beam('SCREENFRAME',a,b,.13,SAND)
    for s in (-1,1):
        for x in (-5,-1):
            v.box('WINDOWFRAME',(x-.16,s*3.82-.09,6.53),(x+3.16,s*3.82+.09,8.66),IRON,bevel=.09)
            v.box('WINDOW',(x,s*3.93-.02,6.7),(x+3,s*3.93+.02,8.5),GLASS)
            v.box('DOOR',(x-.1,s*3.87-.055,4.55),(x+3.13,s*3.87+.055,6.28),PLATE,bevel=.10)
            v.beam('HANDLE',(x+.5,s*4.04,6.02),(x+1.25,s*4.04,6.02),.095,IRON)
        v.box('DOORSEAM',(-1.15,s*3.85-.05,3.5),(-.95,s*3.85+.05,8.7),IRON)
        v.beam('STEP',(-7,s*4.1,2.6),(3,s*4.1,2.6),.25)
        v.beam('ROOFRAIL',(-7,s*3.5,9.15),(3,s*3.5,9.15),.14,SAND)
        v.box('LIGHTRECESS',(9.68,s*3.05-.72,3.48),(10.04,s*3.05+.72,4.30),IRON,bevel=.08)
        v.cyl('HEADLIGHT',(10.08,s*3.05,3.89),.34,.10,LAMP,'X',segments=10)
        v.beam('MIRROR',(3.2,s*3.9,7.2),(3.4,s*5,7.3),.11,IRON)
        v.box('MIRROR',(3.1,s*5-.13,7),(3.8,s*5+.13,8),IRON,bevel=.09)
    v.box('GRILLE',(9.76,-2.4,3.5),(10.01,2.4,4.35),VENT)
    v.box('BUMPER',(9.25,-4.15,2.45),(10.55,4.15,3.25),SAND,bevel=.16)
    for s in (-1,1):v.cyl('TOWEYE',(10.63,s*2.65,2.82),.28,.14,IRON,'X',segments=8)
    v.patch('HOODVENT',[(6.7,-1.8,5.30),(6.7,1.8,5.30),(8.8,1.8,4.89),(8.8,-1.8,4.89)],VENT)
    v.cyl('SPARE',(-9.18,0,5.2),2.05,1.1,RUBBER,'X',cap=HUB)
    detail(v,8.8,3.8,5.0);rws(v,(-1.7,0,9.1));return v

def merkava():
    v=Asset('ILMERK','Merkava','Merkava','Protected main battle tank','AmericaTankCrusader');tankbase(v);gun(v,(-1,0,6.8),17)
    v.profile('TURRET',[(-6.5,0),(6.2,0),(7.5,1.2),(3.9,3.5),(-4.8,3.7),(-7,2)],-5.1,5.1,bone='TURRET')
    for s in (-1,1):
        v.profile('CHEEK',[(-.5,.5),(6.5,.5),(7.8,1.4),(1.4,3.5),(-1,2.7)],s*1.2,s*5.4,PLATE,'TURRET')
        v.box('APS',(-3.1,s*5-.5,2),(-1.5,s*5+.5,3.2),PLATE,'TURRET',.15)
        for i in range(4):v.cyl('SMOKE',(-4.5+i*.6,s*5.1,1),.22,.7,IRON,'X','TURRET',segments=6)
    v.cyl('CUPOLA',(-2.8,2,4),1.4,.6,HATCH,bone='TURRET')
    v.box('OPTIC',(1,-1.8,3.4),(2.7,-.3,4.5),IRON,'TURRET');v.box('OPTICGL',(2.71,-1.65,3.6),(2.75,-.45,4.25),GLASS,'TURRET')
    for s in (-1,1):
        v.beam('BASKET',(-7,s*4.6,.5),(-9,s*4.6,2.7),.15,bone='TURRET');v.beam('BASKET',(-9,s*4.6,2.7),(-5,s*4.6,3.1),.15,bone='TURRET')
    v.bone('LASER',(0,0,4.7),'TURRET');v.bone('APSFX',(0,0,4.7),'TURRET');return v

def namer():
    v=Asset('ILNAMER','Namer','Namer','Heavy infantry transport','AmericaVehicleHumvee');tankbase(v)
    v.profile('ROOF',[(-11,6),(7,6),(5.5,9.4),(-10,9.4)],-5.5,5.5)
    v.box('REARRAMP',(-13.18,-3.7,3.4),(-12.95,3.7,8.7),DOOR)
    for s in (-1,1):
        for x in (-7,-2,3):v.box('TOPLOCKER',(x,s*4.7-.5,9.4),(x+3.3,s*4.7+.5,10.1),LOCKER)
    v.hatch('TOPHATCH',(-6,0,9.5),1.6);rws(v,(1,1.2,9.5));v.bone('EXITSTART',(-9,0,0));v.bone('EXITEND',(-19,0,0));v.bone('LASER',(0,0,2.3),'TURRET');v.bone('APSFX',(0,0,2.3),'TURRET');return v

def pereh():
    v=Asset('ILPEREH','Pereh','Pereh','Long-range missile tank hunter','AmericaVehicleTomahawk');tankbase(v)
    v.bone('TURRET',(-2,0,6.6));v.bone('TURRETEL',(-4,0,1.4),'TURRET')
    v.profile('TURRET',[(-6,0),(4,0),(5,1.5),(2,3.1),(-5,3.1)],-4.5,4.5,bone='TURRET')
    for s in (-1,1):
        v.box('MISSILEBOX',(-1,s*2.5-2,-.2),(7,s*2.5+2,3),PLATE,'TURRETEL',.16)
        for y in (-1.3,0,1.3):
            for z in (.6,2):v.cyl('TUBE',(7.05,s*2.5+y,z),.43,.18,IRON,'X','TURRETEL',segments=8)
    v.cyl('DECOYGUN',(11,0,1.5),.3,15,SAND,'X','TURRET',segments=8)
    v.bone('WEAPONA01',(7.2,2.5,1.3),'TURRETEL');v.bone('MISSILE',(6,0,1),'TURRETEL');return v

def launcher(kind):
    spy=kind=='SPYDER';v=Asset('ILSPYDR' if spy else 'ILPULS','SPYDER' if spy else 'PULS','SPYDER' if spy else 'PULS','Mobile air defence' if spy else 'Rocket artillery','AmericaVehicleAvenger' if spy else 'AmericaVehicleTomahawk');truck(v)
    v.bone('TURRET',(-5,0,4.5));v.cyl('RING',(0,0,.45),3.6,.9,IRON,bone='TURRET');v.bone('TURRETEL',(-3,0,2),'TURRET')
    for s in (-1,1):
        v.box('POD',(-.5,s*2.35-2,-.5),(10,s*2.35+2,3.6),PLATE,'TURRETEL',.17)
        for y in (-.95,.95):
            for z in (.5,2.55):v.cyl('PODCAP',(10.05,s*2.35+y,z),.67,.16,IRON,'X','TURRETEL',segments=8)
    if spy:
        v.cyl('MAST',(-8,0,9),.22,8,IRON);v.box('RADAR',(-8.7,-2.1,12),(-7.5,2.1,15),VENT,bevel=.25)
    for n in ('WEAPONA01','MUZZLE01','MUZZLE02','MUZZLEFX01','MUZZLEFX02'):v.bone(n,(10.3,2.35,1.7),'TURRETEL')
    v.bone('MISSILE',(8,0,1.5),'TURRETEL');return v

def d9():
    v=Asset('ILD9','D9','Armoured D9','Construction vehicle','AmericaVehicleDozer');tread(v,9,5.6,2.8,4)
    v.box('ENGINE',(-2,-3.5,3.7),(7,3.5,7.8),SAND,bevel=.35)
    v.profile('CAB',[(-7,3.8),(0,3.8),(0,10.8),(-1,12),(-6,12),(-7,10.5)],-3.5,3.5)
    v.box('SCREEN',(.02,-2.8,8),(.12,2.8,10.7),GLASS)
    for s in (-1,1):
        v.box('SIDEWIN',(-5.8,s*3.52-.05,8),(-1.2,s*3.52+.05,10.6),GLASS)
        v.beam('BLADERAM',(0,s*4,4),(11,s*7,2.2),.38,SAND)
    v.profile('BLADE',[(10,.4),(13,.4),(13,2),(11,7),(10.3,6.8),(11.6,1.3)],-9.3,9.3,SAND)
    v.box('CUTTINGEDGE',(12.6,-9.5,.3),(13.3,9.5,.9),IRON)
    for x in (-6,-3,0):v.box('RIPPER',(-11,x-.4,.4),(-9,x+.4,5.5),IRON)
    v.cyl('EXHAUST',(2,2.7,9.5),.35,5,IRON);v.bone('DOZERBLADE',(11,0,3));v.bone('REPAIR',(13,0,3));detail(v,7,3.5,7.8);return v

def supply():
    v=Asset('ILSUPTR','SupplyTruck','Supply truck','Resource collector','ChinaVehicleSupplyTruck');truck(v)
    v.profile('CANVAS',[(-12.5,4.5),(3,4.5),(3,9),(-12.5,9)],-4.6,4.6,TARP)
    for x in (-11,-7,-3,1):v.box('STRAP',(x-.16,-4.75,8.85),(x+.16,4.75,9.18),IRON)
    for s in (-1,1):v.box('BEDRAIL',(-13,s*4.7-.2,4.3),(4,s*4.7+.2,6),PLATE)
    v.bone('CARGO',(-6,0,5));return v

def loft(v,name,stations,tile=SAND,bone='CHASSIS',N=10):
    """Elliptical longitudinal stations: x, centre z, half width, half height."""
    bm=bmesh.new();rings=[]
    for x,z,w,h in stations:rings.append([bm.verts.new((x,math.cos(i*math.tau/N)*w,z+math.sin(i*math.tau/N)*h)) for i in range(N)])
    bm.faces.new(list(reversed(rings[0])));bm.faces.new(rings[-1])
    for a,b in zip(rings,rings[1:]):
        for i in range(N):bm.faces.new((a[i],a[(i+1)%N],b[(i+1)%N],b[i]))
    return v.mesh(name,bm,tile,bone)
def wing(v,name,outline,z,thickness=.35,tile=SAND,bone='CHASSIS'):
    bm=bmesh.new();a=[bm.verts.new((x,y,z)) for x,y in outline];b=[bm.verts.new((x,y,z+thickness)) for x,y in outline]
    bm.faces.new(list(reversed(a)));bm.faces.new(b)
    for i in range(len(a)):j=(i+1)%len(a);bm.faces.new((a[i],a[j],b[j],b[i]))
    return v.mesh(name,bm,tile,bone)
def jet(f15=False):
    from aircraft_v2 import create
    return create(sys.modules[__name__],f15)

def apache():
    v=Asset('ILAPACH','Apache','AH-64 Apache','Attack helicopter','AmericaVehicleComanche',category='aircraft')
    loft(v,'BODY',[(-17,4,.5,.6),(-9,4,1.1,1),(-4,4,3,2.7),(6,4,3.2,2.9),(13,3.7,2.4,2.5),(17,3,.7,1.2)])
    loft(v,'CANOPY',[(2,6.2,2.4,1),(6,7,2.45,1.9),(10,6,2.2,1.9),(14,4.8,1.6,1.1)],GLASS)
    v.beam('CANOPYFRAME',(7,2.48,5.7),(7,2.48,8),.15,SAND);v.beam('CANOPYFRAME',(7,-2.48,5.7),(7,-2.48,8),.15,SAND)
    for s in (-1,1):
        # Twin turboshaft housings, stub wings, wing-mounted missiles.
        for x in (-5,):
            obj=loft(v,'ENGINE',[(-8,6.2,1.45,1.45),(-6,6.3,1.65,1.5),(0,6.3,1.5,1.3),(2,6,1,1)])
            for vert in obj.data.vertices:vert.co.y+=s*3.1
        wing(v,'STUBWING',[(-4,s*2),(-3,s*9),(1,s*9),(2,s*2)],3.6,.5)
        v.cyl('POD',(.3,s*7.1,2.2),1.35,5.3,SAND,'X',segments=10)
        for y,z in ((0,0),(.55,.45),(-.55,.45),(0,-.6)):v.cyl('ROCKET',(3,s*7.1+y,2.2+z),.26,.12,IRON,'X',segments=6)
        v.beam('GEAR',(6,s*2.3,2.8),(7,s*4,.6),.23,IRON);v.cyl('WHEEL',(7,s*4,.8),.85,.7,RUBBER,'Y',cap=HUB)
    v.profile('TAILFIN',[(-17,4),(-18,10),(-14.8,9.3),(-13.5,4)],-.23,.23)
    wing(v,'TAILPLANE',[(-15,-6),(-12,-6),(-11,6),(-14,6)],4,.24)
    v.cyl('TAILWHEEL',(-14,0,.65),.65,.55,RUBBER,'Y',cap=HUB)
    v.bone('PROPELLER01',(-1,0,9));v.cyl('MAST',(0,0,-1),.4,2,IRON,bone='PROPELLER01');v.cyl('HUB',(0,0,.25),1.2,.6,IRON,bone='PROPELLER01')
    for a in (0,math.pi/2,math.pi,3*math.pi/2):
        coords=[(2,-.5),(20,-1),(21,.3),(2,.6)];outline=[(x*math.cos(a)-y*math.sin(a),x*math.sin(a)+y*math.cos(a)) for x,y in coords]
        wing(v,'BLADE',outline,.1,.15,IRON,'PROPELLER01')
    v.bone('PROPELLER02',(-17,-.7,7));v.box('TAILROTOR',(-3,-.1,-.25),(3,.1,.25),IRON,'PROPELLER02');v.box('TAILROTOR',(-.25,-.1,-3),(.25,.1,3),IRON,'PROPELLER02')
    v.spins={'PROPELLER01':1,'PROPELLER02':2}
    v.bone('TURRET',(12,0,1.7));v.cyl('GUN',(2,0,0),.2,4,IRON,'X','TURRET',segments=8)
    for n,at,p in [('MUZZLE01',(4.3,0,0),'TURRET'),('WEAPONA01',(3,7,2.2),'CHASSIS'),('WEAPONA02',(3,-7,2.2),'CHASSIS')]:v.bone(n,at,p)
    v.house('HOUSE',[(-10,.9,4),(-7,1.3,4),(-7,1.3,5),(-10,.9,5)]);return v

def infantry(kind):
    from infantry_v2 import create
    return create(sys.modules[__name__],kind)

def slab(v,L,W):v.box('FOUNDATION',(-L,-W,0),(L,W,1.2),CONCRETE,bevel=.35)
def hall(v,x0,x1,y0,y1,H,roof='flat'):
    v.box('WALL',(x0,y0,1),(x1,y1,H),CONCRETE,bevel=.45)
    v.box('PLINTH',(x0-.8,y0-.8,1),(x1+.8,y1+.8,3),SAND)
    for s,y in ((-1,y0),(1,y1)):
        for x in range(int(x0)+5,int(x1)-4,10):
            v.box('WINDOW',(x,y+s*.12,H*.6),(x+4,y+s*.3,H*.6+2.5),GLASS)
            v.box('PIER',(x-3,y-.6,2),(x-1.7,y+.6,H+.8),SAND)
        v.box('ROOFBAND',(x0-1,y-.65,H-.8),(x1+1,y+.65,H+1.1),SAND)
    if roof=='vault':
        span=(y1-y0)/2;cy=(y0+y1)/2
        # Arched reinforced concrete roof, constructed across longitudinal ribs.
        pts=[(cy+span*math.cos(a),H+span*.42*math.sin(a)) for a in [math.pi-i*math.pi/10 for i in range(11)]]
        bm=bmesh.new();a=[bm.verts.new((x0,y,z)) for y,z in pts];b=[bm.verts.new((x1,y,z)) for y,z in pts]
        bm.faces.new(list(reversed(a)));bm.faces.new(b)
        for i in range(len(a)-1):bm.faces.new((a[i],a[i+1],b[i+1],b[i]))
        v.mesh('VAULT',bm,SAND)
        for x in [x0+i*(x1-x0)/5 for i in range(6)]:
            for p,q in zip(pts,pts[1:]):v.beam('ROOFRIB',(x,p[0],p[1]+.2),(x,q[0],q[1]+.2),.3,SAND)
    else:
        v.box('ROOF',(x0-.5,y0-.5,H),(x1+.5,y1+.5,H+.7),SAND)
        for y in (y0,y1):v.box('PARAPET',(x0-.8,y-.7,H),(x1+.8,y+.7,H+1.6),CONCRETE)
        for x in (x0,x1):v.box('PARAPET',(x-.7,y0,H),(x+.7,y1,H+1.6),CONCRETE)
    # Service door and lintel.
    v.box('DOOR',(x1+.03,(y0+y1)/2-3,1),(x1+.18,(y0+y1)/2+3,9),DOOR)
    v.box('CANOPY',(x1,(y0+y1)/2-4,9),(x1+3,(y0+y1)/2+4,9.8),SAND)
    v.house('HOUSE',[(x0+2,y0-.8,H-4),(x0+12,y0-.8,H-4),(x0+12,y0-.8,H-2),(x0+2,y0-.8,H-2)])
def ac(v,x,y,z):
    v.box('AC',(x-3,y-3,z),(x+3,y+3,z+3.8),SAND,bevel=.3);v.box('ACVENT',(x+3.02,y-2.5,z+.6),(x+3.12,y+2.5,z+3.2),VENT)
    v.cyl('FAN',(x,y,z+3.9),2.1,.17,VENT,segments=12)
def mast(v,x,y,z,H=25,dish=True):
    for dx,dy in ((-1,-1),(-1,1),(1,1),(1,-1)):
        v.beam('MAST',(x+dx*1.3,y+dy*1.3,z),(x+dx*.5,y+dy*.5,z+H),.18,IRON)
    for k in range(5):
        a=z+k*H/5;b=z+(k+1)*H/5
        v.beam('BRACE',(x-1,y-1,a),(x+1,y-1,b),.11,IRON)
        v.beam('BRACE',(x-1,y+1,a),(x+1,y+1,b),.11,IRON)
    if dish:
        v.cyl('RADARDISH',(x+1.5,y,z+H*.72),3.5,1,SAND,'X',segments=14);v.cyl('RADARCENTRE',(x+2.1,y,z+H*.72),.6,2,IRON,'X',segments=8)
    v.cyl('ANTENNA',(x,y,z+H+2),.1,4,IRON,segments=6)
def crates(v,x,y,rows=3):
    for i in range(rows):
        v.box('CRATE',(x+i*6,y,1.3),(x+i*6+5,y+6,6),LOCKER,bevel=.15)
        v.box('STRAP',(x+i*6+2,y-.1,6),(x+i*6+2.4,y+6.1,6.2),IRON)
def exitbones(v,start=(0,0,0),end=(55,0,0)):
    v.bone('EXITSTART',start);v.bone('EXITEND',end)
def building(kind):
    specs={
     'CommandCentre':('ILCMD','Command centre','AmericaCommandCenter'),
     'Power':('ILPOWER','Power plant','AmericaPowerPlant'),
     'Barracks':('ILBARR','Barracks','AmericaBarracks'),
     'SupplyCentre':('ILSUPPLY','Supply centre','ChinaSupplyCenter'),
     'Factory':('ILFACT','Armour factory','AmericaWarFactory'),
     'Airfield':('ILAIR','Airfield','AmericaAirfield'),
     'TechCentre':('ILTECH','Defence research centre','AmericaStrategyCenter'),
     'Income':('ILINCOME','Trade office','AmericaSupplyDropZone'),
     'GroundDefence':('ILGDEF','Spike defence bunker','AmericaPatriotBattery'),
     'AirDefence':('ILADEF','Air defence battery','AmericaPatriotBattery'),
     'Superweapon':('ILSUPER','Strategic missile battery','AmericaParticleCannonUplink')}
    name,label,inherit=specs[kind];v=Asset(name,kind,label,kind,inherit,'building')
    if kind=='CommandCentre':
        slab(v,60,62);hall(v,-43,24,-20,24,19);hall(v,-45,-15,28,52,12)
        v.cyl('TOWER',(-29,-43,15),12,28,CONCRETE,segments=8);v.cyl('CONTROL',(-29,-43,31),13,5,GLASS,segments=8);v.cyl('CONTROLROOF',(-29,-43,34.3),14.5,1.7,SAND,segments=8)
        v.ellipsoid('RADOME',(-29,-43,39),(7,7,6),SAND);mast(v,-47,2,20,29)
        for x in (-25,-5,15):ac(v,x,-5,20)
        crates(v,20,38,3);exitbones(v,(-18.8,34.5,.3),(50.9,34.5,.3))
    elif kind=='Power':
        slab(v,34,32);hall(v,-25,11,-22,1,14)
        for x in (-20,-8,4):
            v.cyl('GENERATOR',(x,14,8),4.5,12,SAND,segments=12);v.cyl('COOLER',(x,14,15),5.3,2,VENT,segments=12)
            v.beam('PIPE',(x,-2,5),(x,14,5),.7,IRON)
        for y in (-15,-2,11):
            v.box('TRANSFORMER',(17,y,1.5),(27,y+8,8),VENT,bevel=.3)
            for x in (19,25):v.cyl('INSULATOR',(x,y+4,11),.8,6,DOOR,segments=8)
        for x in (-18,-2):ac(v,x,-10,15)
    elif kind=='Barracks':
        slab(v,48,41);hall(v,-37,-3,-29,26,13);hall(v,0,34,-29,-7,13)
        for x in (3,12,21):v.box('BUNKER',(x,12,1.3),(x+6,28,5.5),TARP,bevel=.8)
        v.box('GATEPOST',(34,-5,1),(38,0,10),CONCRETE);v.box('GATEPOST',(34,17,1),(38,22,10),CONCRETE)
        mast(v,-30,17,14,13,False);crates(v,-3,29,4);exitbones(v,(20,8,0),(54,8,0))
    elif kind=='SupplyCentre':
        slab(v,44,43);hall(v,-36,-3,-30,29,15,'vault')
        for x,y in ((3,-30),(3,-18),(3,19),(20,19)):crates(v,x,y,2)
        v.box('DOCKPLATE',(1,-10,1),(30,10,1.4),CAUTION)
        # Open truck apron. China SupplyCenter stores supplies, SupplyTruck drives through these bones.
        for n,at in [('DOCKSTART',(54,0,0)),('DOCKACTION',(23,0,0)),('DOCKEND',(57,0,0))]:v.bone(n,at)
        for i,at in enumerate(((68,-24,0),(68,24,0),(83,0,0),(89,31,0)),1):v.bone(f'DOCKWAITING{i:02}',at)
        exitbones(v,(23,0,0),(58,0,0));ac(v,-20,0,29)
    elif kind=='Factory':
        slab(v,54,60);hall(v,-43,36,-48,-12,22,'vault');hall(v,-43,20,19,49,15)
        # Factory portal at +X, matching the production lane y=-30.
        v.box('DARKPORTAL',(36.1,-43,1),(36.3,-17,18),IRON);v.box('PORTALFRAME',(35,-45,17.5),(39,-15,20),CAUTION)
        v.box('SERVICE',(21,5,1.3),(50,31,1.7),CAUTION)
        for x in (-25,-3):ac(v,x,32,16)
        crates(v,-38,52,5);mast(v,-46,8,2,26)
        exitbones(v,(-10,-30,.3),(53,-30,.3))
        for n,at in [('DOCKSTART',(66.9,16.2,.3)),('DOCKACTION',(46.5,16.2,.3)),('DOCKEND',(73.1,16.2,.3))]:v.bone(n,at)
        for i,(x,y) in enumerate(((116,44),(116,98),(68,98),(14,98),(-38,98),(-96,98),(-94,40),(-94,-17),(-94,-65)),1):v.bone(f'DOCKWAITING{i:02}',(x,y,.3))
    elif kind=='Airfield':
        slab(v,112,74);v.box('RUNWAY',(-48,-67,1.21),(111,3,1.34),IRON)
        for y in (-49,-13):
            for x in range(-37,100,21):v.box('RUNWAYSTRIPE',(x,y-.7,1.36),(x+12,y+.7,1.39),LAMP)
        # Hangars end behind the exact USA parking and runway contracts.
        for x in (-37,-6):
            hall(v,x,x+29,39,69,13,'vault')
            v.box('HANGARMOUTH',(x+2,38.85,1.5),(x+27,39,11),IRON)
        for y in (-61,-25):hall(v,-109,-87,y,y+28,12,'vault')
        v.cyl('TOWER',(92,48,12),7,23,CONCRETE,segments=8);v.cyl('CAB',(92,48,25),8,5,GLASS,segments=8);v.cyl('CAP',(92,48,28),9,1.4,SAND,segments=8)
        v.cyl('HELIPAD',(66.7,41.6,1.4),17,.14,DOOR,segments=20)
        v.box('HELIMARK',(62,35,1.52),(64,48,1.55),LAMP);v.box('HELIMARK',(69,35,1.52),(71,48,1.55),LAMP);v.box('HELIMARK',(62,41,1.52),(71,43,1.55),LAMP)
        import air_base
        for n,at,yaw in air_base.BONES:v.bone(n,at,rotation=(0,0,math.sin(math.radians(yaw)/2),math.cos(math.radians(yaw)/2)))
        for x in range(-45,112,20):
            for y in (-67,3):v.box('LIGHT',(x,y,1.3),(x+.7,y+.7,2),LAMP)
    elif kind=='TechCentre':
        slab(v,49,46);hall(v,-37,28,-32,17,18);hall(v,-35,-10,21,36,12)
        v.cyl('SENSORBASE',(-10,-8,21),10,4,SAND,segments=12);v.ellipsoid('DOME',(-10,-8,29),(9,9,8),SAND)
        for y in (-20,0,20):mast(v,36,y,1,24 if y else 34)
        ac(v,16,-15,19);crates(v,4,29,4)
    elif kind=='Income':
        slab(v,43,42);hall(v,-34,13,-31,-8,17);hall(v,-34,-11,-5,28,12)
        v.box('CARGOPAD',(-3,-1,1.3),(35,33,1.6),DOOR)
        for x in (0,30):v.box('CARGOMARK',(x,1,1.62),(x+2,30,1.66),LAMP)
        for y in (1,29):v.box('CARGOMARK',(0,y,1.62),(32,y+2,1.66),LAMP)
        crates(v,-31,30,4);ac(v,-13,-19,18);v.bone('SUPPLIES',(15,15,2));v.bone('OCLSPAWN',(15,15,2))
    elif kind in ('GroundDefence','AirDefence'):
        slab(v,17,17);v.cyl('BUNKER',(0,0,4.5),13,7,CONCRETE,segments=8);v.cyl('RING',(0,0,8),7,1,SAND,segments=12)
        v.bone('TURRET',(0,0,8));v.bone('TURRETEL',(-2,0,1),'TURRET')
        if kind=='GroundDefence':
            v.box('SPIKEBOX',(-2,-4,0),(7,4,3.4),PLATE,'TURRETEL',.2)
            for y in (-2.4,0,2.4):v.cyl('TUBE',(7.1,y,1.7),.8,.2,IRON,'X','TURRETEL',segments=8)
            v.box('SIGHT',(-3,-1,3.4),(-1,1,5.3),GLASS,'TURRET')
        else:
            for s in (-1,1):
                v.box('MISSILEBANK',(-4,s*4-2,0),(8,s*4+2,4.5),PLATE,'TURRETEL',.2)
                for y in (-1,1):
                    for z in (1.2,3.4):v.cyl('CAP',(8.1,s*4+y,z),.75,.2,IRON,'X','TURRETEL',segments=8)
            mast(v,-9,8,5,12)
        for i,y in enumerate((-2.5,2.5),1):v.bone(f'WEAPONA{i:02}',(8.3,y,2),'TURRETEL');v.bone(f'MUZZLE{i:02}',(8.3,y,2),'TURRETEL')
        v.house('HOUSE',[(-6,-12,4),(6,-12,4),(6,-12,6),(-6,-12,6)])
    elif kind=='Superweapon':
        slab(v,57,52);hall(v,-46,-18,-37,37,17);hall(v,-13,42,27,42,10)
        for x in (4,29):
            v.cyl('SILO',(x,-9,3),10.5,4,CONCRETE,segments=16);v.cyl('SILOCAP',(x,-9,5.4),9,1.2,PLATE,segments=16)
            for s in (-1,1):v.box('RAIL',(x-12,s*11-9,2),(x+12,s*11-9+.6,3.5),IRON)
            v.bone('LAUNCH'+str(1 if x==4 else 2),(x,-9,7))
        mast(v,-32,19,18,31);ac(v,-32,-17,18);crates(v,-4,-41,6);v.bone('WEAPONA01',(4,-9,7));v.bone('FXBONE',(4,-9,7))
    return v

JOBS={
 'ILSAND':sandcat,'ILMERK':merkava,'ILNAMER':namer,'ILPEREH':pereh,'ILSPYDR':lambda:launcher('SPYDER'),'ILPULS':lambda:launcher('PULS'),
 'ILD9':d9,'ILSUPTR':supply,'ILF16':jet,'ILF15':lambda:jet(True),'ILAPACH':apache,
 'ILRIFLE':lambda:infantry('Rifleman'),'ILSPIKE':lambda:infantry('Spike'),'ILCOMM':lambda:infantry('Commando')}
for key,name in [('CommandCentre','ILCMD'),('Power','ILPOWER'),('Barracks','ILBARR'),('SupplyCentre','ILSUPPLY'),('Factory','ILFACT'),('Airfield','ILAIR'),('TechCentre','ILTECH'),('Income','ILINCOME'),('GroundDefence','ILGDEF'),('AirDefence','ILADEF'),('Superweapon','ILSUPER')]:JOBS[name]=lambda key=key:building(key)

def main():
    BUILD.mkdir(parents=True,exist_ok=True);OUT.mkdir(parents=True,exist_ok=True)
    if any(not (TEX/name).exists() for name in ('il_atlas.tga','il_infantry_atlas.tga','il_aircraft_atlas.tga')):
        subprocess.run(['/usr/bin/env','python3',str(HERE/'paint.py')],check=True)
    ids=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(JOBS)
    for name in ids:
        bpy.ops.wm.read_factory_settings(use_empty=True);JOBS[name]().finish()
    entries=[json.loads((BUILD/(name+'.json')).read_text()) for name in JOBS if (BUILD/(name+'.json')).exists()]
    manifest={'faction':'Israel','version':2,'style':'Layered grey-olive armour, redundant sensors, deep fittings, crew stowage, worn material detail and restrained team colour','axis_contract':'+X forward, +Z up; use Scale 1.0 unless gameplay deliberately changes silhouette',
      'assets':entries,'runtime_directory':'resources/macos/GameData/Art/W3D','texture_directory':'resources/macos/GameData/Art/TexturesHD',
      'infantry_contract':'Original rigid articulated infantry. Explicit MODEL.MODEL_I stationary pose resets the previous clip; MODEL.MODEL_R moving loop, MODEL.MODEL_F attack loop, MODEL.MODEL_X dying ONCE. No stock animation dependencies.',
      'supply_contract':'ILSUPPLY uses ChinaSupplyCenter truck workflow. DockStart/Action/End + waiting bones, idle ILSUPTR and no helicopter pads.',
      'factory_contract':'Factory INI ExitStart=(-10,-30,.3), ExitEnd=(53,-30,.3). RepairDock named bones match AmericaWarFactory. Barracks ExitStart=(20,8,0), ExitEnd=(54,8,0).',
      'airfield_contract':'All USA Airfield runway parking/hangar/prep/start/end bones and HELIPARK01 preserved. Original architecture aligns to these paths.',
      'superweapon_contract':'Original abstract strategic missile silo; launch bones LAUNCH1, LAUNCH2, WEAPONA01, FXBONE. Gameplay ability supplied by integration.',
      'limitations':['Generic original flattened building wreck geometry; destruction rubble can be hand-authored later.','Infantry are original rigid low-poly figures with run/fire/fall animation; lack prone and rappel animation.']}
    (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
if __name__=='__main__':main()

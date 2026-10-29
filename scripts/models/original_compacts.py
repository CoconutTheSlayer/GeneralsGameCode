"""Original EU light vehicles, built from authored geometry and a painted atlas.

No game models or texture archives are imported. The common Blender helpers only
construct mathematical meshes. Source art and its generation prompts live in
art/compact; the exporter preserves the engine's wheel, turret and upgrade names.

Blender -b -P scripts/models/original_compacts.py -- EUWIEST EUPATRIA EUVALUK EUDRONE EUMV4
"""
from pathlib import Path
import hashlib
import json
import math
import sys
import bpy
import bmesh
from mathutils import Matrix, Quaternion, Vector

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import engineer as kit
import puls
import tiger
import w3d
from blender_kit import box, cylinder, new_object, mesh_data, textured, load_image
from coalition_ground import shell
from coalition import render

ROOT = HERE.parents[1]
ART = HERE/'art/compact'
TEX = ROOT/'resources/macos/GameData/Art/TexturesHD'
OUT = ROOT/'resources/macos/GameData/Art/W3D'
BUILD = ROOT/'build/models'
ATLAS = 'eucompact_painted_v2.tga'
TRACK = 'eucompact_track_v2.tga'
# Tile indices in the hand-painted source, from the upper left.
STEEL, PLATE, VENT, LOCKER, HATCH, HUB, RUBBER, TREAD, IRON, GLASS, TUBE, TARP, MEDICAL, CAUTION, LAMP, DOOR = range(16)


def prepare_textures():
    """Only format conversion and extraction: keep the authored pixels unchanged."""
    import subprocess
    subprocess.run(['/usr/bin/env', 'python3', str(HERE/'prepare_compact_textures.py')], check=True)


def unwrap(obj, tile, cap_axis=None, cap_tile=None):
    uv = obj.data.uv_layers.new(name='UVMap')
    for p in obj.data.polygons:
        axis = max(range(3), key=lambda i: abs(p.normal[i]))
        axes = {0:(1,2), 1:(0,2), 2:(0,1)}[axis]
        points = [obj.data.vertices[obj.data.loops[i].vertex_index].co for i in p.loop_indices]
        lo = [min(v[a] for v in points) for a in axes]
        hi = [max(v[a] for v in points) for a in axes]
        t = cap_tile if cap_axis == axis and abs(p.normal[axis]) > .99 else tile
        if t is None: t = tile
        col, row = t % 4, t // 4
        # Inset by 3% of each tile, avoiding neighbouring pixels at coarse mip levels.
        for i, v in zip(p.loop_indices, points):
            u = (v[axes[0]]-lo[0])/max(.001, hi[0]-lo[0])
            vv = (v[axes[1]]-lo[1])/max(.001, hi[1]-lo[1])
            inset=.008 if t==STEEL else .03
            uv.data[i].uv = ((col+inset+u*(1-2*inset))/4, 1-(row+1-inset-vv*(1-2*inset))/4)


class Vehicle:
    def __init__(self, name):
        self.name = name
        self.parts = []
        self.bones = []
        self.spins = {}

    def bone(self, name, at=(0,0,0), parent='CHASSIS', rotation=None):
        self.bones.append((name,parent,at,rotation))
        return name

    def mesh(self, name, bm, tile=STEEL, bone='CHASSIS', cap_axis=None, cap_tile=None, recalc=True):
        if recalc:bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        obj = new_object(name, bm)
        unwrap(obj, tile, cap_axis, cap_tile)
        self.parts.append((name,bone,obj,ATLAS,'solid'))
        return obj

    def box(self, name, lo, hi, tile=STEEL, bone='CHASSIS', bevel=0):
        bm = bmesh.new(); box(bm,lo,hi)
        if bevel: kit.bevel_sharp(bm, bevel)
        return self.mesh(name,bm,tile,bone)

    def cyl(self, name, at, r, length, tile=IRON, axis='Z', bone='CHASSIS', cap=None, segments=12):
        bm=bmesh.new(); cylinder(bm,at,r,length,axis=axis,segments=segments)
        return self.mesh(name,bm,tile,bone, 'XYZ'.index(axis), cap)

    def patch(self, name, corners, tile, bone='CHASSIS'):
        # Winding is explicit at call sites; duplicated back faces make mirror-safe decals.
        bm=bmesh.new()
        bm.faces.new([bm.verts.new(p) for p in corners])
        bm.faces.new([bm.verts.new(p) for p in reversed(corners)])
        # Do not recalculate disconnected coplanar faces: Blender may turn both
        # toward the same side, making markings vanish in the engine's back-face culling.
        obj=self.mesh(name,bm,tile,bone,recalc=False)
        n,b,o,t,_=self.parts[-1]
        self.parts[-1]=(n,b,o,t,'decal')
        # Map the four corners, rather than a bounding box: sloping panels keep their shape.
        uv=obj.data.uv_layers.active
        col,row=tile%4,tile//4
        for poly in obj.data.polygons:
            for i in poly.loop_indices:
                co=obj.data.vertices[obj.data.loops[i].vertex_index].co
                n=min(range(4),key=lambda j:(co-Vector(corners[j])).length)
                u,v=((0,0),(1,0),(1,1),(0,1))[n]
                uv.data[i].uv=((col+.035+u*.93)/4,1-(row+.965-v*.93)/4)
        return obj

    def body(self, name, stations, tile=STEEL):
        bm=bmesh.new(); shell(bm,stations)
        return self.mesh(name,bm,tile)

    def beam(self, name, start, end, width=.18, tile=IRON, bone='CHASSIS'):
        bm=bmesh.new();kit.beam(bm,start,end,width,width)
        return self.mesh(name,bm,tile,bone)

    def hatch(self, name, at, r=1.4):
        self.cyl(name+'RIM', at,r+.12,.16,IRON)
        self.cyl(name,(at[0],at[1],at[2]+.13),r,.18,STEEL,cap=HATCH,segments=12)
        x,y,z=at
        self.box(name+'HINGE',(x-r-.1,y-.36,z+.1),(x-r+.45,y+.36,z+.43),IRON)
        self.beam(name+'HANDLE',(x-.4,y,z+.5),(x+.4,y,z+.5),.16,IRON)

    def house(self, name, corners):
        obj=self.patch(name,corners,STEEL)
        n,b,o,_,_=self.parts[-1]
        self.parts[-1]=(n,b,o,w3d.HOUSE_COLOUR_TEXTURE,'house')
        for loop in obj.data.uv_layers.active.data:loop.uv=(.5,.5)

    def finish(self):
        self.bone('SMOKE01',(-4,0,5));self.bone('SMOKE02',(1,2,4));self.bone('SMOKE03',(0,-2,4))
        world={'CHASSIS':Matrix.Identity(4)}
        for n,p,at,q in self.bones:
            rotation=Quaternion((q[3],*q[:3])) if q else Quaternion()
            world[n]=world[p]@Matrix.Translation(at)@rotation.to_matrix().to_4x4()
        for _,b,o,_,_ in self.parts:o.matrix_world=world[b]
        self.bake_paint()
        # Group static objects but preserve names the draw module hides or scrolls.
        groups={}
        for n,b,o,t,k in self.parts:
            unique=n if n.startswith(('TREADS','TIRE','TURRETUP09','TURRETFX')) else ''
            groups.setdefault((b,t,k,unique),[]).append((n,o))
        parts=[]
        for (b,t,k,_),items in groups.items():
            n=items[0][0];o=kit.join([o for _,o in items],n) if len(items)>1 else items[0][1]
            parts.append((n,b,o,t,k))
        self.parts=parts
        triangles=0
        for suffix in ('','_D'):
            model=w3d.Model(self.name+suffix);ids={'CHASSIS':w3d.CHASSIS}
            for n,p,at,q in self.bones:ids[n]=model.bone(n,ids[p],at,rotation=q)
            for n,b,o,t,k in parts:
                tex=t.replace('.tga','_d.tga') if suffix and t==self.name.lower()+'_paint.tga' else t
                kw={}
                if k in ('house','decal'):kw=dict(shadow=False,shader=w3d.ALPHA_TEST_SHADER)
                elif k=='track':kw=dict(shadow=False,mapper_args=puls.TREAD_MAPPER)
                data=mesh_data(o)
                if not suffix:triangles+=len(data['tris'])
                model.mesh(n,ids[b],**data,texture=tex,**kw)
            if self.spins:model.animate(21,30,{ids[b]:tiger.spin(21,turns) for b,turns in self.spins.items()})
            model.save(str(OUT/(self.name+suffix+'.w3d')))
        world={'CHASSIS':Matrix.Identity(4)}
        for n,p,at,q in self.bones:
            rotation=Quaternion((q[3],*q[:3])) if q else Quaternion()
            world[n]=world[p]@Matrix.Translation(at)@rotation.to_matrix().to_4x4()
        for n,b,o,t,k in parts:
            o.matrix_world=world[b]
            if k=='house':kit.team_colour([o])
            else:
                textured(o,load_image(str(TEX/t)))
                o.active_material.node_tree.nodes['Principled BSDF'].inputs['Roughness'].default_value=1
            if n.startswith(('TURRETUP09','TURRETFX')):o.hide_render=True
        bpy.ops.wm.save_as_mainfile(filepath=str(BUILD/(self.name+'.blend')))
        render(self.name,parts)
        (BUILD/(self.name+'_provenance.json')).write_text(json.dumps({
            'model':self.name,'builder':str(Path(__file__).relative_to(ROOT)),
            'geometry':'Original authored mathematical meshes; no game model imports',
            'source_texture':'scripts/models/art/compact/eu_compact_atlas_v2.png',
            'source_texture_sha256':hashlib.sha256((ART/'eu_compact_atlas_v2.png').read_bytes()).hexdigest(),
            'triangles':triangles,'meshes':len(parts),'bones':[b[0] for b in self.bones],
            'textures':sorted(set(p[3] for p in parts)),
        },indent=2)+'\n')
        print('ORIGINAL_COMPACT',self.name,triangles,'triangles',len(parts),'meshes',flush=True)

    def bake_paint(self):
        """Bake the authored paint and assembled occlusion into one original UV map.

        The runtime has no ambient-occlusion shader. Broad undercuts and fitting
        shadows need to be in the diffuse texture, just as in period RTS art.
        """
        objects=[o for _,_,o,t,_ in self.parts if t==ATLAS]
        decal_objects={o for _,_,o,_,kind in self.parts if kind=='decal'}
        bpy.ops.object.select_all(action='DESELECT')
        for o in objects:
            o.select_set(True)
            o.data.uv_layers.active.name='AtlasUV'
            o.data.uv_layers.new(name='PaintUV')
            o.data.uv_layers.active_index=1
            o.data.uv_layers['PaintUV'].active_render=True
        bpy.context.view_layer.objects.active=objects[0]
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.select_all(action='SELECT')
        bpy.ops.uv.smart_project(angle_limit=.80,island_margin=.007,area_weight=.1)
        bpy.ops.object.mode_set(mode='OBJECT')
        scene=bpy.context.scene;scene.render.engine='CYCLES'
        scene.cycles.device='CPU';scene.cycles.samples=24
        scene.render.bake.margin=4
        source_nodes=[];targets=[]
        for o in objects:
            mat=bpy.data.materials.new(o.name+'_Bake');mat.use_nodes=True
            tree=mat.node_tree;tree.nodes.clear();n=tree.nodes;link=tree.links.new
            uv=n.new('ShaderNodeUVMap');uv.uv_map='AtlasUV'
            src=n.new('ShaderNodeTexImage');link(uv.outputs['UV'],src.inputs['Vector']);source_nodes.append(src)
            ao=n.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=3.6
            # Strong contact shading, with a readable minimum for tiny fittings.
            ao_remap=n.new('ShaderNodeMapRange');ao_remap.inputs['To Min'].default_value=.38
            ao_remap.inputs['To Max'].default_value=1.20;link(ao.outputs['AO'],ao_remap.inputs['Value'])
            # Two-sided surface markings sit just above the hull. Their backing
            # face must not bake a dark occlusion stain over white medical paint.
            if o in decal_objects:ao_remap.inputs['To Min'].default_value=.95
            geom=n.new('ShaderNodeNewGeometry');xyz=n.new('ShaderNodeSeparateXYZ');link(geom.outputs['Position'],xyz.inputs[0])
            height=n.new('ShaderNodeMapRange');height.inputs['From Min'].default_value=.7;height.inputs['From Max'].default_value=5.5
            height.inputs['To Min'].default_value=.65;height.inputs['To Max'].default_value=1.10;link(xyz.outputs['Z'],height.inputs['Value'])
            mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY';link(ao_remap.outputs[0],mul.inputs[0]);link(height.outputs[0],mul.inputs[1])
            col=n.new('ShaderNodeMixRGB');col.blend_type='MULTIPLY';col.inputs[0].default_value=1
            link(src.outputs['Color'],col.inputs[1]);link(mul.outputs[0],col.inputs[2])
            emit=n.new('ShaderNodeEmission');link(col.outputs[0],emit.inputs[0])
            output=n.new('ShaderNodeOutputMaterial');link(emit.outputs[0],output.inputs['Surface'])
            target=n.new('ShaderNodeTexImage');n.active=target;targets.append(target)
            o.data.materials.clear();o.data.materials.append(mat)
            for p in o.data.polygons:p.material_index=0
        for suffix in ('','_d'):
            source=load_image(str(TEX/ATLAS.replace('.tga',suffix+'.tga')))
            for node in source_nodes:node.image=source
            name=self.name.lower()+'_paint'+suffix+'.tga'
            dest=bpy.data.images.new(name,1024,1024,alpha=False)
            for node in targets:node.image=dest
            bpy.ops.object.bake(type='EMIT',use_clear=True)
            dest.filepath_raw=str(TEX/name);dest.file_format='TARGA';dest.save()
        self.parts=[(n,b,o,self.name.lower()+'_paint.tga' if t==ATLAS else t,k) for n,b,o,t,k in self.parts]
        # Runtime exports the active UV layer. Retain the source UVs in the blend
        # project so the asset can be repainted and rebaked without remodelling.
        for o in objects:
            o.data.uv_layers.active_index=1
            o.data.uv_layers['PaintUV'].active_render=True


def tracks(v, length=9, y=4.6, width=2.2, height=3.5):
    profile=[(-length+.9,.2),(length-1.6,.2),(length,1.8),(length-.65,height-.25),
             (-length+.6,height),(-length-.25,1.65)]
    for side in (-1,1):
        bm=bmesh.new();kit.prism_xz(bm,[(x,z+.1 if z<1 else z-.2) for x,z in profile],side*y-width*.45,side*y+width*.45)
        v.mesh('TRACKCORE'+str(side),bm,IRON)
        band=puls.tread_band('TREADSL' if side>0 else 'TREADSR',side,profile,(y-width/2,y+width/2))
        v.parts.append((band.name,'CHASSIS',band,TRACK,'track'))
        for x,z,r in [(-length+.8,1.8,1.0),(-length*.61,1.4,1.15),(-length*.17,1.4,1.15),(length*.30,1.4,1.15),(length*.75,1.9,1.1)]:
            v.cyl('ROADWHEEL',(x,side*(y+width*.51),z),r,.2,IRON,axis='Y',cap=HUB,segments=12)
        # Raised fender with an exposed dark running gear beneath it.
        v.box('TRACKGUARD',(-length+.4,side*y-width*.55,height),(length-.3,side*y+width*.55,height+.35),STEEL)


def tire(v, number, at, r=2.7, width=1.85):
    bone=v.bone(f'TIRE{number:02}',at)
    bm=bmesh.new(); rings=[];n=12
    # Crown, shoulder and inset sidewall; a painted hub supplies the small-scale detail.
    for y,rr in [(-width*.5,r*.82),(-width*.33,r),(width*.33,r),(width*.5,r*.82)]:
        rings.append([bm.verts.new((math.cos(i*2*math.pi/n)*rr,y,math.sin(i*2*math.pi/n)*rr)) for i in range(n)])
    bm.faces.new(list(reversed(rings[0])));bm.faces.new(rings[-1])
    for a,b in zip(rings,rings[1:]):
        for i in range(n):bm.faces.new((a[i],a[(i+1)%n],b[(i+1)%n],b[i]))
    obj=v.mesh(f'TIRE{number:02}',bm,RUBBER,bone,cap_axis=1,cap_tile=HUB)
    # Fit the full radial image to each cap; shoulders retain chunky tread blocks.
    return obj


def lamps(v, x,z,width):
    for side in (-1,1):
        y=side*width
        v.box('LAMPCASE',(x-.2,y-.65,z-.5),(x+.15,y+.65,z+.5),IRON)
        v.patch('HEADLAMP',[(x+.17,y-.5,z-.4),(x+.17,y+.5,z-.4),(x+.17,y+.5,z+.4),(x+.17,y-.5,z+.4)],LAMP)


def wiesel():
    v=Vehicle('EUWIEST');tracks(v,length=8.3,y=4.35,width=2.15,height=3.25)
    v.body('HULL',[(-8.0,1.25,2.8,4.6,5.0,2.7,3.8,3.45),(-3.7,1.1,2.8,4.6,5.05,2.7,3.8,3.45),
        (2.2,1.2,2.8,4.45,4.9,2.7,3.8,3.4),(5.4,1.45,2.8,3.55,3.9,2.5,3.7,3.2),(8.1,2,2.8,2.95,3.1,2.3,3.5,3.1)])
    # Driver's raised right position, low engine deck left, recessed rear weapon platform.
    bm=bmesh.new();kit.prism_xz(bm,[(.1,4.8),(4.9,3.9),(4.0,5.7),(2.7,6.1),(.1,6.1)],.35,3.35)
    v.mesh('DRIVERHOOD',bm,STEEL)
    v.hatch('DRIVERHATCH',(1.4,1.85,6.14),1.1)
    v.box('VISIONBLOCK',(3.0,.75,5.72),(3.55,3.0,6.12),GLASS)
    v.patch('ENGINEGRILLE',[(.0,-3.3,5.04),(2.1,-3.3,4.98),(2.1,-.25,4.98),(.0,-.25,5.04)],VENT)
    v.patch('FRONTGRILLE',[(2.45,-3.3,4.86),(5.1,-3.3,4.03),(5.1,-.25,4.03),(2.45,-.25,4.86)],VENT)
    v.box('REARLOCKER',(-7.85,-3.4,4.85),(-4.4,-.5,5.65),LOCKER)
    v.box('CANVAS',(-7.6,1.35,5.0),(-5.0,3.4,6.0),TARP,bevel=.22)
    v.hatch('GUNNER',(-3.0,.7,5.12),1.45)
    # Broad plate panels on the flanks, bounded by the hull rather than generic camouflage.
    for s in (-1,1):
        v.patch('HULLACCESS',[(-4.1,s*3.82,3.2),(-.5,s*3.82,3.2),(-.5,s*3.82,4.42),(-4.1,s*3.82,4.42)],PLATE)
        v.house('HOUSECOLOR'+str(s),[(-7.6,s*3.85,3.7),(-4.5,s*3.85,3.7),(-4.5,s*3.85,4.35),(-7.6,s*3.85,4.35)])
    v.house('HOUSECOLORROOF',[(-7.3,-3,5.68),(-4.8,-3,5.68),(-4.8,-2.25,5.68),(-7.3,-2.25,5.68)])
    lamps(v,7.5,3.3,2.7)
    v.box('FRONTBUMPER',(7.8,-2.8,2.05),(8.5,2.8,2.5),IRON)
    v.patch('GLACISPANEL',[(5.48,-2.75,3.91),(7.9,-2.75,3.20),(7.9,2.75,3.20),(5.48,2.75,3.91)],PLATE)
    # Original open TOW cradle; tube and thermal sight deliberately readable at camera height.
    turret=v.bone('Turret',(-2.4,-.45,5.25))
    v.cyl('TOWRING',(0,0,.1),1.35,.35,IRON,bone=turret,cap=HATCH)
    for s in (-1,1):v.beam('CRADLE',(-.85,s*.85,.25),(.05,s*.85,2.15),.28,IRON,turret)
    v.cyl('PIVOT',(.15,0,1.75),.55,2.1,STEEL,axis='Y',bone=turret,cap=HUB)
    v.cyl('TOWTUBE',(.55,0,2.55),.83,6.5,TUBE,axis='X',bone=turret,cap=IRON)
    for x in (-2.4,3.5):v.cyl('TOWCOLLAR',(x,0,2.55),.94,.40,IRON,axis='X',bone=turret,cap=IRON)
    v.cyl('TOWBORE',(3.72,0,2.55),.73,.035,IRON,axis='X',bone=turret,cap=IRON)
    v.box('THERMALSIGHT',(-1.3,1.0,1.65),(1.6,2.0,2.85),PLATE,bone=turret,bevel=.12)
    v.patch('SIGHTLENS',[(1.62,1.13,1.85),(1.62,1.88,1.85),(1.62,1.88,2.64),(1.62,1.13,2.64)],GLASS,turret)
    v.bone('TurretMS',(3.85,0,2.55),turret);v.bone('TurretFX',(3.85,0,2.55),turret);v.bone('Barrel',parent=turret)
    v.beam('AERIAL',(-7.1,-2.8,5.65),(-7.7,-2.8,10.2),.055)
    return v


def carrier(ambulance=False):
    v=Vehicle('EUVALUK' if ambulance else 'EUPATRIA')
    # Six wheels, open wheel wells and a stepped forward driving cabin.
    for i,x in enumerate((8.1,-.7,-9.0)):
        for j,s in enumerate((-1,1)):tire(v,i*2+j+1,(x,s*5.65,2.7))
    v.body('LOWERHULL',[(-12.4,2.7,4.0,5.5,5.75,3.8,5.3,4.8),(-6,2.6,4.0,5.6,5.9,3.8,5.4,4.9),
        (6.5,2.7,4.0,5.5,5.8,3.8,5.4,4.9),(12.5,3.4,4.1,4.3,4.5,3.2,4.8,4.4)])
    # Patria has a truck-like windshield; Valuk a low glacis with protected driving position.
    if not ambulance:
        v.body('UPPERHULL',[(-12.25,5.6,5.9,8.15,8.9,4.6,5.25,4.55),(-4.7,5.6,5.9,8.3,9.05,4.6,5.25,4.55),
            (3.6,5.6,5.9,8.3,9.05,4.6,5.25,4.55),(7.9,5.5,5.9,8.4,9.2,4.6,5.2,4.45),
            (11.15,4.7,5.0,5.8,6.3,4.0,4.75,4.1)])
        for s in (-1,1):
            lo,hi=sorted((s*.35,s*3.9))
            v.patch('WINDSCREEN',[(8.0,lo,9.18),(8.0,hi,9.18),(10.4,hi,7.03),(10.4,lo,7.03)],GLASS)
            v.patch('CABGLASS',[(4.7,s*5.24,6.7),(7.7,s*5.24,6.7),(7.7,s*5.24,8.4),(4.7,s*5.24,8.4)],GLASS)
        roof=9.05
    else:
        v.body('UPPERHULL',[(-12.25,5.6,5.9,8.3,9.1,4.6,5.25,4.55),(-3.4,5.6,5.9,8.3,9.1,4.6,5.25,4.55),
            (4.3,5.6,5.9,7.4,8.15,4.6,5.2,4.5),(10.7,4.8,5.0,5.35,5.7,4,4.7,4.1)])
        v.body('MEDICALCOMPARTMENT',[(-11.65,8.85,9.1,10.0,10.55,4.25,4.6,4.05),(-3.7,8.85,9.1,10.0,10.55,4.25,4.6,4.05)])
        roof=8.45
        v.hatch('DRIVER',(3.2,2.1,8.18),1.15)
        v.box('DRIVERSCOPE',(4.4,.85,7.77),(4.95,3.4,8.22),GLASS)
        v.patch('MEDROOF',[(-10.7,-2.9,10.58),(-5.1,-2.9,10.58),(-5.1,2.9,10.58),(-10.7,2.9,10.58)],MEDICAL)
        for s in (-1,1):v.patch('MEDSIDE',[(-10.6,s*5.29,5.9),(-6.4,s*5.29,5.9),(-6.4,s*5.29,8.2),(-10.6,s*5.29,8.2)],MEDICAL)
        v.box('RESCUEBAR',(-2.8,-1.8,9.22),(-1.9,1.8,9.7),CAUTION)
    # Distinct armored wheel brows, undercarriage recesses and external tools.
    for s in (-1,1):
        for x in (8.1,-.7,-9):
            bm=bmesh.new();kit.prism_xz(bm,[(x-3.2,4.6),(x-2.2,5.85),(x+2.2,5.85),(x+3.2,4.6),
                (x+3.05,4.85),(x+2.1,6.2),(x-2.1,6.2),(x-3.05,4.85)],s*5.15,s*6.65)
            v.mesh('WHEELBROW',bm,STEEL)
        v.patch('ACCESSDOOR',[(-3.95,s*5.3,6.15),(.9,s*5.3,6.15),(.9,s*5.3,8.25),(-3.95,s*5.3,8.25)],DOOR)
        v.house('HOUSECOLOR'+str(s),[(1.45,s*5.33,6.35),(4.0,s*5.33,6.35),(4.0,s*5.33,7.35),(1.45,s*5.33,7.35)])
        v.beam('ROOFRAIL',(-10.8,s*4.7,9.2),(-4.8,s*4.7,9.2),.10)
        for x in (-10.8,-4.8):v.beam('RAILFOOT',(x,s*4.7,8.65),(x,s*4.7,9.2),.1)
    v.patch('REARRAMP',[(-12.29,-3.6,4.6),(-12.29,3.6,4.6),(-12.29,3.6,8.2),(-12.29,-3.6,8.2)],DOOR)
    v.box('REARSTEP',(-13.0,-3.5,3.0),(-12.3,3.5,3.35),IRON)
    v.box('BUMPER',(12.2,-4.6,3.2),(13.0,4.6,3.7),IRON)
    lamps(v,11.6,4.7,3.6)
    if not ambulance:
        for s in (-1,1):
            v.box('STOWLOCKER',(-11.6,s*5.20,6.4),(-6.4,s*5.62,7.9),LOCKER)
        v.hatch('PASSENGERHATCH',(-7.8,0,9.1),1.75)
        v.patch('SERVICEPLATE',[(-4.5,-3.95,9.085),(.75,-3.95,9.085),(.75,-1.0,9.085),(-4.5,-1.0,9.085)],PLATE)
        v.patch('BONNET',[(10.45,-3.3,6.97),(11.15,-3.3,6.34),(11.15,3.3,6.34),(10.45,3.3,6.97)],PLATE)
        v.box('ROOFSTOW',(-11.65,-3.95,8.95),(-8.4,-1.9,9.75),TARP,bevel=.18)
        v.patch('ROOFVENT',[(1.2,-3.9,9.08),(4.9,-3.9,9.08),(4.9,-1,9.08),(1.2,-1,9.08)],VENT)
        t=v.bone('Turret',(-1.1,.8,9.08))
        v.cyl('GUNRING',(0,0,.15),1.65,.4,IRON,bone=t,cap=HATCH)
        # Angular ballistic shield with daylight under the barrel.
        bm=bmesh.new();kit.prism_xz(bm,[(-1.25,.3),(1.5,.3),(1.1,2.1),(-.8,2.5)],-.5,.5)
        v.mesh('GUNMOUNT',bm,PLATE,t)
        for s in (-1,1):v.box('GUNSHIELD',(-.9,s*.8,.5),(.5,s*1.7,2.1),STEEL,t)
        v.box('RECEIVER',(-.4,-.32,2.25),(1.8,.32,2.85),IRON,t)
        v.cyl('MG',(3.4,0,2.55),.23,3.8,IRON,'X',t,cap=IRON,segments=8)
        v.cyl('MUZZLE',(5.2,0,2.55),.34,.55,IRON,'X',t,cap=IRON,segments=8)
        v.box('AMMOBOX',(-1.1,-1.8,1.25),(.5,-.75,2.25),TUBE,t)
        v.bone('Muzzle',(5.5,0,2.55),t)
    else:
        v.patch('GLACISPANEL',[(5.15,-3.85,7.86),(9.6,-3.85,6.15),(9.6,3.85,6.15),(5.15,3.85,7.86)],PLATE)
        v.patch('ROOFVENT',[(.4,-3.9,8.68),(3.5,-3.9,8.30),(3.5,-.8,8.30),(.4,-.8,8.68)],VENT)
        v.box('RESCUESTOW',(-3.0,-4.1,8.7),(-.3,-2.1,9.5),TARP,bevel=.18)
    v.beam('AERIAL',(-11.2,3.85,9.25),(-11.9,3.85,13.0),.06)
    return v


def robot(mv4=False):
    v=Vehicle('EUMV4' if mv4 else 'EUDRONE')
    tracks(v,length=6.9,y=4.15,width=2.4,height=3.5)
    if mv4:
        v.body('ENGINEBODY',[(-6.65,1.3,3.3,6.2,6.7,2.4,3.25,2.9),(-4.5,1.3,3.3,6.2,6.7,2.4,3.25,2.9),
            (.1,1.3,3.3,5.65,6.1,2.4,3.25,2.9),(3.25,1.5,3.2,4.3,4.7,2.2,3.0,2.6)])
        v.patch('ENGINEVENT',[(-4.4,-2.55,6.72),(-.4,-2.55,6.20),(-.4,2.55,6.20),(-4.4,2.55,6.72)],VENT)
        for s in (-1,1):
            v.patch('SIDEVENT',[(-5.6,s*3.28,4.5),(-2.1,s*3.28,4.5),(-2.1,s*3.28,5.9),(-5.6,s*3.28,5.9)],VENT)
            v.house('HOUSECOLOR'+str(s),[(-1.5,s*3.30,3.8),(1.4,s*3.30,3.8),(1.4,s*3.30,4.65),(-1.5,s*3.30,4.65)])
            v.beam('LIFTARM',(-.1,s*4.55,4.35),(10.0,s*4.55,2.5),.52,STEEL)
            v.cyl('LIFTPIVOT',(.1,s*4.55,4.3),.8,.9,IRON,'Y',cap=HUB)
            v.beam('HYDRAULIC',(-2,s*3.5,5.2),(4.6,s*4.0,4.0),.32,IRON)
            v.beam('PISTON',(4.6,s*4.0,4.0),(8.5,s*4.5,2.9),.17,STEEL)
        bm=bmesh.new();kit.prism_xz(bm,[(8.3,3.4),(8.8,5.2),(11.5,5.2),(12.4,4.2),(12.1,3.9),(11.15,4.6),(9.3,4.6),(8.8,3.4)],-6.2,6.2)
        v.mesh('FLAILSHIELD',bm,STEEL)
        v.patch('WARNING',[(8.85,-5.6,5.22),(11.4,-5.6,5.22),(11.4,5.6,5.22),(8.85,5.6,5.22)],CAUTION)
        f=v.bone('FLAIL',(10.5,0,2.25),rotation=(.70710678,0,0,.70710678));v.spins[f]=2
        v.cyl('FLAILDRUM',(0,0,0),1.25,11.8,IRON,bone=f,cap=HUB)
        bm=bmesh.new()
        for i in range(10):
            angle=i*.94
            for off in (0,math.pi):
                x,y=math.cos(angle+off),math.sin(angle+off)
                kit.beam(bm,(x,y,i-4.5),(x*2,y*2,i-4.5),.12,.12)
                box(bm,(x*2-.22,y*2-.22,i-4.72),(x*2+.22,y*2+.22,i-4.28))
        v.mesh('HAMMERS',bm,IRON,f)
        v.box('CAMERA',(.6,-.65,6.1),(1.8,.65,7.1),STEEL)
        v.patch('LENS',[(1.82,-.5,6.3),(1.82,.5,6.3),(1.82,.5,6.95),(1.82,-.5,6.95)],GLASS)
        lamps(v,3.2,4.4,2.35)
    else:
        # THeMIS-like twin tracked pontoons flank a low open cargo deck.
        v.box('CARGODECK',(-5.8,-3.0,2.25),(5.5,3.0,2.9),IRON)
        v.patch('LOADBED',[(-5.4,-2.7,2.94),(4.7,-2.7,2.94),(4.7,2.7,2.94),(-5.4,2.7,2.94)],PLATE)
        for s in (-1,1):
            bm=bmesh.new();kit.prism_xz(bm,[(-6.3,3.55),(6.2,3.55),(5.0,4.5),(-4.7,4.5)],s*3.2,s*5.55)
            v.mesh('PONTOON',bm,STEEL)
            lo,hi=sorted((s*3.35,s*5.3))
            v.patch('MOTORVENT',[(-4.8,lo,4.52),(-1.0,lo,4.52),(-1.0,hi,4.52),(-4.8,hi,4.52)],VENT)
            v.house('HOUSECOLOR'+str(s),[(.2,lo,4.52),(3.9,lo,4.52),(3.9,hi,4.52),(.2,hi,4.52)])
        v.box('BATTERY',(-5.3,-2.55,2.95),(-2.9,2.55,3.85),LOCKER)
        v.box('SENSORPLINTH',(-.8,-1.1,2.95),(1.7,1.1,4.0),STEEL)
        v.cyl('MAST',(.45,0,5.0),.34,2.1,IRON)
        t=v.bone('TURRET01',(.45,0,6.05))
        v.box('SENSORHEAD',(-1.2,-1.3,0),(1.2,1.3,1.25),STEEL,t,bevel=.16)
        v.patch('OPTICS',[(1.22,-1.07,.2),(1.22,1.07,.2),(1.22,1.07,1.04),(1.22,-1.07,1.04)],GLASS,t)
        u=v.bone('TURRETUP01',(-.7,0,1.25),t)
        # Explicit mesh name is required by the optional scout machine-gun upgrade.
        bm=bmesh.new();box(bm,(-.7,-.42,0),(1.3,.42,.7));cylinder(bm,(2.9,0,.36),.22,3.5,axis='X',segments=8)
        v.mesh('TURRETUP09',bm,IRON,u)
        v.bone('MUZZLE01',(4.7,0,1.61),t);v.bone('TURRETFX01',(4.7,0,1.61),t)
        lamps(v,5.5,3.7,4.0)
    v.beam('AERIAL',(-5.4,2.55,5.8 if mv4 else 3.6),(-5.9,2.55,8.8 if mv4 else 7.0),.05)
    return v


def build(name):
    prepare_textures()
    bpy.ops.wm.read_factory_settings(use_empty=True)
    from compact_polish import vilkas, wiesel_polished, valuk_polished
    jobs={'EUWIEST':wiesel_polished,'EUVALUK':valuk_polished,'EUBOXER':vilkas,
          'EUPATRIA':carrier,'EUDRONE':robot,'EUMV4':lambda:robot(True)}
    jobs[name]().finish()


if __name__=='__main__':
    selected=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else ['EUWIEST','EUPATRIA','EUVALUK','EUDRONE','EUMV4']
    for name in selected:build(name)

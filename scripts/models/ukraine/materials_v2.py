"""Original shared atlas art rebaked into Ukraine-specific olive/grey diffuse maps.

Source PNGs are copies of our authored Israel v2 art, never stock game textures.
Atlas UV is retained in .blend; game receives one diffuse bake per model/state.
"""
from pathlib import Path
import bpy
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[2]
TEX=ROOT/'resources/macos/GameData/Art/TexturesHD'
INFANTRY={'UARIFL','UASTUG','UACOMM'}
AIRCRAFT={'UAF16','UATB2','UAMI24'}

def family(a):return 'cloth-equipment' if a.name in INFANTRY else 'aircraft-panels' if a.name in AIRCRAFT else 'industrial-surfaces'

def project(a,obj,s,name):
    inf=a.name in INFANTRY;air=a.name in AIRCRAFT
    if inf:
        tile={'uniform':11,'canvas':4,'skin':10,'face':14,'helmet':0,'vest':1,'pouch':3,'webbing':12,
              'boot':6,'sole':7,'rubber':8,'steel':8,'glass':9,'darkpaint':0,'paint':0,'beret':13,'glove':5}.get(s,0)
    elif air:
        tile={'airpaint':0,'paint':0,'panel':1,'hatch':3,'vent':2,'rubber':6,'steel':8,'glass':9,
              'white':10,'darkpaint':11,'exhaust':7,'lamp':14,'radome':12}.get(s,0)
    else:
        tile={'paint':0,'darkpaint':1,'steel':8,'rubber':6,'glass':9,'concrete':12,'roof':8,
              'sand':0,'canvas':11,'lamp':14,'white':12,'panel':1,'vent':2,'locker':3,'wheelhub':5,'tracksteel':7}.get(s,0)
        if 'TREAD' in name:tile=7
        elif 'HATCH' in name:tile=4
        elif 'HUB' in name:tile=5
        elif 'VENT' in name or 'GRILLE' in name:tile=2
    obj['ua_tile']=tile;obj['ua_surface']=s
    uv=obj.data.uv_layers.new(name='AtlasUV')
    low=[min(v.co[i] for v in obj.data.vertices) for i in range(3)]
    high=[max(v.co[i] for v in obj.data.vertices) for i in range(3)]
    for p in obj.data.polygons:
        axis=max(range(3),key=lambda k:abs(p.normal[k]));axes={0:(1,2),1:(0,2),2:(0,1)}[axis]
        face_tile=12 if air and tile==0 and p.normal.z<-.4 else tile
        for li in p.loop_indices:
            co=obj.data.vertices[obj.data.loops[li].vertex_index].co
            u=(co[axes[0]]-low[axes[0]])/max(.001,high[axes[0]]-low[axes[0]])
            v=(co[axes[1]]-low[axes[1]])/max(.001,high[axes[1]]-low[axes[1]])
            inset=.14 if inf and tile in (0,4,11) else .06
            if s=='glass':inset=.22
            if not inf and not air and tile==0:
                # The broad central paint patch, without the tile's welded border.
                u=.06+.88*u;v=.05+.52*v
            else:u=inset+(1-2*inset)*u;v=inset+(1-2*inset)*v
            uv.data[li].uv=((face_tile%4+u)/4,1-(face_tile//4+1-v)/4)

def bake(a):
    from blender_kit import load_image
    a.world();objects=[o for _,_,o,_,k in a.parts if k!='house']
    inf=a.name in INFANTRY;air=a.name in AIRCRAFT
    source=load_image(str(HERE/'paint'/(family(a)+'.png')))
    bpy.ops.object.select_all(action='DESELECT')
    for o in objects:
        o.select_set(True);o.data.uv_layers.new(name='PaintUV');o.data.uv_layers.active_index=1
        o.data.uv_layers['PaintUV'].active_render=True
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.mode_set(mode='EDIT');bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=.85,island_margin=.004,area_weight=.15)
    bpy.ops.object.mode_set(mode='OBJECT')
    scene=bpy.context.scene;scene.render.engine='CYCLES';scene.cycles.device='CPU'
    scene.cycles.samples=8;scene.render.bake.margin=5
    targets=[];damage=[];night=[]
    for name,b,o,s,k in a.parts:
        if k=='house':
            uv=o.data.uv_layers.new(name='PaintUV');o.data.uv_layers.active_index=1
            o.data.uv_layers['PaintUV'].active_render=True
            for loop in uv.data:loop.uv=(.5,.5)
            continue
        mat=bpy.data.materials.new(name+'_V2');mat.use_nodes=True
        tree=mat.node_tree;tree.nodes.clear();n=tree.nodes;link=tree.links.new
        tex=n.new('ShaderNodeTexImage');tex.image=source
        uv=n.new('ShaderNodeUVMap');uv.uv_map='AtlasUV';link(uv.outputs['UV'],tex.inputs['Vector'])
        albedo=tex.outputs['Color'];geom=n.new('ShaderNodeNewGeometry')
        if s in ('blue','yellow','red','white') and not (air and s=='white'):
            rgb=n.new('ShaderNodeRGB');rgb.outputs[0].default_value={'blue':(.10,.31,.58,1),'yellow':(.62,.5,.12,1),'red':(.4,.045,.016,1),'white':(.65,.66,.55,1)}[s];albedo=rgb.outputs[0]
        tint=(1,1,1,1)
        if inf:
            tint={'uniform':(1.2,1.30,.92,1),'canvas':(.95,1.13,.80,1),'helmet':(1.1,1.24,.95,1),
                  'vest':(.95,1.13,.92,1),'pouch':(.83,.96,.69,1),'skin':(.90,.95,1,1)}.get(s,tint)
        elif air:
            tint={'airpaint':(.51,.72,1.34,1),'paint':(.51,.72,1.34,1),'panel':(.50,.70,1.25,1),
                  'hatch':(.50,.70,1.25,1),'darkpaint':(.68,.78,.69,1),'radome':(.57,.65,.67,1)}.get(s,tint)
            if a.name=='UAMI24':tint={'airpaint':(.57,.68,.39,1),'panel':(.57,.68,.39,1),'hatch':(.57,.68,.39,1),'darkpaint':(.63,.69,.49,1)}.get(s,tint)
        else:
            tint={'paint':(.58,.73,.41,1),'darkpaint':(.43,.60,.32,1),'steel':(.66,.71,.70,1),
                  'roof':(.91,1.00,1.0,1),'concrete':(.69,.75,.75,1),'sand':(.88,.86,.68,1),
                  'canvas':(.69,.85,.53,1),'panel':(.45,.64,.35,1),'locker':(.43,.59,.34,1),'wheelhub':(.43,.57,.35,1),'vent':(.68,.72,.67,1),'tracksteel':(.72,.76,.72,1),'rubber':(.70,.75,.70,1),'glass':(.6,.79,.88,1)}.get(s,tint)
        colour=n.new('ShaderNodeMixRGB');colour.blend_type='MULTIPLY';colour.inputs[0].default_value=1
        link(albedo,colour.inputs[1]);colour.inputs[2].default_value=tint;albedo=colour.outputs[0]
        if not inf and not air and s=='paint' and o.get('ua_tile')==0:
            worn=n.new('ShaderNodeMixRGB');worn.inputs[0].default_value=.62
            worn.inputs[1].default_value=(.21,.255,.14,1);link(albedo,worn.inputs[2]);albedo=worn.outputs[0]
        if a.building and s in ('concrete','roof','steel'):
            calm=n.new('ShaderNodeMixRGB');calm.inputs[0].default_value=.26 if s=='concrete' else .38 if s=='roof' else .63
            calm.inputs[1].default_value={'concrete':(.28,.29,.27,1),'roof':(.18,.205,.19,1),'steel':(.13,.15,.13,1)}[s]
            link(albedo,calm.inputs[2]);albedo=calm.outputs[0]
        if s in ('paint','uniform') or (s=='airpaint' and a.name=='UAMI24'):
            grid=n.new('ShaderNodeVectorMath');grid.operation='SCALE'
            grid.inputs[3].default_value=4.5 if inf else .14 if a.building else .50 if air else .8
            link(geom.outputs['Position'],grid.inputs[0])
            snap=n.new('ShaderNodeVectorMath');snap.operation='FLOOR';link(grid.outputs[0],snap.inputs[0])
            noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=.80;noise.inputs['Detail'].default_value=0;link(snap.outputs[0],noise.inputs['Vector'])
            ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.interpolation='CONSTANT'
            ramp.color_ramp.elements[0].position=.34;ramp.color_ramp.elements[0].color=(.68,.74,.58,1)
            ramp.color_ramp.elements[1].position=.64;ramp.color_ramp.elements[1].color=(1.20,1.15,.97,1)
            ramp.color_ramp.elements.new(.45).color=(1,1,1,1);link(noise.outputs['Fac'],ramp.inputs[0])
            camo=n.new('ShaderNodeMixRGB');camo.blend_type='MULTIPLY';camo.inputs[0].default_value=.80
            link(albedo,camo.inputs[1]);link(ramp.outputs[0],camo.inputs[2]);albedo=camo.outputs[0]
        if name=='RUNWAY':
            noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1.8;link(geom.outputs['Position'],noise.inputs[0])
            ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].color=(.055,.06,.06,1);ramp.color_ramp.elements[1].color=(.13,.14,.14,1);link(noise.outputs['Fac'],ramp.inputs[0]);albedo=ramp.outputs[0]
        ao=n.new('ShaderNodeAmbientOcclusion');ao.samples=8;ao.inputs['Distance'].default_value=1.1 if inf else 8 if a.building else 3.2
        shade=n.new('ShaderNodeMapRange');shade.inputs['To Min'].default_value=.72 if inf else .46;shade.inputs['To Max'].default_value=1.12
        if k=='decal':shade.inputs['To Min'].default_value=.96
        link(ao.outputs['AO'],shade.inputs[0])
        xyz=n.new('ShaderNodeSeparateXYZ');link(geom.outputs['Position'],xyz.inputs[0])
        height=n.new('ShaderNodeMapRange');height.inputs['From Min'].default_value=.2; height.inputs['From Max'].default_value=3 if inf else 8 if a.building else 4
        height.inputs['To Min'].default_value=.82; height.inputs['To Max'].default_value=1.03;link(xyz.outputs['Z'],height.inputs[0])
        mult=n.new('ShaderNodeMath');mult.operation='MULTIPLY';link(height.outputs[0],mult.inputs[0]);link(shade.outputs[0],mult.inputs[1])
        shadecol=n.new('ShaderNodeMixRGB');shadecol.blend_type='MULTIPLY';shadecol.inputs[0].default_value=1;link(albedo,shadecol.inputs[1]);link(mult.outputs[0],shadecol.inputs[2])
        soot=n.new('ShaderNodeTexNoise');soot.inputs['Scale'].default_value=1.9 if inf else .3;soot.inputs['Detail'].default_value=2;link(geom.outputs['Position'],soot.inputs[0])
        ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.3;ramp.color_ramp.elements[0].color=(.12,.10,.085,1);ramp.color_ramp.elements[1].position=.7;ramp.color_ramp.elements[1].color=(.72,.70,.60,1);link(soot.outputs['Fac'],ramp.inputs[0])
        scar=n.new('ShaderNodeMixRGB');scar.blend_type='MULTIPLY';scar.inputs[0].default_value=0;link(shadecol.outputs[0],scar.inputs[1]);link(ramp.outputs[0],scar.inputs[2]);damage.append(scar)
        glow=n.new('ShaderNodeMixRGB');glow.inputs[0].default_value=0;link(scar.outputs[0],glow.inputs[1]);glow.inputs[2].default_value=(.75,.58,.20,1)
        if s in ('glass','lamp'):night.append(glow)
        emit=n.new('ShaderNodeEmission');link(glow.outputs[0],emit.inputs[0]);out=n.new('ShaderNodeOutputMaterial');link(emit.outputs[0],out.inputs[0])
        target=n.new('ShaderNodeTexImage');n.active=target;targets.append(target)
        o.data.materials.clear();o.data.materials.append(mat)
        for p in o.data.polygons:p.material_index=0
    size=512 if a.name=='UAFPV' else 1024
    variants=['','_d']+(['_n','_dn'] if a.building else [])
    for suffix in variants:
        for node in damage:node.inputs[0].default_value=.85 if 'd' in suffix else 0
        for node in night:node.inputs[0].default_value=1 if 'n' in suffix else 0
        dest=bpy.data.images.new(a.name.lower()+suffix,size,size,alpha=False)
        for node in targets:node.image=dest
        bpy.ops.object.bake(type='EMIT',use_clear=True)
        dest.filepath_raw=str(TEX/(a.name.lower()+suffix+'.tga'));dest.file_format='TARGA';dest.save()
    a.notes.append('V2 diffuse paint: our original shared atlas art, Ukraine olive/grey palette, restrained digital camouflage, material wear and baked contact shadows. AtlasUV retained in editable source.')
    return variants

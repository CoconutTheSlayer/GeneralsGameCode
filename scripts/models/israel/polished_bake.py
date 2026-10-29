"""Bake original Israel diffuse materials with readable contact shadows.

This local bake deliberately keeps source UVs in the editable Blender file.
The game's fixed-function renderer needs the small fitting shadows in diffuse.
"""
from pathlib import Path
import bpy


def bake_paint(asset):
    root=Path(__file__).resolve().parents[3]
    textures=root/'resources/macos/GameData/Art/TexturesHD'
    from blender_kit import load_image
    dedicated=asset.category in ('infantry','aircraft')
    atlas='il_'+asset.category+'_atlas.tga' if dedicated else 'il_atlas.tga'
    objects=[o for _,_,o,t,_ in asset.parts if t==atlas]
    decals={o for _,_,o,_,kind in asset.parts if kind=='decal'}
    bpy.ops.object.select_all(action='DESELECT')
    for obj in objects:
        obj.select_set(True)
        obj.data.uv_layers.active.name='AtlasUV'
        obj.data.uv_layers.new(name='PaintUV')
        obj.data.uv_layers.active_index=1
        obj.data.uv_layers['PaintUV'].active_render=True
    bpy.context.view_layer.objects.active=objects[0]
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.uv.smart_project(angle_limit=.85,island_margin=.004,area_weight=.15)
    bpy.ops.object.mode_set(mode='OBJECT')
    scene=bpy.context.scene
    scene.render.engine='CYCLES'
    scene.cycles.device='CPU'
    scene.cycles.samples=16
    scene.render.bake.margin=6
    sources=[];targets=[];damage_controls=[]
    is_building=asset.category=='building'
    is_infantry=asset.category=='infantry'
    for obj in objects:
        mat=bpy.data.materials.new(obj.name+'_PolishedBake');mat.use_nodes=True
        tree=mat.node_tree;tree.nodes.clear();nodes=tree.nodes;link=tree.links.new
        uv=nodes.new('ShaderNodeUVMap');uv.uv_map='AtlasUV'
        source=nodes.new('ShaderNodeTexImage');source.interpolation='Linear'
        link(uv.outputs['UV'],source.inputs['Vector']);sources.append(source)
        ao=nodes.new('ShaderNodeAmbientOcclusion')
        ao.inputs['Distance'].default_value=8.0 if is_building else 1.3 if is_infantry else 3.5
        remap=nodes.new('ShaderNodeMapRange')
        remap.inputs['To Min'].default_value=.70 if is_infantry else .50 if dedicated else .32
        remap.inputs['To Max'].default_value=1.13
        if obj in decals:remap.inputs['To Min'].default_value=.92
        link(ao.outputs['AO'],remap.inputs['Value'])
        geom=nodes.new('ShaderNodeNewGeometry')
        albedo=source.outputs['Color']
        material=int(obj.get('israel_material_tile',-1))
        if getattr(asset,'aircraft_camo',False) and material==0:
            camo=nodes.new('ShaderNodeTexNoise');camo.inputs['Scale'].default_value=.18
            camo.inputs['Detail'].default_value=1.2;camo.inputs['Roughness'].default_value=.55
            link(geom.outputs['Position'],camo.inputs['Vector'])
            palette=nodes.new('ShaderNodeValToRGB');palette.color_ramp.interpolation='CONSTANT'
            palette.color_ramp.elements[0].position=.36;palette.color_ramp.elements[0].color=(.59,.72,.43,1)
            palette.color_ramp.elements[1].position=.56;palette.color_ramp.elements[1].color=(1.0,.97,.88,1)
            brown=palette.color_ramp.elements.new(.47);brown.color=(.81,.62,.43,1)
            link(camo.outputs['Fac'],palette.inputs['Fac'])
            top=nodes.new('ShaderNodeSeparateXYZ');link(geom.outputs['Normal'],top.inputs[0])
            above=nodes.new('ShaderNodeMath');above.operation='GREATER_THAN';above.inputs[1].default_value=-.35
            link(top.outputs['Z'],above.inputs[0])
            finish=nodes.new('ShaderNodeMixRGB');finish.blend_type='MULTIPLY'
            link(above.outputs[0],finish.inputs[0]);link(albedo,finish.inputs[1]);link(palette.outputs['Color'],finish.inputs[2])
            albedo=finish.outputs[0]
        if dedicated:
            soot=nodes.new('ShaderNodeTexNoise');soot.inputs['Scale'].default_value=2 if is_infantry else .4
            soot.inputs['Detail'].default_value=2
            link(geom.outputs['Position'],soot.inputs['Vector'])
            ramp=nodes.new('ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].position=.33;ramp.color_ramp.elements[0].color=(.12,.10,.085,1)
            ramp.color_ramp.elements[1].position=.67;ramp.color_ramp.elements[1].color=(.8,.75,.63,1)
            link(soot.outputs['Fac'],ramp.inputs['Fac'])
            damage=nodes.new('ShaderNodeMixRGB');damage.blend_type='MULTIPLY'
            link(albedo,damage.inputs[1]);link(ramp.outputs['Color'],damage.inputs[2])
            damage_controls.append(damage.inputs[0]);albedo=damage.outputs[0]
        if obj.get('israel_surface')=='asphalt':
            # The runway is a broad ground surface, not a tiny steel fitting.
            # Bake fine world-space asphalt grain so long quads cannot stretch
            # the atlas's scratches into diagonal streaks.
            grain=nodes.new('ShaderNodeTexNoise')
            grain.inputs['Scale'].default_value=1.8
            grain.inputs['Detail'].default_value=2
            link(geom.outputs['Position'],grain.inputs['Vector'])
            ramp=nodes.new('ShaderNodeValToRGB')
            ramp.color_ramp.elements[0].color=(.035,.038,.035,1)
            ramp.color_ramp.elements[1].color=(.070,.073,.067,1)
            link(grain.outputs['Fac'],ramp.inputs['Fac'])
            wear=nodes.new('ShaderNodeMixRGB')
            wear.inputs[0].default_value=.08
            link(ramp.outputs['Color'],wear.inputs[1])
            link(source.outputs['Color'],wear.inputs[2])
            albedo=wear.outputs[0]
        xyz=nodes.new('ShaderNodeSeparateXYZ');link(geom.outputs['Position'],xyz.inputs[0])
        height=nodes.new('ShaderNodeMapRange')
        height.inputs['From Min'].default_value=.5
        height.inputs['From Max'].default_value=10 if is_building else 4 if is_infantry else 6
        height.inputs['To Min'].default_value=.74
        height.inputs['To Max'].default_value=1.05
        link(xyz.outputs['Z'],height.inputs['Value'])
        shade=nodes.new('ShaderNodeMath');shade.operation='MULTIPLY'
        link(remap.outputs[0],shade.inputs[0]);link(height.outputs[0],shade.inputs[1])
        coloured=nodes.new('ShaderNodeMixRGB');coloured.blend_type='MULTIPLY';coloured.inputs[0].default_value=1
        link(albedo,coloured.inputs[1]);link(shade.outputs[0],coloured.inputs[2])
        # Canvas and large armour are separate readable materials, not the same
        # yellow base coat. Keep glass, lamp, metal and mechanical atlas panels.
        material=int(obj.get('israel_material_tile',-1))
        tint=nodes.new('ShaderNodeMixRGB');tint.blend_type='MULTIPLY';tint.inputs[0].default_value=1
        link(coloured.outputs[0],tint.inputs[1])
        tint.inputs[2].default_value=(1,1,1,1) if dedicated else {0:(.87,.91,.95,1),11:(.77,.85,.72,1),12:(.94,.96,.94,1)}.get(material,(1,1,1,1))
        emit=nodes.new('ShaderNodeEmission');link(tint.outputs[0],emit.inputs['Color'])
        output=nodes.new('ShaderNodeOutputMaterial');link(emit.outputs[0],output.inputs['Surface'])
        target=nodes.new('ShaderNodeTexImage');nodes.active=target;targets.append(target)
        obj.data.materials.clear();obj.data.materials.append(mat)
        for poly in obj.data.polygons:poly.material_index=0
    resolution=2048 if asset.name in ('ILMERK','ILNAMER','ILPEREH','ILCMD','ILFACT') else 1024
    for suffix in ('','_d'):
        source=load_image(str(textures/(atlas if dedicated else atlas.replace('.tga',suffix+'.tga'))))
        for control in damage_controls:control.default_value=.85 if suffix else 0
        for node in sources:node.image=source
        name=asset.name.lower()+'_paint'+suffix+'.tga'
        dest=bpy.data.images.new(name,resolution,resolution,alpha=False)
        for node in targets:node.image=dest
        bpy.ops.object.bake(type='EMIT',use_clear=True)
        dest.filepath_raw=str(textures/name);dest.file_format='TARGA';dest.save()
    asset.parts=[(n,b,o,asset.name.lower()+'_paint.tga' if t==atlas else t,k) for n,b,o,t,k in asset.parts]
    for obj in objects:
        obj.data.uv_layers.active_index=1
        obj.data.uv_layers['PaintUV'].active_render=True

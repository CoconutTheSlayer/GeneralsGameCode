"""Isolated Russia AO bake, adapted from the existing original mesh painter."""
import bpy
from pathlib import Path
from blender_kit import load_image
TEX=Path(__file__).resolve().parents[3]/"resources/macos/GameData/Art/TexturesHD"
ATLAS="ruatlas.tga"

def bake_paint(self):
    """Bake the authored paint and assembled occlusion into one original UV map.

    The runtime has no ambient-occlusion shader. Broad undercuts and fitting
    shadows need to be in the diffuse texture, just as in period RTS art.
    """
    atlas='rubuild_atlas.tga' if self.building else ATLAS
    objects=[o for _,_,o,t,_ in self.parts if t==atlas]
    if not self.building:
        # The generated image has slightly unequal material rows. Remap the
        # logical 4x4 tile contract to the measured source rectangles so glass,
        # metal and cloth never sample the adjacent skin row.
        xs=(0,314/1254,627/1254,940/1254,1)
        ys=(0,299/1254,602/1254,888/1254,1)
        for obj in objects:
            for loop in obj.data.uv_layers.active.data:
                u,v=loop.uv;col=min(3,max(0,int(u*4)));row=min(3,max(0,int((1-v)*4)))
                lu=u*4-col;lv=(1-v)*4-row
                loop.uv=(xs[col]+(xs[col+1]-xs[col])*(.025+.95*lu),1-(ys[row]+(ys[row+1]-ys[row])*(.025+.95*lv)))
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
    infantry=self.name in ('RURIFLE','RUKORNET','RUCMDO')
    aircraft=self.name in ('RUSU35','RUSU25','RUMI28')
    scene.cycles.device='CPU';scene.cycles.samples=16
    scene.render.bake.margin=4
    source_nodes=[];targets=[];damage_controls=[]
    for o in objects:
        mat=bpy.data.materials.new(o.name+'_Bake');mat.use_nodes=True
        tree=mat.node_tree;tree.nodes.clear();n=tree.nodes;link=tree.links.new
        uv=n.new('ShaderNodeUVMap');uv.uv_map='AtlasUV'
        src=n.new('ShaderNodeTexImage');link(uv.outputs['UV'],src.inputs['Vector']);source_nodes.append(src)
        ao=n.new('ShaderNodeAmbientOcclusion');ao.inputs['Distance'].default_value=5.5 if self.building else 1.0 if infantry else 2.2 if aircraft else 3.6
        # Strong contact shading, with a readable minimum for tiny fittings.
        ao_remap=n.new('ShaderNodeMapRange');ao_remap.inputs['To Min'].default_value=.67 if infantry else .50 if aircraft else .38
        ao_remap.inputs['To Max'].default_value=1.12 if infantry or aircraft else 1.20;link(ao.outputs['AO'],ao_remap.inputs['Value'])
        # Two-sided surface markings sit just above the hull. Their backing
        # face must not bake a dark occlusion stain over white medical paint.
        if o in decal_objects:ao_remap.inputs['To Min'].default_value=.95
        geom=n.new('ShaderNodeNewGeometry');xyz=n.new('ShaderNodeSeparateXYZ');link(geom.outputs['Position'],xyz.inputs[0])
        height=n.new('ShaderNodeMapRange');height.inputs['From Min'].default_value=.7;height.inputs['From Max'].default_value=10.0 if self.building else 5.5
        height.inputs['To Min'].default_value=.86 if infantry else .8 if aircraft else .65;height.inputs['To Max'].default_value=1.10;link(xyz.outputs['Z'],height.inputs['Value'])
        mul=n.new('ShaderNodeMath');mul.operation='MULTIPLY';link(ao_remap.outputs[0],mul.inputs[0]);link(height.outputs[0],mul.inputs[1])
        col=n.new('ShaderNodeMixRGB');col.blend_type='MULTIPLY';col.inputs[0].default_value=1
        link(src.outputs['Color'],col.inputs[1]);link(mul.outputs[0],col.inputs[2])
        colour=col.outputs[0]
        if self.name=='RUSU35' and int(o.get('russia_material_tile',-1))==0:
            # Cooler air-superiority livery, preserving the painted camouflage.
            desat=n.new('ShaderNodeHueSaturation');desat.inputs['Saturation'].default_value=.25;desat.inputs['Value'].default_value=1.5;link(colour,desat.inputs['Color'])
            tint=n.new('ShaderNodeMixRGB');tint.blend_type='MIX';tint.inputs[0].default_value=.30;tint.inputs[2].default_value=(.24,.34,.39,1);link(desat.outputs[0],tint.inputs[1]);colour=tint.outputs[0]
        if not self.building:
            noise=n.new('ShaderNodeTexNoise');noise.inputs['Scale'].default_value=1.7 if infantry else .45
            noise.inputs['Detail'].default_value=2.5;link(geom.outputs['Position'],noise.inputs['Vector'])
            ramp=n.new('ShaderNodeValToRGB');ramp.color_ramp.elements[0].position=.38;ramp.color_ramp.elements[0].color=(.11,.12,.10,1)
            ramp.color_ramp.elements[1].position=.62;ramp.color_ramp.elements[1].color=(.72,.68,.56,1)
            link(noise.outputs['Fac'],ramp.inputs[0])
            damaged=n.new('ShaderNodeMixRGB');damaged.blend_type='MULTIPLY';link(colour,damaged.inputs[1]);link(ramp.outputs[0],damaged.inputs[2]);damage_controls.append(damaged.inputs[0]);colour=damaged.outputs[0]
        emit=n.new('ShaderNodeEmission');link(colour,emit.inputs[0])
        output=n.new('ShaderNodeOutputMaterial');link(emit.outputs[0],output.inputs['Surface'])
        target=n.new('ShaderNodeTexImage');n.active=target;targets.append(target)
        o.data.materials.clear();o.data.materials.append(mat)
        for p in o.data.polygons:p.material_index=0
    for suffix in ('','_d'):
        for control in damage_controls:control.default_value=.82 if suffix else 0
        source=load_image(str(TEX/atlas.replace('.tga',suffix+'.tga')))
        for node in source_nodes:node.image=source
        name=self.name.lower()+'_paint'+suffix+'.tga'
        size=1024 if self.building or infantry else 2048 if self.name in ('RUT90','RUMSTA','RUSU35','RUSU25','RUMI28') else 1024
        dest=bpy.data.images.new(name,size,size,alpha=False)
        for node in targets:node.image=dest
        bpy.ops.object.bake(type='EMIT',use_clear=True)
        dest.filepath_raw=str(TEX/name);dest.file_format='TARGA';dest.save()
    self.parts=[(n,b,o,self.name.lower()+'_paint.tga' if t==atlas else t,k) for n,b,o,t,k in self.parts]
    # Runtime exports the active UV layer. Retain the source UVs in the blend
    # project so the asset can be repainted and rebaked without remodelling.
    for o in objects:
        o.data.uv_layers.active_index=1
        o.data.uv_layers['PaintUV'].active_render=True

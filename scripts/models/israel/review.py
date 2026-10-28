"""Refresh matte-lighting previews and inspect the opposite side of key assets."""
from pathlib import Path
import bpy,json,sys
from mathutils import Vector
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parents[3];BUILD=ROOT/'build/faction-assets/israel'
sys.path.insert(0,str(Path(__file__).parent));import build as builder
manifest=json.loads((Path(__file__).parent/'manifest.json').read_text())
selection=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [a['model'] for a in manifest['assets']]
for name in selection:
    bpy.ops.wm.open_mainfile(filepath=str(BUILD/(name+'.blend')))
    for mat in bpy.data.materials:
        if mat.use_nodes:
            node=mat.node_tree.nodes.get('Principled BSDF')
            if node:node.inputs['Roughness'].default_value=1
    sc=bpy.context.scene
    for obj in list(bpy.data.objects):
        if obj.type in ('CAMERA','LIGHT'):bpy.data.objects.remove(obj,do_unlink=True)
    builder.render(SimpleNamespace(name=name,parts=[(o.name,'CHASSIS',o,'','solid') for o in bpy.data.objects if o.type=='MESH']))
    bpy.ops.wm.save_as_mainfile(filepath=str(BUILD/(name+'.blend')))
    if name in ('ILSAND','ILMERK','ILF16','ILAPACH','ILRIFLE','ILAIR'):
        points=[obj.matrix_world@Vector(p) for obj in bpy.data.objects if obj.type=='MESH' for p in obj.bound_box]
        lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)]);mid=(lo+hi)/2
        sc.camera.location=mid+Vector((-1,-1.25,.9)).normalized()*max(hi-lo)*3
        sc.camera.rotation_euler=(mid-sc.camera.location).to_track_quat('-Z','Y').to_euler()
        sc.render.filepath=str(BUILD/(name+'_rear.png'));bpy.ops.render.render(write_still=True)
    print('ISRAEL_REVIEW',name,flush=True)

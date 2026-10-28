"""Dedicated square studio portraits from editable original Blender models."""
from pathlib import Path
import json,sys
import bpy
from mathutils import Vector

ROOT=Path(__file__).resolve().parents[3]
BUILD=ROOT/'build/faction-assets/israel'
OUT=BUILD/'icons'

def render(entry):
    bpy.ops.wm.open_mainfile(filepath=entry['blend'])
    sc=bpy.context.scene
    for o in list(bpy.data.objects):
        if o.type in ('CAMERA','LIGHT'):bpy.data.objects.remove(o,do_unlink=True)
    objects=[o for o in sc.objects if o.type=='MESH' and not o.hide_render]
    # Project real vertices: a plane's empty bounding-box corners otherwise
    # make its long narrow silhouette unnecessarily small in the menu.
    points=[o.matrix_world@vert.co for o in objects for vert in o.data.vertices]
    lo=Vector([min(p[i] for p in points) for i in range(3)])
    hi=Vector([max(p[i] for p in points) for i in range(3)])
    mid=(lo+hi)/2
    cam=bpy.data.objects.new('IconCamera',bpy.data.cameras.new('IconCamera'))
    sc.collection.objects.link(cam);sc.camera=cam;cam.data.type='ORTHO'
    direction=Vector((1.2,1.45,1.15 if entry['category']=='building' else .9))
    if entry['category']=='aircraft':direction=Vector((.8,1.6,1.4))
    cam.location=mid+direction.normalized()*max(hi-lo)*3
    cam.rotation_euler=(mid-cam.location).to_track_quat('-Z','Y').to_euler()
    local=[cam.rotation_euler.to_quaternion().inverted()@(p-mid) for p in points]
    cam.data.ortho_scale=max(max(p.x for p in local)-min(p.x for p in local),max(p.y for p in local)-min(p.y for p in local))*1.10
    world=bpy.data.worlds.new('PortraitWorld');world.use_nodes=True
    world.node_tree.nodes['Background'].inputs[0].default_value=(.32,.39,.48,1)
    world.node_tree.nodes['Background'].inputs[1].default_value=.7;sc.world=world
    for name,direction,power,color in [('Key',(1,1,1.8),2.8,(1,.87,.69)),('Fill',(-1,1,.8),1.2,(.66,.82,1)),('Rim',(-1,-1,1),2.2,(.95,.86,.72))]:
        lamp=bpy.data.objects.new(name,bpy.data.lights.new(name,'SUN'))
        lamp.data.energy=power;lamp.data.color=color;lamp.rotation_euler=Vector(direction).to_track_quat('Z','Y').to_euler()
        sc.collection.objects.link(lamp)
    sc.render.engine='BLENDER_EEVEE';sc.render.film_transparent=True
    sc.render.resolution_x=512;sc.render.resolution_y=512;sc.render.resolution_percentage=100
    sc.render.image_settings.file_format='PNG';sc.render.image_settings.color_mode='RGBA'
    sc.view_settings.view_transform='Standard';sc.view_settings.look='None';sc.view_settings.exposure=-.30
    sc.render.filepath=str(OUT/(entry['model']+'.png'));bpy.ops.render.render(write_still=True)
    print('ISRAEL_ICON',entry['model'],flush=True)

if __name__=='__main__':
    OUT.mkdir(parents=True,exist_ok=True)
    entries=json.loads((ROOT/'scripts/models/israel/manifest.json').read_text())['assets']
    ids=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else []
    for entry in entries:
        if entry['category']!='infantry' and (not ids or entry['model'] in ids):render(entry)

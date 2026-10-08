"""The European Boxer, an eight-wheeled armoured infantry vehicle, modelled in Blender from simple shapes and
written as a W3D model for the game. Everything in it is made here: the shapes, the camouflage and the
ambient occlusion baked into it, so the model and its textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/boxer.py

Writes resources/macos/GameData/Art/W3D/EUBOXER.w3d, Art/TexturesHD/euboxer.tga and euboxer_tire.tga,
and build/models/EUBOXER.blend (to open and change in Blender) with previews next to it.

The game's axes: +X forward, +Z up, in world units (a Boxer is about 30 long). Bones:
    CHASSIS                  hull
    TIRE01..TIRE08           wheels, front to back, left (+Y) then right; the truck drawer turns them
    TURRET                   the remote weapon station, turning about Z
    MUZZLE01, MUZZLEFX01     where the gun fires, and its flash
    HOUSECOLOR01/02          side stripes in the player's colour
"""
import json
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
import boxer_layout  # noqa: E402
from blender_kit import box, cylinder, load_image, mesh_data, new_object, prism, smooth_by_angle, textured  # noqa: E402
import w3d  # noqa: E402

NAME = "EUBOXER"
HULL_TEXTURE, TIRE_TEXTURE = "euboxer.tga", "euboxer_tire.tga"
DAMAGED_TEXTURE = "euboxer_d.tga"


# Shapes, in game units.
WHEEL_X = (11.2, 6.4, -4.4, -9.2)
WHEEL_Y, WHEEL_Z, WHEEL_RADIUS, WHEEL_WIDTH = 4.45, 2.5, 2.5, 1.5
HULL_HALF_WIDTH, HULL_BOTTOM = 5.5, 5.1
# Side view of the upper hull (x, z), front to back over the top: bow, glacis, driver's roof, the raised
# mission module.
HULL_PROFILE = [(-15.0, HULL_BOTTOM), (14.0, HULL_BOTTOM), (15.6, 6.1), (9.0, 7.7), (0.5, 8.0), (-0.8, 9.0), (-15.0, 9.0)]
LOWER_PROFILE = [(-14.5, 2.2), (12.5, 2.2), (14.7, 5.3), (-14.5, 5.3)]
LOWER_HALF_WIDTH = 3.4
TURRET_AT = (-3.5, 0.0, 9.0)
CHINE_Z = 6.3


# --- making shapes ---------------------------------------------------------------------------------

def hull():
    bm = bmesh.new()
    prism(bm, HULL_PROFILE, HULL_HALF_WIDTH, taper_from=7.0, taper=0.9)
    # The chine: the sides bend out a little above the wheels, as on the real vehicle.
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, CHINE_Z), plane_no=(0, 0, 1))
    for v in bm.verts:
        if abs(v.co.z - CHINE_Z) < 1e-4 and abs(v.co.y) > 1.0:
            v.co.y *= 1.06
    # Chamfered edges catch the light.
    sharp = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(25)]
    bmesh.ops.bevel(bm, geom=sharp, offset=0.22, segments=1, affect="EDGES", profile=0.5)
    prism(bm, LOWER_PROFILE, LOWER_HALF_WIDTH)
    details(bm)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    return new_object("CHASSIS", bm)


def rail(bm, x0, x1, y, z, posts=4):
    """A handrail along x with its posts."""
    cylinder(bm, ((x0 + x1) / 2, y, z + 0.35), 0.06, x1 - x0, axis="X", segments=6)
    for k in range(posts):
        cylinder(bm, (x0 + (x1 - x0) * k / (posts - 1), y, z + 0.17), 0.06, 0.35, segments=6)


def details(bm):
    """Everything bolted onto the hull."""
    # Roof: hatches, the driver's hatch with vision blocks, an air intake, handrails, two antennas.
    for x, y in ((-6.5, 2.4), (-6.5, -2.4), (-11.5, 0.0)):
        cylinder(bm, (x, y, 9.08), 1.1, 0.16, segments=16)
        box(bm, (x - 0.25, y - 1.25, 9.0), (x + 0.25, y - 0.95, 9.3))   # hinge
    cylinder(bm, (3.5, 2.6, 7.95), 0.9, 0.2, segments=16)
    box(bm, (4.5, 1.6, 7.8), (5.0, 3.6, 8.25))                          # vision blocks
    box(bm, (-2.5, -4.2, 9.0), (-0.9, -2.6, 9.45))                      # air intake
    for side in (1, -1):
        rail(bm, -14.2, -2.2, side * 4.55, 9.0)
    cylinder(bm, (-13.8, 4.2, 11.0), 0.07, 4.0, segments=6)
    cylinder(bm, (-13.8, -4.2, 10.4), 0.07, 2.8, segments=6)
    # Engine deck at the front left: raised, with the grille painted on.
    box(bm, (9.6, 0.8, 7.55), (12.8, 4.3, 7.85))
    # Front: headlight housings with guards, tow shackles, mirrors.
    for side in (1, -1):
        box(bm, (15.0, side * 3.4 - 0.5, 5.7), (15.75, side * 3.4 + 0.5, 6.2))
        box(bm, (15.75, side * 3.4 - 0.55, 5.65), (15.85, side * 3.4 + 0.55, 6.25))
        box(bm, (14.6, side * 2.0 - 0.25, 4.6), (15.2, side * 2.0 + 0.25, 5.0))
        box(bm, (13.6, side * 5.5 - 0.15, 6.6), (14.2, side * 5.5 + side * 0.6, 7.6))
    # Sides: stowage boxes on the mission module, bins between the wheel groups, an exhaust at the front left.
    for side in (1, -1):
        box(bm, (-13.5, side * 5.0, 6.0), (-8.0, side * 5.85, 8.3))
        box(bm, (-1.6, side * 3.4, 3.0), (3.6, side * 4.9, 5.1))
    cylinder(bm, (8.5, 5.75, 6.1), 0.28, 1.6, axis="X", segments=10)
    # Back: the ramp, its hinges, a step and tail lights.
    box(bm, (-15.15, -2.6, 5.4), (-14.9, 2.6, 8.3))
    for y in (-1.8, 1.8):
        cylinder(bm, (-15.2, y, 5.45), 0.18, 0.9, axis="Y", segments=8)
    box(bm, (-15.6, -1.5, 4.6), (-14.9, 1.5, 4.8))
    for y in (4.3, -4.3):
        box(bm, (-15.15, y - 0.4, 7.3), (-14.95, y + 0.4, 7.9))


def side_y(z):
    """How far out the hull side is at a height above the chine: it leans in towards the roof."""
    chine = (HULL_HALF_WIDTH + (HULL_HALF_WIDTH * 0.9 - HULL_HALF_WIDTH) * (CHINE_Z - HULL_BOTTOM) / (9.0 - HULL_BOTTOM)) * 1.06
    roof = HULL_HALF_WIDTH * 0.9
    return chine + (roof - chine) * (z - CHINE_Z) / (9.0 - CHINE_Z)


def house_colour(side):
    """The player's colour: a panel on the outer face of each rear stowage box."""
    bm = bmesh.new()
    y = side * 5.88
    verts = [bm.verts.new(v) for v in ((-13.1, y, 6.5), (-8.4, y, 6.5), (-8.4, y, 7.9), (-13.1, y, 7.9))]
    bm.faces.new(verts if side < 0 else list(reversed(verts)))
    return new_object(f"HOUSECOLOR0{1 if side > 0 else 2}", bm)


# The tyre's cross-section (distance from the axle, across the tyre towards the outside), revolved: tread with
# rounded shoulders, sidewalls, a dished rim and the hub cap.
TYRE_PROFILE = [(0.0, -0.55), (2.15, -0.75), (2.5, -0.4), (2.5, 0.4), (2.15, 0.75), (1.5, 0.72), (1.35, 0.5),
                (0.5, 0.6), (0.0, 0.6)]


def wheel(name, location):
    from mathutils import Matrix
    bm = bmesh.new()
    outward = 1 if location[1] > 0 else -1
    verts = [bm.verts.new((r, y * outward, 0)) for r, y in TYRE_PROFILE]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 1, 0), angle=2 * math.pi, steps=14,
                   use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    del Matrix
    return new_object(name, bm, location)


def turret():
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.15), 1.6, 0.3, segments=20)          # base ring
    cylinder(bm, (0, 0, 0.45), 1.3, 0.3, segments=20)          # turntable
    box(bm, (-1.1, -0.75, 0.6), (1.1, 0.75, 1.75))             # cradle
    box(bm, (-0.9, 0.75, 0.75), (0.5, 1.55, 1.6))              # ammunition box
    box(bm, (-0.3, 0.55, 1.35), (0.35, 0.8, 1.5))              # ammunition feed
    box(bm, (0.1, -1.55, 0.95), (1.25, -0.8, 1.85))            # sensor head
    cylinder(bm, (1.3, -1.18, 1.45), 0.22, 0.12, axis="X", segments=12)  # its lens
    box(bm, (0.6, -0.28, 1.05), (2.1, 0.28, 1.5))              # gun receiver
    cylinder(bm, (3.6, 0, 1.25), 0.15, 3.1, axis="X", segments=10)
    cylinder(bm, (5.1, 0, 1.25), 0.22, 0.35, axis="X", segments=10)    # muzzle brake
    # Smoke grenade launchers, four a side.
    for side in (1, -1):
        for k in range(4):
            cylinder(bm, (-0.8 + k * 0.32, side * 1.25, 1.95), 0.12, 0.45, axis="Y", segments=8)
    return new_object("TURRET", bm, TURRET_AT)


MUZZLE = (5.3, 0.0, 1.25)  # in the turret's space


def muzzle_flash():
    bm = bmesh.new()
    x0, x1, r = 0.0, 2.2, 0.7
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * r, math.sin(a) * r
        verts = [bm.verts.new(v) for v in ((x0, -c, -s), (x1, -c, -s), (x1, c, s), (x0, c, s))]
        bm.faces.new(verts)
    obj = new_object("MUZZLEFX01", bm, [TURRET_AT[i] + MUZZLE[i] for i in range(3)])
    return obj


# --- textures --------------------------------------------------------------------------------------

def panel_unwrap(obj, part):
    """UVs like the game's vehicles: every face projected straight onto its panel (boxer_layout.py)."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = boxer_layout.group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = boxer_layout.uv(part, grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def export_layout(parts, path):
    """The faces as they lie on the texture, and which of their edges are seams, for boxer_paint.py."""
    faces = []
    for obj, part in parts:
        me = obj.data
        edge_faces = {}
        for poly in me.polygons:
            for key in poly.edge_keys:
                edge_faces.setdefault(key, []).append(poly)
        for poly in me.polygons:
            grp = boxer_layout.group(tuple(poly.normal))
            vs = list(poly.vertices)
            sharp = []
            for i in range(len(vs)):
                key = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
                around = edge_faces.get(key, [])
                sharp.append(len(around) != 2 or around[0].normal.angle(around[1].normal, 0) > math.radians(25))
            faces.append(dict(part=part, group=grp, px=[boxer_layout.pixel(part, grp, tuple(me.vertices[v].co)) for v in vs], sharp=sharp))
    with open(path, "w") as f:
        json.dump(dict(faces=faces), f)


def bake_occlusion(objects, path, size=512):
    """Bakes ambient occlusion of the hull and turret on their panels, for boxer_paint.py to shade with."""
    image = bpy.data.images.new("occlusion", size, size)
    for obj in objects:
        mat = bpy.data.materials.new(obj.name + "_bake")
        mat.use_nodes = True
        node = mat.node_tree.nodes.new("ShaderNodeTexImage")
        node.image = image
        mat.node_tree.nodes.active = node
        obj.data.materials.clear()
        obj.data.materials.append(mat)
    scene = bpy.context.scene
    engine = scene.render.engine
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.render.bake.margin = 6
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.bake(type="AO")
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()
    scene.render.engine = engine


def paint(layout_path, tex_dir, occlusion):
    """Paints the textures (boxer_paint.py runs outside Blender: it needs Pillow)."""
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, "boxer_paint.py"), layout_path, tex_dir, occlusion], check=True)


def wheel_uvs(obj):
    """Tread around the tyre (texture's upper half), the hub on the sides (lower half)."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        side = abs(poly.normal.y) > 0.7
        corners = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if side:
                corners.append((li, 0.5 + co.x / (WHEEL_RADIUS * 2.1), 0.75 + co.z / (WHEEL_RADIUS * 4.2)))
            else:
                angle = (math.atan2(co.z, co.x) / (2 * math.pi)) % 1.0
                corners.append((li, angle, 0.25 + co.y / WHEEL_WIDTH * 0.45))
        if not side:
            # A face across the seam of the wrap: keep its corners together.
            us = [u for _, u, _ in corners]
            if max(us) - min(us) > 0.5:
                corners = [(li, u + 1.0 if u < 0.5 else u, v) for li, u, v in corners]
            corners = [(li, u * 3, v) for li, u, v in corners]
        for li, u, v in corners:
            uv.data[li].uv = (u, v)


def render_previews(prefix):
    from mathutils import Vector
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 800, 600
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.62, 0.65, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    for i, angle in enumerate((35, 145, 250)):
        a = math.radians(angle)
        cam.location = Vector((math.cos(a) * 48, math.sin(a) * 48, 30))
        cam.rotation_euler = (Vector((0, 0, 4)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{i}.png"
        bpy.ops.render.render(write_still=True)


def build():
    """Makes the Boxer in the open scene: its parts, UVs, paint and textures. Returns the parts."""
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    os.makedirs(tex_dir, exist_ok=True)
    chassis, top = hull(), turret()
    flash = muzzle_flash()
    stripes = [house_colour(1), house_colour(-1)]
    wheels = []
    for i, x in enumerate(WHEEL_X):
        for j, side in enumerate((1, -1)):
            wheels.append(wheel(f"TIRE0{i * 2 + j + 1}", (x, side * WHEEL_Y, WHEEL_Z)))
    for obj, part in ((chassis, "hull"), (top, "turret")):
        smooth_by_angle(obj)
        panel_unwrap(obj, part)
    for obj in wheels:
        smooth_by_angle(obj, 50)
        wheel_uvs(obj)
    for obj in stripes + [flash]:
        obj.data.uv_layers.new(name="UVMap")

    layout = os.path.join(BUILD, NAME + "_layout.json")
    os.makedirs(BUILD, exist_ok=True)
    export_layout(((chassis, "hull"), (top, "turret")), layout)
    occlusion = os.path.join(BUILD, NAME + "_ao.png")
    bake_occlusion([chassis, top], occlusion)
    paint(layout, tex_dir, occlusion)
    hull_image = load_image(os.path.join(tex_dir, HULL_TEXTURE))
    tire_image = load_image(os.path.join(tex_dir, TIRE_TEXTURE))
    for obj in (chassis, top):
        textured(obj, hull_image)
    for obj in wheels:
        textured(obj, tire_image)
    # In Blender, a team colour for the preview; the game paints these in the player's colour.
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    colour.diffuse_color = (0.08, 0.2, 0.75, 1)
    for obj in stripes:
        obj.data.materials.append(colour)
    return dict(chassis=chassis, turret=top, flash=flash, stripes=stripes, wheels=wheels)


def export(parts, name, hull_texture):
    """Writes the model; the damaged one is the same with another texture."""
    model = w3d.Model(name)
    bones = {}
    for obj in parts["wheels"] + [parts["turret"]]:
        bones[obj.name] = model.bone(obj.name, w3d.CHASSIS, tuple(obj.location))
    model.bone("MUZZLE01", bones["TURRET"], MUZZLE)
    bones["MUZZLEFX01"] = model.bone("MUZZLEFX01", bones["TURRET"], MUZZLE)
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=hull_texture)
    model.mesh("TURRET", bones["TURRET"], **mesh_data(parts["turret"]), texture=hull_texture)
    for obj in parts["wheels"]:
        model.mesh(obj.name, bones[obj.name], **mesh_data(obj), texture=TIRE_TEXTURE)
    for obj in parts["stripes"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture="Housecolor2.tga", shadow=False)
    model.mesh("MUZZLEFX01", bones["MUZZLEFX01"], **mesh_data(parts["flash"]), texture="EXTnkMzl01.tga", shadow=False,
               shader=w3d.ADDITIVE_SHADER)
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    export(parts, NAME, HULL_TEXTURE)
    export(parts, NAME + "_D", DAMAGED_TEXTURE)
    parts["flash"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    render_previews(os.path.join(BUILD, NAME))


if __name__ == "__main__":
    main()

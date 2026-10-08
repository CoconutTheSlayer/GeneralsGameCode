"""The European Leopard 2A7 main battle tank, modelled in Blender from simple shapes and written as a W3D model
for the game, the way boxer.py makes the Boxer: shapes, a panel-layout texture painted in Python (leopard_paint.py)
with baked ambient occlusion, and a damaged version. The tank parts here (tracks, road wheels, panel UVs, export
with scrolling treads) are shared with the Leclerc (leclerc.py).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/leopard.py

Writes resources/macos/GameData/Art/W3D/EULEO.w3d and EULEO_D.w3d, Art/TexturesHD/euleo.tga, euleo_d.tga and
euleo_tread.tga, and build/models/EULEO.blend with previews next to it.

The game's axes: +X forward, +Z up, in world units (the USA Crusader it replaces is about 29 long). Bones, named
like the Crusader's (AVLeopard), so the tank draw module of the game finds them:
    CHASSIS                    hull, skirts, road wheels; the meshes TREADSL01 / TREADSR01 are the tracks whose
                               texture W3DTankDraw scrolls (a linear offset mapper on their material)
    TURRET                     turning about Z
    BARREL01                   the gun, which recoils when it fires (WeaponRecoilBone = Barrel)
    TURRETMS01, TURRETFX01     the muzzle: where shells leave, and the flash
    SMOKE01..05                where a badly damaged tank smokes (TransitionDamageFX, RandomBone)
    TREADFX01..04              the track ends
    HOUSECOLOR01..04           panels in the player's colour
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
TEX_DIR = os.path.join(DATA, "Art", "TexturesHD")
sys.path.insert(0, HERE)
from blender_kit import box, cylinder, load_image, mesh_data, new_object, prism, smooth_by_angle, textured  # noqa: E402
from leopard_layout import Layout, group  # noqa: E402
import w3d  # noqa: E402

# Tread texture: the scrolling mapper of the game's own tanks; W3DTankDraw stops its own motion and moves it.
TREAD_MAPPER = "UPerSec=0.0"


# --- shapes ----------------------------------------------------------------------------------------

def plan_prism(bm, pts):
    """A solid from a convex outline seen from above, each corner (x, y, z_bottom, z_top)."""
    bottom = [bm.verts.new((x, y, zb)) for x, y, zb, zt in pts]
    top = [bm.verts.new((x, y, zt)) for x, y, zb, zt in pts]
    faces = [bm.faces.new(bottom), bm.faces.new(top)]
    n = len(pts)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((bottom[i], bottom[j], top[j], top[i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def side_prism(bm, profile, y0, y1):
    """A solid from a side outline (x, z), between y0 and y1 (a plate seen from the side)."""
    a = [bm.verts.new((x, y0, z)) for x, z in profile]
    b = [bm.verts.new((x, y1, z)) for x, z in profile]
    faces = [bm.faces.new(a), bm.faces.new(b)]
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((a[i], a[j], b[j], b[i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def bevel_shell(bm, faces, offset):
    """Chamfers the sharp edges of one closed shell: the edges catch the light."""
    edges = {e for f in faces for e in f.edges}
    sharp = [e for e in edges if e.is_manifold and e.calc_face_angle(0) > math.radians(25)]
    bmesh.ops.bevel(bm, geom=sharp, offset=offset, segments=1, affect="EDGES", profile=0.5)


def track(name, loop, y0, y1, thickness=0.4, per_unit=0.25):
    """A closed track belt. loop: its outline (x, z) going backwards along the ground, up at the rear, forwards on
    top and down at the front. UVs for the tread texture: u along the belt (whole turns of the texture, so it
    tiles), v: the pads (0.5..1), the link ends (0.25..0.5), the inside (0..0.25)."""
    n = len(loop)
    normals = []
    for i in range(n):
        out = [0.0, 0.0]
        for a, b in ((loop[i - 1], loop[i]), (loop[i], loop[(i + 1) % n])):
            dx, dz = b[0] - a[0], b[1] - a[1]
            d = math.hypot(dx, dz)
            out[0] += -dz / d
            out[1] += dx / d
        d = math.hypot(*out)
        normals.append((out[0] / d, out[1] / d))
    inner = [(x - nx * thickness, z - nz * thickness) for (x, z), (nx, nz) in zip(loop, normals)]
    lengths = [math.dist(loop[i], loop[(i + 1) % n]) for i in range(n)]
    turns = max(1, round(sum(lengths) * per_unit))
    k = turns / sum(lengths)
    us = [0.0]
    for length in lengths:
        us.append(us[-1] + length * k)

    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    o0 = [bm.verts.new((x, y0, z)) for x, z in loop]
    o1 = [bm.verts.new((x, y1, z)) for x, z in loop]
    i0 = [bm.verts.new((x, y0, z)) for x, z in inner]
    i1 = [bm.verts.new((x, y1, z)) for x, z in inner]
    faces = []

    def quad(verts, uvs):
        f = bm.faces.new(verts)
        for lp, t in zip(f.loops, uvs):
            lp[uv].uv = t
        faces.append(f)

    for i in range(n):
        j = (i + 1) % n
        ua, ub = us[i], us[i + 1]
        quad((o0[i], o0[j], o1[j], o1[i]), ((ua, 0.5), (ub, 0.5), (ub, 1.0), (ua, 1.0)))       # pads
        quad((i0[i], i1[i], i1[j], i0[j]), ((ua, 0.0), (ua, 0.25), (ub, 0.25), (ub, 0.0)))     # inside
        quad((o0[i], i0[i], i0[j], o0[j]), ((ua, 0.5), (ua, 0.25), (ub, 0.25), (ub, 0.5)))     # link ends
        quad((o1[i], o1[j], i1[j], i1[i]), ((ua, 0.5), (ub, 0.5), (ub, 0.25), (ua, 0.25)))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return new_object(name, bm)


def wheels(name, centres, y0, y1, layout, island, segments=8):
    """Road wheels, idler and sprocket of both sides as one mesh: discs (x, z, radius) between y0 and y1 and
    mirrored. Their faces all map onto one painted wheel on the texture (island: centre x, y, radius in pixels;
    the rubber tyre on the strip island["tyre"])."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    size = layout.size
    cx, cy, cr = island["disc"]
    tx0, ty0, tx1, ty1 = island["tyre"]
    for side in (1, -1):
        for x, z, r in centres:
            ring0, ring1 = [], []
            for k in range(segments):
                a = 2 * math.pi * k / segments
                ring0.append(bm.verts.new((x + math.cos(a) * r, side * y0, z + math.sin(a) * r)))
                ring1.append(bm.verts.new((x + math.cos(a) * r, side * y1, z + math.sin(a) * r)))
            faces = [bm.faces.new(ring0), bm.faces.new(ring1)]
            for k in range(segments):
                j = (k + 1) % segments
                faces.append(bm.faces.new((ring0[k], ring0[j], ring1[j], ring1[k])))
            bmesh.ops.recalc_face_normals(bm, faces=faces)
            for f in faces:
                disc = abs(f.normal.y) > 0.7
                for lp in f.loops:
                    co = lp.vert.co
                    if disc:
                        px, py = cx + (co.x - x) / r * cr, cy - (co.z - z) / r * cr
                    else:
                        a = (math.atan2(co.z - z, co.x - x) / (2 * math.pi)) % 1.0
                        px = tx0 + (tx1 - tx0) * a
                        py = ty0 if abs(co.y) == min(y0, y1) else ty1
                    lp[uv].uv = (px / size, 1 - py / size)
            # The face across the seam of the tyre: keep its corners together.
            for f in faces[2:]:
                us = [lp[uv].uv[0] for lp in f.loops]
                if max(us) - min(us) > 0.5 * (tx1 - tx0) / size:
                    for lp in f.loops:
                        if lp[uv].uv[0] < (tx0 + tx1) / 2 / size:
                            lp[uv].uv[0] += (tx1 - tx0) / size
    return new_object(name, bm)


def quad_object(name, corners, location=(0, 0, 0)):
    """A flat panel (house colour), facing the side its corners turn anticlockwise to."""
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    obj = new_object(name, bm, location)
    obj.data.uv_layers.new(name="UVMap")
    return obj


def side_panels(name, x0, x1, z0, z1, y, location=(0, 0, 0)):
    """The same panel on both sides (at +y and -y), facing out."""
    bm = bmesh.new()
    for s in (1, -1):
        verts = [bm.verts.new(v) for v in ((x0, s * y, z0), (x1, s * y, z0), (x1, s * y, z1), (x0, s * y, z1))]
        bm.faces.new(verts if s < 0 else list(reversed(verts)))
    obj = new_object(name, bm, location)
    obj.data.uv_layers.new(name="UVMap")
    return obj


def muzzle_flash(name, location, length=6.0, radius=1.6):
    """Two crossed quads along +x (additive, EXTnkMzl01.tga, as the game's tanks)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * radius, math.sin(a) * radius
        f = bm.faces.new([bm.verts.new(v) for v in ((0, -c, -s), (length, -c, -s), (length, c, s), (0, c, s))])
        for lp, t in zip(f.loops, ((0, 0), (1, 0), (1, 1), (0, 1))):
            lp[uv].uv = t
    return new_object(name, bm, location)


# --- texture ---------------------------------------------------------------------------------------

def panel_unwrap(obj, part, layout):
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = layout.uv(part, grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def export_layout(parts, layout, path):
    """The faces as they lie on the texture and which of their edges are seams, for the painter."""
    faces = []
    for obj, part in parts:
        me = obj.data
        edge_faces = {}
        for poly in me.polygons:
            for key in poly.edge_keys:
                edge_faces.setdefault(key, []).append(poly)
        for poly in me.polygons:
            grp = group(tuple(poly.normal))
            vs = list(poly.vertices)
            sharp = []
            for i in range(len(vs)):
                key = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
                around = edge_faces.get(key, [])
                sharp.append(len(around) != 2 or around[0].normal.angle(around[1].normal, 0) > math.radians(25))
            faces.append(dict(part=part, group=grp, sharp=sharp,
                              px=[layout.pixel(part, grp, tuple(me.vertices[v].co)) for v in vs]))
    with open(path, "w") as f:
        json.dump(dict(spec=layout.spec, faces=faces), f)


def bake_occlusion(objects, path, size):
    """Bakes ambient occlusion of the panelled parts on their islands, for the painter to shade with."""
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


def paint(painter, layout_path, occlusion):
    """Runs the painter outside Blender (it needs Pillow and numpy)."""
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, painter), layout_path, TEX_DIR, occlusion], check=True)


def render_previews(prefix, distance=60, centre=(4, 0, 4)):
    from mathutils import Vector
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 900, 640
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
    for i, (angle, height) in enumerate(((35, 0.6), (145, 0.6), (250, 0.6), (90, 0.12))):
        a = math.radians(angle)
        cam.location = Vector((centre[0] + math.cos(a) * distance, centre[1] + math.sin(a) * distance,
                               centre[2] + distance * height))
        cam.rotation_euler = (Vector(centre) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{i}.png"
        bpy.ops.render.render(write_still=True)


def preview_material(objs, colour):
    mat = bpy.data.materials.new("preview")
    mat.use_nodes = True
    mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = colour
    for obj in objs:
        obj.data.materials.clear()
        obj.data.materials.append(mat)


# --- export ----------------------------------------------------------------------------------------

def export(parts, name, texture, tread_texture, turret_bone="TURRET"):
    """Writes a tank. parts: chassis, wheels, treads (left, right), turret, barrel (objects placed at their bones),
    stripes [(object, bone name)], flash, muzzle (in the barrel's space), bones [(name, parent, at)]."""
    model = w3d.Model(name)
    bones = {"CHASSIS": w3d.CHASSIS}
    turret, barrel = parts["turret"], parts["barrel"]
    bones[turret_bone] = model.bone(turret_bone, w3d.CHASSIS, tuple(turret.location))
    bones["BARREL01"] = model.bone("BARREL01", bones[turret_bone], tuple(barrel.location - turret.location))
    bones["TURRETMS01"] = model.bone("TURRETMS01", bones["BARREL01"], parts["muzzle"])
    bones["TURRETFX01"] = model.bone("TURRETFX01", bones["BARREL01"], parts["muzzle"])
    for bone_name, parent, at in parts["bones"]:
        bones[bone_name] = model.bone(bone_name, bones[parent], at)
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=texture)
    model.mesh("WHEELS", w3d.CHASSIS, **mesh_data(parts["wheels"]), texture=texture)
    for obj in parts["treads"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=tread_texture, shadow=False,
                   mapper_args=TREAD_MAPPER)
    model.mesh(turret_bone, bones[turret_bone], **mesh_data(turret), texture=texture)
    model.mesh("BARREL01", bones["BARREL01"], **mesh_data(barrel), texture=texture)
    for obj, bone_name in parts["stripes"]:
        model.mesh(obj.name, bones[bone_name], **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("TURRETFX01", bones["TURRETFX01"], **mesh_data(parts["flash"]), texture="EXTnkMzl01.tga",
               shadow=False, shader=w3d.ADDITIVE_SHADER)
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def finish(parts, name, painter, panelled, layout, previews_centre=(4, 0, 4)):
    """UVs, occlusion, paint, models and previews: the steps every tank shares. panelled: [(object, part)]."""
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)
    w3d.write_house_colour(TEX_DIR)
    for obj, part in panelled:
        smooth_by_angle(obj)
        panel_unwrap(obj, part, layout)
    smooth_by_angle(parts["wheels"], 50)
    for obj in parts["treads"]:
        smooth_by_angle(obj, 50)
    layout_path = os.path.join(BUILD, name + "_layout.json")
    export_layout(panelled, layout, layout_path)
    occlusion = os.path.join(BUILD, name + "_ao.png")
    bake_occlusion([obj for obj, _ in panelled], occlusion, layout.size)
    paint(painter, layout_path, occlusion)
    prefix = name.lower()
    hull_image = load_image(os.path.join(TEX_DIR, prefix + ".tga"))
    for obj, _ in panelled:
        textured(obj, hull_image)
    textured(parts["wheels"], hull_image)
    tread_image = load_image(os.path.join(TEX_DIR, parts["tread_texture"]))
    for obj in parts["treads"]:
        textured(obj, tread_image)
    preview_material([obj for obj, _ in parts["stripes"]], (0.08, 0.2, 0.75, 1))
    export(parts, name, prefix + ".tga", parts["tread_texture"], parts.get("turret_bone", "TURRET"))
    export(parts, name + "_D", prefix + "_d.tga", parts["tread_texture"], parts.get("turret_bone", "TURRET"))
    parts["flash"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, name + ".blend"))
    render_previews(os.path.join(BUILD, name), centre=previews_centre)
    # The damaged look, from the first angle.
    damaged = load_image(os.path.join(TEX_DIR, prefix + "_d.tga"))
    for obj, _ in panelled:
        textured(obj, damaged)
    textured(parts["wheels"], damaged)
    from mathutils import Vector
    cam = bpy.context.scene.camera
    a = math.radians(35)
    cam.location = Vector((previews_centre[0] + math.cos(a) * 60, math.sin(a) * 60, previews_centre[2] + 36))
    cam.rotation_euler = (Vector(previews_centre) - cam.location).to_track_quat("-Z", "Y").to_euler()
    bpy.context.scene.render.filepath = os.path.join(BUILD, name + "_damaged.png")
    bpy.ops.render.render(write_still=True)


# --- the Leopard -----------------------------------------------------------------------------------

NAME = "EULEO"
TURRET_AT = (-1.2, 0.0, 6.0)
BARREL_AT = (6.8, 0.0, 1.85)       # in the turret's space: the gun's trunnion, in the mantlet
MUZZLE = (21.6, 0.0, 0.0)          # in the barrel's space
TRACK_Y = (5.15, 7.95)
TRACK_LOOP = [(10.8, 0.0), (-10.9, 0.0), (-12.7, 1.0), (-14.3, 2.3), (-14.25, 3.3), (-13.5, 4.0), (-12.0, 4.2),
              (11.8, 4.1), (13.3, 3.6), (14.0, 2.6), (13.3, 1.4), (12.2, 0.5)]
ROAD_WHEELS = [(-10.4 + k * 20.0 / 6, 1.35, 1.35) for k in range(7)] + [(12.7, 2.6, 1.05), (-13.1, 2.7, 1.1)]

LAYOUT = Layout({
    "size": 1024,
    "parts": {
        "hull": {"box": ((-15.6, 15.6), (-9.0, 9.0), (0.0, 6.4)), "scale": 20,
                 "islands": {"top": (4, 4), "side": (4, 370), "front": (4, 504), "back": (370, 504)},
                 "bottom": (4, 700, 4)},
        "turret": {"box": ((-10.2, 10.4), (-6.4, 6.4), (0.0, 5.2)), "scale": 17,
                   "islands": {"top": (640, 4), "side": (640, 240), "front": (640, 340), "back": (640, 440)},
                   "bottom": (140, 700, 4)},
        "barrel": {"box": ((-0.1, 21.8), (-0.7, 0.7), (-0.7, 0.7)), "scale": 20,
                   "islands": {"top": (4, 640), "side": (4, 668), "front": (450, 640), "back": (480, 640)},
                   "bottom": (220, 700, 4)},
    },
    # the painted road wheel (centre x, y, radius) and the strip of rubber around it
    "wheel": {"disc": (930, 630, 88), "tyre": (600, 700, 800, 730)},
})


def leopard_hull():
    bm = bmesh.new()
    # Lower hull between the tracks: a steep nose under the glacis.
    side_prism(bm, [(-14.4, 1.1), (11.2, 1.1), (14.6, 3.3), (14.8, 4.4), (-14.8, 4.4), (-14.9, 2.2)], -5.0, 5.0)
    # The deck over the tracks, with the long flat glacis of the Leopard 2.
    deck = side_prism(bm, [(-15.2, 4.3), (14.9, 4.3), (15.3, 4.7), (11.0, 6.0), (-14.4, 6.0), (-15.2, 5.4)],
                      -8.0, 8.0)
    bevel_shell(bm, deck, 0.18)
    for s in (1, -1):
        # Side skirts: the heavy armoured front sections of the A7, light ones behind.
        side_prism(bm, [(-14.5, 2.9), (8.6, 2.9), (8.6, 5.9), (-14.5, 5.9)], s * 8.0, s * 8.35)
        side_prism(bm, [(8.6, 2.1), (13.6, 2.1), (14.9, 3.4), (14.9, 5.9), (8.6, 5.9)], s * 8.0, s * 8.85)
        # Headlight guards on the glacis corners, mirrors' stubs.
        box(bm, (13.0, s * 6.2, 5.0), (14.0, s * 7.4, 5.6))
        # Track guard plates over the rear sprocket.
        box(bm, (-15.0, s * 5.2, 4.0), (-13.8, s * 8.0, 4.4))
    # Engine deck: grille housings, the driver's hatch, a fuel can rack and a towing bar at the back.
    box(bm, (-13.8, -4.6, 6.0), (-7.0, 4.6, 6.2))
    cylinder(bm, (9.0, -2.4, 6.05), 0.8, 0.14, segments=10)
    box(bm, (10.0, -3.3, 6.0), (10.4, -1.5, 6.3))                      # driver's periscopes
    box(bm, (-15.7, -6.0, 4.4), (-15.2, -2.0, 5.6))                    # stowage boxes on the rear plate
    box(bm, (-15.7, 2.0, 4.4), (-15.2, 6.0, 5.6))
    for y in (-3.8, 3.8):
        cylinder(bm, (-15.4, y, 3.6), 0.28, 0.9, axis="X", segments=8)  # exhaust grilles' rims
    return new_object("CHASSIS", bm)


def leopard_turret():
    bm = bmesh.new()
    body = plan_prism(bm, [(-9.0, -4.6, 0.3, 3.3), (-7.8, -5.9, 0.0, 3.4), (4.6, -6.0, 0.0, 3.4),
                           (4.6, 6.0, 0.0, 3.4), (-7.8, 5.9, 0.0, 3.4), (-9.0, 4.6, 0.3, 3.3)])
    bevel_shell(bm, body, 0.16)
    # The wedge add-on armour: an arrowhead each side of the gun, sloping down to its point.
    for s in (1, -1):
        wedge = plan_prism(bm, [(3.8, s * 6.05, 0.2, 3.45), (3.8, s * 1.3, 0.2, 3.45), (6.6, s * 1.3, 0.6, 3.0),
                                (10.2, s * 1.9, 1.0, 2.0)])
        bevel_shell(bm, wedge, 0.1)
    box(bm, (4.6, -1.3, 0.7), (7.0, 1.3, 2.9))                        # gun mantlet
    # Roof: the gunner's sight in its armoured box, the commander's panoramic periscope, hatches, the remote
    # weapon station, the crosswind sensor.
    box(bm, (1.4, -4.6, 3.35), (3.9, -2.8, 4.35))
    box(bm, (3.85, -4.3, 3.5), (4.0, -3.1, 4.15))                     # its window
    cylinder(bm, (-1.6, 3.1, 3.85), 0.7, 0.9, segments=10)
    box(bm, (-2.2, 2.5, 4.3), (-0.9, 3.7, 5.1))                       # periscope head
    for x, y in ((-4.0, 2.8), (-4.0, -2.4)):
        cylinder(bm, (x, y, 3.45), 0.95, 0.14, segments=10)
    cylinder(bm, (-5.6, -3.6, 3.6), 0.55, 0.45, segments=8)
    box(bm, (-6.2, -3.95, 3.8), (-4.8, -3.25, 4.35))
    cylinder(bm, (-4.0, -3.6, 4.08), 0.08, 1.8, axis="X", segments=6)
    cylinder(bm, (-7.2, 0.0, 3.8), 0.08, 0.8, segments=6)
    # Bustle stowage basket, smoke dischargers on the cheeks, antennas.
    box(bm, (-10.1, -4.4, 0.9), (-8.8, 4.4, 2.7))
    for s in (1, -1):
        for k in range(4):
            cylinder(bm, (1.0 + k * 0.45, s * 6.25, 2.8), 0.2, 0.6, axis="Y", segments=6)
        cylinder(bm, (-7.6, s * 4.4, 5.1), 0.05, 3.4, segments=4)
    return new_object("TURRET", bm, TURRET_AT)


def leopard_barrel():
    """The long 120 mm L55 gun along +x from its trunnion, with its thermal sleeve."""
    bm = bmesh.new()
    cylinder(bm, (1.0, 0, 0), 0.62, 2.0, axis="X", segments=8)         # breech end in the mantlet
    cylinder(bm, (10.8, 0, 0), 0.38, 21.6, axis="X", segments=8)
    for x in (4.3, 9.6, 14.9):
        cylinder(bm, (x, 0, 0), 0.46, 0.6, axis="X", segments=8)       # sleeve clamps
    box(bm, (20.6, -0.14, 0.34), (21.3, 0.14, 0.62))                   # muzzle reference sensor
    location = [TURRET_AT[i] + BARREL_AT[i] for i in range(3)]
    return new_object("BARREL01", bm, location)


def build():
    hull, top, gun = leopard_hull(), leopard_turret(), leopard_barrel()
    gear = wheels("WHEELS", ROAD_WHEELS, 5.3, 7.8, LAYOUT, LAYOUT.spec["wheel"])
    treads = [track("TREADSL01", TRACK_LOOP, -TRACK_Y[1], -TRACK_Y[0]), track("TREADSR01", TRACK_LOOP, *TRACK_Y)]
    stripes = [
        (side_panels("HOUSECOLOR01", -7.2, -3.6, 1.1, 2.5, 5.97, TURRET_AT), "TURRET"),
        (side_panels("HOUSECOLOR02", -13.6, -9.6, 4.3, 5.4, 8.37), "CHASSIS"),
    ]
    muzzle_at = [TURRET_AT[i] + BARREL_AT[i] + MUZZLE[i] for i in range(3)]
    parts = dict(chassis=hull, turret=top, barrel=gun, wheels=gear, treads=treads, stripes=stripes,
                 flash=muzzle_flash("TURRETFX01", muzzle_at), muzzle=MUZZLE, tread_texture="euleo_tread.tga",
                 bones=[("SMOKE01", "CHASSIS", (0.5, 0.0, 6.2)), ("SMOKE02", "CHASSIS", (8.0, 5.0, 5.8)),
                        ("SMOKE03", "CHASSIS", (-1.0, -4.0, 9.4)), ("SMOKE04", "CHASSIS", (-8.0, -2.4, 6.3)),
                        ("SMOKE05", "CHASSIS", (-12.5, 2.3, 6.4)),
                        ("TREADFX01", "CHASSIS", (-11.0, 6.6, 0.1)), ("TREADFX02", "CHASSIS", (-11.0, -6.6, 0.1)),
                        ("TREADFX03", "CHASSIS", (11.0, 6.6, 0.1)), ("TREADFX04", "CHASSIS", (11.0, -6.6, 0.1))])
    return parts, [(hull, "hull"), (top, "turret"), (gun, "barrel")]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts, panelled = build()
    finish(parts, NAME, "leopard_paint.py", panelled, LAYOUT)


if __name__ == "__main__":
    main()

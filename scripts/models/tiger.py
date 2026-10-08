"""The European Tiger, an attack helicopter (tandem cockpit, stub wings with missiles and rocket pods, a
chin gun, a four-blade rotor), modelled in Blender from simple shapes and written as a W3D model for the
game, in place of the USA Comanche it is built on. Everything in it is made here.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/tiger.py

Writes resources/macos/GameData/Art/W3D/EUTIGR.w3d and EUTIGR_D.w3d (damaged), Art/TexturesHD/eutig_*.tga,
and build/models/EUTIGR.blend with previews next to it. Also the helicopters' shared helpers (the NH90,
nh90.py, imports them).

The rotors spin as the Comanche's do: a looping W3D animation in the model's file (EUTIGR.EUTIGR, 21
frames at 30 a second) turns the bone PROPELLER01 a full turn clockwise seen from above and PROPELLER02
(the tail rotor) two turns; the main rotor's blades are a blurred, alpha blended disc on PROPELLER01.

The game's axes: +X forward, +Z up, the model's origin on the ground. Bones (the Comanche's, so its INI,
death and upgrade logic find them):
    PROPELLER01, PROPELLER02   main and tail rotor (HelicopterSlowDeath: blades fly off, smoke trail)
    MUZZLE01, TURRETFX01       the chin gun's muzzle and its flash (cannon)
    WEAPONA01..04              the missile launchers' tubes (anti-tank missiles)
    MISSILEUPGRADE             the rocket pods, shown with the rocket pod upgrade; WEAPONB01..04 their tubes
    SMOKE01/02, FLARE01/02     damage smoke at the exhausts, countermeasure flares
    HOUSECOLOR01               the player's colour on the fin and wings
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
from blender_kit import box, cylinder, load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
import tiger_paint  # noqa: E402
import w3d  # noqa: E402

NAME = "EUTIGR"
BODY, BODY_D, ROTOR = "eutig_body.tga", "eutig_body_d.tga", "eutig_rotor.tga"
LAYOUT = tiger_paint.TIGER

# The rotors: where they turn and how far they reach.
ROTOR_AT, ROTOR_RADIUS, ROTOR_BLADES = (0.5, 0.0, 10.9), 21.0, 4
TAIL_AT, TAIL_RADIUS = (-24.0, -0.75, 8.7), 3.6
# The tail rotor turns about its bone's Z, which points to the right (-Y): a quarter turn about X.
TAIL_ROTATION = (math.sin(math.pi / 4), 0.0, 0.0, math.cos(math.pi / 4))
MUZZLE = (19.9, 0.0, 1.85)
MISSILE_TUBES = [(2.9, 6.3, 3.75), (2.9, -6.3, 3.75), (2.9, 6.9, 3.2), (2.9, -6.9, 3.2)]
ROCKET_TUBES = [(2.75, 4.25, 3.95), (2.75, -4.25, 3.95), (2.75, 3.75, 3.45), (2.75, -3.75, 3.45)]


# --- shapes ----------------------------------------------------------------------------------------

def _f(c, n):
    return math.copysign(abs(c) ** (2.0 / n), c)


def loft(bm, stations, axis="X", segments=14):
    """A closed body through cross-sections along an axis: each station (t, c1, c2, h1, h2, n) is a rounded
    rectangle (superellipse of exponent n) at t, centred at c1, c2 with half sizes h1, h2 in the other two
    axes (X: y, z; Y: x, z; Z: x, y). The ends are capped."""
    rings = []
    for t, c1, c2, h1, h2, n in stations:
        ring = []
        for k in range(segments):
            a = 2 * math.pi * k / segments
            p, q = c1 + h1 * _f(math.cos(a), n), c2 + h2 * _f(math.sin(a), n)
            co = {"X": (t, p, q), "Y": (p, t, q), "Z": (p, q, t)}[axis]
            ring.append(bm.verts.new(co))
        rings.append(ring)
    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        for k in range(segments):
            j = (k + 1) % segments
            faces.append(bm.faces.new((r0[k], r0[j], r1[j], r1[k])))
    for ring, (t, c1, c2, *_), flip in ((rings[0], stations[0], True), (rings[-1], stations[-1], False)):
        co = {"X": (t, c1, c2), "Y": (c1, t, c2), "Z": (c1, c2, t)}[axis]
        centre = bm.verts.new(co)
        for k in range(segments):
            j = (k + 1) % segments
            faces.append(bm.faces.new((ring[k], ring[j], centre)))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def fuselage_station(x, bottom, top, half_width, n=2.6, y=0.0):
    return (x, y, (bottom + top) / 2, half_width, (top - bottom) / 2, n)


def blur_disc(name, radius, blades, inner=1.0, sweep=70.0, steps=5, z=0.05, clockwise=True):
    """The blurred blades: one flat sector per blade, both sides, u along the blade and v across its sweep
    (v = 1 at the blade's leading edge; it turns clockwise seen from above)."""
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    for b in range(blades):
        a0 = 360.0 * b / blades
        rows = []
        for k in range(steps + 1):
            a = math.radians(a0 + sweep * k / steps)
            rows.append(((math.cos(a) * inner, math.sin(a) * inner, z), (math.cos(a) * radius, math.sin(a) * radius, z),
                         k / steps))
        for (i0, o0, t0), (i1, o1, t1) in zip(rows, rows[1:]):
            v0, v1 = (1 - t0, 1 - t1) if clockwise else (t0, t1)
            for verts, uvs in (((i0, o0, o1, i1), ((0, v0), (1, v0), (1, v1), (0, v1))),
                               ((i1, o1, o0, i0), ((0, v1), (1, v1), (1, v0), (0, v0)))):
                face = bm.faces.new([bm.verts.new(v) for v in verts])
                for loop, t in zip(face.loops, uvs):
                    loop[uv].uv = t
    for face in bm.faces:
        face.normal_update()
    return new_object(name, bm)


def flat_quad(bm, corners, flip=False):
    verts = [bm.verts.new(c) for c in corners]
    bm.faces.new(list(reversed(verts)) if flip else verts)


def spin(frames, turns):
    """Quaternions turning about Z, a frame each, by `turns` whole turns (clockwise seen from above when
    positive): the first and the last frame are the same pose, so the loop is seamless."""
    out = []
    for i in range(frames):
        half = -math.pi * turns * i / (frames - 1)
        out.append((0.0, 0.0, math.sin(half), math.cos(half)))
    return out


def muzzle_flash(name, at, length=2.6, radius=0.9):
    bm = bmesh.new()
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * radius, math.sin(a) * radius
        verts = [bm.verts.new(v) for v in ((0, -c, -s), (length, -c, -s), (length, c, s), (0, c, s))]
        bm.faces.new(verts)
    obj = new_object(name, bm, at)
    uv = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        for li, t in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[li].uv = t
    return obj


# --- the Tiger ---------------------------------------------------------------------------------------

def hull():
    bm = bmesh.new()
    # The fuselage, nose to tail: the gunner's canopy, a step up to the pilot's, the mast and engine bay,
    # then the slim tail boom.
    loft(bm, [
        fuselage_station(19.2, 3.0, 3.9, 0.25, 2.2),
        fuselage_station(18.0, 2.5, 4.6, 1.15, 2.4),
        fuselage_station(16.2, 2.3, 5.4, 1.6),
        fuselage_station(13.5, 2.2, 6.2, 1.85),
        fuselage_station(10.6, 2.2, 6.45, 1.95),
        fuselage_station(9.6, 2.2, 7.5, 2.0),
        fuselage_station(6.5, 2.2, 8.05, 2.1),
        fuselage_station(3.2, 2.3, 8.3, 2.2),
        fuselage_station(0.0, 2.4, 8.7, 2.3),
        fuselage_station(-3.5, 2.6, 8.7, 2.3),
        fuselage_station(-7.0, 3.1, 7.9, 1.9),
        fuselage_station(-10.0, 4.0, 7.1, 1.15, 2.4),
        fuselage_station(-17.0, 4.5, 6.5, 0.8, 2.4),
        fuselage_station(-23.2, 4.9, 6.2, 0.55, 2.4),
        fuselage_station(-24.6, 5.2, 6.0, 0.35, 2.2),
    ], segments=12)
    # Engines either side of the mast, intakes at the front, exhausts turned out at the back.
    for side in (1, -1):
        loft(bm, [
            fuselage_station(2.2, 6.75, 7.35, 0.2, 2.2, side * 2.15),
            fuselage_station(1.3, 6.15, 8.2, 0.95, 2.4, side * 2.25),
            fuselage_station(-6.0, 6.2, 8.2, 1.0, 2.6, side * 2.35),
            fuselage_station(-8.9, 6.7, 7.6, 0.55, 2.2, side * 2.75),
        ], segments=10)
    # The rotor mast.
    cylinder(bm, (ROTOR_AT[0], 0, 9.6), 0.5, 2.4, segments=10)
    loft(bm, [(8.4, ROTOR_AT[0], 0, 1.2, 0.9, 2.4), (9.4, ROTOR_AT[0] - 0.2, 0, 0.8, 0.6, 2.4)], axis="Z", segments=10)
    # Stub wings with a little anhedral, and their pylons.
    for side in (1, -1):
        loft(bm, [(side * 1.6, 0.3, 5.15, 2.1, 0.36, 2.6), (side * 7.6, 0.0, 4.55, 1.55, 0.24, 2.6)], axis="Y",
             segments=8)
        for y, z in ((6.6, 4.6), (4.0, 4.85)):
            box(bm, (-0.7, side * (y - 0.18), z - 0.75), (1.1, side * (y + 0.18), z))
        # The anti-tank missiles: a box of four tubes under each wing tip.
        box(bm, (-2.6, side * 5.95, 2.8), (2.55, side * 7.25, 3.95))
        for _, y, z in MISSILE_TUBES[:2] + MISSILE_TUBES[2:]:
            if y * side > 0:
                cylinder(bm, (2.62, y, z), 0.25, 0.25, axis="X", segments=6)
    # The chin gun: a round turret under the nose, its housing and a long barrel.
    loft(bm, [(1.0, 15.3, 0, 0.55, 0.55, 2.0), (1.25, 15.3, 0, 0.95, 0.95, 2.0), (2.1, 15.3, 0, 1.0, 1.0, 2.0),
              (2.6, 15.3, 0, 0.75, 0.75, 2.0)], axis="Z", segments=10)
    box(bm, (15.0, -0.38, 1.45), (17.0, 0.38, 2.15))
    cylinder(bm, (18.4, 0, MUZZLE[2]), 0.17, 3.0, axis="X", segments=6)
    cylinder(bm, (19.75, 0, MUZZLE[2]), 0.26, 0.35, axis="X", segments=6)
    # Sensors: the nose's sight turret and a small radar warner on each side.
    loft(bm, [(18.0, 0, 3.2, 0.55, 0.45, 2.2), (19.4, 0, 3.1, 0.5, 0.4, 2.2), (19.8, 0, 3.1, 0.25, 0.2, 2.0)],
         segments=10)
    # Tailplane with endplate fins, the fin with the tail rotor's gearbox, a ventral fin.
    loft(bm, [(-4.3, -18.3, 5.5, 1.1, 0.14, 2.6), (4.3, -18.3, 5.5, 1.1, 0.14, 2.6)], axis="Y", segments=8)
    for side in (1, -1):
        loft(bm, [(4.2, -18.6, side * 4.35, 1.1, 0.12, 2.6), (7.0, -18.0, side * 4.35, 0.9, 0.1, 2.6)], axis="Z",
             segments=8)
        loft(bm, [(3.9, -18.3, side * 4.35, 0.5, 0.09, 2.6), (4.25, -18.6, side * 4.35, 1.1, 0.12, 2.6)], axis="Z",
             segments=8)
    loft(bm, [(5.6, -22.6, 0, 1.9, 0.28, 2.6), (8.0, -23.3, 0, 1.55, 0.26, 2.6), (10.4, -24.4, 0, 0.9, 0.22, 2.6)],
         axis="Z", segments=8)
    cylinder(bm, (TAIL_AT[0], -0.45, TAIL_AT[2]), 0.42, 0.5, axis="Y", segments=8)
    loft(bm, [(2.9, -22.2, 0, 0.7, 0.18, 2.4), (5.0, -22.8, 0, 1.4, 0.22, 2.6)], axis="Z", segments=8)
    # Landing gear: main wheels on side struts, a tail wheel.
    for side in (1, -1):
        cylinder(bm, (4.2, side * 2.45, 2.35), 0.16, 1.9, axis="Y", segments=6)
        cylinder(bm, (4.2, side * 3.2, 1.75), 0.18, 1.3, segments=6)
        cylinder(bm, (4.2, side * 3.2, 0.85), 0.85, 0.5, axis="Y", segments=10)
    cylinder(bm, (-21.4, 0, 2.6), 0.14, 3.6, segments=6)
    cylinder(bm, (-21.4, 0, 0.6), 0.6, 0.35, axis="Y", segments=10)
    return new_object("CHASSIS", bm)


def rocket_pods():
    """The upgrade: a rocket pod on each wing's inner pylon (shown by ShowSubObject MissileUpgrade)."""
    bm = bmesh.new()
    for side in (1, -1):
        y = side * 4.0
        loft(bm, [(-2.4, y, 3.7, 0.45, 0.45, 2.0), (-1.9, y, 3.7, 0.78, 0.78, 2.0), (2.2, y, 3.7, 0.78, 0.78, 2.0),
                  (2.6, y, 3.7, 0.7, 0.7, 2.0)], segments=8)
    return new_object("MISSILEUPGRADE", bm)


def rotor_head():
    """The hub and blade roots (turning with PROPELLER01) and the mast-mounted sight on top."""
    from mathutils import Matrix
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0), 1.0, 0.8, segments=10)
    for b in range(ROTOR_BLADES):
        a = 2 * math.pi * b / ROTOR_BLADES + math.radians(35)
        bm_blade = bmesh.new()
        box(bm_blade, (0.7, -0.35, -0.13), (4.1, 0.35, 0.13))
        bmesh.ops.rotate(bm_blade, verts=bm_blade.verts, cent=(0, 0, 0),
                         matrix=Matrix.Rotation(a, 3, "Z"))
        me = bpy.data.meshes.new("tmp")
        bm_blade.to_mesh(me)
        bm_blade.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    cylinder(bm, (0, 0, 0.75), 0.3, 0.7, segments=6)
    loft(bm, [(1.1, 0, 0, 0.8, 0.8, 2.0), (1.9, 0, 0, 0.85, 0.85, 2.0), (2.4, 0, 0, 0.45, 0.45, 2.0)], axis="Z",
         segments=8)
    return new_object("PROPELLER01", bm, ROTOR_AT)


def tail_rotor(blades=3):
    """Three blades and the hub, in PROPELLER02's space (they turn about its Z, which points right)."""
    from mathutils import Matrix
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0), 0.42, 0.5, segments=10)
    for b in range(blades):
        blade = bmesh.new()
        box(blade, (0.3, -0.3, -0.07), (TAIL_RADIUS, 0.3, 0.07))
        bmesh.ops.rotate(blade, verts=blade.verts, cent=(0, 0, 0), matrix=Matrix.Rotation(2 * math.pi * b / blades, 3, "Z"))
        me = bpy.data.meshes.new("tmp")
        blade.to_mesh(me)
        blade.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    obj = new_object("PROPELLER02", bm, TAIL_AT)
    obj.rotation_euler = (math.pi / 2, 0, 0)
    return obj


def house_colour():
    """The player's colour: panels on both sides of the fin and across the stub wings."""
    bm = bmesh.new()
    for side in (1, -1):
        y = side * 0.33
        flat_quad(bm, [(-22.5, y, 6.4), (-24.2, y, 6.4), (-24.6, y, 8.4), (-23.0, y, 8.4)], flip=side < 0)
        for y0, y1 in ((2.6, 3.5),):
            z0 = 5.15 + 0.36 - (y0 - 1.6) / 6.0 * 0.72 + 0.05
            z1 = 5.15 + 0.36 - (y1 - 1.6) / 6.0 * 0.72 + 0.05
            flat_quad(bm, [(1.0, side * y0, z0), (1.0, side * y1, z1), (-0.6, side * y1, z1), (-0.6, side * y0, z0)],
                      flip=side < 0)
    obj = new_object("HOUSECOLOR01", bm)
    for poly in obj.data.polygons:
        poly.use_smooth = False
    return obj


# --- textures (shared with the NH90) -----------------------------------------------------------------

def unwrap(obj, part, layout):
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = tiger_paint.group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = layout.uv(part, grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def export_layout(name, parts, layout, path):
    faces = []
    for obj, part in parts:
        me = obj.data
        edge_faces = {}
        for poly in me.polygons:
            for key in poly.edge_keys:
                edge_faces.setdefault(key, []).append(poly)
        for poly in me.polygons:
            grp = tiger_paint.group(tuple(poly.normal))
            vs = list(poly.vertices)
            sharp = []
            for i in range(len(vs)):
                key = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
                around = edge_faces.get(key, [])
                sharp.append(len(around) != 2 or around[0].normal.angle(around[1].normal, 0) > math.radians(40))
            faces.append(dict(part=part, group=grp, px=[layout.pixel(part, grp, tuple(me.vertices[v].co)) for v in vs],
                              sharp=sharp))
    with open(path, "w") as f:
        json.dump(dict(name=name, faces=faces), f)


def bake_occlusion(objects, path, size=512):
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
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 48
    scene.render.bake.margin = 4
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.bake(type="AO")
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()


def run_painter(script, layout_path, tex_dir, occlusion):
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, script), layout_path, tex_dir, occlusion], check=True)


def blur_material(obj, image):
    mat = bpy.data.materials.new(obj.name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    node = nodes.new("ShaderNodeTexImage")
    node.image = image
    bsdf = nodes["Principled BSDF"]
    links.new(node.outputs["Color"], bsdf.inputs["Base Color"])
    links.new(node.outputs["Alpha"], bsdf.inputs["Alpha"])
    if hasattr(mat, "surface_render_method"):
        mat.surface_render_method = "BLENDED"
    else:
        mat.blend_method = "BLEND"
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def team_colour(objects):
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in objects:
        obj.data.materials.append(colour)


def render_previews(prefix, distance=80.0, height=48.0, target_z=5.0, angles=(35, 145, 250)):
    from mathutils import Vector
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
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
    for i, angle in enumerate(angles):
        a = math.radians(angle)
        cam.location = Vector((math.cos(a) * distance, math.sin(a) * distance, height))
        cam.rotation_euler = (Vector((0, 0, target_z)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{i}.png"
        bpy.ops.render.render(write_still=True)


# --- the Tiger: build and export -----------------------------------------------------------------------

def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    chassis, pods, head, tail = hull(), rocket_pods(), rotor_head(), tail_rotor()
    blur = blur_disc("PROPS01", ROTOR_RADIUS, ROTOR_BLADES)
    blur.location = ROTOR_AT
    flash = muzzle_flash("TURRETFX01", MUZZLE)
    colour = house_colour()
    painted = ((chassis, "hull"), (pods, "hull"), (head, "rotor"), (tail, "tail"))
    for obj, part in painted:
        smooth_by_angle(obj, 40)
        unwrap(obj, part, LAYOUT)
    colour.data.uv_layers.new(name="UVMap")
    w3d.write_house_colour(tex_dir)
    layout_path = os.path.join(BUILD, NAME + "_layout.json")
    export_layout(NAME, painted, LAYOUT, layout_path)
    occlusion = os.path.join(BUILD, NAME + "_ao.png")
    blur.hide_render = flash.hide_render = colour.hide_render = True
    bake_occlusion([chassis, pods, head, tail], occlusion)
    blur.hide_render = colour.hide_render = False
    run_painter("tiger_paint.py", layout_path, tex_dir, occlusion)
    body = load_image(os.path.join(tex_dir, BODY))
    for obj, _ in painted:
        textured(obj, body)
    blur_material(blur, load_image(os.path.join(tex_dir, ROTOR)))
    team_colour([colour])
    return dict(chassis=chassis, pods=pods, head=head, tail=tail, blur=blur, flash=flash, colour=colour)


def export(parts, name, body):
    model = w3d.Model(name)
    head = model.bone("PROPELLER01", w3d.CHASSIS, ROTOR_AT)
    tail = model.bone("PROPELLER02", w3d.CHASSIS, TAIL_AT, rotation=TAIL_ROTATION)
    model.bone("MUZZLE01", w3d.CHASSIS, MUZZLE)
    flash = model.bone("TURRETFX01", w3d.CHASSIS, MUZZLE)
    for i, at in enumerate(MISSILE_TUBES):
        model.bone(f"WEAPONA{i + 1:02d}", w3d.CHASSIS, at)
    upgrade = model.bone("MISSILEUPGRADE", w3d.CHASSIS, (0, 0, 0))
    for i, at in enumerate(ROCKET_TUBES):
        model.bone(f"WEAPONB{i + 1:02d}", upgrade, at)
    for i, side in enumerate((1, -1)):
        model.bone(f"SMOKE{i + 1:02d}", w3d.CHASSIS, (-8.6, side * 2.7, 7.3))
        model.bone(f"FLARE{i + 1:02d}", w3d.CHASSIS, (-7.5, side * 1.7, 3.4), yaw=180 - side * 30)
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=body)
    model.mesh("MISSILEUPGRADE", upgrade, **mesh_data(parts["pods"]), texture=body)
    model.mesh("PROPELLER01", head, **mesh_data(parts["head"]), texture=body, shadow=False)
    model.mesh("PROPELLER02", tail, **mesh_data(parts["tail"]), texture=body, shadow=False)
    model.mesh("PROPS01", head, **mesh_data(parts["blur"]), texture=ROTOR, shadow=False, shader=w3d.ALPHA_BLEND_SHADER)
    model.mesh("HOUSECOLOR01", w3d.CHASSIS, **mesh_data(parts["colour"]), texture=w3d.HOUSE_COLOUR_TEXTURE,
               shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("TURRETFX01", flash, **mesh_data(parts["flash"]), texture="EXTnkMzl01.tga", shadow=False,
               shader=w3d.ADDITIVE_SHADER)
    # The Comanche's rotor speeds: the main rotor a turn, the tail rotor two, every 20 frames at 30 a second.
    model.animate(21, 30, {head: spin(21, 1), tail: spin(21, 2)})
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = build()
    export(parts, NAME, BODY)
    export(parts, NAME + "_D", BODY_D)
    parts["flash"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    render_previews(os.path.join(BUILD, NAME))


if __name__ == "__main__":
    main()

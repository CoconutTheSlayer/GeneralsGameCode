"""The European PULS, a tracked multiple rocket launcher: an armoured cab at the front and, behind it, a
turntable carrying two rocket pods that elevate to fire. Modelled in Blender from simple shapes and written
as a W3D model for the game, with its camouflage and ambient occlusion made here (puls_paint.py). The
helpers here (tracks with scrolling treads, panel UVs, the bake and paint steps) are shared with the
Skyranger and the Wiesel.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/puls.py

Writes resources/macos/GameData/Art/W3D/EUPULS.w3d and EUPULS_D.w3d, Art/TexturesHD/eupuls.tga,
eupuls_d.tga and eupuls_tread.tga, and build/models/EUPULS.blend with previews next to it.

The game's axes: +X forward, +Z up, in world units (about 27 long, like the Tomahawk it replaces). Bones, as
the Tomahawk's draw module and weapon use them:
    TURRET                   the launcher's turntable, turning about Z
    TURRETEL                 the pods' cradle, pitching up to fire (pivot at the pods' rear)
    MISSILE                  the rockets' caps in the pod fronts, hidden while the launcher reloads
    WEAPONA01                where the rocket leaves the pods
    TREADSL / TREADSR        meshes whose texture W3DTankDraw scrolls
    HOUSECOLOR01..04         panels in the player's colour
    SMOKE01                  smoke when badly damaged
"""
import json
import math
import os
import shutil
import subprocess
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
BUILD = os.path.join(ROOT, "build", "models")
TEX_DIR = os.path.join(DATA, "Art", "TexturesHD")
sys.path.insert(0, HERE)
from puls_paint import Layout, group  # noqa: E402

try:  # the numbers below are also read by puls_paint.py, outside Blender
    import bmesh
    import bpy
    from blender_kit import box, cylinder, load_image, mesh_data, new_object, prism, smooth_by_angle, textured  # noqa: E402
    import w3d  # noqa: E402
except ImportError:
    bpy = None

NAME = "EUPULS"
TEXTURE, DAMAGED_TEXTURE, TREAD_TEXTURE = "eupuls.tga", "eupuls_d.tga", "eupuls_tread.tga"
TREAD_MAPPER = "UPerSec=0.0\nVPerSec=0.0\nUScale=1.0\nVScale=1.0"
TREAD_REPEAT = 4.0  # track length per tread texture

# Shapes, in game units.
TRACK_Y = (4.8, 8.0)
TRACK_PROFILE = [(-10.6, 0.15), (10.4, 0.15), (13.0, 1.9), (12.3, 3.5), (-12.3, 3.5), (-13.1, 1.9)]
TRACK_BODY = [(-10.4, 0.55), (10.2, 0.55), (12.5, 1.9), (11.9, 3.25), (-11.9, 3.25), (-12.6, 1.9)]
WHEELS = [(x, 1.45, 1.2) for x in (-8.6, -5.2, -1.8, 1.6, 5.0, 8.4)] + [(11.7, 2.2, 1.05), (-11.8, 2.2, 1.05)]
CAB_X = (6.4, 13.9)
CAB_PROFILE = [(6.4, 3.6), (13.4, 3.6), (13.9, 5.9), (12.6, 9.2), (6.4, 9.2)]
CAB_HALF_WIDTH = 7.9
TURRET_AT = (-4.0, 0.0, 4.2)
TURRETEL_AT = (-6.8, 0.0, 2.2)      # in the turret's space
POD_LENGTH = 13.0
POD_Y = [(-5.0, -0.3), (0.3, 5.0)]
POD_Z0, POD_Z1 = -0.4, 2.9
LAUNCH = (POD_LENGTH + 0.4, 2.65, 1.25)  # WEAPONA01, in the cradle's space

LAYOUT = Layout([
    ("hull", (-13.3, 13.3, -8.2, 8.2, 0.9, 5.7), 18.0),
    ("cab", (6.3, 14.0, -8.0, 8.0, 3.5, 9.9), 18.0),
    ("track", (-13.2, 13.1, 4.7, 8.1, 0.1, 3.6), 14.0),
    ("turret", (-8.2, 3.2, -5.8, 5.8, 0.0, 3.4), 14.0),
    ("pods", (-0.6, 13.1, -5.1, 5.1, -0.5, 3.0), 18.0),
    ("rocket", (13.0, 13.3, -5.1, 5.1, -0.5, 3.0), 12.0),
], size=1024)


# --- shared shapes ---------------------------------------------------------------------------------

def prism_y(bm, profile, y0, y1):
    """A side profile (x, z) pushed out between y0 and y1, closed."""
    a = [bm.verts.new((x, y0, z)) for x, z in profile]
    b = [bm.verts.new((x, y1, z)) for x, z in profile]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[j], a[i], b[i], b[j]))


def fix_normals(bm):
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)


def tilted_box(bm, a, b, pitch_deg, about):
    """A box between two corners, turned by pitch degrees about the Y axis through `about`."""
    from mathutils import Matrix, Vector
    ret = bmesh.ops.create_cube(bm, size=1.0)
    lo = [min(p, q) for p, q in zip(a, b)]
    hi = [max(p, q) for p, q in zip(a, b)]
    m = (Matrix.Translation(about) @ Matrix.Rotation(math.radians(-pitch_deg), 4, "Y") @ Matrix.Translation(-Vector(about))
         @ Matrix.Translation([(p + q) / 2 for p, q in zip(lo, hi)]) @ Matrix.Diagonal((*[q - p for p, q in zip(lo, hi)], 1.0)))
    bmesh.ops.transform(bm, matrix=m, verts=ret["verts"])


def track_body(bm, side, profile=TRACK_BODY, wheels=WHEELS, track_y=TRACK_Y, segments=10):
    """The inside of one track (closed, for the shadow) with its road wheels on the outside."""
    y0, y1 = track_y
    inner, outer = y0 + 0.2, y1 - 0.4
    if side > 0:
        prism_y(bm, profile, inner, outer)
    else:
        prism_y(bm, profile, -outer, -inner)
    for x, z, r in wheels:
        cylinder(bm, (x, side * (y1 - 0.3), z), r, 0.6, axis="Y", segments=segments)


def tread_band(name, side, profile=TRACK_PROFILE, track_y=TRACK_Y):
    """The track links: a band round the profile, facing out, its texture running along it (u)."""
    bm = bmesh.new()
    y0, y1 = (track_y if side > 0 else (-track_y[1], -track_y[0]))
    cx = sum(p[0] for p in profile) / len(profile)
    cz = sum(p[1] for p in profile) / len(profile)
    n = len(profile)
    us, s = [0.0], 0.0
    for i in range(n):
        (ax, az), (bx, bz) = profile[i], profile[(i + 1) % n]
        s += math.hypot(bx - ax, bz - az)
        us.append(s)
    faces = []
    for i in range(n):
        (ax, az), (bx, bz) = profile[i], profile[(i + 1) % n]
        quad = [bm.verts.new((ax, y0, az)), bm.verts.new((bx, y0, bz)), bm.verts.new((bx, y1, bz)), bm.verts.new((ax, y1, az))]
        f = bm.faces.new(quad)
        f.normal_update()
        mid = ((ax + bx) / 2 - cx, (az + bz) / 2 - cz)
        if f.normal.x * mid[0] + f.normal.z * mid[1] < 0:
            f.normal_flip()
        faces.append((f, i))
    uv_layer = bm.loops.layers.uv.new("UVMap")
    for f, i in faces:
        for loop in f.loops:
            co = loop.vert.co
            # Which end of the segment this corner is at.
            (ax, az) = profile[i]
            at_start = abs(co.x - ax) < 1e-5 and abs(co.z - az) < 1e-5
            # Running backwards along the bottom: W3DTankDraw lowers the offset as the vehicle drives on,
            # which then carries the top run forwards, as a track moves.
            u = -(us[i] if at_start else us[i + 1]) / TREAD_REPEAT
            v = (co.y - y0) / (y1 - y0)
            loop[uv_layer].uv = (u, v)
    return new_object(name, bm)


def flat_panel(name, corners, location=(0, 0, 0)):
    """A flat quad (house colour), facing the way the corners turn."""
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    return new_object(name, bm, location)


# --- texture steps ---------------------------------------------------------------------------------

def unwrap(obj, part, layout):
    """UVs like the game's vehicles: every face projected straight onto its panel of the part."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = layout.uv(part, grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def write_layout(parts, layout, path):
    """The faces as they lie on the texture, and which edges are seams, for the painter."""
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
            faces.append(dict(part=part, group=grp, px=[layout.pixel(part, grp, tuple(me.vertices[v].co)) for v in vs],
                              sharp=sharp))
    with open(path, "w") as f:
        json.dump(dict(layout=layout.spec(), faces=faces), f)


def bake_occlusion(objects, path, size=512):
    import boxer
    boxer.bake_occlusion(objects, path, size)


def run_painter(script, layout_path, occlusion):
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, script), layout_path, TEX_DIR, occlusion], check=True)


def house_material():
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    colour.diffuse_color = (0.08, 0.2, 0.75, 1)
    return colour


def finish(name, painted, painter, stripes=(), layout=None):
    """UVs, the occlusion bake, the paint, and textures applied in Blender. painted: [(obj, part)]."""
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(TEX_DIR, exist_ok=True)
    layout = layout or LAYOUT
    for obj, part in painted:
        smooth_by_angle(obj)
        unwrap(obj, part, layout)
    for obj in stripes:
        obj.data.uv_layers.new(name="UVMap")
    w3d.write_house_colour(TEX_DIR)
    layout_path = os.path.join(BUILD, name + "_layout.json")
    write_layout(painted, layout, layout_path)
    occlusion = os.path.join(BUILD, name + "_ao.png")
    bake_occlusion([o for o, _ in painted], occlusion, layout.size)
    run_painter(painter, layout_path, occlusion)


# --- the PULS --------------------------------------------------------------------------------------

def hull():
    bm = bmesh.new()
    prism(bm, [(-12.6, 1.0), (11.0, 1.0), (13.2, 3.0), (13.2, 3.8), (-12.6, 3.8)], 4.8)
    box(bm, (-13.2, -4.8, 3.6), (6.6, 4.8, 4.2))                    # deck between the tracks, which run open
    box(bm, (3.0, -4.8, 4.2), (6.4, 4.8, 5.6))                     # equipment bay behind the cab
    box(bm, (-13.0, -3.6, 4.2), (-8.6, 3.6, 4.6))                  # engine grille plate
    for side in (1, -1):
        box(bm, (-12.6, side * 2.6, 4.6), (-8.4, side * 4.6, 5.5))  # stowage bins at the back
        box(bm, (-13.5, side * 6.6, 3.2), (-13.2, side * 7.6, 4.0))  # mudflap brackets
        box(bm, (11.0, side * 4.8, 3.3), (13.4, side * 8.1, 3.6))   # front mudguards, under the cab
    box(bm, (-13.4, -1.6, 2.2), (-12.6, 1.6, 2.7))                  # tow bar
    return new_object("CHASSIS", bm)


def cab():
    bm = bmesh.new()
    prism(bm, CAB_PROFILE, CAB_HALF_WIDTH, taper_from=7.5, taper=0.93)
    sharp = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(25)]
    bmesh.ops.bevel(bm, geom=sharp, offset=0.2, segments=1, affect="EDGES", profile=0.5)
    for y in (3.5, -3.5):
        cylinder(bm, (8.6, y, 9.3), 1.0, 0.2, segments=12)          # roof hatches
    box(bm, (13.9, -7.4, 3.3), (14.4, 7.4, 3.9))                    # bumper
    for side in (1, -1):
        box(bm, (12.0, side * 7.9, 7.4), (12.5, side * 8.6, 8.4))   # mirrors
    box(bm, (10.2, -1.0, 9.2), (11.2, 1.0, 9.8))                    # roof sensor
    cylinder(bm, (7.0, -6.6, 11.0), 0.07, 3.6, segments=6)          # antenna
    return new_object("CAB", bm)


def tracks():
    bm = bmesh.new()
    for side in (1, -1):
        track_body(bm, side)
    return new_object("TRACKS", bm)


def turret():
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.25), 4.3, 0.5, segments=20)               # turntable
    box(bm, (-7.6, -4.4, 0.5), (2.6, 4.4, 1.5))                     # base frame
    for side in (1, -1):
        box(bm, (-8.0, side * 5.15, 0.4), (-5.6, side * 5.75, 3.2))  # trunnion arms
        box(bm, (-1.0, side * 4.4, 0.5), (1.6, side * 5.4, 1.3))    # hydraulic boxes
    box(bm, (1.0, -2.0, 1.5), (2.6, 2.0, 2.0))                      # travel lock
    return new_object("TURRET", bm, TURRET_AT)


def pods():
    bm = bmesh.new()
    for y0, y1 in POD_Y:
        box(bm, (0.0, y0, POD_Z0), (POD_LENGTH, y1, POD_Z1))
        box(bm, (0.4, y0 + 0.4, POD_Z1), (POD_LENGTH - 0.4, y1 - 0.4, POD_Z1 + 0.12))  # lid
    box(bm, (0.4, -0.3, -0.4), (12.6, 0.3, 0.2))                    # cradle between the pods
    cylinder(bm, (0.3, 0, 0.1), 0.45, 11.4, axis="Y", segments=10)  # pivot shaft
    fix_normals(bm)
    obj = new_object("PODS", bm)
    obj.location = [TURRET_AT[i] + TURRETEL_AT[i] for i in range(3)]
    return obj


def rockets():
    """The rockets' caps filling the pod fronts (the MISSILE sub-object the game hides while reloading)."""
    bm = bmesh.new()
    for y0, y1 in POD_Y:
        box(bm, (POD_LENGTH, y0 + 0.15, POD_Z0 + 0.15), (POD_LENGTH + 0.25, y1 - 0.15, POD_Z1 - 0.15))
    obj = new_object("MISSILE", bm)
    obj.location = [TURRET_AT[i] + TURRETEL_AT[i] for i in range(3)]
    return obj


def build():
    parts = dict(chassis=hull(), cab=cab(), tracks=tracks(), turret=turret(), pods=pods(), missile=rockets())
    parts["treads"] = [tread_band("TREADSL", 1), tread_band("TREADSR", -1)]
    el = [TURRET_AT[i] + TURRETEL_AT[i] for i in range(3)]
    stripes = [
        flat_panel("HOUSECOLOR01", [(2.0, 5.02, 0.4), (6.5, 5.02, 0.4), (6.5, 5.02, 2.3), (2.0, 5.02, 2.3)][::-1], el),
        flat_panel("HOUSECOLOR02", [(2.0, -5.02, 0.4), (6.5, -5.02, 0.4), (6.5, -5.02, 2.3), (2.0, -5.02, 2.3)], el),
        flat_panel("HOUSECOLOR03", [(6.9, 7.93, 4.3), (9.6, 7.93, 4.3), (9.6, 7.93, 5.3), (6.9, 7.93, 5.3)][::-1]),
        flat_panel("HOUSECOLOR04", [(6.9, -7.93, 4.3), (9.6, -7.93, 4.3), (9.6, -7.93, 5.3), (6.9, -7.93, 5.3)]),
    ]
    parts["stripes"] = stripes
    painted = [(parts["chassis"], "hull"), (parts["cab"], "cab"), (parts["tracks"], "track"), (parts["turret"], "turret"),
               (parts["pods"], "pods"), (parts["missile"], "rocket")]
    finish(NAME, painted, "puls_paint.py", stripes=stripes)
    image = load_image(os.path.join(TEX_DIR, TEXTURE))
    for obj, _ in painted:
        textured(obj, image)
    tread = load_image(os.path.join(TEX_DIR, TREAD_TEXTURE))
    for obj in parts["treads"]:
        textured(obj, tread)
    colour = house_material()
    for obj in stripes:
        obj.data.materials.append(colour)
    return parts


def export(parts, name, texture):
    model = w3d.Model(name)
    turret_bone = model.bone("TURRET", w3d.CHASSIS, TURRET_AT)
    el = model.bone("TURRETEL", turret_bone, TURRETEL_AT)
    missile = model.bone("MISSILE", el, (POD_LENGTH, 0.0, 1.2))
    model.bone("WEAPONA01", el, LAUNCH)
    model.bone("SMOKE01", w3d.CHASSIS, (-10.0, 0.0, 4.8))
    model.bone("SMOKE02", w3d.CHASSIS, (4.6, -3.0, 5.8))
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=texture)
    model.mesh("CAB", w3d.CHASSIS, **mesh_data(parts["cab"]), texture=texture)
    model.mesh("TRACKS", w3d.CHASSIS, **mesh_data(parts["tracks"]), texture=texture)
    for obj in parts["treads"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=TREAD_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER, mapper_args=TREAD_MAPPER)
    model.mesh("TURRET", turret_bone, **mesh_data(parts["turret"]), texture=texture)
    model.mesh("PODS", el, **mesh_data(parts["pods"]), texture=texture)
    # The caps' mesh is in the cradle's space: move it into the MISSILE bone's.
    data = mesh_data(parts["missile"])
    data["verts"] = [(x - POD_LENGTH, y, z - 1.2) for x, y, z in data["verts"]]
    model.mesh("MISSILE", missile, **data, texture=texture)
    for obj in parts["stripes"]:
        bone = el if obj.name in ("HOUSECOLOR01", "HOUSECOLOR02") else w3d.CHASSIS
        model.mesh(obj.name, bone, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER)
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def render_previews(prefix):
    import boxer
    boxer.render_previews(prefix)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = build()
    export(parts, NAME, TEXTURE)
    export(parts, NAME + "_D", DAMAGED_TEXTURE)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    render_previews(os.path.join(BUILD, NAME))


if __name__ == "__main__":
    main()

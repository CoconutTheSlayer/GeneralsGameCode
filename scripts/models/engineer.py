"""The European Engineer Vehicle, an armoured engineering vehicle on a tank hull in the manner of the Dachs and
the Kodiak: a crew cab, a dozer blade at the front and a long telescopic excavator arm on a slewing base,
stowed backwards over the engine deck. Modelled in Blender from simple shapes and written as a W3D model for
the game, like the Boxer (boxer.py). It also holds what the European support vehicles share (ambulance.py and
recon_drone.py import it): shapes, scrolling tracks, wheels, panel UVs, baking, painting and writing.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/engineer.py

Writes resources/macos/GameData/Art/W3D/EUDOZ.w3d, EUDOZ_D.w3d (really damaged), EUDOZ_W.w3d and EUDOZ_WD.w3d
(at work: the arm swung forward and digging, the blade lowered; shown while it builds, repairs or clears
mines), Art/TexturesHD/eudoz.tga, eudoz_d.tga and eudoz_tread.tga, and build/models/EUDOZ.blend with previews.

The game's axes: +X forward, +Z up, +Y to the left, in world units. Bones:
    CHASSIS                  hull, cab, running gear
    TREADSL01, TREADSR01     the tracks, scrolled by W3DTankDraw (meshes named TREADS*)
    BLADE                    the dozer blade
    ARM                      the excavator arm's slewing base (turned half round at work)
    EXHAUSTFX01              engine smoke
    DIRTFX01, DIRTFX02       dirt falling from the bucket and the blade while digging
    SMOKE01..04              smoke of the really damaged vehicle
    HOUSECOLOR01..04         stripes in the player's colour (skirts, boom)
"""
import json
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
TEXTURES = os.path.join(DATA, "Art", "TexturesHD")
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
from blender_kit import box, cylinder, load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
from engineer_paint import Layout, group  # noqa: E402
import w3d  # noqa: E402

# Scrolling treads: W3DTankDraw moves the texture of meshes named TREADS* with this mapper.
TREAD_MAPPER = "UPerSec=0.0\r\nVPerSec=0.0\r\nUScale=1.0\r\nVScale=1.0"


# =====================================================================================================
# Shared by the European support vehicles
# =====================================================================================================

def prism_xz(bm, profile, y0, y1):
    """A side profile (x, z) pushed out from y0 to y1."""
    a = [bm.verts.new((x, y0, z)) for x, z in profile]
    b = [bm.verts.new((x, y1, z)) for x, z in profile]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))


def prism_yz(bm, profile, x0, x1):
    """A cross-section (y, z) pushed out from x0 to x1."""
    a = [bm.verts.new((x0, y, z)) for y, z in profile]
    b = [bm.verts.new((x1, y, z)) for y, z in profile]
    bm.faces.new(a)
    bm.faces.new(list(reversed(b)))
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], b[i], b[j], a[j]))


def beam(bm, a, b, half_y, half_z):
    """A box from point a to point b (both at the same y), its cross-section 2 half_y by 2 half_z."""
    a, b = Vector(a), Vector(b)
    d = b - a
    length = d.length
    angle = math.atan2(-d.z, d.x)
    m = (Matrix.Translation((a + b) / 2) @ Matrix.Rotation(angle, 4, "Y")
         @ Matrix.Diagonal((length, 2 * half_y, 2 * half_z, 1.0)))
    bmesh.ops.create_cube(bm, size=1.0, matrix=m)


def tube(bm, a, b, radius, segments=8):
    """A cylinder from point a to point b."""
    a, b = Vector(a), Vector(b)
    d = b - a
    rot = d.to_track_quat("Z", "Y").to_matrix().to_4x4()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=d.length,
                          matrix=Matrix.Translation((a + b) / 2) @ rot)


def bevel_sharp(bm, offset=0.18, degrees=25):
    """Chamfers the sharp edges of the shapes made so far, so they catch the light."""
    sharp = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(degrees)]
    bmesh.ops.bevel(bm, geom=sharp, offset=offset, segments=1, affect="EDGES", profile=0.5)


def finish(name, bm, location=(0, 0, 0)):
    """The shapes as an object, every shell closed and facing out."""
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object(name, bm, location)


def stadium(rear, front, radius, steps=6):
    """The outline (x, z) of a track running round two wheels of the same radius, from the bottom at the back,
    counter-clockwise as seen from the left."""
    pts = []
    for k in range(steps + 1):  # round the front wheel, bottom to top
        a = -math.pi / 2 + math.pi * k / steps
        pts.append((front[0] + math.cos(a) * radius, front[1] + math.sin(a) * radius))
    for k in range(steps + 1):  # round the back wheel, top to bottom
        a = math.pi / 2 + math.pi * k / steps
        pts.append((rear[0] + math.cos(a) * radius, rear[1] + math.sin(a) * radius))
    return pts


def track(name, outline, y0, y1, thickness, link=1.4, links_per_tile=4):
    """A closed track belt round an outline (x, z), across y0..y1, with UVs for a scrolling tread texture:
    u runs along the track (a whole number of tiles round it), v across its outer face (0..0.7), inside
    (0.7..0.8) and sides (0.8..1)."""
    n = len(outline)
    # The inner outline: each point moved inwards along its corner's bisector.
    cx = sum(p[0] for p in outline) / n
    cz = sum(p[1] for p in outline) / n
    inner = []
    for i in range(n):
        p, q, r = Vector(outline[i - 1]), Vector(outline[i]), Vector(outline[(i + 1) % n])
        n1 = Vector((-(q - p).y, (q - p).x)).normalized() if (q - p).length > 1e-6 else Vector((0, 0))
        n2 = Vector((-(r - q).y, (r - q).x)).normalized() if (r - q).length > 1e-6 else Vector((0, 0))
        nb = (n1 + n2).normalized()
        if nb.dot(Vector((cx, cz)) - q) < 0:
            nb = -nb
        inner.append(q + nb * thickness / max(0.5, nb.dot(n1) if n1.length else 1.0))
    arc = [0.0]
    for i in range(n):
        arc.append(arc[-1] + (Vector(outline[(i + 1) % n]) - Vector(outline[i])).length)
    tiles = max(1, round(arc[-1] / (link * links_per_tile)))
    # u grows backwards round the outline: W3DTankDraw lowers the offset to drive forwards, so the top run moves
    # forwards and the ground run backwards.
    us = [-a / arc[-1] * tiles for a in arc]
    bm = bmesh.new()
    uv = bm.loops.layers.uv.new("UVMap")
    O0 = [bm.verts.new((x, y0, z)) for x, z in outline]
    O1 = [bm.verts.new((x, y1, z)) for x, z in outline]
    I0 = [bm.verts.new((p.x, y0, p.y)) for p in inner]
    I1 = [bm.verts.new((p.x, y1, p.y)) for p in inner]
    for i in range(n):
        j = (i + 1) % n
        u0, u1 = us[i], us[i + 1]
        for verts, vs in (((O0[i], O0[j], O1[j], O1[i]), ((u0, 0.0), (u1, 0.0), (u1, 0.7), (u0, 0.7))),
                          ((I0[i], I1[i], I1[j], I0[j]), ((u0, 0.7), (u0, 0.8), (u1, 0.8), (u1, 0.7))),
                          ((O0[i], I0[i], I0[j], O0[j]), ((u0, 0.8), (u0, 1.0), (u1, 1.0), (u1, 0.8))),
                          ((O1[i], O1[j], I1[j], I1[i]), ((u0, 0.8), (u1, 0.8), (u1, 1.0), (u0, 1.0)))):
            f = bm.faces.new(verts)
            for loop, t in zip(f.loops, vs):
                loop[uv].uv = t
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object(name, bm)


TYRE_PROFILE = [(0.0, -0.55), (2.15, -0.75), (2.5, -0.4), (2.5, 0.4), (2.15, 0.75), (1.5, 0.72), (1.35, 0.5),
                (0.5, 0.6), (0.0, 0.6)]  # the Boxer's, for a radius of 2.5 and a width of 1.5


def wheel(name, location, radius, width, steps=14):
    """A tyre with its rim and hub, turning about Y, its outside away from the hull."""
    bm = bmesh.new()
    outward = 1 if location[1] > 0 else -1
    verts = [bm.verts.new((r * radius / 2.5, y * width / 1.5 * outward, 0)) for r, y in TYRE_PROFILE]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 1, 0), angle=2 * math.pi, steps=steps,
                   use_merge=True)
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(name, bm, location)
    wheel_uvs(obj, radius, width)
    smooth_by_angle(obj, 50)
    return obj


def wheel_uvs(obj, radius, width):
    """The Boxer's tyre texture (boxer_paint.paint_tire): hub on the sides (upper half), tread round (lower)."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        side = abs(poly.normal.y) > 0.7
        corners = []
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if side:
                corners.append((li, 0.5 + co.x / (radius * 2.1), 0.75 + co.z / (radius * 4.2)))
            else:
                angle = (math.atan2(co.z, co.x) / (2 * math.pi)) % 1.0
                corners.append((li, angle, 0.25 + co.y / width * 0.45))
        if not side:
            us = [u for _, u, _ in corners]
            if max(us) - min(us) > 0.5:
                corners = [(li, u + 1.0 if u < 0.5 else u, v) for li, u, v in corners]
            corners = [(li, u * 3, v) for li, u, v in corners]
        for li, u, v in corners:
            uv.data[li].uv = (u, v)


def flat(name, corners, location=(0, 0, 0)):
    """A flat panel (house colour, decals) through four corners, facing the way they turn (right hand)."""
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    obj = new_object(name, bm, location)
    obj.data.uv_layers.new(name="UVMap")
    return obj


def side_panels(name1, name2, x0, x1, z0, z1, y):
    """A pair of flat panels on the left (+y) and right (-y) sides, facing out."""
    left = flat(name1, [(x0, y, z0), (x0, y, z1), (x1, y, z1), (x1, y, z0)][::-1])
    right = flat(name2, [(x0, -y, z0), (x0, -y, z1), (x1, -y, z1), (x1, -y, z0)])
    return [left, right]


def muzzle_flash(name, location, length=2.2, radius=0.7):
    """Two crossed quads along +x for an additive flash."""
    bm = bmesh.new()
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * radius, math.sin(a) * radius
        bm.faces.new([bm.verts.new(v) for v in ((0, -c, -s), (length, -c, -s), (length, c, s), (0, c, s))])
    obj = new_object(name, bm, location)
    obj.data.uv_layers.new(name="UVMap")
    return obj


def panel_unwrap(obj, layout, part):
    """UVs like the game's vehicles: every face projected straight onto its part's panel."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = layout.uv(part, grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def layout_faces(objects_parts, layout):
    """The faces as they lie on the texture, and which of their edges are seams, for the painter."""
    faces = []
    for obj, part in objects_parts:
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
    return faces


def bake_occlusion(objects, path, size):
    """Bakes the ambient occlusion of the panel-unwrapped objects on their texture."""
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


def bake_and_paint(name, objects_parts, layout, paint_script, bake_objects=None):
    """Writes the layout, bakes the occlusion and runs the painter (Python 3 with Pillow) on them.
    bake_objects: the objects to bake instead (posed copies of the parts, with the same UVs)."""
    os.makedirs(BUILD, exist_ok=True)
    os.makedirs(TEXTURES, exist_ok=True)
    path = os.path.join(BUILD, name + "_layout.json")
    with open(path, "w") as f:
        json.dump(dict(layout=layout.to_json(), faces=layout_faces(objects_parts, layout)), f)
    occlusion = os.path.join(BUILD, name + "_ao.png")
    bake_occlusion(bake_objects or [o for o, _ in objects_parts], occlusion, layout.size)
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, paint_script), path, TEXTURES, occlusion], check=True)


def join(objects, name):
    """Joins objects (with their UVs) into the first one, named name."""
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.join()
    objects[0].name = name
    objects[0].data.name = name
    return objects[0]


def posed_copy(obj, matrix, name):
    """A copy of an object with its mesh moved by a matrix (UVs kept): a part in another pose."""
    copy = obj.copy()
    copy.data = obj.data.copy()
    copy.data.transform(matrix)
    copy.name = name
    bpy.context.scene.collection.objects.link(copy)
    return copy


def team_colour(objects):
    """In Blender, a team colour for the previews; the game paints HOUSECOLOR meshes in the player's colour."""
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in objects:
        obj.data.materials.clear()
        obj.data.materials.append(colour)


def write_model(name, pieces, bones):
    """pieces: (mesh name, bone name, object, texture, kind) with kind "solid", "tread", "house" or "flash";
    bones: [(name, parent name, location, yaw)] in order. Prints and returns the triangle count."""
    model = w3d.Model(name)
    index = {"CHASSIS": w3d.CHASSIS}
    for bone, parent, at, yaw in bones:
        index[bone] = model.bone(bone, index[parent], tuple(at), yaw)
    for mesh, bone, obj, texture, kind in pieces:
        data = mesh_data(obj)
        if kind == "tread":
            model.mesh(mesh, index[bone], **data, texture=texture, mapper_args=TREAD_MAPPER)
        elif kind == "house":
            model.mesh(mesh, index[bone], **data, texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                       shader=w3d.ALPHA_TEST_SHADER)
        elif kind == "flash":
            model.mesh(mesh, index[bone], **data, texture=texture, shadow=False, shader=w3d.ADDITIVE_SHADER)
        else:
            model.mesh(mesh, index[bone], **data, texture=texture)
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    model.save(out)
    tris = sum(len(m[5]) for m in model.meshes if m[8] is not w3d.ADDITIVE_SHADER)
    print(f"{name}: {len(model.meshes)} meshes, {tris} triangles -> {out}")
    return tris


def render_previews(prefix, distance=55.0, target=(0, 0, 4), angles=(35, 145, 250), height=0.62):
    """Renders the open scene from around (for looking at, not for the game)."""
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 800, 600
    if scene.world is None:
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
    cam = scene.camera
    for i, angle in enumerate(angles):
        a = math.radians(angle)
        cam.location = Vector((math.cos(a) * distance, math.sin(a) * distance, distance * height))
        cam.rotation_euler = (Vector(target) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{i}.png"
        bpy.ops.render.render(write_still=True)


def apply_textures(pieces):
    """Shows the painted textures in Blender."""
    images = {}
    for _, _, obj, texture, kind in pieces:
        if kind in ("solid", "tread") and texture:
            path = os.path.join(TEXTURES, texture)
            if path not in images:
                images[path] = load_image(path)
            textured(obj, images[path])


# =====================================================================================================
# The Engineer Vehicle
# =====================================================================================================

NAME = "EUDOZ"
HULL_TEXTURE, DAMAGED_TEXTURE, TREAD_TEXTURE = "eudoz.tga", "eudoz_d.tga", "eudoz_tread.tga"

# Tracks: round a rear sprocket and a front idler, road wheels between.
TRACK_REAR, TRACK_FRONT, TRACK_RADIUS = (-12.0, 2.15), (10.9, 2.15), 2.15
TRACK_Y0, TRACK_Y1, TRACK_THICKNESS = 5.75, 8.55, 0.45
ROAD_WHEELS_X = (-9.4, -5.9, -2.4, 1.1, 4.6, 8.1)
ROAD_WHEEL_Z, ROAD_WHEEL_RADIUS = 1.75, 1.3
DECK_Z = 7.4

BLADE_AT = (13.0, 0.0)          # x, y of the blade's bone; its height differs travelling and at work
BLADE_Z = {"travel": 1.2, "work": -0.15}
ARM_AT = (6.6, -4.3, DECK_Z)    # the slewing base, on the front right of the deck
BOOM_PIVOT = Vector((-0.6, 0.0, 2.4))
BOOM_LENGTH = 16.8
STICK_PIVOT = BOOM_PIVOT + Vector((-BOOM_LENGTH, 0.0, 0.0))
# (boom, stick) angles in degrees about y (positive lifts the boom's far end and swings the stick back), and the
# base's yaw.
POSES = {"travel": (-1.0, 58.0, 0.0), "work": (-22.0, -18.0, 180.0)}

PARTS = {
    "hull": (-14.4, 14.2, -8.7, 8.7, 0.0, 11.4),
    "running": (-12.6, 11.6, -8.6, 8.6, 0.3, 4.2),
    "blade": (-3.4, 2.8, -9.3, 9.3, 0.0, 4.8),
    "arm": (-18.8, 2.2, -2.1, 2.1, -3.7, 4.1),
}
WEIGHTS = {"running": 0.55, "blade": 0.9, "arm": 1.1}


def hull():
    bm = bmesh.new()
    # Upper hull over the tracks, its glacis sloping to the front.
    prism_xz(bm, [(-14.2, 4.5), (11.2, 4.5), (14.0, 5.6), (11.0, DECK_Z), (-13.8, DECK_Z), (-14.2, 6.8)], -8.6, 8.6)
    # The crew cab on the front left, its front sloping back.
    prism_xz(bm, [(2.4, DECK_Z), (10.8, DECK_Z), (9.4, 10.9), (2.6, 11.1)], 0.4, 7.9)
    bevel_sharp(bm)
    # Lower hull between the tracks.
    prism_xz(bm, [(-13.4, 1.3), (10.6, 1.3), (13.4, 4.5), (-13.4, 4.5)], -5.6, 5.6)
    # Side skirts over the upper run of the tracks.
    for side in (1, -1):
        y0, y1 = sorted((side * 8.6, side * 8.95))
        prism_xz(bm, [(-13.2, 2.5), (10.2, 2.5), (12.6, 4.9), (-13.2, 4.9)], y0, y1)
    # Engine deck at the back, raised, the grilles painted on; exhaust on the left; the rest for the boom.
    box(bm, (-13.6, -7.9, DECK_Z), (-6.8, 7.9, DECK_Z + 0.35))
    box(bm, (-12.9, 6.4, DECK_Z + 0.35), (-11.1, 7.8, DECK_Z + 1.2))
    cylinder(bm, (-12.0, 7.1, DECK_Z + 1.5), 0.35, 0.7, segments=8)
    for y in (-3.5, -5.1):
        beam(bm, (-9.0, y, DECK_Z + 0.35), (-9.4, y, 8.95), 0.18, 0.18)
    box(bm, (-9.8, -5.4, 8.75), (-8.6, -3.2, 9.0))
    # Stowage bins on the right of the deck, a spare track link rack on the glacis.
    box(bm, (-5.8, -8.4, DECK_Z), (1.6, -6.6, DECK_Z + 1.0))
    box(bm, (11.4, 1.0, 6.4), (12.6, 7.6, 6.8))
    # Headlights with guards, tow eyes, mirrors on the cab.
    for side in (1, -1):
        box(bm, (11.0, side * 6.6 - 0.6, 6.9), (11.8, side * 6.6 + 0.6, 7.5))
        box(bm, (13.0, side * 3.8 - 0.3, 3.8), (13.7, side * 3.8 + 0.3, 4.4))
        box(bm, (-14.6, side * 4.0 - 0.35, 4.6), (-14.0, side * 4.0 + 0.35, 5.3))
    box(bm, (10.0, 7.9, 9.6), (10.5, 8.5, 10.5))
    # Cab roof: hatch rim, periscope blocks, an antenna, a rotating beacon.
    cylinder(bm, (6.0, 4.6, 11.2), 1.1, 0.2, segments=14)
    cylinder(bm, (3.4, 7.2, 12.9), 0.07, 3.6, segments=6)
    cylinder(bm, (3.6, 1.2, 11.4), 0.3, 0.45, segments=8)
    # Side handrails on the cab.
    for x in (3.4, 8.6):
        beam(bm, (x, 7.9, 8.4), (x, 7.9, 10.2), 0.08, 0.08)
    return finish("hull", bm)


def running_gear():
    """Road wheels, sprocket and idler inside the tracks."""
    bm = bmesh.new()
    for side in (1, -1):
        y = side * (TRACK_Y0 + TRACK_Y1) / 2
        for x in ROAD_WHEELS_X:
            cylinder(bm, (x, y, ROAD_WHEEL_Z), ROAD_WHEEL_RADIUS, 2.3, axis="Y", segments=12)
        for (x, z) in (TRACK_REAR, TRACK_FRONT):
            cylinder(bm, (x, y, z), TRACK_RADIUS - TRACK_THICKNESS - 0.05, 2.3, axis="Y", segments=14)
        for x in (-6.0, 0.0, 6.0):  # return rollers
            cylinder(bm, (x, y, 3.55), 0.35, 1.2, axis="Y", segments=8)
    return finish("running", bm)


def tracks():
    outline = stadium(TRACK_REAR, TRACK_FRONT, TRACK_RADIUS)
    left = track("TREADSL01", outline, TRACK_Y0, TRACK_Y1, TRACK_THICKNESS)
    right = track("TREADSR01", outline, -TRACK_Y1, -TRACK_Y0, TRACK_THICKNESS)
    return [left, right]


def blade():
    """The dozer blade in its bone's space: a curved mouldboard on two push arms."""
    bm = bmesh.new()
    prism_xz(bm, [(0.0, 0.4), (0.5, 0.0), (2.6, 0.0), (2.15, 0.6), (1.75, 1.5), (1.6, 2.7), (1.75, 3.7), (2.2, 4.4),
                  (1.4, 4.7), (0.4, 4.5), (0.0, 3.6)], -9.2, 9.2)
    bevel_sharp(bm, 0.12, 30)
    for side in (1, -1):
        beam(bm, (-3.2, side * 7.0, 1.7), (0.2, side * 7.0, 1.4), 0.45, 0.45)
        tube(bm, (-1.6, side * 3.6, 4.3), (0.2, side * 3.6, 3.4), 0.3)   # lift rams
        box(bm, (-0.3, side * 7.0 - 0.6, 0.9), (0.2, side * 7.0 + 0.6, 2.2))
    return finish("blade", bm)


def arm_parts():
    """The excavator arm in its bone's space, the boom pointing back (-x), the stick hanging straight down:
    the slewing base, the telescopic boom with its ram, and the stick with the bucket."""
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.45), 2.0, 0.9, segments=16)
    prism_xz(bm, [(-1.6, 0.9), (1.7, 0.9), (1.7, 2.1), (0.7, 3.2), (-1.6, 3.2)], -1.3, 1.3)
    tube(bm, (1.2, 1.35, 1.6), (1.2, 1.75, 1.6), 0.5)
    base = finish("ARM", bm)

    bm = bmesh.new()
    p = BOOM_PIVOT
    box(bm, (p.x - 10.0, -0.8, p.z - 0.85), (p.x + 0.6, 0.8, p.z + 0.85))          # outer boom
    box(bm, (p.x - BOOM_LENGTH - 0.4, -0.55, p.z - 0.6), (p.x - 9.6, 0.55, p.z + 0.6))  # telescopic section
    bevel_sharp(bm, 0.14, 30)
    tube(bm, (p.x - 0.4, 0.0, p.z + 1.2), (p.x - 6.4, 0.0, p.z + 1.05), 0.36)     # ram
    tube(bm, (p.x - 6.4, 0.0, p.z + 1.05), (p.x - 9.0, 0.0, p.z + 0.95), 0.18)
    box(bm, (p.x - 9.3, -0.35, p.z + 0.8), (p.x - 8.7, 0.35, p.z + 1.2))
    tube(bm, (p.x, -0.95, p.z), (p.x, 0.95, p.z), 0.42)                           # foot pin
    tube(bm, (p.x - 15.2, 0.0, p.z + 0.6), (p.x - BOOM_LENGTH + 0.3, 0.0, p.z + 0.9), 0.2)  # stick ram
    boom = finish("BOOM", bm)

    bm = bmesh.new()
    s = STICK_PIVOT
    box(bm, (s.x - 0.5, -0.45, s.z - 4.0), (s.x + 0.5, 0.45, s.z + 0.5))
    tube(bm, (s.x, -0.75, s.z), (s.x, 0.75, s.z), 0.4)
    # The bucket, its mouth facing +x (towards the machine in the stowed pose), with teeth.
    prism_xz(bm, [(s.x - 1.4, s.z - 3.6), (s.x + 0.6, s.z - 3.8), (s.x + 1.6, s.z - 5.2), (s.x + 0.8, s.z - 6.0),
                  (s.x - 0.8, s.z - 5.8), (s.x - 1.6, s.z - 4.8)], -1.45, 1.45)
    for k in range(5):
        y = -1.1 + k * 0.55
        box(bm, (s.x + 1.5, y - 0.15, s.z - 5.35), (s.x + 2.1, y + 0.15, s.z - 5.05))
    stick = finish("STICK", bm)
    return base, boom, stick


def pose_matrices(pose):
    """The boom's and the stick's matrices (bone space) for a pose."""
    boom_angle, stick_angle, _ = POSES[pose]
    rb = Matrix.Translation(BOOM_PIVOT) @ Matrix.Rotation(math.radians(boom_angle), 4, "Y") @ Matrix.Translation(-BOOM_PIVOT)
    tip = rb @ STICK_PIVOT
    rs = Matrix.Translation(tip) @ Matrix.Rotation(math.radians(stick_angle), 4, "Y") @ Matrix.Translation(-tip)
    return rb, rs @ rb


def house_colour():
    """Stripes in the player's colour: on the skirts, and along the boom (posed with it)."""
    skirts = side_panels("HOUSECOLOR01", "HOUSECOLOR02", -11.6, -4.6, 3.1, 4.3, 8.97)
    p = BOOM_PIVOT
    boom = side_panels("HOUSECOLOR03", "HOUSECOLOR04", p.x - 8.8, p.x - 3.6, p.z - 0.45, p.z + 0.35, 0.82)
    return skirts, boom


def build():
    layout = Layout(PARTS, 1024, WEIGHTS)
    print("layout scale", round(layout.scale, 2), "pixels per unit")
    body, gear, bl = hull(), running_gear(), blade()
    base, boom, stick = arm_parts()
    solid = [(body, "hull"), (gear, "running"), (bl, "blade"), (base, "arm"), (boom, "arm"), (stick, "arm")]
    for obj, part in solid:
        smooth_by_angle(obj, 35)
        panel_unwrap(obj, layout, part)
    belts = tracks()
    for obj in belts:
        smooth_by_angle(obj, 50)
    skirts, boom_stripes = house_colour()
    # Placed as in the game for the occlusion bake: blade and arm on their bones, the arm stowed.
    bl.location = (BLADE_AT[0], BLADE_AT[1], BLADE_Z["travel"])
    rb, rs = pose_matrices("travel")
    base.location = ARM_AT
    travel_boom = posed_copy(boom, rb, "BOOM_travel")
    travel_stick = posed_copy(stick, rs, "STICK_travel")
    for obj in (travel_boom, travel_stick):
        obj.location = ARM_AT
    boom.hide_render = stick.hide_render = True
    boom.location = stick.location = (0, 0, -60)  # out of the way of the bake
    w3d.write_house_colour(TEXTURES)
    bake_and_paint(NAME, solid, layout, "engineer_paint.py", [body, gear, bl, base, travel_boom, travel_stick])
    chassis = join([body, gear], "CHASSIS")
    return dict(chassis=chassis, belts=belts, blade=bl, base=base, boom=boom, stick=stick, skirts=skirts,
                boom_stripes=boom_stripes, travel=(travel_boom, travel_stick))


def bones(pose):
    """The bones of a pose: (name, parent, location, yaw)."""
    _, _, yaw = POSES[pose]
    rb, rs = pose_matrices(pose)
    bucket = rs @ (STICK_PIVOT + Vector((0.4, 0.0, -5.6)))
    return [
        ("BLADE", "CHASSIS", (BLADE_AT[0], BLADE_AT[1], BLADE_Z[pose]), 0.0),
        ("ARM", "CHASSIS", ARM_AT, yaw),
        ("EXHAUSTFX01", "CHASSIS", (-12.0, 7.1, DECK_Z + 1.9), 0.0),
        ("DIRTFX01", "ARM", tuple(bucket), 0.0),
        ("DIRTFX02", "BLADE", (1.8, 0.0, 3.0), 0.0),
        ("SMOKE01", "CHASSIS", (6.0, 4.0, 11.4), 0.0),
        ("SMOKE02", "CHASSIS", (-10.0, -3.0, 7.9), 0.0),
        ("SMOKE03", "CHASSIS", (-3.0, 5.0, 7.6), 0.0),
        ("SMOKE04", "CHASSIS", (2.0, -6.0, 7.6), 0.0),
    ]


def export(parts, pose, name, hull_texture):
    rb, rs = pose_matrices(pose)
    boom = posed_copy(parts["boom"], rb, f"BOOM_{name}")
    stick = posed_copy(parts["stick"], rs, f"STICK_{name}")
    stripes = [posed_copy(s, rb, f"{s.name}_{name}") for s in parts["boom_stripes"]]
    pieces = [("CHASSIS", "CHASSIS", parts["chassis"], hull_texture, "solid"),
              ("BLADE", "BLADE", parts["blade"], hull_texture, "solid"),
              ("ARM", "ARM", parts["base"], hull_texture, "solid"),
              ("BOOM", "ARM", boom, hull_texture, "solid"),
              ("STICK", "ARM", stick, hull_texture, "solid")]
    pieces += [(b.name, "CHASSIS", b, TREAD_TEXTURE, "tread") for b in parts["belts"]]
    pieces += [(s.name, "CHASSIS", s, None, "house") for s in parts["skirts"]]
    pieces += [(f"HOUSECOLOR0{3 + i}", "ARM", s, None, "house") for i, s in enumerate(stripes)]
    tris = write_model(name, pieces, bones(pose))
    for obj in [boom, stick] + stripes:
        bpy.data.objects.remove(obj)
    return tris


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    for pose, name, damaged in (("travel", NAME, NAME + "_D"), ("work", NAME + "_W", NAME + "_WD")):
        export(parts, pose, name, HULL_TEXTURE)
        export(parts, pose, damaged, DAMAGED_TEXTURE)
    # Previews: stowed, then at work.
    hull_image = load_image(os.path.join(TEXTURES, HULL_TEXTURE))
    tread_image = load_image(os.path.join(TEXTURES, TREAD_TEXTURE))
    for obj in [parts["chassis"], parts["blade"], parts["base"], parts["boom"], parts["stick"]] + list(parts["travel"]):
        textured(obj, hull_image)
    for obj in parts["belts"]:
        textured(obj, tread_image)
    stripes = parts["skirts"]
    rb, _ = pose_matrices("travel")
    boom_stripes = [posed_copy(s, rb, s.name + "_travel") for s in parts["boom_stripes"]]
    for s in boom_stripes:
        s.location = ARM_AT
    for s in parts["boom_stripes"]:
        s.hide_render = True
    team_colour(stripes + boom_stripes)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    render_previews(os.path.join(BUILD, NAME))
    # At work: the base turned half round, the boom down, the blade lowered.
    _, _, yaw = POSES["work"]
    rb, rs = pose_matrices("work")
    turn = Matrix.Translation(ARM_AT) @ Matrix.Rotation(math.radians(yaw), 4, "Z")
    for obj in list(parts["travel"]) + boom_stripes:
        obj.hide_render = True
    for obj, m in ((parts["base"], Matrix.Identity(4)), (parts["boom"], rb), (parts["stick"], rs)):
        obj.hide_render = False
        obj.location = (0, 0, 0)
        obj.matrix_world = turn @ m
    parts["blade"].location = (BLADE_AT[0], BLADE_AT[1], BLADE_Z["work"])
    render_previews(os.path.join(BUILD, NAME + "_W"), angles=(35, 300))


if __name__ == "__main__":
    main()

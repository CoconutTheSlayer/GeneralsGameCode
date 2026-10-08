"""The European Typhoon, a canard delta multirole fighter, modelled in Blender from simple shapes and
written as a W3D model for the game. Also the jet kit the Rafale (rafale.py) and the Tornado (tornado.py)
are built with: lofted fuselages, wings and fins as bevelled slabs, a projected texture layout painted by
typhoon_paint.py, baked ambient occlusion, and the bones the USA jets' draw modules and weapons use.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/typhoon.py

Writes resources/macos/GameData/Art/W3D/EUTYPH.w3d and EUTYPH_D.w3d, Art/TexturesHD/eutyp.tga and
eutyp_d.tga, and build/models/EUTYPH.blend with previews next to it.

The game's axes: +X forward, +Y left, +Z up, in world units (the Typhoon is about 36 long, like the
Raptor it replaces). Bones (as the Raptor's, AVRAPTOR):
    CHASSIS                    the airframe
    WEAPONA01                  where its missiles leave
    ENGINE01/02, BURNERFX01/02 the nozzles, and the afterburner flames (shown with JETAFTERBURNER)
    WINGTIP01/02               contrails
    SMOKE01/02                 damage smoke
    FLARE01..03                countermeasure flares
    HOUSECOLOR01               the player's colour: the fin's top and bands on the wings
"""
import json
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from mathutils import Vector

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
from blender_kit import box, cylinder, load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
from typhoon_paint import Layout  # noqa: E402
import w3d  # noqa: E402


# --- shapes ----------------------------------------------------------------------------------------

def loft(bm, sections, segments=16, cap_front=True, cap_back=True, dy=0.0):
    """A body through cross-sections (x, half width, z bottom, z top, roundness): roundness 2 is an
    ellipse, larger is squarer. A section of zero width is a point (a nose)."""
    rings = []
    for x, hw, zb, zt, p in sections:
        zm, hh = (zb + zt) / 2, (zt - zb) / 2
        if hw <= 0:
            rings.append([bm.verts.new((x, dy, zm))])
            continue
        ring = []
        for k in range(segments):
            a = 2 * math.pi * k / segments
            c, s = math.cos(a), math.sin(a)
            y = hw * math.copysign(abs(c) ** (2 / p), c)
            z = zm + hh * math.copysign(abs(s) ** (2 / p), s)
            ring.append(bm.verts.new((x, dy + y, z)))
        rings.append(ring)
    faces = []
    for r0, r1 in zip(rings, rings[1:]):
        if len(r0) == 1:
            for k in range(segments):
                faces.append(bm.faces.new((r0[0], r1[k], r1[(k + 1) % segments])))
        elif len(r1) == 1:
            for k in range(segments):
                faces.append(bm.faces.new((r0[k], r1[0], r0[(k + 1) % segments])))
        else:
            for k in range(segments):
                faces.append(bm.faces.new((r0[k], r0[(k + 1) % segments], r1[(k + 1) % segments], r1[k])))
    if len(rings[0]) > 1 and cap_front:
        faces.append(bm.faces.new(rings[0]))
    if len(rings[-1]) > 1 and cap_back:
        faces.append(bm.faces.new(list(reversed(rings[-1]))))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return faces


def slab(bm, outline, thickness, edge=0.12, inset=0.8, mid=None, plane="xy", thin_tip=None):
    """A wing, canard or fin: a flat outline (u, v) with bevelled edges, `thickness` thick in the middle and
    `edge` at the rim. plane "xy": a wing (u = x, v = y, thickness along z, mid(x, y) its middle height);
    "xz": a fin (u = x, v = z, thickness along y, centred on y = mid or 0)."""
    cu = sum(p[0] for p in outline) / len(outline)
    cv = sum(p[1] for p in outline) / len(outline)
    inner = [(cu + (u - cu) * inset, cv + (v - cv) * inset) for u, v in outline]

    def place(u, v, off):
        if plane == "xy":
            z = mid(u, v) if mid else 0.0
            return (u, v, z + off)
        y = mid if isinstance(mid, (int, float)) else 0.0
        return (u, y + off, v)

    def ring(points, t):
        top = [bm.verts.new(place(u, v, t / 2)) for u, v in points]
        bottom = [bm.verts.new(place(u, v, -t / 2)) for u, v in points]
        return top, bottom

    ot, ob = ring(outline, edge)
    it, ib = ring(inner, thickness)
    n = len(outline)
    faces = [bm.faces.new(it), bm.faces.new(list(reversed(ib)))]
    for i in range(n):
        j = (i + 1) % n
        faces.append(bm.faces.new((it[i], it[j], ot[j], ot[i])))
        faces.append(bm.faces.new((ib[j], ib[i], ob[i], ob[j])))
        faces.append(bm.faces.new((ot[i], ot[j], ob[j], ob[i])))
    bmesh.ops.recalc_face_normals(bm, faces=faces)
    return inner


def mirrored(points):
    return [(x, -y) for x, y in reversed(points)]


def clip_band(poly, v0, v1, axis=1):
    """The part of a polygon between two values of one coordinate (Sutherland-Hodgman)."""
    def clip(points, keep, cut):
        out = []
        for i in range(len(points)):
            a, b = points[i], points[(i + 1) % len(points)]
            ka, kb = keep(a), keep(b)
            if ka:
                out.append(a)
            if ka != kb:
                t = (cut - a[axis]) / (b[axis] - a[axis])
                out.append(tuple(a[k] + (b[k] - a[k]) * t for k in range(len(a))))
        return out
    lo, hi = min(v0, v1), max(v0, v1)
    poly = clip(poly, lambda p: p[axis] >= lo, lo)
    return clip(poly, lambda p: p[axis] <= hi, hi) if poly else poly


def flat_panel(bm, points3d, double=False):
    verts = [bm.verts.new(p) for p in points3d]
    bm.faces.new(verts)
    if double:
        verts = [bm.verts.new(p) for p in reversed(points3d)]
        bm.faces.new(verts)


def burner(name, location):
    """The afterburner flame: crossed quads along X, both ways round, the flame's root forwards."""
    bm = bmesh.new()
    L, R = 3.92, 1.9
    quads = [((L, R, 0), (-L, R, 0), (-L, -R, 0), (L, -R, 0)), ((L, 0, R), (-L, 0, R), (-L, 0, -R), (L, 0, -R))]
    for q in quads:
        flat_panel(bm, q, double=True)
    obj = new_object(name, bm, location)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            lateral = y if abs(y) > 1e-3 else z
            uv.data[li].uv = ((L - x) / (2 * L), 0.29 + (lateral + R) / (2 * R) * 0.47)
    return obj


# --- texture layout --------------------------------------------------------------------------------

def unwrap(obj, layout, only=None):
    """Each face projected on the island it faces (or all on the island `only`: the stores under the wings,
    which would otherwise leave their outlines on the painted wing and fuselage above them)."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = only or layout.group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = layout.uv(grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def layout_faces(obj, layout):
    me = obj.data
    edge_faces = {}
    for poly in me.polygons:
        for key in poly.edge_keys:
            edge_faces.setdefault(key, []).append(poly)
    faces = []
    for poly in me.polygons:
        grp = layout.group(tuple(poly.normal))
        vs = list(poly.vertices)
        sharp = []
        for i in range(len(vs)):
            key = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
            around = edge_faces.get(key, [])
            sharp.append(len(around) == 2 and around[0].normal.angle(around[1].normal, 0) > math.radians(42)
                         and layout.group(tuple(around[0].normal)) == layout.group(tuple(around[1].normal)) == grp)
        faces.append(dict(group=grp, px=[layout.pixel(grp, tuple(me.vertices[v].co)) for v in vs], sharp=sharp))
    return faces


def bake_occlusion(obj, path, size=512):
    image = bpy.data.images.new("occlusion", size, size)
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
    scene.world = scene.world or bpy.data.worlds.new("w")
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.bake(type="AO")
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()


# --- the whole jet -----------------------------------------------------------------------------------

class Jet:
    """What a jet script describes: its name and texture, the shapes (a function filling a bmesh), the
    house colour panels, the bones, the burner bones and the marks to paint."""
    name = "EUTYPH"
    texture = "eutyp"
    paint_script = "typhoon_paint.py"
    extent = ((-19.5, 21.0), (-13.5, 13.5), (-3.0, 9.6))
    scheme = dict(colours=[(150, 160, 170), (118, 130, 144)], pattern="soft", under=(176, 182, 188))
    belly_blend = 0.2

    def shapes(self, bm):
        raise NotImplementedError

    def stores(self, bm):
        pass

    def house_colour(self, bm):
        pass

    bones = {}
    burners = {}
    marks = []


def build(jet):
    """Makes the jet in an empty scene, paints and exports it."""
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    layout = Layout(*jet.extent)

    bm = bmesh.new()
    jet.shapes(bm)
    chassis = new_object("CHASSIS", bm)
    smooth_by_angle(chassis, 40)
    unwrap(chassis, layout)
    bm = bmesh.new()
    jet.stores(bm)
    stores = new_object("STORES", bm)
    smooth_by_angle(stores, 40)
    unwrap(stores, layout, only="stores")
    bm = bmesh.new()
    jet.house_colour(bm)
    house = new_object("HOUSECOLOR01", bm)
    house.data.uv_layers.new(name="UVMap")
    flames = [burner(name, at) for name, at in jet.burners.items()]

    w3d.write_house_colour(tex_dir)
    occlusion = os.path.join(BUILD, jet.name + "_ao.png")
    bake_occlusion(chassis, occlusion)
    layout_path = os.path.join(BUILD, jet.name + "_layout.json")
    with open(layout_path, "w") as f:
        json.dump(dict(texture=jet.texture, layout=layout.to_dict(), scheme=jet.scheme, belly_blend=jet.belly_blend,
                       faces=layout_faces(chassis, layout), marks=jet.marks), f)
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, jet.paint_script), layout_path, tex_dir, occlusion], check=True)

    for name, texture in ((jet.name, jet.texture + ".tga"), (jet.name + "_D", jet.texture + "_d.tga")):
        model = w3d.Model(name)
        bone_ids = {}
        for bone, at in jet.bones.items():
            bone_ids[bone] = model.bone(bone, w3d.CHASSIS, at)
        for obj in flames:
            bone_ids[obj.name] = model.bone(obj.name, w3d.CHASSIS, tuple(obj.location))
        hc_bone = model.bone("HOUSECOLOR01", w3d.CHASSIS, (0, 0, 0))
        model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(chassis), texture=texture)
        if stores.data.polygons:
            model.mesh("STORES", w3d.CHASSIS, **mesh_data(stores), texture=texture)
        if house.data.polygons:
            model.mesh("HOUSECOLOR01", hc_bone, **mesh_data(house), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                       shader=w3d.ALPHA_TEST_SHADER)
        for obj in flames:
            model.mesh(obj.name, bone_ids[obj.name], **mesh_data(obj), texture="EXTnkMzl01.tga", shadow=False,
                       shader=w3d.ADDITIVE_SHADER)
        out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
        model.save(out)
        print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")

    image = load_image(os.path.join(tex_dir, jet.texture + ".tga"))
    textured(chassis, image)
    textured(stores, image)
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    house.data.materials.append(colour)
    for obj in flames:
        obj.hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, jet.name + ".blend"))
    render_previews(os.path.join(BUILD, jet.name))


def render_previews(prefix):
    scene = bpy.context.scene
    engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items]
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in engines else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 800, 600
    scene.view_settings.view_transform = "Standard"
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.62, 0.56, 0.44, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.9
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    for i, (angle, height) in enumerate(((35, 34), (145, 30), (250, 40), (200, 8), (90, 90))):
        a = math.radians(angle)
        dist = 62 if height < 80 else 4
        cam.location = Vector((math.cos(a) * dist, math.sin(a) * dist, height))
        cam.rotation_euler = (Vector((0, 0, 1)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{i}.png"
        bpy.ops.render.render(write_still=True)


# --- the Typhoon --------------------------------------------------------------------------------------

class Typhoon(Jet):
    name, texture = "EUTYPH", "eutyp"
    extent = ((-19.5, 20.5), (-13.6, 13.6), (-2.6, 9.6))
    scheme = dict(colours=[(156, 166, 176), (124, 136, 150)], pattern="soft", under=(182, 188, 194))

    # Fuselage: (x, half width, bottom, top, roundness), nose to tail.
    FUSELAGE = [(20.5, 0, 0.55, 0.65, 2), (19.0, 0.35, 0.25, 0.95, 2), (16.5, 1.05, -0.25, 1.45, 2.2),
                (13.5, 1.45, -0.55, 1.95, 2.4), (10.0, 1.7, -0.75, 2.15, 2.6), (6.0, 2.0, -0.8, 2.1, 3.0),
                (0.0, 2.35, -0.8, 1.95, 3.4), (-8.0, 2.4, -0.7, 1.85, 3.4), (-13.0, 2.3, -0.6, 1.7, 3.0),
                (-15.4, 2.15, -0.5, 1.55, 2.8)]
    CANOPY = [(14.6, 0, 1.75, 1.85, 2), (13.6, 0.55, 1.5, 2.55, 2), (11.5, 0.85, 1.5, 3.15, 2),
              (9.0, 0.85, 1.5, 3.05, 2), (7.2, 0.6, 1.5, 2.6, 2), (5.6, 0, 2.0, 2.1, 2)]
    # The chin intake under the cockpit: a squarish duct with a wide, smiling mouth.
    INTAKE = [(8.4, 1.75, -2.35, -0.2, 6), (6.0, 1.95, -2.4, -0.2, 6), (0.0, 2.05, -2.2, -0.3, 6),
              (-6.0, 1.7, -1.4, -0.4, 5)]
    WING = [(4.5, 2.2), (-10.6, 13.0), (-13.2, 13.0), (-14.6, 2.2)]
    CANARD = [(11.2, 1.6), (8.4, 5.8), (7.0, 5.8), (7.6, 1.6)]
    FIN = [(-5.0, 1.5), (-12.4, 9.4), (-14.6, 9.4), (-15.4, 1.5)]
    NOZZLE_Y, NOZZLE_Z, NOZZLE_R = 1.15, 0.45, 1.05

    def stores(self, bm):
        for side in (1, -1):
            # Underwing: a missile on a pylon, and a fuel tank further in.
            box(bm, (-8.0, side * 7.6 - 0.12, -0.8), (-4.6, side * 7.6 + 0.12, -0.2))
            cylinder(bm, (-6.4, side * 7.6, -1.1), 0.3, 6.2, axis="X", segments=8)
            box(bm, (-3.0, side * 4.6 - 0.12, -1.05), (0.5, side * 4.6 + 0.12, -0.2))
            loft(bm, [(4.0, 0, -1.6, -1.5, 2), (2.6, 0.55, -2.1, -1.0, 2), (-3.5, 0.6, -2.15, -0.95, 2),
                      (-5.5, 0, -1.6, -1.5, 2)], segments=10, dy=side * 4.6)

    def wing_z(self, x, y):
        return 0.0 - (abs(y) - 2.2) * 0.02  # a little anhedral

    def shapes(self, bm):
        loft(bm, self.FUSELAGE)
        loft(bm, self.CANOPY, segments=12)
        loft(bm, self.INTAKE, segments=12)
        for side in (1, -1):
            wing = self.WING if side > 0 else mirrored(self.WING)
            slab(bm, wing, 0.55, mid=self.wing_z)
            canard = self.CANARD if side > 0 else mirrored(self.CANARD)
            slab(bm, canard, 0.3, edge=0.08, mid=lambda x, y: 0.75)
            # Nozzles, with a petal ring.
            cylinder(bm, (-16.4, side * self.NOZZLE_Y, self.NOZZLE_Z), self.NOZZLE_R, 2.4, axis="X", segments=14)
            # Wingtip pods (electronic warfare), the Typhoon's tell-tale.
            loft(bm, [(-9.0, 0, 0.0, 0.1, 2), (-10.4, 0.3, -0.35, 0.4, 2), (-13.4, 0.3, -0.35, 0.4, 2),
                      (-14.2, 0, 0.0, 0.1, 2)], segments=8, dy=side * 13.1)
        slab(bm, self.FIN, 0.55, edge=0.1, plane="xz")
        # Spine and the brake-chute / airbrake hump behind the canopy.
        loft(bm, [(7.0, 0, 1.9, 2.0, 2), (4.0, 0.7, 1.6, 2.5, 2), (-4.0, 0.7, 1.6, 2.35, 2), (-8.0, 0, 1.7, 1.9, 2)],
             segments=10)
        # Refuelling probe stub, pitot.
        cylinder(bm, (20.8, 0, 0.6), 0.08, 1.4, axis="X", segments=6)

    def __init__(self):
        self.bones = {
            "WEAPONA01": (4.0, 0.0, -2.6),
            "ENGINE01": (-17.6, self.NOZZLE_Y, self.NOZZLE_Z), "ENGINE02": (-17.6, -self.NOZZLE_Y, self.NOZZLE_Z),
            "WINGTIP01": (-12.0, 13.2, -0.2), "WINGTIP02": (-12.0, -13.2, -0.2),
            "SMOKE01": (-6.0, 3.2, 0.4), "SMOKE02": (2.0, -2.0, 2.2),
            "FLARE01": (-12.0, 2.0, -0.6), "FLARE02": (-12.0, 0.0, -0.8), "FLARE03": (-12.0, -2.0, -0.6),
        }
        # The flames: their root (3.92 forwards of the bone) a little inside the nozzle.
        self.burners = {"BURNERFX01": (-17.6 - 3.0, -self.NOZZLE_Y, self.NOZZLE_Z),
                        "BURNERFX02": (-17.6 - 3.0, self.NOZZLE_Y, self.NOZZLE_Z)}
        self.marks = self.make_marks()

    def house_colour(self, bm):
        # Bands across the outer wings, on the flat inner part of the slab's upper side.
        cu = sum(p[0] for p in self.WING) / 4
        cv = sum(p[1] for p in self.WING) / 4
        inner = [(cu + (u - cu) * 0.8, cv + (v - cv) * 0.8) for u, v in self.WING]
        band = clip_band(inner, 9.2, 10.4)
        for side in (1, -1):
            pts = [(x, side * y, self.wing_z(x, y) + 0.275 + 0.04) for x, y in band]
            flat_panel(bm, pts if side > 0 else list(reversed(pts)))
        # The fin's top on both sides.
        cu = sum(p[0] for p in self.FIN) / 4
        cv = sum(p[1] for p in self.FIN) / 4
        inner = [(cu + (u - cu) * 0.8, cv + (v - cv) * 0.8) for u, v in self.FIN]
        band = clip_band(inner, 7.0, 8.0)
        for side in (1, -1):
            pts = [(x, side * (0.275 + 0.04), z) for x, z in band]
            flat_panel(bm, list(reversed(pts)) if side > 0 else pts)

    def make_marks(self):
        m = []
        # Canopy glass, from above and from the side, with its frame.
        top = [(14.2, 0.3, 2), (13.0, 0.75, 3), (10.5, 0.85, 3), (8.0, 0.75, 3), (6.6, 0.3, 2.5),
               (6.6, -0.3, 2.5), (8.0, -0.75, 3), (10.5, -0.85, 3), (13.0, -0.75, 3), (14.2, -0.3, 2)]
        m.append(dict(kind="glass", group="top", pts=top, frames=[(12.6, 0, 3)]))
        side = [(14.4, 0, 1.85), (12.6, 0, 2.8), (10.0, 0, 3.15), (7.6, 0, 2.75), (6.2, 0, 2.2), (7.0, 0, 1.75),
                (12.0, 0, 1.75)]
        m.append(dict(kind="glass", group="side", pts=side, frames=[(12.6, 0, 2)]))
        # The intake mouth, seen from the front: dark, with a lip.
        mouth = [(8.4, 1.7, -0.4), (8.4, -1.7, -0.4), (8.4, -1.85, -1.4), (8.4, -1.4, -2.2), (8.4, 0, -2.3),
                 (8.4, 1.4, -2.2), (8.4, 1.85, -1.4)]
        m.append(dict(kind="fill", group="front", pts=mouth, colour=(14, 14, 16)))
        # Nozzles from behind.
        for s in (1, -1):
            m.append(dict(kind="nozzle", group="back", at=(-17.6, s * self.NOZZLE_Y, self.NOZZLE_Z), r=self.NOZZLE_R))
            # Exhaust soot on the rear fuselage and the nozzles' sides.
            m.append(dict(kind="soot", group="top", pts=[(-12.5, s * 0.4, 2), (-12.5, s * 2.2, 2), (-17.8, s * 2.3, 2),
                                                          (-17.8, s * 0.2, 2)], strength=170))
            m.append(dict(kind="fill", group="top", pts=[(-15.4, s * 0.15, 2), (-15.4, s * 2.15, 2),
                                                          (-17.6, s * 2.15, 2), (-17.6, s * 0.15, 2)],
                          colour=(84, 80, 74)))
            # Emblems on the wings.
            m.append(dict(kind="emblem", group="top", at=(-6.5, s * 7.0, 0), size=1.5, point="left"))
            # Yellow: the canard tips' warning stripes, and the intake's lip.
            m.append(dict(kind="hazard", group="top", pts=[(8.6, s * 5.0, 1), (8.4, s * 5.8, 1), (7.0, s * 5.8, 1),
                                                            (7.2, s * 5.0, 1)]))
            # Wing panel lines and control surfaces.
            m.append(dict(kind="panels", group="top", pairs=[
                ((-12.6, s * 3.0, 0), (-12.0, s * 12.4, 0)),          # flaperon hinge line
                ((-12.3, s * 7.5, 0), (-14.4, s * 7.5, 0)),
                ((-1.0, s * 3.0, 0), (-8.4, s * 10.6, 0)),
                ((2.0, s * 2.6, 0), (-12.4, s * 2.6, 0)),
            ]))
            m.append(dict(kind="panels", group="bottom", pairs=[((-12.6, s * 3.0, 0), (-12.0, s * 12.4, 0))]))
        m.append(dict(kind="emblem", group="side", at=(-11.6, 0, 5.0), size=1.4))
        m.append(dict(kind="hazard", group="side", pts=[(-12.9, 0, 9.4), (-12.0, 0, 8.7), (-14.4, 0, 8.7),
                                                         (-14.6, 0, 9.4)]))
        m.append(dict(kind="fill", group="side", pts=[(-15.4, 0, 1.5), (-15.4, 0, -0.55), (-17.6, 0, -0.55),
                                                       (-17.6, 0, 1.5)], colour=(78, 74, 70)))
        # Fuselage panel lines (top and side).
        m.append(dict(kind="panels", group="top", pairs=[((x, 2.2, 2), (x, -2.2, 2)) for x in (4.0, -2.0, -8.0)]))
        m.append(dict(kind="panels", group="side", pairs=[((x, 0, 1.8), (x, 0, -0.6)) for x in (15.0, 4.0, -2.0, -8.0)]
                      + [((16.5, 0, 0.9), (-15.0, 0, 0.9))]))
        # The radome, a shade darker.
        m.append(dict(kind="fill", group="top", pts=[(20.5, 0, 1), (18.0, 0.65, 1), (16.5, 1.05, 1), (16.5, -1.05, 1),
                                                      (18.0, -0.65, 1)], colour=(108, 116, 124), outline=(70, 76, 84)))
        m.append(dict(kind="fill", group="side", pts=[(20.5, 0, 0.6), (18.5, 0, 1.15), (16.5, 0, 1.45), (16.5, 0, -0.25),
                                                       (18.5, 0, 0.1)], colour=(108, 116, 124), outline=(70, 76, 84)))
        return m


if __name__ == "__main__":
    build(Typhoon())

"""The European Fusion Plant, modelled in Blender and written as W3D models for the game: a compact fusion
reactor, a plaster drum under a ribbed steel dome, girdled by a toroidal coolant ring whose channels glow,
with two fan cooling units, a control block with a steam stack, and a fenced transformer yard, on a
concrete pad (after a concept painted in the game's style, in the Command Centre's manner).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/fusion_plant.py

How it is painted (as the Command Centre): fusion_plant_paint.py paints small tiling surfaces; Blender
projects them onto the model and bakes them, the ambient occlusion, where the windows and the coolant
channels are, and the height into one texture of the building's own; the painter adds grime and makes
the damaged, wrecked and night versions. Models: EUPWR (intact), _D, _E (wrecked: no dome, fans or stack
top), each with a night version (_N, _DN, _EN); EUPWR_A1, the advanced control rods' injectors, shown
once the plant is upgraded.

The footprint is the USA's (44 long, 60 wide, 46 high, centred). Bones for the game's particle effects:
STEAM01 (the stack), STEAM02/03 (the fans), SMOKE01/02, FIRE01, SPARK01/02 (damaged).

This file also holds the shapes, baking and export shared with garrison.py.
"""
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
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
import w3d  # noqa: E402

TEXTURE_SIZE = 1024


# --- shapes ----------------------------------------------------------------------------------------

class Builder:
    """Shapes added to a bmesh, each face marked with its surface (an index into `surfaces`)."""

    def __init__(self, surfaces):
        self.bm = bmesh.new()
        self.index = {name: i for i, name in enumerate(surfaces)}

    def add(self, surface, make):
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            face.material_index = self.index[surface]

    def box(self, surface, a, b):
        lo = [min(p, q) for p, q in zip(a, b)]
        hi = [max(p, q) for p, q in zip(a, b)]
        centre = [(p + q) / 2 for p, q in zip(lo, hi)]
        size = [q - p for p, q in zip(lo, hi)]
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*size, 1.0))))

    def turned_box(self, surface, centre, size, angle):
        """A box turned by angle about Z round its centre."""
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ Matrix.Rotation(angle, 4, "Z") @ Matrix.Diagonal((*size, 1.0))))

    def cylinder(self, surface, centre, radius, length, axis="Z", segments=16, radius2=None, rotate=0.0):
        rot = {"Z": Matrix.Rotation(rotate, 4, "Z"), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
               "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=length, matrix=Matrix.Translation(centre) @ rot))

    def lathe(self, surface, centre, profile, segments=16, rotate=0.0, surfaces=None):
        """A closed solid of revolution about Z: profile [(r, z)] from bottom to top; r = 0 ends in a point,
        otherwise the end is capped. surfaces: one surface per profile band (overrides `surface`)."""
        cx, cy = centre[0], centre[1]
        z0 = centre[2] if len(centre) > 2 else 0.0

        def make(bm):
            rings = []
            for r, z in profile:
                if r < 1e-6:
                    rings.append([bm.verts.new((cx, cy, z0 + z))])
                else:
                    rings.append([bm.verts.new((cx + math.cos(rotate + 2 * math.pi * k / segments) * r,
                                                cy + math.sin(rotate + 2 * math.pi * k / segments) * r, z0 + z))
                                  for k in range(segments)])
            for i in range(len(rings) - 1):
                a, b = rings[i], rings[i + 1]
                band = self.index[surfaces[i]] if surfaces else self.index[surface]
                for k in range(segments):
                    j = (k + 1) % segments
                    if len(a) == 1:
                        f = bm.faces.new((a[0], b[k], b[j]))
                    elif len(b) == 1:
                        f = bm.faces.new((a[k], a[j], b[0]))
                    else:
                        f = bm.faces.new((a[k], a[j], b[j], b[k]))
                    f.material_index = band
            if len(rings[0]) > 1:
                bm.faces.new(list(reversed(rings[0]))).material_index = self.index[surface]
            if len(rings[-1]) > 1:
                bm.faces.new(rings[-1]).material_index = self.index[surface]
        make(self.bm)

    def torus(self, centre, major, minor, segments, sides, surface_of):
        """A closed ring; surface_of(segment, side) names each face's surface (side 0 faces outwards)."""
        cx, cy, cz = centre
        bm = self.bm
        rows = []
        for i in range(segments):
            a = 2 * math.pi * i / segments
            row = []
            for k in range(sides):
                b = 2 * math.pi * (k - 0.5) / sides
                r = major + math.cos(b) * minor
                row.append(bm.verts.new((cx + math.cos(a) * r, cy + math.sin(a) * r, cz + math.sin(b) * minor)))
            rows.append(row)
        for i in range(segments):
            n = (i + 1) % segments
            for k in range(sides):
                m = (k + 1) % sides
                f = bm.faces.new((rows[i][k], rows[n][k], rows[n][m], rows[i][m]))
                f.material_index = self.index[surface_of(i, k)]

    def sweep(self, surface, path, side_dirs, out_dirs, half_width, depth):
        """A beam of rectangular section along a path of points: side_dirs/out_dirs give, at each point, the
        section's sideways and outward directions (the beam stands out by depth, half inside)."""
        def make(bm):
            rings = []
            for p, s, o in zip(path, side_dirs, out_dirs):
                p, s, o = Vector(p), Vector(s) * half_width, Vector(o) * depth / 2
                rings.append([bm.verts.new(p + o - s), bm.verts.new(p + o + s), bm.verts.new(p - o + s), bm.verts.new(p - o - s)])
            for a, b in zip(rings, rings[1:]):
                for k in range(4):
                    j = (k + 1) % 4
                    bm.faces.new((a[k], a[j], b[j], b[k]))
            bm.faces.new(list(reversed(rings[0])))
            bm.faces.new(rings[-1])
        self.add(surface, make)


def arc(cy, cz, radius, start, end, steps):
    return [(cy + math.cos(a) * radius, cz + math.sin(a) * radius)
            for a in (start + (end - start) * i / steps for i in range(steps + 1))]


def ring(b, surface, x0, x1, y0, y1, z0, z1, width):
    """A frame of four boxes round a rectangle (a cornice or parapet)."""
    b.box(surface, (x0, y0, z0), (x1, y0 + width, z1))
    b.box(surface, (x0, y1 - width, z0), (x1, y1, z1))
    b.box(surface, (x0, y0 + width, z0), (x0 + width, y1 - width, z1))
    b.box(surface, (x1 - width, y0 + width, z0), (x1, y1 - width, z1))


def flat_object(name, quads, uv_of=None):
    """A flat, open mesh of quads (decals, house colour); uv_of(quad index, corner) or 0..1 per quad."""
    bm = bmesh.new()
    for quad in quads:
        bm.faces.new([bm.verts.new(v) for v in quad])
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for i, poly in enumerate(obj.data.polygons):
        for c, li in enumerate(poly.loop_indices):
            uv.data[li].uv = uv_of(i, c) if uv_of else ((0, 0), (1, 0), (1, 1), (0, 1))[c]
    return obj


def both_ways(quads):
    return [q for quad in quads for q in (quad, list(reversed(quad)))]


def pad_object(x0, x1, y0, y1, z):
    """The concrete pad with a chamfered edge, its texture spanning the footprint."""
    bm = bmesh.new()
    outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    top = [bm.verts.new((x * 0.99, y * 0.99, z)) for x, y in outline]
    bm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object("PAD", bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, _ = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x - x0) / (x1 - x0), (y - y0) / (y1 - y0))
    return obj


# --- painting --------------------------------------------------------------------------------------

def surface_material(name, spec, tiles, emitters):
    """A surface: its tile projected from all sides in world units, or a plain colour."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    if isinstance(spec[0], str):
        tile, size = spec
        coords = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1 / size, 1 / size, 1 / size)
        image = nodes.new("ShaderNodeTexImage")
        image.image = load_image(os.path.join(tiles, tile + ".png"))
        image.projection = "BOX"
        image.projection_blend = 0.15
        links.new(coords.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], image.inputs["Vector"])
        links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = [c / 255.0 for c in spec] + [1.0]
    if name in emitters:
        bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
        bsdf.inputs["Emission Strength"].default_value = 0.0
    return mat


def height_material(top):
    """Emits the height above the ground (1 at `top`), for shading walls darker below."""
    mat = bpy.data.materials.get("height") or bpy.data.materials.new("height")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    geometry = nodes.new("ShaderNodeNewGeometry")
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    scale = nodes.new("ShaderNodeMath")
    scale.operation = "DIVIDE"
    scale.inputs[1].default_value = top
    emit = nodes.new("ShaderNodeEmission")
    out = nodes.new("ShaderNodeOutputMaterial")
    links.new(geometry.outputs["Position"], xyz.inputs["Vector"])
    links.new(xyz.outputs["Z"], scale.inputs[0])
    links.new(scale.outputs["Value"], emit.inputs["Color"])
    links.new(emit.outputs["Emission"], out.inputs["Surface"])
    target = nodes.new("ShaderNodeTexImage")
    target.name = "bake target"
    nodes.active = target
    return mat


def bake(objects, kind, image, glowing=(), top=30.0):
    """Bakes into image: DIFFUSE (colour only), AO, EMIT (only the surfaces named in glowing) or HEIGHT."""
    saved = None
    if kind == "HEIGHT":
        mat = height_material(top)
        mat.node_tree.nodes["bake target"].image = image
        saved = [(obj, [m for m in obj.data.materials]) for obj in objects]
        for obj in objects:
            obj.data.materials.clear()
            obj.data.materials.append(mat)
    for obj in objects:
        for mat in obj.data.materials:
            nodes = mat.node_tree.nodes
            target = nodes.get("bake target") or nodes.new("ShaderNodeTexImage")
            target.name = "bake target"
            target.image = image
            nodes.active = target
            bsdf = nodes.get("Principled BSDF")
            if bsdf is not None:
                bsdf.inputs["Emission Strength"].default_value = 1.0 if kind == "EMIT" and mat.name in glowing else 0.0
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64 if kind == "AO" else 4
    settings = scene.render.bake
    settings.margin = 8
    settings.use_pass_direct = settings.use_pass_indirect = False
    settings.use_pass_color = True
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.bake(type="EMIT" if kind == "HEIGHT" else kind)
    if saved:
        for obj, mats in saved:
            obj.data.materials.clear()
            for m in mats:
                obj.data.materials.append(m)


def save(image, path):
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()


def bake_building(builders, surfaces, tiles, bakes, emit_maps, top):
    """Objects from the builders (each a closed set of shapes), unwrapped together onto one atlas, and
    their bakes: colour, occlusion, height and one emission map per entry of emit_maps {file: surfaces}."""
    objects = []
    emitters = {s for group in emit_maps.values() for s in group}
    for name, builder in builders:
        # Each part stays a closed shape of its own (no merging of touching corners): the game builds
        # shadow volumes from these meshes.
        bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
        obj = new_object(name, builder.bm)
        for surface, spec in surfaces.items():
            obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, spec, tiles, emitters))
        smooth_by_angle(obj, 35)
        objects.append(obj)
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    os.makedirs(bakes, exist_ok=True)
    jobs = [("DIFFUSE", "colour.png", ()), ("AO", "occlusion.png", ())]
    jobs += [("EMIT", file, group) for file, group in emit_maps.items()]
    jobs.append(("HEIGHT", "height.png", ()))
    for kind, file, group in jobs:
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(objects, kind, image, glowing=group, top=top)
        save(image, os.path.join(bakes, file))
    return objects


def bake_pad(ground, bakes):
    plain = bpy.data.materials.new("pad bake")
    plain.use_nodes = True
    ground.data.materials.append(plain)
    image = bpy.data.images.new("pad_occlusion.png", 512, 512)
    bake([ground], "AO", image)
    save(image, os.path.join(bakes, "pad_occlusion.png"))


def model_name(base, version, night):
    return base + version + ("N" if night and version else "_N" if night else "")


# --- the fusion plant ------------------------------------------------------------------------------

NAME = "EUPWR"
PREFIX = "eupp"
PAD_Z = 0.6
PAD = (-23.0, 23.0, -31.0, 31.0)
SURFACES = {
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "rib": ("tile_rib", 10.0), "deck": ("tile_deck", 12.0),
    "door": ("tile_door", 10.0), "steel": ("tile_steel", 10.0), "metal": ("tile_metal", 6.0),
    "hazard": ("tile_hazard", 3.0), "grille": ("tile_grille", 3.0), "ceramic": ("tile_ceramic", 2.0),
    "glass": (40, 72, 92), "glow": (104, 198, 255), "dark": (38, 40, 44), "yellow": (222, 182, 46),
    "red": (196, 52, 40), "white": (222, 224, 222),
}
REACTOR = (-3.0, 5.0)          # the drum's centre
DRUM_R, DRUM_TOP = 11.0, 19.0
TORUS_R, TORUS_r, TORUS_Z = 13.2, 2.0, 8.4
DOME_H = 7.5
STACK = (17.5, 27.6, 34.0)     # x, y, top
FANS = [(-14.5, -22.0), (-0.5, -22.0)]
FAN_TOP = 8.6
BONES = {
    "STEAM01": (STACK[0], STACK[1], STACK[2] + 0.5),
    "STEAM02": (FANS[0][0], FANS[0][1], FAN_TOP + 1.0), "STEAM03": (FANS[1][0], FANS[1][1], FAN_TOP + 1.0),
    "SMOKE01": (REACTOR[0] + 4, REACTOR[1] - 3, DRUM_TOP + 3), "SMOKE02": (16.5, 20.0, 14.0),
    "FIRE01": (-8.0, -22.0, FAN_TOP), "SPARK01": (14.0, -20.0, 7.0), "SPARK02": (18.0, -16.0, 7.0),
}


def reactor(b):
    """The drum, its plinth, the coolant ring with its glowing channels and clamps, the door."""
    cx, cy = REACTOR
    b.lathe("trim", (cx, cy, PAD_Z), [(DRUM_R + 1.4, 0), (DRUM_R + 1.4, 1.6), (DRUM_R + 0.3, 2.2), (DRUM_R + 0.3, 2.21)],
            segments=16, surfaces=["trim", "trim", "trim"])
    b.lathe("wall", (cx, cy, PAD_Z), [(DRUM_R, 2.0), (DRUM_R, DRUM_TOP - PAD_Z - 1.4), (DRUM_R + 0.7, DRUM_TOP - PAD_Z - 1.2),
                                       (DRUM_R + 0.7, DRUM_TOP - PAD_Z), (DRUM_R - 0.6, DRUM_TOP - PAD_Z)],
            segments=16, surfaces=["wall", "trim", "trim", "trim"])
    b.lathe("yellow", (cx, cy, 0), [(DRUM_R + 0.12, 11.2), (DRUM_R + 0.12, 11.8)], segments=16)
    # The coolant ring: steel, with glowing channels on its outer face between the clamps.
    b.torus((cx, cy, TORUS_Z), TORUS_R, TORUS_r, 24, 6,
            lambda i, k: "glow" if k in (0, 1) and i % 3 != 0 else "steel")
    for i in range(0, 24, 3):
        a = 2 * math.pi * i / 24
        x, y = cx + math.cos(a) * TORUS_R, cy + math.sin(a) * TORUS_R
        b.turned_box("trim", (x, y, TORUS_Z), (TORUS_r * 2 + 1.0, 2.0, TORUS_r * 2 + 1.0), a)
        x2, y2 = cx + math.cos(a) * (DRUM_R + 0.6), cy + math.sin(a) * (DRUM_R + 0.6)
        b.turned_box("metal", ((x + x2) / 2, (y + y2) / 2, TORUS_Z), (TORUS_R - DRUM_R, 1.0, 1.2), a)
    # The door: a portal at the front (+X), under the ring.
    x = cx + DRUM_R - 0.6
    b.box("trim", (x, cy - 4.2, PAD_Z), (x + 3.4, cy + 4.2, 5.6))
    b.box("door", (x + 3.4, cy - 2.8, PAD_Z + 0.4), (x + 3.6, cy + 2.8, 5.0))
    b.box("hazard", (x + 3.35, cy - 3.4, 5.0), (x + 3.55, cy + 3.4, 5.4))
    # Windows round the drum above the ring.
    for k in range(10):
        a = 2 * math.pi * (k + 0.5) / 10
        if math.cos(a) > 0.9:
            continue
        b.turned_box("glass", (cx + math.cos(a) * (DRUM_R + 0.02), cy + math.sin(a) * (DRUM_R + 0.02), 14.0),
                     (0.3, 2.4, 1.8), a)


def dome(b):
    """The ribbed steel dome, a lantern on top."""
    cx, cy = REACTOR
    steps = 6
    profile = [(DRUM_R - 0.3, 0.0)]
    for i in range(1, steps + 1):
        p = math.pi / 2 * i / steps
        profile.append((max(0.0, (DRUM_R - 0.3) * math.cos(p)), DOME_H * math.sin(p)))
    profile[-1] = (2.2, DOME_H)
    profile.append((0.0, DOME_H))
    b.lathe("steel", (cx, cy, DRUM_TOP), profile, segments=16)
    ribs = 8
    for k in range(ribs):
        a = 2 * math.pi * k / ribs
        dx, dy = math.cos(a), math.sin(a)
        path, sides, outs = [], [], []
        for i in (0, 2, 3, 4, 5):
            p = math.pi / 2 * i / steps * 0.92
            r, z = (DRUM_R - 0.3) * math.cos(p), DOME_H * math.sin(p)
            path.append((cx + dx * r, cy + dy * r, DRUM_TOP + z))
            sides.append((-dy, dx, 0))
            n = Vector((dx * math.cos(p) / (DRUM_R - 0.3), dy * math.cos(p) / (DRUM_R - 0.3), math.sin(p) / DOME_H)).normalized()
            outs.append(tuple(n))
        b.sweep("trim", path, sides, outs, 0.35, 0.7)
    b.cylinder("trim", (cx, cy, DRUM_TOP + DOME_H + 0.4), 2.6, 1.0, segments=10)
    b.cylinder("metal", (cx, cy, DRUM_TOP + DOME_H + 1.6), 1.4, 1.6, segments=8)
    b.cylinder("trim", (cx, cy, DRUM_TOP + DOME_H + 2.6), 1.9, 0.5, segments=8)
    b.cylinder("metal", (cx + 1, cy - 1, DRUM_TOP + DOME_H + 4.4), 0.12, 3.5, segments=4)
    b.cylinder("red", (cx + 1, cy - 1, DRUM_TOP + DOME_H + 6.2), 0.3, 0.4, segments=6)


def cooling(b, top):
    """Two boxy cooling units with big fans on top (the fans in `top`), louvres, and pipes to the ring."""
    for x, y in FANS:
        b.box("trim", (x - 6.2, y - 6.2, PAD_Z), (x + 6.2, y + 6.2, PAD_Z + 1.2))
        b.box("wall", (x - 5.6, y - 5.6, PAD_Z), (x + 5.6, y + 5.6, FAN_TOP - 0.6))
        ring(b, "trim", x - 5.9, x + 5.9, y - 5.9, y + 5.9, FAN_TOP - 1.0, FAN_TOP, 1.2)
        b.box("deck", (x - 4.8, y - 4.8, FAN_TOP - 1.0), (x + 4.8, y + 4.8, FAN_TOP - 0.7))
        for side in (-1, 1):   # louvres on both sides and the back
            b.box("grille", (x - 4.0, y + side * 5.6 - 0.1, PAD_Z + 2.0), (x + 4.0, y + side * 5.6 + 0.1, FAN_TOP - 2.0))
        b.box("grille", (x - 5.7, y - 4.0, PAD_Z + 2.0), (x - 5.5, y + 4.0, FAN_TOP - 2.0))
        b.cylinder("trim", (x, y, FAN_TOP - 0.2), 4.5, 1.2, segments=12, radius2=4.3)
        b.cylinder("dark", (x, y, FAN_TOP + 0.45), 3.9, 0.1, segments=12)
        for c in (-1, 1):       # feet
            b.box("metal", (x + c * 5.6 - 0.8, y - 3, PAD_Z), (x + c * 5.6 + 0.8, y + 3, PAD_Z + 2.2))
    for x, y in FANS:
        for k in range(6):
            a = k * math.pi / 3 + 0.3
            top.turned_box("metal", (x + math.cos(a) * 1.9, y + math.sin(a) * 1.9, FAN_TOP + 0.6), (3.6, 1.0, 0.18), a + 0.3)
        top.cylinder("metal", (x, y, FAN_TOP + 0.7), 0.8, 0.5, segments=8)
        for k in range(4):
            top.turned_box("trim", (x, y, FAN_TOP + 1.25), (8.0, 0.3, 0.2), k * math.pi / 4)
    # Pipes from the units to the ring.
    for x, _ in FANS:
        b.cylinder("metal", (x + 1.0, -13.0, 4.0), 0.9, 6.4, axis="Y", segments=8)
        b.cylinder("trim", (x + 1.0, -15.5, 4.0), 1.2, 0.6, axis="Y", segments=8)
        b.box("metal", (x + 0.2, -10.8, PAD_Z), (x + 1.8, -9.6, 4.0))
    b.cylinder("metal", (-7.5, -10.2, 4.0), 0.9, 17.0, axis="X", segments=8)


def control_block(b, top_part):
    """The control block by the stack: plaster, a yellow band, windows, a door, roof plant; the stack's
    top in `top_part`."""
    x0, x1, y0, y1, top = 11.5, 21.5, 13.0, 25.5, 12.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.0))
    b.box("yellow", (x0 - 0.12, y0 - 0.12, 7.6), (x1 + 0.12, y1 + 0.12, 8.4))
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 1.0, top + 0.6, 1.0)
    b.box("deck", (x0 + 0.5, y0 + 0.5, top - 0.2), (x1 - 0.5, y1 - 0.5, top + 0.1))
    for y in (15.0, 19.0):     # windows to the front
        b.box("trim", (x1, y - 0.3, 8.9), (x1 + 0.4, y + 3.3, 10.9))
        b.box("glass", (x1 + 0.4, y, 9.2), (x1 + 0.5, y + 3.0, 10.6))
    for x in (13.5, 17.5):     # and to the reactor
        b.box("trim", (x - 0.3, y0 - 0.4, 8.9), (x + 3.3, y0, 10.9))
        b.box("glass", (x, y0 - 0.5, 9.2), (x + 3.0, y0 - 0.4, 10.6))
    b.box("door", (x1, 16.5, PAD_Z + 0.4), (x1 + 0.2, 20.5, 6.0))
    b.box("trim", (x1, 15.8, 6.0), (x1 + 1.6, 21.2, 6.6))
    b.box("metal", (x0 + 1.5, y0 + 2, top), (x0 + 5.5, y0 + 6, top + 2.2))
    b.box("grille", (x0 + 5.5, y0 + 2.4, top + 0.4), (x0 + 5.6, y0 + 5.6, top + 1.8))
    # The stack beside it: steel with a yellow top (as the USA plant's).
    sx, sy, stop = STACK
    b.box("trim", (sx - 2.6, sy - 2.2, PAD_Z), (sx + 2.6, sy + 2.2, PAD_Z + 2.0))
    b.cylinder("trim", (sx, sy, (PAD_Z + 22) / 2), 1.9, 22 - PAD_Z, segments=10)
    t = top_part
    t.cylinder("metal", (sx, sy, (22 + stop - 1.5) / 2), 1.6, stop - 1.5 - 22, segments=10)
    t.cylinder("yellow", (sx, sy, stop - 0.75), 1.75, 1.5, segments=10)
    t.cylinder("dark", (sx, sy, stop), 1.3, 0.1, segments=10)
    for z in (24.0, 29.0):
        t.cylinder("trim", (sx, sy, z), 1.9, 0.5, segments=10)
    # A pipe from the block to the drum.
    b.box("metal", (8.0, 11.0, 6.0), (12.0, 12.4, 7.4))


def tanks(b):
    """Two white pressure tanks at the back corner."""
    for x, y in ((-17.5, 24.5), (-17.5, 17.5)):
        b.lathe("white", (x, y, PAD_Z), [(0, 0), (2.8, 0), (2.8, 6.5), (2.0, 7.8), (0, 8.2)], segments=12)
        for c in (-1, 1):
            b.box("metal", (x + c * 2.0 - 0.3, y - 0.3, PAD_Z), (x + c * 2.0 + 0.3, y + 0.3, 1.8))
        b.box("yellow", (x - 2.85, y - 1.2, 3.0), (x - 2.75, y + 1.2, 3.6))
    b.cylinder("metal", (-14.0, 21.0, 4.0), 0.5, 7.0, axis="Y", segments=6)


def transformers(b):
    """The transformer yard at the front corner: two transformers with insulators, a gantry."""
    for x, y in ((12.5, -22.5), (18.0, -22.5)):
        b.box("trim", (x - 2.2, y - 3.2, PAD_Z), (x + 2.2, y + 3.2, PAD_Z + 0.6))
        b.box("metal", (x - 1.8, y - 2.4, PAD_Z), (x + 1.8, y + 2.4, 5.0))
        b.box("grille", (x - 1.9, y - 2.2, 1.6), (x + 1.9, y + 2.2, 4.2))
        for k in (-1.5, 0.0, 1.5):
            b.cylinder("ceramic", (x, y + k, 6.4), 0.42, 2.8, segments=6)
    for y in (-27.0, -18.0):
        for x in (10.0, 20.5):
            b.box("metal", (x - 0.25, y - 0.25, PAD_Z), (x + 0.25, y + 0.25, 10.0))
        b.box("metal", (10.0, y - 0.25, 9.5), (20.5, y + 0.25, 10.0))
    for k in (-1.5, 0.0, 1.5):
        b.cylinder("ceramic", (15.25, -18.0 + k * 0.01 + k, 8.6), 0.3, 1.6, segments=6)
    b.box("hazard", (9.0, -29.0, PAD_Z), (9.6, -12.5, PAD_Z + 0.25))


def wreckage(b):
    """What lies on the drum's floor once the dome has fallen in: broken panels and beams."""
    cx, cy = REACTOR
    rng = [(-4, 2, 0.4), (3, -3, 1.1), (1, 5, 2.0), (-6, -5, 2.6), (5, 3, 0.9), (-1, -1, 1.7)]
    for dx, dy, a in rng:
        b.turned_box("steel", (cx + dx, cy + dy, DRUM_TOP + 0.3), (6.0, 3.0, 1.4), a)
    for dx, dy, a in ((-2, 3, 0.8), (2, -2, 2.2), (-5, -1, 1.4)):
        b.turned_box("trim", (cx + dx, cy + dy, DRUM_TOP + 1.2), (9.0, 0.8, 0.8), a)
    for x, y in FANS:
        b.turned_box("metal", (x + 1, y - 1, FAN_TOP + 0.3), (4.0, 0.9, 0.3), 0.9)
    sx, sy, _ = STACK
    b.turned_box("metal", (sx - 1.0, sy - 3.5, 1.6), (2.4, 9.0, 2.4), 0.5)


def emblems():
    """The faction's mark on the drum above the door, curved round it."""
    cx, cy = REACTOR
    r = DRUM_R + 0.25
    steps = 4
    a0, a1 = -0.28, 0.28        # 6.2 wide round the curve, as high
    z0, z1 = 11.0, 17.2
    quads = []
    for i in range(steps):
        p, q = a0 + (a1 - a0) * i / steps, a0 + (a1 - a0) * (i + 1) / steps
        quads.append([(cx + math.cos(p) * r, cy + math.sin(p) * r, z0), (cx + math.cos(q) * r, cy + math.sin(q) * r, z0),
                      (cx + math.cos(q) * r, cy + math.sin(q) * r, z1), (cx + math.cos(p) * r, cy + math.sin(p) * r, z1)])
    mark = flat_object("EMBLEM", quads, lambda i, c: ((i + (0, 1, 1, 0)[c]) / steps, (0, 0, 1, 1)[c]))
    return [mark]


def house_colours():
    """The player's colour: a band round the drum under its cornice, stripes on the cooling units."""
    cx, cy = REACTOR
    segs, r = 20, DRUM_R + 0.1
    quads = []
    for k in range(segs):
        a, b = 2 * math.pi * k / segs, 2 * math.pi * (k + 1) / segs
        if abs(math.atan2(math.sin(a + math.pi / segs), math.cos(a + math.pi / segs))) < 0.4:
            continue    # leave room for the emblem
        quads.append([(cx + math.cos(a) * r, cy + math.sin(a) * r, 16.4), (cx + math.cos(b) * r, cy + math.sin(b) * r, 16.4),
                      (cx + math.cos(b) * r, cy + math.sin(b) * r, 17.2), (cx + math.cos(a) * r, cy + math.sin(a) * r, 17.2)])
    band = flat_object("HOUSECOLOR01", quads)
    quads = []
    for x, y in FANS:
        quads.append([(x + 5.72, y - 4.5, FAN_TOP - 3.0), (x + 5.72, y + 4.5, FAN_TOP - 3.0),
                      (x + 5.72, y + 4.5, FAN_TOP - 2.0), (x + 5.72, y - 4.5, FAN_TOP - 2.0)])
    stripes = flat_object("HOUSECOLOR02", quads)
    return [band, stripes]


FENCE = [((9.0, -29.5), (21.8, -29.5)), ((21.8, -29.5), (21.8, -11.8)), ((21.8, -11.8), (9.0, -11.8))]
FENCE_HEIGHT = 4.0


def fence_posts(b):
    for (ax, ay), (bx, by) in FENCE:
        steps = max(1, int(math.hypot(bx - ax, by - ay) / 6))
        for i in range(steps + 1):
            t = i / steps
            b.cylinder("metal", (ax + (bx - ax) * t, ay + (by - ay) * t, PAD_Z + FENCE_HEIGHT / 2), 0.15, FENCE_HEIGHT, segments=4)


def fence_object():
    quads = [[(ax, ay, PAD_Z), (bx, by, PAD_Z), (bx, by, PAD_Z + FENCE_HEIGHT), (ax, ay, PAD_Z + FENCE_HEIGHT)] for (ax, ay), (bx, by) in FENCE]
    obj = flat_object("FENCE", both_ways(quads))
    me = obj.data
    uv = me.uv_layers.active
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x + y) / 4.0, (z - PAD_Z) / FENCE_HEIGHT)
    return obj


def injectors(b):
    """The advanced control rods (the upgrade): four injector pylons round the ring, glowing collars."""
    cx, cy = REACTOR
    for k in range(4):
        a = math.pi / 4 + k * math.pi / 2
        x, y = cx + math.cos(a) * (TORUS_R + 0.2), cy + math.sin(a) * (TORUS_R + 0.2)
        b.cylinder("trim", (x, y, TORUS_Z + 4.4), 0.9, 6.0, segments=8)
        b.cylinder("glow", (x, y, TORUS_Z + 3.0), 1.1, 1.0, segments=8)
        b.cylinder("glow", (x, y, TORUS_Z + 5.4), 1.1, 1.0, segments=8)
        b.cylinder("yellow", (x, y, TORUS_Z + 7.6), 1.1, 0.5, segments=8)
        b.cylinder("metal", (x, y, TORUS_Z + 8.4), 0.35, 1.2, segments=6)


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "fusion_plant_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    for name in (f"{PREFIX}_emblem.tga", f"{PREFIX}_fence.tga"):
        shutil.copy(os.path.join(tiles, name), os.path.join(tex_dir, name))
    main, intact, wreck, upgrade = (Builder(SURFACES) for _ in range(4))
    reactor(main)
    cooling(main, intact)
    control_block(main, intact)
    tanks(main)
    transformers(main)
    fence_posts(main)
    dome(intact)
    wreckage(wreck)
    injectors(upgrade)
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    objects = bake_building([("BUILDING", main), ("INTACT", intact), ("WRECK", wreck), ("RODS", upgrade)],
                            SURFACES, tiles, bakes, {"windows.png": ("glass",), "glow.png": ("glow",)}, top=30.0)
    ground = pad_object(*PAD, PAD_Z)
    bake_pad(ground, bakes)
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, f"{PREFIX}_building.tga"))
    for obj in objects:
        textured(obj, baked)
    textured(ground, load_image(os.path.join(tex_dir, f"{PREFIX}_pad.tga")))
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, f"{PREFIX}_emblem.tga")))
    banners = house_colours()
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in banners:
        obj.data.materials.append(colour)
    wire = fence_object()
    textured(wire, load_image(os.path.join(tex_dir, f"{PREFIX}_fence.tga")))
    names = ("building", "intact", "wreck", "rods")
    return dict(zip(names, objects), pad=ground, emblems=marks, banners=banners, fence=wire)


# --- writing the models ----------------------------------------------------------------------------

def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(model_name(NAME, version, night))
    for bone, at in BONES.items():
        model.bone(bone, w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    else:
        model.mesh("WRECK", w3d.CHASSIS, **mesh_data(parts["wreck"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    if version != "_E":
        model.mesh("FENCE", w3d.CHASSIS, **mesh_data(parts["fence"]), texture=f"{PREFIX}_fence.tga", **flat)
        for obj in parts["emblems"]:
            model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["banners"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def export_rods(parts):
    """The upgrade's injectors, a model of their own the game shows over the plant once upgraded."""
    model = w3d.Model(NAME + "_A1")
    model.mesh("RODS", w3d.CHASSIS, **mesh_data(parts["rods"]), texture=f"{PREFIX}_building.tga")
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {sum(len(m[5]) for m in model.meshes)} triangles")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)
    export_rods(parts)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

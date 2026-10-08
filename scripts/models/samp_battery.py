"""The European SAMP/T Battery, modelled in Blender and written as W3D models for the game: a square
plaster plinth with a yellow band and a crew cabin, carrying a steel turntable with a radar dish and a
launcher of eight missile canisters that turns and raises to fire (after a concept painted in the game's
style). Everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/samp_battery.py

Painted as the Command Centre (command_centre.py): samp_battery_paint.py paints small tiling surfaces,
Blender projects them onto the model and bakes them with the ambient occlusion into one texture; the
painter adds grime and makes the damaged, wrecked and night versions. Six models: EUSAMP (intact), _D,
_E (no dish or roof clutter), each with a night version (_N, _DN, _EN) with lit windows.

Bones (as the USA's Patriot, ABPATRIOT, which the game's INI names):
    TURRET01               the turntable, turning about Z
    TURRETEL               the launcher's hinge, a child of TURRET01, pitching about Y; the launcher is
                           modelled level, pointing +X, and the game raises it (NaturalTurretPitch 45)
    WEAPONA01..WEAPONA04   where the missiles leave the canisters (WeaponLaunchBone/WeaponFireFXBone WeaponA)

The footprint is the USA's (a cylinder of radius 12, 14 high); the pad is 26 square.
"""
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
import w3d  # noqa: E402

NAME = "EUSAMP"
PREFIX = "eusa"
PAD_Z = 0.6
PAD_HALF = 13.0
TEXTURE_SIZE = 1024
HEIGHT_TOP = 18.0
# Surfaces: (tile painted by samp_battery_paint.py, units per tile) or a plain colour.
SURFACES = {
    "wall": ("tile_wall", 8.0), "trim": ("tile_trim", 8.0), "deck": ("tile_deck", 8.0), "door": ("tile_door", 6.0),
    "metal": ("tile_metal", 4.0), "sandbag": ("tile_sandbag", 3.0), "hazard": ("tile_hazard", 2.0),
    "grille": ("tile_grille", 2.0), "crate": ("tile_crate", 3.0), "steel": ("tile_steel", 8.0),
    "canister": ("tile_canister", 3.4), "turntable": ("tile_turntable", 4.0),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46), "red": (196, 52, 40), "white": (226, 228, 230),
}

TURRET_AT = (0.0, 0.0, 6.0)              # TURRET01, on the plinth's deck
HINGE = (-4.5, 0.0, 9.8)                 # TURRETEL, in the world
LAUNCHER = (-5.2, 5.6, 3.4, 1.7)         # x0, x1 (from the hinge), half width, row height (2 rows above the hinge)


# --- shapes (shared with bastion.py) ---------------------------------------------------------------

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

    def oriented_box(self, surface, centre, size, matrix):
        """A box of `size` about `centre`, turned by the 4x4 `matrix` first."""
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ matrix @ Matrix.Diagonal((*size, 1.0))))

    def cylinder(self, surface, centre, radius, length, axis="Z", segments=16, radius2=None, rotate=0.0):
        rot = {"Z": Matrix.Rotation(rotate, 4, "Z"), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
               "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=length, matrix=Matrix.Translation(centre) @ rot))

    def sphere(self, surface, centre, radius, u=10, v=6):
        self.add(surface, lambda bm: bmesh.ops.create_uvsphere(
            bm, u_segments=u, v_segments=v, radius=radius, matrix=Matrix.Translation(centre)))

    def prism(self, surface, profile, y0, y1, cap_surface=None):
        """A closed side profile (x, z) pushed along y from y0 to y1."""
        def make(bm):
            a = [bm.verts.new((x, y0, z)) for x, z in profile]
            b = [bm.verts.new((x, y1, z)) for x, z in profile]
            n = len(profile)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
            ends = (bm.faces.new(list(reversed(a))), bm.faces.new(b))
            for e in ends:
                e.material_index = self.index[cap_surface or surface]
            make.ends = ends
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            if face not in make.ends:
                face.material_index = self.index[surface]


def ring(b, surface, x0, x1, y0, y1, z0, z1, width):
    """A frame of four boxes round a rectangle (a cornice or parapet), leaving the middle open."""
    b.box(surface, (x0, y0, z0), (x1, y0 + width, z1))
    b.box(surface, (x0, y1 - width, z0), (x1, y1, z1))
    b.box(surface, (x0, y0 + width, z0), (x0 + width, y1 - width, z1))
    b.box(surface, (x1 - width, y0 + width, z0), (x1, y1 - width, z1))


def dish(b, surface, centre, radius, facing, tilt=0.5):
    """A radar dish facing `facing` (radians about Z), tilted up by `tilt`."""
    def make(bm):
        m = (Matrix.Translation(centre) @ Matrix.Rotation(facing, 4, "Z")
             @ Matrix.Rotation(-math.pi / 2 + tilt, 4, "Y"))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=radius, radius2=radius * 0.3,
                              depth=radius * 0.4, matrix=m)
    b.add(surface, make)


# --- the battery -----------------------------------------------------------------------------------

def plinth(b):
    """The plaster plinth: a plinth course, a yellow band, a cornice, corner piers, a cabin and pipes."""
    h = 8.0
    top = TURRET_AT[2]
    b.box("wall", (-h, -h, PAD_Z), (h, h, top))
    b.box("trim", (-h - 0.4, -h - 0.4, PAD_Z), (h + 0.4, h + 0.4, 1.6))
    b.box("yellow", (-h - 0.1, -h - 0.1, 4.3), (h + 0.1, h + 0.1, 4.75))
    ring(b, "trim", -h - 0.5, h + 0.5, -h - 0.5, h + 0.5, top - 0.6, top + 0.5, 1.0)
    b.box("deck", (-h + 0.5, -h + 0.5, top), (h - 0.5, h - 0.5, top + 0.1))
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * h, sy * h
            b.box("wall", (x - 1.0, y - 1.0, PAD_Z), (x + 1.0, y + 1.0, top + 0.8))
            b.box("trim", (x - 1.2, y - 1.2, top + 0.7), (x + 1.2, y + 1.2, top + 1.1))
    # A maintenance hatch and a vent in the plinth's sides.
    b.box("trim", (-3.0, -h - 0.3, PAD_Z), (1.0, -h, 3.6))
    b.box("door", (-2.6, -h - 0.45, PAD_Z + 0.4), (0.6, -h - 0.3, 3.3))
    b.box("grille", (-h - 0.15, -3.0, 2.2), (-h, 3.0, 3.6))
    # Windows: a lit slit on each side under the band.
    for y0, face in ((h, 1), (-h, -1)):
        for x in (-5.5, 3.0):
            b.box("trim", (x - 0.3, y0, 2.4), (x + 2.8, y0 + face * 0.25, 3.8))
            b.box("glass", (x, y0 + face * 0.25, 2.7), (x + 2.5, y0 + face * 0.32, 3.5))


def cabin(b):
    """The crew cabin at the front corner, with a door, a window and an air conditioner."""
    x0, x1, y0, y1, top = 6.5, 10.6, 2.6, 7.4, 4.8
    b.box("steel", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.2, y0 - 0.2, top), (x1 + 0.2, y1 + 0.2, top + 0.4))
    b.box("trim", (x0 - 0.15, y0 - 0.15, PAD_Z), (x1 + 0.15, y1 + 0.15, PAD_Z + 0.5))
    b.box("door", (x1, 3.4, PAD_Z + 0.5), (x1 + 0.15, 5.4, 4.0))
    b.box("trim", (x1, 3.1, 4.0), (x1 + 0.6, 5.7, 4.3))            # a little canopy
    b.box("trim", (x1 - 0.1, 5.9, 2.4), (x1 + 0.1, 7.0, 3.8))
    b.box("glass", (x1 + 0.1, 6.0, 2.5), (x1 + 0.18, 6.9, 3.7))
    b.box("trim", (7.4, y1, 2.3), (9.8, y1 + 0.15, 3.7))
    b.box("glass", (7.5, y1 + 0.15, 2.4), (9.7, y1 + 0.22, 3.6))
    for k in range(2):                                              # steps
        b.box("trim", (x1 + 0.15 + k * 0.6, 3.2, PAD_Z), (x1 + 0.75 + k * 0.6, 5.6, PAD_Z + 0.5 - k * 0.2))
    # A cable duct from the cabin up to the deck.
    b.box("metal", (6.0, 7.6, PAD_Z), (6.8, 8.4, 5.4))
    b.cylinder("metal", (3.0, 8.75, 5.0), 0.35, 7.0, axis="X", segments=6)
    b.cylinder("metal", (-0.5, 8.75, 3.0), 0.35, 4.0, segments=6)


def cabin_roof(b):
    """What is lost when the battery is wrecked: the air conditioner, an antenna, a light, sandbags."""
    b.box("metal", (7.2, 3.2, 5.2), (9.4, 5.6, 6.4))
    b.box("grille", (9.4, 3.4, 5.4), (9.5, 5.4, 6.2))
    b.cylinder("metal", (10.0, 7.0, 7.7), 0.08, 5.0, segments=5)
    b.sphere("red", (10.0, 7.0, 10.3), 0.25, 6, 4)
    for x, y in ((-7.0, -10.4), (-4.8, -10.4), (-9.4, -8.6), (-10.4, -6.4)):
        b.box("sandbag", (x - 1.0, y - 0.6, PAD_Z), (x + 1.0, y + 0.6, PAD_Z + 1.0))
    for x, y in ((-6.0, -10.4), (-9.6, -7.5)):
        b.box("sandbag", (x - 1.0, y - 0.6, PAD_Z + 1.0), (x + 1.0, y + 0.6, PAD_Z + 1.9))
    b.box("crate", (-11.2, 9.0, PAD_Z), (-8.8, 11.2, PAD_Z + 1.8))
    b.box("crate", (-11.0, 6.6, PAD_Z), (-9.4, 8.6, PAD_Z + 1.4))


def turret(b):
    """The turntable and the launcher's cradle (TURRET01): a chequer-plate deck, a skirt, a housing with
    two yokes for the hinge, an equipment box."""
    cx, cy, z = TURRET_AT
    b.cylinder("trim", (cx, cy, z + 0.3), 6.6, 0.6, segments=20)
    b.cylinder("turntable", (cx, cy, z + 0.8), 6.2, 0.6, segments=20)
    hx, _, hz = HINGE
    b.box("steel", (hx - 1.0, -2.6, z + 1.1), (hx + 4.0, 2.6, z + 2.8))           # the housing
    b.box("trim", (hx + 4.0, -2.6, z + 1.1), (hx + 4.4, 2.6, z + 2.4))
    for side in (-1, 1):                                                          # the yokes
        y = side * 3.75
        b.prism("steel", [(hx - 1.4, z + 1.1), (hx + 2.4, z + 1.1), (hx + 0.8, hz + 0.9), (hx - 1.0, hz + 0.9)],
                y - 0.3, y + 0.3, cap_surface="steel")
        b.cylinder("trim", (hx, y + side * 0.15, hz), 0.75, 0.9, axis="Y", segments=10)
    b.box("steel", (1.2, 3.6, z + 1.1), (3.6, 5.2, z + 2.6))                       # equipment box
    b.box("grille", (3.6, 3.8, z + 1.4), (3.7, 5.0, z + 2.4))
    b.box("yellow", (-6.3, -0.4, z + 1.1), (-5.8, 0.4, z + 1.3))
    for k in range(4):                                                             # hazard edge at the front
        a = -0.5 + k * 0.33
        b.oriented_box("hazard", (cx + math.cos(a) * 5.9, cy + math.sin(a) * 5.9, z + 1.15), (0.5, 1.9, 0.1),
                       Matrix.Rotation(a, 4, "Z"))


def turret_dish(b):
    """The radar on its mast at the turntable's rear (lost when wrecked)."""
    _, _, z = TURRET_AT
    b.cylinder("metal", (-2.0, -4.6, z + 3.1), 0.22, 4.0, segments=6)
    b.box("steel", (-2.6, -5.2, z + 1.1), (-1.4, -4.0, z + 1.9))
    dish(b, "white", (-1.7, -4.6, z + 5.4), 1.7, -0.3, 0.45)


def launcher(b):
    """Eight canisters, four across and two high, in a frame (TURRETEL), level and pointing +X."""
    hx, _, hz = HINGE
    x0, x1, half, row = LAUNCHER
    gap = 0.12
    col = 2 * half / 4
    for i in range(4):
        y = -half + col * (i + 0.5)
        for j in range(2):
            z = hz + 0.35 + row * (j + 0.5)
            b.box("canister", (hx + x0, y - col / 2 + gap, z - row / 2 + gap), (hx + x1, y + col / 2 - gap, z + row / 2 - gap))
            # The front cover: a dark recess and a yellow rim.
            b.box("yellow", (hx + x1, y - col / 2 + 0.25, z - row / 2 + 0.25), (hx + x1 + 0.1, y + col / 2 - 0.25, z + row / 2 - 0.25))
            b.box("dark", (hx + x1 + 0.1, y - col / 2 + 0.45, z - row / 2 + 0.45), (hx + x1 + 0.15, y + col / 2 - 0.45, z + row / 2 - 0.45))
    zt = hz + 0.35 + 2 * row
    for x in (x0 - 0.1, (x0 + x1) / 2 - 0.4, x1 - 0.8):                            # the frame's bands
        b.box("trim", (hx + x, -half - 0.2, hz + 0.2), (hx + x + 0.8, half + 0.2, zt + 0.2))
    b.box("steel", (hx + x0 - 0.2, -half - 0.1, hz - 0.5), (hx + x1 - 0.5, half + 0.1, hz + 0.35))  # the base
    b.cylinder("trim", (hx, 0, hz), 0.6, 2 * half + 1.0, axis="Y", segments=10)       # the hinge pin
    for side in (-1, 1):                                                           # lifting lugs
        b.box("steel", (hx + 1.4, side * 1.5 - 0.3, hz - 1.2), (hx + 2.4, side * 1.5 + 0.3, hz - 0.4))


def build_shapes():
    parts = {k: Builder(SURFACES) for k in ("building", "intact", "turret", "turret_intact", "launcher")}
    plinth(parts["building"])
    cabin(parts["building"])
    cabin_roof(parts["intact"])
    turret(parts["turret"])
    turret_dish(parts["turret_intact"])
    launcher(parts["launcher"])
    return parts


def square_pad(name, half, height, uv_half=None):
    """A square concrete pad with a chamfered edge, its texture covering it from above."""
    uv_half = uv_half or half
    bm = bmesh.new()
    outline = [(-half, -half), (half, -half), (half, half), (-half, half)]
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    top = [bm.verts.new((x * 0.97, y * 0.97, height)) for x, y in outline]
    bm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            x, y, _ = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv = ((x + uv_half) / (2 * uv_half), (y + uv_half) / (2 * uv_half))
    return obj


def decal(name, corners):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    return obj


def emblems():
    """The faction's mark on the plinth's front, beside the cabin."""
    x = 8.0 + 0.03
    return [decal("EMBLEM", [(x, -5.0, 1.8), (x, -1.4, 1.8), (x, -1.4, 4.0), (x, -5.0, 4.0)])]


def band(name, centre, radius, z0, z1, segments=20):
    """An open band round a cylinder (house colour), seen from outside."""
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=segments, radius1=radius, radius2=radius, depth=z1 - z0,
                          matrix=Matrix.Translation((centre[0], centre[1], (z0 + z1) / 2)))
    return new_object(name, bm)


def house_colours():
    """The player's colour: a band round the turntable (TURRET01), stripes on the launcher (TURRETEL)."""
    cx, cy, z = TURRET_AT
    on_turret = [band("HOUSECOLOR01", (cx, cy), 6.65, z + 0.15, z + 0.45)]
    hx, _, hz = HINGE
    x0, x1, half, row = LAUNCHER
    zt = hz + 0.35 + 2 * row
    on_launcher = []
    for k, side in enumerate((-1, 1)):
        y = side * (half + 0.22)
        quad = [(hx + 1.2, y, hz + 0.6), (hx + 2.4, y, hz + 0.6), (hx + 2.4, y, zt - 0.1), (hx + 1.2, y, zt - 0.1)]
        if side < 0:
            quad = list(reversed(quad))
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(v) for v in quad])
        on_launcher.append(new_object(f"HOUSECOLOR0{k + 2}", bm))
    for obj in on_turret + on_launcher:
        obj.data.uv_layers.new(name="UVMap")
    return on_turret, on_launcher


# --- painting (shared with bastion.py) -------------------------------------------------------------

def surface_material(name, spec, tiles):
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
    if name == "glass":
        bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
        bsdf.inputs["Emission Strength"].default_value = 0.0
    return mat


def height_material(top):
    """Emits the height above the ground (0 at the pad, 1 at `top`), for shading walls darker below."""
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


def bake(objects, kind, image, top=HEIGHT_TOP):
    """Bakes into image: kind DIFFUSE (colour only), AO, EMIT (where the windows are) or HEIGHT."""
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
                glow = kind == "EMIT" and mat.name.startswith("glass")
                bsdf.inputs["Emission Strength"].default_value = 1.0 if glow else 0.0
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


def make_objects(builders, surfaces, tiles):
    """Blender objects from the builders, with their surfaces, unwrapped together onto one atlas."""
    objects = {}
    for name, builder in builders.items():
        # Each part stays a closed shape of its own (no merging of touching corners): the game builds
        # shadow volumes from these meshes, and they need closed shapes.
        bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
        obj = new_object(name.upper(), builder.bm)
        for surface, spec in surfaces.items():
            obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, spec, tiles))
        smooth_by_angle(obj, 35)
        objects[name] = obj
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects.values():
        obj.select_set(True)
    bpy.context.view_layer.objects.active = next(iter(objects.values()))
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    return objects


def bake_all(objects, ground, bakes, top):
    """The building's colour, occlusion, windows and height, and the pad's occlusion, as PNGs in `bakes`."""
    os.makedirs(bakes, exist_ok=True)
    for kind, file in (("DIFFUSE", "colour.png"), ("AO", "occlusion.png"), ("EMIT", "windows.png"),
                       ("HEIGHT", "height.png")):
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(objects, kind, image, top)
        save(image, os.path.join(bakes, file))
    plain = bpy.data.materials.new("pad bake")
    plain.use_nodes = True
    ground.data.materials.append(plain)
    image = bpy.data.images.new("pad_occlusion.png", 512, 512)
    bake([ground], "AO", image)
    save(image, os.path.join(bakes, "pad_occlusion.png"))


def house_material():
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    return colour


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "samp_battery_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, f"{PREFIX}_emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))

    objects = make_objects(build_shapes(), SURFACES, tiles)
    ground = square_pad("PAD", PAD_HALF, PAD_Z)
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    bake_all(list(objects.values()), ground, bakes, HEIGHT_TOP)
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, f"{PREFIX}_building.tga"))
    for obj in objects.values():
        textured(obj, baked)
    textured(ground, load_image(os.path.join(tex_dir, f"{PREFIX}_pad.tga")))
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, f"{PREFIX}_emblem.tga")))
    on_turret, on_launcher = house_colours()
    colour = house_material()
    for obj in on_turret + on_launcher:
        obj.data.materials.append(colour)
    return dict(objects=objects, pad=ground, emblems=marks, house_turret=on_turret, house_launcher=on_launcher)


# --- writing the models ----------------------------------------------------------------------------

def moved(data, origin):
    """Mesh data with its vertices in the space of a bone at `origin` (bones are not turned)."""
    data = dict(data)
    data["verts"] = [tuple(v[i] - origin[i] for i in range(3)) for v in data["verts"]]
    return data


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked (still fighting: the launcher stays)."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    turret_bone = model.bone("TURRET01", w3d.CHASSIS, TURRET_AT)
    hinge_rel = tuple(HINGE[i] - TURRET_AT[i] for i in range(3))
    el_bone = model.bone("TURRETEL", turret_bone, hinge_rel)
    x0, x1, half, row = LAUNCHER
    col = 2 * half / 4
    for k, (i, j) in enumerate(((0, 1), (3, 1), (0, 0), (3, 0))):
        y = -half + col * (i + 0.5)
        z = 0.35 + row * (j + 0.5)
        model.bone(f"WEAPONA0{k + 1}", el_bone, (x1 + 0.4, y, z))
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    objects = parts["objects"]
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(objects["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(objects["intact"]), texture=texture)
        model.mesh("DISH", turret_bone, **moved(mesh_data(objects["turret_intact"]), TURRET_AT), texture=texture)
    model.mesh("TURRET", turret_bone, **moved(mesh_data(objects["turret"]), TURRET_AT), texture=texture)
    model.mesh("LAUNCHER", el_bone, **moved(mesh_data(objects["launcher"]), HINGE), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["house_turret"]:
        model.mesh(obj.name, turret_bone, **moved(mesh_data(obj), TURRET_AT), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
    for obj in parts["house_launcher"]:
        model.mesh(obj.name, el_bone, **moved(mesh_data(obj), HINGE), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

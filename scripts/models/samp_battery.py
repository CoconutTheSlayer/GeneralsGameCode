"""The European SAMP/T Battery, modelled in Blender and written as W3D models for the game: no building,
a launcher of eight missile canisters on a low steel turntable dug in behind a horseshoe revetment of
packed earth with a sandbag crest, a square phased-array radar panel on a short lattice mast set into the
berm's back, and a generator trailer, cable drums and crates at the opening (after a concept painted in
the game's style). Everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/samp_battery.py

Painted as the Command Centre (command_centre.py): samp_battery_paint.py paints small tiling surfaces,
Blender projects them onto the model and bakes them with the ambient occlusion into one texture; the
painter adds grime and makes the damaged, wrecked and night versions, and paints the ground (an earth
patch cut out by its alpha, not a square pad). Six models: EUSAMP (intact), _D, _E (no radar, generator
or clutter), each with a night version (_N, _DN, _EN).

Bones (as the USA's Patriot, ABPATRIOT, which the game's INI names):
    TURRET01               the turntable, turning about Z
    TURRETEL               the launcher's hinge, a child of TURRET01, pitching about Y; the launcher is
                           modelled level, pointing +X, and the game raises it (NaturalTurretPitch 45)
    WEAPONA01..WEAPONA04   where the missiles leave the canisters (WeaponLaunchBone/WeaponFireFXBone WeaponA)

The footprint is the USA's (a cylinder of radius 12, 14 high); the berm reaches 12.9, the ground 14.
The shared machinery below (Builder, baking, writing) is also the Artillery Bastion's and the Funds Office's.
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

NAME = "EUSAMP"
PREFIX = "eusa"
PAD_Z = 0.05                             # the ground patch, just over the terrain
PAD_HALF = 14.0
TEXTURE_SIZE = 1024
HEIGHT_TOP = 14.0
# Surfaces: (tile painted by samp_battery_paint.py, units per tile) or a plain colour.
SURFACES = {
    "earth": ("tile_earth", 8.0), "concrete": ("tile_concrete", 6.0), "trim": ("tile_trim", 8.0),
    "metal": ("tile_metal", 4.0), "sandbag": ("tile_sandbag", 3.0), "hazard": ("tile_hazard", 2.0),
    "grille": ("tile_grille", 2.0), "crate": ("tile_crate", 3.0), "steel": ("tile_steel", 8.0),
    "canister": ("tile_canister", 3.4), "turntable": ("tile_turntable", 4.0), "array": ("tile_array", 4.9),
    "olive": ("tile_olive", 4.0), "drum": ("tile_drum", 2.0), "wood": (120, 92, 60),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46), "red": (196, 52, 40), "white": (226, 228, 230),
}

TURRET_AT = (0.0, 0.0, 0.6)              # TURRET01, on the turntable's concrete footing
HINGE = (-4.0, 0.0, 5.0)                 # TURRETEL, in the world
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


# --- the battery -----------------------------------------------------------------------------------

def sweep(b, surface, profile, centre, a0, a1, steps, cap_surface=None):
    """A closed side profile (r, z) swept round `centre` from angle a0 to a1 (radians), capped at both ends:
    a berm, a ring wall. One closed shape, so its shadow volume holds."""
    def make(bm):
        rings = []
        for k in range(steps + 1):
            a = a0 + (a1 - a0) * k / steps
            c, s = math.cos(a), math.sin(a)
            rings.append([bm.verts.new((centre[0] + r * c, centre[1] + r * s, z)) for r, z in profile])
        n = len(profile)
        for k in range(steps):
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((rings[k][i], rings[k][j], rings[k + 1][j], rings[k + 1][i]))
        make.ends = (bm.faces.new(list(reversed(rings[0]))), bm.faces.new(rings[-1]))
    before = set(b.bm.faces)
    make(b.bm)
    for face in set(b.bm.faces) - before:
        face.material_index = b.index[cap_surface if face in make.ends and cap_surface else surface]


def sandbag_row(b, centre, radius, a0, a1, z, size=(1.7, 1.0, 0.55), offset=0.0):
    """Sandbags laid end to end along an arc (one closed box each)."""
    length = size[0]
    count = max(1, int(abs(a1 - a0) * radius / (length * 0.98)))
    for k in range(count):
        a = a0 + (a1 - a0) * (k + 0.5 + offset) / count
        if not min(a0, a1) <= a <= max(a0, a1):
            continue
        at = (centre[0] + radius * math.cos(a), centre[1] + radius * math.sin(a), z + size[2] / 2)
        b.oriented_box("sandbag", at, (size[1], length * 0.94, size[2]), Matrix.Rotation(a, 4, "Z"))


# The revetment: a horseshoe of packed earth round the turntable, open towards -Y (the cables come in).
BERM = [(8.5, -0.3), (9.1, 2.7), (10.4, 2.9), (12.9, -0.3)]     # (r, z) inside foot, inner top, crest, outside foot
BERM_GAP = (-math.pi / 2, math.radians(34))                       # the opening's direction and half width
RADAR = (7.6, 7.6)                                                # the radar's mast, on the berm's back
GENERATOR = (9.6, -10.0)


def revetment(b):
    """The earth berm with a sandbag crest and sandbag cheeks at the opening, and the turntable's footing."""
    gap, half = BERM_GAP
    a0, a1 = gap + half, gap + 2 * math.pi - half
    sweep(b, "earth", BERM, (0, 0), a0, a1, 40)
    crest = (BERM[1][0] + BERM[2][0]) / 2
    sandbag_row(b, (0, 0), crest, a0 + 0.04, a1 - 0.04, BERM[2][1] - 0.15)
    sandbag_row(b, (0, 0), crest, a0 + 0.1, a1 - 0.1, BERM[2][1] + 0.38, size=(1.6, 0.9, 0.5), offset=0.5)
    # Sandbag cheeks holding the berm's two ends, stepping down.
    for a, side in ((a0, -1), (a1, 1)):
        c, s = math.cos(a), math.sin(a)
        for k, (r0, r1, h) in enumerate(((8.4, 13.0, 1.2), (8.6, 12.0, 2.2), (8.8, 10.8, 3.1))):
            r = (r0 + r1) / 2
            ta = a + side * 0.035
            b.oriented_box("sandbag", (r * math.cos(ta), r * math.sin(ta), h / 2 - 0.3 + 0.0),
                           (r1 - r0, 1.1, h + 0.6 - k * 0.0), Matrix.Rotation(a, 4, "Z"))
    # The concrete footing of the turntable, a cable trench cover across the floor.
    b.cylinder("concrete", (0, 0, 0.15), 7.0, 0.9, segments=24)
    b.oriented_box("metal", (0.0, -9.0, 0.05), (1.2, 5.0, 0.4), Matrix.Identity(4))


def radar(b):
    """The square phased-array panel on a short lattice mast, set into the berm's back, facing the camera
    side (-X, -Y), tilted back, with an equipment cabinet at its foot."""
    x, y = RADAR
    base = 2.6
    b.box("concrete", (x - 1.9, y - 1.9, -0.3), (x + 1.9, y + 1.9, base))
    b.box("trim", (x - 2.0, y - 2.0, base), (x + 2.0, y + 2.0, base + 0.3))
    top = base + 4.6
    for sx in (-1, 1):                                          # four legs leaning in, and cross braces
        for sy in (-1, 1):
            lo = (x + sx * 1.5, y + sy * 1.5, base + 0.3)
            hi = (x + sx * 0.7, y + sy * 0.7, top)
            mid = tuple((p + q) / 2 for p, q in zip(lo, hi))
            length = math.dist(lo, hi)
            lean = math.atan2(math.hypot(hi[0] - lo[0], hi[1] - lo[1]), hi[2] - lo[2])
            heading = math.atan2(hi[1] - lo[1], hi[0] - lo[0])
            b.oriented_box("steel", mid, (0.3, 0.3, length),
                           Matrix.Rotation(heading, 4, "Z") @ Matrix.Rotation(-lean, 4, "Y"))
    for z, w in ((base + 1.8, 1.25), (base + 3.6, 0.95)):
        for sx in (-1, 1):
            b.box("steel", (x + sx * w - 0.1, y - w, z), (x + sx * w + 0.1, y + w, z + 0.2))
            b.box("steel", (x - w, y + sx * w - 0.1, z), (x + w, y + sx * w + 0.1, z + 0.2))
    b.box("steel", (x - 1.0, y - 1.0, top), (x + 1.0, y + 1.0, top + 0.5))   # the slewing head
    b.cylinder("trim", (x, y, top + 0.75), 0.7, 0.5, segments=10)
    # The panel: a frame round the array face, a back box; turned to face (-X, -Y), tilted back.
    face = math.radians(-135)
    turn = Matrix.Rotation(face, 4, "Z") @ Matrix.Rotation(math.radians(-18), 4, "Y")
    centre = (x, y, top + 3.4)
    def at(u, v, w):        # u out of the face, v across, w up, in the panel's own frame
        p = turn @ Vector((u, v, w, 1.0))
        return (centre[0] + p[0], centre[1] + p[1], centre[2] + p[2])
    b.oriented_box("steel", at(-0.35, 0, 0), (0.7, 5.4, 5.4), turn)
    b.oriented_box("array", at(0.08, 0, 0), (0.2, 4.9, 4.9), turn)
    b.oriented_box("trim", at(-0.9, 0, -0.6), (0.6, 3.0, 2.6), turn)       # electronics behind
    b.oriented_box("steel", at(-0.6, 0, -2.6), (1.0, 1.0, 1.4), turn)      # the yoke down to the head
    b.sphere("red", (x, y, top + 6.55), 0.22, 6, 4)
    # A cabinet and a ladder at the mast's foot.
    b.box("steel", (x + 2.1, y - 1.2, -0.2), (x + 3.5, y + 1.2, 2.4))
    b.box("grille", (x + 3.5, y - 0.9, 0.8), (x + 3.6, y + 0.9, 2.0))


def generator(b):
    """A generator trailer at the opening: body, louvres, a towbar and wheels; cable drums and crates."""
    x, y = GENERATOR
    b.box("olive", (x - 2.4, y - 1.3, 0.9), (x + 2.4, y + 1.3, 3.2))
    b.box("trim", (x - 2.5, y - 1.4, 3.2), (x + 2.5, y + 1.4, 3.45))
    b.box("grille", (x + 2.4, y - 0.9, 1.3), (x + 2.5, y + 0.9, 2.8))
    b.box("grille", (x - 1.8, y - 1.4, 1.5), (x - 0.2, y - 1.3, 2.7))
    b.box("dark", (x - 2.2, y - 1.0, 0.6), (x + 2.2, y + 1.0, 0.9))
    b.cylinder("metal", (x + 1.4, y + 0.5, 3.9), 0.18, 1.0, segments=6)     # the exhaust
    b.box("steel", (x - 4.2, y - 0.15, 0.6), (x - 2.4, y + 0.15, 0.85))      # the towbar
    for sy in (-1, 1):
        b.cylinder("dark", (x + 0.4, y + sy * 1.15, 0.6), 0.6, 0.35, axis="Y", segments=10)
    for i, (cx, cy) in enumerate(((-10.6, 9.0), (-8.6, 10.6))):              # cable drums
        b.cylinder("drum", (cx, cy, 0.95), 1.0, 1.0, axis="Y" if i else "X", segments=12)
        b.cylinder("wood", (cx, cy, 0.95), 1.25, 0.2, axis="Y" if i else "X", segments=12)
    for cx, cy, h in ((-10.4, -9.6, 1.4), (-8.5, -10.6, 1.4), (-9.6, -10.0, 2.8)):
        b.box("crate", (cx - 0.9, cy - 0.7, h - 1.4), (cx + 0.9, cy + 0.7, h))
    b.box("crate", (11.0, 7.2, 0.0), (12.4, 9.2, 1.3))


def build_shapes():
    parts = {k: Builder(SURFACES) for k in ("building", "intact", "turret", "launcher")}
    revetment(parts["building"])
    radar(parts["intact"])
    generator(parts["intact"])
    turret(parts["turret"])
    launcher(parts["launcher"])
    return parts


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


def decal(name, corners):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    return obj


def flat_ground(name, half, z):
    """A flat square of ground, its texture covering it from above; the painter cuts its outline with the
    alpha (the shader tests it), so the ground can be any shape: an earth patch, an apron."""
    bm = bmesh.new()
    bm.faces.new([bm.verts.new((x, y, z)) for x, y in ((-half, -half), (half, -half), (half, half), (-half, half))])
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            x, y, _ = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv = ((x + half) / (2 * half), (y + half) / (2 * half))
    return obj


def emblems():
    """The faction's mark on the generator's side towards the opening."""
    x, y = GENERATOR
    f = y - 1.33
    return [decal("EMBLEM", [(x + 0.2, f, 1.3), (x + 2.1, f, 1.3), (x + 2.1, f, 3.0), (x + 0.2, f, 3.0)])]


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
    ground = flat_ground("PAD", PAD_HALF, PAD_Z)
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

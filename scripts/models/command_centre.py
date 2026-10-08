"""The European Command Centre, modelled in Blender and written as W3D models for the game: an octagonal
control tower with a glass cab and radar dome, a hall with a curved ribbed roof and a machinery deck, a
lattice mast with dishes, and a quonset hangar with the faction's mark, on a concrete pad (after a
concept painted in the game's style). Everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/command_centre.py

How it is painted: command_centre_paint.py paints small tiling surfaces (plaster panels, corrugated
metal, roof deck, door, dome, trim); Blender projects them onto the model, then bakes them and the
ambient occlusion into one texture of the building's own; the painter adds grime and makes the damaged,
wrecked and night versions. Six models use them: EUCMDHQ (intact), _D, _E (wrecked: no dome, mast or
dishes), each with a night version (_N, _DN, _EN) with lit windows.

The footprint is the USA's (120 long, 140 wide, 49 high, centred); new units leave the hangar along
EXITSTART -> EXITEND, towards +X.
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

NAME = "EUCMDHQ"
PAD_Z = 0.8
TEXTURE_SIZE = 1024
EXITSTART, EXITEND = (-18.8, 34.5, 0.3), (50.9, 34.5, 0.3)
# Surfaces: (tile painted by command_centre_paint.py, units per tile) or a plain colour.
SURFACES = {
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "rib": ("tile_rib", 10.0), "deck": ("tile_deck", 16.0),
    "door": ("tile_door", 12.0), "dome": ("tile_dome", 8.0), "metal": ("tile_metal", 6.0),
    "crate": ("tile_crate", 4.0), "sandbag": ("tile_sandbag", 4.0), "hazard": ("tile_hazard", 3.0),
    "grille": ("tile_grille", 3.0),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46),
}
SURFACE = {name: i for i, name in enumerate(SURFACES)}


# --- shapes ----------------------------------------------------------------------------------------

class Builder:
    """Shapes added to a bmesh, each face marked with its surface."""

    def __init__(self):
        self.bm = bmesh.new()

    def add(self, surface, make):
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            face.material_index = SURFACE[surface]

    def box(self, surface, a, b):
        lo = [min(p, q) for p, q in zip(a, b)]
        hi = [max(p, q) for p, q in zip(a, b)]
        centre = [(p + q) / 2 for p, q in zip(lo, hi)]
        size = [q - p for p, q in zip(lo, hi)]
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*size, 1.0))))

    def cylinder(self, surface, centre, radius, length, axis="Z", segments=16, radius2=None, rotate=0.0):
        rot = {"Z": Matrix.Rotation(rotate, 4, "Z"), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
               "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=length, matrix=Matrix.Translation(centre) @ rot))

    def sphere(self, surface, centre, radius):
        self.add(surface, lambda bm: bmesh.ops.create_uvsphere(
            bm, u_segments=12, v_segments=8, radius=radius, matrix=Matrix.Translation(centre)))

    def extrude_profile(self, surface, profile, x0, x1, cap_surface=None):
        """A closed profile (y, z) pushed along x from x0 to x1."""
        def make(bm):
            a = [bm.verts.new((x0, y, z)) for y, z in profile]
            b = [bm.verts.new((x1, y, z)) for y, z in profile]
            n = len(profile)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
            end_a, end_b = bm.faces.new(list(reversed(a))), bm.faces.new(b)
            end_a.material_index = end_b.material_index = SURFACE[cap_surface or surface]
            make.ends = (end_a, end_b)
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            if face not in make.ends:
                face.material_index = SURFACE[surface]


def arc(cy, cz, radius, start, end, steps):
    return [(cy + math.cos(a) * radius, cz + math.sin(a) * radius)
            for a in (start + (end - start) * i / steps for i in range(steps + 1))]


TOWER = (-36.0, -50.0)
HALL = (-44.0, 30.0, -38.0, 14.0, 16.0)          # x0, x1, y0, y1, wall top
HANGAR = (-18.0, 34.0, 41.0, 16.0)               # x0, x1, centre y, radius


def hall(b):
    """The command hall: walls with piers and a yellow band, an inset entrance, a curved ribbed roof over
    the front, a machinery deck behind it."""
    x0, x1, y0, y1, top = HALL
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.6))             # plinth
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 11.4), (x1 + 0.15, y1 + 0.15, 12.2))         # the band
    b.box("trim", (x0 - 0.6, y0 - 0.6, top - 1.6), (x1 + 0.6, y1 + 0.6, top))           # cornice
    for x in (x0, (x0 + x1) / 2, x1):
        for y in (y0, y1):
            b.box("wall", (x - 2.6, y - 2.6, PAD_Z), (x + 2.6, y + 2.6, top + 1.8))
            b.box("trim", (x - 3.0, y - 3.0, top + 1.6), (x + 3.0, y + 3.0, top + 2.4))
    # The curved roof, a segment of a circle, over the front part.
    sag, half = 7.5, 15.0
    radius = (half ** 2 + sag ** 2) / (2 * sag)
    cy, cz = -2.0, top + sag - radius
    span = math.asin(half / radius)
    curve = arc(cy, cz, radius, math.pi / 2 + span, math.pi / 2 - span, 8)
    b.extrude_profile("rib", curve, x0 + 2.0, x1 - 2.0, cap_surface="trim")
    for x in (x0 + 2.0, (x0 + x1) / 2, x1 - 2.6):   # ribs over the curve
        outer = arc(cy, cz, radius + 0.35, math.pi / 2 + span, math.pi / 2 - span, 8)
        b.extrude_profile("trim", outer, x, x + 0.6)
    # The entrance: a portal standing out from the front, double doors, steps.
    b.box("trim", (x1, -14, PAD_Z), (x1 + 3.5, -1, 11.0))
    b.box("dark", (x1 + 3.5, -12, PAD_Z + 1.2), (x1 + 3.7, -3, 8.4))
    b.box("door", (x1 + 3.6, -11.4, PAD_Z + 1.2), (x1 + 3.8, -3.6, 8.0))
    b.box("trim", (x1 + 3.5, -15, 10.4), (x1 + 5.0, 0, 11.4))                       # canopy
    for k in range(3):
        b.box("trim", (x1 + 3.5 + k * 1.2, -12.5, PAD_Z), (x1 + 4.7 + k * 1.2, -2.5, PAD_Z + 1.2 - k * 0.4))
    # Windows: square, framed, along both sides.
    for y, face in ((y1, 1), (y0, -1)):
        for x in range(int(x0) + 8, int(x1) - 4, 8):
            b.box("trim", (x - 0.4, y, 7.6), (x + 3.4, y + face * 0.5, 10.4))
            b.box("glass", (x, y + face * 0.5, 8.0), (x + 3.0, y + face * 0.6, 10.0))
    # The machinery deck: grilled air conditioning, fans, vents, a pipe run, three antennas.
    deck_y0, deck_y1 = y0 + 1, -18.5
    b.box("trim", (x0, y0, top), (x1, y0 + 0.7, top + 1.2))
    for x in (-34.0, -20.0, -6.0):
        b.box("metal", (x - 3.5, deck_y0 + 1, top), (x + 3.5, deck_y0 + 7, top + 3.6))
        b.box("grille", (x - 3.2, deck_y0 + 0.9, top + 0.6), (x + 3.2, deck_y0 + 1.0, top + 3.2))
    for x in (8.0, 20.0):
        b.cylinder("metal", (x, -28, top + 0.9), 3.2, 1.8, segments=8)
        b.cylinder("dark", (x, -28, top + 1.85), 2.6, 0.2, segments=8)
        b.box("metal", (x - 0.15, -30.6, top + 1.9), (x + 0.15, -25.4, top + 2.1))
        b.box("metal", (x - 2.6, -28.15, top + 1.9), (x + 2.6, -27.85, top + 2.1))
    b.cylinder("metal", ((x0 + x1) / 2, deck_y1 + 0.8, top + 0.8), 0.7, x1 - x0 - 8, axis="X", segments=8)
    for x, h in ((-40, 10), (-38, 10), (26, 12)):
        b.cylinder("metal", (x, y0 + 2.5, top + h / 2), 0.2, h, segments=6)


def tower(b):
    """The octagonal control tower: a heavy base, a glass cab, a roof and the radar dome."""
    cx, cy = TOWER
    rot = math.pi / 8
    b.cylinder("trim", (cx, cy, PAD_Z + 1.6), 13.2, 3.2, segments=8, rotate=rot)
    b.cylinder("wall", (cx, cy, (PAD_Z + 22) / 2), 11.0, 22 - PAD_Z, segments=8, rotate=rot)
    b.cylinder("yellow", (cx, cy, 17.0), 11.15, 0.8, segments=8, rotate=rot)
    for k in range(8):
        a = rot + k * math.pi / 4 + math.pi / 8
        x, y = cx + math.cos(a) * 11.0, cy + math.sin(a) * 11.0
        b.box("trim", (x - 0.7, y - 0.7, PAD_Z), (x + 0.7, y + 0.7, 22))
    b.cylinder("trim", (cx, cy, 22.6), 12.6, 1.2, segments=8, rotate=rot)
    b.cylinder("glass", (cx, cy, 26.4), 12.2, 6.4, segments=8, radius2=13.2, rotate=rot)
    for k in range(8):
        a = rot + k * math.pi / 4 + math.pi / 8
        x, y = cx + math.cos(a) * 12.7, cy + math.sin(a) * 12.7
        b.box("trim", (x - 0.45, y - 0.45, 23.2), (x + 0.45, y + 0.45, 29.6))
    b.cylinder("trim", (cx, cy, 30.2), 14.0, 1.4, segments=8, rotate=rot)
    b.box("door", (cx + 10.4, cy - 3, PAD_Z), (cx + 11.4, cy + 3, 8.5))
    b.box("trim", (cx + 10.4, cy - 3.8, 8.5), (cx + 12.4, cy + 3.8, 9.5))


def dome(b):
    cx, cy = TOWER
    b.cylinder("metal", (cx, cy, 31.6), 7.6, 1.6, segments=12)
    b.sphere("dome", (cx, cy, 37.0), 7.4)
    b.cylinder("metal", (cx, cy, 44.6), 0.3, 1.6, segments=6)
    b.sphere("yellow", (cx, cy, 45.6), 0.5)


def annex(b):
    """A two-storey annex behind the hangar, with its own roof machinery."""
    x0, x1, y0, y1, top = -50.0, -24.0, 16.0, 60.0, 12.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.2))
    b.box("trim", (x0 - 0.5, y0 - 0.5, top - 1.2), (x1 + 0.5, y1 + 0.5, top + 0.6))
    b.box("deck", (x0 + 0.5, y0 + 0.5, top), (x1 - 0.5, y1 - 0.5, top + 0.4))
    for y in range(int(y0) + 5, int(y1) - 3, 7):
        b.box("trim", (x1, y - 0.4, 6.0), (x1 + 0.5, y + 3.4, 9.0))
        b.box("glass", (x1 + 0.5, y, 6.4), (x1 + 0.6, y + 3.0, 8.6))
    b.box("metal", (x0 + 4, y0 + 6, top + 0.4), (x0 + 12, y0 + 14, top + 3.4))
    b.box("grille", (x0 + 12, y0 + 6.4, top + 0.8), (x0 + 12.1, y0 + 13.6, top + 3.0))
    b.cylinder("metal", (x0 + 18, y1 - 10, top + 2.4), 2.6, 4.0, segments=10)


def mast(b, x=-52.0, y=-12.0, z0=PAD_Z, z1=48.0):
    """A lattice antenna mast with two dishes."""
    b.box("trim", (x - 3.2, y - 3.2, z0), (x + 3.2, y + 3.2, z0 + 1.8))
    half = 1.8
    for dx, dy in ((-half, -half), (half, -half), (half, half), (-half, half)):
        b.add("metal", lambda bm, dx=dx, dy=dy: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=4, radius1=0.28, radius2=0.14, depth=z1 - z0,
            matrix=Matrix.Translation((x + dx, y + dy, (z0 + z1) / 2))))
    z = z0 + 4.0
    while z < z1 - 3:
        for (ax, ay), (bx, by) in (((-half, -half), (half, -half)), ((half, -half), (half, half)),
                                   ((half, half), (-half, half)), ((-half, half), (-half, -half))):
            b.box("metal", (x + min(ax, bx) - 0.12, y + min(ay, by) - 0.12, z - 0.12),
                  (x + max(ax, bx) + 0.12, y + max(ay, by) + 0.12, z + 0.12))
        z += 5.0
    for zz, radius, facing in ((38.0, 3.8, 0.4), (30.0, 2.8, -1.2)):
        def make(bm, zz=zz, radius=radius, facing=facing):
            m = (Matrix.Translation((x + math.cos(facing) * 2.6, y + math.sin(facing) * 2.6, zz))
                 @ Matrix.Rotation(facing, 4, "Z") @ Matrix.Rotation(-math.pi / 2 + 0.3, 4, "Y"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=radius, radius2=radius * 0.3,
                                  depth=radius * 0.4, matrix=m)
        b.add("dome", make)


def hangar(b):
    """The quonset hangar: corrugated metal between thick arches, a door with hazard stripes to the front."""
    x0, x1, cy, radius = HANGAR
    base = PAD_Z + 1.5
    b.box("trim", (x0, cy - radius - 0.8, PAD_Z), (x1, cy + radius + 0.8, base))
    half = arc(cy, base, radius, math.pi, 0.0, 10)
    b.extrude_profile("rib", half, x0 + 1.0, x1 - 1.0, cap_surface="wall")
    ring_out = arc(cy, base, radius + 1.6, math.pi, 0.0, 10)
    ring_in = arc(cy, base, radius - 0.8, 0.0, math.pi, 10)
    for x in (x0, (x0 + x1) / 2 - 1.0, x1 - 2.4):
        b.extrude_profile("wall" if x != (x0 + x1) / 2 - 1.0 else "trim", ring_out + ring_in, x, x + 2.4)
    hazard_out = arc(cy, base, radius - 0.8, math.pi, 0.0, 10)
    hazard_in = arc(cy, base, radius - 2.0, 0.0, math.pi, 10)
    b.extrude_profile("hazard", hazard_out + hazard_in, x1 - 0.8, x1 - 0.2)
    door = arc(cy, base, radius - 2.0, math.pi, 0.0, 10)
    b.extrude_profile("door", door, x1 - 0.7, x1 - 0.3)
    b.box("dark", (x1 - 0.3, cy - 0.15, base), (x1 - 0.15, cy + 0.15, base + radius - 2.5))
    # A walkway with a railing along the top, as on the USA's.
    b.box("trim", (x0 + 4, cy - 1.6, base + radius - 0.2), (x1 - 6, cy + 1.6, base + radius + 0.4))
    for side in (-1.6, 1.6):
        b.box("metal", (x0 + 4, cy + side - 0.08, base + radius + 1.6), (x1 - 6, cy + side + 0.08, base + radius + 1.8))


def clutter(b):
    """What stands around a base: crates, fuel drums, a sandbag revetment, barriers, floodlights."""
    for x, y, h in ((44, 58, 3.6), (48.5, 58, 3.6), (44, 62, 3.6), (46.2, 60, 7.2)):
        b.box("crate", (x - 2, y - 2, PAD_Z), (x + 2, y + 2, PAD_Z + h if h < 5 else PAD_Z + 3.6))
    b.box("crate", (44.2, 58.2, PAD_Z + 3.6), (48.2, 62.2, PAD_Z + 7.2))
    for x, y in ((-6, 63), (-3, 63), (0, 63), (-4.5, 60.5), (-1.5, 60.5)):
        b.cylinder("trim", (x, y, PAD_Z + 2.0), 1.3, 4.0, segments=6)
    # A sandbag revetment at the corner by the tower.
    ring = [(48, -64), (56, -64), (56, -50), (52, -50)]
    for (ax, ay), (bx, by) in zip(ring, ring[1:]):
        b.box("sandbag", (min(ax, bx) - 1.2, min(ay, by) - 1.2, PAD_Z), (max(ax, bx) + 1.2, max(ay, by) + 1.2, PAD_Z + 3.2))
    for x, y in ((-56, -66), (56, 66), (-56, 66), (34, -64)):
        b.cylinder("metal", (x, y, PAD_Z + 8), 0.35, 16, segments=6)
        b.box("metal", (x - 1.4, y - 0.7, PAD_Z + 15.2), (x + 1.4, y + 0.7, PAD_Z + 16.6))
    for y in range(-60, 0, 7):
        b.box("trim", (55, y - 3, PAD_Z), (57, y + 3, PAD_Z + 2.4))
    # The emblem placard on its stand by the entrance, and the flagpole.
    b.box("trim", (40, -22, PAD_Z), (42.5, -16, PAD_Z + 1.2))
    b.add("trim", lambda bm: bmesh.ops.create_cube(bm, size=1.0, matrix=(
        Matrix.Translation((41.2, -19, PAD_Z + 4.5)) @ Matrix.Rotation(-0.35, 4, "Y") @ Matrix.Diagonal((0.8, 7, 7, 1)))))
    b.cylinder("metal", (38, 24, PAD_Z + 12), 0.3, 24, segments=6)
    b.box("trim", (36.6, 22.6, PAD_Z), (39.4, 25.4, PAD_Z + 1.6))


def build_shapes():
    main, intact = Builder(), Builder()
    hall(main)
    tower(main)
    hangar(main)
    annex(main)
    clutter(main)
    dome(intact)
    mast(intact)
    return main, intact


PAD_OUTLINE = [(-58, -68), (30, -68), (30, -46), (58, -46), (58, 68), (-58, 68)]


def pad():
    """The concrete pad, L-shaped like the game's, with a chamfered edge; painted as one picture."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in PAD_OUTLINE]
    top = [bm.verts.new((x * 0.995, y * 0.995, PAD_Z)) for x, y in PAD_OUTLINE]
    bm.faces.new(top)
    n = len(PAD_OUTLINE)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object("PAD", bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x + 60) / 120.0, (y + 70) / 140.0)
    return obj


def decal(name, corners):
    bm = bmesh.new()
    verts = [bm.verts.new(c) for c in corners]
    bm.faces.new(verts)
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    return obj


def emblems():
    """The faction's mark on the tower's front, on the placard and on the hangar's side."""
    cx, cy = TOWER
    r = 11.05 * math.cos(math.pi / 8) + 0.1
    marks = [decal("EMBLEM", [(cx + r, cy - 3.6, 9.5), (cx + r, cy + 3.6, 9.5), (cx + r, cy + 3.6, 16.5),
                              (cx + r, cy - 3.6, 16.5)])]
    # The placard leans back by 0.35 radians.
    c, s_ = math.cos(-0.35), math.sin(-0.35)
    def lean(y, z):
        dz = z - (PAD_Z + 4.5)
        return (41.2 + 0.42 * c + dz * s_, y, PAD_Z + 4.5 + dz * c - 0.42 * s_)
    marks.append(decal("EMBLEM3", [lean(-22.2, PAD_Z + 1.3), lean(-15.8, PAD_Z + 1.3), lean(-15.8, PAD_Z + 7.7),
                                   lean(-22.2, PAD_Z + 7.7)]))
    x0, x1, cy2, radius = HANGAR
    a0, a1, steps = math.radians(24), math.radians(64), 6
    base = PAD_Z + 1.5
    bm = bmesh.new()
    rows = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        rows.append([bm.verts.new((x, cy2 + math.cos(a) * (radius + 0.12), base + math.sin(a) * (radius + 0.12)))
                     for x in (19.0, 5.0)])
    for i in range(steps):
        bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0]))
    hangar_mark = new_object("EMBLEM2", bm)
    uv = hangar_mark.data.uv_layers.new(name="UVMap")
    for i, poly in enumerate(hangar_mark.data.polygons):
        for li, (u, v) in zip(poly.loop_indices, ((0, i / steps), (1, i / steps), (1, (i + 1) / steps), (0, (i + 1) / steps))):
            uv.data[li].uv = (u, v)
    marks.append(hangar_mark)
    return marks


def house_colours():
    """The player's colour: a band round the tower, stripes on the hangar's arches, the flag."""
    cx, cy = TOWER
    objects = []
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=11.3, radius2=11.3, depth=1.4,
                          matrix=Matrix.Translation((cx, cy, 20.2)) @ Matrix.Rotation(math.pi / 8, 4, "Z"))
    objects.append(new_object("HOUSECOLOR01", bm))
    x0, x1, hy, radius = HANGAR
    bm = bmesh.new()
    for x in (x0 - 0.05, x1 + 0.05):
        outer = arc(hy, PAD_Z + 1.5, radius + 1.7, math.pi, 0.0, 10)
        inner = arc(hy, PAD_Z + 1.5, radius + 0.6, 0.0, math.pi, 10)
        verts = [bm.verts.new((x, y, z)) for y, z in outer + inner]
        n = len(outer)
        for i in range(n - 1):
            quad = [verts[i], verts[i + 1], verts[2 * n - 2 - i], verts[2 * n - 1 - i]]
            # Both ways, so that it shows whichever way the arch faces.
            bm.faces.new(quad)
            bm.faces.new([bm.verts.new(v.co) for v in reversed(quad)])
    objects.append(new_object("HOUSECOLOR02", bm))
    bm = bmesh.new()
    flag = [(38.2, 24.0, 22.5), (38.2, 33.0, 22.5), (38.2, 33.0, 17.5), (38.2, 24.0, 17.5)]
    a = [bm.verts.new(v) for v in flag]
    bm.faces.new(a)
    bm.faces.new([bm.verts.new(v.co) for v in reversed(a)])
    objects.append(new_object("HOUSECOLOR03", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


# --- painting --------------------------------------------------------------------------------------

def surface_material(name, tiles):
    """A surface: its tile projected from all sides in world units, or a plain colour."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    spec = SURFACES[name]
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


def height_material():
    """Emits the height above the ground (0 at the pad, 1 at the top), for shading walls darker below."""
    mat = bpy.data.materials.get("height") or bpy.data.materials.new("height")
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    nodes.clear()
    geometry = nodes.new("ShaderNodeNewGeometry")
    xyz = nodes.new("ShaderNodeSeparateXYZ")
    scale = nodes.new("ShaderNodeMath")
    scale.operation = "DIVIDE"
    scale.inputs[1].default_value = 46.0
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


def bake(objects, kind, image):
    """Bakes into image: kind DIFFUSE (colour only), AO, EMIT (where the windows are) or HEIGHT."""
    saved = None
    if kind == "HEIGHT":
        mat = height_material()
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
    bake = scene.render.bake
    bake.margin = 8
    bake.use_pass_direct = bake.use_pass_indirect = False
    bake.use_pass_color = True
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


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, "eucc_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "command_centre_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, "eucc_emblem.tga"), os.path.join(tex_dir, "eucc_emblem.tga"))

    main, intact = build_shapes()
    objects = []
    for name, builder in (("BUILDING", main), ("INTACT", intact)):
        bmesh.ops.remove_doubles(builder.bm, verts=builder.bm.verts, dist=0.001)
        bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
        obj = new_object(name, builder.bm)
        for surface in SURFACES:
            obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, tiles))
        smooth_by_angle(obj, 35)
        objects.append(obj)
    # One texture of the building's own: unwrap the building and its intact-only parts together.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    bakes = os.path.join(BUILD, "eucc_bakes")
    os.makedirs(bakes, exist_ok=True)
    ground = pad()
    for kind, file in (("DIFFUSE", "colour.png"), ("AO", "occlusion.png"), ("EMIT", "windows.png"),
                       ("HEIGHT", "height.png")):
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(objects, kind, image)
        save(image, os.path.join(bakes, file))
    # The pad's shading from the buildings standing on it, on its own picture.
    plain = bpy.data.materials.new("pad bake")
    plain.use_nodes = True
    ground.data.materials.append(plain)
    image = bpy.data.images.new("pad_occlusion.png", 512, 512)
    bake([ground], "AO", image)
    save(image, os.path.join(bakes, "pad_occlusion.png"))
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, "eucc_building.tga"))
    for obj in objects:
        textured(obj, baked)
    textured(ground, load_image(os.path.join(tex_dir, "eucc_pad.tga")))
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, "eucc_emblem.tga")))
    banners = house_colours()
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in banners:
        obj.data.materials.append(colour)
    return dict(building=objects[0], intact=objects[1], pad=ground, emblems=marks, banners=banners)


# --- writing the models ----------------------------------------------------------------------------

def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    model.bone("EXITSTART", w3d.CHASSIS, EXITSTART)
    model.bone("EXITEND", w3d.CHASSIS, EXITEND)
    texture = f"eucc_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture="eucc_pad_e.tga" if version == "_E" else "eucc_pad.tga", shadow=False)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture="eucc_emblem.tga", shadow=False)
    for obj in parts["banners"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False)
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def export_all(parts):
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    export_all(parts)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

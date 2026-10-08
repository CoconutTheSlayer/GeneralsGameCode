"""The European Armour Works (war factory), modelled in Blender and written as W3D models for the game: a big
factory hall under a sawtooth (north-light) roof, a steel gatehouse with a raised armoured door over the bay
where the vehicles drive out, a boiler house with two tall stacks, and a repair yard under overhead crane
rails, on ground shaped to the works. The tallest European building. Made the Command Centre's way
(command_centre.py), in the same palette, with yellow only for hazard stripes.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/armour_works.py

Six models: EUFACT (intact), _D, _E (wrecked: no crane bridge, the stacks broken off), each with a night
version (_N, _DN, _EN) with lit windows, skylights and bay.

The footprint is the USA's (106 long, 120 wide, 40 high, centred) and its front is +X, as the USA's (it is
placed facing the camera at -135 degrees). New vehicles are made inside the bay at (-10, -30) and drive out
of the gate along y = -30 to (53, -30) (the parent's DefaultProductionExitUpdate). Vehicles come for repair
under the crane: the DockStart, DockAction, DockEnd and DockWaiting01-09 bones are the USA's places.
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

NAME = "EUFACT"
PREFIX = "euwf"
PAD_Z = 0.8
TEXTURE_SIZE = 1024
PAD_EXTENT = (-56.0, 56.0, -62.0, 62.0)   # what the pad's picture covers (armour_works_paint.EXTENT)
PAD_RECT = (-54.0, 54.0, -60.0, 60.0)
# Bones: the repair dock (RepairDockUpdate finds DockStart, DockAction, DockEnd, DockWaitingNN).
BONES = [
    ("DOCKSTART", (66.9, 16.2, 0.3)), ("DOCKACTION", (46.5, 16.2, 0.3)), ("DOCKEND", (73.1, 16.2, 0.3)),
    ("DOCKWAITING01", (116.5, 44.7, 0.3)), ("DOCKWAITING02", (116.5, 98.8, 0.3)),
    ("DOCKWAITING03", (68.0, 98.8, 0.3)), ("DOCKWAITING04", (14.0, 98.8, 0.3)),
    ("DOCKWAITING05", (-38.8, 98.8, 0.3)), ("DOCKWAITING06", (-96.3, 98.8, 0.3)),
    ("DOCKWAITING07", (-94.0, 40.0, 0.3)), ("DOCKWAITING08", (-94.0, -17.6, 0.3)),
    ("DOCKWAITING09", (-94.0, -65.9, 0.3)),
    # Where new vehicles are made and where they drive to (for reference: the INI holds the points).
    ("EXITSTART", (-10.0, -30.0, 0.3)), ("EXITEND", (53.0, -30.0, 0.3)),
]
# Surfaces: (tile painted by armour_works_paint.py, units per tile) or a plain colour.
SURFACES = {
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "roof": ("tile_roof", 14.0),
    "shutter": ("tile_shutter", 10.0), "girder": ("tile_girder", 6.0), "inside": ("tile_interior", 14.0),
    "metal": ("tile_metal", 6.0), "crate": ("tile_crate", 4.0), "hazard": ("tile_hazard", 3.0),
    "grille": ("tile_grille", 3.0), "concrete": ("tile_concrete", 30.0), "light": ("tile_dome", 8.0),
    "glass": (40, 72, 92), "lamp": (60, 66, 70), "dark": (38, 40, 44), "yellow": (222, 182, 46),
    "red": (196, 52, 40),
}
GLOWING = ("glass", "lamp")   # lit at night


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

    def cylinder(self, surface, centre, radius, length, axis="Z", segments=16, radius2=None, rotate=0.0):
        rot = {"Z": Matrix.Rotation(rotate, 4, "Z"), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
               "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=length, matrix=Matrix.Translation(centre) @ rot))

    def extrude(self, surface, profile, a0, a1, axis="X", cap_surface=None):
        """A closed profile pushed along an axis from a0 to a1: along X the profile is (y, z), along Y (x, z)."""
        def point(a, p, q):
            return (a, p, q) if axis == "X" else (p, a, q)
        ends = []

        def make(bm):
            a = [bm.verts.new(point(a0, p, q)) for p, q in profile]
            b = [bm.verts.new(point(a1, p, q)) for p, q in profile]
            n = len(profile)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
            ends.extend((bm.faces.new(list(reversed(a))), bm.faces.new(b)))
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            face.material_index = self.index[cap_surface if (cap_surface and face in ends) else surface]


def ring(b, surface, x0, x1, y0, y1, z0, z1, width):
    """A frame of four boxes round a rectangle (a cornice or parapet), leaving the middle open."""
    b.box(surface, (x0, y0, z0), (x1, y0 + width, z1))
    b.box(surface, (x0, y1 - width, z0), (x1, y1, z1))
    b.box(surface, (x0, y0 + width, z0), (x0 + width, y1 - width, z1))
    b.box(surface, (x1 - width, y0 + width, z0), (x1, y1 - width, z1))


def railing(b, a, c, z, surface="trim"):
    """A rail with posts from a to c (points in the plane) at height z above the roof at its foot."""
    (ax, ay), (cx, cy) = a, c
    length = math.hypot(cx - ax, cy - ay)
    t = 0.12
    b.box(surface, (min(ax, cx) - t, min(ay, cy) - t, z + 1.6), (max(ax, cx) + t, max(ay, cy) + t, z + 1.85))
    steps = max(1, int(length / 6))
    for i in range(steps + 1):
        x, y = ax + (cx - ax) * i / steps, ay + (cy - ay) * i / steps
        b.box(surface, (x - t, y - t, z), (x + t, y + t, z + 1.7))


def sawtooth(b, x0, x1, y0, y1, top, tooth=12.0, rise=8.0):
    """A north-light roof: teeth along X, each a slope rising towards +X to a tall glazed face."""
    n = max(1, round((x1 - x0) / tooth))
    w = (x1 - x0) / n
    for k in range(n):
        a = x0 + k * w
        b.extrude("roof", [(a, top), (a + w, top), (a + w, top + rise)], y0 - 0.6, y1 + 0.6, axis="Y",
                  cap_surface="trim")
        b.box("trim", (a + w - 0.5, y0 - 0.6, top + rise), (a + w + 0.3, y1 + 0.6, top + rise + 0.6))   # ridge cap
        b.box("glass", (a + w, y0 + 0.6, top + 0.8), (a + w + 0.3, y1 - 0.6, top + rise - 0.6))
        for y in range(int(y0) + 6, int(y1) - 2, 8):                                                   # glazing bars
            b.box("trim", (a + w + 0.3, y - 0.2, top + 0.6), (a + w + 0.5, y + 0.2, top + rise - 0.4))


HALL = (-48.0, 36.0, -56.0, 8.0, 22.0)      # x0, x1, y0, y1, wall top
GATE = (-42.0, -18.0, 17.0)                 # the gate's opening: y0, y1, top
TUNNEL_BACK = -14.0                         # where the drive-through bay ends inside the hall


def hall(b):
    """The factory hall: steel-framed plaster walls under a sawtooth roof, cut through by the vehicle bay."""
    x0, x1, y0, y1, top = HALL
    gy0, gy1, gtop = GATE
    b.box("wall", (x0, y0, PAD_Z), (x1, gy0, top))                     # south of the bay
    b.box("wall", (x0, gy1, PAD_Z), (x1, y1, top))                     # north of it
    b.box("wall", (x0, gy0, PAD_Z), (TUNNEL_BACK, gy1, top))           # behind it
    b.box("wall", (TUNNEL_BACK, gy0, gtop + 2), (x1, gy1, top))        # over it
    # The bay inside: dark linings, lamps that light up at night, a concrete floor.
    b.box("inside", (TUNNEL_BACK, gy0, PAD_Z), (x1, gy0 + 0.3, gtop + 2))
    b.box("inside", (TUNNEL_BACK, gy1 - 0.3, PAD_Z), (x1, gy1, gtop + 2))
    b.box("inside", (TUNNEL_BACK, gy0, PAD_Z), (TUNNEL_BACK + 0.3, gy1, gtop + 2))
    b.box("inside", (TUNNEL_BACK, gy0, gtop + 1.7), (x1, gy1, gtop + 2))
    for x in (-6.0, 8.0, 22.0):
        b.box("lamp", (x - 3, -31.5, gtop + 1.2), (x + 3, -28.5, gtop + 1.7))
    b.box("concrete", (TUNNEL_BACK, gy0, PAD_Z - 0.2), (x1 + 6, gy1, PAD_Z + 0.15))
    # Steel frame: a dark plinth, columns on the long walls, a cornice.
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.6))
    for x in range(int(x0), int(x1) + 1, 12):
        for y, face in ((y0, -1), (y1, 1)):
            b.box("girder", (x - 0.9, y + face * 0.9, PAD_Z), (x + 0.9, y, top + 0.6))
    b.box("trim", (x0 - 0.6, y0 - 0.6, top - 1.0), (x1 + 0.6, y1 + 0.6, top + 0.2))
    # A clerestory of windows high up the south wall, and small ones on the front.
    for x in range(int(x0) + 3, int(x1) - 4, 12):
        b.box("trim", (x, y0 - 0.5, 14.6), (x + 6.4, y0, 18.6))
        b.box("glass", (x + 0.3, y0 - 0.6, 15.0), (x + 6.1, y0 - 0.5, 18.2))
    for y in (-52.0, -1.0):
        b.box("glass", (x1, y, 12.0), (x1 + 0.1, y + 5.0, 16.0))
    sawtooth(b, x0, x1, y0, y1, top)


def gate(b):
    """The armoured gate on the hall's front: a steel gatehouse higher than the roof's eaves, a thick door
    raised into it, hazard stripes on the jambs and the door's edge."""
    x1 = HALL[1]
    gy0, gy1, gtop = GATE
    b.box("girder", (x1, gy0 - 5.0, PAD_Z), (x1 + 4.0, gy0, gtop + 2))      # jambs
    b.box("girder", (x1, gy1, PAD_Z), (x1 + 4.0, gy1 + 5.0, gtop + 2))
    b.box("girder", (x1 - 1.0, gy0 - 6.0, gtop + 2), (x1 + 4.5, gy1 + 6.0, gtop + 13.0))   # the door's housing
    b.box("trim", (x1 - 1.4, gy0 - 6.4, gtop + 13.0), (x1 + 4.9, gy1 + 6.4, gtop + 14.0))
    b.box("metal", (x1 + 1.0, gy0, gtop), (x1 + 3.0, gy1, gtop + 2.0))       # the raised door's lower edge
    b.box("hazard", (x1 + 3.0, gy0, gtop), (x1 + 3.2, gy1, gtop + 1.4))
    for y0_, y1_ in ((gy0 - 1.2, gy0), (gy1, gy1 + 1.2)):
        b.box("hazard", (x1 + 4.0, y0_, PAD_Z), (x1 + 4.2, y1_, 10.0))
    for k in range(3):                                                      # armour plates' seams
        z = gtop + 4.0 + k * 3.0
        b.box("dark", (x1 + 4.5, gy0 - 5.6, z), (x1 + 4.6, gy1 + 5.6, z + 0.25))
    b.box("trim", (x1 + 4.0, gy0, PAD_Z), (x1 + 8.0, gy1, PAD_Z + 0.4))


def buttress(b, x1, y, gtop):
    """A sloped steel buttress beside the gate (a closed wedge)."""
    profile = [(x1, PAD_Z), (x1 + 6.0, PAD_Z), (x1 + 4.0, gtop + 2.0), (x1, gtop + 2.0)]
    b.extrude("girder", profile, y - 1.2, y + 1.2, axis="Y")


def boiler_house(b):
    """The boiler house at the back with its two tall stacks (their lower parts: the tops are intact-only)."""
    x0, x1, y0, y1, top = -52.0, -30.0, 12.0, 38.0, 14.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.4))
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 0.8, top + 0.8, 1.0)
    b.box("roof", (x0 + 0.5, y0 + 0.5, top), (x1 - 0.5, y1 - 0.5, top + 0.3))
    b.box("grille", (x1, 15.0, 4.0), (x1 + 0.2, 21.0, 10.0))
    b.box("shutter", (x1, 25.0, PAD_Z), (x1 + 0.2, 34.0, 9.0))
    b.box("trim", (x1, 24.4, 9.0), (x1 + 0.8, 34.6, 9.8))
    for cx, cy in STACKS:
        b.cylinder("trim", (cx, cy, top + 1.6), 4.0, 3.2, segments=12)
        b.cylinder("girder", (cx, cy, (top + STACK_SPLIT) / 2), 3.0, STACK_SPLIT - top, segments=12)
    # A pipe bridge from the boiler house to the hall.
    b.cylinder("metal", (-41.0, 10.0, 18.0), 0.9, 6.0, axis="Y", segments=8)


STACKS = ((-45.0, 20.0), (-37.0, 31.0))
STACK_SPLIT, STACK_TOP = 40.0, 62.0


def stack_tops(b):
    for cx, cy in STACKS:
        b.cylinder("girder", (cx, cy, (STACK_SPLIT + STACK_TOP) / 2), 2.8, STACK_TOP - STACK_SPLIT, segments=12,
                   radius2=2.5)
        b.cylinder("dark", (cx, cy, STACK_TOP + 0.6), 2.9, 1.2, segments=12)
        for z in (STACK_TOP - 6.0, STACK_TOP - 3.0):                   # red and white bands
            b.cylinder("red", (cx, cy, z), 2.75, 1.4, segments=12)
        for z in (24.0, 34.0, 48.0):                                     # rings with a ladder cage
            b.cylinder("trim", (cx, cy, z), 3.3, 0.5, segments=12)


GANTRY_X = (-24.0, 14.0, 52.0)
GANTRY_Y = (13.0, 55.0)
GANTRY_Z = 24.0


def gantry_frame(b):
    """The crane rails over the repair yard: steel columns carrying two runway girders (they stand when wrecked)."""
    for x in GANTRY_X:
        for y in GANTRY_Y:
            b.box("trim", (x - 1.8, y - 1.8, PAD_Z), (x + 1.8, y + 1.8, PAD_Z + 1.2))
            b.box("girder", (x - 1.1, y - 1.1, PAD_Z), (x + 1.1, y + 1.1, GANTRY_Z))
            b.box("girder", (x - 0.4, y - 3.2, GANTRY_Z - 4.0), (x + 0.4, y + 3.2, GANTRY_Z - 3.2))
    for y in GANTRY_Y:
        b.box("girder", (GANTRY_X[0] - 1.6, y - 1.3, GANTRY_Z), (GANTRY_X[-1] + 1.6, y + 1.3, GANTRY_Z + 2.4))
        b.box("dark", (GANTRY_X[0] - 1.6, y - 0.3, GANTRY_Z + 2.4), (GANTRY_X[-1] + 1.6, y + 0.3, GANTRY_Z + 2.8))


def gantry_bridge(b):
    """The travelling bridge over the repair bay, its trolley, cable and hook (intact-only)."""
    x = 44.0
    z = GANTRY_Z + 2.8
    y0, y1 = GANTRY_Y[0] - 1.6, GANTRY_Y[1] + 1.6
    b.box("girder", (x - 2.2, y0, z), (x + 2.2, y1, z + 2.6))
    for yy in (y0, y1 - 3.0):
        b.box("trim", (x - 2.8, yy, z - 0.6), (x + 2.8, yy + 3.0, z + 3.0))     # end trucks
    b.box("hazard", (x - 2.25, y0 + 3.0, z + 0.4), (x + 2.25, y0 + 5.0, z + 2.2))
    b.box("metal", (x - 2.6, 13.6, z - 1.2), (x + 2.6, 19.0, z + 3.6))        # trolley
    b.box("dark", (x - 0.15, 16.05, 10.0), (x + 0.15, 16.35, z - 1.2))        # cable
    b.box("hazard", (x - 1.0, 15.2, 8.4), (x + 1.0, 17.2, 10.0))               # hook block
    railing(b, (x - 2.0, y0 + 2), (x - 2.0, y1 - 2), z + 2.6)


def booth(b):
    """The yard's control booth: a small steel cabin with windows all round."""
    x0, x1, y0, y1, top = 20.0, 32.0, 46.0, 56.0, 7.5
    b.box("trim", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("glass", (x0 - 0.1, y0 + 1, 4.2), (x1 + 0.1, y1 - 1, 6.6))
    b.box("glass", (x0 + 1, y0 - 0.1, 4.2), (x1 - 1, y1 + 0.1, 6.6))
    b.box("roof", (x0 - 0.6, y0 - 0.6, top), (x1 + 0.6, y1 + 0.6, top + 0.5))


def clutter(b):
    """Crates, drums, a spare engine pack, a stack of track links, floodlights, barriers along the lane."""
    for x, y, h in ((-22, 42, 3.6), (-22, 46.2, 3.6), (-17.8, 42, 3.6), (-22, 42, 7.2)):
        b.box("crate", (x - 2, y - 2, PAD_Z if h < 5 else PAD_Z + 3.6), (x + 2, y + 2, PAD_Z + 3.6 if h < 5 else PAD_Z + 7.2))
    for x, y in ((-20, 24), (-17.2, 24), (-20, 27), (-17.2, 27), (-18.6, 29.8)):
        b.cylinder("trim", (x, y, PAD_Z + 2.0), 1.3, 4.0, segments=6)
    b.box("metal", (0, 40, PAD_Z), (8, 46, PAD_Z + 3.4))          # an engine pack on a pallet
    b.box("crate", (-0.4, 39.6, PAD_Z), (8.4, 46.4, PAD_Z + 0.6))
    b.box("grille", (8, 40.6, PAD_Z + 1.0), (8.1, 45.4, PAD_Z + 3.0))
    for k in range(4):                                            # track links on a rack
        b.box("dark", (-6 + k * 0.1, 22, PAD_Z + k * 0.7), (2 - k * 0.1, 30, PAD_Z + 0.6 + k * 0.7))
    for x, y in ((53.0, -58.0), (53.0, 59.0), (-30.0, 58.0)):
        b.cylinder("metal", (x, y, PAD_Z + 8), 0.35, 16, segments=6)
        b.box("metal", (x - 1.4, y - 0.7, PAD_Z + 15.2), (x + 1.4, y + 0.7, PAD_Z + 16.6))
    for y in (-46.6, -13.4):                                      # barriers beside the lane
        for x in (44.0, 49.0):
            b.box("hazard", (x, y - 0.8, PAD_Z), (x + 3, y + 0.8, PAD_Z + 1.8))


FENCE = [((-30.0, 59.0), (52.0, 59.0))]
FENCE_HEIGHT = 6.0


def fence_posts(b):
    for (ax, ay), (bx, by) in FENCE:
        length = math.hypot(bx - ax, by - ay)
        steps = max(1, int(length / 8))
        for i in range(steps + 1):
            t = i / steps
            b.cylinder("metal", (ax + (bx - ax) * t, ay + (by - ay) * t, PAD_Z + FENCE_HEIGHT / 2), 0.2, FENCE_HEIGHT, segments=6)


def fence():
    bm = bmesh.new()
    for (ax, ay), (bx, by) in FENCE:
        quad = [(ax, ay, PAD_Z), (bx, by, PAD_Z), (bx, by, PAD_Z + FENCE_HEIGHT), (ax, ay, PAD_Z + FENCE_HEIGHT)]
        bm.faces.new([bm.verts.new(v) for v in quad])
        bm.faces.new([bm.verts.new(v) for v in reversed(quad)])
    obj = new_object("FENCE", bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x + y) / 6.0, (z - PAD_Z) / FENCE_HEIGHT)
    return obj


def build_shapes():
    main, intact = Builder(SURFACES), Builder(SURFACES)
    hall(main)
    gate(main)
    x1 = HALL[1]
    for y in (GATE[0] - 7.2, GATE[1] + 7.2):
        buttress(main, x1, y, GATE[2] + 6)
    boiler_house(main)
    gantry_frame(main)
    booth(main)
    clutter(main)
    fence_posts(main)
    gantry_bridge(intact)
    stack_tops(intact)
    return main, intact


# The ground: shaped to the works (hall, yard and the apron in front of the gate), not a square.
PAD_OUTLINE = [(-53.0, -60.0), (38.0, -60.0), (38.0, -50.0), (55.0, -50.0), (55.0, -10.0), (40.0, -6.0),
               (40.0, 8.0), (55.0, 8.0), (55.0, 61.0), (-34.0, 61.0), (-34.0, 42.0), (-53.0, 42.0)]


def ground(name, outline, z, extent):
    """A flat slab of the given outline with a sloped edge, its picture mapped over `extent`."""
    bm = bmesh.new()
    cx = sum(x for x, _ in outline) / len(outline)
    cy = sum(y for _, y in outline) / len(outline)
    bottom = [bm.verts.new((x + math.copysign(0.8, x - cx), y + math.copysign(0.8, y - cy), -0.2)) for x, y in outline]
    top = [bm.verts.new((x, y, z)) for x, y in outline]
    bm.faces.new(top)
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object(name, bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    ex0, ex1, ey0, ey1 = extent
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, _ = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x - ex0) / (ex1 - ex0), (y - ey0) / (ey1 - ey0))
    return obj


def pad():
    return ground("PAD", PAD_OUTLINE, PAD_Z, PAD_EXTENT)


def decal(name, corners):
    bm = bmesh.new()
    bm.faces.new([bm.verts.new(c) for c in corners])
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    return obj


def emblems():
    """The faction's mark on the gate's housing, the boiler house and the hall's south wall."""
    x = HALL[1] + 4.62
    marks = [decal("EMBLEM", [(x, -34.0, 24.0), (x, -26.0, 24.0), (x, -26.0, 30.5), (x, -34.0, 30.5)])]
    x = -30.0 + 0.12
    marks.append(decal("EMBLEM2", [(x, 15.0, 11.0), (x, 21.0, 11.0), (x, 21.0, 13.6), (x, 15.0, 13.6)]))
    y = HALL[2] - 0.12
    marks.append(decal("EMBLEM3", [(-6.0, y, 6.0), (-14.0, y, 6.0), (-14.0, y, 13.0), (-6.0, y, 13.0)]))
    return marks


def double_sided(bm, quad):
    a = [bm.verts.new(v) for v in quad]
    bm.faces.new(a)
    bm.faces.new([bm.verts.new(v.co) for v in reversed(a)])


def house_colours():
    """The player's colour: a stripe across the gate's housing, panels on the crane's bridge, bands on the stacks."""
    objects = []
    bm = bmesh.new()
    x = HALL[1] + 4.6
    gy0, gy1, gtop = GATE
    double_sided(bm, [(x, gy0 - 5.8, gtop + 3.0), (x, gy1 + 5.8, gtop + 3.0), (x, gy1 + 5.8, gtop + 3.9), (x, gy0 - 5.8, gtop + 3.9)])
    objects.append(new_object("HOUSECOLOR01", bm))
    bm = bmesh.new()
    z = GANTRY_Z + 2.8
    for xx in (44.0 - 2.25, 44.0 + 2.25):
        double_sided(bm, [(xx, 20.0, z + 0.6), (xx, 48.0, z + 0.6), (xx, 48.0, z + 2.0), (xx, 20.0, z + 2.0)])
    objects.append(new_object("HOUSECOLOR02", bm))
    bm = bmesh.new()
    for cx, cy in STACKS:
        bmesh.ops.create_cone(bm, cap_ends=False, segments=12, radius1=3.1, radius2=3.1, depth=1.6,
                              matrix=Matrix.Translation((cx, cy, 30.0)))
    objects.append(new_object("HOUSECOLOR03", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


# --- painting --------------------------------------------------------------------------------------

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


def bake(objects, kind, image, glowing=GLOWING, top=40.0):
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
                glow = kind == "EMIT" and mat.name.split(".")[0] in glowing
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


def bake_building(builders, surfaces, tiles, bakes, top):
    """The building's meshes from their builders, unwrapped together onto one texture, and its bakes."""
    objects = []
    for name, builder in builders:
        # Each part stays a closed shape of its own (no merging of touching corners): shadow volumes.
        bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
        obj = new_object(name, builder.bm)
        for surface, spec in surfaces.items():
            obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, spec, tiles))
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
    for kind, file in (("DIFFUSE", "colour.png"), ("AO", "occlusion.png"), ("EMIT", "windows.png"),
                       ("HEIGHT", "height.png")):
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(objects, kind, image, top=top)
        save(image, os.path.join(bakes, file))
    return objects


def bake_pad(ground, bakes):
    plain = bpy.data.materials.new("pad bake")
    plain.use_nodes = True
    ground.data.materials.append(plain)
    image = bpy.data.images.new("pad_occlusion.png", 512, 512)
    bake([ground], "AO", image)
    save(image, os.path.join(bakes, "pad_occlusion.png"))


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "armour_works_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    for name in ("emblem", "fence"):
        shutil.copy(os.path.join(tiles, name + ".tga"), os.path.join(tex_dir, f"{PREFIX}_{name}.tga"))

    main, intact = build_shapes()
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    ground = pad()
    objects = bake_building((("BUILDING", main), ("INTACT", intact)), SURFACES, tiles, bakes, 62.0)
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
    wire = fence()
    textured(wire, load_image(os.path.join(tex_dir, f"{PREFIX}_fence.tga")))
    return dict(building=objects[0], intact=objects[1], pad=ground, emblems=marks, banners=banners, fence=wire)


# --- writing the models ----------------------------------------------------------------------------

def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    for bone, at in BONES:
        model.bone(bone, w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    if version != "_E":
        model.mesh("FENCE", w3d.CHASSIS, **mesh_data(parts["fence"]), texture=f"{PREFIX}_fence.tga", **flat)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["banners"]:
        if version == "_E" and obj.name == "HOUSECOLOR02":
            continue   # it was on the gantry's bridge
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
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

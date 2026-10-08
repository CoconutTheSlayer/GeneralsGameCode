"""The European Armour Works (war factory), modelled in Blender and written as W3D models for the game, after
a concept painted in the game's style: a tall assembly block with a wide open drive-through bay, two gabled
workshop halls with skylights, a ventilation tower, and an open repair yard under a travelling gantry crane,
on a concrete pad. Made the Command Centre's way (command_centre.py), and in the same paint.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/armour_works.py

Six models: EUFACT (intact), _D, _E (wrecked: no gantry bridge, roof machinery or tower fans), each with a
night version (_N, _DN, _EN) with lit windows and a lit bay.

The footprint is the USA's (106 long, 120 wide, 40 high, centred) and its front is +X, as the USA's (it is
placed facing the camera at -135 degrees). New vehicles are made inside the bay at (-10, -30) and drive out
of its open door along y = -30 to (53, -30) (the parent's DefaultProductionExitUpdate). Vehicles come for
repair to the gantry: the DockStart, DockAction, DockEnd and DockWaiting01-09 bones are the USA's places.
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


def railing(b, a, c, z, surface="yellow"):
    """A rail with posts from a to c (points in the plane) at height z above the roof at its foot."""
    (ax, ay), (cx, cy) = a, c
    length = math.hypot(cx - ax, cy - ay)
    t = 0.12
    b.box(surface, (min(ax, cx) - t, min(ay, cy) - t, z + 1.6), (max(ax, cx) + t, max(ay, cy) + t, z + 1.85))
    steps = max(1, int(length / 6))
    for i in range(steps + 1):
        x, y = ax + (cx - ax) * i / steps, ay + (cy - ay) * i / steps
        b.box(surface, (x - t, y - t, z), (x + t, y + t, z + 1.7))


def gable(b, x0, x1, y0, y1, wall, rise, overhang=0.8, skylights=(), along="X"):
    """A gabled roof over a rectangle, the ridge along X (or Y), with skylight strips on its slopes."""
    if along == "X":
        a0, a1, s0, s1 = x0 - overhang, x1 + overhang, y0, y1
    else:
        a0, a1, s0, s1 = y0 - overhang, y1 + overhang, x0, x1
    mid = (s0 + s1) / 2
    eave = 0.6
    outer = [(s0 - overhang, wall - eave * 0.5), (mid, wall + rise), (s1 + overhang, wall - eave * 0.5),
             (s1 + overhang, wall - eave * 0.5 - 0.6), (mid, wall + rise - 0.6), (s0 - overhang, wall - eave * 0.5 - 0.6)]
    b.extrude("roof", outer, a0, a1, axis=along, cap_surface="trim")
    # The gable ends: walls up to the ridge.
    tri = [(s0, wall), (s1, wall), (mid, wall + rise - 0.3)]
    for a in ((x0, x0 + 0.6) if along == "X" else (y0, y0 + 0.6)), ((x1 - 0.6, x1) if along == "X" else (y1 - 0.6, y1)):
        b.extrude("wall", tri, a[0], a[1], axis=along)
    # Skylights: raised glazed strips on both slopes, sitting on the roof.
    for foot in (s0, s1):
        edge = foot - overhang if foot == s0 else foot + overhang

        def roof_z(s):
            return wall - eave * 0.5 + (rise + eave * 0.5) * (s - edge) / (mid - edge)
        sa, sb = foot + (mid - foot) * 0.35, foot + (mid - foot) * 0.6
        quad = [(sa, roof_z(sa) - 0.1), (sb, roof_z(sb) - 0.1), (sb, roof_z(sb) + 0.45), (sa, roof_z(sa) + 0.45)]
        for c0, c1 in skylights:
            b.extrude("glass", quad, c0, c1, axis=along, cap_surface="trim")


def bay(b):
    """The assembly block: a tall hall open at its front (+X) for the vehicles, with a hazard-striped frame,
    the faction's mark over the door, piers, a yellow band, a parapet and roof machinery."""
    x0, x1, y0, y1, top = -16.0, 46.0, -44.0, -16.0, 26.0
    oy0, oy1, oz = -41.0, -19.0, 18.0          # the opening
    b.box("wall", (x0, y0, PAD_Z), (x1, oy0, top))              # side walls
    b.box("wall", (x0, oy1, PAD_Z), (x1, y1, top))
    b.box("wall", (x0, oy0, PAD_Z), (x0 + 3, oy1, top))         # back wall
    b.box("wall", (x1 - 3, oy0, oz), (x1, oy1, top))            # over the door
    b.box("trim", (x0 + 3, oy0, top - 2), (x1 - 3, oy1, top))   # the roof slab
    # Inside: dark linings so the bay reads as deep, and lamps under the roof that light up at night.
    b.box("inside", (x0 + 3, oy0, PAD_Z), (x1 - 3, oy0 + 0.3, top - 2))
    b.box("inside", (x0 + 3, oy1 - 0.3, PAD_Z), (x1 - 3, oy1, top - 2))
    b.box("inside", (x0 + 3, oy0, PAD_Z), (x0 + 3.3, oy1, top - 2))
    b.box("inside", (x0 + 3, oy0, top - 2.3), (x1 - 3, oy1, top - 2))
    for x in (-6.0, 8.0, 22.0, 36.0):
        b.box("lamp", (x - 3, -31.5, top - 2.8), (x + 3, -28.5, top - 2.3))
    b.box("concrete", (x0 + 3, oy0, PAD_Z - 0.2), (x1 + 2, oy1, PAD_Z + 0.15))   # the floor and its sill
    # The front: piers, the hazard frame round the door, a canopy, the band.
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.4))            # plinth
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 20.2), (x1 + 0.15, oy0, 21.0))             # band
    b.box("yellow", (x0 - 0.15, oy1, 20.2), (x1 + 0.15, y1 + 0.15, 21.0))
    for y in (y0, y1):
        for x in (x0 + 2, (x0 + x1) / 2, x1 - 2):
            b.box("wall", (x - 2.2, y - 2.0, PAD_Z), (x + 2.2, y + 2.0, top + 1.4))
            b.box("trim", (x - 2.6, y - 2.4, top + 1.2), (x + 2.6, y + 2.4, top + 2.0))
    b.box("hazard", (x1, oy0 - 1.4, PAD_Z), (x1 + 0.8, oy0, oz + 1.4))
    b.box("hazard", (x1, oy1, PAD_Z), (x1 + 0.8, oy1 + 1.4, oz + 1.4))
    b.box("hazard", (x1, oy0, oz), (x1 + 0.8, oy1, oz + 1.4))
    b.box("trim", (x1 - 0.5, y0 - 0.5, top - 1.2), (x1 + 1.4, y1 + 0.5, top + 0.4))   # cornice
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top, top + 1.4, 1.0)      # parapet
    # Small windows high on the sides.
    for y, face in ((y0, -1), (y1, 1)):
        for x in range(-8, 42, 9):
            b.box("trim", (x - 0.3, y, 13.6), (x + 4.3, y + face * 0.4, 17.4))
            b.box("glass", (x, y + face * 0.4, 14.0), (x + 4.0, y + face * 0.5, 17.0))



def hall_south(b):
    """A long gabled workshop beside the bay, with a roller door and windows."""
    x0, x1, y0, y1, wall = -50.0, 40.0, -59.0, -44.0, 13.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, wall))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.2))
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 10.4), (x1 + 0.15, y1, 11.0))
    gable(b, x0, x1, y0, y1, wall, 5.0, skylights=((-42, -26), (-18, -2), (6, 22)))
    for x in range(int(x0) + 5, int(x1) - 2, 10):     # piers
        b.box("trim", (x - 0.8, y0 - 0.6, PAD_Z), (x + 0.8, y0, wall - 0.4))
    for x in range(int(x0) + 8, int(x1) - 6, 10):     # windows
        b.box("trim", (x - 0.3, y0 - 0.5, 6.6), (x + 5.3, y0, 9.6))
        b.box("glass", (x, y0 - 0.6, 7.0), (x + 5.0, y0 - 0.5, 9.2))
    # A roller door on the front end, framed.
    b.box("trim", (x1, -57.5, PAD_Z), (x1 + 0.8, -45.5, 11.0))
    b.box("shutter", (x1 + 0.8, -56.5, PAD_Z), (x1 + 1.0, -46.5, 10.0))


def hall_back(b):
    """The workshop hall behind the bay and the yard: four gabled bays side by side (a sawtooth skyline)."""
    x0, x1, y0, y1, wall = -50.0, -16.0, -44.0, 42.0, 15.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, wall))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.2))
    b.box("yellow", (x1, -16, 12.2), (x1 + 0.15, y1 + 0.15, 12.8))
    step = (y1 - y0) / 4
    for k in range(4):
        gable(b, x0, x1, y0 + k * step, y0 + (k + 1) * step, wall, 6.0, overhang=0.3,
              skylights=((-46, -22),), along="X")
    # Its front onto the yard: a roller door, windows, piers.
    b.box("trim", (x1, 18.5, PAD_Z), (x1 + 0.8, 35.5, 13.0))
    b.box("shutter", (x1 + 0.8, 19.5, PAD_Z), (x1 + 1.0, 34.5, 12.0))
    for y in (-10.0, 2.0):
        b.box("trim", (x1, y - 0.3, 6.6), (x1 + 0.5, y + 8.3, 10.4))
        b.box("glass", (x1 + 0.5, y, 7.0), (x1 + 0.6, y + 8.0, 10.0))
    for y in (-14.0, 8.0, 16.0, 38.0):
        b.box("trim", (x1, y - 0.8, PAD_Z), (x1 + 0.6, y + 0.8, wall - 0.3))


def tower(b):
    """The ventilation tower on the back corner: a plaster shaft, louvres, a fan deck, a ladder."""
    x0, x1, y0, y1, top = -53.0, -39.0, 42.0, 58.0, 34.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.4))
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 27.0), (x1 + 0.15, y1 + 0.15, 27.8))
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 1.0, top + 0.8, 1.0)
    for y in (45.0, 51.0):                               # louvres on the front and side
        b.box("grille", (x1, y, 22.0), (x1 + 0.2, y + 4.5, 26.0))
    b.box("grille", (-50.0, y0 - 0.2, 22.0), (-42.0, y0, 26.0))
    b.box("trim", (x0 + 0.5, y0 + 0.5, top), (x1 - 0.5, y1 - 0.5, top + 0.3))
    for z in range(4, 33, 2):                            # a ladder up the front
        b.box("metal", (x1 + 0.5, 49.0, z), (x1 + 0.7, 51.0, z + 0.2))
    for y in (49.0, 51.0):
        b.box("metal", (x1 + 0.5, y - 0.1, PAD_Z), (x1 + 0.7, y + 0.1, top))


def annex(b):
    """A low office annex along the back, with windows to the yard."""
    x0, x1, y0, y1, top = -39.0, 12.0, 46.0, 59.0, 10.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.0))
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 1.0, top + 0.8, 1.0)
    b.box("roof", (x0 + 0.5, y0 + 0.5, top), (x1 - 0.5, y1 - 0.5, top + 0.3))
    for x in range(-34, 9, 7):
        b.box("trim", (x - 0.3, y0 - 0.5, 5.0), (x + 4.3, y0, 8.0))
        b.box("glass", (x, y0 - 0.6, 5.4), (x + 4.0, y0 - 0.5, 7.6))
    b.box("glass", (x1, 49, 5.4), (x1 + 0.1, 56, 7.6))
    b.box("dark", (x1, 50.5, PAD_Z), (x1 + 0.3, 54.5, 7.0))   # a door



GANTRY_X = (-10.0, 20.0, 50.0)
GANTRY_Y = (-12.0, 42.0)
GANTRY_Z = 21.0


def gantry_frame(b):
    """The gantry's columns and runway beams over the repair yard (they stand even when wrecked)."""
    for x in GANTRY_X:
        for y in GANTRY_Y:
            b.box("trim", (x - 1.8, y - 1.8, PAD_Z), (x + 1.8, y + 1.8, PAD_Z + 1.2))
            b.box("girder", (x - 1.1, y - 1.1, PAD_Z), (x + 1.1, y + 1.1, GANTRY_Z))
            b.box("girder", (x - 0.4, y - 3.2, GANTRY_Z - 4.0), (x + 0.4, y + 3.2, GANTRY_Z - 3.2))
    for y in GANTRY_Y:
        b.box("girder", (GANTRY_X[0] - 1.6, y - 1.3, GANTRY_Z), (GANTRY_X[-1] + 1.6, y + 1.3, GANTRY_Z + 2.4))
        b.box("yellow", (GANTRY_X[0] - 1.6, y - 1.35, GANTRY_Z + 2.4), (GANTRY_X[-1] + 1.6, y + 1.35, GANTRY_Z + 2.6))


def gantry_bridge(b):
    """The travelling bridge over the repair bay, its trolley, cable and hook."""
    x = 44.0
    z = GANTRY_Z + 2.6
    y0, y1 = GANTRY_Y[0] - 1.6, GANTRY_Y[1] + 1.6
    b.box("girder", (x - 2.2, y0, z), (x + 2.2, y1, z + 2.6))
    for yy in (y0, y1 - 3.0):
        b.box("yellow", (x - 2.8, yy, z - 0.6), (x + 2.8, yy + 3.0, z + 3.0))   # end trucks
    b.box("metal", (x - 2.6, 13.0, z - 1.2), (x + 2.6, 19.0, z + 3.6))           # trolley
    b.box("dark", (x - 0.15, 15.85, 9.0), (x + 0.15, 16.15, z - 1.2))            # cable
    b.box("yellow", (x - 1.0, 15.0, 7.4), (x + 1.0, 17.0, 9.0))                   # hook block
    railing(b, (x - 2.0, y0 + 2), (x - 2.0, y1 - 2), z + 2.6)


def clutter(b):
    """Crates, drums, a spare engine pack, floodlights, barriers along the lane."""
    for x, y, h in ((-12, 32, 3.6), (-12, 36.2, 3.6), (-7.8, 32, 3.6), (-12, 32, 7.2)):
        b.box("crate", (x - 2, y - 2, PAD_Z if h < 5 else PAD_Z + 3.6), (x + 2, y + 2, PAD_Z + 3.6 if h < 5 else PAD_Z + 7.2))
    for x, y in ((-12, -6), (-9.2, -6), (-12, -3), (-9.2, -3), (-10.6, -0.2)):
        b.cylinder("trim", (x, y, PAD_Z + 2.0), 1.3, 4.0, segments=6)
    b.box("metal", (4, 2, PAD_Z), (12, 8, PAD_Z + 3.4))          # an engine pack on a pallet
    b.box("crate", (3.6, 1.6, PAD_Z), (12.4, 8.4, PAD_Z + 0.6))
    b.box("grille", (12, 2.6, PAD_Z + 1.0), (12.1, 7.4, PAD_Z + 3.0))
    for x, y in ((52.0, -58.0), (52.0, 58.0), (-30.0, -16.0)):
        b.cylinder("metal", (x, y, PAD_Z + 8), 0.35, 16, segments=6)
        b.box("metal", (x - 1.4, y - 0.7, PAD_Z + 15.2), (x + 1.4, y + 0.7, PAD_Z + 16.6))
    for x in range(48, 54, 4):                                   # barriers beside the lane
        b.box("trim", (x, -44.8, PAD_Z), (x + 3, -43.2, PAD_Z + 2.0))
        b.box("trim", (x, -16.8, PAD_Z), (x + 3, -15.2, PAD_Z + 2.0))


FENCE = [((12.5, 58.5), (53.0, 58.5))]
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
    for part in (bay, hall_south, hall_back, tower, annex, gantry_frame, clutter, fence_posts):
        part(main)
    intact_only(intact)
    return main, intact


def intact_only(b):
    """What the wrecked building loses: the gantry bridge, roof machinery, tower fans, most skylights."""
    gantry_bridge(b)
    top = 26.0
    b.box("metal", (-8, -38, top), (6, -28, top + 3.6))
    b.box("grille", (6, -37.4, top + 0.5), (6.1, -28.6, top + 3.1))
    for x in (14.0, 26.0):
        b.cylinder("metal", (x, -30, top + 1.0), 3.0, 2.0, segments=8)
        b.cylinder("dark", (x, -30, top + 2.05), 2.4, 0.2, segments=8)
        b.box("metal", (x - 0.15, -32.4, top + 2.1), (x + 0.15, -27.6, top + 2.3))
        b.box("metal", (x - 2.4, -30.15, top + 2.1), (x + 2.4, -29.85, top + 2.3))
    railing(b, (45.5, -43), (45.5, -17), top + 1.4)
    for y in (46.0, 54.0):
        b.box("metal", (-50.5, y - 3.2, 34.3), (-41.5, y + 3.2, 37.4))
        b.cylinder("dark", (-46.0, y, 37.45), 2.8, 0.1, segments=10)
        b.box("metal", (-46.15, y - 2.8, 37.5), (-45.85, y + 2.8, 37.7))
    b.box("metal", (-28, 49, 10.3), (-18, 56, 13.0))
    b.box("grille", (-18, 49.5, 10.6), (-17.9, 55.5, 12.6))
    b.cylinder("metal", (0.0, 52.5, 12.0), 2.4, 3.4, segments=10)


def pad():
    """The concrete pad with a chamfered edge; painted as one picture."""
    x0, x1, y0, y1 = PAD_RECT
    outline = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    top = [bm.verts.new((x * 0.99, y * 0.99, PAD_Z)) for x, y in outline]
    bm.faces.new(top)
    for i in range(4):
        j = (i + 1) % 4
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object("PAD", bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    ex0, ex1, ey0, ey1 = PAD_EXTENT
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x - ex0) / (ex1 - ex0), (y - ey0) / (ey1 - ey0))
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
    """The faction's mark over the bay door, on the tower's front and on the south hall's side."""
    x = 46.0 + 0.12
    marks = [decal("EMBLEM", [(x, -33.0, 19.2), (x, -27.0, 19.2), (x, -27.0, 25.2), (x, -33.0, 25.2)])]
    x = -39.0 + 0.12
    marks.append(decal("EMBLEM2", [(x, 46.5, 14.0), (x, 53.5, 14.0), (x, 53.5, 21.0), (x, 46.5, 21.0)]))
    y = -59.0 - 0.12
    marks.append(decal("EMBLEM3", [(21.0, y, 3.2), (15.0, y, 3.2), (15.0, y, 9.2), (21.0, y, 9.2)]))
    return marks


def double_sided(bm, quad):
    a = [bm.verts.new(v) for v in quad]
    bm.faces.new(a)
    bm.faces.new([bm.verts.new(v.co) for v in reversed(a)])


def house_colours():
    """The player's colour: a band across the bay's front, panels on the gantry bridge, a band on the tower."""
    objects = []
    bm = bmesh.new()
    x = 46.0 + 0.5
    for y0, y1 in ((-44.2, -34.0), (-26.0, -15.8)):
        double_sided(bm, [(x, y0, 23.6), (x, y1, 23.6), (x, y1, 24.6), (x, y0, 24.6)])
    objects.append(new_object("HOUSECOLOR01", bm))
    bm = bmesh.new()
    z = GANTRY_Z + 2.6
    for xx in (44.0 - 2.25, 44.0 + 2.25):
        double_sided(bm, [(xx, -2.0, z + 0.6), (xx, 34.0, z + 0.6), (xx, 34.0, z + 2.0), (xx, -2.0, z + 2.0)])
    objects.append(new_object("HOUSECOLOR02", bm))
    bm = bmesh.new()
    x0, x1, y0, y1 = -53.0, -39.0, 42.0, 58.0
    for quad in ([(x1 + 0.1, y0, 29.0), (x1 + 0.1, y1, 29.0), (x1 + 0.1, y1, 30.4), (x1 + 0.1, y0, 30.4)],
                 [(x0, y0 - 0.1, 29.0), (x1, y0 - 0.1, 29.0), (x1, y0 - 0.1, 30.4), (x0, y0 - 0.1, 30.4)]):
        double_sided(bm, quad)
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
    objects = bake_building((("BUILDING", main), ("INTACT", intact)), SURFACES, tiles, bakes, 40.0)
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

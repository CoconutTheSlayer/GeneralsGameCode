"""The European Joint Command (the strategy centre), modelled in Blender and written as W3D models for the
game: a three-storey headquarters with a glass war room on its roof and a steel entrance bay with the
faction's mark, a quonset hall with a roll-up door, a round gun emplacement, a dome tower and a lattice mast,
on a concrete pad (after a concept painted in the game's style, ~/Projects/eu3d/sg/concept_b.png).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/joint_command.py

Painted the Command Centre's way (command_centre.py): joint_command_paint.py paints small tiling surfaces,
Blender projects them onto the model and bakes them with the ambient occlusion into one texture of the
building's own (eusg_building.tga), and the painter adds grime and makes the damaged, wrecked and night
versions. The models:

    EUSTRAT, _D, _E (wrecked: no dome, mast or war-room roof), each with a night version (_N, _DN, _EN)
    EUSTRAT_G   the bombardment plan's gun, on the round emplacement: bones TURRET01 (turns), TURRETEL
                (elevates), BARREL01 (recoils), MUZZLE01 and the flash MUZZLEFX01
    EUSTRAT_H   the hold-the-line plan: concrete barriers and steel hedgehogs round the pad
    EUSTRAT_S   the search-and-destroy plan: a radar mast on the headquarters' roof

The plans' models are shown by their own draw modules while a plan is active (build_europe.py). The
footprint is the USA's (124 long, 88 wide, 24 high, centred); the front (the entrance) faces -Y.
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

NAME = "EUSTRAT"
PREFIX = "eusg"
PAD_Z = 0.8
TEXTURE_SIZE = 1024
FOOTPRINT = (-62.0, 62.0, -44.0, 44.0)
# Surfaces: (tile painted by joint_command_paint.py, units per tile) or a plain colour.
SURFACES = {
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "rib": ("tile_rib", 10.0), "deck": ("tile_deck", 16.0),
    "door": ("tile_door", 12.0), "dome": ("tile_dome", 8.0), "metal": ("tile_metal", 6.0),
    "crate": ("tile_crate", 4.0), "sandbag": ("tile_sandbag", 4.0), "hazard": ("tile_hazard", 3.0),
    "grille": ("tile_grille", 3.0), "glazing": ("tile_glazing", 6.0), "shutter": ("tile_shutter", 8.0),
    "concrete": ("tile_concrete", 8.0), "skylight": ("tile_glazing", 6.0),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46), "red": (196, 52, 40),
}
# Surfaces that light up at night.
GLOWING = ("glass", "glazing")


# --- shapes ----------------------------------------------------------------------------------------

class Builder:
    """Shapes added to a bmesh, each face marked with its surface (an index into `surfaces`)."""

    def __init__(self, surfaces=SURFACES):
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

    def rod(self, surface, a, b, radius, segments=6, radius2=None):
        """A cylinder from point a to point b."""
        a, b = Vector(a), Vector(b)
        d = b - a
        m = Matrix.Translation((a + b) / 2) @ d.to_track_quat("Z", "Y").to_matrix().to_4x4()
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=d.length, matrix=m))

    def sphere(self, surface, centre, radius, u=12, v=8):
        self.add(surface, lambda bm: bmesh.ops.create_uvsphere(
            bm, u_segments=u, v_segments=v, radius=radius, matrix=Matrix.Translation(centre)))

    def loft(self, surface, bottom, top, cap_surface=None):
        """A closed solid between two outlines of the same number of points (3D, counter-clockwise from above)."""
        def make(bm):
            a = [bm.verts.new(p) for p in bottom]
            b = [bm.verts.new(p) for p in top]
            n = len(a)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
            make.ends = (bm.faces.new(list(reversed(a))), bm.faces.new(b))
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            face.material_index = self.index[cap_surface if (cap_surface and face in make.ends) else surface]

    def extrude(self, surface, profile, a0, a1, axis="X", cap_surface=None):
        """A closed profile pushed along an axis from a0 to a1: along X the profile is (y, z), along Y (x, z)."""
        def at(u, v, a):
            return (a, u, v) if axis == "X" else (u, a, v)
        self.loft(surface, [at(u, v, a0) for u, v in profile], [at(u, v, a1) for u, v in profile], cap_surface)


def arc(cu, cv, radius, start, end, steps):
    return [(cu + math.cos(a) * radius, cv + math.sin(a) * radius)
            for a in (start + (end - start) * i / steps for i in range(steps + 1))]


def ring(b, surface, x0, x1, y0, y1, z0, z1, width):
    """A frame of four boxes round a rectangle (a cornice or parapet), leaving the middle open."""
    b.box(surface, (x0, y0, z0), (x1, y0 + width, z1))
    b.box(surface, (x0, y1 - width, z0), (x1, y1, z1))
    b.box(surface, (x0, y0 + width, z0), (x0 + width, y1 - width, z1))
    b.box(surface, (x1 - width, y0 + width, z0), (x1, y1 - width, z1))


def window(b, x, y, z, normal, width=3.0, height=2.6):
    """A framed window on a wall facing along `normal` ("+X", "-X", "+Y", "-Y"); (x, y) is on the wall."""
    s = 1 if normal[0] == "+" else -1
    if normal[1] == "Y":
        b.box("trim", (x - 0.4, y, z - 0.4), (x + width + 0.4, y + s * 0.45, z + height + 0.4))
        b.box("glass", (x, y + s * 0.45, z), (x + width, y + s * 0.55, z + height))
    else:
        b.box("trim", (x, y - 0.4, z - 0.4), (x + s * 0.45, y + width + 0.4, z + height + 0.4))
        b.box("glass", (x + s * 0.45, y, z), (x + s * 0.55, y + width, z + height))


HQ = (-16.0, 16.0, -20.0, 22.0, 22.0)          # x0, x1, y0, y1, roof
WAR_ROOM = (-11.0, 11.0, -13.0, 15.0, 5.5)      # x0, x1, y0, y1, wall height
HALL = (-58.0, -19.0, -34.0, 22.0, 7.0)         # the quonset hall: x0, x1, y0, y1, wall top
WING = (18.0, 58.0, -6.0, 22.0, 10.0)
DRUM = (36.0, -22.0, 13.0, 13.4)                # the gun emplacement: x, y, radius, top
GUN_AT = (DRUM[0], DRUM[1], DRUM[3] + 0.5)
TOWER = (24.0, 32.0)
MAST = (-54.0, 36.0)


def headquarters(b):
    """The three-storey headquarters with the steel entrance bay to the front."""
    x0, x1, y0, y1, top = HQ
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.6))
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 11.2), (x1 + 0.15, y1 + 0.15, 12.0))
    ring(b, "trim", x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6, top - 1.4, top + 0.6, 1.3)
    b.box("deck", (x0 + 0.7, y0 + 0.7, top), (x1 - 0.7, y1 - 0.7, top + 0.2))
    for x in (x0, x1):
        for y in (y0, y1):
            b.box("wall", (x - 1.6, y - 1.6, PAD_Z), (x + 1.6, y + 1.6, top + 1.2))
            b.box("trim", (x - 2.0, y - 2.0, top + 1.0), (x + 2.0, y + 2.0, top + 1.8))
    for z in (5.0, 15.0):
        for x in (-13.5, -9.5, 6.5, 10.5):
            window(b, x, y0, z, "-Y")
        for x in range(-13, 12, 5):
            window(b, x, y1, z, "+Y")
    for y in range(-16, 19, 6):
        window(b, x1, y, 15.0, "+X")
        window(b, x0, y, 15.0, "-X")
    # The entrance bay: steel, standing out from the front and above the roof, the mark on it.
    b.box("trim", (-6.5, y0 - 2.6, PAD_Z), (6.5, y0, top + 2.4))
    b.box("dark", (-6.9, y0 - 2.9, top + 2.0), (6.9, y0 + 0.4, top + 2.8))
    b.box("yellow", (-6.65, y0 - 2.75, 9.4), (6.65, y0 - 0.2, 10.2))
    b.box("dark", (-3.8, y0 - 2.8, PAD_Z), (3.8, y0 - 2.5, 7.6))
    b.box("door", (-3.3, y0 - 2.95, PAD_Z), (3.3, y0 - 2.7, 7.2))
    b.box("trim", (-5.0, y0 - 5.5, 7.6), (5.0, y0 - 2.6, 8.4))                       # canopy
    for k in range(3):
        b.box("concrete", (-4.5, y0 - 3.8 - k * 1.2, PAD_Z), (4.5, y0 - 2.6 - k * 1.2, PAD_Z + 1.2 - k * 0.4))


def war_room(b, intact):
    """The glass war room on the roof: glazed walls between steel posts, a sloping glass roof (intact only)."""
    x0, x1, y0, y1, h = WAR_ROOM
    z0 = HQ[4] + 0.2
    z1 = z0 + h
    b.box("trim", (x0 - 0.6, y0 - 0.6, z0), (x1 + 0.6, y1 + 0.6, z0 + 0.8))
    b.box("glazing", (x0, y0, z0 + 0.8), (x1, y1, z1))
    for x in (x0, 0.0, x1):
        for y in (y0, y1):
            b.box("trim", (x - 0.5, y - 0.5, z0), (x + 0.5, y + 0.5, z1 + 0.4))
    for y in (y0 + 9.3, y0 + 18.6):
        for x in (x0, x1):
            b.box("trim", (x - 0.5, y - 0.5, z0), (x + 0.5, y + 0.5, z1 + 0.4))
    b.box("trim", (x0 - 0.5, y0 - 0.5, z1), (x1 + 0.5, y1 + 0.5, z1 + 0.7))
    # The sloping roof, glazed, with a steel ridge.
    rise, inset = 3.2, 4.5
    zr = z1 + 0.7
    bottom = [(x0, y0, zr), (x1, y0, zr), (x1, y1, zr), (x0, y1, zr)]
    top = [(x0 + inset, y0 + inset, zr + rise), (x1 - inset, y0 + inset, zr + rise),
           (x1 - inset, y1 - inset, zr + rise), (x0 + inset, y1 - inset, zr + rise)]
    intact.loft("skylight", bottom, top, cap_surface="trim")
    intact.box("metal", (-1.5, y0 + inset + 2, zr + rise), (1.5, y0 + inset + 6, zr + rise + 1.2))   # air vents
    intact.box("metal", (-1.5, y1 - inset - 6, zr + rise), (1.5, y1 - inset - 2, zr + rise + 1.2))


def hall(b):
    """The quonset hall: low walls under a curved ribbed roof, a roll-up door to the front."""
    x0, x1, y0, y1, top = HALL
    cx, half = (x0 + x1) / 2, (x1 - x0) / 2 + 0.6
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.4))
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 5.4), (x1 + 0.15, y1 + 0.15, 6.0))
    sag = 10.0
    radius = (half ** 2 + sag ** 2) / (2 * sag)
    cz = top + sag - radius
    span = math.asin(half / radius)
    curve = arc(cx, cz, radius, math.pi / 2 + span, math.pi / 2 - span, 10)
    b.extrude("rib", curve, y0 - 0.6, y1 + 0.6, axis="Y", cap_surface="wall")
    for y in (y0 - 1.4, y0 + 18.0, y0 + 37.0, y1 - 0.2):      # arches over the roof
        outer = arc(cx, cz, radius + 0.45, math.pi / 2 + span + 0.01, math.pi / 2 - span - 0.01, 10)
        b.extrude("trim", outer, y, y + 1.6, axis="Y")
    # The roll-up door in the front gable, with a hazard frame and a lintel.
    b.box("hazard", (cx - 8.6, y0 - 0.5, PAD_Z), (cx + 8.6, y0 - 0.2, 6.6))
    b.box("shutter", (cx - 7.6, y0 - 0.7, PAD_Z), (cx + 7.6, y0 - 0.3, 6.0))
    b.box("trim", (cx - 9.2, y0 - 1.6, 6.6), (cx + 9.2, y0 - 0.2, 7.4))
    for x in (x0 + 2.5, x1 - 5.5):                         # small windows either side of the door
        window(b, x, y0, 3.2, "-Y", width=3.0, height=2.0)
    for y in range(int(y0) + 6, int(y1) - 4, 9):
        window(b, x0, y, 3.4, "-X", width=3.0, height=2.0)
    # Ventilators along the ridge.
    for y in (y0 + 9, y0 + 27.5, y0 + 46):
        b.cylinder("metal", (cx, y, top + sag + 0.6), 1.4, 1.6, segments=8)
        b.cylinder("dark", (cx, y, top + sag + 1.5), 1.8, 0.3, segments=8)


def wing(b):
    """The east wing: offices with a flat roof, air conditioning and a door; a link to the gun emplacement."""
    x0, x1, y0, y1, top = WING
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.4))
    b.box("yellow", (x0 - 0.15, y0 - 0.15, 7.4), (x1 + 0.15, y1 + 0.15, 8.0))
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 1.0, top + 0.8, 1.2)
    b.box("deck", (x0 + 0.5, y0 + 0.5, top), (x1 - 0.5, y1 - 0.5, top + 0.25))
    for y in range(int(y0) + 3, int(y1) - 3, 6):
        window(b, x1, y, 3.6, "+X")
    for x in range(int(x0) + 26, int(x1) - 3, 6):
        window(b, x, y0, 3.6, "-Y")
    b.box("dark", (x1, 13.0, PAD_Z), (x1 + 0.3, 18.6, 7.0))
    b.box("door", (x1 + 0.2, 13.4, PAD_Z), (x1 + 0.45, 18.2, 6.6))
    b.box("trim", (x1, 12.4, 7.0), (x1 + 2.2, 19.2, 7.8))
    for x, y in ((24.0, 16.0), (52.0, 16.0)):
        b.box("metal", (x - 3, y - 3, top + 0.25), (x + 3, y + 3, top + 3.2))
        b.box("grille", (x - 2.8, y - 3.1, top + 0.8), (x + 2.8, y - 3.0, top + 2.8))
    b.cylinder("metal", (52.0, 4.0, top + 1.2), 2.4, 1.9, segments=8)
    b.cylinder("dark", (52.0, 4.0, top + 2.2), 2.0, 0.2, segments=8)
    # The link from the wing to the emplacement.
    b.box("wall", (28.0, -13.0, PAD_Z), (44.0, y0 + 0.1, 8.0))
    b.box("trim", (27.6, -13.4, 8.0), (44.4, y0 + 0.1, 8.8))


def drum(b):
    """The round gun emplacement: a thick drum with a parapet and the gun's closed hatch on top."""
    x, y, r, top = DRUM
    b.cylinder("wall", (x, y, (PAD_Z + top - 1.6) / 2), r, top - 1.6 - PAD_Z, segments=16)
    b.cylinder("trim", (x, y, PAD_Z + 0.9), r + 0.6, 1.8, segments=16)
    b.cylinder("yellow", (x, y, 9.9), r + 0.12, 0.8, segments=16)
    b.cylinder("trim", (x, y, top - 0.9), r + 0.8, 1.4, segments=16)
    b.cylinder("deck", (x, y, top - 0.1), r + 0.1, 0.4, segments=16)
    b.cylinder("hazard", (x, y, top + 0.15), 7.6, 0.3, segments=16)
    b.cylinder("metal", (x, y, top + 0.3), 6.4, 0.5, segments=16)
    for k in range(4):                                      # the hatch's leaves
        a = k * math.pi / 2 + math.pi / 4
        b.box("dark", (x + math.cos(a) * 3.2 - 0.15, y + math.sin(a) * 3.2 - 0.15, top + 0.5),
              (x + math.cos(a) * 3.2 + 0.15, y + math.sin(a) * 3.2 + 0.15, top + 0.62))
    b.box("dark", (x - 6.4, y - 0.1, top + 0.5), (x + 6.4, y + 0.1, top + 0.6))
    b.box("dark", (x - 0.1, y - 6.4, top + 0.5), (x + 0.1, y + 6.4, top + 0.6))
    for a in (-2.2, -1.6, -0.9, 0.0):                         # vents round the drum, facing the front
        cx, cy = x + math.cos(a) * (r + 0.05), y + math.sin(a) * (r + 0.05)
        b.add("grille", lambda bm, cx=cx, cy=cy, a=a: bmesh.ops.create_cube(bm, size=1.0, matrix=(
            Matrix.Translation((cx, cy, 6.0)) @ Matrix.Rotation(a, 4, "Z") @ Matrix.Diagonal((0.4, 3.0, 2.0, 1)))))
    b.box("dark", (x - 2.4, y - r - 0.3, PAD_Z), (x + 2.4, y - r + 1.0, 6.4))   # a door at the front
    b.box("door", (x - 2.0, y - r - 0.45, PAD_Z), (x + 2.0, y - r + 0.8, 6.0))


def tower(b, intact):
    """The octagonal tower behind the headquarters, its white radar dome intact only."""
    cx, cy = TOWER
    rot = math.pi / 8
    b.cylinder("trim", (cx, cy, PAD_Z + 1.2), 8.6, 2.4, segments=8, rotate=rot)
    b.cylinder("wall", (cx, cy, (PAD_Z + 27) / 2), 7.0, 27 - PAD_Z, segments=8, rotate=rot)
    b.cylinder("yellow", (cx, cy, 20.0), 7.12, 0.8, segments=8, rotate=rot)
    b.cylinder("trim", (cx, cy, 27.6), 8.4, 1.2, segments=8, rotate=rot)
    for z in (9.0, 15.0, 23.0):
        b.box("trim", (cx - 7.3, cy - 1.8, z - 0.4), (cx - 6.6, cy + 1.8, z + 2.6))
        b.box("glass", (cx - 7.4, cy - 1.4, z), (cx - 7.2, cy + 1.4, z + 2.2))
    intact.cylinder("metal", (cx, cy, 28.9), 5.2, 1.4, segments=12)
    intact.sphere("dome", (cx, cy, 33.4), 5.4)
    intact.cylinder("metal", (cx, cy, 39.4), 0.25, 1.4, segments=6)
    intact.sphere("red", (cx, cy, 40.2), 0.45, 8, 6)


def mast(b, x, y, z0=PAD_Z, z1=56.0):
    """A lattice antenna mast with red and white bands and four dishes (the Command Centre's)."""
    b.box("concrete", (x - 3.6, y - 3.6, z0), (x + 3.6, y + 3.6, z0 + 1.8))
    half = 2.0
    for dx, dy in ((-half, -half), (half, -half), (half, half), (-half, half)):
        b.add("metal", lambda bm, dx=dx, dy=dy: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=4, radius1=0.3, radius2=0.15, depth=z1 - z0,
            matrix=Matrix.Translation((x + dx, y + dy, (z0 + z1) / 2))))
    z = z0 + 4.0
    k = 0
    while z < z1 - 2:
        colour = "red" if (k % 2 == 0 and z > z0 + 16) else "metal"
        for (ax, ay), (bx, by) in (((-half, -half), (half, -half)), ((half, -half), (half, half)),
                                   ((half, half), (-half, half)), ((-half, half), (-half, -half))):
            b.box(colour, (x + min(ax, bx) - 0.13, y + min(ay, by) - 0.13, z - 0.13),
                  (x + max(ax, bx) + 0.13, y + max(ay, by) + 0.13, z + 0.13))
        # A diagonal on two faces.
        b.rod("metal", (x - half, y - half, z), (x + half, y - half, z + 5.0), 0.1, 4)
        b.rod("metal", (x - half, y + half, z), (x - half, y - half, z + 5.0), 0.1, 4)
        z += 5.0
        k += 1
    for k, zz in enumerate(range(int(z1) - 10, int(z1), 3)):
        b.box("red" if k % 2 == 0 else "dome", (x - 2.3, y - 2.3, zz), (x + 2.3, y + 2.3, zz + 1.5))
    b.sphere("red", (x, y, z1 + 0.6), 0.6, 8, 6)
    for zz, radius, facing in ((44.0, 3.6, -0.6), (38.0, 3.0, 2.2), (30.0, 2.6, -1.9), (24.0, 2.2, 0.7)):
        def make(bm, zz=zz, radius=radius, facing=facing):
            m = (Matrix.Translation((x + math.cos(facing) * 2.9, y + math.sin(facing) * 2.9, zz))
                 @ Matrix.Rotation(facing, 4, "Z") @ Matrix.Rotation(-math.pi / 2 + 0.3, 4, "Y"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=radius, radius2=radius * 0.3,
                                  depth=radius * 0.4, matrix=m)
        b.add("dome", make)


def clutter(b):
    """Crates, fuel drums, sandbags, floodlights and the flagpole round the front."""
    for x, y, h in ((-14.0, -38.0, 3.6), (-14.0, -34.0, 3.6), (-18.0, -38.0, 3.6)):
        b.box("crate", (x - 1.9, y - 1.9, PAD_Z), (x + 1.9, y + 1.9, PAD_Z + h))
    b.box("crate", (-15.9, -37.8, PAD_Z + 3.6), (-12.3, -34.2, PAD_Z + 6.8))
    for x, y in ((-60.0, -40.0), (-57.4, -40.0), (-58.7, -37.8), (12.0, -40.0), (14.6, -40.0)):
        b.cylinder("trim", (x, y, PAD_Z + 1.8), 1.2, 3.6, segments=6)
    for (ax, ay), (bx, by) in (((18.0, -30.0), (18.0, -38.0)), ((18.0, -38.0), (24.0, -38.0))):
        b.box("sandbag", (min(ax, bx) - 1.2, min(ay, by) - 1.2, PAD_Z), (max(ax, bx) + 1.2, max(ay, by) + 1.2, PAD_Z + 3.0))
    for x, y in ((-61.0, 42.5), (60.5, -42.0), (60.5, 42.5), (-61.0, -42.0)):
        b.cylinder("metal", (x, y, PAD_Z + 7), 0.3, 14, segments=6)
        b.box("metal", (x - 1.2, y - 0.6, PAD_Z + 13.4), (x + 1.2, y + 0.6, PAD_Z + 14.6))
    b.cylinder("metal", (10.0, -30.0, PAD_Z + 11), 0.28, 22, segments=6)               # the flagpole
    b.box("concrete", (8.7, -31.3, PAD_Z), (11.3, -28.7, PAD_Z + 1.4))
    b.box("concrete", (-62.0 + 1, 24.0, PAD_Z), (-40.0, 40.0, PAD_Z + 0.6))          # the generator's plinth
    b.box("metal", (-46.0, 26.0, PAD_Z + 0.6), (-40.5, 38.0, PAD_Z + 5.2))
    b.box("grille", (-40.6, 27.0, PAD_Z + 1.4), (-40.4, 37.0, PAD_Z + 4.6))
    b.cylinder("dark", (-43.0, 30.0, PAD_Z + 6.6), 0.5, 3.0, segments=6)


# --- the battle plans ------------------------------------------------------------------------------

def gun_parts():
    """The bombardment plan's gun, each part in the space of its bone: [(name, parent, offset, builder)]."""
    turret, elevation, barrel = Builder(), Builder(), Builder()
    turret.cylinder("trim", (0, 0, 0.8), 6.4, 1.6, segments=16)
    turret.cylinder("dark", (0, 0, 1.75), 5.6, 0.3, segments=16)
    profile = [(-6.4, 1.9), (3.6, 1.9), (6.4, 4.0), (5.2, 7.8), (-4.6, 7.8), (-6.8, 5.6)]
    turret.extrude("trim", [(x, z) for x, z in profile], -4.4, 4.4, axis="Y", cap_surface="trim")
    turret.box("yellow", (-6.95, -4.5, 5.0), (-6.5, 4.5, 5.6))
    turret.box("metal", (-5.8, -5.6, 2.6), (-1.0, -4.3, 6.4))            # ammunition boxes on the sides
    turret.box("metal", (-5.8, 4.3, 2.6), (-1.0, 5.6, 6.4))
    turret.box("metal", (-3.6, 1.0, 7.8), (-1.0, 3.4, 9.0))              # the commander's sight
    turret.cylinder("glass", (-2.3, 2.2, 9.1), 0.9, 0.3, segments=8)
    elevation.box("trim", (-1.2, -2.6, -2.2), (2.6, 2.6, 2.2))            # the mantlet
    elevation.cylinder("dark", (0, 0, 0), 1.0, 6.2, axis="Y", segments=8)
    barrel.cylinder("metal", (8.2, 0, 0), 0.95, 16.4, axis="X", segments=10)
    barrel.cylinder("metal", (2.0, 0, 0), 1.4, 4.0, axis="X", segments=10)
    barrel.cylinder("dark", (9.5, 0, 0), 1.3, 3.0, axis="X", segments=10)    # the bore evacuator
    barrel.box("dark", (15.6, -1.5, -1.0), (18.0, 1.5, 1.0))                  # the muzzle brake
    return [("TURRET01", None, GUN_AT, turret), ("TURRETEL", "TURRET01", (1.6, 0.0, 5.0), elevation),
            ("BARREL01", "TURRETEL", (2.4, 0.0, 0.0), barrel)]


MUZZLE = (18.2, 0.0, 0.0)  # in the barrel's space


def muzzle_flash(location):
    bm = bmesh.new()
    x0, x1, r = 0.0, 7.0, 2.2
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * r, math.sin(a) * r
        verts = [bm.verts.new(v) for v in ((x0, -c, -s), (x1, -c, -s), (x1, c, s), (x0, c, s))]
        bm.faces.new(verts)
    obj = new_object("MUZZLEFX01", bm, location)
    obj.data.uv_layers.new(name="UVMap")
    uv = obj.data.uv_layers[0]
    for poly in obj.data.polygons:
        for li, t in zip(poly.loop_indices, ((0, 0), (1, 0), (1, 1), (0, 1))):
            uv.data[li].uv = t
    return obj


def barriers(b):
    """Hold the line: concrete barriers round the pad, steel hedgehogs and sandbags by the gaps."""
    profile = [(-1.0, PAD_Z), (1.0, PAD_Z), (0.9, PAD_Z + 0.6), (0.45, PAD_Z + 1.4), (0.35, PAD_Z + 3.0),
               (-0.35, PAD_Z + 3.0), (-0.45, PAD_Z + 1.4), (-0.9, PAD_Z + 0.6)]
    def run(axis, fixed, a0, a1, gaps=()):
        a = a0
        while a + 5.0 <= a1:
            if not any(g0 - 5.0 < a < g1 for g0, g1 in gaps):
                if axis == "X":
                    b.extrude("concrete", [(fixed + u, v) for u, v in profile], a, a + 5.0, axis="X", cap_surface="concrete")
                    b.box("hazard", (a + 0.4, fixed - 0.36, PAD_Z + 3.0), (a + 4.6, fixed + 0.36, PAD_Z + 3.3))
                else:
                    b.extrude("concrete", [(fixed + u, v) for u, v in profile], a, a + 5.0, axis="Y", cap_surface="concrete")
                    b.box("hazard", (fixed - 0.36, a + 0.4, PAD_Z + 3.0), (fixed + 0.36, a + 4.6, PAD_Z + 3.3))
            a += 5.6
    run("X", -42.4, -60.5, 60.5, gaps=((-9.0, 9.0), (-52.0, -24.0)))
    run("Y", 60.4, -40.0, 41.0, gaps=((10.0, 22.0),))
    run("Y", -60.6, -36.0, 22.0)
    for x, y in ((-55.0, -40.0), (-21.0, -40.0), (12.0, -40.0), (58.0, 7.0), (58.0, 25.0)):
        for a, c in ((0.0, 0.0), (math.pi / 3, 1.0), (-math.pi / 3, 1.0)):
            d = Vector((math.cos(a) * 1.9, math.sin(a) * 1.9, 0.0))
            if c:
                d = Vector((d.x * 0.5, d.y * 0.5, 1.6))
            centre = Vector((x, y, PAD_Z + 1.5))
            b.rod("dark", centre - d - Vector((0, 0, 0.0)), centre + d, 0.32, 4)
    for x0, x1 in ((-9.0, -6.0), (6.0, 9.0)):
        b.box("sandbag", (x0, -43.2, PAD_Z), (x1, -41.2, PAD_Z + 2.4))


def search_mast(b):
    """Search and destroy: a telescopic radar mast behind the war room with a phased-array panel."""
    x, y, z = 0.0, 18.6, HQ[4] + 0.2
    b.box("trim", (x - 2.6, y - 2.6, z), (x + 2.6, y + 2.6, z + 1.4))
    b.cylinder("metal", (x, y, z + 8.0), 1.2, 13.4, segments=10)
    b.cylinder("trim", (x, y, z + 14.6), 1.5, 0.6, segments=10)
    b.cylinder("metal", (x, y, z + 18.8), 0.8, 8.4, segments=10)
    b.cylinder("trim", (x, y, z + 23.2), 1.6, 1.0, segments=10)
    # The panel, leaning back, facing the front.
    def panel(bm):
        m = Matrix.Translation((x, y - 0.6, z + 26.8)) @ Matrix.Rotation(-0.35, 4, "X") @ Matrix.Diagonal((14.0, 0.9, 6.4, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    b.add("trim", panel)
    def face(bm):
        m = Matrix.Translation((x, y - 1.25, z + 26.6)) @ Matrix.Rotation(-0.35, 4, "X") @ Matrix.Diagonal((12.8, 0.3, 5.4, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    b.add("grille", face)
    for side in (-1, 1):
        def dish(bm, side=side):
            m = (Matrix.Translation((x + side * 3.4, y + 0.6, z + 17.0)) @ Matrix.Rotation(side * 0.9, 4, "Z")
                 @ Matrix.Rotation(-math.pi / 2 + 0.4, 4, "X"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=2.2, radius2=0.7, depth=0.9, matrix=m)
        b.add("dome", dish)
        b.box("metal", (min(x, x + side * 3.0), y + 0.3, z + 16.6), (max(x, x + side * 3.0), y + 0.9, z + 17.2))
    b.sphere("red", (x, y, z + 30.8), 0.45, 8, 6)
    b.cylinder("metal", (x, y, z + 29.9), 0.15, 1.8, segments=6)


# --- flat parts ------------------------------------------------------------------------------------

PAD_OUTLINE = [(-61.5, -43.5), (61.5, -43.5), (61.5, 43.5), (-61.5, 43.5)]


def pad():
    """The concrete pad with a chamfered edge; painted as one picture."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x * 1.012, y * 1.016, 0.0)) for x, y in PAD_OUTLINE]
    top = [bm.verts.new((x, y, PAD_Z)) for x, y in PAD_OUTLINE]
    bm.faces.new(top)
    n = len(PAD_OUTLINE)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((bottom[i], bottom[j], top[j], top[i]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    obj = new_object("PAD", bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    x0, x1, y0, y1 = FOOTPRINT
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x - x0) / (x1 - x0), (y - y0) / (y1 - y0))
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
    """The faction's mark on the entrance bay and, large, on the wing's roof."""
    y = HQ[2] - 2.68
    top = WING[4] + 0.3
    return [decal("EMBLEM", [(-3.6, y, 11.4), (3.6, y, 11.4), (3.6, y, 18.6), (-3.6, y, 18.6)]),
            decal("EMBLEM2", [(30.0, 0.0, top), (46.0, 0.0, top), (46.0, 16.0, top), (30.0, 16.0, top)])]


def house_colours():
    """The player's colour: a band round the gun emplacement, the hall's front arch, the flag."""
    x, y, r, top = DRUM
    objects = []
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=16, radius1=r + 0.2, radius2=r + 0.2, depth=1.4,
                          matrix=Matrix.Translation((x, y, 7.6)))
    objects.append(new_object("HOUSECOLOR01", bm))
    x0, x1, y0, y1, top = HALL
    cx, half = (x0 + x1) / 2, (x1 - x0) / 2 + 0.6
    sag = 10.0
    radius = (half ** 2 + sag ** 2) / (2 * sag)
    cz = top + sag - radius
    span = math.asin(half / radius)
    bm = bmesh.new()
    yy = y0 - 1.45
    outer = arc(cx, cz, radius + 0.5, math.pi / 2 + span, math.pi / 2 - span, 10)
    inner = arc(cx, cz, radius - 0.6, math.pi / 2 - span, math.pi / 2 + span, 10)
    verts = [bm.verts.new((u, yy, v)) for u, v in outer + inner]
    n = len(outer)
    for i in range(n - 1):
        quad = [verts[i], verts[i + 1], verts[2 * n - 2 - i], verts[2 * n - 1 - i]]
        bm.faces.new(quad)
        bm.faces.new([bm.verts.new(v.co) for v in reversed(quad)])
    objects.append(new_object("HOUSECOLOR02", bm))
    bm = bmesh.new()
    flag = [(10.2, -30.0, 22.5), (10.2, -21.0, 22.5), (10.2, -21.0, 17.5), (10.2, -30.0, 17.5)]
    a = [bm.verts.new(v) for v in flag]
    bm.faces.new(a)
    bm.faces.new([bm.verts.new(v.co) for v in reversed(a)])
    objects.append(new_object("HOUSECOLOR03", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


# --- painting --------------------------------------------------------------------------------------

def surface_material(name, tiles, surfaces=SURFACES):
    """A surface: its tile projected from all sides in world units, or a plain colour."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    spec = surfaces[name]
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


def height_material(top=46.0):
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


def bake(objects, kind, image, glowing=GLOWING, clear=True, top=46.0):
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
    settings.use_clear = clear
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


def solid(name, builder, tiles, location=(0, 0, 0), surfaces=SURFACES):
    """An object from a builder: closed shapes, normals out, every surface's material."""
    # Each part stays a closed shape of its own (no merging of touching corners): the game builds shadow
    # volumes from these meshes, and they need closed shapes.
    bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
    obj = new_object(name, builder.bm, location)
    for surface in surfaces:
        obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, tiles, surfaces))
    smooth_by_angle(obj, 35)
    return obj


def unwrap(objects):
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.003)
    bpy.ops.object.mode_set(mode="OBJECT")


def bake_all(main_objects, prop_objects, ground, bakes, top=46.0, glowing=GLOWING):
    """Bakes the atlas: the building's ambient occlusion without the battle plans' parts standing on it (they
    come and go), then theirs with the building round them; and the pad's occlusion from the building."""
    every = main_objects + prop_objects
    for kind, file in (("DIFFUSE", "colour.png"), ("EMIT", "windows.png"), ("HEIGHT", "height.png")):
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(every, kind, image, glowing=glowing, top=top)
        save(image, os.path.join(bakes, file))
    image = bpy.data.images.new("occlusion.png", TEXTURE_SIZE, TEXTURE_SIZE)
    for obj in prop_objects:
        obj.hide_render = True
    bake(main_objects, "AO", image)
    for obj in prop_objects:
        obj.hide_render = False
    if prop_objects:
        bake(prop_objects, "AO", image, clear=False)
    save(image, os.path.join(bakes, "occlusion.png"))
    plain = bpy.data.materials.new("pad bake")
    plain.use_nodes = True
    ground.data.materials.append(plain)
    for obj in prop_objects:
        obj.hide_render = True
    image = bpy.data.images.new("pad_occlusion.png", 512, 512)
    bake([ground], "AO", image)
    save(image, os.path.join(bakes, "pad_occlusion.png"))
    for obj in prop_objects:
        obj.hide_render = False


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "joint_command_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, f"{PREFIX}_emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))

    main, intact = Builder(), Builder()
    headquarters(main)
    war_room(main, intact)
    hall(main)
    wing(main)
    drum(main)
    tower(main, intact)
    mast(intact, *MAST)
    clutter(main)
    hold, search = Builder(), Builder()
    barriers(hold)
    search_mast(search)
    building = solid("BUILDING", main, tiles)
    whole = solid("INTACT", intact, tiles)
    plans = dict(hold=solid("HOLD", hold, tiles), search=solid("SEARCH", search, tiles))
    # The gun's parts, each at its bone, in its bone's space.
    gun, places = [], {}
    for name, parent, offset, builder in gun_parts():
        at = Vector(offset) + (places[parent] if parent else Vector())
        places[name] = at
        gun.append((name, parent, offset, solid(name, builder, tiles, location=at)))
    flash = muzzle_flash(places["BARREL01"] + Vector(MUZZLE))
    textured(flash, load_image(os.path.join(tiles, "tile_hazard.png")))
    props = list(plans.values()) + [obj for *_, obj in gun]
    unwrap([building, whole] + props)
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    os.makedirs(bakes, exist_ok=True)
    ground = pad()
    flash.hide_render = True
    bake_all([building, whole], props, ground, bakes)
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, f"{PREFIX}_building.tga"))
    for obj in [building, whole] + props:
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
    return dict(building=building, intact=whole, pad=ground, emblems=marks, banners=banners, gun=gun, flash=flash,
                **plans)


# --- writing the models ----------------------------------------------------------------------------

FLAT = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)


def save_model(model):
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **FLAT)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **FLAT)
    for obj in parts["banners"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, **FLAT)
    save_model(model)


def export_plans(parts):
    texture = f"{PREFIX}_building.tga"
    gun = w3d.Model(NAME + "_G")
    bones = {}
    for name, parent, offset, obj in parts["gun"]:
        bones[name] = gun.bone(name, bones[parent] if parent else w3d.CHASSIS, offset)
        gun.mesh(name, bones[name], **mesh_data(obj), texture=texture)
    gun.bone("MUZZLE01", bones["BARREL01"], MUZZLE)
    flash = gun.bone("MUZZLEFX01", bones["BARREL01"], MUZZLE)
    gun.mesh("MUZZLEFX01", flash, **mesh_data(parts["flash"]), texture="EXTnkMzl01.tga", shadow=False,
             shader=w3d.ADDITIVE_SHADER)
    save_model(gun)
    for suffix, key in (("_H", "hold"), ("_S", "search")):
        model = w3d.Model(NAME + suffix)
        model.mesh(key.upper(), w3d.CHASSIS, **mesh_data(parts[key]), texture=texture)
        save_model(model)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)
    export_plans(parts)
    parts["flash"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

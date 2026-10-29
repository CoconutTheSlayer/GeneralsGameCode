"""The European Joint Command (the strategy centre), modelled in Blender and written as W3D models for the
game: a hardened command wedge of three sloped tiers (steel-blue armour, off-white plaster, a band of dark
operations windows) crowned by an antenna farm (a lattice mast, a whip mast, a turning radar array, dishes and
a radome), with the bombardment gun's armoured ring on the low east terrace and an armoured portal to the
front, on an apron shaped like the wedge. It is the base's high-tech brain, its own silhouette among the
faction's buildings.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/joint_command.py

Painted the Command Centre's way (command_centre.py): joint_command_paint.py paints small tiling surfaces,
Blender projects them onto the model and bakes them with the ambient occlusion into one texture of the
building's own (eusg_building.tga), and the painter adds grime and makes the damaged, wrecked and night
versions. The models:

    EUSTRAT, _D, _E (wrecked: the antenna farm is gone), each with a night version (_N, _DN, _EN)
    EUSTRAT_G   the bombardment plan's gun, on its ring: bones TURRET01 (turns), TURRETEL (elevates),
                BARREL01 (recoils), MUZZLE01 and the flash MUZZLEFX01
    EUSTRAT_H   the hold-the-line plan: concrete barriers and steel hedgehogs round the apron
    EUSTRAT_S   the search-and-destroy plan: a radar mast on the crown

The plans' models are shown by their own draw modules while a plan is active (build_europe.py). The
footprint is the USA's (124 long, 88 wide, centred); the front (the portal) faces -Y.
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
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "rib": ("tile_rib", 10.0), "deck": ("tile_deck", 8.0),
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


def inset(outline, d):
    """A convex outline (x, y), counter-clockwise, moved inwards by d on every side."""
    n = len(outline)
    lines = []
    for i in range(n):
        (ax, ay), (bx, by) = outline[i], outline[(i + 1) % n]
        ex, ey = bx - ax, by - ay
        length = math.hypot(ex, ey)
        nx, ny = -ey / length, ex / length            # inwards, for a counter-clockwise outline
        lines.append(((ax + nx * d, ay + ny * d), (ex, ey)))
    out = []
    for i in range(n):
        (p, e), (q, f) = lines[i - 1], lines[i]
        det = e[0] * f[1] - e[1] * f[0]
        t = ((q[0] - p[0]) * f[1] - (q[1] - p[1]) * f[0]) / det
        out.append((p[0] + e[0] * t, p[1] + e[1] * t))
    return out


def tier(b, surface, outline, z0, z1, slope, cap_surface=None):
    """A sloped, armoured tier: the outline at z0 rising to z1, its sides leaning in by `slope`."""
    top = inset(outline, slope)
    b.loft(surface, [(x, y, z0) for x, y in outline], [(x, y, z1) for x, y in top], cap_surface)
    return top


def band(outline_lo, outline_hi, z0, z1, out=0.12):
    """The faces of a sloped band (open), standing `out` proud of the slope: for windows or the player's colour."""
    lo, hi = inset(outline_lo, -out), inset(outline_hi, -out)
    bm = bmesh.new()
    a = [bm.verts.new((x, y, z0)) for x, y in lo]
    c = [bm.verts.new((x, y, z1)) for x, y in hi]
    n = len(a)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((a[i], a[j], c[j], c[i]))
    return bm


def lerp_outline(a, b, t):
    return [(p[0] + (q[0] - p[0]) * t, p[1] + (q[1] - p[1]) * t) for p, q in zip(a, b)]


# The command wedge: three sloped tiers, the gun on the low terrace to the east, the antenna farm on top.
BASE = [(-54.0, -18.0), (-40.0, -36.0), (38.0, -36.0), (56.0, -16.0), (56.0, 22.0), (44.0, 36.0), (-40.0, 36.0),
        (-54.0, 22.0)]
BASE_TOP = 10.0
MIDDLE = [(-44.0, -20.0), (-34.0, -28.0), (22.0, -28.0), (28.0, -22.0), (28.0, 22.0), (22.0, 28.0), (-34.0, 28.0),
          (-44.0, 18.0)]
MIDDLE_TOP = 20.0
CROWN = [(-34.0, -16.0), (-26.0, -22.0), (6.0, -22.0), (14.0, -14.0), (14.0, 14.0), (6.0, 20.0), (-26.0, 20.0),
         (-34.0, 12.0)]
CROWN_TOP = 25.0
WINDOWS = (13.2, 16.6)               # the operations windows' band on the middle tier
GUN_RING = (39.0, 0.0, 8.0)          # on the terrace: x, y, radius
GUN_AT = (GUN_RING[0], GUN_RING[1], BASE_TOP + 3.1)
PORTAL = (-8.0, 8.0, -40.0)          # x0, x1, front y


def wedge(b):
    """The tiers: steel-blue armour below, off-white plaster above, dark trim on the edges."""
    b.loft("dark", [(x, y, PAD_Z) for x, y in inset(BASE, -0.6)], [(x, y, PAD_Z + 1.4) for x, y in inset(BASE, -0.4)])
    top = tier(b, "trim", BASE, PAD_Z + 1.4, BASE_TOP, 6.0, cap_surface="deck")
    b.loft("dark", [(x, y, BASE_TOP) for x, y in inset(top, -0.3)], [(x, y, BASE_TOP + 0.7) for x, y in inset(top, -0.3)])
    mid = tier(b, "wall", MIDDLE, BASE_TOP, MIDDLE_TOP, 4.0, cap_surface="deck")
    b.loft("dark", [(x, y, MIDDLE_TOP) for x, y in inset(mid, -0.3)], [(x, y, MIDDLE_TOP + 0.6) for x, y in inset(mid, -0.3)])
    crown = tier(b, "trim", CROWN, MIDDLE_TOP, CROWN_TOP, 2.0, cap_surface="deck")
    b.loft("dark", [(x, y, CROWN_TOP) for x, y in inset(crown, -0.2)], [(x, y, CROWN_TOP + 0.5) for x, y in inset(crown, -0.2)])
    # Ammunition hatches and vents on the gun's terrace.
    for y in (-16.0, 16.0):
        b.box("metal", (45.0, y - 2.5, BASE_TOP), (49.0, y + 2.5, BASE_TOP + 1.4))
        b.box("grille", (49.0, y - 2.2, BASE_TOP + 0.3), (49.1, y + 2.2, BASE_TOP + 1.2))
    b.box("dark", (30.0, -20.0, BASE_TOP), (33.0, 20.0, BASE_TOP + 0.6))               # a cable duct
    # Armour ribs down the base tier's corners.
    for (x0, y0), (x1, y1) in zip(BASE, top):
        b.rod("dark", (x0, y0, PAD_Z + 1.4), (x1, y1, BASE_TOP), 0.7, 4)


def operations_windows(b):
    """The band of dark operations windows round the middle tier, standing a little proud of its slope."""
    z0, z1 = WINDOWS
    h = MIDDLE_TOP - BASE_TOP
    lo = inset(lerp_outline(MIDDLE, inset(MIDDLE, 4.0), (z0 - BASE_TOP) / h), -0.12)
    hi = inset(lerp_outline(MIDDLE, inset(MIDDLE, 4.0), (z1 - BASE_TOP) / h), -0.12)
    b.loft("glazing", [(x, y, z0) for x, y in lo], [(x, y, z1) for x, y in hi], cap_surface="dark")
    b.loft("dark", [(x, y, z1) for x, y in inset(hi, -0.1)], [(x, y, z1 + 0.5) for x, y in inset(hi, 0.3)])


def portal(b):
    """The armoured entrance to the front: a steel portal through the base tier, the door, a canopy, steps."""
    x0, x1, y = PORTAL
    b.loft("trim", [(x0, y, PAD_Z), (x1, y, PAD_Z), (x1, -30.0, PAD_Z), (x0, -30.0, PAD_Z)],
           [(x0 + 0.6, y + 1.2, 12.0), (x1 - 0.6, y + 1.2, 12.0), (x1 - 0.6, -30.0, 12.0), (x0 + 0.6, -30.0, 12.0)],
           cap_surface="dark")
    b.box("dark", (-4.2, y - 0.3, PAD_Z), (4.2, y + 0.4, 6.8))
    b.box("door", (-3.6, y - 0.45, PAD_Z), (3.6, y + 0.2, 6.3))
    b.box("dark", (-6.4, y - 3.0, 6.8), (6.4, y + 0.3, 7.6))
    b.box("hazard", (-6.4, y - 3.05, 6.9), (6.4, y - 2.85, 7.5))
    for k in range(3):
        b.box("concrete", (-5.0, y - 1.2 - k * 1.2, PAD_Z), (5.0, y - k * 1.2, PAD_Z + 1.2 - k * 0.4))


def gun_ring(b):
    """The bombardment gun's ring on the terrace: an octagonal armoured collar, the closed hatch."""
    x, y, r = GUN_RING
    z = BASE_TOP
    b.cylinder("trim", (x, y, z + 1.3), r, 2.6, segments=8, radius2=r - 0.9, rotate=math.pi / 8)
    b.cylinder("dark", (x, y, z + 2.75), r - 0.6, 0.3, segments=8, rotate=math.pi / 8)
    b.cylinder("hazard", (x, y, z + 2.95), 6.6, 0.2, segments=16)
    b.cylinder("metal", (x, y, z + 3.05), 5.8, 0.3, segments=16)
    b.box("dark", (x - 5.8, y - 0.1, z + 3.2), (x + 5.8, y + 0.1, z + 3.3))
    b.box("dark", (x - 0.1, y - 5.8, z + 3.2), (x + 0.1, y + 5.8, z + 3.3))


def antenna_farm(b, intact):
    """The crown's antennas: a tall lattice mast, a second mast, a turning radar array, dishes and a radome."""
    mast(intact, -22.0, 9.0, CROWN_TOP + 0.5, 54.0, base=False)
    mast(intact, -28.0, -11.0, CROWN_TOP + 0.5, 42.0, base=False)
    intact.cylinder("metal", (-6.0, 11.0, CROWN_TOP + 9.5), 0.5, 19.0, segments=6, radius2=0.25)
    for z in (30.0, 36.0, 41.0):
        intact.box("metal", (-9.0, 10.8, z), (-3.0, 11.2, z + 0.25))
    intact.sphere("red", (-6.0, 11.0, CROWN_TOP + 19.3), 0.4, 8, 6)
    # The turning radar: a pedestal, a yoke and a wide lattice array, leaning back.
    x, y, z = -12.0, -9.0, CROWN_TOP + 0.5
    b.cylinder("trim", (x, y, z + 1.0), 2.6, 2.0, segments=10)
    b.cylinder("metal", (x, y, z + 3.0), 1.2, 2.0, segments=8)
    def array(bm):
        m = (Matrix.Translation((x, y, z + 6.6)) @ Matrix.Rotation(0.5, 4, "Z") @ Matrix.Rotation(-0.4, 4, "X")
             @ Matrix.Diagonal((15.0, 0.8, 4.6, 1)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    intact.add("trim", array)
    def face(bm):
        m = (Matrix.Translation((x, y, z + 6.6)) @ Matrix.Rotation(0.5, 4, "Z") @ Matrix.Rotation(-0.4, 4, "X")
             @ Matrix.Translation((0, -0.45, 0)) @ Matrix.Diagonal((14.0, 0.3, 3.8, 1)))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    intact.add("grille", face)
    # Dishes on the middle tier's deck and a radome on the crown.
    for (dx, dy, facing, radius) in ((20.0, -20.0, -1.2, 3.4), (20.0, 18.0, 0.6, 2.8), (-37.0, -2.0, 3.0, 3.0)):
        b.cylinder("metal", (dx, dy, MIDDLE_TOP + 1.6), 0.6, 3.2, segments=6)
        def dish(bm, dx=dx, dy=dy, facing=facing, radius=radius):
            m = (Matrix.Translation((dx, dy, MIDDLE_TOP + 3.6)) @ Matrix.Rotation(facing, 4, "Z")
                 @ Matrix.Rotation(-math.pi / 2 + 0.6, 4, "Y"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=radius, radius2=radius * 0.3,
                                  depth=radius * 0.45, matrix=m)
        intact.add("dome", dish)
    b.cylinder("metal", (-1.0, 9.0, CROWN_TOP + 1.0), 3.0, 1.0, segments=12)
    intact.sphere("dome", (-1.0, 9.0, CROWN_TOP + 4.2), 3.4)
    for x0, y0 in ((-26.0, -15.0), (0.0, -15.0)):                 # the crown's railings' posts and air vents
        b.box("metal", (x0 - 1.4, y0 - 1.0, CROWN_TOP + 0.5), (x0 + 1.4, y0 + 1.0, CROWN_TOP + 2.2))


def mast(b, x, y, z0=PAD_Z, z1=56.0, base=True):
    """A lattice antenna mast with red and white bands and four dishes (the Command Centre's)."""
    if base:
        b.box("concrete", (x - 3.6, y - 3.6, z0), (x + 3.6, y + 3.6, z0 + 1.8))
    else:
        b.box("dark", (x - 2.8, y - 2.8, z0 - 0.5), (x + 2.8, y + 2.8, z0 + 0.6))
    half = 1.8
    for dx, dy in ((-half, -half), (half, -half), (half, half), (-half, half)):
        b.add("metal", lambda bm, dx=dx, dy=dy: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=4, radius1=0.3, radius2=0.15, depth=z1 - z0,
            matrix=Matrix.Translation((x + dx, y + dy, (z0 + z1) / 2))))
    z = z0 + 4.0
    k = 0
    while z < z1 - 2:
        colour = "red" if (k % 2 == 1) else "metal"
        for (ax, ay), (bx, by) in (((-half, -half), (half, -half)), ((half, -half), (half, half)),
                                   ((half, half), (-half, half)), ((-half, half), (-half, -half))):
            b.box(colour, (x + min(ax, bx) - 0.13, y + min(ay, by) - 0.13, z - 0.13),
                  (x + max(ax, bx) + 0.13, y + max(ay, by) + 0.13, z + 0.13))
        b.rod("metal", (x - half, y - half, z), (x + half, y - half, z + 5.0), 0.1, 4)
        b.rod("metal", (x - half, y + half, z), (x - half, y - half, z + 5.0), 0.1, 4)
        z += 5.0
        k += 1
    for k, zz in enumerate(range(int(z1) - 6, int(z1), 3)):
        b.box("red" if k % 2 == 0 else "dome", (x - 2.1, y - 2.1, zz), (x + 2.1, y + 2.1, zz + 1.5))
    b.sphere("red", (x, y, z1 + 0.6), 0.6, 8, 6)
    for zz, radius, facing in ((z1 - 10, 3.0, -0.6), (z1 - 16, 2.6, 2.2), (z1 - 22, 2.2, -1.9)):
        def make(bm, zz=zz, radius=radius, facing=facing):
            m = (Matrix.Translation((x + math.cos(facing) * 2.7, y + math.sin(facing) * 2.7, zz))
                 @ Matrix.Rotation(facing, 4, "Z") @ Matrix.Rotation(-math.pi / 2 + 0.3, 4, "Y"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=radius, radius2=radius * 0.3,
                                  depth=radius * 0.4, matrix=m)
        b.add("dome", make)


def clutter(b):
    """Crates, fuel drums, sandbags, a generator and floodlights round the wedge."""
    for x, y, h in ((-24.0, -39.0, 3.4), (-20.2, -39.0, 3.4), (-22.1, -39.0, 6.6)):
        if h > 4:
            b.box("crate", (x - 1.7, y - 1.7, PAD_Z + 3.4), (x + 1.7, y + 1.7, PAD_Z + 6.6))
        else:
            b.box("crate", (x - 1.8, y - 1.8, PAD_Z), (x + 1.8, y + 1.8, PAD_Z + h))
    for x, y in ((20.0, -39.5), (22.6, -39.5), (21.3, -37.3)):
        b.cylinder("trim", (x, y, PAD_Z + 1.8), 1.2, 3.6, segments=6)
    for (ax, ay), (bx, by) in (((12.0, -40.0), (16.0, -40.0)),):
        b.box("sandbag", (ax - 1.2, ay - 1.2, PAD_Z), (bx + 1.2, by + 1.2, PAD_Z + 2.6))
    for x, y in ((-57.0, -20.0), (57.0, -19.0), (46.0, 38.0), (-42.0, 38.5)):
        b.cylinder("metal", (x, y, PAD_Z + 7), 0.3, 14, segments=6)
        b.box("metal", (x - 1.2, y - 0.6, PAD_Z + 13.4), (x + 1.2, y + 0.6, PAD_Z + 14.6))
    b.box("metal", (-58.0, -4.0, PAD_Z), (-55.0, 8.0, PAD_Z + 4.2))                # the generator
    b.box("grille", (-58.1, -3.0, PAD_Z + 1.0), (-57.9, 7.0, PAD_Z + 3.6))



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
    """Hold the line: concrete barriers along the apron's edge, steel hedgehogs and sandbags by the gaps."""
    profile = [(-1.0, 0.0), (1.0, 0.0), (0.9, 0.6), (0.45, 1.4), (0.35, 3.0), (-0.35, 3.0), (-0.45, 1.4), (-0.9, 0.6)]
    ring = inset(PAD_OUTLINE, 2.2)
    gaps = ((-28.0, -16.0), (-11.0, 11.0), (8.0, 26.0))         # the front's door, crates and drums
    n = len(ring)
    for i in range(n):
        a, c = Vector((*ring[i], PAD_Z)), Vector((*ring[(i + 1) % n], PAD_Z))
        d = c - a
        length = d.length
        d.normalize()
        side = Vector((-d.y, d.x, 0.0))
        t = 1.5
        while t + 5.0 <= length - 1.5:
            p = a + d * t
            q = p + d * 5.0
            front = abs(p.y - ring[1][1]) < 0.1 and abs(q.y - ring[1][1]) < 0.1
            if not (front and any(g0 - 0.5 < x < g1 + 0.5 for g0, g1 in gaps for x in (p.x, q.x))):
                b.loft("concrete", [p + side * u + Vector((0, 0, v)) for u, v in profile],
                       [q + side * u + Vector((0, 0, v)) for u, v in profile])
                strip = [p + d * 0.4 - side * 0.36, p + d * 0.4 + side * 0.36, q - d * 0.4 + side * 0.36,
                         q - d * 0.4 - side * 0.36]
                b.loft("hazard", [s + Vector((0, 0, 3.0)) for s in strip], [s + Vector((0, 0, 3.3)) for s in strip])
            t += 5.6
    for x, y in ((-30.0, -40.0), (30.0, -40.0), (58.0, 0.0), (-57.5, 14.0)):
        centre = Vector((x, y, PAD_Z + 1.5))
        for a, lift in ((0.0, 0.0), (math.pi / 3, 1.6), (-math.pi / 3, 1.6)):
            d = Vector((math.cos(a) * 1.9, math.sin(a) * 1.9, 0.0)) * (0.5 if lift else 1.0) + Vector((0, 0, lift))
            b.rod("dark", centre - d, centre + d, 0.32, 4)
    for x0, x1 in ((-11.0, -8.0), (8.0, 11.0)):
        b.box("sandbag", (x0, -41.4, PAD_Z), (x1, -39.4, PAD_Z + 2.4))


def search_mast(b):
    """Search and destroy: a telescopic radar mast on the crown with a phased-array panel."""
    x, y, z = 6.0, -10.0, CROWN_TOP + 0.5
    b.box("trim", (x - 2.4, y - 2.4, z - 0.3), (x + 2.4, y + 2.4, z + 1.2))
    b.cylinder("metal", (x, y, z + 8.0), 1.1, 13.4, segments=10)
    b.cylinder("trim", (x, y, z + 14.6), 1.4, 0.6, segments=10)
    b.cylinder("metal", (x, y, z + 18.8), 0.75, 8.4, segments=10)
    b.cylinder("trim", (x, y, z + 23.2), 1.5, 1.0, segments=10)
    def panel(bm):
        m = Matrix.Translation((x, y - 0.6, z + 26.8)) @ Matrix.Rotation(-0.35, 4, "X") @ Matrix.Diagonal((12.0, 0.9, 5.6, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    b.add("trim", panel)
    def face(bm):
        m = Matrix.Translation((x, y - 1.25, z + 26.6)) @ Matrix.Rotation(-0.35, 4, "X") @ Matrix.Diagonal((11.0, 0.3, 4.6, 1))
        bmesh.ops.create_cube(bm, size=1.0, matrix=m)
    b.add("grille", face)
    b.sphere("red", (x, y, z + 30.6), 0.45, 8, 6)
    b.cylinder("metal", (x, y, z + 29.7), 0.15, 1.8, segments=6)


# --- flat parts ------------------------------------------------------------------------------------

PAD_OUTLINE = [(-60.0, -22.0), (-44.0, -42.0), (42.0, -42.0), (61.0, -20.0), (61.0, 26.0), (48.0, 42.0), (-44.0, 42.0),
               (-60.0, 26.0)]


def pad():
    """The apron, shaped like the wedge, with a chamfered edge; painted as one picture."""
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in inset(PAD_OUTLINE, -1.0)]
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
    """The faction's mark above the portal's door, on its sloping face."""
    x0, x1, y = PORTAL
    lean = 1.2 / (12.0 - PAD_Z)
    def at(x, z):
        return (x, y + (z - PAD_Z) * lean - 0.1, z)
    z = BASE_TOP + 0.75
    return [decal("EMBLEM", [at(-3.0, 7.9), at(3.0, 7.9), at(3.0, 11.6), at(-3.0, 11.6)])]


def house_colours():
    """The player's colour: a band on the middle tier below the windows, a ring round the gun's collar."""
    objects = []
    h = MIDDLE_TOP - BASE_TOP
    lo = lerp_outline(MIDDLE, inset(MIDDLE, 4.0), 0.12)
    hi = lerp_outline(MIDDLE, inset(MIDDLE, 4.0), 0.22)
    objects.append(new_object("HOUSECOLOR01", band(lo, hi, BASE_TOP + 0.12 * h, BASE_TOP + 0.22 * h, out=0.1)))
    x, y, r = GUN_RING
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=r - 0.15, radius2=r - 0.5, depth=0.9,
                          matrix=Matrix.Translation((x, y, BASE_TOP + 1.5)) @ Matrix.Rotation(math.pi / 8, 4, "Z"))
    objects.append(new_object("HOUSECOLOR02", bm))
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
    wedge(main)
    operations_windows(main)
    portal(main)
    gun_ring(main)
    antenna_farm(main, intact)
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

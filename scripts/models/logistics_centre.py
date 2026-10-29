"""The European Logistics Centre (the supply centre), modelled in Blender and written as W3D models for the
game: an open container yard under one huge yellow-and-steel gantry crane, whose legs ride on rails and
whose box girders span the stacks of multi-coloured shipping containers and reach out over the lane, with
a trolley, its cab and a container hanging from the spreader; three tall silos with a catwalk and a
conveyor at the back; a small flat-roofed dispatch office with a glazed control room at the front; the
landing square kept clear where supply trucks and helicopters unload (after a concept painted in the game's
style; no curved roofs, so it reads apart from the Command Centre). It is made the way the Command Centre
is (command_centre.py), and the Funds Office (funds_office.py) uses its machinery.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/logistics_centre.py

How it is painted: logistics_centre_paint.py paints small tiling surfaces; Blender projects them onto the
model, then bakes them and the ambient occlusion into one texture of the building's own; the painter adds
grime and makes the damaged, wrecked and night versions. Six models use them: EUSUPC (intact), _D, _E
(wrecked: the crane's bridge fallen across the stacks, no catwalk, floodlights or mast), each with a night
version (_N, _DN, _EN).

The footprint is the USA's (88 long, 90 wide, centred). Gathering needs the dock's bones
(SupplyCenterDockUpdate): DOCKSTART, DOCKACTION and DOCKEND on the landing square, where trucks stop and
helicopters land, and DOCKWAITING01..09 round the outside, where they queue (the USA's places). The game's
camera looks at it from -Y, +X to the right: the landing square is at the front right, the office at the
front left, the crane across the middle, the silos at the back right.
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

NAME = "EUSUPC"
PREFIX = "eusc"
PAD_Z = 0.8
TEXTURE_SIZE = 1024
# Surfaces: (tile painted by the painter, units per tile) or a plain colour.
SURFACES = {
    "wall": ("tile_wall", 16.0), "office": ("tile_office", 16.0), "trim": ("tile_trim", 12.0),
    "rib": ("tile_rib", 10.0), "deck": ("tile_deck", 16.0), "shutter": ("tile_shutter", 8.0),
    "metal": ("tile_metal", 6.0), "crate": ("tile_crate", 4.0), "sandbag": ("tile_sandbag", 4.0),
    "hazard": ("tile_hazard", 3.0), "grille": ("tile_grille", 3.0), "container": ("tile_container", 8.0),
    "container2": ("tile_container2", 8.0), "container3": ("tile_container3", 8.0),
    "container4": ("tile_container4", 8.0), "container5": ("tile_container5", 8.0),
    "craneyellow": ("tile_crane", 8.0), "concrete": ("tile_concrete", 14.0), "roof": ("tile_roof", 6.0),
    "tank": ("tile_tank", 10.0), "pallet": ("tile_pallet", 3.0),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46), "red": (196, 52, 40),
    "white": (226, 226, 222), "lamp": (240, 236, 210),
}
SURFACE = {name: i for i, name in enumerate(SURFACES)}
# Surfaces that light up at night.
GLOWING = ("glass", "lamp")


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

    def turned_box(self, surface, centre, size, angle):
        """A box turned about the vertical."""
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ Matrix.Rotation(angle, 4, "Z")
            @ Matrix.Diagonal((*size, 1.0))))

    def beam(self, surface, a, b, thickness):
        """A square bar from a to b."""
        ax = [q - p for p, q in zip(a, b)]
        length = math.sqrt(sum(c * c for c in ax))
        from mathutils import Vector
        rot = Vector((0, 0, 1)).rotation_difference(Vector(ax).normalized()).to_matrix().to_4x4()
        centre = [(p + q) / 2 for p, q in zip(a, b)]
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ rot @ Matrix.Diagonal((thickness, thickness, length, 1.0))))

    def cylinder(self, surface, centre, radius, length, axis="Z", segments=16, radius2=None, rotate=0.0):
        rot = {"Z": Matrix.Rotation(rotate, 4, "Z"), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
               "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=length, matrix=Matrix.Translation(centre) @ rot))

    def sphere(self, surface, centre, radius, scale=(1, 1, 1), segments=(12, 8)):
        self.add(surface, lambda bm: bmesh.ops.create_uvsphere(
            bm, u_segments=segments[0], v_segments=segments[1], radius=radius,
            matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*scale, 1.0))))

    def lathe(self, surface, centre, profile, segments=16, surfaces=None):
        """A closed solid of revolution about Z: profile [(r, z)] from bottom to top, r = 0 ends in a point;
        surfaces: one surface per profile band (overrides `surface`)."""
        cx, cy, z0 = centre

        def make(bm):
            rings = []
            for r, z in profile:
                if r < 1e-6:
                    rings.append([bm.verts.new((cx, cy, z0 + z))])
                else:
                    rings.append([bm.verts.new((cx + math.cos(2 * math.pi * k / segments) * r,
                                                cy + math.sin(2 * math.pi * k / segments) * r, z0 + z))
                                  for k in range(segments)])
            for i in range(len(rings) - 1):
                a, b = rings[i], rings[i + 1]
                band = SURFACE[surfaces[i] if surfaces else surface]
                for k in range(segments):
                    j = (k + 1) % segments
                    if len(a) == 1:
                        f = bm.faces.new((a[0], b[k], b[j]))
                    elif len(b) == 1:
                        f = bm.faces.new((a[k], a[j], b[0]))
                    else:
                        f = bm.faces.new((a[k], a[j], b[j], b[k]))
                    f.material_index = band
            for ring_, flip in ((rings[0], True), (rings[-1], False)):
                if len(ring_) > 1:
                    bm.faces.new(list(reversed(ring_)) if flip else ring_).material_index = SURFACE[surface]
        make(self.bm)

    def extrude_profile(self, surface, profile, x0, x1, cap_surface=None, axis="X"):
        """A closed profile (y, z) pushed along x from x0 to x1 (or a profile (x, z) along y)."""
        def point(s, u, z):
            return (s, u, z) if axis == "X" else (u, s, z)

        def make(bm):
            a = [bm.verts.new(point(x0, u, z)) for u, z in profile]
            b = [bm.verts.new(point(x1, u, z)) for u, z in profile]
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


def ring(b, surface, x0, x1, y0, y1, z0, z1, width):
    """A frame of four boxes round a rectangle (a cornice or parapet), leaving the middle open."""
    b.box(surface, (x0, y0, z0), (x1, y0 + width, z1))
    b.box(surface, (x0, y1 - width, z0), (x1, y1, z1))
    b.box(surface, (x0, y0 + width, z0), (x0 + width, y1 - width, z1))
    b.box(surface, (x1 - width, y0 + width, z0), (x1, y1 - width, z1))


def crate_stack(b, x, y, layout, size=4.0, surface="crate"):
    """Crates in rows: layout is a list of (dx, dy, levels)."""
    for dx, dy, levels in layout:
        for k in range(levels):
            s = size * (0.92 if k else 1.0)
            cx, cy = x + dx * size, y + dy * size
            b.box(surface, (cx - s / 2, cy - s / 2, PAD_Z + k * size), (cx + s / 2, cy + s / 2, PAD_Z + (k + 1) * size))


def container(b, x, y, length, along="X", surface="container", z=PAD_Z):
    """A shipping container: ribbed sides, a dark door end."""
    w, h = 4.8, 5.2
    if along == "X":
        b.box(surface, (x - length / 2, y - w / 2, z), (x + length / 2, y + w / 2, z + h))
        b.box("dark", (x + length / 2, y - w / 2 + 0.3, z + 0.3), (x + length / 2 + 0.15, y + w / 2 - 0.3, z + h - 0.3))
    else:
        b.box(surface, (x - w / 2, y - length / 2, z), (x + w / 2, y + length / 2, z + h))
        b.box("dark", (x - w / 2 + 0.3, y - length / 2 - 0.15, z + 0.3), (x + w / 2 - 0.3, y - length / 2, z + h - 0.3))


def floodlight(b, x, y, height=16.0, facing=0.0):
    b.box("trim", (x - 1.2, y - 1.2, PAD_Z), (x + 1.2, y + 1.2, PAD_Z + 1.0))
    b.cylinder("metal", (x, y, PAD_Z + height / 2), 0.35, height, segments=6)
    b.turned_box("metal", (x, y, PAD_Z + height), (0.6, 3.6, 0.4), facing)
    for side in (-1.1, 1.1):
        cx, cy = x - math.sin(facing) * side, y + math.cos(facing) * side
        b.turned_box("dark", (cx, cy, PAD_Z + height + 0.9), (1.0, 1.6, 1.4), facing)
        b.turned_box("lamp", (cx + math.cos(facing) * 0.55, cy + math.sin(facing) * 0.55, PAD_Z + height + 0.9),
                     (0.1, 1.3, 1.1), facing)


# --- the Logistics Centre --------------------------------------------------------------------------

DOCK = (22.0, -20.0)
DOCK_Z = PAD_Z
# Where trucks and helicopters queue to unload: the USA's places, round the outside of the footprint.
WAITING = [(67.61, -16.58), (67.61, 10.85), (67.61, 44.93), (46.04, 72.27), (5.27, 72.27), (-41.12, 72.27),
           (-79.49, 35.27), (-79.49, -7.79), (-79.49, -53.23)]
RAILS = (-38.0, 2.0)                          # the crane's rails, along y
CRANE_Y = (4.0, 22.0)                         # its legs' y
GIRDER_Z = 36.0                               # the girders' underside
GIRDER_X = (-44.0, 15.0)
SILOS = [(17.0, 36.0), (28.0, 36.0), (37.5, 23.0)]
SILO_R, SILO_TOP = 4.4, 30.0
OFFICE = (-42.0, -24.0, -43.0, -31.0)         # x0, x1, y0, y1
OFFICE_TOP = PAD_Z + 10.4
# Where the burning building smokes (ParticleSysBone in build_europe.py).
SMOKE = [(-33.0, -37.0, OFFICE_TOP + 1.0), (-16.0, 12.0, 12.0), (28.0, 36.0, SILO_TOP + 1.0), (-38.0, 13.0, 26.0)]
# The containers under the crane: (x, y, levels, surface), each 12 long along x.
STACKS = [(-27.0, -4.0, 2, "container"), (-14.0, -4.0, 1, "container3"),
          (-27.0, 2.0, 3, "container2"), (-14.0, 2.0, 2, "container4"),
          (-27.0, 8.0, 1, "container5"), (-14.0, 8.0, 3, "container"),
          (-27.0, 14.0, 2, "container3"), (-14.0, 14.0, 0, ""),
          (-27.0, 20.0, 3, "container4"), (-14.0, 20.0, 2, "container2"),
          (-27.0, 26.0, 2, "container"), (-14.0, 26.0, 3, "container5"),
          (-27.0, 32.0, 1, "container2"), (-14.0, 32.0, 2, "container3"),
          (-27.0, 38.0, 2, "container5"), (-14.0, 38.0, 1, "container4")]
LEVEL_COLOURS = ["container", "container3", "container2", "container4", "container5"]


def containers(b):
    """Stacks of shipping containers in muted colours, each level a different one, between the rails."""
    for i, (x, y, levels, surface) in enumerate(STACKS):
        for k in range(levels):
            s = surface if k == 0 else LEVEL_COLOURS[(LEVEL_COLOURS.index(surface) + 2 * k + i) % len(LEVEL_COLOURS)]
            container(b, x + (0.3 if k % 2 else 0.0), y, 12.0, along="X", surface=s, z=PAD_Z + k * 5.2)
    # A few by the lane, waiting for the trucks.
    container(b, 9.0, 4.0, 12.0, along="Y", surface="container3")
    container(b, 9.0, 4.0, 12.0, along="Y", surface="container4", z=PAD_Z + 5.2)
    container(b, 15.0, 14.0, 12.0, along="Y", surface="container2")


def crane_legs(b):
    """The crane's legs: on each rail a sill beam on wheeled bogies, two legs rising from it, braced."""
    top = GIRDER_Z
    for x in RAILS:
        ya, yb = CRANE_Y
        b.box("craneyellow", (x - 1.2, ya - 3.0, PAD_Z + 1.2), (x + 1.2, yb + 3.0, PAD_Z + 3.4))   # sill beam
        for y in (ya - 1.8, yb + 1.8):
            b.box("dark", (x - 1.4, y - 1.6, PAD_Z), (x + 1.4, y + 1.6, PAD_Z + 1.4))           # bogies
        for y in (ya, yb):
            b.box("craneyellow", (x - 1.3, y - 1.3, PAD_Z + 3.4), (x + 1.3, y + 1.3, top))
        b.box("craneyellow", (x - 1.1, ya, 18.0), (x + 1.1, yb, 19.6))                        # tie beam
        b.beam("craneyellow", (x, ya + 1.0, PAD_Z + 3.6), (x, yb - 1.0, 17.8), 0.8)
        b.beam("craneyellow", (x, yb - 1.0, 19.8), (x, ya + 1.0, top - 0.4), 0.8)
        b.box("hazard", (x - 1.25, ya - 3.05, PAD_Z + 1.4), (x + 1.25, ya - 2.4, PAD_Z + 3.2))


def crane_top(b):
    """The bridge: two box girders spanning the yard and beyond, end carriages, a trolley with its cab and a
    container hanging from the spreader, a walkway, the machinery house."""
    top = GIRDER_Z
    x0, x1 = GIRDER_X
    ya, yb = CRANE_Y
    for y in (ya + 1.0, yb - 1.0):
        b.box("craneyellow", (x0, y - 1.5, top), (x1, y + 1.5, top + 4.2))
        b.box("trim", (x0, y - 1.6, top + 4.2), (x1, y + 1.6, top + 4.6))
    for x in RAILS:
        b.box("craneyellow", (x - 1.4, ya - 1.2, top - 0.2), (x + 1.4, yb + 1.2, top + 4.8))
    b.box("metal", (x0 + 0.5, ya - 1.6, top + 0.2), (x1 - 0.5, ya - 0.3, top + 0.4))         # walkway
    # The machinery house at the far end, behind the left leg.
    b.box("wall", (x0, ya + 2.0, top + 4.6), (x0 + 9.0, yb - 2.0, top + 9.0))
    b.box("trim", (x0 - 0.3, ya + 1.7, top + 8.8), (x0 + 9.3, yb - 1.7, top + 9.4))
    b.box("grille", (x0 - 0.1, ya + 4.0, top + 5.6), (x0, yb - 4.0, top + 7.8))
    # The trolley over the stacks, its cab hanging beneath on the camera's side.
    tx = -18.0
    b.box("metal", (tx - 3.5, ya + 0.4, top + 4.6), (tx + 3.5, yb - 0.4, top + 6.4))
    b.box("trim", (tx - 2.0, ya - 3.4, top - 4.2), (tx + 2.0, ya - 0.2, top + 0.4))
    b.box("glass", (tx - 1.8, ya - 3.5, top - 3.6), (tx + 1.8, ya - 3.4, top - 1.0))
    for dx in (-2.4, 2.4):
        for y in (12.0, 14.0):
            b.cylinder("dark", (tx + dx, y, top - 5.0), 0.12, 10.0, segments=4)
    b.box("craneyellow", (tx - 6.2, 10.6, top - 10.6), (tx + 6.2, 15.4, top - 10.0))         # spreader
    container(b, tx, 13.0, 12.0, along="X", surface="container4", z=top - 15.8)


def silos(b, intact):
    """Three tall silos of light steel on concrete rings, with ladders, a catwalk over their tops (in
    `intact`), and a conveyor down to the yard."""
    for x, y in SILOS:
        profile = [(SILO_R + 0.8, 0.0), (SILO_R + 0.8, 2.6), (SILO_R, 2.6), (SILO_R, 9.0), (SILO_R + 0.2, 9.0),
                   (SILO_R + 0.2, 10.0), (SILO_R, 10.0), (SILO_R, SILO_TOP - 3.0), (1.4, SILO_TOP), (0.0, SILO_TOP + 0.2)]
        b.lathe("tank", (x, y, PAD_Z), profile, segments=14,
                surfaces=["concrete", "concrete", "tank", "trim", "trim", "trim", "tank", "roof", "roof"])
        b.box("metal", (x - 0.7, y - SILO_R - 0.9, PAD_Z + 2.6), (x + 0.7, y - SILO_R + 0.1, SILO_TOP - 2.6))   # ladder
        b.box("dark", (x - 0.5, y - SILO_R - 1.0, PAD_Z + 3.0), (x + 0.5, y - SILO_R - 0.85, SILO_TOP - 3.0))
        b.box("yellow", (x - 1.2, y - SILO_R - 0.3, SILO_TOP - 2.2), (x + 1.2, y - SILO_R + 0.3, SILO_TOP - 1.8))
    (ax, ay), (bx, by), (cx, cy) = SILOS
    z = SILO_TOP - 0.6
    intact.box("metal", (ax, ay - 0.9, z), (bx, by + 0.9, z + 0.4))
    intact.beam("metal", (bx, by, z + 0.2), (cx, cy, z + 0.2), 1.6)
    intact.box("yellow", (ax, ay - 1.0, z + 1.5), (bx, ay - 0.8, z + 1.7))
    intact.box("metal", (bx - 2.0, by - 2.0, SILO_TOP + 0.2), (bx + 2.0, by + 2.0, SILO_TOP + 2.0))   # head house
    # The conveyor from the first silo's foot down to a hopper by the lane.
    b.beam("trim", (ax - SILO_R + 1.0, ay - 2.0, 14.0), (8.0, 24.0, PAD_Z + 4.0), 1.6)
    b.box("metal", (5.0, 21.5, PAD_Z), (10.0, 26.5, PAD_Z + 4.4))
    for t in (0.35, 0.7):
        x, y, zz = (ax - SILO_R + 1.0) + (8.0 - ax + SILO_R - 1.0) * t, (ay - 2.0) + (24.0 - ay + 2.0) * t, 14.0 + (PAD_Z + 4.0 - 14.0) * t
        b.box("trim", (x - 0.3, y - 0.3, PAD_Z), (x + 0.3, y + 0.3, zz))


def office(b, intact):
    """The dispatch office: two storeys of plaster on a plinth, steel-blue window rows, a parapet, and a
    glazed control room on the roof looking over the yard."""
    x0, x1, y0, y1 = OFFICE
    top = OFFICE_TOP
    b.box("office", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.0))
    ring(b, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 0.6, top + 0.9, 1.0)
    b.box("deck", (x0 + 0.5, y0 + 0.5, top - 0.2), (x1 - 0.5, y1 - 0.5, top + 0.2))
    for z in (3.4, 7.8):
        for x in (x0 + 2.0, x0 + 5.6, x1 - 4.0):
            b.box("trim", (x - 0.3, y0 - 0.4, z - 0.3), (x + 2.9, y0, z + 2.2))
            b.box("glass", (x, y0 - 0.5, z), (x + 2.6, y0 - 0.4, z + 1.9))
        for y in (y0 + 2.0, y1 - 4.6):
            b.box("trim", (x1, y - 0.3, z - 0.3), (x1 + 0.4, y + 2.9, z + 2.2))
            b.box("glass", (x1 + 0.4, y, z), (x1 + 0.5, y + 2.6, z + 1.9))
    b.box("dark", (x1 - 9.6, y0 - 0.3, PAD_Z), (x1 - 6.4, y0, 6.0))
    b.box("shutter", (x1 - 9.3, y0 - 0.4, PAD_Z), (x1 - 6.7, y0 - 0.3, 5.6))
    b.box("trim", (x1 - 10.4, y0 - 2.6, 6.2), (x1 - 5.6, y0, 6.8))
    # The control room: a glazed box leaning out over the yard's side.
    cx0, cx1, cy0, cy1 = x1 - 9.0, x1 + 1.0, y0 + 2.0, y1 - 1.0
    b.box("trim", (cx0, cy0, top), (cx1, cy1, top + 0.8))
    b.box("glass", (cx0 + 0.3, cy0 + 0.3, top + 0.8), (cx1 - 0.3, cy1 - 0.3, top + 3.4))
    b.box("trim", (cx0 - 0.5, cy0 - 0.5, top + 3.4), (cx1 + 0.5, cy1 + 0.5, top + 4.2))
    intact.box("metal", (x0 + 2.0, y1 - 5.0, top), (x0 + 7.0, y1 - 1.5, top + 2.0))
    intact.box("grille", (x0 + 2.2, y1 - 5.1, top + 0.4), (x0 + 6.8, y1 - 5.0, top + 1.6))
    intact.cylinder("metal", (cx0 + 1.0, cy1 - 1.0, top + 8.2), 0.15, 8.0, segments=4)
    intact.sphere("red", (cx0 + 1.0, cy1 - 1.0, top + 12.3), 0.35, segments=(6, 4))


def clutter(b):
    """Pallets and crates by the lane, barriers along the front, the rails' buffer stops."""
    crate_stack(b, 34.0, 6.0, [(0, 0, 2), (1, 0, 1), (0, 1, 1)], size=3.6)
    for x, y, n in ((-8.0, -36.0, 3), (-2.0, -36.0, 2), (38.0, -2.0, 2)):
        for k in range(n):
            b.box("pallet", (x - 2.4, y - 2.4, PAD_Z + k * 0.7), (x + 2.4, y + 2.4, PAD_Z + (k + 1) * 0.7 - 0.08))
    for x in RAILS:
        for y in (-40.0, 42.0):
            b.box("hazard", (x - 1.6, y - 0.8, PAD_Z), (x + 1.6, y + 0.8, PAD_Z + 1.8))
    for y in range(-40, -26, 4):   # barriers along the landing square's outer side
        b.box("trim", (42.4, y - 1.6, PAD_Z), (43.4, y + 1.6, PAD_Z + 1.8))


def lights(b):
    floodlight(b, 40.0, -42.0, height=18.0, facing=math.radians(135))
    floodlight(b, -42.0, 42.0, height=18.0, facing=math.radians(-45))


def wreckage(b):
    """The crane's bridge fallen across the stacks, its trolley in the yard."""
    b.turned_box("craneyellow", (-18.0, 9.0, PAD_Z + 12.0), (44.0, 2.6, 3.4), 0.12)
    b.turned_box("craneyellow", (-12.0, 18.0, PAD_Z + 1.7), (30.0, 2.6, 3.4), -0.25)
    b.turned_box("metal", (-6.0, -8.0, PAD_Z + 0.8), (7.0, 5.0, 1.6), 0.6)
    b.turned_box("tank", (24.0, 26.0, PAD_Z + 1.0), (6.0, 4.0, 2.0), 1.1)


FENCE = [((-43.0, -28.0), (-43.0, 38.0)), ((24.0, 44.0), (-36.0, 44.0))]
FENCE_HEIGHT = 6.0


def fence_posts(b, fence=FENCE, height=FENCE_HEIGHT):
    for (ax, ay), (bx, by) in fence:
        length = math.hypot(bx - ax, by - ay)
        steps = max(1, int(length / 8))
        for i in range(steps + 1):
            t = i / steps
            b.cylinder("metal", (ax + (bx - ax) * t, ay + (by - ay) * t, PAD_Z + height / 2), 0.2, height, segments=6)


def fence_mesh(fence=FENCE, height=FENCE_HEIGHT, name="FENCE"):
    """Chain-link panels between the posts, both ways round (cut away by the texture's alpha)."""
    bm = bmesh.new()
    for (ax, ay), (bx, by) in fence:
        quad = [(ax, ay, PAD_Z), (bx, by, PAD_Z), (bx, by, PAD_Z + height), (ax, ay, PAD_Z + height)]
        bm.faces.new([bm.verts.new(v) for v in quad])
        bm.faces.new([bm.verts.new(v) for v in reversed(quad)])
    obj = new_object(name, bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((x + y) / 6.0, (z - PAD_Z) / height)
    return obj


def build_shapes():
    main, intact, wreck = Builder(), Builder(), Builder()
    containers(main)
    crane_legs(main)
    crane_top(intact)
    silos(main, intact)
    office(main, intact)
    clutter(main)
    fence_posts(main)
    lights(intact)
    wreckage(wreck)
    return main, intact, wreck


def pad_mesh(outline, extent, z=PAD_Z, inset=0.995):
    """The concrete pad with a chamfered edge; its texture covers extent (x0, x1, y0, y1)."""
    x0, x1, y0, y1 = extent
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in outline]
    top = [bm.verts.new((x * inset, y * inset, z)) for x, y in outline]
    bm.faces.new(top)
    n = len(outline)
    for i in range(n):
        j = (i + 1) % n
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
    """The faction's mark over the office's door, and on the machinery house on the crane."""
    x0, x1, y0, y1 = OFFICE
    ex0, ex1, y = x1 - 9.8, x1 - 6.2, y0 - 0.06
    marks = [decal("EMBLEM", [(ex0, y, 6.9), (ex1, y, 6.9), (ex1, y, 10.5), (ex0, y, 10.5)])]
    gx0 = GIRDER_X[0]
    ya, yb = CRANE_Y
    z = GIRDER_Z
    y = ya + 2.0 - 0.06
    marks.append(decal("EMBLEM2", [(gx0 + 2.6, y, z + 5.0), (gx0 + 6.4, y, z + 5.0), (gx0 + 6.4, y, z + 8.6),
                                   (gx0 + 2.6, y, z + 8.6)]))
    return marks


def double_sided(name, quads):
    bm = bmesh.new()
    for quad in quads:
        bm.faces.new([bm.verts.new(v) for v in quad])
        bm.faces.new([bm.verts.new(v) for v in reversed(quad)])
    return new_object(name, bm)


def house_colours():
    """The player's colour: a band under the office's parapet, stripes along the crane's girders."""
    x0, x1, y0, y1 = OFFICE
    objects = []
    bm = bmesh.new()
    z0, z1 = OFFICE_TOP - 1.9, OFFICE_TOP - 1.2
    pts = [(x0 - 0.12, y0 - 0.12), (x1 + 0.12, y0 - 0.12), (x1 + 0.12, y1 + 0.12), (x0 - 0.12, y1 + 0.12)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        bm.faces.new([bm.verts.new(v) for v in ((ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1))])
    objects.append(new_object("HOUSECOLOR01", bm))
    ya, yb = CRANE_Y
    gx0, gx1 = GIRDER_X
    quads = []
    for y in (ya + 1.0 - 1.36, yb - 1.0 + 1.36):
        quads.append([(gx0 + 10, y, GIRDER_Z + 1.2), (gx1 - 4, y, GIRDER_Z + 1.2), (gx1 - 4, y, GIRDER_Z + 2.2),
                      (gx0 + 10, y, GIRDER_Z + 2.2)])
    objects.append(double_sided("HOUSECOLOR02", quads))
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
    if name in GLOWING:
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


def bake(objects, kind, image, top=24.0):
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
                glow = kind == "EMIT" and mat.name.split(".")[0] in GLOWING
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


def bake_building(builders, prefix, paint, ground, top):
    """Turns the builders into objects with one unique texture: unwraps them together, bakes colour,
    occlusion, windows and height, has the painter compose the textures; also bakes the pad's occlusion."""
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{prefix}_tiles")
    objects = []
    for name, builder in builders:
        # Each part stays a closed shape of its own (no merging of touching corners): the game builds
        # shadow volumes from these meshes, and they need closed shapes.
        bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
        obj = new_object(name, builder.bm)
        for surface in SURFACES:
            obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, tiles))
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
    bakes = os.path.join(BUILD, f"{prefix}_bakes")
    os.makedirs(bakes, exist_ok=True)
    for kind, file in (("DIFFUSE", "colour.png"), ("AO", "occlusion.png"), ("EMIT", "windows.png"),
                       ("HEIGHT", "height.png")):
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(objects, kind, image, top=top)
        save(image, os.path.join(bakes, file))
    plain = bpy.data.materials.new("pad bake")
    plain.use_nodes = True
    ground.data.materials.append(plain)
    image = bpy.data.images.new("pad_occlusion.png", 512, 512)
    bake([ground], "AO", image)
    save(image, os.path.join(bakes, "pad_occlusion.png"))
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, f"{prefix}_building.tga"))
    for obj in objects:
        textured(obj, baked)
    textured(ground, load_image(os.path.join(tex_dir, f"{prefix}_pad.tga")))
    return objects


def paint_tiles(prefix, paint):
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{prefix}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    for name in (f"{prefix}_emblem.tga", f"{prefix}_fence.tga"):
        shutil.copy(os.path.join(tiles, name), os.path.join(tex_dir, name))


def house_material(objects):
    colour = bpy.data.materials.get("house colour") or bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in objects:
        obj.data.materials.append(colour)


# The ground: the yard's concrete with its corners cut back on the far side, where the silos and the
# crane's machinery end, so it is not one more square pad.
PAD_OUTLINE = [(-44, -45), (44, -45), (44, 24), (34, 45), (-44, 45)]
EXTENT = (-44.0, 44.0, -45.0, 45.0)


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    paint = os.path.join(HERE, "logistics_centre_paint.py")
    paint_tiles(PREFIX, paint)
    main, intact, wreck = build_shapes()
    ground = pad_mesh(PAD_OUTLINE, EXTENT)
    objects = bake_building((("BUILDING", main), ("INTACT", intact), ("WRECK", wreck)), PREFIX, paint, ground,
                            top=44.0)
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, f"{PREFIX}_emblem.tga")))
    banners = house_colours()
    house_material(banners)
    wire = fence_mesh()
    textured(wire, load_image(os.path.join(tex_dir, f"{PREFIX}_fence.tga")))
    return dict(building=objects[0], intact=objects[1], wreck=objects[2], pad=ground, emblems=marks, banners=banners,
                fence=wire)


# --- writing the models ----------------------------------------------------------------------------

def dock_bones(model):
    """The bones SupplyCenterDockUpdate looks for (DockStart, DockAction, DockEnd, DockWaiting01..)."""
    for bone in ("DOCKSTART", "DOCKACTION", "DOCKEND"):
        model.bone(bone, w3d.CHASSIS, (*DOCK, DOCK_Z))
    for i, (x, y) in enumerate(WAITING, 1):
        model.bone(f"DOCKWAITING{i:02d}", w3d.CHASSIS, (x, y, DOCK_Z))
    for i, at in enumerate(SMOKE, 1):
        model.bone(f"SMOKE{i:02d}", w3d.CHASSIS, at)


def export(parts, version, night, name=NAME, prefix=PREFIX, bones=dock_bones):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(name + version + ("N" if night and version else "_N" if night else ""))
    bones(model)
    texture = f"{prefix}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    elif parts.get("wreck") is not None:
        model.mesh("WRECK", w3d.CHASSIS, **mesh_data(parts["wreck"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{prefix}_pad_e.tga" if version == "_E" else f"{prefix}_pad.tga", **flat)
    if version != "_E" and parts.get("fence") is not None:
        model.mesh("FENCE", w3d.CHASSIS, **mesh_data(parts["fence"]), texture=f"{prefix}_fence.tga", **flat)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{prefix}_emblem.tga", **flat)
    for obj in parts["banners"]:
        if version == "_E" and obj.name in parts.get("intact_banners", ()):
            continue
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    # The crane's stripes fall with its bridge.
    parts["intact_banners"] = ("HOUSECOLOR02",)
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

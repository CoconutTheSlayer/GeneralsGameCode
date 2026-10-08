"""The European Logistics Centre (the supply centre), modelled in Blender and written as W3D models for the
game: a warehouse with a vaulted steel roof and three roller doors, a two-storey office, a gantry crane over
the landing square where supply trucks and helicopters unload, two storage tanks, crates, pallets and
containers, on a concrete pad (after a concept painted in the game's style). It is made the way the
Command Centre is (command_centre.py), and Airlift Depot (airlift_depot.py) uses its machinery.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/logistics_centre.py

How it is painted: logistics_centre_paint.py paints small tiling surfaces; Blender projects them onto the
model, then bakes them and the ambient occlusion into one texture of the building's own; the painter adds
grime and makes the damaged, wrecked and night versions. Six models use them: EUSUPC (intact), _D, _E
(wrecked: no gantry, floodlights, fans or flag), each with a night version (_N, _DN, _EN).

The footprint is the USA's (88 long, 90 wide, centred). Gathering needs the dock's bones
(SupplyCenterDockUpdate): DOCKSTART, DOCKACTION and DOCKEND on the landing square, where trucks stop and
helicopters land, and DOCKWAITING01..09 round the outside, where they queue (the USA's places). Buildings
are placed turned by -45 degrees, so the corner at (+X, -Y), with the landing square, faces the camera.
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
    "container2": ("tile_container2", 8.0), "tank": ("tile_tank", 10.0), "pallet": ("tile_pallet", 3.0),
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

WAREHOUSE = (-42.0, 18.0, 14.0, 42.0, 10.0)     # x0, x1, y0, y1, wall top
OFFICE = (22.0, 42.0, 18.0, 42.0)               # x0, x1, y0, y1
DOCK = (22.0, -20.0)
DOCK_Z = PAD_Z
# Where trucks and helicopters queue to unload: the USA's places, round the outside of the footprint.
WAITING = [(67.61, -16.58), (67.61, 10.85), (67.61, 44.93), (46.04, 72.27), (5.27, 72.27), (-41.12, 72.27),
           (-79.49, 35.27), (-79.49, -7.79), (-79.49, -53.23)]
# Where the burning building smokes (ParticleSysBone in build_europe.py).
SMOKE = [(-30.0, 24.0, 18.0), (-6.0, 34.0, 17.0), (10.0, 22.0, 16.0), (32.0, 30.0, 14.0)]


def warehouse(b):
    """The warehouse: plaster walls on a plinth, a yellow band, a vaulted roof of corrugated steel with ribs,
    three roller doors with hazard frames facing the apron, small windows, roof fans."""
    x0, x1, y0, y1, top = WAREHOUSE
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.4))
    b.box("yellow", (x0 - 0.15, y0 - 0.15, top - 1.4), (x1 + 0.15, y1 + 0.15, top - 0.7))
    for x in (x0, -22.0, -2.0, x1):
        for y in (y0, y1):
            b.box("trim", (x - 1.2, y - 1.2, PAD_Z), (x + 1.2, y + 1.2, top + 0.6))
    # The vaulted roof: a segment of a circle across the hall, ribs over it.
    half, sag = (y1 - y0) / 2 + 0.8, 7.0
    radius = (half ** 2 + sag ** 2) / (2 * sag)
    cy, cz = (y0 + y1) / 2, top + sag - radius
    span = math.asin(half / radius)
    curve = arc(cy, cz, radius, math.pi / 2 + span, math.pi / 2 - span, 10)
    b.extrude_profile("rib", curve, x0 - 0.8, x1 + 0.8, cap_surface="trim")
    for x in (x0 - 0.8, -32.0, -22.0, -12.0, -2.0, 8.0, x1 - 0.2):
        outer = arc(cy, cz, radius + 0.35, math.pi / 2 + span, math.pi / 2 - span, 10)
        b.extrude_profile("trim", outer, x, x + 1.0)
    # The gable ends: plaster up to the curve.
    for x, face in ((x0, -1), (x1, 1)):
        gable = [(y0, top)] + arc(cy, cz, radius - 0.1, math.pi / 2 + span * 0.97, math.pi / 2 - span * 0.97, 10)[1:-1] + [(y1, top)]
        b.extrude_profile("wall", gable, x + face * 0.3 - 0.3, x + face * 0.3 + 0.3)
    # Roller doors with hazard frames, facing the apron (-Y).
    for x in (-32.0, -12.0, 6.0):
        b.box("hazard", (x - 5.4, y0 - 0.5, PAD_Z), (x + 5.4, y0, 8.6))
        b.box("shutter", (x - 4.4, y0 - 0.7, PAD_Z), (x + 4.4, y0 - 0.4, 7.6))
        b.box("dark", (x - 4.6, y0 - 1.5, 7.6), (x + 4.6, y0 - 0.2, 8.3))   # the roll box
        b.box("trim", (x - 4.0, y0 - 3.2, PAD_Z), (x + 4.0, y0 - 0.5, PAD_Z + 0.6))   # the ramp
    # Small windows high on the back and the ends.
    for x in range(int(x0) + 6, int(x1) - 2, 10):
        b.box("trim", (x - 0.3, y1, 6.0), (x + 3.3, y1 + 0.4, 8.4))
        b.box("glass", (x, y1 + 0.4, 6.3), (x + 3.0, y1 + 0.5, 8.1))
    b.box("trim", (x0 - 0.4, 24, 5.0), (x0, 30, 8.6))
    b.box("glass", (x0 - 0.5, 24.4, 5.4), (x0 - 0.4, 29.6, 8.2))
    # A side door at the west end.
    b.box("shutter", (x0 - 0.3, 33, PAD_Z), (x0, 37, 7.0))
    b.box("trim", (x0 - 1.5, 32.4, 7.0), (x0, 37.6, 7.6))
    # Drainpipes.
    for x in (-27.0, -7.0):
        b.box("metal", (x - 0.25, y0 - 0.5, PAD_Z), (x + 0.25, y0, top))


def roof_fans(b):
    x0, x1, y0, y1, top = WAREHOUSE
    peak = top + 7.0
    for x in (-34.0, -14.0, 6.0):
        b.box("metal", (x - 2.2, 26.0, peak - 0.4), (x + 2.2, 30.0, peak + 1.4))
        b.cylinder("grille", (x, 28.0, peak + 1.6), 1.6, 0.4, segments=8)


def office(b):
    """The two-storey office: plaster, steel blue-grey bands and cornice, rows of square windows, a door
    with a canopy towards the apron, roof machinery and a parapet."""
    x0, x1, y0, y1 = OFFICE
    top = 14.0
    b.box("office", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.5, y0 - 0.5, PAD_Z), (x1 + 0.5, y1 + 0.5, 2.2))
    b.box("trim", (x0 - 0.3, y0 - 0.3, 7.4), (x1 + 0.3, y1 + 0.3, 8.2))            # band between floors
    ring(b, "trim", x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6, top - 0.8, top + 1.0, 1.2)  # parapet
    b.box("deck", (x0 + 0.6, y0 + 0.6, top), (x1 - 0.6, y1 - 0.6, top + 0.2))
    # Windows on the front (-Y) and the side (+X), both floors.
    for z in (3.6, 9.4):
        for x in (x0 + 3.0, x0 + 14.0):   # the door and the faction's mark between them
            b.box("trim", (x - 0.3, y0 - 0.4, z - 0.3), (x + 3.3, y0, z + 2.9))
            b.box("glass", (x, y0 - 0.5, z), (x + 3.0, y0 - 0.4, z + 2.6))
        for y in (y0 + 3.0, y0 + 9.0, y0 + 15.0, y0 + 20.0):
            b.box("trim", (x1, y - 0.3, z - 0.3), (x1 + 0.4, y + 3.3, z + 2.9))
            b.box("glass", (x1 + 0.4, y, z), (x1 + 0.5, y + 3.0, z + 2.6))
    # The door and its canopy.
    b.box("dark", (x0 + 8.3, y0 - 0.3, PAD_Z), (x0 + 12.2, y0, 6.4))
    b.box("shutter", (x0 + 8.6, y0 - 0.4, PAD_Z), (x0 + 11.9, y0 - 0.3, 6.0))
    b.box("trim", (x0 + 7.4, y0 - 3.0, 6.6), (x0 + 13.1, y0, 7.2))
    for k in range(2):
        b.box("trim", (x0 + 8.0, y0 - 1.2 - k * 1.0, PAD_Z), (x0 + 12.5, y0, PAD_Z + 0.9 - k * 0.4))
    # Roof machinery.
    b.box("metal", (x0 + 3, y0 + 12, top), (x0 + 10, y0 + 19, top + 3.0))
    b.box("grille", (x0 + 3.2, y0 + 11.9, top + 0.5), (x0 + 9.8, y0 + 12.0, top + 2.6))
    b.cylinder("metal", (x1 - 5, y1 - 5, top + 1.0), 2.4, 2.0, segments=10)
    b.cylinder("dark", (x1 - 5, y1 - 5, top + 2.05), 2.0, 0.1, segments=10)


def office_mast(b):
    x0, x1, y0, y1 = OFFICE
    b.cylinder("metal", (x1 - 3, y0 + 4, 14.0 + 5.0), 0.2, 10.0, segments=6)
    b.cylinder("metal", (x1 - 6, y0 + 4, 14.0 + 3.5), 0.2, 7.0, segments=6)
    b.sphere("red", (x1 - 3, y0 + 4, 24.2), 0.4, segments=(6, 4))


def gantry(b):
    """A gantry crane straddling the landing square: four legs, two girders along X, a bridge with a
    trolley and a hoist hook. High and wide enough for a helicopter to land beneath."""
    dx, dy = DOCK
    xa, xb, ya, yb, top = dx - 15.0, dx + 15.0, dy - 14.0, dy + 14.0, 16.0
    for x in (xa, xb):
        for y in (ya, yb):
            b.box("trim", (x - 1.4, y - 1.4, PAD_Z), (x + 1.4, y + 1.4, PAD_Z + 1.2))   # footing
            b.box("yellow", (x - 0.7, y - 0.7, PAD_Z + 1.2), (x + 0.7, y + 0.7, top))
        b.beam("yellow", (x, ya + 0.6, PAD_Z + 1.4), (x, ya + 4.5, 6.0), 0.4)          # braces
        b.beam("yellow", (x, yb - 0.6, PAD_Z + 1.4), (x, yb - 4.5, 6.0), 0.4)
        b.box("trim", (x - 0.9, ya - 0.9, top), (x + 0.9, yb + 0.9, top + 2.0))           # end girders
    for y in (ya, yb):
        b.box("hazard", (xa - 0.9, y - 0.8, top + 2.0), (xb + 0.9, y + 0.8, top + 3.2))   # running girders
    # The bridge along Y with the trolley and hook, parked over the landing square's edge.
    bx = dx + 12.0
    b.box("trim", (bx - 1.0, ya - 0.8, top + 3.2), (bx + 1.0, yb + 0.8, top + 4.4))
    b.box("metal", (bx - 1.6, dy - 2.0, top + 0.8), (bx + 1.6, dy + 2.0, top + 3.2))
    b.box("dark", (bx - 0.8, dy - 2.4, top + 3.2), (bx + 0.8, dy - 0.8, top + 4.8))   # the cab on top
    b.cylinder("dark", (bx, dy, top - 2.5), 0.12, 6.0, segments=4)
    b.box("yellow", (bx - 0.6, dy - 0.6, top - 6.2), (bx + 0.6, dy + 0.6, top - 5.4))
    # A container hanging from it, clear of a landing helicopter's rotor.
    container(b, bx, dy, 9.0, along="Y", surface="container", z=top - 11.8)


def tanks(b):
    """Two horizontal storage tanks on concrete saddles, with yellow bands and a ladder to a walkway."""
    for x in (-36.0, -24.0):
        y0, y1, r = -40.0, -16.0, 4.6
        for y in (y0 + 4, (y0 + y1) / 2, y1 - 4):
            b.box("trim", (x - 3.6, y - 1.0, PAD_Z), (x + 3.6, y + 1.0, PAD_Z + 3.6))
        b.cylinder("tank", (x, (y0 + y1) / 2, PAD_Z + 2.2 + r), r, y1 - y0, axis="Y", segments=14)
        for y in (y0, y1):
            b.sphere("tank", (x, y, PAD_Z + 2.2 + r), r, scale=(1, 0.35, 1), segments=(14, 6))
        for y in (y0 + 6, y1 - 6):
            b.cylinder("yellow", (x, y, PAD_Z + 2.2 + r), r + 0.12, 1.0, axis="Y", segments=14)
        b.cylinder("metal", (x, y1 - 3, PAD_Z + 2.2 + 2 * r + 0.4), 0.8, 1.0, segments=8)   # hatch
    # A walkway between the tanks with a ladder.
    b.box("metal", (-31.4, -36.0, PAD_Z + 11.0), (-28.6, -20.0, PAD_Z + 11.4))
    for y in (-36.0, -20.0):
        b.box("metal", (-31.4, y - 0.2, PAD_Z), (-31.0, y + 0.2, PAD_Z + 12.6))
        b.box("metal", (-29.0, y - 0.2, PAD_Z), (-28.6, y + 0.2, PAD_Z + 12.6))
    for z in range(2, 12, 2):
        b.box("metal", (-31.0, -36.1, PAD_Z + z), (-29.0, -35.9, PAD_Z + z + 0.25))
    # A pipe from the tanks to the warehouse.
    b.cylinder("metal", (-30.0, -2.0, PAD_Z + 1.4), 0.6, 28.0, axis="Y", segments=8)
    b.cylinder("metal", (-30.0, 12.0, PAD_Z + 4.4), 0.6, 6.0, segments=8)


def clutter(b):
    """Crates, pallets, containers, barriers and floodlights round the apron."""
    crate_stack(b, -12.0, -38.0, [(0, 0, 2), (1, 0, 1), (0, 1, 1), (1, 1, 2), (2, 0, 1)])
    crate_stack(b, 13.0, 6.0, [(0, 0, 1), (1, 0, 2)], size=3.6)
    crate_stack(b, -40.0, -6.0, [(0, 0, 2), (0, 1, 1), (1, 0, 1)])
    for x, y, n in ((2.0, -40.0, 3), (8.0, -40.0, 2), (-22.0, 5.0, 2)):
        for k in range(n):
            b.box("pallet", (x - 2.4, y - 2.4, PAD_Z + k * 0.7), (x + 2.4, y + 2.4, PAD_Z + (k + 1) * 0.7 - 0.08))
    container(b, -37.0, 6.0, 10.0, along="X", surface="container2")
    container(b, -37.0, 6.0, 10.0, along="X", surface="container", z=PAD_Z + 5.2)
    container(b, 40.0, 8.0, 10.0, along="Y", surface="container2")
    for x in range(-8, 8, 4):   # barriers along the front edge
        b.box("trim", (x - 1.6, -43.6, PAD_Z), (x + 1.6, -42.6, PAD_Z + 1.8))
    # A flagpole between the warehouse and the office.
    b.box("trim", (18.6, 8.6, PAD_Z), (21.4, 11.4, PAD_Z + 1.4))


def lights_and_flag(b):
    floodlight(b, 41.0, -42.0, facing=math.radians(135))
    floodlight(b, -41.0, -42.0, facing=math.radians(45))
    floodlight(b, -22.0, 10.5, height=12.0, facing=math.radians(-90))
    b.cylinder("metal", (20.0, 10.0, PAD_Z + 11.0), 0.25, 22.0, segments=6)
    b.sphere("yellow", (20.0, 10.0, PAD_Z + 22.2), 0.4, segments=(6, 4))


FENCE = [((-43.0, -44.0), (-43.0, 12.0)), ((-43.0, -44.0), (-16.0, -44.0))]
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
    main, intact = Builder(), Builder()
    warehouse(main)
    office(main)
    tanks(main)
    clutter(main)
    fence_posts(main)
    gantry(intact)
    roof_fans(intact)
    office_mast(intact)
    lights_and_flag(intact)
    return main, intact


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
    """The faction's mark on the warehouse's west gable, and over the office door."""
    x0, x1, y0, y1, top = WAREHOUSE
    marks = [decal("EMBLEM", [(x0 - 0.65, 32.0, 10.6), (x0 - 0.65, 24.0, 10.6), (x0 - 0.65, 24.0, 16.0),
                              (x0 - 0.65, 32.0, 16.0)])]
    ox0, ox1, oy0, oy1 = OFFICE
    marks.append(decal("EMBLEM2", [(ox0 + 8.2, oy0 - 0.45, 8.5), (ox0 + 12.0, oy0 - 0.45, 8.5),
                                   (ox0 + 12.0, oy0 - 0.45, 12.3), (ox0 + 8.2, oy0 - 0.45, 12.3)]))
    return marks


def double_sided(name, quads):
    bm = bmesh.new()
    for quad in quads:
        bm.faces.new([bm.verts.new(v) for v in quad])
        bm.faces.new([bm.verts.new(v) for v in reversed(quad)])
    return new_object(name, bm)


def house_colours():
    """The player's colour: a band under the office's parapet, stripes on the gantry's girders, the flag."""
    x0, x1, y0, y1 = OFFICE
    objects = []
    bm = bmesh.new()
    z0, z1 = 12.5, 13.1
    pts = [(x0 - 0.12, y0 - 0.12), (x1 + 0.12, y0 - 0.12), (x1 + 0.12, y1 + 0.12), (x0 - 0.12, y1 + 0.12)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        bm.faces.new([bm.verts.new(v) for v in ((ax, ay, z0), (bx, by, z0), (bx, by, z1), (ax, ay, z1))])
    objects.append(new_object("HOUSECOLOR01", bm))
    dx, dy = DOCK
    quads = []
    for y, face in ((dy - 14.0 - 0.85, -1), (dy + 14.0 + 0.85, 1)):
        quads.append([(dx - 10, y, 16.0 + 2.2), (dx + 10, y, 16.0 + 2.2), (dx + 10, y, 16.0 + 3.0), (dx - 10, y, 16.0 + 3.0)])
    objects.append(double_sided("HOUSECOLOR02", quads))
    objects.append(double_sided("HOUSECOLOR03", [[(20.2, 10.3, 21.5), (20.2, 17.0, 21.5), (20.2, 17.0, 17.5),
                                                  (20.2, 10.3, 17.5)]]))
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


PAD_OUTLINE = [(-44, -45), (44, -45), (44, 45), (-44, 45)]
EXTENT = (-44.0, 44.0, -45.0, 45.0)


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    paint = os.path.join(HERE, "logistics_centre_paint.py")
    paint_tiles(PREFIX, paint)
    main, intact = build_shapes()
    ground = pad_mesh(PAD_OUTLINE, EXTENT)
    objects = bake_building((("BUILDING", main), ("INTACT", intact)), PREFIX, paint, ground, top=24.0)
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, f"{PREFIX}_emblem.tga")))
    banners = house_colours()
    house_material(banners)
    wire = fence_mesh()
    textured(wire, load_image(os.path.join(tex_dir, f"{PREFIX}_fence.tga")))
    return dict(building=objects[0], intact=objects[1], pad=ground, emblems=marks, banners=banners, fence=wire)


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
    # The gantry's stripes and the flag go with the gantry and the flagpole.
    parts["intact_banners"] = ("HOUSECOLOR02", "HOUSECOLOR03")
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

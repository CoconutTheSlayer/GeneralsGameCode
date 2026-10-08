"""The European Garrison (barracks), modelled in Blender and written as W3D models for the game: an angular
L-shaped quarters block (a three-storey wing along the back, a two-storey wing down the side) with flat roofs,
dark parapets, steel-blue window bands and taller bare-concrete stair cores; a tall watchtower with an
octagonal glazed cab by the gate; a steel rappelling tower with ropes and a cargo net; a firing range with
target frames before an earth backstop; a gravel drill yard in the middle and a gate in a low wall at the
front (+X), where the infantry march out (after a concept painted in the game's style, in the Command
Centre's manner but with a silhouette of its own: no curved roofs).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/garrison.py

Painted as the Command Centre and the Fusion Plant (the shapes, baking and export helpers come from
fusion_plant.py; garrison_paint.py paints the tiles and composes the texture). Models: EUBARR (intact),
_D, _E (wrecked: the watchtower's cab, the roof plant, the net, the boom and the flag gone, rubble on the
roofs), each with a night version (_N, _DN, _EN) with lit window bands.

The footprint is the USA's (110 long, 90 wide, 20 high, centred). The ground is cut to the compound's shape
(the pad's texture is see-through outside it). New infantry appear in the drill yard (the parent's
UnitCreatePoint, 0 0 0) and walk out of the gate to its NaturalRallyPoint (55 0 0); healed infantry leave
along the bones EXITSTART -> EXITEND, through the gate (HealContain, OpenContain.cpp). The lane along y = 0
stays clear. Bones for the damage effects: SMOKE01/02, FIRE01/02.
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
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, textured  # noqa: E402
from fusion_plant import (BUILD, DATA, Builder, bake_building, bake_pad, both_ways, flat_object,  # noqa: E402
                          model_name, pad_object, ring, surface_material)
import w3d  # noqa: E402

NAME = "EUBARR"
PREFIX = "eubr"
PAD_Z = 0.6
PAD = (-56.0, 56.0, -46.0, 46.0)
SURFACES = {
    "wall": ("tile_wall", 16.0), "concrete": ("tile_concrete", 14.0), "trim": ("tile_trim", 12.0),
    "deck": ("tile_deck", 12.0), "door": ("tile_door", 10.0), "metal": ("tile_metal", 6.0),
    "hazard": ("tile_hazard", 3.0), "grille": ("tile_grille", 3.0), "sandbag": ("tile_sandbag", 4.0),
    "earth": ("tile_earth", 12.0), "band": ("tile_band", 4.0),
    "glass": (40, 72, 92), "dark": (30, 32, 36), "yellow": (222, 182, 46), "red": (196, 52, 40),
    "white": (232, 230, 222), "rope": (176, 150, 104), "olive": (88, 100, 72), "wood": (150, 118, 80),
}
STOREY = 5.6
MAIN_WING = (-50.0, 16.0, 27.0, 42.0, 3)         # x0, x1, y0, y1, storeys
SIDE_WING = (-50.0, -36.0, -16.0, 27.0, 2)
CORES = [(-41.0, -33.0, 21.0, 31.0, 23.6), (16.0, 23.0, 31.0, 40.0, 22.0)]   # x0, x1, y0, y1, top
PIER = (-17.0, -8.0)                              # the entrance pier on the main wing, with the mark
EMBLEM2_X = (-46.0, -40.0)                        # the mark on the side wing's end
TOWER = (44.0, -36.0)                            # the watchtower
SHAFT_TOP, CAB_TOP = 27.0, 34.6
RAPPEL = (38.0, 31.0, 4.5, 26.0)                 # centre x, y, half size, top
RANGE = (-50.0, 20.0, -44.0, -24.0)              # x0, x1, y0, y1 of the firing range
TARGETS_X = 8.5
GATE_X, GATE_HALF = 50.0, 8.0
FLAG = (46.0, 17.0)
EXITSTART, EXITEND = (28.0, 0.0, PAD_Z), (62.0, 0.0, PAD_Z)
BONES = {"SMOKE01": (-24.0, 35.0, 17.0), "SMOKE02": (-43.0, 0.0, 12.0),
         "FIRE01": (TOWER[0], TOWER[1], SHAFT_TOP), "FIRE02": (-2.0, 26.0, 6.0)}


def top_of(storeys):
    return PAD_Z + storeys * STOREY + 0.8


def frustum(b, surface, lo, hi, z0, z1):
    """A closed block whose bottom (x0, x1, y0, y1) at z0 narrows to its top at z1 (berms, footings)."""
    def make(bm):
        a = [bm.verts.new((x, y, z0)) for x, y in ((lo[0], lo[2]), (lo[1], lo[2]), (lo[1], lo[3]), (lo[0], lo[3]))]
        c = [bm.verts.new((x, y, z1)) for x, y in ((hi[0], hi[2]), (hi[1], hi[2]), (hi[1], hi[3]), (hi[0], hi[3]))]
        bm.faces.new(list(reversed(a)))
        bm.faces.new(c)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((a[i], a[j], c[j], c[i]))
    b.add(surface, make)


def beam(b, surface, a, c, thickness):
    """A square bar from a to c."""
    axis = Vector(c) - Vector(a)
    rot = Vector((0, 0, 1)).rotation_difference(axis.normalized()).to_matrix().to_4x4()
    centre = (Vector(a) + Vector(c)) / 2
    b.add(surface, lambda bm: bmesh.ops.create_cube(
        bm, size=1.0, matrix=Matrix.Translation(centre) @ rot @ Matrix.Diagonal((thickness, thickness, axis.length, 1.0))))


def band(b, axis, at, out, lo, hi, z0, z1):
    """A steel-blue window band on a wall: a frame standing out of the wall, the glazing in front of it.
    axis "X": the wall faces along x (at its x, out = +1 or -1), the band runs along y from lo to hi."""
    def span(d0, d1, s0, s1, za, zb):
        if axis == "X":
            return (at + out * d0, s0, za), (at + out * d1, s1, zb)
        return (s0, at + out * d0, za), (s1, at + out * d1, zb)
    b.box("trim", *span(0.0, 0.3, lo, hi, z0 - 0.35, z1 + 0.35))
    b.box("band", *span(0.3, 0.4, lo + 0.25, hi - 0.25, z0, z1))


def wing(main, rect, skip=(), gaps=None):
    """A flat-roofed block of quarters: plaster over a concrete plinth, one window band a storey on every
    side (skip: sides left blank, "-X", "+X", "-Y", "+Y"; gaps: {side: [(lo, hi)]}, spans left out of a
    side's bands), a dark parapet round a roof deck. Returns the roof's height."""
    gaps = gaps or {}
    x0, x1, y0, y1, storeys = rect
    top = top_of(storeys)
    main.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    main.box("concrete", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.0))
    ring(main, "trim", x0 - 0.5, x1 + 0.5, y0 - 0.5, y1 + 0.5, top - 0.6, top + 1.0, 1.0)
    main.box("deck", (x0 + 0.5, y0 + 0.5, top - 0.2), (x1 - 0.5, y1 - 0.5, top + 0.2))
    for k in range(storeys):
        z0 = PAD_Z + 2.6 + k * STOREY
        z1 = z0 + 2.0
        for side, axis, at, out, lo, hi in (("-Y", "Y", y0, -1, x0, x1), ("+Y", "Y", y1, 1, x0, x1),
                                            ("-X", "X", x0, -1, y0, y1), ("+X", "X", x1, 1, y0, y1)):
            if side in skip:
                continue
            edges = [lo + 1.5] + [e for g in gaps.get(side, ()) for e in g] + [hi - 1.5]
            for a, c in zip(edges[::2], edges[1::2]):
                band(main, axis, at, out, a, c, z0, z1)
    return top


def quarters(main, intact):
    """The L of quarters, its stair cores, the entrance pier with the faction's mark and the roof plant."""
    top = wing(main, MAIN_WING, gaps={"-Y": [PIER]})
    side = wing(main, SIDE_WING, skip=("+Y",), gaps={"+X": [(1.0, 7.0)], "-Y": [EMBLEM2_X]})
    # The entrance pier: bare concrete, standing out of the main wing and above its parapet.
    x0, x1 = PIER
    y0 = MAIN_WING[2]
    main.box("concrete", (x0, y0 - 1.2, PAD_Z), (x1, y0 + 1.0, top + 1.6))
    main.box("trim", (x0 - 0.3, y0 - 1.5, top + 1.4), (x1 + 0.3, y0 + 1.0, top + 2.2))
    main.box("door", (x0 + 2.2, y0 - 1.35, PAD_Z), (x1 - 2.2, y0 - 1.2, 6.0))
    main.box("trim", (x0 - 1.0, y0 - 4.2, 6.6), (x1 + 1.0, y0 - 1.2, 7.3))           # the canopy
    for k in range(3):
        main.box("concrete", (x0 + 1.4, y0 - 2.2 - k * 1.0, PAD_Z), (x1 - 1.4, y0 - 1.2, PAD_Z + 0.9 - k * 0.3))
    # A door from the side wing to the yard (+X), under a canopy.
    sx1 = SIDE_WING[1]
    main.box("door", (sx1, 2.0, PAD_Z), (sx1 + 0.15, 6.0, 5.6))
    main.box("trim", (sx1, 1.0, 6.0), (sx1 + 2.6, 7.0, 6.6))
    main.box("hazard", (sx1, 1.4, PAD_Z), (sx1 + 0.2, 1.9, 5.6))
    # Stair cores: bare concrete towers rising over the roofs, a slit of glass up each.
    for cx0, cx1, cy0, cy1, ctop in CORES:
        main.box("concrete", (cx0, cy0, PAD_Z), (cx1, cy1, ctop))
        main.box("trim", (cx0 - 0.4, cy0 - 0.4, ctop - 0.4), (cx1 + 0.4, cy1 + 0.4, ctop + 0.6))
        main.box("glass", ((cx0 + cx1) / 2 - 0.9, cy0 - 0.12, 3.0), ((cx0 + cx1) / 2 + 0.9, cy0, ctop - 2.0))
    main.box("glass", (CORES[1][1], 34.6, 3.0), (CORES[1][1] + 0.12, 36.4, CORES[1][4] - 2.0))
    main.box("glass", (CORES[0][0] - 0.12, 25.1, 3.0), (CORES[0][0], 26.9, side - 1.0))
    # The roof plant: air conditioners, a water tank, aerials.
    for x, y in ((-44.0, 36.0), (-30.0, 36.5), (-4.0, 36.0), (6.0, 35.0)):
        intact.box("metal", (x - 2.4, y - 2.0, top + 0.2), (x + 2.4, y + 2.0, top + 2.6))
        intact.cylinder("dark", (x, y, top + 2.65), 1.5, 0.1, segments=8)
        intact.box("grille", (x - 2.0, y - 2.1, top + 0.6), (x + 2.0, y - 2.0, top + 2.2))
    intact.box("metal", (-47.0, -8.0, side + 0.2), (-40.0, -2.0, side + 2.0))
    intact.box("grille", (-47.1, -7.4, side + 0.5), (-47.0, -2.6, side + 1.7))
    intact.cylinder("concrete", (-43.0, 12.0, side + 2.4), 2.2, 4.4, segments=8)
    intact.cylinder("metal", (-22.0, 39.0, top + 5.0), 0.15, 10.0, segments=4)
    intact.cylinder("metal", (-19.0, 39.0, top + 3.5), 0.15, 7.0, segments=4)
    intact.cylinder("red", (-22.0, 39.0, top + 10.2), 0.3, 0.4, segments=6)


def watchtower(main, intact):
    """A slender concrete shaft with slit windows and a ladder cage, and an octagonal glazed cab on top
    (in `intact`), sandbags round its foot."""
    x, y = TOWER
    h = 2.5
    main.box("concrete", (x - h - 0.6, y - h - 0.6, PAD_Z), (x + h + 0.6, y + h + 0.6, 2.4))
    main.box("concrete", (x - h, y - h, PAD_Z), (x + h, y + h, SHAFT_TOP))
    for z in (7.0, 14.0, 21.0):
        main.box("trim", (x - h - 0.2, y - h - 0.2, z), (x + h + 0.2, y + h + 0.2, z + 0.6))
    for z in (4.0, 10.5, 17.0, 23.0):
        main.box("glass", (x - h - 0.1, y - 0.6, z), (x - h, y + 0.6, z + 2.2))
        main.box("glass", (x - 0.6, y - h - 0.1, z), (x + 0.6, y - h, z + 2.2))
    main.box("door", (x + h, y - 1.2, PAD_Z), (x + h + 0.12, y + 1.2, 5.0))
    main.box("metal", (x + h, y + 1.6, PAD_Z), (x + h + 1.2, y + 2.2, SHAFT_TOP))      # the ladder's cage
    # The cab: a flared octagonal platform, a band of glass, an overhanging roof.
    r = 3.6
    profile = [(r, SHAFT_TOP - 0.6), (r + 1.6, SHAFT_TOP + 0.8), (r + 1.6, SHAFT_TOP + 1.4), (r + 1.2, SHAFT_TOP + 1.4),
               (r + 1.2, CAB_TOP - 2.0), (r + 2.0, CAB_TOP - 1.6), (r + 2.0, CAB_TOP - 0.8), (1.0, CAB_TOP), (0.0, CAB_TOP + 0.1)]
    intact.lathe("trim", (x, y, 0.0), profile, segments=8, rotate=math.pi / 8,
                 surfaces=["concrete", "trim", "trim", "glass", "trim", "trim", "deck", "deck"])
    intact.cylinder("metal", (x + 1.0, y + 1.0, CAB_TOP + 3.5), 0.15, 7.0, segments=4)
    intact.cylinder("red", (x + 1.0, y + 1.0, CAB_TOP + 7.2), 0.3, 0.4, segments=6)
    intact.turned_box("dark", (x - 3.2, y - 3.2, CAB_TOP - 1.0), (1.2, 1.0, 0.8), math.radians(45))   # searchlight
    for (ax, ay), (bx, by) in (((x - 6.0, y - 6.0), (x + 6.0, y - 6.0)), ((x - 6.0, y - 4.0), (x - 6.0, y + 4.0))):
        main.box("sandbag", (min(ax, bx) - 1.0, min(ay, by) - 1.0, PAD_Z), (max(ax, bx) + 1.0, max(ay, by) + 1.0, PAD_Z + 2.0))


def rappel_tower(main, intact):
    """A steel training tower: four posts, two platforms, cross braces; ropes down its side, a cargo net
    from its first platform to the yard (in `intact`)."""
    cx, cy, h, top = RAPPEL
    x0, x1, y0, y1 = cx - h, cx + h, cy - h, cy + h
    for x in (x0, x1):
        for y in (y0, y1):
            main.box("concrete", (x - 1.0, y - 1.0, PAD_Z), (x + 1.0, y + 1.0, PAD_Z + 0.8))
            main.box("trim", (x - 0.4, y - 0.4, PAD_Z), (x + 0.4, y + 0.4, top + 1.2))
    for z in (12.0, top):
        main.box("deck", (x0 - 0.3, y0 - 0.3, z - 0.4), (x1 + 0.3, y1 + 0.3, z + 0.1))
        main.box("yellow", (x0 - 0.3, y0 - 0.4, z + 1.1), (x1 + 0.3, y0 - 0.2, z + 1.3))      # rails
        main.box("yellow", (x0 - 0.4, y0 - 0.3, z + 1.1), (x0 - 0.2, y1 + 0.3, z + 1.3))
    for (ax, ay), (bx, by) in (((x0, y1), (x1, y1)), ((x1, y0), (x1, y1))):
        beam(main, "trim", (ax, ay, PAD_Z + 0.8), (bx, by, 12.0), 0.3)
        beam(main, "trim", (bx, by, 12.0), (ax, ay, top - 0.4), 0.3)
    main.box("wood", (x0 - 0.5, y0 + 0.6, PAD_Z), (x0 - 0.2, y1 - 0.6, 11.0))                  # climbing wall
    for k, y in enumerate((y0 + 1.6, cy, y1 - 1.6)):
        intact.box("rope", (x0 - 1.2, y - 0.15, PAD_Z + 0.4 + k * 1.5), (x0 - 0.9, y + 0.15, top))
        intact.box("metal", (x0 - 1.6, y - 0.3, top - 0.3), (x0, y + 0.3, top))
    # The cargo net, sloping from the first platform's edge down to the ground on the yard's side.
    za, ya, yb = 12.0, y0, y0 - 6.0
    for k in range(5):
        t = k / 4
        z, y = za + (PAD_Z + 0.2 - za) * t, ya + (yb - ya) * t
        intact.box("rope", (x0 + 0.3, y - 0.12, z - 0.12), (x1 - 0.3, y + 0.12, z + 0.12))
    for k in range(6):
        x = x0 + 0.6 + k * (2 * h - 1.2) / 5
        beam(intact, "rope", (x, ya, za), (x, yb, PAD_Z + 0.2), 0.22)


def firing_range(main, intact):
    """Shooting lanes along the -Y side: a roofed firing point behind sandbags at the -X end, target frames
    before an earth backstop at the +X end, low earth banks along the outer side."""
    x0, x1, y0, y1 = RANGE
    frustum(main, "earth", (x1 - 9.0, x1 + 1.0, y0 - 1.0, y1 + 2.0), (x1 - 6.0, x1 - 2.0, y0 + 0.5, y1), PAD_Z - 0.4, 6.4)
    frustum(main, "earth", (x0 + 6.0, x1 - 8.0, y0 - 1.5, y0 + 3.0), (x0 + 8.0, x1 - 9.0, y0 - 0.5, y0 + 1.2), PAD_Z - 0.4, 2.6)
    # The firing point: a flat concrete roof on posts, a sandbag parapet.
    fx0, fx1 = x0 + 1.0, x0 + 8.0
    for x in (fx0, fx1 - 0.6):
        for y in (y0 + 1.0, y1 - 1.6):
            main.box("trim", (x, y, PAD_Z), (x + 0.6, y + 0.6, 5.0))
    main.box("concrete", (fx0 - 0.6, y0 + 0.4, 5.0), (fx1 + 0.6, y1 - 0.8, 5.8))
    main.box("trim", (fx0 - 0.8, y0 + 0.2, 5.6), (fx1 + 0.8, y1 - 0.6, 6.0))
    main.box("concrete", (fx0 - 0.4, y0 + 1.0, PAD_Z), (fx0 + 0.2, y1 - 1.0, 3.4))          # back wall
    main.box("sandbag", (fx1 - 0.4, y0 + 1.0, PAD_Z), (fx1 + 1.4, y1 - 1.6, PAD_Z + 1.4))
    # Target frames, facing the firing point.
    for y in (-40.5, -36.0, -31.5, -27.0):
        for dy in (-1.4, 1.4):
            main.box("metal", (TARGETS_X - 0.15, y + dy - 0.15, PAD_Z), (TARGETS_X + 0.15, y + dy + 0.15, 4.6))
        intact.box("white", (TARGETS_X - 0.35, y - 1.3, 1.8), (TARGETS_X - 0.15, y + 1.3, 4.4))
    # Ammunition boxes by the firing point, a low concrete kerb between the range and the yard.
    for k in range(3):
        main.box("olive", (fx1 + 2.0 + k * 1.8, y1 - 3.0, PAD_Z), (fx1 + 3.4 + k * 1.8, y1 - 2.0, PAD_Z + 1.0))
    main.box("concrete", (fx1 + 1.0, y1 - 0.2, PAD_Z), (x1 - 9.0, y1 + 0.6, PAD_Z + 1.2))


def gate(main, intact):
    """A low concrete wall along the front with a gate, its posts striped, a boom raised (in `intact`)."""
    for side in (-1, 1):
        ya, yb = side * (GATE_HALF + 2.6), side * 44.0
        main.box("concrete", (GATE_X, min(ya, yb), PAD_Z), (GATE_X + 1.2, max(ya, yb), 3.6))
        main.box("trim", (GATE_X - 0.2, min(ya, yb), 3.4), (GATE_X + 1.4, max(ya, yb), 3.9))
        pa, pb = side * GATE_HALF, side * (GATE_HALF + 2.6)
        main.box("concrete", (GATE_X - 0.8, min(pa, pb), PAD_Z), (GATE_X + 2.0, max(pa, pb), 6.6))
        main.box("trim", (GATE_X - 1.0, min(pa, pb) - 0.2, 6.4), (GATE_X + 2.2, max(pa, pb) + 0.2, 7.0))
        main.box("hazard", (GATE_X - 0.9, min(pa, pb) + 0.2, 1.4), (GATE_X - 0.8, max(pa, pb) - 0.2, 2.6))
    intact.box("metal", (GATE_X + 0.4, -GATE_HALF + 0.1, PAD_Z), (GATE_X + 1.2, -GATE_HALF + 0.9, 4.4))
    beam(intact, "hazard", (GATE_X + 0.8, -GATE_HALF + 0.5, 4.0), (GATE_X + 0.8, -GATE_HALF + 2.4, 14.0), 0.4)
    # The flagpole inside the gate.
    fx, fy = FLAG
    main.lathe("concrete", (fx, fy, PAD_Z), [(2.2, 0), (2.2, 0.9), (1.2, 0.9), (1.2, 1.5), (0, 1.5)], segments=8)
    intact.cylinder("metal", (fx, fy, PAD_Z + 10.5), 0.22, 18.0, segments=6)
    intact.cylinder("yellow", (fx, fy, PAD_Z + 19.7), 0.4, 0.4, segments=6)


def yard(main):
    """Sandbags and a few crates round the edges of the drill yard (its middle and the lane stay clear)."""
    for (ax, ay), (bx, by) in (((-30.0, 22.0), (-22.0, 22.0)), ((28.0, -18.0), (28.0, -10.0)), ((24.0, 10.0), (24.0, 18.0))):
        main.box("sandbag", (min(ax, bx) - 1.0, min(ay, by) - 1.0, PAD_Z), (max(ax, bx) + 1.0, max(ay, by) + 1.0, PAD_Z + 1.8))
    for cx, cy, z in ((-31.0, -12.0, 0.0), (-31.0, -8.6, 0.0), (-31.0, -10.3, 1.7)):
        main.box("olive", (cx - 1.6, cy - 1.6, PAD_Z + z), (cx + 1.6, cy + 1.6, PAD_Z + z + 1.7))
    # A pull-up frame and parallel bars by the side wing.
    for y in (-10.0, -2.0):
        main.box("metal", (-30.2, y - 0.15, PAD_Z), (-29.8, y + 0.15, 5.6))
    main.box("metal", (-30.2, -10.0, 5.3), (-29.8, -2.0, 5.6))


def wreckage(wreck):
    """What lies about when it burns out: the cab's wreck at the tower's foot, broken parapets on the roofs."""
    x, y = TOWER
    for k, (dx, dy, a) in enumerate(((-4.5, 2.0, 0.4), (-2.0, -5.0, 1.3), (4.5, -3.0, 2.2))):
        wreck.turned_box("trim" if k else "deck", (x + dx, y + dy, PAD_Z + 0.8), (5.0, 3.0, 1.6), a)
    top = top_of(MAIN_WING[4])
    for k, (bx, a) in enumerate(((-42.0, 0.3), (-26.0, 2.0), (2.0, 1.1), (10.0, 2.6))):
        wreck.turned_box("concrete", (bx, 34.0 + (k % 2) * 3, top + 0.6), (6.0, 3.0, 1.2), a)
    side = top_of(SIDE_WING[4])
    wreck.turned_box("trim", (-43.0, 6.0, side + 0.5), (8.0, 1.0, 1.0), 0.9)
    wreck.turned_box("wall", (-34.0, 14.0, PAD_Z + 0.8), (5.0, 3.0, 1.6), 0.5)


def emblems():
    """The faction's mark on the entrance pier and on the side wing's end."""
    x0, x1 = PIER
    y = MAIN_WING[2] - 1.26
    top = top_of(MAIN_WING[4])
    pier = flat_object("EMBLEM", [[(x0 + 1.0, y, top - 7.0), (x1 - 1.0, y, top - 7.0), (x1 - 1.0, y, top), (x0 + 1.0, y, top)]])
    ex0, ex1 = EMBLEM2_X
    ey = SIDE_WING[2] - 0.06
    end = flat_object("EMBLEM2", [[(ex0 + 0.4, ey, 3.4), (ex1 - 0.4, ey, 3.4), (ex1 - 0.4, ey, 8.6), (ex0 + 0.4, ey, 8.6)]])
    return [pier, end]


def house_colours():
    """The player's colour: bands on the gate posts and the watchtower, the flag."""
    quads = []
    for side in (-1, 1):
        pa, pb = side * GATE_HALF, side * (GATE_HALF + 2.6)
        x = GATE_X - 0.86
        quads.append([(x, max(pa, pb), 4.2), (x, min(pa, pb), 4.2), (x, min(pa, pb), 5.4), (x, max(pa, pb), 5.4)])
    tx, ty = TOWER
    h = 2.56
    quads.append([(tx - h, ty + h, 24.4), (tx - h, ty - h, 24.4), (tx - h, ty - h, 25.6), (tx - h, ty + h, 25.6)])
    quads.append([(tx - h, ty - h, 24.4), (tx + h, ty - h, 24.4), (tx + h, ty - h, 25.6), (tx - h, ty - h, 25.6)])
    bands = flat_object("HOUSECOLOR01", quads)
    fx, fy = FLAG
    flag = [(fx, fy + 0.2, PAD_Z + 19.4), (fx, fy + 7.6, PAD_Z + 19.4), (fx, fy + 7.6, PAD_Z + 15.0), (fx, fy + 0.2, PAD_Z + 15.0)]
    flag_obj = flat_object("HOUSECOLOR02", both_ways([flag]))
    return [bands, flag_obj]


def band_material(tiles):
    """The window bands' material: they glow at night only in their panes (the tile's mask), not their
    mullions."""
    mat = surface_material("band", SURFACES["band"], tiles, ("band",))
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    image = next(n for n in nodes if n.type == "TEX_IMAGE")
    mask = nodes.new("ShaderNodeTexImage")
    mask.image = load_image(os.path.join(tiles, "tile_band_mask.png"))
    mask.image.colorspace_settings.name = "Non-Color"
    mask.projection = "BOX"
    mask.projection_blend = 0.15
    links.new(image.inputs["Vector"].links[0].from_socket, mask.inputs["Vector"])
    links.new(mask.outputs["Color"], nodes["Principled BSDF"].inputs["Emission Color"])
    return mat


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "garrison_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, f"{PREFIX}_emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))
    main, intact, wreck = (Builder(SURFACES) for _ in range(3))
    quarters(main, intact)
    watchtower(main, intact)
    rappel_tower(main, intact)
    firing_range(main, intact)
    gate(main, intact)
    yard(main)
    wreckage(wreck)
    band_material(tiles)
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    objects = bake_building([("BUILDING", main), ("INTACT", intact), ("WRECK", wreck)], SURFACES, tiles, bakes,
                            {"windows.png": ("glass", "band")}, top=36.0)
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
    return dict(zip(("building", "intact", "wreck"), objects), pad=ground, emblems=marks, banners=banners)


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(model_name(NAME, version, night))
    model.bone("EXITSTART", w3d.CHASSIS, EXITSTART)
    model.bone("EXITEND", w3d.CHASSIS, EXITEND)
    for bone, at in BONES.items():
        model.bone(bone, w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    model.mesh("INTACT" if version != "_E" else "WRECK", w3d.CHASSIS,
               **mesh_data(parts["intact" if version != "_E" else "wreck"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    if version != "_E":
        for obj in parts["emblems"]:
            model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["banners"]:
        if version == "_E" and obj.name == "HOUSECOLOR02":
            continue                           # the flag burnt with its pole
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

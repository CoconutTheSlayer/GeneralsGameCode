"""The European Garrison (barracks), modelled in Blender and written as W3D models for the game: a walled
compound round a parade square, two quonset barrack halls with yellow arches and skylights, a two-storey
quarters block with roof plant, and a gatehouse whose roller door stands open to the front (+X), where
the infantry march out; a guard post, a flagpole and sandbags outside (after a concept painted in the
game's style, in the Command Centre's manner).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/garrison.py

Painted as the Command Centre and the Fusion Plant (the shapes, baking and export helpers come from
fusion_plant.py; garrison_paint.py paints the tiles and composes the texture). Models: EUBARR (intact),
_D, _E (wrecked: the halls' roofs gone, their arches standing), each with a night version (_N, _DN, _EN).

The footprint is the USA's (110 long, 90 wide, 20 high, centred). New infantry appear in the parade square
(the parent's UnitCreatePoint, 0 0 0) and walk out of the gate to its NaturalRallyPoint (55 0 0); healed
infantry leave along the bones EXITSTART -> EXITEND, through the gate (HealContain, OpenContain.cpp).
Bones for the damage effects: SMOKE01/02, FIRE01/02.
"""
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, textured  # noqa: E402
from fusion_plant import (BUILD, DATA, Builder, arc, bake_building, bake_pad, both_ways, flat_object,  # noqa: E402
                          model_name, pad_object, ring)
import w3d  # noqa: E402

NAME = "EUBARR"
PREFIX = "eubr"
PAD_Z = 0.6
PAD = (-56.0, 56.0, -46.0, 46.0)
SURFACES = {
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "roof": ("tile_roof", 10.0), "deck": ("tile_deck", 12.0),
    "door": ("tile_door", 10.0), "metal": ("tile_metal", 6.0), "hazard": ("tile_hazard", 3.0),
    "grille": ("tile_grille", 3.0), "sandbag": ("tile_sandbag", 4.0),
    "glass": (40, 72, 92), "dark": (30, 32, 36), "yellow": (222, 182, 46), "red": (196, 52, 40),
}
HALLS = [(-37.0, 16.0, 29.0), (-37.0, 16.0, -29.0)]   # x0, x1, centre y
HALL_R, HALL_BASE = 9.0, 4.0                          # the roof's radius, the top of the plaster base
BLOCK = (-53.0, -37.0, -40.0, 40.0, 11.0)             # x0, x1, y0, y1, top
GATE = (36.0, 46.0, 7.0, 13.0)                        # x0, x1, half opening, tower's outer y
GATE_TOP = 13.0
EXITSTART, EXITEND = (28.0, 0.0, PAD_Z), (62.0, 0.0, PAD_Z)
BONES = {"SMOKE01": (-20.0, 29.0, 12.0), "SMOKE02": (-45.0, -20.0, 11.0),
         "FIRE01": (0.0, -29.0, 6.0), "FIRE02": (41.0, 10.0, GATE_TOP)}


def extrude(b, surface, profile, x0, x1, cap=None):
    """A closed profile (y, z) pushed along x from x0 to x1."""
    def make(bm):
        a = [bm.verts.new((x0, y, z)) for y, z in profile]
        c = [bm.verts.new((x1, y, z)) for y, z in profile]
        n = len(profile)
        for i in range(n):
            j = (i + 1) % n
            bm.faces.new((a[i], a[j], c[j], c[i]))
        ends = (bm.faces.new(list(reversed(a))), bm.faces.new(c))
        for f in ends:
            f.material_index = b.index[cap or surface]
        make.ends = ends
    before = set(b.bm.faces)
    make(b.bm)
    for face in set(b.bm.faces) - before:
        if face not in make.ends:
            face.material_index = b.index[surface]


def hall(main, roof, x0, x1, cy):
    """A quonset barrack hall on a plaster base: plaster gables, yellow arches, doors with canopies to the
    parade square, skylights. The corrugated roof and skylights go in `roof` (gone when wrecked)."""
    r, base = HALL_R, HALL_BASE
    main.box("trim", (x0, cy - r - 0.4, PAD_Z), (x1, cy + r + 0.4, 1.8))
    main.box("wall", (x0 + 0.2, cy - r, PAD_Z), (x1 - 0.2, cy + r, base))
    main.box("trim", (x0, cy - r - 0.3, base - 0.3), (x1, cy + r + 0.3, base + 0.1))
    gable = arc(cy, base, r - 0.1, math.pi, 0.0, 10)
    extrude(main, "wall", gable, x0 + 0.2, x0 + 1.0)
    extrude(main, "wall", gable, x1 - 1.0, x1 - 0.2)
    extrude(roof, "roof", arc(cy, base, r, math.pi, 0.0, 10), x0 + 1.0, x1 - 1.0)
    outer, inner = arc(cy, base, r + 0.5, math.pi, 0.0, 10), arc(cy, base, r - 0.4, 0.0, math.pi, 10)
    for x in (x0, x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3, x1 - 1.0):
        extrude(main, "yellow" if x not in (x0, x1 - 1.0) else "trim", outer + inner, x, x + 1.0)
    for x in (x0 + 10.0, x1 - 18.0):           # skylights along the ridge
        roof.box("trim", (x - 2.0, cy - 1.6, base + r - 0.4), (x + 2.0, cy + 1.6, base + r + 0.6))
        roof.box("glass", (x - 1.6, cy - 1.2, base + r + 0.6), (x + 1.6, cy + 1.2, base + r + 0.75))
    # The gable at the gate's end: a door and two windows.
    main.box("door", (x1 - 0.2, cy - 2.0, PAD_Z), (x1, cy + 2.0, 6.4))
    main.box("trim", (x1 - 0.2, cy - 2.6, 6.4), (x1 + 1.2, cy + 2.6, 7.0))
    for dy in (-5.0, 5.0):
        main.box("glass", (x1 - 0.2, cy + dy - 1.0, 5.0), (x1 + 0.05, cy + dy + 1.0, 7.0))
    # Doors to the parade square, under little canopies standing out from the curve.
    face = cy - r if cy > 0 else cy + r
    out = -1.0 if cy > 0 else 1.0
    for x in (x0 + 12.0, x1 - 12.0):
        main.box("wall", (x - 2.6, face - out * 1.0, PAD_Z), (x + 2.6, face + out * 1.4, 8.0))
        main.box("door", (x - 1.6, face + out * 1.4, PAD_Z + 0.2), (x + 1.6, face + out * 1.55, 6.4))
        main.box("trim", (x - 3.0, face + out * 1.4, 7.4), (x + 3.0, face + out * 3.0, 8.0))
        main.box("trim", (x - 1.8, face + out * 1.4, PAD_Z), (x + 1.8, face + out * 2.8, PAD_Z + 0.5))
    # Small windows along the base, both sides.
    for side in (-1, 1):
        y = cy + side * r
        for x in range(int(x0) + 5, int(x1) - 3, 6):
            if any(abs(x + 1 - d) < 4 for d in (x0 + 12.0, x1 - 12.0)) and side == -out:
                continue
            main.box("glass", (x, y - 0.1 if side < 0 else y - 0.05, 2.2), (x + 2.0, y + 0.05 if side < 0 else y + 0.1, 3.4))


def quarters(main, intact):
    """The two-storey quarters block along the back (-X): plaster, a dark plinth, a yellow band, windows
    on both floors, a big door to the square; air conditioning on the roof (in `intact`)."""
    x0, x1, y0, y1, top = BLOCK
    main.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    main.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.0))
    main.box("yellow", (x0 - 0.12, y0 - 0.12, 6.2), (x1 + 0.12, y1 + 0.12, 6.8))
    ring(main, "trim", x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6, top - 1.0, top + 0.8, 1.2)
    main.box("deck", (x0 + 0.6, y0 + 0.6, top - 0.2), (x1 - 0.6, y1 - 0.6, top + 0.15))
    for x, side in ((x1, 1), (x0, -1)):
        for y in range(int(y0) + 3, int(y1) - 2, 6):
            if x == x1 and (abs(y + 1.25) < 6 or abs(abs(y) - 29) < 8):
                continue                       # the door, and where the halls join on
            for z in (3.4, 8.0):
                main.box("trim", (x, y - 0.3, z - 0.3), (x + side * 0.35, y + 2.8, z + 1.9))
                main.box("glass", (x + side * 0.35, y, z), (x + side * 0.45, y + 2.5, z + 1.6))
    main.box("trim", (x1, -5.0, PAD_Z), (x1 + 1.4, 5.0, 8.4))
    main.box("door", (x1 + 1.4, -3.6, PAD_Z + 0.3), (x1 + 1.6, 3.6, 7.0))
    main.box("trim", (x1 + 1.4, -6.0, 8.4), (x1 + 3.6, 6.0, 9.0))
    for k in range(3):
        main.box("trim", (x1 + 1.4 + k * 0.8, -4.2, PAD_Z), (x1 + 2.2 + k * 0.8, 4.2, PAD_Z + 0.9 - k * 0.3))
    for x, y in ((-49.0, -30.0), (-49.0, -22.0), (-41.0, -30.0), (-45.0, 26.0)):
        intact.box("metal", (x - 2.6, y - 2.6, top), (x + 2.6, y + 2.6, top + 2.8))
        intact.cylinder("dark", (x, y, top + 2.85), 1.9, 0.1, segments=10)
        intact.box("grille", (x + 2.6, y - 2.2, top + 0.4), (x + 2.7, y + 2.2, top + 2.4))
    intact.box("metal", (-49.0, 4.0, top), (-41.0, 12.0, top + 1.8))
    intact.cylinder("metal", (-44.0, -8.0, top + 4.0), 0.15, 8.0, segments=4)


def gatehouse(main, intact):
    """Two plaster towers with a lintel over the gate, the roller door rolled up under it."""
    x0, x1, half, outer = GATE
    for side in (-1, 1):
        ya, yb = side * half, side * outer
        main.box("wall", (x0, min(ya, yb), PAD_Z), (x1, max(ya, yb), GATE_TOP))
        main.box("trim", (x0 - 0.4, min(ya, yb) - 0.4, PAD_Z), (x1 + 0.4, max(ya, yb) + 0.4, 2.2))
        main.box("glass", (x1, side * (half + 1.5) - 1.0, 7.0), (x1 + 0.1, side * (half + 1.5) + 1.0, 9.0))
        main.box("hazard", (x1 - 0.5, side * half - 0.1 * side, PAD_Z), (x1 + 0.1, side * half + 0.5 * side, 6.0))
    main.box("wall", (x0, -half, 10.0), (x1, half, GATE_TOP))
    ring(main, "trim", x0 - 0.6, x1 + 0.6, -outer - 0.6, outer + 0.6, GATE_TOP - 1.0, GATE_TOP + 0.8, 1.2)
    main.box("deck", (x0 + 0.6, -outer, GATE_TOP - 0.2), (x1 - 0.6, outer, GATE_TOP + 0.15))
    main.box("trim", (x0 + 1.0, -half, 9.4), (x1 - 1.0, half, 10.0))
    main.box("metal", (x1 - 1.4, -half, PAD_Z), (x1 - 1.0, -half + 0.4, 9.4))        # door guides
    main.box("metal", (x1 - 1.4, half - 0.4, PAD_Z), (x1 - 1.0, half, 9.4))
    main.cylinder("door", (x1 - 1.6, 0.0, 9.0), 0.7, 2 * half - 0.8, axis="Y", segments=8)
    intact.box("metal", (x0 + 2.0, -outer + 1.0, GATE_TOP), (x0 + 6.0, -outer + 5.0, GATE_TOP + 2.0))
    intact.cylinder("metal", (x0 + 3.0, outer - 2.0, GATE_TOP + 4.0), 0.15, 8.0, segments=4)
    intact.cylinder("red", (x0 + 3.0, outer - 2.0, GATE_TOP + 8.2), 0.3, 0.4, segments=6)


def walls(main):
    """The compound's walls from the halls to the gatehouse."""
    x0 = HALLS[0][1]
    gx0, _, _, outer = GATE
    for side in (-1, 1):
        y = side * (HALLS[0][2] + HALL_R - 0.6)
        main.box("wall", (x0, y - 0.6, PAD_Z), (gx0 + 4.0, y + 0.6, 6.0))
        main.box("trim", (x0, y - 0.8, 5.6), (gx0 + 4.0, y + 0.8, 6.3))
        main.box("trim", (x0, y - 0.8, PAD_Z), (gx0 + 4.0, y + 0.8, 1.6))
        ya, yb = side * outer, y + side * 0.6
        main.box("wall", (gx0 + 3.4, min(ya, yb), PAD_Z), (gx0 + 4.6, max(ya, yb), 6.0))
        main.box("trim", (gx0 + 3.2, min(ya, yb), 5.6), (gx0 + 4.8, max(ya, yb), 6.3))


def outside(main, intact):
    """A guard post by the gate, the flagpole, sandbags along the marching lane, crates."""
    x, y = 50.5, 22.0
    main.box("trim", (x - 3.0, y - 3.0, PAD_Z), (x + 3.0, y + 3.0, 1.4))
    main.box("wall", (x - 2.4, y - 2.4, PAD_Z), (x + 2.4, y + 2.4, 6.4))
    main.box("glass", (x - 2.5, y - 1.8, 4.0), (x + 2.5, y + 1.8, 5.6))
    main.box("glass", (x - 1.8, y - 2.5, 4.0), (x + 1.8, y + 2.5, 5.6))
    main.box("trim", (x - 3.2, y - 3.2, 6.4), (x + 3.2, y + 3.2, 7.2))
    intact.box("metal", (x - 2.2, y - 0.6, PAD_Z + 0.8), (x - 1.8, y - 0.2, 6.0))
    for (ax, ay), (bx, by) in (((47.0, 10.0), (55.0, 10.0)), ((47.0, -10.0), (55.0, -10.0)),
                               ((-56.0 + 1.5, -44.0), (-30.0, -44.0)), ((-30.0, 44.0), (-56.0 + 1.5, 44.0))):
        main.box("sandbag", (min(ax, bx), min(ay, by) - 1.1, PAD_Z), (max(ax, bx), max(ay, by) + 1.1, PAD_Z + 2.4))
    fx, fy = 50.5, -24.0
    main.lathe("trim", (fx, fy, PAD_Z), [(2.6, 0), (2.6, 1.0), (1.4, 1.0), (1.4, 1.6), (0, 1.6)], segments=8)
    intact.cylinder("metal", (fx, fy, PAD_Z + 11.0), 0.25, 19.0, segments=6)
    intact.cylinder("yellow", (fx, fy, PAD_Z + 20.7), 0.45, 0.4, segments=6)
    for cx, cy, h in ((22.0, -33.0, 3.4), (25.6, -33.0, 3.4), (23.8, -33.0, 6.8)):
        main.box("trim" if h > 4 else "metal", (cx - 1.7, cy - 1.7, PAD_Z if h < 4 else PAD_Z + 3.4), (cx + 1.7, cy + 1.7, PAD_Z + h))
    for cx, cy in ((22.0, 33.0), (24.8, 33.0)):
        main.cylinder("trim", (cx, cy, PAD_Z + 2.0), 1.2, 4.0, segments=6)


def training(main):
    """A little of the drill ground at the square's sides (its middle and the lane stay clear): climbing
    walls, a row of tyres, a pull-up frame."""
    for y in (-14.5, 14.5):
        main.box("trim", (-26.0, y - 0.5, PAD_Z), (-20.0, y + 0.5, 4.6))
        main.box("metal", (-26.4, y - 0.7, PAD_Z), (-26.0, y + 0.7, 5.2))
        main.box("metal", (-20.0, y - 0.7, PAD_Z), (-19.6, y + 0.7, 5.2))
    for k in range(5):
        main.cylinder("dark", (2.0 + k * 2.6, 15.0, PAD_Z + 0.45), 1.1, 0.9, segments=8)
    for x in (2.0, 12.0):
        main.box("metal", (x - 0.2, -15.2, PAD_Z), (x + 0.2, -14.8, 6.0))
    main.box("metal", (2.0, -15.15, 5.6), (12.0, -14.85, 5.9))


def wreckage(wreck):
    """What lies in the burnt-out halls: roof sheets fallen in, broken beams."""
    for x0, x1, cy in HALLS:
        for k, a in enumerate((0.4, 2.1, 1.0, 2.7, 0.2)):
            x = x0 + 4 + k * (x1 - x0 - 8) / 4
            wreck.turned_box("roof", (x, cy + (k % 2 - 0.5) * 6, HALL_BASE + 0.6), (8.0, 4.0, 1.0), a)
        for k, a in enumerate((0.7, 2.4)):
            wreck.turned_box("trim", (x0 + 14 + k * 20, cy, HALL_BASE + 1.4), (12.0, 0.8, 0.8), a)


def emblems():
    """The faction's mark over the gate."""
    x = GATE[1] + 0.05
    return [flat_object("EMBLEM", [[(x, -1.6, 9.7), (x, 1.6, 9.7), (x, 1.6, 12.9), (x, -1.6, 12.9)]])]


def house_colours():
    """The player's colour: bands on the gate's towers, the flag."""
    x1, half, outer = GATE[1] + 0.06, GATE[2], GATE[3]
    quads = []
    for side in (-1, 1):
        ya, yb = side * (half + 0.4), side * (outer - 0.4)
        quads.append([(x1, min(ya, yb), 10.6), (x1, max(ya, yb), 10.6), (x1, max(ya, yb), 11.6), (x1, min(ya, yb), 11.6)])
    bands = flat_object("HOUSECOLOR01", quads)
    fx, fy = 50.5, -24.0
    flag = [(fx, fy - 0.2, PAD_Z + 19.8), (fx, fy - 7.8, PAD_Z + 19.8), (fx, fy - 7.8, PAD_Z + 15.4), (fx, fy - 0.2, PAD_Z + 15.4)]
    flag_obj = flat_object("HOUSECOLOR02", both_ways([flag]))
    return [bands, flag_obj]


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
    for x0, x1, cy in HALLS:
        hall(main, intact, x0, x1, cy)
    quarters(main, intact)
    gatehouse(main, intact)
    walls(main)
    outside(main, intact)
    training(main)
    wreckage(wreck)
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    objects = bake_building([("BUILDING", main), ("INTACT", intact), ("WRECK", wreck)], SURFACES, tiles, bakes,
                            {"windows.png": ("glass",)}, top=16.0)
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

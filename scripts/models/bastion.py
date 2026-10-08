"""The European Artillery Bastion, modelled in Blender and written as W3D models for the game: a square
concrete bunker with sloped glacis walls, four corner casemates with firing slits where infantry
garrison it, gate houses front and back, and an armoured howitzer turret on a raised platform (after a
concept painted in the game's style). Everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/bastion.py

Painted as the Command Centre and the SAMP/T Battery (the shared code is samp_battery.py's):
bastion_paint.py paints small tiling surfaces, Blender projects them onto the model and bakes them with
the ambient occlusion into one texture; the painter makes the damaged, wrecked and night versions. Six
models: EUBAST (intact), _D, _E (no clutter, antenna or cupola), each with a night version (_N, _DN, _EN).

Bones (as the USA's Fire Base, ABFIREBASE, which the game's INI names):
    TURRET01               the turret, turning about Z
    TURRETEL               the gun's trunnion, a child of TURRET01, pitching about Y; the gun points +X
    BARREL01               the barrel, recoiling when it fires (WeaponRecoilBone Barrel)
    MUZZLE0101             where the shell leaves (WeaponLaunchBone MUZZLE01)
    MUZZLEFX01             the muzzle flash, a mesh of that name shown when it fires (WeaponMuzzleFlash,
                           WeaponFireFXBone MuzzleFX)
    STATION01..STATION04   where the garrison stands, one inside each corner casemate (GarrisonContain
                           places infantry at STATION bones, named by ExtraPublicBone in the INI)

The footprint is the USA's (a box of 52 by 52, 15 high, centred); the pad covers all of it.
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
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, new_object, textured  # noqa: E402
import w3d  # noqa: E402
from samp_battery import (BUILD, DATA, Builder, bake_all, band, decal, house_material, make_objects, moved,  # noqa: E402
                          ring, square_pad)

NAME = "EUBAST"
PREFIX = "eufb"
PAD_Z = 0.6
PAD_HALF = 26.0
HEIGHT_TOP = 20.0
SURFACES = {
    "wall": ("tile_wall", 10.0), "concrete": ("tile_concrete", 12.0), "trim": ("tile_trim", 8.0),
    "deck": ("tile_deck", 10.0), "door": ("tile_door", 8.0), "metal": ("tile_metal", 4.0),
    "sandbag": ("tile_sandbag", 3.0), "hazard": ("tile_hazard", 2.5), "grille": ("tile_grille", 2.0),
    "crate": ("tile_crate", 3.0), "steel": ("tile_steel", 8.0), "armour": ("tile_armour", 8.0),
    "glass": (40, 72, 92), "dark": (30, 32, 36), "yellow": (222, 182, 46), "red": (196, 52, 40),
}

BODY = (18.0, 15.5, 9.0)                 # half width at the ground, at the top, the deck's height
CASEMATE = (17.5, 5.0, 12.5)             # centre (+-), half width, height
TURRET_AT = (0.0, 0.0, 10.4)             # TURRET01, on the gun platform
TRUNNION = (6.0, 0.0, 13.4)              # TURRETEL, in the world
MUZZLE = 23.8                            # from the trunnion along the barrel
STATIONS = [(1, 1), (1, -1), (-1, -1), (-1, 1)]   # STATION01..04, in the casemates (as the USA's order)


def frustum(b, surface, half0, half1, z0, z1):
    """A square block whose sides lean in, from half width half0 at z0 to half1 at z1."""
    def make(bm):
        lo = [bm.verts.new((x * half0, y * half0, z0)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        hi = [bm.verts.new((x * half1, y * half1, z1)) for x, y in ((-1, -1), (1, -1), (1, 1), (-1, 1))]
        bm.faces.new(list(reversed(lo)))
        bm.faces.new(hi)
        for i in range(4):
            j = (i + 1) % 4
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    b.add(surface, make)


def body(b):
    """The bunker: sloped concrete glacis, a deck with a parapet, the raised gun platform."""
    h0, h1, top = BODY
    b.box("trim", (-h0 - 0.4, -h0 - 0.4, PAD_Z), (h0 + 0.4, h0 + 0.4, PAD_Z + 0.8))
    frustum(b, "concrete", h0, h1, PAD_Z, top)
    b.box("deck", (-h1 + 0.2, -h1 + 0.2, top), (h1 - 0.2, h1 - 0.2, top + 0.1))
    ring(b, "wall", -h1, h1, -h1, h1, top, top + 1.6, 1.2)
    ring(b, "trim", -h1 - 0.15, h1 + 0.15, -h1 - 0.15, h1 + 0.15, top + 1.6, top + 2.0, 1.5)
    b.cylinder("trim", (0, 0, top + 0.7), 8.5, 1.4, segments=24)
    b.cylinder("deck", (0, 0, top + 1.45), 8.0, 0.1, segments=24)
    for k in range(12):                      # hazard marks round the platform's edge
        a = k * math.pi / 6
        b.oriented_box("hazard", (math.cos(a) * 8.52, math.sin(a) * 8.52, top + 0.7), (0.1, 1.6, 0.9),
                       Matrix.Rotation(a, 4, "Z"))
    # Vents and a ready-ammunition hatch on the deck.
    for x, y in ((-11.0, -9.0), (-11.0, 9.0)):
        b.box("grille", (x - 1.6, y - 1.0, top), (x + 1.6, y + 1.0, top + 0.8))
    b.box("steel", (9.0, -12.0, top), (12.0, -9.0, top + 0.5))
    b.box("hazard", (8.8, -12.2, top), (12.2, -11.9, top + 0.55))


def casemates(b):
    """The four corner casemates: plaster, a plinth, a yellow band, a cap, firing slits facing out."""
    c, h, top = CASEMATE
    for sx in (-1, 1):
        for sy in (-1, 1):
            x, y = sx * c, sy * c
            b.box("wall", (x - h, y - h, PAD_Z), (x + h, y + h, top))
            b.box("trim", (x - h - 0.3, y - h - 0.3, PAD_Z), (x + h + 0.3, y + h + 0.3, 2.2))
            b.box("yellow", (x - h - 0.08, y - h - 0.08, 9.4), (x + h + 0.08, y + h + 0.08, 9.9))
            b.box("trim", (x - h - 0.35, y - h - 0.35, top), (x + h + 0.35, y + h + 0.35, top + 0.7))
            b.box("deck", (x - h + 0.6, y - h + 0.6, top + 0.7), (x + h - 0.6, y + h - 0.6, top + 0.8))
            # Firing slits in the two outer faces: a hood, a dark slot, a sill.
            fx = x + sx * h
            b.box("trim", (fx, y - 2.6, 8.0), (fx + sx * 0.6, y + 2.6, 8.5))
            b.box("dark", (fx, y - 2.2, 6.6), (fx + sx * 0.12, y + 2.2, 7.9))
            b.box("trim", (fx, y - 2.4, 6.2), (fx + sx * 0.4, y + 2.4, 6.6))
            fy = y + sy * h
            b.box("trim", (x - 2.6, fy, 8.0), (x + 2.6, fy + sy * 0.6, 8.5))
            b.box("dark", (x - 2.2, fy, 6.6), (x + 2.2, fy + sy * 0.12, 7.9))
            b.box("trim", (x - 2.4, fy, 6.2), (x + 2.4, fy + sy * 0.4, 6.6))
            # A lit window towards the deck.
            ix = x - sx * h
            b.box("glass", (ix - sx * 0.08, y - 1.4, 10.4), (ix, y + 1.4, 11.4))


def gates(b):
    """Gate houses: the front one carries the emblem, the back one the ammunition door."""
    for side in (1, -1):
        x0, x1 = sorted((side * 15.0, side * 19.6))
        b.box("wall", (x0, -5.0, PAD_Z), (x1, 5.0, 8.6))
        b.box("trim", (x0 - 0.3, -5.3, PAD_Z), (x1 + 0.3, 5.3, 2.0))
        b.box("yellow", (x0 - 0.08, -5.08, 6.3), (x1 + 0.08, 5.08, 6.8))
        b.box("trim", (x0 - 0.3, -5.3, 8.6), (x1 + 0.3, 5.3, 9.3))
    # The ammunition door at the back, framed in hazard stripes, with a ramp.
    b.box("hazard", (-19.8, -3.4, PAD_Z), (-19.6, 3.4, 6.0))
    b.box("door", (-19.95, -2.8, PAD_Z), (-19.8, 2.8, 5.5))
    b.add("trim", lambda bm: bmesh.ops.create_cube(bm, size=1.0, matrix=(
        Matrix.Translation((-21.2, 0, PAD_Z + 0.2)) @ Matrix.Rotation(0.12, 4, "Y") @ Matrix.Diagonal((3.0, 5.6, 0.5, 1)))))
    # Front: a lamp over the emblem, a plaque frame for it.
    b.box("trim", (19.6, -3.2, 2.2), (19.75, 3.2, 6.1))


def sandbags(b):
    """Sandbag walls along the front between the casemates and the gate."""
    for y0, y1 in ((-12.2, -5.6), (5.6, 12.2)):
        b.box("sandbag", (19.0, y0, PAD_Z), (21.0, y1, PAD_Z + 1.6))
        b.box("sandbag", (19.4, y0 + 0.5, PAD_Z + 1.6), (20.6, y1 - 0.5, PAD_Z + 2.6))


def clutter(b):
    """Lost when the bastion is wrecked: crates, an antenna, a floodlight, an observation cupola."""
    for x, y, z in ((-22.5, 7.0, 0), (-22.5, 9.4, 0), (-20.5, 8.2, 0), (-22.5, 8.2, 1.8)):
        b.box("crate", (x - 1.0, y - 1.0, PAD_Z + z), (x + 1.0, y + 1.2, PAD_Z + z + 1.8))
    for x, y in ((-21.0, -7.4), (-22.6, -7.4), (-21.8, -9.0)):
        b.cylinder("trim", (x, y, PAD_Z + 1.2), 0.75, 2.4, segments=8)
    c, h, top = CASEMATE
    b.cylinder("metal", (-c - 2.5, c + 2.5, top + 4.5), 0.12, 8.0, segments=5)
    b.sphere("red", (-c - 2.5, c + 2.5, top + 8.6), 0.3, 6, 4)
    b.cylinder("metal", (c - 3.0, -c + 3.0, top + 2.2), 0.15, 3.0, segments=5)
    b.box("metal", (c - 3.6, -c + 2.6, top + 3.6), (c - 2.4, -c + 3.4, top + 4.4))
    b.cylinder("armour", (c, c, top + 1.6), 2.0, 1.8, segments=12)
    b.cylinder("trim", (c, c, top + 2.7), 2.3, 0.4, segments=12)
    b.cylinder("dark", (c, c, top + 1.7), 2.05, 0.5, segments=12)
    b.box("metal", (c + 0.6, c - 0.3, top + 2.9), (c + 1.0, c + 0.3, top + 4.0))


def turret(b):
    """The armoured turret (TURRET01): a ring, a sloped housing, stowage, a bustle, a commander's cupola."""
    tx, ty, z = TURRET_AT
    b.cylinder("trim", (tx, ty, z + 0.4), 5.6, 0.8, segments=20)
    profile = [(-6.5, z + 0.8), (5.0, z + 0.8), (6.8, z + 3.0), (5.2, z + 5.6), (-5.0, z + 5.6), (-6.8, z + 3.2)]
    b.prism("armour", profile, -4.6, 4.6)
    b.box("armour", (-8.4, -3.4, z + 1.4), (-6.4, 3.4, z + 4.8))                 # the bustle
    b.box("grille", (-8.5, -2.6, z + 2.0), (-8.4, 2.6, z + 4.2))
    for side in (-1, 1):                                                          # stowage boxes
        y = side * 4.6
        b.box("steel", (-4.8, y, z + 1.6), (-0.6, y + side * 0.9, z + 3.6))
        b.box("trim", (-4.9, y, z + 3.6), (-0.5, y + side * 1.0, z + 3.9))
    b.cylinder("armour", (-2.4, 2.0, z + 6.1), 1.3, 1.0, segments=10)             # the cupola
    b.cylinder("trim", (-2.4, 2.0, z + 6.7), 1.45, 0.25, segments=10)
    b.box("dark", (-1.4, 1.4, z + 5.8), (-1.15, 2.6, z + 6.3))
    b.box("armour", (0.5, -3.0, z + 5.6), (2.5, -1.6, z + 6.2))                   # the loader's hatch
    b.box("yellow", (-6.9, -0.5, z + 2.9), (-6.6, 0.5, z + 3.4))


def turret_antenna(b):
    _, _, z = TURRET_AT
    b.cylinder("metal", (-5.6, -3.6, z + 8.6), 0.08, 6.0, segments=5)
    b.box("metal", (-5.9, -3.9, z + 5.6), (-5.3, -3.3, z + 5.9))


def mantlet(b):
    """The gun's mantlet and recoil sleeve (TURRETEL)."""
    hx, _, hz = TRUNNION
    b.box("armour", (hx - 0.4, -2.0, hz - 1.5), (hx + 1.6, 2.0, hz + 1.4))
    b.box("trim", (hx + 1.6, -1.6, hz - 1.1), (hx + 1.9, 1.6, hz + 1.0))
    b.cylinder("steel", (hx + 3.2, 0, hz), 0.95, 2.6, axis="X", segments=12)


def barrel(b):
    """The barrel (BARREL01): a long tube, a bore evacuator, a muzzle brake."""
    hx, _, hz = TRUNNION
    b.cylinder("steel", (hx + (4.5 + MUZZLE - 1.8) / 2, 0, hz), 0.55, MUZZLE - 1.8 - 4.5, axis="X", segments=12)
    b.cylinder("steel", (hx + 12.5, 0, hz), 0.85, 2.8, axis="X", segments=12)
    b.box("dark", (hx + MUZZLE - 2.0, -0.95, hz - 0.75), (hx + MUZZLE, 0.95, hz + 0.75))
    b.box("steel", (hx + MUZZLE - 1.9, -1.0, hz - 0.5), (hx + MUZZLE - 1.1, 1.0, hz + 0.5))
    b.box("steel", (hx + MUZZLE - 0.9, -1.0, hz - 0.5), (hx + MUZZLE - 0.1, 1.0, hz + 0.5))


def build_shapes():
    parts = {k: Builder(SURFACES) for k in ("building", "intact", "turret", "turret_intact", "mantlet", "barrel")}
    body(parts["building"])
    casemates(parts["building"])
    gates(parts["building"])
    sandbags(parts["building"])
    clutter(parts["intact"])
    turret(parts["turret"])
    turret_antenna(parts["turret_intact"])
    mantlet(parts["mantlet"])
    barrel(parts["barrel"])
    return parts


def muzzle_flash():
    """Two crossed quads from the muzzle forward, both ways round (additive, shown when it fires)."""
    bm = bmesh.new()
    length, r = 5.0, 1.8
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * r, math.sin(a) * r
        quad = [(0, -c, -s), (length, -c, -s), (length, c, s), (0, c, s)]
        bm.faces.new([bm.verts.new(v) for v in quad])
        bm.faces.new([bm.verts.new(v) for v in reversed(quad)])
    obj = new_object("MUZZLEFX01", bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for poly in obj.data.polygons:
        for li in poly.loop_indices:
            x, y, z = obj.data.vertices[obj.data.loops[li].vertex_index].co
            uv.data[li].uv = (x / length, 0.5 + (y + z) / (2 * r * 1.42))
    return obj


def emblems():
    return [decal("EMBLEM", [(19.78, -2.9, 2.4), (19.78, 2.9, 2.4), (19.78, 2.9, 5.9), (19.78, -2.9, 5.9)])]


def house_colours():
    """The player's colour: a band round the gun platform, stripes on the turret's sides."""
    _, _, top = BODY
    on_body = [band("HOUSECOLOR01", (0, 0), 8.56, top + 0.15, top + 0.45, segments=24)]
    tx, ty, z = TURRET_AT
    on_turret = []
    for k, side in enumerate((-1, 1)):
        y = side * 4.62
        quad = [(-0.4, y, z + 4.2), (4.6, y, z + 4.2), (4.6, y, z + 4.8), (-0.4, y, z + 4.8)]
        if side < 0:
            quad = list(reversed(quad))
        bm = bmesh.new()
        bm.faces.new([bm.verts.new(v) for v in quad])
        on_turret.append(new_object(f"HOUSECOLOR0{k + 2}", bm))
    for obj in on_body + on_turret:
        obj.data.uv_layers.new(name="UVMap")
    return on_body, on_turret


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "bastion_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, f"{PREFIX}_emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))

    objects = make_objects(build_shapes(), SURFACES, tiles)
    ground = square_pad("PAD", PAD_HALF, PAD_Z)
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
    on_body, on_turret = house_colours()
    colour = house_material()
    for obj in on_body + on_turret:
        obj.data.materials.append(colour)
    return dict(objects=objects, pad=ground, emblems=marks, house_body=on_body, house_turret=on_turret,
                flash=muzzle_flash())


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked (still fighting: the gun stays)."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    turret_bone = model.bone("TURRET01", w3d.CHASSIS, TURRET_AT)
    el_bone = model.bone("TURRETEL", turret_bone, tuple(TRUNNION[i] - TURRET_AT[i] for i in range(3)))
    barrel_bone = model.bone("BARREL01", el_bone, (0, 0, 0))
    model.bone("MUZZLE0101", barrel_bone, (MUZZLE + 0.3, 0, 0))
    flash_bone = model.bone("MUZZLEFX01", barrel_bone, (MUZZLE, 0, 0))
    c = CASEMATE[0]
    for k, (sx, sy) in enumerate(STATIONS):
        model.bone(f"STATION0{k + 1}", w3d.CHASSIS, (sx * c, sy * c, PAD_Z))
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    objects = parts["objects"]
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(objects["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(objects["intact"]), texture=texture)
        model.mesh("ANTENNA", turret_bone, **moved(mesh_data(objects["turret_intact"]), TURRET_AT), texture=texture)
    model.mesh("TURRET", turret_bone, **moved(mesh_data(objects["turret"]), TURRET_AT), texture=texture)
    model.mesh("MANTLET", el_bone, **moved(mesh_data(objects["mantlet"]), TRUNNION), texture=texture)
    model.mesh("BARREL", barrel_bone, **moved(mesh_data(objects["barrel"]), TRUNNION), texture=texture)
    model.mesh("MUZZLEFX01", flash_bone, **mesh_data(parts["flash"]), texture="EXTnkMzl01.tga", shadow=False,
               shader=w3d.ADDITIVE_SHADER)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["house_body"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
    for obj in parts["house_turret"]:
        model.mesh(obj.name, turret_bone, **moved(mesh_data(obj), TURRET_AT), texture=w3d.HOUSE_COLOUR_TEXTURE, **flat)
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

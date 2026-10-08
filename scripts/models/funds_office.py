"""The European Funds Office (Europe's money maker, in place of the USA's supply drop zone), modelled in
Blender and written as W3D models for the game: the base's tall glass tower. A slim octagonal tower of
blue-tinted curtain glass in a plaster and steel grid rises from a two-storey glass lobby podium; its top
two floors are set back inside a steel crown, and a navy pylon carrying the faction's mark runs up its
front past the roof. At its foot a paved plaza with a fountain and hedges, two official cars, and a guard
booth, blast barriers and sandbags so it still reads as military (after a concept painted in the game's
style). Made the way the Command Centre is, with the SAMP/T Battery's machinery (samp_battery.py).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/funds_office.py

Six models: EUFUNDS (intact), _D, _E (wrecked: no pylon top, crown frame, antennas or dishes), each with a
night version (_N, _DN, _EN) with lit windows. Bones SMOKE01..03 carry the damaged and wrecked smoke and
fire (build_europe.py). The footprint is the USA's drop zone's (54 by 54, centred); the spawned view
looks from the (-X, -Y) corner, so the plaza is there and the tower stands at the back.
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
from samp_battery import (BUILD, DATA, Builder, bake_all, decal, flat_ground, house_material,  # noqa: E402
                          make_objects)

NAME = "EUFUNDS"
PREFIX = "eufo"
PAD_Z = 0.05
PAD_HALF = 27.0
HEIGHT_TOP = 46.0
SURFACES = {
    "office": ("tile_office", 12.0), "trim": ("tile_trim", 10.0), "deck": ("tile_deck", 12.0),
    "metal": ("tile_metal", 5.0), "steel": ("tile_steel", 8.0), "crate": ("tile_crate", 3.0),
    "sandbag": ("tile_sandbag", 3.0), "hazard": ("tile_hazard", 2.5), "grille": ("tile_grille", 3.0),
    "curtain": ("tile_curtain", 4.2), "glass_lit": ("tile_curtain", 4.2), "hedge": ("tile_hedge", 3.0),
    "barrier": ("tile_barrier", 5.0), "dome": ("tile_dome", 5.0),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46), "red": (196, 52, 40),
    "lamp": (240, 236, 210), "water": (84, 140, 176), "navy": (40, 52, 92), "car": (30, 32, 38),
}

C = (7.0, 8.0)                 # the tower's centre
HALF, CHAMFER = 9.0, 2.6       # the tower's half width and corner chamfer
PODIUM = (-5.0, 19.0, -4.0, 20.0, 9.2)    # x0, x1, y0, y1, roof
STOREY = 4.2
FLOORS = 6                     # tower storeys above the podium
TOWER_TOP = PODIUM[4] + FLOORS * STOREY  # 34.4
CROWN = (6.6, 6.0)             # the set-back top floors' half width, height
PYLON = (7.0, -1.0 - 1.0, 49.0)          # x, y (standing proud of the -Y face), top
FOUNTAIN = (-12.0, -12.0)
SMOKE = [(0.0, 2.0, 10.0), (11.0, 14.0, 30.0), (16.0, -1.0, 10.0)]


def octagon(cx, cy, half, chamfer):
    """A square with cut corners, counter-clockwise."""
    h, c = half, half - chamfer
    pts = [(-c, -h), (c, -h), (h, -c), (h, c), (c, h), (-c, h), (-h, c), (-h, -c)]
    return [(cx + x, cy + y) for x, y in pts]


def solid(b, surface, outline, z0, z1, top_outline=None):
    """A prism from an outline at z0 to the same (or `top_outline`) at z1: one closed shape."""
    def make(bm):
        lo = [bm.verts.new((x, y, z0)) for x, y in outline]
        hi = [bm.verts.new((x, y, z1)) for x, y in (top_outline or outline)]
        bm.faces.new(list(reversed(lo)))
        bm.faces.new(hi)
        for i in range(len(lo)):
            j = (i + 1) % len(lo)
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    b.add(surface, make)


def tower(b):
    """The tower: curtain glass storeys (some lit at night) between plaster floor bands, a pier at every
    corner and fins down the middle of each face, a roof slab."""
    cx, cy = C
    base = PODIUM[4]
    for k in range(FLOORS):
        z = base + k * STOREY
        solid(b, "glass_lit" if k % 3 != 1 else "curtain", octagon(cx, cy, HALF - 0.35, CHAMFER), z, z + STOREY)
        solid(b, "office", octagon(cx, cy, HALF + 0.15, CHAMFER), z + STOREY - 0.7, z + STOREY)
    # Corner piers at the chamfers' ends, plaster, full height; steel fins in the middle of each face.
    for x, y in octagon(cx, cy, HALF, CHAMFER):
        b.box("office", (x - 0.55, y - 0.55, base), (x + 0.55, y + 0.55, TOWER_TOP + 0.4))
    for (x, y), size in (((cx - 3.2, cy - HALF), (0.4, 0.8)), ((cx + 3.2, cy - HALF), (0.4, 0.8)),
                         ((cx - 3.2, cy + HALF), (0.4, 0.8)), ((cx + 3.2, cy + HALF), (0.4, 0.8)),
                         ((cx - HALF, cy - 3.2), (0.8, 0.4)), ((cx - HALF, cy + 3.2), (0.8, 0.4)),
                         ((cx + HALF, cy - 3.2), (0.8, 0.4)), ((cx + HALF, cy + 3.2), (0.8, 0.4))):
        b.box("steel", (x - size[0] / 2, y - size[1] / 2, base), (x + size[0] / 2, y + size[1] / 2, TOWER_TOP))
    solid(b, "trim", octagon(cx, cy, HALF + 0.5, CHAMFER), TOWER_TOP, TOWER_TOP + 0.8)
    # The crown's set-back floors: glass, a roof, machinery.
    h, top = CROWN
    solid(b, "glass_lit", octagon(cx, cy, h, CHAMFER - 0.6), TOWER_TOP + 0.8, TOWER_TOP + top)
    solid(b, "trim", octagon(cx, cy, h + 0.4, CHAMFER - 0.6), TOWER_TOP + top, TOWER_TOP + top + 0.6)
    b.box("metal", (cx - 4.0, cy + 1.0, TOWER_TOP + top + 0.6), (cx + 1.0, cy + 5.0, TOWER_TOP + top + 2.4))
    b.box("grille", (cx - 3.8, cy + 0.9, TOWER_TOP + top + 0.9), (cx + 0.8, cy + 1.0, TOWER_TOP + top + 2.1))


def crown_frame(b):
    """The steel frame round the set-back floors: posts at the tower's corners and a ring beam (lost when
    wrecked), antennas, a dish."""
    cx, cy = C
    z0, z1 = TOWER_TOP + 0.8, TOWER_TOP + CROWN[1] + 0.4
    corners = octagon(cx, cy, HALF - 0.2, CHAMFER)
    for x, y in corners:
        b.box("steel", (x - 0.35, y - 0.35, z0), (x + 0.35, y + 0.35, z1))
    for (ax, ay), (bx, by) in zip(corners, corners[1:] + corners[:1]):
        mx, my = (ax + bx) / 2, (ay + by) / 2
        length = math.hypot(bx - ax, by - ay)
        b.oriented_box("steel", (mx, my, z1 - 0.3), (length + 0.7, 0.5, 0.6),
                       Matrix.Rotation(math.atan2(by - ay, bx - ax), 4, "Z"))
    top = TOWER_TOP + CROWN[1] + 0.6
    for x, y, hgt in ((cx + 3.5, cy + 3.5, 9.0), (cx - 4.5, cy + 4.5, 6.0)):
        b.cylinder("metal", (x, y, top + hgt / 2), 0.16, hgt, segments=6)
        b.sphere("red", (x, y, top + hgt + 0.2), 0.3, 6, 4)
    b.cylinder("metal", (cx + 3.0, cy - 3.0, top + 0.8), 0.3, 1.6, segments=6)

    def make(bm):
        m = (Matrix.Translation((cx + 3.0, cy - 3.0, top + 2.2)) @ Matrix.Rotation(-2.3, 4, "Z")
             @ Matrix.Rotation(-math.pi / 2 + 0.6, 4, "Y"))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=1.6, radius2=0.5, depth=0.6, matrix=m)
    b.add("dome", make)


def pylon_base(b):
    """The pylon's lower shaft, up the tower's front from the podium roof (stays when wrecked)."""
    x, y, _ = PYLON
    b.box("navy", (x - 1.8, y - 1.0, PODIUM[4]), (x + 1.8, y + 1.0, 28.0))


def pylon_top(b):
    """The pylon's upper shaft past the roof, with a steel cap (falls when wrecked)."""
    x, y, top = PYLON
    b.box("navy", (x - 1.8, y - 1.0, 28.0), (x + 1.8, y + 1.0, top - 1.0))
    b.box("trim", (x - 2.1, y - 1.3, top - 1.0), (x + 2.1, y + 1.3, top))
    b.box("metal", (x - 1.0, y - 0.6, top), (x + 1.0, y + 0.6, top + 0.5))


def podium(b):
    """The two-storey lobby: glass between plaster piers, a plinth, a parapet, the entrance canopy on the
    plaza side, steel shutters on the driveway side."""
    x0, x1, y0, y1, top = PODIUM
    solid(b, "glass_lit", [(x0 + 0.4, y0 + 0.4), (x1 - 0.4, y0 + 0.4), (x1 - 0.4, y1 - 0.4), (x0 + 0.4, y1 - 0.4)],
          PAD_Z, top)
    b.box("office", (x0, y0, top - 4.9), (x1, y1, top - 4.2))                       # the floor band
    b.box("trim", (x0 - 0.3, y0 - 0.3, PAD_Z), (x1 + 0.3, y1 + 0.3, PAD_Z + 0.8))   # plinth
    b.box("office", (x0 - 0.3, y0 - 0.3, top), (x1 + 0.3, y1 + 0.3, top + 0.9))     # parapet / roof slab
    for x in (x0, x0 + 6.0, x0 + 12.0, x0 + 18.0, x1):
        for y in (y0, y1):
            b.box("office", (x - 0.7, y - 0.7, PAD_Z), (x + 0.7, y + 0.7, top))
    for y in (y0 + 6.0, y0 + 12.0, y0 + 18.0):
        for x in (x0, x1):
            b.box("office", (x - 0.7, y - 0.7, PAD_Z), (x + 0.7, y + 0.7, top))
    # The entrance on the plaza side (-Y): a canopy on posts, glass doors, steps.
    b.box("dark", (-1.0, y0 - 0.2, PAD_Z), (5.0, y0 + 0.4, PAD_Z + 4.0))
    b.box("glass", (-0.6, y0 - 0.3, PAD_Z + 0.3), (4.6, y0 - 0.2, PAD_Z + 3.6))
    b.box("trim", (-2.0, y0 - 4.0, PAD_Z + 4.2), (6.0, y0, PAD_Z + 4.8))
    for x in (-1.7, 5.7):
        b.box("metal", (x - 0.2, y0 - 3.8, PAD_Z), (x + 0.2, y0 - 3.4, PAD_Z + 4.2))
    for k in range(2):
        b.box("trim", (-1.5, y0 - 1.2 - k * 1.0, PAD_Z), (5.5, y0, PAD_Z + 0.8 - k * 0.35))


def plaza(b):
    """The fountain, hedges in planters, benches, lamps."""
    fx, fy = FOUNTAIN
    b.cylinder("trim", (fx, fy, PAD_Z + 0.5), 3.8, 1.0, segments=16)
    b.cylinder("water", (fx, fy, PAD_Z + 1.05), 3.3, 0.2, segments=16)
    b.cylinder("office", (fx, fy, PAD_Z + 1.6), 0.6, 2.2, segments=8)
    b.cylinder("trim", (fx, fy, PAD_Z + 2.8), 1.6, 0.4, segments=12)
    b.cylinder("water", (fx, fy, PAD_Z + 3.05), 1.3, 0.12, segments=12)
    for (xa, ya), (xb, yb) in (((-24.0, -2.0), (-14.0, -1.0)), ((-24.0, -9.0), (-23.0, -2.0)),
                               ((-24.0, 6.0), (-8.0, 7.0)), ((-9.0, 7.0), (-8.0, 16.0))):
        b.box("trim", (xa - 0.3, ya - 0.3, PAD_Z), (xb + 0.3, yb + 0.3, PAD_Z + 0.8))
        b.box("hedge", (xa, ya, PAD_Z + 0.8), (xb, yb, PAD_Z + 2.0))
    for x, y in ((-18.0, -5.5), (-6.0, -7.0)):
        b.box("dark", (x - 1.6, y - 0.4, PAD_Z + 0.6), (x + 1.6, y + 0.4, PAD_Z + 0.9))
        for dx in (-1.3, 1.3):
            b.box("dark", (x + dx - 0.15, y - 0.3, PAD_Z), (x + dx + 0.15, y + 0.3, PAD_Z + 0.6))
    for x, y in ((-5.0, -17.0), (-21.0, -17.0), (-21.0, 3.0)):
        b.cylinder("dark", (x, y, PAD_Z + 3.0), 0.15, 6.0, segments=6)
        b.sphere("lamp", (x, y, PAD_Z + 6.2), 0.45, 8, 4)


def car(b, x, y, angle):
    """An official saloon car: body, cabin, dark windows, wheels."""
    c, s = math.cos(angle), math.sin(angle)
    turn = Matrix.Rotation(angle, 4, "Z")

    def at(u, v, z):
        return (x + u * c - v * s, y + u * s + v * c, z)
    b.oriented_box("car", at(0, 0, PAD_Z + 0.95), (8.0, 3.4, 1.3), turn)
    b.oriented_box("car", at(-0.4, 0, PAD_Z + 2.1), (4.2, 3.0, 1.1), turn)
    b.oriented_box("glass", at(-0.4, 0, PAD_Z + 2.1), (4.3, 2.9, 0.8), turn)
    for u in (-2.6, 2.6):
        for v in (-1.55, 1.55):
            b.add("dark", lambda bm, u=u, v=v: bmesh.ops.create_cone(
                bm, cap_ends=True, segments=8, radius1=0.65, radius2=0.65, depth=0.5,
                matrix=Matrix.Translation(at(u, v, PAD_Z + 0.65)) @ turn @ Matrix.Rotation(math.pi / 2, 4, "X")))


def gate(b):
    """The guard booth with a barrier arm across the driveway, sandbags, blast barriers along the edges."""
    x, y = 21.0, -14.0
    b.box("trim", (x - 2.6, y - 2.6, PAD_Z), (x + 2.6, y + 2.6, PAD_Z + 0.5))
    b.box("office", (x - 2.0, y - 2.0, PAD_Z + 0.5), (x + 2.0, y + 2.0, PAD_Z + 4.6))
    b.box("glass", (x - 2.1, y - 1.4, PAD_Z + 2.4), (x + 2.1, y + 1.4, PAD_Z + 3.8))
    b.box("glass", (x - 1.4, y - 2.1, PAD_Z + 2.4), (x + 1.4, y + 2.1, PAD_Z + 3.8))
    b.box("trim", (x - 2.6, y - 2.6, PAD_Z + 4.6), (x + 2.6, y + 2.6, PAD_Z + 5.2))
    b.box("hazard", (x - 3.6, y - 1.0, PAD_Z), (x - 2.6, y + 1.0, PAD_Z + 2.6))   # the arm's post
    b.box("hazard", (x - 3.4, y - 11.0, PAD_Z + 2.2), (x - 3.0, y - 1.0, PAD_Z + 2.6))
    for k in range(3):
        b.box("sandbag", (x + 2.8, y - 3.0, PAD_Z + k * 0.9), (x + 4.4, y + 3.0, PAD_Z + (k + 1) * 0.9))
    for yy in (-6.0, -1.0, 4.0, 9.0, 14.0, 19.0, 24.0):           # blast barriers along the east edge
        b.box("barrier", (25.0, yy - 2.2, PAD_Z), (26.4, yy + 2.2, PAD_Z + 0.9))
        b.box("barrier", (25.3, yy - 2.2, PAD_Z + 0.9), (26.1, yy + 2.2, PAD_Z + 2.4))
    for xx in (-22.0, -17.0, -12.0, -7.0):                        # and the south edge, by the cars
        b.box("barrier", (xx - 2.2, -26.4, PAD_Z), (xx + 2.2, -25.0, PAD_Z + 0.9))
        b.box("barrier", (xx - 2.2, -26.1, PAD_Z + 0.9), (xx + 2.2, -25.3, PAD_Z + 2.4))
    for cx, cy, h in ((22.5, 22.5, 1.8), (20.5, 22.5, 1.8), (22.5, 20.5, 1.8), (22.5, 22.5, 3.6)):
        b.box("crate", (cx - 1.0, cy - 1.0, PAD_Z + h - 1.8), (cx + 1.0, cy + 1.0, PAD_Z + h))


def build_shapes():
    parts = {k: Builder(SURFACES) for k in ("building", "intact")}
    main, intact = parts["building"], parts["intact"]
    tower(main)
    podium(main)
    pylon_base(main)
    plaza(main)
    car(main, -18.0, -20.5, math.pi / 2)
    car(main, -12.0, -20.5, math.pi / 2)
    gate(main)
    pylon_top(intact)
    crown_frame(intact)
    return parts


def emblems():
    """The faction's mark high on the pylon's front and side, and over the entrance."""
    x, y, top = PYLON
    z0, z1 = top - 5.0, top - 1.6
    f = y - 1.03
    s = x - 1.83
    return [decal("EMBLEM", [(x - 1.5, f, z0), (x + 1.5, f, z0), (x + 1.5, f, z1), (x - 1.5, f, z1)]),
            decal("EMBLEM2", [(s, y + 0.85, z0), (s, y - 0.85, z0), (s, y - 0.85, z0 + 1.7), (s, y + 0.85, z0 + 1.7)]),
            decal("EMBLEM3", [(0.4, PODIUM[2] + 0.37, PAD_Z + 5.0), (3.6, PODIUM[2] + 0.37, PAD_Z + 5.0),
                              (3.6, PODIUM[2] + 0.37, PAD_Z + 8.0), (0.4, PODIUM[2] + 0.37, PAD_Z + 8.0)])]


def house_colours():
    """The player's colour: a band under the tower's roof slab, two stripes down the pylon's front."""
    cx, cy = C
    za, zb = TOWER_TOP - 0.62, TOWER_TOP - 0.05
    pts = octagon(cx, cy, HALF + 0.2, CHAMFER)
    bm = bmesh.new()
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        bm.faces.new([bm.verts.new(v) for v in ((ax, ay, za), (bx, by, za), (bx, by, zb), (ax, ay, zb))])
    objects = [new_object("HOUSECOLOR01", bm)]
    x, y, _ = PYLON
    f = y - 1.02
    bm = bmesh.new()
    for u in (-1.5, 1.0):
        q = [(x + u, f, PODIUM[4] + 1.0), (x + u + 0.5, f, PODIUM[4] + 1.0), (x + u + 0.5, f, 40.0), (x + u, f, 40.0)]
        bm.faces.new([bm.verts.new(v) for v in q])
    objects.append(new_object("HOUSECOLOR02", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "funds_office_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, f"{PREFIX}_emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))

    objects = make_objects(build_shapes(), SURFACES, tiles)
    ground = flat_ground("PAD", PAD_HALF, PAD_Z)
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
    banners = house_colours()
    colour = house_material()
    for obj in banners:
        obj.data.materials.append(colour)
    return dict(objects=objects, pad=ground, emblems=marks, banners=banners)


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked (the pylon's top and the crown's frame are gone)."""
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    for i, at in enumerate(SMOKE, 1):
        model.bone(f"SMOKE{i:02d}", w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{version.lower()}{'n' if night else ''}.tga"
    wrecked = version == "_E"
    objects = parts["objects"]
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(objects["building"]), texture=texture)
    if not wrecked:
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(objects["intact"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]), texture=f"{PREFIX}_pad{'_e' if wrecked else ''}.tga", **flat)
    for obj in parts["emblems"]:
        if wrecked and obj.name in ("EMBLEM", "EMBLEM2"):
            continue
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["banners"]:
        if wrecked and obj.name == "HOUSECOLOR02":
            continue
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

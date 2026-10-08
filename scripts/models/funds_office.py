"""The European Funds Office (Europe's money maker, in place of the USA's supply drop zone), modelled in
Blender and written as W3D models for the game: a three-storey bureau of plaster and curtain-wall glass with
a lower wing, a pylon carrying the faction's mark, a plaza with a fountain and hedges, two official cars,
and a guard booth, blast barriers and sandbags so it still reads as military (after a concept painted in the
game's style). Made the way the Command Centre is, with the Logistics Centre's machinery
(logistics_centre.py).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/funds_office.py

Six models: EUFUNDS (intact), _D, _E (wrecked: no pylon, dishes or masts), each with a night version
(_N, _DN, _EN) with lit windows. The footprint is the USA's drop zone's (54 by 54, centred). Buildings are
placed turned by -45 degrees, so the corner at (+X, -Y), with the plaza and the gate, faces the camera.
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
import logistics_centre as lc  # noqa: E402
from blender_kit import load_image, mesh_data, new_object, textured  # noqa: E402
import w3d  # noqa: E402

NAME = "EUFUNDS"
PREFIX = "eufo"
PAD_Z = lc.PAD_Z
# The office's own surfaces, on top of the Logistics Centre's (the Builder marks faces from these).
lc.SURFACES.clear()
lc.SURFACES.update({
    "wall": ("tile_wall", 16.0), "office": ("tile_office", 12.0), "trim": ("tile_trim", 12.0),
    "deck": ("tile_deck", 16.0), "shutter": ("tile_shutter", 6.0), "metal": ("tile_metal", 6.0),
    "crate": ("tile_crate", 4.0), "sandbag": ("tile_sandbag", 4.0), "hazard": ("tile_hazard", 3.0),
    "grille": ("tile_grille", 3.0), "curtain": ("tile_curtain", 5.0), "curtain_dark": ("tile_curtain", 5.0),
    "hedge": ("tile_hedge", 3.0), "paving": ("tile_paving", 6.0), "dome": ("tile_dome", 6.0),
    "glass": (40, 72, 92), "dark": (38, 40, 44), "yellow": (222, 182, 46), "red": (196, 52, 40),
    "white": (226, 226, 222), "lamp": (240, 236, 210), "water": (84, 140, 176), "navy": (40, 52, 92),
    "car": (30, 32, 38),
})
lc.SURFACE.clear()
lc.SURFACE.update({name: i for i, name in enumerate(lc.SURFACES)})
lc.GLOWING = ("curtain", "glass", "lamp")

MAIN = (-25.0, 0.0, 0.0, 25.0)       # x0, x1, y0, y1 of the three-storey block
WING = (0.0, 25.0, 8.0, 25.0)        # the two-storey wing
STOREY = 5.2
PYLON = (3.6, -3.6)
FOUNTAIN = (-6.0, -11.0)
SMOKE = [(-14.0, 14.0, 17.5), (12.0, 18.0, 12.0), (-20.0, 4.0, 6.0)]


def block(b, rect, storeys, dark_storeys=()):
    """An office block: curtain-wall glass storeys between plaster floor bands and corner piers, a plinth, a
    parapet round a roof deck. Returns the roof's height."""
    x0, x1, y0, y1 = rect
    top = PAD_Z + storeys * STOREY
    inset = 0.5
    for k in range(storeys):
        z = PAD_Z + k * STOREY
        b.box("curtain_dark" if k in dark_storeys else "curtain", (x0 + inset, y0 + inset, z), (x1 - inset, y1 - inset, z + STOREY))
        b.box("office", (x0, y0, z + STOREY - 0.9), (x1, y1, z + STOREY))     # the floor band
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, PAD_Z + 1.0))   # plinth
    for x in (x0, x1):
        for y in (y0, y1):
            b.box("office", (x - 1.3 if x == x0 else x - 2.6, y - 1.3 if y == y0 else y - 2.6, PAD_Z),
                  (x + 2.6 if x == x0 else x + 1.3, y + 2.6 if y == y0 else y + 1.3, top + 0.6))
    # Mid piers on the long faces, so the glass reads as bays.
    for x in (x0 + (x1 - x0) / 3, x0 + 2 * (x1 - x0) / 3):
        for y in (y0, y1):
            b.box("office", (x - 0.6, y - 0.3, PAD_Z), (x + 0.6, y + 0.3, top))
    for y in (y0 + (y1 - y0) / 3, y0 + 2 * (y1 - y0) / 3):
        for x in (x0, x1):
            b.box("office", (x - 0.3, y - 0.6, PAD_Z), (x + 0.3, y + 0.6, top))
    lc.ring(b, "trim", x0 - 0.6, x1 + 0.6, y0 - 0.6, y1 + 0.6, top, top + 1.4, 1.2)
    b.box("deck", (x0 + 0.6, y0 + 0.6, top), (x1 - 0.6, y1 - 0.6, top + 0.2))
    return top


def offices(b):
    main_top = block(b, MAIN, 3, dark_storeys=(1,))
    wing_top = block(b, WING, 2, dark_storeys=(0,))
    x0, x1, y0, y1 = MAIN
    # The entrance on the plaza: a canopy, glass doors, steps.
    b.box("dark", (-12.5, y0 - 0.3, PAD_Z), (-7.5, y0, PAD_Z + 4.0))
    b.box("glass", (-12.0, y0 - 0.4, PAD_Z + 0.3), (-8.0, y0 - 0.3, PAD_Z + 3.6))
    b.box("trim", (-13.5, y0 - 3.4, PAD_Z + 4.2), (-6.5, y0, PAD_Z + 4.8))
    for x in (-13.2, -6.8):
        b.box("metal", (x - 0.2, y0 - 3.2, PAD_Z), (x + 0.2, y0 - 2.8, PAD_Z + 4.2))
    for k in range(2):
        b.box("trim", (-13.0, y0 - 1.2 - k * 1.0, PAD_Z), (-7.0, y0, PAD_Z + 0.8 - k * 0.35))
    # Armoured ground floor: steel shutters over the glass at the west end and on the wing's front.
    for xa, xb in ((-23.0, -18.0), (-17.0, -14.0)):
        b.box("shutter", (xa, y0 - 0.2, PAD_Z + 0.6), (xb, y0 + 0.5, PAD_Z + 4.0))
    for xa, xb in ((14.0, 18.0), (19.0, 23.0)):
        b.box("shutter", (xa, WING[2] - 0.2, PAD_Z + 0.6), (xb, WING[2] + 0.5, PAD_Z + 4.0))
    b.box("dark", (5.0, WING[2] - 0.3, PAD_Z), (8.0, WING[2], PAD_Z + 3.6))   # the wing's door
    b.box("trim", (4.4, WING[2] - 1.6, PAD_Z + 3.8), (8.6, WING[2], PAD_Z + 4.3))
    # Roof machinery.
    for x in (-21.0, -15.0):
        b.box("metal", (x, 16.0, main_top + 0.2), (x + 4.5, 21.5, main_top + 2.6))
        b.box("grille", (x + 0.3, 15.9, main_top + 0.6), (x + 4.2, 16.0, main_top + 2.2))
    b.box("metal", (-8.0, 4.0, main_top + 0.2), (-3.0, 8.0, main_top + 1.8))
    b.box("metal", (14.0, 18.0, wing_top + 0.2), (20.0, 22.0, wing_top + 2.0))
    b.box("grille", (14.3, 17.9, wing_top + 0.5), (19.7, 18.0, wing_top + 1.7))
    return main_top, wing_top


def dishes_and_masts(b, main_top, wing_top):
    """Two dishes on the main roof, an antenna mast on the wing."""
    for (x, y), radius, facing in (((-18.0, 6.0), 2.4, -0.8), ((-11.0, 9.0), 1.8, -1.6)):
        b.cylinder("metal", (x, y, main_top + 1.2), 0.3, 2.2, segments=6)
        def make(bm, x=x, y=y, radius=radius, facing=facing):
            m = (Matrix.Translation((x, y, main_top + 2.6)) @ Matrix.Rotation(facing, 4, "Z")
                 @ Matrix.Rotation(-math.pi / 2 + 0.6, 4, "Y"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=10, radius1=radius, radius2=radius * 0.3,
                                  depth=radius * 0.4, matrix=m)
        b.add("dome", make)
    x, y = 21.0, 12.0
    b.box("trim", (x - 1.0, y - 1.0, wing_top + 0.2), (x + 1.0, y + 1.0, wing_top + 0.8))
    b.cylinder("metal", (x, y, wing_top + 5.0), 0.2, 9.0, segments=6)
    for z in (wing_top + 4.0, wing_top + 7.0):
        b.box("metal", (x - 1.2, y - 0.1, z), (x + 1.2, y + 0.1, z + 0.2))
    b.sphere("red", (x, y, wing_top + 9.7), 0.35, segments=(6, 4))


def pylon(b):
    """A tall square pylon in navy with a stone base and a steel cap: the faction's mark at the top."""
    x, y = PYLON
    b.box("trim", (x - 2.4, y - 2.4, PAD_Z), (x + 2.4, y + 2.4, PAD_Z + 1.6))
    b.box("navy", (x - 1.8, y - 1.8, PAD_Z + 1.6), (x + 1.8, y + 1.8, 22.0))
    b.box("trim", (x - 2.1, y - 2.1, 22.0), (x + 2.1, y + 2.1, 23.0))
    b.box("metal", (x - 1.2, y - 1.2, 23.0), (x + 1.2, y + 1.2, 23.6))


def plaza(b):
    """The fountain, hedges in planters, benches, lamps."""
    fx, fy = FOUNTAIN
    b.cylinder("trim", (fx, fy, PAD_Z + 0.5), 3.8, 1.0, segments=16)
    b.cylinder("water", (fx, fy, PAD_Z + 1.05), 3.3, 0.2, segments=16)
    b.cylinder("trim", (fx, fy, PAD_Z + 1.6), 0.6, 2.2, segments=8)
    b.cylinder("trim", (fx, fy, PAD_Z + 2.8), 1.6, 0.4, segments=12)
    b.cylinder("water", (fx, fy, PAD_Z + 3.05), 1.3, 0.12, segments=12)
    # A hedge square at the west of the plaza, planters along the wing.
    for (xa, ya), (xb, yb) in (((-23.5, -15.0), (-14.5, -14.0)), ((-23.5, -7.0), (-14.5, -6.0)),
                               ((-23.5, -14.0), (-22.5, -7.0))):
        b.box("trim", (xa - 0.3, ya - 0.3, PAD_Z), (xb + 0.3, yb + 0.3, PAD_Z + 0.8))
        b.box("hedge", (xa, ya, PAD_Z + 0.8), (xb, yb, PAD_Z + 2.0))
    for x in (11.0, 16.0, 21.0):
        b.box("trim", (x - 1.8, 5.0, PAD_Z), (x + 1.8, 7.0, PAD_Z + 0.9))
        b.box("hedge", (x - 1.5, 5.3, PAD_Z + 0.9), (x + 1.5, 6.7, PAD_Z + 1.9))
    for x, y in ((-19.0, -10.5), (-6.0, -4.0)):
        b.box("dark", (x - 1.6, y - 0.4, PAD_Z + 0.6), (x + 1.6, y + 0.4, PAD_Z + 0.9))
        for dx in (-1.3, 1.3):
            b.box("dark", (x + dx - 0.15, y - 0.3, PAD_Z), (x + dx + 0.15, y + 0.3, PAD_Z + 0.6))
    for x, y in ((-2.0, -16.0), (-24.0, -2.0)):
        b.cylinder("dark", (x, y, PAD_Z + 3.0), 0.15, 6.0, segments=6)
        b.sphere("lamp", (x, y, PAD_Z + 6.2), 0.45, segments=(8, 4))


def car(b, x, y, angle):
    """An official saloon car: body, cabin, dark windows."""
    c, s = math.cos(angle), math.sin(angle)

    def at(u, v, z):
        return (x + u * c - v * s, y + u * s + v * c, z)
    b.turned_box("car", at(0, 0, PAD_Z + 0.95), (8.0, 3.4, 1.3), angle)
    b.turned_box("car", at(-0.4, 0, PAD_Z + 2.1), (4.2, 3.0, 1.1), angle)
    b.turned_box("glass", at(-0.4, 0, PAD_Z + 2.1), (4.3, 2.9, 0.8), angle)
    for u in (-2.6, 2.6):
        for v in (-1.55, 1.55):
            b.add("dark", lambda bm, u=u, v=v: bmesh.ops.create_cone(
                bm, cap_ends=True, segments=8, radius1=0.65, radius2=0.65, depth=0.5,
                matrix=Matrix.Translation(at(u, v, PAD_Z + 0.65)) @ Matrix.Rotation(angle, 4, "Z")
                @ Matrix.Rotation(math.pi / 2, 4, "X")))


def gate(b):
    """The guard booth with a barrier arm across the driveway, sandbags, blast barriers along the edges."""
    x, y = 19.5, -7.5
    b.box("trim", (x - 2.6, y - 2.6, PAD_Z), (x + 2.6, y + 2.6, PAD_Z + 0.5))
    b.box("office", (x - 2.0, y - 2.0, PAD_Z + 0.5), (x + 2.0, y + 2.0, PAD_Z + 4.6))
    b.box("glass", (x - 2.1, y - 1.4, PAD_Z + 2.4), (x + 2.1, y + 1.4, PAD_Z + 3.8))
    b.box("glass", (x - 1.4, y - 2.1, PAD_Z + 2.4), (x + 1.4, y + 2.1, PAD_Z + 3.8))
    b.box("trim", (x - 2.6, y - 2.6, PAD_Z + 4.6), (x + 2.6, y + 2.6, PAD_Z + 5.2))
    b.box("hazard", (x - 1.0, y - 3.6, PAD_Z), (x + 1.0, y - 2.6, PAD_Z + 2.6))   # the arm's post
    b.box("hazard", (x - 10.0, y - 3.3, PAD_Z + 2.2), (x - 1.0, y - 2.9, PAD_Z + 2.6))
    for k in range(3):   # sandbags in front of the booth
        b.box("sandbag", (x + 2.8, y - 3.0 + k * 0.0, PAD_Z + k * 0.9), (x + 4.4, y + 3.0, PAD_Z + (k + 1) * 0.9))
    # Blast barriers along the east and south edges, leaving the driveway open.
    for yy in (-4.0, 1.0, 6.0, 11.0, 16.0, 21.0):
        b.box("wall", (24.4, yy - 2.2, PAD_Z), (25.6, yy + 2.2, PAD_Z + 0.9))
        b.box("wall", (24.6, yy - 2.2, PAD_Z + 0.9), (25.4, yy + 2.2, PAD_Z + 2.2))
    for xx in (-1.0, 4.0):
        b.box("wall", (xx - 2.2, -25.6, PAD_Z), (xx + 2.2, -24.4, PAD_Z + 0.9))
        b.box("wall", (xx - 2.2, -25.4, PAD_Z + 0.9), (xx + 2.2, -24.6, PAD_Z + 2.2))
    lc.crate_stack(b, 21.5, -22.5, [(0, 0, 2), (1, 0, 1), (0, 1, 1)], size=2.6)


def build_shapes():
    main, intact = lc.Builder(), lc.Builder()
    main_top, wing_top = offices(main)
    plaza(main)
    car(main, -19.2, -20.5, math.pi / 2)
    car(main, -11.8, -20.5, math.pi / 2)
    gate(main)
    pylon(intact)
    dishes_and_masts(intact, main_top, wing_top)
    return main, intact, main_top


def emblems():
    """The faction's mark high on the pylon's two faces towards the camera, and over the entrance."""
    x, y = PYLON
    h, z0, z1 = 1.65, 17.4, 20.7
    marks = [lc.decal("EMBLEM", [(x - h, y - 1.85, z0), (x + h, y - 1.85, z0), (x + h, y - 1.85, z1), (x - h, y - 1.85, z1)]),
             lc.decal("EMBLEM2", [(x + 1.85, y - h, z0), (x + 1.85, y + h, z0), (x + 1.85, y + h, z1), (x + 1.85, y - h, z1)])]
    marks.append(lc.decal("EMBLEM3", [(-11.6, MAIN[2] - 0.55, PAD_Z + 5.0), (-8.4, MAIN[2] - 0.55, PAD_Z + 5.0),
                                     (-8.4, MAIN[2] - 0.55, PAD_Z + 8.2), (-11.6, MAIN[2] - 0.55, PAD_Z + 8.2)]))
    return marks


def house_colours(main_top):
    """The player's colour: a band under the main block's parapet, stripes down the pylon's edges."""
    x0, x1, y0, y1 = MAIN
    objects = []
    bm = bmesh.new()
    za, zb = main_top - 1.6, main_top - 0.95
    pts = [(x0 - 0.05, y0 - 0.05), (x1 + 0.05, y0 - 0.05), (x1 + 0.05, y1 + 0.05), (x0 - 0.05, y1 + 0.05)]
    for (ax, ay), (bx, by) in zip(pts, pts[1:] + pts[:1]):
        bm.faces.new([bm.verts.new(v) for v in ((ax, ay, za), (bx, by, za), (bx, by, zb), (ax, ay, zb))])
    objects.append(new_object("HOUSECOLOR01", bm))
    px, py = PYLON
    quads = []
    for u in (-1.85 + 0.15, 1.85 - 0.65):   # two stripes on each face towards the camera
        quads.append([(px + u, py - 1.86, 2.4), (px + u + 0.5, py - 1.86, 2.4), (px + u + 0.5, py - 1.86, 14.8),
                      (px + u, py - 1.86, 14.8)])
        quads.append([(px + 1.86, py + u, 2.4), (px + 1.86, py + u + 0.5, 2.4), (px + 1.86, py + u + 0.5, 14.8),
                      (px + 1.86, py + u, 14.8)])
    bm = bmesh.new()
    for q in quads:
        bm.faces.new([bm.verts.new(v) for v in q])
    objects.append(new_object("HOUSECOLOR02", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


PAD_OUTLINE = [(-27, -27), (27, -27), (27, 27), (-27, 27)]
EXTENT = (-27.0, 27.0, -27.0, 27.0)


def build():
    tex_dir = os.path.join(lc.DATA, "Art", "TexturesHD")
    paint = os.path.join(HERE, "funds_office_paint.py")
    tiles = os.path.join(lc.BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, f"{PREFIX}_emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))
    main, intact, main_top = build_shapes()
    ground = lc.pad_mesh(PAD_OUTLINE, EXTENT)
    objects = lc.bake_building((("BUILDING", main), ("INTACT", intact)), PREFIX, paint, ground, top=24.0)
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, f"{PREFIX}_emblem.tga")))
    banners = house_colours(main_top)
    lc.house_material(banners)
    return dict(building=objects[0], intact=objects[1], pad=ground, emblems=marks, banners=banners)


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked (the pylon has fallen: no pylon, its marks or stripes)."""
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    for i, at in enumerate(SMOKE, 1):
        model.bone(f"SMOKE{i:02d}", w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{version.lower()}{'n' if night else ''}.tga"
    wrecked = version == "_E"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if not wrecked:
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
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
    model.save(os.path.join(lc.DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(lc.BUILD, exist_ok=True)
    parts = build()
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(lc.BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

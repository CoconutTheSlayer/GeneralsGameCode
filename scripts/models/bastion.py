"""The European Artillery Bastion, modelled in Blender and written as W3D models for the game: a heavy,
low hexagonal casemate of dark bare concrete with steeply sloped glacis walls, half buried in packed earth
berms heaped against five of its six sides, firing slits above the earth line, a sloped parapet round a
gun deck, and an armoured howitzer turret on a raised ring; the bare back wall carries a recessed blast-door
portal (after a concept painted in the game's style). Everything is made here, so the models and textures
can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/bastion.py

Painted as the Command Centre and the SAMP/T Battery (the shared code is samp_battery.py's):
bastion_paint.py paints small tiling surfaces, Blender projects them onto the model and bakes them with
the ambient occlusion into one texture; the painter makes the damaged, wrecked and night versions and the
ground, an earth patch cut out by its alpha. Six models: EUBAST (intact), _D, _E (no clutter, antenna or
cupola), each with a night version (_N, _DN, _EN).

Bones (as the USA's Fire Base, ABFIREBASE, which the game's INI names):
    TURRET01               the turret, turning about Z
    TURRETEL               the gun's trunnion, a child of TURRET01, pitching about Y; the gun points +X
    BARREL01               the barrel, recoiling when it fires (WeaponRecoilBone Barrel)
    MUZZLE0101             where the shell leaves (WeaponLaunchBone MUZZLE01)
    MUZZLEFX01             the muzzle flash, a mesh of that name shown when it fires (WeaponMuzzleFlash,
                           WeaponFireFXBone MuzzleFX)
    STATION01..STATION04   where the garrison stands, on the gun deck behind the parapet's corners
                           (GarrisonContain places infantry at STATION bones, named by ExtraPublicBone)

The footprint is the USA's (a box of 52 by 52, 15 high, centred); the berms reach 25.5 along X, 20 along Y.
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
from samp_battery import (BUILD, DATA, Builder, bake_all, band, decal, flat_ground, house_material,  # noqa: E402
                          make_objects, moved)

NAME = "EUBAST"
PREFIX = "eufb"
PAD_Z = 0.05
PAD_HALF = 26.0
HEIGHT_TOP = 18.0
SURFACES = {
    "concrete": ("tile_concrete", 10.0), "slab": ("tile_slab", 6.0), "earth": ("tile_earth", 9.0),
    "trim": ("tile_trim", 8.0), "door": ("tile_door", 6.0), "metal": ("tile_metal", 4.0),
    "sandbag": ("tile_sandbag", 3.0), "hazard": ("tile_hazard", 2.5), "grille": ("tile_grille", 2.0),
    "crate": ("tile_crate", 3.0), "steel": ("tile_steel", 8.0), "armour": ("tile_armour", 8.0),
    "glass": (40, 72, 92), "dark": (24, 25, 28), "yellow": (222, 182, 46), "red": (196, 52, 40),
}

# The casemate's plan at the ground (counter-clockwise), its walls leaning in by SLOPE up to the deck.
PLAN = [(-13.5, -13.0), (13.5, -13.0), (18.5, 0.0), (13.5, 13.0), (-13.5, 13.0), (-18.5, 0.0)]
DECK = 8.0
SLOPE = 3.2
BERM = [(-0.4, -0.4), (-2.3, 4.6), (0.0, 5.0), (1.6, 4.7), (3.4, 3.4), (5.4, 1.4), (7.4, -0.4)]   # (offset, z), a mound
PLATFORM = (7.4, 1.2)                    # the gun ring's radius and height on the deck
TURRET_AT = (0.0, 0.0, DECK + 1.2)       # TURRET01, on the gun ring
TRUNNION = (6.0, 0.0, DECK + 4.2)        # TURRETEL, in the world
MUZZLE = 23.8                            # from the trunnion along the barrel
STATIONS = [(1, 1), (1, -1), (-1, -1), (-1, 1)]   # STATION01..04, on the deck (as the USA's order)
STATION_AT = (9.5, 5.6)


def normals(points, closed=True):
    """Outward normals (x, y) of a counter-clockwise outline's edges."""
    n = len(points) if closed else len(points) - 1
    out = []
    for i in range(n):
        (ax, ay), (bx, by) = points[i], points[(i + 1) % len(points)]
        length = math.hypot(bx - ax, by - ay)
        out.append(((by - ay) / length, -(bx - ax) / length))
    return out


def offset(points, d, closed=True):
    """The outline moved out by d (mitred corners)."""
    ns = normals(points, closed)
    out = []
    for i, (x, y) in enumerate(points):
        if closed:
            a, b = ns[i - 1], ns[i]
        else:
            a = ns[max(i - 1, 0)]
            b = ns[min(i, len(ns) - 1)]
        mx, my = a[0] + b[0], a[1] + b[1]
        k = d / (1 + a[0] * b[0] + a[1] * b[1])
        out.append((x + mx * k, y + my * k))
    return out


def loft(b, surface, path, profile, closed=True):
    """A closed cross-section (offset out of the path, z) carried along a counter-clockwise path: a berm, a
    parapet. Closed paths make a ring; open ones are capped at both ends. One closed shape."""
    def make(bm):
        rows = [offset(path, d, closed) for d, _ in profile]
        loops = [[bm.verts.new((rows[j][i][0], rows[j][i][1], profile[j][1])) for j in range(len(profile))]
                 for i in range(len(path))]
        n = len(profile)
        steps = len(path) if closed else len(path) - 1
        for i in range(steps):
            a, c = loops[i], loops[(i + 1) % len(path)]
            for j in range(n):
                k = (j + 1) % n
                bm.faces.new((a[j], a[k], c[k], c[j]))
        if not closed:
            bm.faces.new(loops[0])
            bm.faces.new(list(reversed(loops[-1])))
    b.add(surface, make)


def solid(b, surface, bottom, top, z0, z1):
    """A block from one outline at z0 to another (same corners) at z1."""
    def make(bm):
        lo = [bm.verts.new((x, y, z0)) for x, y in bottom]
        hi = [bm.verts.new((x, y, z1)) for x, y in top]
        bm.faces.new(list(reversed(lo)))
        bm.faces.new(hi)
        for i in range(len(lo)):
            j = (i + 1) % len(lo)
            bm.faces.new((lo[i], lo[j], hi[j], hi[i]))
    b.add(surface, make)


def on_wall(edge, along, z, depth=0.0):
    """A point on the sloped wall over PLAN's edge `edge`, `along` (0..1) its length, at height z, moved
    `depth` out of the wall; and the turn that lays a box's X axis along the wall's outward normal."""
    (ax, ay), (bx, by) = PLAN[edge], PLAN[(edge + 1) % len(PLAN)]
    nx, ny = normals(PLAN)[edge]
    inset = SLOPE * z / DECK
    lean = math.atan2(SLOPE, DECK)
    x = ax + (bx - ax) * along - nx * (inset - depth * math.cos(lean))
    y = ay + (by - ay) * along - ny * (inset - depth * math.cos(lean))
    turn = Matrix.Rotation(math.atan2(ny, nx), 4, "Z") @ Matrix.Rotation(-lean, 4, "Y")
    return (x, y, z + depth * math.sin(lean)), turn


def casemate(b):
    """The concrete casemate, its parapet, the gun ring, firing slits, the blast-door portal at the back."""
    top = offset(PLAN, -SLOPE)
    solid(b, "concrete", PLAN, top, -0.4, DECK)
    loft(b, "concrete", top, [(0.0, DECK - 0.1), (-0.5, DECK + 1.3), (-1.7, DECK + 1.3), (-1.7, DECK - 0.1)])
    loft(b, "slab", offset(PLAN, -SLOPE - 0.5), [(0.1, DECK + 1.3), (0.1, DECK + 1.55), (-1.3, DECK + 1.55), (-1.3, DECK + 1.3)])
    b.cylinder("concrete", (0, 0, DECK + PLATFORM[1] / 2), PLATFORM[0], PLATFORM[1], segments=24)
    b.cylinder("slab", (0, 0, DECK + PLATFORM[1] + 0.05), PLATFORM[0] - 0.4, 0.1, segments=24)
    for k in range(8):                       # small hazard marks round the gun ring's edge
        a = k * math.pi / 4 + math.pi / 8
        b.oriented_box("hazard", (math.cos(a) * (PLATFORM[0] + 0.02), math.sin(a) * (PLATFORM[0] + 0.02), DECK + 0.7),
                       (0.1, 1.2, 0.6), Matrix.Rotation(a, 4, "Z"))
    # Firing slits above the earth line: a heavy concrete hood over a dark slot, on every side.
    for edge, places in ((0, ((0.22, 5.0), (0.5, 5.0), (0.78, 5.0))), (1, ((0.5, 5.5),)), (2, ((0.5, 5.5),)),
                         (3, ((0.14, 3.4), (0.86, 3.4))), (4, ((0.5, 5.5),)), (5, ((0.5, 5.5),))):
        for along, w in places:
            at, turn = on_wall(edge, along, 5.9, 0.05)
            b.oriented_box("dark", at, (0.3, w, 0.75), turn)
            at, turn = on_wall(edge, along, 6.75, 0.35)
            b.oriented_box("slab", at, (0.9, w + 1.0, 0.45), turn)
    # The portal on the bare back wall (+Y): a projecting concrete frame, a steel blast door, hazard posts.
    b.box("concrete", (-5.2, 9.0, -0.4), (5.2, 15.4, 7.4))
    b.box("slab", (-5.6, 9.0, 7.4), (5.6, 15.8, 8.0))
    b.box("door", (-3.4, 15.4, 0.0), (3.4, 15.6, 4.8))
    for x in (-4.3, 4.3):
        b.box("hazard", (x - 0.35, 15.4, 0.0), (x + 0.35, 16.2, 3.4))
    b.box("trim", (-3.8, 15.6, 4.8), (3.8, 16.6, 5.2))
    # Vents and a ready-ammunition hatch on the deck.
    for x, y in ((-10.0, -6.0), (-10.0, 6.0)):
        b.box("grille", (x - 1.4, y - 0.9, DECK), (x + 1.4, y + 0.9, DECK + 0.7))
    b.box("steel", (8.5, -7.6, DECK), (11.0, -5.6, DECK + 0.4))


def berms(b):
    """Earth heaped against five sides, leaving the back wall bare; sandbags along its foot."""
    loft(b, "earth", [PLAN[4], PLAN[5], PLAN[0], PLAN[1], PLAN[2], PLAN[3]], BERM, closed=False)
    for x0, x1 in ((-12.5, -6.0), (6.0, 12.5)):
        b.box("sandbag", (x0, 13.0, -0.2), (x1, 14.6, 1.2))
        b.box("sandbag", (x0 + 0.5, 13.2, 1.2), (x1 - 0.5, 14.2, 2.1))


def clutter(b):
    """Lost when the bastion is wrecked: an observation cupola, an antenna, crates and sandbags."""
    tx, ty = -10.6, -0.0
    b.cylinder("armour", (tx, ty, DECK + 0.9), 1.7, 1.8, segments=12)
    b.cylinder("trim", (tx, ty, DECK + 1.95), 2.0, 0.35, segments=12)
    b.cylinder("dark", (tx, ty, DECK + 1.3), 1.75, 0.4, segments=12)
    b.cylinder("metal", (-10.0, 7.0, DECK + 5.0), 0.12, 8.0, segments=5)
    b.sphere("red", (-10.0, 7.0, DECK + 9.1), 0.3, 6, 4)
    for x, y, z in ((-8.6, -6.6, 0), (-6.6, -6.6, 0), (-7.6, -6.6, 1.4)):
        b.box("crate", (x - 0.9, y - 0.7, DECK + z), (x + 0.9, y + 0.7, DECK + z + 1.4))
    for x, y in ((8.6, 6.6), (10.4, 5.2)):
        b.box("sandbag", (x - 1.0, y - 0.6, DECK), (x + 1.0, y + 0.6, DECK + 0.9))
    for x in (-8.0, -10.2):                       # crates and drums by the portal
        b.box("crate", (x - 1.0, 14.6, -0.2), (x + 1.0, 16.4, 1.6))
    for x, y in ((8.8, 15.6), (10.4, 15.4)):
        b.cylinder("trim", (x, y, 1.0), 0.7, 2.2, segments=8)


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
    casemate(parts["building"])
    berms(parts["building"])
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
    """The faction's mark over the blast door."""
    y = 15.43
    return [decal("EMBLEM", [(0.9, y, 5.4), (-0.9, y, 5.4), (-0.9, y, 7.2), (0.9, y, 7.2)])]


def house_colours():
    """The player's colour: a band round the gun platform, stripes on the turret's sides."""
    on_body = [band("HOUSECOLOR01", (0, 0), PLATFORM[0] + 0.03, DECK + 0.1, DECK + 0.35, segments=24)]
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
    for k, (sx, sy) in enumerate(STATIONS):
        model.bone(f"STATION0{k + 1}", w3d.CHASSIS, (sx * STATION_AT[0], sy * STATION_AT[1], DECK))
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

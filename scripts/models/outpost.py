"""The European Forward Outpost, modelled in Blender and written as W3D models for the game: a compact
blockhouse of light cast concrete with chamfered corners, firing slits on every side and a steel door
under the faction's mark, ringed by low sandbag walls; a lattice lookout tower with a glazed cab and a
mast flying a small flag in the player's colour; a white medical container and a field tent marked with
red crosses (the post patches up the troops around it); crates, an antenna and jerry cans (after a concept
painted in the game's style). Everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/outpost.py

Painted as the Command Centre and the SAMP/T Battery (the shared code is samp_battery.py's):
outpost_paint.py paints small tiling surfaces, Blender projects them onto the model and bakes them with
the ambient occlusion into one texture; the painter makes the damaged, wrecked and night versions (the
tower's cab lit) and the ground, a gravel patch cut out by its alpha. Six models: EUOUTP (intact), _D, _E
(the tower, tent and container wrecked, the roof clutter gone), each with a night version (_N, _DN, _EN).

Bones:
    FIREPOINT01..06   outside the firing slits: where the garrison shoots from (GarrisonContain looks for
                      FIREPOINT bones, as on China's Bunker, NBBUNKER)
    SMOKE01, SMOKE02, FIRE01   smoke and fire of the damaged and wrecked models (the INI's ParticleSysBone)

The footprint is a box of 40 by 40 (GeometryMajorRadius/MinorRadius 20); the door faces +X, the camera.
"""
import math
import os
import shutil
import subprocess
import sys

import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, textured  # noqa: E402
import w3d  # noqa: E402
from samp_battery import BUILD, DATA, Builder, bake_all, flat_ground, house_material, make_objects  # noqa: E402
from bastion import loft, offset, solid  # noqa: E402
from fusion_plant import both_ways, flat_object  # noqa: E402

NAME = "EUOUTP"
PREFIX = "euop"
PAD_Z = 0.05
PAD_HALF = 20.0
HEIGHT_TOP = 14.0
SURFACES = {
    "concrete": ("tile_concrete", 8.0), "slab": ("tile_slab", 6.0), "trim": ("tile_trim", 6.0),
    "door": ("tile_door", 5.0), "metal": ("tile_metal", 4.0), "sandbag": ("tile_sandbag", 3.2),
    "hazard": ("tile_hazard", 2.0), "grille": ("tile_grille", 2.0), "crate": ("tile_crate", 2.4),
    "steel": ("tile_steel", 6.0), "olive": ("tile_olive", 3.0), "container": ("tile_container", 6.0),
    "canvas": ("tile_canvas", 5.0),
    "glass": (40, 72, 92), "dark": (26, 27, 30), "yellow": (222, 182, 46), "red": (200, 40, 34),
    "white": (232, 232, 228),
}

HALF, CHAMFER, WALL_TOP = 9.0, 2.6, 7.0
PLAN = [(-HALF, -HALF + CHAMFER), (-HALF + CHAMFER, -HALF), (HALF - CHAMFER, -HALF), (HALF, -HALF + CHAMFER),
        (HALF, HALF - CHAMFER), (HALF - CHAMFER, HALF), (-HALF + CHAMFER, HALF), (-HALF, HALF - CHAMFER)]
SLIT_Z = 4.4
# Firing slits: (face normal x, y, position along the face), each with a FIREPOINT outside it.
SLITS = [(0, -1, -3.4), (0, -1, 3.4), (1, 0, -5.0), (1, 0, 5.0), (0, 1, 2.0), (-1, 0, 0.0)]
TOWER = (-12.6, 12.0)                     # the lookout tower's centre
TOWER_LEG, DECK = 2.0, 9.4
CONTAINER = (-15.0, -3.0, -17.2, -12.2, 5.0)   # x0, x1, y0, y1, height
TENT = (-18.6, -12.6, -10.6, -4.4, 4.2)        # x0, x1, y0, y1, ridge height
BONES = {"SMOKE01": (2.0, -2.0, WALL_TOP + 0.5), "SMOKE02": (-9.0, -14.5, 3.0), "FIRE01": (-12.6, 12.0, 4.0)}


def strut(b, surface, a, c, size=0.3):
    """A square beam from point a to point c (lattice legs and braces)."""
    d = [c[i] - a[i] for i in range(3)]
    length = math.sqrt(sum(x * x for x in d))
    yaw = math.atan2(d[1], d[0])
    pitch = math.atan2(d[2], math.hypot(d[0], d[1]))
    turn = Matrix.Rotation(yaw, 4, "Z") @ Matrix.Rotation(-pitch, 4, "Y")
    centre = tuple((a[i] + c[i]) / 2 for i in range(3))
    b.oriented_box(surface, centre, (length, size, size), turn)


def on_face(nx, ny, along, z, out=0.0):
    """A point on the blockhouse's face with outward normal (nx, ny), `along` it (left to right seen from
    outside... any consistent way), at height z, `out` units out of the wall."""
    if nx:
        return (nx * (HALF + out), along, z)
    return (along, ny * (HALF + out), z)


def blockhouse(b):
    """The concrete blockhouse: a footing, walls, a chamfered parapet, slits with hoods, the door."""
    solid(b, "slab", offset(PLAN, 0.5), offset(PLAN, 0.35), -0.4, 1.0)
    solid(b, "concrete", PLAN, PLAN, 0.9, WALL_TOP)
    loft(b, "slab", PLAN, [(0.25, WALL_TOP - 0.3), (0.25, WALL_TOP + 0.5), (-0.15, WALL_TOP + 1.0),
                           (-0.9, WALL_TOP + 1.0), (-0.9, WALL_TOP - 0.3)])
    for nx, ny, along in SLITS:
        w = 2.4 if nx > 0 else 3.4
        size_n, size_t = 0.24, w
        at = on_face(nx, ny, along, SLIT_Z, 0.05)
        b.box("dark", (at[0] - (size_n if nx else size_t) / 2, at[1] - (size_t if nx else size_n) / 2, SLIT_Z - 0.35),
              (at[0] + (size_n if nx else size_t) / 2, at[1] + (size_t if nx else size_n) / 2, SLIT_Z + 0.35))
        hood = on_face(nx, ny, along, SLIT_Z + 0.65, 0.3)
        hn, ht = 0.75, w + 1.0
        b.box("slab", (hood[0] - (hn if nx else ht) / 2, hood[1] - (ht if nx else hn) / 2, SLIT_Z + 0.45),
              (hood[0] + (hn if nx else ht) / 2, hood[1] + (ht if nx else hn) / 2, SLIT_Z + 0.85))
    # The door on the front (+X): a concrete pilaster round a steel door, a sill with hazard stripes.
    b.box("concrete", (HALF - 0.1, -2.3, 0.9), (HALF + 0.7, 2.3, WALL_TOP + 0.6))
    b.box("door", (HALF + 0.7, -1.5, 0.15), (HALF + 0.85, 1.5, 4.1))
    b.box("trim", (HALF + 0.7, -1.8, 4.1), (HALF + 1.0, 1.8, 4.45))
    b.box("hazard", (HALF + 0.7, -1.9, -0.1), (HALF + 2.4, 1.9, 0.18))
    for y in (-1.95, 1.95):
        b.box("hazard", (HALF + 0.7, y - 0.17, 0.15), (HALF + 0.95, y + 0.17, 3.9))
    # Roof: a hatch, a vent.
    b.box("steel", (-4.0, -2.0, WALL_TOP), (-2.0, 0.0, WALL_TOP + 0.35))
    b.box("grille", (2.5, 3.0, WALL_TOP), (4.6, 4.6, WALL_TOP + 0.7))


def sandbag_run(b, a, c, rows=3, bag=(1.25, 0.95, 0.5), skip_end=False):
    """Sandbags laid end to end from a to c (x, y), `rows` high, every other row offset by half a bag."""
    dx, dy = c[0] - a[0], c[1] - a[1]
    length = math.hypot(dx, dy)
    turn = Matrix.Rotation(math.atan2(dy, dx), 4, "Z")
    count = max(1, round(length / bag[0]))
    step = length / count
    for row in range(rows):
        shift = 0.5 if row % 2 else 0.0
        shrink = 0.08 * row
        for k in range(count):
            t = (k + 0.5 + shift) / count
            if t > 1.0:
                continue
            x, y = a[0] + dx * t, a[1] + dy * t
            jitter = 0.04 * ((k * 7 + row * 3) % 5 - 2)
            b.oriented_box("sandbag", (x, y + jitter, bag[2] * (row + 0.5) - 0.1),
                           (step * 0.96, bag[1] - shrink, bag[2] * 0.94), turn)


def sandbags(b):
    """Low sandbag walls round the front corners, open at the door and the back."""
    sandbag_run(b, (-1.0, -12.0), (12.2, -12.0))
    sandbag_run(b, (12.6, -11.6), (12.6, -3.6))
    sandbag_run(b, (12.6, 3.6), (12.6, 11.6))
    sandbag_run(b, (12.2, 12.0), (-8.0, 12.0))


def tower(b, intact):
    """The lookout tower: four lattice legs with braces, a deck with rails, a glazed cab, the mast."""
    tx, ty = TOWER
    h = TOWER_LEG
    corners = [(tx - h, ty - h), (tx + h, ty - h), (tx + h, ty + h), (tx - h, ty + h)]
    for x, y in corners:
        b.box("slab", (x - 0.45, y - 0.45, -0.3), (x + 0.45, y + 0.45, 0.5))
        strut(intact, "trim", (x, y, 0.3), (x + (tx - x) * 0.12, y + (ty - y) * 0.12, DECK), 0.32)
    for i in range(4):
        (ax, ay), (cx, cy) = corners[i], corners[(i + 1) % 4]
        for z0, z1 in ((0.6, DECK * 0.5), (DECK * 0.5, DECK - 0.2)):
            s0, s1 = 0.12 * z0 / DECK, 0.12 * z1 / DECK
            a = (ax + (tx - ax) * s0, ay + (ty - ay) * s0, z0)
            c = (cx + (tx - cx) * s1, cy + (ty - cy) * s1, z1)
            strut(intact, "steel", a, c, 0.16)
    z = DECK
    intact.box("trim", (tx - h - 0.5, ty - h - 0.5, z), (tx + h + 0.5, ty + h + 0.5, z + 0.35))
    for x0, y0, x1, y1 in ((tx - h - 0.5, ty - h - 0.5, tx + h + 0.5, ty - h - 0.4),
                           (tx - h - 0.5, ty + h + 0.4, tx + h + 0.5, ty + h + 0.5),
                           (tx + h + 0.4, ty - h - 0.5, tx + h + 0.5, ty + h + 0.5),
                           (tx - h - 0.5, ty - h - 0.5, tx - h - 0.4, ty + h + 0.5)):
        intact.box("steel", (x0, y0, z + 1.0), (x1, y1, z + 1.12))
    for x, y in ((tx - h - 0.45, ty - h - 0.45), (tx + h + 0.45, ty - h - 0.45), (tx + h + 0.45, ty + h + 0.45),
                 (tx - h - 0.45, ty + h + 0.45)):
        intact.box("steel", (x - 0.06, y - 0.06, z + 0.35), (x + 0.06, y + 0.06, z + 1.12))
    c = 1.7
    intact.box("trim", (tx - c, ty - c, z + 0.35), (tx + c, ty + c, z + 1.4))
    intact.box("glass", (tx - c + 0.05, ty - c + 0.05, z + 1.4), (tx + c - 0.05, ty + c - 0.05, z + 2.6))
    for x, y in ((tx - c, ty - c), (tx + c, ty - c), (tx + c, ty + c), (tx - c, ty + c)):
        intact.box("trim", (x - 0.12, y - 0.12, z + 1.4), (x + 0.12, y + 0.12, z + 2.6))
    intact.box("trim", (tx - c - 0.4, ty - c - 0.4, z + 2.6), (tx + c + 0.4, ty + c + 0.4, z + 3.0))
    intact.box("yellow", (tx + c + 0.38, ty - 0.6, z + 2.62), (tx + c + 0.42, ty + 0.6, z + 2.98))
    intact.cylinder("metal", (tx - 0.8, ty - 0.8, z + 6.5), 0.09, 7.0, segments=6)
    intact.sphere("red", (tx - 0.8, ty - 0.8, z + 10.05), 0.18, 6, 4)
    for k in range(9):                                   # the ladder up the front leg
        intact.box("steel", (tx + h + 0.15, ty - 0.55, 0.9 + k * 0.95), (tx + h + 0.3, ty + 0.55, 1.0 + k * 0.95))


def medical(intact, wreck):
    """The white medical container and the field tent, red crosses on them; on the wreck, crushed."""
    x0, x1, y0, y1, h = CONTAINER
    intact.box("container", (x0, y0, 0.0), (x1, y1, h))
    intact.box("trim", (x0 - 0.1, y0 - 0.1, h - 0.15), (x1 + 0.1, y1 + 0.1, h + 0.1))
    intact.box("trim", (x0 - 0.1, y0 - 0.1, -0.1), (x1 + 0.1, y1 + 0.1, 0.25))
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2

    def cross(at, normal, size):
        """A red cross on a white square, standing a little out of a face with this normal (axis, sign)."""
        axis, sign = normal
        arm, bar = size, size * 0.3
        dims = {0: [(0.06, size * 1.4, size * 1.4), (0.08, arm, bar), (0.08, bar, arm)],
                1: [(size * 1.4, 0.06, size * 1.4), (arm, 0.08, bar), (bar, 0.08, arm)],
                2: [(size * 1.4, size * 1.4, 0.06), (arm, bar, 0.08), (bar, arm, 0.08)]}[axis]
        for k, (sx, sy, sz) in enumerate(dims):
            p = list(at)
            p[axis] += sign * (0.03 + 0.04 * (k > 0))
            intact.box("white" if k == 0 else "red", (p[0] - sx / 2, p[1] - sy / 2, p[2] - sz / 2),
                       (p[0] + sx / 2, p[1] + sy / 2, p[2] + sz / 2))

    cross((cx, cy, h + 0.1), (2, 1), 3.4)
    cross((cx + 2.0, y0, h * 0.55), (1, -1), 2.4)
    cross((x1, cy, h * 0.55), (0, 1), 2.2)
    intact.box("glass", (cx - 4.6, y0 - 0.05, 2.4), (cx - 3.0, y0, 3.6))
    intact.box("door", (x1 - 0.05, cy - 1.8, 0.3), (x1 + 0.08, cy - 0.6, 3.9))
    intact.box("grille", (x0 + 1.0, cy - 1.0, h + 0.1), (x0 + 3.0, cy + 1.0, h + 0.7))
    # The tent: a canvas ridge tent along Y, a red cross on its front gable.
    tx0, tx1, ty0, ty1, th = TENT
    mid = (tx0 + tx1) / 2
    profile = [(tx0, 0.0), (tx1, 0.0), (tx1, 1.8), (mid, th), (tx0, 1.8)]
    intact.prism("canvas", profile, ty0, ty1)
    intact.box("red", (tx1 + 0.02, (ty0 + ty1) / 2 - 0.25, 1.0), (tx1 + 0.1, (ty0 + ty1) / 2 + 0.25, 2.6))
    intact.box("red", (tx1 + 0.02, (ty0 + ty1) / 2 - 0.8, 1.55), (tx1 + 0.1, (ty0 + ty1) / 2 + 0.8, 2.05))
    for y in (ty0 - 0.6, ty1 + 0.6):
        intact.cylinder("metal", (mid, y, th / 2), 0.06, th, segments=5)
    # The wreck: the container crushed and burnt, the tent gone, the tower fallen across the yard.
    wreck.oriented_box("container", (cx, cy, 1.4), (x1 - x0, y1 - y0, 2.6), Matrix.Rotation(0.06, 4, "X"))
    wreck.oriented_box("container", (cx - 2.0, cy, 3.0), (5.0, y1 - y0 - 0.6, 1.0), Matrix.Rotation(0.2, 4, "Y"))
    tx, ty = TOWER
    for k, (dx, dy) in enumerate(((-1, -1), (1, -1), (1, 1), (-1, 1))):
        x, y = tx + dx * TOWER_LEG, ty + dy * TOWER_LEG
        strut(wreck, "trim", (x, y, 0.3), (x + dx * 0.4, y + dy * 0.4, 2.2 + k * 0.7), 0.32)
    strut(wreck, "trim", (tx + 1.0, ty - 1.6, 0.4), (tx + 8.5, ty - 2.4, 1.2), 0.32)
    strut(wreck, "trim", (tx + 1.2, ty + 1.6, 0.4), (tx + 8.6, ty + 0.6, 1.4), 0.32)
    strut(wreck, "steel", (tx + 2.0, ty - 1.8, 0.7), (tx + 7.0, ty + 0.9, 1.2), 0.16)
    wreck.oriented_box("trim", (tx + 9.6, ty - 0.8, 1.3), (3.2, 3.6, 2.0), Matrix.Rotation(0.5, 4, "Y"))
    for x, y, s, a in ((-6.0, -11.0, 1.4, 0.3), (-16.0, -7.0, 1.0, 0.9), (-15.0, 4.0, 1.2, 0.5), (-10.0, 6.0, 0.8, 1.2)):
        wreck.oriented_box("slab", (x, y, s * 0.3), (s * 1.6, s, s * 0.8), Matrix.Rotation(a, 4, "Z"))


def clutter(b):
    """Lost when the outpost is wrecked: crates and an antenna on the roof, crates and jerry cans by the
    container."""
    z = WALL_TOP
    for x, y, zz, s in ((-6.2, 3.0, 0, 1.4), (-4.6, 3.0, 0, 1.3), (-5.4, 3.1, 1.3, 1.2), (5.0, -5.2, 0, 1.3)):
        b.box("crate", (x - s / 2, y - s / 2, z + zz), (x + s / 2, y + s / 2, z + zz + s))
    b.box("olive", (3.0, -6.4, z), (4.4, -4.6, z + 0.9))
    b.cylinder("metal", (-6.0, -5.8, z + 4.0), 0.08, 8.0, segments=5)
    b.box("steel", (-6.6, -6.4, z), (-5.4, -5.2, z + 0.9))
    for k in range(4):
        b.box("olive", (-2.6 + k * 0.62, -13.2, 0.0), (-2.1 + k * 0.62, -12.5, 1.1))
    for x, y, s in ((-1.2, -14.8, 1.4), (0.4, -15.0, 1.2)):
        b.box("crate", (x - s / 2, y - s / 2, 0.0), (x + s / 2, y + s / 2, s))
    b.box("crate", (-17.6, 12.0, 0.0), (-16.0, 13.6, 1.4))


def build_shapes():
    parts = {k: Builder(SURFACES) for k in ("building", "intact", "wreck")}
    blockhouse(parts["building"])
    sandbags(parts["building"])
    tower(parts["building"], parts["intact"])
    medical(parts["intact"], parts["wreck"])
    clutter(parts["intact"])
    return parts


def emblems():
    """The faction's mark on the pilaster over the door."""
    x = HALF + 0.72
    return [flat_object("EMBLEM", [[(x, -1.2, 4.8), (x, 1.2, 4.8), (x, 1.2, 7.2), (x, -1.2, 7.2)]])]


def house_colours():
    """The player's colour: a band round the blockhouse's foot, the flag on the tower's mast."""
    quads = []
    for (ax, ay), (bx, by) in zip(PLAN, PLAN[1:] + PLAN[:1]):
        length = math.hypot(bx - ax, by - ay)
        nx, ny = (by - ay) / length * 0.04, -(bx - ax) / length * 0.04
        quads.append([(ax + nx, ay + ny, 1.25), (bx + nx, by + ny, 1.25), (bx + nx, by + ny, 1.75),
                      (ax + nx, ay + ny, 1.75)])
    band = flat_object("HOUSECOLOR01", quads)
    tx, ty = TOWER
    mx, my = tx - 0.8, ty - 0.8
    top = DECK + 9.8
    flag = [(mx, my + 0.1, top - 2.5), (mx, my + 4.0, top - 2.1), (mx, my + 4.0, top - 0.4), (mx, my + 0.1, top)]
    return [band, flat_object("HOUSECOLOR02", both_ways([flag]))]


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "outpost_paint.py")
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
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    for k, (nx, ny, along) in enumerate(SLITS):
        model.bone(f"FIREPOINT0{k + 1}", w3d.CHASSIS, on_face(nx, ny, along, SLIT_Z, 1.2))
    for bone, at in BONES.items():
        model.bone(bone, w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    objects = parts["objects"]
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(objects["building"]), texture=texture)
    model.mesh("INTACT" if version != "_E" else "WRECK", w3d.CHASSIS,
               **mesh_data(objects["intact" if version != "_E" else "wreck"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    if version != "_E":
        for obj in parts["emblems"]:
            model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["banners"]:
        if version == "_E" and obj.name == "HOUSECOLOR02":
            continue                           # the flag fell with the tower
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

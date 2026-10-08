"""The European Orbital Lance (the superweapon uplink), modelled in Blender and written as W3D models for the
game: one giant dish facing the sky on a tall tapered concrete tower (the tallest silhouette in the base), its
lance-shaped emitter held at the focus by three struts, a ring of five glowing capacitor and coolant pylons
round the tower's foot, and a sloped armoured control bunker joined to it by a conduit, on a round yard
shaped to the tower (after a concept painted in the game's style, ~/Projects/eu3d/ol/concept_a.png, reworked
to the faction's rule that every building has its own silhouette).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/orbital_lance.py

Painted the Command Centre's way, with the Joint Command's tools (joint_command.py): orbital_lance_paint.py
paints the tiles, Blender bakes them with the ambient occlusion into euol_building.tga, the painter makes
the damaged, wrecked and night versions. The models: EULANCE, _D, _E (wrecked: the dish, its struts and
the emitter are gone), each with a night version (_N, _DN, _EN).

The bones the superweapon's effects need (ParticleUplinkCannonUpdate), in every version:
    FX01..FX05    the tops of the five pylons: the outer nodes that flare while it charges, and where the
                  connector lasers start (OuterEffectBoneName FX, OuterEffectNumBones 5)
    FXCONNECTOR   the emitter at the dish's focus, where the connector lasers meet
    FXMAIN        the emitter's tip, where the beam leaves for orbit
The footprint is the USA's (128 long, 76 wide, centred).
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
from blender_kit import load_image, mesh_data, new_object, textured  # noqa: E402
import joint_command as jc  # noqa: E402
import w3d  # noqa: E402

DATA, BUILD = jc.DATA, jc.BUILD
NAME = "EULANCE"
PREFIX = "euol"
PAD_Z = jc.PAD_Z
FOOTPRINT = (-64.0, 64.0, -38.0, 38.0)
SURFACES = dict(jc.SURFACES)
SURFACES.update({"energy": (120, 214, 255), "navy": (44, 54, 96), "white": ("tile_dome", 12.0)})
GLOWING = ("glass",)

DISH = (-22.0, 0.0)                 # the tower's axis
TOWER_TOP = 40.0
VERTEX_Z = 48.5                     # the dish's centre, on its axis
AZIMUTH, ELEVATION = math.radians(-110.0), math.radians(72.0)
RADIUS, SAG, THICK = 17.0, 4.5, 0.9
FOCAL = RADIUS ** 2 / (4 * SAG)
N = Vector((math.cos(ELEVATION) * math.cos(AZIMUTH), math.cos(ELEVATION) * math.sin(AZIMUTH), math.sin(ELEVATION)))
U = Vector((-math.sin(AZIMUTH), math.cos(AZIMUTH), 0.0))          # the elevation axis, level
V = N.cross(U)
VERTEX = Vector((DISH[0], DISH[1], VERTEX_Z))
FOCUS = VERTEX + N * (FOCAL - 3.0)  # the emitter sits a little inside the focus
TIP = FOCUS + N * 10.0
PYLON_RADIUS = 21.0
PYLONS = [(DISH[0] + math.cos(math.radians(a)) * PYLON_RADIUS, DISH[1] + math.sin(math.radians(a)) * PYLON_RADIUS)
          for a in (18, 90, 162, 234, 306)]
PYLON_TOP = 15.0
BUNKER = [(14.0, -22.0), (22.0, -29.0), (52.0, -29.0), (59.0, -21.0), (59.0, 20.0), (52.0, 27.0), (22.0, 27.0), (14.0, 20.0)]
BUNKER_TOP = 9.0


def tower_radius(z):
    return 8.0 - 3.0 * (z - PAD_Z) / (TOWER_TOP - PAD_Z)


def dish_point(r, a, w):
    """A point of the dish: r from its axis, at angle a round it, w along the axis from the centre."""
    return VERTEX + U * (math.cos(a) * r) + V * (math.sin(a) * r) + N * w


def dish(b):
    """The dish, facing the sky: a closed shell, the concave face white, the back steel, the rim dark;
    the lance-shaped emitter on three struts at its focus."""
    rings, segments = 6, 24
    bm, idx = b.bm, b.index
    def ring_verts(back):
        out = []
        for i in range(1, rings + 1):
            r = RADIUS * i / rings
            w = SAG * (r / RADIUS) ** 2 - (THICK if back else 0.0)
            out.append([bm.verts.new(dish_point(r, 2 * math.pi * k / segments, w)) for k in range(segments)])
        return out
    front, back = ring_verts(False), ring_verts(True)
    centre_f, centre_b = bm.verts.new(VERTEX), bm.verts.new(VERTEX - N * THICK)
    faces = []
    for k in range(segments):
        j = (k + 1) % segments
        faces.append((bm.faces.new((centre_f, front[0][k], front[0][j])), "white"))
        faces.append((bm.faces.new((centre_b, back[0][j], back[0][k])), "trim"))
        for i in range(rings - 1):
            faces.append((bm.faces.new((front[i][k], front[i + 1][k], front[i + 1][j], front[i][j])), "white"))
            faces.append((bm.faces.new((back[i][k], back[i][j], back[i + 1][j], back[i + 1][k])), "trim"))
        faces.append((bm.faces.new((front[-1][k], back[-1][k], back[-1][j], front[-1][j])), "dark"))
    for face, surface in faces:
        face.material_index = idx[surface]
    for k in range(6):
        a = k * math.pi / 3
        b.rod("trim", dish_point(4.0, a, -THICK - 0.2), dish_point(RADIUS - 0.6, a, SAG - THICK - 0.3), 0.45, 4)
    b.rod("metal", VERTEX - N * 0.6, VERTEX - N * 4.2, 3.2, 12)
    for k in range(3):
        a = math.pi / 2 + k * 2 * math.pi / 3
        b.rod("metal", dish_point(RADIUS - 1.0, a, SAG - 0.3), FOCUS - N * 1.6, 0.5, 6)
    b.rod("trim", FOCUS - N * 3.4, FOCUS + N * 0.4, 2.6, 10, radius2=2.2)              # the emitter's housing
    b.rod("dark", FOCUS - N * 4.0, FOCUS - N * 3.4, 1.6, 10)
    for w in (0.9, 2.5, 4.1):
        b.rod("energy", FOCUS + N * w, FOCUS + N * (w + 0.7), 2.3, 12)                 # its glowing coils
    b.rod("metal", FOCUS + N * 0.4, FOCUS + N * 5.6, 1.5, 10)
    b.rod("trim", FOCUS + N * 5.6, FOCUS + N * 6.4, 1.9, 10)
    b.rod("metal", FOCUS + N * 6.4, TIP - N * 0.5, 1.5, 10, radius2=0.12)             # the lance
    b.sphere("energy", TIP, 0.8, 8, 6)


def tower(b):
    """The tall concrete tower: tapered octagon on buttresses, steel bands, a ladder cage, the head and yoke."""
    x, y = DISH
    rot = math.pi / 8
    b.cylinder("concrete", (x, y, PAD_Z + 1.0), 12.0, 2.0, segments=8, rotate=rot)
    b.cylinder("concrete", (x, y, (PAD_Z + TOWER_TOP) / 2), 8.0, TOWER_TOP - PAD_Z, segments=8, radius2=5.0, rotate=rot)
    for z in (12.0, 24.0, 34.0):
        r = tower_radius(z)
        b.cylinder("trim", (x, y, z), r + 0.25, 1.4, segments=8, radius2=r + 0.2, rotate=rot)
    for k in range(4):                                  # buttresses
        a = k * math.pi / 2 + math.pi / 4
        c, s = math.cos(a), math.sin(a)
        side = Vector((-s, c, 0)) * 0.9
        foot, root, high = Vector((x + c * 13.0, y + s * 13.0, PAD_Z)), Vector((x + c * 6.5, y + s * 6.5, PAD_Z)), \
            Vector((x + c * 6.2, y + s * 6.2, 15.0))
        b.loft("trim", [foot - side, foot + side, root + side, root - side],
               [foot - side + Vector((0, 0, 1.6)), foot + side + Vector((0, 0, 1.6)), high + side, high - side])
    b.box("dark", (x - 2.0, y - 8.3, PAD_Z), (x + 2.0, y - 7.4, 7.0))               # the door, facing the front
    b.box("door", (x - 1.6, y - 8.45, PAD_Z), (x + 1.6, y - 7.6, 6.6))
    for z in range(4, int(TOWER_TOP) - 2, 4):                                        # the ladder cage, at the back
        r = tower_radius(z)
        b.box("metal", (x - 0.9, y + r * 0.95, z), (x + 0.9, y + r * 0.95 + 1.6, z + 0.25))
    # The head: a collar, the turntable, a yoke to the dish's elevation axis.
    b.cylinder("trim", (x, y, TOWER_TOP + 1.0), 6.8, 2.0, segments=8, radius2=6.2, rotate=rot)
    b.cylinder("metal", (x, y, TOWER_TOP + 2.6), 6.0, 1.2, segments=16)
    b.cylinder("yellow", (x, y, TOWER_TOP + 2.0), 6.85, 0.3, segments=16)
    hinge = VERTEX - N * 3.6
    for side in (-1, 1):
        foot = Vector((x, y, TOWER_TOP + 3.2)) + U * (side * 5.0)
        top = hinge + U * (side * 5.0)
        b.loft("trim", [foot + U * -0.9 + V * -1.6, foot + U * 0.9 + V * -1.6, foot + U * 0.9 + V * 1.6, foot + U * -0.9 + V * 1.6],
               [top + U * -0.7 + V * -0.9, top + U * 0.7 + V * -0.9, top + U * 0.7 + V * 0.9, top + U * -0.7 + V * 0.9])
        b.rod("dark", hinge + U * (side * 4.2), hinge + U * (side * 6.0), 1.2, 10)
    b.sphere("red", (x + 4.0, y + 4.0, TOWER_TOP + 3.8), 0.4, 8, 6)


def pylon(b, x, y):
    """A capacitor and coolant pylon: a steel column with glowing coils between insulators, a cap; its FX bone
    on top; a cable to the tower."""
    b.cylinder("concrete", (x, y, PAD_Z + 0.7), 2.8, 1.4, segments=8, rotate=math.pi / 8)
    b.cylinder("metal", (x, y, (PAD_Z + 1.4 + 12.6) / 2), 1.3, 12.6 - PAD_Z - 1.4, segments=10)
    for z in (4.0, 6.6, 9.2):
        b.cylinder("dark", (x, y, z - 0.6), 1.9, 0.35, segments=10)
        b.cylinder("energy", (x, y, z + 0.3), 1.55, 1.3, segments=10)
    b.cylinder("trim", (x, y, 13.0), 1.8, 0.9, segments=10, radius2=1.0)
    b.sphere("energy", (x, y, PYLON_TOP - 0.7), 0.85, 8, 6)
    d = Vector((DISH[0] - x, DISH[1] - y, 0))
    start = Vector((x, y, PAD_Z + 0.4)) + d.normalized() * 2.6
    end = Vector((DISH[0], DISH[1], PAD_Z + 0.4)) - d.normalized() * 11.5
    b.rod("dark", start, end, 0.45, 4)


def bunker(b):
    """The control bunker: sloped steel-blue armour, a slit of dark windows, an armoured door, coolers on top."""
    jc.tier(b, "trim", BUNKER, PAD_Z, BUNKER_TOP, 4.0, cap_surface="deck")
    top = jc.inset(BUNKER, 4.0)
    b.loft("dark", [(x, y, BUNKER_TOP) for x, y in jc.inset(top, -0.3)], [(x, y, BUNKER_TOP + 0.6) for x, y in jc.inset(top, -0.3)])
    z0, z1 = 5.0, 6.6
    lo = jc.inset(jc.lerp_outline(BUNKER, top, (z0 - PAD_Z) / (BUNKER_TOP - PAD_Z)), -0.12)
    hi = jc.inset(jc.lerp_outline(BUNKER, top, (z1 - PAD_Z) / (BUNKER_TOP - PAD_Z)), -0.12)
    b.loft("glass", [(x, y, z0) for x, y in lo], [(x, y, z1) for x, y in hi], cap_surface="dark")
    # The door: a portal through the front slope.
    b.loft("trim", [(26.0, -31.5, PAD_Z), (34.0, -31.5, PAD_Z), (34.0, -24.0, PAD_Z), (26.0, -24.0, PAD_Z)],
           [(26.4, -30.4, 8.0), (33.6, -30.4, 8.0), (33.6, -24.0, 8.0), (26.4, -24.0, 8.0)], cap_surface="dark")
    b.box("dark", (27.6, -31.8, PAD_Z), (32.4, -31.2, 6.0))
    b.box("door", (28.0, -31.95, PAD_Z), (32.0, -31.4, 5.6))
    b.box("hazard", (26.0, -32.4, PAD_Z), (34.0, -31.6, PAD_Z + 0.15))
    # Coolers and two coolant tanks on the roof.
    for x in (22.5, 27.5):
        b.box("metal", (x - 2.0, -12.0, BUNKER_TOP + 0.2), (x + 2.0, 12.0, BUNKER_TOP + 3.0))
        b.box("grille", (x - 2.1, -11.4, BUNKER_TOP + 0.8), (x + 2.1, 11.4, BUNKER_TOP + 2.6))
    for y in (-8.0, 8.0):
        b.cylinder("metal", (50.0, y, BUNKER_TOP + 3.4), 3.2, 6.4, segments=12)
        b.cylinder("trim", (50.0, y, BUNKER_TOP + 6.9), 3.4, 0.6, segments=12)
        b.cylinder("energy", (50.0, y, BUNKER_TOP + 3.0), 3.25, 0.6, segments=12)
    b.box("dark", (47.0, -1.0, BUNKER_TOP + 6.2), (53.0, 1.0, BUNKER_TOP + 6.8))
    # The conduit from the bunker to the tower, on trestles.
    for yy in (-2.6, 2.6):
        b.cylinder("dark", ((14.0 + DISH[0] + 9.0) / 2, yy, 3.4), 0.6, 14.0 - DISH[0] - 9.0, axis="X", segments=6)
    for xx in (-8.0, -1.0, 6.0, 12.0):
        b.box("metal", (xx - 0.3, -3.6, PAD_Z), (xx + 0.3, 3.6, 2.9))


def clutter(b):
    """Floodlights, drums and crates."""
    for x, y in ((-52.0, -18.0), (-52.0, 18.0), (60.0, -30.0), (60.0, 28.0)):
        b.cylinder("metal", (x, y, PAD_Z + 7), 0.3, 14, segments=6)
        b.box("metal", (x - 1.2, y - 0.6, PAD_Z + 13.4), (x + 1.2, y + 0.6, PAD_Z + 14.6))
    for x, y in ((12.0, 28.0), (9.4, 28.0), (10.7, 30.2)):
        b.cylinder("trim", (x, y, PAD_Z + 1.8), 1.2, 3.6, segments=6)
    for x, y in ((8.0, -30.0), (8.0, -26.2)):
        b.box("crate", (x - 1.8, y - 1.8, PAD_Z), (x + 1.8, y + 1.8, PAD_Z + 3.4))


def hull(points):
    """The convex hull of points (x, y), counter-clockwise."""
    pts = sorted(set(points))
    def half(seq):
        out = []
        for p in seq:
            while len(out) >= 2 and ((out[-1][0] - out[-2][0]) * (p[1] - out[-2][1]) - (out[-1][1] - out[-2][1]) * (p[0] - out[-2][0])) <= 0:
                out.pop()
            out.append(p)
        return out
    lower, upper = half(pts), half(reversed(pts))
    return lower[:-1] + upper[:-1]


# The ground: a round yard round the tower joined to the bunker's apron.
PAD_OUTLINE = hull([(round(DISH[0] + math.cos(a) * 35.0, 3), round(DISH[1] + math.sin(a) * 35.0, 3))
                    for a in (k * math.pi / 10 for k in range(20))]
                   + [(8.0, -35.0), (56.0, -35.0), (63.0, -27.0), (63.0, 25.0), (56.0, 33.0), (8.0, 33.0)])


def pad():
    bm = bmesh.new()
    bottom = [bm.verts.new((x, y, 0.0)) for x, y in jc.inset(PAD_OUTLINE, -1.0)]
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


def emblems():
    """The faction's mark, large on the bunker's roof and on the tower's front face."""
    z = BUNKER_TOP + 0.75                               # on the roof's armour slab (0.6 thick)
    x, y = DISH
    def face(z):
        return y - (tower_radius(z) * math.cos(math.pi / 8) + 0.12)
    return [jc.decal("EMBLEM", [(33.0, -10.0, z), (45.0, -10.0, z), (45.0, 2.0, z), (33.0, 2.0, z)]),
            jc.decal("EMBLEM2", [(x - 2.6, face(17.0), 17.0), (x + 2.6, face(17.0), 17.0), (x + 2.6, face(22.2), 22.2),
                                 (x - 2.6, face(22.2), 22.2)])]


def house_colours():
    """The player's colour: a band round the tower, a stripe round the bunker's slope."""
    x, y = DISH
    objects = []
    bm = bmesh.new()
    z0, z1 = 28.0, 30.0
    bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=tower_radius(z0) + 0.12, radius2=tower_radius(z1) + 0.12,
                          depth=z1 - z0, matrix=Matrix.Translation((x, y, (z0 + z1) / 2)) @ Matrix.Rotation(math.pi / 8, 4, "Z"))
    objects.append(new_object("HOUSECOLOR01", bm))
    top = jc.inset(BUNKER, 4.0)
    z0, z1 = 2.4, 3.4
    lo = jc.lerp_outline(BUNKER, top, (z0 - PAD_Z) / (BUNKER_TOP - PAD_Z))
    hi = jc.lerp_outline(BUNKER, top, (z1 - PAD_Z) / (BUNKER_TOP - PAD_Z))
    objects.append(new_object("HOUSECOLOR02", jc.band(lo, hi, z0, z1, out=0.1)))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


BONES = [(f"FX{i + 1:02d}", (x, y, PYLON_TOP)) for i, (x, y) in enumerate(PYLONS)] + [
    ("FXCONNECTOR", tuple(FOCUS)), ("FXMAIN", tuple(TIP + N * 0.8))]


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "orbital_lance_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    for name in (f"{PREFIX}_emblem.tga",):
        shutil.copy(os.path.join(tiles, name), os.path.join(tex_dir, name))

    main, intact = jc.Builder(SURFACES), jc.Builder(SURFACES)
    tower(main)
    dish(intact)
    for x, y in PYLONS:
        pylon(main, x, y)
    bunker(main)
    clutter(main)
    building = jc.solid("BUILDING", main, tiles, surfaces=SURFACES)
    whole = jc.solid("INTACT", intact, tiles, surfaces=SURFACES)
    jc.unwrap([building, whole])
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    os.makedirs(bakes, exist_ok=True)
    ground = pad()
    jc.bake_all([building, whole], [], ground, bakes, top=72.0, glowing=GLOWING)
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, f"{PREFIX}_building.tga"))
    for obj in (building, whole):
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
    for name, at in BONES:                                 # markers, to see the bones in the .blend
        marker = bpy.data.objects.new(name, None)
        marker.location = at
        marker.empty_display_size = 1.5
        bpy.context.scene.collection.objects.link(marker)
    return dict(building=building, intact=whole, pad=ground, emblems=marks, banners=banners)


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    for name, at in BONES:
        model.bone(name, w3d.CHASSIS, at)
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **jc.FLAT)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **jc.FLAT)
    for obj in parts["banners"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, **jc.FLAT)
    jc.save_model(model)


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

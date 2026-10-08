"""The European Air Base (airfield), modelled in Blender and written as W3D models for the game: a long concrete
runway strip (both runways) dominating the ground, four low hardened aircraft shelters of angular reinforced
concrete with their blast doors slid open (two facing the runways' heads, two along the apron), a slender
control tower with a wide glazed cab, a low operations bunker, a helipad and a fuel bowser. Made the Command
Centre's way, with the Armour Works' helpers, in the shared palette with yellow only for hazard stripes.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/air_base.py

Six models: EUAIRF (intact), _D, _E (wrecked: no tower cab or mast, no roof machinery), each with a night
version (_N, _DN, _EN) with lit windows and shelters.

The footprint is the USA's (224 long, 148 wide, centred), its runways run towards +X (placed at -45 degrees,
towards the camera's lower right). ParkingPlaceBehavior (2 rows x 2 runways) finds its places by the bones
the USA's model has, at the same places and facing the same ways: RunwayNParkingM (where aircraft park),
RunwayNParkMHan (inside the shelters, where new aircraft appear), RunwayNPrepM (where they wait on the
runway), RunwayStartN / RunwayEndN, and HeliPark01 for helicopters. The INI must list them as
ExtraPublicBone (build_europe.py does).
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
import armour_works as aw  # noqa: E402
from armour_works import Builder, ring, railing  # noqa: E402
from blender_kit import load_image, mesh_data, new_object, textured  # noqa: E402
import w3d  # noqa: E402

DATA, BUILD = aw.DATA, aw.BUILD
NAME = "EUAIRF"
PREFIX = "euaf"
PAD_Z = 0.4                       # a thin apron: aircraft park on its bones at z 0
PAD_EXTENT = (-112.0, 112.0, -74.0, 74.0)
# (name, position, yaw in degrees): the USA's places (abarfrccmd.w3d).
BONES = [
    ("HELIPARK01", (66.7, 41.6, 0.0), -90),
    ("RUNWAY1PARK1HAN", (-21.1, 51.9, 0.0), -90), ("RUNWAY2PARK1HAN", (9.5, 51.9, 0.0), -90),
    ("RUNWAY1PARK2HAN", (-87.1, -49.0, 0.0), 0), ("RUNWAY2PARK2HAN", (-87.1, -13.1, 0.0), 0),
    ("RUNWAY1PARKING1", (-21.1, 22.7, 0.0), -90), ("RUNWAY2PARKING1", (9.5, 22.7, 0.0), -90),
    ("RUNWAY1PARKING2", (-56.4, -49.0, 0.0), 0), ("RUNWAY2PARKING2", (-56.4, -13.1, 0.0), 0),
    ("RUNWAY1PREP1", (9.5, -49.0, 0.0), 0), ("RUNWAY2PREP1", (9.5, -13.1, 0.0), 0),
    ("RUNWAY1PREP2", (-21.1, -49.0, 0.0), 0), ("RUNWAY2PREP2", (-21.1, -13.1, 0.0), 0),
    ("RUNWAYSTART1", (30.8, -49.0, 0.0), 0), ("RUNWAYSTART2", (30.8, -13.1, 0.0), 0),
    ("RUNWAYEND1", (110.1, -49.0, 0.0), 0), ("RUNWAYEND2", (110.1, -13.1, 0.0), 0),
]
PUBLIC_BONES = ["Runway1Parking1", "Runway1Parking2", "Runway2Parking1", "Runway2Parking2",
                "Runway1Park1Han", "Runway1Park2Han", "Runway2Park1Han", "Runway2Park2Han",
                "Runway1Prep1", "Runway1Prep2", "Runway2Prep1", "Runway2Prep2",
                "RunwayStart1", "RunwayStart2", "RunwayEnd1", "RunwayEnd2", "HeliPark01"]
SURFACES = dict(aw.SURFACES)


# --- shapes ----------------------------------------------------------------------------------------

class Frame:
    """A hangar's own frame: u out of its door, v across it, z up; turned so the door faces -Y or +X."""

    def __init__(self, cx, cy, facing):
        self.cx, self.cy, self.facing = cx, cy, facing

    def point(self, u, v, z=0.0):
        if self.facing == "-Y":
            return (self.cx + v, self.cy - u, z)
        return (self.cx + u, self.cy + v, z)

    def box(self, b, surface, a, c):
        b.box(surface, self.point(*a), self.point(*c))

    def extrude(self, b, surface, profile, u0, u1, cap_surface=None):
        """A profile (v, z) pushed along u from u0 to u1."""
        if self.facing == "-Y":
            profile = [(self.cx + v, z) for v, z in profile]
            b.extrude(surface, profile, self.cy - u1, self.cy - u0, axis="Y", cap_surface=cap_surface)
        else:
            profile = [(self.cy + v, z) for v, z in profile]
            b.extrude(surface, profile, self.cx + u0, self.cx + u1, axis="X", cap_surface=cap_surface)


def shelter(b, extra, frame, depth=34.0, half=14.5, top_half=9.5, height=10.5, wall=1.6):
    """A hardened aircraft shelter: angular reinforced concrete with sloped sides and a flat roof, a heavy
    door frame at u = depth / 2 with the blast doors slid aside, a dark inside. `extra` (intact-only) gets
    the roof's vents."""
    u0, u1 = -depth / 2, depth / 2
    # The sloped side walls, the roof slab, the back wall.
    for s in (-1, 1):
        side = [(s * half, PAD_Z), (s * (half - wall), PAD_Z), (s * (top_half - wall * 0.4), height - wall),
                (s * top_half, height)]
        frame.extrude(b, "concrete", side if s < 0 else list(reversed(side)), u0, u1 - 1.0)
    frame.box(b, "concrete", (u0, -top_half, height - wall), (u1 - 1.0, top_half, height))
    frame.extrude(b, "concrete", [(-half, PAD_Z), (half, PAD_Z), (top_half, height), (-top_half, height)], u0, u0 + 1.4)
    # The door frame: thick concrete jambs and lintel standing proud of the shell.
    opening, open_top = half - 3.2, height - 2.6
    for s in (-1, 1):
        jamb = [(s * (half + 0.6), PAD_Z), (s * opening, PAD_Z), (s * opening, open_top), (s * (top_half + 0.4), height + 0.6)]
        frame.extrude(b, "concrete", jamb if s < 0 else list(reversed(jamb)), u1 - 1.0, u1 + 1.2)
    frame.box(b, "concrete", (u1 - 1.0, -top_half - 0.4, open_top), (u1 + 1.2, top_half + 0.4, height + 0.6))
    frame.box(b, "trim", (u1 + 1.2, -opening, open_top - 0.6), (u1 + 1.5, opening, open_top))
    # The blast doors, slid aside on their rails, hazard stripes on their edges.
    for s in (-1, 1):
        frame.box(b, "girder", (u1 + 1.4, s * (opening - 0.5), PAD_Z), (u1 + 3.0, s * (half + 3.8), open_top - 0.4))
        frame.box(b, "hazard", (u1 + 3.0, s * (opening - 0.5), PAD_Z + 0.4), (u1 + 3.2, s * (opening + 0.9), open_top - 0.8))
        frame.box(b, "dark", (u1 + 1.2, s * (opening - 1.0), PAD_Z), (u1 + 3.4, s * (half + 4.2), PAD_Z + 0.4))
    # Inside: dark linings, lamps that light up at night.
    frame.box(b, "inside", (u0 + 1.4, -top_half + 0.4, height - wall - 0.3), (u1 - 1.0, top_half - 0.4, height - wall))
    frame.box(b, "inside", (u0 + 1.4, -half + wall + 1.0, PAD_Z), (u0 + 1.7, half - wall - 1.0, height - wall))
    for u in (u0 + 7, 0.0, u1 - 6):
        frame.box(b, "lamp", (u - 1.2, -2.0, height - wall - 0.8), (u + 1.2, 2.0, height - wall - 0.3))
    frame.box(b, "dark", (u0 + 1.4, -half + wall, PAD_Z + 0.05), (u1 - 1.0, half - wall, PAD_Z + 0.1))
    # On the roof: ventilators and a parapet lip.
    frame.box(b, "trim", (u0 - 0.3, -top_half - 0.3, height), (u1 - 1.0, top_half + 0.3, height + 0.5))
    for u in (u0 + 6.0, u0 + 14.0):
        extra.cylinder("metal", frame.point(u, 0.0, height + 1.4), 1.4, 1.8, segments=8)
        extra.cylinder("dark", frame.point(u, 0.0, height + 2.35), 1.1, 0.1, segments=8)


def tower(b, cab):
    """The control tower: a slender round concrete shaft, a wide glazed cab (intact-only), a mast."""
    cx, cy = -94.0, 54.0
    b.cylinder("trim", (cx, cy, PAD_Z + 1.0), 6.0, 2.0, segments=8, rotate=math.pi / 8)
    b.cylinder("concrete", (cx, cy, 16.0), 3.2, 31.0, segments=10)
    for z in (9.0, 17.0):
        b.box("glass", (cx + 2.9, cy - 0.7, z), (cx + 3.3, cy + 0.7, z + 2.4))
    b.cylinder("trim", (cx, cy, 31.8), 6.4, 1.6, segments=8, radius2=7.6, rotate=math.pi / 8)     # the cab's floor
    cab.cylinder("glass", (cx, cy, 35.2), 7.2, 5.2, segments=8, radius2=8.0, rotate=math.pi / 8)
    for k in range(8):
        a = math.pi / 8 + k * math.pi / 4 + math.pi / 8
        x, y = cx + math.cos(a) * 7.7, cy + math.sin(a) * 7.7
        cab.box("trim", (x - 0.35, y - 0.35, 32.6), (x + 0.35, y + 0.35, 37.8))
    cab.cylinder("girder", (cx, cy, 38.4), 8.8, 1.2, segments=8, radius2=8.0, rotate=math.pi / 8)
    cab.box("metal", (cx - 2.0, cy - 2.0, 39.0), (cx + 2.0, cy + 2.0, 40.6))
    cab.cylinder("metal", (cx, cy, 46.0), 0.25, 11.0, segments=6)
    cab.box("light", (cx + 2.4, cy - 2.2, 41.0), (cx + 2.8, cy + 2.2, 43.4))                    # a radar panel
    cab.add("red", lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=8, v_segments=6, radius=0.45,
                                                        matrix=aw.Matrix.Translation((cx, cy, 51.6))))


def operations(b, extra):
    """A low operations bunker by the tower: concrete with a steel roof, slit windows and a door."""
    x0, x1, y0, y1, top = -108.0, -70.0, 16.0, 40.0, 7.0
    b.extrude("concrete", [(y0 - 2.0, PAD_Z), (y1 + 2.0, PAD_Z), (y1, top), (y0, top)], x0, x1)
    b.box("girder", (x0 - 0.4, y0 - 0.4, top), (x1 + 0.4, y1 + 0.4, top + 0.8))
    for x in range(-104, -72, 8):
        b.box("glass", (x, y0 - 1.05, 4.4), (x + 4.0, y0 - 0.85, 5.6))
    b.box("dark", (x1, 25.0, PAD_Z), (x1 + 0.2, 30.0, 5.6))
    b.box("trim", (x1, 24.0, 5.6), (x1 + 2.4, 31.0, 6.2))
    extra.box("metal", (-100, 28, top + 0.8), (-92, 36, top + 3.2))
    extra.box("grille", (-92, 28.5, top + 1.1), (-91.9, 35.5, top + 2.9))
    extra.cylinder("metal", (-80.0, 24.0, top + 3.0), 0.2, 4.4, segments=6)
    extra.cylinder("light", (-80.0, 24.0, top + 5.0), 1.6, 0.4, segments=10)


def clutter(b):
    """A fuel bowser, crates, drums, runway lights, floodlights, a windsock."""
    x, y = 40.0, 64.0
    b.box("dark", (x - 9, y - 2.2, PAD_Z + 0.8), (x + 7, y + 2.2, PAD_Z + 1.8))
    b.box("trim", (x + 4, y - 2.4, PAD_Z + 1.4), (x + 8, y + 2.4, PAD_Z + 5.2))
    b.box("glass", (x + 8, y - 2.0, PAD_Z + 3.4), (x + 8.1, y + 2.0, PAD_Z + 4.8))
    b.cylinder("light", (x - 2.5, y, PAD_Z + 4.0), 2.2, 12.0, axis="X", segments=10)
    for wx in (x - 6, x - 2, x + 5.5):
        for wy in (y - 2.4, y + 2.4):
            b.cylinder("dark", (wx, wy, PAD_Z + 1.0), 1.0, 0.8, axis="Y", segments=8)
    for cx, cy, h in ((-56, 56, 3.6), (-56, 60.2, 3.6), (-51.8, 56, 3.6), (-56, 56, 7.2)):
        b.box("crate", (cx - 2, cy - 2, PAD_Z if h < 5 else PAD_Z + 3.6), (cx + 2, cy + 2, PAD_Z + 3.6 if h < 5 else PAD_Z + 7.2))
    for cx, cy in ((-48, 64), (-45.2, 64), (-46.6, 66.6)):
        b.cylinder("trim", (cx, cy, PAD_Z + 2.0), 1.3, 4.0, segments=6)
    for yy in (-65.0, 0.0):                            # runway edge lights, red at the far end
        for xx in range(-40, 111, 15):
            b.box("red" if xx > 100 else "light", (xx - 0.4, yy - 0.4, RUNWAY_Z), (xx + 0.4, yy + 0.4, RUNWAY_Z + 0.9))
    for cx, cy in ((108.0, 8.0), (-40.0, 72.0), (88.0, 62.0)):
        b.cylinder("metal", (cx, cy, PAD_Z + 8), 0.35, 16, segments=6)
        b.box("metal", (cx - 1.4, cy - 0.7, PAD_Z + 15.2), (cx + 1.4, cy + 0.7, PAD_Z + 16.6))
    b.cylinder("metal", (104.0, 12.0, PAD_Z + 6), 0.25, 12, segments=6)   # the windsock
    b.cylinder("red", (106.2, 12.0, PAD_Z + 11.2), 0.9, 4.0, axis="X", segments=8, radius2=0.5)


FRONT_SHELTERS = [Frame(-21.1, 52.0, "-Y"), Frame(9.5, 52.0, "-Y")]
SIDE_SHELTERS = [Frame(-88.0, -49.0, "+X"), Frame(-88.0, -13.1, "+X")]


def build_shapes():
    main, intact = Builder(SURFACES), Builder(SURFACES)
    for frame in FRONT_SHELTERS:
        shelter(main, intact, frame, depth=34.0, half=14.5)
    for frame in SIDE_SHELTERS:
        shelter(main, intact, frame, depth=38.0, half=15.0, top_half=10.0)
    tower(main, intact)
    operations(main, intact)
    clutter(main)
    return main, intact


# The ground: a long concrete runway strip (both runways) and an apron round the shelters, tower and helipad.
RUNWAY_Z = 0.55
RUNWAY_OUTLINE = [(-46.0, -68.0), (111.0, -68.0), (111.0, 3.0), (-46.0, 3.0)]
APRON_OUTLINE = [(-111.0, -68.0), (-46.0, -68.0), (-46.0, 3.0), (46.0, 3.0), (48.0, 22.0), (88.0, 22.0),
                 (88.0, 61.0), (52.0, 61.0), (52.0, 70.0), (30.0, 73.0), (-111.0, 73.0)]


def pad():
    """Both slabs as one flat mesh (two closed shells), painted as one picture."""
    parts = [aw.ground("PAD", APRON_OUTLINE, PAD_Z, PAD_EXTENT), aw.ground("RUNWAY", RUNWAY_OUTLINE, RUNWAY_Z, PAD_EXTENT)]
    bpy.ops.object.select_all(action="DESELECT")
    for obj in parts:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = parts[0]
    bpy.ops.object.join()
    return parts[0]


def emblems():
    """The faction's mark on the tower's shaft and the front shelters' lintels."""
    d = aw.decal
    marks = []
    r = 3.2 + 0.12
    marks.append(d("EMBLEM", [(-94.0 + r, 52.2, 21.0), (-94.0 + r, 55.8, 21.0), (-94.0 + r, 55.8, 24.6), (-94.0 + r, 52.2, 24.6)]))
    for i, cx in enumerate((-21.1, 9.5)):
        y = 52.0 - 17.0 - 1.2 - 0.12
        marks.append(d(f"EMBLEM{3 + i}", [(cx + 3.0, y, 8.4), (cx - 3.0, y, 8.4), (cx - 3.0, y, 10.9), (cx + 3.0, y, 10.9)]))
    return marks


def house_colours():
    """The player's colour: stripes on the shelters' lintels and a band round the tower's shaft."""
    objects = []
    bm = bmesh.new()
    for cx in (-21.1, 9.5):
        y = 52.0 - 17.0 - 1.2 - 0.12
        for x0, x1 in ((cx - 9.5, cx - 4.0), (cx + 4.0, cx + 9.5)):
            aw.double_sided(bm, [(x0, y, 9.2), (x1, y, 9.2), (x1, y, 10.2), (x0, y, 10.2)])
    for cy in (-49.0, -13.1):
        x = -88.0 + 19.0 + 1.2 + 0.12
        aw.double_sided(bm, [(x, cy - 10.0, 9.2), (x, cy + 10.0, 9.2), (x, cy + 10.0, 10.2), (x, cy - 10.0, 10.2)])
    objects.append(new_object("HOUSECOLOR01", bm))
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=10, radius1=3.35, radius2=3.35, depth=1.4,
                          matrix=aw.Matrix.Translation((-94.0, 54.0, 28.0)))
    objects.append(new_object("HOUSECOLOR02", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, f"{PREFIX}_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "air_base_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    shutil.copy(os.path.join(tiles, "emblem.tga"), os.path.join(tex_dir, f"{PREFIX}_emblem.tga"))

    main, intact = build_shapes()
    bakes = os.path.join(BUILD, f"{PREFIX}_bakes")
    ground = pad()
    objects = aw.bake_building((("BUILDING", main), ("INTACT", intact)), SURFACES, tiles, bakes, 40.0)
    aw.bake_pad(ground, bakes)
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
    return dict(building=objects[0], intact=objects[1], pad=ground, emblems=marks, banners=banners)


def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    for bone, at, yaw in BONES:
        model.bone(bone, w3d.CHASSIS, at, yaw=yaw)
    texture = f"{PREFIX}_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    flat = dict(shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture=f"{PREFIX}_pad_e.tga" if version == "_E" else f"{PREFIX}_pad.tga", **flat)
    for obj in parts["emblems"]:
        if version == "_E" and obj.name in ("EMBLEM3", "EMBLEM4"):
            continue
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=f"{PREFIX}_emblem.tga", **flat)
    for obj in parts["banners"]:
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

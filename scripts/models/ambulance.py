"""The European Field Ambulance: a protected four-wheeled vehicle in the manner of the Dingo 2 ambulance, its armoured
cab in front and a tall medical module behind, marked with red crosses on white, a decontamination spray on the
roof. Made like the Engineer Vehicle (engineer.py, whose shared helpers it uses).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/ambulance.py

Writes resources/macos/GameData/Art/W3D/EUAMB.w3d and EUAMB_D.w3d (really damaged), Art/TexturesHD/euamb.tga,
euamb_d.tga and euamb_tire.tga, and build/models/EUAMB.blend with previews.

Bones (the USA Ambulance's, which the game uses):
    TIRE01..04                     wheels: front left, front right, rear left, rear right (W3DTruckDraw turns them)
    TURRET, TURRETEL, WEAPONA01    the spray: turning, pitching, and where it sprays from
    EXITSTART01..03, EXITEND01..03 the ways out for the infantry inside: the back door and both sides
    SMOKE01..04                    smoke of the really damaged vehicle
    HOUSECOLOR01/02                stripes in the player's colour
"""
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import engineer as kit  # noqa: E402
from blender_kit import box, cylinder, load_image, smooth_by_angle, textured  # noqa: E402
from engineer_paint import Layout  # noqa: E402
import w3d  # noqa: E402

NAME = "EUAMB"
HULL_TEXTURE, DAMAGED_TEXTURE, TIRE_TEXTURE = "euamb.tga", "euamb_d.tga", "euamb_tire.tga"

WHEELS = {"TIRE01": (10.4, 5.6), "TIRE02": (10.4, -5.6), "TIRE03": (-7.1, 5.6), "TIRE04": (-7.1, -5.6)}
WHEEL_Z, WHEEL_RADIUS, WHEEL_WIDTH = 2.8, 2.8, 2.0
MODULE_TOP = 11.4
TURRET_AT = (-1.6, 0.0, MODULE_TOP)
TURRETEL_AT = (0.0, 0.0, 0.95)        # in the turret's space
NOZZLE = (3.0, 0.0, 0.0)              # in the pitching part's space

PARTS = {
    "body": (-12.2, 15.2, -6.9, 6.9, 0.0, 12.6),
    "turret": (-1.4, 3.4, -1.3, 1.3, -0.6, 1.6),
}
WEIGHTS = {"turret": 1.4}


def body():
    bm = bmesh.new()
    # The medical module: a tall box behind the cab, a little wider.
    box(bm, (-11.4, -5.0, 4.4), (1.6, 5.0, MODULE_TOP))
    # The cab, its windscreen leaning back, and the bonnet over the engine.
    kit.prism_xz(bm, [(1.4, 4.6), (9.4, 4.6), (9.6, 7.6), (8.0, 10.0), (1.4, 10.1)], -4.6, 4.6)
    kit.prism_xz(bm, [(9.2, 4.4), (14.0, 4.4), (14.6, 5.8), (13.8, 7.0), (9.4, 7.7)], -4.4, 4.4)
    kit.bevel_sharp(bm, 0.16)
    # V-shaped belly against mines, under it all.
    kit.prism_yz(bm, [(-2.6, 1.6), (2.6, 1.6), (4.3, 3.2), (4.3, 4.6), (-4.3, 4.6), (-4.3, 3.2)], -11.0, 12.8)
    # Wheel arches: a mudguard over each wheel, the front ones joined to the bonnet's sides.
    for (x, y) in WHEELS.values():
        side = 1 if y > 0 else -1
        y0, y1 = sorted((side * 4.3, side * 6.9))
        kit.prism_xz(bm, [(x - 3.4, 5.6), (x - 2.6, 6.3), (x + 2.6, 6.3), (x + 3.4, 5.6)], y0, y1)
    # Steps under the cab doors, a bull bar and headlights in front, a grille.
    for side in (1, -1):
        y0, y1 = sorted((side * 4.5, side * 5.6))
        box(bm, (3.0, y0, 3.8), (7.0, y1, 4.2))
        box(bm, (14.0, side * 3.4 - 0.6, 6.0), (14.7, side * 3.4 + 0.6, 6.7))
        box(bm, (9.6, side * 4.6, 8.6), (10.1, side * 5.4, 9.6))                  # mirrors
        kit.beam(bm, (14.9, side * 2.6, 3.6), (14.9, side * 2.6, 6.0), 0.18, 0.18)
    box(bm, (14.72, -2.8, 5.7), (15.08, 2.8, 6.06))
    box(bm, (14.7, -3.1, 4.0), (15.1, 3.1, 4.5))
    # The back: double doors with a step, a ladder to the roof, tail lights.
    box(bm, (-11.75, -3.4, 4.8), (-11.4, 3.4, 10.4))
    box(bm, (-12.1, -3.0, 3.6), (-11.0, 3.0, 4.1))
    for y in (-4.2, -3.8):
        kit.beam(bm, (-11.6, y, 5.0), (-11.6, y, MODULE_TOP + 0.4), 0.09, 0.09)
    # The roof: air conditioning, floodlights, a blue beacon on the cab, an antenna.
    box(bm, (-9.8, -2.6, MODULE_TOP), (-6.0, 2.6, MODULE_TOP + 1.0))
    for y in (4.2, -4.2):
        box(bm, (0.8, y - 0.45, MODULE_TOP), (1.5, y + 0.45, MODULE_TOP + 0.6))
    cylinder(bm, (7.0, 0.0, 10.35), 0.45, 0.5, segments=10)
    cylinder(bm, (-10.6, 4.4, MODULE_TOP + 1.8), 0.07, 3.6, segments=6)
    # Stowage on the module's sides: a stretcher locker each side.
    for side in (1, -1):
        y0, y1 = sorted((side * 5.0, side * 5.5))
        box(bm, (-10.6, y0, 4.8), (-6.4, y1, 6.6))
    return kit.finish("CHASSIS", bm)


def turret():
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.2), 1.1, 0.4, segments=14)
    kit.prism_xz(bm, [(-1.2, 0.4), (1.0, 0.4), (0.8, 1.5), (-1.0, 1.5)], -0.9, 0.9)
    base = kit.finish("TURRET", bm)
    bm = bmesh.new()
    cylinder(bm, (0.0, 0.0, 0.0), 0.45, 1.4, axis="Y", segments=10)       # trunnion
    cylinder(bm, (1.5, 0.0, 0.0), 0.28, 2.4, axis="X", segments=10)       # spray barrel
    cylinder(bm, (2.85, 0.0, 0.0), 0.4, 0.4, axis="X", segments=10)      # nozzle
    box(bm, (-0.5, 0.75, -0.35), (0.9, 1.3, 0.45))                         # camera
    pitch = kit.finish("TURRETEL", bm)
    return base, pitch


def wheels():
    return [kit.wheel(name, (x, y, WHEEL_Z), WHEEL_RADIUS, WHEEL_WIDTH) for name, (x, y) in WHEELS.items()]


def house_colour():
    return kit.side_panels("HOUSECOLOR01", "HOUSECOLOR02", -10.8, 0.9, 10.0, 10.7, 5.02)


BONES = [
    ("TURRET", "CHASSIS", TURRET_AT, 0.0),
    ("TURRETEL", "TURRET", TURRETEL_AT, 0.0),
    ("WEAPONA01", "TURRETEL", NOZZLE, 0.0),
    ("EXITSTART01", "CHASSIS", (-11.0, 0.0, 3.2), 180.0),
    ("EXITEND01", "CHASSIS", (-17.0, 0.0, 0.0), 180.0),
    ("EXITSTART02", "CHASSIS", (-1.7, 4.0, 3.2), 90.0),
    ("EXITEND02", "CHASSIS", (-1.7, 11.0, 0.0), 90.0),
    ("EXITSTART03", "CHASSIS", (-1.7, -4.0, 3.2), -90.0),
    ("EXITEND03", "CHASSIS", (-1.7, -11.0, 0.0), -90.0),
    ("SMOKE01", "CHASSIS", (12.0, 0.6, 7.6), 0.0),
    ("SMOKE02", "CHASSIS", (6.0, 4.0, 9.8), 0.0),
    ("SMOKE03", "CHASSIS", (-4.0, -3.0, MODULE_TOP), 0.0),
    ("SMOKE04", "CHASSIS", (-10.0, 1.0, MODULE_TOP), 0.0),
] + [(name, "CHASSIS", (x, y, WHEEL_Z), 0.0) for name, (x, y) in WHEELS.items()]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    layout = Layout(PARTS, 1024, WEIGHTS)
    print("layout scale", round(layout.scale, 2), "pixels per unit")
    hull, (base, pitch) = body(), turret()
    for obj, part in ((hull, "body"), (base, "turret"), (pitch, "turret")):
        smooth_by_angle(obj, 35)
        kit.panel_unwrap(obj, layout, part)
    tyres = wheels()
    stripes = house_colour()
    base.location = TURRET_AT
    pitch.location = tuple(a + b for a, b in zip(TURRET_AT, TURRETEL_AT))
    w3d.write_house_colour(kit.TEXTURES)
    kit.bake_and_paint(NAME, [(hull, "body"), (base, "turret"), (pitch, "turret")], layout, "ambulance_paint.py")
    for name, texture in ((NAME, HULL_TEXTURE), (NAME + "_D", DAMAGED_TEXTURE)):
        pieces = [("CHASSIS", "CHASSIS", hull, texture, "solid"), ("TURRET", "TURRET", base, texture, "solid"),
                  ("TURRETEL", "TURRETEL", pitch, texture, "solid")]
        pieces += [(t.name, t.name, t, TIRE_TEXTURE, "solid") for t in tyres]
        pieces += [(s.name, "CHASSIS", s, None, "house") for s in stripes]
        kit.write_model(name, pieces, BONES)
    image, tyre = load_image(os.path.join(kit.TEXTURES, HULL_TEXTURE)), load_image(os.path.join(kit.TEXTURES, TIRE_TEXTURE))
    for obj in (hull, base, pitch):
        textured(obj, image)
    for obj in tyres:
        textured(obj, tyre)
    kit.team_colour(stripes)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(kit.BUILD, NAME + ".blend"))
    kit.render_previews(os.path.join(kit.BUILD, NAME), distance=46.0, target=(1, 0, 5))

if __name__ == "__main__":
    main()

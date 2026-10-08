"""The European Recon Drone: a small tracked unmanned ground vehicle in the manner of the THeMIS, two track units
either side of a low payload deck, a telescopic sensor mast with a camera head and a radar panel, and a remote
weapon station whose light machine gun appears with the upgrade. Made like the Engineer Vehicle (engineer.py,
whose shared helpers it uses).

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/recon_drone.py

Writes resources/macos/GameData/Art/W3D/EUDRONE.w3d and EUDRONE_D.w3d (really damaged),
Art/TexturesHD/eudrn.tga, eudrn_d.tga and eudrn_tread.tga, and build/models/EUDRONE.blend with previews.

Bones and sub-objects (the USA Sentry Drone's, which the game uses):
    TREADSL01, TREADSR01   the tracks, scrolled by W3DTankDraw
    TURRET01               the weapon station, turning about Z
    TURRETUP01             the gun's recoil bone, carrying the gun TURRETUP09 (hidden until the upgrade)
    TURRETFX01, MUZZLE01   the muzzle and its flash (mesh TURRETFX01)
    SMOKE01..03            smoke of the really damaged vehicle
    HOUSECOLOR01/02        stripes in the player's colour
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

NAME = "EUDRONE"
HULL_TEXTURE, DAMAGED_TEXTURE, TREAD_TEXTURE = "eudrn.tga", "eudrn_d.tga", "eudrn_tread.tga"

TRACK_REAR, TRACK_FRONT, TRACK_RADIUS = (-6.3, 1.55), (6.5, 1.55), 1.55
TRACK_Y0, TRACK_Y1, TRACK_THICKNESS = 3.0, 5.7, 0.35
DECK_Z = 3.4
TURRET_AT = (1.2, 0.0, DECK_Z)
GUN_AT = (0.3, 0.0, 1.55)          # the recoil bone, in the turret's space
MUZZLE = (5.0, 0.0, 0.0)           # in the gun's space
MAST_X, MAST_TOP = -5.0, 13.0

PARTS = {
    "hull": (-8.2, 8.4, -6.1, 6.1, 0.0, DECK_Z + 1.0),
    "mast": (-6.6, -3.4, -1.6, 1.6, DECK_Z, MAST_TOP + 1.4),
    "turret": (-1.8, 2.2, -1.6, 1.6, 0.0, 2.4),
    "gun": (-1.0, 5.4, -0.9, 0.9, -0.6, 0.7),
}
WEIGHTS = {"turret": 1.5, "gun": 1.4, "mast": 1.0}


def hull():
    bm = bmesh.new()
    # The payload deck between the track units, its nose sloping down.
    kit.prism_xz(bm, [(-7.2, 1.6), (6.6, 1.6), (8.0, 2.6), (7.2, DECK_Z), (-7.4, DECK_Z), (-7.8, 2.4)], -3.0, 3.0)
    # The track units' bodies inside the tracks, and the side plates over the road wheels.
    for side in (1, -1):
        y0, y1 = sorted((side * 3.0, side * 5.7))
        kit.prism_xz(bm, [(-6.4, 0.9), (6.6, 0.9), (7.4, 1.6), (6.6, 2.65), (-6.4, 2.65), (-7.1, 1.6)], y0, y1)
        y0, y1 = sorted((side * 5.75, side * 6.0))
        kit.prism_xz(bm, [(-5.8, 0.75), (5.9, 0.75), (6.9, 1.7), (5.9, 2.7), (-5.8, 2.7), (-6.7, 1.7)], y0, y1)
    kit.bevel_sharp(bm, 0.12)
    # On the deck: stowage boxes, the battery pack, the mast's base; lights and cameras at the corners.
    box(bm, (-7.0, -2.8, DECK_Z), (-3.6, 2.8, DECK_Z + 0.9))
    box(bm, (3.2, -2.6, DECK_Z), (6.6, -0.8, DECK_Z + 0.6))
    box(bm, (3.2, 0.8, DECK_Z), (6.6, 2.6, DECK_Z + 0.6))
    for side in (1, -1):
        box(bm, (7.3, side * 4.4 - 0.5, 1.9), (7.8, side * 4.4 + 0.5, 2.4))
        box(bm, (-7.3, side * 4.4 - 0.4, 1.9), (-6.9, side * 4.4 + 0.4, 2.3))
        cylinder(bm, (7.6, side * 2.2, 3.0), 0.3, 0.5, axis="X", segments=8)
    cylinder(bm, (-2.8, 2.4, DECK_Z + 1.3), 0.06, 2.6, segments=6)
    return kit.finish("hull", bm)


def running_gear():
    bm = bmesh.new()
    for side in (1, -1):
        y = side * (TRACK_Y0 + TRACK_Y1) / 2
        for x in (-4.2, -1.4, 1.4, 4.2):
            cylinder(bm, (x, y, 1.1), 0.75, 2.1, axis="Y", segments=10)
        for (x, z) in (TRACK_REAR, TRACK_FRONT):
            cylinder(bm, (x, y, z), TRACK_RADIUS - TRACK_THICKNESS - 0.05, 2.1, axis="Y", segments=12)
    return kit.finish("running", bm)


def mast():
    """The telescopic sensor mast with its camera head and radar panel, fixed to the deck's back."""
    bm = bmesh.new()
    x = MAST_X
    box(bm, (x - 1.1, -1.1, DECK_Z + 0.9), (x + 1.1, 1.1, DECK_Z + 1.6))
    cylinder(bm, (x, 0, DECK_Z + 4.0), 0.36, 4.8, segments=10)
    cylinder(bm, (x, 0, DECK_Z + 8.2), 0.26, 3.8, segments=10)
    # The head: a gimbal with two lenses, a radar panel behind it.
    box(bm, (x - 0.7, -0.9, MAST_TOP - 0.2), (x + 0.9, 0.9, MAST_TOP + 0.9))
    cylinder(bm, (x + 1.05, -0.45, MAST_TOP + 0.35), 0.3, 0.3, axis="X", segments=10)
    cylinder(bm, (x + 1.05, 0.45, MAST_TOP + 0.35), 0.22, 0.3, axis="X", segments=10)
    box(bm, (x - 1.2, -1.5, MAST_TOP - 0.1), (x - 0.9, 1.5, MAST_TOP + 1.3))
    cylinder(bm, (x, 0, MAST_TOP + 1.25), 0.05, 0.8, segments=6)
    return kit.finish("mast", bm)


def turret():
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.2), 1.5, 0.4, segments=16)
    kit.prism_xz(bm, [(-1.6, 0.4), (1.5, 0.4), (1.9, 1.0), (1.4, 2.1), (-1.6, 2.1)], -1.0, 1.0)
    # The day/thermal sight on the left.
    box(bm, (-0.4, 1.0, 0.9), (1.4, 1.55, 2.0))
    return kit.finish("TURRET01", bm)


def gun():
    """The light machine gun on its cradle, in the recoil bone's space: hidden until the upgrade."""
    bm = bmesh.new()
    box(bm, (-0.9, -0.4, -0.3), (1.6, 0.4, 0.45))
    box(bm, (-0.6, -0.9, -0.5), (0.8, -0.4, 0.35))                  # ammunition box
    cylinder(bm, (3.2, 0, 0.05), 0.13, 3.4, axis="X", segments=8)
    cylinder(bm, (4.85, 0, 0.05), 0.2, 0.4, axis="X", segments=8)   # flash hider
    box(bm, (1.6, -0.2, -0.15), (2.4, 0.2, 0.25))
    return kit.finish("TURRETUP09", bm)


def build():
    layout = Layout(PARTS, 512, WEIGHTS)
    print("layout scale", round(layout.scale, 2), "pixels per unit")
    body, gear, sensor, top, mg = hull(), running_gear(), mast(), turret(), gun()
    solid = [(body, "hull"), (gear, "hull"), (sensor, "mast"), (top, "turret"), (mg, "gun")]
    for obj, part in solid:
        smooth_by_angle(obj, 35)
        kit.panel_unwrap(obj, layout, part)
    outline = kit.stadium(TRACK_REAR, TRACK_FRONT, TRACK_RADIUS)
    belts = [kit.track("TREADSL01", outline, TRACK_Y0, TRACK_Y1, TRACK_THICKNESS, link=0.9),
             kit.track("TREADSR01", outline, -TRACK_Y1, -TRACK_Y0, TRACK_THICKNESS, link=0.9)]
    for obj in belts:
        smooth_by_angle(obj, 50)
    stripes = kit.side_panels("HOUSECOLOR01", "HOUSECOLOR02", -4.8, 1.2, 1.3, 2.2, 6.03)
    flash = kit.muzzle_flash("TURRETFX01", (0, 0, 0), 1.8, 0.55)
    top.location = TURRET_AT
    mg.location = tuple(a + b for a, b in zip(TURRET_AT, GUN_AT))
    w3d.write_house_colour(kit.TEXTURES)
    kit.bake_and_paint(NAME, solid, layout, "recon_drone_paint.py")
    chassis = kit.join([body, gear, sensor], "CHASSIS")
    return dict(chassis=chassis, turret=top, gun=mg, belts=belts, stripes=stripes, flash=flash)


BONES = [
    ("TURRET01", "CHASSIS", TURRET_AT, 0.0),
    ("TURRETUP01", "TURRET01", GUN_AT, 0.0),
    ("TURRETFX01", "TURRETUP01", MUZZLE, 0.0),
    ("MUZZLE01", "TURRETUP01", MUZZLE, 0.0),
    ("SMOKE01", "CHASSIS", (-5.0, 3.0, DECK_Z + 1.0), 0.0),
    ("SMOKE02", "CHASSIS", (3.0, -2.0, DECK_Z + 0.6), 0.0),
    ("SMOKE03", "CHASSIS", (0.0, 4.4, 2.8), 0.0),
]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    p = build()
    for name, texture in ((NAME, HULL_TEXTURE), (NAME + "_D", DAMAGED_TEXTURE)):
        pieces = [("CHASSIS", "CHASSIS", p["chassis"], texture, "solid"),
                  ("TURRET01", "TURRET01", p["turret"], texture, "solid"),
                  ("TURRETUP09", "TURRETUP01", p["gun"], texture, "solid"),
                  ("TURRETFX01", "TURRETFX01", p["flash"], "EXTnkMzl01.tga", "flash")]
        pieces += [(b.name, "CHASSIS", b, TREAD_TEXTURE, "tread") for b in p["belts"]]
        pieces += [(s.name, "CHASSIS", s, None, "house") for s in p["stripes"]]
        kit.write_model(name, pieces, BONES)
    image = load_image(os.path.join(kit.TEXTURES, HULL_TEXTURE))
    for obj in (p["chassis"], p["turret"], p["gun"]):
        textured(obj, image)
    tread = load_image(os.path.join(kit.TEXTURES, TREAD_TEXTURE))
    for obj in p["belts"]:
        textured(obj, tread)
    kit.team_colour(p["stripes"])
    p["flash"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(kit.BUILD, NAME + ".blend"))
    kit.render_previews(os.path.join(kit.BUILD, NAME), distance=36.0, target=(0, 0, 4.5))


if __name__ == "__main__":
    main()

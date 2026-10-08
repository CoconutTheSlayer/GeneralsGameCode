"""The European Leclerc main battle tank, modelled in Blender from simple shapes and written as a W3D model for
the game with the tank parts of leopard.py: a low, boxy turret with flat armour blocks at the front and a long
bustle (its autoloader) reaching over the engine deck, the commander's tall drum sight, rows of smoke grenade
boxes, six road wheels, two fuel drums on the hull's back, and the point defence laser of the Paladin it
replaces on a mast at the back of the turret. Painted by leclerc_paint.py in a splinter camouflage.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/leclerc.py

Writes resources/macos/GameData/Art/W3D/EULEC.w3d and EULEC_D.w3d, Art/TexturesHD/eulec.tga, eulec_d.tga and
eulec_tread.tga, and build/models/EULEC.blend with previews next to it.

Bones, named like the Paladin's (AVPaladin): CHASSIS; TURRET01 (Turret = Turret01); BARREL01 (recoils);
TURRETMS01, TURRETFX01 (the muzzle and its flash); LASER (on the turret: where PaladinPointDefenseLaser's beam
starts, LaserBoneName = LASER); SMOKE01..05, TREADFX01..04, HEADLIGHT01/02; HOUSECOLOR01/02. The tracks are the
meshes TREADSL01 / TREADSR01, scrolled by W3DTankDraw.
"""
import os
import sys

import bmesh
import bpy

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_kit import box, cylinder, new_object  # noqa: E402
from leopard import (bevel_shell, finish, muzzle_flash, plan_prism, side_panels, side_prism, track,  # noqa: E402
                     wheels)
from leopard_layout import Layout  # noqa: E402

NAME = "EULEC"
TURRET_AT = (-0.5, 0.0, 6.0)
BARREL_AT = (6.2, 0.0, 1.35)        # in the turret's space
MUZZLE = (20.2, 0.0, 0.0)          # in the barrel's space
LASER_AT = (-7.7, 0.0, 4.2)        # in the turret's space: the lens of the laser on its mast
TRACK_Y = (5.2, 8.1)
TRACK_LOOP = [(11.6, 0.0), (-12.2, 0.0), (-13.6, 1.0), (-15.3, 2.4), (-15.2, 3.4), (-14.4, 4.1), (-12.8, 4.25),
              (12.8, 4.15), (14.3, 3.7), (14.8, 2.7), (14.1, 1.5), (12.9, 0.5)]
ROAD_WHEELS = [(-11.4 + k * 4.2, 1.4, 1.4) for k in range(6)] + [(13.3, 2.7, 1.05), (-14.0, 2.8, 1.15)]

LAYOUT = Layout({
    "size": 1024,
    "parts": {
        "hull": {"box": ((-17.8, 16.2), (-9.2, 9.2), (0.0, 6.6)), "scale": 18,
                 "islands": {"top": (4, 4), "side": (4, 342), "front": (4, 468), "back": (340, 468)},
                 "bottom": (4, 700, 4)},
        "turret": {"box": ((-13.8, 6.6), (-6.2, 6.2), (0.0, 5.4)), "scale": 17,
                   "islands": {"top": (640, 4), "side": (640, 222), "front": (640, 320), "back": (640, 418)},
                   "bottom": (150, 700, 4)},
        "barrel": {"box": ((-0.1, 20.4), (-0.7, 0.7), (-0.7, 0.7)), "scale": 20,
                   "islands": {"top": (4, 600), "side": (4, 632), "front": (420, 600), "back": (452, 600)},
                   "bottom": (240, 700, 4)},
    },
    "wheel": {"disc": (930, 630, 88), "tyre": (600, 700, 800, 730)},
})


def leclerc_hull():
    bm = bmesh.new()
    side_prism(bm, [(-15.3, 1.1), (12.0, 1.1), (15.3, 3.4), (15.5, 4.4), (-15.6, 4.4), (-15.8, 2.2)], -5.0, 5.0)
    # The deck over the tracks: a short steep glacis, flat all the way back.
    deck = side_prism(bm, [(-16.0, 4.3), (15.6, 4.3), (16.0, 4.8), (13.0, 6.0), (-15.4, 6.0), (-16.0, 5.5)],
                      -8.2, 8.2)
    bevel_shell(bm, deck, 0.18)
    for s in (1, -1):
        # Skirts: three thick armour blocks at the front, thin panels behind that leave the wheels free.
        side_prism(bm, [(-15.4, 2.9), (6.0, 2.9), (6.0, 5.9), (-15.4, 5.9)], s * 8.2, s * 8.55)
        side_prism(bm, [(6.0, 2.2), (14.6, 2.2), (15.6, 3.2), (15.6, 5.9), (6.0, 5.9)], s * 8.2, s * 9.1)
        box(bm, (14.2, s * 6.4, 5.4), (15.0, s * 7.6, 6.0))          # headlight boxes
        box(bm, (-16.0, s * 5.2, 4.0), (-14.8, s * 8.2, 4.4))        # mudguards over the sprockets
    # Engine deck: the big grille housing, the driver's hatch at the front left, periscopes.
    box(bm, (-14.8, -5.6, 6.0), (-6.5, 5.6, 6.25))
    cylinder(bm, (11.0, 3.0, 6.05), 0.8, 0.14, segments=10)
    box(bm, (12.0, 2.2, 6.0), (12.4, 3.8, 6.3))
    # Two fuel drums on brackets across the back: the Leclerc's signature.
    for y in (-3.0, 3.0):
        cylinder(bm, (-17.0, y, 5.2), 1.0, 4.2, axis="Y", segments=10)
        box(bm, (-16.4, y - 1.6, 4.3), (-15.8, y + 1.6, 4.6))
    box(bm, (-16.4, -5.5, 3.6), (-15.8, 5.5, 4.4))                    # the bracket's beam
    return new_object("CHASSIS", bm)


def leclerc_turret():
    bm = bmesh.new()
    # Low and boxy, as wide at the back as at the front: the bustle carries the autoloader.
    body = plan_prism(bm, [(-12.8, -4.6, 0.3, 2.6), (-12.0, -5.3, 0.0, 2.7), (3.8, -5.8, 0.0, 2.7),
                           (5.2, -4.6, 0.0, 2.7), (5.2, 4.6, 0.0, 2.7), (3.8, 5.8, 0.0, 2.7),
                           (-12.0, 5.3, 0.0, 2.7), (-12.8, 4.6, 0.3, 2.6)])
    bevel_shell(bm, body, 0.16)
    # Flat-faced armour blocks either side of the gun.
    for s in (1, -1):
        block = side_prism(bm, [(3.6, 0.2), (6.4, 0.2), (6.4, 2.5), (3.6, 2.75)], s * 1.4, s * 5.2)
        bevel_shell(bm, block, 0.1)
    box(bm, (5.0, -1.3, 0.5), (6.7, 1.3, 2.2))                        # mantlet
    # Commander's drum sight on its pedestal, the gunner's sight box, two hatches.
    cylinder(bm, (0.8, 3.4, 3.3), 0.55, 1.2, segments=8)
    cylinder(bm, (0.8, 3.4, 4.25), 1.0, 0.9, segments=10)
    box(bm, (1.6, 2.95, 3.95), (1.95, 3.85, 4.55))                    # its window
    box(bm, (1.5, -4.8, 2.65), (4.2, -3.2, 3.5))
    for x, y in ((-2.2, 2.6), (-2.2, -2.4)):
        cylinder(bm, (x, y, 2.75), 0.9, 0.14, segments=10)
    # Smoke grenade boxes along the sides, a stowage box at the back, antennas.
    for s in (1, -1):
        box(bm, (-6.6, s * 5.35, 1.6), (-2.4, s * 6.05, 2.65))
        cylinder(bm, (-11.6, s * 4.4, 4.4), 0.05, 3.4, segments=4)
    box(bm, (-13.7, -3.8, 0.6), (-12.6, 3.8, 2.6))
    # The point defence laser on its mast over the bustle.
    cylinder(bm, (-9.9, 0.0, 3.1), 0.45, 1.0, segments=8)
    housing = plan_prism(bm, [(-11.2, -1.0, 3.5, 4.6), (-10.6, -1.3, 3.4, 4.9), (-8.9, -1.3, 3.4, 4.9),
                              (-8.6, -0.9, 3.5, 4.7), (-8.6, 0.9, 3.5, 4.7), (-8.9, 1.3, 3.4, 4.9),
                              (-10.6, 1.3, 3.4, 4.9), (-11.2, 1.0, 3.5, 4.6)])
    bevel_shell(bm, housing, 0.1)
    cylinder(bm, (-8.2, 0.0, 4.2), 0.5, 0.9, axis="X", segments=8)  # the emitter
    return new_object("TURRET01", bm, TURRET_AT)


def leclerc_barrel():
    """The 120 mm L52 gun: a plain tube in its thermal sleeve, no fume extractor."""
    bm = bmesh.new()
    cylinder(bm, (1.0, 0, 0), 0.6, 2.0, axis="X", segments=8)
    cylinder(bm, (10.1, 0, 0), 0.4, 20.2, axis="X", segments=8)
    for x in (6.0, 12.5):
        cylinder(bm, (x, 0, 0), 0.47, 0.5, axis="X", segments=8)
    cylinder(bm, (19.6, 0, 0), 0.45, 1.2, axis="X", segments=8)      # the muzzle's thicker end
    box(bm, (18.6, -0.14, 0.38), (19.2, 0.14, 0.64))
    location = [TURRET_AT[i] + BARREL_AT[i] for i in range(3)]
    return new_object("BARREL01", bm, location)


def build():
    hull, top, gun = leclerc_hull(), leclerc_turret(), leclerc_barrel()
    gear = wheels("WHEELS", ROAD_WHEELS, 5.35, 7.95, LAYOUT, LAYOUT.spec["wheel"])
    treads = [track("TREADSL01", TRACK_LOOP, -TRACK_Y[1], -TRACK_Y[0]), track("TREADSR01", TRACK_LOOP, *TRACK_Y)]
    stripes = [
        (side_panels("HOUSECOLOR01", -11.5, -7.5, 0.8, 2.0, 5.45, TURRET_AT), "TURRET01"),
        (side_panels("HOUSECOLOR02", -14.5, -10.5, 4.3, 5.4, 8.57), "CHASSIS"),
    ]
    muzzle_at = [TURRET_AT[i] + BARREL_AT[i] + MUZZLE[i] for i in range(3)]
    parts = dict(chassis=hull, turret=top, barrel=gun, wheels=gear, treads=treads, stripes=stripes,
                 flash=muzzle_flash("TURRETFX01", muzzle_at), muzzle=MUZZLE, tread_texture="eulec_tread.tga",
                 turret_bone="TURRET01",
                 bones=[("LASER", "TURRET01", LASER_AT),
                        ("SMOKE01", "CHASSIS", (0.0, 0.0, 6.4)), ("SMOKE02", "CHASSIS", (10.0, 5.3, 6.1)),
                        ("SMOKE03", "TURRET01", (-0.1, -4.1, 2.7)), ("SMOKE04", "CHASSIS", (-9.5, -2.4, 6.3)),
                        ("SMOKE05", "TURRET01", (-12.0, 2.4, 2.7)),
                        ("TREADFX01", "CHASSIS", (-12.0, 6.6, 0.1)), ("TREADFX02", "CHASSIS", (-12.0, -6.6, 0.1)),
                        ("TREADFX03", "CHASSIS", (11.6, 6.6, 0.1)), ("TREADFX04", "CHASSIS", (11.6, -6.6, 0.1)),
                        ("HEADLIGHT01", "CHASSIS", (15.0, -7.0, 5.7)), ("HEADLIGHT02", "CHASSIS", (15.0, 7.0, 5.7))])
    return parts, [(hull, "hull"), (top, "turret"), (gun, "barrel")]


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts, panelled = build()
    finish(parts, NAME, "leclerc_paint.py", panelled, LAYOUT, previews_centre=(2, 0, 4))


if __name__ == "__main__":
    main()

"""The European Rafale, a canard delta strike fighter, built with the Typhoon's jet kit (typhoon.py). It
replaces the USA stealth fighter, so it wears a dark grey low-visibility scheme; unlike the Typhoon its
intakes are half-moons on the fuselage sides under close-coupled canards, its nose is long and slender with
a refuelling probe, and it carries a big centreline tank.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/rafale.py

Writes resources/macos/GameData/Art/W3D/EURAF.w3d and EURAF_D.w3d, Art/TexturesHD/euraf.tga and euraf_d.tga.
Bones as the stealth fighter's (AVSTEALTH): WEAPONA01/02 under the wings, ENGINE01/02, BURNERFX03/04,
WINGTIP01/02, SMOKE01/02, FLARE01..03, HOUSECOLOR01.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_kit import box, cylinder  # noqa: E402
from typhoon import Jet, build, clip_band, flat_panel, loft, mirrored, slab  # noqa: E402


class Rafale(Jet):
    name, texture = "EURAF", "euraf"
    paint_script = "rafale_paint.py"
    extent = ((-19.0, 21.0), (-13.0, 13.0), (-2.8, 10.0))
    scheme = dict(colours=[(92, 100, 112), (78, 86, 98)], pattern="soft", under=(108, 116, 126))
    belly_blend = -0.2

    FUSELAGE = [(20.6, 0, 0.75, 0.85, 2), (19.0, 0.3, 0.5, 1.1, 2), (16.0, 0.85, 0.05, 1.6, 2.2),
                (13.0, 1.2, -0.3, 1.95, 2.4), (9.0, 1.45, -0.55, 2.0, 2.6), (5.0, 1.7, -0.75, 1.95, 2.8),
                (0.0, 2.2, -0.8, 1.85, 3.2), (-8.0, 2.3, -0.7, 1.75, 3.2), (-12.5, 2.1, -0.55, 1.6, 3.0),
                (-14.8, 1.9, -0.45, 1.45, 2.8)]
    CANOPY = [(15.4, 0, 1.6, 1.7, 2), (14.0, 0.55, 1.4, 2.5, 2), (11.8, 0.82, 1.4, 3.05, 2),
              (9.4, 0.8, 1.45, 2.95, 2), (7.6, 0.55, 1.6, 2.5, 2), (6.0, 0, 1.9, 2.0, 2)]
    WING = [(3.6, 2.3), (-10.2, 12.2), (-12.6, 12.2), (-14.2, 2.3)]
    CANARD = [(6.4, 1.9), (3.9, 5.3), (2.7, 5.3), (3.0, 1.9)]
    FIN = [(-3.6, 1.4), (-11.4, 9.9), (-13.8, 9.9), (-14.8, 1.4)]
    NOZZLE_Y, NOZZLE_Z, NOZZLE_R = 1.0, 0.4, 0.95

    def wing_z(self, x, y):
        return -0.25

    def shapes(self, bm):
        loft(bm, self.FUSELAGE)
        loft(bm, self.CANOPY, segments=12)
        for side in (1, -1):
            # The half-moon intakes on the sides, under the canards.
            loft(bm, [(6.2, 0.95, -0.85, 0.95, 2.2), (4.0, 1.15, -0.9, 1.05, 2.4), (-2.0, 1.1, -0.85, 0.95, 2.4),
                      (-6.0, 0.4, -0.5, 0.5, 2)], segments=12, dy=side * 2.0)
            wing = self.WING if side > 0 else mirrored(self.WING)
            slab(bm, wing, 0.5, mid=self.wing_z)
            canard = self.CANARD if side > 0 else mirrored(self.CANARD)
            slab(bm, canard, 0.28, edge=0.08, mid=lambda x, y: 1.05 + (abs(y) - 1.9) * 0.08)
            cylinder(bm, (-15.9, side * self.NOZZLE_Y, self.NOZZLE_Z), self.NOZZLE_R, 2.4, axis="X", segments=14)
            # Missiles on the wingtip rails.
            cylinder(bm, (-10.4, side * 12.35, -0.25), 0.22, 5.4, axis="X", segments=8)
        slab(bm, self.FIN, 0.5, edge=0.1, plane="xz")
        # The fin's root fairing and the refuelling probe on the right of the nose.
        loft(bm, [(-2.0, 0, 1.7, 1.8, 2), (-5.0, 0.6, 1.4, 2.4, 2), (-13.5, 0.6, 1.4, 2.4, 2), (-15.2, 0, 1.6, 1.8, 2)],
             segments=10)
        cylinder(bm, (14.2, -0.95, 1.55), 0.13, 5.2, axis="X", segments=8)
        loft(bm, [(17.4, 0, 1.55, 1.56, 2), (16.8, 0.16, 1.4, 1.7, 2), (11.6, 0.16, 1.4, 1.7, 2)], segments=8,
             dy=-0.95)
        cylinder(bm, (21.0, 0, 0.8), 0.07, 1.2, axis="X", segments=6)

    def stores(self, bm):
        for side in (1, -1):
            box(bm, (-4.2, side * 5.2 - 0.12, -1.0), (-0.8, side * 5.2 + 0.12, -0.4))
            cylinder(bm, (-2.6, side * 5.2, -1.3), 0.3, 6.0, axis="X", segments=8)
        # The big centreline tank.
        box(bm, (-3.0, -0.15, -1.3), (2.5, 0.15, -0.7))
        loft(bm, [(5.5, 0, -1.9, -1.8, 2), (3.5, 0.75, -2.6, -1.1, 2), (-3.5, 0.8, -2.65, -1.05, 2),
                  (-6.5, 0, -1.9, -1.8, 2)], segments=12)

    def __init__(self):
        self.bones = {
            "WEAPONA01": (-0.5, 5.2, -1.6), "WEAPONA02": (-0.5, -5.2, -1.6),
            "ENGINE01": (-17.1, self.NOZZLE_Y, self.NOZZLE_Z), "ENGINE02": (-17.1, -self.NOZZLE_Y, self.NOZZLE_Z),
            "WINGTIP01": (-12.6, 12.4, -0.25), "WINGTIP02": (-12.6, -12.4, -0.25),
            "SMOKE01": (-4.0, -2.0, 1.6), "SMOKE02": (-6.5, 8.5, 0.0),
            "FLARE01": (-11.5, 1.9, -0.6), "FLARE02": (-11.5, 0.0, -0.8), "FLARE03": (-11.5, -1.9, -0.6),
        }
        self.burners = {"BURNERFX03": (-17.1 - 3.0, -self.NOZZLE_Y, self.NOZZLE_Z),
                        "BURNERFX04": (-17.1 - 3.0, self.NOZZLE_Y, self.NOZZLE_Z)}
        self.marks = self.make_marks()

    def house_colour(self, bm):
        # A thin band along each wing's trailing edge, and the fin's leading edge band: low-visibility.
        cu = sum(p[0] for p in self.WING) / 4
        cv = sum(p[1] for p in self.WING) / 4
        inner = [(cu + (u - cu) * 0.8, cv + (v - cv) * 0.8) for u, v in self.WING]
        band = clip_band(inner, 7.6, 8.6)
        for side in (1, -1):
            pts = [(x, side * y, self.wing_z(x, y) + 0.25 + 0.04) for x, y in band]
            flat_panel(bm, pts if side > 0 else list(reversed(pts)))
        cu = sum(p[0] for p in self.FIN) / 4
        cv = sum(p[1] for p in self.FIN) / 4
        inner = [(cu + (u - cu) * 0.8, cv + (v - cv) * 0.8) for u, v in self.FIN]
        band = clip_band(inner, 7.8, 8.5)
        for side in (1, -1):
            pts = [(x, side * (0.25 + 0.04), z) for x, z in band]
            flat_panel(bm, list(reversed(pts)) if side > 0 else pts)

    def make_marks(self):
        m = []
        top = [(15.0, 0.3, 2), (13.6, 0.72, 3), (11.4, 0.82, 3), (9.0, 0.72, 3), (7.2, 0.3, 2.5),
               (7.2, -0.3, 2.5), (9.0, -0.72, 3), (11.4, -0.82, 3), (13.6, -0.72, 3), (15.0, -0.3, 2)]
        m.append(dict(kind="glass", group="top", pts=top, frames=[(13.2, 0, 3)]))
        side = [(15.2, 0, 1.65), (13.4, 0, 2.7), (11.0, 0, 3.05), (8.4, 0, 2.7), (6.8, 0, 2.1), (7.6, 0, 1.65),
                (12.6, 0, 1.6)]
        m.append(dict(kind="glass", group="side", pts=side, frames=[(13.2, 0, 2)]))
        for s in (1, -1):
            # The intake mouths from the front: half moons against the fuselage.
            mouth = [(6.2, s * (2.0 + 0.95 * c), -0.0 + 0.9 * z) for c, z in
                     ((0.0, 1.0), (0.6, 0.85), (0.92, 0.4), (1.0, 0.0), (0.92, -0.4), (0.6, -0.85), (0.0, -1.0))]
            m.append(dict(kind="fill", group="front", pts=mouth, colour=(12, 12, 14)))
            m.append(dict(kind="nozzle", group="back", at=(-17.1, s * self.NOZZLE_Y, self.NOZZLE_Z), r=self.NOZZLE_R))
            m.append(dict(kind="soot", group="top", pts=[(-12.0, s * 0.3, 2), (-12.0, s * 2.0, 2), (-17.2, s * 2.0, 2),
                                                          (-17.2, s * 0.1, 2)], strength=150))
            m.append(dict(kind="fill", group="top", pts=[(-14.8, s * 0.1, 2), (-14.8, s * 1.95, 2),
                                                          (-17.1, s * 1.95, 2), (-17.1, s * 0.1, 2)],
                          colour=(70, 66, 62)))
            m.append(dict(kind="emblem", group="top", at=(-7.0, s * 6.6, 0), size=1.3, point="left"))
            # The intake tops from above: dark mouths' lips and a small yellow warning chevron.
            m.append(dict(kind="hazard", group="top", pts=[(5.6, s * 2.3, 1), (5.6, s * 2.8, 1), (4.6, s * 2.8, 1),
                                                            (4.6, s * 2.3, 1)]))
            m.append(dict(kind="panels", group="top", pairs=[
                ((-12.2, s * 3.0, 0), (-11.8, s * 11.8, 0)),
                ((-12.0, s * 7.2, 0), (-14.0, s * 7.2, 0)),
                ((0.0, s * 3.4, 0), (-6.5, s * 9.0, 0)),
                ((-3.0, s * 2.4, 0), (-3.0, s * 7.0, 0)),
            ]))
        m.append(dict(kind="emblem", group="side", at=(-11.0, 0, 5.0), size=1.2))
        m.append(dict(kind="fill", group="side", pts=[(-14.8, 0, 1.45), (-14.8, 0, -0.45), (-17.1, 0, -0.45),
                                                       (-17.1, 0, 1.45)], colour=(66, 62, 58)))
        m.append(dict(kind="panels", group="top", pairs=[((x, 2.2, 2), (x, -2.2, 2)) for x in (3.0, -3.0, -9.0)]))
        m.append(dict(kind="panels", group="side", pairs=[((x, 0, 1.8), (x, 0, -0.6)) for x in (15.5, 5.0, -3.0, -9.0)]
                      + [((16.0, 0, 0.8), (-14.5, 0, 0.8))]))
        # The radome: darker still, long and pointed.
        m.append(dict(kind="fill", group="top", pts=[(20.6, 0, 1), (17.5, 0.6, 1), (15.5, 0.85, 1), (15.5, -0.85, 1),
                                                      (17.5, -0.6, 1)], colour=(62, 66, 72), outline=(40, 44, 50)))
        m.append(dict(kind="fill", group="side", pts=[(20.6, 0, 0.8), (17.5, 0, 1.35), (15.5, 0, 1.6), (15.5, 0, 0.05),
                                                       (17.5, 0, 0.35)], colour=(62, 66, 72), outline=(40, 44, 50)))
        return m


if __name__ == "__main__":
    build(Rafale())

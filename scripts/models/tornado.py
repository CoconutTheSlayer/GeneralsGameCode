"""The European Tornado, a swing-wing strike bomber, built with the Typhoon's jet kit (typhoon.py): a long
two-seat fuselage with a tandem canopy, box intakes, shoulder wings swept half back from their fixed
gloves, big low tailplanes, a towering fin, and bombs under the belly. It replaces the USA Aurora, so it
wears a hard-edged splinter camouflage of blue-greys and slate, unlike the two fighters' smooth greys.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/tornado.py

Writes resources/macos/GameData/Art/W3D/EUTORN.w3d and EUTORN_D.w3d, Art/TexturesHD/eutor.tga and eutor_d.tga.
Bones as the Aurora's (AVAURORA): WEAPONA01 under the belly where the bombs fall from, ENGINE01/02,
BURNERFX03/04, WINGTIP01/02, SMOKE01/02, FLARE01..03, HOUSECOLOR01.
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from blender_kit import box, cylinder  # noqa: E402
from typhoon import Jet, build, clip_band, flat_panel, loft, mirrored, slab  # noqa: E402


class Tornado(Jet):
    name, texture = "EUTORN", "eutor"
    paint_script = "tornado_paint.py"
    extent = ((-20.5, 22.0), (-15.0, 15.0), (-3.2, 11.6))
    scheme = dict(colours=[(132, 142, 150), (94, 106, 120), (74, 84, 84)], pattern="splinter", patches=110,
                  under=(150, 156, 162))
    belly_blend = -0.6

    FUSELAGE = [(22.0, 0, 0.65, 0.75, 2), (20.4, 0.45, 0.25, 1.15, 2), (17.5, 1.15, -0.35, 1.75, 2.2),
                (14.0, 1.5, -0.7, 2.1, 2.6), (8.0, 1.75, -0.9, 2.2, 3.2), (2.0, 2.55, -1.0, 2.2, 4.0),
                (-6.0, 2.75, -0.95, 2.1, 4.0), (-13.0, 2.6, -0.8, 1.9, 3.6), (-17.2, 2.25, -0.6, 1.7, 3.0)]
    # Two seats in tandem under one long canopy, with a frame between them.
    CANOPY = [(16.6, 0, 1.95, 2.05, 2), (15.4, 0.6, 1.8, 2.85, 2), (13.0, 0.95, 1.8, 3.35, 2),
              (10.6, 0.95, 1.8, 3.2, 2), (8.4, 0.95, 1.8, 3.35, 2), (6.4, 0.8, 1.8, 3.0, 2), (4.6, 0, 2.1, 2.2, 2)]
    GLOVE = [(7.5, 2.3), (-0.5, 5.3), (-7.6, 5.3), (-7.6, 2.3)]
    WING = [(-0.6, 4.9), (-10.6, 14.6), (-13.0, 14.6), (-7.6, 4.9)]
    TAIL = [(-10.8, 2.2), (-16.4, 8.8), (-18.8, 8.8), (-18.2, 2.2)]
    FIN = [(-5.5, 1.8), (-14.2, 11.4), (-17.0, 11.4), (-18.0, 1.8)]
    NOZZLE_Y, NOZZLE_Z, NOZZLE_R = 1.2, 0.5, 1.0

    def wing_z(self, x, y):
        return 1.35 + (abs(y) - 4.9) * 0.012

    def tail_z(self, x, y):
        return 0.2 - (abs(y) - 2.2) * 0.07

    def shapes(self, bm):
        loft(bm, self.FUSELAGE)
        loft(bm, self.CANOPY, segments=12)
        for side in (1, -1):
            # The box intakes, raked forward at the top.
            loft(bm, [(6.6, 0.75, -0.75, 1.55, 8), (5.6, 0.95, -0.85, 1.65, 8), (-2.0, 1.0, -0.85, 1.6, 8),
                      (-7.0, 0.5, -0.6, 1.2, 6)], segments=12, dy=side * 2.6)
            glove = self.GLOVE if side > 0 else mirrored(self.GLOVE)
            slab(bm, glove, 0.6, mid=lambda x, y: 1.35)
            wing = self.WING if side > 0 else mirrored(self.WING)
            slab(bm, wing, 0.45, mid=self.wing_z)
            tail = self.TAIL if side > 0 else mirrored(self.TAIL)
            slab(bm, tail, 0.4, mid=self.tail_z)
            cylinder(bm, (-18.2, side * self.NOZZLE_Y, self.NOZZLE_Z), self.NOZZLE_R, 2.2, axis="X", segments=14)
        slab(bm, self.FIN, 0.6, edge=0.12, plane="xz")
        # The dorsal spine running into the fin, and the fin's tip fairing.
        loft(bm, [(4.0, 0, 1.95, 2.05, 2), (1.0, 0.85, 1.6, 2.75, 2), (-8.0, 0.85, 1.6, 2.75, 2), (-12.0, 0, 1.8, 2.2, 2)],
             segments=10)
        loft(bm, [(-13.4, 0, 11.1, 11.2, 2), (-14.6, 0.32, 10.9, 11.6, 2), (-17.2, 0.32, 10.9, 11.6, 2),
                  (-18.0, 0, 11.2, 11.3, 2)], segments=8)
        cylinder(bm, (22.4, 0, 0.7), 0.08, 1.2, axis="X", segments=6)

    def stores(self, bm):
        for side in (1, -1):
            # Big drop tanks under the wings, and an electronic pod on the glove.
            box(bm, (-6.0, side * 7.6 - 0.14, 0.0), (-2.4, side * 7.6 + 0.14, 1.2))
            loft(bm, [(1.5, 0, -0.75, -0.65, 2), (-0.5, 0.75, -1.45, 0.05, 2), (-7.5, 0.8, -1.5, 0.1, 2),
                      (-10.0, 0, -0.75, -0.65, 2)], segments=12, dy=side * 7.6)
            # Two bombs side by side under the belly.
            box(bm, (-1.5, side * 0.9 - 0.12, -1.3), (2.5, side * 0.9 + 0.12, -0.9))
            loft(bm, [(4.6, 0, -1.95, -1.85, 2), (3.4, 0.5, -2.4, -1.4, 2), (-1.8, 0.5, -2.4, -1.4, 2),
                      (-3.6, 0.25, -2.15, -1.65, 2)], segments=10, dy=side * 0.9)
            box(bm, (-4.2, side * 0.9 - 0.7, -1.94), (-2.8, side * 0.9 + 0.7, -1.86))  # tail fins
            box(bm, (-4.2, side * 0.9 - 0.04, -2.6), (-2.8, side * 0.9 + 0.04, -1.2))

    def __init__(self):
        self.bones = {
            "WEAPONA01": (1.0, 0.0, -2.6),
            "ENGINE01": (-19.3, self.NOZZLE_Y, self.NOZZLE_Z), "ENGINE02": (-19.3, -self.NOZZLE_Y, self.NOZZLE_Z),
            "WINGTIP01": (-12.0, 14.7, 1.45), "WINGTIP02": (-12.0, -14.7, 1.45),
            "SMOKE01": (3.0, -2.2, 2.0), "SMOKE02": (3.0, 2.2, 2.0),
            "FLARE01": (-14.0, 2.2, -0.6), "FLARE02": (-14.0, 0.0, -0.8), "FLARE03": (-14.0, -2.2, -0.6),
        }
        self.burners = {"BURNERFX03": (-19.3 - 3.0, -self.NOZZLE_Y, self.NOZZLE_Z),
                        "BURNERFX04": (-19.3 - 3.0, self.NOZZLE_Y, self.NOZZLE_Z)}
        self.marks = self.make_marks()

    def house_colour(self, bm):
        # The tailplanes' tips and a band high on the fin.
        cu = sum(p[0] for p in self.TAIL) / 4
        cv = sum(p[1] for p in self.TAIL) / 4
        inner = [(cu + (u - cu) * 0.8, cv + (v - cv) * 0.8) for u, v in self.TAIL]
        band = clip_band(inner, 6.2, 7.6)
        for side in (1, -1):
            pts = [(x, side * y, self.tail_z(x, y) + 0.2 + 0.04) for x, y in band]
            flat_panel(bm, pts if side > 0 else list(reversed(pts)))
        cu = sum(p[0] for p in self.FIN) / 4
        cv = sum(p[1] for p in self.FIN) / 4
        inner = [(cu + (u - cu) * 0.8, cv + (v - cv) * 0.8) for u, v in self.FIN]
        band = clip_band(inner, 8.4, 9.6)
        for side in (1, -1):
            pts = [(x, side * (0.3 + 0.04), z) for x, z in band]
            flat_panel(bm, list(reversed(pts)) if side > 0 else pts)

    def make_marks(self):
        m = []
        top = [(16.2, 0.35, 2), (14.6, 0.85, 3), (11.0, 0.95, 3), (6.8, 0.85, 3), (5.2, 0.35, 2.5),
               (5.2, -0.35, 2.5), (6.8, -0.85, 3), (11.0, -0.95, 3), (14.6, -0.85, 3), (16.2, -0.35, 2)]
        m.append(dict(kind="glass", group="top", pts=top, frames=[(14.4, 0, 3), (10.0, 0, 3)]))
        side = [(16.4, 0, 2.0), (14.4, 0, 3.05), (12.6, 0, 3.35), (10.4, 0, 3.15), (8.4, 0, 3.35), (6.0, 0, 2.9),
                (4.6, 0, 2.15), (6.0, 0, 1.85), (15.6, 0, 1.85)]
        m.append(dict(kind="glass", group="side", pts=side, frames=[(14.4, 0, 2), (10.0, 0, 2)]))
        for s in (1, -1):
            mouth = [(6.6, s * 1.9, 1.5), (6.6, s * 3.3, 1.5), (6.6, s * 3.3, -0.7), (6.6, s * 1.9, -0.7)]
            m.append(dict(kind="fill", group="front", pts=mouth, colour=(12, 12, 14)))
            m.append(dict(kind="hazard", group="top", pts=[(6.8, s * 1.9, 1), (6.8, s * 3.3, 1), (6.0, s * 3.3, 1),
                                                            (6.0, s * 1.9, 1)]))
            m.append(dict(kind="nozzle", group="back", at=(-19.3, s * self.NOZZLE_Y, self.NOZZLE_Z), r=self.NOZZLE_R))
            m.append(dict(kind="soot", group="top", pts=[(-14.0, s * 0.3, 2), (-14.0, s * 2.3, 2), (-19.4, s * 2.3, 2),
                                                          (-19.4, s * 0.1, 2)], strength=160))
            m.append(dict(kind="fill", group="top", pts=[(-17.2, s * 0.15, 2), (-17.2, s * 2.25, 2),
                                                          (-19.3, s * 2.25, 2), (-19.3, s * 0.15, 2)],
                          colour=(80, 76, 70)))
            m.append(dict(kind="emblem", group="top", at=(-6.5, s * 9.0, 0), size=1.5, point="left"))
            # The wing's flaps and slats, the glove's pivot.
            m.append(dict(kind="panels", group="top", pairs=[
                ((-2.2, s * 6.2, 0), (-10.4, s * 14.0, 0)),
                ((-6.6, s * 5.6, 0), (-12.0, s * 13.0, 0)),
                ((-4.0, s * 5.0, 0), (-4.0, s * 2.6, 0)),
                ((-14.4, s * 3.0, 0), (-17.6, s * 7.6, 0)),
            ]))
            m.append(dict(kind="rivets", group="top", pts=[(-4.0, s * 4.9, 0)]))
        m.append(dict(kind="emblem", group="side", at=(-12.6, 0, 5.2), size=1.5))
        m.append(dict(kind="hazard", group="side", pts=[(-13.6, 0, 11.4), (-13.0, 0, 10.9), (-17.4, 0, 10.9),
                                                         (-17.8, 0, 11.4)]))
        m.append(dict(kind="fill", group="side", pts=[(-17.2, 0, 1.7), (-17.2, 0, -0.6), (-19.3, 0, -0.6),
                                                       (-19.3, 0, 1.7)], colour=(74, 70, 66)))
        m.append(dict(kind="panels", group="top", pairs=[((x, 2.7, 2), (x, -2.7, 2)) for x in (3.0, -4.0, -11.0)]))
        m.append(dict(kind="panels", group="side", pairs=[((x, 0, 2.0), (x, 0, -0.8)) for x in (17.0, 3.0, -4.0, -11.0)]
                      + [((18.0, 0, 0.8), (-17.0, 0, 0.8))]))
        m.append(dict(kind="fill", group="top", pts=[(22.0, 0, 1), (19.5, 0.8, 1), (17.5, 1.15, 1), (17.5, -1.15, 1),
                                                      (19.5, -0.8, 1)], colour=(96, 102, 108), outline=(60, 66, 72)))
        m.append(dict(kind="fill", group="side", pts=[(22.0, 0, 0.7), (19.5, 0, 1.4), (17.5, 0, 1.75), (17.5, 0, -0.35),
                                                       (19.5, 0, 0.0)], colour=(96, 102, 108), outline=(60, 66, 72)))
        return m


if __name__ == "__main__":
    build(Tornado())

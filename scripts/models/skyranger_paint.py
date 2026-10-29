"""Paints the Skyranger's textures: the hull with the Boxer's painter (boxer_paint.py) but without its number
plates, so the two read as one family, and the turret and its fittings with the shared vehicle painter
(puls_paint.py). skyranger.py runs it with Python 3:

    python3 scripts/models/skyranger_paint.py build/models/EUSKYR_layout.json OUT_DIR [OCCLUSION.png]

It also reads EUSKYR_hull_layout.json and EUSKYR_hull_ao.png next to the layout.
"""
import json
import os
import sys

import numpy as np
from PIL import Image

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import boxer_paint  # noqa: E402
from puls_paint import LIT, SEAM, UP, emblem, glass, hazard, paint_all, rivets, seam, tube_face  # noqa: E402

LASERS = [(-13.0, 3.8), (-13.0, -3.8)]  # skyranger.py's point defence emitters


def no_text(*_args, **_kwargs):
    """No numbers or letters on European vehicles."""


def blank_plate(draw, centre):
    x, y = centre
    draw.rectangle([x - 16 * UP, y - 4 * UP, x + 16 * UP, y + 4 * UP], fill=(52, 58, 66), outline=SEAM, width=UP)


def radar_face(draw, box):
    """An AESA panel: dark tiles in a grid."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(46, 52, 60), outline=SEAM, width=UP)
    nx, ny = 6, 4
    for i in range(1, nx):
        x = x0 + (x1 - x0) * i / nx
        draw.line([(x, y0), (x, y1)], fill=(80, 90, 100), width=UP)
    for j in range(1, ny):
        y = y0 + (y1 - y0) * j / ny
        draw.line([(x0, y), (x1, y)], fill=(80, 90, 100), width=UP)
    draw.line([(x0, y0), (x1, y0)], fill=LIT, width=UP)


S = 1.3  # skyranger.py's turret scale


class Scaled:
    """The canvas with the turret's and gun's points given at their design size."""

    def __init__(self, c):
        self.c, self.layout = c, c.layout

    def P(self, part, grp, co):
        k = S if part in ("turret", "gun") else 1.0
        return self.c.P(part, grp, tuple(v * k for v in co))

    def rect(self, part, grp, a, b):
        k = S if part in ("turret", "gun") else 1.0
        return self.c.rect(part, grp, tuple(v * k for v in a), tuple(v * k for v in b))


def details(c, draw, rng):
    c = Scaled(c)
    # The search radar on its post: seen from the back and the front, a tiled array.
    for grp in ("front", "back"):
        radar_face(draw, c.rect("turret", grp, (0, -2.0, 5.55), (0, 2.0, 3.15)))
    # The cheek panels.
    radar_face(draw, c.rect("turret", "side", (1.0, 0, 1.45), (2.8, 0, 0.5)))
    # Turret roof: hatch outline, rivets, an emblem; sides: a hazard tab by the gun port.
    a = c.rect("turret", "top", (-1.8, 1.6, 0), (0.4, -0.6, 0))
    draw.rectangle(a, outline=SEAM, width=2 * UP)
    rivets(draw, [c.P("turret", "top", (x, y, 0)) for x in np.arange(-3.4, 2.8, 0.7) for y in (2.3, -2.3)], 0.35)
    emblem(draw, c.P("turret", "top", (-1.0, -1.6, 0)), 9)
    emblem(draw, c.P("turret", "side", (-2.0, 0, 2.1)), 7)
    seam(draw, c.P("turret", "side", (-3.7, 0, 1.5)), c.P("turret", "side", (3.6, 0, 1.5)))
    # The sight's glass.
    sx, sy = c.P("turret", "front", (0, 1.4, 3.0))
    draw.ellipse([sx - 5 * UP, sy - 5 * UP, sx + 5 * UP, sy + 5 * UP], fill=(30, 60, 90), outline=SEAM, width=UP)
    draw.ellipse([sx - 2.5 * UP, sy - 3 * UP, sx, sy - UP], fill=(150, 200, 230))
    glass(draw, [c.P("turret", "front", (0, 1.0, 3.3)), c.P("turret", "front", (0, 1.8, 3.3)),
                 c.P("turret", "front", (0, 1.8, 2.75)), c.P("turret", "front", (0, 1.0, 2.75))])
    # Gun: dark barrel, the pod's four tubes and a yellow band, a hazard tab on the mantlet.
    tube_face(draw, c.rect("gun", "front", (0, 2.95, 0.65), (0, 4.25, -0.65)), 2, 2)
    hazard(draw, c.rect("gun", "side", (1.2, 0, 0.6), (1.8, 0, -0.6)), 3)
    a = c.rect("gun", "side", (2.2, 0, 0.3), (7.4, 0, -0.3))
    draw.rectangle(a, fill=(54, 58, 64))
    a = c.rect("gun", "top", (2.2, -0.6, 0), (7.4, -1.2, 0))
    draw.rectangle(a, fill=(58, 62, 68))
    # Designator: its window; point defence emitters: a dark lens.
    glass(draw, [c.P("designator", "front", (0, -2.9, 9.5)), c.P("designator", "front", (0, -2.1, 9.5)),
                 c.P("designator", "front", (0, -2.1, 8.9)), c.P("designator", "front", (0, -2.9, 8.9))])
    for x, y in LASERS:
        px, py = c.P("pd", "top", (x, y, 0))
        r = 0.25 * c.layout.bounds["pd"][1] * UP
        draw.ellipse([px - r, py - r, px + r, py + r], fill=(60, 20, 20), outline=SEAM, width=UP)


def main():
    layout, out = sys.argv[1], sys.argv[2]
    occlusion = sys.argv[3] if len(sys.argv) > 3 else None
    paint_all(layout, out, occlusion, details, ("eusky.tga", "eusky_d.tga"), small=("pd", "designator"))
    # The hull: the Boxer's paint, plates blank.
    boxer_paint.text = no_text
    boxer_paint.plate = blank_plate
    hull_layout = json.load(open(layout.replace("_layout.json", "_hull_layout.json")))
    ao_path = layout.replace("_layout.json", "_hull_ao.png")
    ao = Image.open(ao_path) if os.path.exists(ao_path) else None
    boxer_paint.paint_hull(hull_layout, occlusion=ao, seed=23).save(os.path.join(out, "eusky_hull.tga"))
    boxer_paint.paint_hull(hull_layout, damaged=True, occlusion=ao, seed=23).save(os.path.join(out, "eusky_hull_d.tga"))
    print("painted")


if __name__ == "__main__":
    main()

"""Paints the Wiesel EW's textures with the shared vehicle painter (puls_paint.py). wiesel.py runs it with
Python 3:

    python3 scripts/models/wiesel_paint.py build/models/EUWIES_layout.json OUT_DIR [OCCLUSION.png]
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from puls_paint import (SEAM, UP, emblem, glass, grille, hatch, hazard, paint_all, paint_tread, rivets,  # noqa: E402
                        seam, wheel_disc)

WHEELS = [(x, 1.45, 1.25) for x in (-6.6, -3.0, 0.6, 4.2)] + [(8.9, 2.3, 1.0), (-8.9, 2.0, 0.95)]  # wiesel.py's


def details(c, draw, rng):
    # Hull: the driver's hatch and vision blocks, the engine grille, headlights, rivets along the fenders.
    hatch(draw, c.P("hull", "top", (4.4, 2.6, 0)), 0.9 * c.layout.bounds["hull"][1] * UP)
    grille(draw, c.rect("hull", "top", (6.6, -4.2, 0), (8.6, -1.4, 0)), slats=7)
    grille(draw, c.rect("hull", "front", (0, -2.6, 3.6), (0, 2.6, 2.4)), slats=5, vertical=False)
    for y in (-3.9, 3.9):
        a, b = c.P("hull", "front", (0, y - 0.5, 4.2)), c.P("hull", "front", (0, y + 0.5, 3.8))
        draw.rectangle([min(a[0], b[0]), a[1], max(a[0], b[0]), b[1]], fill=(230, 226, 200), outline=SEAM, width=UP)
    for y in (4.5, -4.5):
        rivets(draw, [c.P("hull", "top", (x, y, 0)) for x in np.arange(-9.5, 6.0, 1.2)])
    seam(draw, c.P("hull", "top", (6.0, 4.5, 0)), c.P("hull", "top", (6.0, -4.5, 0)))
    emblem(draw, c.P("hull", "side", (2.0, 0, 4.5)), 9)
    hazard(draw, c.rect("hull", "back", (0, -4.5, 5.4), (0, -2.8, 4.9)))
    hazard(draw, c.rect("hull", "back", (0, 2.8, 5.4), (0, 4.5, 4.9)))
    for y in (-2.0, 2.0):
        a, b = c.P("hull", "back", (0, y - 0.4, 4.6)), c.P("hull", "back", (0, y + 0.4, 4.1))
        draw.rectangle([min(a[0], b[0]), a[1], max(a[0], b[0]), b[1]], fill=(170, 30, 25), outline=SEAM, width=UP)
    # The electronic warfare box: equipment doors with handles, a cooling grille, a window at the front.
    for x0, x1 in ((-8.4, -5.8), (-5.6, -3.0)):
        a = c.rect("ew", "side", (x0, 0, 7.2), (x1, 0, 6.0))
        draw.rectangle(a, outline=SEAM, width=2 * UP)
        hx, hy = c.P("ew", "side", (x1 - 0.4, 0, 6.6))
        draw.rectangle([hx - UP, hy - 3 * UP, hx + UP, hy + 3 * UP], fill=(190, 196, 200))
    grille(draw, c.rect("ew", "top", (-9.2, 3.8, 0), (-7.0, 1.6, 0)), slats=6)
    grille(draw, c.rect("ew", "top", (-9.2, -1.6, 0), (-7.0, -3.8, 0)), slats=6)
    emblem(draw, c.P("ew", "top", (-2.8, 2.6, 0)), 10)
    glass(draw, [c.P("ew", "front", (0, -3.0, 7.4)), c.P("ew", "front", (0, 3.0, 7.4)),
                 c.P("ew", "front", (0, 3.0, 6.7)), c.P("ew", "front", (0, -3.0, 6.7))])
    rivets(draw, [c.P("ew", "side", (x, 0, 7.45)) for x in np.arange(-9.3, -1.2, 0.9)], 0.4)
    # Mast: yellow and black bands at the collars; the jammer panels' dipoles; the dish's face.
    for z in (11.8, 14.4):
        hazard(draw, c.rect("mast", "side", (-5.8, 0, z + 0.05), (-4.6, 0, z - 0.25)), 3)
        hazard(draw, c.rect("mast", "front", (0, -0.6, z + 0.05), (0, 0.6, z - 0.25)), 3)
    for side in (1, -1):
        for grp in ("side",):
            x0, y0, x1, y1 = c.rect("mast", grp, (-5.7, 0, 17.6), (-4.7, 0, 15.0))
            draw.rectangle([x0, y0, x1, y1], fill=(60, 66, 74), outline=SEAM, width=UP)
            for k in range(7):
                yy = y0 + (y1 - y0) * (k + 0.5) / 7
                w = (x1 - x0) * (0.25 + 0.6 * k / 7)
                draw.line([((x0 + x1) / 2 - w / 2, yy), ((x0 + x1) / 2 + w / 2, yy)], fill=(200, 205, 210), width=UP)
            draw.line([((x0 + x1) / 2, y0), ((x0 + x1) / 2, y1)], fill=(30, 32, 36), width=UP)
    cx, cy = c.P("mast", "front", (0, 0, 16.25))
    r = 1.35 * c.layout.bounds["mast"][1] * UP
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(196, 202, 206), outline=SEAM, width=UP)
    for k in (0.75, 0.5):
        draw.ellipse([cx - r * k, cy - r * k, cx + r * k, cy + r * k], outline=(150, 156, 160), width=UP)
    draw.ellipse([cx - r * 0.18, cy - r * 0.18, cx + r * 0.18, cy + r * 0.18], fill=(225, 185, 40))
    # Running gear.
    for x, z, rr in WHEELS:
        wheel_disc(draw, c.P("track", "side", (x, 0, z)), rr * c.layout.bounds["track"][1] * UP)


def main():
    layout, out = sys.argv[1], sys.argv[2]
    occlusion = sys.argv[3] if len(sys.argv) > 3 else None
    paint_all(layout, out, occlusion, details, ("euwie.tga", "euwie_d.tga"), muddy=("track", "hull"), seed=31,
              small=("mast",))
    paint_tread(seed=9).save(os.path.join(out, "euwie_tread.tga"))
    print("painted")


if __name__ == "__main__":
    main()

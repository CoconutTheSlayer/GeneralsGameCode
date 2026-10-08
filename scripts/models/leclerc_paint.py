"""Paints the Leclerc's textures with the painter of leopard_paint.py, in a splinter camouflage (hard, angular
shards rather than the Leopard's rounded patches) and with the Leclerc's own markings.

    python3 scripts/models/leclerc_paint.py build/models/EULEC_layout.json OUT_DIR [OCCLUSION.png]
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from leopard_paint import (GLASS, SEAM, UP, YELLOW, Painter, emblem, grille, hatch, hazard, light,  # noqa: E402
                           paint_tread, rivets, seam)

SPLINTER = [(176, 186, 194), (96, 110, 126), (204, 210, 214)]


def splinter(w, rng):
    """Long angular shards over the light base, as a splinter scheme is painted."""
    img = Image.new("RGB", (w, w), SPLINTER[0])
    draw = ImageDraw.Draw(img)
    for colour, count in ((SPLINTER[1], 110), (SPLINTER[2], 40)):
        for _ in range(count):
            cx, cy = rng.uniform(0, w), rng.uniform(0, w)
            a = rng.uniform(0, math.pi)
            length, width = rng.uniform(0.06, 0.16) * w, rng.uniform(0.015, 0.045) * w
            dx, dy = math.cos(a), math.sin(a)
            pts = [(cx - dx * length, cy - dy * length),
                   (cx - dy * width + dx * rng.uniform(-0.3, 0.3) * length, cy + dx * width + dy * rng.uniform(-0.3, 0.3) * length),
                   (cx + dx * length, cy + dy * length),
                   (cx + dy * width * rng.uniform(0.5, 1.5), cy - dx * width * rng.uniform(0.5, 1.5))]
            draw.polygon(pts, fill=colour)
    return np.asarray(img, float)


def leclerc_details(p, draw, rng):
    top = lambda x, y, z=6.0: p.P("hull", "top", (x, y, z))  # noqa: E731
    side = lambda x, z: p.P("hull", "side", (x, 8.6, z))  # noqa: E731

    # Engine deck: one big grille field in four, cross seams, the driver's hatch, the glacis seam.
    for x0, x1 in ((-14.5, -10.8), (-10.5, -6.8)):
        for y0, y1 in ((-5.3, -0.3), (0.3, 5.3)):
            grille(draw, p.box("hull", "top", (x0, y0, 6.25), (x1, y1, 6.25)), slats=9, vertical=False)
    for x in (-4.0, 3.5, 9.5):
        seam(draw, top(x, 8.0), top(x, -8.0))
        rivets(draw, [top(x - 0.4, y) for y in np.arange(-7.6, 7.8, 1.4)])
    for y in (5.6, -5.6):
        seam(draw, top(-15.0, y), top(12.8, y), lit=False)
    hatch(draw, top(11.0, 3.0), 0.8 * 18 * UP)
    seam(draw, top(13.0, 8.2), top(13.0, -8.2))
    for y in (7.0, -7.0):
        light(draw, p.box("hull", "top", (14.4, y - 0.4, 6.0), (14.9, y + 0.4, 6.0)))
    # Fuel drums: darker paint, with their bands and filler caps.
    for y in (-3.0, 3.0):
        r = p.box("hull", "top", (-18.0, y - 2.1, 6.2), (-16.0, y + 2.1, 6.2))
        draw.rectangle(r, fill=(74, 82, 70), outline=SEAM, width=UP)
        for k in (0.2, 0.5, 0.8):
            yy = r[1] + (r[3] - r[1]) * k
            draw.line([(r[0], yy), (r[2], yy)], fill=(40, 44, 40), width=2 * UP)
        cx, cy = (r[0] + r[2]) / 2, r[1] + (r[3] - r[1]) * 0.35
        draw.ellipse([cx - 3 * UP, cy - 3 * UP, cx + 3 * UP, cy + 3 * UP], fill=(120, 124, 110), outline=SEAM)
        b = p.box("hull", "back", (-18.0, y - 2.1, 6.2), (-18.0, y + 2.1, 4.2))
        draw.rectangle(b, fill=(70, 78, 66), outline=SEAM, width=UP)
        for k in (0.2, 0.5, 0.8):
            xx = b[0] + (b[2] - b[0]) * k
            draw.line([(xx, b[1]), (xx, b[3])], fill=(40, 44, 40), width=2 * UP)
    hazard(draw, p.box("hull", "top", (-16.4, 5.5, 4.4), (-15.8, 1.6, 4.4)), 4)

    # Skirts: the three thick front blocks, bolted; light panels behind; the emblem on the front block.
    for x in (8.9, 11.8):
        seam(draw, side(x, 5.9), side(x, 2.2))
    rivets(draw, [side(x, z) for x in (6.4, 8.5, 9.3, 11.4, 12.2, 14.4) for z in (5.4, 2.7)])
    for x in (-11.8, -8.2, -4.6, -1.0, 2.6):
        seam(draw, side(x, 5.9), side(x, 2.9), lit=False)
    rivets(draw, [side(x, 5.6) for x in np.arange(-15.0, 6.0, 1.2)])
    emblem(draw, side(10.35, 4.0), 15)
    seam(draw, side(-16.0, 6.0), side(16.0, 6.0))

    # Front and back.
    for y in (7.0, -7.0):
        light(draw, p.box("hull", "front", (15.0, y - 0.5, 5.9), (15.0, y + 0.5, 5.5)))
        light(draw, p.box("hull", "back", (-16.0, y - 0.4, 5.6), (-16.0, y + 0.4, 5.1)), (170, 30, 25))
    for y in (2.6, -2.6):
        hx, hy = p.P("hull", "front", (15.5, y, 2.8))
        draw.ellipse([hx - 6 * UP, hy - 5 * UP, hx + 6 * UP, hy + 5 * UP], outline=YELLOW, width=2 * UP)
    grille(draw, p.box("hull", "back", (-16.0, -4.5, 3.9), (-16.0, 4.5, 2.6)), slats=4, vertical=False)

    # Turret: hatches, roof seams, the laser's lens, the smoke grenade tubes, the sights' glass, the emblem.
    ttop = lambda x, y: p.P("turret", "top", (x, y, 2.7))  # noqa: E731
    tside = lambda x, z: p.P("turret", "side", (x, 5.6, z))  # noqa: E731
    for (x, y) in ((-2.2, 2.6), (-2.2, -2.4)):
        hatch(draw, ttop(x, y), 0.9 * 17 * UP)
    for x in (-8.0, -4.6, 3.4):
        seam(draw, ttop(x, 5.4), ttop(x, -5.4))
    rivets(draw, [ttop(x, y) for x in np.arange(-12.0, 3.0, 1.3) for y in (4.9, -4.9)])
    for s in (1, -1):
        for k in range(6):
            cx, cy = ttop(-6.25 + k * 0.7, s * 5.7)
            draw.ellipse([cx - 4 * UP, cy - 4 * UP, cx + 4 * UP, cy + 4 * UP], fill=(30, 32, 36), outline=SEAM)
    draw.rectangle(p.box("turret", "top", (-10.4, 0.9, 4.9), (-9.1, -0.9, 4.9)), fill=(48, 54, 62), outline=SEAM, width=UP)
    for k in range(4):
        y0 = -0.8 + k * 0.42
        draw.line([ttop(-10.2, y0), ttop(-9.3, y0)], fill=(110, 118, 126), width=UP)
    hazard(draw, p.box("turret", "side", (-10.6, 1.3, 4.75), (-9.0, 1.3, 4.45)), 4)
    lx, ly = p.P("turret", "front", (-7.75, 0.0, 4.2))
    draw.ellipse([lx - 8 * UP, ly - 8 * UP, lx + 8 * UP, ly + 8 * UP], fill=(30, 30, 34), outline=SEAM, width=UP)
    draw.ellipse([lx - 6 * UP, ly - 6 * UP, lx + 6 * UP, ly + 6 * UP], fill=(170, 30, 30))
    draw.ellipse([lx - 3 * UP, ly - 4 * UP, lx + UP, ly], fill=(250, 170, 160))
    draw.rectangle(p.box("turret", "front", (4.2, -4.6, 3.35), (4.2, -3.4, 2.85)), fill=GLASS, outline=SEAM, width=UP)
    draw.rectangle(p.box("turret", "front", (1.95, 3.05, 4.45), (1.95, 3.75, 4.05)), fill=GLASS, outline=SEAM, width=UP)
    seam(draw, tside(-12.0, 2.15), tside(3.8, 2.15), lit=False)
    seam(draw, tside(-6.8, 2.7), tside(-6.8, 0.2), lit=False)
    emblem(draw, tside(-0.6, 1.3), 12)
    hazard(draw, p.box("turret", "top", (-13.7, 1.2, 2.6), (-12.6, -1.2, 2.6)), 5)
    mx, my = p.P("barrel", "front", (20.2, 0.0, 0.0))
    draw.ellipse([mx - 4 * UP, my - 4 * UP, mx + 4 * UP, my + 4 * UP], fill=(12, 12, 14))


def main():
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    painter = Painter(sys.argv[1], occlusion)
    painter.paint(leclerc_details, splinter, seed=21).save(os.path.join(out, "eulec.tga"))
    painter.paint(leclerc_details, splinter, damaged=True, seed=21).save(os.path.join(out, "eulec_d.tga"))
    paint_tread(seed=5, pads=7).save(os.path.join(out, "eulec_tread.tga"))
    print("painted")


if __name__ == "__main__":
    main()

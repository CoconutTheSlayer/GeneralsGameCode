"""The NH90's textures, with the helicopters' shared layout and painter (tiger_paint.py). nh90.py writes the
faces as they lie on the texture (build/models/EUNH90_layout.json) and the baked ambient occlusion, then
runs this with Python 3 and Pillow:

    python3 scripts/models/nh90_paint.py build/models/EUNH90_layout.json OUT_DIR [OCCLUSION.png]

The layout (NH90) needs neither Pillow nor Blender: nh90.py imports it inside Blender for the UVs.
"""
import json
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import tiger_paint  # noqa: E402
from tiger_paint import Layout, P, chevron, glass, hazard  # noqa: E402

# The NH90, in game units (+X forward, +Z up; the Chinook's size).
NH90 = Layout({
    "hull": dict(x=(-26.6, 19.6), y=(-5.5, 5.5), z=(0.0, 16.0), s=10.0,
                 side=(4, 4), top=(4, 168), front=(4, 282), back=(118, 282), bottom=(232, 282, 3.5)),
    "rotor": dict(x=(-4.2, 4.2), y=(-4.2, 4.2), z=(-1.0, 1.4), s=9.0, top=(232, 330), side=(312, 330)),
    "tail": dict(x=(-4.2, 4.2), y=(-4.2, 4.2), z=(-0.8, 0.8), s=8.5, top=(232, 410), side=(312, 410)),
})
tiger_paint.L_OF["EUNH90"] = NH90


def nh90_details(draw, rng, L):
    from boxer_paint import UP, SEAM, LIT, rivets, grille

    def side(x, z):
        return P(L, "hull", "side", (x, 3.0, z))

    def top(x, y):
        return P(L, "hull", "top", (x, y, 9.0))

    def front(y, z):
        return P(L, "hull", "front", (19.0, y, z))

    def back(y, z):
        return P(L, "hull", "back", (-20.0, y, z))

    def rect(a, b, **kw):
        draw.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], **kw)

    # The cockpit: a wide windscreen, side windows and the chin windows by the pilots' feet.
    glass(draw, [side(18.2, 5.6), side(16.0, 7.6), side(12.9, 8.3), side(12.4, 5.9), side(13.0, 4.9), side(17.0, 4.6)])
    glass(draw, [side(17.6, 3.9), side(16.0, 4.3), side(16.0, 2.9), side(17.0, 2.8)])
    draw.line([side(15.2, 4.7), side(14.8, 8.0)], fill=(30, 34, 40), width=2 * UP)
    glass(draw, [front(-2.6, 7.2), front(-0.15, 7.6), front(-0.15, 5.4), front(-2.4, 5.1)])
    glass(draw, [front(0.15, 7.6), front(2.6, 7.2), front(2.4, 5.1), front(0.15, 5.4)])
    glass(draw, [top(17.6, 1.7), top(15.6, 2.6), top(15.6, -2.6), top(17.6, -1.7)])
    # The cabin: a sliding door with its window, a row of windows behind it, the rear door.
    rect(side(5.5, 7.6), side(-1.5, 1.8), outline=SEAM, width=2 * UP)
    draw.line([side(5.5, 7.4), side(-1.5, 7.4)], fill=(70, 74, 80), width=UP)   # the door's rail
    glass(draw, [side(4.6, 6.8), side(1.2, 6.8), side(1.2, 5.2), side(4.6, 5.2)])
    for x in (9.8, -3.3, -6.6):
        glass(draw, [side(x, 6.8), side(x - 2.0, 6.8), side(x - 2.0, 5.3), side(x, 5.3)])
    rect(side(-9.2, 7.6), side(-11.0, 4.6), outline=SEAM, width=UP)
    # Panel lines, rivets, the engine bay's grilles and exhaust soot.
    for x in (12.2, 7.6, -8.0, -14.5):
        draw.line([side(x, 1.6 if x > -9 else 5.0), side(x, 8.8)], fill=SEAM, width=UP)
    rivets(draw, [side(x, 8.5) for x in [12.0 - 1.4 * k for k in range(14)]], 0.4)
    rivets(draw, [side(x, 2.0) for x in [12.0 - 1.4 * k for k in range(14)]], 0.4)
    a, b = side(6.5, 10.4), side(1.0, 9.0)
    grille(draw, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]), slats=8)
    for y in (1.5, -1.5):
        a, b = top(-0.5, y + 0.7), top(-4.5, y - 0.7)
        grille(draw, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]), slats=6)
    for y in (2.2, -2.2):
        for k in range(30):
            px, py = top(-8.0 - k * 0.32, y * (1 + k * 0.012) + rng.uniform(-0.2, 0.2))
            r = (0.9 + k * 0.05) * UP * 3
            draw.ellipse([px - r, py - r * 0.7, px + r, py + r * 0.7], fill=(40, 42, 46))
    for k in range(26):
        px, py = side(-8.2 - k * 0.32, 9.6 - k * 0.04 + rng.uniform(-0.2, 0.2))
        r = (0.8 + k * 0.05) * UP * 3
        draw.ellipse([px - r, py - r * 0.6, px + r, py + r * 0.6], fill=(42, 44, 48))
    # The rear ramp, seen from behind: its outline and hinges; hazard stripes on its edge.
    rect(back(-2.4, 5.4), back(2.4, 1.8), outline=SEAM, width=2 * UP)
    hazard(draw, back(-2.4, 1.9), back(2.4, 1.9), 2 * UP, 8)
    rect(P(L, "hull", "bottom", (-8.2, 2.5, 0)), P(L, "hull", "bottom", (-14.2, -2.5, 0)), outline=SEAM, width=UP)
    # Markings: the chevron on the tail boom and on the cabin roof, a yellow band by the tail rotor, the
    # walkway lines on the roof, hazard stripes on the sponsons' steps.
    chevron(draw, side(-17.0, 7.4), 4.5)
    chevron(draw, top(-11.5, 0.0), 6.0, math.pi / 2)
    chevron(draw, side(9.0, 3.4), 4.0)
    hazard(draw, side(-20.5, 6.5), side(-20.5, 8.2), 2.2 * UP, 4)
    for y in (2.4, -2.4):
        draw.line([top(10.0, y), top(-7.0, y)], fill=(226, 186, 40), width=UP)
    hazard(draw, side(4.0, 1.4), side(-5.0, 1.4), 1.6 * UP, 10)
    draw.line([side(19.2, 5.0), side(17.0, 6.6)], fill=LIT, width=UP)

    # The rotor head's blade cuffs and the tail rotor's tips in yellow.
    for a in range(4):
        ang = a * math.pi / 2 + math.radians(45)
        p = P(L, "rotor", "top", (math.cos(ang) * 3.8, math.sin(ang) * 3.8, 0.5))
        draw.ellipse([p[0] - 3 * UP, p[1] - 3 * UP, p[0] + 3 * UP, p[1] + 3 * UP], fill=(226, 186, 40))
    for a in range(4):
        ang = a * math.pi / 2
        p = P(L, "tail", "top", (math.cos(ang) * 3.7, math.sin(ang) * 3.7, 0.0))
        draw.ellipse([p[0] - 3 * UP, p[1] - 3 * UP, p[0] + 3 * UP, p[1] + 3 * UP], fill=(226, 186, 40))


def main():
    from PIL import Image
    layout = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    tiger_paint.paint_body(layout, nh90_details, occlusion=occlusion, seed=33).save(os.path.join(out, "eunh_body.tga"))
    tiger_paint.paint_body(layout, nh90_details, damaged=True, occlusion=occlusion, seed=33).save(
        os.path.join(out, "eunh_body_d.tga"))
    tiger_paint.paint_rotor_blur(os.path.join(out, "eunh_rotor.tga"), seed=9)
    print("painted")


if __name__ == "__main__":
    main()

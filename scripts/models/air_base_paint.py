"""Paints the European Air Base's textures, in two steps that air_base.py runs (Python 3 and Pillow), with the
Armour Works' tiles and weathering (armour_works_paint.py):

    tiles OUT_DIR             the tiling surfaces Blender projects onto the model
    compose BAKE_DIR OUT_DIR  the building's texture and its damaged, wrecked and night versions, and the
                              apron: two runways with centre dashes and hold bars, taxi lines from the
                              hangars, parking boxes, the helipad and the faction's mark
"""
import math
import os
import sys

from PIL import ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import armour_works_paint as aw  # noqa: E402

PREFIX = "euaf"
EXTENT = (-112.0, 112.0, -74.0, 74.0)
RUNWAYS = (-49.0, -13.1)                 # runway centre lines (y), from RUNWAY_X[0] to the pad's end
RUNWAY_X = (-40.0, 112.0)
RUNWAY_HALF = 14.0
RUNWAY_STRIP = (-46.0, 111.0, -68.0, 3.0)  # the concrete strip both runways lie on (air_base.RUNWAY_OUTLINE)
ASPHALT, WHITE, YELLOW, NAVY, GOLD = (96, 98, 100), (232, 230, 222), (214, 176, 52), (28, 34, 64), (236, 200, 40)


def poly(p, d, points, **kw):
    d.polygon([p.px(x, y) for x, y in points], **kw)


def line(p, d, a, b, units, fill):
    d.line([p.px(*a), p.px(*b)], fill=fill, width=p.width(units))


def disc(p, d, cx, cy, r, steps=48, **kw):
    poly(p, d, [(cx + math.cos(2 * math.pi * i / steps) * r, cy + math.sin(2 * math.pi * i / steps) * r)
                for i in range(steps)], **kw)


def emblem(p, d, cx, cy, half):
    """The faction's mark flat on the apron, square in the world, the chevron pointing to +X."""
    poly(p, d, [(cx - half, cy - half), (cx + half, cy - half), (cx + half, cy + half), (cx - half, cy + half)],
         fill=NAVY, outline=WHITE)
    h = half
    poly(p, d, [(cx - 0.4 * h, cy + 0.65 * h), (cx + 0.55 * h, cy), (cx - 0.4 * h, cy - 0.65 * h),
                (cx - 0.4 * h, cy - 0.42 * h), (cx + 0.15 * h, cy), (cx - 0.4 * h, cy + 0.42 * h)], fill=GOLD)


def markings(p, d):
    # The runway strip: lighter, smoother concrete with joints, set apart from the apron.
    from PIL import Image
    img = d._image
    x0, x1, y0, y1 = RUNWAY_STRIP
    mask = Image.new("L", img.size, 0)
    ImageDraw.Draw(mask).polygon([p.px(x0, y0), p.px(x1, y0), p.px(x1, y1), p.px(x0, y1)], fill=150)
    img.paste(Image.new("RGB", img.size, (176, 176, 170)), (0, 0), mask)
    for x in range(int(x0), int(x1), 15):
        line(p, d, (x, y0), (x, y1), 0.25, (128, 128, 124))
    for y in RUNWAYS:
        x0r = RUNWAY_X[0]
        for edge in (y - RUNWAY_HALF + 1.2, y + RUNWAY_HALF - 1.2):
            line(p, d, (x0r, edge), (x1, edge), 0.7, WHITE)
        for x in range(36, 108, 12):
            line(p, d, (x, y), (x + 6, y), 0.9, WHITE)
        for k in range(6):                                  # threshold bars at the start
            yy = y - RUNWAY_HALF + 3 + k * (2 * RUNWAY_HALF - 6) / 5
            line(p, d, (24, yy), (31, yy), 1.3, WHITE)
        for x in (-4.0,):                                   # hold bars
            for k in (0, 1):
                line(p, d, (x + k * 1.6, y - RUNWAY_HALF + 1), (x + k * 1.6, y + RUNWAY_HALF - 1), 0.6, YELLOW)
        for k, ch in enumerate((-1, 1)):                    # the runways' numbers as bars
            line(p, d, (100, y + ch * 4), (106, y + ch * 4), 1.0, WHITE)
    # Taxi lines from the hangars to the runways, and parking boxes in front of the hangars.
    for x in (-21.1, 9.5):
        line(p, d, (x, 34), (x, RUNWAYS[1]), 0.6, YELLOW)
        poly(p, d, [(x - 11, 12), (x + 11, 12), (x + 11, 34), (x - 11, 34)], outline=WHITE)
    for y in RUNWAYS:
        line(p, d, (-68, y), (-40, y), 0.6, YELLOW)
        poly(p, d, [(-68, y - 11), (-44, y - 11), (-44, y + 11), (-68, y + 11)], outline=WHITE)
    # The helipad: a white ring, a yellow cross.
    cx, cy = 66.7, 41.6
    disc(p, d, cx, cy, 17.0, fill=(150, 152, 150))
    disc(p, d, cx, cy, 15.5, outline=WHITE)
    disc(p, d, cx, cy, 14.6, outline=YELLOW)
    poly(p, d, [(cx - 9, cy - 1.6), (cx + 9, cy - 1.6), (cx + 9, cy + 1.6), (cx - 9, cy + 1.6)], fill=YELLOW)
    poly(p, d, [(cx - 1.6, cy - 9), (cx + 1.6, cy - 9), (cx + 1.6, cy + 9), (cx - 1.6, cy + 9)], fill=YELLOW)
    emblem(p, d, 30.0, 14.0, 7.0)


def main():
    if sys.argv[1] == "tiles":
        aw.tiles(sys.argv[2])
    else:
        aw.compose(sys.argv[2], sys.argv[3], PREFIX, markings, EXTENT, seed=11)


if __name__ == "__main__":
    main()

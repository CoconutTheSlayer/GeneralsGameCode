"""Paints the Boxer's textures in the style of the game's vehicles: crisp panels with dark seams and lit
edges, rivets, hatches, grilles and lights, painted shading, stains, streaks and dust, over a blue-grey
camouflage. boxer.py writes the faces of the model on the texture (build/models/EUBOXER_layout.json) and
runs this with Python 3 and Pillow, with the ambient occlusion it baked:

    python3 scripts/models/boxer_paint.py build/models/EUBOXER_layout.json OUT_DIR [OCCLUSION.png]
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from boxer_layout import SIZE, pixel  # noqa: E402

UP = 4  # painted at four times the size, then shrunk: smooth lines
W = SIZE * UP

CAMO = [(124, 138, 150), (84, 97, 112), (166, 176, 184)]
SEAM, LIT = (22, 25, 30), (205, 212, 218)
DUST = (156, 142, 118)


def P(part, grp, co):
    x, y = pixel(part, grp, co)
    return x * UP, y * UP


def smooth_noise(size, cells, rng):
    grid = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, size, endpoint=False)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    a = grid[i][:, i] * (1 - f)[None, :] + grid[i][:, i + 1] * f[None, :]
    b = grid[i + 1][:, i] * (1 - f)[None, :] + grid[i + 1][:, i + 1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def camouflage(rng):
    """Hard-edged patches, as painted on vehicles."""
    n1 = smooth_noise(W, 9, rng) * 0.75 + smooth_noise(W, 23, rng) * 0.25
    n2 = smooth_noise(W, 8, rng) * 0.75 + smooth_noise(W, 21, rng) * 0.25
    img = np.empty((W, W, 3))
    img[:] = CAMO[0]
    img[n1 > 0.58] = CAMO[1]
    img[(n2 > 0.62) & (n1 <= 0.58)] = CAMO[2]
    return img


def paint_hull(layout, damaged=False, seed=11, occlusion=None):
    rng = np.random.default_rng(seed)
    base = camouflage(rng)

    # Each face filled, darker the more it faces down or away from the light.
    shade = Image.new("L", (W, W), 0)
    mask = Image.new("L", (W, W), 0)
    ds, dm = ImageDraw.Draw(shade), ImageDraw.Draw(mask)
    light = {"top": 255, "side": 222, "front": 214, "back": 196, "bottom": 90}
    for f in layout["faces"]:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) < 3:
            continue
        ds.polygon(poly, fill=light[f["group"]])
        dm.polygon(poly, fill=255)
    img = base * (np.asarray(shade, float)[..., None] / 255.0)

    # Painted shading: the sides darken towards the ground, the roof towards its edges.
    v = np.arange(W)[:, None] / UP
    for (part, grp), (z_top, z_bottom) in {("hull", "side"): (200, 312), ("hull", "front"): (318, 430),
                                            ("hull", "back"): (318, 430)}.items():
        rows = (v >= z_top) & (v < z_bottom)
        t = np.clip((v - z_top) / (z_bottom - z_top), 0, 1)
        img *= np.where(rows, 1.08 - 0.38 * t, 1.0)[..., None]

    # Stains and grain.
    stains = smooth_noise(W, 30, rng) * 0.6 + smooth_noise(W, 70, rng) * 0.4
    img *= (0.80 + 0.28 * stains)[..., None]
    img *= (0.94 + 0.12 * rng.random((W, W)))[..., None]
    # Dust on the lower sides, front and back.
    side_rows = (v >= 200) & (v < 312)
    t = np.clip((v - 260) / 52.0, 0, 1) * side_rows
    end_rows = (v >= 318) & (v < 430)
    t = t + np.clip((v - 385) / 45.0, 0, 1) * end_rows
    dusty = t * (0.55 + 0.45 * smooth_noise(W, 40, rng))
    img = img * (1 - dusty[..., None] * 0.7) + np.array(DUST) * dusty[..., None] * 0.7

    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)

    # Rain and oil streaks running down the sides and ends.
    for _ in range(140):
        x = rng.uniform(0, W)
        y0 = rng.choice([200, 318]) * UP + rng.uniform(0, 30 * UP)
        length = rng.uniform(15, 60) * UP
        draw.line([(x, y0), (x + rng.uniform(-3, 3), y0 + length)], fill=(48, 52, 58), width=int(rng.uniform(2, 5)))

    # Seams along the model's edges, lit on the upper side.
    for f in layout["faces"]:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            a, b = poly[i], poly[(i + 1) % len(poly)]
            # The turret is drawn smaller on the texture: finer seams, not lit.
            small = f.get("part") == "turret"
            draw.line([a, b], fill=SEAM, width=UP if small else 3 * UP)
            if small:
                continue
            # Light the edge on the face's side, nudged towards its middle.
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = cx - mx, cy - my
            d = math.hypot(dx, dy) or 1.0
            ox, oy = dx / d * 2.5 * UP, dy / d * 2.5 * UP
            if f["group"] in ("top", "side", "front", "back") and dy >= -abs(dx):
                draw.line([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)], fill=LIT, width=UP)

    paint_details(draw, rng)
    canvas = weather(canvas, layout, rng)

    if occlusion is not None:
        # Contact shadows from the baked occlusion, softened so the painted shading still leads.
        ao = np.asarray(occlusion.convert("L").resize((W, W), Image.BILINEAR), float) / 255.0
        arr = np.asarray(canvas, float) * (0.55 + 0.45 * ao)[..., None]
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if damaged:
        arr = np.asarray(canvas, float)
        soot = np.clip((smooth_noise(W, 12, rng) - 0.45) * 4, 0, 1)
        arr = arr * (1 - soot[..., None] * 0.85) * 0.62
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(canvas)
        for _ in range(26):
            x, y, r = rng.uniform(0, W), rng.uniform(0, 430 * UP), rng.uniform(4, 12) * UP
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(18, 16, 14))
            draw.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(90, 50, 25))

    outside = Image.fromarray(255 - np.asarray(mask))
    canvas.paste((0, 0, 0), mask=outside)
    small = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    return small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


MUD = (88, 72, 52)


def weather(canvas, layout, rng):
    """Mud thrown up by the wheels and worn paint along the edges; returns the weathered canvas."""
    side = lambda x, z: P("hull", "side", (x, 5.0, z))  # noqa: E731
    # Mud goes on a layer of its own, softened and laid on thinly.
    mud = Image.new("L", (W, W), 0)
    draw = ImageDraw.Draw(mud)
    # Mud: dense low down and around each wheel, thinning upwards.
    for wx in (11.2, 6.4, -4.4, -9.2):
        for _ in range(170):
            a = rng.uniform(math.pi * 0.05, math.pi * 0.95)
            r = rng.uniform(2.6, 4.8)
            x, z = wx + math.cos(a) * r * 1.2, 2.5 + math.sin(a) * r * 0.9
            if z > 6.6:
                continue
            px, py = side(x, z)
            s_ = rng.uniform(0.3, 1.2) * UP
            draw.ellipse([px - s_, py - s_ * 0.8, px + s_, py + s_ * 0.8], fill=int(rng.uniform(120, 255)))
    for _ in range(400):
        px, py = side(rng.uniform(-15, 15), rng.uniform(2.2, 4.4))
        s_ = rng.uniform(0.4, 1.6) * UP
        draw.ellipse([px - s_, py - s_, px + s_, py + s_], fill=int(rng.uniform(100, 220)))
    for _ in range(120):
        px, py = P("hull", "front", (15.0, rng.uniform(-5.5, 5.5), rng.uniform(2.2, 5.2)))
        s_ = rng.uniform(0.4, 1.4) * UP
        draw.ellipse([px - s_, py - s_, px + s_, py + s_], fill=int(rng.uniform(100, 220)))
    amount = np.asarray(mud.filter(ImageFilter.GaussianBlur(UP * 0.6)), float)[..., None] / 255.0 * 0.8
    arr = np.asarray(canvas, float) * (1 - amount) + np.array(MUD, float) * amount
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)
    # Worn edges: short light scratches beside the hull's seams.
    for f in layout["faces"]:
        if f.get("part") == "turret" or f["group"] == "bottom":
            continue
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
            length = math.hypot(bx - ax, by - ay)
            for _ in range(int(length / (40 * UP))):
                t = rng.uniform(0, 1)
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                ox, oy = rng.uniform(-3, 3) * UP, rng.uniform(-3, 3) * UP
                draw.line([(x + ox, y + oy), (x + ox + rng.uniform(-4, 4) * UP, y + oy + rng.uniform(-1, 1) * UP)],
                          fill=(150, 158, 164), width=UP)
    return canvas


def rivets(draw, points, r=0.55):
    for x, y in points:
        draw.ellipse([x - r * UP, y - r * UP, x + r * UP, y + r * UP], fill=(40, 44, 50))
        draw.ellipse([x - r * UP, y - r * UP, x, y], fill=(200, 206, 212))


def seam(draw, a, b, lit=True):
    draw.line([a, b], fill=SEAM, width=2 * UP)
    if lit:
        draw.line([(a[0], a[1] + 2 * UP), (b[0], b[1] + 2 * UP)], fill=LIT, width=UP)


def grille(draw, x0, y0, x1, y1, slats=6, vertical=True):
    draw.rectangle([x0, y0, x1, y1], fill=(30, 33, 38), outline=SEAM, width=UP)
    for i in range(slats):
        t = (i + 0.5) / slats
        if vertical:
            x = x0 + (x1 - x0) * t
            draw.line([(x, y0 + UP), (x, y1 - UP)], fill=(110, 118, 126), width=UP)
        else:
            y = y0 + (y1 - y0) * t
            draw.line([(x0 + UP, y), (x1 - UP, y)], fill=(110, 118, 126), width=UP)
    draw.line([(x0, y0), (x1, y0)], fill=LIT, width=UP)


def hatch(draw, centre, radius):
    x, y = centre
    r = radius * 16 * UP
    draw.ellipse([x - r, y - r, x + r, y + r], outline=SEAM, width=3 * UP)
    draw.arc([x - r + 3 * UP, y - r + 3 * UP, x + r - 3 * UP, y + r - 3 * UP], 180, 300, fill=LIT, width=UP)
    draw.rectangle([x - r * 0.25, y - r * 1.05, x + r * 0.25, y - r * 0.75], fill=(60, 66, 74), outline=SEAM)
    for a in range(0, 360, 60):
        bx, by = x + math.cos(math.radians(a)) * r * 0.7, y + math.sin(math.radians(a)) * r * 0.7
        rivets(draw, [(bx, by)], 0.45)


def emblem(draw, centre, size):
    """The European arm of service mark: a white chevron in a dark square."""
    x, y = centre
    s = size * UP
    draw.rectangle([x - s, y - s * 0.75, x + s, y + s * 0.75], fill=(28, 34, 60), outline=(220, 220, 220), width=UP)
    draw.polygon([(x - s * 0.7, y + s * 0.4), (x, y - s * 0.5), (x + s * 0.7, y + s * 0.4), (x + s * 0.45, y + s * 0.4),
                  (x, y - s * 0.12), (x - s * 0.45, y + s * 0.4)], fill=(235, 200, 40))


def text(draw, centre, words, size):
    """Stencilled white letters."""
    from PIL import ImageFont
    font = ImageFont.load_default(size=size * UP // 4)
    x, y = centre
    draw.text((x, y), words, font=font, fill=(222, 222, 214), anchor="mm")


def plate(draw, centre):
    """A number plate: white with black characters."""
    x, y = centre
    draw.rectangle([x - 16 * UP, y - 4 * UP, x + 16 * UP, y + 4 * UP], fill=(225, 225, 220), outline=SEAM, width=UP)
    text_colour = (20, 20, 20)
    from PIL import ImageFont
    font = ImageFont.load_default(size=6 * UP)
    draw.text((x, y), "Y-7042", font=font, fill=text_colour, anchor="mm")


def paint_details(draw, rng):
    top = lambda x, y: P("hull", "top", (x, y, 9.0))  # noqa: E731
    side = lambda x, z: P("hull", "side", (x, 5.0, z))  # noqa: E731
    front = lambda y, z: P("hull", "front", (15.0, y, z))  # noqa: E731
    back = lambda y, z: P("hull", "back", (-15.0, y, z))  # noqa: E731

    # Roof: plate seams with rivets, hatches, the engine deck grille at the front right, an emblem.
    for x in (4.5, -5.0, -10.0):
        seam(draw, top(x, 4.9), top(x, -4.9))
        rivets(draw, [top(x + 0.5, y) for y in np.arange(-4.4, 4.5, 1.1)])
    for y in (4.6, -4.6):
        rivets(draw, [top(x, y) for x in np.arange(-14.5, 14.0, 1.2)])
    for (x, y), r in (((-6.5, 2.4), 1.1), ((-6.5, -2.4), 1.1), ((-11.5, 0.0), 1.1), ((3.5, 2.6), 0.9)):
        hatch(draw, top(x, y), r)
    gx0, gy0 = top(12.5, 4.0)
    gx1, gy1 = top(9.9, 1.1)
    grille(draw, min(gx0, gx1), min(gy0, gy1), max(gx0, gx1), max(gy0, gy1), slats=8)
    # Air intake on the roof's right, behind the step.
    gx0, gy0 = top(-0.9, -2.6)
    gx1, gy1 = top(-2.5, -4.2)
    grille(draw, min(gx0, gx1), min(gy0, gy1), max(gx0, gx1), max(gy0, gy1), slats=5, vertical=False)
    gx0, gy0 = top(-1.8, 1.4)
    gx1, gy1 = top(-4.0, -1.4)
    draw.rectangle([min(gx0, gx1), min(gy0, gy1), max(gx0, gx1), max(gy0, gy1)], outline=SEAM, width=2 * UP)
    emblem(draw, top(-12.6, -3.0), 9)

    # Sides: a seam under the roof edge with rivets, plate joints, vision blocks, a towing cable.
    seam(draw, side(-15.0, 8.4), side(15.0, 8.4))
    rivets(draw, [side(x, 8.0) for x in np.arange(-14.5, 14.5, 1.3)])
    for x in (9.0, -0.8, -8.0):
        seam(draw, side(x, 8.4), side(x, 5.3), lit=False)
    for x in (1.5, 4.5):
        a, b = side(x, 8.9), side(x + 1.6, 8.5)
        draw.rectangle([a[0], a[1], b[0], b[1]], fill=(40, 70, 95), outline=SEAM, width=UP)
    cable = [side(x, 5.9 + 0.25 * math.sin(x * 0.7)) for x in np.arange(-13.0, 8.0, 0.5)]
    draw.line(cable, fill=(70, 74, 80), width=2 * UP)
    draw.line(cable, fill=(150, 156, 160), width=UP)
    emblem(draw, side(-6.0, 6.9), 10)
    # Stowage bins between the wheels: lids, latches.
    a, b = side(-1.6, 5.1), side(3.6, 3.0)
    draw.rectangle([a[0], a[1], b[0], b[1]], outline=SEAM, width=2 * UP)
    draw.line([(a[0], a[1] + 3 * UP), (b[0], a[1] + 3 * UP)], fill=LIT, width=UP)
    for x in (-0.4, 2.4):
        l = side(x, 4.6)
        draw.rectangle([l[0] - 3 * UP, l[1] - 2 * UP, l[0] + 3 * UP, l[1] + 2 * UP], fill=(52, 58, 66))
    text(draw, side(-11.0, 6.55), "Y-7042", 26)

    # Front: headlights, a grille between them, tow hooks.
    for y in (3.4, -3.4):
        a, b = front(y - 0.55, 6.25), front(y + 0.55, 5.65)
        draw.rectangle([a[0], a[1], b[0], b[1]], fill=(230, 226, 200), outline=SEAM, width=UP)
        hx, hy = front(y, 4.3)  # tow hook
        draw.ellipse([hx - 5 * UP, hy - 4 * UP, hx + 5 * UP, hy + 4 * UP], outline=SEAM, width=2 * UP)
    a, b = front(-1.6, 5.9), front(1.6, 4.6)
    grille(draw, a[0], a[1], b[0], b[1], slats=6, vertical=False)
    plate(draw, front(0.0, 6.6))

    # Back: the ramp with its hinges and handle, tail lights.
    a, b = back(-2.6, 8.3), back(2.6, 5.4)
    draw.rectangle([a[0], a[1], b[0], b[1]], outline=SEAM, width=3 * UP)
    draw.line([(a[0] + 3 * UP, a[1] + 3 * UP), (b[0] - 3 * UP, a[1] + 3 * UP)], fill=LIT, width=UP)
    for y in (-1.8, 1.8):
        h = back(y, 5.6)
        draw.rectangle([h[0] - 3 * UP, h[1] - 2 * UP, h[0] + 3 * UP, h[1] + 2 * UP], fill=(50, 55, 62))
    hx, hy = back(1.6, 7.0)
    draw.rectangle([hx - 4 * UP, hy - UP, hx + 4 * UP, hy + UP], fill=(190, 196, 200))
    plate(draw, back(0.0, 5.0))
    for y in (4.3, -4.3):
        lx, ly = back(y, 7.6)
        draw.rectangle([lx - 4 * UP, ly - 3 * UP, lx + 4 * UP, ly + 3 * UP], fill=(170, 30, 25), outline=SEAM, width=UP)

    # Turret: the sight's glass and the ammunition box lid.
    sx, sy = P("turret", "front", (1.2, -1.3, 1.3))
    draw.ellipse([sx - 6 * UP, sy - 4 * UP, sx + 6 * UP, sy + 4 * UP], fill=(30, 60, 90), outline=SEAM, width=UP)
    draw.ellipse([sx - 3 * UP, sy - 3 * UP, sx, sy], fill=(150, 200, 230))


def paint_tire(rng):
    """The tyre: hub in the upper half (an ellipse that the wheel's UVs make round), tread below."""
    img = Image.new("RGB", (W // 2, W // 2), (30, 31, 33))
    draw = ImageDraw.Draw(img)
    w = W // 2
    # Hub: u = 0.5 + x / (2.1 R), v = 0.75 + z / (4.2 R) in Blender's UVs.
    cx, cy, rx, ry = w * 0.5, w * 0.25, w / 2.1, w / 4.2
    draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(36, 37, 40))
    for k, colour in ((0.62, (88, 98, 108)), (0.56, (128, 140, 150)), (0.24, (70, 78, 86))):
        draw.ellipse([cx - rx * k, cy - ry * k, cx + rx * k, cy + ry * k], fill=colour, outline=(20, 22, 26), width=UP)
    draw.arc([cx - rx * 0.56, cy - ry * 0.56, cx + rx * 0.56, cy + ry * 0.56], 190, 290, fill=(200, 208, 214), width=UP)
    for a in range(0, 360, 45):
        bx, by = cx + math.cos(math.radians(a)) * rx * 0.4, cy + math.sin(math.radians(a)) * ry * 0.4
        draw.ellipse([bx - 2 * UP, by - UP, bx + 2 * UP, by + UP], fill=(40, 44, 48))
    # The sidewall: a raised ring near the rim.
    draw.ellipse([cx - rx * 0.8, cy - ry * 0.8, cx + rx * 0.8, cy + ry * 0.8], outline=(48, 50, 54), width=2 * UP)
    draw.ellipse([cx - rx * 0.62, cy - ry * 0.62, cx + rx * 0.62, cy + ry * 0.62], outline=(20, 22, 26), width=UP)
    # Tread: chevron lugs across the lower half, three times around.
    top_, mid, bottom = w * 0.56, w * 0.75, w * 0.94
    n = 30
    for i in range(n):
        x = i * w / n
        step = w / n
        lug = [(x, top_), (x + step * 0.45, top_), (x + step * 0.85, mid), (x + step * 0.45, bottom), (x, bottom),
               (x + step * 0.4, mid)]
        draw.polygon(lug, fill=(46, 47, 50))
        draw.line([(x, top_), (x + step * 0.4, mid)], fill=(76, 78, 82), width=UP)
    return img.resize((256, 256), Image.LANCZOS)


def main():
    layout = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    paint_hull(layout, occlusion=occlusion).save(os.path.join(out, "euboxer.tga"))
    paint_hull(layout, damaged=True, occlusion=occlusion).save(os.path.join(out, "euboxer_d.tga"))
    paint_tire(np.random.default_rng(3)).save(os.path.join(out, "euboxer_tire.tga"))
    print("painted")


if __name__ == "__main__":
    main()

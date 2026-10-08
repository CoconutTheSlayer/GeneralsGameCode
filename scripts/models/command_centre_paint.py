"""Paints the European Command Centre's tiling textures in the style of the game's buildings: painted
cladding panels with seams, rivets and grime, window bands, ribbed bay walls, a segmented door, a
concrete pad, roofs and the faction's mark, each also damaged, wrecked and (with lit windows) at night.
command_centre.py runs it with Python 3 and Pillow:

    python3 scripts/models/command_centre_paint.py OUT_DIR
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

UP = 4  # painted larger, then shrunk
SEAM, LIT = (24, 27, 32), (196, 204, 212)
CLADDING = [(118, 132, 146), (104, 118, 132), (132, 144, 156)]
GLASS, GLASS_LIT = (34, 52, 72), (236, 196, 110)
FRAME = (170, 178, 186)
CONCRETE = (140, 142, 142)


def tiling_noise(w, h, cells, rng):
    """Smooth noise that repeats across the texture, so tiles meet without a seam."""
    gx, gy = cells, max(1, round(cells * h / w))
    grid = rng.random((gy, gx))
    ys, xs = np.linspace(0, gy, h, endpoint=False), np.linspace(0, gx, w, endpoint=False)
    yi, xi = ys.astype(int), xs.astype(int)
    fy, fx = ys - yi, xs - xi
    fy, fx = fy * fy * (3 - 2 * fy), fx * fx * (3 - 2 * fx)
    a = grid[yi % gy][:, xi % gx] * (1 - fx) + grid[yi % gy][:, (xi + 1) % gx] * fx
    b = grid[(yi + 1) % gy][:, xi % gx] * (1 - fx) + grid[(yi + 1) % gy][:, (xi + 1) % gx] * fx
    return a * (1 - fy)[:, None] + b * fy[:, None]


def grime(img, rng, amount=0.22, streaks=0, streak_colour=(46, 50, 56)):
    """Stains, grain and rain streaks over a painted image (tiling)."""
    w, h = img.size
    arr = np.asarray(img, float)
    stains = tiling_noise(w, h, 6, rng) * 0.6 + tiling_noise(w, h, 14, rng) * 0.4
    arr *= (1 - amount + amount * 1.3 * stains)[..., None]
    arr *= (0.95 + 0.1 * rng.random((h, w)))[..., None]
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for _ in range(streaks):
        x = rng.uniform(0, w)
        y = rng.uniform(0, h * 0.7)
        d.line([(x, y), (x + rng.uniform(-2, 2), y + rng.uniform(h * 0.05, h * 0.25))], fill=streak_colour,
               width=int(rng.uniform(1, 3) * UP / 2))
    return out


def rivet_row(d, x0, x1, y, step):
    x = x0
    while x <= x1:
        d.ellipse([x - UP, y - UP, x + UP, y + UP], fill=(52, 58, 66))
        d.ellipse([x - UP, y - UP, x, y], fill=LIT)
        x += step


def damage(img, rng, level):
    """Soot, scorch marks and cracks (level 1), burnt through with holes (level 2)."""
    w, h = img.size
    arr = np.asarray(img, float)
    soot = np.clip((tiling_noise(w, h, 5, rng) - (0.55 if level == 1 else 0.35)) * 3.5, 0, 1)
    arr = arr * (1 - soot[..., None] * 0.85) * (0.85 if level == 1 else 0.6)
    out = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(out)
    for _ in range(10 * level):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        pts = [(x, y)]
        for _ in range(5):
            x += rng.uniform(-14, 14) * UP
            y += rng.uniform(-10, 10) * UP
            pts.append((x, y))
        d.line(pts, fill=(18, 18, 18), width=UP)
    if level == 2:
        for _ in range(6):
            x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(6, 16) * UP
            d.ellipse([x - r, y - r, x + r, y + r], fill=(8, 8, 8))
            d.ellipse([x - r * 1.4, y - r * 1.4, x + r * 1.4, y + r * 1.4], outline=(60, 38, 24), width=2 * UP)
    return out


def facade(rng, night=False, level=0):
    """40 x 20 units: two storeys of cladding with a window band each."""
    w, h = 512 * UP, 256 * UP
    img = Image.new("RGB", (w, h), CLADDING[0])
    d = ImageDraw.Draw(img)
    px = w / 40.0  # pixels per unit
    for storey in range(2):
        z0 = h - storey * 10 * px          # bottom of the storey (y grows down)
        # Cladding panels, 5 units wide, alternating shades.
        for k in range(8):
            colour = CLADDING[(k + storey) % 3]
            d.rectangle([k * 5 * px, z0 - 10 * px, (k + 1) * 5 * px, z0], fill=colour)
        # Window band, 4.2 to 7.4 units up, mullions every 2.5 units.
        top, bottom = z0 - 7.4 * px, z0 - 4.2 * px
        d.rectangle([0, top - 0.3 * px, w, bottom + 0.3 * px], fill=FRAME)
        for k in range(16):
            x0, x1 = k * 2.5 * px + 0.18 * px, (k + 1) * 2.5 * px - 0.18 * px
            lit = night and (level == 0 or rng.random() < 0.5) and rng.random() < 0.8
            pane = GLASS_LIT if lit else GLASS
            d.rectangle([x0, top, x1, bottom], fill=pane)
            if not lit:
                d.polygon([(x0, top), (x0 + 0.9 * px, top), (x0, top + 1.6 * px)], fill=(70, 96, 122))
            if level == 2 and rng.random() < 0.5:
                d.rectangle([x0, top, x1, bottom], fill=(10, 10, 10))
        # Seams: floor line, panel joints, the sill and lintel lit from above.
        d.line([(0, z0 - 10 * px), (w, z0 - 10 * px)], fill=SEAM, width=3 * UP)
        d.line([(0, z0 - 10 * px + 3 * UP), (w, z0 - 10 * px + 3 * UP)], fill=LIT, width=UP)
        for k in range(9):
            d.line([(k * 5 * px, z0 - 10 * px), (k * 5 * px, top - 0.3 * px)], fill=SEAM, width=2 * UP)
            d.line([(k * 5 * px, bottom + 0.3 * px), (k * 5 * px, z0)], fill=SEAM, width=2 * UP)
        d.line([(0, bottom + 0.4 * px), (w, bottom + 0.4 * px)], fill=LIT, width=UP)
        rivet_row(d, 0.6 * px, w, z0 - 9.4 * px, 1.25 * px)
        rivet_row(d, 0.6 * px, w, z0 - 0.6 * px, 1.25 * px)
    # A darker plinth at the foot.
    d.rectangle([0, h - 1.2 * px, w, h], fill=(86, 92, 98))
    img = grime(img, rng, streaks=40, streak_colour=(70, 76, 84))
    if night:
        img = Image.fromarray((np.asarray(img, float) * 0.85).astype(np.uint8))
    if level:
        img = damage(img, rng, level)
    return img.resize((512, 256), Image.LANCZOS)


def roof(rng, level=0):
    w = h = 256 * UP
    img = Image.new("RGB", (w, h), (112, 116, 120))
    d = ImageDraw.Draw(img)
    px = w / 24.0
    for k in range(5):  # membrane strips
        d.line([(0, k * 6 * px), (w, k * 6 * px)], fill=(84, 88, 92), width=2 * UP)
        d.line([(k * 6 * px, 0), (k * 6 * px, h)], fill=(96, 100, 104), width=UP)
    for x, y in ((6, 6), (18, 18)):  # vents
        cx, cy = x * px, y * px
        d.rectangle([cx - px, cy - px, cx + px, cy + px], fill=(70, 74, 80), outline=SEAM, width=UP)
        for i in range(4):
            d.line([(cx - px + UP * 2, cy - px + (i + 0.5) * px / 2), (cx + px - UP * 2, cy - px + (i + 0.5) * px / 2)],
                   fill=(130, 136, 140), width=UP)
    img = grime(img, rng, amount=0.3)
    if level:
        img = damage(img, rng, level)
    return img.resize((256, 256), Image.LANCZOS)


def bay(rng, level=0):
    """Ribbed steel walls of the vehicle bay, 24 x 14.2 units."""
    w, h = 256 * UP, 256 * UP
    img = Image.new("RGB", (w, h), CLADDING[1])
    d = ImageDraw.Draw(img)
    px = w / 24.0
    for k in range(48):  # ribs every half unit
        x = k * 0.5 * px
        d.line([(x, 0), (x, h)], fill=(80, 92, 104), width=UP)
        d.line([(x + UP, 0), (x + UP, h)], fill=(150, 160, 170), width=UP)
    for y in (0.06 * h, 0.94 * h):
        d.rectangle([0, y - 0.4 * px, w, y + 0.4 * px], fill=(88, 96, 104))
        d.line([(0, y - 0.4 * px), (w, y - 0.4 * px)], fill=LIT, width=UP)
    d.rectangle([0, 0.94 * h, w, h], fill=(80, 84, 88))
    img = grime(img, rng, streaks=60)
    if level:
        img = damage(img, rng, level)
    return img.resize((256, 256), Image.LANCZOS)


def door(rng, level=0):
    """The bay door: horizontal sections in a frame with warning stripes."""
    w = h = 256 * UP
    img = Image.new("RGB", (w, h), (126, 134, 140))
    d = ImageDraw.Draw(img)
    for i in range(12):
        y = i * h / 12
        d.rectangle([0, y, w, y + h / 12], fill=(120 + (i % 2) * 10, 128 + (i % 2) * 10, 136 + (i % 2) * 10))
        d.line([(0, y), (w, y)], fill=SEAM, width=2 * UP)
        d.line([(0, y + 2 * UP), (w, y + 2 * UP)], fill=LIT, width=UP)
    s = 14 * UP  # warning stripes round the opening
    for edge in ((0, 0, w, s), (0, 0, s, h), (w - s, 0, w, h)):
        d.rectangle(edge, fill=(220, 180, 40))
    for k in range(-h, w + h, 6 * s // 2):
        d.line([(k, 0), (k + s * 3, s * 3)], fill=(30, 30, 30), width=s // 2)
    for k in range(0, h, 3 * s):
        d.line([(0, k), (s, k + s)], fill=(30, 30, 30), width=s // 2)
        d.line([(w - s, k), (w, k + s)], fill=(30, 30, 30), width=s // 2)
    img = grime(img, rng, streaks=40)
    if level:
        img = damage(img, rng, level)
    return img.resize((256, 256), Image.LANCZOS)


def pad(rng, level=0):
    w = h = 256 * UP
    img = Image.new("RGB", (w, h), CONCRETE)
    d = ImageDraw.Draw(img)
    px = w / 30.0
    for k in range(4):  # slab joints every 10 units
        d.line([(0, k * 10 * px), (w, k * 10 * px)], fill=(104, 100, 92), width=2 * UP)
        d.line([(k * 10 * px, 0), (k * 10 * px, h)], fill=(104, 100, 92), width=2 * UP)
    for _ in range(5):  # oil stains
        x, y, r = rng.uniform(0, w), rng.uniform(0, h), rng.uniform(4, 14) * UP
        d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=(126, 128, 128))
    img = grime(img, rng, amount=0.25)
    if level:
        img = damage(img, rng, level)
    return img.resize((256, 256), Image.LANCZOS)


def metal(rng):
    w = h = 128 * UP
    img = Image.new("RGB", (w, h), (116, 126, 136))
    d = ImageDraw.Draw(img)
    for _ in range(60):
        x, y = rng.uniform(0, w), rng.uniform(0, h)
        d.line([(x, y), (x + rng.uniform(-10, 10) * UP, y + rng.uniform(-3, 3) * UP)], fill=(160, 168, 176), width=UP)
    return grime(img, rng, amount=0.2).resize((128, 128), Image.LANCZOS)


def helipad(rng):
    w = h = 256 * UP
    img = Image.new("RGB", (w, h), (78, 82, 86))
    d = ImageDraw.Draw(img)
    c, r = w / 2, w * 0.46
    d.ellipse([c - r, c - r, c + r, c + r], outline=(225, 225, 220), width=10 * UP)
    d.ellipse([c - r * 0.8, c - r * 0.8, c + r * 0.8, c + r * 0.8], outline=(220, 180, 40), width=5 * UP)
    bar, tall, wide = w * 0.06, w * 0.42, w * 0.3
    for x in (c - wide / 2, c + wide / 2 - bar):  # the H
        d.rectangle([x, c - tall / 2, x + bar, c + tall / 2], fill=(230, 230, 225))
    d.rectangle([c - wide / 2, c - bar / 2, c + wide / 2, c + bar / 2], fill=(230, 230, 225))
    return grime(img, rng, amount=0.2).resize((256, 256), Image.LANCZOS)


def emblem(rng):
    """The faction's mark: a gold chevron on dark blue, as on its vehicles."""
    w = h = 128 * UP
    img = Image.new("RGB", (w, h), (28, 34, 64))
    d = ImageDraw.Draw(img)
    d.rectangle([4 * UP, 4 * UP, w - 4 * UP, h - 4 * UP], outline=(225, 225, 225), width=3 * UP)
    c = w / 2
    d.polygon([(c - 0.32 * w, c + 0.2 * w), (c, c - 0.26 * w), (c + 0.32 * w, c + 0.2 * w), (c + 0.2 * w, c + 0.2 * w),
               (c, c - 0.08 * w), (c - 0.2 * w, c + 0.2 * w)], fill=(236, 200, 40))
    return img.resize((128, 128), Image.LANCZOS)


def main():
    out = sys.argv[1]
    rng = np.random.default_rng(21)
    images = {
        "eucc_facade": facade(rng), "eucc_facade_n": facade(rng, night=True),
        "eucc_facade_d": facade(rng, level=1), "eucc_facade_dn": facade(rng, night=True, level=1),
        "eucc_facade_e": facade(rng, level=2), "eucc_facade_en": facade(rng, night=True, level=2),
        "eucc_roof": roof(rng), "eucc_roof_d": roof(rng, 1), "eucc_roof_e": roof(rng, 2),
        "eucc_bay": bay(rng), "eucc_bay_d": bay(rng, 1), "eucc_bay_e": bay(rng, 2),
        "eucc_door": door(rng), "eucc_door_d": door(rng, 1), "eucc_door_e": door(rng, 2),
        "eucc_pad": pad(rng), "eucc_pad_e": pad(rng, 2),
        "eucc_metal": metal(rng), "eucc_helipad": helipad(rng), "eucc_emblem": emblem(rng),
    }
    for name, image in images.items():
        if name not in ("eucc_emblem", "eucc_helipad"):
            # The game's sunlight is warm and dim: paint lighter and a little cooler than seems right here.
            arr = np.asarray(image, float) * np.array([1.26, 1.3, 1.36])
            image = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        image.save(os.path.join(out, name + ".tga"))
    print(f"painted {len(images)} textures")


if __name__ == "__main__":
    main()

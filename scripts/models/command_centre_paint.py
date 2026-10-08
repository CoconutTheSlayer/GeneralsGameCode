"""Paints the European Command Centre's textures, in two steps that command_centre.py runs (Python 3 and
Pillow):

    tiles OUT_DIR             small tiling surfaces, painted in the game's style, that Blender projects onto
                              the model: plaster panels, corrugated metal, roof deck, the blue hangar door,
                              dome panels, steel trim; and the pad's and the emblem's own textures
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked (colour, ambient occlusion,
                              where the windows are): grime and weathering on top, and its damaged,
                              wrecked and night versions (lit windows)
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


def panels(colour, rng, size=256, step=64, seam=(92, 90, 84), rivets=True, light=(220, 216, 206)):
    """Square panels with seams, lit top edges and rivets."""
    w = size * UP
    img = Image.new("RGB", (w, w), colour)
    d = ImageDraw.Draw(img)
    s = step * UP
    for k in range(0, w + 1, s):
        d.line([(0, k), (w, k)], fill=seam, width=2 * UP)
        d.line([(0, k + 2 * UP), (w, k + 2 * UP)], fill=light, width=UP)
        d.line([(k, 0), (k, w)], fill=seam, width=2 * UP)
        if rivets:
            for j in range(0, w, s // 4):
                for x, y in ((k + 3 * UP, j + s // 8), (j + s // 8, k + 5 * UP)):
                    d.ellipse([x - UP, y - UP, x + UP, y + UP], fill=seam)
    return img


def tile_wall(rng):
    return grime(panels((214, 214, 208), rng, seam=(110, 112, 114), light=(236, 236, 232)), rng, amount=0.24, streaks=30, streak_colour=(160, 160, 156)).resize((256, 256), Image.LANCZOS)


def tile_trim(rng):
    return grime(panels((70, 104, 150), rng, step=128, seam=(36, 52, 76), light=(140, 168, 200)), rng, amount=0.2).resize((256, 256), Image.LANCZOS)


def tile_rib(rng):
    """Corrugated metal: ribs across the image's width."""
    w = 256 * UP
    img = Image.new("RGB", (w, w))
    arr = np.zeros((w, w, 3))
    x = np.arange(w) / w * 16 * 2 * math.pi
    shade = 0.78 + 0.22 * np.sin(x)
    arr[:] = (np.array([158, 168, 178])[None, None, :] * shade[None, :, None])
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 64 * UP):  # overlaps of the sheets
        d.line([(0, k), (w, k)], fill=(110, 118, 126), width=UP)
    return grime(img, rng, amount=0.25).resize((256, 256), Image.LANCZOS)


def tile_deck(rng):
    return grime(panels((104, 106, 108), rng, step=128, seam=(70, 72, 74), rivets=False, light=(124, 126, 128)), rng,
                 amount=0.35).resize((256, 256), Image.LANCZOS)


def tile_door(rng):
    w = 256 * UP
    img = Image.new("RGB", (w, w), (66, 96, 136))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 32 * UP):
        d.rectangle([0, k, w, k + 32 * UP], fill=(66 + (k // (32 * UP)) % 2 * 10, 96, 136))
        d.line([(0, k), (w, k)], fill=(30, 44, 62), width=2 * UP)
        d.line([(0, k + 2 * UP), (w, k + 2 * UP)], fill=(130, 160, 196), width=UP)
    for x in range(0, w, 64 * UP):
        d.rectangle([x + 20 * UP, 10 * UP, x + 44 * UP, 20 * UP], fill=(150, 176, 200))  # small windows
    return grime(img, rng, amount=0.2).resize((256, 256), Image.LANCZOS)


def tile_dome(rng):
    return grime(panels((222, 224, 226), rng, step=64, seam=(170, 172, 176), rivets=False, light=(240, 240, 240)), rng,
                 amount=0.15).resize((256, 256), Image.LANCZOS)


def tile_metal(rng):
    img = Image.new("RGB", (128 * UP, 128 * UP), (120, 126, 134))
    d = ImageDraw.Draw(img)
    for _ in range(40):
        x, y = rng.uniform(0, 128 * UP), rng.uniform(0, 128 * UP)
        d.line([(x, y), (x + rng.uniform(-8, 8) * UP, y + rng.uniform(-2, 2) * UP)], fill=(168, 174, 180), width=UP)
    return grime(img, rng, amount=0.25).resize((128, 128), Image.LANCZOS)


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


def compose(bake_dir, out):
    """The building's texture from Blender's bakes, and its versions."""
    rng = np.random.default_rng(7)
    colour = np.asarray(Image.open(os.path.join(bake_dir, "colour.png")).convert("RGB"), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "occlusion.png")).convert("L"), float)[..., None] / 255.0
    windows = np.asarray(Image.open(os.path.join(bake_dir, "windows.png")).convert("L"), float)[..., None] / 255.0
    h, w = ao.shape[:2]
    stains = (tiling_noise(w, h, 10, rng) * 0.6 + tiling_noise(w, h, 30, rng) * 0.4)[..., None]
    lit = colour * (0.42 + 0.58 * ao) * (0.86 + 0.24 * stains)
    # The game's light is warm and dim: paint a little lighter and cooler.
    lit *= np.array([1.16, 1.2, 1.3])
    day = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    versions = {"": day, "_d": damage(day, rng, 1), "_e": damage(day, rng, 2)}
    for suffix, img in versions.items():
        img.save(os.path.join(out, f"eucc_building{suffix}.tga"))
        # At night the building darkens and its windows light up.
        arr = np.asarray(img, float) * 0.8
        glow = windows * (1.0 if suffix != "_e" else 0.35)
        arr = arr * (1 - glow) + np.array(GLASS_LIT) * glow
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(out, f"eucc_building{suffix}n.tga"))
    print("composed the building's textures")


def main():
    rng = np.random.default_rng(21)
    if sys.argv[1] == "tiles":
        out = sys.argv[2]
        images = {"tile_wall": tile_wall(rng), "tile_trim": tile_trim(rng), "tile_rib": tile_rib(rng),
                  "tile_deck": tile_deck(rng), "tile_door": tile_door(rng), "tile_dome": tile_dome(rng),
                  "tile_metal": tile_metal(rng), "eucc_pad": pad(rng), "eucc_pad_e": pad(rng, 2),
                  "eucc_emblem": emblem(rng)}
        for name, image in images.items():
            image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
        print(f"painted {len(images)} tiles")
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

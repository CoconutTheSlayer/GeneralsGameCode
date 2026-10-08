"""Paints the European SAMP/T Battery's textures, in two steps that samp_battery.py runs (Python 3 and
Pillow); trim, sandbags, crates and hazard stripes are the Command Centre's (command_centre_paint.py), so
the base looks like one army:

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model: packed earth for
                              the berm, poured concrete, the launcher's canisters, steel and turntable, the
                              radar's array face, the generator's olive paint, cable drums; the emblem
    compose BAKE_DIR OUT_DIR  the battery's texture from what Blender baked (colour, ambient occlusion,
                              windows, height): grime on top, its damaged, wrecked and night versions; and
                              the ground: an earth patch with a ragged edge cut out by its alpha

compose() and paint_ground() are shared with the Artillery Bastion and the Funds Office.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import command_centre_paint as cc  # noqa: E402
from command_centre_paint import UP, damage, grime, panels, tiling_noise  # noqa: E402

PREFIX = "eusa"
GLASS_LIT = cc.GLASS_LIT


def tile_steel(rng):
    """The launcher's blue-grey steel: large panels, lighter than the trim, so it reads from far away."""
    return grime(panels((150, 164, 178), rng, step=128, seam=(78, 90, 104), light=(200, 210, 220)), rng,
                 amount=0.18).resize((256, 256), Image.LANCZOS)


def tile_canister(rng):
    """Missile canisters seen from the side: ribbed stiffeners across, a darker frame at the ends."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (146, 160, 174))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 32 * UP):
        d.rectangle([k, 0, k + 4 * UP, w], fill=(104, 118, 132))
        d.line([(k + 5 * UP, 0), (k + 5 * UP, w)], fill=(176, 188, 200), width=UP)
    for y in (0, w // 2):
        d.line([(0, y), (w, y)], fill=(60, 68, 78), width=2 * UP)
    return grime(img, rng, amount=0.2).resize((128, 128), Image.LANCZOS)


def tile_turntable(rng):
    """The turntable's deck: chequer plate in steel blue-grey."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (104, 116, 128))
    d = ImageDraw.Draw(img)
    for y in range(0, w, 8 * UP):
        for x in range((y // (8 * UP)) % 2 * 4 * UP, w, 8 * UP):
            d.line([(x, y + UP), (x + 3 * UP, y + 4 * UP)], fill=(140, 152, 164), width=UP)
    return grime(img, rng, amount=0.3).resize((128, 128), Image.LANCZOS)


EARTH = (192, 160, 118)


def tile_earth(rng, colour=EARTH):
    """Packed sandy earth: blotches, pebbles, a few rain runnels down the slope."""
    w = 128 * UP
    arr = np.ones((w, w, 3)) * np.array(colour, float)
    arr *= (0.82 + 0.3 * tiling_noise(w, w, 8, rng))[..., None]
    arr *= (0.9 + 0.12 * tiling_noise(w, w, 24, rng))[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(260):
        x, y, r = rng.uniform(0, w), rng.uniform(0, w), rng.uniform(0.6, 2.2) * UP
        tone = rng.uniform(0.6, 1.15)
        d.ellipse([x - r, y - r * 0.8, x + r, y + r * 0.8], fill=tuple(int(c * tone) for c in colour))
    return grime(img, rng, amount=0.15, streaks=14, streak_colour=tuple(int(c * 0.78) for c in colour)
                 ).resize((128, 128), Image.LANCZOS)


def tile_concrete(rng):
    """Light poured concrete with formwork lines."""
    return grime(panels((186, 184, 176), rng, step=64, seam=(132, 130, 124), rivets=False, light=(206, 204, 198)),
                 rng, amount=0.3).resize((128, 128), Image.LANCZOS)


def tile_array(rng):
    """The radar's face: a grid of dark square elements in a lighter frame (the whole tile is one face)."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (70, 78, 88))
    d = ImageDraw.Draw(img)
    n = 10
    cell = (w - 8 * UP) / n
    for i in range(n):
        for j in range(n):
            x, y = 4 * UP + i * cell, 4 * UP + j * cell
            tone = int(rng.uniform(-6, 6))
            d.rectangle([x + UP, y + UP, x + cell - UP, y + cell - UP], fill=(46 + tone, 54 + tone, 64 + tone))
            d.line([(x + UP, y + UP), (x + cell - UP, y + UP)], fill=(104, 114, 126), width=UP)
    d.rectangle([0, 0, w - 1, w - 1], outline=(120, 130, 140), width=4 * UP)
    return grime(img, rng, amount=0.12).resize((128, 128), Image.LANCZOS)


def tile_olive(rng):
    """Olive-drab painted steel with panel seams (the generator)."""
    return grime(panels((112, 122, 88), rng, step=64, seam=(70, 78, 56), light=(146, 156, 118)), rng,
                 amount=0.25).resize((128, 128), Image.LANCZOS)


def tile_drum(rng):
    """Black cable wound on a drum."""
    w = 64 * UP
    img = Image.new("RGB", (w, w), (40, 40, 42))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 3 * UP):
        d.line([(0, k), (w, k + UP)], fill=(64, 64, 66), width=UP)
    return grime(img, rng, amount=0.2).resize((64, 64), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(31)
    images = {"tile_trim": cc.tile_trim(rng), "tile_metal": cc.tile_metal(rng), "tile_sandbag": cc.tile_sandbag(rng),
              "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng), "tile_crate": cc.tile_crate(rng),
              "tile_steel": tile_steel(rng), "tile_canister": tile_canister(rng), "tile_turntable": tile_turntable(rng),
              "tile_earth": tile_earth(rng), "tile_concrete": tile_concrete(rng), "tile_array": tile_array(rng),
              "tile_olive": tile_olive(rng), "tile_drum": tile_drum(rng), f"{PREFIX}_emblem": cc.emblem(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


def compose(bake_dir, out, prefix):
    """The building's texture from Blender's bakes, and its versions (as the Command Centre's)."""
    rng = np.random.default_rng(7)
    colour = np.asarray(Image.open(os.path.join(bake_dir, "colour.png")).convert("RGB"), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "occlusion.png")).convert("L"), float)[..., None] / 255.0
    windows = np.asarray(Image.open(os.path.join(bake_dir, "windows.png")).convert("L"), float)[..., None] / 255.0
    height = np.asarray(Image.open(os.path.join(bake_dir, "height.png")).convert("L"), float)[..., None] / 255.0
    h, w = ao.shape[:2]
    stains = (tiling_noise(w, h, 10, rng) * 0.6 + tiling_noise(w, h, 30, rng) * 0.4)[..., None]
    lit = colour * (0.45 + 0.55 * ao) * (0.86 + 0.24 * stains) * (0.8 + 0.32 * np.sqrt(height))
    lit *= np.array([1.16, 1.2, 1.3])
    day = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    versions = {"": day, "_d": damage(day, rng, 1), "_e": damage(day, rng, 2)}
    for suffix, img in versions.items():
        img.save(os.path.join(out, f"{prefix}_building{suffix}.tga"))
        arr = np.asarray(img, float) * 0.8
        glow = windows * (1.0 if suffix != "_e" else 0.35)
        arr = arr * (1 - glow) + np.array(GLASS_LIT) * glow
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(out, f"{prefix}_building{suffix}n.tga"))
    print("composed the building's textures")


def paint_ground(bake_dir, out, prefix, half, rng, inside, marks, base=None, size=1024, ragged=1.0):
    """Ground of +-half units painted as one picture with an alpha: the earth (or `base`, an image of
    `size`), then marks(draw, pixel, scale); kept where inside(x, y) (arrays of units, +Y up) is above 0 plus
    a ragged noise (times `ragged`), so the outline is irregular and speckled like scattered gravel. Darkened where the
    building's shadow lies (its baked occlusion). Writes <prefix>_pad.tga and _pad_e.tga (RGBA)."""
    w = size
    if base is None:
        tile = tile_earth(rng, (204, 168, 122)).resize((w // 4, w // 4))
        base = Image.new("RGB", (w, w))
        for x in range(0, w, tile.width):
            for y in range(0, w, tile.height):
                base.paste(tile, (x, y))
    img = base.copy()
    scale = w / (2 * half)

    def pixel(x, y):
        return (x + half) * scale, (half - y) * scale
    marks(ImageDraw.Draw(img), pixel, scale)
    arr = np.asarray(img, float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((w, w)), float)
    arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.14, 1.12, 1.1])
    ys, xs = np.mgrid[0:w, 0:w]
    ux, uy = xs / scale - half, half - ys / scale
    edge = inside(ux, uy) + ((tiling_noise(w, w, 9, rng) - 0.5) * 2.4 + (rng.random((w, w)) - 0.5) * 1.6) * ragged
    alpha = np.where(edge > 0, 255, 0).astype(np.uint8)
    day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    for suffix, img in (("", day), ("_e", damage(day, rng, 2))):
        rgba = img.convert("RGBA")
        rgba.putalpha(Image.fromarray(alpha))
        rgba.save(os.path.join(out, f"{prefix}_pad{suffix}.tga"))


PAD_HALF = 14.0


def battery_inside(x, y):
    """A rounded square of ground: the berm's circle and the clutter in the corners."""
    return 13.4 - (np.abs(x) ** 4 + np.abs(y) ** 4) ** 0.25


def battery_marks(d, pixel, scale):
    """The floor inside the berm, tyre tracks through the opening, cables from the generator."""
    floor, track, cable = (178, 156, 120), (156, 136, 104), (36, 36, 38)
    a, b = pixel(-8.8, 8.8), pixel(8.8, -8.8)
    d.ellipse([a[0], a[1], b[0], b[1]], fill=floor)
    for x in (-1.9, 1.9):                                    # tyre tracks out through the opening
        for k in range(3):
            p, q = pixel(x - 0.5 + k * 0.4, -7.0), pixel(x - 0.1 + k * 0.4, -14.5)
            d.rectangle([p[0], p[1], q[0], q[1]], fill=track)
    def wire(points, width=0.18):
        d.line([pixel(*p) for p in points], fill=cable, width=max(2, int(width * scale)), joint="curve")
    wire([(7.4, -10.2), (5.0, -10.6), (2.2, -9.4), (0.4, -11.6), (0.0, -7.0), (0.6, -5.4)])
    wire([(8.0, -9.0), (9.4, -6.0), (11.6, -2.0), (12.4, 3.0), (11.6, 6.4), (10.2, 8.4)])
    wire([(-8.6, 9.6), (-6.0, 11.6), (-1.0, 12.6), (4.0, 11.6), (6.0, 10.0)], 0.14)


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        compose(sys.argv[2], sys.argv[3], PREFIX)
        paint_ground(sys.argv[2], sys.argv[3], PREFIX, PAD_HALF, np.random.default_rng(5), battery_inside,
                     battery_marks)


if __name__ == "__main__":
    main()

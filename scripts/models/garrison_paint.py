"""Paints the European Garrison's textures, in two steps that garrison.py runs (Python 3 and Pillow); it
shares the Command Centre's painting (command_centre_paint.py), so the base looks like one army:

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model (plaster,
                              corrugated roofs, steel trim, the blue roller door...); the pad's and the
                              emblem's own
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked (colour, ambient occlusion,
                              windows, height): grime on top, and its damaged, wrecked and night versions
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_centre_paint import (UP, GLASS_LIT, damage, emblem, grime, pad, tile_deck,  # noqa: E402
                                  tile_door, tile_grille, tile_hazard, tile_metal, tile_sandbag, tile_trim,
                                  tile_wall, tiling_noise)

PREFIX = "eubr"


def tile_roof(rng):
    """Steel blue-grey corrugated roofing: ribs across the image's width."""
    import math
    w = 256 * UP
    x = np.arange(w) / w * 16 * 2 * math.pi
    shade = 0.8 + 0.2 * np.sin(x)
    arr = np.zeros((w, w, 3))
    arr[:] = np.array([128, 142, 158])[None, None, :] * shade[None, :, None]
    img = Image.fromarray(arr.astype(np.uint8))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 64 * UP):
        d.line([(0, k), (w, k)], fill=(86, 96, 108), width=UP)
    return grime(img, rng, amount=0.25, streaks=24, streak_colour=(92, 100, 110)).resize((256, 256), Image.LANCZOS)


PAD_SIZE = 1024
PAD_X, PAD_Y = (-56.0, 56.0), (-46.0, 46.0)


def pad_pixel(x, y):
    return ((x - PAD_X[0]) / (PAD_X[1] - PAD_X[0]) * PAD_SIZE * UP,
            (1 - (y - PAD_Y[0]) / (PAD_Y[1] - PAD_Y[0])) * PAD_SIZE * UP)


def rect(d, x0, y0, x1, y1, **kw):
    a, b = pad_pixel(x0, y0), pad_pixel(x1, y1)
    d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], **kw)


def paint_pad(bake_dir, out, rng):
    """The pad as one picture: concrete slabs, the parade square with its markings, the marching lane out
    of the gate, darker where the buildings shade it."""
    w = PAD_SIZE * UP
    tile = pad(rng).resize((256 * UP, 256 * UP))
    img = Image.new("RGB", (w, w))
    for x in range(0, w, tile.width):
        for y in range(0, w, tile.height):
            img.paste(tile, (x, y))
    d = ImageDraw.Draw(img)
    yellow, white = (214, 176, 52), (226, 224, 214)
    unit = UP * PAD_SIZE / 112
    rect(d, -30, -15, 30, 15, outline=white, width=int(0.6 * unit))           # the parade square
    for x in range(-24, 25, 8):                                              # where the squads form up
        for y in (-9, 0, 9):
            rect(d, x - 0.5, y - 0.5, x + 0.5, y + 0.5, fill=white)
    for x in range(20, 56, 5):                                               # the lane out of the gate
        rect(d, x, -0.4, x + 2.6, 0.4, fill=yellow)
    for y in (-6.5, 6.5):
        rect(d, 36, y - 0.3, 56, y + 0.3, fill=white)
    cx, cy = pad_pixel(-14, 0)                                               # the faction's mark
    # The texture is stretched over a footprint wider than deep: keep the mark square on the ground.
    r, q = 6 * unit, 6 * UP * PAD_SIZE / (PAD_Y[1] - PAD_Y[0])
    d.rectangle([cx - r, cy - q, cx + r, cy + q], fill=(28, 34, 64), outline=white, width=int(0.5 * unit))
    d.polygon([(cx + r * 0.4, cy - q * 0.65), (cx - r * 0.55, cy), (cx + r * 0.4, cy + q * 0.65), (cx + r * 0.4, cy + q * 0.42),
               (cx - r * 0.15, cy), (cx + r * 0.4, cy - q * 0.42)], fill=(236, 200, 40))
    for _ in range(40):
        x, y = pad_pixel(rng.uniform(-54, 54), rng.uniform(-44, 44))
        rr = rng.uniform(0.5, 2) * unit
        d.ellipse([x - rr, y - rr * 0.6, x + rr, y + rr * 0.6], fill=(118, 118, 112))
    arr = np.asarray(img.resize((PAD_SIZE, PAD_SIZE), Image.LANCZOS), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((PAD_SIZE, PAD_SIZE)), float)
    arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
    day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    day.save(os.path.join(out, f"{PREFIX}_pad.tga"))
    damage(day, rng, 2).save(os.path.join(out, f"{PREFIX}_pad_e.tga"))


def compose(bake_dir, out):
    rng = np.random.default_rng(13)
    load = lambda name, mode: np.asarray(Image.open(os.path.join(bake_dir, name)).convert(mode), float)  # noqa: E731
    colour = load("colour.png", "RGB")
    ao = load("occlusion.png", "L")[..., None] / 255.0
    windows = load("windows.png", "L")[..., None] / 255.0
    height = load("height.png", "L")[..., None] / 255.0
    h, w = ao.shape[:2]
    stains = (tiling_noise(w, h, 10, rng) * 0.6 + tiling_noise(w, h, 30, rng) * 0.4)[..., None]
    lit = colour * (0.42 + 0.58 * ao) * (0.86 + 0.24 * stains) * (0.78 + 0.36 * np.sqrt(height))
    lit *= np.array([1.16, 1.2, 1.3])
    day = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    # The wreck keeps a little more of its paint than the shared damage leaves, to read at a distance.
    versions = {"": day, "_d": damage(day, rng, 1), "_e": Image.blend(damage(day, rng, 2), day, 0.3)}
    for suffix, img in versions.items():
        img.save(os.path.join(out, f"{PREFIX}_building{suffix}.tga"))
        arr = np.asarray(img, float) * 0.8
        lights = windows * (1.0 if suffix != "_e" else 0.35)
        arr = arr * (1 - lights) + np.array(GLASS_LIT) * lights
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(out, f"{PREFIX}_building{suffix}n.tga"))
    paint_pad(bake_dir, out, rng)
    print("composed the garrison's textures")


def main():
    rng = np.random.default_rng(29)
    if sys.argv[1] == "tiles":
        out = sys.argv[2]
        images = {"tile_wall": tile_wall(rng), "tile_trim": tile_trim(rng), "tile_roof": tile_roof(rng),
                  "tile_deck": tile_deck(rng), "tile_door": tile_door(rng), "tile_metal": tile_metal(rng),
                  "tile_hazard": tile_hazard(rng), "tile_grille": tile_grille(rng), "tile_sandbag": tile_sandbag(rng),
                  f"{PREFIX}_emblem": emblem(rng)}
        for name, image in images.items():
            image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
        print(f"painted {len(images)} tiles")
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

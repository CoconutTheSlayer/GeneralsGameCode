"""Paints the European Fusion Plant's textures, in two steps that fusion_plant.py runs (Python 3 and Pillow);
it shares the Command Centre's painting (command_centre_paint.py), so the base looks like one army:

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model (plaster, steel
                              trim, the dome's steel panels, fan grilles...); the pad's and emblem's own
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked (colour, ambient occlusion,
                              windows, coolant channels, height): grime on top, and its damaged, wrecked and
                              night versions (lit windows, glowing coolant)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_centre_paint import (UP, GLASS_LIT, damage, emblem, fence_texture, grime, pad, panels,  # noqa: E402
                                  tile_deck, tile_door, tile_grille, tile_hazard, tile_metal, tile_rib,
                                  tile_trim, tile_wall, tiling_noise)

PREFIX = "eupp"
GLOW_DAY, GLOW_NIGHT = (104, 198, 255), (150, 232, 255)


def tile_steel(rng):
    """The dome's steel blue-grey panels."""
    return grime(panels((138, 152, 168), rng, step=64, seam=(76, 86, 100), rivets=True, light=(184, 194, 206)), rng,
                 amount=0.22, streaks=20, streak_colour=(78, 86, 96)).resize((256, 256), Image.LANCZOS)


def tile_ceramic(rng):
    """Brown glazed insulators: rings."""
    w = 64 * UP
    img = Image.new("RGB", (w, w), (132, 70, 44))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 8 * UP):
        d.rectangle([0, k, w, k + 3 * UP], fill=(92, 46, 28))
        d.line([(0, k + 4 * UP), (w, k + 4 * UP)], fill=(196, 126, 92), width=UP)
    return grime(img, rng, amount=0.15).resize((64, 64), Image.LANCZOS)


PAD_SIZE = 512
PAD_X, PAD_Y = (-23.0, 23.0), (-31.0, 31.0)


def pad_pixel(x, y):
    """A point of the footprint on the pad's texture (seen from above, +X to the right)."""
    return ((x - PAD_X[0]) / (PAD_X[1] - PAD_X[0]) * PAD_SIZE * UP,
            (1 - (y - PAD_Y[0]) / (PAD_Y[1] - PAD_Y[0])) * PAD_SIZE * UP)


def rect(d, x0, y0, x1, y1, **kw):
    a, b = pad_pixel(x0, y0), pad_pixel(x1, y1)
    d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], **kw)


def paint_pad(bake_dir, out, rng):
    """The pad as one picture: concrete slabs, a walkway to the reactor's door, hazard edging round the
    transformer yard, darker where the buildings shade it."""
    w = PAD_SIZE * UP
    tile = pad(rng).resize((256 * UP, 256 * UP))
    img = Image.new("RGB", (w, w))
    for x in range(0, w, tile.width):
        for y in range(0, w, tile.height):
            img.paste(tile, (x, y))
    d = ImageDraw.Draw(img)
    yellow, white = (214, 176, 52), (226, 224, 214)
    unit = UP * PAD_SIZE / 50
    for x in range(10, 22, 3):                      # zebra walkway from the door to the front edge
        rect(d, x, 1.5, x + 1.5, 8.5, fill=white)
    rect(d, 8.5, -28.5, 21.5, -12.5, outline=yellow, width=int(0.8 * unit))   # the transformer yard
    for y in range(-27, -13, 2):
        rect(d, 8.5, y, 9.3, y + 1, fill=(34, 32, 30))
    rect(d, -21.5, -29.5, 6.5, -14.5, outline=white, width=int(0.4 * unit))   # the cooling units' bay
    for _ in range(20):
        x, y = pad_pixel(rng.uniform(-22, 22), rng.uniform(-30, 30))
        rr = rng.uniform(0.5, 2) * unit
        d.ellipse([x - rr, y - rr * 0.6, x + rr, y + rr * 0.6], fill=(118, 118, 112))
    arr = np.asarray(img.resize((PAD_SIZE, PAD_SIZE), Image.LANCZOS), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((PAD_SIZE, PAD_SIZE)), float)
    arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
    day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    day.save(os.path.join(out, f"{PREFIX}_pad.tga"))
    damage(day, rng, 2).save(os.path.join(out, f"{PREFIX}_pad_e.tga"))


def compose(bake_dir, out):
    rng = np.random.default_rng(11)
    load = lambda name, mode: np.asarray(Image.open(os.path.join(bake_dir, name)).convert(mode), float)  # noqa: E731
    colour = load("colour.png", "RGB")
    ao = load("occlusion.png", "L")[..., None] / 255.0
    windows = load("windows.png", "L")[..., None] / 255.0
    glow = load("glow.png", "L")[..., None] / 255.0
    height = load("height.png", "L")[..., None] / 255.0
    h, w = ao.shape[:2]
    stains = (tiling_noise(w, h, 10, rng) * 0.6 + tiling_noise(w, h, 30, rng) * 0.4)[..., None]
    lit = colour * (0.42 + 0.58 * ao) * (0.86 + 0.24 * stains) * (0.78 + 0.36 * np.sqrt(height))
    lit *= np.array([1.16, 1.2, 1.3])
    # The coolant glows a little even by day: it is not darkened by the occlusion.
    lit = lit * (1 - glow) + np.array(GLOW_DAY) * glow * (0.8 + 0.2 * ao)
    day = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    # The wreck keeps a little more of its paint than the shared damage leaves, to read at a distance.
    versions = {"": day, "_d": damage(day, rng, 1), "_e": Image.blend(damage(day, rng, 2), day, 0.3)}
    for suffix, img in versions.items():
        img.save(os.path.join(out, f"{PREFIX}_building{suffix}.tga"))
        arr = np.asarray(img, float) * 0.8
        lights = windows * (1.0 if suffix != "_e" else 0.35)
        arr = arr * (1 - lights) + np.array(GLASS_LIT) * lights
        coolant = glow * {"": 1.0, "_d": 0.8, "_e": 0.25}[suffix]
        arr = arr * (1 - coolant) + np.array(GLOW_NIGHT) * coolant
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(out, f"{PREFIX}_building{suffix}n.tga"))
    paint_pad(bake_dir, out, rng)
    print("composed the fusion plant's textures")


def main():
    rng = np.random.default_rng(23)
    if sys.argv[1] == "tiles":
        out = sys.argv[2]
        images = {"tile_wall": tile_wall(rng), "tile_trim": tile_trim(rng), "tile_rib": tile_rib(rng),
                  "tile_deck": tile_deck(rng), "tile_door": tile_door(rng), "tile_steel": tile_steel(rng),
                  "tile_metal": tile_metal(rng), "tile_hazard": tile_hazard(rng), "tile_grille": tile_grille(rng),
                  "tile_ceramic": tile_ceramic(rng),
                  f"{PREFIX}_emblem": emblem(rng), f"{PREFIX}_fence": fence_texture()}
        for name, image in images.items():
            image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
        print(f"painted {len(images)} tiles")
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

"""Paints the European SAMP/T Battery's textures, in two steps that samp_battery.py runs (Python 3 and
Pillow); the surfaces are the Command Centre's (command_centre_paint.py), so the base looks like one army:

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model: the Command
                              Centre's plaster, trim, deck, door, sandbags, hazard stripes and grilles, and
                              the launcher's own canisters and turntable; the emblem
    compose BAKE_DIR OUT_DIR  the battery's texture from what Blender baked (colour, ambient occlusion,
                              windows, height): grime on top, its damaged, wrecked and night versions, and
                              the pad, painted as one picture

compose() and paint_square_pad() are shared with the Artillery Bastion (bastion_paint.py).
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


def tiles(out):
    rng = np.random.default_rng(31)
    images = {"tile_wall": cc.tile_wall(rng), "tile_trim": cc.tile_trim(rng), "tile_deck": cc.tile_deck(rng),
              "tile_door": cc.tile_door(rng), "tile_metal": cc.tile_metal(rng), "tile_sandbag": cc.tile_sandbag(rng),
              "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng), "tile_crate": cc.tile_crate(rng),
              "tile_steel": tile_steel(rng), "tile_canister": tile_canister(rng), "tile_turntable": tile_turntable(rng),
              f"{PREFIX}_emblem": cc.emblem(rng)}
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


def paint_square_pad(bake_dir, out, prefix, half, rng, marks):
    """A square pad of +-half units, painted as one picture: concrete slabs, then marks(draw, pixel, scale),
    darkened where the building's shadow lies (its baked occlusion). Writes <prefix>_pad.tga and _pad_e.tga."""
    size = 512
    w = size * UP
    tile = cc.pad(rng).resize((256 * UP, 256 * UP))
    img = Image.new("RGB", (w, w))
    for x in range(0, w, tile.width):
        for y in range(0, w, tile.height):
            img.paste(tile, (x, y))
    scale = w / (2 * half)   # pixels per unit

    def pixel(x, y):
        """Seen from above, +X to the right, +Y up."""
        return (x + half) * scale, (half - y) * scale
    marks(ImageDraw.Draw(img), pixel, scale)
    arr = np.asarray(img.resize((size, size), Image.LANCZOS), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((size, size)), float)
    arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
    day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    day.save(os.path.join(out, f"{prefix}_pad.tga"))
    damage(day, rng, 2).save(os.path.join(out, f"{prefix}_pad_e.tga"))


PAD_HALF = 13.0


def battery_marks(d, pixel, scale):
    """Yellow hazard corners, a walkway to the cabin and dashes round the plinth."""
    yellow, white = (214, 176, 52), (226, 224, 214)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a, b = pixel(sx * 11.6, sy * 11.6), pixel(sx * 9.4, sy * 11.6)
            d.line([a, b], fill=yellow, width=int(0.6 * scale))
            a, b = pixel(sx * 11.6, sy * 11.6), pixel(sx * 11.6, sy * 9.4)
            d.line([a, b], fill=yellow, width=int(0.6 * scale))
    for y in range(-7, 2, 2):
        a, b = pixel(9.6, y), pixel(11.4, y + 0.9)
        d.rectangle([a[0], b[1], b[0], a[1]], fill=white)


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        compose(sys.argv[2], sys.argv[3], PREFIX)
        paint_square_pad(sys.argv[2], sys.argv[3], PREFIX, PAD_HALF, np.random.default_rng(5), battery_marks)


if __name__ == "__main__":
    main()

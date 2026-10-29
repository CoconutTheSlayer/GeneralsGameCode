"""Paints the European Forward Outpost's textures, in two steps that outpost.py runs (Python 3 and Pillow),
with the Command Centre's trim, doors, crates, sandbags and hazard stripes, the SAMP/T Battery's concrete,
steel and olive paint, and the Artillery Bastion's cast slabs, so the base looks like one army:

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model; its own are the
                              medical container's white corrugated steel and the tent's canvas; and the emblem
    compose BAKE_DIR OUT_DIR  the outpost's texture from what Blender baked, its damaged, wrecked and night
                              versions, and the ground: a gravel patch (cut out by its alpha) with hazard
                              chevrons before the door and tyre tracks
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import bastion_paint as fb  # noqa: E402
import command_centre_paint as cc  # noqa: E402
import samp_battery_paint as sa  # noqa: E402
from command_centre_paint import UP, grime  # noqa: E402

PREFIX = "euop"
PAD_HALF = 20.0


def tile_container(rng):
    """White corrugated container steel: vertical ribs, a lit edge on each."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (226, 226, 220))
    d = ImageDraw.Draw(img)
    for x in range(0, w, 16 * UP):
        d.rectangle([x, 0, x + 5 * UP, w], fill=(196, 198, 194))
        d.line([(x + 6 * UP, 0), (x + 6 * UP, w)], fill=(246, 246, 242), width=UP)
    return grime(img, rng, amount=0.18, streaks=16, streak_colour=(176, 170, 156)).resize((128, 128), Image.LANCZOS)


def tile_canvas(rng):
    """Off-white canvas: a coarse weave, seams, dust."""
    w = 128 * UP
    arr = np.ones((w, w, 3)) * np.array((214, 206, 182), float)
    arr *= (0.9 + 0.12 * cc.tiling_noise(w, w, 12, rng))[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 42 * UP):
        d.line([(0, k), (w, k)], fill=(170, 162, 140), width=2 * UP)
    return grime(img, rng, amount=0.2).resize((128, 128), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(53)
    images = {"tile_trim": cc.tile_trim(rng), "tile_door": cc.tile_door(rng), "tile_metal": cc.tile_metal(rng),
              "tile_sandbag": cc.tile_sandbag(rng), "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng),
              "tile_crate": cc.tile_crate(rng), "tile_steel": sa.tile_steel(rng), "tile_olive": sa.tile_olive(rng),
              "tile_concrete": sa.tile_concrete(rng), "tile_slab": fb.tile_slab(rng),
              "tile_container": tile_container(rng), "tile_canvas": tile_canvas(rng), f"{PREFIX}_emblem": cc.emblem(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


def outpost_inside(x, y):
    """A rounded square of gravel round the post, and a lane out of the door."""
    square = 18.6 - (np.abs(x) ** 4 + np.abs(y) ** 4) ** 0.25
    lane = np.minimum(4.5 - np.abs(y), 19.8 - x)
    return np.maximum(square, np.minimum(lane, 3.0))


def outpost_marks(d, pixel, scale):
    """Darker trodden gravel round the walls, hazard chevrons before the door, tyre tracks out of the lane."""
    a, b = pixel(-12.0, 12.0), pixel(12.0, -12.0)
    d.rounded_rectangle([a[0], a[1], b[0], b[1]], radius=3 * scale, fill=(170, 150, 118))
    for x in (2.6, -2.6):
        for k in range(3):
            p, q = pixel(11.0, x - 0.5 + k * 0.35), pixel(20.0, x - 0.2 + k * 0.35)
            d.rectangle([p[0], q[1], q[0], p[1]], fill=(140, 124, 98))
    for k in range(4):                       # chevrons pointing out of the door (+X)
        x = 11.6 + k * 1.3
        pts = [pixel(x, -2.4), pixel(x + 0.9, 0.0), pixel(x, 2.4), pixel(x + 0.55, 2.4), pixel(x + 1.45, 0.0),
               pixel(x + 0.55, -2.4)]
        d.polygon(pts, fill=(214, 176, 52) if k % 2 == 0 else (40, 38, 34))


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        sa.compose(sys.argv[2], sys.argv[3], PREFIX)
        sa.paint_ground(sys.argv[2], sys.argv[3], PREFIX, PAD_HALF, np.random.default_rng(13), outpost_inside,
                        outpost_marks)


if __name__ == "__main__":
    main()

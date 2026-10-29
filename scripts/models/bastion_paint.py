"""Paints the European Artillery Bastion's textures, in two steps that bastion.py runs (Python 3 and Pillow),
with the Command Centre's trim, doors and crates and the SAMP/T Battery's earth and steel
(samp_battery_paint.py):

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model: dark bare concrete
                              with formwork lines and rust streaks, lighter cast slabs, the gun's armour;
                              and the emblem
    compose BAKE_DIR OUT_DIR  the bastion's texture from what Blender baked, its damaged, wrecked and night
                              versions, and the ground: an earth patch round the berms (cut out by its
                              alpha) with a lane to the blast door
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import command_centre_paint as cc  # noqa: E402
import samp_battery_paint as sa  # noqa: E402
from command_centre_paint import UP, grime, panels  # noqa: E402

PREFIX = "eufb"
PAD_HALF = 26.0


def tile_concrete(rng):
    """Dark bare concrete: board-formwork lines, tie holes, rust and rain streaks."""
    w = 256 * UP
    img = Image.new("RGB", (w, w), (112, 114, 112))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 16 * UP):                   # formwork boards
        tone = int(rng.uniform(-8, 8))
        d.rectangle([0, k, w, k + 16 * UP], fill=(112 + tone, 114 + tone, 112 + tone))
        d.line([(0, k), (w, k)], fill=(84, 86, 84), width=UP)
    for x in range(0, w, 64 * UP):                   # tie holes in rows
        for y in range(8 * UP, w, 64 * UP):
            d.ellipse([x + 30 * UP, y - UP * 2, x + 34 * UP, y + UP * 2], fill=(80, 80, 80))
    img = grime(img, rng, amount=0.32, streaks=30, streak_colour=(92, 90, 86))
    d = ImageDraw.Draw(img)
    for _ in range(10):                              # rust streaks from embedded steel
        x, y = rng.uniform(0, w), rng.uniform(0, w * 0.6)
        d.line([(x, y), (x + rng.uniform(-3, 3), y + rng.uniform(w * 0.08, w * 0.25))], fill=(128, 92, 64), width=2 * UP)
    return img.resize((256, 256), Image.LANCZOS)


def tile_slab(rng):
    """Lighter cast concrete for caps, hoods and the deck."""
    return grime(panels((140, 140, 136), rng, step=64, seam=(100, 100, 96), rivets=False, light=(158, 158, 152)),
                 rng, amount=0.3).resize((128, 128), Image.LANCZOS)


def tile_armour(rng):
    """The gun's armour: blue-grey plates with weld seams and bolts."""
    return grime(panels((140, 154, 168), rng, step=96, seam=(72, 84, 98), light=(192, 204, 216)), rng,
                 amount=0.2).resize((256, 256), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(41)
    images = {"tile_trim": cc.tile_trim(rng), "tile_door": cc.tile_door(rng), "tile_metal": cc.tile_metal(rng),
              "tile_sandbag": cc.tile_sandbag(rng), "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng),
              "tile_crate": cc.tile_crate(rng), "tile_steel": sa.tile_steel(rng), "tile_earth": sa.tile_earth(rng),
              "tile_concrete": tile_concrete(rng), "tile_slab": tile_slab(rng), "tile_armour": tile_armour(rng),
              f"{PREFIX}_emblem": cc.emblem(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


PLAN = [(-13.5, -13.0), (13.5, -13.0), (18.5, 0.0), (13.5, 13.0), (-13.5, 13.0), (-18.5, 0.0)]


def bastion_inside(x, y):
    """Within the casemate's plan grown by 8.5 units (the berms reach 7), and the lane to the door."""
    d = np.full(x.shape, -1e9)
    for (ax, ay), (bx, by) in zip(PLAN, PLAN[1:] + PLAN[:1]):
        length = np.hypot(bx - ax, by - ay)
        nx, ny = (by - ay) / length, -(bx - ax) / length
        d = np.maximum(d, (x - ax) * nx + (y - ay) * ny)
    lane = np.minimum(6.5 - np.abs(x), 25.0 - y)
    return np.maximum(8.0 - d, np.minimum(lane, 8.0))


def bastion_marks(d, pixel, scale):
    """A gravel lane to the blast door, tyre tracks."""
    a, b = pixel(-6.0, 25.5), pixel(6.0, 13.0)
    d.rectangle([a[0], a[1], b[0], b[1]], fill=(150, 140, 122))
    for x in (-3.4, 3.4):
        for k in range(3):
            p, q = pixel(x - 0.5 + k * 0.35, 25.5), pixel(x - 0.2 + k * 0.35, 15.6)
            d.rectangle([p[0], p[1], q[0], q[1]], fill=(126, 116, 100))


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        sa.compose(sys.argv[2], sys.argv[3], PREFIX)
        sa.paint_ground(sys.argv[2], sys.argv[3], PREFIX, PAD_HALF, np.random.default_rng(9), bastion_inside,
                        bastion_marks)


if __name__ == "__main__":
    main()

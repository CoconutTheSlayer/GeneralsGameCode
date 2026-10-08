"""Paints the European Artillery Bastion's textures, in two steps that bastion.py runs (Python 3 and Pillow),
with the Command Centre's surfaces and the SAMP/T Battery's steel (samp_battery_paint.py):

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model, and the emblem
    compose BAKE_DIR OUT_DIR  the bastion's texture from what Blender baked, its damaged, wrecked and night
                              versions, and the pad, painted as one picture
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
    """Poured concrete for the glacis: large cast panels, lighter than the plaster's seams."""
    return grime(panels((206, 200, 186), rng, step=128, seam=(132, 126, 114), rivets=False, light=(228, 224, 212)),
                 rng, amount=0.3, streaks=40, streak_colour=(160, 150, 132)).resize((256, 256), Image.LANCZOS)


def tile_armour(rng):
    """The gun's armour: blue-grey plates with weld seams and bolts."""
    return grime(panels((140, 154, 168), rng, step=96, seam=(72, 84, 98), light=(192, 204, 216)), rng,
                 amount=0.2).resize((256, 256), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(41)
    images = {"tile_wall": cc.tile_wall(rng), "tile_trim": cc.tile_trim(rng), "tile_deck": cc.tile_deck(rng),
              "tile_door": cc.tile_door(rng), "tile_metal": cc.tile_metal(rng), "tile_sandbag": cc.tile_sandbag(rng),
              "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng), "tile_crate": cc.tile_crate(rng),
              "tile_steel": sa.tile_steel(rng), "tile_concrete": tile_concrete(rng), "tile_armour": tile_armour(rng),
              f"{PREFIX}_emblem": cc.emblem(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


def bastion_marks(d, pixel, scale):
    """Yellow corner marks, a lane to the ammunition door at the back, tyre marks."""
    yellow, white = (214, 176, 52), (226, 224, 214)
    for sx in (-1, 1):
        for sy in (-1, 1):
            a = pixel(sx * 24.6, sy * 24.6)
            for b in (pixel(sx * 20.0, sy * 24.6), pixel(sx * 24.6, sy * 20.0)):
                d.line([a, b], fill=yellow, width=int(0.8 * scale))
    for y in (-3.6, 3.6):
        a, b = pixel(-25.0, y), pixel(-19.5, y)
        d.line([a, b], fill=yellow, width=int(0.5 * scale))
    for x in range(-25, -19, 2):
        a, b = pixel(x, -2.6), pixel(x + 1.0, 2.6)
        d.rectangle([a[0], b[1], b[0], a[1]], fill=white)


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        sa.compose(sys.argv[2], sys.argv[3], PREFIX)
        sa.paint_square_pad(sys.argv[2], sys.argv[3], PREFIX, PAD_HALF, np.random.default_rng(9), bastion_marks)


if __name__ == "__main__":
    main()

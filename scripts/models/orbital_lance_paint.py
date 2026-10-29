"""Paints the European Orbital Lance's textures (the superweapon uplink), in the two steps that orbital_lance.py
runs (Python 3 and Pillow): the Joint Command's tiles (joint_command_paint.py, the Command Centre's surfaces),
and the composing of what Blender baked into the building's texture, its versions and the pad.

    tiles OUT_DIR             the tiles and the emblem
    compose BAKE_DIR OUT_DIR  euol_building*.tga and euol_pad*.tga
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import command_centre_paint as cc  # noqa: E402
import joint_command_paint as jc  # noqa: E402

PREFIX = "euol"
FOOTPRINT = (-64.0, 64.0, -38.0, 38.0)
DISH = (-22.0, 0.0)


def paint_pad(bake_dir, out, rng):
    """The yard: white rings round the tower, a hazard sill at the bunker's door, tyre marks."""
    pad = jc.Pad(FOOTPRINT, rng)
    x, y = DISH
    for radius, width in ((27.0, 0.6), (31.5, 0.4)):
        a, b = pad.px(x - radius, y + radius), pad.px(x + radius, y - radius)
        pad.d.ellipse([a[0], a[1], b[0], b[1]], outline=jc.WHITE, width=int(pad.units(width)))
    pad.hazard(26.0, -35.0, 34.0, -32.6, step=1.2)
    pad.wear(rng, 50)
    pad.save(bake_dir, out, PREFIX, rng)


def main():
    if sys.argv[1] == "tiles":
        jc.tiles(sys.argv[2])
        rng = np.random.default_rng(5)
        cc.emblem(rng).save(os.path.join(sys.argv[2], f"{PREFIX}_emblem.tga"))
    else:
        jc.compose(sys.argv[2], sys.argv[3], prefix=PREFIX, pad_painter=paint_pad)


if __name__ == "__main__":
    main()

"""Paints the European Funds Office's textures, in two steps that funds_office.py runs (Python 3 and Pillow),
with the Logistics Centre's painter (logistics_centre_paint.py) and the Command Centre's tiles:

    tiles OUT_DIR             tiling surfaces Blender projects onto the model: plaster, trim, deck, grilles,
                              crates, roller shutters, and the office's own curtain-wall glass, hedges and
                              paving; and the emblem
    compose BAKE_DIR OUT_DIR  the building's texture (grime, damaged, wrecked and night versions) and the pad
                              painted as one picture: a paved plaza with a ring round the fountain, parking
                              bays, a driveway past the guard booth
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_centre_paint import (UP, emblem, grime, panels, pad, tile_crate, tile_deck, tile_grille,  # noqa: E402
                                  tile_hazard, tile_metal, tile_sandbag, tile_trim, tile_wall)
from logistics_centre_paint import (NAVY, WHITE, YELLOW, PadCanvas, compose_building, tile_office,  # noqa: E402
                                    tile_shutter)

PREFIX = "eufo"


def tile_curtain(rng):
    """A curtain wall: tinted steel blue-grey panes in dark frames, a lighter sky reflection across them."""
    w = 128 * UP
    img = Image.new("RGB", (w, w))
    arr = np.zeros((w, w, 3))
    ys, xs = np.mgrid[0:w, 0:w] / w
    sky = 0.75 + 0.35 * np.clip(1 - np.abs((xs + ys) - 0.9) * 2.2, 0, 1)   # a diagonal glint
    arr[:] = np.array([62, 92, 118])
    arr *= sky[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    step = w // 2
    for k in range(0, w + 1, step):
        d.rectangle([k - 3 * UP, 0, k + 3 * UP, w], fill=(44, 48, 56))
        d.rectangle([0, k - 3 * UP, w, k + 3 * UP], fill=(44, 48, 56))
        d.line([(k + 3 * UP, 0), (k + 3 * UP, w)], fill=(150, 160, 170), width=UP)
    d.rectangle([0, w // 2 - 2 * UP, w, w // 2 + 6 * UP], fill=(52, 56, 64))   # the floor's transom
    return grime(img, rng, amount=0.12).resize((128, 128), Image.LANCZOS)


def tile_hedge(rng):
    """Trimmed hedge: dark and light leaves."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (64, 96, 48))
    d = ImageDraw.Draw(img)
    for _ in range(900):
        x, y, r = rng.uniform(0, w), rng.uniform(0, w), rng.uniform(2, 6) * UP
        g = int(rng.uniform(80, 150))
        d.ellipse([x - r, y - r, x + r, y + r], fill=(int(g * 0.55), g, int(g * 0.4)))
    return grime(img, rng, amount=0.2).resize((128, 128), Image.LANCZOS)


def tile_paving(rng):
    """Light stone slabs in a running bond."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (196, 188, 172))
    d = ImageDraw.Draw(img)
    rows = 4
    for r in range(rows):
        y = r * w / rows
        off = (r % 2) * w / 4
        for k in range(-1, 3):
            x = off + k * w / 2
            tone = int(rng.uniform(-14, 14))
            d.rectangle([x + UP, y + UP, x + w / 2 - UP, y + w / rows - UP], fill=(196 + tone, 188 + tone, 172 + tone))
        d.line([(0, y), (w, y)], fill=(130, 124, 112), width=UP)
    return grime(img, rng, amount=0.2).resize((128, 128), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(31)
    images = {"tile_wall": tile_wall(rng), "tile_trim": tile_trim(rng), "tile_deck": tile_deck(rng),
              "tile_metal": tile_metal(rng), "tile_crate": tile_crate(rng), "tile_sandbag": tile_sandbag(rng),
              "tile_hazard": tile_hazard(rng), "tile_grille": tile_grille(rng), "tile_shutter": tile_shutter(rng),
              "tile_office": tile_office(rng), "tile_curtain": tile_curtain(rng), "tile_hedge": tile_hedge(rng),
              "tile_paving": tile_paving(rng),
              "tile_dome": grime(panels((222, 224, 226), rng, step=64, seam=(170, 172, 176), rivets=False,
                                        light=(240, 240, 240)), rng, amount=0.15).resize((256, 256), Image.LANCZOS),
              f"{PREFIX}_emblem": emblem(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


EXTENT = (-27.0, 27.0, -27.0, 27.0)
FOUNTAIN = (-6.0, -11.0)


def paint_pad(bake_dir, out, rng):
    c = PadCanvas(EXTENT, size=1024, rng=rng)
    c.stains(rng, count=12)
    # The plaza: stone paving from the entrance to the fountain and round it.
    slab = tile_paving(rng).resize((int(6 * c.unit), int(6 * c.unit)))
    x0, y0 = c.px(-24.0, 0.0)
    x1, y1 = c.px(6.0, -18.0)
    plaza = Image.new("RGB", (int(x1 - x0), int(y1 - y0)))
    for x in range(0, plaza.width, slab.width):
        for y in range(0, plaza.height, slab.height):
            plaza.paste(slab, (x, y))
    c.img.paste(plaza, (int(x0), int(y0)))
    c.rect((-24.0, 0.0), (6.0, -18.0), outline=(120, 114, 102), width=c.width(0.5))
    c.circle(FOUNTAIN, 5.6, (150, 142, 128), 1.0)
    c.circle(FOUNTAIN, 6.4, NAVY, 0.5)
    # Parking bays for the official cars, at the front edge.
    for x in (-23.0, -15.5, -8.0):
        c.line((x, -25.0), (x, -16.0), WHITE, 0.4)
    c.line((-23.0, -25.0), (-8.0, -25.0), WHITE, 0.4)
    # The driveway past the guard booth, with a stop line and yellow kerb marks.
    c.rect((8.0, -26.5), (20.0, -9.0), fill=(104, 104, 102))
    c.line((8.0, -12.6), (20.0, -12.6), WHITE, 0.7)
    for y in range(-26, -9, 3):
        c.line((7.6, y), (7.6, y + 1.5), YELLOW, 0.6)
        c.line((20.4, y), (20.4, y + 1.5), YELLOW, 0.6)
    # Walkway to the wing's door.
    for y in range(-1, 7, 2):
        c.rect((4.0, y), (9.0, y + 1.0), fill=WHITE)
    c.save(bake_dir, out, PREFIX, rng)


def compose(bake_dir, out):
    rng = compose_building(bake_dir, out, PREFIX)
    paint_pad(bake_dir, out, rng)
    print("composed the building's textures")


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

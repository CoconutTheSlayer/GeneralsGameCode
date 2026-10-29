"""Paints the European Funds Office's textures, in two steps that funds_office.py runs (Python 3 and Pillow),
with the Command Centre's tiles and the SAMP/T Battery's painter (samp_battery_paint.py):

    tiles OUT_DIR             tiling surfaces Blender projects onto the model: plaster, trim, deck, steel,
                              grilles, crates, and the office's own curtain-wall glass, hedges, blast
                              barriers; and the emblem
    compose BAKE_DIR OUT_DIR  the building's texture (grime, damaged, wrecked and night versions) and the
                              ground painted as one picture: a paved plaza with a ring round the fountain,
                              parking bays, a driveway past the guard booth
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_centre_paint import (UP, emblem, grime, panels, tile_crate, tile_deck, tile_grille,  # noqa: E402
                                  tile_hazard, tile_metal, tile_sandbag, tile_trim)
import samp_battery_paint as sa  # noqa: E402

PREFIX = "eufo"
NAVY, WHITE, YELLOW = (40, 52, 92), (226, 224, 214), (214, 176, 52)


def tile_office(rng):
    """The office's plaster, a little warmer than the Command Centre's."""
    return grime(panels((228, 220, 200), rng, step=128, seam=(130, 122, 106), rivets=False, light=(246, 240, 226)), rng,
                 amount=0.22, streaks=30, streak_colour=(170, 160, 140)).resize((256, 256), Image.LANCZOS)


def tile_barrier(rng):
    """Cast concrete blast barriers."""
    return grime(panels((182, 180, 172), rng, step=128, seam=(120, 118, 110), rivets=False, light=(200, 198, 190)),
                 rng, amount=0.3, streaks=30, streak_colour=(130, 126, 118)).resize((128, 128), Image.LANCZOS)


def tile_curtain(rng):
    """A curtain wall: tinted steel blue-grey panes in dark frames, a lighter sky reflection across them."""
    w = 128 * UP
    img = Image.new("RGB", (w, w))
    arr = np.zeros((w, w, 3))
    ys, xs = np.mgrid[0:w, 0:w] / w
    sky = 0.75 + 0.35 * np.clip(1 - np.abs((xs + ys) - 0.9) * 2.2, 0, 1)   # a diagonal glint
    arr[:] = np.array([70, 112, 150])
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
    images = {"tile_trim": tile_trim(rng), "tile_deck": tile_deck(rng), "tile_metal": tile_metal(rng),
              "tile_crate": tile_crate(rng), "tile_sandbag": tile_sandbag(rng), "tile_hazard": tile_hazard(rng),
              "tile_grille": tile_grille(rng), "tile_office": tile_office(rng), "tile_curtain": tile_curtain(rng),
              "tile_hedge": tile_hedge(rng), "tile_steel": sa.tile_steel(rng), "tile_barrier": tile_barrier(rng),
              "tile_dome": grime(panels((222, 224, 226), rng, step=64, seam=(170, 172, 176), rivets=False,
                                        light=(240, 240, 240)), rng, amount=0.15).resize((256, 256), Image.LANCZOS),
              f"{PREFIX}_emblem": emblem(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


HALF = 27.0
FOUNTAIN = (-12.0, -12.0)


def paving(rng, size):
    """The lot paved in light stone slabs (the whole ground's picture)."""
    slab = tile_paving(rng).resize((size // 9, size // 9))
    img = Image.new("RGB", (size, size))
    for x in range(0, size, slab.width):
        for y in range(0, size, slab.height):
            img.paste(slab, (x, y))
    return img


def office_inside(x, y):
    """The square lot, its corners a little rounded."""
    return 26.6 - (np.abs(x) ** 8 + np.abs(y) ** 8) ** 0.125


def office_marks(d, pixel, scale):
    def rect(a, b, **kw):
        p, q = pixel(*a), pixel(*b)
        d.rectangle([min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])], **kw)

    def circle(c, r, **kw):
        p = pixel(*c)
        d.ellipse([p[0] - r * scale, p[1] - r * scale, p[0] + r * scale, p[1] + r * scale], **kw)
    asphalt = (98, 98, 96)
    rect((-26.0, -26.0), (-6.0, -16.0), fill=asphalt)                 # the car park by the plaza
    for x in (-21.0, -15.0, -9.0):
        rect((x - 0.2, -25.0), (x + 0.2, -17.0), fill=WHITE)
    rect((14.0, -27.0), (24.0, -4.0), fill=asphalt)                    # the driveway past the booth
    rect((14.0, -9.4), (24.0, -8.8), fill=WHITE)
    for y in range(-26, -4, 3):
        rect((13.6, y), (14.0, y + 1.5), fill=YELLOW)
    circle(FOUNTAIN, 6.4, fill=(150, 142, 128))
    circle(FOUNTAIN, 6.4, outline=NAVY, width=max(2, int(0.5 * scale)))
    circle(FOUNTAIN, 4.6, fill=(176, 168, 152))
    for x in range(-1, 6, 2):                                           # the walk to the doors
        rect((x, -10.5), (x + 1.0, -8.5), fill=WHITE)


def compose(bake_dir, out):
    rng = np.random.default_rng(7)
    sa.compose(bake_dir, out, PREFIX)
    sa.paint_ground(bake_dir, out, PREFIX, HALF, rng, office_inside, office_marks, base=paving(rng, 1024),
                    ragged=0.1)
    print("composed the ground")


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

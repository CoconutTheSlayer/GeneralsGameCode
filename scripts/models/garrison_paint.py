"""Paints the European Garrison's textures, in two steps that garrison.py runs (Python 3 and Pillow); it
shares the Command Centre's painting (command_centre_paint.py), so the base looks like one army:

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model (plaster, bare
                              concrete, steel trim, the steel-blue window bands and where their panes are,
                              the earth of the range's banks...); the emblem's own
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked (colour, ambient occlusion,
                              windows, height): grime on top, and its damaged, wrecked and night versions;
                              and the ground as one picture: a gravel drill yard, concrete aprons, the lane
                              out of the gate, the range's lanes, its edge ragged and see-through (alpha)
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_centre_paint import (UP, GLASS_LIT, damage, emblem, grime, pad, panels, tile_deck,  # noqa: E402
                                  tile_door, tile_grille, tile_hazard, tile_metal, tile_sandbag, tile_trim,
                                  tile_wall, tiling_noise)

PREFIX = "eubr"


def tile_concrete(rng):
    """Bare cast concrete: board-marked panels with tie holes, cooler and greyer than the plaster."""
    img = panels((176, 176, 170), rng, step=128, seam=(118, 118, 112), rivets=False, light=(198, 198, 192))
    d = ImageDraw.Draw(img)
    s = 128 * UP
    for x in range(s // 4, img.width, s // 2):
        for y in range(s // 4, img.height, s // 2):
            d.ellipse([x - 2 * UP, y - 2 * UP, x + 2 * UP, y + 2 * UP], fill=(110, 110, 106))
    for k in range(0, img.height, 16 * UP):
        d.line([(0, k), (img.width, k)], fill=(166, 166, 160), width=UP)
    return grime(img, rng, amount=0.3, streaks=40, streak_colour=(120, 118, 112)).resize((256, 256), Image.LANCZOS)


def tile_earth(rng):
    """Packed earth of the range's banks: sandy brown, stones, dry tufts."""
    w = 256 * UP
    noise = tiling_noise(w, w, 8, rng) * 0.5 + tiling_noise(w, w, 24, rng) * 0.5
    arr = np.array([164, 132, 92])[None, None, :] * (0.8 + 0.35 * noise)[..., None]
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for _ in range(140):
        x, y, r = rng.uniform(0, w), rng.uniform(0, w), rng.uniform(1, 4) * UP
        d.ellipse([x - r, y - r * 0.7, x + r, y + r * 0.7], fill=(120 + int(rng.uniform(0, 40)),) * 2 + (96,))
    for _ in range(40):
        x, y = rng.uniform(0, w), rng.uniform(0, w)
        for _ in range(4):
            d.line([(x, y), (x + rng.uniform(-5, 5) * UP, y - rng.uniform(3, 8) * UP)], fill=(130, 124, 70), width=UP)
    return grime(img, rng, amount=0.15).resize((256, 256), Image.LANCZOS)


BAND_GLASS, BAND_MULLION = (60, 96, 128), (82, 98, 116)


def band_tiles(rng):
    """The window bands: steel-blue glazing with a mullion every two units (the tile is four units wide,
    the same all the way up), and a mask of where the panes are (they light up at night)."""
    w = 256 * UP
    img = Image.new("RGB", (w, w), BAND_GLASS)
    mask = Image.new("L", (w, w), 255)
    d, m = ImageDraw.Draw(img), ImageDraw.Draw(mask)
    for x0 in (0, w // 2):
        d.rectangle([x0 + 12 * UP, 0, x0 + 30 * UP, w], fill=(84, 124, 156))     # a reflection in each pane
        d.rectangle([x0 + 34 * UP, 0, x0 + 38 * UP, w], fill=(78, 116, 148))
        for x in (x0 - 5 * UP, x0 + w // 2 - 5 * UP):
            d.rectangle([x, 0, x + 10 * UP, w], fill=BAND_MULLION)
            d.line([(x + 2 * UP, 0), (x + 2 * UP, w)], fill=(150, 164, 180), width=UP)
            m.rectangle([x, 0, x + 10 * UP, w], fill=0)
    d.rectangle([w - 5 * UP, 0, w, w], fill=BAND_MULLION)
    m.rectangle([w - 5 * UP, 0, w, w], fill=0)
    img = grime(img, rng, amount=0.12)
    return img.resize((256, 256), Image.LANCZOS), mask.resize((256, 256), Image.LANCZOS)


# --- the ground, painted as one picture -------------------------------------------------------------

PAD_SIZE = 1024
SCALE = 2                       # painted at twice the size, then shrunk
PAD_X, PAD_Y = (-56.0, 56.0), (-46.0, 46.0)
WHITE, YELLOW = (226, 224, 214), (214, 176, 52)


def pad_pixel(x, y):
    return ((x - PAD_X[0]) / (PAD_X[1] - PAD_X[0]) * PAD_SIZE * SCALE,
            (1 - (y - PAD_Y[0]) / (PAD_Y[1] - PAD_Y[0])) * PAD_SIZE * SCALE)


def rect(d, x0, y0, x1, y1, **kw):
    a, b = pad_pixel(x0, y0), pad_pixel(x1, y1)
    d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], **kw)


def region(x0, y0, x1, y1):
    """A mask of a rectangle of the footprint."""
    w = PAD_SIZE * SCALE
    m = Image.new("L", (w, w), 0)
    rect(ImageDraw.Draw(m), x0, y0, x1, y1, fill=255)
    return m


def textured_fill(colour, rng, cells, spread, speckle):
    """A field of colour with soft blotches and fine grain (gravel, earth)."""
    w = PAD_SIZE * SCALE
    blotch = tiling_noise(w, w, cells, rng) * 0.6 + tiling_noise(w, w, cells * 4, rng) * 0.4
    grain = rng.normal(0, 1, (w, w))
    arr = np.array(colour, float)[None, None, :] * (1 - spread + 2 * spread * blotch)[..., None]
    arr += (grain * speckle)[..., None]
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))


def paint_pad(bake_dir, out, rng):
    """The ground: concrete aprons round the quarters, the watchtower and the gate; a gravel drill yard in
    the middle with the squads' marks; an asphalt lane out of the gate; the firing range's earth with its
    lanes; dirt towards a ragged edge, beyond which the ground is see-through (the map shows)."""
    w = PAD_SIZE * SCALE
    tile = pad(rng).resize((256 * SCALE, 256 * SCALE))
    concrete = Image.new("RGB", (w, w))
    for x in range(0, w, tile.width):
        for y in range(0, w, tile.height):
            concrete.paste(tile, (x, y))
    dirt = textured_fill((170, 140, 104), rng, 6, 0.12, 6)
    img = dirt.copy()
    for area in ((-55, 22, 24, 45), (-55, -20, -31, 45), (-31, -24, 24, -20), (38, -44, 54, -27), (44, -27, 54, 44),
                 (30, 24, 46, 40)):
        img.paste(concrete, (0, 0), region(*area))
    gravel = textured_fill((148, 138, 120), rng, 10, 0.1, 14).filter(ImageFilter.GaussianBlur(0.6))
    img.paste(gravel, (0, 0), region(-31, -20, 31, 22))
    earth = textured_fill((162, 132, 96), rng, 8, 0.12, 8)
    img.paste(earth, (0, 0), region(-50, -44, 22, -24))
    asphalt = textured_fill((84, 86, 88), rng, 8, 0.08, 6)
    img.paste(asphalt, (0, 0), region(24, -5, 56, 5))
    img.paste(asphalt, (0, 0), region(31, -5, 44, 22))
    d = ImageDraw.Draw(img)
    unit = PAD_SIZE * SCALE / (PAD_X[1] - PAD_X[0])
    rect(d, -31, -20, 31, 22, outline=WHITE, width=int(0.5 * unit))                 # the drill yard
    for x in range(-22, 23, 7):                                                    # where the squads form up
        for y in (-12, -6, 6, 12):
            rect(d, x - 0.4, y - 0.4, x + 0.4, y + 0.4, fill=WHITE)
    for x in range(26, 50, 5):                                                     # the lane out of the gate
        rect(d, x, -0.3, x + 2.6, 0.3, fill=YELLOW)
    rect(d, 49, -8, 50.5, 8, fill=WHITE)                                           # the stop line
    for k in range(-7, 8, 2):
        rect(d, 47, k, 48.4, k + 1.0, fill=(40, 40, 40))
    for y in (-38.25, -33.75, -29.25):                                             # the range's lanes
        rect(d, -41, y - 0.2, 8, y + 0.2, fill=WHITE)
    for x in (-30, -18, -6):                                                       # distance marks
        rect(d, x - 0.2, -42, x + 0.2, -25, fill=(200, 196, 180))
    for _ in range(60):
        x, y = pad_pixel(rng.uniform(-54, 54), rng.uniform(-44, 44))
        r = rng.uniform(0.4, 1.6) * unit
        d.ellipse([x - r, y - r * 0.6, x + r, y + r * 0.6], fill=(122, 118, 108))
    # The edge: a soft band of dirt, then a ragged cut.
    xs = (np.arange(w) + 0.5) / w * (PAD_X[1] - PAD_X[0]) + PAD_X[0]
    ys = PAD_Y[1] - (np.arange(w) + 0.5) / w * (PAD_Y[1] - PAD_Y[0])
    gx, gy = np.meshgrid(xs, ys)
    r = 7.0
    qx = np.maximum(np.abs(gx) - (PAD_X[1] - r), 0)
    qy = np.maximum(np.abs(gy) - (PAD_Y[1] - r), 0)
    inside = r - np.hypot(qx, qy)                                                  # distance in from the edge
    inside = np.minimum(inside, np.minimum(PAD_X[1] - np.abs(gx), PAD_Y[1] - np.abs(gy)))
    ragged = tiling_noise(w, w, 40, rng) * 0.7 + tiling_noise(w, w, 120, rng) * 0.3
    cut = 0.4 + 1.6 * ragged
    arr = np.asarray(img, float)
    fade = np.clip((inside - cut) / 3.0, 0, 1)[..., None]
    arr = arr * (0.55 + 0.45 * fade) + np.array([176, 146, 108]) * (0.45 - 0.45 * fade)
    alpha = np.where(inside > cut, 255, 0).astype(np.uint8)
    small = lambda a: np.asarray(Image.fromarray(a).resize((PAD_SIZE, PAD_SIZE), Image.LANCZOS), float)  # noqa: E731
    arr = small(np.clip(arr, 0, 255).astype(np.uint8))
    alpha = Image.fromarray(alpha).resize((PAD_SIZE, PAD_SIZE), Image.BILINEAR).point(lambda v: 255 if v > 127 else 0)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((PAD_SIZE, PAD_SIZE)), float)
    arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
    day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    for suffix, img in (("", day), ("_e", damage(day, rng, 2))):
        rgba = img.convert("RGBA")
        rgba.putalpha(alpha)
        rgba.save(os.path.join(out, f"{PREFIX}_pad{suffix}.tga"))


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
        band, band_mask = band_tiles(rng)
        images = {"tile_wall": tile_wall(rng), "tile_trim": tile_trim(rng), "tile_deck": tile_deck(rng),
                  "tile_door": tile_door(rng), "tile_metal": tile_metal(rng), "tile_hazard": tile_hazard(rng),
                  "tile_grille": tile_grille(rng), "tile_sandbag": tile_sandbag(rng),
                  "tile_concrete": tile_concrete(rng), "tile_earth": tile_earth(rng), "tile_band": band,
                  "tile_band_mask": band_mask, f"{PREFIX}_emblem": emblem(rng)}
        for name, image in images.items():
            image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
        print(f"painted {len(images)} tiles")
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

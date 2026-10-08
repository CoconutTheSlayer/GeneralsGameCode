"""Paints the European Armour Works' textures, in two steps that armour_works.py runs (Python 3 and Pillow),
in the same style as the Command Centre (it reuses command_centre_paint.py's tiles and weathering):

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model: the Command Centre's
                              plaster, trim, metal, crates, hazard stripes and grilles, plus standing-seam roof
                              sheeting, roller shutters, steel girders and the dark inside of the bay
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked (colour, ambient occlusion,
                              windows, height): grime, and its damaged, wrecked and night versions; the pad

compose() and paint_pad() take the texture prefix and the pad's markings, so other buildings use them too.
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import command_centre_paint as cc  # noqa: E402
from command_centre_paint import UP, damage, grime, pad, tiling_noise  # noqa: E402

PREFIX = "euwf"
GLASS_LIT = cc.GLASS_LIT
YELLOW, WHITE, NAVY, GOLD = (214, 176, 52), (226, 224, 214), (28, 34, 64), (236, 200, 40)


def tile_roof(rng):
    """Standing-seam roof sheeting, steel blue-grey: raised seams across the image's width."""
    w = 256 * UP
    x = np.arange(w)
    seam = (x % (32 * UP)) < 3 * UP
    lit = ((x % (32 * UP)) >= 3 * UP) & ((x % (32 * UP)) < 5 * UP)
    base = np.array([116, 130, 146], float)
    row = np.where(seam[:, None], base * 0.62, np.where(lit[:, None], base * 1.25, base))
    arr = np.repeat(row[None, :, :], w, axis=0)
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return grime(img, rng, amount=0.28, streaks=20, streak_colour=(80, 88, 96)).resize((256, 256), Image.LANCZOS)


def tile_shutter(rng):
    """A roller shutter: thin horizontal slats, grey-blue."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (132, 146, 160))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 6 * UP):
        d.line([(0, k), (w, k)], fill=(84, 96, 110), width=UP)
        d.line([(0, k + UP), (w, k + UP)], fill=(176, 188, 198), width=UP)
    return grime(img, rng, amount=0.22).resize((128, 128), Image.LANCZOS)


def tile_girder(rng):
    """Painted steel girders: blue-grey with bolted plates."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (84, 100, 118))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 32 * UP):
        d.rectangle([k + 2 * UP, 2 * UP, k + 30 * UP, w - 2 * UP], outline=(56, 66, 80), width=UP)
        for y in range(8 * UP, w, 24 * UP):
            d.ellipse([k + 4 * UP, y, k + 6 * UP, y + 2 * UP], fill=(150, 162, 176))
    return grime(img, rng, amount=0.25).resize((128, 128), Image.LANCZOS)


def tile_interior(rng):
    """The inside of the bay: dark panels with a few lamp-lit patches."""
    img = cc.panels((70, 74, 80), rng, step=64, seam=(40, 42, 46), rivets=False, light=(92, 96, 102))
    return grime(img, rng, amount=0.3).resize((256, 256), Image.LANCZOS)


def tile_concrete(rng):
    return pad(rng)


def tiles(out):
    rng = np.random.default_rng(31)
    images = {"tile_wall": cc.tile_wall(rng), "tile_trim": cc.tile_trim(rng), "tile_metal": cc.tile_metal(rng),
              "tile_crate": cc.tile_crate(rng), "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng),
              "tile_roof": tile_roof(rng), "tile_shutter": tile_shutter(rng), "tile_girder": tile_girder(rng),
              "tile_interior": tile_interior(rng), "tile_concrete": tile_concrete(rng),
              "tile_dome": cc.tile_dome(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + ".png"))
    cc.emblem(rng).save(os.path.join(out, "emblem.tga"))
    cc.fence_texture().save(os.path.join(out, "fence.tga"))
    print(f"painted {len(images)} tiles")


# --- the pad ---------------------------------------------------------------------------------------

class PadPainter:
    """The pad as one picture over the footprint (x0, x1, y0, y1), seen from above with +X to the right."""

    def __init__(self, extent, size=1024):
        self.x0, self.x1, self.y0, self.y1 = extent
        self.size = size
        self.w = size * UP
        self.units = self.w / max(self.x1 - self.x0, self.y1 - self.y0)

    def px(self, x, y):
        return ((x - self.x0) / (self.x1 - self.x0) * self.w, (1 - (y - self.y0) / (self.y1 - self.y0)) * self.w)

    def rect(self, d, a, b, **kw):
        (ax, ay), (bx, by) = self.px(*a), self.px(*b)
        d.rectangle([min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)], **kw)

    def width(self, units):
        return max(1, int(units * self.units))

    def emblem(self, d, x, y, half, point="-X"):
        """The faction's mark painted flat: a gold chevron on dark blue."""
        cx, cy = self.px(x, y)
        r = half * self.units
        d.rectangle([cx - r, cy - r, cx + r, cy + r], fill=NAVY, outline=WHITE, width=self.width(0.6))
        s = -1 if point == "-X" else 1
        d.polygon([(cx - s * r * 0.4, cy - r * 0.65), (cx + s * r * 0.55, cy), (cx - s * r * 0.4, cy + r * 0.65),
                   (cx - s * r * 0.4, cy + r * 0.42), (cx + s * r * 0.15, cy), (cx - s * r * 0.4, cy - r * 0.42)], fill=GOLD)


def paint_pad(bake_dir, out, rng, prefix, extent, markings):
    """Concrete slabs, the building's markings (markings(painter, draw)), tyre marks, darker by the walls."""
    p = PadPainter(extent)
    tile = pad(rng).resize((256 * UP, 256 * UP))
    img = Image.new("RGB", (p.w, p.w))
    for x in range(0, p.w, tile.width):
        for y in range(0, p.w, tile.height):
            img.paste(tile, (x, y))
    d = ImageDraw.Draw(img)
    markings(p, d)
    for _ in range(30):
        x, y = p.px(rng.uniform(p.x0, p.x1), rng.uniform(p.y0, p.y1))
        rr = rng.uniform(1, 4) * p.units
        d.ellipse([x - rr, y - rr * 0.6, x + rr, y + rr * 0.6], fill=(118, 118, 112))
    arr = np.asarray(img.resize((p.size, p.size), Image.LANCZOS), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((p.size, p.size)), float)
    arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
    day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    day.save(os.path.join(out, f"{prefix}_pad.tga"))
    damage(day, rng, 2).save(os.path.join(out, f"{prefix}_pad_e.tga"))


def compose(bake_dir, out, prefix, markings, extent, seed=7):
    """The building's texture from Blender's bakes and its versions (as the Command Centre's)."""
    rng = np.random.default_rng(seed)
    colour = np.asarray(Image.open(os.path.join(bake_dir, "colour.png")).convert("RGB"), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "occlusion.png")).convert("L"), float)[..., None] / 255.0
    windows = np.asarray(Image.open(os.path.join(bake_dir, "windows.png")).convert("L"), float)[..., None] / 255.0
    height = np.asarray(Image.open(os.path.join(bake_dir, "height.png")).convert("L"), float)[..., None] / 255.0
    h, w = ao.shape[:2]
    stains = (tiling_noise(w, h, 10, rng) * 0.6 + tiling_noise(w, h, 30, rng) * 0.4)[..., None]
    lit = colour * (0.42 + 0.58 * ao) * (0.86 + 0.24 * stains) * (0.78 + 0.36 * np.sqrt(height))
    lit *= np.array([1.16, 1.2, 1.3])
    day = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    versions = {"": day, "_d": damage(day, rng, 1), "_e": damage(day, rng, 2)}
    for suffix, img in versions.items():
        img.save(os.path.join(out, f"{prefix}_building{suffix}.tga"))
        arr = np.asarray(img, float) * 0.8
        glow = windows * (1.0 if suffix != "_e" else 0.35)
        arr = arr * (1 - glow) + np.array(GLASS_LIT) * glow
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(out, f"{prefix}_building{suffix}n.tga"))
    paint_pad(bake_dir, out, rng, prefix, extent, markings)
    print("composed the building's textures")


# --- the Armour Works' pad -------------------------------------------------------------------------

EXTENT = (-56.0, 56.0, -62.0, 62.0)


def markings(p, d):
    """A lane out of the bay (+X), the repair bay's box under the gantry, parking boxes, the faction's mark."""
    # Lane edges and dashes from the bay door to the pad's edge.
    for y in (-41.5, -18.5):
        (ax, ay), (bx, by) = p.px(46, y), p.px(56, y)
        d.line([(ax, ay), (bx, by)], fill=YELLOW, width=p.width(0.8))
    for x in range(47, 56, 5):
        (ax, ay), (bx, by) = p.px(x, -30), p.px(x + 2.5, -30)
        d.line([(ax, ay), (bx, by)], fill=WHITE, width=p.width(0.9))
    # The repair bay under the gantry: a hazard-striped frame and a cross.
    p.rect(d, (34, 4), (54, 28), outline=YELLOW, width=p.width(1.2))
    for k in range(5):
        a, b = p.px(34 + k * 4, 4), p.px(36 + k * 4, 2.6)
        d.rectangle([a[0], a[1], b[0], b[1]], fill=(30, 30, 28))
    (ax, ay), (bx, by) = p.px(40, 16), p.px(52, 16)
    d.line([(ax, ay), (bx, by)], fill=YELLOW, width=p.width(0.5))
    # Parking boxes in the yard.
    for x in (2, 16):
        p.rect(d, (x, 34), (x + 11, 52), outline=WHITE, width=p.width(0.5))
    p.emblem(d, 24, 16, 7)


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
    else:
        compose(sys.argv[2], sys.argv[3], PREFIX, markings, EXTENT)


if __name__ == "__main__":
    main()

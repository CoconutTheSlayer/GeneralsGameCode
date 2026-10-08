"""Paints the European Joint Command's textures (the strategy centre), in two steps that joint_command.py runs
(Python 3 and Pillow). The surfaces are the Command Centre's (command_centre_paint.py), so the base looks like
one army, with a few of its own: the war room's glazing, a roll-up door, plain concrete.

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model, and the emblem
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked (colour, ambient occlusion,
                              where the windows are, height): grime on top, and its damaged, wrecked and
                              night versions; the pad, painted as one picture

orbital_lance_paint.py uses the same steps for the Orbital Lance (compose() and paint_pad() take the
texture prefix and the footprint).
"""
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import command_centre_paint as cc  # noqa: E402

UP = cc.UP
PREFIX = "eusg"
FOOTPRINT = (-62.0, 62.0, -44.0, 44.0)   # x0, x1, y0, y1 that the pad's texture covers
NAVY, GOLD, WHITE, YELLOW = (28, 34, 64), (236, 200, 40), (226, 224, 214), (214, 176, 52)


def tile_glazing(rng):
    """The war room's glass: dark blue panes in a steel grid, a lighter streak of sky on each."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (44, 66, 92))
    d = ImageDraw.Draw(img)
    step = 32 * UP
    for x in range(0, w, step):
        for y in range(0, w, step):
            d.polygon([(x + 4 * UP, y + 4 * UP), (x + 14 * UP, y + 4 * UP), (x + 4 * UP, y + 14 * UP)], fill=(86, 112, 140))
    for k in range(0, w + 1, step):
        d.line([(0, k), (w, k)], fill=(150, 160, 170), width=3 * UP)
        d.line([(k, 0), (k, w)], fill=(150, 160, 170), width=3 * UP)
    return cc.grime(img, rng, amount=0.12).resize((128, 128), Image.LANCZOS)


def tile_shutter(rng):
    """A grey roll-up door: horizontal slats."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (150, 156, 160))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 8 * UP):
        d.line([(0, k), (w, k)], fill=(96, 100, 106), width=UP)
        d.line([(0, k + UP), (w, k + UP)], fill=(196, 200, 204), width=UP)
    return cc.grime(img, rng, amount=0.22).resize((128, 128), Image.LANCZOS)


def tile_concrete(rng):
    """Cast concrete for barriers and blocks."""
    img = Image.new("RGB", (128 * UP, 128 * UP), (172, 168, 158))
    d = ImageDraw.Draw(img)
    for _ in range(30):
        x, y, r = rng.uniform(0, 128 * UP), rng.uniform(0, 128 * UP), rng.uniform(1, 2) * UP
        d.ellipse([x - r, y - r, x + r, y + r], fill=(140, 136, 128))
    return cc.grime(img, rng, amount=0.25, streaks=12, streak_colour=(120, 116, 108)).resize((128, 128), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(31)
    images = {"tile_wall": cc.tile_wall(rng), "tile_trim": cc.tile_trim(rng), "tile_rib": cc.tile_rib(rng),
              "tile_deck": cc.tile_deck(rng), "tile_door": cc.tile_door(rng), "tile_dome": cc.tile_dome(rng),
              "tile_metal": cc.tile_metal(rng), "tile_crate": cc.tile_crate(rng), "tile_sandbag": cc.tile_sandbag(rng),
              "tile_hazard": cc.tile_hazard(rng), "tile_grille": cc.tile_grille(rng), "tile_glazing": tile_glazing(rng),
              "tile_shutter": tile_shutter(rng), "tile_concrete": tile_concrete(rng)}
    for name, image in images.items():
        image.save(os.path.join(out, name + ".png"))
    print(f"painted {len(images)} tiles")


# --- the pad ---------------------------------------------------------------------------------------

PAD_SIZE = 1024


class Pad:
    """A picture of the pad seen from above (+X to the right), covering the footprint."""

    def __init__(self, footprint, rng):
        self.x0, self.x1, self.y0, self.y1 = footprint
        self.w = PAD_SIZE * UP
        self.scale = self.w / max(self.x1 - self.x0, self.y1 - self.y0)
        tile = cc.pad(rng).resize((256 * UP, 256 * UP))
        self.img = Image.new("RGB", (self.w, self.w))
        for x in range(0, self.w, tile.width):
            for y in range(0, self.w, tile.height):
                self.img.paste(tile, (x, y))
        self.d = ImageDraw.Draw(self.img)

    def px(self, x, y):
        return ((x - self.x0) / (self.x1 - self.x0) * self.w, (1 - (y - self.y0) / (self.y1 - self.y0)) * self.w)

    def units(self, u):
        """A length on the ground in pixels (along x; the picture is stretched to the footprint)."""
        return u * self.w / (self.x1 - self.x0)

    def rect(self, x0, y0, x1, y1, fill=None, outline=None, width=0.5):
        a, b = self.px(x0, y0), self.px(x1, y1)
        self.d.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], fill=fill,
                         outline=outline, width=max(1, int(self.units(width))))

    def line(self, x0, y0, x1, y1, fill, width=0.8):
        self.d.line([self.px(x0, y0), self.px(x1, y1)], fill=fill, width=max(1, int(self.units(width))))

    def emblem(self, x, y, r):
        """The gold chevron on dark blue; it points to -X on the texture: up the screen from the game's camera."""
        cx, cy = self.px(x, y)
        rx, ry = self.units(r), r * self.w / (self.y1 - self.y0)
        self.d.rectangle([cx - rx, cy - ry, cx + rx, cy + ry], fill=NAVY, outline=WHITE, width=int(self.units(0.6)))
        self.d.polygon([(cx + rx * 0.4, cy - ry * 0.65), (cx - rx * 0.55, cy), (cx + rx * 0.4, cy + ry * 0.65),
                        (cx + rx * 0.4, cy + ry * 0.42), (cx - rx * 0.15, cy), (cx + rx * 0.4, cy - ry * 0.42)], fill=GOLD)

    def hazard(self, x0, y0, x1, y1, step=2.0):
        """Yellow and black stripes in a band."""
        self.rect(x0, y0, x1, y1, fill=YELLOW)
        a, b = self.px(x0, y0), self.px(x1, y1)
        lo, hi = (min(a[0], b[0]), min(a[1], b[1])), (max(a[0], b[0]), max(a[1], b[1]))
        band = Image.new("RGB", (int(hi[0] - lo[0]) + 1, int(hi[1] - lo[1]) + 1), YELLOW)
        bd = ImageDraw.Draw(band)
        s = self.units(step)
        span = band.width + band.height
        k = -band.height
        while k < span:
            bd.polygon([(k, band.height), (k + s, band.height), (k + s + band.height, 0), (k + band.height, 0)], fill=(34, 32, 30))
            k += 2 * s
        self.img.paste(band, (int(lo[0]), int(lo[1])))

    def wear(self, rng, count=30):
        for _ in range(count):
            x, y = self.px(rng.uniform(self.x0, self.x1), rng.uniform(self.y0, self.y1))
            rr = self.units(rng.uniform(1, 4))
            self.d.ellipse([x - rr, y - rr * 0.6, x + rr, y + rr * 0.6], fill=(118, 118, 112))

    def save(self, bake_dir, out, prefix, rng):
        arr = np.asarray(self.img.resize((PAD_SIZE, PAD_SIZE), Image.LANCZOS), float)
        ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize((PAD_SIZE, PAD_SIZE)), float)
        arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
        day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        day.save(os.path.join(out, f"{prefix}_pad.tga"))
        cc.damage(day, rng, 2).save(os.path.join(out, f"{prefix}_pad_e.tga"))


def paint_pad(bake_dir, out, rng):
    """The Joint Command's pad: a walkway to the entrance, lanes to the hall's door, markings by the gun."""
    pad = Pad(FOOTPRINT, rng)
    pad.rect(-5.5, -43, 5.5, -23, fill=(168, 168, 164))         # the walkway to the entrance
    pad.line(-5.5, -43, -5.5, -23, YELLOW, 0.6)
    pad.line(5.5, -43, 5.5, -23, YELLOW, 0.6)
    pad.line(-49, -43, -49, -36, YELLOW, 0.8)                   # the lane out of the hall
    pad.line(-28, -43, -28, -36, YELLOW, 0.8)
    pad.hazard(-50, -38, -27, -36.6)
    pad.rect(14, -42, 56, -38.5, outline=WHITE, width=0.4)      # parking boxes in front of the gun
    for x in range(22, 56, 8):
        pad.line(x, -42, x, -38.5, WHITE, 0.4)
    pad.emblem(48, 30, 7)                                       # beside the dome tower
    pad.wear(rng)
    pad.save(bake_dir, out, PREFIX, rng)


# --- the building's texture ------------------------------------------------------------------------

def compose(bake_dir, out, prefix=PREFIX, pad_painter=paint_pad):
    """The building's texture from Blender's bakes, and its versions."""
    rng = np.random.default_rng(7)
    colour = np.asarray(Image.open(os.path.join(bake_dir, "colour.png")).convert("RGB"), float)
    ao = np.asarray(Image.open(os.path.join(bake_dir, "occlusion.png")).convert("L"), float)[..., None] / 255.0
    windows = np.asarray(Image.open(os.path.join(bake_dir, "windows.png")).convert("L"), float)[..., None] / 255.0
    height = np.asarray(Image.open(os.path.join(bake_dir, "height.png")).convert("L"), float)[..., None] / 255.0
    h, w = ao.shape[:2]
    stains = (cc.tiling_noise(w, h, 10, rng) * 0.6 + cc.tiling_noise(w, h, 30, rng) * 0.4)[..., None]
    # Darker towards the ground, as the game's buildings are painted.
    lit = colour * (0.42 + 0.58 * ao) * (0.86 + 0.24 * stains) * (0.78 + 0.36 * np.sqrt(np.clip(height, 0, 1)))
    # The game's light is warm and dim: paint a little lighter and cooler.
    lit *= np.array([1.16, 1.2, 1.3])
    day = Image.fromarray(np.clip(lit, 0, 255).astype(np.uint8))
    versions = {"": day, "_d": cc.damage(day, rng, 1), "_e": cc.damage(day, rng, 2)}
    for suffix, img in versions.items():
        img.save(os.path.join(out, f"{prefix}_building{suffix}.tga"))
        # At night the building darkens and its windows light up.
        arr = np.asarray(img, float) * 0.8
        glow = windows * (1.0 if suffix != "_e" else 0.35)
        arr = arr * (1 - glow) + np.array(cc.GLASS_LIT) * glow
        Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).save(os.path.join(out, f"{prefix}_building{suffix}n.tga"))
    pad_painter(bake_dir, out, rng)
    print(f"composed the {prefix} textures")


def main():
    if sys.argv[1] == "tiles":
        tiles(sys.argv[2])
        rng = np.random.default_rng(5)
        cc.emblem(rng).save(os.path.join(sys.argv[2], f"{PREFIX}_emblem.tga"))
    else:
        compose(sys.argv[2], sys.argv[3])


if __name__ == "__main__":
    main()

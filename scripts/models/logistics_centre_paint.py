"""Paints the European Logistics Centre's textures, in two steps that logistics_centre.py runs (Python 3 and
Pillow), the way command_centre_paint.py does for the Command Centre (whose tiles and weathering it reuses):

    tiles OUT_DIR             small tiling surfaces that Blender projects onto the model: the Command Centre's
                              plaster, trim, deck, hazard stripes and crates, and the Logistics Centre's own
                              shipping containers in five muted colours, the crane's yellow steel, bare
                              concrete, the silos' plates, roller doors and pallets
    compose BAKE_DIR OUT_DIR  the building's texture from what Blender baked, with grime, its damaged,
                              wrecked and night versions, and the yard painted as one picture: the crane's
                              rails, the container bays, the landing square where trucks and helicopters
                              unload, the faction's mark
"""
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from command_centre_paint import (GLASS_LIT, UP, damage, emblem, fence_texture, grime, pad, panels,  # noqa: E402
                                  tile_crate, tile_deck, tile_grille, tile_hazard, tile_metal, tile_rib,
                                  tile_sandbag, tile_trim, tile_wall, tiling_noise)

PREFIX = "eusc"
YELLOW, WHITE, NAVY, GOLD = (214, 176, 52), (226, 224, 214), (28, 34, 64), (236, 200, 40)


def tile_shutter(rng):
    """A steel roller door: narrow horizontal slats, steel blue-grey."""
    w = 256 * UP
    img = Image.new("RGB", (w, w), (112, 128, 146))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 12 * UP):
        d.line([(0, k), (w, k)], fill=(60, 70, 84), width=UP)
        d.line([(0, k + UP), (w, k + UP)], fill=(160, 174, 190), width=UP)
    return grime(img, rng, amount=0.22, streaks=20, streak_colour=(80, 86, 94)).resize((256, 256), Image.LANCZOS)


def tile_container(rng, colour=(70, 102, 140)):
    """A shipping container's side: deep vertical ribs."""
    w = 256 * UP
    x = np.arange(w) / w * 20 * 2 * math.pi
    shade = 0.8 + 0.2 * np.sign(np.sin(x)) * np.abs(np.sin(x)) ** 0.3
    arr = np.array(colour)[None, None, :] * shade[None, :, None] * np.ones((w, 1, 1))
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    d = ImageDraw.Draw(img)
    for k in (0, w // 2):
        d.line([(0, k), (w, k)], fill=tuple(int(c * 0.6) for c in colour), width=2 * UP)
    return grime(img, rng, amount=0.28, streaks=24, streak_colour=tuple(int(c * 0.55) for c in colour)).resize(
        (256, 256), Image.LANCZOS)


def tile_tank(rng):
    """Light grey steel plates of a storage tank."""
    return grime(panels((206, 210, 212), rng, step=64, seam=(140, 146, 150), rivets=True, light=(232, 234, 236)), rng,
                 amount=0.2, streaks=40, streak_colour=(150, 140, 120)).resize((256, 256), Image.LANCZOS)


def tile_pallet(rng):
    """Wooden pallets and planks."""
    w = 128 * UP
    img = Image.new("RGB", (w, w), (164, 132, 88))
    d = ImageDraw.Draw(img)
    for k in range(0, w, 16 * UP):
        d.rectangle([0, k, w, k + 12 * UP], fill=(176 + int(rng.uniform(-14, 14)), 142, 96))
        d.line([(0, k + 12 * UP), (w, k + 12 * UP)], fill=(90, 70, 46), width=4 * UP)
    return grime(img, rng, amount=0.25).resize((128, 128), Image.LANCZOS)


def tile_office(rng):
    """The office's walls: the Command Centre's plaster, a little warmer."""
    return grime(panels((228, 220, 200), rng, step=128, seam=(130, 122, 106), rivets=False, light=(246, 240, 226)), rng,
                 amount=0.22, streaks=30, streak_colour=(170, 160, 140)).resize((256, 256), Image.LANCZOS)


def tile_crane(rng):
    """The crane's steel: safety yellow plates with seams and bolts."""
    return grime(panels((226, 186, 54), rng, step=64, seam=(150, 118, 30), rivets=True, light=(244, 214, 110)), rng,
                 amount=0.25, streaks=30, streak_colour=(150, 120, 60)).resize((256, 256), Image.LANCZOS)


def tile_concrete(rng):
    """Bare cast concrete: board-marked panels, cooler and greyer than the plaster."""
    img = panels((176, 176, 170), rng, step=128, seam=(118, 118, 112), rivets=False, light=(198, 198, 192))
    d = ImageDraw.Draw(img)
    for k in range(0, img.height, 16 * UP):
        d.line([(0, k), (img.width, k)], fill=(166, 166, 160), width=UP)
    return grime(img, rng, amount=0.3, streaks=40, streak_colour=(120, 118, 112)).resize((256, 256), Image.LANCZOS)


def tile_roof(rng):
    """The silos' cones: grey steel plates."""
    return grime(panels((150, 156, 160), rng, step=64, seam=(100, 106, 112), rivets=True, light=(184, 188, 192)), rng,
                 amount=0.25).resize((256, 256), Image.LANCZOS)


def tiles(out):
    rng = np.random.default_rng(21)
    images = {"tile_wall": tile_wall(rng), "tile_trim": tile_trim(rng), "tile_rib": tile_rib(rng),
              "tile_deck": tile_deck(rng), "tile_metal": tile_metal(rng), "tile_crate": tile_crate(rng),
              "tile_sandbag": tile_sandbag(rng), "tile_hazard": tile_hazard(rng), "tile_grille": tile_grille(rng),
              "tile_shutter": tile_shutter(rng), "tile_container": tile_container(rng),
              "tile_container2": tile_container(rng, (92, 104, 72)), "tile_tank": tile_tank(rng),
              "tile_container3": tile_container(rng, (142, 76, 60)),
              "tile_container4": tile_container(rng, (206, 202, 188)),
              "tile_container5": tile_container(rng, (122, 126, 130)), "tile_crane": tile_crane(rng),
              "tile_concrete": tile_concrete(rng), "tile_roof": tile_roof(rng),
              "tile_pallet": tile_pallet(rng), "tile_office": tile_office(rng), "tile_dome": tile_tank(rng),
              "tile_door": tile_shutter(rng), "tile_pad": pad(rng),
              f"{PREFIX}_emblem": emblem(rng), f"{PREFIX}_fence": fence_texture()}
    for name, image in images.items():
        image.save(os.path.join(out, name + (".png" if name.startswith("tile_") else ".tga")))
    print(f"painted {len(images)} tiles")


# --- the pad, painted as one picture ---------------------------------------------------------------

class PadCanvas:
    """The pad's picture: a footprint (x0, x1, y0, y1) seen from above, +X to the right, +Y up."""

    def __init__(self, extent, size=1024, rng=None):
        self.x0, self.x1, self.y0, self.y1 = extent
        self.size = size
        w = size * UP
        tile = pad(rng).resize((256 * UP, 256 * UP))
        self.img = Image.new("RGB", (w, w))
        for x in range(0, w, tile.width):
            for y in range(0, w, tile.height):
                self.img.paste(tile, (x, y))
        self.d = ImageDraw.Draw(self.img)
        self.unit = w / (self.x1 - self.x0)

    def px(self, x, y):
        w = self.size * UP
        return ((x - self.x0) / (self.x1 - self.x0) * w, (1 - (y - self.y0) / (self.y1 - self.y0)) * w)

    def width(self, units):
        return max(1, int(units * self.unit))

    def rect(self, a, b, **kw):
        p, q = self.px(*a), self.px(*b)
        self.d.rectangle([min(p[0], q[0]), min(p[1], q[1]), max(p[0], q[0]), max(p[1], q[1])], **kw)

    def line(self, a, b, colour, units):
        self.d.line([self.px(*a), self.px(*b)], fill=colour, width=self.width(units))

    def circle(self, c, r, colour, units):
        x, y = self.px(*c)
        rr = r * self.unit
        self.d.ellipse([x - rr, y - rr, x + rr, y + rr], outline=colour, width=self.width(units))

    def polygon(self, points, **kw):
        self.d.polygon([self.px(*p) for p in points], **kw)

    def emblem(self, c, half, angle):
        """The faction's mark on the ground: a gold chevron on a dark blue square, the chevron pointing
        along `angle` (radians from +X)."""
        cx, cy = c
        self.rect((cx - half, cy - half), (cx + half, cy + half), fill=NAVY, outline=WHITE, width=self.width(0.6))
        ca, sa = math.cos(angle), math.sin(angle)

        def at(u, v):  # u along the point, v across
            return (cx + u * ca - v * sa, cy + u * sa + v * ca)
        for off in (0.0, -0.42):
            pts = [(0.62 + off, 0), (-0.05 + off, 0.62), (-0.33 + off, 0.62), (0.34 + off, 0), (-0.33 + off, -0.62),
                   (-0.05 + off, -0.62)]
            self.polygon([at(u * half * 0.8, v * half * 0.8) for u, v in pts], fill=GOLD)

    def stains(self, rng, count=30):
        for _ in range(count):
            x, y = self.px(rng.uniform(self.x0, self.x1), rng.uniform(self.y0, self.y1))
            rr = rng.uniform(1, 4) * self.unit
            self.d.ellipse([x - rr, y - rr * 0.6, x + rr, y + rr * 0.6], fill=(118, 118, 112))

    def save(self, bake_dir, out, prefix, rng):
        arr = np.asarray(self.img.resize((self.size, self.size), Image.LANCZOS), float)
        ao = np.asarray(Image.open(os.path.join(bake_dir, "pad_occlusion.png")).convert("L").resize(
            (self.size, self.size)), float)
        arr = arr * (0.5 + 0.5 * ao[..., None] / 255.0) * np.array([1.1, 1.12, 1.16])
        day = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        day.save(os.path.join(out, f"{prefix}_pad.tga"))
        damage(day, rng, 2).save(os.path.join(out, f"{prefix}_pad_e.tga"))


EXTENT = (-44.0, 44.0, -45.0, 45.0)
DOCK = (22.0, -20.0)
RAILS = (-38.0, 2.0)


def paint_pad(bake_dir, out, rng):
    """The yard: the crane's rails along its length, the container bays between them, the landing square
    where trucks and helicopters unload, a lane from it to the crane, walkway stripes to the office."""
    c = PadCanvas(EXTENT, rng=rng)
    c.stains(rng, count=50)   # under the markings
    steel, dark = (150, 154, 158), (70, 70, 68)
    for x in RAILS:           # the rails, in their channels
        c.rect((x - 1.6, -44), (x + 1.6, 44), fill=(104, 104, 100))
        for dx in (-0.9, 0.9):
            c.line((x + dx, -44), (x + dx, 44), dark, 0.5)
            c.line((x + dx - 0.12, -44), (x + dx - 0.12, 44), steel, 0.25)
    for y in range(-6, 42, 6):   # the container bays
        for x in (-27.0, -14.0):
            c.rect((x - 6.4, y - 2.8), (x + 6.4, y + 2.8), outline=WHITE, width=c.width(0.3))
    # The landing square: a yellow frame with hazard ticks, a ring and a cross.
    dx, dy = DOCK
    c.rect((dx - 11, dy - 11), (dx + 11, dy + 11), outline=YELLOW, width=c.width(1.0))
    for k in range(-10, 11, 4):
        c.line((dx + k, dy - 11.5), (dx + k + 1.5, dy - 10.5), (34, 32, 30), 0.6)
    c.circle(DOCK, 7.5, YELLOW, 0.9)
    c.line((dx - 4, dy), (dx + 4, dy), WHITE, 1.6)
    c.line((dx, dy - 4), (dx, dy + 4), WHITE, 1.6)
    # A dashed lane from the landing square up the yard under the crane's reach.
    for y in range(-6, 30, 6):
        c.line((22, y), (22, y + 3.5), YELLOW, 0.8)
    for y in (-8.0, 30.0):
        c.line((5, y), (40, y), WHITE, 0.4)
    # The faction's mark on the apron, pointing up the screen from the game's camera.
    c.emblem((-11.0, -22.0), 5.5, math.radians(90))
    for x in range(-23, -15, 3):   # walkway stripes to the office's door
        c.rect((x, -30.5), (x + 1.5, -26), fill=WHITE)
    c.save(bake_dir, out, PREFIX, rng)


# --- the building's texture ------------------------------------------------------------------------

def compose_building(bake_dir, out, prefix):
    """The building's texture from Blender's bakes, and its damaged, wrecked and night versions."""
    rng = np.random.default_rng(7)
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
    return rng


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

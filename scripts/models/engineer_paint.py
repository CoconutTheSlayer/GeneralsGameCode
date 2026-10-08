"""Paints the European Engineer Vehicle's textures, and holds what the European support vehicles share (the
Engineer Vehicle, the Field Ambulance and the Recon Drone: ambulance_paint.py and recon_drone_paint.py import it):

- Layout: where each side of each part lies on the texture. Like the Boxer (boxer_layout.py), every face is
  projected straight onto its part's roof, side, front, back or underside panel, but the panels are packed
  automatically, as large as the texture allows.
- paint_body(): the Boxer's way of painting (boxer_paint.py) for any layout: blue-grey camouflage, shading,
  seams and lit edges, stains, streaks, dust and mud, worn edges, the baked ambient occlusion, and a burnt
  version for the damaged model.
- paint_tread(): track links for scrolling treads.

engineer.py writes the faces of the model on the texture (build/models/EUDOZ_layout.json) and runs this with
Python 3 and Pillow, with the ambient occlusion it baked:

    python3 scripts/models/engineer_paint.py build/models/EUDOZ_layout.json OUT_DIR [OCCLUSION.png]

Layout needs neither Pillow nor numpy, so that the model scripts can use it inside Blender.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

GROUPS = ("top", "side", "front", "back", "bottom")
BOTTOM_SCALE = 0.3  # undersides are hardly ever seen: drawn small


def group(normal):
    """Which panel a face belongs to, by the way it faces."""
    x, y, z = normal
    if abs(z) >= abs(x) and abs(z) >= abs(y):
        return "top" if z > 0 else "bottom"
    if abs(y) >= abs(x):
        return "side"
    return "front" if x > 0 else "back"


class Layout:
    """parts: {name: (x0, x1, y0, y1, z0, z1)}, each part's box in its own space; weights: {name: factor} to
    give a part more (or fewer) pixels per unit than the others. The panels are packed in rows on a
    size x size texture (pixels y down), at the largest scale that fits."""

    def __init__(self, parts, size=512, weights=None, pad=4, islands=None, scale=None):
        self.parts = {k: tuple(v) for k, v in parts.items()}
        self.size, self.pad = size, pad
        self.weights = dict(weights or {})
        if islands is None:
            lo, hi = 1.0, 128.0
            for _ in range(40):
                mid = (lo + hi) / 2
                if self._pack(mid) is not None:
                    lo = mid
                else:
                    hi = mid
            scale, islands = lo, self._pack(lo)
        self.scale = scale
        self.islands = {tuple(k.split("/")) if isinstance(k, str) else k: tuple(v) for k, v in islands.items()}

    def s(self, part):
        """Pixels per unit of a part."""
        return self.scale * self.weights.get(part, 1.0)

    def dims(self, part, grp, s=None):
        x0, x1, y0, y1, z0, z1 = self.parts[part]
        s = self.s(part) if s is None else s
        X, Y, Z = (x1 - x0) * s, (y1 - y0) * s, (z1 - z0) * s
        return {"top": (X, Y), "side": (X, Z), "front": (Y, Z), "back": (Y, Z),
                "bottom": (X * BOTTOM_SCALE, Y * BOTTOM_SCALE)}[grp]

    def _pack(self, scale):
        items = []
        for part in self.parts:
            for grp in GROUPS:
                w, h = self.dims(part, grp, scale * self.weights.get(part, 1.0))
                items.append((math.ceil(h), math.ceil(w), part, grp))
        items.sort(reverse=True)
        x = y = self.pad
        shelf, islands = 0, {}
        for h, w, part, grp in items:
            if w + 2 * self.pad > self.size:
                return None
            if x + w + self.pad > self.size:
                x, y, shelf = self.pad, y + shelf + self.pad, 0
            if y + h + self.pad > self.size:
                return None
            islands[(part, grp)] = (x, y)
            x += w + self.pad
            shelf = max(shelf, h)
        return islands

    def pixel(self, part, grp, co):
        """Where a point of the part lies on the texture."""
        x0, x1, y0, y1, z0, z1 = self.parts[part]
        s = self.s(part)
        x = min(max(co[0], x0), x1)
        y = min(max(co[1], y0), y1)
        z = min(max(co[2], z0), z1)
        left, top = self.islands[(part, grp)]
        if grp == "top":
            return left + (x - x0) * s, top + (y1 - y) * s
        if grp == "bottom":
            return left + (x - x0) * s * BOTTOM_SCALE, top + (y1 - y) * s * BOTTOM_SCALE
        if grp == "side":
            return left + (x - x0) * s, top + (z1 - z) * s
        # front and back: across the width
        return left + (y - y0) * s, top + (z1 - z) * s

    def uv(self, part, grp, co):
        """The same as a Blender UV (v up)."""
        px, py = self.pixel(part, grp, co)
        return px / self.size, 1.0 - py / self.size

    def to_json(self):
        return dict(parts=self.parts, size=self.size, weights=self.weights, pad=self.pad, scale=self.scale,
                    islands={f"{p}/{g}": v for (p, g), v in self.islands.items()})

    @classmethod
    def from_json(cls, data):
        return cls(data["parts"], data["size"], data["weights"], data["pad"], data["islands"], data["scale"])


# --- painting (Python 3 with Pillow and numpy, outside Blender) ----------------------------------------

try:
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # inside Blender only the layout is used
    np = Image = ImageDraw = ImageFilter = None

UP = 4  # painted at four times the size, then shrunk: smooth lines
CAMO = [(124, 138, 150), (84, 97, 112), (166, 176, 184)]
SEAM, LIT = (22, 25, 30), (205, 212, 218)
DUST, MUD = (156, 142, 118), (88, 72, 52)
YELLOW, DARK_BLUE, GOLD = (226, 184, 40), (28, 34, 60), (235, 200, 40)


class Painter:
    """Coordinates for drawing on a layout at UP times its size."""

    def __init__(self, layout):
        self.layout = layout
        self.W = layout.size * UP

    def P(self, part, grp, co):
        x, y = self.layout.pixel(part, grp, co)
        return x * UP, y * UP

    def rect(self, part, grp, a, b):
        """The rectangle between two points of a panel, as [x0, y0, x1, y1]."""
        (ax, ay), (bx, by) = self.P(part, grp, a), self.P(part, grp, b)
        return [min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)]


def smooth_noise(size, cells, rng):
    grid = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, size, endpoint=False)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    a = grid[i][:, i] * (1 - f)[None, :] + grid[i][:, i + 1] * f[None, :]
    b = grid[i + 1][:, i] * (1 - f)[None, :] + grid[i + 1][:, i + 1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def camouflage(W, rng, colours=CAMO, scale=1.0):
    """Hard-edged patches, as painted on vehicles."""
    c1, c2 = max(3, int(9 * scale)), max(6, int(23 * scale))
    n1 = smooth_noise(W, c1, rng) * 0.75 + smooth_noise(W, c2, rng) * 0.25
    n2 = smooth_noise(W, c1, rng) * 0.75 + smooth_noise(W, c2, rng) * 0.25
    img = np.empty((W, W, 3))
    img[:] = colours[0]
    img[n1 > 0.58] = colours[1]
    img[(n2 > 0.62) & (n1 <= 0.58)] = colours[2]
    return img


def height_map(painter):
    """The height above the ground (in the part's own units) of each pixel of the side, front and back panels,
    -1 elsewhere, and of the roof panels their top height."""
    layout, W = painter.layout, painter.W
    z = np.full((W, W), -1.0)
    rows = np.arange(W)[:, None] / UP
    for (part, grp), (left, top) in layout.islands.items():
        x0, x1, y0, y1, z0, z1 = layout.parts[part]
        w, h = layout.dims(part, grp)
        c0, c1 = int(left * UP), int((left + w) * UP) + 1
        r0, r1 = int(top * UP), int((top + h) * UP) + 1
        if grp in ("side", "front", "back"):
            z[r0:r1, c0:c1] = (z1 - (rows[r0:r1] - top) / layout.s(part))
        elif grp == "top":
            z[r0:r1, c0:c1] = z1
    return z


def paint_body(layout, faces, details=None, damaged=False, seed=11, occlusion=None, colours=CAMO, camo_scale=1.0,
               mud_below=3.5, mud_spots=(), plain=None, brighten=1.18):
    """A hull texture for the faces (from the layout json) of a model laid out by `layout`.
    details(draw, painter, rng): paints the vehicle's own hatches, grilles, markings.
    mud_below: height up to which mud is thrown on the sides; mud_spots: (part, x, z, radius) arcs of mud
    around wheels on side panels. plain: {(part, group): colour} panels painted in one colour, not camouflage."""
    rng = np.random.default_rng(seed)
    painter = Painter(layout)
    W = painter.W
    base = camouflage(W, rng, colours, camo_scale)
    if plain:
        for (part, grp), colour in plain.items():
            if (part, grp) in layout.islands:
                left, top = layout.islands[(part, grp)]
                w, h = layout.dims(part, grp)
                base[int(top * UP):int((top + h) * UP) + 1, int(left * UP):int((left + w) * UP) + 1] = colour

    # Each face filled, darker the more it faces down or away from the light.
    shade = Image.new("L", (W, W), 0)
    mask = Image.new("L", (W, W), 0)
    ds, dm = ImageDraw.Draw(shade), ImageDraw.Draw(mask)
    light = {"top": 255, "side": 222, "front": 214, "back": 196, "bottom": 150}
    for f in faces:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) < 3:
            continue
        ds.polygon(poly, fill=light[f["group"]])
        dm.polygon(poly, fill=255)
    img = base * (np.asarray(shade, float)[..., None] / 255.0)

    # Painted shading: sides darken towards the ground.
    z = height_map(painter)
    vertical = z >= 0
    top_z = max(p[5] for p in layout.parts.values())
    t = np.clip(1.0 - z / max(top_z, 1.0), 0, 1)
    img *= np.where(vertical, 1.06 - 0.30 * t, 1.0)[..., None]

    # Stains and grain.
    stains = smooth_noise(W, 30, rng) * 0.6 + smooth_noise(W, 70, rng) * 0.4
    img *= (0.82 + 0.26 * stains)[..., None]
    img *= (0.94 + 0.12 * rng.random((W, W)))[..., None]
    # Dust low down.
    dusty = np.where(vertical, np.clip((mud_below + 2.5 - z) / 4.0, 0, 1), 0) * (0.5 + 0.5 * smooth_noise(W, 40, rng))
    img = img * (1 - dusty[..., None] * 0.6) + np.array(DUST) * dusty[..., None] * 0.6

    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)

    # Rain and oil streaks running down the side, front and back panels.
    for (part, grp), (left, top) in layout.islands.items():
        if grp not in ("side", "front", "back"):
            continue
        w, h = layout.dims(part, grp)
        for _ in range(int(w * h / 3000) + 1):
            x = (left + rng.uniform(0, w)) * UP
            y0 = (top + rng.uniform(0, h * 0.4)) * UP
            length = rng.uniform(0.2, 0.6) * h * UP
            draw.line([(x, y0), (x + rng.uniform(-2, 2), y0 + length)], fill=(70, 76, 84), width=int(rng.uniform(2, 4)))

    # Seams along the model's edges, lit on the upper side.
    for f in faces:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) < 3:
            continue
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        fine = layout.s(f["part"]) < 0.8 * layout.scale or f["group"] == "bottom"
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            a, b = poly[i], poly[(i + 1) % len(poly)]
            draw.line([a, b], fill=SEAM, width=UP if fine else 2 * UP)
            if fine:
                continue
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = cx - mx, cy - my
            d = math.hypot(dx, dy) or 1.0
            ox, oy = dx / d * 2.0 * UP, dy / d * 2.0 * UP
            if dy >= -abs(dx):
                draw.line([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)], fill=LIT, width=UP)

    if details:
        details(draw, painter, rng)
    canvas = weather(canvas, painter, faces, z, rng, mud_below, mud_spots)

    if occlusion is not None:
        ao = np.asarray(occlusion.convert("L").resize((W, W), Image.BILINEAR), float) / 255.0
        arr = np.asarray(canvas, float) * (0.55 + 0.45 * ao)[..., None]
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    # Brighter than it looks here: the game's lighting darkens it.
    canvas = Image.fromarray(np.clip(np.asarray(canvas, float) * brighten, 0, 255).astype(np.uint8))
    if damaged:
        canvas = burn(canvas, rng)

    outside = Image.fromarray(255 - np.asarray(mask))
    canvas.paste((0, 0, 0), mask=outside)
    small = canvas.resize((layout.size, layout.size), Image.LANCZOS)
    return small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def burn(canvas, rng):
    """Soot, scorch and holes for the really damaged model."""
    W = canvas.size[0]
    arr = np.asarray(canvas, float)
    soot = np.clip((smooth_noise(W, 12, rng) - 0.45) * 4, 0, 1)
    arr = arr * (1 - soot[..., None] * 0.85) * 0.62
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)
    for _ in range(int(26 * (W / 2048) ** 2) + 8):
        x, y, r = rng.uniform(0, W), rng.uniform(0, W), rng.uniform(4, 12) * UP
        draw.ellipse([x - r, y - r, x + r, y + r], fill=(18, 16, 14))
        draw.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(90, 50, 25))
    return canvas


def weather(canvas, painter, faces, z, rng, mud_below, mud_spots):
    """Mud thrown up from the ground and worn paint along the edges; returns the weathered canvas."""
    W = painter.W
    mud = Image.new("L", (W, W), 0)
    draw = ImageDraw.Draw(mud)
    low = np.argwhere((z >= 0) & (z < mud_below))
    if len(low):
        for k in rng.choice(len(low), size=min(len(low), int(len(low) / (UP * UP * 30)) + 50), replace=False):
            py, px = low[k]
            s_ = rng.uniform(0.4, 1.5) * UP
            draw.ellipse([px - s_, py - s_ * 0.8, px + s_, py + s_ * 0.8], fill=int(rng.uniform(90, 220)))
    for part, wx, wz, radius in mud_spots:
        for _ in range(150):
            a = rng.uniform(math.pi * 0.05, math.pi * 0.95)
            r = rng.uniform(radius * 1.05, radius * 1.9)
            px, py = painter.P(part, "side", (wx + math.cos(a) * r * 1.2, 0, wz + math.sin(a) * r * 0.9))
            s_ = rng.uniform(0.3, 1.2) * UP
            draw.ellipse([px - s_, py - s_ * 0.8, px + s_, py + s_ * 0.8], fill=int(rng.uniform(120, 255)))
    amount = np.asarray(mud.filter(ImageFilter.GaussianBlur(UP * 0.6)), float)[..., None] / 255.0 * 0.75
    arr = np.asarray(canvas, float) * (1 - amount) + np.array(MUD, float) * amount
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)
    # Worn edges: short light scratches beside the seams.
    for f in faces:
        if f["group"] == "bottom":
            continue
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        for i, sharp in enumerate(f["sharp"]):
            if not sharp or len(poly) < 2:
                continue
            (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
            length = math.hypot(bx - ax, by - ay)
            for _ in range(int(length / (40 * UP))):
                t = rng.uniform(0, 1)
                x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                ox, oy = rng.uniform(-3, 3) * UP, rng.uniform(-3, 3) * UP
                draw.line([(x + ox, y + oy), (x + ox + rng.uniform(-4, 4) * UP, y + oy + rng.uniform(-1, 1) * UP)],
                          fill=(150, 158, 164), width=UP)
    return canvas


# --- details shared by the vehicles ------------------------------------------------------------------

def rivets(draw, points, r=0.5):
    for x, y in points:
        draw.ellipse([x - r * UP, y - r * UP, x + r * UP, y + r * UP], fill=(40, 44, 50))
        draw.ellipse([x - r * UP, y - r * UP, x, y], fill=(200, 206, 212))


def seam(draw, a, b, lit=True):
    draw.line([a, b], fill=SEAM, width=2 * UP)
    if lit:
        draw.line([(a[0], a[1] + 2 * UP), (b[0], b[1] + 2 * UP)], fill=LIT, width=UP)


def grille(draw, box, slats=6, vertical=True):
    x0, y0, x1, y1 = box
    draw.rectangle([x0, y0, x1, y1], fill=(30, 33, 38), outline=SEAM, width=UP)
    for i in range(slats):
        t = (i + 0.5) / slats
        if vertical:
            x = x0 + (x1 - x0) * t
            draw.line([(x, y0 + UP), (x, y1 - UP)], fill=(110, 118, 126), width=UP)
        else:
            y = y0 + (y1 - y0) * t
            draw.line([(x0 + UP, y), (x1 - UP, y)], fill=(110, 118, 126), width=UP)
    draw.line([(x0, y0), (x1, y0)], fill=LIT, width=UP)


def hatch(draw, centre, r):
    """A round hatch, r in drawing pixels."""
    x, y = centre
    draw.ellipse([x - r, y - r, x + r, y + r], outline=SEAM, width=2 * UP)
    draw.arc([x - r + 2 * UP, y - r + 2 * UP, x + r - 2 * UP, y + r - 2 * UP], 180, 300, fill=LIT, width=UP)
    draw.rectangle([x - r * 0.25, y - r * 1.05, x + r * 0.25, y - r * 0.75], fill=(60, 66, 74), outline=SEAM)
    rivets(draw, [(x + math.cos(math.radians(a)) * r * 0.7, y + math.sin(math.radians(a)) * r * 0.7)
                  for a in range(0, 360, 60)], 0.4)


def emblem(draw, centre, size):
    """The faction's mark: a gold chevron on dark blue, white edged (size: half width in drawing pixels / UP)."""
    x, y = centre
    s = size * UP
    draw.rectangle([x - s, y - s * 0.75, x + s, y + s * 0.75], fill=DARK_BLUE, outline=(220, 220, 220), width=UP)
    draw.polygon([(x - s * 0.7, y + s * 0.4), (x, y - s * 0.5), (x + s * 0.7, y + s * 0.4), (x + s * 0.45, y + s * 0.4),
                  (x, y - s * 0.12), (x - s * 0.45, y + s * 0.4)], fill=GOLD)


def hazard(draw, box, stripe=None):
    """Yellow and black diagonal stripes in a rectangle."""
    x0, y0, x1, y1 = [int(round(v)) for v in box]
    w, h = max(1, x1 - x0), max(1, y1 - y0)
    stripe = stripe or max(2 * UP, h * 0.8)
    patch = Image.new("RGB", (w, h), YELLOW)
    pd = ImageDraw.Draw(patch)
    k, i = -h, 0
    while k < w:
        if i % 2:
            pd.polygon([(k, h), (k + stripe, h), (k + stripe + h, 0), (k + h, 0)], fill=(26, 26, 26))
        k += stripe
        i += 1
    draw._image.paste(patch, (x0, y0))
    draw.rectangle([x0, y0, x1, y1], outline=SEAM, width=UP)


def light(draw, box, colour=(230, 226, 200)):
    draw.rectangle(box, fill=colour, outline=SEAM, width=UP)
    x0, y0, x1, y1 = box
    draw.rectangle([x0 + UP, y0 + UP, (x0 + x1) / 2, (y0 + y1) / 2], fill=tuple(min(255, c + 25) for c in colour))


def vision_block(draw, box):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(36, 64, 88), outline=SEAM, width=UP)
    draw.line([(x0 + UP, y0 + UP), (x0 + (x1 - x0) * 0.4, y0 + UP)], fill=(150, 196, 220), width=UP)


def tool(draw, a, b, width=1.2):
    """A pioneer tool strapped on: a shovel or pick handle with its head."""
    draw.line([a, b], fill=(92, 70, 46), width=int(width * UP))
    draw.rectangle([b[0] - 2 * UP, b[1] - 2 * UP, b[0] + 2 * UP, b[1] + 2 * UP], fill=(60, 64, 70), outline=SEAM)


def paint_tread(size=(256, 128), links=4, seed=5):
    """Track links, repeating across u (the way the track runs) `links` times; v: the outer face of the track
    from 0 to 0.7, its inside to 0.8, its sides above."""
    w, h = size[0] * UP, size[1] * UP
    img = Image.new("RGB", (w, h), (34, 35, 37))
    draw = ImageDraw.Draw(img)
    step = w / links
    # Image rows: y = (1 - v) * h; the outer face is the lower 70 %.
    top_outer = h * 0.30
    for i in range(links):
        x0 = i * step
        # the shoe: a plate with a rubber pad and grousers
        draw.rectangle([x0 + step * 0.04, top_outer + UP, x0 + step * 0.96, h - UP], fill=(58, 60, 63))
        draw.rectangle([x0 + step * 0.12, top_outer + h * 0.08, x0 + step * 0.88, h - h * 0.08], fill=(30, 30, 31))
        draw.line([(x0 + step * 0.04, top_outer + UP), (x0 + step * 0.96, top_outer + UP)], fill=(120, 124, 128), width=UP)
        draw.rectangle([x0 + step * 0.42, top_outer, x0 + step * 0.58, h], fill=(78, 80, 84))
        # end connectors
        for yy in (top_outer + h * 0.04, h - h * 0.10):
            draw.rectangle([x0 - step * 0.06, yy, x0 + step * 0.06, yy + h * 0.06], fill=(96, 100, 104))
    # The inside and the sides: dark worn metal.
    draw.rectangle([0, h * 0.2, w, top_outer], fill=(46, 47, 49))
    draw.rectangle([0, 0, w, h * 0.2], fill=(40, 41, 43))
    for i in range(links * 2):
        x = (i + 0.5) * step / 2
        draw.rectangle([x - step * 0.1, h * 0.04, x + step * 0.1, h * 0.16], fill=(64, 66, 70))
    rng = np.random.default_rng(seed)
    arr = np.asarray(img, float)
    arr *= (0.9 + 0.2 * rng.random((h, w)))[..., None]
    dust = np.clip(smooth_noise(max(w, h), 12, rng)[:h, :w] - 0.3, 0, 1)
    arr = arr * (1 - dust[..., None] * 0.5) + np.array(MUD) * dust[..., None] * 0.5
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return img.resize(size, Image.LANCZOS)


def paint_tire_texture(seed=3):
    """The Boxer's tyre (hub in the upper half, tread in the lower): the wheels' UVs follow its layout."""
    import boxer_paint
    return boxer_paint.paint_tire(np.random.default_rng(seed))


def load_faces(path):
    data = json.load(open(path))
    return Layout.from_json(data["layout"]), data["faces"]


# --- the Engineer Vehicle ----------------------------------------------------------------------------

def engineer_details(draw, p, rng):
    """Hatches, grilles, tools, lights, markings of the Engineer Vehicle (coordinates: engineer.py)."""
    P, R = p.P, p.rect
    # Roof of the hull: engine deck grilles at the back, plate seams, tools.
    grille(draw, R("hull", "top", (-13.2, 6.4, 0), (-7.4, 1.0, 0)), slats=9)
    grille(draw, R("hull", "top", (-13.2, -1.0, 0), (-7.4, -6.4, 0)), slats=9)
    grille(draw, R("hull", "top", (-6.6, 3.6, 0), (-4.4, -3.6, 0)), slats=5, vertical=False)
    for x in (-3.6, 1.8):
        seam(draw, P("hull", "top", (x, 8.2, 0)), P("hull", "top", (x, -8.2, 0)))
    rivets(draw, [P("hull", "top", (x, y, 0)) for x in (-3.2, 2.2) for y in range(-7, 8, 2)])
    tool(draw, P("hull", "top", (-3.0, 7.4, 0)), P("hull", "top", (1.2, 7.4, 0)))
    tool(draw, P("hull", "top", (-3.0, 6.8, 0)), P("hull", "top", (0.8, 6.8, 0)))
    # Cab roof: a hatch, periscopes.
    hatch(draw, P("hull", "top", (6.0, 4.6, 0)), 1.2 * p.layout.s("hull") * UP)
    for y in (2.2, 3.4, 5.6, 6.8):
        draw.rectangle(R("hull", "top", (9.1, y - 0.4, 0), (9.6, y + 0.4, 0)), fill=(36, 64, 88), outline=SEAM)
    emblem(draw, P("hull", "top", (-10.2, 0.0, 0)), 1.6 * p.layout.s("hull"))
    # Sides: the cab's windows, a stowed tow cable, house-colour stripe (its own mesh), chevron.
    for x in (4.0, 6.4):
        vision_block(draw, R("hull", "side", (x, 0, 10.4), (x + 1.8, 0, 9.4)))
    cable = [P("hull", "side", (x, 0, 6.4 + 0.2 * math.sin(x * 0.8))) for x in [k * 0.5 for k in range(-26, 4)]]
    draw.line(cable, fill=(70, 74, 80), width=2 * UP)
    draw.line(cable, fill=(150, 156, 160), width=UP)
    emblem(draw, P("hull", "side", (-2.5, 0, 6.0)), 1.1 * p.layout.s("hull"))
    hazard(draw, R("hull", "side", (-14.0, 0, 7.4), (-12.0, 0, 7.0)))
    hazard(draw, R("hull", "side", (11.0, 0, 7.4), (12.6, 0, 7.0)))
    # Skirts: their bolts.
    rivets(draw, [P("hull", "side", (x, 0, 4.6)) for x in range(-12, 12, 2)], 0.45)
    # Front: the cab's windscreen blocks, headlights, hazard bars on the glacis.
    for y in (2.0, 4.3, 6.4):
        vision_block(draw, R("hull", "front", (0, y - 0.8, 10.6), (0, y + 0.8, 9.8)))
    for y in (6.6, -6.6):
        light(draw, R("hull", "front", (0, y - 0.6, 6.6), (0, y + 0.6, 6.0)))
    hazard(draw, R("hull", "front", (0, -8.4, 7.3), (0, -3.0, 6.9)))
    # Back: tail lights, a towing pintle, the exhaust's grille.
    for y in (7.0, -7.0):
        light(draw, R("hull", "back", (0, y - 0.6, 6.8), (0, y + 0.6, 6.2)), (170, 30, 25))
    grille(draw, R("hull", "back", (0, -3.0, 6.6), (0, 3.0, 5.0)), slats=6, vertical=False)
    # The blade: wear along its cutting edge, a hazard stripe along its top.
    hazard(draw, R("blade", "back", (0, -9.0, 5.2), (0, 9.0, 4.7)))
    hazard(draw, R("blade", "front", (0, -9.0, 5.2), (0, 9.0, 4.7)))
    edge = R("blade", "front", (0, -9.2, 1.0), (0, 9.2, 0.0))
    draw.rectangle(edge, fill=(150, 150, 146))
    # The arm: hazard bands at its joints, a chevron on the boom.
    for x0, x1 in ((-16.6, -15.6),):
        hazard(draw, R("arm", "side", (x0, 0, 3.0), (x1, 0, 1.4)))
    emblem(draw, P("arm", "side", (-6.0, 0, 2.2)), 0.8 * p.layout.s("arm"))
    for part in ("arm",):
        rivets(draw, [P(part, "side", (x, 0, 2.95)) for x in range(-14, 0, 2)], 0.4)


def main():
    layout, faces = load_faces(sys.argv[1])
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    spots = [("running", x, 1.4, 1.3) for x in (-10.0, -6.2, -2.4, 1.4, 5.2, 9.0)]
    kw = dict(details=engineer_details, occlusion=occlusion, mud_below=4.5, mud_spots=spots)
    paint_body(layout, faces, **kw).save(os.path.join(out, "eudoz.tga"))
    paint_body(layout, faces, damaged=True, **kw).save(os.path.join(out, "eudoz_d.tga"))
    paint_tread().save(os.path.join(out, "eudoz_tread.tga"))
    print("painted")


if __name__ == "__main__":
    main()

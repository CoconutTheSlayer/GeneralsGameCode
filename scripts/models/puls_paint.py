"""Paints the PULS rocket launcher's textures, and holds what the European vehicle painters share (the
Skyranger and the Wiesel use it too): a panel layout of a model's parts on one texture, like the game's own
vehicle textures (the Boxer's method, boxer_layout.py / boxer_paint.py, made general), and a painter for
crisp panels with dark seams and lit edges, steel blue-grey camouflage, stains, dust, mud, worn edges,
baked ambient occlusion and a burnt damaged version. No Blender needed; puls.py runs it with Python 3:

    python3 scripts/models/puls_paint.py build/models/EUPULS_layout.json OUT_DIR [OCCLUSION.png]
"""
import json
import math
import os
import sys

import numpy as np

try:
    from PIL import Image, ImageDraw, ImageFilter
except ImportError:  # inside Blender only the layout is needed
    Image = ImageDraw = ImageFilter = None

UP = 4  # painted at four times the size, then shrunk: smooth lines
CAMO = [(124, 138, 150), (84, 97, 112), (166, 176, 184)]
SEAM, LIT = (22, 25, 30), (205, 212, 218)
DUST, MUD = (156, 142, 118), (88, 72, 52)
GROUPS = ("top", "side", "front", "back", "bottom")
LIGHT = {"top": 255, "side": 222, "front": 214, "back": 196, "bottom": 90}


# --- the layout ------------------------------------------------------------------------------------

def group(normal):
    """Which panel a face belongs to, by the way it faces."""
    x, y, z = normal
    if abs(z) >= abs(x) and abs(z) >= abs(y):
        return "top" if z > 0 else "bottom"
    if abs(y) >= abs(x):
        return "side"
    return "front" if x > 0 else "back"


class Layout:
    """Where each side of each part lies on a SIZE x SIZE texture (pixels, y down): per part a roof view, one
    side view shared by both sides, the front and the back, each a straight projection of the part, and the
    bottom squeezed small. parts: [(name, (x0, x1, y0, y1, z0, z1), pixels per unit)]."""

    def __init__(self, parts, size=512, pad=4):
        self.size, self.parts = size, [(n, tuple(b), s) for n, b, s in parts]
        self.bounds = {n: (b, s) for n, b, s in self.parts}
        rects = []
        for n, (x0, x1, y0, y1, z0, z1), s in self.parts:
            dims = {"top": ((x1 - x0) * s, (y1 - y0) * s), "side": ((x1 - x0) * s, (z1 - z0) * s),
                    "front": ((y1 - y0) * s, (z1 - z0) * s), "back": ((y1 - y0) * s, (z1 - z0) * s),
                    "bottom": ((x1 - x0) * s / 4, (y1 - y0) * s / 4)}
            rects += [((n, g), math.ceil(w), math.ceil(h)) for g, (w, h) in dims.items()]
        # Shelves, tallest first.
        self.islands = {}
        x = y = shelf = pad
        for key, w, h in sorted(rects, key=lambda r: -r[2]):
            if x + w + pad > size:
                x, y = pad, y + shelf + pad
                shelf = 0
            self.islands[key] = (x, y, w, h)
            x += w + pad
            shelf = max(shelf, h)
        if y + shelf + pad > size:
            raise ValueError(f"layout overflows the {size} texture ({y + shelf + pad})")

    def spec(self):
        return dict(size=self.size, parts=self.parts)

    @staticmethod
    def from_spec(spec):
        return Layout(spec["parts"], spec["size"])

    def pixel(self, part, grp, co):
        (x0, x1, y0, y1, z0, z1), s = self.bounds[part]
        x, y, z = (min(max(v, lo), hi) for v, lo, hi in zip(co, (x0, y0, z0), (x1, y1, z1)))
        left, top, _, _ = self.islands[(part, grp)]
        if grp == "top":
            return left + (x - x0) * s, top + (y1 - y) * s
        if grp == "bottom":
            return left + (x - x0) * s / 4, top + (y - y0) * s / 4
        if grp == "side":
            return left + (x - x0) * s, top + (z1 - z) * s
        if grp == "front":
            return left + (y - y0) * s, top + (z1 - z) * s
        return left + (y1 - y) * s, top + (z1 - z) * s  # the back, seen from behind

    def uv(self, part, grp, co):
        px, py = self.pixel(part, grp, co)
        return px / self.size, 1.0 - py / self.size


# --- painting --------------------------------------------------------------------------------------

def smooth_noise(size, cells, rng):
    grid = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, size, endpoint=False)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    a = grid[i][:, i] * (1 - f)[None, :] + grid[i][:, i + 1] * f[None, :]
    b = grid[i + 1][:, i] * (1 - f)[None, :] + grid[i + 1][:, i + 1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def camouflage(w, rng, colours=CAMO):
    """Hard-edged patches, as painted on vehicles."""
    n1 = smooth_noise(w, 9, rng) * 0.75 + smooth_noise(w, 23, rng) * 0.25
    n2 = smooth_noise(w, 8, rng) * 0.75 + smooth_noise(w, 21, rng) * 0.25
    img = np.empty((w, w, 3))
    img[:] = colours[0]
    img[n1 > 0.58] = colours[1]
    img[(n2 > 0.62) & (n1 <= 0.58)] = colours[2]
    return img


class Canvas:
    """The texture being painted at UP times its size, with the layout's coordinates."""

    def __init__(self, layout):
        self.layout = layout
        self.W = layout.size * UP

    def P(self, part, grp, co):
        x, y = self.layout.pixel(part, grp, co)
        return x * UP, y * UP

    def rect(self, part, grp, a, b):
        """The canvas rectangle between two model points on a panel."""
        (ax, ay), (bx, by) = self.P(part, grp, a), self.P(part, grp, b)
        return [min(ax, bx), min(ay, by), max(ax, bx), max(ay, by)]

    def island(self, part, grp):
        x, y, w, h = self.layout.islands[(part, grp)]
        return x * UP, y * UP, (x + w) * UP, (y + h) * UP


def paint(layout, faces, details=None, occlusion=None, damaged=False, seed=11, muddy=(), small=(), colours=CAMO, brightness=1.18):
    """The texture of a model's panels. faces: from the model script (part, group, px, sharp). details(c, draw,
    rng) paints what is particular to the vehicle; muddy: parts whose lower sides get mud; small: parts drawn
    with finer seams."""
    c = Canvas(layout)
    W = c.W
    rng = np.random.default_rng(seed)
    base = camouflage(W, rng, colours)

    shade = Image.new("L", (W, W), 0)
    mask = Image.new("L", (W, W), 0)
    ds, dm = ImageDraw.Draw(shade), ImageDraw.Draw(mask)
    for f in faces:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) >= 3:
            ds.polygon(poly, fill=LIGHT[f["group"]])
            dm.polygon(poly, fill=255)
    img = base * (np.asarray(shade, float)[..., None] / 255.0)

    # Painted shading: sides, fronts and backs darken towards the ground.
    rows = np.arange(W)[:, None]
    cols = np.arange(W)[None, :]
    factor = np.ones((W, W))
    dusty = np.zeros((W, W))
    dust_noise = smooth_noise(W, 40, rng)
    for (part, grp), _ in layout.islands.items():
        if grp not in ("side", "front", "back"):
            continue
        x0, y0, x1, y1 = c.island(part, grp)
        inside = (rows >= y0) & (rows < y1) & (cols >= x0) & (cols < x1)
        t = np.clip((rows - y0) / max(1, y1 - y0), 0, 1)
        factor = np.where(inside, 1.08 - 0.34 * t, factor)
        d = np.clip((t - 0.5) / 0.5, 0, 1) * (0.55 + 0.45 * dust_noise)
        dusty = np.where(inside, d, dusty)
    img *= factor[..., None]
    stains = smooth_noise(W, 30, rng) * 0.6 + smooth_noise(W, 70, rng) * 0.4
    img *= (0.80 + 0.28 * stains)[..., None]
    img *= (0.94 + 0.12 * rng.random((W, W)))[..., None]
    img = img * (1 - dusty[..., None] * 0.6) + np.array(DUST) * dusty[..., None] * 0.6

    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)

    # Rain and oil streaks running down from the top of the sides and ends.
    for (part, grp), _ in layout.islands.items():
        if grp not in ("side", "front", "back") or part in small:
            continue
        x0, y0, x1, y1 = c.island(part, grp)
        for _ in range(int((x1 - x0) * (y1 - y0) / (UP * UP * 1400))):
            x = rng.uniform(x0, x1)
            y = y0 + rng.uniform(0, (y1 - y0) * 0.3)
            length = rng.uniform(0.2, 0.7) * (y1 - y0)
            draw.line([(x, y), (x + rng.uniform(-2, 2), y + length)], fill=(70, 76, 84), width=int(rng.uniform(UP, 2 * UP)))

    # Seams along the model's edges, lit on the upper side.
    for f in faces:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        fine = f["part"] in small
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            a, b = poly[i], poly[(i + 1) % len(poly)]
            draw.line([a, b], fill=SEAM, width=UP if fine else 2 * UP)
            if fine or f["group"] == "bottom":
                continue
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = cx - mx, cy - my
            d = math.hypot(dx, dy) or 1.0
            ox, oy = dx / d * 2.2 * UP, dy / d * 2.2 * UP
            if dy >= -abs(dx):
                draw.line([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)], fill=LIT, width=UP)

    if details:
        details(c, draw, rng)

    # Mud thrown up by the running gear, on its own layer, softened and laid on thinly.
    mud = Image.new("L", (W, W), 0)
    dmud = ImageDraw.Draw(mud)
    for part in muddy:
        for grp in ("side", "front", "back"):
            x0, y0, x1, y1 = c.island(part, grp)
            for _ in range(int((x1 - x0) / UP * 4)):
                t = rng.uniform(0, 1) ** 0.6
                px, py = rng.uniform(x0, x1), y1 - t * (y1 - y0) * 0.55
                s_ = rng.uniform(0.3, 1.4) * UP
                dmud.ellipse([px - s_, py - s_ * 0.8, px + s_, py + s_ * 0.8], fill=int(rng.uniform(100, 240)))
    amount = np.asarray(mud.filter(ImageFilter.GaussianBlur(UP * 0.6)), float)[..., None] / 255.0 * 0.75
    arr = np.asarray(canvas, float) * (1 - amount) + np.array(MUD, float) * amount
    canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)

    # Worn edges: short light scratches beside the seams.
    for f in faces:
        if f["part"] in small or f["group"] == "bottom":
            continue
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
            for _ in range(int(math.hypot(bx - ax, by - ay) / (40 * UP))):
                t = rng.uniform(0, 1)
                x, y = ax + (bx - ax) * t + rng.uniform(-3, 3) * UP, ay + (by - ay) * t + rng.uniform(-3, 3) * UP
                draw.line([(x, y), (x + rng.uniform(-4, 4) * UP, y + rng.uniform(-1, 1) * UP)], fill=(150, 158, 164),
                          width=UP)

    if occlusion is not None:
        ao = np.asarray(occlusion.convert("L").resize((W, W), Image.BILINEAR), float) / 255.0
        arr = np.asarray(canvas, float) * (0.55 + 0.45 * ao)[..., None]
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if damaged:
        arr = np.asarray(canvas, float)
        soot = np.clip((smooth_noise(W, 12, rng) - 0.45) * 4, 0, 1)
        arr = arr * (1 - soot[..., None] * 0.85) * 0.62
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(canvas)
        keys = [k for k in layout.islands if k[1] in ("top", "side", "front", "back")]
        for _ in range(30):
            x0, y0, x1, y1 = c.island(*keys[int(rng.integers(len(keys)))])
            x, y, r = rng.uniform(x0, x1), rng.uniform(y0, y1), rng.uniform(3, 9) * UP
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(18, 16, 14))
            draw.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(90, 50, 25))

    # The game's lighting darkens textures: paint them brighter than they should look.
    canvas = Image.fromarray(np.clip(np.asarray(canvas, float) * brightness, 0, 255).astype(np.uint8))
    outside = Image.fromarray(255 - np.asarray(mask))
    canvas.paste((0, 0, 0), mask=outside)
    out = canvas.resize((layout.size, layout.size), Image.LANCZOS)
    return out.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


# --- details shared by the vehicles ----------------------------------------------------------------

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
    """A round hatch, r in canvas pixels."""
    x, y = centre
    draw.ellipse([x - r, y - r, x + r, y + r], outline=SEAM, width=2 * UP)
    draw.arc([x - r + 2 * UP, y - r + 2 * UP, x + r - 2 * UP, y + r - 2 * UP], 180, 300, fill=LIT, width=UP)
    draw.rectangle([x - r * 0.25, y - r * 1.05, x + r * 0.25, y - r * 0.75], fill=(60, 66, 74), outline=SEAM)


def emblem(draw, centre, size):
    """The European mark: a gold chevron on dark blue."""
    x, y = centre
    s = size * UP
    draw.rectangle([x - s, y - s * 0.75, x + s, y + s * 0.75], fill=(28, 34, 60), outline=(220, 220, 220), width=UP)
    draw.polygon([(x - s * 0.7, y + s * 0.4), (x, y - s * 0.5), (x + s * 0.7, y + s * 0.4), (x + s * 0.45, y + s * 0.4),
                  (x, y - s * 0.12), (x - s * 0.45, y + s * 0.4)], fill=(235, 200, 40))


def hazard(draw, box, stripes=4):
    """A small yellow and black warning panel."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(225, 185, 40))
    w = (x1 - x0) / stripes
    for i in range(stripes):
        if i % 2:
            draw.polygon([(x0 + i * w, y1), (x0 + (i + 1) * w, y0), (x0 + min(stripes, i + 1.6) * w, y0),
                          (x0 + min(stripes, i + 0.6) * w, y1)], fill=(30, 30, 30))
    draw.rectangle(box, outline=SEAM, width=UP)


def glass(draw, poly):
    """A window: dark blue glass with a sky reflection."""
    draw.polygon(poly, fill=(32, 52, 72), outline=SEAM)
    xs, ys = [p[0] for p in poly], [p[1] for p in poly]
    x0, y0, x1, y1 = min(xs), min(ys), max(xs), max(ys)
    draw.polygon([(x0 + (x1 - x0) * 0.15, y1 - UP), (x0 + (x1 - x0) * 0.35, y0 + UP), (x0 + (x1 - x0) * 0.45, y0 + UP),
                  (x0 + (x1 - x0) * 0.25, y1 - UP)], fill=(110, 150, 180))
    draw.line(poly + [poly[0]], fill=SEAM, width=2 * UP)


def wheel_disc(draw, centre, r):
    """A road wheel seen from the side, r in canvas pixels: rubber rim, dished steel, hub and bolts."""
    x, y = centre
    draw.ellipse([x - r, y - r, x + r, y + r], fill=(34, 35, 38))
    for k, colour in ((0.78, (96, 106, 116)), (0.62, (124, 136, 146)), (0.26, (70, 78, 86))):
        draw.ellipse([x - r * k, y - r * k, x + r * k, y + r * k], fill=colour, outline=SEAM, width=UP)
    draw.arc([x - r * 0.62, y - r * 0.62, x + r * 0.62, y + r * 0.62], 190, 290, fill=LIT, width=UP)
    for a in range(0, 360, 60):
        bx, by = x + math.cos(math.radians(a)) * r * 0.42, y + math.sin(math.radians(a)) * r * 0.42
        draw.ellipse([bx - UP, by - UP, bx + UP, by + UP], fill=(40, 44, 48))


def tube_face(draw, box, cols, rows, cap=None):
    """The front of a launcher pod: a grid of tubes (dark), or of rocket caps (cap colour)."""
    x0, y0, x1, y1 = box
    w, h = (x1 - x0) / cols, (y1 - y0) / rows
    r = min(w, h) * 0.38
    for i in range(cols):
        for j in range(rows):
            cx, cy = x0 + (i + 0.5) * w, y0 + (j + 0.5) * h
            if cap:
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=cap, outline=SEAM, width=UP)
                draw.ellipse([cx - r * 0.45, cy - r * 0.45, cx + r * 0.1, cy + r * 0.1], fill=(230, 226, 210))
            else:
                draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(14, 15, 17), outline=(110, 118, 126), width=UP)
                draw.ellipse([cx - r * 0.6, cy - r * 0.6, cx + r * 0.6, cy + r * 0.6], fill=(5, 5, 6))


def paint_tread(seed=5, shoes=4):
    """Track links: u runs along the track (shoes of it per texture), v across it."""
    rng = np.random.default_rng(seed)
    w, h = 128 * UP, 64 * UP
    img = Image.new("RGB", (w, h), (44, 45, 48))
    draw = ImageDraw.Draw(img)
    step = w / shoes
    for i in range(shoes):
        x = i * step
        draw.rectangle([x + 2 * UP, 2 * UP, x + step - 2 * UP, h - 2 * UP], fill=(66, 67, 70), outline=(22, 22, 24), width=UP)
        draw.rectangle([x + step * 0.35, 3 * UP, x + step * 0.55, h - 3 * UP], fill=(92, 92, 94))   # grouser
        draw.line([(x + step * 0.35, 3 * UP), (x + step * 0.35, h - 3 * UP)], fill=(140, 140, 138), width=UP)
        for y in (h * 0.2, h * 0.8):
            draw.ellipse([x + step * 0.8 - 2 * UP, y - 2 * UP, x + step * 0.8 + 2 * UP, y + 2 * UP], fill=(30, 30, 32))
        draw.rectangle([x, h * 0.44, x + step, h * 0.56], fill=(36, 36, 38))                       # guide horns
    arr = np.asarray(img, float)
    arr = arr * (0.9 + 0.2 * rng.random((h, w)))[..., None]
    dust = smooth_noise(w, 16, rng)[:h] * 0.5
    arr = arr * (1 - dust[..., None] * 0.5) + np.array(DUST) * dust[..., None] * 0.5
    return Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)).resize((128, 64), Image.LANCZOS)


def paint_all(layout_path, out_dir, occlusion_path, details, names, **kwargs):
    """Paints the intact and the damaged texture: names = (intact, damaged) file names."""
    data = json.load(open(layout_path))
    layout = Layout.from_spec(data["layout"])
    occlusion = Image.open(occlusion_path) if occlusion_path and os.path.exists(occlusion_path) else None
    paint(layout, data["faces"], details, occlusion, **kwargs).save(os.path.join(out_dir, names[0]))
    paint(layout, data["faces"], details, occlusion, damaged=True, **kwargs).save(os.path.join(out_dir, names[1]))


# --- the PULS --------------------------------------------------------------------------------------

def puls_details(c, draw, rng):
    import puls  # the shapes' numbers (puls.py imports Blender only when run)
    # Cab: windscreen and side windows, door seams, a roof hatch, the emblem on the doors.
    x0, x1 = puls.CAB_X
    for y in (-1, 1):
        a = c.P("cab", "front", (0, y * 6.6, 8.6))
        b = c.P("cab", "front", (0, y * 0.5, 6.4))
        glass(draw, [(a[0], a[1]), (b[0], a[1]), (b[0], b[1]), (a[0], b[1])])
    for x in (x1 - 4.6, x1 - 2.3):
        a, b = c.P("cab", "side", (x, 0, 8.6)), c.P("cab", "side", (x + 1.9, 0, 7.0))
        glass(draw, [a, (b[0], a[1]), b, (a[0], b[1])])
    seam(draw, c.P("cab", "side", (x1 - 5.0, 0, 9.0)), c.P("cab", "side", (x1 - 5.0, 0, 4.4)), lit=False)
    seam(draw, c.P("cab", "side", (x0 + 0.8, 0, 9.0)), c.P("cab", "side", (x0 + 0.8, 0, 4.4)), lit=False)
    emblem(draw, c.P("cab", "side", (x1 - 2.6, 0, 5.6)), 7)
    hatch(draw, c.P("cab", "top", (x0 + 2.2, 3.5, 9.2)), 4.5 * UP)
    hatch(draw, c.P("cab", "top", (x0 + 2.2, -3.5, 9.2)), 4.5 * UP)
    for y in (-5.6, 5.6):  # headlights
        a, b = c.P("cab", "front", (0, y - 0.7, 5.6)), c.P("cab", "front", (0, y + 0.7, 4.9))
        draw.rectangle([min(a[0], b[0]), a[1], max(a[0], b[0]), b[1]], fill=(230, 226, 200), outline=SEAM, width=UP)
    grille(draw, c.rect("cab", "front", (0, -3.5, 5.9), (0, 3.5, 4.6)), slats=7, vertical=False)
    # Deck: engine grilles, a stowage box lid, rivets along the fenders.
    grille(draw, c.rect("hull", "top", (-12.2, 2.0, 0), (-9.0, -2.0, 0)), slats=6)
    for y in (4.4, -4.4):
        rivets(draw, [c.P("hull", "top", (x, y, 0)) for x in np.arange(-12.5, 6.0, 1.5)])
    hazard(draw, c.rect("hull", "back", (0, -4.6, 4.2), (0, -2.6, 3.6)))
    hazard(draw, c.rect("hull", "back", (0, 2.6, 4.2), (0, 4.6, 3.6)))
    for y in (-3.0, 3.0):  # tail lights
        a, b = c.P("hull", "back", (0, y - 0.5, 3.4)), c.P("hull", "back", (0, y + 0.5, 2.8))
        draw.rectangle([min(a[0], b[0]), a[1], max(a[0], b[0]), b[1]], fill=(170, 30, 25), outline=SEAM, width=UP)
    # Running gear: the road wheels, sprocket and idler on the track side.
    for x, z, r in puls.WHEELS:
        wheel_disc(draw, c.P("track", "side", (x, 0, z)), r * c.layout.bounds["track"][1] * UP)
    # Launcher: pod side seams and lifting lugs, a hazard band, the pods' tube grid and the turntable.
    for x in np.arange(1.5, puls.POD_LENGTH, 2.6):
        seam(draw, c.P("pods", "side", (x, 0, puls.POD_Z1)), c.P("pods", "side", (x, 0, puls.POD_Z0)), lit=False)
    rivets(draw, [c.P("pods", "side", (x, 0, puls.POD_Z1 - 0.3)) for x in np.arange(0.5, puls.POD_LENGTH, 0.9)], 0.4)
    hazard(draw, c.rect("pods", "side", (puls.POD_LENGTH - 1.2, 0, puls.POD_Z1 - 0.2), (puls.POD_LENGTH - 0.3, 0, puls.POD_Z0 + 0.2)), 3)
    for y0, y1 in puls.POD_Y:
        tube_face(draw, c.rect("pods", "front", (0, y0 + 0.25, puls.POD_Z1 - 0.25), (0, y1 - 0.25, puls.POD_Z0 + 0.25)), 2, 3)
        a, b = c.P("pods", "top", (0.6, y0 + 0.3, 0)), c.P("pods", "top", (puls.POD_LENGTH - 0.6, y1 - 0.3, 0))
        draw.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], outline=SEAM, width=UP)
        emblem(draw, c.P("pods", "top", (puls.POD_LENGTH * 0.3, (y0 + y1) / 2, 0)), 14)
    for y0, y1 in puls.POD_Y:
        tube_face(draw, c.rect("rocket", "front", (0, y0 + 0.25, puls.POD_Z1 - 0.25), (0, y1 - 0.25, puls.POD_Z0 + 0.25)), 2, 3,
                  cap=(196, 170, 70))
    hazard(draw, c.rect("turret", "side", (-1.5, 0, 1.3), (1.5, 0, 0.7)), 5)


def main():
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    layout, out = sys.argv[1], sys.argv[2]
    occlusion = sys.argv[3] if len(sys.argv) > 3 else None
    paint_all(layout, out, occlusion, puls_details, ("eupuls.tga", "eupuls_d.tga"), muddy=("track", "hull"),
              small=("rocket",))
    paint_tread().save(os.path.join(out, "eupuls_tread.tga"))
    print("painted")


if __name__ == "__main__":
    main()

"""Paints the Leopard's textures in the style of the game's vehicles, the way boxer_paint.py paints the Boxer:
crisp panels with dark seams and lit edges, rivets, hatches, grilles and lights, painted shading, stains, streaks,
dust and mud over a steel blue-grey camouflage, the baked ambient occlusion multiplied in, and a burnt version for
the damaged model. The painting itself is shared with the Leclerc (leclerc_paint.py); the Leopard's own markings
are in leopard_details().

    python3 scripts/models/leopard_paint.py build/models/EULEO_layout.json OUT_DIR [OCCLUSION.png]
"""
import json
import math
import os
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageFilter

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from leopard_layout import Layout  # noqa: E402

UP = 2  # painted at twice the size, then shrunk: smooth lines

CAMO = [(142, 156, 168), (98, 112, 128), (184, 194, 202)]
SEAM, LIT = (22, 25, 30), (205, 212, 218)
DUST, MUD = (156, 142, 118), (88, 72, 52)
YELLOW = (226, 186, 40)
GLASS = (40, 70, 95)


def smooth_noise(size, cells, rng):
    grid = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, size, endpoint=False)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    a = grid[i][:, i] * (1 - f)[None, :] + grid[i][:, i + 1] * f[None, :]
    b = grid[i + 1][:, i] * (1 - f)[None, :] + grid[i + 1][:, i + 1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def blotches(w, rng, colours=CAMO):
    """Hard-edged rounded patches, as painted on vehicles."""
    n1 = smooth_noise(w, 9, rng) * 0.75 + smooth_noise(w, 23, rng) * 0.25
    n2 = smooth_noise(w, 8, rng) * 0.75 + smooth_noise(w, 21, rng) * 0.25
    img = np.empty((w, w, 3))
    img[:] = colours[0]
    img[n1 > 0.58] = colours[1]
    img[(n2 > 0.62) & (n1 <= 0.58)] = colours[2]
    return img


class Painter:
    """Paints one tank's body texture from its layout (faces on the texture) and its own details."""

    def __init__(self, layout_json, occlusion=None):
        data = json.load(open(layout_json))
        self.layout = Layout(data["spec"])
        self.faces = data["faces"]
        self.size = self.layout.size
        self.w = self.size * UP
        self.occlusion = occlusion

    def P(self, part, grp, co):
        x, y = self.layout.pixel(part, grp, co)
        return x * UP, y * UP

    def box(self, part, grp, a, b):
        """A rectangle on an island between two points of the part: (left, top, right, bottom)."""
        (x0, y0), (x1, y1) = self.P(part, grp, a), self.P(part, grp, b)
        return [min(x0, x1), min(y0, y1), max(x0, x1), max(y0, y1)]

    def islands(self, part, groups=("side", "front", "back")):
        for grp in groups:
            left, top, right, bottom = self.layout.extent(part, grp)
            yield grp, (left * UP, top * UP, right * UP, bottom * UP)

    def paint(self, details, camo, damaged=False, seed=11, lower=(("hull", 3.6),)):
        """details(painter, draw, rng) paints the markings; camo(w, rng) the base; lower: parts whose lower
        islands get dust and mud, with the height (z) below which the mud lies."""
        rng = np.random.default_rng(seed)
        w = self.w
        base = camo(w, rng)
        shade = Image.new("L", (w, w), 0)
        mask = Image.new("L", (w, w), 0)
        ds, dm = ImageDraw.Draw(shade), ImageDraw.Draw(mask)
        light = {"top": 255, "side": 222, "front": 214, "back": 196, "bottom": 90}
        for f in self.faces:
            poly = [(x * UP, y * UP) for x, y in f["px"]]
            if len(poly) < 3:
                continue
            ds.polygon(poly, fill=light[f["group"]])
            dm.polygon(poly, fill=255)
        img = base * (np.asarray(shade, float)[..., None] / 255.0)

        # Painted shading: the side, front and back views darken towards the ground.
        rows = np.arange(w)[:, None].astype(float)
        cols = np.arange(w)[None, :].astype(float)
        dust = np.zeros((w, w))
        for part, mud_z in lower:
            for grp, (l, t, r, b) in self.islands(part):
                inside = (rows >= t) & (rows < b) & (cols >= l) & (cols < r)
                k = np.clip((rows - t) / max(b - t, 1), 0, 1)
                img *= np.where(inside, 1.08 - 0.36 * k, 1.0)[..., None]
                dust += inside * np.clip((k - 0.45) / 0.55, 0, 1)
        for part in self.layout.spec["parts"]:
            if all(part != p for p, _ in lower):
                for grp, (l, t, r, b) in self.islands(part):
                    inside = (rows >= t) & (rows < b) & (cols >= l) & (cols < r)
                    k = np.clip((rows - t) / max(b - t, 1), 0, 1)
                    img *= np.where(inside, 1.06 - 0.22 * k, 1.0)[..., None]

        stains = smooth_noise(w, 30, rng) * 0.6 + smooth_noise(w, 70, rng) * 0.4
        img *= (0.82 + 0.26 * stains)[..., None]
        img *= (0.94 + 0.12 * rng.random((w, w)))[..., None]
        dusty = dust * (0.55 + 0.45 * smooth_noise(w, 40, rng))
        img = img * (1 - dusty[..., None] * 0.6) + np.array(DUST) * dusty[..., None] * 0.6

        canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(canvas)
        # Rain streaks running down the side, front and back views.
        for part, _ in lower:
            for grp, (l, t, r, b) in self.islands(part):
                for _ in range(int((r - l) / (22 * UP))):
                    x = rng.uniform(l, r)
                    y0 = t + rng.uniform(0, (b - t) * 0.4)
                    draw.line([(x, y0), (x + rng.uniform(-2, 2) * UP, y0 + rng.uniform(0.2, 0.6) * (b - t))],
                              fill=(70, 76, 84), width=UP)
        self.seams(draw)
        details(self, draw, rng)
        canvas = self.weather(canvas, rng, lower)

        if self.occlusion is not None:
            ao = np.asarray(self.occlusion.convert("L").resize((w, w), Image.BILINEAR), float) / 255.0
            arr = np.asarray(canvas, float) * (0.55 + 0.45 * ao)[..., None]
            canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

        if damaged:
            arr = np.asarray(canvas, float)
            soot = np.clip((smooth_noise(w, 12, rng) - 0.45) * 4, 0, 1)
            arr = arr * (1 - soot[..., None] * 0.85) * 0.62
            canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
            draw = ImageDraw.Draw(canvas)
            for _ in range(40):
                x, y, r = rng.uniform(0, w), rng.uniform(0, w * 0.68), rng.uniform(3, 10) * UP
                draw.ellipse([x - r, y - r, x + r, y + r], fill=(18, 16, 14))
                draw.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(90, 50, 25))

        outside = Image.fromarray(255 - np.asarray(mask))
        canvas.paste((0, 0, 0), mask=outside)
        self.wheel(canvas, damaged)
        small = canvas.resize((self.size, self.size), Image.LANCZOS)
        return small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))

    def seams(self, draw):
        """Dark seams along the model's edges, lit on the upper side of each face."""
        for f in self.faces:
            poly = [(x * UP, y * UP) for x, y in f["px"]]
            if len(poly) < 3:
                continue
            cx = sum(p[0] for p in poly) / len(poly)
            cy = sum(p[1] for p in poly) / len(poly)
            fine = f["part"] != "hull"
            for i, sharp in enumerate(f["sharp"]):
                if not sharp:
                    continue
                a, b = poly[i], poly[(i + 1) % len(poly)]
                draw.line([a, b], fill=SEAM, width=UP * (1 if fine else 2))
                mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
                dx, dy = cx - mx, cy - my
                d = math.hypot(dx, dy) or 1.0
                ox, oy = dx / d * 2.0 * UP, dy / d * 2.0 * UP
                if f["group"] != "bottom" and dy >= -abs(dx):
                    draw.line([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)], fill=LIT, width=UP)

    def weather(self, canvas, rng, lower):
        """Mud thrown up by the tracks on the lower side, front and back views, and worn paint on the edges."""
        mud = Image.new("L", (self.w, self.w), 0)
        draw = ImageDraw.Draw(mud)
        for part, mud_z in lower:
            (x0, x1), (y0, y1), (z0, z1) = self.layout.spec["parts"][part]["box"]
            for grp, (l, t, r, b) in self.islands(part):
                zt = t + (z1 - mud_z) / (z1 - z0) * (b - t)
                for _ in range(int((r - l) * 1.2 / UP)):
                    px = rng.uniform(l, r)
                    py = rng.uniform(zt, b) if rng.random() < 0.8 else rng.uniform(zt - (b - zt) * 0.6, zt)
                    s_ = rng.uniform(0.4, 1.6) * UP
                    draw.ellipse([px - s_, py - s_ * 0.8, px + s_, py + s_ * 0.8], fill=int(rng.uniform(110, 240)))
        amount = np.asarray(mud.filter(ImageFilter.GaussianBlur(UP * 0.8)), float)[..., None] / 255.0 * 0.8
        arr = np.asarray(canvas, float) * (1 - amount) + np.array(MUD, float) * amount
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(canvas)
        for f in self.faces:
            if f["group"] == "bottom" or f["part"] == "barrel":
                continue
            poly = [(x * UP, y * UP) for x, y in f["px"]]
            for i, sharp in enumerate(f["sharp"]):
                if not sharp:
                    continue
                (ax, ay), (bx, by) = poly[i], poly[(i + 1) % len(poly)]
                length = math.hypot(bx - ax, by - ay)
                for _ in range(int(length / (30 * UP))):
                    t = rng.uniform(0, 1)
                    x, y = ax + (bx - ax) * t, ay + (by - ay) * t
                    ox, oy = rng.uniform(-3, 3) * UP, rng.uniform(-3, 3) * UP
                    draw.line([(x + ox, y + oy), (x + ox + rng.uniform(-4, 4) * UP, y + oy + rng.uniform(-1, 1) * UP)],
                              fill=(150, 158, 164), width=UP)
        return canvas

    def wheel(self, canvas, damaged):
        """The road wheel every wheel disc shows, and the rubber strip of their tyres."""
        spec = self.layout.spec["wheel"]
        draw = ImageDraw.Draw(canvas)
        cx, cy, r = (v * UP for v in spec["disc"])
        tone = 0.6 if damaged else 1.0

        def c(rgb):
            return tuple(int(v * tone) for v in rgb)
        draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=c((34, 35, 38)))                 # rubber rim
        draw.ellipse([cx - r * 0.8, cy - r * 0.8, cx + r * 0.8, cy + r * 0.8], fill=c((100, 112, 124)), outline=SEAM, width=UP * 2)
        draw.arc([cx - r * 0.78, cy - r * 0.78, cx + r * 0.78, cy + r * 0.78], 190, 290, fill=c(LIT), width=UP * 2)
        draw.ellipse([cx - r * 0.55, cy - r * 0.55, cx + r * 0.55, cy + r * 0.55], fill=c((82, 94, 106)), outline=SEAM, width=UP)
        draw.ellipse([cx - r * 0.25, cy - r * 0.25, cx + r * 0.25, cy + r * 0.25], fill=c((120, 132, 142)), outline=SEAM, width=UP)
        for a in range(0, 360, 45):
            bx, by = cx + math.cos(math.radians(a)) * r * 0.4, cy + math.sin(math.radians(a)) * r * 0.4
            draw.ellipse([bx - 3 * UP, by - 3 * UP, bx + 3 * UP, by + 3 * UP], fill=c((40, 44, 48)))
        # mud on the lower half of the wheel
        for k in range(160):
            a = math.radians(20 + 140 * (k % 37) / 37)
            rr = r * (0.55 + 0.45 * ((k * 7919) % 100) / 100)
            px, py = cx + math.cos(a) * rr, cy + math.sin(a) * rr
            draw.ellipse([px - 3 * UP, py - 2 * UP, px + 3 * UP, py + 2 * UP], fill=c(MUD))
        x0, y0, x1, y1 = (v * UP for v in spec["tyre"])
        draw.rectangle([x0, y0, x1, y1], fill=c((36, 36, 38)))
        draw.rectangle([x0, y0 + (y1 - y0) * 0.6, x1, y1], fill=c((70, 62, 50)))


# --- markings, shared ------------------------------------------------------------------------------

def rivets(draw, points, r=0.6):
    for x, y in points:
        draw.ellipse([x - r * UP, y - r * UP, x + r * UP, y + r * UP], fill=(40, 44, 50))
        draw.ellipse([x - r * UP, y - r * UP, x, y], fill=(200, 206, 212))


def seam(draw, a, b, lit=True):
    draw.line([a, b], fill=SEAM, width=2 * UP)
    if lit:
        draw.line([(a[0], a[1] + 2 * UP), (b[0], b[1] + 2 * UP)], fill=LIT, width=UP)


def grille(draw, rect, slats=6, vertical=True):
    x0, y0, x1, y1 = rect
    draw.rectangle([x0, y0, x1, y1], fill=(30, 33, 38), outline=SEAM, width=UP)
    for i in range(slats):
        t = (i + 0.5) / slats
        if vertical:
            x = x0 + (x1 - x0) * t
            draw.line([(x, y0 + UP), (x, y1 - UP)], fill=(110, 118, 126), width=UP * 2)
        else:
            y = y0 + (y1 - y0) * t
            draw.line([(x0 + UP, y), (x1 - UP, y)], fill=(110, 118, 126), width=UP * 2)
    draw.line([(x0, y0), (x1, y0)], fill=LIT, width=UP)


def hatch(draw, centre, r):
    x, y = centre
    draw.ellipse([x - r, y - r, x + r, y + r], outline=SEAM, width=2 * UP)
    draw.arc([x - r + 2 * UP, y - r + 2 * UP, x + r - 2 * UP, y + r - 2 * UP], 180, 300, fill=LIT, width=UP)
    draw.rectangle([x - r * 0.25, y - r * 1.05, x + r * 0.25, y - r * 0.75], fill=(60, 66, 74), outline=SEAM)
    rivets(draw, [(x + math.cos(math.radians(a)) * r * 0.7, y + math.sin(math.radians(a)) * r * 0.7)
                  for a in range(0, 360, 60)], 0.45)


def emblem(draw, centre, size):
    """The European arm of service mark: a gold chevron on a dark blue square."""
    x, y = centre
    s = size * UP
    draw.rectangle([x - s, y - s * 0.75, x + s, y + s * 0.75], fill=(28, 34, 60), outline=(220, 220, 220), width=UP)
    draw.polygon([(x - s * 0.7, y + s * 0.4), (x, y - s * 0.5), (x + s * 0.7, y + s * 0.4), (x + s * 0.45, y + s * 0.4),
                  (x, y - s * 0.12), (x - s * 0.45, y + s * 0.4)], fill=(235, 200, 40))


def hazard(draw, rect, stripes=4):
    """A small yellow and black hazard patch."""
    x0, y0, x1, y1 = rect
    draw.rectangle(rect, fill=YELLOW, outline=SEAM, width=UP)
    step = (x1 - x0) / stripes
    for k in range(stripes):
        if k % 2:
            draw.polygon([(x0 + k * step, y1), (x0 + (k + 1) * step, y0), (x0 + min(k + 2, stripes) * step, y0),
                          (x0 + (k + 1) * step, y1)], fill=(30, 30, 30))


def light(draw, rect, colour=(230, 226, 200)):
    draw.rectangle(rect, fill=colour, outline=SEAM, width=UP)


# --- the Leopard -----------------------------------------------------------------------------------

def leopard_details(p, draw, rng):
    top = lambda x, y, z=6.0: p.P("hull", "top", (x, y, z))  # noqa: E731
    side = lambda x, z: p.P("hull", "side", (x, 8.4, z))  # noqa: E731

    # Engine deck: three rows of grilles, plate seams and rivets, the driver's hatch, the glacis seam.
    for x0, x1 in ((-13.6, -11.4), (-11.0, -8.8)):
        for y0, y1 in ((-4.4, -0.3), (0.3, 4.4)):
            grille(draw, p.box("hull", "top", (x0, y0, 6.2), (x1, y1, 6.2)), slats=7)
    grille(draw, p.box("hull", "top", (-8.5, -4.4, 6.2), (-7.2, 4.4, 6.2)), slats=10, vertical=False)
    for x in (-6.5, 1.0, 7.5):
        seam(draw, top(x, 7.8), top(x, -7.8))
        rivets(draw, [top(x + 0.4, y) for y in np.arange(-7.4, 7.6, 1.2)])
    for y in (5.2, -5.2):
        seam(draw, top(-14.2, y), top(10.8, y), lit=False)
        rivets(draw, [top(x, y + 0.5) for x in np.arange(-13.5, 10.5, 1.5)])
    hatch(draw, top(9.0, -2.4), 0.8 * 20 * UP)
    seam(draw, top(11.0, 8.0), top(11.0, -8.0))
    for y in (6.8, -6.8):
        light(draw, p.box("hull", "top", (13.2, y - 0.4, 5.6), (13.8, y + 0.4, 5.6)))
    hazard(draw, p.box("hull", "top", (14.6, 7.6, 4.7), (15.2, 6.2, 4.7)), 3)
    hazard(draw, p.box("hull", "top", (14.6, -6.2, 4.7), (15.2, -7.6, 4.7)), 3)
    # Fuel can racks and a tow cable along the rear deck edges.
    for s in (1, -1):
        cable = [top(x, s * (6.6 + 0.2 * math.sin(x))) for x in np.arange(-13.5, -1.0, 0.5)]
        draw.line(cable, fill=(70, 74, 80), width=3 * UP)
        draw.line(cable, fill=(150, 156, 160), width=UP)

    # Skirts (the side view): the heavy front sections bolted on, the light panels behind, the emblem.
    for x in (-10.7, -6.9, -3.1, 0.7, 4.6):
        seam(draw, side(x, 5.9), side(x, 2.9), lit=False)
    seam(draw, side(8.6, 5.9), side(8.6, 2.1))
    seam(draw, side(11.7, 5.9), side(11.7, 2.1), lit=False)
    rivets(draw, [side(x, 5.5) for x in np.arange(-14.0, 14.6, 1.0)])
    rivets(draw, [side(x, 2.7) for x in np.arange(8.9, 13.4, 0.9)])
    emblem(draw, side(10.2, 4.1), 16)
    seam(draw, side(-15.0, 6.0), side(15.0, 6.0))

    # Front: the headlights, tow hooks; back: the exhaust grilles, tail lights, a stowage box lid.
    front = lambda y, z: p.P("hull", "front", (15.0, y, z))  # noqa: E731
    back = lambda y, z: p.P("hull", "back", (-15.0, y, z))  # noqa: E731
    for y in (6.8, -6.8):
        light(draw, p.box("hull", "front", (14.0, y - 0.5, 5.5), (14.0, y + 0.5, 5.1)))
    for y in (3.0, -3.0):
        hx, hy = front(y, 2.6)
        draw.ellipse([hx - 6 * UP, hy - 5 * UP, hx + 6 * UP, hy + 5 * UP], outline=YELLOW, width=2 * UP)
    for y in (3.8, -3.8):
        grille(draw, p.box("hull", "back", (-15.0, y - 1.2, 4.0), (-15.0, y + 1.2, 3.0)), slats=5, vertical=False)
    for y in (7.3, -7.3):
        light(draw, p.box("hull", "back", (-15.0, y - 0.4, 5.6), (-15.0, y + 0.4, 5.1)), (170, 30, 25))

    # Turret: roof seams, hatches, the sights' glass, a hazard patch on the basket; the emblem on the cheeks.
    ttop = lambda x, y: p.P("turret", "top", (x, y, 3.4))  # noqa: E731
    tside = lambda x, z: p.P("turret", "side", (x, 6.0, z))  # noqa: E731
    for (x, y) in ((-4.0, 2.8), (-4.0, -2.4)):
        hatch(draw, ttop(x, y), 0.95 * 18 * UP)
    for x in (-6.8, 0.4):
        seam(draw, ttop(x, 5.6), ttop(x, -5.6))
    rivets(draw, [ttop(x, y) for x in np.arange(-7.8, 4.2, 1.2) for y in (5.4, -5.4)])
    draw.rectangle(p.box("turret", "top", (1.7, -4.4, 4.35), (3.6, -3.0, 4.35)), outline=SEAM, width=UP)
    hazard(draw, p.box("turret", "top", (-10.0, 1.4, 2.7), (-8.9, -1.4, 2.7)), 5)
    for x in np.arange(-10.0, -8.9, 0.25):
        draw.line([ttop(x, 4.3), ttop(x, -4.3)], fill=(60, 64, 70), width=UP)
    seam(draw, tside(3.8, 3.4), tside(3.8, 0.2))
    seam(draw, tside(-8.4, 2.8), tside(4.6, 2.8), lit=False)
    rivets(draw, [tside(x, 3.1) for x in np.arange(-7.4, 3.6, 0.9)])
    emblem(draw, tside(-1.2, 1.7), 13)
    # (The gunner's sight window is left unpainted: the wedges' faces share that part of the front view.)
    draw.rectangle(p.box("turret", "side", (-2.2, 6.0, 5.0), (-0.9, 6.0, 4.55)), fill=GLASS, outline=SEAM, width=UP)
    # Gun: the bore at the muzzle, a band on the sleeve.
    mx, my = p.P("barrel", "front", (21.6, 0.0, 0.0))
    draw.ellipse([mx - 4 * UP, my - 4 * UP, mx + 4 * UP, my + 4 * UP], fill=(12, 12, 14))


def leopard_camo(w, rng):
    """The Leopard's dark scheme: dark steel blue-grey with mid and pale patches (the Leclerc is pale)."""
    return blotches(w, rng, [(96, 110, 126), (134, 148, 162), (172, 182, 192)])


def paint_tread(seed=3, pads=6, size=256):
    """The track: rubber pads on steel links (v 0.5..1, the top half of the picture), the link ends with their
    connectors (the next quarter), the inside with guide horns (the bottom quarter). u repeats; pads per turn."""
    rng = np.random.default_rng(seed)
    w = size * 4
    img = Image.new("RGB", (w, w), (58, 58, 60))
    draw = ImageDraw.Draw(img)
    step = w / pads
    for k in range(pads):
        x = k * step
        # pads: dark rubber blocks with a steel end connector between the links
        draw.rectangle([x + step * 0.06, w * 0.03, x + step * 0.78, w * 0.47], fill=(36, 36, 38))
        draw.rectangle([x + step * 0.1, w * 0.06, x + step * 0.74, w * 0.2], fill=(46, 46, 48))
        draw.rectangle([x + step * 0.82, 0, x + step * 0.98, w * 0.5], fill=(104, 104, 104))
        draw.line([(x + step * 0.82, 0), (x + step * 0.82, w * 0.5)], fill=(150, 150, 146), width=4)
        # link ends: the end connectors and the pin
        draw.rectangle([x + step * 0.05, w * 0.53, x + step * 0.95, w * 0.72], fill=(78, 76, 72), outline=(30, 30, 30), width=4)
        draw.ellipse([x + step * 0.4, w * 0.58, x + step * 0.6, w * 0.67], fill=(130, 128, 124))
        # inside: the guide horn
        draw.rectangle([x + step * 0.35, w * 0.76, x + step * 0.65, w * 0.97], fill=(96, 96, 96), outline=(30, 30, 30), width=4)
    arr = np.asarray(img, float)
    dust = smooth_noise(w, 16, rng)
    arr = arr * (1 - dust[..., None] * 0.35) + np.array(DUST) * dust[..., None] * 0.35
    img = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    return img.resize((size, size), Image.LANCZOS)


def main():
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    painter = Painter(sys.argv[1], occlusion)
    painter.paint(leopard_details, leopard_camo).save(os.path.join(out, "euleo.tga"))
    painter.paint(leopard_details, leopard_camo, damaged=True).save(os.path.join(out, "euleo_d.tga"))
    paint_tread().save(os.path.join(out, "euleo_tread.tga"))
    print("painted")


if __name__ == "__main__":
    main()

"""Paints the European jets' textures (the Typhoon's, and the Rafale's and Tornado's through rafale_paint.py
and tornado_paint.py) in the style of the game's aircraft: crisp panels with dark seams and lit edges,
painted shading, camouflage, exhaust soot and wear. The model script (typhoon.py) writes the model's faces
as they lie on the texture and the marks to paint (canopy, intakes, nozzles, emblems...) into a JSON file
and runs this with Python 3, Pillow and NumPy, with the ambient occlusion it baked:

    python3 scripts/models/typhoon_paint.py LAYOUT.json OUT_DIR [OCCLUSION.png]

Also holds the texture layout (Layout), which the model scripts import inside Blender: each side of the jet
is a straight projection on its own island, the top (planform) the largest, as the game's camera looks down.
"""
import json
import math
import os
import sys

SIZE = 512
# Islands: (left, top, right, bottom) in pixels of the texture.
ISLANDS = {
    "top": (4, 4, 508, 316),
    "side": (4, 322, 340, 432),
    "bottom": (346, 322, 508, 432),
    "front": (4, 438, 170, 508),
    "back": (176, 438, 342, 508),
    "stores": (348, 438, 508, 508),   # tanks, missiles and bombs: plainly painted, seen from the side
}


class Layout:
    """Where a point of the model lies on the texture, given the model's extent (x, y, z ranges)."""

    def __init__(self, xr, yr, zr):
        self.xr, self.yr, self.zr = tuple(xr), tuple(yr), tuple(zr)
        (x0, x1), (y0, y1), (z0, z1) = self.xr, self.yr, self.zr
        self.scale = {}
        for grp, (l, t, r, b) in ISLANDS.items():
            if grp in ("top", "bottom"):
                w, h = x1 - x0, y1 - y0
            elif grp in ("side", "stores"):
                w, h = x1 - x0, z1 - z0
            else:
                w, h = y1 - y0, z1 - z0
            self.scale[grp] = min((r - l) / w, (b - t) / h)

    @staticmethod
    def group(normal):
        x, y, z = normal
        if abs(z) >= abs(x) * 0.8 and abs(z) >= abs(y) * 0.8:
            return "top" if z > 0 else "bottom"
        if abs(y) >= abs(x):
            return "side"
        return "front" if x > 0 else "back"

    def pixel(self, grp, co):
        x, y, z = co
        (x0, x1), (y0, y1), (z0, z1) = self.xr, self.yr, self.zr
        x, y, z = min(max(x, x0), x1), min(max(y, y0), y1), min(max(z, z0), z1)
        left, top = ISLANDS[grp][:2]
        s = self.scale[grp]
        if grp == "top":
            return left + (x1 - x) * s, top + (y1 - y) * s        # nose to the left, left wing up
        if grp == "bottom":
            return left + (x1 - x) * s, top + (y - y0) * s
        if grp in ("side", "stores"):
            return left + (x1 - x) * s, top + (z1 - z) * s
        if grp == "front":
            return left + (y1 - y) * s, top + (z1 - z) * s
        return left + (y - y0) * s, top + (z1 - z) * s

    def uv(self, grp, co):
        px, py = self.pixel(grp, co)
        return px / SIZE, 1.0 - py / SIZE

    def to_dict(self):
        return dict(xr=self.xr, yr=self.yr, zr=self.zr)


# --- painting (outside Blender) -------------------------------------------------------------------

UP = 4
W = SIZE * UP
SEAM, LIT = (24, 27, 32), (214, 220, 226)
NAVY, GOLD, HAZARD = (26, 34, 64), (232, 192, 52), (226, 184, 30)


def _np():
    import numpy as np
    return np


def smooth_noise(size, cells, rng):
    np = _np()
    grid = rng.random((cells + 1, cells + 1))
    t = np.linspace(0, cells, size, endpoint=False)
    i = t.astype(int)
    f = t - i
    f = f * f * (3 - 2 * f)
    a = grid[i][:, i] * (1 - f)[None, :] + grid[i][:, i + 1] * f[None, :]
    b = grid[i + 1][:, i] * (1 - f)[None, :] + grid[i + 1][:, i + 1] * f[None, :]
    return a * (1 - f)[:, None] + b * f[:, None]


def camouflage(scheme, rng):
    """The base colours. scheme: {"colours": [...], "pattern": "soft" | "splinter" | "plain"}."""
    np = _np()
    colours = [np.array(c, float) for c in scheme["colours"]]
    img = np.empty((W, W, 3))
    img[:] = colours[0]
    pattern = scheme.get("pattern", "soft")
    if pattern == "plain":
        tone = smooth_noise(W, 6, rng)
        img *= (0.94 + 0.12 * tone)[..., None]
    elif pattern == "soft":
        # Two-tone air superiority grey: lighter underneath is done by the islands, here soft blotches.
        n1 = smooth_noise(W, 7, rng) * 0.7 + smooth_noise(W, 17, rng) * 0.3
        mix = np.clip((n1 - 0.5) * 6, 0, 1)[..., None]
        img = img * (1 - mix) + colours[1] * mix
    else:
        # Splinter camouflage: hard-edged angular patches, as on strike aircraft.
        from PIL import Image, ImageDraw
        layer = Image.new("L", (W, W), 0)
        d = ImageDraw.Draw(layer)
        for _ in range(int(scheme.get("patches", 70))):
            cx, cy = rng.uniform(0, W), rng.uniform(0, W)
            r = rng.uniform(25, 70) * UP
            n = int(rng.integers(4, 7))
            a0 = rng.uniform(0, math.pi)
            pts = [(cx + math.cos(a0 + k * 2 * math.pi / n) * r * rng.uniform(0.5, 1.2),
                    cy + math.sin(a0 + k * 2 * math.pi / n) * r * rng.uniform(0.3, 1.0)) for k in range(n)]
            d.polygon(pts, fill=int(rng.integers(1, len(colours))) * 80)
        arr = np.asarray(layer)
        for k in range(1, len(colours)):
            img[arr == k * 80] = colours[k]
    return img


def paint(data, damaged=False, occlusion=None, seed=7):
    np = _np()
    from PIL import Image, ImageDraw, ImageFilter
    lay = data["layout"]
    layout = Layout(lay["xr"], lay["yr"], lay["zr"])
    rng = np.random.default_rng(seed)

    def P(grp, co):
        x, y = layout.pixel(grp, co)
        return x * UP, y * UP

    base = camouflage(data["scheme"], rng)
    # The underside is the light grey of the scheme, the sides blend into it.
    under = np.array(data["scheme"].get("under", (170, 176, 182)), float)

    shade = Image.new("L", (W, W), 0)
    mask = Image.new("L", (W, W), 0)
    isl = Image.new("L", (W, W), 0)
    ds, dm, di = ImageDraw.Draw(shade), ImageDraw.Draw(mask), ImageDraw.Draw(isl)
    light = {"top": 255, "side": 228, "front": 222, "back": 200, "bottom": 205}
    for f in data["faces"]:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) < 3:
            continue
        ds.polygon(poly, fill=light[f["group"]])
        dm.polygon(poly, fill=255)
    for grp, (l, t, r, b) in ISLANDS.items():
        if grp == "bottom":
            di.rectangle([l * UP, t * UP, r * UP, b * UP], fill=255)
    img = base.copy()
    bottom = np.asarray(isl, float)[..., None] / 255.0
    img = img * (1 - bottom) + under * bottom
    # The side view: the lower half of the fuselage fades to the underside grey.
    l, t, r, b = ISLANDS["side"]
    zlo, zhi = layout.zr
    zmid = data.get("belly_blend", (zlo + zhi) / 2)
    _, ymid = layout.pixel("side", (0, 0, zmid))
    v = np.arange(W)[:, None] / UP
    rows = (v >= t) & (v < b)
    blend = np.clip((v - ymid) / 10.0, 0, 1) * rows
    img = img * (1 - blend[..., None]) + under * blend[..., None]
    img = img * (np.asarray(shade, float)[..., None] / 255.0)
    # The stores' island: the underside grey, lit from above.
    l, t, r, b = [c * UP for c in ISLANDS["stores"]]
    rows = np.clip((np.arange(W) - t) / max(1, b - t), 0, 1)
    tone = (1.08 - 0.4 * rows)[t:b, None, None]
    img[t:b, l:r] = under * 0.92 * tone
    dm.rectangle([l, t, r, b], fill=255)

    # Grain and stains, lighter than on ground vehicles: aircraft are kept cleaner.
    stains = smooth_noise(W, 30, rng) * 0.6 + smooth_noise(W, 80, rng) * 0.4
    img *= (0.88 + 0.18 * stains)[..., None]
    img *= (0.96 + 0.08 * rng.random((W, W)))[..., None]

    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)

    # Seams along the model's edges, lit on the face's side.
    for f in data["faces"]:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            a, c = poly[i], poly[(i + 1) % len(poly)]
            draw.line([a, c], fill=SEAM, width=2 * UP)
            mx, my = (a[0] + c[0]) / 2, (a[1] + c[1]) / 2
            dx, dy = cx - mx, cy - my
            d = math.hypot(dx, dy) or 1.0
            ox, oy = dx / d * 1.6 * UP, dy / d * 1.6 * UP
            draw.line([(a[0] + ox, a[1] + oy), (c[0] + ox, c[1] + oy)], fill=LIT, width=UP)

    for mark in data["marks"]:
        paint_mark(draw, canvas, mark, P, rng)

    if occlusion is not None:
        ao = np.asarray(occlusion.convert("L").resize((W, W), Image.BILINEAR), float) / 255.0
        l, t, r, b = [c * UP for c in ISLANDS["stores"]]
        ao[t:b, l:r] = 1.0
        arr = np.asarray(canvas, float) * (0.6 + 0.4 * ao)[..., None]
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))

    if damaged:
        arr = np.asarray(canvas, float)
        soot = np.clip((smooth_noise(W, 12, rng) - 0.42) * 4, 0, 1)
        arr = arr * (1 - soot[..., None] * 0.85) * 0.62
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(canvas)
        for _ in range(30):
            x, y, r = rng.uniform(0, W), rng.uniform(0, W), rng.uniform(3, 9) * UP
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(18, 16, 14))
            draw.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(96, 52, 24))

    outside = Image.fromarray(255 - np.asarray(mask))
    canvas.paste((0, 0, 0), mask=outside)
    small = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    return small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def paint_mark(draw, canvas, mark, P, rng):
    kind, grp = mark["kind"], mark["group"]
    pts = [P(grp, p) for p in mark.get("pts", [])]
    if kind == "glass":
        draw.polygon(pts, fill=(22, 36, 58), outline=SEAM)
        # A sky reflection along one side and the frame.
        xs = [p[0] for p in pts]
        ys = [p[1] for p in pts]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        draw.line([(x0 + (x1 - x0) * 0.25, y0 + (y1 - y0) * 0.3), (x0 + (x1 - x0) * 0.7, y0 + (y1 - y0) * 0.22)],
                  fill=(150, 196, 226), width=2 * UP)
        draw.line([(x0 + (x1 - x0) * 0.3, y0 + (y1 - y0) * 0.45), (x0 + (x1 - x0) * 0.55, y0 + (y1 - y0) * 0.4)],
                  fill=(92, 140, 180), width=UP)
        for fx in mark.get("frames", ()):
            fxp = P(grp, fx)
            draw.line([(fxp[0], y0), (fxp[0], y1)], fill=(60, 66, 74), width=2 * UP)
    elif kind == "fill":
        draw.polygon(pts, fill=tuple(mark["colour"]), outline=tuple(mark.get("outline", SEAM)))
    elif kind == "line":
        draw.line(pts, fill=tuple(mark.get("colour", SEAM)), width=int(mark.get("width", 1) * UP))
        if mark.get("lit"):
            draw.line([(x, y + 1.5 * UP) for x, y in pts], fill=LIT, width=UP)
    elif kind == "nozzle":
        (cx, cy), = [P(grp, mark["at"])]
        rx = mark["r"] * _scale(P, grp, mark["at"])
        for k, col in ((1.0, (46, 44, 42)), (0.82, (88, 80, 70)), (0.62, (20, 18, 18))):
            draw.ellipse([cx - rx * k, cy - rx * k, cx + rx * k, cy + rx * k], fill=col)
        for a in range(0, 360, 30):
            ca, sa = math.cos(math.radians(a)), math.sin(math.radians(a))
            draw.line([(cx + ca * rx * 0.62, cy + sa * rx * 0.62), (cx + ca * rx * 0.98, cy + sa * rx * 0.98)],
                      fill=(30, 28, 26), width=UP)
    elif kind == "emblem":
        (x, y), = [P(grp, mark["at"])]
        s = mark["size"] * _scale(P, grp, mark["at"])
        draw.rectangle([x - s, y - s * 0.8, x + s, y + s * 0.8], fill=NAVY, outline=(214, 214, 210), width=UP)
        # A gold chevron pointing the way the jet flies (left on the top islands, up on the fin).
        if mark.get("point", "up") == "left":
            draw.polygon([(x + s * 0.45, y - s * 0.65), (x - s * 0.55, y), (x + s * 0.45, y + s * 0.65),
                          (x + s * 0.45, y + s * 0.38), (x - s * 0.15, y), (x + s * 0.45, y - s * 0.38)], fill=GOLD)
        else:
            draw.polygon([(x - s * 0.7, y + s * 0.45), (x, y - s * 0.5), (x + s * 0.7, y + s * 0.45),
                          (x + s * 0.42, y + s * 0.45), (x, y - s * 0.12), (x - s * 0.42, y + s * 0.45)], fill=GOLD)
    elif kind == "soot":
        np = _np()
        from PIL import Image, ImageDraw, ImageFilter
        layer = Image.new("L", canvas.size, 0)
        d = ImageDraw.Draw(layer)
        d.polygon(pts, fill=int(mark.get("strength", 150)))
        layer = layer.filter(ImageFilter.GaussianBlur(4 * UP))
        a = np.asarray(layer, float)[..., None] / 255.0
        arr = np.asarray(canvas, float) * (1 - a) + np.array((28, 26, 24), float) * a
        canvas.paste(Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8)))
    elif kind == "hazard":
        draw.polygon(pts, fill=HAZARD, outline=SEAM)
    elif kind == "panels":
        # Panel lines across a surface: lines between pairs of points.
        for a, b in mark["pairs"]:
            pa, pb = P(grp, a), P(grp, b)
            draw.line([pa, pb], fill=(52, 58, 66), width=UP)
            draw.line([(pa[0] + UP, pa[1] + UP), (pb[0] + UP, pb[1] + UP)], fill=(170, 178, 186), width=max(1, UP // 2))
    elif kind == "rivets":
        for p in pts:
            draw.ellipse([p[0] - UP * 0.6, p[1] - UP * 0.6, p[0] + UP * 0.6, p[1] + UP * 0.6], fill=(52, 58, 66))


def _scale(P, grp, at):
    """Pixels (on the large canvas) per model unit on an island, near a point."""
    a = P(grp, at)
    b = P(grp, (at[0] - 1.0, at[1], at[2])) if grp in ("top", "bottom", "side") else P(grp, (at[0], at[1] - 1.0, at[2]))
    return math.hypot(a[0] - b[0], a[1] - b[1])


def main():
    from PIL import Image
    data = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    texture = data["texture"]
    paint(data, occlusion=occlusion).save(os.path.join(out, texture + ".tga"))
    paint(data, damaged=True, occlusion=occlusion).save(os.path.join(out, texture + "_d.tga"))
    print("painted", texture)


if __name__ == "__main__":
    main()

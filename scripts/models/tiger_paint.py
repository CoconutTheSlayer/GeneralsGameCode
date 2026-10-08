"""The Tiger's textures, and the helicopters' shared texture layout and painter (the NH90 uses them too).

Like the Boxer (boxer_layout.py, boxer_paint.py), every face of a part is projected straight onto a panel
of the texture by the way it faces: a top view, one side view shared by both sides, the front, the back and
a small bottom view. tiger.py writes the faces as they lie on the texture (build/models/EUTIGR_layout.json)
and the baked ambient occlusion, then runs this with Python 3 and Pillow:

    python3 scripts/models/tiger_paint.py build/models/EUTIGR_layout.json OUT_DIR [OCCLUSION.png]

The layout part (Layout) needs neither Pillow nor Blender: tiger.py imports it inside Blender for the UVs.
"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

SIZE = 512


def group(normal):
    """Which panel a face belongs to, by the way it faces."""
    x, y, z = normal
    if abs(z) >= abs(x) and abs(z) >= abs(y):
        return "top" if z > 0 else "bottom"
    if abs(y) >= abs(x):
        return "side"
    return "front" if x > 0 else "back"


class Layout:
    """parts: {part: dict(x=(lo, hi), y=(lo, hi), z=(lo, hi), s=pixels per unit,
    top=(left, top), side=..., front=..., back=..., bottom=(left, top, pixels per unit))}.
    A part without a front/back/bottom panel draws those faces on its side/top panel."""

    def __init__(self, parts, size=SIZE):
        self.parts = parts
        self.size = size

    def pixel(self, part, grp, co):
        p = self.parts[part]
        (x0, x1), (y0, y1), (z0, z1), s = p["x"], p["y"], p["z"], p["s"]
        x = min(max(co[0], x0), x1)
        y = min(max(co[1], y0), y1)
        z = min(max(co[2], z0), z1)
        if grp == "bottom":
            if "bottom" in p:
                left, top, bs = p["bottom"]
                return left + (x - x0) * bs, top + (y - y0) * bs
            grp = "top"
        if grp in ("front", "back") and grp not in p:
            grp = "side"
        left, top = p[grp]
        if grp == "top":
            return left + (x - x0) * s, top + (y1 - y) * s
        if grp == "side":
            return left + (x - x0) * s, top + (z1 - z) * s
        if grp == "front":
            return left + (y - y0) * s, top + (z1 - z) * s
        return left + (y1 - y) * s, top + (z1 - z) * s

    def uv(self, part, grp, co):
        px, py = self.pixel(part, grp, co)
        return px / self.size, 1.0 - py / self.size


# The Tiger, in game units (+X forward, +Z up; about three units to the metre).
TIGER = Layout({
    "hull": dict(x=(-25.6, 19.8), y=(-8.0, 8.0), z=(0.0, 11.0), s=10.6,
                 side=(4, 4), top=(4, 124), front=(4, 296), back=(180, 296), bottom=(356, 296, 3.35)),
    # The rotor head and the tail rotor, each in its bone's own space.
    "rotor": dict(x=(-4.2, 4.2), y=(-4.2, 4.2), z=(-1.2, 2.6), s=9.0, top=(4, 420), side=(84, 420)),
    "tail": dict(x=(-4.0, 4.0), y=(-4.0, 4.0), z=(-0.8, 0.8), s=9.0, top=(164, 420), side=(244, 420)),
})


# --- painting --------------------------------------------------------------------------------------

def P(layout, part, grp, co):
    from boxer_paint import UP
    x, y = layout.pixel(part, grp, co)
    return x * UP, y * UP


def base_canvas(layout, faces, rng, light=None, palette=None):
    """Camouflage over every face, shaded by the way it faces; returns (image array, mask)."""
    import numpy as np
    from PIL import Image, ImageDraw
    from boxer_paint import W, UP, camouflage
    base = camouflage(rng) if palette is None else palette(rng)
    shade = Image.new("L", (W, W), 0)
    mask = Image.new("L", (W, W), 0)
    ds, dm = ImageDraw.Draw(shade), ImageDraw.Draw(mask)
    light = light or {"top": 255, "side": 236, "front": 228, "back": 214, "bottom": 130}
    for f in faces:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) < 3:
            continue
        ds.polygon(poly, fill=light[f["group"]])
        dm.polygon(poly, fill=255)
    img = base * (np.asarray(shade, float)[..., None] / 255.0)
    return img, mask


def seams_and_edges(draw, faces, rng, lit=(205, 212, 218), seam=(22, 25, 30)):
    """Dark seams along the model's sharp edges, lit on the face's side; small parts get fine lines."""
    from boxer_paint import UP
    for f in faces:
        poly = [(x * UP, y * UP) for x, y in f["px"]]
        if len(poly) < 3:
            continue
        cx = sum(p[0] for p in poly) / len(poly)
        cy = sum(p[1] for p in poly) / len(poly)
        fine = f["part"] != "hull" or f["group"] == "bottom"
        for i, sharp in enumerate(f["sharp"]):
            if not sharp:
                continue
            a, b = poly[i], poly[(i + 1) % len(poly)]
            draw.line([a, b], fill=seam, width=UP if fine else 2 * UP)
            if fine:
                continue
            mx, my = (a[0] + b[0]) / 2, (a[1] + b[1]) / 2
            dx, dy = cx - mx, cy - my
            d = math.hypot(dx, dy) or 1.0
            ox, oy = dx / d * 2.0 * UP, dy / d * 2.0 * UP
            draw.line([(a[0] + ox, a[1] + oy), (b[0] + ox, b[1] + oy)], fill=lit, width=UP)


def finish(canvas, mask, occlusion, damaged, rng, soot_rows=None, brighten=1.22):
    """Baked contact shadows, burns for the damaged model, black outside the faces, shrunk and sharpened."""
    import numpy as np
    from PIL import Image, ImageDraw, ImageFilter
    from boxer_paint import W, UP, smooth_noise
    if occlusion is not None:
        ao = np.asarray(occlusion.convert("L").resize((W, W), Image.BILINEAR), float) / 255.0
        arr = np.asarray(canvas, float) * (0.6 + 0.4 * ao)[..., None]
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
    if damaged:
        arr = np.asarray(canvas, float)
        soot = np.clip((smooth_noise(W, 12, rng) - 0.45) * 4, 0, 1)
        arr = arr * (1 - soot[..., None] * 0.85) * 0.62
        canvas = Image.fromarray(np.clip(arr, 0, 255).astype(np.uint8))
        draw = ImageDraw.Draw(canvas)
        for _ in range(30):
            x, y, r = rng.uniform(0, W), rng.uniform(0, (soot_rows or 410) * UP), rng.uniform(3, 9) * UP
            draw.ellipse([x - r, y - r, x + r, y + r], fill=(18, 16, 14))
            draw.ellipse([x - r * 0.45, y - r * 0.45, x + r * 0.45, y + r * 0.45], fill=(90, 50, 25))
    # The game's lighting darkens the textures: paint them brighter than they should look.
    canvas = Image.fromarray(np.clip(np.asarray(canvas, float) * brighten, 0, 255).astype(np.uint8))
    outside = Image.fromarray(255 - np.asarray(mask))
    canvas.paste((0, 0, 0), mask=outside)
    small = canvas.resize((SIZE, SIZE), Image.LANCZOS)
    return small.filter(ImageFilter.UnsharpMask(radius=1.2, percent=60, threshold=2))


def weathering(img, layout, rng, part="hull"):
    """Painted shading (sides darker low down), stains, grain and exhaust soot; returns the array."""
    import numpy as np
    from boxer_paint import W, UP, smooth_noise
    p = layout.parts[part]
    v = np.arange(W)[:, None] / UP
    top = p["side"][1]
    bottom = top + (p["z"][1] - p["z"][0]) * p["s"]
    rows = (v >= top) & (v < bottom)
    t = np.clip((v - top) / (bottom - top), 0, 1)
    img = img * np.where(rows, 1.1 - 0.32 * t, 1.0)[..., None]
    stains = smooth_noise(W, 30, rng) * 0.6 + smooth_noise(W, 70, rng) * 0.4
    img = img * (0.84 + 0.24 * stains)[..., None]
    img = img * (0.95 + 0.10 * rng.random((W, W)))[..., None]
    return img


def glass(draw, poly, frame=(30, 34, 40)):
    """A canopy pane: dark blue glass with a sky reflection."""
    from boxer_paint import UP
    draw.polygon(poly, fill=(46, 66, 86), outline=frame)
    xs = [p[0] for p in poly]
    ys = [p[1] for p in poly]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    # A soft streak of reflected sky across the upper part.
    draw.line([(x0 + (x1 - x0) * 0.2, y0 + (y1 - y0) * 0.35), (x0 + (x1 - x0) * 0.75, y0 + (y1 - y0) * 0.2)],
              fill=(150, 185, 210), width=2 * UP)
    draw.line(poly + [poly[0]], fill=frame, width=2 * UP)


def chevron(draw, centre, size, angle=0.0):
    """The faction's mark: a gold chevron on a dark blue square (rotated by angle, radians)."""
    from boxer_paint import UP
    x, y = centre
    s = size * UP
    c, sn = math.cos(angle), math.sin(angle)

    def r(px, py):
        return x + px * c - py * sn, y + px * sn + py * c
    draw.polygon([r(-s, -s * 0.8), r(s, -s * 0.8), r(s, s * 0.8), r(-s, s * 0.8)], fill=(28, 34, 62), outline=(200, 200, 200))
    draw.polygon([r(-s * 0.7, s * 0.42), r(0, -s * 0.5), r(s * 0.7, s * 0.42), r(s * 0.45, s * 0.42), r(0, -s * 0.12),
                  r(-s * 0.45, s * 0.42)], fill=(235, 200, 40))


def hazard(draw, a, b, width, stripes=6):
    """Yellow and black hazard stripes along a line from a to b (canvas pixels)."""
    ax, ay = a
    bx, by = b
    for i in range(stripes):
        t0, t1 = i / stripes, (i + 1) / stripes
        colour = (226, 186, 40) if i % 2 == 0 else (28, 28, 30)
        draw.line([(ax + (bx - ax) * t0, ay + (by - ay) * t0), (ax + (bx - ax) * t1, ay + (by - ay) * t1)],
                  fill=colour, width=int(width))


def paint_rotor_blur(path, blades=4, span=0.78, tip_colour=(226, 186, 40), seed=5):
    """The blurred rotor: u along the blade (hub to tip), v across a blade's sweep (1: the blade itself, then
    a fading trail). RGBA, alpha blended in the game."""
    import numpy as np
    from PIL import Image
    w, h = 256, 128
    u = np.linspace(0, 1, w)[None, :]
    v = np.linspace(1, 0, h)[:, None]   # image row 0 is v = 1 (Blender's v up; the game flips on load)
    core = np.clip((v - 0.86) / 0.05, 0, 1)
    trail = np.exp(-(0.86 - v) * 5.5) * (v < 0.86) * 0.5
    alpha = np.maximum(core * 0.92, trail)
    alpha = alpha * np.clip(u / 0.08, 0, 1) * np.clip((1.0 - u) / 0.025, 0, 1)
    rgb = np.empty((h, w, 3))
    rgb[:] = (52, 58, 66)
    tip = (u > 0.9) & (u < 0.975)
    rgb[np.broadcast_to(tip, (h, w))] = tip_colour
    rng = np.random.default_rng(seed)
    rgb *= (0.92 + 0.12 * rng.random((h, w)))[..., None]
    rgba = np.dstack([np.clip(rgb, 0, 255), np.clip(alpha * 255, 0, 255)]).astype(np.uint8)
    Image.fromarray(rgba, "RGBA").save(path)


# --- the Tiger --------------------------------------------------------------------------------------

def tiger_details(draw, rng, L):
    from boxer_paint import UP, SEAM, LIT, rivets, grille

    def side(x, z):
        return P(L, "hull", "side", (x, 5.0, z))

    def top(x, y):
        return P(L, "hull", "top", (x, y, 9.0))

    def front(y, z):
        return P(L, "hull", "front", (19.0, y, z))

    # Canopies: the gunner in front, the pilot behind and higher, framed.
    glass(draw, [side(17.6, 4.0), side(15.2, 5.6), side(10.6, 6.25), side(10.6, 4.4), side(16.4, 3.85)])
    glass(draw, [side(9.6, 6.4), side(8.6, 7.5), side(4.2, 7.95), side(3.8, 6.6), side(4.4, 5.7), side(9.6, 5.3)])
    for x in (13.3, 7.0):
        draw.line([side(x, 4.0), side(x, 7.8)], fill=(30, 34, 40), width=2 * UP)
    glass(draw, [top(17.6, 0.0), top(15.2, 1.15), top(10.5, 1.45), top(10.5, -1.45), top(15.2, -1.15)])
    glass(draw, [top(9.6, 1.5), top(4.0, 1.6), top(4.0, -1.6), top(9.6, -1.5)])
    draw.line([top(10.05, 1.6), top(10.05, -1.6)], fill=(30, 34, 40), width=3 * UP)
    a, b = front(-1.2, 5.8), front(1.2, 4.0)
    glass(draw, [a, (b[0], a[1]), b, (a[0], b[1])])

    # Panel lines and rivets along the fuselage.
    for x in (12.0, 2.5, -3.5, -9.0, -15.0):
        draw.line([side(x, 2.0 if x > -9 else 4.0), side(x, 4.4 if x > 3 else 6.6)], fill=SEAM, width=UP)
    draw.line([side(-9.0, 4.2), side(-24.0, 5.0)], fill=SEAM, width=UP)
    rivets(draw, [side(x, 2.6) for x in [16.0 - 1.5 * k for k in range(14)]], 0.4)
    rivets(draw, [side(x, 4.7 + (x + 9) * -0.05) for x in [-10.0 - 1.4 * k for k in range(10)]], 0.4)
    # Access doors, the engine intakes and exhaust grilles on the nacelles.
    for x0, x1, z0, z1 in ((1.0, -2.0, 4.6, 3.0), (-4.5, -7.5, 5.6, 3.4)):
        a, b = side(x0, z0), side(x1, z1)
        draw.rectangle([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], outline=SEAM, width=UP)
    a, b = side(-1.0, 8.1), side(-5.2, 7.0)
    grille(draw, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]), slats=7)
    a, b = side(1.4, 7.9), side(0.2, 6.6)
    draw.ellipse([min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1])], fill=(24, 26, 30), outline=SEAM)
    for y in (2.25, -2.25):
        a, b = top(-2.0, y + 0.6), top(-6.4, y - 0.6)
        grille(draw, min(a[0], b[0]), min(a[1], b[1]), max(a[0], b[0]), max(a[1], b[1]), slats=6)
    # Exhaust soot behind the engines, on the top and the sides.
    for y in (2.5, -2.5):
        for k in range(28):
            px, py = top(-8.5 - k * 0.28, y * (1 + k * 0.01) + rng.uniform(-0.25, 0.25))
            r = (0.9 + k * 0.05) * UP * 3
            draw.ellipse([px - r, py - r * 0.7, px + r, py + r * 0.7], fill=(40, 42, 46))
    for k in range(24):
        px, py = side(-8.6 - k * 0.3, 7.2 - k * 0.04 + rng.uniform(-0.2, 0.2))
        r = (0.8 + k * 0.05) * UP * 3
        draw.ellipse([px - r, py - r * 0.6, px + r, py + r * 0.6], fill=(42, 44, 48))
    # Walkway lines on the roof, a hazard band near the tail rotor and marks: the chevron on the boom sides
    # and on the roof behind the mast.
    hazard(draw, side(-21.2, 4.6), side(-21.2, 6.2), 2.2 * UP, 4)
    chevron(draw, side(-13.0, 5.3), 4.2)
    chevron(draw, top(-12.5, 0.0), 4.0, math.pi / 2)
    for y in (1.0, -1.0):
        draw.line([top(2.0, y), top(-6.0, y)], fill=(226, 186, 40), width=UP)
    # Wings: the walk-on strip and the pylons' hazard tips.
    for y in (7.2, -7.2):
        hazard(draw, top(1.8, y), top(-1.5, y), 2 * UP, 4)
    # Nose: the sensor window under the chin and a lit edge on the radome.
    a, b = front(-0.7, 3.2), front(0.7, 2.2)
    draw.rectangle([a[0], a[1], b[0], b[1]], fill=(60, 90, 70), outline=SEAM, width=UP)
    draw.line([side(18.8, 3.6), side(16.5, 4.6)], fill=LIT, width=UP)

    # The rotor head: dark steel with the blade cuffs in yellow at their tips.
    def rtop(x, y):
        return P(L, "rotor", "top", (x, y, 1.0))
    for a in range(4):
        ang = a * math.pi / 2 + math.radians(35)
        tx, ty = math.cos(ang) * 3.8, math.sin(ang) * 3.8
        p = rtop(tx, ty)
        draw.ellipse([p[0] - 3 * UP, p[1] - 3 * UP, p[0] + 3 * UP, p[1] + 3 * UP], fill=(226, 186, 40))
    # The tail rotor's blade tips.
    for a in range(3):
        ang = a * 2 * math.pi / 3
        p = P(L, "tail", "top", (math.cos(ang) * 3.5, math.sin(ang) * 3.5, 0.0))
        draw.ellipse([p[0] - 3 * UP, p[1] - 3 * UP, p[0] + 3 * UP, p[1] + 3 * UP], fill=(226, 186, 40))


def paint_body(layout, details, damaged=False, occlusion=None, seed=21):
    import numpy as np
    from PIL import Image, ImageDraw
    from boxer_paint import W, UP
    faces = layout_faces = layout["faces"]
    rng = np.random.default_rng(seed)
    img, mask = base_canvas(L_OF[layout["name"]], faces, rng)
    img = weathering(img, L_OF[layout["name"]], rng)
    # Rotor parts: darker steel instead of camouflage.
    canvas = Image.fromarray(np.clip(img, 0, 255).astype(np.uint8))
    draw = ImageDraw.Draw(canvas)
    for f in layout_faces:
        if f["part"] in ("rotor", "tail"):
            poly = [(x * UP, y * UP) for x, y in f["px"]]
            if len(poly) >= 3:
                shade = {"top": 1.0, "side": 0.85, "front": 0.8, "back": 0.75, "bottom": 0.6}[f["group"]]
                draw.polygon(poly, fill=tuple(int(c * shade) for c in (78, 84, 92)))
    # Rain streaks down the sides.
    side_top = L_OF[layout["name"]].parts["hull"]["side"][1]
    for _ in range(110):
        x = rng.uniform(0, W)
        y0 = side_top * UP + rng.uniform(0, 70 * UP)
        draw.line([(x, y0), (x + rng.uniform(-2, 2), y0 + rng.uniform(10, 40) * UP)], fill=(52, 56, 62),
                  width=int(rng.uniform(2, 4)))
    seams_and_edges(draw, faces, rng)
    details(draw, rng, L_OF[layout["name"]])
    return finish(canvas, mask, occlusion, damaged, rng)


L_OF = {"EUTIGR": TIGER}


def main():
    from PIL import Image
    layout = json.load(open(sys.argv[1]))
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    paint_body(layout, tiger_details, occlusion=occlusion).save(os.path.join(out, "eutig_body.tga"))
    paint_body(layout, tiger_details, damaged=True, occlusion=occlusion).save(os.path.join(out, "eutig_body_d.tga"))
    paint_rotor_blur(os.path.join(out, "eutig_rotor.tga"))
    print("painted")


if __name__ == "__main__":
    main()

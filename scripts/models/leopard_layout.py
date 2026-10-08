"""Where each side of a tank lies on its texture, the way boxer_layout.py does it for the Boxer, made general so
that the Leopard and the Leclerc share it: every part (hull, turret, gun, ...) has a box in its own space and a
scale, and each of its sides (top, side, front, back) is a straight projection of that box onto an island of the
texture. Both sides of the vehicle share the side view. Used by leopard.py / leclerc.py (UVs) and the painters;
no Blender needed.

A spec is a dict: {"size": 1024, "parts": {part: {"box": ((x0, x1), (y0, y1), (z0, z1)), "scale": px_per_unit,
"islands": {group: (left, top)}, "bottom": (left, top, scale)}}}. Pixels are y down.
"""


def clamp(v, lo, hi):
    return max(lo, min(hi, v))


def group(normal):
    """Which panel a face belongs to, by the way it faces."""
    x, y, z = normal
    if abs(z) >= abs(x) and abs(z) >= abs(y):
        return "top" if z > 0 else "bottom"
    if abs(y) >= abs(x):
        return "side"
    return "front" if x > 0 else "back"


class Layout:
    def __init__(self, spec):
        self.spec = spec
        self.size = spec["size"]

    def extent(self, part, grp):
        """(left, top, right, bottom) of an island, in pixels."""
        p = self.spec["parts"][part]
        (x0, x1), (y0, y1), (z0, z1) = p["box"]
        s = p["scale"]
        left, top = p["islands"][grp]
        w, h = {"top": (x1 - x0, y1 - y0), "side": (x1 - x0, z1 - z0), "front": (y1 - y0, z1 - z0),
                "back": (y1 - y0, z1 - z0)}[grp]
        return left, top, left + w * s, top + h * s

    def pixel(self, part, grp, co):
        """Where a point of the part lies on the texture."""
        p = self.spec["parts"][part]
        (x0, x1), (y0, y1), (z0, z1) = p["box"]
        s = p["scale"]
        x, y, z = clamp(co[0], x0, x1), clamp(co[1], y0, y1), clamp(co[2], z0, z1)
        if grp == "bottom":
            left, top, bs = p["bottom"]
            return left + (x - x0) * bs, top + (y - y0) * bs
        left, top = p["islands"][grp]
        if grp == "top":
            return left + (x - x0) * s, top + (y1 - y) * s
        if grp == "side":
            return left + (x - x0) * s, top + (z1 - z) * s
        if grp == "front":
            return left + (y - y0) * s, top + (z1 - z) * s
        # back: seen from behind, so the vehicle's left (+y) is on the left
        return left + (y1 - y) * s, top + (z1 - z) * s

    def uv(self, part, grp, co):
        """The same as a Blender UV (v up)."""
        px, py = self.pixel(part, grp, co)
        return px / self.size, 1.0 - py / self.size

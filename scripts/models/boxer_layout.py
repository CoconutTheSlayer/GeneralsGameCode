"""Where each side of the Boxer lies on its texture, like the game's own vehicle textures: the roof as
one panel, one side view shared by both sides, the front and the back, each a straight projection of the
model, so that details can be painted at their place on the vehicle. Used by boxer.py (UVs) and
boxer_paint.py (painting); no Blender needed.

Pixels are on a SIZE x SIZE texture, y down. Coordinates are the model's (hull) or the turret's own.
"""
SIZE = 512

# Hull: 16 pixels per unit.
HULL_X, HULL_Y, HULL_Z = (-15.6, 15.8), (-5.9, 5.9), (2.2, 9.2)
S = 16.0
# Turret: 10 pixels per unit.
TUR_X, TUR_Y, TUR_Z = (-1.6, 5.5), (-1.8, 1.8), (0.0, 1.9)
T = 10.0

ISLANDS = {
    # (part, group): (left, top) of the island
    ("hull", "top"): (5, 5),
    ("hull", "side"): (5, 200),
    ("hull", "front"): (5, 318),
    ("hull", "back"): (200, 318),
    ("turret", "top"): (5, 440),
    ("turret", "side"): (85, 440),
    ("turret", "front"): (165, 440),
    ("turret", "back"): (210, 440),
}


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


def pixel(part, grp, co):
    """Where a point of the model lies on the texture."""
    x, y, z = co
    if part == "hull":
        (x0, x1), (y0, y1), (z0, z1), s = HULL_X, HULL_Y, HULL_Z, S
    else:
        (x0, x1), (y0, y1), (z0, z1), s = TUR_X, TUR_Y, TUR_Z, T
    x, y, z = clamp(x, x0, x1), clamp(y, y0, y1), clamp(z, z0, z1)
    if grp == "bottom":
        # Hardly ever seen: squeezed into a corner.
        if part == "hull":
            return 400 + (x - x0) * 3.4, 318 + (y - y0) * 9.0
        return 255 + (x - x0) * 4.0, 440 + (y - y0) * 4.0
    left, top = ISLANDS[(part, grp)]
    if grp == "top":
        return left + (x - x0) * s, top + (y1 - y) * s
    if grp == "side":
        return left + (x - x0) * s, top + (z1 - z) * s
    # front and back: across the width
    return left + (y - y0) * s, top + (z1 - z) * s


def uv(part, grp, co):
    """The same as a Blender UV (v up)."""
    px, py = pixel(part, grp, co)
    return px / SIZE, 1.0 - py / SIZE

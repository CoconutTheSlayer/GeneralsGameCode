"""Paints the European Field Ambulance's textures (ambulance.py runs it), with the support vehicles' painter in
engineer_paint.py: the blue-grey camouflage, white panels with red crosses on the medical module, windows,
lights, and the tyres.

    python3 scripts/models/ambulance_paint.py build/models/EUAMB_layout.json OUT_DIR [OCCLUSION.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engineer_paint import (SEAM, UP, Image, emblem, grille, hazard, light, load_faces, paint_body,  # noqa: E402
                            paint_tire_texture, rivets, seam, vision_block)

WHITE, RED = (232, 232, 226), (196, 28, 30)


def red_cross(draw, box):
    """A red cross on a white square, edged dark."""
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=WHITE, outline=SEAM, width=UP)
    w, h = x1 - x0, y1 - y0
    t = min(w, h) * 0.22
    cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
    arm = min(w, h) * 0.38
    draw.rectangle([cx - t / 2, cy - arm, cx + t / 2, cy + arm], fill=RED)
    draw.rectangle([cx - arm, cy - t / 2, cx + arm, cy + t / 2], fill=RED)


def window(draw, box):
    x0, y0, x1, y1 = box
    draw.rectangle(box, fill=(34, 58, 80), outline=SEAM, width=2 * UP)
    draw.polygon([(x0 + 2 * UP, y1 - 2 * UP), (x0 + (x1 - x0) * 0.35, y0 + 2 * UP), (x0 + (x1 - x0) * 0.5, y0 + 2 * UP),
                  (x0 + (x1 - x0) * 0.15, y1 - 2 * UP)], fill=(96, 138, 166))


def details(draw, p, rng):
    P, R = p.P, p.rect
    # The module's sides: a red cross on white, a door outline, the stretcher locker.
    red_cross(draw, R("body", "side", (-6.4, 0, 9.6), (-1.4, 0, 5.0)))
    draw.rectangle(R("body", "side", (-10.4, 0, 9.6), (-7.2, 0, 4.9)), outline=SEAM, width=2 * UP)
    rivets(draw, [P("body", "side", (x, 0, 11.0)) for x in range(-11, 2)], 0.45)
    hazard(draw, R("body", "side", (-10.6, 0, 6.6), (-6.4, 0, 6.2)))
    # The cab: side windows over the doors, the door seams, a chevron on the door.
    window(draw, R("body", "side", (2.2, 0, 9.6), (4.8, 0, 7.6)))
    window(draw, R("body", "side", (5.2, 0, 9.6), (8.0, 0, 7.6)))
    for x in (1.9, 5.0, 8.6):
        seam(draw, P("body", "side", (x, 0, 9.9)), P("body", "side", (x, 0, 4.8)), lit=False)
    emblem(draw, P("body", "side", (6.6, 0, 6.2)), 0.9 * p.layout.s("body"))
    # Bonnet: the engine grille, louvres on the bonnet top.
    grille(draw, R("body", "top", (13.0, 3.2, 0), (10.2, 1.2, 0)), slats=6)
    grille(draw, R("body", "top", (13.0, -1.2, 0), (10.2, -3.2, 0)), slats=6)
    # The windscreen, two armoured panes; headlights; the grille.
    for y0, y1 in ((-4.0, -0.25), (0.25, 4.0)):
        window(draw, R("body", "front", (0, y0, 9.8), (0, y1, 7.7)))
    for y in (3.4, -3.4):
        light(draw, R("body", "front", (0, y - 0.6, 6.7), (0, y + 0.6, 6.0)))
    grille(draw, R("body", "front", (0, -2.4, 5.6), (0, 2.4, 4.6)), slats=4, vertical=False)
    # The roof: a big red cross on the cab for the air, walkway seams on the module.
    red_cross(draw, R("body", "top", (2.0, 2.2, 0), (6.4, -2.2, 0)))
    for x in (-5.4, -3.0):
        seam(draw, P("body", "top", (x, 4.8, 0)), P("body", "top", (x, -4.8, 0)))
    grille(draw, R("body", "top", (-9.6, 2.4, 0), (-6.2, -2.4, 0)), slats=7)
    # The back: doors with a red cross each side of the gap, tail lights, the step.
    red_cross(draw, R("body", "back", (0, -3.2, 9.4), (0, -0.2, 6.4)))
    red_cross(draw, R("body", "back", (0, 0.2, 9.4), (0, 3.2, 6.4)))
    seam(draw, P("body", "back", (0, 0.0, 10.4)), P("body", "back", (0, 0.0, 4.8)), lit=False)
    for y in (4.4, -4.4):
        light(draw, R("body", "back", (0, y - 0.5, 7.6), (0, y + 0.5, 6.8)), (170, 30, 25))
        light(draw, R("body", "back", (0, y - 0.5, 6.6), (0, y + 0.5, 6.1)), (220, 140, 30))
    hazard(draw, R("body", "back", (0, -3.0, 4.1), (0, 3.0, 3.6)))
    # The spray turret: its camera's lens.
    vision_block(draw, R("turret", "front", (0, 0.8, 0.4), (0, 1.25, -0.2)))


def main():
    layout, faces = load_faces(sys.argv[1])
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    spots = [("body", x, 2.8, 2.8) for x in (10.4, -7.1)]
    kw = dict(details=details, occlusion=occlusion, mud_below=4.6, mud_spots=spots, seed=21)
    paint_body(layout, faces, **kw).save(os.path.join(out, "euamb.tga"))
    paint_body(layout, faces, damaged=True, **kw).save(os.path.join(out, "euamb_d.tga"))
    paint_tire_texture().save(os.path.join(out, "euamb_tire.tga"))
    print("painted")


if __name__ == "__main__":
    main()

"""Paints the European Recon Drone's textures (recon_drone.py runs it), with the support vehicles' painter in
engineer_paint.py: blue-grey camouflage, sensor lenses, lights, hazard marks and the track links.

    python3 scripts/models/recon_drone_paint.py build/models/EUDRONE_layout.json OUT_DIR [OCCLUSION.png]
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from engineer_paint import (SEAM, UP, Image, emblem, grille, hazard, light, load_faces, paint_body,  # noqa: E402
                            paint_tread, rivets, seam, vision_block)


def lens(draw, centre, r, colour=(40, 80, 120)):
    x, y = centre
    draw.ellipse([x - r, y - r, x + r, y + r], fill=(20, 22, 26), outline=SEAM, width=UP)
    draw.ellipse([x - r * 0.7, y - r * 0.7, x + r * 0.7, y + r * 0.7], fill=colour)
    draw.ellipse([x - r * 0.5, y - r * 0.55, x - r * 0.1, y - r * 0.15], fill=(170, 210, 235))


def details(draw, p, rng):
    P, R = p.P, p.rect
    s = p.layout.s
    # Deck: hatches over the battery and electronics, the chevron, tie-down rivets.
    grille(draw, R("hull", "top", (-3.2, 2.4, 0), (0.0, 0.6, 0)), slats=5)
    grille(draw, R("hull", "top", (-3.2, -0.6, 0), (0.0, -2.4, 0)), slats=5)
    emblem(draw, P("hull", "top", (-5.3, 0.0, 0)), 1.1 * s("hull"))
    rivets(draw, [P("hull", "top", (x, y, 0)) for x in (-7.0, 7.0) for y in (-2.6, 2.6)], 0.5)
    for y in (4.35, -4.35):
        seam(draw, P("hull", "top", (-6.2, y, 0)), P("hull", "top", (6.4, y, 0)), lit=False)
    # Side plates: bolts, a hazard band at the front, a chevron.
    rivets(draw, [P("hull", "side", (x, 0, 2.45)) for x in range(-5, 6)], 0.45)
    rivets(draw, [P("hull", "side", (x, 0, 0.95)) for x in range(-5, 6)], 0.45)
    hazard(draw, R("hull", "side", (4.2, 0, 2.5), (5.6, 0, 2.1)))
    emblem(draw, P("hull", "side", (3.0, 0, 1.75)), 0.55 * s("hull"))
    # Front: driving cameras and lights at the corners, the bumper's hazard stripe.
    for y in (2.2, -2.2):
        lens(draw, P("hull", "front", (0, y, 3.0)), 0.3 * s("hull") * UP)
    for y in (4.4, -4.4):
        light(draw, R("hull", "front", (0, y - 0.5, 2.4), (0, y + 0.5, 1.9)))
    hazard(draw, R("hull", "front", (0, -2.8, 2.5), (0, 2.8, 2.0)))
    for y in (4.4, -4.4):
        light(draw, R("hull", "back", (0, y - 0.4, 2.3), (0, y + 0.4, 1.9)), (170, 30, 25))
    # The mast's head: two lenses, the radar panel's elements.
    lens(draw, P("mast", "front", (0, -0.45, MAST_TOP + 0.35)), 0.3 * s("mast") * UP)
    lens(draw, P("mast", "front", (0, 0.45, MAST_TOP + 0.35)), 0.22 * s("mast") * UP, (90, 40, 30))
    x0, y0, x1, y1 = R("mast", "back", (0, -1.45, MAST_TOP + 1.25), (0, 1.45, MAST_TOP - 0.05))
    draw.rectangle([x0, y0, x1, y1], fill=(70, 78, 86), outline=SEAM, width=UP)
    for i in range(6):
        for j in range(4):
            cx, cy = x0 + (i + 0.5) * (x1 - x0) / 6, y0 + (j + 0.5) * (y1 - y0) / 4
            draw.rectangle([cx - UP * 2, cy - UP * 2, cx + UP * 2, cy + UP * 2], fill=(150, 160, 168))
    for z in (DECK_Z + 6.4, DECK_Z + 2.0):
        hazard(draw, R("mast", "side", (-5.4, 0, z + 0.3), (-4.6, 0, z)))
    # The weapon station's sight, the gun's receiver.
    vision_block(draw, R("turret", "front", (0, 1.05, 1.9), (0, 1.5, 1.1)))
    vision_block(draw, R("turret", "side", (0.2, 0, 1.8), (1.2, 0, 1.2)))


MAST_TOP, DECK_Z = 13.0, 3.4  # recon_drone.py's


def main():
    layout, faces = load_faces(sys.argv[1])
    out = sys.argv[2]
    occlusion = Image.open(sys.argv[3]) if len(sys.argv) > 3 and os.path.exists(sys.argv[3]) else None
    kw = dict(details=details, occlusion=occlusion, mud_below=2.4, seed=33, camo_scale=0.8)
    paint_body(layout, faces, **kw).save(os.path.join(out, "eudrn.tga"))
    paint_body(layout, faces, damaged=True, **kw).save(os.path.join(out, "eudrn_d.tga"))
    paint_tread(size=(256, 128), links=4, seed=9).save(os.path.join(out, "eudrn_tread.tga"))
    print("painted")


if __name__ == "__main__":
    main()

"""The European Wiesel EW, a small, low tracked carrier with an electronic warfare superstructure and a tall
telescopic mast carrying jammer antennas and an emitter dish. Modelled in Blender from simple shapes and
written as a W3D model for the game, with the PULS's helpers (puls.py) for its tracks, UVs and paint.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/wiesel.py

Writes resources/macos/GameData/Art/W3D/EUWIES.w3d and EUWIES_D.w3d, Art/TexturesHD/euwie.tga,
euwie_d.tga and euwie_tread.tga, and build/models/EUWIES.blend with previews next to it.

Bones the Microwave tank's modules use (the whole vehicle turns to aim, it has no turret):
    WEAPON02            where the disabling beam leaves: the emitter dish at the mast's top
    PROJECTORGLOW09     the dish's glow
    TREADSL / TREADSR   meshes whose texture W3DTankDraw scrolls
    HOUSECOLOR01/02     panels in the player's colour
    SMOKE01, SMOKE      smoke when badly damaged
"""
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import boxer  # noqa: E402
import puls  # noqa: E402
from blender_kit import box, cylinder, load_image, mesh_data, new_object, prism, textured  # noqa: E402
from puls import BUILD, DATA, TEX_DIR, TREAD_MAPPER, flat_panel, track_body, tread_band  # noqa: E402
from puls_paint import Layout  # noqa: E402
import w3d  # noqa: E402

NAME = "EUWIES"
TEXTURE, DAMAGED_TEXTURE, TREAD_TEXTURE = "euwie.tga", "euwie_d.tga", "euwie_tread.tga"

TRACK_Y = (3.4, 6.2)
TRACK_PROFILE = [(-8.6, 0.15), (7.6, 0.15), (10.2, 2.3), (9.5, 3.3), (-9.3, 3.3), (-10.0, 1.9)]
TRACK_BODY = [(-8.4, 0.55), (7.4, 0.55), (9.8, 2.3), (9.2, 3.05), (-9.0, 3.05), (-9.6, 1.9)]
WHEELS = [(x, 1.45, 1.25) for x in (-6.6, -3.0, 0.6, 4.2)] + [(8.9, 2.3, 1.0), (-8.9, 2.0, 0.95)]
MAST_X = -5.2
HEAD_Z = 16.25
DISH_X = -4.4
EMITTER = (-3.0, 0.0, HEAD_Z)       # WEAPON02
# The real Wiesel is tiny; the game's vehicle is drawn this much larger than the shapes below, closer to the
# size of the Microwave tank it stands in for (its selection box and the beam's reach).
K = 1.2
GLOW = (-3.3, 0.0, HEAD_Z)          # PROJECTORGLOW09

LAYOUT = Layout([
    ("hull", (-10.7, 10.7, -6.4, 6.4, 0.9, 5.7), 28.0),
    ("ew", (-9.7, -0.1, -4.7, 4.7, 5.5, 8.5), 30.0),
    ("track", (-10.1, 10.3, 3.3, 6.3, 0.1, 3.4), 22.0),
    ("mast", (-7.0, -2.9, -2.4, 2.4, 7.5, 17.8), 26.0),
], size=1024)


def hull():
    bm = bmesh.new()
    prism(bm, [(-9.8, 1.0), (7.8, 1.0), (10.0, 3.4), (-9.8, 3.4)], 3.4)
    upper = bmesh.new()
    prism(upper, [(-10.0, 3.3), (9.6, 3.3), (10.4, 3.8), (6.0, 5.6), (-10.0, 5.6)], 4.7)  # the tracks run open beside it
    sharp = [e for e in upper.edges if e.is_manifold and e.calc_face_angle(0) > 0.44]
    bmesh.ops.bevel(upper, geom=sharp, offset=0.2, segments=1, affect="EDGES", profile=0.5)
    me = bpy.data.meshes.new("tmp")
    upper.to_mesh(me)
    upper.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)
    cylinder(bm, (4.4, 2.6, 5.65), 0.9, 0.2, segments=14)             # driver's hatch
    box(bm, (5.0, 1.8, 5.5), (5.5, 3.4, 5.95))                        # his vision blocks
    box(bm, (6.6, -4.2, 4.9), (8.6, -1.4, 5.15))                      # engine grille on the glacis
    for side in (1, -1):
        box(bm, (9.8, side * 3.4, 3.8), (10.5, side * 4.4, 4.2))      # headlights
        box(bm, (-10.4, side * 2.8, 3.4), (-10.0, side * 4.4, 4.6))   # rear stowage
        box(bm, (8.6, side * 4.7, 3.35), (10.6, side * 6.3, 3.6))     # front mudguards
    cylinder(bm, (8.2, -3.9, 5.7), 0.25, 1.4, segments=8)             # exhaust
    return new_object("CHASSIS", bm)


def ew_box():
    bm = bmesh.new()
    prism(bm, [(-9.6, 5.6), (-1.0, 5.6), (-0.2, 6.4), (-1.2, 7.6), (-9.6, 7.6)], 4.6)
    box(bm, (-6.6, -1.4, 7.6), (-3.8, 1.4, 8.4))                      # mast base
    for side in (1, -1):
        box(bm, (-8.4, side * 4.6, 6.0), (-3.0, side * 4.8, 7.2))     # side equipment doors
        cylinder(bm, (-9.2, side * 4.0, 9.9), 0.08, 4.6, segments=6)  # whip antennas
        cylinder(bm, (-9.2, side * 4.0, 7.75), 0.25, 0.3, segments=8)
    box(bm, (-2.8, -3.6, 7.6), (-1.6, -2.4, 8.2))                     # GPS dome base
    cylinder(bm, (-2.2, -3.0, 8.4), 0.5, 0.4, segments=10)
    return new_object("EW", bm)


def mast():
    from mathutils import Matrix
    bm = bmesh.new()
    for z0, z1, r in ((8.4, 11.8, 0.55), (11.8, 14.4, 0.42), (14.4, HEAD_Z - 0.2, 0.3)):
        cylinder(bm, (MAST_X, 0, (z0 + z1) / 2), r, z1 - z0, segments=10)
        cylinder(bm, (MAST_X, 0, z1 - 0.1), r + 0.12, 0.2, segments=10)   # collars
    box(bm, (MAST_X - 0.6, -2.2, HEAD_Z - 0.3), (MAST_X + 0.6, 2.2, HEAD_Z + 0.25))  # cross arm
    for side in (1, -1):
        box(bm, (MAST_X - 0.5, side * 1.95, HEAD_Z - 1.2), (MAST_X + 0.5, side * 2.25, HEAD_Z + 1.4))  # jammer panels
    box(bm, (MAST_X - 0.4, -0.4, HEAD_Z + 0.25), (MAST_X + 0.4, 0.4, HEAD_Z + 1.0))   # receiver head
    cylinder(bm, (MAST_X, 0, HEAD_Z + 1.9), 0.06, 1.8, segments=6)                     # top whip
    # The emitter dish, facing forward, with its feed.
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.35, radius2=1.4, depth=0.55,
                          matrix=Matrix.Translation((DISH_X + 0.3, 0, HEAD_Z)) @ Matrix.Rotation(1.5708, 4, "Y"))
    cylinder(bm, ((DISH_X + EMITTER[0]) / 2 + 0.2, 0, HEAD_Z), 0.07, abs(EMITTER[0] - DISH_X) - 0.2, axis="X", segments=6)
    box(bm, (EMITTER[0] - 0.35, -0.2, HEAD_Z - 0.2), (EMITTER[0] + 0.05, 0.2, HEAD_Z + 0.2))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    return new_object("MAST", bm)


def tracks():
    bm = bmesh.new()
    for side in (1, -1):
        track_body(bm, side, TRACK_BODY, WHEELS, TRACK_Y)
    return new_object("TRACKS", bm)


def build():
    parts = dict(chassis=hull(), ew=ew_box(), tracks=tracks(), mast=mast())
    parts["treads"] = [tread_band("TREADSL", 1, TRACK_PROFILE, TRACK_Y), tread_band("TREADSR", -1, TRACK_PROFILE, TRACK_Y)]
    stripes = [
        flat_panel("HOUSECOLOR01", [(-8.2, 4.82, 6.15), (-3.2, 4.82, 6.15), (-3.2, 4.82, 7.05), (-8.2, 4.82, 7.05)][::-1]),
        flat_panel("HOUSECOLOR02", [(-8.2, -4.82, 6.15), (-3.2, -4.82, 6.15), (-3.2, -4.82, 7.05), (-8.2, -4.82, 7.05)]),
    ]
    parts["stripes"] = stripes
    painted = [(parts["chassis"], "hull"), (parts["ew"], "ew"), (parts["tracks"], "track"), (parts["mast"], "mast")]
    puls.finish(NAME, painted, "wiesel_paint.py", stripes=stripes, layout=LAYOUT)
    from mathutils import Matrix
    for obj in [o for o, _ in painted] + parts["treads"] + stripes:
        obj.data.transform(Matrix.Scale(K, 4))
    image = load_image(os.path.join(TEX_DIR, TEXTURE))
    for obj, _ in painted:
        textured(obj, image)
    tread = load_image(os.path.join(TEX_DIR, TREAD_TEXTURE))
    for obj in parts["treads"]:
        textured(obj, tread)
    colour = puls.house_material()
    for obj in stripes:
        obj.data.materials.append(colour)
    return parts


def export(parts, name, texture):
    model = w3d.Model(name)
    model.bone("WEAPON02", w3d.CHASSIS, [v * K for v in EMITTER])
    model.bone("PROJECTORGLOW09", w3d.CHASSIS, [v * K for v in GLOW])
    model.bone("SMOKE01", w3d.CHASSIS, (-7.2, 2.4, 9.4))
    model.bone("SMOKE", w3d.CHASSIS, (9.1, -3.6, 6.5))
    for key, mesh in (("chassis", "CHASSIS"), ("ew", "EW"), ("tracks", "TRACKS"), ("mast", "MAST")):
        model.mesh(mesh, w3d.CHASSIS, **mesh_data(parts[key]), texture=texture)
    for obj in parts["treads"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=TREAD_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER, mapper_args=TREAD_MAPPER)
    for obj in parts["stripes"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER)
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = build()
    export(parts, NAME, TEXTURE)
    export(parts, NAME + "_D", DAMAGED_TEXTURE)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    boxer.render_previews(os.path.join(BUILD, NAME))


if __name__ == "__main__":
    main()

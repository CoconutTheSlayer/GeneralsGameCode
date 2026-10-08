"""The European Skyranger 30, air defence on the Boxer: the Boxer's eight-wheeled hull (boxer.py) under a
compact turret with a 30 mm revolver cannon, a missile pod beside it and a search radar panel at its back.
In the game the turret is an object of its own riding on the hull (like the Avenger's), so there are two
models:

    EUSKYR, EUSKYR_D      the hull, its wheels, the target designator and the point defence emitters
    EUSKYR_G, EUSKYR_GD   the turret, turning on TURRET01 and pitching the gun and pod on TURRETEL01

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/skyranger.py

Textures (made by skyranger_paint.py): eusky_hull.tga / eusky_hull_d.tga (the Boxer's paint, without its
plates), eusky.tga / eusky_d.tga (turret and fittings); the tyres use the Boxer's euboxer_tire.tga.

Bones the Avenger's modules use:
    hull:   TIRE01..08, FIREPOINT01 (where the turret rides), TURRETFX03 (target designator laser),
            LAZERSPOT01/02 (point defence lasers), TURRET01 (a copy of the turret, shown only when a
            GLA bomb truck disguises itself as a Skyranger), SMOKE01
    turret: TURRET01, TURRETEL01 (gun pitch), TURRETFX01 (gun muzzle), TURRETFX02 (missile pod), TURRETEL
"""
import math
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import boxer  # noqa: E402
import puls  # noqa: E402
from blender_kit import box, cylinder, load_image, mesh_data, new_object, prism, textured  # noqa: E402
from puls import BUILD, DATA, TEX_DIR, flat_panel, tilted_box  # noqa: E402
from puls_paint import Layout  # noqa: E402
import w3d  # noqa: E402

NAME = "EUSKYR"
HULL_TEXTURE, HULL_DAMAGED = "eusky_hull.tga", "eusky_hull_d.tga"
TEXTURE, DAMAGED_TEXTURE = "eusky.tga", "eusky_d.tga"
FIREPOINT = boxer.TURRET_AT                 # (-3.5, 0, 9.0) on the Boxer's roof
S = 1.3                                     # the turret is drawn at this scale: big enough to read at game zoom
GUN_AT = (1.6 * S, 0.0, 1.6 * S)            # TURRETEL01 in the turret's space
MUZZLE = (7.55 * S, -0.9 * S, 0.0)          # TURRETFX01 in the gun's space
POD_FRONT = (2.3 * S, 3.6 * S, 0.0)         # TURRETFX02
DESIGNATOR = (6.8, -2.5, 9.25)              # TURRETFX03, on the hull
LASERS = [(-13.0, 3.8, 9.75), (-13.0, -3.8, 9.75)]  # LAZERSPOT01/02

LAYOUT = Layout([
    ("turret", (-4.0 * S, 4.0 * S, -2.9 * S, 2.9 * S, 0.0, 5.8 * S), 19.0),
    ("gun", (-1.1 * S, 7.6 * S, -1.8 * S, 4.4 * S, -0.9 * S, 0.9 * S), 16.0),
    ("designator", (5.4, 7.0, -3.2, -1.8, 7.7, 9.8), 24.0),
    ("pd", (-13.6, -12.4, -4.4, 4.4, 8.9, 9.9), 20.0),
], size=512)


def turret():
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.2), 2.6, 0.4, segments=20)               # turret ring
    prism(bm, [(-3.8, 0.3), (3.0, 0.3), (3.9, 1.3), (3.1, 2.7), (-3.8, 2.7)], 2.7, taper_from=1.5, taper=0.9)
    for side in (1, -1):
        box(bm, (1.0, side * 2.55, 0.5), (2.8, side * 2.8, 1.45))      # radar panels on the cheeks
        box(bm, (-3.6, side * 1.4, 2.7), (-2.0, side * 2.2, 3.0))      # smoke dischargers' base
        for k in range(3):
            cylinder(bm, (-3.3 + k * 0.55, side * 1.8, 3.15), 0.2, 0.5, axis="X", segments=8)
    box(bm, (-3.4, -0.35, 2.7), (-2.6, 0.35, 3.3))                     # radar post
    tilted_box(bm, (-3.25, -2.0, 3.1), (-2.95, 2.0, 5.6), 18, (-3.1, 0, 3.1))  # search radar, leaning back
    box(bm, (1.3, 0.9, 2.6), (2.3, 1.9, 3.4))                          # sight
    cylinder(bm, (2.4, 1.4, 3.0), 0.3, 0.2, axis="X", segments=10)     # its lens
    bmesh.ops.scale(bm, vec=(S, S, S), verts=bm.verts)
    return new_object("TURRET01", bm, FIREPOINT)


def gun():
    bm = bmesh.new()
    box(bm, (-0.8, -1.6, -0.8), (0.9, -0.2, 0.8))                      # mantlet
    cylinder(bm, (0.0, 1.0, 0.0), 0.35, 5.4, axis="Y", segments=10)   # trunnion shaft out to the pod
    cylinder(bm, (1.5, -0.9, 0.0), 0.45, 1.4, axis="X", segments=12)  # revolver cannon
    cylinder(bm, (4.6, -0.9, 0.0), 0.22, 4.8, axis="X", segments=8)   # barrel
    cylinder(bm, (7.15, -0.9, 0.0), 0.34, 0.8, axis="X", segments=10) # muzzle device
    box(bm, (-1.0, 2.85, -0.75), (2.2, 4.35, 0.75))                    # missile pod, two by two
    box(bm, (-0.6, 2.4, -0.3), (0.6, 2.85, 0.3))                       # its mount
    bmesh.ops.scale(bm, vec=(S, S, S), verts=bm.verts)
    obj = new_object("GUN", bm, [FIREPOINT[i] + GUN_AT[i] for i in range(3)])
    return obj


def designator():
    bm = bmesh.new()
    cylinder(bm, (6.1, -2.5, 8.3), 0.25, 1.1, segments=10)
    box(bm, (5.6, -3.0, 8.8), (6.7, -2.0, 9.6))
    return new_object("DESIGNATOR", bm)


def point_defence():
    bm = bmesh.new()
    for x, y, z in LASERS:
        cylinder(bm, (x, y, 9.2), 0.45, 0.4, segments=12)
        cylinder(bm, (x, y, 9.55), 0.28, 0.3, segments=10)
    return new_object("POINTDEFENCE", bm)


def build():
    os.makedirs(BUILD, exist_ok=True)
    chassis = boxer.hull()
    boxer.smooth_by_angle(chassis)
    boxer.panel_unwrap(chassis, "hull")
    wheels = []
    for i, x in enumerate(boxer.WHEEL_X):
        for j, side in enumerate((1, -1)):
            wheels.append(boxer.wheel(f"TIRE0{i * 2 + j + 1}", (x, side * boxer.WHEEL_Y, boxer.WHEEL_Z)))
    for obj in wheels:
        boxer.smooth_by_angle(obj, 50)
        boxer.wheel_uvs(obj)
    stripes = [boxer.house_colour(1), boxer.house_colour(-1)]
    for obj in stripes:
        obj.data.uv_layers.new(name="UVMap")
    top, cannon, kit, pd = turret(), gun(), designator(), point_defence()
    turret_stripes = [
        flat_panel("HOUSECOLOR03", [(x * S, y * S, z * S) for x, y, z in
                                    [(-3.5, 2.72, 0.5), (-0.6, 2.72, 0.5), (-0.6, 2.72, 1.3), (-3.5, 2.72, 1.3)][::-1]], FIREPOINT),
        flat_panel("HOUSECOLOR04", [(x * S, y * S, z * S) for x, y, z in
                                    [(-3.5, -2.72, 0.5), (-0.6, -2.72, 0.5), (-0.6, -2.72, 1.3), (-3.5, -2.72, 1.3)]], FIREPOINT),
    ]
    # The hull's layout and occlusion for the Boxer's painter; the turret's for ours.
    boxer.export_layout(((chassis, "hull"),), os.path.join(BUILD, NAME + "_hull_layout.json"))
    boxer.bake_occlusion([chassis], os.path.join(BUILD, NAME + "_hull_ao.png"))
    puls.finish(NAME, [(top, "turret"), (cannon, "gun"), (kit, "designator"), (pd, "pd")], "skyranger_paint.py",
                stripes=turret_stripes, layout=LAYOUT)
    hull_image = load_image(os.path.join(TEX_DIR, HULL_TEXTURE))
    textured(chassis, hull_image)
    tire = load_image(os.path.join(TEX_DIR, boxer.TIRE_TEXTURE))
    for obj in wheels:
        textured(obj, tire)
    image = load_image(os.path.join(TEX_DIR, TEXTURE))
    for obj in (top, cannon, kit, pd):
        textured(obj, image)
    colour = puls.house_material()
    for obj in stripes + turret_stripes:
        obj.data.materials.append(colour)
    # At rest the gun points 45 degrees up, as the game holds it.
    cannon.rotation_euler = (0, math.radians(-45), 0)
    return dict(chassis=chassis, wheels=wheels, stripes=stripes, turret=top, gun=cannon, kit=kit, pd=pd,
                turret_stripes=turret_stripes)


def export_turret_parts(model, parent, parts, texture):
    """The turret's bones and meshes under `parent`: TURRET01 turning, TURRETEL01 pitching."""
    t = model.bone("TURRET01", parent, (0, 0, 0) if parent == w3d.ROOT else FIREPOINT)
    el = model.bone("TURRETEL01", t, GUN_AT)
    model.mesh("TURRET01", t, **mesh_data(parts["turret"]), texture=texture)
    model.mesh("TURRETEL01", el, **mesh_data(parts["gun"]), texture=texture)
    for obj in parts["turret_stripes"]:
        model.mesh(obj.name, t, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER)
    return t, el


def export_hull(parts, name, hull_texture, texture):
    model = w3d.Model(name)
    bones = {}
    for obj in parts["wheels"]:
        bones[obj.name] = model.bone(obj.name, w3d.CHASSIS, tuple(obj.location))
    model.bone("FIREPOINT01", w3d.CHASSIS, FIREPOINT)
    model.bone("TURRETFX03", w3d.CHASSIS, DESIGNATOR)
    for i, at in enumerate(LASERS):
        model.bone(f"LAZERSPOT0{i + 1}", w3d.CHASSIS, at)
    model.bone("SMOKE01", w3d.CHASSIS, (-8.0, 0.0, 9.4))
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=hull_texture)
    for obj in parts["wheels"]:
        model.mesh(obj.name, bones[obj.name], **mesh_data(obj), texture=boxer.TIRE_TEXTURE)
    model.mesh("DESIGNATOR", w3d.CHASSIS, **mesh_data(parts["kit"]), texture=texture)
    model.mesh("POINTDEFENCE", w3d.CHASSIS, **mesh_data(parts["pd"]), texture=texture)
    for obj in parts["stripes"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False,
                   shader=w3d.ALPHA_TEST_SHADER)
    # The turret, hidden unless disguised: in the hull model its meshes keep their own names under the bone
    # TURRET01, whose sub-object the draw module hides.
    export_turret_parts(model, w3d.CHASSIS, parts, texture)
    save(model, name)


def export_turret(parts, name, texture):
    model = w3d.Model(name)
    model.pivots = [("ROOTTRANSFORM", -1, (0, 0, 0))]
    t, el = export_turret_parts(model, w3d.ROOT, parts, texture)
    model.bone("TURRETEL", t, GUN_AT)
    model.bone("TURRETFX01", el, MUZZLE)
    model.bone("TURRETFX02", el, POD_FRONT)
    save(model, name)


def save(model, name):
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = build()
    # mesh_data reads the mesh in its own space: the gun's tilt in Blender is for the previews only.
    export_hull(parts, NAME, HULL_TEXTURE, TEXTURE)
    export_hull(parts, NAME + "_D", HULL_DAMAGED, DAMAGED_TEXTURE)
    export_turret(parts, NAME + "_G", TEXTURE)
    export_turret(parts, NAME + "_GD", DAMAGED_TEXTURE)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    boxer.render_previews(os.path.join(BUILD, NAME))


if __name__ == "__main__":
    main()

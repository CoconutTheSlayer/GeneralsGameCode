"""The European NH90, a transport helicopter (one four-blade main rotor, a four-blade tail rotor, sponsons
with the main wheels, a rear ramp), modelled in Blender from simple shapes and written as a W3D model for
the game, in place of the USA Chinook it is built on. It carries supplies and troops as the Chinook does.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/nh90.py

Writes resources/macos/GameData/Art/W3D/EUNH90.w3d and EUNH90_D.w3d (damaged), Art/TexturesHD/eunh_*.tga,
and build/models/EUNH90.blend with previews next to it. Shapes, texture and export helpers: tiger.py.

The rotors spin as the Chinook's do: a looping W3D animation in the model's file (EUNH90.EUNH90, 21 frames
at 30 a second) turns PROPELLER01 (the main rotor, with its blurred blades PROPS01) a full turn and
PROPELLER02 (the tail rotor) two.

Bones (the Chinook's, where the game looks for them):
    PROPELLER01, PROPELLER02          main and tail rotor (HelicopterSlowDeath: blades fly off, smoke trail)
    ROPESTART01..04, ROPEEND01..04    where the ropes hang from the side doors for a combat drop
    EXITSTART01..03, EXITEND01..03    the way out for passengers: down the rear ramp (01), the side doors
    EXHAUST01/02, SMOKE01/02          the engines' exhausts, damage smoke
    HOUSECOLOR01                      the player's colour on the fin and the engine cowling
"""
import math
import os
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from blender_kit import box, cylinder, load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
import nh90_paint  # noqa: E402
import w3d  # noqa: E402
from tiger import (BUILD, DATA, blur_disc, blur_material, bake_occlusion, export_layout, flat_quad,  # noqa: E402
                   fuselage_station, loft, render_previews, run_painter, spin, team_colour, unwrap)

NAME = "EUNH90"
BODY, BODY_D, ROTOR = "eunh_body.tga", "eunh_body_d.tga", "eunh_rotor.tga"
LAYOUT = nh90_paint.NH90

ROTOR_AT, ROTOR_RADIUS, ROTOR_BLADES = (1.5, 0.0, 12.5), 20.0, 4
TAIL_AT, TAIL_RADIUS, TAIL_BLADES = (-24.2, 0.95, 12.0), 3.8, 4
# The tail rotor (on the left of the fin) turns about its bone's Z, which points left (+Y).
TAIL_ROTATION = (-math.sin(math.pi / 4), 0.0, 0.0, math.cos(math.pi / 4))
# Quarter turns about Z for bones that face sideways or back (the Chinook's rope ends face out).
FACING = {0: (0.0, 0.0, 0.0, 1.0), 90: (0.0, 0.0, math.sin(math.pi / 4), math.cos(math.pi / 4)),
          -90: (0.0, 0.0, -math.sin(math.pi / 4), math.cos(math.pi / 4)), 180: (0.0, 0.0, 1.0, 0.0)}
# Ropes hang from the sliding doors, front and back of each; the rope ends twelve units below.
ROPES = [((4.6, 3.7, 2.4), (4.6, 4.2, -10.5), 0, -90), ((-0.8, 3.7, 2.4), (-0.8, 4.2, -10.5), 0, -90),
         ((4.6, -3.7, 2.4), (4.6, -4.2, -10.5), 180, 90), ((-0.8, -3.7, 2.4), (-0.8, -4.2, -10.5), 180, 90)]
EXITS = [((-8.5, 0.0, 3.0), (-21.0, 0.0, 0.0)), ((2.0, 2.4, 3.0), (2.0, 9.5, 0.0)), ((2.0, -2.4, 3.0), (2.0, -9.5, 0.0))]


def hull():
    bm = bmesh.new()
    # The fuselage: the rounded nose and cockpit, the tall square cabin, the underside rising to the rear
    # ramp, then the tail boom.
    loft(bm, [
        fuselage_station(19.4, 3.8, 5.0, 0.5, 2.2),
        fuselage_station(18.4, 2.6, 6.2, 1.9, 2.4),
        fuselage_station(16.2, 1.9, 7.6, 2.9, 2.6),
        fuselage_station(13.4, 1.6, 8.6, 3.4, 3.0),
        fuselage_station(10.0, 1.5, 8.9, 3.6, 3.4),
        fuselage_station(-4.5, 1.5, 8.9, 3.6, 3.4),
        fuselage_station(-8.2, 1.6, 8.8, 3.5, 3.2),
        fuselage_station(-12.0, 4.0, 8.6, 2.6, 3.0),
        fuselage_station(-14.6, 5.6, 8.4, 1.6, 2.6),
        fuselage_station(-21.0, 6.4, 8.3, 0.95, 2.4),
        fuselage_station(-24.8, 6.9, 8.0, 0.45, 2.2),
    ], segments=12)
    # The engines and the main gearbox on the roof, the mast.
    loft(bm, [fuselage_station(9.8, 8.0, 9.0, 1.4, 2.4), fuselage_station(7.8, 8.0, 10.6, 2.5, 2.8),
              fuselage_station(-3.5, 8.0, 10.9, 2.7, 2.8), fuselage_station(-7.6, 8.0, 10.1, 2.1, 2.6),
              fuselage_station(-9.8, 8.2, 9.0, 1.0, 2.2)], segments=12)
    cylinder(bm, (ROTOR_AT[0], 0, 11.4), 0.6, 1.6, segments=8)
    for side in (1, -1):
        loft(bm, [(-6.8, side * 2.3, 9.7, 0.6, 0.5, 2.0), (-8.6, side * 2.7, 9.9, 0.55, 0.45, 2.0)], segments=8)
    # Sponsons with the main wheels; the nose wheels.
    for side in (1, -1):
        loft(bm, [fuselage_station(5.4, 1.4, 2.8, 0.35, 2.2, side * 3.7), fuselage_station(3.8, 0.9, 3.7, 1.1, 2.8, side * 3.9),
                  fuselage_station(-4.6, 0.9, 3.7, 1.1, 2.8, side * 3.9), fuselage_station(-6.4, 1.4, 3.0, 0.4, 2.2, side * 3.7)],
             segments=10)
        cylinder(bm, (-1.0, side * 4.1, 0.9), 0.9, 0.6, axis="Y", segments=10)
        cylinder(bm, (13.6, side * 0.55, 0.7), 0.7, 0.45, axis="Y", segments=10)
    cylinder(bm, (13.6, 0, 1.3), 0.18, 1.2, segments=6)
    # Sensors under the nose: a weather radar fairing and a small turret.
    loft(bm, [(19.0, 0, 3.3, 0.5, 0.4, 2.2), (19.8, 0, 3.4, 0.35, 0.3, 2.0)], segments=8)
    # The fin, swept back, the tail rotor's gearbox, the stabiliser on the right.
    loft(bm, [(7.6, -21.9, 0, 2.7, 0.36, 2.6), (11.0, -23.4, 0, 2.0, 0.32, 2.6), (15.0, -25.2, 0, 1.3, 0.26, 2.6)],
         axis="Z", segments=8)
    cylinder(bm, (TAIL_AT[0], 0.55, TAIL_AT[2]), 0.45, 0.5, axis="Y", segments=8)
    loft(bm, [(-0.2, -23.2, 10.6, 1.2, 0.16, 2.6), (-5.2, -23.4, 10.8, 0.9, 0.13, 2.6)], axis="Y", segments=8)
    # A tail skid under the boom.
    box(bm, (-22.6, -0.2, 5.6), (-21.4, 0.2, 6.6))
    # Steps under the doors.
    for side in (1, -1):
        box(bm, (4.4, side * 3.4, 1.0), (-0.6, side * 4.0, 1.25))
    return new_object("CHASSIS", bm)


def rotor_head():
    from mathutils import Matrix
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0), 1.1, 0.8, segments=10)
    cylinder(bm, (0, 0, 0.75), 0.45, 0.8, segments=6)
    for b in range(ROTOR_BLADES):
        blade = bmesh.new()
        box(blade, (0.8, -0.38, -0.14), (4.1, 0.38, 0.14))
        bmesh.ops.rotate(blade, verts=blade.verts, cent=(0, 0, 0),
                         matrix=Matrix.Rotation(2 * math.pi * b / ROTOR_BLADES + math.radians(45), 3, "Z"))
        me = bpy.data.meshes.new("tmp")
        blade.to_mesh(me)
        blade.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    return new_object("PROPELLER01", bm, ROTOR_AT)


def tail_rotor():
    from mathutils import Matrix
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0), 0.45, 0.5, segments=8)
    for b in range(TAIL_BLADES):
        blade = bmesh.new()
        box(blade, (0.3, -0.3, -0.07), (TAIL_RADIUS, 0.3, 0.07))
        bmesh.ops.rotate(blade, verts=blade.verts, cent=(0, 0, 0),
                         matrix=Matrix.Rotation(2 * math.pi * b / TAIL_BLADES, 3, "Z"))
        me = bpy.data.meshes.new("tmp")
        blade.to_mesh(me)
        blade.free()
        bm.from_mesh(me)
        bpy.data.meshes.remove(me)
    obj = new_object("PROPELLER02", bm, TAIL_AT)
    obj.rotation_euler = (-math.pi / 2, 0, 0)
    return obj


def house_colour():
    """The player's colour: both sides of the fin and the top of the engine cowling."""
    bm = bmesh.new()
    for side in (1, -1):
        y = side * 0.42
        flat_quad(bm, [(-21.4, y, 8.6), (-24.0, y, 8.6), (-24.9, y, 11.0), (-22.6, y, 11.0)], flip=side < 0)
    flat_quad(bm, [(-0.6, -1.0, 10.96), (-0.6, 1.0, 10.96), (-3.4, 1.0, 10.96), (-3.4, -1.0, 10.96)])
    obj = new_object("HOUSECOLOR01", bm)
    for poly in obj.data.polygons:
        poly.use_smooth = False
    return obj


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    chassis, head, tail = hull(), rotor_head(), tail_rotor()
    blur = blur_disc("PROPS01", ROTOR_RADIUS, ROTOR_BLADES)
    blur.location = ROTOR_AT
    colour = house_colour()
    painted = ((chassis, "hull"), (head, "rotor"), (tail, "tail"))
    for obj, part in painted:
        smooth_by_angle(obj, 40)
        unwrap(obj, part, LAYOUT)
    colour.data.uv_layers.new(name="UVMap")
    w3d.write_house_colour(tex_dir)
    layout_path = os.path.join(BUILD, NAME + "_layout.json")
    export_layout(NAME, painted, LAYOUT, layout_path)
    occlusion = os.path.join(BUILD, NAME + "_ao.png")
    blur.hide_render = colour.hide_render = True
    bake_occlusion([chassis, head, tail], occlusion)
    blur.hide_render = colour.hide_render = False
    run_painter("nh90_paint.py", layout_path, tex_dir, occlusion)
    body = load_image(os.path.join(tex_dir, BODY))
    for obj, _ in painted:
        textured(obj, body)
    blur_material(blur, load_image(os.path.join(tex_dir, ROTOR)))
    team_colour([colour])
    return dict(chassis=chassis, head=head, tail=tail, blur=blur, colour=colour)


def export(parts, name, body):
    model = w3d.Model(name)
    head = model.bone("PROPELLER01", w3d.CHASSIS, ROTOR_AT)
    tail = model.bone("PROPELLER02", w3d.CHASSIS, TAIL_AT, rotation=TAIL_ROTATION)
    for i, (start, end, start_facing, end_facing) in enumerate(ROPES):
        model.bone(f"ROPESTART{i + 1:02d}", w3d.CHASSIS, start, rotation=FACING[start_facing])
        model.bone(f"ROPEEND{i + 1:02d}", w3d.CHASSIS, end, rotation=FACING[end_facing])
    for i, (start, end) in enumerate(EXITS):
        model.bone(f"EXITSTART{i + 1:02d}", w3d.ROOT, start)
        model.bone(f"EXITEND{i + 1:02d}", w3d.ROOT, end)
    for i, side in enumerate((1, -1)):
        model.bone(f"EXHAUST{i + 1:02d}", w3d.CHASSIS, (-8.8, side * 2.75, 9.9))
        model.bone(f"SMOKE{i + 1:02d}", w3d.CHASSIS, (-6.0, side * 2.2, 10.2))
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=body)
    model.mesh("PROPELLER01", head, **mesh_data(parts["head"]), texture=body, shadow=False)
    model.mesh("PROPELLER02", tail, **mesh_data(parts["tail"]), texture=body, shadow=False)
    model.mesh("PROPS01", head, **mesh_data(parts["blur"]), texture=ROTOR, shadow=False, shader=w3d.ALPHA_BLEND_SHADER)
    model.mesh("HOUSECOLOR01", w3d.CHASSIS, **mesh_data(parts["colour"]), texture=w3d.HOUSE_COLOUR_TEXTURE,
               shadow=False, shader=w3d.ALPHA_TEST_SHADER)
    model.animate(21, 30, {head: spin(21, 1), tail: spin(21, 2)})
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    parts = build()
    export(parts, NAME, BODY)
    export(parts, NAME + "_D", BODY_D)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    render_previews(os.path.join(BUILD, NAME), distance=80.0, height=50.0, target_z=6.0)


if __name__ == "__main__":
    main()

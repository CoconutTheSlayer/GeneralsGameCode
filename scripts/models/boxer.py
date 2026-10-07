"""The European Boxer, an eight-wheeled armoured infantry vehicle, modelled in Blender from simple shapes and
written as a W3D model for the game. Everything in it is made here: the shapes, the camouflage and the
ambient occlusion baked into it, so the model and its textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/boxer.py

Writes resources/macos/GameData/Art/W3D/EUBOXER.w3d, Art/TexturesHD/euboxer.tga and euboxer_tire.tga,
and build/models/EUBOXER.blend (to open and change in Blender) with previews next to it.

The game's axes: +X forward, +Z up, in world units (a Boxer is about 30 long). Bones:
    CHASSIS                  hull
    TIRE01..TIRE08           wheels, front to back, left (+Y) then right; the truck drawer turns them
    TURRET                   the remote weapon station, turning about Z
    MUZZLE01, MUZZLEFX01     where the gun fires, and its flash
    HOUSECOLOR01/02          side stripes in the player's colour
"""
import json
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
import boxer_layout  # noqa: E402
import w3d  # noqa: E402

NAME = "EUBOXER"
HULL_TEXTURE, TIRE_TEXTURE = "euboxer.tga", "euboxer_tire.tga"
DAMAGED_TEXTURE = "euboxer_d.tga"


# Shapes, in game units.
WHEEL_X = (11.2, 6.4, -4.4, -9.2)
WHEEL_Y, WHEEL_Z, WHEEL_RADIUS, WHEEL_WIDTH = 4.45, 2.5, 2.5, 1.5
HULL_HALF_WIDTH, HULL_BOTTOM = 5.5, 5.1
# Side view of the upper hull (x, z), front to back over the top: bow, glacis, driver's roof, the raised
# mission module.
HULL_PROFILE = [(-15.0, HULL_BOTTOM), (14.0, HULL_BOTTOM), (15.6, 6.1), (9.0, 7.7), (0.5, 8.0), (-0.8, 9.0), (-15.0, 9.0)]
LOWER_PROFILE = [(-14.5, 2.2), (12.5, 2.2), (14.7, 5.3), (-14.5, 5.3)]
LOWER_HALF_WIDTH = 3.4
TURRET_AT = (-3.5, 0.0, 9.0)
CHINE_Z = 6.3


# --- making shapes ---------------------------------------------------------------------------------

def new_object(name, bm, location=(0, 0, 0)):
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    bpy.context.scene.collection.objects.link(obj)
    return obj


def prism(bm, profile, half_width, taper_from=None, taper=1.0):
    """The side profile (x, z) pushed out to both sides; above taper_from the sides lean in."""
    def y_at(z, side):
        if taper_from is not None and z > taper_from:
            return side * half_width * taper
        return side * half_width
    left = [bm.verts.new((x, y_at(z, 1), z)) for x, z in profile]
    right = [bm.verts.new((x, y_at(z, -1), z)) for x, z in profile]
    bm.faces.new(list(reversed(left)))
    bm.faces.new(right)
    n = len(profile)
    for i in range(n):
        j = (i + 1) % n
        bm.faces.new((left[i], left[j], right[j], right[i]))


def box(bm, a, b):
    """A box between two corners, given in any order."""
    lo = [min(p, q) for p, q in zip(a, b)]
    hi = [max(p, q) for p, q in zip(a, b)]
    bmesh.ops.create_cube(bm, size=1.0, matrix=_box_matrix(lo, hi))


def _box_matrix(lo, hi):
    from mathutils import Matrix
    centre = [(a + b) / 2 for a, b in zip(lo, hi)]
    size = [b - a for a, b in zip(lo, hi)]
    return Matrix.Translation(centre) @ Matrix.Diagonal((*size, 1.0))


def cylinder(bm, centre, radius, length, axis="Z", segments=16):
    from mathutils import Matrix
    rot = {"Z": Matrix.Identity(4), "X": Matrix.Rotation(math.pi / 2, 4, "Y"), "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=length,
                          matrix=Matrix.Translation(centre) @ rot)


def hull():
    bm = bmesh.new()
    prism(bm, HULL_PROFILE, HULL_HALF_WIDTH, taper_from=7.0, taper=0.9)
    # The chine: the sides bend out a little above the wheels, as on the real vehicle.
    geom = bm.verts[:] + bm.edges[:] + bm.faces[:]
    bmesh.ops.bisect_plane(bm, geom=geom, plane_co=(0, 0, CHINE_Z), plane_no=(0, 0, 1))
    for v in bm.verts:
        if abs(v.co.z - CHINE_Z) < 1e-4 and abs(v.co.y) > 1.0:
            v.co.y *= 1.06
    # Chamfered edges catch the light.
    sharp = [e for e in bm.edges if e.is_manifold and e.calc_face_angle(0) > math.radians(25)]
    bmesh.ops.bevel(bm, geom=sharp, offset=0.22, segments=1, affect="EDGES", profile=0.5)
    prism(bm, LOWER_PROFILE, LOWER_HALF_WIDTH)
    # Hatches, the driver's hatch, headlights, mirrors, an antenna, the rear door and side stowage boxes.
    for x, y in ((-6.5, 2.4), (-6.5, -2.4), (-11.5, 0.0)):
        cylinder(bm, (x, y, 9.08), 1.1, 0.16)
    cylinder(bm, (3.5, 2.6, 7.95), 0.9, 0.2)
    for side in (1, -1):
        box(bm, (15.0, side * 3.4 - 0.5, 5.7), (15.75, side * 3.4 + 0.5, 6.2))
        box(bm, (13.6, side * 5.5 - 0.15, 6.6), (14.2, side * 5.5 + (0.6 if side > 0 else -0.6), 7.6))
        box(bm, (-13.5, side * 5.0, 6.0), (-8.0, side * 5.85, 8.3))
    cylinder(bm, (-13.8, 4.2, 11.0), 0.07, 4.0)
    box(bm, (-15.15, -2.6, 5.4), (-14.9, 2.6, 8.3))
    bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
    return new_object("CHASSIS", bm)


def side_y(z):
    """How far out the hull side is at a height above the chine: it leans in towards the roof."""
    chine = (HULL_HALF_WIDTH + (HULL_HALF_WIDTH * 0.9 - HULL_HALF_WIDTH) * (CHINE_Z - HULL_BOTTOM) / (9.0 - HULL_BOTTOM)) * 1.06
    roof = HULL_HALF_WIDTH * 0.9
    return chine + (roof - chine) * (z - CHINE_Z) / (9.0 - CHINE_Z)


def house_colour(side):
    """A stripe along the side of the mission module, in the player's colour."""
    bm = bmesh.new()
    z0, z1 = 7.3, 8.5
    y0, y1 = side * (side_y(z0) + 0.06), side * (side_y(z1) + 0.06)
    verts = [bm.verts.new(v) for v in ((-14.4, y0, z0), (-1.4, y0, z0), (-1.4, y1, z1), (-14.4, y1, z1))]
    bm.faces.new(verts if side < 0 else list(reversed(verts)))
    return new_object(f"HOUSECOLOR0{1 if side > 0 else 2}", bm)


def wheel(name, location):
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0), WHEEL_RADIUS, WHEEL_WIDTH, axis="Y", segments=18)
    # The hub: the outer cap inset and pushed in.
    outer = max(bm.faces, key=lambda f: f.calc_center_median().y * (1 if location[1] > 0 else -1))
    inset = bmesh.ops.inset_region(bm, faces=[outer], thickness=0.9, depth=-0.25)
    del inset
    return new_object(name, bm, location)


def turret():
    bm = bmesh.new()
    cylinder(bm, (0, 0, 0.25), 1.5, 0.5, segments=16)
    box(bm, (-1.2, -1.0, 0.5), (1.2, 1.0, 1.8))
    box(bm, (-0.8, 1.0, 0.7), (0.6, 1.7, 1.6))      # ammunition box
    box(bm, (0.0, -1.6, 0.9), (1.2, -1.0, 1.7))     # sight
    box(bm, (0.6, -0.3, 1.0), (2.0, 0.3, 1.5))      # gun receiver
    cylinder(bm, (3.6, 0, 1.25), 0.16, 3.2, axis="X", segments=8)
    return new_object("TURRET", bm, TURRET_AT)


MUZZLE = (5.3, 0.0, 1.25)  # in the turret's space


def muzzle_flash():
    bm = bmesh.new()
    x0, x1, r = 0.0, 2.2, 0.7
    for a in (0.0, math.pi / 2):
        c, s = math.cos(a) * r, math.sin(a) * r
        verts = [bm.verts.new(v) for v in ((x0, -c, -s), (x1, -c, -s), (x1, c, s), (x0, c, s))]
        bm.faces.new(verts)
    obj = new_object("MUZZLEFX01", bm, [TURRET_AT[i] + MUZZLE[i] for i in range(3)])
    return obj


# --- textures --------------------------------------------------------------------------------------

def panel_unwrap(obj, part):
    """UVs like the game's vehicles: every face projected straight onto its panel (boxer_layout.py)."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        grp = boxer_layout.group(tuple(poly.normal))
        for li in poly.loop_indices:
            uv.data[li].uv = boxer_layout.uv(part, grp, tuple(me.vertices[me.loops[li].vertex_index].co))


def export_layout(parts, path):
    """The faces as they lie on the texture, and which of their edges are seams, for boxer_paint.py."""
    faces = []
    for obj, part in parts:
        me = obj.data
        edge_faces = {}
        for poly in me.polygons:
            for key in poly.edge_keys:
                edge_faces.setdefault(key, []).append(poly)
        for poly in me.polygons:
            grp = boxer_layout.group(tuple(poly.normal))
            vs = list(poly.vertices)
            sharp = []
            for i in range(len(vs)):
                key = tuple(sorted((vs[i], vs[(i + 1) % len(vs)])))
                around = edge_faces.get(key, [])
                sharp.append(len(around) != 2 or around[0].normal.angle(around[1].normal, 0) > math.radians(25))
            faces.append(dict(part=part, group=grp, px=[boxer_layout.pixel(part, grp, tuple(me.vertices[v].co)) for v in vs], sharp=sharp))
    with open(path, "w") as f:
        json.dump(dict(faces=faces), f)


def paint(layout_path, tex_dir):
    """Paints the textures (boxer_paint.py runs outside Blender: it needs Pillow)."""
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, "boxer_paint.py"), layout_path, tex_dir], check=True)


def load_image(path):
    image = bpy.data.images.load(path, check_existing=True)
    image.reload()
    return image


def wheel_uvs(obj):
    """Tread around the tyre (texture's upper half), the hub on the sides (lower half)."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        side = abs(poly.normal.y) > 0.7
        for li in poly.loop_indices:
            co = me.vertices[me.loops[li].vertex_index].co
            if side:
                uv.data[li].uv = (0.5 + co.x / (WHEEL_RADIUS * 2.1), 0.75 + co.z / (WHEEL_RADIUS * 4.2))
            else:
                angle = (math.atan2(co.z, co.x) / (2 * math.pi)) % 1.0
                uv.data[li].uv = (angle * 3, 0.25 + co.y / WHEEL_WIDTH * 0.45)


def textured(obj, image):
    mat = bpy.data.materials.new(obj.name)
    mat.use_nodes = True
    node = mat.node_tree.nodes.new("ShaderNodeTexImage")
    node.image = image
    mat.node_tree.links.new(node.outputs["Color"], mat.node_tree.nodes["Principled BSDF"].inputs["Base Color"])
    mat.node_tree.nodes.active = node
    obj.data.materials.clear()
    obj.data.materials.append(mat)


def smooth_by_angle(obj, degrees=35):
    bpy.ops.object.select_all(action="DESELECT")
    obj.select_set(True)
    bpy.context.view_layer.objects.active = obj
    bpy.ops.object.shade_auto_smooth(angle=math.radians(degrees))


def mesh_data(obj):
    """Vertices (in the object's space), normals, uvs and triangles, one W3D vertex per distinct corner."""
    depsgraph = bpy.context.evaluated_depsgraph_get()
    me = obj.evaluated_get(depsgraph).to_mesh()
    me.calc_loop_triangles()
    uv = me.uv_layers.active.data
    normals = me.corner_normals
    index, verts, norms, uvs, tris = {}, [], [], [], []
    for tri in me.loop_triangles:
        corners = []
        for li in tri.loops:
            v = me.loops[li].vertex_index
            n = tuple(round(a, 4) for a in normals[li].vector)
            t = tuple(round(a, 5) for a in uv[li].uv)
            key = (v, n, t)
            if key not in index:
                index[key] = len(verts)
                verts.append(tuple(me.vertices[v].co))
                norms.append(n)
                uvs.append(t)
            corners.append(index[key])
        tris.append(corners)
    obj.evaluated_get(depsgraph).to_mesh_clear()
    return dict(verts=verts, normals=norms, uvs=uvs, tris=tris)


def render_previews(prefix):
    from mathutils import Vector
    scene = bpy.context.scene
    scene.render.engine = "BLENDER_EEVEE_NEXT" if "BLENDER_EEVEE_NEXT" in [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties["engine"].enum_items] else "BLENDER_EEVEE"
    scene.render.resolution_x, scene.render.resolution_y = 800, 600
    world = bpy.data.worlds.new("sky")
    world.use_nodes = True
    world.node_tree.nodes["Background"].inputs["Color"].default_value = (0.6, 0.62, 0.65, 1)
    world.node_tree.nodes["Background"].inputs["Strength"].default_value = 0.8
    scene.world = world
    sun = bpy.data.objects.new("sun", bpy.data.lights.new("sun", "SUN"))
    sun.data.energy = 3.5
    sun.rotation_euler = (math.radians(40), math.radians(10), math.radians(30))
    scene.collection.objects.link(sun)
    cam = bpy.data.objects.new("camera", bpy.data.cameras.new("camera"))
    cam.data.lens = 50
    scene.collection.objects.link(cam)
    scene.camera = cam
    for i, angle in enumerate((35, 145, 250)):
        a = math.radians(angle)
        cam.location = Vector((math.cos(a) * 48, math.sin(a) * 48, 30))
        cam.rotation_euler = (Vector((0, 0, 4)) - cam.location).to_track_quat("-Z", "Y").to_euler()
        scene.render.filepath = f"{prefix}_{i}.png"
        bpy.ops.render.render(write_still=True)


def build():
    """Makes the Boxer in the open scene: its parts, UVs, paint and textures. Returns the parts."""
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    os.makedirs(tex_dir, exist_ok=True)
    chassis, top = hull(), turret()
    flash = muzzle_flash()
    stripes = [house_colour(1), house_colour(-1)]
    wheels = []
    for i, x in enumerate(WHEEL_X):
        for j, side in enumerate((1, -1)):
            wheels.append(wheel(f"TIRE0{i * 2 + j + 1}", (x, side * WHEEL_Y, WHEEL_Z)))
    for obj, part in ((chassis, "hull"), (top, "turret")):
        smooth_by_angle(obj)
        panel_unwrap(obj, part)
    for obj in wheels:
        smooth_by_angle(obj, 50)
        wheel_uvs(obj)
    for obj in stripes + [flash]:
        obj.data.uv_layers.new(name="UVMap")

    layout = os.path.join(BUILD, NAME + "_layout.json")
    os.makedirs(BUILD, exist_ok=True)
    export_layout(((chassis, "hull"), (top, "turret")), layout)
    paint(layout, tex_dir)
    hull_image = load_image(os.path.join(tex_dir, HULL_TEXTURE))
    tire_image = load_image(os.path.join(tex_dir, TIRE_TEXTURE))
    for obj in (chassis, top):
        textured(obj, hull_image)
    for obj in wheels:
        textured(obj, tire_image)
    colour = bpy.data.materials.new("house colour")
    colour.diffuse_color = (0.9, 0.75, 0.1, 1)
    for obj in stripes:
        obj.data.materials.append(colour)
    return dict(chassis=chassis, turret=top, flash=flash, stripes=stripes, wheels=wheels)


def export(parts, name, hull_texture):
    """Writes the model; the damaged one is the same with another texture."""
    model = w3d.Model(name)
    bones = {}
    for obj in parts["wheels"] + [parts["turret"]]:
        bones[obj.name] = model.bone(obj.name, w3d.CHASSIS, tuple(obj.location))
    model.bone("MUZZLE01", bones["TURRET"], MUZZLE)
    bones["MUZZLEFX01"] = model.bone("MUZZLEFX01", bones["TURRET"], MUZZLE)
    model.mesh("CHASSIS", w3d.CHASSIS, **mesh_data(parts["chassis"]), texture=hull_texture)
    model.mesh("TURRET", bones["TURRET"], **mesh_data(parts["turret"]), texture=hull_texture)
    for obj in parts["wheels"]:
        model.mesh(obj.name, bones[obj.name], **mesh_data(obj), texture=TIRE_TEXTURE)
    for obj in parts["stripes"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture="Housecolor2.tga", shadow=False)
    model.mesh("MUZZLEFX01", bones["MUZZLEFX01"], **mesh_data(parts["flash"]), texture="EXTnkMzl01.tga", shadow=False,
               shader=w3d.ADDITIVE_SHADER)
    out = os.path.join(DATA, "Art", "W3D", name + ".w3d")
    os.makedirs(os.path.dirname(out), exist_ok=True)
    model.save(out)
    print(f"{name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles -> {out}")


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    export(parts, NAME, HULL_TEXTURE)
    export(parts, NAME + "_D", DAMAGED_TEXTURE)
    parts["flash"].hide_render = True
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))
    render_previews(os.path.join(BUILD, NAME))


if __name__ == "__main__":
    main()

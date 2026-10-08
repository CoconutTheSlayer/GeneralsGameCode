"""The European Command Centre, modelled in Blender from simple shapes and written as W3D models for the
game: a two-storey command block, a command tower with a radar dome, a vehicle bay, an antenna mast,
satellite dishes and a helipad on a concrete pad. Its textures are tiling materials painted by
command_centre_paint.py; everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/command_centre.py

Six models, the same shapes with other paint: EUCMDHQ (intact), _D (damaged), _E (wrecked: the dome and
mast are gone), each with a night version (_N, _DN, _EN) with lit windows. They go to
resources/macos/GameData/Art/W3D, the textures to Art/TexturesHD, and build/models/EUCMDHQ.blend.

The footprint is the USA's (a box 120 long, 140 wide, 49 high, centred). New units leave the vehicle
bay along EXITSTART -> EXITEND, towards +X.
"""
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
from blender_kit import box, cylinder, load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
import w3d  # noqa: E402

NAME = "EUCMDHQ"
PAD_Z = 0.8
# Materials: each a mesh of its own with a tiling texture. (texture, units per texture across, up)
MATERIALS = {
    "BUILDING": ("eucc_facade.tga", 40.0, 20.0),   # walls with window bands, two storeys per texture
    "ROOF": ("eucc_roof.tga", 24.0, 24.0),
    "BAY": ("eucc_bay.tga", 24.0, 14.2),           # the vehicle bay's ribbed walls
    "DOOR": ("eucc_door.tga", 24.0, 12.2),         # stretched once over the bay door
    "PAD": ("eucc_pad.tga", 30.0, 30.0),
    "METAL": ("eucc_metal.tga", 6.0, 6.0),          # mast, dishes, rails, lights, machinery
    "HELIPAD": ("eucc_helipad.tga", 24.0, 24.0),    # one decal
    "EMBLEM": ("eucc_emblem.tga", 10.0, 10.0),      # the faction's mark on the tower
}
# Damage and night: which textures each version uses instead (the rest stay).
VERSIONS = {
    "": {},
    "_D": {"eucc_facade.tga": "eucc_facade_d.tga", "eucc_roof.tga": "eucc_roof_d.tga", "eucc_bay.tga": "eucc_bay_d.tga",
           "eucc_door.tga": "eucc_door_d.tga"},
    "_E": {"eucc_facade.tga": "eucc_facade_e.tga", "eucc_roof.tga": "eucc_roof_e.tga", "eucc_bay.tga": "eucc_bay_e.tga",
           "eucc_door.tga": "eucc_door_e.tga", "eucc_pad.tga": "eucc_pad_e.tga"},
}
NIGHT = {"eucc_facade.tga": "eucc_facade_n.tga", "eucc_facade_d.tga": "eucc_facade_dn.tga",
         "eucc_facade_e.tga": "eucc_facade_en.tga"}
EXITSTART, EXITEND = (-18.8, 34.5, 0.3), (50.9, 34.5, 0.3)


# --- shapes ----------------------------------------------------------------------------------------

class Parts:
    """One bmesh per material, plus the meshes that stay out of the wreck."""

    def __init__(self):
        self.bm = {name: bmesh.new() for name in MATERIALS}
        self.intact_only = {name: bmesh.new() for name in MATERIALS}

    def __getitem__(self, name):
        return self.bm[name]


def lattice_mast(bm, x, y, z0, z1, width=1.6):
    """An antenna mast: four legs and cross braces."""
    h = width / 2
    for dx, dy in ((-h, -h), (h, -h), (h, h), (-h, h)):
        cylinder(bm, (x + dx, y + dy, (z0 + z1) / 2), 0.12, z1 - z0, segments=5)
    z = z0 + 3.0
    while z < z1:
        for (ax, ay), (bx, by) in (((-h, -h), (h, -h)), ((h, -h), (h, h)), ((h, h), (-h, h)), ((-h, h), (-h, -h))):
            box(bm, (x + min(ax, bx) - 0.08, y + min(ay, by) - 0.08, z - 0.08), (x + max(ax, bx) + 0.08, y + max(ay, by) + 0.08, z + 0.08))
        z += 3.0


def dish(bm, centre, radius, tilt):
    """A satellite dish on a short stand, tilted up towards the sky."""
    from mathutils import Matrix
    x, y, z = centre
    cylinder(bm, (x, y, z + 0.9), 0.35, 1.8, segments=8)
    rot = Matrix.Translation((x, y, z + 2.2 + radius * 0.3)) @ Matrix.Rotation(tilt, 4, "Y")
    bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius, radius2=radius * 0.25, depth=radius * 0.45,
                          matrix=rot @ Matrix.Rotation(math.pi, 4, "X"))
    cylinder(bm, (x + math.sin(tilt) * radius * 0.6, y, z + 2.2 + radius * 0.3 + math.cos(tilt) * radius * 0.6), 0.12,
             radius * 1.2, segments=5)


def radar_dome(bm, centre, radius):
    x, y, z = centre
    cylinder(bm, (x, y, z + 0.8), radius * 0.8, 1.6, segments=20)
    bmesh.ops.create_uvsphere(bm, u_segments=20, v_segments=10, radius=radius,
                              matrix=__import__("mathutils").Matrix.Translation((x, y, z + 1.6 + radius * 0.75)))


def build_shapes():
    p = Parts()
    # The pad, chamfered at its edge.
    box(p["PAD"], (-58, -68, 0.0), (58, 68, PAD_Z))
    # Command block: two storeys, a parapet round the roof.
    box(p["BUILDING"], (-50, -62, PAD_Z), (12, 18, 20.0))
    for a, b in (((-50, -62, 20), (12, -61, 21.4)), ((-50, 17, 20), (12, 18, 21.4)),
                 ((-50, -62, 20), (-49, 18, 21.4)), ((11, -62, 20), (12, 18, 21.4))):
        box(p["BUILDING"], a, b)
    box(p["ROOF"], (-49, -61, 20.0), (11, 17, 20.15))
    # Entrance canopy on the front.
    box(p["METAL"], (12, -36, 8.0), (18, -14, 8.6))
    for y in (-35, -15):
        cylinder(p["METAL"], (17.4, y, (PAD_Z + 8) / 2), 0.35, 8 - PAD_Z, segments=8)
    # Command tower with the radar dome.
    box(p["BUILDING"], (-46, -58, PAD_Z), (-22, -34, 38.0))
    box(p["ROOF"], (-45.5, -57.5, 38.0), (-22.5, -34.5, 38.15))
    radar_dome(p.intact_only["METAL"], (-34, -46, 38.0), 6.0)
    # Vehicle bay with its door to the front, where new units leave.
    box(p["BAY"], (-26, 18, PAD_Z), (30, 54, 15.0))
    box(p["ROOF"], (-25.5, 18.5, 15.0), (29.5, 53.5, 15.15))
    box(p["DOOR"], (30.0, 24.5, PAD_Z), (30.3, 47.5, 13.0))
    # Roof machinery, dishes, the helipad and a mast.
    for x, y in ((-12, -55), (-4, -55), (4, -55)):
        box(p["METAL"], (x - 3, y - 2.5, 20.15), (x + 3, y + 2.5, 23.0))
        cylinder(p["METAL"], (x, y, 23.3), 1.6, 0.6, segments=12)
    dish(p.intact_only["METAL"], (0, 8, 20.15), 3.6, math.radians(35))
    dish(p.intact_only["METAL"], (-40, 6, 20.15), 2.6, math.radians(50))
    lattice_mast(p.intact_only["METAL"], 2, -42, 20.15, 48.0)
    disc = p["HELIPAD"]
    bmesh.ops.create_circle(disc, cap_ends=True, segments=24, radius=11.0,
                            matrix=__import__("mathutils").Matrix.Translation((-14, -18, 20.25)))
    # The faction's mark high on the tower, to the front.
    box(p["EMBLEM"], (-21.95, -50, 28.0), (-21.8, -42, 36.0))
    # Floodlights at the corners, barriers along the edges, leaving the bay's way out open.
    for x, y in ((-55, -65), (55, -65), (-55, 65), (55, 65)):
        cylinder(p["METAL"], (x, y, PAD_Z + 7), 0.3, 14, segments=6)
        box(p["METAL"], (x - 1.2, y - 0.6, PAD_Z + 13.4), (x + 1.2, y + 0.6, PAD_Z + 14.6))
    for y in range(-60, 61, 8):
        if 18 <= y <= 52:
            continue
        box(p["PAD"], (54.5, y - 3, PAD_Z), (56.5, y + 3, PAD_Z + 2.2))
    for x in range(-52, 53, 8):
        for y in (-66, 66):
            box(p["PAD"], (x - 3, y - 1, PAD_Z), (x + 3, y + 1, PAD_Z + 2.2))
    return p


def house_colours():
    """The player's colour: tall banners on the tower's front and side."""
    banners = []
    for i, quad in enumerate((((-21.9, -56, 10), (-21.9, -52, 10), (-21.9, -52, 26), (-21.9, -56, 26)),
                              ((-21.9, -40, 10), (-21.9, -36, 10), (-21.9, -36, 26), (-21.9, -40, 26)),
                              ((-44, -33.9, 10), (-24, -33.9, 10), (-24, -33.9, 13), (-44, -33.9, 13)))):
        bm = bmesh.new()
        verts = [bm.verts.new(v) for v in quad]
        face = bm.faces.new(verts)
        face.normal_update()
        if i < 2 and face.normal.x < 0 or i == 2 and face.normal.y < 0:
            face.normal_flip()
        banners.append(new_object(f"HOUSECOLOR0{i + 1}", bm))
    return banners


# --- UVs -------------------------------------------------------------------------------------------

def world_uvs(obj, across, up, z0=PAD_Z):
    """Tiling UVs from the world: walls along their run and up from the pad, roofs and decals from above."""
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        n = poly.normal
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            if abs(n.z) > 0.7:
                uv.data[li].uv = (x / across, y / up)
            elif abs(n.x) > abs(n.y):
                uv.data[li].uv = ((y if n.x > 0 else -y) / across, (z - z0) / up)
            else:
                uv.data[li].uv = ((-x if n.y > 0 else x) / across, (z - z0) / up)


def stretched_uvs(obj, axes):
    """UVs that stretch the texture once over the object (door, helipad, emblem), seen along `axes`."""
    me = obj.data
    a, b = axes
    co = [v.co for v in me.vertices]
    lo = [min(c[i] for c in co) for i in range(3)]
    hi = [max(c[i] for c in co) for i in range(3)]
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            c = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = ((c[a] - lo[a]) / ((hi[a] - lo[a]) or 1), (c[b] - lo[b]) / ((hi[b] - lo[b]) or 1))


# --- building it -----------------------------------------------------------------------------------

def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    os.makedirs(tex_dir, exist_ok=True)
    os.makedirs(BUILD, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    subprocess.run([python, os.path.join(HERE, "command_centre_paint.py"), tex_dir], check=True)
    shapes = build_shapes()
    objects = {}
    for which, store in (("", shapes.bm), ("_X", shapes.intact_only)):
        for name, bm in store.items():
            if not bm.verts:
                bm.free()
                continue
            bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.001)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            if name == "HELIPAD":  # a flat decal: make it face up
                for face in bm.faces:
                    if face.normal.z < 0:
                        face.normal_flip()
            obj = new_object(name + which, bm)
            texture, across, up = MATERIALS[name]
            if name == "DOOR":
                stretched_uvs(obj, (1, 2))
            elif name in ("HELIPAD",):
                stretched_uvs(obj, (0, 1))
            elif name == "EMBLEM":
                stretched_uvs(obj, (1, 2))
            else:
                world_uvs(obj, across, up)
            smooth_by_angle(obj, 40)
            textured(obj, load_image(os.path.join(tex_dir, texture)))
            objects[name + which] = obj
    banners = house_colours()
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in banners:
        obj.data.uv_layers.new(name="UVMap")
        obj.data.materials.append(colour)
    return objects, banners


def export(objects, banners, suffix, night):
    model = w3d.Model(NAME + suffix + ("N" if night and suffix else "_N" if night else ""))
    model.bone("EXITSTART", w3d.CHASSIS, EXITSTART)
    model.bone("EXITEND", w3d.CHASSIS, EXITEND)
    swap = VERSIONS[suffix]
    for key, obj in objects.items():
        name = key.replace("_X", "")
        if key.endswith("_X") and suffix == "_E":
            continue  # the wreck has lost its dome, mast and dishes
        texture = swap.get(MATERIALS[name][0], MATERIALS[name][0])
        if night:
            texture = NIGHT.get(texture, texture)
        shadow = name in ("BUILDING", "BAY") and not key.endswith("_X")
        model.mesh(key.replace("_X", "2") if key.endswith("_X") else key, w3d.CHASSIS, **mesh_data(obj),
                   texture=texture, shadow=shadow)
    for obj in banners:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture="Housecolor2.tga", shadow=False)
    out = os.path.join(DATA, "Art", "W3D", model.name + ".w3d")
    model.save(out)
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def export_all(objects, banners):
    for suffix in VERSIONS:
        for night in (False, True):
            export(objects, banners, suffix, night)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    objects, banners = build()
    export_all(objects, banners)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

"""The European Command Centre, modelled in Blender and written as W3D models for the game: an octagonal
control tower with a glass cab and radar dome, a hall with a curved ribbed roof and a machinery deck, a
lattice mast with dishes, and a quonset hangar with the faction's mark, on a concrete pad (after a
concept painted in the game's style). Everything is made here, so the models and textures can be shared.

    /Applications/Blender.app/Contents/MacOS/Blender -b -P scripts/models/command_centre.py

How it is painted: command_centre_paint.py paints small tiling surfaces (plaster panels, corrugated
metal, roof deck, door, dome, trim); Blender projects them onto the model, then bakes them and the
ambient occlusion into one texture of the building's own; the painter adds grime and makes the damaged,
wrecked and night versions. Six models use them: EUCMDHQ (intact), _D, _E (wrecked: no dome, mast or
dishes), each with a night version (_N, _DN, _EN) with lit windows.

The footprint is the USA's (120 long, 140 wide, 49 high, centred); new units leave the hangar along
EXITSTART -> EXITEND, towards +X.
"""
import math
import os
import shutil
import subprocess
import sys

import bmesh
import bpy
from mathutils import Matrix

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.normpath(os.path.join(HERE, "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")
BUILD = os.path.join(ROOT, "build", "models")
sys.path.insert(0, HERE)
from blender_kit import load_image, mesh_data, new_object, smooth_by_angle, textured  # noqa: E402
import w3d  # noqa: E402

NAME = "EUCMDHQ"
PAD_Z = 0.8
TEXTURE_SIZE = 1024
EXITSTART, EXITEND = (-18.8, 34.5, 0.3), (50.9, 34.5, 0.3)
# Surfaces: (tile painted by command_centre_paint.py, units per tile) or a plain colour.
SURFACES = {
    "wall": ("tile_wall", 16.0), "trim": ("tile_trim", 12.0), "rib": ("tile_rib", 10.0), "deck": ("tile_deck", 16.0),
    "door": ("tile_door", 12.0), "dome": ("tile_dome", 8.0), "metal": ("tile_metal", 6.0),
    "glass": (34, 60, 74), "dark": (38, 40, 44),
}
SURFACE = {name: i for i, name in enumerate(SURFACES)}


# --- shapes ----------------------------------------------------------------------------------------

class Builder:
    """Shapes added to a bmesh, each face marked with its surface."""

    def __init__(self):
        self.bm = bmesh.new()

    def add(self, surface, make):
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            face.material_index = SURFACE[surface]

    def box(self, surface, a, b):
        lo = [min(p, q) for p, q in zip(a, b)]
        hi = [max(p, q) for p, q in zip(a, b)]
        centre = [(p + q) / 2 for p, q in zip(lo, hi)]
        size = [q - p for p, q in zip(lo, hi)]
        self.add(surface, lambda bm: bmesh.ops.create_cube(
            bm, size=1.0, matrix=Matrix.Translation(centre) @ Matrix.Diagonal((*size, 1.0))))

    def cylinder(self, surface, centre, radius, length, axis="Z", segments=16, radius2=None, rotate=0.0):
        rot = {"Z": Matrix.Rotation(rotate, 4, "Z"), "X": Matrix.Rotation(math.pi / 2, 4, "Y"),
               "Y": Matrix.Rotation(math.pi / 2, 4, "X")}[axis]
        self.add(surface, lambda bm: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius if radius2 is None else radius2,
            depth=length, matrix=Matrix.Translation(centre) @ rot))

    def sphere(self, surface, centre, radius):
        self.add(surface, lambda bm: bmesh.ops.create_uvsphere(
            bm, u_segments=20, v_segments=12, radius=radius, matrix=Matrix.Translation(centre)))

    def extrude_profile(self, surface, profile, x0, x1, cap_surface=None):
        """A closed profile (y, z) pushed along x from x0 to x1."""
        def make(bm):
            a = [bm.verts.new((x0, y, z)) for y, z in profile]
            b = [bm.verts.new((x1, y, z)) for y, z in profile]
            n = len(profile)
            for i in range(n):
                j = (i + 1) % n
                bm.faces.new((a[i], a[j], b[j], b[i]))
            end_a, end_b = bm.faces.new(list(reversed(a))), bm.faces.new(b)
            end_a.material_index = end_b.material_index = SURFACE[cap_surface or surface]
            make.ends = (end_a, end_b)
        before = set(self.bm.faces)
        make(self.bm)
        for face in set(self.bm.faces) - before:
            if face not in make.ends:
                face.material_index = SURFACE[surface]


def arc(cy, cz, radius, start, end, steps):
    return [(cy + math.cos(a) * radius, cz + math.sin(a) * radius)
            for a in (start + (end - start) * i / steps for i in range(steps + 1))]


def hall(b):
    """The command hall: walls with piers, a curved ribbed roof, a machinery deck."""
    x0, x1, y0, y1, top = -38.0, 28.0, -30.0, 12.0, 14.0
    b.box("wall", (x0, y0, PAD_Z), (x1, y1, top))
    b.box("trim", (x0 - 0.4, y0 - 0.4, PAD_Z), (x1 + 0.4, y1 + 0.4, 2.2))          # plinth
    b.box("trim", (x0 - 0.5, y0 - 0.5, top - 1.4), (x1 + 0.5, y1 + 0.5, top))      # cornice
    for x in (x0, x1):
        for y in (y0, y1):
            b.box("wall", (x - 2.2, y - 2.2, PAD_Z), (x + 2.2, y + 2.2, top + 1.6))
            b.box("trim", (x - 2.5, y - 2.5, top + 1.4), (x + 2.5, y + 2.5, top + 2.0))
    # The curved roof over the front part, a segment of a circle.
    sag, half = 7.0, 13.0
    radius = (half ** 2 + sag ** 2) / (2 * sag)
    cy, cz = -2.0, top + sag - radius
    span = math.asin(half / radius)
    curve = arc(cy, cz, radius, math.pi / 2 + span, math.pi / 2 - span, 16)
    b.extrude_profile("rib", [(y, z) for y, z in curve], x0 + 1.5, x1 - 1.5, cap_surface="trim")
    # Windows along the sides, a door at the front.
    for y, face in ((y1, 1), (y0, -1)):
        for x in range(int(x0) + 6, int(x1) - 3, 7):
            b.box("glass", (x, y + face * 0.05, 8.6), (x + 4, y + face * 0.35, 10.8))
            b.box("trim", (x - 0.3, y + face * 0.05, 8.2), (x + 4.3, y + face * 0.45, 8.6))
    b.box("door", (x1, -11, PAD_Z), (x1 + 0.4, -3, 8.5))
    b.box("trim", (x1, -12, 8.5), (x1 + 1.2, -2, 9.3))
    # The machinery deck behind the curve: fans, air conditioning, a pipe, antennas, a parapet.
    b.box("trim", (x0, y0, top), (x1, y0 + 0.6, top + 1.0))
    for x in (-24.0, -10.0):
        b.cylinder("metal", (x, -22, top + 0.9), 3.0, 1.8, segments=16)
        b.cylinder("dark", (x, -22, top + 1.85), 2.4, 0.2, segments=16)
        b.box("metal", (x - 0.15, -24.4, top + 1.9), (x + 0.15, -19.6, top + 2.1))
        b.box("metal", (x - 2.4, -22.15, top + 1.9), (x + 2.4, -21.85, top + 2.1))
    for x in (4.0, 14.0):
        b.box("metal", (x - 3, -27, top), (x + 3, -19, top + 3.2))
        b.box("dark", (x - 2.4, -27.05, top + 0.6), (x + 2.4, -26.9, top + 2.6))
    b.cylinder("metal", ((x0 + x1) / 2, -16.2, top + 0.8), 0.6, x1 - x0 - 6, axis="X", segments=8)
    for x, h in ((-30, 9), (20, 7), (22, 11)):
        b.cylinder("metal", (x, -26, top + h / 2), 0.18, h, segments=6)


def tower(b):
    """The octagonal control tower: a glass cab, a roof and the radar dome."""
    cx, cy = -30.0, -52.0
    rot = math.pi / 8
    b.cylinder("trim", (cx, cy, PAD_Z + 1.2), 10.6, 2.4, segments=8, rotate=rot)
    b.cylinder("wall", (cx, cy, (PAD_Z + 24) / 2), 9.0, 24 - PAD_Z, segments=8, rotate=rot)
    for k in range(8):  # vertical trim strips at the corners
        a = rot + k * math.pi / 4 + math.pi / 8
        x, y = cx + math.cos(a) * 9.0, cy + math.sin(a) * 9.0
        b.box("trim", (x - 0.5, y - 0.5, PAD_Z), (x + 0.5, y + 0.5, 24))
    b.cylinder("trim", (cx, cy, 24.5), 10.2, 1.0, segments=8, rotate=rot)
    b.cylinder("glass", (cx, cy, 28.0), 10.4, 6.0, segments=8, radius2=11.2, rotate=rot)
    for k in range(8):  # mullions
        a = rot + k * math.pi / 4 + math.pi / 8
        x, y = cx + math.cos(a) * 10.85, cy + math.sin(a) * 10.85
        b.box("trim", (x - 0.35, y - 0.35, 25), (x + 0.35, y + 0.35, 31))
    b.cylinder("trim", (cx, cy, 31.6), 12.0, 1.2, segments=8, rotate=rot)
    b.box("door", (cx + 8.6, cy - 2.5, PAD_Z), (cx + 9.4, cy + 2.5, 8.0))


def dome(b):
    cx, cy = -30.0, -52.0
    b.cylinder("metal", (cx, cy, 32.9), 6.4, 1.4, segments=20)
    b.sphere("dome", (cx, cy, 37.4), 6.2)


def mast(b, x=-49.0, y=2.0, z0=PAD_Z, z1=47.0):
    """A lattice antenna mast with two dishes."""
    b.box("trim", (x - 3, y - 3, z0), (x + 3, y + 3, z0 + 1.6))
    half = 1.6
    for dx, dy in ((-half, -half), (half, -half), (half, half), (-half, half)):
        b.add("metal", lambda bm, dx=dx, dy=dy: bmesh.ops.create_cone(
            bm, cap_ends=True, segments=5, radius1=0.25, radius2=0.12, depth=z1 - z0,
            matrix=Matrix.Translation((x + dx * (1 - 0.0), y + dy, (z0 + z1) / 2))))
    z = z0 + 3
    while z < z1 - 2:
        for (ax, ay), (bx, by) in (((-half, -half), (half, -half)), ((half, -half), (half, half)),
                                   ((half, half), (-half, half)), ((-half, half), (-half, -half))):
            b.box("metal", (x + min(ax, bx) - 0.1, y + min(ay, by) - 0.1, z - 0.1),
                  (x + max(ax, bx) + 0.1, y + max(ay, by) + 0.1, z + 0.1))
        z += 3.0
    for zz, radius, facing in ((36.0, 3.4, 0.0), (29.0, 2.4, -math.pi / 2)):
        def make(bm, zz=zz, radius=radius, facing=facing):
            m = (Matrix.Translation((x + math.cos(facing) * 2.4, y + math.sin(facing) * 2.4, zz))
                 @ Matrix.Rotation(facing, 4, "Z") @ Matrix.Rotation(-math.pi / 2 + 0.3, 4, "Y"))
            bmesh.ops.create_cone(bm, cap_ends=True, segments=16, radius1=radius, radius2=radius * 0.3,
                                  depth=radius * 0.4, matrix=m)
        b.add("dome", make)


def hangar(b):
    """The quonset hangar: a half-cylinder of corrugated metal between thick arches, the door to the front."""
    x0, x1, cy, radius, base = -12.0, 30.0, 38.0, 14.0, PAD_Z + 1.5
    b.box("trim", (x0, cy - radius - 0.6, PAD_Z), (x1, cy + radius + 0.6, base))
    half = arc(cy, base, radius, math.pi, 0.0, 18)
    b.extrude_profile("rib", [(y, z) for y, z in half], x0 + 1.0, x1 - 1.0, cap_surface="wall")
    ring_out = arc(cy, base, radius + 1.4, math.pi, 0.0, 18)
    ring_in = arc(cy, base, radius - 0.6, 0.0, math.pi, 18)
    for x in (x0, x1 - 2.0):
        b.extrude_profile("wall", ring_out + ring_in, x, x + 2.0)
    door = arc(cy, base, radius - 0.6, math.pi, 0.0, 18)
    b.extrude_profile("door", [(y, z) for y, z in door], x1 - 0.6, x1 - 0.2)
    b.box("dark", (x1 - 0.2, cy - 0.15, base), (x1 - 0.05, cy + 0.15, base + radius - 1.5))  # the door's middle seam


def build_shapes():
    main, intact = Builder(), Builder()
    hall(main)
    tower(main)
    hangar(main)
    dome(intact)
    mast(intact)
    return main, intact


def pad():
    """The concrete pad, with a chamfered edge; tiled with its own texture."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0, matrix=Matrix.Translation((0, 0, PAD_Z / 2)) @ Matrix.Diagonal((116, 136, PAD_Z, 1)))
    top = [v for v in bm.verts if v.co.z > PAD_Z / 2]
    for v in top:
        v.co.x *= 0.99
        v.co.y *= 0.99
    obj = new_object("PAD", bm)
    me = obj.data
    uv = me.uv_layers.new(name="UVMap")
    for poly in me.polygons:
        for li in poly.loop_indices:
            x, y, z = me.vertices[me.loops[li].vertex_index].co
            uv.data[li].uv = (x / 30.0, y / 30.0) if abs(poly.normal.z) > 0.5 else ((x + y) / 30.0, z / 30.0)
    return obj


def decal(name, corners):
    bm = bmesh.new()
    verts = [bm.verts.new(c) for c in corners]
    bm.faces.new(verts)
    obj = new_object(name, bm)
    uv = obj.data.uv_layers.new(name="UVMap")
    for li, (u, v) in zip(range(4), ((0, 0), (1, 0), (1, 1), (0, 1))):
        uv.data[li].uv = (u, v)
    return obj


def emblems():
    """The faction's mark on the tower's front and on the hangar's side."""
    cx, cy, r = -30.0, -52.0, 8.4
    tower_face = decal("EMBLEM", [(cx + r, cy - 3, 13), (cx + r, cy + 3, 13), (cx + r, cy + 3, 19), (cx + r, cy - 3, 19)])
    # On the hangar's curve, the side towards +Y: a strip that follows the curve, just above it.
    a0, a1, steps = math.radians(22), math.radians(58), 6
    cy2, base, radius = 38.0, PAD_Z + 1.5, 14.15
    bm = bmesh.new()
    rows = []
    for i in range(steps + 1):
        a = a0 + (a1 - a0) * i / steps
        rows.append([bm.verts.new((x, cy2 + math.cos(a) * radius, base + math.sin(a) * radius)) for x in (14.0, 2.0)])
    faces = [bm.faces.new((rows[i][0], rows[i][1], rows[i + 1][1], rows[i + 1][0])) for i in range(steps)]
    hangar_face = new_object("EMBLEM2", bm)
    uv = hangar_face.data.uv_layers.new(name="UVMap")
    for i, poly in enumerate(hangar_face.data.polygons):
        for li, (u, v) in zip(poly.loop_indices, ((0, i / steps), (1, i / steps), (1, (i + 1) / steps), (0, (i + 1) / steps))):
            uv.data[li].uv = (u, v)
    del faces
    return [tower_face, hangar_face]


def house_colours():
    """The player's colour: a band round the tower under the cab, and stripes on the hangar's arches."""
    objects = []
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=False, segments=8, radius1=9.25, radius2=9.25, depth=1.4,
                          matrix=Matrix.Translation((-30, -52, 22.6)) @ Matrix.Rotation(math.pi / 8, 4, "Z"))
    objects.append(new_object("HOUSECOLOR01", bm))
    bm = bmesh.new()
    for x in (-12.05, 30.05):
        outer = arc(38.0, PAD_Z + 1.5, 15.45, math.pi, 0.0, 18)
        inner = arc(38.0, PAD_Z + 1.5, 14.65, 0.0, math.pi, 18)
        verts = [bm.verts.new((x, y, z)) for y, z in outer + inner]
        n = len(outer)
        for i in range(n - 1):
            quad = [verts[i], verts[i + 1], verts[2 * n - 2 - i], verts[2 * n - 1 - i]]
            # Both ways, so that it shows whichever way the arch faces.
            bm.faces.new(quad)
            bm.faces.new([bm.verts.new(v.co) for v in reversed(quad)])
    objects.append(new_object("HOUSECOLOR02", bm))
    for obj in objects:
        obj.data.uv_layers.new(name="UVMap")
    return objects


# --- painting --------------------------------------------------------------------------------------

def surface_material(name, tiles):
    """A surface: its tile projected from all sides in world units, or a plain colour."""
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    nodes, links = mat.node_tree.nodes, mat.node_tree.links
    bsdf = nodes["Principled BSDF"]
    spec = SURFACES[name]
    if isinstance(spec[0], str):
        tile, size = spec
        coords = nodes.new("ShaderNodeTexCoord")
        mapping = nodes.new("ShaderNodeMapping")
        mapping.inputs["Scale"].default_value = (1 / size, 1 / size, 1 / size)
        image = nodes.new("ShaderNodeTexImage")
        image.image = load_image(os.path.join(tiles, tile + ".png"))
        image.projection = "BOX"
        image.projection_blend = 0.15
        links.new(coords.outputs["Object"], mapping.inputs["Vector"])
        links.new(mapping.outputs["Vector"], image.inputs["Vector"])
        links.new(image.outputs["Color"], bsdf.inputs["Base Color"])
    else:
        bsdf.inputs["Base Color"].default_value = [c / 255.0 for c in spec] + [1.0]
    if name == "glass":
        bsdf.inputs["Emission Color"].default_value = (1, 1, 1, 1)
        bsdf.inputs["Emission Strength"].default_value = 0.0
    return mat


def bake(objects, kind, image, emit_glass=False):
    """Bakes into image: kind DIFFUSE (colour only), AO, or EMIT (where the windows are)."""
    for obj in objects:
        for mat in obj.data.materials:
            nodes = mat.node_tree.nodes
            target = nodes.get("bake target") or nodes.new("ShaderNodeTexImage")
            target.name = "bake target"
            target.image = image
            nodes.active = target
            bsdf = nodes["Principled BSDF"]
            if kind == "EMIT":
                bsdf.inputs["Emission Strength"].default_value = 1.0 if mat.name.startswith("glass") else 0.0
            else:
                bsdf.inputs["Emission Strength"].default_value = 0.0
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "CPU"
    scene.cycles.samples = 64 if kind == "AO" else 4
    bake = scene.render.bake
    bake.margin = 8
    bake.use_pass_direct = bake.use_pass_indirect = False
    bake.use_pass_color = True
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.bake(type=kind)


def save(image, path):
    image.filepath_raw = path
    image.file_format = "PNG"
    image.save()


def build():
    tex_dir = os.path.join(DATA, "Art", "TexturesHD")
    tiles = os.path.join(BUILD, "eucc_tiles")
    os.makedirs(tiles, exist_ok=True)
    python = shutil.which("python3") or "/usr/bin/python3"
    paint = os.path.join(HERE, "command_centre_paint.py")
    subprocess.run([python, paint, "tiles", tiles], check=True)
    w3d.write_house_colour(tex_dir)
    for name in ("eucc_pad.tga", "eucc_pad_e.tga", "eucc_emblem.tga"):
        shutil.copy(os.path.join(tiles, name), os.path.join(tex_dir, name))

    main, intact = build_shapes()
    objects = []
    for name, builder in (("BUILDING", main), ("INTACT", intact)):
        bmesh.ops.remove_doubles(builder.bm, verts=builder.bm.verts, dist=0.001)
        bmesh.ops.recalc_face_normals(builder.bm, faces=builder.bm.faces)
        obj = new_object(name, builder.bm)
        for surface in SURFACES:
            obj.data.materials.append(bpy.data.materials.get(surface) or surface_material(surface, tiles))
        smooth_by_angle(obj, 35)
        objects.append(obj)
    # One texture of the building's own: unwrap the building and its intact-only parts together.
    bpy.ops.object.select_all(action="DESELECT")
    for obj in objects:
        obj.select_set(True)
    bpy.context.view_layer.objects.active = objects[0]
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(angle_limit=math.radians(55), island_margin=0.004)
    bpy.ops.object.mode_set(mode="OBJECT")
    bakes = os.path.join(BUILD, "eucc_bakes")
    os.makedirs(bakes, exist_ok=True)
    for kind, file in (("DIFFUSE", "colour.png"), ("AO", "occlusion.png"), ("EMIT", "windows.png")):
        image = bpy.data.images.new(file, TEXTURE_SIZE, TEXTURE_SIZE)
        bake(objects, kind, image)
        save(image, os.path.join(bakes, file))
    subprocess.run([python, paint, "compose", bakes, tex_dir], check=True)
    baked = load_image(os.path.join(tex_dir, "eucc_building.tga"))
    for obj in objects:
        textured(obj, baked)

    ground = pad()
    textured(ground, load_image(os.path.join(tex_dir, "eucc_pad.tga")))
    marks = emblems()
    for obj in marks:
        textured(obj, load_image(os.path.join(tex_dir, "eucc_emblem.tga")))
    banners = house_colours()
    colour = bpy.data.materials.new("house colour")
    colour.use_nodes = True
    colour.node_tree.nodes["Principled BSDF"].inputs["Base Color"].default_value = (0.08, 0.2, 0.75, 1)
    for obj in banners:
        obj.data.materials.append(colour)
    return dict(building=objects[0], intact=objects[1], pad=ground, emblems=marks, banners=banners)


# --- writing the models ----------------------------------------------------------------------------

def export(parts, version, night):
    """version: "" intact, "_D" damaged, "_E" wrecked."""
    lower = version.lower()
    model = w3d.Model(NAME + version + ("N" if night and version else "_N" if night else ""))
    model.bone("EXITSTART", w3d.CHASSIS, EXITSTART)
    model.bone("EXITEND", w3d.CHASSIS, EXITEND)
    texture = f"eucc_building{lower}{'n' if night else ''}.tga"
    model.mesh("BUILDING", w3d.CHASSIS, **mesh_data(parts["building"]), texture=texture)
    if version != "_E":
        model.mesh("INTACT", w3d.CHASSIS, **mesh_data(parts["intact"]), texture=texture)
    model.mesh("PAD", w3d.CHASSIS, **mesh_data(parts["pad"]),
               texture="eucc_pad_e.tga" if version == "_E" else "eucc_pad.tga", shadow=False)
    for obj in parts["emblems"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture="eucc_emblem.tga", shadow=False)
    for obj in parts["banners"]:
        model.mesh(obj.name, w3d.CHASSIS, **mesh_data(obj), texture=w3d.HOUSE_COLOUR_TEXTURE, shadow=False)
    model.save(os.path.join(DATA, "Art", "W3D", model.name + ".w3d"))
    print(f"{model.name}: {len(model.meshes)} meshes, {sum(len(m[5]) for m in model.meshes)} triangles")


def export_all(parts):
    for version in ("", "_D", "_E"):
        for night in (False, True):
            export(parts, version, night)


def main():
    bpy.ops.wm.read_factory_settings(use_empty=True)
    os.makedirs(BUILD, exist_ok=True)
    parts = build()
    export_all(parts)
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(BUILD, NAME + ".blend"))


if __name__ == "__main__":
    main()

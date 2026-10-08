"""Blender helpers shared by the model scripts: making shapes, materials, and reading a mesh out for the
W3D writer (w3d.py). Imported by scripts run inside Blender.
"""
import math

import bmesh
import bpy


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


def load_image(path):
    image = bpy.data.images.load(path, check_existing=True)
    image.reload()
    return image


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

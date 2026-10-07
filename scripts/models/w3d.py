"""Writes a W3D model for Command & Conquer Generals (no Blender needed): a hierarchy of bones, one textured mesh per bone and
the HLOD that ties them together, the layout of the game's own vehicle models (see w3d_file.h).

    model = Model("EUBOXER")
    turret = model.bone("TURRET", parent=CHASSIS, at=(0, 0, 9))
    model.mesh("TURRET", turret, verts, normals, uvs, tris, "eu_boxer.tga")
    model.save("EUBOXER.w3d")

Mesh vertices are in the space of their bone. uvs are Blender's (v up), as W3D keeps them: the game turns
v over when it loads a mesh (meshmdlio.cpp).
"""
import math
import struct

MESH, VERTICES, NORMALS, HEADER3, TRIANGLES, SHADE_IDX = 0x0, 0x2, 0x3, 0x1F, 0x20, 0x22
MATERIAL_INFO, SHADERS, VERTEX_MATERIALS, VERTEX_MATERIAL, VM_NAME, VM_INFO = 0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D
TEXTURES, TEXTURE, TEXTURE_NAME = 0x30, 0x31, 0x32
MATERIAL_PASS, VM_IDS, SHADER_IDS, TEXTURE_STAGE, TEXTURE_IDS, STAGE_TEXCOORDS = 0x38, 0x39, 0x3A, 0x48, 0x49, 0x4A
HIERARCHY, HIERARCHY_HEADER, PIVOTS, PIVOT_FIXUPS = 0x100, 0x101, 0x102, 0x103
HLOD, HLOD_HEADER, HLOD_LOD_ARRAY, HLOD_SUB_OBJECT_ARRAY_HEADER, HLOD_SUB_OBJECT = 0x700, 0x701, 0x702, 0x703, 0x704

MESH_VERSION, HTREE_VERSION, HLOD_VERSION = 0x40002, 0x40001, 0x10000
CAST_SHADOW = 0x8000
ROOT, CHASSIS = 0, 1


def chunk(cid, body, has_children=False):
    return struct.pack("<II", cid, len(body) | (0x80000000 if has_children else 0)) + body


def name(text, length=16):
    data = text.encode("ascii")[:length - 1]
    return data + bytes(length - len(data))


def cstring(text):
    return text.encode("ascii") + b"\0"


# Opaque, textured and lit: depth compare less-equal, depth write, src one dst zero, texture modulated by
# lighting (the game's default solid shader).
OPAQUE_SHADER = bytes([3, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0])
# Additive, for muzzle flashes: no depth write, src one dst one.
ADDITIVE_SHADER = bytes([3, 0, 0, 1, 2, 1, 0, 1, 1, 0, 0, 2, 0, 0, 0, 2])
# White ambient, diffuse and specular, no emission, shininess 0.1, opacity 1.
DEFAULT_MATERIAL = struct.pack("<I4B4B4B4Bfff", 0, 255, 255, 255, 0, 255, 255, 255, 0, 255, 255, 255, 0, 0, 0, 0, 0, 0.1, 1.0, 0.0)


class Model:
    def __init__(self, model_name):
        self.name = model_name.upper()
        self.pivots = [("ROOTTRANSFORM", -1, (0, 0, 0)), ("CHASSIS", ROOT, (0, 0, 0))]
        self.meshes = []

    def bone(self, bone_name, parent=CHASSIS, at=(0, 0, 0)):
        """A bone at a place relative to its parent; its index."""
        self.pivots.append((bone_name.upper(), parent, tuple(at)))
        return len(self.pivots) - 1

    def mesh(self, mesh_name, bone, verts, normals, uvs, tris, texture, shadow=True, shader=OPAQUE_SHADER):
        self.meshes.append((mesh_name.upper(), bone, verts, normals, uvs, tris, texture, shadow, shader))

    def _hierarchy(self):
        header = struct.pack("<I", HTREE_VERSION) + name(self.name) + struct.pack("<I3f", len(self.pivots), 0, 0, 0)
        pivots = b"".join(name(n) + struct.pack("<i3f3f4f", parent, *at, 0, 0, 0, 0, 0, 0, 1) for n, parent, at in self.pivots)
        fixups = b"".join(struct.pack("<12f", 1, 0, 0, 0, 0, 1, 0, 0, 0, 0, 1, 0) for _ in self.pivots)
        return chunk(HIERARCHY, chunk(HIERARCHY_HEADER, header) + chunk(PIVOTS, pivots) + chunk(PIVOT_FIXUPS, fixups), True)

    def _mesh(self, mesh_name, verts, normals, uvs, tris, texture, shadow, shader):
        lo = [min(v[i] for v in verts) for i in range(3)]
        hi = [max(v[i] for v in verts) for i in range(3)]
        centre = [(a + b) / 2 for a, b in zip(lo, hi)]
        radius = max(math.dist(v, centre) for v in verts)
        header = struct.pack("<II", MESH_VERSION, CAST_SHADOW if shadow else 0) + name(mesh_name) + name(self.name)
        header += struct.pack("<IIIIiII", len(tris), len(verts), 1, 0, 0, 0, 0)
        header += struct.pack("<II", 1 | 2 | 4, 1) + struct.pack("<3f3f3ff", *lo, *hi, *centre, radius)
        body = chunk(HEADER3, header)
        body += chunk(VERTICES, b"".join(struct.pack("<3f", *v) for v in verts))
        body += chunk(NORMALS, b"".join(struct.pack("<3f", *n) for n in normals))
        faces = b""
        for a, b, c in tris:
            p, q, r = verts[a], verts[b], verts[c]
            u = [q[i] - p[i] for i in range(3)]
            w = [r[i] - p[i] for i in range(3)]
            n = [u[1] * w[2] - u[2] * w[1], u[2] * w[0] - u[0] * w[2], u[0] * w[1] - u[1] * w[0]]
            length = math.sqrt(sum(x * x for x in n)) or 1.0
            n = [x / length for x in n]
            faces += struct.pack("<3II3ff", a, b, c, 0, *n, sum(n[i] * p[i] for i in range(3)))
        body += chunk(TRIANGLES, faces)
        body += chunk(SHADE_IDX, b"".join(struct.pack("<I", i) for i in range(len(verts))))
        body += chunk(MATERIAL_INFO, struct.pack("<4I", 1, 1, 1, 1))
        body += chunk(VERTEX_MATERIALS, chunk(VERTEX_MATERIAL, chunk(VM_NAME, cstring(mesh_name.lower())) + chunk(VM_INFO, DEFAULT_MATERIAL), True), True)
        body += chunk(SHADERS, shader)
        body += chunk(TEXTURES, chunk(TEXTURE, chunk(TEXTURE_NAME, cstring(texture)), True), True)
        stage = chunk(TEXTURE_IDS, struct.pack("<I", 0)) + chunk(STAGE_TEXCOORDS, b"".join(struct.pack("<2f", u, v) for u, v in uvs))
        body += chunk(MATERIAL_PASS, chunk(VM_IDS, struct.pack("<I", 0)) + chunk(SHADER_IDS, struct.pack("<I", 0)) + chunk(TEXTURE_STAGE, stage, True), True)
        return chunk(MESH, body, True)

    def _hlod(self):
        header = struct.pack("<II", HLOD_VERSION, 1) + name(self.name) + name(self.name)
        subs = chunk(HLOD_SUB_OBJECT_ARRAY_HEADER, struct.pack("<If", len(self.meshes), 3.4028234663852886e38))
        for mesh_name, bone, *_ in self.meshes:
            subs += chunk(HLOD_SUB_OBJECT, struct.pack("<I", bone) + name(f"{self.name}.{mesh_name}", 32))
        return chunk(HLOD, chunk(HLOD_HEADER, header) + chunk(HLOD_LOD_ARRAY, subs, True), True)

    def save(self, path):
        data = self._hierarchy()
        for mesh_name, bone, verts, normals, uvs, tris, texture, shadow, shader in self.meshes:
            data += self._mesh(mesh_name, verts, normals, uvs, tris, texture, shadow, shader)
        data += self._hlod()
        with open(path, "wb") as f:
            f.write(data)

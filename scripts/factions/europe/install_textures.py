"""Draws the European faction's units in their own colours: a steel blue-grey in place of the USA's
desert tan on vehicles, a grey-green on the infantry's uniforms, and Europe's emblem (a gold chevron on
a dark blue square) where the USA's stars and eagles were; numbers and letters are painted over. The
textures are made from the player's own copy of the game, never shipped with this code, and go to
resources/macos/GameData/Art/TexturesHD (ignored by git), where the game finds them by name
(W3DFileSystem.cpp). Needs Pillow and NumPy.

    python3 scripts/factions/europe/install_textures.py [GAME FOLDER]

GAME FOLDER is searched for Textures.big and TexturesZH.big (default: ~/Games).
"""
import colorsys
import io
import os
import struct
import sys

import numpy as np
from PIL import Image, ImageDraw

from build_europe import DATA, TEXTURES, european_texture

# Recolouring: (hue in degrees, saturation, brightness). Each pixel keeps its brightness and takes the hue.
VEHICLE = (212, 0.22, 0.88)   # steel blue-grey
INFANTRY = (95, 0.20, 1.0)    # grey-green
# Textures recoloured otherwise than as vehicles, by name (lower case, without extension).
COLOURS = {
    "zhca_airanger": INFANTRY,
    "zhca_nithunter": INFANTRY,
    "zhca_aipthfindr": INFANTRY,
    "z_aipthfindr2": INFANTRY,
    "zhca_aihero2": INFANTRY,
    "z_infxtras": INFANTRY,
}
# Parts left in their own colours (skin), as boxes (left, top, right, bottom) in texture pixels.
KEEP = {
    "zhca_airanger": [(50, 16, 64, 32)],
    "zhca_nithunter": [],
    "zhca_aipthfindr": [(42, 25, 50, 33)],
    "zhca_aihero2": [(0, 0, 12, 34), (12, 0, 38, 17), (38, 0, 48, 34), (48, 0, 60, 13), (25, 47, 47, 64)],
}

# The USA's markings, by texture (lower case, without extension; a damaged version shares its intact
# version's layout). Each: (box, fill, emblem). The box (left, top, right, bottom) is filled from the
# camouflage around it: "h" blends each row from the box's left edge to its right edge, "v" each column
# from top to bottom, (dx, dy) copies the same-sized area that far away, and an (r, g, b) colour paints
# it plain. Emblem: the size in pixels of Europe's emblem painted in the middle (0 for none), where a
# national marking was; or (size, turn), the chevron turned clockwise by turn degrees (90, 180 or 270)
# where the model maps the texture on its side.
STAR_BAND = (64, 0)  # tank side skirts: the same armour band further along
MARKINGS = {
    ("avleopard", "avleopard_d"): [
        ((42, 120, 82, 158), STAR_BAND, 24),  # star on a shield, turret side
        ((48, 199, 74, 219), (64, 0), 0),     # chevron, hull skirt
    ],
    ("avpaladin", "avpaladin_d"): [
        ((42, 116, 82, 152), STAR_BAND, 24),  # star on a shield
    ],
    ("avtomahawk", "avtomahawk_d"): [
        ((42, 111, 82, 146), STAR_BAND, 24),  # star on a shield
        ((64, 199, 92, 219), (64, 0), 0),     # chevron, hull skirt
    ],
    ("avconstdoz", "avconstdoz_d"): [
        ((71, 104, 94, 130), "h", (16, 270)), # star on a shield, blade arm
        ((190, 198, 216, 228), "h", 0),       # chevron
    ],
    ("avsentry", "avsentry_d"): [
        ((5, 141, 32, 171), "h", 18),         # star on a shield
    ],
    ("avcomanche", "avcomanche_d"): [
        ((166, 177, 199, 206), (-100, 0), 20),  # eagle
    ],
    ("avchinook", "avchinook_d"): [
        ((19, 104, 41, 120), "h", 0),         # "74"
        ((124, 138, 161, 164), "h", 18),      # eagle
    ],
    ("avraptor", "avraptor_d"): [
        ((163, 48, 208, 64), "h", 0),         # "YA-11"
        ((58, 151, 79, 174), "h", 14),        # eagle
    ],
    ("avaurora", "avaurora_d"): [
        ((51, 40, 85, 67), "h", 18),          # eagle
        ((100, 148, 175, 163), "h", 0),       # "AF", upside down
        ((128, 209, 155, 223), "h", 0),       # "5541"
        ((142, 222, 167, 241), "v", 0),       # "VA"
    ],
    ("atflag01",): [
        ((0, 0, 64, 64), (28, 40, 88), 64),   # the Stars and Stripes: Europe's flag
    ],
}

EMBLEM_BLUE, EMBLEM_GOLD = (26, 38, 86), (222, 178, 52)


def big_entries(path):
    """The files of an EA .big archive: header BIGF, big endian count, then offset, size and name."""
    with open(path, "rb") as f:
        data = f.read()
    count, = struct.unpack(">I", data[8:12])
    pos = 16
    for _ in range(count):
        offset, size = struct.unpack(">II", data[pos:pos + 8])
        end = data.index(b"\0", pos + 8)
        yield data[pos + 8:end].decode("latin-1"), data[offset:offset + size]
        pos = end + 1


def find_archives(root):
    found = {}
    for folder, _, files in os.walk(root):
        for name in files:
            if name.lower() in ("textures.big", "textureszh.big"):
                found.setdefault(name.lower(), os.path.join(folder, name))
    # Zero Hour's textures replace the original game's.
    return [found[n] for n in ("textures.big", "textureszh.big") if n in found]


def markings(base):
    for names, covers in MARKINGS.items():
        if base in names:
            return covers
    return []


def cover(pixels, box, fill):
    """Paints over the box (float RGBA array, changed in place) with the camouflage around it."""
    left, top, right, bottom = box
    height, width = pixels.shape[:2]
    if fill == "h":
        a = pixels[top:bottom, max(left - 2, 0):left].mean(1)
        b = pixels[top:bottom, right:min(right + 2, width)].mean(1)
        t = ((np.arange(left, right) - left + 0.5) / (right - left))[None, :, None]
        pixels[top:bottom, left:right] = a[:, None] * (1 - t) + b[:, None] * t
    elif fill == "v":
        a = pixels[max(top - 2, 0):top, left:right].mean(0)
        b = pixels[bottom:min(bottom + 2, height), left:right].mean(0)
        t = ((np.arange(top, bottom) - top + 0.5) / (bottom - top))[:, None, None]
        pixels[top:bottom, left:right] = a[None] * (1 - t) + b[None] * t
    elif len(fill) == 2:
        dx, dy = fill
        pixels[top:bottom, left:right] = pixels[top + dy:bottom + dy, left + dx:right + dx].copy()
    else:
        pixels[top:bottom, left:right, :3] = np.array(fill, np.float32) / 255


def emblem(size, scale=8):
    """Europe's emblem: a gold chevron on a dark blue square, size x size pixels (RGBA float)."""
    s = size * scale
    image = Image.new("RGBA", (s, s), EMBLEM_BLUE + (255,))
    draw = ImageDraw.Draw(image)
    # A chevron pointing up: two bars meeting at the top, its arms reaching the lower corners.
    w = 0.24 * s
    apex, foot = 0.2 * s, 0.78 * s
    left, right, middle = 0.14 * s, 0.86 * s, 0.5 * s
    draw.polygon([(left, foot), (middle, apex), (right, foot), (right - w, foot),
                  (middle, apex + w * 1.25), (left + w, foot)], fill=EMBLEM_GOLD + (255,))
    border = max(scale // 2, int(0.05 * s))
    draw.rectangle([0, 0, s - 1, s - 1], outline=(14, 20, 46, 255), width=border)
    small = image.resize((size, size), Image.LANCZOS)
    return np.asarray(small).astype(np.float32) / 255


def paint_emblem(pixels, box, size):
    """Paints the emblem in the middle of the box, as dirty or burnt as the paint it replaces."""
    size, turn = size if isinstance(size, tuple) else (size, 0)
    left, top, right, bottom = box
    x, y = (left + right - size) // 2, (top + bottom - size) // 2
    under = pixels[y:y + size, x:x + size, :3]
    luminance = under @ np.array([0.299, 0.587, 0.114], np.float32)
    shade = np.clip(luminance / max(np.percentile(luminance, 90), 1e-3), 0.35, 1)[..., None]
    pixels[y:y + size, x:x + size, :3] = np.rot90(emblem(size), -(turn // 90))[..., :3] * shade


def recolor(pixels, colour, keep=()):
    """Keeps each pixel's brightness and gives its colour the hue; grey stays grey, kept boxes stay."""
    hue, chroma, brightness = colour
    original = pixels[..., :3].copy()
    rgb = pixels[..., :3]
    brightest, darkest = rgb.max(-1), rgb.min(-1)
    saturation = np.where(brightest > 0, (brightest - darkest) / np.maximum(brightest, 1e-6), 0)
    luminance = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    tint = np.array(colorsys.hls_to_rgb(hue / 360, 0.5, chroma), np.float32) * 2
    weight = np.clip(saturation * 3, 0, 1)[..., None]
    out = luminance[..., None] * ((1 - weight) + tint * weight) * brightness
    pixels[..., :3] = np.clip(out, 0, 1)
    for left, top, right, bottom in keep:
        pixels[top:bottom, left:right, :3] = original[top:bottom, left:right]


def europeanise(image, base):
    pixels = np.asarray(image.convert("RGBA")).astype(np.float32) / 255
    covers = markings(base)
    for box, fill, _ in covers:
        cover(pixels, box, fill)
    recolor(pixels, COLOURS.get(base, VEHICLE), KEEP.get(base, ()))
    for box, _, size in covers:
        if size:
            paint_emblem(pixels, box, size)
    return Image.fromarray((np.clip(pixels, 0, 1) * 255 + 0.5).astype(np.uint8))


def main():
    root = sys.argv[1] if len(sys.argv) > 1 else os.path.expanduser("~/Games")
    archives = find_archives(root)
    if not archives:
        sys.exit(f"No Textures.big found in {root}; pass the game folder.")
    wanted = {os.path.splitext(t)[0].lower(): t for names in TEXTURES.values() for t in names}
    sources = {}
    for archive in archives:
        for name, blob in big_entries(archive):
            base, ext = os.path.splitext(name.replace("\\", "/").rsplit("/", 1)[-1].lower())
            if base in wanted and ext in (".dds", ".tga"):
                sources[base] = (name, blob)
    missing = sorted(set(wanted) - set(sources))
    if missing:
        sys.exit(f"Not found in {', '.join(archives)}: {', '.join(missing)}")
    out_dir = os.path.join(DATA, "Art", "TexturesHD")
    os.makedirs(out_dir, exist_ok=True)
    for base, texture in sorted(wanted.items()):
        image = Image.open(io.BytesIO(sources[base][1]))
        europeanise(image, base).save(os.path.join(out_dir, european_texture(texture)))
    print(f"Wrote {len(wanted)} textures to {out_dir}")


if __name__ == "__main__":
    main()

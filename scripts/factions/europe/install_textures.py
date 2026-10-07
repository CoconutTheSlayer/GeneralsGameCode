"""Draws the European faction's vehicles in their own colours: a steel blue-grey in place of the USA's
desert tan. The textures are made from the player's own copy of the game, never shipped with this
code, and go to resources/macos/GameData/Art/TexturesHD (ignored by git), where the game finds them by
name (W3DFileSystem.cpp). Needs Pillow and NumPy.

    python3 scripts/factions/europe/install_textures.py [GAME FOLDER]

GAME FOLDER is searched for Textures.big and TexturesZH.big (default: ~/Games).
"""
import colorsys
import io
import os
import struct
import sys

import numpy as np
from PIL import Image

from build_europe import DATA, TEXTURES, european_texture

HUE, SATURATION, BRIGHTNESS = 212, 0.22, 0.88


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


def recolor(image):
    """Keeps each pixel's brightness and gives its colour the European hue; grey stays grey."""
    pixels = np.asarray(image.convert("RGBA")).astype(np.float32) / 255
    rgb = pixels[..., :3]
    brightest, darkest = rgb.max(-1), rgb.min(-1)
    saturation = np.where(brightest > 0, (brightest - darkest) / np.maximum(brightest, 1e-6), 0)
    luminance = rgb @ np.array([0.299, 0.587, 0.114], np.float32)
    tint = np.array(colorsys.hls_to_rgb(HUE / 360, 0.5, SATURATION), np.float32) * 2
    weight = np.clip(saturation * 3, 0, 1)[..., None]
    out = luminance[..., None] * ((1 - weight) + tint * weight) * BRIGHTNESS
    pixels[..., :3] = np.clip(out, 0, 1)
    return Image.fromarray((pixels * 255).astype(np.uint8))


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
        recolor(image).save(os.path.join(out_dir, european_texture(texture)))
    print(f"Wrote {len(wanted)} textures to {out_dir}")


if __name__ == "__main__":
    main()

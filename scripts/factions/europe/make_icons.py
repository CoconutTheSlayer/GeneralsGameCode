"""Draws the European faction's build buttons and unit portraits with an image model on OpenRouter,
each from the USA picture it replaces so that it keeps the game's look. Like install_textures.py it
works from the player's own copy of the game, and what it makes stays out of git:

    ~/.cache/generals/eu_icons/<object>.png               each drawing, kept so that a rerun only
                                                          draws what is missing
    resources/macos/GameData/Art/TexturesHD/eu_icons.tga  all of them in one texture
    resources/macos/GameData/Data/INI/Addon/Client/EuropeIcons.ini
                                                          points the faction's pictures at it (it loads
                                                          after Europe.ini)

The OpenRouter key is read from ~/.config/generals/openrouter_key. Needs Pillow.

    python3 scripts/factions/europe/make_icons.py [--only Euro_Leopard,...] [--redraw] [GAME FOLDER]
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image

from build_europe import BUILDINGS, DATA, UNITS, USA_PICTURES
from install_textures import big_entries

MODEL = "google/gemini-3-pro-image"
CACHE = os.path.expanduser("~/.cache/generals/eu_icons")
CELL = (200, 160)  # the shape of the game's buttons and portraits, 5:4
COLUMNS = 5
ATLAS = 1024

STYLE = (
    "This is a unit portrait from the real-time strategy game Command & Conquer Generals Zero Hour. "
    "Paint a new portrait in exactly the same style: the same slightly painterly photographic look, "
    "camera angle and bright daylight, with the same kind of light background as the reference (pale sky, "
    "haze or sunlit desert, never dark). Show the subject close up and large, cut off by the frame the "
    "same way as in the reference. "
    "The subject: {subject} "
    "It belongs to a European army: vehicles and equipment in a steel blue-grey camouflage, "
    "uniforms in grey-green European camouflage. "
    "No text, no letters, no logos, no flags of real countries, no border or frame. "
    "Landscape image, aspect ratio 5:4."
)

# What each portrait shows.
SUBJECTS = {
    "Euro_CommandCenter": "a modern European military headquarters building with a large radar dome and antennas.",
    "Euro_PowerPlant": "a compact high-tech fusion power plant with a glowing blue reactor core and cooling towers.",
    "Euro_Barracks": "a modern European army garrison building with a training yard.",
    "Euro_SupplyCenter": "a military logistics centre with cargo containers and a helicopter landing pad.",
    "Euro_WarFactory": "a large modern armoured vehicle factory hall with a big gate.",
    "Euro_Airfield": "a military air base with a control tower and hangars.",
    "Euro_StrategyCenter": "a joint command centre: a hardened bunker building with satellite dishes and screens.",
    "Euro_PatriotBattery": "a SAMP/T surface-to-air missile launcher with eight vertical missile canisters on a truck.",
    "Euro_FireBase": "a fortified concrete artillery bastion with a long-barrelled howitzer.",
    "Euro_ParticleCannonUplink": "a satellite uplink station aiming a beam of blue light at the sky.",
    "Euro_SupplyDropZone": "an airlift depot: a drop zone with a transport aircraft dropping supply crates on parachutes.",
    "Euro_Dozer": "a modern armoured military engineering vehicle with a dozer blade and a crane arm.",
    "Euro_Rifleman": "a modern European infantry soldier with a helmet, body armour and an assault rifle.",
    "Euro_Milan": "a European soldier aiming a MILAN anti-tank guided missile launcher on a tripod.",
    "Euro_Marksman": "a camouflaged European sniper with a long precision rifle and a ghillie hood.",
    "Euro_Commando": "a European special forces operator with night vision goggles and a suppressed carbine.",
    "Euro_Boxer": "a Boxer eight-wheeled armoured infantry fighting vehicle with a remote weapon station.",
    "Euro_Leopard": "a Leopard 2A7 main battle tank with its long 120 mm gun.",
    "Euro_Leclerc": "a Leclerc main battle tank with an angular turret and a long 120 mm gun.",
    "Euro_Puls": "a PULS multiple rocket launcher on an armoured truck, its rocket pods raised.",
    "Euro_Skyranger": "a Skyranger 30 air defence vehicle: a Boxer with a turret carrying a 30 mm cannon and a radar.",
    "Euro_Wiesel": "a small Wiesel tracked vehicle carrying an electronic warfare antenna mast and jammer.",
    "Euro_Ambulance": "an armoured military field ambulance with a red cross on white.",
    "Euro_ReconDrone": "a small tracked reconnaissance robot drone with a sensor mast and a light machine gun.",
    "Euro_Typhoon": "a Eurofighter Typhoon fighter jet with canard wings, in flight.",
    "Euro_Rafale": "a Dassault Rafale fighter jet with delta wings and canards, in flight.",
    "Euro_Tornado": "a Panavia Tornado swing-wing bomber jet, in flight, carrying bombs.",
    "Euro_Tiger": "a Eurocopter Tiger attack helicopter with a chin cannon and missiles, in flight.",
    "Euro_NH90": "an NH90 transport helicopter, in flight.",
}

PARENTS = {o[0]: o[1] for o in BUILDINGS + UNITS}


def find_atlases(root):
    """The game's interface textures, the localized ones replacing the others."""
    textures = {}
    for folder, _, files in os.walk(root):
        for name in files:
            if name.lower() in ("textures.big", "textureszh.big", "englishzh.big"):
                for entry, blob in big_entries(os.path.join(folder, name)):
                    base = entry.replace("\\", "/").rsplit("/", 1)[-1].lower()
                    if base.startswith("sauserinterface512_") and (base not in textures or "english" in entry.lower()):
                        textures[base] = blob
    return {name: Image.open(io.BytesIO(blob)).convert("RGBA") for name, blob in textures.items()}


def reference(atlases, name):
    texture, left, top, right, bottom = USA_PICTURES[name][1]
    return atlases[texture.lower()].crop((left, top, right, bottom)).resize((480, 384), Image.LANCZOS)


def draw(name, picture, key):
    buffer = io.BytesIO()
    picture.convert("RGB").save(buffer, "PNG")
    body = {
        "model": MODEL,
        "modalities": ["image", "text"],
        "messages": [{"role": "user", "content": [
            {"type": "text", "text": STYLE.format(subject=SUBJECTS[name])},
            {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}},
        ]}],
    }
    request = urllib.request.Request("https://openrouter.ai/api/v1/chat/completions", data=json.dumps(body).encode(),
                                     headers={"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    with urllib.request.urlopen(request, timeout=300) as response:
        answer = json.load(response)
    images = answer["choices"][0]["message"].get("images") or []
    if not images:
        raise RuntimeError(f"{name}: no image in the answer: {json.dumps(answer)[:300]}")
    data = images[0]["image_url"]["url"].split(",", 1)[1]
    return Image.open(io.BytesIO(base64.b64decode(data))).convert("RGB")


def fit(image):
    """Crops the drawing to the shape of a cell and scales it to the cell."""
    width, height = image.size
    want = CELL[0] / CELL[1]
    if width / height > want:
        cut = int(height * want)
        image = image.crop(((width - cut) // 2, 0, (width - cut) // 2 + cut, height))
    else:
        cut = int(width / want)
        image = image.crop((0, (height - cut) // 2, width, (height - cut) // 2 + cut))
    return image.resize(CELL, Image.LANCZOS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("game", nargs="?", default=os.path.expanduser("~/Games"))
    parser.add_argument("--only", help="comma separated objects to draw")
    parser.add_argument("--redraw", action="store_true", help="draw again even if a drawing is kept")
    args = parser.parse_args()
    with open(os.path.expanduser("~/.config/generals/openrouter_key")) as f:
        key = f.read().strip()
    os.makedirs(CACHE, exist_ok=True)

    names = list(SUBJECTS)
    wanted = args.only.split(",") if args.only else names
    todo = [n for n in wanted if args.redraw or not os.path.exists(os.path.join(CACHE, n + ".png"))]
    if todo:
        atlases = find_atlases(args.game)

        def one(name):
            try:
                draw(name, reference(atlases, name), key).save(os.path.join(CACHE, name + ".png"))
                print(f"drew {name}", flush=True)
            except Exception as e:  # keep going; a rerun tries again
                print(f"failed {name}: {e}", file=sys.stderr, flush=True)

        with ThreadPoolExecutor(6) as pool:
            list(pool.map(one, todo))

    # One texture with every drawing there is, and the pictures pointing at it.
    atlas = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 255))
    lines = ["; The European faction's own pictures (scripts/factions/europe/make_icons.py). Generated, do not edit.", ""]
    drawn = 0
    for i, name in enumerate(names):
        path = os.path.join(CACHE, name + ".png")
        if not os.path.exists(path):
            continue
        x, y = (i % COLUMNS) * CELL[0], (i // COLUMNS) * CELL[1]
        atlas.paste(fit(Image.open(path).convert("RGB")), (x, y))
        drawn += 1
        for image in (name, f"{name}_L"):
            lines += [
                f"MappedImage {image}",
                "  Texture = eu_icons.tga",
                f"  TextureWidth = {ATLAS}",
                f"  TextureHeight = {ATLAS}",
                f"  Coords = Left:{x} Top:{y} Right:{x + CELL[0]} Bottom:{y + CELL[1]}",
                "  Status = NONE",
                "End",
                "",
            ]
    atlas.save(os.path.join(DATA, "Art", "TexturesHD", "eu_icons.tga"))
    with open(os.path.join(DATA, "Data", "INI", "Addon", "Client", "EuropeIcons.ini"), "w", newline="\r\n") as f:
        f.write("\n".join(lines))
    print(f"{drawn} of {len(names)} pictures in eu_icons.tga")


if __name__ == "__main__":
    main()

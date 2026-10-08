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

    python3 scripts/factions/europe/make_icons.py [--only Euro_Leopard,...] [--redraw] [--from-shots] [GAME FOLDER]

When ~/.cache/generals/eu_shots/<object>.png holds a picture of the object as it is in the game (cropped from a
screenshot), the portrait is painted from it, so that it shows the faction's own models.
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

SHOTS = os.path.expanduser("~/.cache/generals/eu_shots")  # each object as it looks in the game (icon_shots.py)

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
# With a shot of the object in the game, the portrait shows that very object.
SHOT_STYLE = (
    "The first image is a unit portrait from the real-time strategy game Command & Conquer Generals Zero Hour. "
    "The second image shows the actual object as it looks in that game, from the game's high camera. "
    "Paint a new portrait of exactly the object in the second image: the same shape, parts, proportions, "
    "colours, markings and emblem (its look matters more than its name), in exactly the style of the first "
    "image: the same slightly painterly photographic look, a lower, closer camera like the first image's, and "
    "bright daylight with a light background (pale sky, haze or sunlit desert, never dark). Show it close up and "
    "large, cut off by the frame the same way as in the first image. Leave out any interface marks (health bars, "
    "selection boxes, text) of the second image. Where the object carries a star or eagle marking, paint a small gold "
    "chevron on a dark blue square instead, and leave out any numbers or lettering. "
    "It is {subject} "
    "No text, no letters, no logos, no flags of real countries, no border or frame. "
    "Landscape image, aspect ratio 5:4."
)

# What each portrait shows.
SUBJECTS = {
    "Euro_CommandCenter": "the European command centre: an octagonal control tower with a white radar dome, a hall with a curved ribbed roof, a lattice antenna mast and a quonset hangar with a gold chevron emblem.",
    "Euro_PowerPlant": "the European fusion plant: a plaster drum under a ribbed steel dome, ringed by glowing blue coolant channels, with fan cooling units, white tanks and a steam stack.",
    "Euro_Barracks": "the European garrison: an L-shaped flat-roofed quarters block with blue window bands, a tall watchtower with a glass cab, a steel rappelling tower and a firing range by a drill yard.",
    "Euro_SupplyCenter": "the European logistics centre: a huge yellow gantry crane spanning stacks of coloured shipping containers, three tall silos and a small dispatch office.",
    "Euro_WarFactory": "the European armour works: a large factory hall with a sawtooth roof and glazed faces, an armoured gate and two tall smoke stacks.",
    "Euro_Airfield": "the European air base: a long concrete runway, low angular concrete aircraft shelters, a slender control tower with a glass cab and a helipad.",
    "Euro_StrategyCenter": "the European joint command: a hardened octagonal stepped wedge with a band of dark operations windows, crowned by an antenna farm with lattice masts, dishes and a radome.",
    "Euro_PatriotBattery": "the SAMP/T air defence battery: a launcher of eight missile canisters on a turntable inside a horseshoe earth berm with sandbags, and a square radar panel on a mast.",
    "Euro_FireBase": "the European artillery bastion: a low hexagonal casemate of dark bare concrete with firing slits, half buried in earth mounds, with a howitzer turret on top.",
    "Euro_ParticleCannonUplink": "the orbital lance: a giant sky-facing dish on a tall tapered concrete tower, ringed by glowing capacitor pylons, beside an armoured control bunker.",
    "Euro_FundsOffice": "the EU funds office: a slim octagonal glass office tower with a navy pylon carrying a gold chevron, and a fountain plaza at its foot.",
    "Euro_Dozer": "a European armoured engineering vehicle: a tracked hull with a curved dozer blade and a telescopic excavator arm.",
    "Euro_Rifleman": "a modern European infantry soldier in a steel blue-grey and grey-green camouflage combat uniform, helmet and body armour, holding an assault rifle (a modern soldier, never a historical uniform).",
    "Euro_Milan": "a European soldier aiming a MILAN anti-tank guided missile launcher on a tripod.",
    "Euro_Marksman": "a camouflaged European sniper with a long precision rifle and a ghillie hood.",
    "Euro_Commando": "a European special forces operator with night vision goggles and a suppressed carbine.",
    "Euro_Boxer": "a Boxer eight-wheeled armoured infantry fighting vehicle with a remote weapon station.",
    "Euro_Leopard": "a Leopard 2A7 main battle tank with a wedge-armoured turret and a long 120 mm gun, in dark steel blue-grey camouflage.",
    "Euro_Leclerc": "a Leclerc main battle tank with a low boxy turret, an autoloader bustle and a long 120 mm gun, in pale splinter camouflage.",
    "Euro_Puls": "a PULS rocket artillery vehicle: a tracked carrier with an armoured cab and two raised rocket pods.",
    "Euro_Skyranger": "a Skyranger 30 air defence vehicle: an eight-wheeled Boxer with a turret carrying a raised 30 mm cannon, a missile pod and a radar panel.",
    "Euro_Wiesel": "a small Wiesel tracked vehicle with a tall telescopic electronic warfare mast carrying jammer panels and an emitter dish.",
    "Euro_Ambulance": "an armoured 4x4 field ambulance with a tall medical module, red crosses on white, in steel blue-grey camouflage.",
    "Euro_ReconDrone": "a small tracked unmanned ground robot with a telescopic sensor mast, a camera head and a radar panel.",
    "Euro_Typhoon": "a Eurofighter Typhoon fighter jet with canard wings, in flight.",
    "Euro_Rafale": "a Dassault Rafale fighter jet with delta wings and canards, in flight.",
    "Euro_Tornado": "a Panavia Tornado swing-wing bomber jet, in flight, carrying bombs.",
    "Euro_Tiger": "a Tiger attack helicopter with a stepped tandem cockpit, stub wings with missile boxes and a chin gun, in flight, rotors spinning.",
    "Euro_NH90": "an NH90 transport helicopter with a tall square cabin and sliding doors, in flight, rotors spinning.",
    # Research.
    "Euro_UpgradeGreenDeal": "the Green Deal subsidies: a fusion power plant crowned with solar panels, with a stream of gold coins.",
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


def as_url(picture):
    buffer = io.BytesIO()
    picture.convert("RGB").save(buffer, "PNG")
    return {"type": "image_url", "image_url": {"url": "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()}}


def draw(name, picture, key):
    shot = os.path.join(SHOTS, name + ".png")
    if os.path.exists(shot):
        content = [{"type": "text", "text": SHOT_STYLE.format(subject=SUBJECTS[name])}, as_url(picture),
                   as_url(Image.open(shot))]
    else:
        content = [{"type": "text", "text": STYLE.format(subject=SUBJECTS[name])}, as_url(picture)]
    body = {"model": MODEL, "modalities": ["image", "text"], "messages": [{"role": "user", "content": content}]}
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
    parser.add_argument("--from-shots", action="store_true",
                        help="draw again every object whose shot in the game is newer than its drawing")
    args = parser.parse_args()
    with open(os.path.expanduser("~/.config/generals/openrouter_key")) as f:
        key = f.read().strip()
    os.makedirs(CACHE, exist_ok=True)

    names = list(SUBJECTS)
    wanted = args.only.split(",") if args.only else names
    def stale(n):
        drawing, shot = os.path.join(CACHE, n + ".png"), os.path.join(SHOTS, n + ".png")
        return (not os.path.exists(drawing) or
                (args.from_shots and os.path.exists(shot) and os.path.getmtime(shot) > os.path.getmtime(drawing)))
    todo = [n for n in wanted if args.redraw or stale(n)]
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

"""Paints the European faction's other pictures with an image model on OpenRouter, each from the USA picture
it replaces (build_europe.py EURO_ART) so that it keeps the game's look: the faction's crest, score screen,
watermark, side icon, logo and general's medallions, the buttons of the general's powers and promotions, and
the USA upgrades the faction researches. Like make_icons.py it works from the player's own copy of the game,
and what it makes stays out of git:

    ~/.cache/generals/eu_art/<image>.png                    each painting, kept so that a rerun only paints
                                                            what is missing
    resources/macos/GameData/Art/TexturesHD/eu_art.tga      the buttons
    resources/macos/GameData/Art/TexturesHD/eu_faction.tga  the faction's pictures
    resources/macos/GameData/Data/INI/Addon/Client/EuropeArt.ini
                                                            redefines the images of EURO_ART (it loads after
                                                            Europe.ini, which points them at the USA's pictures)

The OpenRouter key is read from ~/.config/generals/openrouter_key. Needs Pillow.

    python3 scripts/factions/europe/make_art.py [--only Euro_PowerParadrop,...] [--redraw] [GAME FOLDER]
"""
import argparse
import base64
import io
import json
import os
import sys
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from PIL import Image, ImageDraw, ImageFilter

from build_europe import DATA, EURO_ART
from install_textures import big_entries
from make_icons import MODEL, SHOTS, as_url, fit

CACHE = os.path.expanduser("~/.cache/generals/eu_art")
ICONS = os.path.expanduser("~/.cache/generals/eu_icons")  # make_icons.py's portraits: the European look
CELL = (200, 160)
COLUMNS = 5
ATLAS = 1024

EUROPE = ("It belongs to a European army: aircraft in light grey, vehicles and equipment in steel blue-grey, "
          "uniforms in grey-green European camouflage; its only marking is a small gold chevron on a dark blue "
          "square. ")
NOTHING = ("No text, no letters, no numbers, no logos, no stars, no eagles, no flags of real countries, "
           "no border or frame. ")

BUTTON = (
    "The first image is a button picture of a general's power or an upgrade from the real-time strategy game "
    "Command & Conquer Generals Zero Hour. Paint a new button picture in exactly the same style: the same "
    "slightly painterly photographic look, colours, lighting, background, camera angle, composition and framing "
    "as the first image, but showing: {subject} {refs}The first image is a small, blurry thumbnail: paint "
    "yours sharp and detailed, never pixelated, and without the thumbnail's bevelled edge. " + EUROPE + NOTHING + "Landscape image, aspect ratio 5:4."
)
REFS = "The other images show the European {what} as they look in the game: paint them just like that. "

# The faction's emblem, in words.
EMBLEM = ("a heraldic shield in dark navy blue enamel with a large bold gold chevron (an upward pointing V), "
          "edged in polished steel, flanked by two swept wings of brushed steel blue-grey and off-white metal")

# Each picture: (kind, what to paint, European references: make_icons.py portraits or in-game shots).
ART = {
    # The faction.
    "Euro_LoadScreen": ("crest",
        "Paint the crest of a European army in exactly the style of this image: the same polished, shiny, "
        "bevelled metal and enamel rendering, the same lighting, size, placement and symmetrical layout, the "
        f"same kind of wide swept wings; but the crest is {EMBLEM}, with a slender upright sword behind the "
        "shield. Colours: steel blue-grey, off-white, gold and dark navy blue only (no red). " + NOTHING +
        "Plain flat pure magenta background (#FF00FF) everywhere around the crest. Square image.", []),
    "Euro_ScoreScreen": ("screen",
        "The first image is a screen of the real-time strategy game Command & Conquer Generals Zero Hour. Paint a "
        "new one in exactly the same style and layout: the same glowing blue technical frame with its thin lines, "
        "grid and rulers around the picture, the same dark blue surround. Inside the frame, a view from the "
        "game's high camera of a European army in battle: two or three Leopard main battle tanks in steel "
        "blue-grey camouflage advancing past a European base (buildings like those in the other images, off-white "
        "plaster, steel blue-grey roofs, a white radar dome, curved ribbed hall roofs), on sunlit desert ground with "
        "rocks and some trees, smoke trails and an explosion in the distance. " + NOTHING +
        "Landscape image, aspect ratio 4:3.", ["shot:Euro_CommandCenter", "shot:Euro_WarFactory", "icon:Euro_Leopard"]),
    "Euro_Watermark": ("watermark",
        "This is a faction watermark from the real-time strategy game Command & Conquer Generals Zero Hour. Paint "
        "a new one in exactly the same style: the same flat, faded, pale background colour, the same soft muted "
        f"flat colours and the same size and placement of the emblem; but the emblem is {EMBLEM}. " + NOTHING +
        "Landscape image, aspect ratio 5:3.", []),
    "Euro_SideIcon": ("icon",
        "This is a tiny faction icon from the real-time strategy game Command & Conquer Generals Zero Hour, shown "
        "at 24 by 22 pixels. Paint a new one in exactly the same style, filling the square the same way: a dark "
        "navy blue square with a thin steel edge, and on it a bold gold chevron pointing UP (shaped like the "
        "symbol ^, its point at the top) with small off-white wings at its sides; simple, bold, smooth shapes "
        "that read at a tiny size, painted smoothly (not pixel art). " + NOTHING + "Square image.", []),
    "Euro_MedallionRegular": ("medallion",
        "This is a general's medallion from the real-time strategy game Command & Conquer Generals Zero Hour. Paint "
        "a new one in exactly the same style: the same round metal medallion with its rim, the same colours, glow, "
        f"lighting and size; but in the centre, instead of the eagle emblem, {EMBLEM}. " + NOTHING +
        "Plain black background. Square image.", []),
    "Euro_MedallionHilite": ("medallion",
        "The first image is a general's medallion from the real-time strategy game Command & Conquer Generals Zero "
        "Hour, highlighted. The second image is the European medallion. Paint the European medallion of the second "
        "image, with exactly the same shape and the same emblem, which stays clearly visible and sharp (the dark navy "
        "shield with the gold upward chevron and the steel wings, exactly as in the second image); only the colours "
        "of the rim and the glow behind the emblem change to those of the first image. "
        + NOTHING + "Plain black background. Square image.", ["art:Euro_MedallionRegular"]),
    "Euro_MedallionSelect": ("medallion",
        "The first image is a general's medallion from the real-time strategy game Command & Conquer Generals Zero "
        "Hour, selected. The second image is the European medallion. Paint the European medallion of the second "
        "image, with exactly the same shape and the same emblem, which stays clearly visible and sharp (the dark navy "
        "shield with the gold upward chevron and the steel wings, exactly as in the second image); only the colours "
        "of the rim and the glow behind the emblem change to those of the first image. "
        + NOTHING + "Plain black background. Square image.", ["art:Euro_MedallionRegular"]),
    # The general's powers.
    "Euro_PowerSpectreGunship": ("button",
        "a large four-engine turboprop military transport aircraft (like an A400M) in light grey, converted to a "
        "gunship, banking over the land and firing a cannon from its side.", []),
    "Euro_PowerLeafletDrop": ("button",
        "a four-engine turboprop military transport aircraft (like an A400M) in light grey, flying low and "
        "releasing a long cloud of thousands of paper leaflets behind it.", []),
    "Euro_PowerA10ThunderboltMissileStrike": ("button",
        "a Eurofighter Typhoon fighter jet, firing air to ground missiles with bright smoke trails.", ["icon:Euro_Typhoon"]),
    "Euro_PowerA10ThunderboltMissileStrike2": ("button",
        "two Eurofighter Typhoon fighter jets in formation, firing air to ground missiles with smoke trails.",
        ["icon:Euro_Typhoon"]),
    "Euro_PowerA10ThunderboltMissileStrike3": ("button",
        "a formation of three Eurofighter Typhoon fighter jets flying low over the land, carrying missiles.",
        ["icon:Euro_Typhoon"]),
    "Euro_PowerParadrop": ("button",
        "a few paratroopers descending under round olive grey parachutes against a pale sky.", []),
    "Euro_PowerParadrop2": ("button",
        "more paratroopers descending under round olive grey parachutes against a pale sky.", []),
    "Euro_PowerParadrop3": ("button",
        "many paratroopers descending under round olive grey parachutes, with a four-engine transport aircraft.", []),
    "Euro_PowerSpyDrone": ("button",
        "a European reconnaissance drone (long slender wings, a V-tail and a rear propeller) in light grey, flying "
        "over the clouds.", []),
    "Euro_PowerEmergencyRepair": ("button",
        "a large steel wrench in front of a European main battle tank being repaired.", ["icon:Euro_Leopard"]),
    "Euro_PowerEmergencyRepair2": ("button",
        "bright welding sparks showering from the hull of a European main battle tank being repaired.",
        ["icon:Euro_Leopard"]),
    "Euro_PowerEmergencyRepair3": ("button",
        "a small flying repair drone with robotic arms and a welding torch repairing a European main battle tank.",
        ["icon:Euro_Leopard"]),
    "Euro_PowerDaisyCutter": ("button",
        "a huge thermobaric bomb falling on a parachute from a four-engine transport aircraft in light grey.", []),
    "Euro_PowerSpySatelliteScan": ("button",
        "a European navigation and observation satellite with wide blue solar panels, orbiting above the Earth.", []),
    "Euro_PowerFireParticleUplinkCannon": ("button",
        "a blinding beam of blue-white energy striking down from the sky beside the giant dish of the orbital "
        "lance tower, lighting up the ground.", ["icon:Euro_ParticleCannonUplink"]),
    "Euro_PowerCIAIntelligence": ("button",
        "a magnifying glass over a satellite map with a few dark blue markers on it.", []),
    "Euro_PowerMOAB": ("button",
        "a Panavia Tornado swing-wing jet releasing a huge heavy bomb.", ["icon:Euro_Tornado"]),
    # The upgrades.
    "Euro_UpgradeFlashBang": ("button",
        "a stun grenade, a steel blue-grey cylinder with a gold band and a pin, flying through the air.", []),
    "Euro_UpgradeCaptureBuilding": ("button",
        "a European soldier raising a plain dark blue banner with a gold chevron on the roof of a captured concrete "
        "building.", ["icon:Euro_Rifleman"]),
    "Euro_UpgradeSentryDroneGun": ("button",
        "the small tracked European reconnaissance robot drone, fitted with a machine gun turret, firing.",
        ["icon:Euro_ReconDrone"]),
    "Euro_UpgradeTOWMissile": ("button",
        "an anti-tank guided missile launching with a burst of smoke from the remote weapon station on the roof of "
        "a Boxer eight-wheeled armoured vehicle.", ["icon:Euro_Boxer"]),
    "Euro_UpgradeRocketPods": ("button",
        "close up of the stub wing of a Eurocopter Tiger attack helicopter carrying a rocket pod, firing rockets.",
        ["icon:Euro_Tiger"]),
    "Euro_UpgradeLaserMissiles": ("button",
        "laser guided missiles under the wing of a Eurofighter Typhoon, with a thin red laser beam.",
        ["icon:Euro_Typhoon"]),
    "Euro_UpgradeCountermeasures": ("button",
        "a Eurofighter Typhoon jet releasing a fan of bright burning decoy flares.", ["icon:Euro_Typhoon"]),
    "Euro_UpgradeBunkerBusters": ("button",
        "a bunker buster bomb exploding through the thick concrete roof of a bunker, fire and debris.", []),
}
REF_NAMES = {"Euro_Typhoon": "Typhoon jet", "Euro_Tornado": "Tornado jet", "Euro_Leopard": "Leopard tank",
             "Euro_ParticleCannonUplink": "orbital lance", "Euro_Rifleman": "soldier", "Euro_ReconDrone": "drone",
             "Euro_Boxer": "Boxer", "Euro_Tiger": "Tiger helicopter"}

# Where each picture goes: the buttons in eu_art.tga, the faction's pictures in eu_faction.tga at their own size.
FACTION_PLACES = {
    "Euro_ScoreScreen": (0, 0, 800, 600),
    "Euro_LoadScreen": (0, 604, 388, 388),
    "Euro_Watermark": (400, 604, 160, 96),
    "Euro_MedallionRegular": (400, 712, 40, 40),
    "Euro_MedallionHilite": (448, 712, 40, 40),
    "Euro_MedallionSelect": (496, 712, 40, 40),
    "Euro_Logo": (544, 712, 48, 48),
    "Euro_SideIcon": (600, 712, 24, 22),
}


def find_textures(root, wanted):
    """The game's textures named in wanted, the localized ones replacing the others."""
    found = {}
    for folder, _, files in os.walk(root):
        for name in files:
            if name.lower().endswith(".big"):
                for entry, blob in big_entries(os.path.join(folder, name)):
                    base = entry.replace("\\", "/").rsplit("/", 1)[-1].lower()
                    if base in wanted and (base not in found or "english" in entry.lower()):
                        found[base] = blob
    return {name: Image.open(io.BytesIO(blob)).convert("RGBA") for name, blob in found.items()}


def original(textures, name):
    texture, _, left, top, right, bottom = EURO_ART[name]
    return textures[texture.lower()].crop((left, top, right, bottom))


def reference(textures, name):
    """The USA picture, large enough for the model to see it, on black where it is see-through."""
    picture = original(textures, name)
    scale = max(1, 480 // max(picture.size))
    picture = picture.resize((picture.width * scale, picture.height * scale), Image.LANCZOS)
    flat = Image.new("RGBA", picture.size, (0, 0, 0, 255))
    flat.alpha_composite(picture)
    return flat


def european(ref):
    kind, name = ref.split(":", 1)
    folder = {"icon": ICONS, "shot": SHOTS, "art": CACHE}[kind]
    return Image.open(os.path.join(folder, name + ".png"))


def paint(name, textures, key):
    kind, text, refs = ART[name]
    if kind == "button":
        what = ", ".join(REF_NAMES[r.split(":", 1)[1]] for r in refs)
        text = BUTTON.format(subject=text, refs=REFS.format(what=what) if refs else "")
    content = [{"type": "text", "text": text}, as_url(reference(textures, name))]
    content += [as_url(european(r)) for r in refs]
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


def crop_to(image, width, height):
    """Crops the painting to the shape of width x height and scales it to that size."""
    w, h = image.size
    if w / h > width / height:
        cut = int(h * width / height)
        image = image.crop(((w - cut) // 2, 0, (w - cut) // 2 + cut, h))
    else:
        cut = int(w * height / width)
        image = image.crop((0, (h - cut) // 2, w, (h - cut) // 2 + cut))
    return image.resize((width, height), Image.LANCZOS)


def cut_out_magenta(image, size):
    """The crest on its magenta background: see-through where the background is, trimmed and centred like the
    USA's crest."""
    image = image.convert("RGB")
    alpha = Image.new("L", image.size, 255)
    pixels = image.load()
    a = alpha.load()
    for y in range(image.height):
        for x in range(image.width):
            pr, pg, pb = pixels[x, y]
            magenta = min(pr, pb) - pg  # how magenta it is: large on the background
            a[x, y] = 0 if magenta > 120 else 255 if magenta < 40 else int(255 * (120 - magenta) / 80)
            if magenta > 0 and a[x, y] < 255:  # take the magenta tint off the edges
                pixels[x, y] = (pr - magenta // 2 if pr > pg else pr, pg, pb - magenta // 2 if pb > pg else pb)
    image = image.convert("RGBA")
    image.putalpha(alpha.filter(ImageFilter.GaussianBlur(0.6)))
    box = alpha.point(lambda v: 255 if v > 32 else 0).getbbox() or (0, 0, image.width, image.height)
    image = image.crop(box)
    image.thumbnail((size - 8, size - 8), Image.LANCZOS)
    out = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    out.paste(image, ((size - image.width) // 2, (size - image.height) // 2), image)
    return out


def logo(size):
    """The faction's flat logo, drawn like the USA's: a black silhouette with a white outline, see-through around
    it. A shield carrying the chevron, cut out in white."""
    big = size * 8
    shield = Image.new("L", (big, big), 0)
    d = ImageDraw.Draw(shield)
    edge = [(0.16, 0.10), (0.84, 0.10), (0.84, 0.48), (0.80, 0.62), (0.72, 0.74), (0.61, 0.84), (0.50, 0.91),
            (0.39, 0.84), (0.28, 0.74), (0.20, 0.62), (0.16, 0.48)]
    d.polygon([(x * big, y * big) for x, y in edge], fill=255)
    chevron = Image.new("L", (big, big), 0)
    ImageDraw.Draw(chevron).polygon([(x * big, y * big) for x, y in (
        (0.50, 0.24), (0.74, 0.54), (0.74, 0.70), (0.50, 0.42), (0.26, 0.70), (0.26, 0.54))], fill=255)
    outline = shield.filter(ImageFilter.MaxFilter(17))
    image = Image.new("RGBA", (big, big), (0, 0, 0, 0))
    image.paste((255, 255, 255, 255), (0, 0), outline)
    image.paste((0, 0, 0, 255), (0, 0), shield)
    image.paste((255, 255, 255, 255), (0, 0), chevron)
    return image.resize((size, size), Image.LANCZOS)


def finish(name, painting, textures):
    """The painting as the game shows it."""
    kind = ART[name][0] if name in ART else None
    if name in FACTION_PLACES:
        _, _, width, height = FACTION_PLACES[name]
        if kind == "crest":
            return cut_out_magenta(painting, width)
        picture = crop_to(painting.convert("RGB"), width, height).convert("RGBA")
        if kind == "medallion":  # round like the USA's medallion
            picture.putalpha(original(textures, name).getchannel("A"))
        return picture
    return fit(painting.convert("RGB"))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("game", nargs="?", default=os.path.expanduser("~/Games"))
    parser.add_argument("--only", help="comma separated pictures to paint")
    parser.add_argument("--redraw", action="store_true", help="paint again even if a painting is kept")
    args = parser.parse_args()
    os.makedirs(CACHE, exist_ok=True)
    textures = find_textures(args.game, {EURO_ART[n][0].lower() for n in EURO_ART})

    wanted = args.only.split(",") if args.only else list(ART)
    todo = [n for n in wanted if args.redraw or not os.path.exists(os.path.join(CACHE, n + ".png"))]
    if todo:
        with open(os.path.expanduser("~/.config/generals/openrouter_key")) as f:
            key = f.read().strip()

        def one(name):
            try:
                paint(name, textures, key).save(os.path.join(CACHE, name + ".png"))
                print(f"painted {name}", flush=True)
            except Exception as e:  # keep going; a rerun tries again
                print(f"failed {name}: {e}", file=sys.stderr, flush=True)

        # The medallions that start from the European one wait for it.
        first = [n for n in todo if not any(r.startswith("art:") for r in ART[n][2])]
        with ThreadPoolExecutor(6) as pool:
            list(pool.map(one, first))
            list(pool.map(one, [n for n in todo if n not in first]))

    buttons = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 255))
    faction = Image.new("RGBA", (ATLAS, ATLAS), (0, 0, 0, 0))
    lines = ["; The European faction's other pictures (scripts/factions/europe/make_art.py). Generated, do not edit.", ""]
    cell = 0
    for name in EURO_ART:
        path = os.path.join(CACHE, name + ".png")
        if name == "Euro_Logo":
            picture = logo(FACTION_PLACES[name][2])
        elif os.path.exists(path):
            picture = finish(name, Image.open(path), textures)
        else:
            continue
        if name in FACTION_PLACES:
            texture, (x, y, w, h) = "eu_faction.tga", FACTION_PLACES[name]
            faction.paste(picture, (x, y))
        else:
            texture, x, y, (w, h) = "eu_art.tga", (cell % COLUMNS) * CELL[0], (cell // COLUMNS) * CELL[1], CELL
            buttons.paste(picture, (x, y))
            cell += 1
        lines += [f"MappedImage {name}", f"  Texture = {texture}", f"  TextureWidth = {ATLAS}",
                  f"  TextureHeight = {ATLAS}", f"  Coords = Left:{x} Top:{y} Right:{x + w} Bottom:{y + h}",
                  "  Status = NONE", "End", ""]
    folder = os.path.join(DATA, "Art", "TexturesHD")
    buttons.save(os.path.join(folder, "eu_art.tga"))
    faction.save(os.path.join(folder, "eu_faction.tga"))
    with open(os.path.join(DATA, "Data", "INI", "Addon", "Client", "EuropeArt.ini"), "w", newline="\r\n") as f:
        f.write("\n".join(lines))
    print(f"{(len(lines) - 2) // 8} of {len(EURO_ART)} pictures in eu_art.tga and eu_faction.tga")


if __name__ == "__main__":
    main()

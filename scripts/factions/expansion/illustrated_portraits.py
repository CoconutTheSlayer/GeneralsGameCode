"""Export complete illustrated roster portraits without falling back to model renders."""
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageOps

ROOT = Path(__file__).resolve().parents[3]


def export_portraits(faction, prefix, assets):
    sources = ROOT / 'scripts/models' / faction / 'portraits'
    missing = [key for key in assets if not (sources / (key.lower() + '.png')).is_file()]
    if missing:
        raise FileNotFoundError(f'Missing illustrated {faction} portraits: ' + ', '.join(missing))
    art = ROOT / 'resources/macos/GameData/Art'
    review = []
    for key, asset in assets.items():
        source = Image.open(sources / (key.lower() + '.png')).convert('RGB')
        icon = ImageOps.fit(source, (128, 128), method=Image.Resampling.LANCZOS)
        ImageDraw.Draw(icon).rectangle((0, 0, 127, 127), outline=(46, 57, 66), width=1)
        icon.save(art / 'Textures' / (prefix + '_' + key.lower() + '.tga'))
        portrait = ImageOps.fit(source, (256, 256), method=Image.Resampling.LANCZOS)
        hd_name = asset.get('portrait', asset['model'].lower() + '_icon.tga')
        portrait.save(art / 'TexturesHD' / hd_name)
        review.append((asset['display_name'], portrait))
    sheet = Image.new('RGB', (5 * 280, ((len(review) + 4) // 5) * 304), (18, 25, 32))
    draw = ImageDraw.Draw(sheet)
    try:
        font = ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf', 16)
    except OSError:
        font = ImageFont.load_default()
    for index, (label, icon) in enumerate(review):
        x, y = index % 5 * 280, index // 5 * 304
        sheet.paste(icon, (x + 12, y + 8))
        draw.text((x + 12, y + 272), label, fill=(220, 227, 231), font=font)
    output = ROOT / 'build/faction-assets' / faction
    output.mkdir(parents=True, exist_ok=True)
    sheet.save(output / 'icons-review.png')

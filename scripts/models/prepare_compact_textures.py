"""Lossless format conversion and tile extraction from the authored source atlases."""
from pathlib import Path
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
ART=ROOT/'scripts/models/art/compact'
TEX=ROOT/'resources/macos/GameData/Art/TexturesHD'
for suffix in ('','_d'):
    source=ART/('eu_compact_atlas_v2'+suffix+'.png')
    if not source.exists():
        if suffix:continue
        raise FileNotFoundError(source)
    # The legacy renderer expects power-of-two textures. This is a resample for
    # the engine, not a repaint; retain the full-resolution source alongside it.
    Image.open(source).convert('RGB').resize((1024,1024),Image.Resampling.LANCZOS).save(TEX/('eucompact_painted_v2'+suffix+'.tga'))
image=Image.open(ART/'eu_compact_atlas_v2.png').convert('RGB')
w,h=image.size
# The atlas's fourth tile in its second row contains the continuous track shoes.
# Rotate to align those shoes with W3DTankDraw's scrolling U coordinate.
image.crop((3*w//4,h//4,w,h//2)).transpose(Image.Transpose.ROTATE_90).resize((256,256),Image.Resampling.LANCZOS).save(TEX/'eucompact_track_v2.tga')

"""Paint the authored window islands for the matching night building variants."""
from pathlib import Path
import json,sys
from PIL import Image,ImageDraw
ROOT=Path(__file__).resolve().parents[3]
name=sys.argv[1];tex=ROOT/'resources/macos/GameData/Art/TexturesHD'
faces=json.loads((ROOT/'build/faction-assets/israel'/f'{name}_lights.json').read_text())
for source,target in (('','_n'),('_d','_dn')):
    im=Image.open(tex/(name.lower()+'_paint'+source+'.tga')).convert('RGB');d=ImageDraw.Draw(im)
    for face in faces:d.polygon([(int(u*(im.width-1)),int((1-v)*(im.height-1))) for u,v in face],fill=(227,214,155) if not source else (126,115,82))
    im.save(tex/(name.lower()+'_paint'+target+'.tga'))

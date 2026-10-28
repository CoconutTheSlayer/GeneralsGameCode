"""Prepare Russia's original generated atlas; preserve a procedural fallback.
Only format conversion and isolated track-tile extraction touch the source pixels.
Building artwork has its own preparation path and is not modified here.
"""
from pathlib import Path
import math,random
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=ROOT/'resources/macos/GameData/Art/TexturesHD'
random.seed(835)
def main():
 OUT.mkdir(parents=True,exist_ok=True)
 painted=HERE/'atlas_polished.png'
 if painted.exists():
  atlas=Image.open(painted).convert('RGB').resize((2048,2048),Image.Resampling.LANCZOS)
  atlas.save(OUT/'ruatlas.tga');atlas.save(OUT/'ruatlas_d.tga')
  # Damage is baked from a shader mask, preserving the same authored source UVs.
  atlas.crop((round(940/1254*2048),round(299/1254*2048),2048,round(602/1254*2048))).resize((512,512),Image.Resampling.LANCZOS).save(OUT/'rutrack.tga')
  Image.new('RGB',(8,8),'white').save(OUT/'ruhouse.tga')
  return
 palette=[(110,120,76),(91,101,67),(44,50,37),(96,106,68),(99,110,72),(75,80,58),(30,32,30),(44,44,37),(40,45,36),(44,72,79),(109,117,78),(93,96,67),(149,145,125),(170,149,67),(220,205,148),(117,123,80)]
 im=Image.new('RGB',(1024,1024));d=ImageDraw.Draw(im)
 for tile,col in enumerate(palette):
  x=(tile%4)*256;y=(tile//4)*256
  d.rectangle((x,y,x+255,y+255),fill=col)
  for k in range(2500):
   px=x+random.randrange(256);py=y+random.randrange(256);v=random.randint(-8,8)
   d.point((px,py),fill=tuple(max(0,min(255,c+v)) for c in col))
  if tile in (0,1,3,4,10,11,15):
   for a,b in ((0,36),(90,128),(210,247)):
    # Broad, low contrast olive camo, distinct from EU slate paint.
    pts=[(x+a-35,y-5),(x+b+20,y-5),(x+b-15,y+90),(x+b+50,y+180),(x+b+22,y+260),(x+a-6,y+260),(x+a+18,y+158),(x+a-36,y+83)]
    d.polygon(pts,fill=tuple(int(c*.82) for c in col))
  if tile in (1,3,4,15):
   d.rounded_rectangle((x+10,y+10,x+245,y+245),radius=10,outline=tuple(int(c*.57) for c in col),width=3)
   d.line((x+14,y+15,x+240,y+15),fill=tuple(min(255,int(c*1.26)) for c in col),width=2)
   for px,py in ((22,22),(234,22),(22,234),(234,234)):
    d.ellipse((x+px-3,y+py-3,x+px+3,y+py+3),fill=(144,149,114));d.point((x+px,y+py),fill=(39,45,31))
  if tile==2:
   for yy in range(8,248,12):d.rectangle((x+8,y+yy,x+248,y+yy+4),fill=(12,18,17));d.line((x+8,y+yy+5,x+248,y+yy+5),fill=(99,107,79),width=2)
  if tile==5:
   for r,c in ((108,(18,22,20)),(93,(117,120,82)),(76,(58,67,45)),(46,(126,131,91)),(16,(47,53,34))):d.ellipse((x+128-r,y+128-r,x+128+r,y+128+r),fill=c)
   for i in range(8):
    a=i*math.pi/4;px=x+128+math.cos(a)*61;py=y+128+math.sin(a)*61;d.ellipse((px-5,py-5,px+5,py+5),fill=(170,173,144))
  if tile in (6,7):
   for yy in range(0,256,24):d.line((x+4,y+yy+4,x+126,y+yy+19,x+250,y+yy+4),fill=(72,73,64),width=9)
  if tile==9:
   for yy in range(256):d.line((x,y+yy,x+255,y+yy),fill=(int(75-yy*.16),int(114-yy*.27),int(119-yy*.26)))
   d.line((x+20,y+30,x+228,y+207),fill=(125,148,144),width=7)
  if tile==12:
   for yy in range(0,256,64):d.line((x,y+yy,x+255,y+yy),fill=(113,114,102),width=2)
   d.line((x+128,y,x+128,y+256),fill=(127,127,109),width=2)
  if tile==13:
   patch=Image.new('RGB',(256,256),col);pd=ImageDraw.Draw(patch)
   for a in range(-256,512,70):pd.polygon([(a,0),(a+34,0),(a+290,256),(a+256,256)],fill=(47,47,34))
   im.paste(patch,(x,y));d=ImageDraw.Draw(im)
   # Clip geometry-overdraw back to tile bounds below, through mask isolated painter next revision.
  if tile==14:
   d.rectangle((x+10,y+10,x+245,y+245),fill=(77,80,64));d.rectangle((x+24,y+24,x+231,y+231),fill=(226,219,181))
   for yy in range(32,228,20):d.line((x+24,y+yy,x+231,y+yy),fill=(191,190,163),width=2)
 # The diagonal hazard strokes are clipped by redrawing neighbouring solid tile edges.
 im.save(OUT/'ruatlas.tga')
 damage=im.copy();dd=ImageDraw.Draw(damage)
 for tile in range(16):
  x=(tile%4)*256;y=(tile//4)*256
  for n in range(14):
   px=x+random.randrange(12,240);py=y+random.randrange(12,240);r=random.randrange(2,14)
   dd.ellipse((px-r,py-r,px+r,py+r),fill=(39+random.randrange(15),39+random.randrange(12),30+random.randrange(12)))
 damage.save(OUT/'ruatlas_d.tga')
 Image.new('RGB',(8,8),'white').save(OUT/'ruhouse.tga')
 track=Image.new('RGB',(128,64),(33,34,29));dt=ImageDraw.Draw(track)
 for x in range(0,128,16):dt.rectangle((x+1,3,x+12,60),fill=(91,92,73));dt.line((x+2,6,x+11,6),fill=(143,143,112),width=2);dt.rectangle((x+4,18,x+9,44),fill=(43,46,36))
 track.save(OUT/'rutrack.tga')
 im.save(HERE/'atlas_preview.png')
if __name__=='__main__':main()

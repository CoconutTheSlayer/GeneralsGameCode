"""Original industrial surface tiles for Russia's buildings, generated from code.

Dense multiscale diffuse grain, structural seams, worn edge highlights and runoff
are intentionally baked: the Generals renderer has no roughness/normal texture.
This atlas belongs only to building bakes; unit paint and geometry stay untouched.
"""
from pathlib import Path
import random,math
import numpy as np
from PIL import Image,ImageDraw
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2]
OUT=ROOT/'resources/macos/GameData/Art/TexturesHD'
SIZE=256
COLORS=[(95,108,70),(106,117,85),(42,48,36),(108,117,79),(110,117,88),(89,98,71),(34,36,32),(46,47,38),(52,60,43),(46,70,76),(104,113,79),(131,130,113),(153,153,134),(174,148,55),(220,208,168),(102,113,80)]

def surface(tile,damaged=False):
 rng=np.random.default_rng(9200+tile);r=random.Random(415+tile)
 base=np.array(COLORS[tile],dtype=float)
 # Dense grain survives minification because there is also broad dusty variation.
 fields=[]
 for n,amp in ((7,13),(22,7),(256,3)):
  f=rng.uniform(0,255,(n,n)).astype('uint8')
  fields.append((np.array(Image.fromarray(f).resize((SIZE,SIZE),Image.Resampling.BICUBIC),dtype=float)/255-.5)*amp*2)
 noise=sum(fields);arr=np.clip(base[None,None,:]+noise[:,:,None],0,255).astype('uint8');im=Image.fromarray(arr);d=ImageDraw.Draw(im)
 def seam(x0,y0,x1,y1,w=2):
  d.line((x0,y0,x1,y1),fill=tuple(int(v*.43) for v in base),width=w)
  d.line((x0+2,y0+2,x1+2,y1+2),fill=tuple(min(255,int(v*1.28)) for v in base),width=1)
 def edge():
  d.rectangle((2,2,253,253),outline=tuple(int(v*.52) for v in base),width=2)
  d.line((4,251,4,4,251,4),fill=tuple(min(255,int(v*1.32)) for v in base),width=2)
 if tile==0: # Standing-seam olive roofing, with real scale material variation.
  for x in range(0,256,21):
   seam(x,0,x,255,3)
   for y in (7,125,244):
    d.ellipse((x+3,y-1,x+5,y+1),fill=(164,168,139))
   for _ in range(7):
    y=r.randrange(256);length=r.randrange(2,15);d.line((x+1,y,x+1,y+length),fill=r.choice([(122,116,78),(139,137,102),(69,78,49)]),width=2)
  seam(0,126,255,126,2)
  # Folded sheet highlights, broad enough to read at the default game camera.
  for x in range(3,256,21):d.line((x,0,x,255),fill=(130,140,98),width=1)
 elif tile==12: # Precast concrete with deep panel joints and subtle cracks/runoff.
  for y in (0,64,128,192,255):seam(0,y,255,y,2)
  for x in (0,128,255):seam(x,0,x,255,2)
  for x in (10,119,138,246):
   for y in (10,55,74,119,138,183,202,246):
    d.ellipse((x-2,y-2,x+2,y+2),fill=(104,107,92));d.point((x-1,y-1),fill=(188,190,163))
  for _ in range(17):
   x=r.randrange(9,245);y=r.choice((3,67,131,195));length=r.randrange(4,28)
   d.line((x,y,x+1,y+length),fill=(121,122,105),width=r.choice((1,2,3)))
  for x,y in ((18,22),(141,77),(97,208)):
   d.line([(x,y),(x+7,y+9),(x+5,y+15),(x+13,y+26)],fill=(103,105,92),width=1)
 elif tile==11: # Concrete ground pads: larger slabs, chipped expansion joints.
  for x in (0,64,128,192,255):seam(x,0,x,255,2)
  for y in (0,64,128,192,255):seam(0,y,255,y,2)
  for _ in range(25):
   x=r.randrange(256);y=r.choice((2,65,129,193,253));d.line((x,y,x+r.randrange(2,12),y+1),fill=(173,171,146),width=2)
  d.line([(21,101),(26,110),(21,123),(30,134),(31,147)],fill=(92,94,81),width=1)
 elif tile in (1,3,4,10,15):
  edge()
  # Reinforced steel plates and shutter ribs, not vehicle camouflage.
  for y in range(20,240,28 if tile==15 else 72):seam(8,y,247,y,3 if tile==15 else 2)
  for x,y in ((15,15),(240,15),(15,240),(240,240)):
   d.ellipse((x-3,y-3,x+3,y+3),fill=(55,64,43));d.line((x-2,y-2,x+1,y-2),fill=(180,184,143),width=2)
  for _ in range(30):
   x=r.choice((r.randrange(4,251),r.choice((5,251))));y=r.choice((r.randrange(4,251),r.choice((5,251))))
   d.line((x,y,x+r.randrange(2,8),y+r.choice((-1,0,1))),fill=r.choice([(161,163,132),(68,78,50),(127,112,74)]),width=1)
 elif tile==2:
  edge()
  for y in range(10,247,12):d.rectangle((8,y,247,y+5),fill=(13,20,17));d.line((8,y+6,247,y+6),fill=(110,119,89),width=2)
 elif tile==9:
  # Framed glazing: slightly dirty gradient and a subdued reflection.
  for y in range(256):
   c=(int(79-y*.18),int(113-y*.26),int(121-y*.28));d.line((0,y,255,y),fill=c)
  edge();d.line((15,30,233,203),fill=(125,148,143),width=4)
  for x in (64,128,192):d.line((x,5,x,250),fill=(44,55,48),width=3)
 elif tile==13:
  for x in range(-256,512,64):d.polygon([(x,0),(x+30,0),(x+286,256),(x+256,256)],fill=(38,42,31))
  for _ in range(250):
   x=r.randrange(256);y=r.randrange(256);d.line((x,y,x+r.randrange(1,6),y),fill=(130,124,92),width=1)
 elif tile==14:
  edge();d.rectangle((17,17,238,238),fill=(218,208,170))
  for y in range(27,235,23):d.line((20,y,235,y),fill=(172,172,144),width=2)
 # Grounding, seam dirt, chipped highlights. No random bright dots on every panel.
 if tile not in (9,13,14):
  for _ in range(28):
   x=r.randrange(256);y=r.choice((r.randrange(2,20),r.randrange(235,255)))
   d.line((x,y,x+r.randrange(1,10),y),fill=tuple(max(0,int(c*.7)) for c in base),width=1)
 if damaged:
  for _ in range(8):
   x=r.randrange(256);y=r.randrange(256);rr=r.randrange(5,22)
   d.ellipse((x-rr,y-rr,x+rr,y+rr),fill=(68,68,51));d.ellipse((x-rr*.5,y-rr*.5,x+rr*.5,y+rr*.5),fill=(42,45,34))
   d.line((x,y,x+r.randrange(-12,12),min(255,y+rr*2)),fill=(78,77,57),width=3)
 return im

def main():
 for damaged in (False,True):
  atlas=Image.new('RGB',(1024,1024))
  for tile in range(16):atlas.paste(surface(tile,damaged),((tile%4)*256,(tile//4)*256))
  name='rubuild_atlas'+('_d' if damaged else '')
  atlas.save(OUT/(name+'.tga'));atlas.save(HERE/(name+'.png'))
if __name__=='__main__':main()

"""Original procedural surfaces for the Israel art set; no imported game art."""
from pathlib import Path
import math, random
from PIL import Image, ImageDraw, ImageFilter
ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'resources/macos/GameData/Art/TexturesHD'
def main():
    OUT.mkdir(parents=True,exist_ok=True)
    for family,source in [('infantry','infantry_atlas_v2.png'),('aircraft','aviation_atlas_v2.png')]:
        path=Path(__file__).parent/source
        if path.exists():
            Image.open(path).convert('RGB').resize((2048,2048),Image.Resampling.LANCZOS).save(OUT/f'il_{family}_atlas.tga')
    painted=Path(__file__).parent/'atlas_polished.png'
    if not painted.exists():painted=Path(__file__).parent/'atlas_painted.png'
    if painted.exists():
        OUT.mkdir(parents=True,exist_ok=True)
        atlas=Image.open(painted).convert('RGB').resize((2048,2048),Image.Resampling.LANCZOS)
        atlas.save(OUT/'il_atlas.tga')
        Image.open(painted.with_name(painted.stem+'_d.png')).convert('RGB').resize((2048,2048),Image.Resampling.LANCZOS).save(OUT/'il_atlas_d.tga')
        atlas.crop((1536,512,2048,1024)).save(OUT/'il_track.tga')
        Image.new('RGB',(8,8),'white').save(OUT/'ilhouse.tga')
        Image.new('RGB',(16,16),(175,141,109)).save(OUT/'il_skin.tga')
        Image.new('RGB',(8,8),(219,213,186)).save(OUT/'il_mark.tga')
        return
    rng=random.Random(417)
    colours=[(153,146,123),(134,129,111),(53,58,55),(137,133,113),(157,150,126),(121,119,102),(37,39,37),(66,65,57),(63,65,61),(42,66,70),(126,122,104),(115,111,85),(154,150,135),(191,161,58),(229,216,169),(89,96,91)]
    atlas=Image.new('RGB',(1024,1024))
    for i,col in enumerate(colours):
        tile=Image.new('RGB',(256,256));p=tile.load()
        for y in range(256):
            for x in range(256):
                n=rng.gauss(0,1.5)+3*math.sin(x/87)+2*math.cos(y/59)
                p[x,y]=tuple(max(0,min(255,int(c+n))) for c in col)
        d=ImageDraw.Draw(tile)
        if i in (1,3,4,15):
            d.rounded_rectangle((6,6,249,249),radius=7,outline=(66,68,59),width=4)
            d.line((9,245,9,9,246,9),fill=(183,173,145),width=2)
            for x,y in ((18,18),(237,18),(18,237),(237,237)):
                d.ellipse((x-3,y-3,x+3,y+3),fill=(63,65,59));d.point((x-1,y-1),fill=(214,204,166))
        if i==2:
            for y in range(10,250,17):
                d.rectangle((9,y,247,y+8),fill=(24,31,31));d.line((9,y+9,247,y+9),fill=(114,114,97),width=3)
        if i==4:
            d.ellipse((32,32,224,224),outline=(73,75,65),width=7);d.rounded_rectangle((86,112,170,138),radius=7,fill=(54,60,58))
        if i==5:
            for r,c in ((119,(39,42,39)),(95,(137,134,113)),(75,(93,96,83)),(40,(161,150,123))): d.ellipse((128-r,128-r,128+r,128+r),fill=c)
            for k in range(8):
                a=k*math.tau/8;x=128+60*math.cos(a);y=128+60*math.sin(a);d.ellipse((x-7,y-7,x+7,y+7),fill=(44,50,46))
        if i in (6,7):
            for y in range(-20,280,23):
                d.line((0,y,100,y+12,156,y+12,256,y),fill=(92,92,79),width=9)
                d.line((0,y+9,100,y+21,156,y+21,256,y+9),fill=(21,24,23),width=5)
        if i==9:
            d.polygon([(0,12),(256,91),(256,126),(0,47)],fill=(70,96,99));d.line((0,254,255,254),fill=(20,35,37),width=10)
        if i==11:
            for y in range(12,256,44):d.line((0,y,256,y+9),fill=(81,83,64),width=2)
        if i==13:
            for x in range(-256,512,78):d.polygon([(x,0),(x+34,0),(x-222,256),(x-256,256)],fill=(38,42,38))
        if i==14:
            d.ellipse((20,20,236,236),fill=(251,237,188));d.ellipse((48,48,208,208),fill=(250,247,224))
        atlas.paste(tile,((i%4)*256,(i//4)*256))
    OUT.mkdir(parents=True,exist_ok=True)
    atlas.save(OUT/'il_atlas.tga');atlas.save(Path(__file__).parent/'atlas.png')
    damage=atlas.convert('RGB');d=ImageDraw.Draw(damage,'RGBA')
    for _ in range(1100):
        x=rng.randrange(1024);y=rng.randrange(1024);r=rng.randrange(2,18)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(25,24,19,rng.randrange(12,100)))
    damage.save(OUT/'il_atlas_d.tga')
    atlas.crop((3*256,256,4*256,2*256)).save(OUT/'il_track.tga')
    Image.new('RGB',(8,8),'white').save(OUT/'ilhouse.tga')
if __name__=='__main__':main()

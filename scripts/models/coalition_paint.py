"""Shared Generals-style paint for the coalition additions, using the established EU painter."""
import os
import sys
from PIL import Image, ImageDraw
from engineer_paint import load_faces, paint_body, grille, seam, emblem, rivets, UP, GROUPS


AIRCRAFT=False
REFINED=False
MODEL=''


def details(draw, p, rng):
    if REFINED:
        compact_details(draw,p)
        return
    for part, (x0,x1,y0,y1,z0,z1) in p.layout.parts.items():
        if part not in ('hull','cab','turret','body','pod'):
            continue
        w,h=x1-x0,z1-z0
        if w < 2 or h < 1:
            continue
        if not AIRCRAFT:
            grille(draw,p.rect(part,'top',(x0+w*.1,y0*.4,z1),(x0+w*.29,y1*.4,z1)),slats=6)
        for t in (.25,.65):
            seam(draw,p.P(part,'side',(x0+w*t,0,z0+h*.15)),p.P(part,'side',(x0+w*t,0,z1-h*.12)))
        emblem(draw,p.P(part,'side',(x0+w*.48,0,z0+h*.6)),max(2,p.layout.s(part)*min(w,h)*.13))


def compact_details(draw,p):
    # Equipment is actual geometry. Avoid the old generic grilles and huge edge
    # lines painted across launcher tubes, crew hatches and the entire roof.
    if MODEL in ('euvaluk','eupatria'):
        for x in (-11.7,-6.2,4):
            seam(draw,p.P('hull','side',(x,0,5.4)),p.P('hull','side',(x,0,7.9)))
        emblem(draw,p.P('hull','top',(10.2,0,0)),.65*p.layout.s('hull'))
        for y in (-3.9,3.9):
            rivets(draw,[p.P('hull','top',(x,y,0)) for x in (-11,-5,1,8)],.38)
    else:
        emblem(draw,p.P('hull','top',(7.1,1.7,0)),.65*p.layout.s('hull'))
        for x in (-8,-3,2):
            rivets(draw,[p.P('hull','side',(x,0,4.6))],.38)
    # Small identification stencil, kept in the armour paint rather than a neon label.
    text={'euvaluk':'V-06','eupatria':'P-26','euwiest':'W-12','eumv4':'MV-04'}[MODEL]
    x,y=p.P('hull','side',(-7 if MODEL!='euwiest' else -6,0,5.8 if MODEL in ('euvaluk','eupatria') else 3.9))
    draw.text((x,y),text,fill=(192,204,208),stroke_width=0)


def detail_atlas(out):
    """Fittings shared by the compact models, with broad value changes for game zoom."""
    im=Image.new('RGB',(256,256),(45,53,62));d=ImageDraw.Draw(im)
    colours=[(80,94,108),(31,36,41),(25,62,80),(205,208,183),(140,35,28),(192,130,43),
             (192,201,195),(79,94,99),(33,41,46),(50,55,53),(121,133,126),(17,23,28)]
    for i,c in enumerate(colours):
        x=(i%4)*64;y=(i//4)*64
        for yy in range(64):
            k=.73+.3*(1-yy/63)
            d.line((x,y+yy,x+63,y+yy),fill=tuple(int(v*k) for v in c))
        d.rectangle((x+3,y+3,x+60,y+60),outline=tuple(min(255,int(v*1.25)) for v in c),width=2)
    # Glass: dark border and a restrained cool reflection, never luminous.
    d.polygon([(132,5),(185,5),(148,55),(132,55)],fill=(63,109,130))
    d.line((132,6,183,6),fill=(140,174,184),width=2)
    # Headlamp face.
    d.rectangle((199,9,247,53),fill=(212,216,193),outline=(95,105,108),width=3)
    for x in range(203,247,7):d.line((x,12,x,50),fill=(169,184,183))
    # Medical patch: white cloth backing with the game's green medical cross.
    x,y=128,64;d.rectangle((x+4,y+4,x+59,y+59),fill=(209,214,205))
    d.rectangle((x+26,y+12,x+38,y+52),fill=(26,100,77));d.rectangle((x+12,y+26,x+52,y+38),fill=(26,100,77))
    # Dark vent recess with broad louvres.
    for yy in range(134,188,7):
        d.line((6,yy,57,yy),fill=(91,105,115),width=2)
        d.line((6,yy+2,57,yy+2),fill=(15,23,29),width=3)
    for x in range(66,127,16):
        d.polygon([(x,134),(min(x+8,123),134),(max(68,x-16),187),(max(68,x-24),187)],fill=(169,137,56))
    # Tube paint and steel retain rubbed upper edges without becoming chrome.
    for x0,y0 in ((0,0),(128,128)):
        d.line((x0+5,y0+7,x0+58,y0+7),fill=(151,164,165),width=2)
        d.line((x0+5,y0+55,x0+58,y0+55),fill=(33,43,48),width=3)
    im.save(os.path.join(out,'eucompact_detail.tga'))


def main():
    global AIRCRAFT,REFINED,MODEL
    layout,faces=load_faces(sys.argv[1]);out=sys.argv[2]
    name=os.path.basename(sys.argv[1]).removesuffix('_layout.json').lower()
    MODEL=name
    REFINED=name in ('euvaluk','eupatria','euwiest','eumv4')
    AIRCRAFT=name in ('eupuma','eua400m','eugripen','euapache')
    ao=Image.open(sys.argv[3]) if len(sys.argv)>3 and os.path.exists(sys.argv[3]) else None
    plain={(part,group):((151,163,170) if part=='running' else (94,109,121))
           for part in ('running','arms','turret') if part in layout.parts for group in GROUPS} if REFINED else None
    for damaged in (False,True):
        paint_body(layout,faces,details=details,damaged=damaged,occlusion=ao,mud_below=2.0 if REFINED else 3.2,
                   plain=plain,camo_scale=.8 if REFINED else 1,seed=43).save(
            os.path.join(out,name+('_d' if damaged else '')+'.tga'))
    if REFINED:detail_atlas(out)
    for key,col in [('metal',(42,51,61)),('glass',(23,56,72))]:
        im=Image.new('RGB',(32,32),col);d=ImageDraw.Draw(im)
        d.line([(0,1),(31,1)],fill=(127,157,172),width=2)
        im.save(os.path.join(out,f'eucoal_{key}.tga'))
    im=Image.new('RGB',(64,64),(210,216,217));d=ImageDraw.Draw(im)
    d.rectangle((25,10,39,54),fill=(15,96,80));d.rectangle((10,25,54,39),fill=(15,96,80))
    im.save(os.path.join(out,'eucoal_medical.tga'))


if __name__=='__main__':main()

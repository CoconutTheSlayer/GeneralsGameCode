"""Original F-16I and F-15I silhouettes; +X forward, with fixed game launch bones."""
import math


def create(api, f15=False):
    v=api.Asset('ILF15' if f15 else 'ILF16','F15I' if f15 else 'F16I',
        'F-15I Raam' if f15 else 'F-16I Sufa','Strike aircraft' if f15 else 'Air-superiority fighter',
        'AmericaJetRaptor','aircraft')
    v._israel_geometry_polished=True;v.art_revision='aircraft-v2';v.aircraft_camo=True
    def loft(name,stations,tile=0,y=0):
        o=api.loft(v,name,stations,tile,N=20)
        for vert in o.data.vertices:vert.co.y+=y
        for p in o.data.polygons:p.use_smooth=True
        return o
    def wing(name,points,z,thickness=.18,tile=0):
        return api.wing(v,name,points,z,thickness,tile)
    def nozzle(x,y,z,r):
        from polish_geometry import _ring
        _ring(v,'NOZZLE',(x,y,z),r,r*.78,1.4,7,axis='X',segments=20)
        v.cyl('EXHAUSTDARK',(x+.32,y,z),r*.77,.10,8,'X',segments=20)
        for i in range(16):
            a=i*math.tau/16
            v.beam('PETAL',(x-.68,y+r*.99*math.cos(a),z+r*.99*math.sin(a)),
                (x+.53,y+r*.90*math.cos(a),z+r*.90*math.sin(a)),.035,8)
    def missile(x,y,z,bomb=False):
        r=.53 if bomb else .24;length=9 if bomb else 7.5
        loft('STORE',[(x-length/2,z,r*.5,r*.5),(x-length/2+1,z,r,r),
             (x+length/2-1.3,z,r,r),(x+length/2,z,.035,.035)],10,y)
        for s in (-1,1):
            wing('STOREFIN',[(x-length/2+.3,y),(x-length/2+.2,y+s*r*3),
                            (x-length/2+2,y+s*r*1.8),(x-length/2+2.1,y)],z,.10,12)
        v.profile('STOREVERT',[(x-length/2+.3,z),(x-length/2+.3,z+r*3),
                  (x-length/2+2,z+r*1.6),(x-length/2+2.1,z)],y-.06,y+.06,12)
    def team(corners):v.house('HOUSE',corners)

    if f15:
        # Broad shoulder and two separate nacelles, square intake ramps, twin tails.
        loft('FUSELAGE',[(-25,3.9,2.0,.7),(-19,4.1,3.7,1.5),(-10,4.0,4.4,1.9),
             (1,4.0,4.0,1.8),(7,4.2,2.0,1.65),(15,4.2,1.3,1.2),(21,3.95,.65,.65),(25,3.8,.04,.04)])
        for s in (-1,1):
            loft('NACELLE',[(-25,3.2,1.65,1.55),(-21,3.35,1.95,1.65),(-7,3.4,1.95,1.6),(3,3.6,1.7,1.2)],0,s*2.5)
            nozzle(-25.7,s*2.5,3.25,1.68)
            wing('MAINWING',[(5,s*3),(-3.5,s*17.8),(-10,s*17.4),(-13,s*3.5)],4.0,.34)
            wing('TAILPLANE',[(-16,s*2),(-20,s*10.4),(-26,s*11),(-25,s*2)],4.2,.24)
            # Thick ramp housing and visibly recessed mouth, rather than a dark box.
            v.profile('INTAKERAMP',[(-9,2.5),(7.1,2.5),(6.1,6.0),(-6,5.65)],s*3.7-1.27,s*3.7+1.27,0)
            v.box('INTAKEMOUTH',(7.12,s*3.7-1.02,2.85),(7.19,s*3.7+1.02,5.55),8,bevel=.08)
            for yy in (-1.25,1.25):v.beam('INTAKELIP',(7.2,s*3.7+yy,2.6),(6.23,s*3.7+yy,5.97),.12,0)
            fin=v.profile('TAILFIN',[(-25,4.5),(-22.6,12.2),(-19.5,12.0),(-14.5,4.8)],s*3.9-.17,s*3.9+.17,0)
            for vert in fin.data.vertices:vert.co.y+=s*max(0,vert.co.z-4.6)*.09
            v.beam('RUDDER',(-23.9,s*4.0,5.1),(-22.0,s*4.53,11.4),.035,8)
            v.beam('AILERON',(-10.1,s*16.8,4.37),(-11.6,s*6.0,4.37),.025,8)
            # Conformal packs curve tightly against the engine sides.
            loft('CONFORMAL',[(-17,3.7,.3,.4),(-12,3.8,.75,.8),(0,3.9,.8,.9),(4,3.9,.2,.3)],0,s*4.4)
            team([(-6,s*10,4.37),(-3.8,s*9,4.37),(-4.8,s*12.6,4.37),(-7,s*13.3,4.37)])
        L=24;span=17.8
    else:
        # Slender single-engine fuselage, long root extensions and one central fin.
        loft('FUSELAGE',[(-21,3.5,1.5,1.45),(-17,3.7,1.95,1.85),(-8,3.8,2.35,1.9),
            (2,3.85,2.05,1.8),(10,3.9,1.65,1.45),(16,3.65,1.10,.92),(20.5,3.5,.28,.28),(22,3.48,.025,.025)])
        nozzle(-22,0,3.6,1.59)
        for s in (-1,1):
            wing('ROOTEXTENSION',[(10,s*1.4),(1,s*4.2),(-11,s*4.1),(-13,s*1.9)],4.05,.32)
            wing('MAINWING',[(2,s*2.2),(-5.8,s*13.4),(-10.4,s*13.4),(-11.4,s*2.1)],3.95,.25)
            wing('TAILPLANE',[(-14,s*1.4),(-18,s*8.3),(-23,s*7.4),(-21,s*1.25)],3.6,.22)
            loft('CONFORMAL',[(-13,4.7,.3,.35),(-9,5.0,.82,.64),(-1,5.0,.85,.73),(5,4.8,.35,.4)],0,s*2.22)
            v.profile('VENTRALFIN',[(-18,2.2),(-20,.55),(-16,.7),(-13,2.1)],s*1.30-.09,s*1.30+.09,12)
            v.beam('AILERON',(-9.6,s*12.9,4.22),(-10.6,s*5.8,4.22),.025,8)
            missile(-7,s*13.65,3.98)
            team([(-5.5,s*7.7,4.23),(-3.8,s*6.7,4.23),(-6.2,s*10.5,4.23),(-7.9,s*11.0,4.23)])
        loft('SPINE',[(-15,5.1,.35,.3),(-10,5.6,.55,.6),(-1,5.7,.55,.55),(4,5.6,.25,.3)],0)
        v.profile('TAILFIN',[(-20,4.4),(-17.2,11.8),(-14.6,11.7),(-10,4.6)],-.18,.18,0)
        v.beam('RUDDER',(-18.9,.19,5.0),(-16.8,.19,11.3),.026,8)
        # Single characteristic chin intake with a real lip and inset darkness.
        loft('CHININTAKE',[(-5,2.3,1.25,.65),(0,2.10,1.7,.95),(5.8,2.2,1.53,.90),(6.6,2.3,1.22,.73)],12)
        v.cyl('INTAKEBLACK',(6.67,0,2.28),.92,.06,8,'X',segments=16)
        intake=v.parts[-1][2]
        for vert in intake.data.vertices:vert.co.y*=1.30
        L=20;span=13.4

    # Twin-seat canopy with a single separating bow, clear glass and a sand frame.
    loft('CANOPY',[(2.2,5.7,.4,.15),(4,6.05,1.07,.95),(7.6,6.30,1.25,1.30),
        (11.5,6.1,1.03,1.10),(14.3,5.12,.13,.10)],9)
    for s in (-1,1):
        v.beam('CANOPYRAIL',(3,s*.81,5.6),(11.8,s*.88,5.5),.075,0)
        v.beam('CANOPYBOW',(8.1,s*1.19,6.30),(8.1,s*.38,7.54),.06,0)
    v.beam('CANOPYTOP',(8.1,-.39,7.54),(8.1,.39,7.54),.055,0)
    v.profile('DORSALANTENNA',[(-6,6.0),(-7,7.0),(-4,6.9),(-3,6.0)],-.07,.07,8)
    # Radome in restrained neutral paint; no tank armour texture on the nose.
    loft('RADOME',[(16,3.7,1.04,.87),(20,3.6,.45,.4),(24.4 if f15 else 21.9,3.55,.03,.03)],12)
    for s in (-1,1):
        top=4.365 if f15 else 4.225
        end=16 if f15 else 12
        v.beam('WINGSEAM',(-5.5,s*4.5,top),(-7.4,s*end,top),.028,8)
        v.patch('ACCESSPANEL',[(-6.3,s*5.3,top+.008),(-4.3,s*5.3,top+.008),
            (-4.3,s*7.0,top+.008),(-6.3,s*7.0,top+.008)],1)
        for y in (7,10.5):
            v.box('PYLON',(-4,s*y-.18,1.55),(-1,s*y+.18,3.97),12,bevel=.09)
            missile(0,s*y,1.45,bomb=f15)
        # Centerline tank halves sit below the fuselage and preserve the gun muzzle.
    loft('CENTRETANK',[(-13,.8,.1,.1),(-10,.8,.65,.6),(-2,.8,.72,.63),(3,.9,.1,.1)],12)
    for name,at in [('ENGINE01',(-25.8,2.5,3.25) if f15 else (-22.2,0,3.6)),('ENGINE02',(-25.8,-2.5,3.25) if f15 else (-22.2,0,3.6)),
        ('WINGTIP01',(-8,span,4.0)),('WINGTIP02',(-8,-span,4.0)),
        ('WEAPONA01',(-1,7,1.45)),('WEAPONA02',(-1,-7,1.45)),('MUZZLE01',(13,1,3.5))]:v.bone(name,at)
    return v

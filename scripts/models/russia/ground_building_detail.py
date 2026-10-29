"""Bounded original Russia ground/architecture detail pass.

No bones, animation, hide-mesh contracts or silhouette extents are changed.
Additions stay inside the prior assembled bounds, including rotated launchers.
The source atlas and finished infantry/aircraft are deliberately independent.
"""
import math
import bpy,bmesh
from mathutils import Matrix,Vector,Quaternion

STEEL,PLATE,VENT,LOCKER,HATCH,HUB,RUBBER,TREAD,IRON,GLASS,TUBE,TARP,CONCRETE,CAUTION,LAMP,DOOR=range(16)
GROUND=('RUBMPT','RUTIGR','RUT90','RUBMP3','RUTUNG','RUMSTA','RUTOS','RUENG','RUSUP')


def box(v,n,lo,hi,tile=STEEL,bone='CHASSIS',bevel=0):
    return v.box('D_'+n,lo,hi,tile,bone,bevel)


def rod(v,n,a,b,r=.12,tile=IRON,bone='CHASSIS',segments=8):
    a,b=Vector(a),Vector(b);d=b-a
    bm=bmesh.new()
    bmesh.ops.create_cone(bm,cap_ends=True,segments=segments,radius1=r,radius2=r,depth=d.length,
        matrix=Matrix.Translation((a+b)/2)@d.to_track_quat('Z','Y').to_matrix().to_4x4())
    return v.mesh('D_'+n,bm,tile,bone)


def ring(v,n,at,r,inner,depth=.16,tile=IRON,bone='CHASSIS',axis='Z',segments=10):
    bm=bmesh.new();rotation={'Z':Matrix.Identity(4),'X':Matrix.Rotation(math.pi/2,4,'Y'),'Y':Matrix.Rotation(math.pi/2,4,'X')}[axis]
    m=Matrix.Translation(at)@rotation;rs=[]
    for z,rad in ((-depth/2,r),(depth/2,r),(depth/2,inner),(-depth/2,inner)):
        rs.append([bm.verts.new(m@Vector((math.cos(i*math.tau/segments)*rad,math.sin(i*math.tau/segments)*rad,z))) for i in range(segments)])
    for a,b in zip(rs,rs[1:]+rs[:1]):
        for i in range(segments):j=(i+1)%segments;bm.faces.new((a[i],a[j],b[j],b[i]))
    return v.mesh('D_'+n,bm,tile,bone)


def sensor(v,p,bone='CHASSIS',size=1):
    x,y,z=p
    box(v,'SCOPE',(x-.7*size,y-.65*size,z),(x+.8*size,y+.65*size,z+1.1*size),IRON,bone,.08)
    box(v,'SCOPEHOOD',(x-.8*size,y-.73*size,z+.9*size),(x+1*size,y+.73*size,z+1.2*size),STEEL,bone,.06)
    box(v,'SCOPEGLASS',(x+.81*size,y-.49*size,z+.24*size),(x+.83*size,y+.49*size,z+.8*size),GLASS,bone)


def hatch(v,x,y,z,r=1,bone='CHASSIS'):
    ring(v,'HATCHRIM',(x,y,z),r+.15,r-.1,.18,STEEL,bone)
    box(v,'HATCHHANDLE',(x-.43,y-.13,z+.1),(x+.43,y+.13,z+.32),IRON,bone)
    for dy in (-.55,.55):
        box(v,'PERISCOPE',(x+.75,y+dy-.18,z+.05),(x+1.14,y+dy+.18,z+.42),IRON,bone)
        box(v,'PERILENS',(x+1.145,y+dy-.14,z+.16),(x+1.16,y+dy+.14,z+.35),GLASS,bone)


def stow(v,p,size=(3,1.3,.9),bone='CHASSIS'):
    x,y,z=p;L,W,H=size
    box(v,'STOWAGE',(x,y,z),(x+L,y+W,z+H),TARP,bone,.15)
    for t in (.25,.75):
        v.beam('D_STRAP',(x+L*t,y-.025,z+H),(x+L*t,y+W+.025,z+H),.075,IRON,bone)
        v.beam('D_STRAP',(x+L*t,y-.025,z+.12),(x+L*t,y-.025,z+H),.075,IRON,bone)


def mg(v,x,y,z,bone='TURRET'):
    rod(v,'MGPINTLE',(x,y,z),(x,y,z+.7),.18,IRON,bone)
    box(v,'MGRECEIVER',(x-.6,y-.25,z+.5),(x+.65,y+.25,z+1),IRON,bone)
    rod(v,'MGBARREL',(x+.5,y,z+.8),(x+3.1,y,z+.8),.12,IRON,bone)
    box(v,'MGAMMO',(x-.3,y+.3,z+.35),(x+.6,y+.95,z+.85),TARP,bone)


def running(v,L,Y,roof,n=6):
    # Open wheels remain visible beneath segmented fender fittings.
    for s in (-1,1):
        for i in range(n):
            x=-L+2+(2*L-4)*i/(n-1)
            ring(v,'HUBRIM',(x,s*(Y+1.15),2),.74,.51,.1,STEEL,axis='Y',segments=8)
        for x in (-L+2,-L+6,L-5):
            box(v,'FENDERBRACE',(x,s*(Y+.5)-.45,4.5),(x+.25,s*(Y+.5)+.45,4.9),IRON)
        rod(v,'TOOL',(-L+1,s*(Y-.25),roof+.1),(-L+6,s*(Y-.25),roof+.1),.105,IRON)
        box(v,'TOOLHEAD',(-L+5.6,s*(Y-.25)-.37,roof+.05),(-L+6.5,s*(Y-.25)+.37,roof+.2),IRON)
        ring(v,'TOWLOOP',(L-1,s*Y*.66,3.6),.43,.22,.18,IRON,axis='X',segments=8)
    for i in range(4):
        box(v,'SPARETRACK',(L-7+i*.8,-2.8,roof+.03),(L-6.35+i*.8,-1.3,roof+.25),IRON)
    hatch(v,L-6,1.8,roof+.14,.8)
    for i in range(5):
        box(v,'ENGINELOUVRE',(-L+1.1+i*.64,-2.6,roof+.18),(-L+1.3+i*.64,2.6,roof+.39),IRON)


def bmpt(v):
    running(v,13,5.8,6.5)
    for side in (-1,1):
        for x in (-8,-4,0,4,8):
            box(v,'ERABOLT',(x,side*6.88-.04,4.7),(x+.25,side*6.88+.04,4.94),IRON)
        stow(v,(-9,side*3.8-.6,6.7),(3.6,1.1,.85))
        for x in (-2.3,-.8,.7):
            rod(v,'SMOKE',(x,side*2.8,1.6),(x+.75,side*3.2,1.9),.19,IRON,'TURRET')
        rod(v,'GUNBRACE',(2,side*.72,.18),(4,side*.72,.18),.30,STEEL,'BARREL')
        for x in (-2,.0,1.7):box(v,'TURRETSEAM',(x,side*2.81-.02,.7),(x+.08,side*2.81+.02,2.05),IRON,'TURRET')
    hatch(v,-8,-1.8,6.7,.8)
    rod(v,'CABLE',(-10,-5.6,6.6),(-4,-5.6,6.6),.13,IRON)

def t90(v):
    running(v,13,5.8,6.5)
    for s in (-1,1):
        for i in range(6):
            x=-9+i*2.8
            box(v,'SKIRTARMOUR',(x,s*7.02-.12,3.6),(x+2.5,s*7.02+.12,4.88),STEEL,bevel=.08)
            for xx in (x+.35,x+2.1):v.cyl('D_SKIRTBOLT',(xx,s*7.155,4.58),.11,.035,IRON,'Y',segments=6)
        for i in range(3):
            x=.05+i*1.35
            v.prism('D_WEDGEERA',[(x,.88),(x+1.14,.88),(x+1.04,2.08),(x+.12,2.3)],s*3.95-.22,s*3.95+.22,PLATE,'TURRET')
        sensor(v,(3.2,s*2.35,1.45),'TURRET',.6)
    hatch(v,-1,-1.68,3.25,1.15,'TURRET');mg(v,-2,1.6,3.4)
    stow(v,(-5.2,-1.7,2.6),(2.3,2.1,.6),'TURRET')


def bmp(v):
    running(v,12.5,5.6,6.3)
    for s in (-1,1):
        for i in range(5):
            x=-10.8+i*4.05
            box(v,'SKIRTPANEL',(x,s*6.74-.12,3.52),(x+3.75,s*6.74+.12,4.3),PLATE)
        for x in (-7.8,-3.8):hatch(v,x,s*2.25,6.65,.9)
        box(v,'REARGRILLE',(-12.57,s*3.8-.65,4.05),(-12.51,s*3.8+.65,5.38),VENT)
        rod(v,'REARHANDLE',(-12.65,s*3,4.2),(-12.65,s*3,5.4),.10)
    sensor(v,(1.1,-1.9,1.58),'TURRET',.72)
    box(v,'REARRAMP',(-12.59,-1.8,2.7),(-12.55,1.8,5.7),PLATE)
    for z in (3,4,5):rod(v,'RAMPBAR',(-12.67,-1.6,z),(-12.67,1.6,z),.09)


def msta(v):
    running(v,15,6,6.8,7)
    for s in (-1,1):
        y=s*5.73
        box(v,'GUNHOUSEACCESS',(.25,y-.06,1.5),(3.45,y+.06,5.2),PLATE,'TURRET',.12)
        for z in (1.65,5.05):v.beam('D_ACCESSFRAME',(.4,y+s*.09,z),(3.3,y+s*.09,z),.07,IRON,'TURRET')
        rod(v,'ACCESSHANDLE',(2.8,y+s*.17,2.65),(2.8,y+s*.17,3.45),.10,bone='TURRET')
        box(v,'VENT',(-5.1,y-.04,5.95),(-1.1,y+.04,7.08),VENT,'TURRET')
        for x in (-5,-2):
            rod(v,'HANDRAIL',(x,y,5.8),(x,y,7.45),.105,bone='TURRET')
        stow(v,(-5.2,s*3.6-.8,7.83),(2.6,1.4,.52),'TURRET')
        for z in (2,3.5,5):rod(v,'REARLADDER',(-6.64,s*2.8-.65,z),(-6.64,s*2.8+.65,z),.1,bone='TURRET')
    hatch(v,-1.5,1.8,7.88,1.25,'TURRET');sensor(v,(2,0,6.8),'TURRET',.65)
    # Broad armoured gun-house seams and an ammunition-feed back plate.
    box(v,'AMMOFEED',(-7.07,-1.5,1.25),(-6.96,1.5,4.85),IRON,'TURRET')
    for x in (-4,-1,2):v.beam('D_ROOFJOINT',(x,-4.7,7.86),(x,4.7,7.86),.055,IRON,'TURRET')


def tos(v):
    running(v,13,6,6.1)
    for s in (-1,1):
        y=s*5.07
        box(v,'LAUNCHERENDCAP',(-6.47,y-.14,-.78),(-5.85,y+.14,3.84),PLATE,'BARREL')
        box(v,'LAUNCHERENDCAP',(5.75,y-.14,-.78),(6.32,y+.14,3.84),PLATE,'BARREL')
        for x in (-3.75,-.8,2.2):
            box(v,'LAUNCHERSTIFFENER',(x,y-.17,-.82),(x+.26,y+.17,3.85),IRON,'BARREL')
        for z in (-.65,3.78):rod(v,'LAUNCHERRAIL',(-6.15,y,z),(6.2,y,z),.13,STEEL,'BARREL')
        box(v,'ACCESSPANEL',(-2.85,y+s*.19-.02,.3),(1.5,y+s*.19+.02,2.55),PLATE,'BARREL')
        rod(v,'PANELHANDLE',(-.9,y+s*.28,1),(.2,y+s*.28,1),.10,bone='BARREL')
        rod(v,'TRUNNION',(0,s*2.95,1.45),(0,s*4.4,1.45),.54,PLATE,'TURRET')
        ring(v,'TRUNNIONRIM',(0,s*4.5,1.45),.66,.43,.17,IRON,'TURRET','Y')
        rod(v,'ELEVATIONRAM',(-2.3,s*3.7,.45),(2.3,s*3.7,2),.27,IRON,'TURRET')
    sensor(v,(1.8,-1.9,2),'TURRET',.72)


def tung(v):
    running(v,13.5,5.8,6.8)
    hatch(v,-1,-1.33,3.48,1,'TURRET');sensor(v,(2.25,-1.5,2.75),'TURRET',.7)
    for s in (-1,1):
        stow(v,(-3.5,s*3.1-.6,2.9),(2.3,1.2,.6),'TURRET')
        for x in (-2.4,2):
            box(v,'MISSILECLAMP',(x,s*5.3-.95,1.45),(x+.23,s*5.3+.95,3.1),IRON,'BARREL')
        for z in (-.18,.26):ring(v,'GUNMOUTH',(8.56,s*4.7,z),.27,.13,.12,IRON,'BARREL','X',8)
    for y in (-2.75,0,2.75):rod(v,'RADARBRACE',(-.51,y,1.1),(-.51,y,3.2),.08,IRON,'RADAR')
    for z in (1.2,2.2,3.2):rod(v,'RADARBAR',(-.52,-2.8,z),(-.52,2.8,z),.065,IRON,'RADAR')
    ring(v,'RADARBEZEL',(4.63,0,2.8),1.34,1.06,.16,IRON,'TURRET','X',12)


def cab_frames(v,truck):
    # Actual recessed rim, hub and lug geometry survives game-scale minification.
    for bone,parent,at,q in v.bones:
        if not bone.startswith('TIRE'):continue
        s=1 if at[1]>0 else -1
        ring(v,'WHEELRIM',(0,s*1.025,0),1.18,.94,.12,IRON,bone,'Y',12)
        v.cyl('D_AXLEHUB',(0,s*1.11,0),.34,.24,IRON,'Y',bone,segments=6)
        for i in range(6):
            angle=i*math.tau/6
            v.cyl('D_WHEELLUG',(.66*math.cos(angle),s*1.115,.66*math.sin(angle)),.115,.12,IRON,'Y',bone,segments=6)
    if truck:
        front=[(13.87,-3.95,6.08),(13.87,3.95,6.08),(13.49,3.95,8.87),(13.49,-3.95,8.87)]
    else:front=[(5.23,-3.72,6.76),(5.23,3.72,6.76),(3.32,3.72,8.79),(3.32,-3.72,8.79)]
    for p,q in zip(front,front[1:]+front[:1]):rod(v,'WINDFRAME',p,q,.11,STEEL)
    for s in (-1,1):
        if truck:pts=[(6.85,s*4.48,6.66),(11.85,s*4.48,6.66),(11.15,s*4.48,9.45),(6.85,s*4.48,9.45)]
        else:pts=[(-6.1,s*4.21,6.22),(-3.4,s*4.21,6.22),(-3.4,s*4.21,8.38),(-6.1,s*4.21,8.38)]
        for p,q in zip(pts,pts[1:]+pts[:1]):rod(v,'SIDEFRAME',p,q,.09,STEEL)
        if not truck:
            for p,q in zip(pts,pts[1:]+pts[:1]):
                p=(p[0]+4,p[1],p[2]);q=(q[0]+4,q[1],q[2]);rod(v,'SIDEFRAME',p,q,.09,STEEL)
        for xx in ((7.0,10.2) if truck else (-5.8,-1.8)):
            box(v,'DOORARMOUR',(xx,s*4.33-.1,4.35),(xx+2.65,s*4.33+.1,5.65),STEEL,bevel=.09)
        x=13.9 if truck else 9.4
        rod(v,'BULLGUARD',(x,-4.3,4.1),(x,4.3,4.1),.15,IRON)
        for y in (-3.5,3.5):rod(v,'LIGHTGUARD',(x,y,3.85),(x,y,5.55),.12,IRON)
        for z in (3.5,4.1):box(v,'CABSTEP',((6.5 if truck else -3.5),s*5.05-.65,z),((10.5 if truck else .8),s*5.05+.65,z+.12),IRON)
    for x in ((13.77,) if truck else (4.85,)):
        for y in (-2,2):rod(v,'WIPER',(x,y-.6,6.6 if truck else 7.0),(x-.12,y+.65,7.9),.04)


def tigr(v):
    cab_frames(v,False)
    for s in (-1,1):
        box(v,'TURRETSHIELD',(-.55,s*.9-.13,.4),(1.4,s*.9+.13,2.0),PLATE,'TURRET',.10)
        rod(v,'ROOFRAIL',(-6.5,s*3.6,9.18),(1.5,s*3.6,9.18),.12)
        box(v,'SIDEVENT',(-8.7,s*4.24-.035,5.7),(-7.4,s*4.24+.035,7.5),VENT)
    stow(v,(-7.4,-2.8,9.07),(2.7,1.6,.65))
    sensor(v,(.2,0,1.9),'TURRET',.48)


def supply(v):
    cab_frames(v,True)
    for s in (-1,1):
        for x in (-14.8,-10,-5,0,4.7):box(v,'BEDSTANCHION',(x,s*4.9-.11,4.65),(x+.22,s*4.9+.11,7.42),IRON)
        for x in (-12,-6,0):ring(v,'TIEDOWN',(x,s*4.99,5.5),.24,.12,.12,IRON,axis='Y',segments=8)
        box(v,'FUELTANK',(1,s*3.8-.55,2.45),(5.3,s*3.8+.55,3.75),STEEL,bevel=.18)
        rod(v,'CABHANDLE',(6.22,s*4.51,5.8),(6.22,s*4.51,8.5),.10)
    rod(v,'EXHAUST',(5.65,-3.85,4),(5.65,-3.85,9.4),.23)
    ring(v,'EXHAUSTLIP',(5.65,-3.85,9.4),.3,.17,.18,IRON)
    box(v,'ROOFHATCH',(11.4,-1.5,9.57),(12.3,1.5,9.83),HATCH,bevel=.1)
    for z in (5,6,7):rod(v,'TAILGATERIB',(-15.03,-4.4,z),(-15.03,4.4,z),.08)


def engineer(v):
    running(v,11,5.3,5.7)
    # Armoured cab with proper side glazing, framing and a distinct service door.
    for s,y in ((-1,-.26),(1,4.56)):
        v.patch('D_CABSIDEGLASS',[(-5.2,y,7.1),(-.5,y,7.1),(-.85,y,9.32),(-5.2,y,9.32)],GLASS)
        pts=[(-5.3,y,7),(-.4,y,7),(-.8,y,9.4),(-5.3,y,9.4)]
        for p,q in zip(pts,pts[1:]+pts[:1]):rod(v,'CABFRAME',p,q,.12,STEEL)
        for x in (-5.7,-2.8):rod(v,'DOORFRAME',(x,y,5.9),(x,y,9.5),.065)
        box(v,'CABDOOR',(-5.6,y-.045,5.92),(-2.9,y+.045,6.85),PLATE)
        rod(v,'DOORHANDLE',(-3.8,y+s*.13,6.55),(-3.15,y+s*.13,6.55),.08)
        box(v,'STEP',(-5,y-.48,4.55),(-2.5,y+.48,4.75),IRON)
    for y in (.4,3.9):rod(v,'SCREENBAR',(1.12,y,7),(1.12,y,8.8),.10,STEEL)
    for z in (7,8.8):rod(v,'SCREENBAR',(1.12,.4,z),(1.12,3.9,z),.10,STEEL)
    hatch(v,-3,2.1,10.08,.86)
    for s in (-1,1):
        rod(v,'BLADECYL',(3.5,s*4.1,4.2),(7.4,s*4.65,3.6),.31,STEEL)
        rod(v,'BLADERAM',(7.2,s*4.65,3.62),(10.6,s*5,3.1),.16,IRON)
        for x,z in ((3.6,4.1),(10.5,3.1)):v.cyl('D_RAMJOINT',(x,s*4.85,z),.42,.32,IRON,'Y',segments=8)
    for y in (-6,-3,0,3,6):rod(v,'BLADERIB',(10.13,y,5.2),(11.85,y,1.2),.12,IRON)
    for y in (-6.8,-4.55,-2.3,0,2.3,4.55,6.8):box(v,'CUTTER',(13.26,y-.42,.26),(13.56,y+.42,.68),IRON)
    rod(v,'CRANERAM',(-6.2,-3.8,6.6),(-3.1,-3.8,11.85),.25,IRON)
    rod(v,'CRANERAMROD',(-3.2,-3.8,11.7),(-2.2,-3.8,13.35),.14,STEEL)
    for x,z in ((-7,5.85),(-2,13.95)):v.cyl('D_CRANEPIN',(x,-3.2,z),.5,1.35,IRON,'Y',segments=10)
    ring(v,'HOOK',(7,-3.2,9),.44,.25,.18,IRON,axis='Y',segments=8)
    stow(v,(-9,-4.2,5.78),(2.3,1.4,.8))


def service(v,x,y,z):
    box(v,'SERVICE',(x-2.8,y-2,z),(x+2.8,y+2,z+3),STEEL,bevel=.16)
    box(v,'SERVICEVENT',(x+2.81,y-1.65,z+.35),(x+2.86,y+1.65,z+2.55),VENT)
    rod(v,'CONDUIT',(x-2.95,y-1.7,z+.15),(x-2.95,y-1.7,z+3.9),.18)
    rod(v,'CONDUIT',(x-2.95,y-1.7,z+3.9),(x+.5,y-1.7,z+3.9),.18)


def doorframe(v,x,y,z=0,H=7,W=4):
    for s in (-1,1):box(v,'DOORFRAME',(x,y+s*(W/2+.18)-.2,z+.5),(x+.45,y+s*(W/2+.18)+.2,z+H+.35),STEEL)
    box(v,'DOORHEADER',(x,y-W/2-.4,z+H),(x+.55,y+W/2+.4,z+H+.6),STEEL)
    for s in (-1,1):box(v,'DOORLAMP',(x+.5,y+s*(W/2+1.1)-.35,z+H-.5),(x+.65,y+s*(W/2+1.1)+.35,z+H+.2),LAMP)


def ladder(v,x,y,z,H):
    for sy in (-1,1):rod(v,'LADDERRAIL',(x,y+sy*.85,z),(x,y+sy*.85,z+H),.11)
    for i in range(int(H/1.8)+1):rod(v,'LADDERRUNG',(x,y-.85,z+i*1.8),(x,y+.85,z+i*1.8),.09)


def fan(v,x,y,z,r=2):
    box(v,'FANBASE',(x-r-.4,y-r-.4,z),(x+r+.4,y+r+.4,z+.7),STEEL,bevel=.12)
    v.cyl('D_FANWELL',(x,y,z+.72),r,.12,IRON,segments=12)
    ring(v,'FANGUARD',(x,y,z+.88),r+.12,r-.12,.2,STEEL,segments=12)
    for offset in (-.6,0,.6):rod(v,'FANGRILLE',(x-r*.8,y+offset*r,z+.94),(x+r*.8,y+offset*r,z+.94),.08)


def structure(v):
    n=v.name
    # Industrial masonry: visible expansion joints/door surrounds and role-specific machinery.
    if n=='RUCC':
        service(v,-29,-5,18.85);fan(v,-12,-5,18.85,2.3);ladder(v,26.25,-12,1,28)
        doorframe(v,26.3,-8,H=6.5);doorframe(v,16.3,-5,H=6.5)
        for y in (-24,13):box(v,'CORNERARMOUR',(-39,y-1,1),(-36,y+1,17.7),STEEL)
        for y in (-18,2):rod(v,'ROOFCABLE',(-37,y,19),(-3,y,19),.14)
    elif n=='RUPWR':
        service(v,-21,-23,.6)
        for x in (12,28):
            for z in (4,15):ring(v,'TANKBAND',(x,-11,z),7.15,6.9,.5,IRON,segments=16)
            ladder(v,x+7.2,-11,1,19)
            rod(v,'FUELPIPE',(x,-18,2),(x,-22,2),.32)
        rod(v,'TRANSFERPIPE',(12,-22,2),(28,-22,2),.32)
        doorframe(v,3.76,0);fan(v,-10,0,21.2,2)
    elif n=='RUBARR':
        doorframe(v,9.3,-8);doorframe(v,6.8,22)
        service(v,-29,-27,.6);fan(v,-19,-8,19.95,1.8)
        for x in (-31,-22):stow(v,(x,29,.6),(6,2.5,2))
        for y in (-20,-10,0):box(v,'LOCKERS',(16,y,.6),(18.5,y+3,5),LOCKER)
        ladder(v,-35.4,-17,1,13)
    elif n=='RUSUPPLY':
        service(v,-41,31,.6);doorframe(v,-.9,6,H=13.8,W=38)
        for y in (-15,27):box(v,'DOCKBUMPER',(.3,y-.5,.6),(2,y+.5,4.5),IRON)
        for y in (-13,25):box(v,'PORTALLIGHT',(1,y-.5,14.7),(1.3,y+.5,15.5),LAMP)
        ladder(v,-46.4,13,1,17)
        for x in (-32,-19):
            for y in (-32,-24):box(v,'CARGOCORNER',(x-5.12,y-.12,1),(x-4.83,y+.12,7),IRON)
        fan(v,-31,6,23.75,2)
    elif n=='RUFACT':
        doorframe(v,26.25,-28,H=19.25,W=39)
        service(v,-38,48,.6);fan(v,-22,-28,30.65,2.4)
        for y in (-48,-8):rod(v,'DOORRAIL',(26.7,y,1),(26.7,y,20),.18)
        ladder(v,-47.4,-40,1,24)
        # Overhead service beam with supported end housings above the loading bay.
        rod(v,'HOISTRAIL',(16,-48,22.7),(16,-8,22.7),.35,IRON)
        for y in (-47,-9):box(v,'HOISTBRACKET',(13,y-1,21),(19,y+1,24),STEEL)
        box(v,'HOISTMOTOR',(15,-30,22),(17,-26,24.5),IRON)
        rod(v,'HOISTCHAIN',(16,-28,22),(16,-28,19.9),.07)
    elif n=='RUAIR':
        service(v,-57,58,.6);fan(v,-82,42,11.86,2.2)
        for y in (-49,-13):
            doorframe(v,-68.7,y,H=10,W=23)
            box(v,'POWERPOINT',(-66,y-16.5,.6),(-62,y-14,3),STEEL)
        for x in (-21,9):
            box(v,'SHELTERVENT',(x-9,50,14.1),(x-4,55,15.7),VENT)
        for z in (10,23,36):ring(v,'TOWERBAND',(-91,50,z),3.15,2.94,.55,STEEL,segments=8)
        ladder(v,-95,49,1,38)
    elif n=='RUTECH':
        service(v,-32,-15,21.85);fan(v,-25,18,21.85,2)
        doorframe(v,9.3,2,H=6.5);doorframe(v,33.3,12,H=6.5)
        ladder(v,33.3,5,1,29)
        for y in (-20,23):box(v,'REINFORCEDCORNERS',(-44,y-1,1),(-41,y+1,20.6),STEEL)
        for x in (-30,-18,-6):rod(v,'UTILITYPIPE',(x,-28.5,2),(x,-28.5,7.7),.22)
        ring(v,'DISHGUARD',(-12,10,30),9.6,9.25,.25,IRON,segments=16)
    elif n=='RUINCOME':
        doorframe(v,16.25,4,H=14,W=32);service(v,-31,31,.6);fan(v,-12,4,25.4,2)
        for x,y in ((28,-20),(28,0),(24,24)):
            for xx in (x-5.8,x+5.8):box(v,'CONTAINERPOST',(xx-.15,y-7.1,.6),(xx+.15,y+7.1,8.9),IRON)
            for yy in (y-4.5,y+4.5):rod(v,'LOCKINGBAR',(x+6.1,yy,1),(x+6.1,yy,8.2),.10)
        ladder(v,-39.8,16,1,17)
    elif n=='RUGDEF':
        for s in (-1,1):
            box(v,'BUNKERARMOUR',(-7,s*9.15-.15,1.4),(7,s*9.15+.15,4.55),STEEL)
            for x in (-5,0,5):box(v,'BUNKERJOIN',(x-.08,s*9.34-.035,1.65),(x+.08,s*9.34+.035,4.3),IRON)
        hatch(v,-1,-1.25,2.53,1.0,'TURRET');sensor(v,(1.2,1.65,1.6),'TURRET',.52)
        doorframe(v,10.4,0,H=4.6,W=3.5)
    elif n=='RUADEF':
        service(v,-9,-8,7.85)
        for s in (-1,1):rod(v,'MOUNTPIN',(0,s*2.6,-.8),(0,s*3.6,-.8),.45,IRON,'BARREL')
        for y,z in ((-2,0),(2,0),(-2,3),(2,3)):
            for x in (-4,3):ring(v,'TUBECLAMP',(x,y,z),1.26,1.1,.26,IRON,'BARREL','X',10)
            ring(v,'TUBEMOUTH',(6.07,y,z),1.22,.99,.16,IRON,'BARREL','X',10)
        doorframe(v,5.3,0,H=6.5,W=4)
    elif n=='RUSUPER':
        service(v,-43,-46,.6);doorframe(v,-21.2,-27,H=6.5,W=4);fan(v,-35,-27,17.85,2)
        for y in (-25,25):
            for x in (-18,36):box(v,'SILODRIVE',(x,y-2,1),(x+5,y+2,4.9),VENT,bevel=.18)
        for x in (-10,20):rod(v,'SILOREINFORCE',(x,-19,5.68),(x,19,5.68),.13,IRON)
        for x in (25,39):ladder(v,x+6.2,40,1,13)
        for y in (-44,-10):box(v,'SILOBUNKERCORNER',(-48,y-1,1),(-45,y+1,16.5),STEEL)


def world_matrices(v):
    world={'CHASSIS':Matrix.Identity(4)}
    for n,p,at,q in v.bones:
        world[n]=world[p]@Matrix.Translation(at)@(Quaternion((q[3],*q[:3])) if q else Quaternion()).to_matrix().to_4x4()
    return world


def apply(v):
    if v.name not in GROUND and not v.building:return v
    if getattr(v,'_ground_building_detail',False):return v
    bones=list(v.bones);world=world_matrices(v);initial=len(v.parts)
    points=[world[b]@vert.co for _,b,o,_,_ in v.parts for vert in o.data.vertices]
    lo=Vector([min(p[i] for p in points) for i in range(3)]);hi=Vector([max(p[i] for p in points) for i in range(3)])
    jobs={'RUBMPT':bmpt,'RUTIGR':tigr,'RUT90':t90,'RUBMP3':bmp,'RUTUNG':tung,'RUMSTA':msta,'RUTOS':tos,'RUENG':engineer,'RUSUP':supply}
    if v.building:structure(v)
    else:jobs[v.name](v)
    # An explicit envelope preserves the runtime dimensions exactly. Decorative
    # rim tops fit the existing silhouette rather than changing collision tuning.
    clipped=0
    for _,b,o,_,_ in v.parts[initial:]:
        inv=world[b].inverted();largest=0
        for vert in o.data.vertices:
            p=world[b]@vert.co;q=Vector([max(lo[i]+.001,min(hi[i]-.001,p[i])) for i in range(3)])
            largest=max(largest,(p-q).length)
            if (p-q).length>.001:clipped+=1;vert.co=inv@q
        if largest>.001:print('DETAIL_ENVELOPE',v.name,o.name,round(largest,3),flush=True)
    assert v.bones==bones
    v._ground_building_detail=True
    print('RUSSIA_DETAIL',v.name,'added_parts',len(v.parts)-initial,'envelope_adjusted_vertices',clipped,flush=True)
    return v


if __name__=='__main__':
    import sys,json
    from pathlib import Path
    sys.path.insert(0,str(Path(__file__).resolve().parent))
    import build
    from blender_kit import mesh_data
    report=[]
    names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [n for n in build.BUILDERS if n in GROUND or n not in ('RUSU35','RUSU25','RUMI28')]
    for n in names:
        bpy.ops.wm.read_factory_settings(use_empty=True);v=build.BUILDERS[n]();bones=list(v.bones);build.polish(v)
        count=sum(len(mesh_data(o)['tris']) for _,_,o,_,_ in v.parts)
        assert count<12000,(n,count)
        assert v.bones==bones
        assert all(math.isfinite(c) for _,_,o,_,_ in v.parts for vert in o.data.vertices for c in vert.co)
        size=len(v.parts);apply(v);assert size==len(v.parts)
        report.append({'model':n,'triangles':count,'bones':'unchanged','finite':True,'idempotent':True})
    path=build.BUILD/'ground-building-detail-qa.json';path.write_text(json.dumps(report,indent=2)+'\n');print('DETAIL_QA_PASSED',len(report),flush=True)

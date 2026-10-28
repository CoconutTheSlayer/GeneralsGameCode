"""Bounded original ground/industrial geometry finish for Ukraine.

Role-specific fittings only. Existing bones and original world bounds are frozen.
New parts are consolidated by surface/tile/bone before diffuse baking.
"""
import math
import bmesh
from mathutils import Matrix,Vector

VEHICLES={'UAKOZAK','UAOPLOT','UABTR4','UABUK','UABOHD','UADRONE','UADOZR','UASUPLY'}

def box(v,n,lo,hi,s='panel',b='CHASSIS',bevel=.06):return v.box('P_'+n,lo,hi,s,b,bevel)
def rod(v,n,a,b,r=.10,s='steel',bone='CHASSIS'):return v.beam('P_'+n,a,b,r,s,bone)
def ring(v,n,at,R,r,L=.15,s='steel',axis='Z',bone='CHASSIS',N=10):
    bm=bmesh.new();m=Matrix.Translation(at)@{'X':Matrix.Rotation(math.pi/2,4,'Y'),'Y':Matrix.Rotation(math.pi/2,4,'X'),'Z':Matrix.Identity(4)}[axis];rr=[]
    for z,rad in ((-L/2,R),(L/2,R),(L/2,r),(-L/2,r)):
        rr.append([bm.verts.new(m@Vector((rad*math.cos(i*math.tau/N),rad*math.sin(i*math.tau/N),z))) for i in range(N)])
    for a,b in zip(rr,rr[1:]+rr[:1]):
        for i in range(N):bm.faces.new((a[i],a[(i+1)%N],b[(i+1)%N],b[i]))
    return v.mesh('P_'+n,bm,s,bone)
def bolt(v,at,axis='Y',b='CHASSIS',r=.10):v.cyl('P_BOLT',at,r,.10,'steel',axis,b,segments=6)
def sensor(v,at,scale=.7,b='CHASSIS'):
    x,y,z=at;q=scale
    box(v,'OPTICBODY',(x-.60*q,y-.50*q,z),(x+.55*q,y+.5*q,z+.8*q),'steel',b,.07*q)
    box(v,'OPTICHOOD',(x-.65*q,y-.57*q,z+.72*q),(x+.70*q,y+.57*q,z+.94*q),'panel',b,.05*q)
    box(v,'OPTICGLASS',(x+.56*q,y-.36*q,z+.20*q),(x+.60*q,y+.36*q,z+.65*q),'glass',b,0)
    v.cyl('P_THERMAL',(x+.64*q,y+.22*q,z+.41*q),.13*q,.12*q,'glass','X',b,segments=8)
def rack(v,lo,hi,b='CHASSIS',bag=True):
    x,y,z=lo;X,Y,Z=hi
    for yy in (y,Y):
        rod(v,'RACKRAIL',(x,yy,Z),(X,yy,Z),.10,bone=b)
        rod(v,'RACKBASE',(x,yy,z),(X,yy,z),.10,bone=b)
        for xx in (x,X):rod(v,'RACKPOST',(xx,yy,z),(xx,yy,Z),.08,bone=b)
    for xx in (x,X,(x+X)/2):rod(v,'RACKCROSS',(xx,y,z),(xx,Y,z),.08,bone=b)
    if bag:
        box(v,'STOWAGE',(x+.15,y+.15,z+.1),(X-.15,Y-.15,Z-.16),'canvas',b,.16)
        for f in (.3,.7):rod(v,'STRAP',(x+f*(X-x),y+.13,Z-.1),(x+f*(X-x),Y-.13,Z-.1),.045,'steel',b)
def grille(v,lo,hi,b='CHASSIS',slats=5):
    x,y,z=lo;X,Y,Z=hi;box(v,'VENTFRAME',lo,hi,'steel',b,.04)
    box(v,'VENTFACE',(x+.12,y+.12,Z+.012),(X-.12,Y-.12,Z+.035),'vent',b,0)
    for i in range(slats):
        xx=x+.22+(X-x-.44)*i/max(1,slats-1)
        box(v,'LOUVRE',(xx-.04,y+.17,Z+.035),(xx+.04,Y-.17,Z+.12),'steel',b,.015)
def hatch(v,at,r=1,b='CHASSIS'):
    x,y,z=at;ring(v,'HATCHRIM',at,r+.12,r-.10,.13,'steel','Z',b)
    rod(v,'HATCHHANDLE',(x-.35,y,z+.17),(x+.35,y,z+.17),.07,'steel',b)
    for yy in (-.52,.52):
        box(v,'PERISCOPE',(x+.72,y+yy-.16,z+.02),(x+1.08,y+yy+.16,z+.32),'steel',b,.035)
        box(v,'PERIGLASS',(x+1.085,y+yy-.12,z+.1),(x+1.10,y+yy+.12,z+.25),'glass',b,0)
def gun(v,at,b='TURRET'):
    x,y,z=at;v.cyl('P_GUNPINTLE',(x,y,z+.22),.18,.44,'steel',bone=b,segments=8)
    box(v,'MGRECEIVER',(x-.45,y-.20,z+.31),(x+.48,y+.20,z+.65),'steel',b,.05)
    rod(v,'MGCOOLER',(x+.38,y,z+.5),(x+1.1,y,z+.5),.12,'steel',b)
    rod(v,'MGBARREL',(x+1.05,y,z+.5),(x+2.4,y,z+.5),.07,'steel',b)
    box(v,'MGMAG',(x-.1,y+.22,z+.19),(x+.42,y+.62,z+.66),'locker',b,.05)
def wheels(v):
    for name,_,at,_ in list(v.bones):
        if not name.startswith('TIRE'):continue
        sign=1 if at[1]>0 else -1
        ring(v,'HUBRIM',(0,sign*.77,0),.99,.79,.1,'wheelhub','Y',name,10)
        for j in range(5):
            rad=j*math.tau/5;bolt(v,(.59*math.cos(rad),sign*.86,.59*math.sin(rad)),'Y',name,.095)
def tracked(v,y,L):
    for sign in (-1,1):
        for x in (-L*.79,-L*.47,-L*.14,L*.19,L*.52,L*.82):
            bolt(v,(x,sign*y,1.8),'Y',r=.23)
        for x in (-L+.8,L-.8):
            box(v,'TRACKGUARD',(x-.18,sign*y-.62,1.1),(x+.18,sign*y+.62,3.35),'rubber')
def tow(v,x,y,z):
    for sign in (-1,1):
        box(v,'TOWBRACKET',(x-.5,sign*y-.25,z-.17),(x-.1,sign*y+.25,z+.24),'steel')
        ring(v,'TOWEYE',(x,sign*y,z),.28,.15,.14,'steel','X',N=8)
def team(v,x0,x1,y,z,h=.45,b='CHASSIS'):v.team(x0,x1,y,z,h,b)

def kozak(v):
    wheels(v);tow(v,10.55,2.8,3.9)
    rack(v,(-9,-2.8,8.27),(-5.6,2.7,9.1))
    for sign in (-1,1):
        box(v,'SILLARMOUR',(-8.65,sign*4.12-.06,4.53),(-4.0,sign*4.12+.06,5.47))
        for x in (-8.3,-4.35):bolt(v,(x,sign*4.22,5.16))
        box(v,'FUELCAN',(-9.60,sign*2.85-.55,4.32),(-8.87,sign*2.85+.55,6.06),'locker')
        rod(v,'MUDGUARD',(-8.35,sign*4.7,3.7),(-8.35,sign*4.7,1.6),.08,'rubber')
        rod(v,'ROOFGRAB',(-1.3,sign*3.5,8.1),(1.6,sign*3.5,8.1),.085)
    team(v,-7.8,-5.7,4.23,4.72,.38)
    grille(v,(5.3,-1.5,5.96),(8.4,1.5,6.13),slats=5)
    for sign in (-1,1):rod(v,'BRUSHGUARD',(10.45,sign*3.4,3.6),(10.45,sign*3.4,5.6),.10)
    rod(v,'BRUSHBAR',(10.45,-3.4,4.5),(10.45,3.4,4.5),.10)
    box(v,'GUNRECEIVER',(-.35,-.25,1.25),(1.1,.25,1.75),'steel','TURRET')
    box(v,'MGBELT',(-.65,.42,.6),(.35,1.12,1.40),'locker','TURRET')
    sensor(v,(.12,-1.15,.4),.55,'TURRET')

def oplot(v):
    tracked(v,6.65,12);tow(v,11.8,3.1,4.3)
    grille(v,(-11,-3.55,5.65),(-6.2,3.55,5.87),slats=7)
    for sign in (-1,1):
        for i in range(5):
            x=-10.5+i*4.0;bolt(v,(x,sign*6.58,4.45));bolt(v,(x+2.4,sign*6.58,4.45))
        rod(v,'TOWCABLE',(-10,sign*4.6,5.53),(-5.4,sign*4.6,5.63),.095)
        for i in range(3):
            x=.15+i*1.2
            box(v,'ERACAP',(x,sign*3.8-.60,2.32),(x+.88,sign*3.8+.60,2.62),'panel','TURRET',.055)
            bolt(v,(x+.35,sign*4.43,2.4),'Y','TURRET')
        for i in range(3):
            x=6.0+i*1.55;z=5.8-(x-5)*.165
            v.prism('P_GLACISERA',[(x,z),(x+1.36,z-.22),(x+1.30,z+.17),(x,z+.36)],sign*.35,sign*3.4,'panel')
    rack(v,(-6.05,-2.75,1.05),(-4.55,2.70,2.66),'TURRET')
    hatch(v,(-2,1.5,2.91),1.12,'TURRET');gun(v,(-2.15,1.38,2.95))
    sensor(v,(-1.65,-2.15,2.55),.72,'TURRET')
    ring(v,'MANTLET',(3.60,0,1.2),.66,.45,.48,'panel','X','TURRET',12)
    for x in (5.0,9.7,11.0):ring(v,'BARRELBAND',(x,0,1.2),.43,.37,.12,'steel','X','TURRET',10)

def btr(v):
    wheels(v);tow(v,12.7,3.1,4.3)
    for sign in (-1,1):
        for x in (-10,-6,-2,2):
            box(v,'SIDEARMOUR',(x,sign*5.34-.11,5.0),(x+3.5,sign*5.34+.11,5.76))
            for xx in (x+.35,x+3.1):bolt(v,(xx,sign*5.5,5.53))
        for x in (-9,-5,-1):
            ring(v,'FIRINGPORT',(x,sign*5.43,7.0),.28,.16,.10,'steel','Y',N=8)
        rod(v,'HANDRAIL',(-11,sign*4.7,8.2),(-5.5,sign*4.7,8.2),.07)
    box(v,'RAMPRIM',(-13.07,-3.4,3.9),(-12.9,3.4,7.46),'steel')
    box(v,'RAMP',(-13.14,-3.11,4.12),(-13.08,3.11,7.24),'panel')
    for z in (4.5,6.7):rod(v,'RAMPHINGE',(-13.15,-2.8,z),(-13.15,2.8,z),.09)
    rod(v,'RAMPLOCK',(-13.17,-.15,4.6),(-13.17,-.15,6.9),.075)
    for x in (-9.3,-5.7):hatch(v,(x,1.0,8.48),.85)
    grille(v,(-10.7,-4.15,8.1),(-6.3,-2.3,8.5),slats=5)
    rack(v,(-12.1,2.7,8.32),(-9.45,4.2,9.25))
    ring(v,'GUNBRACE',(2.6,0,1.2),.37,.23,.5,'steel','X','TURRET',10)
    for sign in (-1,1):
        for x in (-1.95,-1.4):
            v.cyl('P_SMOKE',(x,sign*2.05,1.45),.18,.70,'steel','X','TURRET',segments=8)
    sensor(v,(1.2,1.15,1.5),.48,'TURRET')

def buk(v):
    tracked(v,6.72,12);tow(v,11.8,3.1,4.1)
    grille(v,(-11,-3.8,6.25),(-6.6,3.8,6.45),slats=7);hatch(v,(7.1,-1.8,5.90),.9)
    for sign in (-1,1):
        box(v,'SERVICELOCKER',(-9.5,sign*5.6-.4,4.70),(-4.3,sign*5.6+.4,5.82),'locker')
        rod(v,'HYDRAULIC',(-4.7,sign*3.85,.35),(.5,sign*3.85,2.9),.20,'panel','TURRET')
        rod(v,'PISTON',(-1.7,sign*3.85,1.75),(1.2,sign*3.85,3.2),.095,'steel','TURRET')
        for x in (-4.4,-1.4,1.6):rod(v,'CRADLE',(x,sign*4.0,.40),(x+1.1,sign*4.0,2.1),.12,'steel','TURRET')
    ring(v,'RADARRIM',(3.54,0,4.3),1.90,1.65,.15,'steel','X','TURRET',16)
    v.cyl('P_RADARFACE',(3.59,0,4.3),1.62,.05,'vent','X','TURRET',segments=16)
    for y in (-3.6,-1.2,1.2,3.6):
        for x,z in ((-3.5,2.5),(2.0,3.45)):ring(v,'MISSILEBAND',(x,y,z),.46,.37,.14,'steel','X','TURRET',8)
    sensor(v,(2.2,-2.1,.95),.6,'TURRET')

def truck_details(v,L,cab,y,axles):
    wheels(v);tow(v,L+.2,y*.65,3.7)
    for sign in (-1,1):
        box(v,'CABSTEP',(cab-.2,sign*(y+.43)-.34,2.92),(cab+2.2,sign*(y+.43)+.34,3.15),'steel')
        rod(v,'CABGRAB',(cab+.22,sign*(y+.1),5.35),(cab+.22,sign*(y+.1),6.25),.07)
        box(v,'CABVISOR',(cab+.1,sign*2.55-.13,7.86),(L-3.6,sign*2.55+.13,8.22),'panel')
        for xx in axles[-2:]:box(v,'MUDAPRON',(xx-2.4,sign*y-.7,.75),(xx-2.23,sign*y+.7,3.55),'rubber')
    box(v,'ROOFVENT',(cab+.9,-1.4,8.04),(cab+2.9,1.4,8.30),'vent')

def bohdana(v):
    truck_details(v,17,9,4.7,(12,5,-6,-13))
    for sign in (-1,1):
        for x in (-2.75,.8):box(v,'AMMODRAWER',(x,sign*4.45-.06,5.10),(x+3.1,sign*4.45+.06,6.8),'locker')
        rod(v,'DECKRAIL',(-15,sign*4.65,6.0),(-10.2,sign*4.65,6.0),.10)
        for x in (-15,-10.2):rod(v,'RAILPOST',(x,sign*4.65,4.8),(x,sign*4.65,6.0),.08)
        rod(v,'JACKBODY',(-14.1,sign*3.7,4.65),(-15.2,sign*5.1,2.30),.23,'panel')
        rod(v,'JACKPISTON',(-15.2,sign*5.1,2.30),(-16,sign*6.1,1.0),.11)
        rod(v,'RECOILCYL',(0,sign*.64,3.63),(5.2,sign*.64,3.63),.20,'panel','TURRET')
        rod(v,'RECOILROD',(4.5,sign*.64,3.63),(8.1,sign*.64,3.63),.085,'steel','TURRET')
    box(v,'BREECHSHIELD',(-2.2,-1.0,2.1),(-.85,1.0,3.5),'panel','TURRET')
    box(v,'LOADTRAY',(-4.2,-.55,2.2),(-2.2,.55,2.48),'steel','TURRET')
    sensor(v,(-.8,1.85,2.0),.7,'TURRET')
    box(v,'CONSOLE',(-10.5,2.0,4.8),(-8.3,3.3,6.05),'panel')
    box(v,'CONTROLGLASS',(-8.29,2.18,5.27),(-8.24,3.12,5.85),'glass')
    rack(v,(-14.8,-3.5,4.85),(-11.0,-1.7,5.8),bag=False)

def drone(v):
    truck_details(v,11.5,5,4.3,(7,-7))
    rack(v,(-10.25,-3.4,9.14),(-6.1,-1.3,10.10))
    box(v,'ACBODY',(.0,-2.3,9.1),(3.4,.5,10.18),'panel')
    grille(v,(.25,-2.08,10.17),(3.14,.28,10.25),slats=5)
    ring(v,'MASTCOLLAR',(-8,0,9.45),.48,.19,.42,'steel')
    rod(v,'MASTCABLE',(-8,.31,9.55),(-8,.31,14.2),.044)
    for z in (4.2,5.1,6.0,6.9,7.8):rod(v,'LADDER',(-11.35,-2.2,z),(-11.35,-.5,z),.065)
    for y in (-2.2,-.5):rod(v,'LADDERRAIL',(-11.35,y,3.7),(-11.35,y,8.35),.075)
    box(v,'OPERATORPANEL',(-2.1,4.37,4.3),(2.3,4.46,6.45),'locker')
    box(v,'SCREEN',(-1.60,4.475,5.31),(.4,4.49,6.05),'glass')
    for x in (-1.45,-.78,-.1):v.cyl('P_SWITCH',(x,4.5,4.95),.09,.05,'yellow','Y',segments=8)
    for y in (-1.22,1.22):
        box(v,'DRONECASSETTE',(-1.6,y-.52,.1),(1.7,y+.52,1.18),'locker','TURRET')
        rod(v,'LAUNCHBRACE',(-1.6,y,.2),(2.3,y,1.7),.09,'steel','TURRET')

def engineer(v):
    tracked(v,5.88,9)
    for sign in (-1,1):
        rod(v,'BLADECYL',(-.5,sign*3.2,4.45),(5.8,sign*3.2,3.25),.31,'panel')
        rod(v,'BLADERAM',(4.9,sign*3.2,3.45),(8.9,sign*3.2,2.25),.13)
        rod(v,'CABGRAB',(-4.4,sign*2.79,6.0),(-4.4,sign*2.79,8.25),.075)
        box(v,'CABFRAME',(-4.5,sign*2.73-.06,5.95),(.15,sign*2.73+.06,6.12),'steel')
        for x in (-3.6,-.9):bolt(v,(x,sign*2.82,6.0))
    v.patch('P_FRONTGLASS',[(.77,-2.15,6.0),(.77,2.15,6.0),(.4,2.15,8.48),(.4,-2.15,8.48)],'glass')
    grille(v,(2,-2.8,5.25),(6,2.8,5.64),slats=6)
    rack(v,(-7.4,-2.3,5.9),(-5.4,1.6,6.9))
    v.cyl('P_AIRCLEANER',(-6.5,2.5,6.65),.48,1.7,'panel',segments=10)
    v.cyl('P_FILTERCAP',(-6.5,2.5,7.5),.64,.16,'steel',segments=10)
    for y in (-5.4,-3.6,-1.8,0,1.8,3.6,5.4):
        box(v,'CUTTER',(1.45,y-.48,.28),(1.98,y+.48,.64),'tracksteel','BLADE',.03)
        bolt(v,(2.015,y,1.2),'X','BLADE',.12)
    for y in (-5,-2,2,5):rod(v,'BLADERIB',(.43,y,1.0),(1.30,y,3.6),.14,'steel','BLADE')

def supply(v):
    truck_details(v,14,7,4.6,(9,-5,-10))
    for sign in (-1,1):
        v.cyl('P_FUELTANK',(2.8,sign*3.7,3.15),.68,3.9,'panel','X',segments=10)
        for x in (1.6,4.0):ring(v,'TANKSTRAP',(x,sign*3.7,3.15),.72,.65,.12,'steel','X',N=10)
        for x in (-12,-7,-2):rod(v,'CARGOPOST',(x,sign*3.86,4.5),(x,sign*3.86,7.9),.085)
        rod(v,'CARGORAIL',(-12,sign*3.86,7.9),(-2,sign*3.86,7.9),.08)
    for x in (-12,-7,-2):rod(v,'CARGOBOW',(x,-3.86,7.9),(x,3.86,7.9),.08)
    box(v,'TAILGATE',(-13.92,-4.3,4.5),(-13.83,4.3,6.28),'panel')
    for y in (-2.8,0,2.8):rod(v,'GATEHINGE',(-13.95,y-.4,4.64),(-13.95,y+.4,4.64),.10)
    rod(v,'GATELOCK',(-13.98,-1.0,5.55),(-13.98,1.0,5.55),.08)
    for x in (-10,-5,0):
        for sign in (-1,1):rod(v,'TIEDOWN',(x,sign*3.5,7.6),(x+.7,sign*4.45,4.7),.045,'steel')

HALLS={'UACMD':(-48,13,-42,9,18),'UAPOWER':(-23,8,-20,15,13),'UABARR':(-36,20,-25,6,13),
 'UASUPP':(-42,-8,-33,32,15),'UAFACT':(-49,-10,15,44,14),'UAAIR':(-106,-68,12,64,18),
 'UATECH':(-40,21,-31,8,18),'UAINCOM':(-31,12,-25,14,13),'UASUPER':(-45,-10,-37,32,15)}
def service(v,x,y,z=1,size=1):
    q=size;box(v,'SERVICECAB',(x,y,z),(x+3*q,y+2.4*q,z+4.5*q),'locker',bevel=.16)
    box(v,'SERVICEVENT',(x+3.02*q,y+.3*q,z+1*q),(x+3.10*q,y+2.1*q,z+3.8*q),'vent',bevel=0)
    rod(v,'CONDUIT',(x+.4*q,y,z+1*q),(x+.4*q,y-1.7*q,z+1*q),.11*q)
def hall_details(v):
    x0,x1,y0,y1,h=HALLS[v.name];ym=(y0+y1)/2
    # Deep door jambs, a real threshold and hinges add scale without blocking exits.
    for yy in (ym-3.17,ym+3.17):box(v,'DOORFRAME',(x1+.40,yy-.15,1),(x1+.63,yy+.15,8.9),'steel')
    box(v,'DOORHEADER',(x1+.40,ym-3.32,8.65),(x1+.63,ym+3.32,8.95),'steel')
    box(v,'THRESHOLD',(x1+.45,ym-3.5,1.04),(x1+2.5,ym+3.5,1.37),'steel')
    for z in (2.5,6.5):rod(v,'DOORHINGE',(x1+.7,ym-2.84,z),(x1+.7,ym-2.84,z+.7),.10)
    rod(v,'DOORGRIP',(x1+.72,ym+1.9,4),(x1+.72,ym+1.9,5.25),.11)
    for y in (y0,y1):
        sign=-1 if y==y0 else 1;face=y+sign*.34
        for x in range(int(x0)+6,int(x1)-3,9):
            box(v,'WINDOWMULLION',(x+1.9,face-.06,h*.5),(x+2.08,face+.06,h*.7),'steel',bevel=.01)
            box(v,'WINDOWSILL',(x-.3,face-.22,h*.5-.28),(x+4.4,face+.22,h*.5-.08),'steel')
        rod(v,'DRAINPIPE',(x0+2,face,1.3),(x0+2,face,h-.2),.18)
        for z in (3,h*.5,h-1):ring(v,'PIPECOLLAR',(x0+2,face,z),.25,.18,.13,'steel')
    # Roof fittings sit on the low shoulder below the retained pitched ridge.
    z=h+1.0;yy=y1-4.6
    box(v,'ROOFVENT',(x0+5,yy-1.7,z),(x0+12,yy+1.7,z+1.8),'steel',bevel=.15)
    box(v,'ROOFLOUVRE',(x0+5.2,yy-1.52,z+1.82),(x0+11.8,yy+1.52,z+1.85),'vent',bevel=0)
    for xx in (x0+5.4,x0+11.6):bolt(v,(xx,yy,z+1.94),'Z',r=.18)
    # A wall-mounted air handler and connected pipe, within the existing foundation.
    xx=x0+7;yy=y1+.65
    box(v,'AIRHANDLER',(xx,yy,2.3),(xx+8,yy+2.1,7.0),'steel',bevel=.2)
    for x in (xx+2.1,xx+5.9):
        ring(v,'FANGUARD',(x,yy+2.15,4.65),1.55,1.29,.14,'steel','Y',N=12)
        v.cyl('P_FAN',(x,yy+2.22,4.65),1.20,.06,'vent','Y',segments=12)
    rod(v,'HANDLERPIPE',(xx+7,yy+.5,6),(xx+7,y1-.1,9),.17)

def building(v):
    if v.name in HALLS:hall_details(v)
    if v.name=='UACMD':
        service(v,21,-25,1,1.3)
        box(v,'GARAGEFRAME',(18,24,10.8),(20.3,45,12.7),'panel')
        for y in (25.4,44.0):rod(v,'GARAGERAIL',(20.4,y,1.3),(20.4,y,11.3),.16)
        for x in (-27,-19):box(v,'TOWERPANEL',(x,-31.1,24),(x+3,-30.8,31),'vent')
    elif v.name=='UAPOWER':
        for y in (-14,6):
            rod(v,'COOLANT',(10,y,4),(21,y,4),.5,'panel')
            ring(v,'VALVE',(13,y,5),.85,.6,.16,'steel')
            rod(v,'VALVESHAFT',(13,y,4),(13,y,5.0),.15)
        for x in (-15,-10,-5):box(v,'GENVENT',(x,-15.2,18),(x+3,-15.05,21.2),'vent')
    elif v.name=='UABARR':
        rack(v,(9,10,1.3),(28,13,4.6),bag=False)
        for x in (11,17,23):box(v,'KIT',(x,10.25,1.5),(x+3.3,12.75,4.05),'locker')
        box(v,'BENCH',(9,16,2.6),(27,18.0,3.05),'canvas')
        for x in (11,25):box(v,'BENCHLEG',(x,16.4,1.2),(x+.5,17.6,2.6),'steel')
    elif v.name=='UASUPP':
        for x in (0,11):
            for y in (-23,-10):
                box(v,'PALLET',(x-4.2,y-4.2,2.36),(x+4.2,y+4.2,2.74),'steel')
                for yy in (y-2.8,y+2.8):box(v,'PALLETRUNNER',(x-4.1,yy-.35,2.25),(x+4.1,yy+.35,2.41),'steel')
        box(v,'CRANERUNNER',(-3,-18,22.1),(19,-12,22.6),'steel')
        ring(v,'HOOK',(8,-15,13.5),.65,.4,.3,'steel','Y',N=10)
        service(v,23,-29,1,1.2)
    elif v.name=='UAFACT':
        for y in (-37,1):
            box(v,'PORTAL',(29.5,y-.6,1.4),(32.4,y+.6,16.2),'panel')
            rod(v,'ROLLERTRACK',(32.5,y,2.0),(32.5,y,16.1),.19)
            for z in (4,10,15):bolt(v,(32.7,y,z),'X',r=.24)
        box(v,'PORTALHEADER',(30,-37,16.0),(32.6,1,18.0),'panel')
        for y in (-27,-11):box(v,'FLOORRAIL',(-46,y-.22,1.03),(25,y+.22,1.15),'steel')
        box(v,'WORKBENCH',(-43,-35,5.0),(-23,-28,5.5),'steel')
        for x in (-41,-25):box(v,'BENCHBASE',(x,-34,1.1),(x+1,-29,5.0),'panel')
        service(v,40,40,1,1.1)
    elif v.name=='UAAIR':
        service(v,35,59,1,1.45)
        for x in (-41,-9,23,55,87):
            box(v,'EDGEBASE',(x,-65.2,1.2),(x+1.2,-64,1.5),'steel')
            v.cyl('P_RUNWAYLIGHT',(x+.6,-64.6,1.7),.27,.36,'lamp',segments=8)
        for x in (-28,4):
            for y in (31,61):box(v,'HANGARFRAME',(x-11.2,y-.3,1.1),(x-8.8,y+.3,13.2),'steel')
            box(v,'HANGARHEADER',(x-10,29.15,11.8),(x+10,29.55,13.7),'panel')
        box(v,'GROUNDPOWER',(-62,56,1.2),(-52,63,5.1),'locker')
    elif v.name=='UATECH':
        for x in (29,39):
            for y in (-24,-13,-2):box(v,'SERVERLOUVRE',(x+6.02,y,2.4),(x+6.12,y+7,8.9),'vent')
            rod(v,'SERVERPIPE',(x+3,-27,8),(x+3,-30,8),.28)
        service(v,24,15,1,1.5)
    elif v.name=='UAINCOM':
        box(v,'TOOLBENCH',(12,-26,4.0),(26,-22,4.4),'steel')
        for x in (13,24):box(v,'BENCHBASE',(x,-25.5,1.2),(x+.7,-22.5,4.0),'panel')
        for x in (16,20):
            v.cyl('P_GASCYL',(x,-24,6.3),1.0,3.8,'panel',segments=12)
            v.cyl('P_BOTTLEVALVE',(x,-24,8.3),.22,.36,'steel',segments=8)
        service(v,15,10,1,1.0)
    elif v.name=='UASUPER':
        for x in (9,31):
            for y in (-20,16):
                box(v,'LIDMOTOR',(x+6.5,y-7.2,3.0),(x+9.6,y-3.6,5.7),'vent')
                for xx in (x-5.5,x+5.5):
                    for yy in (y-8,y+8):bolt(v,(xx,yy,8.95),'Z',r=.19)
                rod(v,'LIDRAM',(x+7.5,y+1,3.5),(x+7.5,y+7.0,7.5),.18)
        service(v,-4,35,1,1.2)
    else:
        # Defences retain their low bunker silhouettes and exact traversing rigs.
        box(v,'BUNKERDOOR',(12.65,-2.8,1.3),(12.93,2.8,4.9),'locker')
        for y in (-2.97,2.97):box(v,'DOORJAMB',(12.62,y-.15,1.1),(13.1,y+.15,5.1),'steel')
        hatch(v,(-2,1.5,3.92),.72,'TURRET')
        sensor(v,(1.0,-1.5,3.10),.70,'TURRET')
        if v.name=='UAGUARD':
            for y in (-1,1):ring(v,'BARRELCOLLAR',(4.0,y,2.3),.45,.33,.9,'panel','X','TURRET',10)
            box(v,'AMMOLOCKER',(-4,-3.2,.5),(-2.6,-1.0,2.7),'locker','TURRET')
        else:
            for y in (-4.6,4.6):
                for z in (1.2,3):ring(v,'LAUNCHRIM',(7.12,y,z),.58,.44,.15,'steel','X','TURRET',8)
        for sign in (-1,1):rod(v,'ACCESSRAIL',(-9,sign*7.7,6.1),(-3,sign*10.6,6.1),.10)

def apply(a):
    if getattr(a,'_ukraine_ground_polished',False) or (a.name not in VEHICLES and not a.building):return a
    import engineer as kit
    originals={p[2] for p in a.parts};bones=list(a.bones);a.world()
    pts=[o.matrix_world@v.co for _,_,o,_,_ in a.parts for v in o.data.vertices]
    lo=Vector([min(p[i] for p in pts) for i in range(3)]);hi=Vector([max(p[i] for p in pts) for i in range(3)])
    jobs={'UAKOZAK':kozak,'UAOPLOT':oplot,'UABTR4':btr,'UABUK':buk,'UABOHD':bohdana,'UADRONE':drone,'UADOZR':engineer,'UASUPLY':supply}
    (jobs[a.name] if a.name in jobs else building)(a)
    assert a.bones==bones,'Added fitting changed a gameplay bone'
    world=a.world();groups={};keep=[];clamped=0
    for part in a.parts:
        n,b,o,s,k=part
        if o in originals:keep.append(part);continue
        inv=world[b].inverted()
        for v in o.data.vertices:
            p=world[b]@v.co;q=Vector([max(lo[i]+.003,min(hi[i]-.003,p[i])) for i in range(3)])
            if (q-p).length>1e-5:clamped+=1
            v.co=inv@q
        o.data.update()
        groups.setdefault((b,s,k,int(o.get('ua_tile',0))),[]).append(o)
    for i,((b,s,k,tile),objects) in enumerate(groups.items()):
        n='POLISH%02d'%i;o=kit.join(objects,n) if len(objects)>1 else objects[0]
        o.name=n;o['ua_tile']=tile;o['ua_surface']=s
        keep.append((n,b,o,s,k))
    a.parts=keep;a.world();a._ukraine_ground_polished=True
    a.notes.append('Ground V3: original role-specific fittings, layered armour/optics/mechanical or industrial details. Added parts consolidated by material and existing bone. Original world bounds, bone transforms and pitched roof outlines preserved.')
    a.notes.append('Detail geometry source scripts/models/ukraine/polish_ground.py; boundary-limited vertices '+str(clamped)+'.')
    return a

if __name__=='__main__':
    from pathlib import Path
    import sys,json,bpy
    here=Path(__file__).resolve().parent;sys.path.insert(0,str(here));import generate as api
    from blender_kit import mesh_data
    names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else [n for n in api.JOBS if n in VEHICLES or n in {v[0] for v in api.BUILDINGS.values()}]
    results=[]
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True);a=api.JOBS[name]();before=sum(len(mesh_data(o)['tris']) for _,_,o,_,_ in a.parts);bones=list(a.bones)
        apply(a);after=sum(len(mesh_data(o)['tris']) for _,_,o,_,_ in a.parts)
        assert a.bones==bones and after<11000,(name,after)
        assert all(math.isfinite(c) for _,_,o,_,_ in a.parts for v in o.data.vertices for c in v.co)
        results.append({'model':name,'before':before,'after':after,'added':after-before,'parts':len(a.parts),'bones_unchanged':True})
    (api.BUILD/'v3-geometry-validation.json').write_text(json.dumps({'status':'passed','assets':results},indent=2)+'\n');print(json.dumps(results),flush=True)

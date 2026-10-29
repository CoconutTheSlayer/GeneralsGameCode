"""Original shaped Ukrainian airframes; existing dimensions and animation bones.

+X nose. F-16 wing/intake silhouette; TB2 inverted-V twin-boom tail; Mi-24
rounded troop cabin, tandem bubbles, engine pods and articulated rotors.
"""
import math
import bmesh
from mathutils import Matrix,Vector

def create(api,kind):
    name,key,label,role,base={'f16':('UAF16','F16','F-16','Multirole fighter','AmericaJetRaptor'),
     'tb2':('UATB2','TB2','TB2','Armed aerial scout','AmericaJetRaptor'),
     'mi24':('UAMI24','Mi24','Mi-24','Heavy assault helicopter','AmericaVehicleComanche')}[kind]
    a=api.Asset(name,key,label,role,base)
    def smooth(o):
        for p in o.data.polygons:p.use_smooth=True
        return o
    def loft(n,rings,s='paint',y=0,b='CHASSIS',N=20):
        bm=bmesh.new();vv=[]
        for x,z,ry,rz in rings:vv.append([bm.verts.new((x,y+ry*math.cos(i*math.tau/N),z+rz*math.sin(i*math.tau/N))) for i in range(N)])
        bm.faces.new(list(reversed(vv[0])));bm.faces.new(vv[-1])
        for p,q in zip(vv,vv[1:]):
            for i in range(N):bm.faces.new((p[i],p[(i+1)%N],q[(i+1)%N],q[i]))
        return smooth(a.mesh(n,bm,s,b))
    def ell(n,at,r,s='paint',b='CHASSIS'):
        bm=bmesh.new();bmesh.ops.create_uvsphere(bm,u_segments=16,v_segments=10,radius=1,matrix=Matrix.Translation(at)@Matrix.Diagonal((*r,1)))
        return smooth(a.mesh(n,bm,s,b))
    def wing(n,xy,z,t=.10,s='paint',b='CHASSIS'):return api.wing(a,n,xy,z,t,s,b)
    def ring(n,at,outer,inner,length,s='steel',axis='X',b='CHASSIS',N=20):
        bm=bmesh.new();vv=[];rot={'X':Matrix.Rotation(math.pi/2,4,'Y'),'Y':Matrix.Rotation(math.pi/2,4,'X'),'Z':Matrix.Identity(4)}[axis]
        mat=Matrix.Translation(at)@rot
        for z,r in ((-length/2,outer),(length/2,outer),(-length/2,inner),(length/2,inner)):
            vv.append([bm.verts.new(mat@Vector((r*math.cos(i*math.tau/N),r*math.sin(i*math.tau/N),z))) for i in range(N)])
        for j,k in ((0,1),(1,3),(3,2),(2,0)):
            for i in range(N):bm.faces.new((vv[j][i],vv[j][(i+1)%N],vv[k][(i+1)%N],vv[k][i]))
        return a.mesh(n,bm,s,b)
    def missile(x,y,z,L=5,r=.22,s='white'):
        loft('MISSILE',[(x-L/2,z,r*.5,r*.5),(x-L/2+.5,z,r,r),(x+L/2-.8,z,r,r),(x+L/2,z,.025,.025)],s,y)
        for sign in (-1,1):
            wing('FIN',[(x-L/2+.1,y),(x-L/2-.1,y+sign*r*3),(x-L/2+1,y+sign*r*2),(x-L/2+1.25,y)],z,.035,s)
        a.prism('FIN',[(x-L/2+.1,z),(x-L/2-.1,z+r*3),(x-L/2+1,z+r*2),(x-L/2+1.25,z)],y-.035,y+.035,s)
    if kind=='f16':
        loft('FUSELAGE',[(-13,1.9,1.48,1.42),(-9,2.0,1.80,1.7),(-3,2.0,2.05,1.85),(3,2.02,1.85,1.63),(7.5,2.0,1.36,1.12),(11,1.91,.85,.74),(15.95,1.86,.03,.035)])
        loft('RADOME',[(9.6,1.96,1.05,.86),(12,1.9,.71,.63),(15.98,1.86,.025,.025)],'radome')
        ring('NOZZLE',(-13.35,0,1.9),1.48,1.13,.75,'exhaust')
        a.cyl('NOZZLEDARK',(-13.06,0,1.9),1.1,.08,'rubber','X',segments=20)
        for j in range(16):
            rad=j*math.tau/16
            a.beam('NOZZLEPETAL',(-13.74,1.48*math.cos(rad),1.9+1.48*math.sin(rad)),(-13.0,1.37*math.cos(rad),1.9+1.37*math.sin(rad)),.025,'steel')
        for sign in (-1,1):
            wing('LERX',[(7.0,sign*1.3),(1.1,sign*3.3),(-6.3,sign*3.4),(-9.0,sign*1.7)],2.18,.13)
            wing('MAINWING',[(2.8,sign*2),(-4.1,sign*11.9),(-7.2,sign*11.9),(-7.8,sign*1.7)],1.55,.12)
            wing('TAILPLANE',[(-8.6,sign*1.3),(-11.0,sign*6.1),(-14.0,sign*5.7),(-12.6,sign*1.2)],1.91,.105)
            a.prism('VENTRALFIN',[(-12,1),(-13.2,-.15),(-10.2,.03),(-9.1,1.1)],sign*1.1-.07,sign*1.1+.07,'radome')
            a.beam('AILERON',(-6.65,sign*11.2,1.685),(-7.15,sign*4,1.685),.028,'steel')
            a.beam('LEADSEAM',(1.7,sign*3,1.685),(-4.55,sign*11.2,1.685),.025,'steel')
            a.prism('PYLON',[(-4.1,-.45),(.1,-.45),(-.25,1.45),(-3.3,1.45)],sign*5-.14,sign*5+.14,'radome')
            loft('DROPTANK',[(-6,-.65,.08,.08),(-4.5,-.70,.58,.54),(0,-.70,.60,.55),(2,-.62,.06,.06)],'radome',sign*5)
            a.box('RAIL',(-5.5,sign*9-.09,.7),(-1.8,sign*9+.09,1.5),'radome',bevel=.04)
            missile(-2.5,sign*9,.3,6,.24)
            missile(-5.2,sign*12,1.55,4.5,.17)
            a.patch('HOUSECOLOR',[(-5.8,sign*6,1.691),(-4.7,sign*6,1.691),(-4.7,sign*9,1.691),(-5.8,sign*9,1.691)],house=True)
            a.bone('MUZZLE%02d'%(1 if sign>0 else 2),(.5,sign*9,.3))
        a.prism('TAILFIN',[(-12.8,2.5),(-10.8,7.95),(-8.6,7.95),(-5.8,2.65)],-.14,.14)
        for sign in (-1,1):a.beam('RUDDER',(-11.95,sign*.155,3.2),(-10.27,sign*.155,7.5),.025,'steel')
        loft('SPINE',[(-9,3.6,.28,.25),(-5,3.85,.48,.48),(0,3.8,.42,.4),(2,3.7,.17,.18)])
        # Hollow elliptical intake lip, darker recess and rounded lower trunk.
        loft('INTAKETRUNK',[(-4,.9,1.0,.45),(0,.40,1.4,.68),(3.9,.40,1.18,.67)],'radome')
        lip=ring('INTAKELIP',(4.05,0,.4),.83,.67,.25,'radome',N=20)
        for v in lip.data.vertices:v.co.y*=1.47
        bore=a.cyl('INTAKERECESS',(3.91,0,.4),.665,.06,'rubber','X',segments=20)
        for v in bore.data.vertices:v.co.y*=1.47
        loft('CANOPY',[(.6,3.58,.18,.10),(2.1,4.0,.82,.73),(4.5,4.2,.97,1.02),(6.7,3.8,.73,.70),(7.7,3.12,.10,.08)],'glass')
        for sign in (-1,1):
            a.beam('CANOPYRAIL',(1.5,sign*.73,3.7),(6.5,sign*.66,3.45),.055,'radome')
            a.beam('CANOPYBOW',(5.7,sign*.90,4.0),(5.7,sign*.31,5.10),.055,'radome')
        a.beam('CANOPYCROWN',(5.7,-.31,5.10),(5.7,.31,5.10),.05,'radome')
        a.prism('ANTENNA',[(-4,4.3),(-4.4,5),(-3.3,4.95),(-2.8,4.3)],-.045,.045,'steel')
        a.bone('ENGINE01',(-14,0,1.9));a.bone('MUZZLEFX01',(.5,9,.3))
    elif kind=='tb2':
        loft('FUSELAGE',[(-8,1.1,.52,.59),(-5,1.1,1.10,1.02),(-.5,1.15,1.4,1.2),(4,1.12,1.1,.95),(7.3,1.02,.64,.58),(9,1.0,.05,.10)])
        loft('DORSALFAIRING',[(-4,2.0,.2,.15),(-1,2.2,.66,.52),(2,2.08,.52,.38),(4,1.95,.15,.10)],'radome')
        for sign in (-1,1):
            wing('MAINWING',[(1.3,sign*.95),(-1.8,sign*15.95),(-4.0,sign*15.95),(-3.0,sign*.9)],1.7,.13,'radome')
            a.beam('FLAP',(-3.58,sign*14.9,1.845),(-2.78,sign*4.0,1.845),.025,'steel')
            loft('BOOM',[(-12,1.9,.17,.18),(-8,1.75,.21,.23),(-3.2,1.6,.25,.25),(-.5,1.55,.18,.17)],'radome',sign*2.9,N=12)
            # Two angled tail surfaces form a true inverted V, rather than four flat slabs.
            points=[(-12.3,sign*2.9,1.85),(-12.2,0,4.15),(-9.4,0,4.15),(-9.3,sign*2.9,1.85)]
            bm=bmesh.new();lower=[bm.verts.new((x,y,z-.09)) for x,y,z in points];upper=[bm.verts.new((x,y,z+.09)) for x,y,z in points]
            bm.faces.new(list(reversed(lower)));bm.faces.new(upper)
            for j in range(4):bm.faces.new((lower[j],lower[(j+1)%4],upper[(j+1)%4],upper[j]))
            a.mesh('VTAIL',bm,'radome')
            a.box('PYLON',(-1.1,sign*6-.11,.18),(.55,sign*6+.11,1.6),'radome',bevel=.05)
            missile(-.5,sign*6,0,3.2,.28,'darkpaint')
            a.patch('HOUSECOLOR',[(-2.4,sign*8,1.845),(-3.2,sign*8,1.845),(-3.4,sign*10.9,1.845),(-2.6,sign*10.9,1.845)],house=True)
        # Separate gimbal and downward lens, with a recessed front optical window.
        a.cyl('GIMBALNECK',(5,0,.06),.43,.70,'steel',segments=12)
        ell('GIMBAL',(5,0,-.52),(.70,.69,.66),'radome')
        a.cyl('CAMERALENS',(5.60,0,-.49),.32,.08,'glass','X',segments=16)
        a.cyl('CAMERALENS',(5,0,-1.14),.28,.05,'glass',segments=16)
        a.patch('HATCH',[(-.5,-.6,2.35),(1.6,-.5,2.2),(1.6,.5,2.2),(-.5,.6,2.35)],'hatch')
        a.prism('ANTENNA',[(1.9,2.25),(2.0,2.9),(2.6,2.25)],-.04,.04,'steel')
        prop=a.bone('PROPELLER',(-8.2,0,1));a.spins[prop]=1
        for sign in (-1,1):wing('PROPELLER',[(sign*.25,-.10),(sign*3.0,-.18),(sign*3.2,.18),(sign*.6,.25)],0,.045,'steel',prop)
        a.cyl('SPINNER',(0,0,-.22),.28,.65,'radome',bone=prop,segments=12,r2=.09)
        a.bone('MUZZLE01',(0,6,0));a.bone('MUZZLE02',(0,-6,0))
        a.notes.append('Original twin-boom inverted-V empennage, fuller airframe, articulated EO gimbal and pusher prop. Existing X-oriented propeller bone/clip retained.')
    else:
        loft('CABIN',[(-12,4,.52,.75),(-9,3.9,1.0,1.52),(-6,3.55,2.07,2.4),(-1.5,3.35,2.82,2.62),(3.4,3.28,2.55,2.43),(6.2,3.1,1.94,1.9),(9.6,2.82,1.32,1.31),(12.7,2.72,.45,.59),(13,2.72,.06,.15)])
        loft('BELLY',[(-7,1.15,.30,.25),(-3,1.05,1.85,.45),(3,1.1,1.75,.50),(7.5,1.7,.35,.30)],'darkpaint')
        # Two distinct rounded tandem bubbles, carefully spaced vertically.
        for x,z,r in ((8.4,4.02,1.35),(3.8,5.08,1.60)):
            loft('CANOPY',[(x-r*1.4,z-.38,.28,.25),(x-r*.7,z+.12,r*.82,r*.88),(x+.25,z+.17,r*.87,r*.98),(x+r*1.15,z-.15,r*.55,r*.64),(x+r*1.55,z-.70,.14,.16)],'glass')
            for sign in (-1,1):
                a.beam('CANOPYRAIL',(x-r*.9,sign*r*.84,z-.42),(x+r*.99,sign*r*.62,z-.48),.070,'paint')
                a.beam('CANOPYBOW',(x+.35,sign*r*.86,z+.08),(x+.35,sign*r*.28,z+r*.98),.07,'paint')
            a.beam('CANOPYTOP',(x+.35,-r*.28,z+r*.98),(x+.35,r*.28,z+r*.98),.06,'paint')
        loft('TAILBOOM',[(-23.3,7.02,.26,.40),(-19,6.5,.48,.54),(-13,4.8,.80,.83),(-8,4.1,1.08,1.25)])
        a.prism('TAILFIN',[(-23.45,6.7),(-23.95,10.1),(-22.1,10.0),(-20.4,6.5)],-.16,.16)
        for sign in (-1,1):
            wing('TAILPLANE',[(-17.8,sign*.4),(-19.6,sign*4.3),(-21.1,sign*4.0),(-19.5,sign*.4)],6.7,.10)
            wing('STUBWING',[(-4.0,sign*2.4),(-5.0,sign*8),(0,sign*8),(1.8,sign*2.4)],3.55,.20)
            loft('ENGINE',[(-6.2,6.0,.45,.60),(-5.5,6.1,.94,.97),(-1.0,6.25,1.02,1.03),(1.45,6.1,.80,.80),(2.0,6.0,.73,.73)],'paint',sign*1.35)
            ring('ENGINEINTAKE',(2.02,sign*1.35,6.0),.75,.56,.18,'steel')
            a.cyl('INTAKEBLACK',(1.96,sign*1.35,6.0),.55,.05,'rubber','X',segments=16)
            ring('EXHAUST',(-5.45,sign*1.35,6.1),.70,.51,.75,'exhaust')
            a.cyl('EXHAUSTBORE',(-5.28,sign*1.35,6.1),.5,.06,'rubber','X',segments=16)
            a.box('PYLON',(-2.4,sign*6.2-.16,2.55),(.25,sign*6.2+.16,3.4),'steel',bevel=.07)
            a.cyl('ROCKETPOD',(-1,sign*6.2,2),.82,4,'darkpaint','X',segments=16)
            ring('PODRIM',(1.02,sign*6.2,2),.83,.72,.16,'steel')
            for j in range(7):
                ang=j*math.tau/6;dy,dz=(0,0) if j==6 else (.46*math.cos(ang),.46*math.sin(ang))
                a.cyl('ROCKETBORE',(1.08,sign*6.2+dy,2+dz),.17,.05,'rubber','X',segments=8)
            a.beam('GEARLEG',(-1,sign*2.2,2.3),(-1,sign*3.45,.38),.18,'steel')
            a.beam('GEARBRACE',(-3,sign*2.2,2.2),(-1,sign*3.45,.50),.13,'steel')
            a.cyl('WHEEL',(-1,sign*3.55,.48),.70,.48,'rubber','Y',segments=16)
            a.cyl('HUB',(-1,sign*3.84,.48),.32,.08,'steel','Y',segments=12)
            a.patch('CABINWINDOW',[(-5,sign*2.54,3.1),(-2.8,sign*2.83,3.1),(-2.8,sign*2.64,4.45),(-5,sign*2.32,4.4)],'glass')
            a.beam('DOORSEAM',(-5.9,sign*2.16,2.1),(-5.9,sign*2.16,4.6),.035,'steel')
            a.beam('HANDLE',(-4.8,sign*2.63,2.78),(-4.1,sign*2.73,2.78),.06,'steel')
            if sign>0:a.team(-2.0,.2,2.86,2.40,.55)
        ell('GUNTURRET',(10.4,0,1.40),(.8,.70,.60),'darkpaint')
        a.beam('CHINGUN',(10.65,0,1.38),(13.0,0,1.38),.12,'steel')
        a.beam('NOSEGEAR',(8.4,0,1.4),(8.2,0,.15),.15,'steel')
        for y in (-.27,.27):a.cyl('NOSEWHEEL',(8.2,y,.23),.45,.28,'rubber','Y',segments=12)
        r=a.bone('ROTOR',(0,0,7.7));a.spins[r]=1
        a.cyl('MAST',(0,0,-.50),.31,1.3,'steel',bone=r,segments=12)
        a.cyl('HUB',(0,0,.16),.65,.36,'steel',bone=r,segments=12)
        for j in range(5):
            ang=j*math.tau/5
            xy=[(math.cos(ang)*radius-math.sin(ang)*y,math.sin(ang)*radius+math.cos(ang)*y) for radius,y in ((.55,-.18),(3,-.30),(16,-.39),(16,.39),(3,.30),(.55,.18))]
            wing('MAINBLADE',xy,.30,.055,'steel',r)
            a.beam('PITCHLINK',(.5*math.cos(ang),.5*math.sin(ang),-.28),(1.8*math.cos(ang),1.8*math.sin(ang),.25),.07,'exhaust',r)
        tr=a.bone('TAILROTOR',(-22.5,.6,7.2));a.spins[tr]=1
        for j in range(3):
            ang=j*math.tau/3;xy=[(math.cos(ang)*rad-math.sin(ang)*y,math.sin(ang)*rad+math.cos(ang)*y) for rad,y in ((.25,-.13),(3.1,-.21),(3.1,.21),(.25,.13))]
            wing('TAILBLADE',xy,0,.045,'steel',tr)
        a.cyl('TAILHUB',(0,0,.05),.30,.35,'steel',bone=tr,segments=12)
        a.bone('MUZZLE01',(1,6,2));a.bone('MUZZLE02',(1,-6,2));a.bone('MUZZLEFX01',(11,0,2))
        a.notes.append('Mi-24 V2 original rounded fuselage, stepped tandem canopies, hollow engine intakes/exhausts, detailed rocket pods and rotor head; existing rotor pivots retained.')
    a.notes.append('Aircraft V2 uses original shaped airframe geometry, projected panel/glass textures and contact-shadow diffuse bake. Existing muzzle and effect bone positions retained; no gameplay scale adjustment.')
    return a

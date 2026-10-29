"""Original articulated infantry with human proportions and dedicated cloth UVs."""
import math
import bmesh
from mathutils import Matrix, Vector


def create(api, kind):
    spike, comm = kind == 'Spike', kind == 'Commando'
    model = {'Rifleman':'RURIFLE','Spike':'RUKORNET','Commando':'RUCMDO'}[kind]
    parent = 'AmericaInfantryMissileDefender' if spike else 'AmericaInfantryColonelBurton' if comm else 'AmericaInfantryRanger'
    v = api.Articulated(model, 'Anti-tank missile team' if spike else 'Assault engineer' if comm else 'Rifle infantry', parent)
    v.art_revision = 'russia-articulated-v2'
    def smooth(obj):
        for p in obj.data.polygons: p.use_smooth = True
        return obj
    def ell(name, at, radii, tile=11, bone='CHASSIS'):
        return smooth(v.ellipsoid(name,at,radii,tile,bone))
    def tube(name,a,b,r1,r2,tile=11,bone='CHASSIS'):
        a,b=Vector(a),Vector(b);delta=b-a;bm=bmesh.new()
        bmesh.ops.create_cone(bm,cap_ends=True,segments=10,radius1=r1,radius2=r2,depth=delta.length,
            matrix=Matrix.Translation((a+b)/2)@delta.to_track_quat('Z','Y').to_matrix().to_4x4())
        return smooth(v.mesh(name,bm,tile,bone))
    def section(name,rings,tile=11,bone='CHASSIS',N=16):
        bm=bmesh.new();verts=[]
        for z,cx,rx,ry in rings:
            verts.append([bm.verts.new((cx+rx*math.cos(i*math.tau/N),ry*math.sin(i*math.tau/N),z)) for i in range(N)])
        bm.faces.new(list(reversed(verts[0])));bm.faces.new(verts[-1])
        for a,b in zip(verts,verts[1:]):
            for i in range(N):bm.faces.new((a[i],a[(i+1)%N],b[(i+1)%N],b[i]))
        return smooth(v.mesh(name,bm,tile,bone))

    # Each leg has a knee and ankle. Clothing follows the joint, not one rigid post.
    for side,s in [('L',1),('R',-1)]:
        leg='LEG'+side;knee='KNEE'+side;foot='FOOT'+side
        v.bone(leg,(0,s*.43,3.35))
        tube('THIGH',(0,0,-.05),(.10,0,-1.28),.31,.25,11,leg)
        ell('THIGHFOLD',(.02,0,-.4),(.32,.32,.38),11,leg)
        v.bone(knee,(.1,0,-1.28),leg)
        ell('KNEE',(0,0,-.09),(.27,.27,.31),11,knee)
        tube('SHIN',(0,0,-.15),(-.08,0,-1.42),.235,.16,11,knee)
        v.box('KNEEPAD',(.20,-.20,-.29),(.31,.20,.13),6,knee,.06)
        v.bone(foot,(-.08,0,-1.48),knee)
        v.box('BOOT',(-.27,-.25,-.47),(.59,.25,.12),6,foot,.14)
        v.box('SOLE',(-.3,-.27,-.5),(.64,.27,-.36),7,foot,.05)
        v.box('LACES',(.29,-.14,-.13),(.51,.14,.01),8,foot,.03)
        v.box('THIGHPOCKET',(-.13,s*.25-.09,-.79),(.2,s*.25+.09,-.2),3,leg,.08)
    section('PELVIS',[(3.02,-.03,.32,.54),(3.28,0,.39,.66),(3.7,0,.34,.63)],11)
    section('UNIFORM',[(3.55,0,.34,.61),(3.95,0,.38,.66),(4.62,-.015,.44,.79),(5.16,-.04,.41,.76),(5.42,-.04,.25,.46)],11)
    section('PLATECARRIER',[(3.82,.03,.39,.58),(4.2,.04,.48,.69),(4.95,.015,.49,.70),(5.16,0,.39,.53)],1)
    v.box('FRONTPLATE',(.42,-.52,4.03),(.55,.52,4.96),1,bevel=.12)
    for y in (-.37,0,.37):
        v.box('MAGPOUCH',(.51,y-.16,3.95),(.73,y+.16,4.48),3,bevel=.055)
    for s in (-1,1):
        tube('WEBBING',(.40,s*.5,4.95),(-.3,s*.5,5.26),.075,.075,12)
        v.box('BELTPOUCH',(-.2,s*.63-.11,3.48),(.2,s*.63+.11,3.88),3,bevel=.06)
    v.box('BELT',(-.37,-.66,3.48),(.41,.66,3.66),8,bevel=.07)
    v.box('BELTBUCKLE',(.4,-.13,3.48),(.46,.13,3.67),12,bevel=.02)
    v.box('HYDRATION',(-.66,-.47,4.0),(-.42,.47,5.03),3,bevel=.13)
    v.box('RADIO',(-.7,.26,4.55),(-.53,.53,5.2),8,bevel=.035)
    tube('ANTENNA',(-.64,.4,5.1),(-.64,.4,5.88),.019,.012,8)
    tube('NECK',(0,0,5.32),(0,0,5.76),.19,.20,10)
    head=section('HEAD',[(5.65,.05,.22,.24),(5.78,.06,.29,.32),(6.08,.035,.35,.37),
                        (6.36,0,.34,.36),(6.52,-.03,.25,.27),(6.57,-.04,.1,.15)],10,N=20)
    ell('NOSE',(.36,0,6.12),(.12,.10,.16),10)
    for s in (-1,1):
        ell('EAR',(.01,s*.365,6.08),(.095,.075,.16),10)
        ell('EYE',(.337,s*.14,6.30),(.018,.050,.022),8)
        tube('BROW',(.334,s*.09,6.355),(.327,s*.20,6.34),.014,.012,8)
    if comm:
        section('BERET',[(6.40,-.04,.37,.39),(6.55,-.13,.43,.47),(6.69,-.10,.32,.37),(6.75,-.13,.16,.20)],13)
        for s in (-1,1):ell('HEADSET',(-.04,s*.39,6.11),(.15,.07,.2),8)
        tube('MIC',(.02,-.45,5.99),(.41,-.19,5.91),.023,.023,8)
        ell('MICFOAM',(.43,-.18,5.91),(.065,.04,.045),8)
    else:
        helmet=section('HELMET',[(6.15,-.08,.39,.41),(6.38,-.08,.43,.45),(6.61,-.11,.36,.39),(6.77,-.12,.20,.24),(6.82,-.12,.045,.06)],0,N=20)
        for vert in helmet.data.vertices:
            if vert.co.z<6.44:vert.co.z+=max(0,min(1,(vert.co.x+.10)/.32))*(6.44-vert.co.z)
        for s in (-1,1):tube('CHINSTRAP',(.03,s*.38,6.27),(.13,s*.18,5.70),.024,.024,12)
        v.box('HELMETMOUNT',(.31,-.08,6.34),(.4,.08,6.53),8,bevel=.02)

    v.bone('ARMS',(0,0,5.13))
    for s in (-1,1):
        shoulder=(0,s*.82,0);elbow=(.53,s*.90,-.80)
        hand=(1.42,s*.16,-.78) if not spike else (1.28,s*.24,-.08)
        ell('SHOULDER',shoulder,(.31,.30,.36),11,'ARMS')
        tube('UPPERARM',shoulder,elbow,.26,.21,11,'ARMS')
        ell('ELBOW',elbow,(.21,.21,.25),11,'ARMS')
        tube('FOREARM',elbow,hand,.21,.135,11,'ARMS')
        ell('GLOVE',hand,(.18,.14,.18),5,'ARMS')
    if spike:
        v.cyl('LAUNCHER',(1.10,-.14,.16),.35,3.45,4,'X','ARMS',segments=16)
        for x in (-.59,2.8):v.cyl('CAPRIM',(x,-.14,.16),.39,.12,8,'X','ARMS',segments=16)
        v.cyl('APERTURE',(2.87,-.14,.16),.30,.05,8,'X','ARMS',segments=16)
        v.box('CLU',(.63,-.77,-.10),(1.32,-.49,.49),8,'ARMS',.07)
        v.box('CLUGLASS',(1.325,-.7,.06),(1.34,-.55,.31),9,'ARMS')
        tube('GRIP',(.9,-.16,-.16),(.9,-.16,-.66),.10,.10,8,'ARMS')
        muzzle=(2.94,-.14,.16)
    else:
        # Original AK-family silhouette: separate stock, forward curved magazine and long fore-end.
        v.box('RIFLEBODY',(.72,-.25,-.90),(2.03,.05,-.59),8,'ARMS',.05)
        v.box('HANDGUARD',(2.0,-.26,-.87),(2.57,.06,-.59),0,'ARMS',.05)
        v.box('STOCK',(.22,-.23,-.98),(.8,.03,-.66),0,'ARMS',.04)
        v.prism('MAGAZINE',[(1.30,-.87),(1.57,-.87),(1.77,-1.39),(1.48,-1.35)],-.2,.02,8,'ARMS')
        v.box('GRIP',(1.46,-.18,-1.18),(1.63,.02,-.83),8,'ARMS',.025)
        v.box('TOPRAIL',(.83,-.2,-.56),(2.12,.01,-.47),8,'ARMS',.02)
        v.cyl('OPTIC',(1.6,-.09,-.40),.105,.38,8,'X','ARMS',segments=10)
        v.cyl('LENS',(1.8,-.09,-.40),.077,.02,9,'X','ARMS',segments=10)
        tube('BARREL',(2.52,-.1,-.70),(3.14,-.1,-.70),.065,.05,8,'ARMS')
        tube('GASTUBE',(2.48,-.1,-.55),(2.94,-.1,-.55),.04,.04,8,'ARMS')
        v.box('FRONTSIGHT',(2.94,-.15,-.73),(3.05,-.05,-.38),8,'ARMS',.02)
        muzzle=(3.20,-.1,-.7)
        if comm:
            v.cyl('GRENADETUBE',(2.28,-.10,-1.04),.16,.85,8,'X','ARMS',segments=12)
            muzzle=(2.75,-.10,-1.04)
            for y in (-.4,.05):v.box('DEMOCHARGE',(-.95,y,3.72),(-.64,y+.34,4.72),0,bevel=.07)
    for name in ('MUZZLE01','MUZZLEFX01','WEAPONA01'):v.bone(name,muzzle,'ARMS')
    for s in (-1,1):
        y=s*1.10
        v.house('HOUSE', [(-.13,y,4.85),(.21,y,4.85),(.21,y,5.08),(-.13,y,5.08)])
    v.house('CHESTTEAM',[(.565,-.34,4.68),(.565,-.06,4.68),(.565,-.06,4.86),(.565,-.34,4.86)])
    def q(a):return (0,math.sin(a/2),0,math.cos(a/2))
    # W3D keeps the previous clip when a condition has no animation. An explicit
    # neutral clip resets every animated joint when a soldier stops or ceases fire.
    v.animations['_I']={bone:[q(0) for _ in range(21)] for bone in
                       ('CHASSIS','LEGL','LEGR','KNEEL','KNEER','FOOTL','FOOTR','ARMS')}
    run={}
    for side,phase in [('L',0),('R',math.pi)]:
        run['LEG'+side]=[q(.52*math.sin(i*math.tau/20+phase)) for i in range(21)]
        run['KNEE'+side]=[q(.08+.75*max(0,math.sin(i*math.tau/20+phase))) for i in range(21)]
        run['FOOT'+side]=[q(-.08-.22*max(0,math.sin(i*math.tau/20+phase))) for i in range(21)]
    run['ARMS']=[q(.025*math.sin(i*math.tau*2/20)) for i in range(21)]
    v.animations['_R']=run
    v.animations['_F']={'ARMS':[q(.025*math.sin(i*math.tau/5)) for i in range(21)]}
    v.animations['_X']={'CHASSIS':[q(math.pi*.5*i/20) for i in range(21)],
                        'KNEEL':[q(.65*i/20) for i in range(21)],'KNEER':[q(.5*i/20) for i in range(21)]}
    # Match the stock Ranger's thirteen-unit standing height at ModelScale=1.
    for _,_,obj,_,_ in v.parts:
        for vert in obj.data.vertices:vert.co*=2.0
    v.bones=[(n,p,tuple(c*2 for c in at),q) for n,p,at,q in v.bones]
    return v

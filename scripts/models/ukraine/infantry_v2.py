"""Original Ukrainian infantry at the existing 6.5-unit authored skeleton scale.

Bone names and local positions are unchanged. All dynamic joints reset in idle,
fire and death clips so W3D cannot retain the final gait pose when units stop.
"""
import math
import bmesh
from mathutils import Matrix,Vector

def create(api,kind):
    name,key,label,base={'rifle':('UARIFL','Rifleman','Rifleman','AmericaInfantryRanger'),
      'stugna':('UASTUG','Stugna','Stugna Team','AmericaInfantryMissileDefender'),
      'commando':('UACOMM','Commando','Sapper','AmericaInfantryRanger'),
      'manpads':('UAMANP','MANPADS','MANPADS Team','AmericaInfantryMissileDefender')}[kind]
    a=api.Asset(name,key,label,'Infantry',base)
    def smooth(o):
        for p in o.data.polygons:p.use_smooth=True
        return o
    def ell(n,at,r,s='uniform',b='CHASSIS'):
        bm=bmesh.new();bmesh.ops.create_uvsphere(bm,u_segments=12,v_segments=8,radius=1,matrix=Matrix.Translation(at)@Matrix.Diagonal((*r,1)))
        return smooth(a.mesh(n,bm,s,b))
    def tube(n,p,q,r0,r1,s='uniform',b='CHASSIS'):
        p,q=Vector(p),Vector(q);d=q-p;bm=bmesh.new()
        bmesh.ops.create_cone(bm,cap_ends=True,segments=12,radius1=r0,radius2=r1,depth=d.length,
            matrix=Matrix.Translation((p+q)/2)@d.to_track_quat('Z','Y').to_matrix().to_4x4())
        return smooth(a.mesh(n,bm,s,b))
    def section(n,rings,s='uniform',b='CHASSIS',N=16):
        bm=bmesh.new();vv=[]
        for z,cx,rx,ry in rings:vv.append([bm.verts.new((cx+rx*math.cos(i*math.tau/N),ry*math.sin(i*math.tau/N),z)) for i in range(N)])
        bm.faces.new(list(reversed(vv[0])));bm.faces.new(vv[-1])
        for one,two in zip(vv,vv[1:]):
            for i in range(N):bm.faces.new((one[i],one[(i+1)%N],two[(i+1)%N],two[i]))
        return smooth(a.mesh(n,bm,s,b))
    root=a.bone('BODYROOT');pelvis=a.bone('PELVIS',(0,0,3.25),root)
    section('HIPS',[(-.23,-.03,.33,.54),(0,0,.40,.64),(.43,0,.34,.61)],b=pelvis)
    chest=a.bone('TORSO',(0,0,.45),pelvis)
    section('JACKET',[(-.10,0,.34,.59),(.32,0,.40,.66),(.97,-.02,.43,.77),(1.48,-.03,.40,.72),(1.70,-.04,.25,.46)],b=chest)
    section('CARRIER',[(.16,.04,.40,.58),(.40,.04,.49,.67),(1.18,0,.49,.68),(1.42,-.01,.38,.52)],'vest',chest)
    a.box('FRONTPLATE',(.44,-.51,.30),(.58,.51,1.20),'vest',chest,.09)
    for y in (-.37,0,.37):a.box('MAGPOUCH',(.57,y-.16,.23),(.78,y+.16,.76),'pouch',chest,.065)
    a.box('BELT',(-.36,-.64,-.05),(.40,.64,.12),'webbing',chest,.05)
    a.box('BUCKLE',(.40,-.13,-.04),(.48,.13,.13),'steel',chest,.02)
    for sign in (-1,1):
        tube('SHOULDERSTRAP',(.4,sign*.46,1.22),(-.3,sign*.47,1.57),.07,.07,'webbing',chest)
        a.box('BELTPOUCH',(-.17,sign*.63-.1,-.17),(.22,sign*.63+.1,.23),'pouch',chest,.065)
    a.box('HYDRATION',(-.68,-.44,.25),(-.40,.44,1.28),'canvas',chest,.14)
    a.box('RADIO',(-.75,.27,.85),(-.52,.52,1.5),'steel',chest,.035)
    tube('ANTENNA',(-.66,.39,1.45),(-.69,.39,2.17),.022,.012,'steel',chest)
    tube('NECK',(0,0,1.55),(0,0,1.91),.18,.21,'skin',chest)
    head=a.bone('HEAD',(0,0,2.1),chest)
    face=section('HEAD',[(-.30,.065,.22,.23),(-.17,.06,.29,.31),(.08,.025,.34,.36),(.34,-.02,.33,.35),(.48,-.04,.23,.26),(.52,-.05,.09,.12)],'skin',head,N=20)
    for p in face.data.polygons:
        if p.normal.x<=.35:continue
        for li in p.loop_indices:
            co=face.data.vertices[face.data.loops[li].vertex_index].co
            u=max(0,min(1,.5-co.y/.73));v=max(0,min(1,(co.z+.29)/.68))
            face.data.uv_layers['AtlasUV'].data[li].uv=((2+.07+.86*u)/4,1-(3+.93-.86*v)/4)
    ell('NOSE',(.34,0,.10),(.105,.09,.13),'skin',head)
    for sign in (-1,1):
        ell('EAR',(-.02,sign*.355,.08),(.09,.07,.15),'skin',head)
        ell('EYE',(.33,sign*.135,.235),(.018,.043,.02),'rubber',head)
    if False:
        section('BERET',[(.27,-.055,.36,.37),(.41,-.12,.43,.43),(.57,-.14,.29,.33),(.62,-.16,.14,.18)],'beret',head)
        for sign in (-1,1):ell('HEADSET',(-.045,sign*.37,.09),(.14,.075,.19),'steel',head)
        tube('MIC',(.03,-.40,-.02),(.39,-.16,-.10),.020,.020,'steel',head)
        ell('MICFOAM',(.39,-.16,-.10),(.06,.04,.04),'rubber',head)
    else:
        helmet=section('HELMET',[(.13,-.07,.38,.40),(.33,-.09,.42,.43),(.54,-.10,.35,.37),(.69,-.11,.18,.22),(.73,-.11,.045,.055)],'helmet',head,N=20)
        for vert in helmet.data.vertices:
            if vert.co.z<.39:vert.co.z+=max(0,min(1,(vert.co.x+.1)/.30))*(.39-vert.co.z)
        for sign in (-1,1):tube('CHINSTRAP',(.02,sign*.37,.22),(.14,sign*.17,-.27),.024,.024,'webbing',head)
        a.box('NVGMOUNT',(.30,-.075,.32),(.39,.075,.51),'steel',head,.025)
    for sign,side in ((1,'L'),(-1,'R')):
        leg=a.bone('LEG'+side,(0,sign*.43,0),pelvis)
        tube('THIGH',(0,0,-.07),(.12,0,-1.40),.31,.24,b=leg)
        ell('THIGHFOLD',(.015,0,-.3),(.31,.31,.34),b=leg)
        a.box('THIGHPOCKET',(-.13,sign*.25-.09,-.95),(.22,sign*.25+.09,-.40),'pouch',leg,.065)
        shin=a.bone('SHIN'+side,(.12,0,-1.5),leg)
        ell('KNEE',(0,0,.02),(.255,.25,.30),b=shin)
        tube('SHIN',(0,0,-.10),(-.11,0,-1.14),.23,.16,b=shin)
        a.box('KNEEPAD',(.20,-.18,-.17),(.31,.18,.22),'boot',shin,.07)
        a.box('BOOT',(-.33,-.25,-1.50),(.57,.25,-.97),'boot',shin,.12)
        a.box('SOLE',(-.35,-.27,-1.58),(.62,.27,-1.42),'sole',shin,.045)
        a.box('LACES',(.30,-.14,-1.14),(.49,.14,-1.01),'steel',shin,.02)
        arm=a.bone('ARM'+side,(0,sign*.86,1.5),chest)
        ell('SHOULDER',(0,0,-.035),(.29,.29,.34),b=arm)
        tube('UPPERARM',(0,0,-.06),(.20,sign*.2,-.8),.265,.20,b=arm)
        fore=a.bone('FORE'+side,(.2,sign*.2,-.8),arm)
        ell('ELBOW',(0,0,0),(.205,.205,.23),b=fore)
        hand=(1.15,-sign*.86,.94) if kind in ('stugna','manpads') else (1.1,-sign*.89,.13)
        tube('FOREARM',(0,0,0),hand,.21,.135,b=fore)
        ell('GLOVE',hand,(.18,.14,.17),'glove',fore)
    if kind in ('stugna','manpads'):
        # Portable gameplay abstraction: a single articulated missile tube,
        # optical unit and grip; remove the redundant rifle of the old model.
        tube('TUBE',(-.65 if kind=='manpads' else -.20,-.65,1.70),(3.20,-.65,1.70),.22 if kind=='manpads' else .36,.22 if kind=='manpads' else .36,'darkpaint',chest)
        for x in (-.18,3.15):a.cyl('TUBERIM',(x,-.65,1.7),.25 if kind=='manpads' else .40,.12,'steel','X',chest,16)
        a.cyl('APERTURE',(3.23,-.65,1.7),.20 if kind=='manpads' else .29,.07,'rubber','X',chest,16)
        a.box('CLU',(.65,-1.17,1.66),(1.53,-.86,2.30),'steel',chest,.07)
        a.cyl('CLULENS',(1.55,-1.015,2.10),.15,.04,'glass','X',chest,12)
        a.box('GRIP',(1.2,-.75,1.05),(1.38,-.55,1.5),'rubber',chest,.03)
        for x in (.12,2.7):a.cyl('TUBEBAND',(x,-.65,1.7),.378,.14,'webbing','X',chest,16)
        muzzle=(3.3,-.65,5.4)
        a.notes.append('Portable Stugna caricature preserves infantry gameplay; original detailed tube/CLU replaces redundant carried rifle.')
    else:
        # Recognisable conventional AK-pattern silhouette, with wood/polymer
        # handguard and curved magazine; short suppressor for the commando.
        a.box('RECEIVER',(.72,-.16,.66),(2.05,.16,.93),'steel',chest,.05)
        a.prism('STOCK',[(.32,.62),(.78,.68),(1.05,.89),(.55,.99),(.25,.91)],-.14,.14,'boot',chest)
        a.box('HANDGUARD',(1.92,-.18,.65),(2.62,.18,.89),'darkpaint',chest,.055)
        a.prism('MAGAZINE',[(1.34,.67),(1.60,.69),(1.73,.20),(1.57,.04),(1.37,.08),(1.46,.24)],-.10,.10,'steel',chest)
        a.box('PISTOLGRIP',(.94,-.11,.30),(1.12,.11,.69),'rubber',chest,.035)
        tube('BARREL',(2.53,0,.82),(3.60,0,.82),.075,.055,'steel',chest)
        tube('GASTUBE',(2.43,0,.98),(3.10,0,.98),.06,.05,'steel',chest)
        a.box('FRONTSIGHT',(3.06,-.055,.85),(3.15,.055,1.12),'steel',chest)
        a.box('TOPRAIL',(1.11,-.10,.93),(2.01,.10,1.01),'steel',chest,.02)
        muzzle=(3.6,0,4.52)
        if False:
            a.cyl('SUPPRESSOR',(3.69,0,.82),.13,.90,'steel','X',chest,12)
            a.cyl('SCOPE',(1.63,0,1.15),.14,.58,'steel','X',chest,12)
            a.cyl('SCOPELENS',(1.935,0,1.15),.105,.025,'glass','X',chest,12)
            muzzle=(4.15,0,4.52)
    if kind=='commando':
        a.box('DEMOBAG',(-1.00,-.58,.24),(-.67,.58,1.30),'canvas',chest,.09)
        a.cyl('MINECASE',(-.95,-.67,.85),.36,.18,'darkpaint','Y',chest,12)
        a.beam('PROBE',(-.81,.61,-.25),(-.81,.61,1.55),.035,'steel',chest)
    for n in ('MUZZLE01','MUZZLEFX01','Muzzle'):a.bone(n,muzzle)
    a.team(-.15,.20,1.135,1.25,.22,chest)
    a.patch('HOUSECOLOR',[(.595,-.36,.98),(.595,-.09,.98),(.595,-.09,1.16),(.595,-.36,1.16)],bone=chest,house=True)
    def q(v):return (0,math.sin(v/2),0,math.cos(v/2))
    dynamic=('BODYROOT','PELVIS','TORSO','HEAD','LEGL','LEGR','SHINL','SHINR','ARML','ARMR','FOREL','FORER')
    for suffix,mode in (('_W','walk'),('_I','idle'),('_F','fire'),('_DIE','die')):
        channels={bone:[q(0) for _ in range(21)] for bone in dynamic}
        if mode=='walk':
            for side,phase in (('L',0),('R',math.pi)):
                channels['LEG'+side]=[q(.52*math.sin(f*math.tau/20+phase)) for f in range(21)]
                channels['SHIN'+side]=[q(.08+.72*max(0,math.sin(f*math.tau/20+phase))) for f in range(21)]
            # The held weapon and hands move together with the upper body.
            channels['TORSO']=[q(.025*math.sin(f*math.tau*2/20)) for f in range(21)]
        elif mode=='fire':channels['TORSO']=[q(.018*math.sin(f*math.tau/5)) for f in range(21)]
        elif mode=='die':channels['BODYROOT']=[q(-min(f/14,1)*math.pi/2) for f in range(21)]
        a.extra_animations[suffix]=channels
    a.notes.append('Infantry V2 original shaped anatomy/face/helmet, cloth, plate carrier, pouches, gloves and original weapon geometry. Existing bones/local transforms retained; every clip explicitly resets all animated joints. Keep gameplay Scale=1.5.')
    return a

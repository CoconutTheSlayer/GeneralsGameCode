"""Original Vilkas IFV: a faceted mission hull and a readable remote turret.

Everything here is authored mathematical geometry. The eight wheel pivots and
weapon pivots are the existing game contracts; dimensions remain in that hull's
original footprint. Broad armour uses paint rather than repeated bolt panels.
"""
import bmesh
from original_compacts import Vehicle, tire, lamps
from original_compacts import STEEL, IRON, VENT, GLASS, TUBE, HATCH, HUB, LOCKER, DOOR
from coalition_ground import shell
import engineer as kit
from compact_polish_common import stowage


def plain_paint(obj):
    """Use the atlas's painted fields without stamping welds on every facet."""
    uv=obj.data.uv_layers.active
    for face in obj.data.polygons:
        # The upper and lower regions each retain the approved blue/slate camo.
        x0,y0,w,h=(.22,.035,.74,.32) if face.normal.z>.5 else (.03,.57,.93,.38)
        for i in face.loop_indices:
            u=uv.data[i].uv.x*4
            v=4-uv.data[i].uv.y*4
            uv.data[i].uv=((x0+u*w)/4,1-(y0+v*h)/4)
    return obj


def armour(v, name, stations, bone='CHASSIS'):
    """Loft bevelled armour rings, keeping useful silhouette facets at RTS scale."""
    bm=bmesh.new();shell(bm,stations)
    return plain_paint(v.mesh(name,bm,STEEL,bone))


def prism(v, name, profile, y0, y1, tile=STEEL, bone='CHASSIS'):
    bm=bmesh.new();kit.prism_xz(bm,profile,y0,y1)
    obj=v.mesh(name,bm,tile,bone)
    return plain_paint(obj) if tile==STEEL else obj


def vilkas():
    v=Vehicle('EUBOXER')
    # Two pairs of axles, inset suspension, and projecting hubs distinguish the
    # carrier from both the six-wheel ambulance and a tracked light tank.
    for i,x in enumerate((9.2,4.0,-4.0,-9.2)):
        for j,side in enumerate((1,-1)):
            number=i*2+j+1
            wheel=tire(v,number,(x,side*5.8,2.65),r=2.65,width=1.85)
            hub=v.cyl('WHEELHUB',(0,side*1.00,0),.79,.35,IRON,'Y',f'TIRE{number:02}',cap=HUB,segments=8)
            # One named wheel mesh per pivot, preserving UVs while avoiding
            # duplicate mesh identifiers and eight unnecessary runtime draws.
            n,b,_,texture,kind=v.parts[-2]
            v.parts[-2:]=[(n,b,kit.join([wheel,hub],n),texture,kind)]
            v.beam('SUSPENSION',(x-1.15,side*4.85,4.1),(x+.2,side*4.85,2.65),.32,IRON)
    v.body('LOWERHULL',[(-12.6,2.6,4.4,5.7,6.0,3.3,5.4,4.7),
        (8.8,2.6,4.4,5.7,6.0,3.3,5.4,4.7),(13.0,3.6,4.4,4.9,5.2,3.0,4.9,4.4)],IRON)
    armour(v,'ARMOUREDCORE',[(-12.45,5.2,5.7,8.4,9.15,4.5,5.65,4.75),
        (-2.8,5.2,5.7,8.4,9.15,4.5,5.65,4.75),(-1.4,5.2,5.7,7.9,8.5,4.5,5.65,4.75),
        (5.4,5.0,5.6,7.8,8.4,4.3,5.55,4.65),(12.8,4.7,5.0,5.35,5.6,3.9,5.05,4.4)])
    for side in (-1,1):
        # Three substantial chamfered armour groups replace the four identical
        # bolted cupboard doors. A recessed belt keeps the hull off the wheels.
        lo,hi=sorted((side*5.56,side*6.06))
        for x0,x1,top in ((-12.1,-7.8,8.35),(-7.55,-2.5,8.35),(-2.25,4.65,7.95)):
            prism(v,'FLANKARMOUR',[(x0,6.15),(x1-.3,6.15),(x1,6.45),(x1,top-.25),
                (x1-.35,top),(x0+.35,top),(x0,top-.25)],lo,hi)
        lo,hi=sorted((side*5.45,side*6.22))
        prism(v,'RECESSEDFENDER',[(-12.2,5.35),(6.75,5.35),(7.35,5.6),(-12.2,5.6)],lo,hi,IRON)
        for x in (9.2,4,-4,-9.2):
            lo,hi=sorted((side*5.05,side*6.95))
            prism(v,'WHEELARCH',[(x-2.85,4.7),(x-1.85,5.55),(x+1.85,5.55),(x+2.85,4.7),
                (x+2.9,5.15),(x+2.0,5.95),(x-2.0,5.95),(x-2.9,5.15)],lo,hi)
        v.house('HOUSECOLOR'+str(side),[(-11.7,side*6.08,6.4),(-8.2,side*6.08,6.4),
            (-8.2,side*6.08,7.8),(-11.7,side*6.08,7.8)])
        v.box('REARFLAP',(-12.5,side*5.7-.95,1.3),(-12.2,side*5.7+.95,4.2),IRON)
        v.beam('ROOFGRAB',(-11,side*4.75,9.4),(-8.2,side*4.75,9.4),.12,IRON)
    v.hatch('DRIVER',(3.55,2.3,8.45),1.12)
    # Three small vision blocks communicate a protected driver's station.
    for y in (1.3,2.3,3.3):
        v.box('DRIVERVISION',(4.55,y-.34,8.4),(5.0,y+.34,8.82),GLASS)
    v.box('GRILLEBASE',(1.5,-4.5,8.44),(5.1,-.55,8.65),IRON)
    v.patch('ENGINELUVRE',[(1.66,-4.32,8.68),(4.95,-4.32,8.68),(4.95,-.72,8.68),(1.66,-.72,8.68)],VENT)
    # Narrow maintenance ribs are physical fittings. The glacis itself retains
    # broad uninterrupted paint instead of a giant four-bolt square decal.
    for side in (-1,1):
        v.beam('GLACISSEAM',(6.25,side*2.6,8.15),(11.55,side*2.6,6.18),.055,IRON)
        v.beam('TOWBRACKET',(11.8,side*3.0,5.97),(12.8,side*3.0,5.6),.22,IRON)
    v.box('NOSESEAM',(11.5,-2.6,6.125),(11.6,2.6,6.235),IRON)
    v.hatch('REARHATCH',(-9.5,.0,9.18),1.65)
    stowage(v,'REARBAG',(-12,-4.15,9.2),(-8.5,-2.3,10.28))
    v.box('REARLOCKER',(-12.1,2.55,9.13),(-8.4,4.25,10.1),LOCKER,bevel=.1)
    v.patch('RAMP',[(-12.48,-3.6,5.45),(-12.48,3.6,5.45),(-12.48,3.6,8.6),(-12.48,-3.6,8.6)],DOOR)
    v.box('REARSTEP',(-13.2,-3.5,3.3),(-12.45,3.5,3.65),IRON)
    lamps(v,12.4,5.15,4.0)
    v.box('BUMPER',(12.6,-3.8,3.85),(13.35,3.8,4.45),IRON)

    # Low, wide remote turret: tapered front cheeks, separate cannon cradle,
    # twin missile canisters and the raised optical head each read as a role.
    t=v.bone('TURRET',(-3.6,0,9.15))
    v.cyl('TURRETRING',(0,0,.18),2.5,.50,IRON,bone=t,cap=HATCH)
    armour(v,'TURRETSHELL',[(-3.3,.35,.7,1.95,2.45,1.55,2.1,1.55),
        (-1.65,.35,.7,2.45,3.05,2.2,3.05,2.30),
        (1.25,.35,.65,2.1,2.6,2.15,2.85,1.95),
        (2.45,.6,.85,1.7,2.0,.65,1.2,.8)],t)
    v.box('CANNONCRADLE',(1.9,-.68,1.15),(3.6,.68,2.35),IRON,t,bevel=.14)
    v.cyl('GUNELEVATION',(2.15,0,1.75),.55,2.2,IRON,'Y',t,cap=HUB,segments=10)
    v.cyl('BARRELSLEEVE',(3.95,0,1.8),.43,2.25,STEEL,'X',t,cap=IRON,segments=8)
    v.cyl('CANNON',(5.7,0,1.8),.235,5.55,IRON,'X',t,cap=IRON,segments=8)
    v.cyl('MUZZLEBRAKE',(8.35,0,1.8),.38,.72,IRON,'X',t,cap=IRON,segments=8)
    # The two visible forward apertures make the missile launcher legible even
    # when the weapon meshes collapse to only a few pixels in the game camera.
    v.box('MISSILEMOUNT',(-2.6,2.75,.95),(.35,3.35,2.15),IRON,t)
    prism(v,'MISSILESHIELD',[(-2.7,1.0),(1.5,1.0),(1.65,2.55),(1.2,2.9),(-2.5,2.9)],3.15,4.30,STEEL,t)
    for z in (1.48,2.25):
        v.box('MISSILECANISTER',(-2.45,3.3,z-.29),(1.78,4.13,z+.29),TUBE,t)
        v.cyl('MISSILEAPERTURE',(1.8,3.73,z),.265,.12,IRON,'X',t,cap=IRON,segments=8)
    v.box('OPTICBASE',(-1.85,-1.9,2.35),(-.35,-.45,3.2),IRON,t,bevel=.1)
    prism(v,'OPTICHOOD',[(-2.0,3.03),(-.10,3.03),(.1,3.65),(-.35,3.97),(-1.8,3.97)],-1.9,-.45,STEEL,t)
    v.patch('SIGHT',[(.0,-1.72,3.2),(.0,-.63,3.2),(.11,-.63,3.6),(.11,-1.72,3.6)],GLASS,t)
    v.box('TURRETLOCKER',(-3.65,-1.5,.65),(-3.25,1.5,2.05),LOCKER,t)
    # Short launcher banks form useful dark silhouette accents, without
    # littering the roof with tiny geometry that disappears during play.
    for side in (-1,1):
        for z in (1.05,1.55,2.05):
            v.cyl('SMOKELAUNCHER',(.8,side*2.7,z),.21,.9,IRON,'X',t,cap=IRON,segments=6)
    v.bone('MUZZLE01',(8.72,0,1.8),t);v.bone('MUZZLEFX01',(8.72,0,1.8),t)
    v.beam('RADIO',(-11.6,4,10.0),(-12.1,4,14),.065)
    return v

"""Original Israel faction geometry polish. No exports, baking or gameplay changes.

Hook immediately after construction: ``asset = JOBS[name](); apply(asset)``.
The additions use the existing atlas indices and existing local bone coordinates.
No bones, wheel/track contracts, animation channels or building access paths change.
New parts are consolidated by bone/texture/kind/tile so detail does not imply hundreds
of final draw calls. Running this module directly performs geometry-only QA.
"""
import math
from pathlib import Path
import sys

import bpy
import bmesh
from mathutils import Matrix, Vector, Quaternion

SAND, PLATE, VENT, LOCKER, HATCH, HUB, RUBBER, TREAD, IRON, GLASS, TUBE, TARP, CONCRETE, CAUTION, LAMP, DOOR = range(16)


def _box(v, name, a, b, tile=SAND, bone='CHASSIS', bevel=.10):
    return v.box('P_' + name, a, b, tile, bone, bevel)


def _ring(v, name, at, outer, inner, depth, tile=IRON, bone='CHASSIS', axis='Z', segments=12):
    """A real open ring; useful for guards, raised hatches and missile mouths."""
    bm = bmesh.new()
    rot = {'Z': Matrix.Identity(4), 'X': Matrix.Rotation(math.pi / 2, 4, 'Y'),
           'Y': Matrix.Rotation(math.pi / 2, 4, 'X')}[axis]
    matrix = Matrix.Translation(at) @ rot
    rings = []
    for z, r in ((-depth / 2, outer), (depth / 2, outer), (depth / 2, inner), (-depth / 2, inner)):
        rings.append([bm.verts.new(matrix @ Vector((r * math.cos(i * math.tau / segments),
                     r * math.sin(i * math.tau / segments), z))) for i in range(segments)])
    for a, b in zip(rings, rings[1:] + rings[:1]):
        for i in range(segments):
            j = (i + 1) % segments
            bm.faces.new((a[i], a[j], b[j], b[i]))
    return v.mesh('P_' + name, bm, tile, bone)


def _rod(v, name, a, b, radius=.14, tile=IRON, bone='CHASSIS', segments=8):
    a, b = Vector(a), Vector(b)
    delta = b - a
    if delta.length < 1e-6:
        return None
    bm = bmesh.new()
    bmesh.ops.create_cone(bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius,
                          depth=delta.length, matrix=Matrix.Translation((a + b) / 2) @
                          delta.to_track_quat('Z', 'Y').to_matrix().to_4x4())
    return v.mesh('P_' + name, bm, tile, bone)


def _bolt(v, at, axis='Y', bone='CHASSIS', radius=.13):
    v.cyl('P_BOLT', at, radius, .10, IRON, axis, bone, segments=6)


def _team(v, corners, bone='CHASSIS'):
    v.patch('P_HOUSE', corners, SAND, bone)
    n, b, o, _, _ = v.parts[-1]
    tex = next((t for _, _, _, t, k in v.parts if k == 'house'), 'ilhouse.tga')
    v.parts[-1] = (n, b, o, tex, 'house')
    for loop in o.data.uv_layers.active.data:
        loop.uv = (.5, .5)


def _chevron(v, x, y, z, size=1, bone='CHASSIS'):
    """Small warm-white tactical mark, kept separate from player colour."""
    for side in (-1,1):
        corners=[(x,y,z),(x+side*1.25*size,y,z+1.15*size),
                 (x+side*1.53*size,y,z+.97*size),(x+side*.27*size,y,z-.2*size)]
        v.patch('P_CHEVRON',corners,SAND,bone)
        n,b,o,_,_=v.parts[-1]
        v.parts[-1]=(n,b,o,'il_mark.tga','decal')
        for loop in o.data.uv_layers.active.data:loop.uv=(.5,.5)


def _sensor(v, at, bone='CHASSIS', size=1, side=1):
    """Armoured EO package: deep bezel, inset glass, side thermal aperture."""
    x, y, z = at
    _box(v, 'SENSOR', (x-.65*size,y-.6*size,z), (x+.75*size,y+.6*size,z+1.05*size), IRON, bone, .12*size)
    _box(v, 'SENSORHOOD', (x-.7*size,y-.67*size,z+.88*size), (x+.95*size,y+.67*size,z+1.14*size), SAND, bone, .08*size)
    _box(v, 'SENSORGLASS', (x+.755*size,y-.43*size,z+.23*size), (x+.785*size,y+.43*size,z+.77*size), GLASS, bone, 0)
    v.cyl('P_THERMAL', (x+.83*size,y+side*.42*size,z+.49*size), .18*size, .16*size, GLASS, 'X', bone, segments=8)


def _rack(v, lo, hi, bone='CHASSIS', fabric=True):
    """A supported stowage basket with a real open frame, not a floating box."""
    x, y, z = lo
    X, Y, Z = hi
    for yy in (y, Y):
        for xx in (x, X):
            _rod(v, 'RACKPOST', (xx,yy,z), (xx,yy,Z), .10, IRON, bone)
        _rod(v, 'RACKRAIL', (x,yy,Z), (X,yy,Z), .12, IRON, bone)
        _rod(v, 'RACKRAIL', (x,yy,z), (X,yy,z), .12, IRON, bone)
    for xx in (x, X):
        _rod(v, 'RACKEND', (xx,y,Z), (xx,Y,Z), .12, IRON, bone)
    for i in range(5):
        xx = x + (X-x)*i/4
        _rod(v, 'RACKFLOOR', (xx,y,z), (xx,Y,z), .10, IRON, bone)
    if fabric:
        _box(v, 'STOWAGE', (x+.22,y+.22,z+.08), (X-.22,Y-.22,Z-.22), TARP, bone, .24)
        for f in (.3,.7):
            xx = x + (X-x)*f
            v.beam('P_STOWAGESTRAP', (xx,y+.15,Z-.15), (xx,Y-.15,Z-.15), .07, IRON, bone)


def _mg(v, at, bone='TURRET', facing=1):
    x, y, z = at
    v.cyl('P_MGPINTLE', (x,y,z+.3), .22, .6, IRON, bone=bone, segments=8)
    _box(v, 'MGRECEIVER', (x-.7,y-.25,z+.45), (x+.7,y+.25,z+.9), IRON, bone)
    _rod(v, 'MGCOOLER', (x+.4*facing,y,z+.7), (x+1.45*facing,y,z+.7), .18, IRON, bone)
    _rod(v, 'MGBARREL', (x+1.3*facing,y,z+.7), (x+3.0*facing,y,z+.7), .10, IRON, bone)
    _box(v, 'AMMOBOX', (x-.35,y+.3,z+.3), (x+.5,y+.85,z+.9), TARP, bone)
    v.beam('P_MGGRIP', (x-.65,y-.42,z+.65), (x-.65,y+.05,z+.65), .08, IRON, bone)


def _aps(v, x, y, z, side, bone='CHASSIS'):
    """Flat radar panel plus twin countermeasure launch cups, with structural supports."""
    _box(v, 'APSFOOT', (x-.8,y-.6,z-.25), (x+.8,y+.6,z+.2), IRON, bone)
    _box(v, 'APSRADAR', (x-.7,y-.46,z+.15), (x+.65,y+.46,z+1.25), SAND, bone, .14)
    _box(v, 'RADARFACE', (x-.54,y+side*.48-.03,z+.38), (x+.45,y+side*.48+.03,z+1.09), VENT, bone, 0)
    for xx in (x-.43,x+.23):
        v.cyl('P_APSTUBE', (xx,y+side*.85,z+.22), .27, .55, IRON, 'Y', bone, segments=8)
        _ring(v, 'APSCUP', (xx,y+side*1.15,z+.22), .33,.22,.13,SAND,bone,'Y',8)


def _hatch_detail(v, at, radius=1, bone='CHASSIS'):
    x, y, z = at
    _ring(v,'HATCHLIP',(x,y,z),radius+.18,radius-.10,.2,SAND,bone,segments=12)
    _box(v,'HATCHBAR',(x-.5,y-.12,z+.18),(x+.5,y+.12,z+.34),IRON,bone,.04)
    for offset in (-.6,.6):
        _box(v,'PERISCOPE',(x+.9,y+offset-.2,z+.2),(x+1.32,y+offset+.2,z+.62),IRON,bone,.05)
        _box(v,'PERIGLASS',(x+1.325,y+offset-.15,z+.31),(x+1.34,y+offset+.15,z+.53),GLASS,bone,0)


def _armoured_running_gear(v, length=12, y=8.35, z=5.0):
    """Segmented spaced side armour; leave the wheels and tread silhouette exposed."""
    for s in (-1,1):
        for i in range(5):
            x = -length+.35+i*(2*length-.7)/5
            width = (2*length-.7)/5-.17
            v.profile('P_SPACEDSKIRT',[(x,z-.2),(x+width,z-.2),(x+width-.28,z+2.1),(x+.35,z+2.35)],s*y-.18,s*y+.18,SAND)
            v.beam('P_SKIRTSEAM',(x+.2,s*(y+.21),z+.12),(x+width-.2,s*(y+.21),z+.12),.07,IRON)
            for xx in (x+.5,x+width-.5):
                _bolt(v,(xx,s*(y+.22),z+1.75))
        _team(v,[(1,s*(y+.23),z+.45),(4.8,s*(y+.23),z+.45),(4.8,s*(y+.23),z+1.25),(1,s*(y+.23),z+1.25)])
        _chevron(v,-4.8,s*(y+.24),z+.65,.7)
        _rod(v,'TOWCABLE',(-length+.7,s*6.25,5.75),(-length+5.5,s*6.25,5.75),.13,IRON)
    # The glacis stays broad; two towing brackets and spare tracks add scale.
    for s in (-1,1):
        _box(v,'TOWBRACKET',(12.6,s*4.6-.4,3.6),(13.6,s*4.6+.4,4.4),IRON)
        _ring(v,'TOWEYE',(13.75,s*4.6,4.0),.42,.22,.25,IRON,axis='X',segments=8)
    for i in range(4):
        _box(v,'SPARELINK',(4.3+i*1.1,-2.7,6.58),(5.25+i*1.1,-1.25,6.89),IRON,bevel=.07)


def _merkava(v):
    _armoured_running_gear(v)
    for s in (-1,1):
        # Several distinct wedge facets imply expensive modular armour.
        v.profile('P_CHEEKARMOUR',[(.2,1.4),(6.8,1.4),(7.6,2.0),(2.0,3.9),(.2,3.6)],s*1.55,s*5.57,PLATE,'TURRET')
        v.beam('P_CHEEKTRIM',(1.2,s*5.62,3.25),(5.7,s*5.62,1.8),.12,IRON,'TURRET')
        _aps(v,-3.0,s*5.15,2.1,s,'TURRET')
        _rack(v,(-8.8,min(s*4.7,s*1.3),1.1),(-6.6,max(s*4.7,s*1.3),3.0),'TURRET',fabric=s>0)
        # Two short antennas are less noisy than a forest of identical poles.
        _rod(v,'COMMS',(-5.0,s*3.8,3.1),(-5.1,s*3.9,5.0),.055,IRON,'TURRET',6)
    # Signature rear bustle basket and hanging anti-RPG chain fringe.
    _rack(v,(-9.0,-4.7,.9),(-7.25,4.7,2.45),'TURRET',False)
    for i in range(12):
        y = -4.25 + i*8.5/11
        bottom = -.12 + .16*(i%2)
        _rod(v,'BUSTLECHAIN',(-8.8,y,.98),(-8.8,y,bottom),.065,IRON,'TURRET',6)
        v.ellipsoid('P_CHAINWEIGHT',(-8.8,y,bottom-.16),(.18,.18,.21),IRON,'TURRET')
    _hatch_detail(v,(-2.8,2,4.34),1.1,'TURRET')
    _mg(v,(-1.0,2.05,4.0))
    _sensor(v,(.4,-1.7,3.9),'TURRET',.95)
    _box(v,'APSMAST',(-4.3,-.4,3.6),(-3.7,.4,4.7),SAND,'TURRET')
    _ring(v,'BARRELCOLLAR',(5.6,0,0),.86,.72,.65,SAND,'BARREL','X')


def _namer(v):
    _armoured_running_gear(v)
    for s in (-1,1):
        _aps(v,-2.5,s*5.0,9.4,s)
        for x in (-8.5,-4.8,.1):
            _box(v,'ROOFRAIL',(x,s*4.8-.18,9.55),(x+2.7,s*4.8+.18,9.88),IRON)
        _rack(v,(-10.2,min(s*4.3,s*2.4),9.42),(-6.8,max(s*4.3,s*2.4),10.6),fabric=True)
    _hatch_detail(v,(-6,0,9.64),1.38)
    _sensor(v,(4.6,0,9.12),size=.8)
    # Layered rear door, visible hinges, grip and guarded rear lights.
    _box(v,'RAMPRIM',(-13.48,-4,3.35),(-13.13,4,8.8),IRON,bevel=.16)
    _box(v,'RAMPARMOUR',(-13.64,-3.65,3.6),(-13.5,3.65,8.5),SAND,bevel=.14)
    for z in (4.15,7.95):
        _rod(v,'RAMPHINGE',(-13.72,-3.3,z),(-13.72,3.3,z),.14,IRON)
    _box(v,'RAMPSPLIT',(-13.75,-.09,3.8),(-13.66,.09,8.3),IRON,bevel=0)
    _rod(v,'RAMPGRIP',(-13.83,-.8,6.1),(-13.83,.8,6.1),.10,IRON)
    _box(v,'REARSTEP',(-14.15,-3.5,2.4),(-12.9,3.5,2.75),IRON)
    for s in (-1,1):
        _box(v,'REARLIGHT',(-13.35,s*5.1-.32,5.6),(-13.05,s*5.1+.32,6.5),LAMP)


def _pereh(v):
    _armoured_running_gear(v)
    _sensor(v,(-4.8,0,4.0),'TURRET',1.25)
    _mg(v,(-2.8,-3,3.2),'TURRET')
    for s in (-1,1):
        _rack(v,(-5.8,min(s*4.7,s*2.8),3.0),(-2.9,max(s*4.7,s*2.8),4.25),'TURRET')
        for x in (1,4.4):
            _box(v,'PODSTRAP',(x,s*2.5-2.1,2.95),(x+.2,s*2.5+2.1,3.25),IRON,'TURRETEL',.04)
        for y in (-1.3,0,1.3):
            for z in (.6,2):
                _ring(v,'LAUNCHMOUTH',(7.22,s*2.5+y,z),.46,.31,.27,SAND,'TURRETEL','X',8)
        _rod(v,'PODPISTON',(-3.6,s*3.7,1.0),(2,s*3.7,3.1),.20,IRON,'TURRET')
    _hatch_detail(v,(-2,1.5,3.2),.95,'TURRET')


def _truck(v):
    # Reinforced door lower panels do not cover the inherited team-colour bands.
    for s in (-1,1):
        _box(v,'DOORLOWER',(6,s*4.53-.11,4.05),(10.15,s*4.53+.11,4.84),SAND)
        _rod(v,'DOORGRAB',(6.6,s*4.72,6.58),(7.7,s*4.72,6.58),.11,IRON)
        _box(v,'DOORHINGE',(9.9,s*4.63-.08,5.2),(10.3,s*4.63+.08,6.4),IRON,'CHASSIS',.04)
        for z in (2.6,3.35):
            _box(v,'CABSTEP',(5.15,s*5.2-.48,z),(7.45,s*5.2+.48,z+.22),IRON,bevel=.06)
        _rod(v,'STEPRAIL',(5.25,s*5.2,2.5),(5.25,s*5.2,5.1),.13,IRON)
        _box(v,'MUDGUARD',(-10.8,s*5.1-.82,.55),(-10.56,s*5.1+.82,3.6),RUBBER,bevel=.02)
        _rod(v,'FUELTANK',(-1.8,s*3.55,3.0),(2.8,s*3.55,3.0),.65,SAND,segments=10)
    _box(v,'BUMPER',(12.7,-4.8,3.7),(13.5,4.8,4.25),IRON,bevel=.12)
    for s in (-1,1):
        _ring(v,'TOWEYE',(13.58,s*3.7,4.0),.34,.20,.18,IRON,axis='X',segments=8)
        _rod(v,'LIGHTGUARD',(13.20,s*3.5-.6,5.15),(13.20,s*3.5+.6,5.15),.07,IRON)
    _box(v,'ROOFHATCH',(6.7,-1.8,10.33),(9.2,1.8,10.52),PLATE,bevel=.15)
    _sensor(v,(7.6,2.5,10.33),size=.65)
    _rod(v,'EXHAUST',(5.0,-3.8,4.0),(5.0,-3.8,10.9),.18,IRON)


def _drop_parts(v, names, bone):
    retained = []
    for p in v.parts:
        if p[0] in names and p[1] == bone:
            bpy.data.objects.remove(p[2],do_unlink=True)
        else:
            retained.append(p)
    v.parts = retained


def _launcher(v, air_defence):
    _truck(v)
    _drop_parts(v, {'POD','PODCAP'}, 'TURRETEL')
    for s in (-1,1):
        _box(v,'CRADLESIDE',(-2,s*4.65-.2,0),(3,s*4.65+.2,2.8),IRON,'TURRET')
        v.cyl('P_ELEVATIONAXLE',(-1,s*4.8,1.4),.68,.6,SAND,'Y','TURRET',segments=10)
        _rod(v,'ELEVATIONRAM',(-3,s*4.2,.2),(2.5,s*4.2,2.8),.25,SAND,'TURRET')
    if air_defence:
        # Individual guided-missile canisters, tall cross-section and exposed truss.
        # Front launches stay near the established local x=10.3 weapon bones.
        for y in (-3.55,-1.18,1.18,3.55):
            _box(v,'GUIDEDCANISTER',(-.2,y-.96,.28),(10,y+.96,3.3),SAND,'TURRETEL',.25)
            _box(v,'CANISTERSEAM',(-.3,y-.7,3.30),(10.1,y+.7,3.50),IRON,'TURRETEL',.04)
            _box(v,'CANISTEREND',(10.02,y-.89,.38),(10.27,y+.89,3.18),PLATE,'TURRETEL',.15)
            _ring(v,'GUIDEDMOUTH',(10.3,y,1.73),.75,.60,.20,IRON,'TURRETEL','X',10)
            for x in (1.0,7.7):
                _box(v,'CANISTERCLAMP',(x,y-1.03,.17),(x+.28,y+1.03,.42),IRON,'TURRETEL',.04)
                _box(v,'CANISTERCLAMP',(x,y-1.03,3.12),(x+.28,y+1.03,3.43),IRON,'TURRETEL',.04)
        for s in (-1,1):
            _rod(v,'RADARBRACE',(-9,s*1.4,5),(-8,s*.65,12),.15,IRON)
        _sensor(v,(-8.1,0,14.95),size=.9)
        for s in (-1,1):
            _box(v,'RADAREAR',(-8.65,s*2.1-.45,12.2),(-7.3,s*2.1+.45,14.2),SAND,bevel=.14)
        _box(v,'CONTROLBOX',(-11,-3.4,4.45),(-7,-1.2,6.6),VENT)
    else:
        # Wide rocket crates: nine deep mouths per pod and obvious reinforcing ribs.
        for s in (-1,1):
            _box(v,'ROCKETCRATE',(-.5,s*2.35-2.15,-.55),(10,s*2.35+2.15,3.85),SAND,'TURRETEL',.15)
            _box(v,'ROCKETFRONT',(10.02,s*2.35-1.97,-.33),(10.14,s*2.35+1.97,3.64),IRON,'TURRETEL',0)
            for y in (-1.28,0,1.28):
                for z in (.38,1.55,2.72):
                    _ring(v,'ROCKETMOUTH',(10.27,s*2.35+y,z),.49,.35,.30,SAND,'TURRETEL','X',8)
            for x in (1.2,5,8.8):
                _box(v,'CRATERIB',(x,s*2.35-2.26,3.76),(x+.32,s*2.35+2.26,4.12),IRON,'TURRETEL',.04)
            for x in (1.2,8.8):
                _box(v,'SIDECLAMP',(x,s*4.58-.12,-.35),(x+.3,s*4.58+.12,3.8),IRON,'TURRETEL',.04)
        _rack(v,(-12.5,-4.3,4.45),(-9.3,-2.2,5.6))
    for s in (-1,1):
        _box(v,'STABILIZER',(-11.5,s*4.6-.35,2.4),(-10.3,s*4.6+.35,5.1),SAND)
        _box(v,'STABFOOT',(-12,s*4.6-.75,2.3),(-9.8,s*4.6+.75,2.65),IRON)


def _sandcat(v):
    for s in (-1,1):
        # Deep window armour frames, separated door faces and robust side steps.
        for x in (-5,-1):
            _box(v,'DOORARMOUR',(x+.2,s*3.98-.09,4.45),(x+2.92,s*3.98+.09,6.2),SAND,bevel=.16)
            _rod(v,'DOORSEAM',(x-.15,s*4.05,4.45),(x-.15,s*4.05,8.45),.055,IRON)
            for xx in (x+.45,x+2.65):_bolt(v,(xx,s*4.1,4.77),radius=.10)
            _box(v,'WINDOWHOOD',(x-.2,s*3.92-.16,8.55),(x+3.2,s*3.92+.16,8.88),SAND)
        _box(v,'RUNNINGBOARD',(-3.6,s*4.15-.42,2.48),(3.8,s*4.15+.42,2.77),IRON)
        _rod(v,'REARGRIP',(-8.0,s*3.87,4.7),(-8.0,s*3.87,7.3),.12,IRON)
        _box(v,'ROOFBRACKET',(-4.6,s*2.55-.25,9),(-3.9,s*2.55+.25,9.45),IRON)
    _rack(v,(-7.4,-2.35,9.1),(-4.5,2.35,10.3))
    _sensor(v,(0,0,2.02),'TURRET',.62)
    _box(v,'GUNSHIELD',(.6,-1.45,.6),(1.0,1.45,2.25),SAND,'TURRET',.15)
    _ring(v,'SPARESTRAP',(-9.85,0,5.2),1.8,1.58,.17,SAND,axis='X',segments=12)
    for y in (-2.9,2.9):
        _rod(v,'BULLBAR',(10.63,y,2.9),(10.63,y,4.8),.17,IRON)
    _rod(v,'BULLBAR',(10.63,-3.3,4.8),(10.63,3.3,4.8),.17,IRON)
    _box(v,'SKIDPLATE',(9.55,-2.4,1.93),(10.5,2.4,2.3),IRON)
    for s in (-1,1):
        _team(v,[(.2,s*4.12,4.9),(2.55,s*4.12,4.9),(2.55,s*4.12,5.45),(.2,s*4.12,5.45)])
        _chevron(v,-3.4,s*4.13,4.95,.42)


def _d9(v):
    # External protection cage and vent depth give the armoured cab an unmistakable silhouette.
    for s in (-1,1):
        for x in (-6.3,-3.7,-1.1):
            _rod(v,'CABBAR',(x,s*3.78,7.8),(x,s*3.78,11.25),.12,IRON)
        for z in (7.8,11.25):_rod(v,'CABCAGE',(-6.45,s*3.78,z),(-.7,s*3.78,z),.15,SAND)
        _rod(v,'CABGRAB',(-7.12,s*3.0,6),(-7.12,s*3.0,10),.13,IRON)
        _box(v,'CABSTEP',(-8.15,s*3.1-.65,4.1),(-6.9,s*3.1+.65,4.45),IRON)
        _rod(v,'LIFTCYLINDER',(2.0,s*3.4,5.3),(7.1,s*5.7,4.3),.40,SAND,segments=10)
        _rod(v,'LIFTROD',(7.0,s*5.7,4.3),(10.6,s*7.0,3.7),.20,IRON)
        v.cyl('P_LIFTPIN',(10.6,s*7,3.7),.47,.85,IRON,'Y',segments=10)
        _box(v,'ENGINEVENT',(1.2,s*3.58-.1,5),(5.5,s*3.58+.1,7.3),VENT)
        for x in (1.5,2.6,3.7,4.8):_rod(v,'VENTLOUVER',(x,s*3.73,5.25),(x,s*3.73,7.1),.085,SAND)
    for y in (-5.5,0,5.5):
        v.profile('P_BLADERIB',[(10.05,1.0),(10.5,1.0),(9.4,5.8),(9.1,6.5),(9.6,6.5)],y-.22,y+.22,IRON)
    for y in (-7.8,-5.2,-2.6,0,2.6,5.2,7.8):
        v.profile('P_BLADETOOTH',[(12.7,.7),(14.15,.13),(14.35,.45),(13.0,1.35)],y-.4,y+.4,IRON)
    _sensor(v,(-5.8,-2.3,12.03),size=.6)
    _box(v,'ROOFSLAB',(-6.6,-3.8,11.96),(-.7,3.8,12.35),SAND,bevel=.2)
    for s in (-1,1):_rod(v,'WORKLIGHTBAR',(-.7,s*2.6,12.25),(.45,s*2.6,12.25),.13,IRON)


def _supply(v):
    _truck(v)
    for s in (-1,1):
        for x in (-11.2,-7,-2.8,1.4):
            _box(v,'BEDUPRIGHT',(x,s*4.83-.18,4.5),(x+.3,s*4.83+.18,7.05),SAND,bevel=.05)
            _rod(v,'TIEDOWN',(x+.1,s*4.98,6.5),(x+.1,s*4.98,8.6),.06,IRON)
        _box(v,'SIDERAIL',(-12.4,s*4.9-.15,6.7),(3.5,s*4.9+.15,7.0),IRON,bevel=.04)
    _box(v,'TAILGATE',(-13.22,-4.65,4.5),(-13.0,4.65,6.3),PLATE)
    for y in (-3.3,0,3.3):_rod(v,'TAILGATEHINGE',(-13.36,y-.45,4.5),(-13.36,y+.45,4.5),.13,IRON)
    _box(v,'REARSTEP',(-13.8,-3,3.4),(-12.6,3,3.7),IRON)
    _rack(v,(-12.2,-2.5,9.08),(-9.0,2.5,10.25))


def _aircraft(v):
    if v.name=='ILAPACH':
        _sensor(v,(14.2,0,1.4),size=1.25)
        v.ellipsoid('P_NOSEOPTIC',(16.8,0,3.2),(1.05,1.4,1.2),IRON)
        _box(v,'NOSELENS',(17.72,-.65,2.8),(17.85,.65,3.7),GLASS,bevel=.06)
        _rod(v,'RADARSTALK',(-1,0,9.6),(-1,0,11.25),.22,IRON)
        v.cyl('P_LONGBOW',(-1,0,11.65),2.6,.85,SAND,segments=12)
        _ring(v,'RADARLIP',(-1,0,11.72),2.7,2.5,.14,IRON,segments=12)
        for s in (-1,1):
            _box(v,'ENGINEVENT',(-7,s*3.1-.8,7.15),(-2,s*3.1+.8,7.45),VENT)
            _rod(v,'GEARBRACE',(3.5,s*2.4,3.2),(7,s*4,.8),.14,IRON)
            _rod(v,'CANOPYFRAME',(3,s*2.46,6.0),(5.2,s*2.35,8.5),.11,SAND)
            _box(v,'CHAFF',(-9,s*1.55-.4,4.1),(-7,s*1.55+.4,5.1),VENT)
        return
    f15 = v.name=='ILF15'
    length=23 if f15 else 20
    for s in (-1,1):
        # Separated control surfaces, robust pylon root fairings and defensive sensors.
        _rod(v,'WINGROOT',(2,s*3.5,4.07),(-10,s*5.3,4.07),.055,IRON)
        _rod(v,'AIRBRAKE',(-7,s*4.5,5.6),(-11,s*4.5,5.6),.065,IRON)
        _box(v,'PYLONROOT',(-5.8,s*7-.55,3.25),(-2.6,s*7+.55,3.65),SAND,bevel=.16)
        _box(v,'CHAFF',(-length+5,s*2.4-.42,2.1),(-length+8,s*2.4+.42,2.45),VENT)
        _sensor(v,(0,s*3.1,4.8),size=.35)
        if f15:
            _ring(v,'NOZZLERIM',(-length-1.18,s*1.9,3.3),1.47,1.20,.25,IRON,axis='X',segments=12)
            _box(v,'INTAKELIP',(5.9,s*3.3-1.05,2),(6.25,s*3.3+1.05,4.8),SAND,bevel=.08)
            _box(v,'INTAKESHADOW',(6.26,s*3.3-.8,2.3),(6.29,s*3.3+.8,4.5),IRON,bevel=0)
            _rod(v,'FINSEAM',(-length+2,s*3.76,6),(-length+4,s*3.76,10.6),.055,IRON)
        else:
            _box(v,'CHEEK',(6.5,s*2.05-.35,3.7),(9,s*2.05+.35,4.5),SAND,bevel=.2)
    _rod(v,'PITOT',(length-.3,0,3.6),(length+1.7,0,3.6),.07,IRON,segments=6)
    if not f15:
        _ring(v,'EXHAUST',(-22.55,0,3.6),1.74,1.4,.3,IRON,axis='X',segments=12)
        _box(v,'INTAKELIP',(4.7,-1.72,1.47),(5.2,1.72,1.78),SAND,bevel=.1)
    # One canopy bow, not a repeated window-frame texture on every loft face.
    for s in (-1,1):_rod(v,'CANOPYBOW',(7,s*1.52,6.1),(7,s*.15,7.77),.075,SAND)


def _infantry(v):
    for y in (-.65,0,.65):
        _box(v,'MAGPOUCH',(.97,y-.27,4.05),(1.25,y+.27,4.8),TARP,bevel=.10)
        _box(v,'POUCHFLAP',(1.22,y-.29,4.57),(1.28,y+.29,4.80),TARP,bevel=.04)
    _box(v,'BELT',(-.62,-1.04,3.65),(.82,1.04,3.84),IRON,bevel=.07)
    for s in (-1,1):
        _box(v,'BELTPOUCH',(-.4,s*.95-.23,3.43),(.15,s*.95+.23,4.10),TARP,bevel=.12)
        _rod(v,'SHOULDERWEB',(-.3,s*.76,5.65),(.86,s*.76,4.90),.10,IRON)
        _box(v,'RADIO',(-1.33,s*.54-.23,4.65),(-1.14,s*.54+.23,5.30),IRON,bevel=.06)
    _rod(v,'RADIOANT',(-1.30,.6,5.1),(-1.30,.6,6.3),.035,IRON,segments=6)
    if v.name!='ILCOMM':
        # Exaggerated cloth helmet cover: an irregular soft rim, not another hard sphere.
        bm=bmesh.new();rings=[];N=12
        for z,r in ((6.60,.68),(6.82,.88),(7.13,.61)):
            rings.append([bm.verts.new((-.08+r*math.cos(i*math.tau/N)*(1+.1*math.cos(3*i*math.tau/N)),
                         r*math.sin(i*math.tau/N),z+.07*math.sin(i*math.tau*5/N))) for i in range(N)])
        bm.faces.new(list(reversed(rings[0])));bm.faces.new(rings[-1])
        for a,b in zip(rings,rings[1:]):
            for i in range(N):bm.faces.new((a[i],a[(i+1)%N],b[(i+1)%N],b[i]))
        v.mesh('P_HELMETCLOTH',bm,TARP)
    else:
        _box(v,'NVGMOUNT',(.42,-.18,6.79),(.65,.18,7.03),IRON,bevel=.04)
        _box(v,'KNIFESHEATH',(-.22,-1.13,3.35),(.11,-.91,4.45),IRON,bevel=.08)
    if v.name=='ILSPIKE':
        _rod(v,'LAUNCHERSTRAP',(.1,-.62,.82),(2.5,-.62,.82),.055,IRON,'ARMS')
        _box(v,'SIGHTHOOD',(1.92,-1.18,.78),(2.78,-.77,1.13),SAND,'ARMS',.04)


def _barrier(v,x,y,length=10,along='X'):
    # Tapered concrete security blocks, deliberately kept off production lanes.
    if along=='X':v.profile('P_BARRIER',[(x,1.15),(x+length,1.15),(x+length-.5,3.8),(x+.5,3.8)],y-.85,y+.85,CONCRETE)
    else:
        obj=v.profile('P_BARRIER',[(0,1.15),(length,1.15),(length-.5,3.8),(.5,3.8)],-.85,.85,CONCRETE)
        transform=Matrix.Translation((x,y,0))@Matrix.Rotation(math.pi/2,4,'Z')
        obj.data.transform(transform)
    for d in (length*.25,length*.75):
        xx,yy=(x+d,y) if along=='X' else (x,y+d)
        _box(v,'BARRIERREFLECTOR',(xx-.3,yy-.9,2.4),(xx+.3,yy-.88,3.0),CAUTION,bevel=0)


def _service(v,x,y,z):
    _box(v,'SERVICEBOX',(x-2.4,y-2,z),(x+2.4,y+2,z+3.5),SAND,bevel=.18)
    _box(v,'SERVICEDOOR',(x+2.42,y-1.75,z+.25),(x+2.5,y+1.75,z+3.2),VENT,bevel=0)
    _rod(v,'CONDUIT',(x-2.5,y-2.1,z+.5),(x-2.5,y-2.1,z+4.7),.20,IRON)
    _rod(v,'CONDUIT',(x-2.5,y-2.1,z+4.7),(x+1,y-2.1,z+4.7),.20,IRON)


def _roof_sensor(v,x,y,z):
    _box(v,'SENSORPLINTH',(x-2,y-2,z),(x+2,y+2,z+1.0),CONCRETE)
    v.cyl('P_SENSORPED',(x,y,z+2.3),.5,3,IRON,segments=8)
    _sensor(v,(x,y,z+3.3),size=1.8)


def _building(v):
    footprints={'ILCMD':(60,62),'ILPOWER':(34,32),'ILBARR':(48,41),'ILSUPPLY':(44,43),
                'ILFACT':(54,60),'ILAIR':(112,74),'ILTECH':(49,46),'ILINCOME':(43,42),
                'ILGDEF':(17,17),'ILADEF':(17,17),'ILSUPER':(57,52)}
    L,W=footprints[v.name]
    if v.name in ('ILGDEF','ILADEF'):
        _ring(v,'BUNKERAPRON',(0,0,1.7),14.4,11.9,1.1,CONCRETE,segments=8)
        _ring(v,'BUNKERCAP',(0,0,7.7),13.55,10.8,.65,SAND,segments=8)
        for s in (-1,1):
            _box(v,'ARMOURPANEL',(-7,s*11.65-.23,3.5),(7,s*11.65+.23,6.0),SAND,bevel=.2)
            _team(v,[(-4,s*11.94,4),(4,s*11.94,4),(4,s*11.94,5),(-4,s*11.94,5)])
            _sensor(v,(-1.8,s*3.8,3.6),'TURRET',.7)
        _box(v,'ACCESSHATCH',(-13.5,-2.6,1.5),(-13.1,2.6,5.8),DOOR)
        for y in (-3.3,3.3):_rod(v,'HATCHGRIP',(-13.65,y,2.8),(-13.65,y,5.7),.12,IRON)
        for y in (-2.4,0,2.4):
            if v.name=='ILGDEF':_ring(v,'SPIKEMOUTH',(7.24,y,1.7),.86,.63,.24,IRON,'TURRETEL','X',10)
        return
    # Three reinforced rear corners, leaving every +X production exit and dock apron clear.
    for y in (-W+3,W-3):
        _barrier(v,-L+3,y,12)
    _barrier(v,-L+3,-W+6,10,'Y')
    for y in (-W+4,W-4):
        _box(v,'PERIMETERPOST',(-L+2,y-.5,1.2),(-L+3,y+.5,6.0),SAND)
        _box(v,'POSTLIGHT',(-L+2.15,y-.35,6),(-L+2.85,y+.35,6.55),LAMP)
    if v.name=='ILCMD':
        _roof_sensor(v,11,8,19.7)
        _service(v,-40,-13,20.0)
        for z in (7,17,25):_ring(v,'TOWERBAND',(-29,-43,z),12.3,11.65,.7,SAND,segments=8)
        for y in (-16,19):_box(v,'BUTTRESS',(-43.8,y-.8,2),(-41.5,y+.8,18.2),SAND)
        _box(v,'RADARSHROUD',(-37,-51,33.8),(-21,-35,35.4),SAND,bevel=.5)
    elif v.name=='ILPOWER':
        for x in (-20,-8,4):
            _ring(v,'GENERATORGUARD',(x,14,14.7),5.7,4.9,.4,IRON,segments=12)
            for s in (-1,1):_rod(v,'SERVICEPIPE',(x,s*2+14,3),(x,s*2+14,14.5),.15,IRON)
        _service(v,-25,-26,1.3)
        _roof_sensor(v,4,-11,14.8)
    elif v.name=='ILBARR':
        _roof_sensor(v,-22,-16,13.7)
        for y in (-17,7,20):_box(v,'WINDOWVISOR',(-2.7,y-2.5,9.1),(-1,y+2.5,9.6),SAND)
        for x in (7,19):_barrier(v,x,32,8)
        _service(v,-31,-33,1.3)
        for y in (2,14):
            _box(v,'GATEARMOUR',(34.0,y-.5,1.3),(36.0,y+.5,7.8),SAND)
    elif v.name=='ILSUPPLY':
        _roof_sensor(v,-20,0,28.8)
        _service(v,33,29,1.3)
        for y in (-24,23):
            _box(v,'DOORFRAME',(-3.1,y-1.0,1.4),(-1.3,y+1.0,14.8),SAND)
        for x in (5,17):_barrier(v,x,-35,9)
    elif v.name=='ILFACT':
        # Heavy door surround and overhead service rails frame the clear exit opening.
        for y in (-45,-15):_box(v,'PORTALJAMB',(35.3,y-.8,1.3),(39.0,y+.8,19.4),SAND)
        _box(v,'PORTALHEADER',(35.3,-46,19.1),(39,-14,21),SAND)
        for y in (-43,-17):_rod(v,'DOORRAIL',(39.13,y,2),(39.13,y,18.5),.16,IRON)
        _service(v,-30,52,1.3)
        _roof_sensor(v,6,34,15.7)
        _rod(v,'CRANEBOOM',(-30,20,20),(-5,20,20),.4,IRON)
    elif v.name=='ILAIR':
        # Low revetments are behind hangars, never across parking-to-runway paths.
        for x in (-38,-6):_barrier(v,x,71,28)
        for y in (-62,-26):_barrier(v,-110,y,28,'Y')
        for z in (8,19,27):_ring(v,'TOWERARMOUR',(92,48,z),7.6,6.8,.55,SAND,segments=8)
        _roof_sensor(v,92,48,29)
        _service(v,37,65,1.3)
        for y in (-49,-13):
            for x in (-40,99):
                _box(v,'RUNWAYCHEVRON',(x,y-9,1.38),(x+1.2,y+9,1.45),LAMP,bevel=0)
    elif v.name=='ILTECH':
        _roof_sensor(v,15,2,18.7)
        _service(v,-32,30,13)
        _ring(v,'DOMEGUARD',(-10,-8,22.8),10.7,9.9,.55,IRON,segments=16)
        for y in (-31,16):_box(v,'LABBUTTRESS',(-36,y-1,2),(-32,y+1,18.1),SAND)
    elif v.name=='ILINCOME':
        _roof_sensor(v,-20,-20,17.7)
        _service(v,-29,33,1.3)
        _box(v,'VAULTFRAME',(13.15,-24,1.5),(13.55,-15,10.3),IRON)
        _box(v,'VAULT',(13.58,-23.3,2),(13.85,-15.7,9.6),PLATE)
        _ring(v,'VAULTLOCK',(14,-19.5,5.7),1.0,.7,.18,IRON,axis='X',segments=12)
    elif v.name=='ILSUPER':
        for x in (4,29):
            _ring(v,'SILOARMOUR',(x,-9,5.5),10.9,9.3,.5,SAND,segments=16)
            for s in (-1,1):_box(v,'SILOMOTOR',(x-12.4,s*11-10,2),(x-10.5,s*11-7.5,5),VENT)
        _roof_sensor(v,-32,-20,17.7)
        _service(v,32,33,10.8)


def _consolidate(v, originals):
    """Join only newly authored parts; original meshes and their hide/scroll names survive."""
    import engineer as kit
    keep=[];groups={}
    for p in v.parts:
        if p[2] in originals:
            keep.append(p)
        else:
            n,b,o,t,k=p
            tile=int(o.get('israel_material_tile',SAND))
            groups.setdefault((b,t,k,tile),[]).append(o)
    for i,((bone,texture,kind,tile),objects) in enumerate(groups.items()):
        name=('HOUSECOLORP' if kind=='house' else 'POLISH')+str(i)
        obj=kit.join(objects,name) if len(objects)>1 else objects[0]
        obj.name=name
        obj['israel_material_tile']=tile
        keep.append((name,bone,obj,texture,kind))
    v.parts=keep


def apply(asset):
    """Add the whole original geometry pass; returns the same asset, without exporting it."""
    if getattr(asset,'_israel_geometry_polished',False):
        return asset
    bones_before=list(asset.bones)
    originals={p[2] for p in asset.parts}
    jobs={'ILSAND':_sandcat,'ILMERK':_merkava,'ILNAMER':_namer,'ILPEREH':_pereh,
          'ILSPYDR':lambda v:_launcher(v,True),'ILPULS':lambda v:_launcher(v,False),
          'ILD9':_d9,'ILSUPTR':_supply}
    if asset.name in jobs:
        jobs[asset.name](asset)
    elif asset.category=='aircraft':
        _aircraft(asset)
    elif asset.category=='infantry':
        _infantry(asset)
    elif asset.category=='building':
        _building(asset)
    else:
        raise ValueError('No Israel polish recipe for '+asset.name)
    _consolidate(asset,originals)
    assert asset.bones==bones_before, 'Polish changed a gameplay/animation bone'
    asset._israel_geometry_polished=True
    return asset


if __name__=='__main__':
    # Geometry-only validation: no finish(), texture writes, W3D or blend exports.
    import json
    here=Path(__file__).resolve().parent
    sys.path.insert(0,str(here))
    import build
    from blender_kit import mesh_data
    names=sys.argv[sys.argv.index('--')+1:] if '--' in sys.argv else list(build.JOBS)
    report=[]
    for name in names:
        bpy.ops.wm.read_factory_settings(use_empty=True)
        v=build.JOBS[name]()
        before=sum(len(mesh_data(o)['tris']) for _,_,o,_,_ in v.parts)
        bones=list(v.bones)
        apply(v)
        after=sum(len(mesh_data(o)['tris']) for _,_,o,_,_ in v.parts)
        assert all(math.isfinite(c) for _,_,o,_,_ in v.parts for vert in o.data.vertices for c in vert.co)
        assert v.bones==bones
        assert after<=12000,(name,after)
        assert all(b=='CHASSIS' or b in {n for n,_,_,_ in bones} for _,b,_,_,_ in v.parts)
        snapshot=len(v.parts);apply(v);assert len(v.parts)==snapshot
        report.append(dict(model=name,before=before,after=after,added=after-before,bones_unchanged=True,parts=len(v.parts)))
    print('ISRAEL_GEOMETRY_QA '+json.dumps(report),flush=True)

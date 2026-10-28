"""Original Wiesel TOW with readable running gear and an open launcher cradle.

The compact vehicle keeps the established faction atlas and all engine bone
contracts. Its geometry and model-specific UV projection are authored here;
no stock model or texture is used.
"""
import math
import json
from pathlib import Path
import bmesh
from mathutils import Matrix, Vector

from original_compacts import Vehicle, lamps, TRACK, BUILD, ROOT
from original_compacts import STEEL, IRON, PLATE, VENT, GLASS, TARP, TUBE, HATCH, HUB
import engineer as kit
import puls


class Wiesel(Vehicle):
    def finish(self):
        super().finish()
        path=BUILD/(self.name+'_provenance.json')
        provenance=json.loads(path.read_text())
        provenance.update(builder=str(Path(__file__).relative_to(ROOT)),
                          exporter='scripts/models/original_compacts.py',
                          refinements=['Open track loops and recessed load wheels',
                                       'Tapered fenders and suspended running gear',
                                       'Open TOW cradle, muzzle sleeve and thermal optic',
                                       'Vehicle-specific continuous panel UV projection'])
        path.write_text(json.dumps(provenance,indent=2)+'\n')

    def beam(self, name, start, end, width=.18, tile=IRON, bone='CHASSIS'):
        # Unlike the older X/Z helper, suspension braces also cross the hull.
        a,b=Vector(start),Vector(end)
        direction=b-a
        rotation=direction.to_track_quat('Z','Y').to_matrix().to_4x4()
        matrix=Matrix.Translation((a+b)/2)@rotation@Matrix.Diagonal((2*width,2*width,direction.length,1))
        bm=bmesh.new()
        bmesh.ops.create_cube(bm,size=1,matrix=matrix)
        return self.mesh(name,bm,tile,bone)

    def mesh(self, name, bm, tile=STEEL, bone='CHASSIS', cap_axis=None,
             cap_tile=None, recalc=True):
        obj = super().mesh(name, bm, tile, bone, cap_axis, cap_tile, recalc)
        if tile == STEEL:
            # One projection across each panel group instead of repeating the
            # complete welded plate on every narrow triangle and chamfer.
            verts = [v.co for v in obj.data.vertices]
            uv = obj.data.uv_layers.active
            for poly in obj.data.polygons:
                axis = max(range(3), key=lambda i: abs(poly.normal[i]))
                if axis == cap_axis and cap_tile is not None:
                    continue
                axes = {0: (1, 2), 1: (0, 2), 2: (0, 1)}[axis]
                lo = [min(p[a] for p in verts) for a in axes]
                hi = [max(p[a] for p in verts) for a in axes]
                # Thin fittings borrow the clean center of the paint tile;
                # broad hull plates retain its deliberate edge highlights.
                inset = .06 if max(hi[i]-lo[i] for i in range(2)) > 3 else .32
                for li in poly.loop_indices:
                    co = obj.data.vertices[obj.data.loops[li].vertex_index].co
                    u = (co[axes[0]]-lo[0])/max(.001, hi[0]-lo[0])
                    v = (co[axes[1]]-lo[1])/max(.001, hi[1]-lo[1])
                    uv.data[li].uv = ((inset+u*(1-2*inset))/4,
                                      1-(1-inset-v*(1-2*inset))/4)
        return obj


def _tube_ring(v, name, x, radius, inner_radius, width, z, tile, bone):
    """An open sleeve, so the missile tube has a recessed muzzle at game scale."""
    bm = bmesh.new()
    loops = []
    segments=8
    for xx, r in ((x-width/2, radius), (x+width/2, radius),
                  (x+width/2, inner_radius), (x-width/2, inner_radius)):
        loops.append([bm.verts.new((xx, math.cos(i*math.tau/segments)*r,
                                   z+math.sin(i*math.tau/segments)*r)) for i in range(segments)])
    for a, b in zip(loops, loops[1:]+loops[:1]):
        for i in range(segments):
            bm.faces.new((a[i], a[(i+1)%segments], b[(i+1)%segments], b[i]))
    return v.mesh(name, bm, tile, bone)


def _running_gear(v):
    # The thin loop leaves daylight around the large load wheels. The earlier
    # solid side slab concealed their depth and made the vehicle read as a sled.
    profile = [(-7.3,.22), (5.8,.22), (7.85,1.7), (7.8,2.65),
               (6.7,3.65), (-6.75,3.50), (-8.05,2.45), (-8.05,1.35)]
    inner = [(-7.10,.60), (5.68,.60), (7.46,1.85), (7.42,2.48),
             (6.57,3.27), (-6.61,3.12), (-7.67,2.27), (-7.67,1.55)]
    for side in (-1, 1):
        band = puls.tread_band('TREADSL' if side > 0 else 'TREADSR',
                               side, profile, (3.32, 5.50))
        v.parts.append((band.name, 'CHASSIS', band, TRACK, 'track'))
        bm = bmesh.new()
        for y in (side*3.34, side*5.48):
            a = [bm.verts.new((x,y,z)) for x,z in profile]
            b = [bm.verts.new((x,y,z)) for x,z in inner]
            for i in range(len(a)):
                bm.faces.new((a[i],a[(i+1)%len(a)],b[(i+1)%len(b)],b[i]))
        v.mesh('TRACKSIDE', bm, IRON)
        v.box('SUSPENSIONBACK',(-6.8,side*3.70-.13,1.0),
              (6.65,side*3.70+.13,2.90),IRON)
        wheels = [(-6.7,1.94,1.08),(-3.65,1.77,1.39),
                  (-.20,1.77,1.39),(3.25,1.77,1.39),(6.5,2.10,1.13)]
        for i,(x,z,r) in enumerate(wheels):
            v.beam('SWINGARM',(x-.8,side*4.2,2.8),
                   (x,side*4.55,z),.23,IRON)
            v.cyl('ROADRUBBER',(x,side*4.60,z),r,.91,
                  IRON,'Y',cap=IRON,segments=10)
            v.cyl('WHEELDISH',(x,side*5.09,z),r*.86,.14,
                  STEEL,'Y',cap=HUB,segments=10)
            v.cyl('HUBCAP',(x,side*5.19,z),r*.32,.20,
                  IRON,'Y',cap=HUB,segments=6)
        # The chamfered mudguards stop before the high nose of the tracks.
        # Their narrow outer lip exposes the track run in the top-down view.
        bm = bmesh.new()
        lo,hi = sorted((side*3.45,side*5.18))
        kit.prism_xz(bm,[(-7.72,3.48),(5.95,3.62),(7.28,3.08),
                         (7.32,3.42),(6.04,3.96),(-7.72,3.82)],lo,hi)
        v.mesh('MUDGUARD',bm,STEEL)
        for x in (-5.4,.2,4.8):
            v.beam('FENDERBRACE',(x,side*3.57,4.18),
                   (x,side*5.08,3.96),.12,IRON)
        v.box('REARMUDFLAP',(-7.81,lo,.64),(-7.66,hi,3.39),IRON)


def _launcher(v):
    t = v.bone('Turret',(-2.45,-.48,5.23))
    v.cyl('TOWBEARING',(0,0,.10),1.35,.23,IRON,bone=t,cap=HATCH)
    v.cyl('TOWPEDESTAL',(0,0,.42),.62,.53,STEEL,bone=t,cap=IRON)
    # Substantial triangular open cheeks make the mounting understandable
    # without turning the light weapon carrier into a miniature tank turret.
    for side in (-1,1):
        bm=bmesh.new()
        lo,hi=sorted((side*.62,side*.91))
        kit.prism_xz(bm,[(-.85,.54),(.62,.54),(.55,2.05),(-.18,2.05)],lo,hi)
        v.mesh('TRUNNIONCHEEK',bm,STEEL,t)
        v.cyl('PIVOTCAP',(.21,side*.99,1.70),.38,.20,
              IRON,'Y',t,cap=HUB,segments=12)
    v.beam('CRADLEBASE',(-1.35,0,1.85),(1.38,0,1.85),.35,IRON,t)
    v.cyl('MISSILETUBE',(.56,0,2.63),.79,6.45,TUBE,'X',t,cap=IRON)
    for x in (-2.48,2.85):
        _tube_ring(v,'LAUNCHCOLLAR',x,.94,.78,.30,2.63,IRON,t)
    # The forward lip projects beyond the dark end cap, leaving a visible bore.
    _tube_ring(v,'MUZZLESLEEVE',3.75,.94,.69,.60,2.63,IRON,t)
    v.cyl('RECESSEDBORE',(3.47,0,2.63),.66,.025,IRON,'X',t,cap=IRON)
    # Two strong straps read at distance; a rib also clarifies the tube length.
    for x in (-1.65,1.65):
        _tube_ring(v,'TUBESTRAP',x,.83,.79,.16,2.63,STEEL,t)
    v.beam('TUBERAIL',(-2.25,0,3.42),(3.28,0,3.42),.12,TUBE,t)
    v.box('OPTICSARM',(-.95,.7,1.36),(.95,1.92,1.63),IRON,t)
    v.box('THERMALBODY',(-1.30,1.10,1.62),(1.03,2.38,2.69),STEEL,t,bevel=.10)
    v.box('OPTICHOOD',(.95,1.02,1.54),(1.49,2.47,2.77),IRON,t)
    v.patch('THERMALLENS',[(1.51,1.17,1.71),(1.51,2.31,1.71),
                          (1.51,2.31,2.60),(1.51,1.17,2.60)],GLASS,t)
    # The rear eyepiece and hand grips give the exposed weapon a human scale.
    v.cyl('EYEPIECE',(-1.6,1.76,2.18),.31,.68,IRON,'X',t,cap=GLASS,segments=8)
    for y in (-.85,.85):
        v.beam('AIMGRIP',(-1.05,y,.80),(-1.52,y,1.22),.17,IRON,t)
    v.bone('TurretMS',(4.10,0,2.63),t)
    v.bone('TurretFX',(4.10,0,2.63),t)
    v.bone('Barrel',parent=t)


def wiesel_polished():
    v=Wiesel('EUWIEST')
    _running_gear(v)
    v.body('HULL',[(-7.8,1.36,2.86,4.60,4.96,2.50,3.73,3.20),
                   (-4.0,1.24,2.86,4.60,5.00,2.60,3.83,3.25),
                   (1.7,1.24,2.83,4.46,4.89,2.60,3.78,3.20),
                   (5.35,1.48,2.78,3.49,3.88,2.44,3.63,3.13),
                   (7.87,2.10,2.73,2.96,3.14,2.20,3.48,2.94)])
    # The asymmetrical hood and single broad engine grille are the strongest
    # small-scale identification features besides the exposed TOW launcher.
    bm=bmesh.new()
    kit.prism_xz(bm,[(.0,4.82),(4.95,3.86),(4.20,5.38),
                     (2.71,5.98),(.0,5.98)],.44,3.21)
    v.mesh('DRIVERHOOD',bm,STEEL)
    v.hatch('DRIVERHATCH',(1.26,1.82,6.02),1.02)
    v.box('DRIVERPERISCOPE',(2.78,.78,5.87),(3.50,2.95,6.18),IRON)
    v.patch('DRIVERVISION',[(3.52,.92,5.95),(3.52,2.80,5.95),
                           (3.52,2.80,6.12),(3.52,.92,6.12)],GLASS)
    grille_stations=[(-.25,5.03),(1.72,4.96),(4.65,4.15)]
    for (x,z),(xx,zz) in zip(grille_stations,grille_stations[1:]):
        v.patch('ENGINEGRILLE',[(x,-3.10,z),(xx,-3.10,zz),
                               (xx,-.24,zz),(x,-.24,z)],VENT)
        for y in (-3.16,-.18):
            v.beam('GRILLEEDGE',(x,y,z+.02),(xx,y,zz+.02),.075,STEEL)
    v.patch('GLACISPANEL',[(5.12,-2.86,3.99),(7.59,-2.76,3.26),
                          (7.59,2.76,3.26),(5.12,2.86,3.99)],PLATE)
    for side in (-1,1):
        # Long uninterrupted faction stripe, with the surrounding plate kept
        # quiet so the tiny unit can still be read as the player's vehicle.
        v.house('HOUSECOLOR'+str(side),[(-7.42,side*3.86,3.85),
                (-3.45,side*3.86,3.85),(-3.45,side*3.86,4.45),(-7.42,side*3.86,4.45)])
        v.patch('HULLACCESS',[(-2.9,side*3.85,3.17),(.7,side*3.82,3.17),
                              (.7,side*3.82,4.35),(-2.9,side*3.85,4.35)],PLATE)
        v.beam('HULLGRAB',(-6.70,side*3.48,4.79),(-5.55,side*3.48,4.79),.14,IRON)
    v.box('REARAMMOBOX',(-7.47,-3.05,5.02),(-4.55,-.54,5.62),STEEL,bevel=.08)
    v.patch('AMMOLID',[(-7.26,-2.88,5.65),(-4.73,-2.88,5.65),
                       (-4.73,-.72,5.65),(-7.26,-.72,5.65)],PLATE)
    v.house('HOUSECOLORROOF',[(-7.05,-2.58,5.68),(-4.93,-2.58,5.68),
                             (-4.93,-2.10,5.68),(-7.05,-2.10,5.68)])
    v.box('REARPACK',(-7.31,1.60,5.02),(-5.01,3.11,5.78),TARP,bevel=.17)
    v.cyl('SPAREMISSILE',(-3.86,2.86,5.45),.46,4.5,TUBE,'X',cap=IRON)
    for x in (-5.52,-2.16):
        v.cyl('SPARESTRAP',(x,2.86,5.45),.52,.20,IRON,'X',cap=IRON)
    v.hatch('GUNNER',(-2.44,-.45,5.03),1.38)
    v.cyl('EXHAUST',(-4.45,-3.92,4.74),.40,3.42,IRON,'X',cap=IRON)
    for x in (-5.59,-3.25):
        v.cyl('EXHAUSTBAND',(x,-3.92,4.74),.46,.15,STEEL,'X',cap=IRON)
    v.cyl('EXHAUSTTIP',(-6.02,-3.92,4.96),.23,.71,IRON,cap=IRON)
    lamps(v,7.28,3.34,2.75)
    v.box('NOSERAIL',(7.90,-2.43,2.22),(8.27,2.43,2.51),IRON)
    for side in (-1,1):
        v.beam('TOWBRACKET',(7.57,side*2.34,2.62),(8.22,side*2.34,2.96),.24,IRON)
    v.beam('AERIAL',(-7.04,-2.73,5.73),(-7.62,-2.73,10.05),.055,IRON)
    _launcher(v)
    return v

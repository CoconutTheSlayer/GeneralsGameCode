"""Original Valuk ambulance: continuous medical hull and six-wheel running gear.

All geometry is authored here. The common compact atlas is only a paint source;
the exported model receives its own diffuse/occlusion bake and damage variant.
"""
import bmesh
from original_compacts import Vehicle, tire, lamps
from original_compacts import STEEL, IRON, VENT, GLASS, TARP, MEDICAL, HUB, DOOR
import engineer as kit
from compact_polish_common import stowage


def wheel_arch(v, x, side):
    """A narrow armoured brow, with a dark open well behind each tire."""
    y0,y1=sorted((side*5.08,side*6.55))
    profile=[(x-3.00,4.25),(x-2.30,5.70),(x+2.25,5.70),(x+3.0,4.25),
             (x+2.80,4.31),(x+2.12,5.39),(x-2.15,5.39),(x-2.80,4.31)]
    bm=bmesh.new();kit.prism_xz(bm,profile,y0,y1)
    v.mesh('WHEELBROW',bm,STEEL)
    # The top return is dark rather than a solid slab filling the wheel opening.
    v.beam('ARCHSHADOW',(x-2.1,side*5.15,5.28),(x+2.1,side*5.15,5.28),.23,IRON)


def valuk_polished():
    v=Vehicle('EUVALUK')
    # Keep the existing compact footprint and all six animated-wheel contracts.
    for i,x in enumerate((7.20,-.65,-7.70)):
        v.cyl('AXLE',(x,0,2.8),.36,10.3,IRON,'Y',cap=IRON,segments=8)
        for j,side in enumerate((-1,1)):
            tire(v,i*2+j+1,(x,side*5.63,2.70),r=2.63,width=1.88)
            wheel_arch(v,x,side)

    # One continuous wedge carries the elevated treatment space into the driving
    # position; there is no separate box perched on the carrier roof.
    v.body('MEDICALHULL',[
        (-11.1,3.1,4.35,8.85,9.65,3.45,5.13,4.28),
        (-8.0,2.75,4.35,8.85,9.65,3.55,5.22,4.30),
        (-2.25,2.65,4.35,8.85,9.65,3.55,5.22,4.30),
        (1.25,2.65,4.35,8.05,8.85,3.55,5.22,4.25),
        (4.05,2.7,4.35,7.30,8.08,3.55,5.16,4.18),
        (7.70,2.85,4.35,5.25,6.00,3.4,4.95,4.1),
        (11.05,3.40,4.1,4.65,4.80,3.1,4.50,4.05),
    ])
    # Strong nose undercut and slim front tow fittings; omit the oversized
    # decorative bolted plate that previously dominated the bonnet.
    v.box('FRONTBUMPER',(10.70,-4.15,3.45),(11.55,4.15,3.88),IRON)
    lamps(v,11.20,4.22,3.38)
    for side in (-1,1):
        v.beam('TOWEYE',(10.95,side*2.1,3.65),(11.6,side*2.1,3.65),.24,STEEL)
        # A low towing rail defines the waist and separates paint from running gear.
        v.beam('LOWERRETURN',(-10.65,side*5.25,5.55),(3.90,side*5.2,5.55),.18,IRON)
        v.box('REARFLAP',(-10.8,side*5.61-.83,1.4),(-10.53,side*5.61+.83,4.4),IRON)

    # Driver is offset to the right; the engine remains on the left. Recessed
    # sights and a split grille give two distinct readable functional shapes.
    v.hatch('DRIVER',(2.52,2.05,8.55),1.07)
    v.box('SIGHTFRAME',(3.37,.92,8.17),(4.0,3.15,8.58),IRON)
    v.patch('DRIVERSCOPE',[(4.025,1.07,8.24),(4.025,2.98,8.24),
                           (4.025,2.98,8.51),(4.025,1.07,8.51)],GLASS)
    v.patch('ENGINELOUVRE',[(.95,-3.65,8.94),(3.48,-3.65,8.29),
                            (3.48,-.55,8.29),(.95,-.55,8.94)],VENT)
    v.beam('ENGINESEAM',(4.24,-3.60,7.99),(6.20,-3.60,6.87),.10,IRON)
    v.beam('ENGINESEAM',(4.24,-.60,7.99),(6.20,-.60,6.87),.10,IRON)
    for side in (-1,1):
        v.beam('DRIVERGRAB',(1.15,side*4.28,8.93),(2.15,side*4.27,8.65),.14,IRON)

    # White/green rescue markings are flush to the medical hull. Large marks on
    # roof and flanks are legible from game height without extra signboard boxes.
    v.patch('MEDROOF',[(-9.60,-2.72,9.68),(-3.15,-2.72,9.68),
                       (-3.15,2.72,9.68),(-9.60,2.72,9.68)],MEDICAL)
    for side in (-1,1):
        v.patch('MEDSIDE',[(-9.45,side*5.245,6.12),(-4.24,side*5.245,6.12),
                           (-4.24,side*5.245,8.62),(-9.45,side*5.245,8.62)],MEDICAL)
        # Cab access and a broad player-colour band remain distinct from markings.
        v.patch('ACCESSDOOR',[(-1.77,side*5.25,6.05),(.82,side*5.25,6.05),
                              (.82,side*5.25,7.73),(-1.77,side*5.25,8.30)],DOOR)
        v.house('HOUSECOLOR'+str(side),[(1.25,side*5.26,6.08),(3.91,side*5.20,6.08),
                                       (3.91,side*5.20,6.85),(1.25,side*5.26,7.10)])
        v.beam('ROOFGRAB',(-9.9,side*3.94,9.93),(-7.7,side*3.94,9.93),.14,IRON)
        for x in (-9.9,-7.7):v.beam('GRABFOOT',(x,side*3.94,9.65),(x,side*3.94,9.93),.12,IRON)
    v.house('HOUSEROOF',[(-2.05,-3.7,9.63),(-.78,-3.7,9.34),
                         (-.78,-2.65,9.34),(-2.05,-2.65,9.63)])

    # A slim protected light bar and one folded rescue stretcher provide medical
    # equipment without covering the identification panel or adding a roof box.
    v.box('LIGHTBARBASE',(-1.22,-2.45,9.42),(-.61,2.45,9.63),IRON)
    v.box('LIGHTBAR',(-1.16,-2.32,9.63),(-.66,2.32,10.03),GLASS)
    stowage(v,'STRETCHER',(-9.78,-4.08,9.74),(-4.80,-3.05,10.20))
    for y in (-4.12,-3.0):
        v.beam('STRETCHERPOLE',(-10.10,y,9.88),(-4.53,y,9.88),.13,STEEL)
    v.box('AIRFILTER',(-10.42,2.53,9.64),(-8.75,3.63,10.07),STEEL,bevel=.15)
    v.patch('FILTERTOP',[(-10.28,2.64,10.09),(-8.90,2.64,10.09),
                        (-8.90,3.50,10.09),(-10.28,3.50,10.09)],VENT)

    # The rear opens as two full-height patient doors, with an obvious step.
    v.patch('REARLEFT',[(-11.13,-3.95,4.55),(-11.13,-.10,4.55),
                        (-11.13,-.10,8.9),(-11.13,-3.95,8.9)],DOOR)
    v.patch('REARRIGHT',[(-11.14,.10,4.55),(-11.14,3.95,4.55),
                         (-11.14,3.95,8.9),(-11.14,.10,8.9)],DOOR)
    v.beam('DOORSEAM',(-11.19,0,4.48),(-11.19,0,8.96),.11,IRON)
    v.box('PATIENTSTEP',(-11.8,-3.66,3.5),(-11.06,3.66,3.8),IRON)
    for side in (-1,1):
        v.beam('REARGRAB',(-11.27,side*4.36,6.85),(-11.27,side*4.36,8.05),.14,IRON)
        for z in (5.2,8.2):v.box('HINGE',(-11.26,side*3.70-.20,z-.18),(-11.05,side*3.70+.20,z+.18),IRON)
    v.cyl('EXHAUST',(-.80,-5.35,7.05),.28,2.35,IRON,'X',cap=IRON,segments=8)
    v.cyl('AERIALFOOT',(-10.10,3.82,9.79),.22,.35,IRON,segments=8)
    v.beam('AERIAL',(-10.10,3.82,9.9),(-10.52,3.82,12.0),.055,IRON)
    return v

"""Compact coalition vehicles, using the established EU armour and running gear.

Shapes and fittings are exaggerated just enough to read from the Generals camera.
Shared details use one small atlas; articulated parts keep the game's original bones.
"""
import math
import bmesh
from mathutils import Vector
import engineer as kit
import w3d
from blender_kit import box, cylinder


DETAILS = {'steel':0, 'rubber':1, 'glass':2, 'lamp':3, 'red':4, 'amber':5,
           'medical':6, 'tarp':7, 'grille':8, 'hazard':9, 'olive':10, 'black':11}


def detail(a, name, bm, material='steel', bone='CHASSIS'):
    obj=a.mesh(name,bm,bone=bone,texture='eucompact_detail.tga')
    uv=obj.data.uv_layers.active
    tile=DETAILS[material]; u0=(tile%4)/4; v0=1-(tile//4+1)/4
    # Independent face projection keeps a lens, vent or panel legible without stretching.
    for poly in obj.data.polygons:
        normal=poly.normal; drop=max(range(3),key=lambda i:abs(normal[i]))
        axes=[i for i in range(3) if i!=drop]
        if drop==0:axes=[1,2]
        points=[obj.data.vertices[obj.data.loops[li].vertex_index].co for li in poly.loop_indices]
        lo=[min(p[i] for p in points) for i in axes]; hi=[max(p[i] for p in points) for i in axes]
        for li,p in zip(poly.loop_indices,points):
            u=(p[axes[0]]-lo[0])/max(.01,hi[0]-lo[0]); v=(p[axes[1]]-lo[1])/max(.01,hi[1]-lo[1])
            uv.data[li].uv=(u0+.012+u*.226,v0+.012+v*.226)
    return obj


def panel(a,name,points,material='glass',bone='CHASSIS'):
    bm=bmesh.new();bm.faces.new([bm.verts.new(p) for p in points])
    # Surface patches must survive the engine's back-face culling on either side
    # of a mirrored hull. Give each face its own reversed vertices and normals.
    bm.faces.new([bm.verts.new(p) for p in reversed(points)])
    return detail(a,name,bm,material,bone)


def armour(a,name,bm,part='hull',bone='CHASSIS',bevel=.10):
    bmesh.ops.recalc_face_normals(bm,faces=bm.faces)
    if bevel:kit.bevel_sharp(bm,bevel)
    return a.mesh(name,bm,part,bone=bone)


def shell(bm,sections):
    """An eight-sided armoured body: belly, lower slope, side wall and roof chamfer."""
    rings=[]
    for x,bottom,waist,shoulder,roof,belly,width,top in sections:
        yz=[(-belly,bottom),(-width,waist),(-width,shoulder),(-top,roof),
            (top,roof),(width,shoulder),(width,waist),(belly,bottom)]
        rings.append([bm.verts.new((x,y,z)) for y,z in yz])
    bm.faces.new(list(reversed(rings[0])));bm.faces.new(rings[-1])
    for left,right in zip(rings,rings[1:]):
        for i in range(8):bm.faces.new((left[i],left[(i+1)%8],right[(i+1)%8],right[i]))


def hatch(a,name,at,r=1.5,bone='CHASSIS'):
    x,y,z=at; bm=bmesh.new()
    cylinder(bm,(x,y,z),r+.13,.16,segments=12)
    detail(a,name+'RIM',bm,'rubber',bone)
    bm=bmesh.new();cylinder(bm,(x,y,z+.16),r,.22,segments=12)
    box(bm,(x-r-.1,y-.35,z+.1),(x-r+.5,y+.35,z+.4))
    armour(a,name,bm,'hatches',bone,bevel=.055)
    bm=bmesh.new();kit.tube(bm,(x-.4,y,z+.35),(x+.4,y,z+.35),.09)
    detail(a,name+'HANDLE',bm,'steel',bone)


def grille(a,name,lo,hi):
    bm=bmesh.new();box(bm,lo,hi);detail(a,name,bm,'grille')


def lights(a,x,z,width):
    bm=bmesh.new()
    for s in (-1,1):box(bm,(x-.25,s*width-.65,z-.4),(x+.35,s*width+.65,z+.45))
    detail(a,'LAMPHOUSING',bm)
    for s in (-1,1):
        panel(a,'HEADLAMP'+str(s),[(x+.36,s*width-.43,z-.24),(x+.36,s*width+.43,z-.24),
                                   (x+.36,s*width+.43,z+.25),(x+.36,s*width-.43,z+.25)],'lamp')


def carrier(Asset,name,ambulance):
    a=Asset(name);bm=bmesh.new()
    # Valuk has a low sloped nose and a raised medical compartment. Patria's
    # distinct forward driving cabin and short bonnet avoid two identical boxes.
    if ambulance:
        sections=[(-13,3,4.3,8.2,9.1,4.1,5.75,4.8),(-10,2.9,4.3,8.4,9.2,4.2,5.85,4.8),
                  (4,2.9,4.3,8.4,9.2,4.2,5.85,4.8),(9,3,4.3,6.4,7.1,4.1,5.6,4.6),
                  (13,3.5,4.4,4.9,5.3,3.6,5.05,4.5)]
    else:
        sections=[(-13,3,4.4,8.1,9,4,5.8,4.8),(-8,2.9,4.4,8.2,9.1,4.1,5.9,4.8),
                  (4.5,2.9,4.4,8.2,9.1,4.1,5.9,4.8),(7.3,3,4.4,8.9,9.6,4.1,5.8,4.8),
                  (10.3,3.2,4.5,6.2,6.7,4,5.5,4.5),(13.3,3.5,4.5,4.9,5.3,3.5,4.9,4.3)]
    shell(bm,sections);armour(a,'HULL',bm,bevel=.14)
    # Wheel wells read as dark recesses, with broad armoured fenders above them.
    wheel_x=(8,-.5,-9)
    for i,x in enumerate(wheel_x):
        for j,s in enumerate((1,-1)):a.wheel(i*2+j+1,(x,s*5.9,2.65),2.65,1.85)
    bm=bmesh.new()
    for s in (-1,1):
        for x in wheel_x:
            y0,y1=sorted((s*5.5,s*6.7))
            kit.prism_xz(bm,[(x-3.15,4.7),(x-2.15,5.5),(x+2.15,5.5),(x+3.15,4.7),
                             (x+3.15,5),(x+2.2,5.85),(x-2.2,5.85),(x-3.15,5)],y0,y1)
    armour(a,'FENDERS',bm,'fenders',bevel=.06)
    bm=bmesh.new()
    for s in (-1,1):
        for x in (-11.8,-3.4,5.1):box(bm,(x,s*6.55,2.2),(x+.45,s*6.7,4.8))
        # Passenger door and raised equipment locker interrupt the side armour.
        y0,y1=sorted((s*5.91,s*6.05))
        kit.prism_xz(bm,[(-5.4,5.6),(-1.5,5.6),(-1.5,8),(-5.4,8)],y0,y1)
    armour(a,'SIDEFITTINGS',bm,'fittings',bevel=.06)
    bm=bmesh.new()
    for s in (-1,1):
        for z in (5.7,7.6):box(bm,(-5.5,s*6.08,z),(-4.9,s*6.18,z+.2))
        kit.tube(bm,(-2.8,s*6.16,7.3),(-2.0,s*6.16,7.3),.09)
        kit.tube(bm,(-7,s*5.2,9.1),(-2,s*5.2,9.1),.10)
        for x in (-7,-2):kit.tube(bm,(x,s*5.2,8.65),(x,s*5.2,9.1),.10)
    detail(a,'HANDRAILS',bm)
    # Front bumper, tow shackles and readable headlamps.
    bm=bmesh.new();box(bm,(12.8,-4.8,3.2),(13.8,4.8,3.75))
    for s in (-1,1):
        kit.tube(bm,(13.8,s*3.3,3.5),(14.2,s*3.3,4.1),.22)
        box(bm,(-13.35,s*4.4-.4,5),(-13.05,s*4.4+.4,5.6))
    detail(a,'BUMPER',bm);lights(a,12.6,4.95,3.9)
    # Dark, inset driver's glazing sits on the actual sloped armour plane.
    for s in (-1,1):
        y0,y1=sorted((s*.5,s*3.4))
        if ambulance:
            panel(a,'WINDSCREEN'+str(s),[(5.2,y0,8.75),(5.2,y1,8.75),(7.0,y1,8.0),(7.0,y0,8.0)])
        else:
            panel(a,'WINDSCREEN'+str(s),[(7.75,y0,9.18),(7.75,y1,9.18),(9.6,y1,7.38),(9.6,y0,7.38)])
        # Rear lamps.
        panel(a,'REARLIGHT'+str(s),[(-13.36,s*4.4-.28,5.1),(-13.36,s*4.4+.28,5.1),
                                   (-13.36,s*4.4+.28,5.45),(-13.36,s*4.4-.28,5.45)],'red')
    # Rear loading ramp, hinge and steps.
    bm=bmesh.new();box(bm,(-13.15,-3.6,4.15),(-12.98,3.6,8.15))
    armour(a,'REARRAMP',bm,'ramp',bevel=.04)
    bm=bmesh.new();cylinder(bm,(-13.25,0,4.25),.22,7.4,axis='Y',segments=8)
    box(bm,(-13.75,-2.7,3.1),(-13.1,2.7,3.4))
    detail(a,'RAMPHINGE',bm)
    hatch(a,'DRIVERHATCH',(3.1,2.3,9.25),1.2)
    grille(a,'ENGINEVENT',(-1.5,-4.4,9.14),(3,-1.4,9.3))
    bm=bmesh.new();cylinder(bm,(-8.5,-4.2,9.7),.4,3,axis='X',segments=10)
    detail(a,'EXHAUST',bm)
    if ambulance:
        bm=bmesh.new();shell(bm,[(-11.7,8.9,9.3,10.3,10.8,4.2,4.65,4.2),(-2.5,8.9,9.3,10.3,10.8,4.2,4.65,4.2)])
        armour(a,'MEDICALCAB',bm,'cab',bevel=.1)
        hatch(a,'ROOFHATCH',(-7.2,0,10.95),1.65)
        # Roof and side markings remain visible from the normal game view.
        panel(a,'MEDROOF',[(-5.5,-2,10.94),(-2.9,-2,10.94),(-2.9,2,10.94),(-5.5,2,10.94)],'medical')
        for s in (-1,1):
            panel(a,'MEDSIDE'+str(s),[(-10.8,s*5.91,6),(-6.8,s*5.91,6),(-6.8,s*5.91,8.7),(-10.8,s*5.91,8.7)],'medical')
        bm=bmesh.new();box(bm,(-1.1,-1.5,9.45),(-.2,1.5,9.9));detail(a,'RESCUELIGHT',bm,'amber')
    else:
        hatch(a,'PASSENGERHATCH',(-8,0,9.2),1.7)
        a.bone('Turret',at=(-1,1.0,9.2));a.bone('Muzzle','Turret',(5.7,0,2.8))
        bm=bmesh.new();cylinder(bm,(0,0,.3),1.65,.6,segments=12)
        kit.prism_xz(bm,[(-1.5,.5),(1.3,.5),(1.6,1.1),(.8,2.4),(-1.4,2.4)],-.8,.8)
        box(bm,(-1.5,-2.1,.7),(.4,-.85,1.7));armour(a,'GUNSTATION',bm,'turret','Turret')
        bm=bmesh.new();box(bm,(-.5,-.4,2.35),(1.9,.4,3.15))
        cylinder(bm,(3.6,0,2.8),.26,3.8,axis='X',segments=8)
        cylinder(bm,(5.4,0,2.8),.36,.6,axis='X',segments=8)
        detail(a,'MACHINEGUN',bm,'steel','Turret')
        panel(a,'GUNSIGHT',[(1.62,.85,1.4),(1.62,1.6,1.4),(1.62,1.6,2.1),(1.62,.85,2.1)],'glass','Turret')
    bm=bmesh.new()
    for s in (-1,1):
        cylinder(bm,(-10,s*3.8,10.0 if ambulance else 9.4),.25,.4,segments=8)
        kit.tube(bm,(-10,s*3.8,10.1 if ambulance else 9.5),(-10.8,s*3.8,14 if ambulance else 13.5),.07)
    detail(a,'ANTENNAS',bm)
    a.colours(-4.7,-.8,6.25,7.05,6.11)
    return a


def tracked(Asset,name,mv4):
    import wiesel
    a=Asset(name)
    # Keep the well-established animated track belt, but separate tyres, hubs and
    # hull paint so the running gear does not read as a single camouflaged slab.
    for s in (1,-1):
        obj=wiesel.tread_band('TREADSL' if s==1 else 'TREADSR',s,wiesel.TRACK_PROFILE,wiesel.TRACK_Y)
        a.pieces.append((obj.name,'CHASSIS',obj,'euwie_tread.tga','solid'))
    rubber=bmesh.new();hubs=bmesh.new()
    for s in (-1,1):
        for x,z,r in wiesel.WHEELS:
            cylinder(rubber,(x,s*4.8,z),r,2.45,axis='Y',segments=12)
            cylinder(hubs,(x,s*6.05,z),r*.62,.18,axis='Y',segments=10)
            cylinder(hubs,(x,s*6.18,z),r*.25,.20,axis='Y',segments=8)
    detail(a,'RUNNINGGEAR',rubber,'rubber');armour(a,'WHEELHUBS',hubs,'running',bevel=0)
    bm=bmesh.new()
    shell(bm,[(-9.8,1.1,3.2,4.9,5.55,3.1,4.7,4.3),(-6,1.1,3.2,5.1,5.7,3.1,4.7,4.2),
              (4,1.1,3.2,5.1,5.7,3.1,4.7,4.2),(9.8,2.2,3.5,3.8,4.1,3,4.5,4)])
    armour(a,'CHASSIS',bm,bevel=.12)
    bm=bmesh.new()
    for s in (-1,1):
        y0,y1=sorted((s*4.5,s*6.35))
        kit.prism_xz(bm,[(-9.7,3.25),(9.9,3.25),(9.4,3.65),(-9.2,3.65)],y0,y1)
    armour(a,'TRACKGUARDS',bm,'fenders',bevel=.04)
    lights(a,9.6,4.0,3.7)
    if mv4:
        # A separate remotely operated engine body, with no crew hatch or tank roof.
        bm=bmesh.new();shell(bm,[(-8,5.5,5.8,7.7,8.2,3.5,3.7,3.2),
                                (-3,5.5,5.8,7.7,8.2,3.5,3.7,3.2),(1.5,5.5,5.8,6.5,7.2,3.5,3.7,3.2)])
        armour(a,'ENGINE',bm,'engine');grille(a,'ENGINETOP',(-6.8,-2.6,8.24),(-3.1,2.6,8.4))
        grille(a,'ENGINEFRONT',(1.55,-2.8,5.9),(1.7,2.8,6.6))
        bm=bmesh.new()
        for s in (-1,1):
            kit.beam(bm,(1,s*5.0,4.7),(12,s*5.0,2.6),.55,.5)
            cylinder(bm,(2,s*5.0,4.4),.85,1.4,axis='Y',segments=10)
        armour(a,'LIFTARMS',bm,'arms',bevel=.08)
        bm=bmesh.new()
        for s in (-1,1):
            kit.tube(bm,(-1,s*4.65,6),(5.8,s*4.65,4.4),.33)
            kit.tube(bm,(5.8,s*4.65,4.4),(10,s*4.65,3.25),.18)
            # Hydraulic hoses curve back to the machine.
            for p,q in [((-2,s*4.1,6.2),(0,s*4.4,6.7)),((0,s*4.4,6.7),(3,s*4.7,5.3))]:kit.tube(bm,p,q,.14)
        detail(a,'HYDRAULICS',bm)
        bm=bmesh.new();kit.prism_xz(bm,[(10,3.2),(10.5,5.3),(13.5,5.3),(14.4,4.2),(14.1,3.8),(12.9,4.6),(11.1,4.6),(10.8,3.2)],-6.6,6.6)
        armour(a,'FLAILSHIELD',bm,'shield',bevel=.09)
        panel(a,'CAUTION',[(10.52,-5.8,5.32),(13.45,-5.8,5.32),(13.45,5.8,5.32),(10.52,5.8,5.32)],'hazard')
        a.bone('FLAIL',at=(12.4,0,2.3),rotation=(.70710678,0,0,.70710678));a.spins['FLAIL']=2
        bm=bmesh.new();cylinder(bm,(0,0,0),1.15,12.3,axis='Z',segments=12)
        for i,z in enumerate(range(-5,6)):
            angle=i*.83
            for off in (0,math.pi):
                x,y=math.cos(angle+off),math.sin(angle+off)
                kit.tube(bm,(x,y,z),(x*2.0,y*2.0,z),.12,6)
                box(bm,(x*2-.27,y*2-.27,z-.25),(x*2+.27,y*2+.27,z+.25))
        detail(a,'FLAILDRUM',bm,'steel','FLAIL')
        bm=bmesh.new();cylinder(bm,(-1,0,7.7),.33,1.2,segments=10);box(bm,(-1.6,-.8,8.2),(-.3,.8,9.1))
        armour(a,'CAMERA',bm,'fittings');panel(a,'CAMERALENS',[(-.28,-.55,8.35),(-.28,.55,8.35),(-.28,.55,8.95),(-.28,-.55,8.95)])
        a.colours(-7,-3,6.4,7.2,3.75)
    else:
        hatch(a,'DRIVER',(3,2.0,5.85),1.15)
        hatch(a,'GUNNER',(-4,0,5.85),1.7)
        grille(a,'ENGINEDECK',(4.2,-3.9,5.3),(7,-1.15,5.48))
        # The cylindrical TOW tube, cradle and bulky thermal sight are the main
        # silhouette. Dark end caps make it read as a launcher rather than a vent.
        a.bone('Turret',at=(-3,0,5.8));bm=bmesh.new()
        cylinder(bm,(0,0,.45),1.05,.9,segments=12)
        for s in (-1,1):kit.prism_xz(bm,[(-1.4,.8),(1.3,.8),(.9,2.9),(-1.1,2.9)],s*1.1,s*1.45)
        box(bm,(-1.5,-2.6,2.1),(1.5,-1.3,3.7));armour(a,'LAUNCHERMOUNT',bm,'turret','Turret')
        bm=bmesh.new();cylinder(bm,(.6,0,3.2),.83,8.5,axis='X',segments=12)
        for x in (-3.4,-1.7,2.8,4.6):cylinder(bm,(x,0,3.2),.97,.28,axis='X',segments=12)
        detail(a,'TOWTUBE',bm,'olive','Turret')
        bm=bmesh.new()
        for x in (-3.68,4.88):cylinder(bm,(x,0,3.2),.75,.06,axis='X',segments=12)
        detail(a,'TOWENDS',bm,'black','Turret')
        panel(a,'THERMALSIGHT',[(1.53,-2.5,2.4),(1.53,-1.4,2.4),(1.53,-1.4,3.5),(1.53,-2.5,3.5)],'glass','Turret')
        a.bone('TurretMS','Turret',(5.0,0,3.2));a.bone('Barrel','Turret');a.bone('TurretFX','Turret',(5.0,0,3.2))
        # Spare missile canister is stowed on the hull side, with retaining straps.
        bm=bmesh.new();cylinder(bm,(-4,-4.95,5.0),.65,7,axis='X',segments=10)
        detail(a,'SPARETOW',bm,'olive')
        bm=bmesh.new()
        for x in (-6.3,-1.8):cylinder(bm,(x,-4.95,5.0),.73,.24,axis='X',segments=10)
        kit.tube(bm,(-8.2,3.4,5.9),(-8.9,3.4,11.2),.07)
        box(bm,(-9.9,-3.1,4.1),(-9.3,1.9,5.35));detail(a,'STOWAGE',bm,'steel')
        a.colours(-7,-1,4.1,4.9,4.75)
    return a

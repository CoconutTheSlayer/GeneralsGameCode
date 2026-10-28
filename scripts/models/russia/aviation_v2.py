"""Original Russia aviation detail, retaining original skeleton and weapon hooks."""
import math
import bmesh
from mathutils import Matrix,Vector
STEEL,PLATE,VENT,LOCKER,HATCH,HUB,RUBBER,TREAD,IRON,GLASS,TUBE,TARP,CONCRETE,CAUTION,LAMP,DOOR=range(16)

def ring(a,name,at,radius,inner,depth,axis='X',bone='CHASSIS'):
 bm=bmesh.new();rot={'X':Matrix.Rotation(math.pi/2,4,'Y'),'Z':Matrix.Identity(4)}[axis];m=Matrix.Translation(at)@rot;N=16;rings=[]
 for z,r in ((-depth/2,radius),(depth/2,radius),(depth/2,inner),(-depth/2,inner)):
  rings.append([bm.verts.new(m@Vector((r*math.cos(i*math.tau/N),r*math.sin(i*math.tau/N),z))) for i in range(N)])
 for first,second in zip(rings,rings[1:]+rings[:1]):
  for i in range(N):bm.faces.new((first[i],first[(i+1)%N],second[(i+1)%N],second[i]))
 return a.mesh(name,bm,IRON,bone)

def ell(a,name,at,radii,tile=STEEL,bone='CHASSIS'):
 bm=bmesh.new();bmesh.ops.create_uvsphere(bm,u_segments=16,v_segments=10,radius=1,matrix=Matrix.Translation(at)@Matrix.Diagonal((*radii,1)));o=a.mesh(name,bm,tile,bone)
 for p in o.data.polygons:p.use_smooth=True
 return o

def seam(a,name,start,end,w=.04,tile=IRON,bone='CHASSIS'):a.beam(name,start,end,w,tile,bone)

def apply(a):
 if getattr(a,'_aviation_v2',False):return
 a._aviation_v2=True;bones=list(a.bones)
 if a.name!='RUMI28':
  attack=a.name=='RUSU25';front=2.1 if attack else 5.1;ey=2.9 if attack else 3.5
  for s in (-1,1):
   # Rolled lips and recessed compressor faces create real depth in the intakes.
   ring(a,'INTAKELIP',(front+.23,s*ey,3.9),1.3,1.05,.34)
   ring(a,'EXHAUSTLIP',(-19.65,s*(2.8 if attack else 3.5),3.1),1.13,.81,.4)
   a.cyl('NOZZLECORE',(-19.72,s*(2.8 if attack else 3.5),3.1),.48,.1,IRON,'X',segments=12)
   for i in range(12):
    angle=i*math.tau/12;yy=s*(2.8 if attack else 3.5)+math.cos(angle)*1.08;zz=3.1+math.sin(angle)*1.08
    seam(a,'NOZZLEPETAL',(-19.2,yy,zz),(-19.82,yy,zz),.035)
   # The broad planform stays intact; panel joins articulate wing construction.
   if attack:
    seam(a,'AILERON',(-5.6,s*6,4.97),(-5.9,s*17.3,4.97),.042)
    seam(a,'WINGRIB',(1,s*8,4.98),(-5.6,s*8,4.98),.027)
    seam(a,'WINGRIB',(-.8,s*13,4.98),(-6,s*13,4.98),.027)
    a.prism('WINGFENCE',[(-5.5,4.96),(1.7,4.96),(1.7,5.75),(-5.5,5.55)],s*8.15-.06,s*8.15+.06,STEEL)
   else:
    seam(a,'AILERON',(-11,s*6,4.98),(-12.8,s*17,4.98),.042)
    seam(a,'WINGRIB',(-3,s*10,4.98),(-11.5,s*10,4.98),.03)
    seam(a,'WINGRIB',(-7,s*14,4.98),(-12.1,s*14,4.98),.03)
    a.cyl('WINGTIPRAIL',(-10.1,s*18.1,4.75),.14,5.8,IRON,'X',segments=8)
   x0,x1=(-5.7,-3.2) if attack else (-7,-4)
   a.patch('ACCESSPANEL',[(x0,s*4.5,5.01),(x1,s*4.5,5.01),(x1,s*6.7,5.01),(x0,s*6.7,5.01)],PLATE)
   a.box('COUNTERMEASURES',(-15,s*2.0-.3,6.2),(-12.9,s*2.0+.3,6.48),VENT,bevel=.08)
   a.box('ENGINEVENT',(-6,s*1.8-.55,6.65),(-3.4,s*1.8+.55,6.87),VENT,bevel=.07)
   # Fins on the original missiles, no changes to launch positions.
   for y in (7,11,15):
    x=-2 if attack else -6;yy=s*y
    for offs in (-1,1):
     a.prism('MISSILEFIN',[(x-2.4,2.7),(x-1.0,2.7),(x-2.0,3.35)],yy+offs*.26,yy+offs*.31,IRON)
  for s in (-1,1):
   seam(a,'CANOPYRAIL',(2.1,s*1.4,6.05),(9.8,s*.58,6.15),.085,STEEL)
   seam(a,'CANOPYBOW',(5.4,s*1.34,6.75),(5.4,s*.77,8.21),.065,STEEL)
  seam(a,'CANOPYCROWN',(5.4,-.77,8.21),(5.4,.77,8.21),.065,STEEL)
  ell(a,'IRST',(10.6,-.65,5.8),(.52,.46,.49),IRON)
  ell(a,'IRSTGLASS',(10.85,-.65,5.92),(.33,.32,.33),GLASS)
  seam(a,'PITOT',((16.5 if attack else 21),0,4.1),((18 if attack else 23.4),0,4.1),.055)
  a.box('DORSALVENT',(-3,-.5,6.94),(0,.5,7.12),VENT,bevel=.06)
 else:
  # Armoured cockpit surrounds, engine filters, angular sensor nose and mechanical hub.
  for s in (-1,1):
   ring(a,'ENGINEFILTER',(2.18,s*3,6.8),1.18,.91,.34)
   ring(a,'EXHAUSTCOLLAR',(-8.55,s*3,6.3),1.02,.78,.4)
   a.box('ENGINEGRILLE',(-5.8,s*3-.72,8.18),(-2.8,s*3+.72,8.35),VENT,bevel=.06)
   seam(a,'CABRAIL',(3.4,s*1.48,6.73),(6.8,s*1.15,6.82),.1,STEEL)
   seam(a,'CABRAIL',(8.4,s*1.48,5.45),(11.6,s*.98,5.47),.1,STEEL)
   for x,z in ((4.9,7.3),(9.7,6)):
    seam(a,'CANOPYBOW',(x,s*1.39,z-.4),(x,s*.65,z+.94),.08,STEEL)
    seam(a,'CANOPYRIDGE',(x,-.65,z+.94),(x,.65,z+.94),.08,STEEL)
   seam(a,'HANDRAIL',(2.8,s*2.76,5.4),(5.9,s*2.65,4.9),.085)
   seam(a,'STEP',(3.8,s*3.0,3.2),(6.0,s*3.0,3.2),.15)
   for x in (3.8,6.0):seam(a,'STEPBRACE',(x,s*2.3,3.4),(x,s*3,3.2),.09)
   a.box('CHAFF',(-9,s*1.9-.35,5.9),(-7.5,s*1.9+.35,6.4),VENT,bevel=.09)
   a.prism('COCKPITARMOUR',[(2.5,4.4),(8.2,3.9),(8.2,4.5),(3.6,5.4)],s*2.53-.08,s*2.53+.08,PLATE)
   for x in (-4,-1):seam(a,'ENGINEPANEL',(x,s*3,5.65),(x,s*4.1,7.2),.045)
  ell(a,'NOSERADOME',(13.6,0,4.57),(1.15,1.35,1.15),STEEL)
  ell(a,'EOSPHERE',(13.9,0,3.25),(.77,.80,.69),IRON)
  a.cyl('EOLENS',(14.57,-.27,3.4),.31,.14,GLASS,'X',segments=12)
  a.cyl('THERMAL',(14.56,.31,3.24),.22,.15,GLASS,'X',segments=10)
  a.cyl('ROTORCOLLAR',(-1,0,9.1),1.25,.6,IRON,segments=16)
  for i in range(5):
   ang=i*math.tau/5;c,s=math.cos(ang),math.sin(ang)
   seam(a,'PITCHLINK',(c*.65,s*.65,-1),(c*2.1,s*2.1,.05),.12,IRON,'PROPELLER01')
  seam(a,'TAILANTENNA',(-24,0,9),(-25.8,0,11),.065)
 assert a.bones==bones

"""Validate original W3D exports, generate contact sheets and publish manifest.
No stock geometry dependencies; Pillow is used only to compose rendered previews.
"""
from pathlib import Path
import json,struct,hashlib,sys,math
from PIL import Image,ImageDraw,ImageFont
ROOT=Path(__file__).resolve().parents[3];HERE=Path(__file__).resolve().parent
BUILD=ROOT/'build/faction-assets/ukraine';ART=ROOT/'resources/macos/GameData/Art'
sys.path.insert(0,str(ROOT/'scripts/factions/europe'))
from validate_roster import check_model
from coalition_infantry import chunks,cstr
NAMES=['UAKOZAK','UAOPLOT','UABTR4','UABUK','UABOHD','UADRONE','UARIFL','UASTUG','UACOMM','UAF16','UATB2','UAMI24','UADOZR','UASUPLY','UAFPV','UACMD','UAPOWER','UABARR','UASUPP','UAFACT','UAAIR','UATECH','UAINCOM','UAGUARD','UAAA','UASUPER','UAMANP','UAMINE']

def walk(data):
 for cid,body,nested in chunks(data):
  yield cid,body
  if nested:yield from walk(body)

def main():
 entries=[];exports=[];animations=[]
 for name in NAMES:
  assert name.startswith('UA') and len(name)<=8,name
  e=json.loads((BUILD/(name+'.json')).read_text())
  e['category']='building' if name in NAMES[15:26] else 'infantry' if name in ('UARIFL','UASTUG','UACOMM','UAMANP') else 'aircraft' if name in ('UAF16','UATB2','UAMI24') else 'projectile' if name in ('UAFPV','UAMINE') else 'vehicle'
  e['parent']=e.pop('suggested_inherited_object');e['bone_contract']=e['bones'];e['bones']=[b['name'] for b in e['bone_contract']];e['preview']=str(ROOT/e['preview'])
  for bone in e['bone_contract']:
   if bone['name']=='PROPELLER':bone['quaternion_xyzw']=[0,2**-.5,0,2**-.5]
   if bone['name']=='TAILROTOR':bone['quaternion_xyzw']=[2**-.5,0,0,2**-.5]
  for variant in e['variants']:
   p=ART/'W3D'/(variant+'.w3d');tri=check_model(p);tex=set();bones=[];meshes=[]
   for cid,body in walk(p.read_bytes()):
    if cid==0x32:tex.add(cstr(body))
    if cid==0x102:
     bones=[cstr(body[i:i+16]) for i in range(0,len(body),60)]
     for offset in range(0,len(body),60):
      q=struct.unpack_from('<4f',body,offset+44);assert abs(sum(v*v for v in q)-1)<.001,(variant,'invalid bone quaternion')
    if cid==31:meshes.append(cstr(body[8:24]))
    if cid==0x4a:
     values=struct.unpack('<'+'f'*(len(body)//4),body);assert all(math.isfinite(v) for v in values)
   for cid,body,_ in chunks(p.read_bytes()):
    if cid!=0:continue
    blocks={c:b for c,b,_ in chunks(body)}
    if not cstr(blocks[31][8:24]).startswith('HOUSECOLOR'):continue
    verts=[struct.unpack_from('<3f',blocks[2],i) for i in range(0,len(blocks[2]),12)]
    planes={}
    for j in range(0,len(blocks[32]),32):
     ids=struct.unpack_from('<3I',blocks[32],j);normal=struct.unpack_from('<3f',blocks[32],j+16);axis=max(range(3),key=lambda k:abs(normal[k]));plane=(axis,round(verts[ids[0]][axis],2))
     planes.setdefault(plane,set()).add(1 if normal[axis]>0 else -1)
    assert all(signs=={-1,1} for signs in planes.values()),(name,'one-sided player marking',planes)
   assert len(meshes)==len(set(meshes)),(name,'duplicate truncated mesh name')
   assert set(e['bones'])<=set(bones),(name,'missing bone')
   assert 'HOUSECOLOR' in meshes or name in ('UAFPV','UAMINE','UATB2'),(name,'missing house colour')
   for t in tex:
    im=Image.open(ART/'TexturesHD'/t);assert im.format=='TGA',(name,t,'texture extension does not match native TGA payload');assert t.startswith('ua'),(name,'foreign texture',t)
    assert all(v>0 and not(v&(v-1)) for v in im.size),(name,t,'non-POT texture')
   exports.append({'model':variant,'triangles':tri,'meshes':len(meshes),'textures':sorted(tex),'sha256':hashlib.sha256(p.read_bytes()).hexdigest()})
  assert (ART/'TexturesHD'/(name.lower()+'.tga')).read_bytes()!=(ART/'TexturesHD'/(name.lower()+'_d.tga')).read_bytes()
  for clip in e['animations']:
   hierarchy,animation=clip.split('.')
   file=ART/'W3D'/(animation+'.w3d')
   assert file.exists(),file
   found=False
   for cid,body in walk(file.read_bytes()):
    if cid==0x201:
     assert cstr(body[4:20])==animation,(clip,'wrong clip name',cstr(body[4:20]))
     assert cstr(body[20:36])==hierarchy,(clip,'wrong hierarchy')
     found=True
   assert found,(clip,'missing animation header');animations.append(clip)
   if animation.endswith('_I'):
    base=ART/'W3D'/(hierarchy+'.w3d')
    pivots=next(body for cid,body in walk(base.read_bytes()) if cid==0x102)
    names=[cstr(pivots[i:i+16]) for i in range(0,len(pivots),60)]
    reset=set()
    for cid,body in walk(file.read_bytes()):
     if cid!=0x202:continue
     first,last,size,kind,bone,_=struct.unpack_from('<6H',body)
     assert (first,last,size,kind)==(0,20,4,6),(clip,'invalid idle channel')
     for offset in range(12,len(body),16):
      q=struct.unpack_from('<4f',body,offset);assert sum(abs(v-e) for v,e in zip(q,(0,0,0,1)))<1e-6,(clip,'idle not neutral')
     reset.add(names[bone])
    assert {'BODYROOT','PELVIS','TORSO','HEAD','LEGL','LEGR','SHINL','SHINR','ARML','ARMR','FOREL','FORER'}<=reset,(clip,'incomplete idle reset')
  # Playable portraits are owned/exported by the illustrated-portrait workflow.
  # Model review must never overwrite them with small Blender thumbnails.
  if (ART/'TexturesHD'/e['portrait']).exists():
   e['portrait_size']=list(Image.open(ART/'TexturesHD'/e['portrait']).size)
   if (HERE/'portraits'/(e['key'].lower()+'.png')).exists():
    e['portrait_source']=str((HERE/'portraits'/(e['key'].lower()+'.png')).relative_to(ROOT))
    e['portrait_size']=[256,256]
  entries.append(e)
 manifest={'faction':'Ukraine','geometry_origin':'Original authored mathematical geometry; no stock visual models imported. Infantry and aircraft V2 retain original bone contracts.','paint_origin':'Original shared generated cloth/aviation/industrial atlas art, Ukraine-specific tint and restrained digital camouflage, material wear and baked diffuse contact shadows.','assets':entries,'runtime_contract_notes':['Unit orientation +X, Z up. Vehicle attachment and wheel bones are model-local.','Infantry original rigid skeletal animation hierarchy uses each intact model base name. For damaged infantry states use the same intact model and base animation hierarchy. Explicit idle clip resets every joint; Scale=1.5 remains appropriate.','Factory bay stays open. Truck supply centre and factory repair use separate DOCKSTART/DOCKACTION/DOCKEND and nine queue bones.','No gameplay, strings or stock files were modified by the asset generator.']}
 (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
 font=ImageFont.truetype('/System/Library/Fonts/Helvetica.ttc',20)
 for group,assets in [('units',[e for e in entries if e['category']!='building']),('buildings',[e for e in entries if e['category']=='building']),('all',entries)]:
  cols=3 if group!='all' else 4;cw,ch=320,270;rows=math.ceil(len(assets)/cols)
  sheet=Image.new('RGB',(cw*cols,ch*rows),(28,33,28));draw=ImageDraw.Draw(sheet)
  for i,e in enumerate(assets):
   im=Image.open(e['preview']).convert('RGB');im.thumbnail((cw,240),Image.Resampling.LANCZOS);x=(i%cols)*cw;y=(i//cols)*ch;sheet.paste(im,(x+(cw-im.width)//2,y));draw.text((x+12,y+243),e['display_name'],fill=(225,229,210),font=font)
  sheet.save(BUILD/(group+'_contact.png'))
 report={'status':'passed','assets':len(entries),'unit_assets':15,'projectiles':2,'buildings':11,'model_exports':len(exports),'animation_clips':animations,'exports':exports}
 (BUILD/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
 print(json.dumps({k:v for k,v in report.items() if k!='exports'},indent=2))
if __name__=='__main__':main()

"""Validate every original Russia export and create the implementation manifest."""
from pathlib import Path
import sys,json,math,struct,hashlib
from PIL import Image,ImageDraw,ImageFont
HERE=Path(__file__).resolve().parent;ROOT=HERE.parents[2];BUILD=ROOT/'build/faction-assets/russia';ART=ROOT/'resources/macos/GameData/Art'
sys.path.insert(0,str(ROOT/'scripts/factions/europe'))
from coalition_infantry import chunks,cstr
from stock_data import asset,record
ROSTER=[
('Tigr','Tigr Radar Scout','vehicle','RUTIGR'),('T90','T-90','vehicle','RUT90'),('BMP3','BMPT Assault Support','vehicle','RUBMPT'),('Tunguska','Tunguska','vehicle','RUTUNG'),('Msta','Msta-S','vehicle','RUMSTA'),('TOS','TOS-1A','vehicle','RUTOS'),
('Rifleman','Rifleman','infantry','RURIFLE'),('Kornet','Kornet Team','infantry','RUKORNET'),('Commando','Assault Engineer','infantry','RUCMDO'),('Su35','Su-35','aircraft','RUSU35'),('Su25','Su-25','aircraft','RUSU25'),('Mi28','Mi-28','aircraft','RUMI28'),('Engineer','Armoured Engineer','vehicle','RUENG'),('SupplyTruck','Supply Truck','vehicle','RUSUP'),
('CommandCenter','Command Centre','building','RUCC'),('PowerPlant','Power Station','building','RUPWR'),('Barracks','Barracks','building','RUBARR'),('SupplyCenter','Supply Centre','building','RUSUPPLY'),('WarFactory','War Factory','building','RUFACT'),('Airfield','Airfield','building','RUAIR'),('TechCenter','Military Institute','building','RUTECH'),('Income','Logistics Ministry','building','RUINCOME'),('GroundDefense','Cannon Emplacement','building','RUGDEF'),('AirDefense','Radar Missile Defence','building','RUADEF'),('Superweapon','Strategic Missile Silo','building','RUSUPER')]

def walk(data):
 for c,b,k in chunks(data):
  yield c,b
  if k:yield from walk(b)

def check_model(path,external=None):
 data=path.read_bytes();meshes={};refs=[];bones=[];textures=set();hier=None;triangles=0;anims=[]
 for cid,body,_ in chunks(data):
  if cid==0:
   p={c:b for c,b,k in chunks(body)};h=p[31];name=cstr(h[8:24]);assert name not in meshes,(path,'duplicate mesh',name);ntri,nvert=struct.unpack_from('<II',h,40)
   assert len(p[2])==nvert*12 and len(p[3])==nvert*12 and len(p[32])==ntri*32,(path,'mesh lengths')
   for key in (2,3):assert all(math.isfinite(x) for x in struct.unpack('<'+'f'*(len(p[key])//4),p[key])),(path,'nonfinite data')
   for i in range(ntri):assert max(struct.unpack_from('<3I',p[32],i*32))<nvert,(path,'bad triangle')
   meshes[name]=ntri;triangles+=ntri
   mesh_textures=set()
   for c,b in walk(body):
    if c==0x32:textures.add(cstr(b));mesh_textures.add(cstr(b))
    if c==0x4A:assert all(math.isfinite(x) for x in struct.unpack('<'+'f'*(len(b)//4),b)),(path,'nonfinite UV')
   if 'ruhouse.tga' in mesh_textures:assert name.startswith('HOUSECOLOR'),(path,'player-colour mesh lacks HOUSECOLOR prefix',name)
  if cid==0x100:
   for c,b,k in chunks(body):
    if c==0x102:
     bones=[cstr(b[i:i+16]) for i in range(0,len(b),60)];assert len(bones)==len(set(bones)),(path,'duplicate bones')
     for i in range(len(bones)):assert struct.unpack_from('<i',b,i*60+16)[0]<i,(path,'bone order')
  if cid==0x700:
   for c,b in walk(body):
    if c==0x701:hier=cstr(b[24:40])
    if c==0x704:refs.append((struct.unpack_from('<I',b)[0],cstr(b[4:])))
  if cid==0x200:
   for c,b,k in chunks(body):
    if c==0x201:anims.append(cstr(b[20:36])+'.'+cstr(b[4:20]))
 if external:
  assert hier==external,(path,hier,external)
  for c,b,k in chunks(asset(external+'.w3d')):
   if c==0x100:
    for cc,bb,kk in chunks(b):
     if cc==0x102:bones=[cstr(bb[i:i+16]) for i in range(0,len(bb),60)]
 assert len(refs)==len(meshes) and triangles>0,(path,'mesh references')
 for b,n in refs:assert b<len(bones) and n.split('.',1)[1] in meshes,(path,'dangling bone/mesh',b,n)
 for t in textures:
  assert t.startswith('ru'),(path,'external visible texture',t)
  im=Image.open(ART/'TexturesHD'/t);assert all(x>0 and x&(x-1)==0 for x in im.size),(path,'texture size')
 return {'model':path.stem,'triangles':triangles,'meshes':len(meshes),'bones':bones,'textures':sorted(textures),'animations':anims,'sha256':hashlib.sha256(data).hexdigest()}

def main():
 assets=[];reports=[];animation_reports=[]
 for key,title,category,name in ROSTER:
  r=json.loads((BUILD/(name+'.json')).read_text());entry={**r,'key':key,'display_name':title,'category':category,'parent':r['suggested_inherited_object'],'bones':[b['name'] for b in r['bones']],'bone_contract':r['bones'],'textures':r['texture_files'],'preview':str(ROOT/r['preview']),'blend':str(ROOT/r['blend'])}
  assert len(name)<=8;record('Object',entry['parent'])
  for variant in r['variants']:reports.append(check_model(ART/'W3D'/(variant+'.w3d'),r.get('external_skeleton')))
  assert (ART/'TexturesHD'/(name.lower()+'_paint.tga')).read_bytes()!=(ART/'TexturesHD'/(name.lower()+'_paint_d.tga')).read_bytes(),name
  if category=='building':entry['night_variant_note']='Night variants preserve authored architecture; no emissive lights are baked in this initial pass.'
  if category=='infantry':
   entry['animation_note']=r.get('animation_contract','Original authored articulated rig and animation clips.')
   entry['weapon_fire_bone']='MUZZLE01'
   if isinstance(r.get('animations'),dict):
    for suffix,clip in r['animations'].items():
     path=ART/'W3D'/(name+suffix+'.w3d');data=path.read_bytes();channels=0
     for cid,body,_ in chunks(data):
      assert cid==0x200,(path,'unexpected animation chunk')
      for cc,bb,_ in chunks(body):
       if cc==0x201:
        assert cstr(bb[20:36])==name and cstr(bb[4:20])==name+suffix,(path,'wrong animation hierarchy')
       if cc==0x202:
        first,last,dim,kind,bone,_=struct.unpack_from('<6H',bb)
        assert first==0 and last==20 and dim==4 and kind==6 and bone<len(r['bones'])+2,(path,'invalid channel')
        values=struct.unpack('<'+'f'*((len(bb)-12)//4),bb[12:]);assert all(math.isfinite(x) for x in values)
        for j in range(0,len(values),4):assert abs(sum(x*x for x in values[j:j+4])-1)<.001,(path,'invalid quaternion')
        channels+=1
     assert channels>0,(path,'empty animation')
     animation_reports.append({'file':path.name,'clip':clip,'channels':channels,'status':'passed'})
  if category!='building':
   entry['art_revision']='russia-v2'
   entry['material_source']='scripts/models/russia/atlas_polished.png'
   entry['material_prompt']='scripts/models/russia/atlas_polished.prompt.txt'
   entry['surface_note']='Original generated olive paint, hardware, smooth cloth and skin; source rectangles mapped explicitly, assembled contact shading and damage baked into 1k/2k textures.'
  if category in ('vehicle','building'):
   entry['detail_revision']='russia-ground-building-detail'
   entry['detail_source']='scripts/models/russia/ground_building_detail.py'
   entry['detail_contract']='Original fittings within unchanged assembled bounds; all turret, muzzle, exit, docking and parking transforms preserved.'
  assets.append(entry)
 manifest={'faction':'Russia','style':'Heavy olive painted armour, dark running gear, broad wear, industrial concrete and olive steel architecture. Original visible geometry only.','assets':assets,'contracts':{'coordinates':'+X forward, +Z up, game scale; wheeled origin ground zero.','turrets':'TURRET yaw; BARREL pitch child; MUZZLE01/MUZZLEFX01 muzzle and fire FX; TREADSL/TREADSR scrolling.','wheels':'TIRE01..06: front left/right first, then rear axle pairs. Tigr has four, supply six.','factory':'EXITSTART (-10,-30,.3), EXITEND (53,-30,.3); production SpawnPoint/ExitPoint should match. Repair docking uses DOCKSTART/ACTION/END plus nine WAITING bones. Bay is permanently open.','supply':'China SupplyTruck collection workflow; DOCKSTART (47,-20,.3), DOCKACTION (22,-20,.3), DOCKEND (48,-20,.3); nine waiting bones. Build truck SpawnPoint/ExitPoint (20,20,.3)/(55,20,.3).','airfield':'USA 2x2 runway parking contract, all 17 standard public parking/runway/heli bones included. List these as ExtraPublicBone in Draw.','infantry':'Original authored full-size articulated rig at ModelScale1.0. MODEL.MODEL_I explicit idle/reset, _R run, _F attack, _X death. No stock skeleton dependency; knees/ankles remain attached throughout motion.','helicopter':'RUMI28.RUMI28 loop spins PROPELLER01/02; WEAPONA01..04 and WEAPONB01..04; TURRET/BARREL gun.','wrecks':'Vehicles use original _D as wreck visual; buildings _E/_EN use compressed burned shells. Infantry death uses the original articulated _X clip.','night':'Building night variants are present; dedicated illuminated night repaint is deferred.'},'validation':'build/faction-assets/russia/validation.json','contact_sheet':'build/faction-assets/russia/contact-sheet.png'}
 (HERE/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n');(BUILD/'validation.json').write_text(json.dumps({'status':'passed','assets':len(assets),'exports':len(reports),'animation_exports':len(animation_reports),'geometry':'No stock visible meshes imported','models':reports,'animations':animation_reports},indent=2)+'\n')
 cols=5;tw=320;th=267;sheet=Image.new('RGB',(cols*tw,math.ceil(len(assets)/cols)*th),(33,38,32));d=ImageDraw.Draw(sheet)
 try:font=ImageFont.truetype('/System/Library/Fonts/Supplemental/Arial.ttf',17)
 except OSError:font=ImageFont.load_default()
 for i,e in enumerate(assets):
  im=Image.open(e['preview']).convert('RGB');im.thumbnail((tw,240));x=i%cols*tw;y=i//cols*th;sheet.paste(im,(x+(tw-im.width)//2,y));d.text((x+10,y+241),e['display_name'],font=font,fill=(226,228,208))
 sheet.save(BUILD/'contact-sheet.png');print(json.dumps({'status':'passed','assets':len(assets),'exports':len(reports),'manifest':str(HERE/'manifest.json')},indent=2))
if __name__=='__main__':main()

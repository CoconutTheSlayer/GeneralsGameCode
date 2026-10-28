"""Check the six original compact exports and their actual runtime dependencies."""
from pathlib import Path
import hashlib
import json
import math
import struct
import sys
from PIL import Image
ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts/factions/europe'))
from validate_roster import check_model
import build_europe
from coalition_infantry import chunks,cstr
DATA=ROOT/'resources/macos/GameData/Art'
MODELS={
    'EUBOXER':{'TURRET','MUZZLE01','MUZZLEFX01',*(f'TIRE{i:02}' for i in range(1,9))},
    'EUWIEST':{'TURRET','TURRETMS','TURRETFX','BARREL'},
    'EUPATRIA':{'TURRET','MUZZLE',*(f'TIRE{i:02}' for i in range(1,7))},
    'EUVALUK':{*(f'TIRE{i:02}' for i in range(1,7))},
    'EUDRONE':{'TURRET01','TURRETUP01','TURRETFX01','MUZZLE01'},
    'EUMV4':{'FLAIL'},
}
def walk(data):
    for cid,body,nested in chunks(data):
        yield cid,body
        if nested:yield from walk(body)
report=[]
for model,required in MODELS.items():
    for suffix in ('','_D'):
        path=DATA/'W3D'/(model+suffix+'.w3d')
        triangles=check_model(path)
        tex=set();bones=set();meshes=set();animation=False
        for cid,body in walk(path.read_bytes()):
            if cid==0x32:tex.add(cstr(body).lower())
            if cid==0x102:bones|={cstr(body[i:i+16]).upper() for i in range(0,len(body),60)}
            if cid==31:
                mesh=cstr(body[8:24]).upper()
                assert mesh not in meshes,(model,'duplicate runtime mesh name',mesh)
                meshes.add(mesh)
            if cid==0x200:animation=True
        assert required<=bones,(model,required-bones)
        if model=='EUDRONE':assert 'TURRETUP09' in meshes
        if model=='EUMV4':assert animation
        expected=model.lower()+'_paint'+suffix.lower()+'.tga'
        assert tex<={expected,'eucompact_track.tga','eucompact_track_v2.tga','euhouse.tga'},(model,tex)
        assert expected in tex,(model,'missing original painted texture',tex)
        for texture in tex:
            image=Image.open(DATA/'TexturesHD'/texture)
            assert all(n>0 and n&(n-1)==0 for n in image.size),(texture,'non-power-of-two')
        report.append(dict(model=path.stem,triangles=triangles,meshes=len(meshes),textures=sorted(tex),sha256=hashlib.sha256(path.read_bytes()).hexdigest()))
    intact=(DATA/'TexturesHD'/(model.lower()+'_paint.tga')).read_bytes()
    damaged=(DATA/'TexturesHD'/(model.lower()+'_paint_d.tga')).read_bytes()
    assert intact!=damaged,(model,'damage texture unchanged')
# Keep the live entry points on the original mesh pipeline.
for script in ('coalition.py','recon_drone.py','original_compacts.py','compact_polish.py',
               'compact_polish_common.py','wiesel_polish.py','vilkas_polish.py','valuk_polish.py','boxer.py'):
    source=(ROOT/'scripts/models'/script).read_text()
    assert 'from native_vehicles' not in source and 'from stock_data' not in source,script
# Death paths must not silently reintroduce stock vehicle hulks or flying turrets.
for unit in ('Euro_Boxer','Euro_Wiesel','Euro_Patria','Euro_Ambulance','Euro_ReconDrone','Euro_MV4'):
    entry=next(o for o in build_europe.UNITS if o[0]==unit)
    effects=[line.split('=')[1].split()[-1] for line in entry[4]['extra']
             if line.strip().startswith(('OCL =','CreationList ='))]
    assert effects and set(effects)=={unit+'_Wreck'},(unit,effects)
out=ROOT/'build/original-compacts/validation.json'
out.parent.mkdir(parents=True,exist_ok=True)
out.write_text(json.dumps({'status':'passed','exports':report},indent=2)+'\n')
print(json.dumps({'status':'passed','original_exports':len(report),'triangles':{r['model']:r['triangles'] for r in report}},indent=2))

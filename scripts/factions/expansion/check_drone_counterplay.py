"""Ensure ordinary anti-air can acquire and destroy a guided attack drone."""
from pathlib import Path
import json,os,re,subprocess,sys
from check_personal_aps import ROOT,OUT,DATA,main as check_aps
sys.path.insert(0,str(ROOT/'scripts/factions/europe'))
from stock_data import record,module

def main():
    check_aps()
    locomotor='\n'.join(record('Locomotor','TomahawkMissileLocomotor'))
    locomotor=re.sub(r'(?m)^(\s*(?:Speed|SpeedDamaged|MinSpeed)\s*=)\s*[^\n]+',r'\1 65',locomotor)
    guidance='\n'.join(module('TomahawkMissile','ModuleTag_07')).replace('ModuleTag_07','ModuleTag_DroneGuidance')
    guidance=re.sub(r'FuelLifetime\s*=\s*4000','FuelLifetime = 12000',guidance)
    ini='Locomotor Test_DroneLocomotor\n'+locomotor+'\nEnd\n'+'''ChildObject Test_AttackDrone TomahawkMissile
  KindOf = PRELOAD CAN_CAST_REFLECTIONS PROJECTILE SMALL_MISSILE DRONE VEHICLE AIRCRAFT
  ReplaceModule ModuleTag_07
'''+guidance+'''
  End
  Locomotor = SET_NORMAL Test_DroneLocomotor
  ReplaceModule ModuleTag_02
    Body = ActiveBody ModuleTag_DroneHealth
      MaxHealth = 20
      InitialHealth = 20
    End
  End
End
ChildWeapon Test_DroneWeapon TomahawkMissileWeapon
  AttackRange = 650
  MinimumAttackRange = 0
  PrimaryDamage = 1
  SecondaryDamage = 0
  ProjectileObject = Test_AttackDrone
  ClipReloadTime = 4000
End
ChildObject Test_DroneCarrier AmericaVehicleTomahawk
  WeaponReplace = TomahawkMissileWeapon Test_DroneWeapon
  ReplaceModule ModuleTag_02
    Body = ActiveBody ModuleTag_CarrierHealth
      MaxHealth = 100000
      InitialHealth = 100000
    End
  End
End
'''
    (DATA/'Data/INI/Addon/Logic/ZZDroneCounterplay.ini').write_text(ini)
    battle=OUT/'drone-battle.txt'
    battle.write_text(f'map Tournament Desert\ncash 10000\nseed 5\nsuperweapons 0\nresult {OUT}/drone-result.json\nplayer human FactionGLA 0 0\nplayer easy FactionAmerica 1 2\n')
    env={k:v for k,v in os.environ.items() if not k.startswith(('GENERALS_','D3D8METAL_'))}
    env.update(GENERALS_NO_MESSAGEBOX='1',GENERALS_DRONE_LOG='1',GENERALS_DUEL='GLAVehicleQuadCannon:3,Test_DroneCarrier:3',GENERALS_DUEL_SECONDS='35',GENERALS_DUEL_DISTANCE='500',GENERALS_DUEL_HOLD_SIDE='0')
    log=OUT/'drone-native.log'
    with log.open('w') as f:
        p=subprocess.run([str(OUT/'bin/generalszh'),'-headless','-noaudio','-noFPSLimit','-gamespeed','3000','-battle',str(battle)],cwd=str(Path.home()/'Games/generalszh'),env=env,stdout=f,stderr=f,timeout=60)
    text=log.read_text(errors='replace')
    assert p.returncode==0,text[-3000:]
    hits=re.findall(r'DRONE_DAMAGE frame (\d+) drone (\d+) source GLAVehicleQuadCannon damage ([\d.]+)',text)
    assert hits,('Stock Quad Cannon did not shoot the drones',text[-3000:])
    assert 'DUEL_RESULT' in text and 'DUEL_RESULT error' not in text,text[-2000:]
    damage={}
    for _,drone,amount in hits:damage[drone]=damage.get(drone,0)+float(amount)
    destroyed=sum(amount>=20 for amount in damage.values())
    assert destroyed, 'No drone received lethal AA damage'
    report={'status':'passed','ordinary_aa_hits':len(hits),'drones_hit':len(damage),'drones_destroyed':destroyed,'automatic_acquisition':True,'log':str(log)}
    (OUT/'drone-validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report))

if __name__=='__main__':main()

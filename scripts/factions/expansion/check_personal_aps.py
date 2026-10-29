"""Run an isolated native test of personal APS targeting, recharge, and split text loading."""
from pathlib import Path
import json
import os
import re
import shutil
import subprocess

ROOT=Path(__file__).resolve().parents[3]
OUT=ROOT/'build/new-factions/aps-test'
DATA=OUT/'Resources/GameData'

def main():
    (OUT/'bin').mkdir(parents=True,exist_ok=True)
    # A copy resolves its own ../Resources/GameData, leaving live add-on data untouched.
    shutil.copy2(ROOT/'build/macos/GeneralsMD/generalszh',OUT/'bin/generalszh')
    shutil.copytree(ROOT/'resources/macos/GameData/Data',DATA/'Data',dirs_exist_ok=True)
    (DATA/'Data/INI/Addon/Logic/ZZDroneCounterplay.ini').unlink(missing_ok=True)
    art=DATA/'Art'
    if not art.exists():art.symlink_to(ROOT/'resources/macos/GameData/Art',target_is_directory=True)
    (DATA/'Data/english/Addon').mkdir(parents=True,exist_ok=True)
    (DATA/'Data/english/Addon/PersonalAPSTest.str').write_text('TEST:PersonalAPS\n"Personal protection test"\nEND\n')
    (DATA/'Data/INI/Addon/Logic/ZZPersonalAPSTest.ini').write_text('''ChildWeapon Test_APSBeam PaladinPointDefenseLaser
  DelayBetweenShots = 8000
  AttackRange = 100
End
ChildWeapon Test_ZeroGun PaladinTankGun
  PrimaryDamage = 0
  SecondaryDamage = 0
End
ChildWeapon Test_MissileGun MissileDefenderMissileWeapon
  DelayBetweenShots = 700
  PrimaryDamage = 1
End
ChildObject Test_ProtectedTank AmericaTankPaladin
  WeaponReplace = PaladinTankGun Test_ZeroGun
  ReplaceModule ModuleTag_02
    Body = ActiveBody ModuleTag_TestBody
      MaxHealth = 100000
      InitialHealth = 100000
    End
  End
  ReplaceModule ModuleTag_07
    Behavior = PointDefenseLaserUpdate ModuleTag_TestAPS
      WeaponTemplate = Test_APSBeam
      PrimaryTargetTypes = SMALL_MISSILE
      ScanRate = 100
      ScanRange = 120
      ProtectOnlySelf = Yes
    End
  End
End
ChildObject Test_MissileInfantry AmericaInfantryMissileDefender
  Side = China
  WeaponReplace = MissileDefenderMissileWeapon Test_MissileGun
End
''')
    battle=OUT/'battle.txt'
    battle.write_text(f'map Tournament Desert\ncash 10000\nseed 5\nsuperweapons 0\nresult {OUT}/result.json\nplayer human FactionAmerica 0 0\nplayer easy FactionChina 1 2\n')
    env={k:v for k,v in os.environ.items() if not k.startswith(('GENERALS_','D3D8METAL_'))}
    env.update(GENERALS_NO_MESSAGEBOX='1',GENERALS_APS_LOG='1',GENERALS_DUEL='Test_ProtectedTank:3,Test_MissileInfantry:9',GENERALS_DUEL_SECONDS='35',GENERALS_DUEL_DISTANCE='160')
    log=OUT/'native.log'
    with log.open('w') as f:
        p=subprocess.run([str(OUT/'bin/generalszh'),'-headless','-noaudio','-noFPSLimit','-gamespeed','3000','-battle',str(battle)],cwd=str(Path.home()/'Games/generalszh'),env=env,stdout=f,stderr=f,timeout=60)
    text=log.read_text(errors='replace')
    assert p.returncode==0,text[-3000:]
    shots=[tuple(map(int,m)) for m in re.findall(r'APS_INTERCEPT frame (\d+) defender (\d+) target (\d+) missile (\d+)',text)]
    assert len(shots)>=3,('No sustained interception',text[-1500:])
    last={}
    for frame,defender,target,missile in shots:
        assert defender==target,('Neighbour protection leaked',defender,target)
        if defender in last:assert frame-last[defender]>=240,('APS recharge too short',frame,last[defender])
        last[defender]=frame
    assert re.search(r'loaded 1 texts from .*PersonalAPSTest.str',text),'Split localization did not load'
    assert 'DUEL_RESULT' in text,text[-1500:]
    report={'status':'passed','interceptions':len(shots),'protected_vehicles':len(last),'minimum_recharge_seconds':8,'localization':'separate faction text file loaded','log':str(log),'shots':shots}
    (OUT/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps({k:v for k,v in report.items() if k!='shots'}))

if __name__=='__main__':main()

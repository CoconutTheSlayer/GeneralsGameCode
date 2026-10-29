#!/usr/bin/env python3
"""Build the Russia add-on from original art and the player's installed game data.

Run from any directory: python3 scripts/factions/russia/build_faction.py
Only Russia-owned generated files are written. No stock visible unit/building meshes
are copied; infantry uses our original articulated rigs and animation clips.
"""
from pathlib import Path
import json
import math
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'resources/macos/GameData'
OUT = ROOT / 'build/new-factions/russia'
sys.path.insert(0, str(ROOT / 'scripts/factions/europe'))
import stock_data as stock

MANIFEST = json.loads((ROOT / 'scripts/models/russia/manifest.json').read_text())
ASSETS = {a['key']: a for a in MANIFEST['assets']}
RETIRED = {'Su35', 'Mi28'}
ACTIVE_UNITS = [k for k, a in ASSETS.items() if a['category'] != 'building' and k not in RETIRED]
DISPLAY_NAMES = {'BMP3': 'BMPT Assault Support', 'Commando': 'Assault Engineer', 'Tigr': 'Tigr Radar Scout'}

# Cost, seconds, health, prerequisite. These are deliberately a playtest baseline.
STATS = {
    'Tigr': (500, 7, 180, 'WarFactory'),
    'T90': (850, 10, 500, 'WarFactory'),
    'BMP3': (950, 12, 480, 'WarFactory'),
    'Tunguska': (900, 12, 300, 'WarFactory'),
    'Msta': (1300, 18, 250, 'TechCenter'),
    'TOS': (1500, 20, 320, 'TechCenter'),
    'Rifleman': (150, 4, 90, 'Barracks'),
    'Kornet': (375, 7, 100, 'Barracks'),
    'Commando': (400, 8, 140, 'WarFactory'),
    'Su35': (1400, 20, 180, 'Airfield'),
    'Su25': (1300, 20, 250, 'Airfield'),
    'Mi28': (1600, 22, 260, 'Airfield'),
    'Engineer': (1000, 5, 250, 'CommandCenter'),
    'SupplyTruck': (600, 10, 300, 'SupplyCenter'),
    'CommandCenter': (2000, 45, 5000, None),
    'PowerPlant': (800, 10, 1000, None),
    'Barracks': (600, 10, 1000, None),
    'SupplyCenter': (1500, 10, 1500, 'PowerPlant'),
    'WarFactory': (2000, 20, 2200, 'SupplyCenter'),
    'Airfield': (1000, 30, 1800, 'SupplyCenter'),
    'TechCenter': (2200, 40, 2500, 'WarFactory'),
    'Income': (2500, 40, 1500, 'TechCenter'),
    'GroundDefense': (800, 20, 900, 'PowerPlant'),
    'AirDefense': (1000, 25, 1100, 'PowerPlant'),
    'Superweapon': (5000, 60, 4000, 'TechCenter'),
}
PARENTS = {k:a['parent'] for k,a in ASSETS.items()}
PARENTS.update(T90='AmericaTankCrusader', Msta='AmericaVehicleTomahawk',
               TOS='AmericaVehicleTomahawk', BMP3='AmericaTankCrusader', Commando='AmericaInfantryRanger', GroundDefense='AmericaPatriotBattery')
DESCRIPTIONS = {
    'Tigr': 'Light radar scout. Detects hidden enemies nearby. Nearby enemy artillery fire triggers a brief approximate radar contact, at most once every twelve seconds. Weak machine gun; no passengers.',
    'T90': 'Affordable assault tank. One powerful shell followed by a slow reload. Sluggish movement and turret handling leave it vulnerable to kiting.',
    'BMP3': 'Armoured infantry escort. Twin autocannons cut down exposed infantry and light vehicles. Cannot clear garrisons; bring assault engineers for buildings. No passengers, anti-air or anti-tank missiles.',
    'Tunguska': 'Burst air defence. Four heavy anti-air missiles fire rapidly, followed by a six-second reload. Short-range cannon provides limited self-defence; ineffective against tanks.',
    'Msta': 'Heavy siege howitzer. Automatically sets up to fire a powerful shell, then reloads for six seconds. Inaccurate against moving targets and vulnerable up close.',
    'TOS': 'Short-range assault launcher. Eight unguided rockets saturate a target area, followed by ten seconds reloading. Must close dangerously near the enemy.',
    'Rifleman': 'Cheap rifle infantry. Screens artillery and captures buildings after Capture Training. Individually weak; no horde bonus.',
    'Kornet': 'Heavy anti-tank team. Deploys for two seconds, fires one powerful missile, then reloads for 5.6 seconds. Packs before moving. Vulnerable to infantry and close attacks; cannot engage aircraft.',
    'Commando': 'Close assault engineer. Demolition grenades clear two garrisoned infantry per hit and damage structures. Short throwing range demands armoured cover. No stealth, hero limit or sniper ability.',
    'Su35': 'Retired from normal production. Preserved for custom scenarios.',
    'Su25': 'Slow armoured strike aircraft. Six unguided explosive rockets per sortie. Strong against stationary concentrations; cannot fight aircraft.',
    'Mi28': 'Retired from normal production. Preserved for custom scenarios.',
    'Engineer': 'Builds and repairs Russian structures and clears mines.',
    'SupplyTruck': 'Collects supply crates and delivers them to the Supply Depot.',
    'CommandCenter': 'Builds engineers, supplies radar and directs a clearly telegraphed artillery preparation.',
    'PowerPlant': 'Produces eight power. Improved Turbines add another five power at this plant.',
    'Barracks': 'Trains cheap riflemen, ground-only Kornet teams and assault engineers. Research Capture Training here.',
    'SupplyCenter': 'Collects resources from supply trucks. Includes one truck when completed.',
    'WarFactory': 'Builds six specialised ground vehicles. Fast T-90 production sustains the assault; no universal armour or veterancy upgrade.',
    'Airfield': 'Four runway spaces for Su-25 ground-attack aircraft. Russia has no buildable fighter or helicopter.',
    'TechCenter': 'Unlocks siege artillery and late-game structures. Research Siege Ammunition and Assault Equipment here.',
    'Income': 'Generates $20 every two seconds while powered. Protect it to sustain a late-game army.',
    'GroundDefense': 'Fixed anti-armour cannon. Requires power; cannot engage aircraft.',
    'AirDefense': 'Radar-guided missile battery fires four-shot anti-air salvos. Requires power; cannot engage ground units.',
    'Superweapon': 'Strategic missile silo. Launches a nuclear missile after the visible six-minute countdown. Requires ten power.',
}

# New weapon definitions preserve engine projectile/FX contracts but set explicit
# burst lengths and reload windows. No horde or continuous-fire escalation.
WEAPONS = [
 ('TigrGun','HumveeGun',dict(AttackRange=145,PrimaryDamage=4,ClipSize=4,DelayBetweenShots=130,ClipReloadTime=1800,AntiAirborneVehicle='No')),
 ('T90Gun','CrusaderTankGun',dict(AttackRange=160,PrimaryDamage=100,ClipSize=1,DelayBetweenShots=0,ClipReloadTime=3400)),
 ('BMPGun','HumveeGun',dict(AttackRange=165,PrimaryDamage=7,ClipSize=0,DelayBetweenShots=100,ClipReloadTime=0,AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('TunguskaGun','HumveeGun',dict(AttackRange=160,PrimaryDamage=3,ClipSize=0,DelayBetweenShots=150,ClipReloadTime=0,AntiAirborneVehicle='Yes',AntiAirborneInfantry='Yes')),
 ('TunguskaMissile','HumveeMissileWeaponAir',dict(AttackRange=300,PrimaryDamage=55,ClipSize=4,DelayBetweenShots=180,ClipReloadTime=6000,AntiGround='No')),
 ('MstaGun','FireBaseHowitzerGun',dict(AttackRange=390,MinimumAttackRange=95,PrimaryDamage=125,PrimaryDamageRadius=22,SecondaryDamage=25,SecondaryDamageRadius=36,
     ScatterRadius=15,ScatterRadiusVsInfantry=22,ClipSize=1,DelayBetweenShots=0,ClipReloadTime=6000,MinTargetPitch=-90,MaxTargetPitch=90,PreAttackDelay=1000,PreAttackType='PER_CLIP')),
 ('TOSRocket','TomahawkMissileWeapon',dict(AttackRange=220,MinimumAttackRange=65,PrimaryDamage=28,PrimaryDamageRadius=14,
     SecondaryDamage=8,SecondaryDamageRadius=28,ClipSize=8,DelayBetweenShots=180,ClipReloadTime=10000,PreAttackDelay=0,
     ScatterRadius=22,ScatterRadiusVsInfantry=22,ProjectileObject='Russia_UnguidedRocket',ProjectileDetonationFX='FX_FireBaseHowitzerExplosion',AntiAirborneVehicle='No')),
 ('Rifle','RangerAdvancedCombatRifle',dict(AttackRange=105,PrimaryDamage=4,ClipSize=4,DelayBetweenShots=150,ClipReloadTime=1200)),
 ('KornetMissile','MissileDefenderMissileWeapon',dict(AttackRange=205,PrimaryDamage=140,PrimaryDamageRadius=5,ScatterRadiusVsInfantry=15,ClipSize=1,DelayBetweenShots=0,ClipReloadTime=5600,AntiAirborneVehicle='No',AntiAirborneInfantry='No',AntiGround='Yes')),
 ('CommandoDemolition','RangerFlashBangGrenadeWeapon',dict(AttackRange=70,MinimumAttackRange=0,PrimaryDamage=85,PrimaryDamageRadius=12,SecondaryDamage=18,SecondaryDamageRadius=23,ClipReloadTime=2800,DamageType='EXPLOSION',DeathType='EXPLODED',ProjectileDetonationFX='FX_FireBaseHowitzerExplosion',ProjectileObject='Russia_DemolitionGrenade',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('Su35Missile','RaptorJetMissileWeapon',dict(PrimaryDamage=100,ClipSize=4,AntiGround='No',AntiAirborneVehicle='Yes')),
 ('Su25Missile','RaptorJetMissileWeapon',dict(AttackRange=220,MinimumAttackRange=40,PrimaryDamage=48,PrimaryDamageRadius=15,SecondaryDamage=8,SecondaryDamageRadius=25,ClipSize=6,DelayBetweenShots=180,ScatterRadius=18,DamageType='EXPLOSION',ProjectileObject='Russia_UnguidedRocket',AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('Mi28Gun','Comanche20mmCannonWeapon',dict(PrimaryDamage=6,ClipSize=8,DelayBetweenShots=100,ClipReloadTime=1800)),
 ('Mi28Missile','ComancheAntiTankMissileWeapon',dict(PrimaryDamage=40,ClipSize=4,DelayBetweenShots=250,ClipReloadTime=5000)),
 ('DefenseGun','CrusaderTankGun',dict(AttackRange=190,PrimaryDamage=70,ClipSize=1,DelayBetweenShots=0,ClipReloadTime=2400)),
 ('DefenseMissile','PatriotMissileWeaponAir',dict(AttackRange=350,PrimaryDamage=40,ClipSize=4,DelayBetweenShots=200,ClipReloadTime=3800)),
]

def ident(key): return 'Russia_' + key
def module_headers(parent):
    return [m.groups() for line in stock.record('Object',parent)
            if (m:=re.match(r'\s*(Draw|Behavior|Body)\s*=\s*(\w+)\s+(\w+)',line))]
def read_module(parent,tag):
    # Several stock infantry modules have their final End indented less than
    # their header. Remove whitespace only; fixed-width slicing truncates End.
    source=stock.record('Object',parent)
    for i,line in enumerate(source):
        if re.match(r'\s*(Draw|Behavior|Body)\s*=\s*\w+\s+'+re.escape(tag)+r'(?:\s|$)',line):
            indent=len(line)-len(line.lstrip());result=[line.strip()]
            for rest in source[i+1:]:
                leading=len(rest)-len(rest.lstrip())
                result.append(rest[min(indent,leading):])
                if rest.strip()=='End' and leading<=indent:return result
    raise KeyError((parent,tag))
def module_copy(parent,tag,replacements=(),strip=()):
    lines=read_module(parent,tag)
    text='\n'.join(lines).replace(tag,'ModuleTag_Russia_'+tag.removeprefix('ModuleTag_'))
    for old,new in replacements:text=text.replace(old,new)
    lines=[l for l in text.splitlines() if not any(re.match(r'\s*'+x+r'\b',l) for x in strip)]
    return [f'ReplaceModule {tag}']+['  '+l for l in lines]+['End']
def added_module(kind,tag,lines,field='Behavior'):
    return [f'{field} = {kind} ModuleTag_Russia_{tag}']+['  '+l for l in lines]+['End']
def replacement(tag,kind,lines,field='Behavior',parent=None):
    # ReplaceModule only accepts the original module's exact class. Changes of
    # class must remove/add, including StructureBody over an ActiveBody parent.
    original=next((k for f,k,t in module_headers(parent) if t==tag),kind) if parent else kind
    start=[f'ReplaceModule {tag}'] if original==kind else [f'RemoveModule {tag}','AddModule']
    return start+['  '+l for l in added_module(kind,tag,lines,field)]+['End']
def ws(primary=None,secondary=None,tertiary=None,condition='None'):
    return ['WeaponSet',f'  Conditions = {condition}',*[f'  Weapon = {s} {ident(v) if v else "None"}' for s,v in
      [('PRIMARY',primary),('SECONDARY',secondary),('TERTIARY',tertiary)]],'End']
def copied_record(kind,parent,new,replacements=()):
    text='\n'.join(stock.record(kind,parent))
    for a,b in replacements:text=text.replace(a,b)
    return [f'{kind} {new}',text,'End','']

def draw(key):
    a=ASSETS[key];p=PARENTS[key];model=a['model'];category=a['category']
    removed=[f'RemoveModule {tag}' for field,kind,tag in module_headers(p) if field=='Draw']
    if category=='infantry':
        # Original articulated Russian infantry with an explicit neutral clip.
        lines=removed+['AddModule','  Draw = W3DModelDraw ModuleTag_Russia_Draw','    OkToChangeModelColor = Yes']
        states=[('NONE','_I','LOOP'),('MOVING','_R','LOOP'),('MOVING ATTACKING','_R','LOOP'),
                ('FIRING_A','_F','LOOP'),('FIRING_B','_F','LOOP'),('USING_WEAPON_A','_F','LOOP'),
                ('ATTACKING','_F','LOOP'),('UNPACKING','_F','LOOP'),('RAISING_FLAG','_F','LOOP'),
                ('PACKING','_I','LOOP'),('DYING','_X','ONCE'),('FREEFALL','_X','ONCE'),('PARACHUTING','_I','LOOP')]
        for flags,anim,mode in states:
            lines += [f'    ConditionState = {flags}',f'      Model = {model}',
                      f'      Animation = {model}.{model}{anim}',f'      AnimationMode = {mode}']
            for slot in ('PRIMARY','SECONDARY','TERTIARY'):
                lines += [f'      WeaponLaunchBone = {slot} MUZZLE01',f'      WeaponFireFXBone = {slot} MUZZLE01']
            lines += ['    End']
        return lines+['  End','End']
    wheels=4 if key=='Tigr' else 6 if key=='SupplyTruck' else 0
    tracked=category=='vehicle' and not wheels
    kind='W3DTruckDraw' if wheels else 'W3DTankDraw' if tracked else 'W3DModelDraw'
    lines=removed+['AddModule',f'  Draw = {kind} ModuleTag_Russia_Draw','    OkToChangeModelColor = Yes']
    bones=a.get('bones',[])
    for b in bones:
        if category=='building' and (key in ('Airfield','WarFactory','SupplyCenter') or b.startswith('EXIT')):
            lines.append(f'    ExtraPublicBone = {b}')
    if category=='building':
        states=[]
        for construction in ('','AWAITING_CONSTRUCTION PARTIALLY_CONSTRUCTED ACTIVELY_BEING_CONSTRUCTED'):
            for condition,suffix in [('',''),('DAMAGED','_D'),('REALLYDAMAGED RUBBLE','_E')]:
                for night in (False,True):
                    flags=' '.join(x for x in [construction,condition,'NIGHT' if night else ''] if x) or 'NONE'
                    name=model+suffix+('N' if suffix else '_N' if night else '') if night else model+suffix
                    states.append((flags,name,bool(construction)))
    else:states=[('NONE',model,False),('REALLYDAMAGED',model+'_D',False),('RUBBLE',model+'_D',False)]
    for flags,name,construction in states:
        lines += [f'    ConditionState = {flags}',f'      Model = {name}']
        if construction:lines.append('      Flags = ADJUST_HEIGHT_BY_CONSTRUCTION_PERCENT')
        if 'TURRET' in bones:
            lines += ['      Turret = TURRET','      TurretPitch = BARREL']
        for slot in ('PRIMARY','SECONDARY','TERTIARY'):
            launch='GRENADE01' if key=='BMP3' and slot=='SECONDARY' else 'MUZZLE' if key=='BMP3' and slot=='PRIMARY' else 'WEAPONA' if key in ('TOS','Su35','Su25','AirDefense') or (key in ('Tunguska','Mi28') and slot=='SECONDARY') else 'MUZZLE01'
            lines += [f'      WeaponLaunchBone = {slot} {launch}',f'      WeaponFireFXBone = {slot} {launch}']
        if key in ('T90','BMP3','Msta','GroundDefense'):
            lines += ['      WeaponRecoilBone = PRIMARY BARREL']
        if key=='Mi28' and 'RUBBLE' not in flags:
            lines += [f'      Animation = {name}.{name}','      AnimationMode = LOOP']
        if key=='Tunguska' and 'RUBBLE' not in flags:
            lines += [f'      Animation = {name}.{name}','      AnimationMode = LOOP']
        if key=='Engineer':lines += ['      ParticleSysBone = FXBUILD SparksSmall'] if 'CONSTRUCT' in flags else []
        if flags in ('REALLYDAMAGED','DAMAGED'):
            lines += ['      ParticleSysBone = SMOKE01 SmolderingSmoke']
        lines += ['    End']
    if wheels:
        labels=['LeftFront','RightFront','LeftRear','RightRear'] if wheels==4 else ['LeftFront','RightFront','MidLeftFront','MidRightFront','LeftRear','RightRear']
        lines += [f'    {l}TireBone = TIRE{i+1:02}' for i,l in enumerate(labels)]
        lines += ['    TireRotationMultiplier = 0.2','    TrackMarks = EXTireTrack.tga','    Dust = RocketBuggyDust']
    if tracked:
        lines += ['    TrackMarks = EXTnkTrack.tga','    TreadAnimationRate = 2.0','    TreadDriveSpeedFraction = 0.3','    TreadPivotSpeedFraction = 0.6']
    return lines+['  End','End']

def clean_behavior(key):
    """Remove inherited technology and all stock hull/turret/pilot death spawns."""
    p=PARENTS[key];category=ASSETS[key]['category'];lines=[]
    for field,kind,tag in module_headers(p):
        if field!='Behavior':continue
        remove=kind in {'ObjectCreationUpgrade','EjectPilotDie','HordeUpdate','LocomotorSetUpgrade',
                       'GenerateMinefieldBehavior','CommandSetUpgrade','ArmorUpgrade','PreorderCreate'}
        remove |= kind in {'WeaponSetUpgrade','MaxHealthUpgrade','ExperienceScalarUpgrade','WeaponBonusUpgrade'}
        if category=='building':
            remove |= kind=='CreateObjectDie'
            remove |= key=='CommandCenter' and kind in ('OCLSpecialPower','SpecialAbility','SpectreGunshipDeploymentUpdate','GrantScienceUpgrade')
            remove |= key=='TechCenter' and kind in ('SpecialAbility','BattlePlanUpdate','AIUpdateInterface','SpyVisionSpecialPower','SpyVisionUpdate')
            remove |= key in ('GroundDefense','AirDefense') and kind=='AssistedTargetingUpdate'
        if key=='Tigr' and kind=='TransportContain':remove=True
        if key in ('Kornet','Commando') and kind in ('SpecialAbility','SpecialAbilityUpdate','SpecialAbilityUpdateModule','StealthUpdate','CommandButtonHuntUpdate'):remove=True
        if key=='Commando' and kind in ('SpecialAbility','UnpauseSpecialPowerUpgrade'):remove=True
        if key in ('Su25','Su35') and kind=='CountermeasuresBehavior':remove=True
        if remove:
            lines.append(f'RemoveModule {tag}');continue
        body='\n'.join(read_module(p,tag))
        if kind=='CreateObjectDie':
            lines+=module_copy(p,tag,[(m,ident(key)+'_Wreck') for m in re.findall(r'CreationList\s*=\s*(\w+)',body)])
        elif kind=='SlowDeathBehavior':
            data=module_copy(p,tag,strip=('OCL',))
            if category!='infantry':data[-2:-2]=[f'    OCL = FINAL {ident(key)}_Wreck']
            lines+=data
        elif kind=='JetSlowDeathBehavior':
            data=module_copy(p,tag,strip=('OCLOnGroundDeath','OCLInitialDeath','OCLSecondary','OCLHitGround','OCLFinalBlowUp'))
            data[-2:-2]=[f'    OCLOnGroundDeath = {ident(key)}_Wreck',f'    OCLFinalBlowUp = {ident(key)}_Wreck']
            lines+=data
        elif kind=='HelicopterSlowDeathBehavior':
            data=module_copy(p,tag,strip=('OCLEjectPilot','OCLBlade','OCLHitGround','OCLFinalBlowUp','BladeObjectName','FinalRubbleObject'))
            # FinalRubbleObject is dereferenced unconditionally by the engine.
            # BladeObjectName is unused when OCLBlade is omitted.
            data[-2:-2]=['    FinalRubbleObject = Russia_Mi28Rubble']
            lines+=data
    return lines

def unit_modules(key):
    p=PARENTS[key];a=ASSETS[key];lines=[]
    if key in ('Tigr','T90','BMP3','Msta','TOS'):
        speed={'Tigr':160,'T90':65,'BMP3':100,'Msta':45,'TOS':45}[key]
        fields=['Turret',f'  TurretTurnRate = {speed}','  TurretPitchRate = 55',
            '  AllowsPitch = Yes','  ControlledWeaponSlots = PRIMARY SECONDARY','End','AutoAcquireEnemiesWhenIdle = Yes']
        kind='DeployStyleAIUpdate' if key=='Msta' else 'AIUpdateInterface'
        if key in ('Msta','TOS'):fields.insert(4,'  FirePitch = '+('45' if key=='Msta' else '30'))
        if key=='Msta':fields+=['UnpackTime = 1800','PackTime = 900','TurretsFunctionOnlyWhenDeployed = Yes']
        lines+=replacement('ModuleTag_03',kind,fields,parent=p)
        lines += [f'Locomotor = SET_NORMAL {ident(key)}Locomotor']
    if key=='Kornet':
        lines+=replacement('ModuleTag_04','DeployStyleAIUpdate',['AutoAcquireEnemiesWhenIdle = Yes','UnpackTime = 2000','PackTime = 800'],parent=p)
        lines+=['Locomotor = SET_NORMAL MissileDefenderLocomotor']
    if key=='Tigr':
        lines+=added_module('StealthDetectorUpdate','Recon',['DetectionRange = 170','DetectionRate = 500','CanDetectWhileContained = No',
            'CounterBatteryRange = 450','CounterBatteryRadius = 60','CounterBatteryRevealObject = Russia_CounterBatteryContact','CounterBatteryCooldown = 12000'])
    if key in ('Msta','TOS'):
        lines+=added_module('WeaponBonusUpgrade','SiegeAmmo',['TriggeredBy = Upgrade_RussiaSiegeAmmo'])
    if key=='Commando':
        lines+=added_module('WeaponBonusUpgrade','AssaultEquipment',['TriggeredBy = Upgrade_RussiaAssaultEquipment'])
    if key=='Rifleman':
        lines+=module_copy(p,'ModuleTag_20',[('Upgrade_InfantryCaptureBuilding','Upgrade_RussiaCapture')])
    if key=='Su25':
        lines+=module_copy(p,'ModuleTag_09')
        lines+=['Locomotor = SET_NORMAL Russia_Su25Locomotor','Locomotor = SET_TAXIING BasicJetTaxiLocomotor']
    if key=='Mi28':
        lines+=module_copy(p,'ModuleTag_06',[('TurretTurnRate = 0','TurretTurnRate = 120'),('TurretPitchRate = 0','TurretPitchRate = 90')])
        lines+=['Locomotor = SET_NORMAL ComancheLocomotor','Locomotor = SET_TAXIING BasicHelicopterTaxiLocomotor']
    return lines

def building_modules(key):
    p=PARENTS[key];lines=[]
    if key=='CommandCenter':
        lines+=module_copy(p,'ModuleTag_13',[('X:-18.0  Y:  35.0','X:-18.8 Y:34.5'),('X: 60.0  Y:  35.0','X:50.9 Y:34.5')])
        # Russia relies on its radar scout, not an American satellite scan.
        for ability,stockname in [('Barrage','ArtilleryBarrage')]:
            extra=[f'SpecialPowerTemplate = Russia_{ability}',f'OCL = Russia_ArtilleryBarrage1',
                   f'UpgradeOCL = SCIENCE_Russia{ability}2 Russia_ArtilleryBarrage2',
                   f'UpgradeOCL = SCIENCE_Russia{ability}3 Russia_ArtilleryBarrage3']
            if ability=='Barrage':extra+=['CreateLocation = CREATE_AT_EDGE_FARTHEST_FROM_TARGET']
            else:extra+=['CreateLocation = CREATE_AT_LOCATION']
            lines+=added_module('OCLSpecialPower',ability,extra)
    elif key=='PowerPlant':
        lines+=module_copy(p,'ModuleTag_07',[('Upgrade_AmericaAdvancedControlRods','Upgrade_RussiaTurbines')])
    elif key=='Barracks':
        lines+=replacement('ModuleTag_12','DefaultProductionExitUpdate',['UnitCreatePoint = X:10 Y:0 Z:0.3','NaturalRallyPoint = X:43 Y:0 Z:0.3'],parent=p)
    elif key=='SupplyCenter':
        lines+=module_copy(p,'ModuleTag_12',[('ChinaVehicleSupplyTruck','Russia_SupplyTruck')])
        lines+=replacement('ModuleTag_11','SupplyCenterProductionExitUpdate',['UnitCreatePoint = X:20 Y:20 Z:0.3','NaturalRallyPoint = X:55 Y:20 Z:0.3'],parent=p)
    elif key=='Income':
        lines+=replacement('ModuleTag_05','AutoDepositUpdate',['DepositTiming = 2000','DepositAmount = 20','InitialCaptureBonus = 0'],parent=p)
    elif key in ('GroundDefense','AirDefense'):
        lines+=replacement('ModuleTag_06','AIUpdateInterface',['Turret','  TurretTurnRate = 120','  TurretPitchRate = 120','  AllowsPitch = Yes',
            '  ControlledWeaponSlots = PRIMARY','End','AutoAcquireEnemiesWhenIdle = Yes'],parent=p)
    return lines

WEAPON_SETS = {
 'Tigr':('TigrGun',None),'T90':('T90Gun',None),'BMP3':('BMPGun',None),'Tunguska':('TunguskaGun','TunguskaMissile'),
 'Msta':('MstaGun',None),'TOS':('TOSRocket',None),'Rifleman':('Rifle',None),'Kornet':('KornetMissile',None),
 'Commando':('CommandoDemolition',None),'Su35':('Su35Missile',None),'Su25':('Su25Missile',None),
 'Mi28':('Mi28Gun','Mi28Missile'),'TechCenter':(None,None),'GroundDefense':('DefenseGun',None),'AirDefense':('DefenseMissile',None),
}
MENUS = {
 'Engineer':dict(enumerate(['PowerPlant','Barracks','SupplyCenter','WarFactory','Airfield','TechCenter','Income','GroundDefense','AirDefense','Superweapon','CommandCenter'],1)),
 'CommandCenter':{1:'Engineer',3:'PowerBarrage',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'PowerPlant':{1:'UpgradeTurbines',14:'Command_Sell'},
 'Barracks':{1:'Rifleman',2:'Kornet',3:'Commando',9:'UpgradeCapture',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'SupplyCenter':{1:'SupplyTruck',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'WarFactory':{1:'Tigr',2:'T90',3:'BMP3',4:'Tunguska',5:'Msta',6:'TOS',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'Airfield':{1:'Su25',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'TechCenter':{1:'UpgradeSiegeAmmo',2:'UpgradeAssaultEquipment',14:'Command_Sell'},
 'Income':{14:'Command_Sell'},'GroundDefense':{13:'Command_Stop',14:'Command_Sell'},
 'AirDefense':{13:'Command_Stop',14:'Command_Sell'},'Superweapon':{1:'PowerMissile',14:'Command_Sell'},
 'Infantry':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Rifleman':{1:'CaptureBuilding',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Commando':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Vehicle':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'BMP3':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Aircraft':{10:'Command_GuardFlyingUnitsOnly',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'SupplyTruck':{14:'Command_Stop'},
}
MENUS['Engineer'].update({12:'Command_DisarmMinesAtPosition',14:'Command_Stop'})
UPGRADES={
 'Turbines':('Improved Turbines','Adds five power at this plant.',400,15,'PowerPlant','OBJECT'),
 'Capture':('Capture Training','Riflemen can capture neutral and enemy buildings.',1000,20,'Rifleman','PLAYER'),
 'SiegeAmmo':('Siege Ammunition','Msta-S shells and TOS rockets deal 20% more damage. Reload windows remain unchanged.',1500,40,'Msta','PLAYER'),
 'AssaultEquipment':('Assault Equipment','Assault engineer demolition grenades deal 25% more damage. Garrison casualties remain two per hit.',800,25,'Commando','PLAYER'),
}
POWERS={
 'Barrage':('Artillery Preparation','Marks an area for everyone to see, then shells it after a warning delay. More promotion ranks add shells. Recharges in five minutes.','Command_ArtilleryBarrage','Msta'),
 'Missile':('Strategic Missile','Launches a nuclear missile at the selected target. Recharges in six minutes.','Command_NeutronMissile','Superweapon'),
}

# Every USA template asked for by the reused skirmish scripts resolves to a core
# Russian role. Additional base-side aliases cover generic builder/supply queries.
ALIASES={
 'AmericaCommandCenter':'CommandCenter','AmericaPowerPlant':'PowerPlant','AmericaBarracks':'Barracks',
 'AmericaSupplyCenter':'SupplyCenter','AmericaWarFactory':'WarFactory','AmericaAirfield':'Airfield',
 'AmericaStrategyCenter':'TechCenter','AmericaSupplyDropZone':'Income','AmericaPatriotBattery':'AirDefense',
 'AmericaFireBase':'GroundDefense','AmericaParticleCannonUplink':'Superweapon',
 'AmericaVehicleDozer':'Engineer','AmericaVehicleChinook':'SupplyTruck','AmericaInfantryRanger':'Rifleman',
 'AmericaInfantryMissileDefender':'Kornet','AmericaInfantryColonelBurton':'Commando','AmericaInfantryPathfinder':'Commando',
 'AmericaTankCrusader':'T90','AmericaTankPaladin':'T90','AmericaVehicleHumvee':'BMP3','AmericaVehicleMedic':'Tigr',
 'AmericaVehicleSentryDrone':'Tigr','AmericaTankAvenger':'Tunguska','AmericaVehicleTomahawk':'Msta','AmericaTankMicrowave':'TOS',
 'AmericaJetRaptor':'Su25','AmericaJetStealthFighter':'Su25','AmericaJetAurora':'Su25','AmericaVehicleComanche':'TOS',
 'AmericaVehicleBattleDrone':'Tigr','AmericaVehicleScoutDrone':'Tigr','AmericaVehicleHellfireDrone':'Tunguska',
 'ChinaVehicleDozer':'Engineer','ChinaVehicleSupplyTruck':'SupplyTruck','ChinaSupplyCenter':'SupplyCenter',
}

def object_record(key):
    a=ASSETS[key];parent=PARENTS[key];category=a['category'];cost,time,hp,pre=STATS[key]
    lines=[f'ChildObject {ident(key)} {parent}',f'  DisplayName = OBJECT:{ident(key)}','  Side = Russia',
        f'  ButtonImage = {ident(key)}',f'  SelectPortrait = {ident(key)}_L',f'  BuildCost = {cost}',f'  BuildTime = {time}',
        '  Buildable = '+('No' if key in RETIRED else 'Yes'),'  Prerequisites']
    if pre:lines += ['    Object = '+' '.join(ident(x) for x in pre.split())]
    lines += ['  End']
    menu=key if key in MENUS else 'Infantry' if category=='infantry' else 'Aircraft' if category=='aircraft' else 'Vehicle'
    lines += [f'  CommandSet = Russia_{menu}CommandSet']
    for i in range(1,6):lines.append(f'  UpgradeCameo{i} = NONE')
    if key in ('Msta','TOS'):lines+=['  UpgradeCameo1 = Upgrade_RussiaSiegeAmmo']
    if key=='Commando':lines+=['  UpgradeCameo1 = Upgrade_RussiaAssaultEquipment']
    if key=='Commando':lines+=['  MaxSimultaneousOfType = 0','  VisionRange = 130','  ShroudClearingRange = 220']
    if key in ('Msta','TOS'):lines+=['  KindOf = PRELOAD SELECTABLE CAN_ATTACK CAN_CAST_REFLECTIONS VEHICLE SCORE']
    if category=='infantry':
        # Original articulated meshes are authored at stock Ranger height,
        # approximately 13.5 world units, and use their own local hierarchy.
        lines+=['  Scale = 1.0']
    if key=='Tigr':lines+=['  KindOf = PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS VEHICLE SCORE','  VisionRange = 240','  ShroudClearingRange = 280']
    if key=='PowerPlant':lines+=['  EnergyProduction = 8','  EnergyBonus = 5']
    if key=='Income':lines+=['  EnergyProduction = -2','  KindOf = STRUCTURE SELECTABLE IMMOBILE SCORE FS_TECHNOLOGY MP_COUNT_FOR_VICTORY FS_SUPPLY_DROPZONE POWERED']
    if category=='building':
        x,y,z=a['dimensions'];lines += ['  Geometry = BOX',f'  GeometryMajorRadius = {x/2:.2f}',f'  GeometryMinorRadius = {y/2:.2f}',f'  GeometryHeight = {z:.2f}']
    if key in WEAPON_SETS:
        w1,w2=WEAPON_SETS[key]
        for condition in ('None','PLAYER_UPGRADE'):
            weaponlines=ws(w1,w2,condition=condition)
            if key=='Tunguska':weaponlines[-1:-1]=['  PreferredAgainst = SECONDARY AIRCRAFT']
            lines+=['  '+l for l in weaponlines]
    # A fresh body also removes inherited stock model-piece healing dependencies.
    bodytag=next(tag for field,kind,tag in module_headers(parent) if field=='Body')
    bodykind='StructureBody' if category=='building' else 'ActiveBody'
    extra=replacement(bodytag,bodykind,[f'MaxHealth = {hp}',f'InitialHealth = {hp}',f'SubdualDamageCap = {hp*2}',
            'SubdualDamageHealRate = 500','SubdualDamageHealAmount = 50'],field='Body',parent=parent)
    extra+=draw(key)+clean_behavior(key)
    extra+=building_modules(key) if category=='building' else unit_modules(key)
    # Remove the strategy centre's passive battle-plan weapon and China weapons
    # upgrades entirely; only explicitly advertised abilities remain available.
    lines+=['  '+l for l in extra]
    return lines+['End','']

def projectile_records():
    # Original visible rocket with dumb ballistic flight; cannot follow moving targets.
    return [
      'Object Russia_CounterBatteryContact','  VisionRange = 60','  ShroudClearingRange = 60',
      '  EditorSorting = SYSTEM','  KindOf = NO_COLLIDE IMMOBILE UNATTACKABLE INERT',
      '  Body = ImmortalBody ModuleTag_Russia_ContactBody','    MaxHealth = 1','    InitialHealth = 1','  End',
      '  Behavior = DeletionUpdate ModuleTag_Russia_ContactExpiry','    MinLifetime = 4000','    MaxLifetime = 4000','  End','End','',
      'ChildObject Russia_UnguidedRocket GenericTankShell',
      '  ReplaceModule ModuleTag_01',
      '    Draw = W3DModelDraw ModuleTag_Russia_RocketDraw',
      '      DefaultConditionState','        Model = RUROCKET','      End','    End','  End',
      '  ReplaceModule ModuleTag_04',
      '    Behavior = DumbProjectileBehavior ModuleTag_Russia_RocketFlight',
      '      FirstHeight = 5','      SecondHeight = 15','      FirstPercentIndent = 20%',
      '      SecondPercentIndent = 70%','      FlightPathAdjustDistPerSecond = 0',
      '    End','  End','End','',
      'ChildObject Russia_DemolitionGrenade RangerFlashBangGrenade',
      '  Scale = 0.45','  ReplaceModule ModuleTag_01',
      '    Draw = W3DModelDraw ModuleTag_Russia_GrenadeDraw',
      '      DefaultConditionState','        Model = RUROCKET','      End','    End','  End',
      '  ReplaceModule ModuleTag_05',
      '    Behavior = DumbProjectileBehavior ModuleTag_Russia_GrenadeFlight',
      '      FirstHeight = 30','      SecondHeight = 55','      FirstPercentIndent = 30%',
      '      SecondPercentIndent = 70%','      GarrisonHitKillRequiredKindOf = INFANTRY',
      '      GarrisonHitKillForbiddenKindOf = NONE','      GarrisonHitKillCount = 2',
      '      GarrisonHitKillFX = FX_FlashBangGarrisonBuildingHit','      FlightPathAdjustDistPerSecond = 0',
      '    End','  End','End','']

def build_logic():
    logic=['; Generated by scripts/factions/russia/build_faction.py.','']
    for key,parent,changes in WEAPONS:
        visible_changes=dict(changes)
        if key in ('T90Gun','KornetMissile','TunguskaMissile','MstaGun','TOSRocket','Su35Missile','Su25Missile'):
            visible_changes['ShowsAmmoPips']='Yes'
        if key in ('MstaGun','TOSRocket'):visible_changes['WeaponBonus']='PLAYER_UPGRADE DAMAGE 120%'
        if key=='CommandoDemolition':visible_changes['WeaponBonus']='PLAYER_UPGRADE DAMAGE 125%'
        logic += [f'ChildWeapon {ident(key)} {parent}',*[f'  {k} = {v}' for k,v in visible_changes.items()],'End','']
    for key,parent,speed in [('Tigr','HumveeLocomotor',78),('T90','CrusaderLocomotor',30),('BMP3','CrusaderLocomotor',36),('Msta','TomahawkLocomotor',27),('TOS','TomahawkLocomotor',30),('Su25','RaptorJetLocomotor',115)]:
        body='\n'.join(stock.record('Locomotor',parent))
        body=re.sub(r'(?m)^(\s*Speed\s*=).*$',r'\g<1> '+str(speed),body)
        body=re.sub(r'(?m)^(\s*SpeedDamaged\s*=).*$',r'\g<1> '+str(round(speed*.65)),body)
        if key in ('T90','BMP3'):
            body=re.sub(r'(?m)^(\s*TurnRate\s*=).*$',r'\g<1> 65',body)
            body=re.sub(r'(?m)^(\s*Acceleration\s*=).*$',r'\g<1> 35',body)
        if key=='Su25':body=re.sub(r'(?m)^(\s*MinSpeed\s*=).*$',r'\g<1> 65',body)
        logic += [f'Locomotor {ident(key)}Locomotor',body,'End','']
    logic += projectile_records()
    for key,a in ASSETS.items():
        if a['category']!='infantry':
            model=a['model']+('_E' if a['category']=='building' else '_D')
            logic += [f'ObjectCreationList {ident(key)}_Wreck','  CreateDebris',f'    ModelNames = {model}',
                '    Count = 1','    Mass = 120','    Disposition = SEND_IT_FLYING','    DispositionIntensity = 0.02',
                '    SpinRate = 3','    BounceSound = VehicleDebris','  End','End','']
    for name,(title,desc,cost,time,icon,scope) in UPGRADES.items():
        logic += [f'Upgrade Upgrade_Russia{name}',f'  Type = {scope}',f'  DisplayName = UPGRADE:Russia{name}',
                  f'  BuildCost = {cost}',f'  BuildTime = {time}',f'  ButtonImage = {ident(icon)}','End','']
    for rank in range(1,4):
        body='\n'.join(stock.record('ObjectCreationList',f'SUPERWEAPON_ArtilleryBarrage{rank}'))
        body=body.replace('OnlyVisibleToOwningPlayer = Yes','OnlyVisibleToOwningPlayer = No')
        body=re.sub(r'(DelayDeliveryMax\s*=)\s*\d+',r'\g<1> 8000',body)
        body=re.sub(r'(DelayDeliveryMax\s*=\s*8000)',r'DelayDeliveryMin = 6500\n    \1',body)
        logic += [f'ObjectCreationList Russia_ArtilleryBarrage{rank}',body,'End','']
    for ability in ('Barrage',):
        for rank in range(1,4):
            pre='SCIENCE_AMERICA' if rank==1 else f'SCIENCE_Russia{ability}{rank-1}'
            if ability=='Barrage' or rank>1:pre+=' SCIENCE_Rank3' if rank<3 else ' SCIENCE_Rank8'
            logic += [f'Science SCIENCE_Russia{ability}{rank}',f'  PrerequisiteSciences = {pre}','  SciencePurchasePointCost = 1',
                '  IsGrantable = Yes',f'  DisplayName = SCIENCE:Russia{ability}{rank}',f'  Description = CONTROLBAR:Russia{ability}Description','End','']
    for ability,source in [('Barrage','SuperweaponArtilleryBarrage')]:
        replacements=[]
        if ability=='Barrage':replacements=[('SCIENCE_ArtilleryBarrage1','SCIENCE_RussiaBarrage1')]
        logic+=copied_record('SpecialPower',source,ident(ability),replacements)
    logic+=['ChildObject Russia_Mi28Rubble ComancheRubbleHull','  Side = Russia','  Buildable = No',
        '  ReplaceModule ModuleTag_01','    Draw = W3DModelDraw ModuleTag_Russia_RubbleDraw',
        '      DefaultConditionState','        Model = RUMI28_D','      End','    End','  End','End','']
    for key in ASSETS:logic+=object_record(key)
    logic += ['PlayerTemplate FactionRussia','  Side = Russia','  BaseSide = USA','  PlayableSide = Yes','  StartMoney = 0',
        '  PreferredColor = R:135 G:65 B:50','  IntrinsicSciences = SCIENCE_AMERICA',
        '  PurchaseScienceCommandSetRank1 = Russia_ScienceRank1','  PurchaseScienceCommandSetRank3 = Russia_ScienceRank3',
        '  PurchaseScienceCommandSetRank8 = Russia_ScienceRank8','  SpecialPowerShortcutCommandSet = Russia_SpecialPowerShortcut',
        '  SpecialPowerShortcutWinName = GenPowersShortcutBarUS.wnd','  SpecialPowerShortcutButtonCount = 2',
        '  DisplayName = INI:FactionRussia','  StartingBuilding = Russia_CommandCenter','  StartingUnit0 = Russia_Engineer',
        '  ScoreScreenImage = Russia_LoadScreen','  LoadScreenImage = Russia_LoadScreen','  LoadScreenMusic = Load_China',
        '  ScoreScreenMusic = Score_China','  FlagWaterMark = Russia_Logo','  EnabledImage = Russia_SideIcon',
        '  BeaconName = MultiplayerBeacon','  SideIconImage = Russia_SideIcon','  GeneralImage = Russia_Logo','  OldFaction = No',
        '  ArmyTooltip = TOOLTIP:BioStrategyLong_Russia','  Features = GUI:BioFeatures_Russia',
        '  MedallionRegular = Russia_MedallionRegular','  MedallionHilite = Russia_MedallionHilite','  MedallionSelect = Russia_MedallionSelect',
        '  SkirmishAISide = America']
    logic += [f'  SkirmishAIReplace = {p} {ident(k)}' for p,k in ALIASES.items()]
    logic += ['  SkirmishAIUpgrade = Upgrade_RussiaCapture Russia_Barracks 1',
        '  SkirmishAIUpgrade = Upgrade_RussiaSiegeAmmo Russia_TechCenter 1',
        '  SkirmishAIUpgrade = Upgrade_RussiaAssaultEquipment Russia_TechCenter 1','End','']
    return '\n'.join(logic)

def mapped_image(name,texture,w,h):
    return [f'MappedImage {name}',f'  Texture = {texture}',f'  TextureWidth = {w}',f'  TextureHeight = {h}',
        f'  Coords = Left:0 Top:0 Right:{w} Bottom:{h}','  Status = NONE','End','']

def build_client():
    client=['; Generated Russia portraits, build buttons and menus.','']
    for key in ASSETS:
        for suffix in ('','_L'):client+=mapped_image(ident(key)+suffix,'rui_'+key.lower()+'.tga',128,128)
    for name in ('Logo','SideIcon','LoadScreen','MedallionRegular','MedallionHilite','MedallionSelect'):
        client+=mapped_image('Russia_'+name,'rui_'+name.lower()+'.tga',512 if name=='LoadScreen' else 128,512 if name=='LoadScreen' else 128)
    for key,a in ASSETS.items():
        command='DOZER_CONSTRUCT' if a['category']=='building' else 'UNIT_BUILD'
        client += [f'CommandButton Russia_Construct{key}',f'  Command = {command}',f'  Object = {ident(key)}',
          f'  TextLabel = CONTROLBAR:Russia_Construct{key}',f'  DescriptLabel = CONTROLBAR:Russia_Description{key}',
          f'  ButtonImage = {ident(key)}','  ButtonBorderType = BUILD','End','']
    for key,(_,_,_,_,icon,scope) in UPGRADES.items():
        client += [f'CommandButton Russia_Upgrade{key}',f'  Command = {scope}_UPGRADE',f'  Upgrade = Upgrade_Russia{key}',
          f'  TextLabel = CONTROLBAR:Russia_Upgrade{key}',f'  DescriptLabel = CONTROLBAR:Russia_Upgrade{key}Description',
          f'  ButtonImage = {ident(icon)}','  ButtonBorderType = UPGRADE','End','']
    client += ['ChildCommandButton Russia_CaptureBuilding Command_AmericaRangerCaptureBuilding',
               '  Upgrade = Upgrade_RussiaCapture','  ButtonImage = Russia_Rifleman','End','']
    for key,(_,_,source,icon) in POWERS.items():
        for shortcut in (False,True):
            name='Russia_Power'+key+('Shortcut' if shortcut else '')
            client += [f'ChildCommandButton {name} {source}',f'  TextLabel = CONTROLBAR:Russia_Power{key}',
                f'  DescriptLabel = CONTROLBAR:Russia{key}Description',f'  ButtonImage = {ident(icon)}']
            if key!='Missile':client += [f'  SpecialPower = {ident(key)}']
            if key in ('Barrage','Repair'):client += ['  Science = '+' '.join(f'SCIENCE_Russia{key}{i}' for i in range(1,4))]
            if shortcut:client += ['  Command = SPECIAL_POWER_FROM_SHORTCUT']
            client += ['End','']
    for ability in ('Barrage',):
        for rank in range(1,4):
            client += [f'CommandButton Russia_Purchase{ability}{rank}','  Command = PURCHASE_SCIENCE',
                f'  Science = SCIENCE_Russia{ability}{rank}',f'  TextLabel = SCIENCE:Russia{ability}{rank}',
                f'  DescriptLabel = CONTROLBAR:Russia{ability}Description',f'  ButtonImage = Russia_{"Msta" if ability=="Barrage" else "Engineer"}',
                '  ButtonBorderType = UPGRADE','End','']
    for menu,slots in MENUS.items():
        client += [f'CommandSet Russia_{menu}CommandSet']
        for slot,entry in sorted(slots.items()):
            button=entry if entry.startswith('Command_') else 'Russia_Construct'+entry if entry in ASSETS else 'Russia_'+entry
            client += [f'  {slot} = {button}']
        client+=['End','']
    extra={
        'ScienceRank1':{},
        'ScienceRank3':{1:'PurchaseBarrage1',2:'PurchaseBarrage2'},
        'ScienceRank8':{1:'PurchaseBarrage3'},
        'SpecialPowerShortcut':{1:'PowerBarrageShortcut',2:'PowerMissileShortcut'},
    }
    for menu,slots in extra.items():
        client += [f'CommandSet Russia_{menu}',*[f'  {slot} = Russia_{entry}' for slot,entry in sorted(slots.items())],'End','']
    return '\n'.join(client)

def build_strings():
    strings=['// Generated Russia faction names and tooltips.','']
    def add(key,value):strings.extend([key,'"'+value.replace('"',"'")+'"','END',''])
    add('INI:FactionRussia','Russia')
    add('SIDE:Russia','Russia')
    add('TOOLTIP:BioStrategyLong_Russia','Subtlety has left the factory. Open the fight with overwhelming artillery salvos, then send in the armour. Concentrated fire is devastating, but long reload windows leave artillery vulnerable. Tanks and infantry must cover the gaps.')
    add('GUI:BioFeatures_Russia','Heavy armour, oversized firepower, explosive salvos, long reloads')
    for key,a in ASSETS.items():
        add('OBJECT:'+ident(key),DISPLAY_NAMES.get(key,a['display_name']))
        add('CONTROLBAR:Russia_Construct'+key,DISPLAY_NAMES.get(key,a['display_name']))
        add('CONTROLBAR:Russia_Description'+key,DESCRIPTIONS[key])
    for key,(title,desc,*_) in UPGRADES.items():
        add('UPGRADE:Russia'+key,title);add('CONTROLBAR:Russia_Upgrade'+key,title)
        add('CONTROLBAR:Russia_Upgrade'+key+'Description',desc)
    for key,(title,desc,*_) in POWERS.items():
        add('CONTROLBAR:Russia_Power'+key,title);add('CONTROLBAR:Russia'+key+'Description',desc)
    for ability in ('Barrage',):
        for rank in range(1,4):add(f'SCIENCE:Russia{ability}{rank}',POWERS[ability][0]+' '+str(rank))
    return '\n'.join(strings)

def build_portraits():
    from PIL import Image,ImageDraw
    sys.path.insert(0, str(ROOT / 'scripts/factions/expansion'))
    from illustrated_portraits import export_portraits
    tex=DATA/'Art/Textures';tex.mkdir(parents=True,exist_ok=True)
    export_portraits('russia', 'rui', ASSETS)
    for name in ('Logo','SideIcon','LoadScreen','MedallionRegular','MedallionHilite','MedallionSelect'):
        size=512 if name=='LoadScreen' else 128
        image=Image.new('RGB',(size,size),(20,27,23));d=ImageDraw.Draw(image)
        edge=(184,139,78) if 'Select' in name else (104,155,170) if 'Hilite' in name else (156,160,136)
        d.rounded_rectangle((size*.05,size*.05,size*.95,size*.95),radius=size*.08,fill=(44,53,40),outline=edge,width=max(2,size//40))
        # A geometric industrial badge with a small national tricolour.
        points=[]
        for n in range(10):
            angle=-math.pi/2+n*math.pi/5;r=size*(.29 if n%2==0 else .13)
            points.append((size*.5+math.cos(angle)*r,size*.43+math.sin(angle)*r))
        d.polygon(points,fill=(185,177,128),outline=(231,222,173))
        for i,color in enumerate([(224,226,224),(46,91,155),(168,62,55)]):
            d.rectangle((size*.19,size*(.77+i*.035),size*.81,size*(.805+i*.035)),fill=color)
        image.save(tex/('rui_'+name.lower()+'.tga'))

def atomic_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text+'\n');os.replace(tmp,path)

def validate(logic,client):
    all_objects=re.findall(r'^ChildObject (Russia_\w+) (\w+)',logic,re.M)
    objects=[(n,p) for n,p in all_objects if n not in ('Russia_Mi28Rubble','Russia_UnguidedRocket','Russia_DemolitionGrenade')]
    units=ACTIVE_UNITS
    assert len(units)==12 and len(objects)==25
    assert len([x for x in MENUS['WarFactory'].values() if x in ASSETS])==6
    assert len(set(k for k,p in objects))==25
    assert not re.search(r'^\s*Behavior = HordeUpdate',logic,re.M)
    assert not any(k in RETIRED for menu in MENUS.values() for k in menu.values())
    assert not any(k in RETIRED for k in ALIASES.values())
    assert not any(x in logic for x in ('Upgrade_RussiaArmor','Upgrade_RussiaTraining','SCIENCE_RussiaRepair'))
    assert all(ident(k) in logic for k in ASSETS)
    local_objects={n for n,p in objects}
    for source,target in ALIASES.items():
        stock.record('Object',source)
        assert ident(target) in local_objects,(source,target)
    for n in re.findall(r'^\s*Object = (Russia_\w+)$',client,re.M):assert n in local_objects,n
    # Confirm all inherited tags and public draw/launch bones exist before load.
    for key,a in ASSETS.items():
        record=logic.split(f'ChildObject {ident(key)} ',1)[1].split('\nEnd\n',1)[0]
        valid_tags={tag for _,_,tag in module_headers(PARENTS[key])}
        changed=re.findall(r'^\s*(?:RemoveModule|ReplaceModule) (\w+)',record,re.M)
        assert len(changed)==len(set(changed)),(key,'module modified twice')
        for tag in changed:assert tag in valid_tags,(key,tag)
        for variant in a['variants']:
            assert (DATA/'Art/W3D'/f'{variant}.w3d').exists(),variant
        assert (DATA/'Art/Textures'/('rui_'+key.lower()+'.tga')).exists()
    # Every stock command referenced is present; new commands are all defined.
    defined=set(re.findall(r'^(?:ChildCommandButton|CommandButton) (\w+)',client,re.M))
    for command in re.findall(r'^\s*\d+ = (\w+)',client,re.M):
        if command not in defined:stock.record('CommandButton',command)
    assert not re.search(r'^\s*(d|nd)\s*$',logic,re.M),'Truncated End token'
    return {'faction':'FactionRussia','units':len(units),'buildings':11,'weapons':len(WEAPONS),
        'factory_buttons':6,'ai_replacements':len(ALIASES),'validation':'passed',
        'native_validation':'parent integration runner required','balance':'initial playtest baseline'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    build_portraits()
    logic=build_logic();client=build_client();strings=build_strings()
    report=validate(logic,client)
    atomic_write(DATA/'Data/INI/Addon/Logic/Russia.ini',logic)
    atomic_write(DATA/'Data/INI/Addon/Client/Russia.ini',client)
    atomic_write(DATA/'Data/english/Addon/Russia.str',strings)
    production=['Russia_PowerPlant']*4+['Russia_SupplyCenter Russia_SupplyTruck','Russia_TechCenter',
        'Russia_CommandCenter Russia_Engineer','Russia_Barracks '+','.join('Russia_'+x for x in ('Rifleman','Kornet','Commando')),
        'Russia_WarFactory '+','.join('Russia_'+x for x in ('Tigr','T90','BMP3','Tunguska','Msta','TOS')),
        'Russia_Airfield Russia_Su25',
        'Russia_Income','Russia_GroundDefense','Russia_AirDefense','Russia_Superweapon']
    atomic_write(OUT/'production.txt','\n'.join(production))
    atomic_write(OUT/'validation.json',json.dumps(report,indent=2))
    roster={'faction':'FactionRussia','art_manifest':'scripts/models/russia/manifest.json',
        'signature':'Salvos with substantial automatic reload windows; no horde bonus.',
        'unit_count':12,'building_count':11,'native_validation':'See parent native_review.py reports.',
        'limitations':['Initial balance baseline; competitive matchups need playtesting.',
                       'Stock voice/audio fallback; original faction voices have not been recorded.',
                       'Original infantry uses explicit authored idle, move, attack and death clips.',
                       'Night variants exist but illuminated repaint is deferred by the asset manifest.'],
        'roster':[dict(key=ident(k),name=DISPLAY_NAMES.get(k,a['display_name']),category=a['category'],model=a['model'],
                       parent=PARENTS[k],cost=STATS[k][0],build_seconds=STATS[k][1],health=STATS[k][2],
                       description=DESCRIPTIONS[k]) for k,a in ASSETS.items() if k not in RETIRED], 'retired_preserved_assets':sorted(RETIRED)}
    atomic_write(OUT/'roster.json',json.dumps(roster,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

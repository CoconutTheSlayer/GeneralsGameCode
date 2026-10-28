#!/usr/bin/env python3
"""Build the Ukraine add-on from original art and the player's installed game data.

Run from any directory: python3 scripts/factions/ukraine/build_faction.py
Only Ukraine-owned generated files are written. No stock visible unit/building meshes are copied. Original UA infantry and aircraft animations are used; stock gameplay behavior supplies familiar Generals controls.
"""
from pathlib import Path
import argparse
import json
import math
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'resources/macos/GameData'
OUT = ROOT / 'build/new-factions/ukraine'
sys.path.insert(0, str(ROOT / 'scripts/factions/europe'))
import stock_data as stock

MANIFEST = json.loads((ROOT / 'scripts/models/ukraine/manifest.json').read_text())
ALL_ASSETS = {a['key']: a for a in MANIFEST['assets']}
RETIRED = {'Kozak','Oplot','F16','Mi24'}
ASSETS = {k:a for k,a in ALL_ASSETS.items() if a['category'] != 'projectile' and k not in RETIRED}

# Cost, seconds, health, prerequisite. These are deliberately a playtest baseline.

STATS = {
 'Kozak':(500,8,200,'WarFactory'),'Oplot':(1050,12,470,'WarFactory'),
 'BTR4':(700,10,280,'WarFactory'),'Buk':(1000,12,260,'WarFactory'),
 'Bohdana':(1150,16,190,'TechCenter'),'DroneController':(850,13,160,'WarFactory'),
 'Rifleman':(150,4,95,'Barracks'),'Stugna':(350,6,85,'Barracks'),'MANPADS':(300,5,80,'Barracks'),
 'Commando':(450,8,100,'Barracks'),'F16':(1450,20,170,'Airfield'),
 'TB2':(650,12,110,'Airfield'),'Mi24':(1550,22,240,'TechCenter'),
 'EngineeringVehicle':(1000,5,250,'CommandCenter'),'SupplyTruck':(600,10,300,'SupplyCenter'),
 'CommandCenter':(2000,45,5000,None),'PowerPlant':(800,10,1000,None),
 'Barracks':(600,10,1000,None),'SupplyCenter':(1500,10,1500,'PowerPlant'),
 'WarFactory':(2000,20,2100,'SupplyCenter'),'Airfield':(800,18,1200,'SupplyCenter'),
 'TechCenter':(2000,35,1800,'WarFactory'),'IncomeCenter':(2500,40,1400,'TechCenter'),
 'GroundDefense':(800,20,850,'PowerPlant'),'AADefense':(1000,25,1000,'PowerPlant'),
 'Superweapon':(5000,60,4000,'TechCenter'),
}
PARENTS={k:a['parent'] for k,a in ASSETS.items()}
PARENTS.update(TB2='AmericaVehicleComanche',Commando='AmericaInfantryRanger',Airfield='AmericaBarracks',Buk='AmericaVehicleTomahawk',Bohdana='AmericaVehicleTomahawk',DroneController='AmericaVehicleTomahawk')
DESCRIPTIONS={
 'Kozak':'Fast scout with a machine gun and two infantry seats. Reveals nearby hidden enemies. Passengers dismount to fight; fragile against armour.',
 'Oplot':'Mobile main battle tank. A reliable cannon counters vehicles. Missile infantry and aircraft are dangerous without support.',
 'BTR4':'Four-seat infantry carrier with an autocannon. Strong against infantry and light vehicles. Passengers must dismount to fire.',
 'Buk':'Prepared long-range air defence. Automatically sets up for 1.2 seconds, fires two heavy missiles, then reloads for 5.5 seconds. Packs for 0.7 seconds before moving. MANPADS cover its reload; cannot attack ground targets.',
 'Bohdana':'Fast, fragile wheeled artillery. A lighter, less accurate shell trades firepower for relocation. Sets up in 0.8 seconds and packs in 0.5 seconds; 80-unit minimum range. Fire and reposition.',
 'DroneController':'Fragile long-range attack-drone van. Automatically launches one drone every 12 seconds. Normal anti-air and missile defences can shoot the drone down. No stockpiling, anti-air attack or veterancy.',
 'Rifleman':'Affordable territorial infantry for screening and holding buildings. Can capture after Capture Training. Weak alone; anti-tank teams and BTRs supply support.',
 'Stugna':'Prepared ground anti-tank infantry with steady missile fire. Sets up for 1.2 seconds; packs in 0.5 seconds. Field Concealment hides a stationary team between engagements. Fragile against infantry and detection.',
 'MANPADS':'Affordable short-range missile air defence with no setup delay. Covers Buk batteries while they move or reload. Cannot attack ground targets; shelter behind infantry and carriers.',
 'Commando':'Sapper with a short-range carbine, detection and demolition charges. Deploys one mine at his feet for $100; mine arms after 3 seconds. No hero limit or innate stealth.',
 'F16':'Multirole fighter carrying four missiles per sortie. Engages air or ground targets and returns to its airfield to reload.',
 'TB2':'Persistent unarmed scout UAV. Stays airborne without returning to reload. Wide vision, fragile against air defence. Sensor Optics unlocks a short local detection sweep.',
 'Mi24':'Attack helicopter with cannon and anti-tank missiles. Rearms automatically while flying; vulnerable to anti-air.',
 'EngineeringVehicle':'Builds and repairs Ukrainian structures and clears mines.',
 'SupplyTruck':'Collects supply crates and delivers them to the Supply Depot.',
 'CommandCenter':'Builds engineering vehicles, supplies radar, and directs reconnaissance, decoys and limited drone raids.',
 'PowerPlant':'Produces eight power. Improved Turbines add another five power at this plant.',
 'Barracks':'Trains territorial infantry, Stugna teams, MANPADS and sappers. Research Capture Training here.',
 'SupplyCenter':'Collects resources from supply trucks. Includes one truck when completed.',
 'WarFactory':'Builds BTR-4 carriers, Buk air defence, mobile Bohdana artillery and automatic drone controllers. No main battle tank.',
 'Airfield':'Compact drone assembly and launch workshop. Produces persistent unarmed TB2 scouts without runway slots or rearming.',
 'TechCenter':'Unlocks Bohdana artillery and late-game structures. Research drone replacement, concealment and sensor optics.',
 'IncomeCenter':'Generates $20 every two seconds while powered. Protect it to sustain a late-game army.',
 'GroundDefense':'A powered fixed autocannon deters infantry and light vehicles. Cannot attack aircraft; heavy armour can overpower it.',
 'AADefense':'Powered radar-guided missile battery. Engages aircraft only. Defend it from ground attackers.',
 'Superweapon':'Long-range drone command complex. Launches a conventional drone raid after a visible five-minute countdown. Air defence can intercept carriers and attack drones. Requires ten power.',
}
WEAPONS=[
 ('KozakGun','HumveeGun',dict(AttackRange=150,PrimaryDamage=6,DelayBetweenShots=150)),
 ('OplotGun','CrusaderTankGun',dict(AttackRange=160,PrimaryDamage=66,DelayBetweenShots=1600)),
 ('BTRGun','HumveeGun',dict(AttackRange=175,PrimaryDamage=9,DelayBetweenShots=160)),
 ('BukMissile','HumveeMissileWeaponAir',dict(AttackRange=350,PrimaryDamage=90,ClipSize=2,DelayBetweenShots=300,ClipReloadTime=5500,
      ShowsAmmoPips='Yes',AntiGround='No',AntiAirborneVehicle='Yes',AntiAirborneInfantry='No')),
 ('BohdanaGun','FireBaseHowitzerGun',dict(AttackRange=335,MinimumAttackRange=80,PrimaryDamage=70,PrimaryDamageRadius=12,
      SecondaryDamage=10,SecondaryDamageRadius=18,ScatterRadius=10,ScatterRadiusVsInfantry=15,
      ClipSize=1,DelayBetweenShots=0,ClipReloadTime=5000,ShowsAmmoPips='Yes',MinTargetPitch=-90,MaxTargetPitch=90)),
 ('DroneWeapon','TomahawkMissileWeapon',dict(AttackRange=300,MinimumAttackRange=60,PrimaryDamage=145,PrimaryDamageRadius=8,
      SecondaryDamage=10,SecondaryDamageRadius=12,ClipSize=1,ClipReloadTime=12000,DelayBetweenShots=12000,PreAttackDelay=300,
      ProjectileObject='Ukraine_AttackDrone',
      AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('Rifle','RangerAdvancedCombatRifle',dict(AttackRange=110,PrimaryDamage=6,DelayBetweenShots=200)),
 ('StugnaMissile','MissileDefenderMissileWeapon',dict(AttackRange=230,PrimaryDamage=60,DelayBetweenShots=1700,AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('CommandoRifle','RangerAdvancedCombatRifle',dict(AttackRange=90,PrimaryDamage=5,DelayBetweenShots=250)),
 ('MANPADSMissile','MissileDefenderMissileWeapon',dict(AttackRange=190,PrimaryDamage=35,DelayBetweenShots=1400,AntiGround='No',AntiAirborneVehicle='Yes',AntiAirborneInfantry='Yes')),
 ('F16Missile','RaptorJetMissileWeapon',dict(PrimaryDamage=90,ClipSize=4,AntiGround='Yes',AntiAirborneVehicle='Yes')),
 ('TB2Missile','RaptorJetMissileWeapon',dict(AttackRange=230,PrimaryDamage=105,ClipSize=2,AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('Mi24Gun','Comanche20mmCannonWeapon',dict(PrimaryDamage=6,DelayBetweenShots=150)),
 ('Mi24Missile','ComancheAntiTankMissileWeapon',dict(PrimaryDamage=45,ClipSize=4,DelayBetweenShots=250,ClipReloadTime=5000)),
 ('DefenseGun','HumveeGun',dict(AttackRange=195,PrimaryDamage=14,DelayBetweenShots=140)),
 ('DefenseMissile','PatriotMissileWeaponAir',dict(AttackRange=350,PrimaryDamage=45,DelayBetweenShots=500)),
]

WEAPONS.append(('DroneWeaponUpgraded','TomahawkMissileWeapon',dict(next(changes for name,parent,changes in WEAPONS if name=='DroneWeapon'),ClipReloadTime=9000,DelayBetweenShots=9000)))

def ident(key): return 'Ukraine_' + key
def module_headers(parent):
    return [m.groups() for line in stock.record('Object',parent)
            if (m:=re.match(r'\s*(Draw|Behavior|Body)\s*=\s*(\w+)\s+(\w+)',line))]
def module_copy(parent,tag,replacements=(),strip=()):
    lines=stock.module(parent,tag)
    text='\n'.join(lines).replace(tag,'ModuleTag_Ukraine_'+tag.removeprefix('ModuleTag_'))
    for old,new in replacements:text=text.replace(old,new)
    lines=[l for l in text.splitlines() if not any(re.match(r'\s*'+x+r'\b',l) for x in strip)]
    return [f'ReplaceModule {tag}']+['  '+l for l in lines]+['End']
def added_module(kind,tag,lines,field='Behavior'):
    return [f'{field} = {kind} ModuleTag_Ukraine_{tag}']+['  '+l for l in lines]+['End']

def replacement(tag,kind,lines,field='Behavior',parent=None):
    # A ReplaceModule may only replace the same type. Typed conversions are
    # explicit remove/add operations so inherited locomotor data is reset.
    oldkind=next((t for f,t,g in module_headers(parent) if g==tag),None) if parent else None
    block=['  '+l for l in added_module(kind,tag,lines,field)]
    if oldkind and oldkind!=kind:return [f'RemoveModule {tag}','AddModule']+block+['End']
    return [f'ReplaceModule {tag}']+block+['End']

def ws(primary=None,secondary=None,tertiary=None,condition='None'):
    return ['WeaponSet',f'  Conditions = {condition}',*[f'  Weapon = {s} {ident(v) if v else "None"}' for s,v in
      [('PRIMARY',primary),('SECONDARY',secondary),('TERTIARY',tertiary)]],'End']
def copied_record(kind,parent,new,replacements=()):
    text='\n'.join(stock.record(kind,parent))
    for a,b in replacements:text=text.replace(a,b)
    return [f'{kind} {new}',text,'End','']


def draw(key):
    a=ASSETS[key];p=PARENTS[key];model=a['model'];category=a['category'];bones=a['bones']
    removed=[f'RemoveModule {tag}' for field,kind,tag in module_headers(p) if field=='Draw']
    if category=='infantry':
        lines=removed+['AddModule','  Draw = W3DModelDraw ModuleTag_Ukraine_Draw','    OkToChangeModelColor = Yes']
        # Every condition uses the original UA hierarchy and authored clips.
        states=[('NONE','I','LOOP'),('MOVING','W','LOOP'),('ATTACKING','F','LOOP'),
                ('FIRING_A','F','LOOP'),('FIRING_B','F','LOOP'),('RELOADING_A','F','LOOP'),
                ('SPECIAL_CHEERING','I','LOOP'),('UNPACKING','F','LOOP'),('PACKING','F','LOOP')]
        states += [(f'DYING {flag}'.strip(),'DIE','ONCE') for flag in ('','EXPLODED_FLAILING','EXPLODED_BOUNCING')]
        for flags,clip,mode in states:
            lines += [f'    ConditionState = {flags}',f'      Model = {model}',f'      Animation = {model}.{model}_{clip}',
                f'      AnimationMode = {mode}','      WeaponLaunchBone = PRIMARY MUZZLE01',
                '      WeaponFireFXBone = PRIMARY MUZZLEFX01','    End']
        return lines+['  End','End']
    wheels=sum(b.startswith('TIRE') for b in bones)
    tracked=category=='vehicle' and not wheels
    kind='W3DTruckDraw' if wheels else 'W3DTankDraw' if tracked else 'W3DModelDraw'
    lines=removed+['AddModule',f'  Draw = {kind} ModuleTag_Ukraine_Draw','    OkToChangeModelColor = Yes']
    if category=='building':
        lines += [f'    ExtraPublicBone = {b}' for b in bones]
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
        if construction:lines+=['      Flags = ADJUST_HEIGHT_BY_CONSTRUCTION_PERCENT']
        if 'TURRET' in bones:lines+=['      Turret = TURRET']
        if 'BARREL' in bones:lines+=['      TurretPitch = BARREL']
        for slot in ('PRIMARY','SECONDARY','TERTIARY'):
            # Prefix enumeration supports the paired missile launchers.
            fxbone='MUZZLEFX01' if 'MUZZLEFX01' in bones else 'MUZZLE01'
            if 'MUZZLE01' in bones:lines += [f'      WeaponLaunchBone = {slot} MUZZLE',f'      WeaponFireFXBone = {slot} {fxbone}']
        if key in ('Oplot','BTR4','Bohdana'):lines+=['      WeaponRecoilBone = PRIMARY BARREL']
        if key in ('Mi24','TB2') and 'RUBBLE' not in flags:
            lines += [f'      Animation = {name}.{name}','      AnimationMode = LOOP']
        if flags in ('REALLYDAMAGED','DAMAGED'):lines+=['      ParticleSysBone = SMOKE01 SmolderingSmoke']
        lines += ['    End']
    if category=='building':
        lines += ['    ConditionState = AWAITING_CONSTRUCTION','      Model = NONE','    End',
                  '    AliasConditionState = SOLD']
    if wheels:
        labels={4:['LeftFront','RightFront','LeftRear','RightRear'],
                6:['LeftFront','RightFront','MidLeftFront','MidRightFront','LeftRear','RightRear'],
                8:['LeftFront','RightFront','MidLeftFront','MidRightFront','MidLeftRear','MidRightRear','LeftRear','RightRear']}[wheels]
        lines += [f'    {label}TireBone = TIRE{i+1:02}' for i,label in enumerate(labels)]
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
            remove |= key in ('GroundDefense','AADefense') and kind=='AssistedTargetingUpdate'

        if key in ('Stugna','MANPADS') and kind in ('SpecialAbility','SpecialAbilityUpdate'):remove=True
        if key=='Commando' and kind in ('SpecialAbility','SpecialAbilityUpdate','StealthUpdate','StealthUpgrade','CommandButtonHuntUpdate','AutoFindHealingUpdate'):remove=True
        if key=='Commando' and tag=='ModuleTag_20':remove=True
        if key=='Superweapon' and kind in ('SpecialAbility','ParticleUplinkCannonUpdate','SpecialPowerCreate'):remove=True
        if key=='Airfield' and kind=='HealContain':remove=True
        if key=='TB2' and kind in ('CountermeasuresBehavior','HelicopterSlowDeathBehavior'):remove=True
        if remove:
            lines.append(f'RemoveModule {tag}');continue
        if kind=='CreateObjectDie':
            body='\n'.join(stock.module(p,tag))
            lines+=module_copy(p,tag,[(m,ident(key)+'_Wreck') for m in re.findall(r'CreationList\s*=\s*(\w+)',body)])
        elif kind=='SlowDeathBehavior':
            data=module_copy(p,tag,strip=('OCL',))
            if category!='infantry':data[-2:-2]=[f'    OCL = FINAL {ident(key)}_Wreck']
            lines+=data
        elif kind=='InstantDeathBehavior':
            data=module_copy(p,tag,strip=('OCL',))
            if category!='infantry':data[-2:-2]=[f'    OCL = {ident(key)}_Wreck']
            lines+=data
        elif kind=='JetSlowDeathBehavior':
            data=module_copy(p,tag,strip=('OCLOnGroundDeath','OCLInitialDeath','OCLSecondary','OCLHitGround','OCLFinalBlowUp'))
            data[-2:-2]=[f'    OCLOnGroundDeath = {ident(key)}_Wreck',f'    OCLFinalBlowUp = {ident(key)}_Wreck']
            lines+=data
        elif kind=='HelicopterSlowDeathBehavior':
            data=module_copy(p,tag,[("ComancheRubbleHull","Ukraine_Mi24Rubble"),("ComancheBlades","Ukraine_Mi24Rubble"),
                ("Propeller02","SMOKE01"),("Propeller01","ROTOR")],
                strip=('OCLEjectPilot','OCLBlade','OCLHitGround','OCLFinalBlowUp'))
            lines+=data
    return lines


def unit_modules(key):
    p=PARENTS[key];a=ASSETS[key];lines=[]
    if key in ('BTR4','Buk','Bohdana','DroneController','Stugna'):
        kind='TransportAIUpdate' if key=='BTR4' else 'DeployStyleAIUpdate' if key in ('Buk','Bohdana','Stugna') else 'AIUpdateInterface'
        settings=['AutoAcquireEnemiesWhenIdle = Yes']
        if key not in ('Stugna',):
            settings += ['Turret','  TurretTurnRate = 130','  RecenterTime = 900','  ControlledWeaponSlots = PRIMARY']
            if key=='Bohdana':settings+=['  TurretPitchRate = 60','  AllowsPitch = Yes','  FirePitch = 45']
            settings+=['End']
        if key in ('Buk','Bohdana','Stugna'):
            settings+=['UnpackTime = '+('800' if key=='Bohdana' else '1200'),
                       'PackTime = '+('700' if key=='Buk' else '500'),
                       'TurretsFunctionOnlyWhenDeployed = Yes','TurretsMustCenterBeforePacking = No']
        lines+=replacement('ModuleTag_04' if key=='Stugna' else 'ModuleTag_03',kind,settings,parent=p)
        if key=='BTR4':
            if any(tag=='ModuleTag_20' for _,_,tag in module_headers(p)):lines+=['RemoveModule ModuleTag_20']
            contain='\n'.join(stock.module(p,'ModuleTag_05'))
            contain=re.sub(r'PassengersAllowedToFire\s*=\s*Yes','PassengersAllowedToFire = No',contain)
            contain=re.sub(r'Slots\s*=\s*5','Slots = 4',contain)
            contain=re.sub(r'NumberOfExitPaths\s*=\s*3','NumberOfExitPaths = 1',contain).replace('ModuleTag_05','ModuleTag_Ukraine_Contain')
            lines+=['ReplaceModule ModuleTag_05']+['  '+l for l in contain.splitlines()]+['End']
        lines += ['Locomotor = SET_NORMAL MissileDefenderLocomotor' if key=='Stugna' else f'Locomotor = SET_NORMAL {ident(key)}Locomotor']
    if key=='TB2':
        ai=next(tag for field,kind,tag in module_headers(p) if kind=='JetAIUpdate')
        lines+=replacement(ai,'AIUpdateInterface',['AutoAcquireEnemiesWhenIdle = No'],parent=p)
        lines+=['Locomotor = SET_NORMAL Ukraine_TB2Locomotor']
        lines+=added_module('OCLSpecialPower','SensorSweep',['SpecialPowerTemplate = Ukraine_SensorSweep','OCL = Ukraine_CreateSensorPulse','CreateLocation = CREATE_AT_LOCATION','StartsPaused = Yes'])
        lines+=added_module('UnpauseSpecialPowerUpgrade','Optics',['TriggeredBy = Upgrade_UkraineOptics','SpecialPowerTemplate = Ukraine_SensorSweep'])
        lines+=added_module('SlowDeathBehavior','DroneDeath',['DeathTypes = ALL','DestructionDelay = 0','FX = FINAL FX_GenericMissileDeath','OCL = FINAL Ukraine_TB2_Wreck'])
    if key=='DroneController':lines+=added_module('WeaponSetUpgrade','DroneReplacement',['TriggeredBy = Upgrade_UkraineDrones'])
    if key in ('Rifleman','Stugna','Commando','DroneController'):
        lines+=added_module('StealthUpdate','Concealed',['StealthDelay = 3500','StealthForbiddenConditions = MOVING ATTACKING USING_ABILITY FIRING_PRIMARY TAKING_DAMAGE','FriendlyOpacityMin = 75%','FriendlyOpacityMax = 75%','InnateStealth = No','OrderIdleEnemiesToAttackMeUponReveal = Yes'])
        lines+=added_module('StealthUpgrade','Concealment',['TriggeredBy = Upgrade_UkraineConcealment'])
    if key=='Rifleman':lines+=module_copy(p,'ModuleTag_20',[('Upgrade_InfantryCaptureBuilding','Upgrade_UkraineCapture')])
    if key=='Commando':
        lines+=added_module('StealthDetectorUpdate','SapperDetection',['DetectionRange = 130','DetectionRate = 500','CanDetectWhileContained = No'])
        lines+=added_module('SpecialAbility','Demolition',['SpecialPowerTemplate = Ukraine_Demolition','UpdateModuleStartsAttack = Yes'])
        lines+=added_module('SpecialAbilityUpdate','PlantDemolition',['SpecialPowerTemplate = Ukraine_Demolition','StartAbilityRange = 5','PreparationTime = 0','SpecialObject = TNTStickyBomb','MaxSpecialObjects = 1','SpecialObjectsPersistWhenOwnerDies = Yes','SpecialObjectsPersistent = Yes','UniqueSpecialObjectTargets = Yes','UnpackTime = 3500','PackTime = 0','FleeRangeAfterCompletion = 75'])
        lines+=added_module('OCLSpecialPower','Mine',['SpecialPowerTemplate = Ukraine_LayMine','OCL = Ukraine_CreateArmingMine','CreateLocation = CREATE_AT_LOCATION','MoneyCost = 100'])
    return lines

def building_modules(key):
    p=PARENTS[key];lines=[]
    bones={b['name']:b['position'] for b in ASSETS[key]['bone_contract']}
    def point(name):
        x,y,z=bones[name]
        return f'X:{x} Y:{y} Z:{z}'
    exits=['UnitCreatePoint = '+point('EXITSTART'),'NaturalRallyPoint = '+point('EXITEND')]
    if key=='CommandCenter':
        lines+=replacement('ModuleTag_13','DefaultProductionExitUpdate',exits)
        lines+=added_module('OCLSpecialPower','Recon',['SpecialPowerTemplate = Ukraine_Recon','OCL = SUPERWEAPON_SpySatellite','CreateLocation = CREATE_AT_LOCATION'])
        lines+=added_module('OCLSpecialPower','DroneRaid',['SpecialPowerTemplate = Ukraine_DroneRaid','OCL = Ukraine_Raid1','UpgradeOCL = SCIENCE_UkraineDroneRaid2 Ukraine_Raid2','CreateLocation = CREATE_AT_EDGE_NEAR_SOURCE'])
        lines+=added_module('OCLSpecialPower','Decoy',['SpecialPowerTemplate = Ukraine_Decoy','OCL = Ukraine_CreateDecoys','CreateLocation = CREATE_AT_LOCATION','OCLAdjustPositionToPassable = Yes'])
    elif key=='PowerPlant':
        lines+=module_copy(p,'ModuleTag_07',[('Upgrade_AmericaAdvancedControlRods','Upgrade_UkraineTurbines')])
    elif key in ('Barracks','Airfield'):
        lines+=replacement('ModuleTag_12','DefaultProductionExitUpdate',exits)
    elif key=='SupplyCenter':
        lines+=module_copy(p,'ModuleTag_12',[('ChinaVehicleSupplyTruck','Ukraine_SupplyTruck')])
        lines+=replacement('ModuleTag_11','SupplyCenterProductionExitUpdate',exits)
    elif key=='WarFactory':
        lines+=replacement('ModuleTag_11','DefaultProductionExitUpdate',exits)
    elif key=='Superweapon':
        lines+=added_module('OCLSpecialPower','LongRangeRaid',['SpecialPowerTemplate = Ukraine_LongRangeRaid','OCL = Ukraine_RaidSuper','CreateLocation = CREATE_AT_EDGE_NEAR_SOURCE'])
        lines+=added_module('SpecialPowerCreate','RaidTimer',[])
    elif key=='IncomeCenter':
        lines+=replacement('ModuleTag_05','AutoDepositUpdate',['DepositTiming = 2000','DepositAmount = 20','InitialCaptureBonus = 0'],parent=p)
    elif key in ('GroundDefense','AADefense'):
        lines+=replacement('ModuleTag_06','AIUpdateInterface',['Turret','  TurretTurnRate = 120','  TurretPitchRate = 120','  AllowsPitch = Yes',
            '  ControlledWeaponSlots = PRIMARY','End','AutoAcquireEnemiesWhenIdle = Yes'])
    return lines


WEAPON_SETS={
 'Kozak':('KozakGun',None),'Oplot':('OplotGun',None),'BTR4':('BTRGun',None),'Buk':('BukMissile',None),
 'Bohdana':('BohdanaGun',None),'DroneController':('DroneWeapon',None),'Rifleman':('Rifle',None),'Stugna':('StugnaMissile',None),
 'MANPADS':('MANPADSMissile',None),'Commando':('CommandoRifle',None),'F16':('F16Missile',None),'TB2':(None,None),
 'Mi24':('Mi24Gun','Mi24Missile'),'TechCenter':(None,None),'GroundDefense':('DefenseGun',None),'AADefense':('DefenseMissile',None),
}

MENUS = {
 'EngineeringVehicle':dict(enumerate(['PowerPlant','Barracks','SupplyCenter','WarFactory','Airfield','TechCenter','IncomeCenter','GroundDefense','AADefense','Superweapon','CommandCenter'],1)),
 'CommandCenter':{1:'EngineeringVehicle',3:'PowerDroneRaid',5:'PowerDecoy',7:'PowerRecon',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'PowerPlant':{1:'UpgradeTurbines',14:'Command_Sell'},
 'Barracks':{1:'Rifleman',2:'Stugna',3:'MANPADS',4:'Commando',9:'UpgradeCapture',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'SupplyCenter':{1:'SupplyTruck',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'WarFactory':{1:'BTR4',2:'Buk',3:'Bohdana',4:'DroneController',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'Airfield':{1:'TB2',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'TechCenter':{1:'UpgradeDrones',2:'UpgradeConcealment',3:'UpgradeOptics',14:'Command_Sell'},
 'IncomeCenter':{14:'Command_Sell'},'GroundDefense':{13:'Command_Stop',14:'Command_Sell'},
 'AADefense':{13:'Command_Stop',14:'Command_Sell'},'Superweapon':{1:'PowerLongRangeRaid',14:'Command_Sell'},
 'Infantry':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Rifleman':{1:'CaptureBuilding',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Commando':{1:'LayMine',2:'Demolition',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Vehicle':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'BTR4':{1:'Command_TransportExit',2:'Command_TransportExit',3:'Command_TransportExit',4:'Command_TransportExit',
         9:'Command_Evacuate',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Aircraft':{10:'Command_GuardFlyingUnitsOnly',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'TB2':{1:'SensorSweep',13:'Command_Guard',14:'Command_Stop'},
 'SupplyTruck':{14:'Command_Stop'},
}

MENUS['EngineeringVehicle'].update({12:'Command_DisarmMinesAtPosition',14:'Command_Stop'})
UPGRADES={
 'Turbines':('Improved Turbines','Adds five power at this plant.',400,15,'PowerPlant','OBJECT'),
 'Capture':('Capture Training','Riflemen can capture neutral and enemy buildings.',1000,20,'Rifleman','PLAYER'),
 'Drones':('Workshop Drone Kits','Drone controller reload time improves from 12 to 9 seconds. Does not create or stockpile extra drones.',1200,35,'DroneController','PLAYER'),
 'Concealment':('Field Concealment','Territorial infantry, Stugna teams, sappers and drone controllers hide after 3.5 seconds stationary without attacking or taking damage. Detectors reveal them.',1200,35,'Commando','PLAYER'),
 'Optics':('Sensor Optics','Unlocks a local TB2 sensor sweep: reveals hidden enemies within 210 range for 8 seconds, then recharges for 45 seconds.',800,25,'TB2','PLAYER'),
}
POWERS={
 'Recon':('Recon Sweep','Reveals a target area temporarily. Recharges in one minute.','Command_SpySatelliteScan','TB2'),
 'DroneRaid':('Drone Raid','One strike carrier launches six interceptable drones. Rank two adds a second carrier. Recharges in four minutes.','Command_A10ThunderboltMissileStrike','DroneController'),
 'Decoy':('Decoy Deployment','Deploys two unarmed, fragile BTR decoys at a visible location for 35 seconds. Recharges in two minutes.','Command_SpySatelliteScan','BTR4'),
 'LongRangeRaid':('Long-Range Drone Raid','Four strike carriers each launch six conventional attack drones. Air defence can intercept both carriers and drones. Visible five-minute countdown.','Command_A10ThunderboltMissileStrike','Superweapon'),
}

# Every USA template asked for by the reused skirmish scripts resolves to a core
# Ukrainian role. Additional base-side aliases cover generic builder/supply queries.
ALIASES={
 'AmericaCommandCenter':'CommandCenter','AmericaPowerPlant':'PowerPlant','AmericaBarracks':'Barracks',
 'AmericaSupplyCenter':'SupplyCenter','AmericaWarFactory':'WarFactory','AmericaAirfield':'Airfield',
 'AmericaStrategyCenter':'TechCenter','AmericaSupplyDropZone':'IncomeCenter','AmericaPatriotBattery':'AADefense',
 'AmericaFireBase':'GroundDefense','AmericaParticleCannonUplink':'Superweapon',
 'AmericaVehicleDozer':'EngineeringVehicle','AmericaVehicleChinook':'SupplyTruck','AmericaInfantryRanger':'Rifleman',
 'AmericaInfantryMissileDefender':'Stugna','AmericaInfantryColonelBurton':'Commando','AmericaInfantryPathfinder':'MANPADS',
 'AmericaTankCrusader':'BTR4','AmericaTankPaladin':'DroneController','AmericaVehicleHumvee':'BTR4','AmericaVehicleMedic':'BTR4',
 'AmericaVehicleSentryDrone':'DroneController','AmericaTankAvenger':'Buk','AmericaVehicleTomahawk':'Bohdana','AmericaTankMicrowave':'DroneController',
 'AmericaJetRaptor':'TB2','AmericaJetStealthFighter':'DroneController','AmericaJetAurora':'Bohdana','AmericaVehicleComanche':'BTR4',
 'AmericaVehicleBattleDrone':'BTR4','AmericaVehicleScoutDrone':'BTR4','AmericaVehicleHellfireDrone':'Buk',
 'ChinaVehicleDozer':'EngineeringVehicle','ChinaVehicleSupplyTruck':'SupplyTruck','ChinaSupplyCenter':'SupplyCenter',
}

def object_record(key):
    a=ASSETS[key];parent=PARENTS[key];category=a['category'];cost,time,hp,pre=STATS[key]
    lines=[f'ChildObject {ident(key)} {parent}',f'  DisplayName = OBJECT:{ident(key)}','  Side = Ukraine',
        f'  ButtonImage = {ident(key)}',f'  SelectPortrait = {ident(key)}_L',f'  BuildCost = {cost}',f'  BuildTime = {time}',
        '  Buildable = Yes','  Prerequisites']
    if pre:lines += ['    Object = '+' '.join(ident(x) for x in pre.split())]
    lines += ['  End']
    menu=key if key in MENUS else 'Infantry' if category=='infantry' else 'Aircraft' if category=='aircraft' else 'Vehicle'
    lines += [f'  CommandSet = Ukraine_{menu}CommandSet']
    # Native comparison against the installed infantry keeps the original UA
    # rigs readable beside the other factions at the normal gameplay camera.
    # Native side-by-side review of the detailed rig against Ranger and Israel.
    if category=='infantry':lines+=['  Scale = 1.5']
    for i in range(1,6):lines.append(f'  UpgradeCameo{i} = NONE')
    if key=='DroneController':lines+=['  UpgradeCameo1 = Upgrade_UkraineDrones']
    if key in ('Rifleman','Stugna','Commando','DroneController'):lines+=['  UpgradeCameo2 = Upgrade_UkraineConcealment']
    if key=='Commando':lines+=['  MaxSimultaneousOfType = 0']
    if key=='Kozak':lines+=['  VisionRange = 240','  ShroudClearingRange = 280']
    if key=='DroneController':lines+=['  VisionRange = 230','  ShroudClearingRange = 230','  IsTrainable = No']
    if key=='TB2':lines+=['  VisionRange = 300','  ShroudClearingRange = 350','  KindOf = PRELOAD CAN_CAST_REFLECTIONS SELECTABLE VEHICLE SCORE AIRCRAFT DRONE','  UpgradeCameo1 = Upgrade_UkraineOptics','  SoundAmbient = NoSound']
    if key=='Airfield':lines+=['  KindOf = PRELOAD STRUCTURE SELECTABLE IMMOBILE SCORE CAPTURABLE FS_FACTORY AUTO_RALLYPOINT MP_COUNT_FOR_VICTORY FS_AIRFIELD','  EnergyProduction = -1']
    if key=='PowerPlant':lines+=['  EnergyProduction = 8','  EnergyBonus = 5']
    if key=='IncomeCenter':lines+=['  EnergyProduction = -2','  KindOf = STRUCTURE SELECTABLE IMMOBILE SCORE FS_TECHNOLOGY MP_COUNT_FOR_VICTORY FS_SUPPLY_DROPZONE POWERED']
    if category in ('building','vehicle','aircraft'):
        x,y,z=a['dimensions']['size'];lines += ['  Geometry = BOX',f'  GeometryMajorRadius = {x/2:.2f}',f'  GeometryMinorRadius = {y/2:.2f}',f'  GeometryHeight = {z:.2f}']
    if key in WEAPON_SETS:
        w1,w2=WEAPON_SETS[key]
        for condition in ('None','PLAYER_UPGRADE'):
            weaponlines=ws('DroneWeaponUpgraded' if key=='DroneController' and condition=='PLAYER_UPGRADE' else w1,w2,condition=condition)
            if key=='Commando':weaponlines=[x.replace('Ukraine_ColonelBurtonKnifeWeapon','ColonelBurtonKnifeWeapon') for x in weaponlines]
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


def drone_records():
    locomotor='\n'.join(stock.record('Locomotor','TomahawkMissileLocomotor'))
    locomotor=re.sub(r'(?m)^(\s*(?:Speed|SpeedDamaged|MinSpeed)\s*=)\s*[^\n]+',r'\1 65',locomotor)
    locomotor=re.sub(r'(?m)^(\s*PreferredHeight\s*=)\s*[^\n]+',r'\1 55',locomotor)
    lines=['Locomotor Ukraine_AttackDroneLocomotor',locomotor,'End','',
        'ChildObject Ukraine_AttackDrone TomahawkMissile','  Side = Ukraine','  Buildable = No',
        '  KindOf = PRELOAD CAN_CAST_REFLECTIONS PROJECTILE SMALL_MISSILE DRONE VEHICLE AIRCRAFT',
        '  RemoveModule ModuleTag_01','  AddModule','    Draw = W3DModelDraw ModuleTag_Ukraine_DroneDraw',
        '      OkToChangeModelColor = Yes','      DefaultConditionState','        Model = UAFPV','      End','    End','  End',
        '  ReplaceModule ModuleTag_07','    Behavior = MissileAIUpdate ModuleTag_Ukraine_DroneGuidance',
        '      TryToFollowTarget = Yes','      FuelLifetime = 10000','      IgnitionDelay = 0','      IgnitionFX = NONE',
        '      InitialVelocity = 65','      DistanceToTravelBeforeTurning = 15','      DistanceToTargetBeforeDiving = 65',
        '      DistanceToTargetForLock = 10','    End','  End',
        '  Locomotor = SET_NORMAL Ukraine_AttackDroneLocomotor',
        '  ReplaceModule ModuleTag_02','    Body = ActiveBody ModuleTag_Ukraine_DroneHealth',
        '      MaxHealth = 20','      InitialHealth = 20','    End','  End',
        '  ReplaceModule DeathModuleTag_02','    Behavior = InstantDeathBehavior ModuleTag_Ukraine_DroneLaserDeath',
        '      DeathTypes = NONE +LASERED','      FX = FX_GenericMissileDisintegrate','    End','  End',
        '  Geometry = BOX','  GeometryMajorRadius = 2.5','  GeometryMinorRadius = 1.7','  GeometryHeight = 1.2',
        '  Shadow = SHADOW_VOLUME','End','']
    return lines

def build_logic():
    logic=['; Generated by scripts/factions/ukraine/build_faction.py.','']+drone_records()
    for key,parent,changes in WEAPONS:
        logic += [f'ChildWeapon {ident(key)} {parent}',*[f'  {k} = {v}' for k,v in changes.items()],'End','']
    for key,parent,speed in [('Kozak','HumveeLocomotor',85),('BTR4','HumveeLocomotor',62),('Buk','CrusaderLocomotor',40),('Bohdana','HumveeLocomotor',50),('DroneController','HumveeLocomotor',58),('TB2','ComancheLocomotor',95)]:
        body='\n'.join(stock.record('Locomotor',parent))
        body=re.sub(r'(?m)^(\s*Speed\s*=).*$',r'\g<1> '+str(speed),body)
        body=re.sub(r'(?m)^(\s*SpeedDamaged\s*=).*$',r'\g<1> '+str(round(speed*.65)),body)
        if key=='TB2':body=re.sub(r'(?m)^(\s*PreferredHeight\s*=).*$',r'\g<1> 100',body)
        logic += [f'Locomotor {ident(key)}Locomotor',body,'End','']
    for key,a in ASSETS.items():
        if a['category']!='infantry':
            model=a['model']+('_E' if a['category']=='building' else '_D')
            logic += [f'ObjectCreationList {ident(key)}_Wreck','  CreateDebris',f'    ModelNames = {model}',
                '    Count = 1','    Mass = 120','    Disposition = SEND_IT_FLYING','    DispositionIntensity = 0.02',
                '    SpinRate = 3','    BounceSound = VehicleDebris','  End','End','']
    for name,(title,desc,cost,time,icon,scope) in UPGRADES.items():
        logic += [f'Upgrade Upgrade_Ukraine{name}',f'  Type = {scope}',f'  DisplayName = UPGRADE:Ukraine{name}',
                  f'  BuildCost = {cost}',f'  BuildTime = {time}',f'  ButtonImage = {ident(icon)}','End','']
    from support import support_logic
    logic+=support_logic(stock)
    for key in ASSETS:logic+=object_record(key)
    logic+=support_logic(stock, post=True)
    logic += ['PlayerTemplate FactionUkraine','  Side = Ukraine','  BaseSide = USA','  PlayableSide = Yes','  StartMoney = 0',
        '  PreferredColor = R:70 G:110 B:195','  IntrinsicSciences = SCIENCE_AMERICA',
        '  PurchaseScienceCommandSetRank1 = Ukraine_ScienceRank1','  PurchaseScienceCommandSetRank3 = Ukraine_ScienceRank3',
        '  PurchaseScienceCommandSetRank8 = Ukraine_ScienceRank8','  SpecialPowerShortcutCommandSet = Ukraine_SpecialPowerShortcut',
        '  SpecialPowerShortcutWinName = GenPowersShortcutBarUS.wnd','  SpecialPowerShortcutButtonCount = 4',
        '  DisplayName = INI:FactionUkraine','  StartingBuilding = Ukraine_CommandCenter','  StartingUnit0 = Ukraine_EngineeringVehicle',
        '  ScoreScreenImage = Ukraine_LoadScreen','  LoadScreenImage = Ukraine_LoadScreen','  LoadScreenMusic = Load_USA',
        '  ScoreScreenMusic = Score_USA','  FlagWaterMark = Ukraine_Logo','  EnabledImage = Ukraine_SideIcon',
        '  BeaconName = MultiplayerBeacon','  SideIconImage = Ukraine_SideIcon','  GeneralImage = Ukraine_Logo','  OldFaction = No',
        '  ArmyTooltip = TOOLTIP:BioStrategyLong_Ukraine','  Features = GUI:BioFeatures_Ukraine',
        '  MedallionRegular = Ukraine_MedallionRegular','  MedallionHilite = Ukraine_MedallionHilite','  MedallionSelect = Ukraine_MedallionSelect',
        '  SkirmishAISide = America']
    logic += [f'  SkirmishAIReplace = {p} {ident(k)}' for p,k in ALIASES.items()]
    logic += ['  SkirmishAIUpgrade = Upgrade_UkraineCapture Ukraine_Barracks 1',
        '  SkirmishAIUpgrade = Upgrade_UkraineDrones Ukraine_TechCenter 1',
        '  SkirmishAIUpgrade = Upgrade_UkraineConcealment Ukraine_TechCenter 1',
        '  SkirmishAIUpgrade = Upgrade_UkraineOptics Ukraine_TechCenter 1','End','']
    return '\n'.join(logic)

def mapped_image(name,texture,w,h):
    return [f'MappedImage {name}',f'  Texture = {texture}',f'  TextureWidth = {w}',f'  TextureHeight = {h}',
        f'  Coords = Left:0 Top:0 Right:{w} Bottom:{h}','  Status = NONE','End','']

def build_client():
    client=['; Generated Ukraine portraits, build buttons and menus.','', 'ChildCommandButton Ukraine_CaptureBuilding Command_AmericaRangerCaptureBuilding','  Upgrade = Upgrade_UkraineCapture','End','']
    for key in ASSETS:
        for suffix in ('','_L'):client+=mapped_image(ident(key)+suffix,'uai_'+key.lower()+'.tga',128,128)
    for name in ('Logo','SideIcon','LoadScreen','MedallionRegular','MedallionHilite','MedallionSelect'):
        client+=mapped_image('Ukraine_'+name,'uai_'+name.lower()+'.tga',512 if name=='LoadScreen' else 128,512 if name=='LoadScreen' else 128)
    for key,a in ASSETS.items():
        command='DOZER_CONSTRUCT' if a['category']=='building' else 'UNIT_BUILD'
        client += [f'CommandButton Ukraine_Construct{key}',f'  Command = {command}',f'  Object = {ident(key)}',
          f'  TextLabel = CONTROLBAR:Ukraine_Construct{key}',f'  DescriptLabel = CONTROLBAR:Ukraine_Description{key}',
          f'  ButtonImage = {ident(key)}','  ButtonBorderType = BUILD','End','']
    for key,(_,_,_,_,icon,scope) in UPGRADES.items():
        client += [f'CommandButton Ukraine_Upgrade{key}',f'  Command = {scope}_UPGRADE',f'  Upgrade = Upgrade_Ukraine{key}',
          f'  TextLabel = CONTROLBAR:Ukraine_Upgrade{key}',f'  DescriptLabel = CONTROLBAR:Ukraine_Upgrade{key}Description',
          f'  ButtonImage = {ident(icon)}','  ButtonBorderType = UPGRADE','End','']
    from support import support_client
    client+=support_client()
    for key,(_,_,source,icon) in POWERS.items():
        for shortcut in (False,True):
            name='Ukraine_Power'+key+('Shortcut' if shortcut else '')
            client += [f'ChildCommandButton {name} {source}',f'  TextLabel = CONTROLBAR:Ukraine_Power{key}',
                f'  DescriptLabel = CONTROLBAR:Ukraine{key}Description',f'  ButtonImage = {ident(icon)}']
            client += [f'  SpecialPower = {ident(key)}','  Science = SCIENCE_UkraineDroneRaid1 SCIENCE_UkraineDroneRaid2' if key=='DroneRaid' else '  Science = SCIENCE_UkraineDecoy' if key=='Decoy' else '  Science = SCIENCE_AMERICA']
            if shortcut:client += ['  Command = SPECIAL_POWER_FROM_SHORTCUT']
            client += ['End','']
    for ability in ('DroneRaid1','DroneRaid2','Decoy'):
        client += [f'CommandButton Ukraine_Purchase{ability}','  Command = PURCHASE_SCIENCE',f'  Science = SCIENCE_Ukraine{ability}',f'  TextLabel = SCIENCE:Ukraine{ability}',f'  DescriptLabel = CONTROLBAR:Ukraine{"Decoy" if ability=="Decoy" else "DroneRaid"}Description','  ButtonImage = Ukraine_DroneController','  ButtonBorderType = UPGRADE','End','']
    for menu,slots in MENUS.items():
        client += [f'CommandSet Ukraine_{menu}CommandSet']
        for slot,entry in sorted(slots.items()):
            button=entry if entry.startswith('Command_') else 'Ukraine_Construct'+entry if entry in ASSETS else 'Ukraine_'+entry
            client += [f'  {slot} = {button}']
        client+=['End','']
    extra={
        'ScienceRank1':{1:'PurchaseDecoy'},
        'ScienceRank3':{1:'PurchaseDroneRaid1'},
        'ScienceRank8':{1:'PurchaseDroneRaid2'},
        'SpecialPowerShortcut':{1:'PowerReconShortcut',2:'PowerDroneRaidShortcut',3:'PowerDecoyShortcut',4:'PowerLongRangeRaidShortcut'},
    }
    for menu,slots in extra.items():
        client += [f'CommandSet Ukraine_{menu}',*[f'  {slot} = Ukraine_{entry}' for slot,entry in sorted(slots.items())],'End','']
    return '\n'.join(client)

def build_strings():
    strings=['// Generated Ukraine faction names and tooltips.','']
    def add(key,value):strings.extend([key,'"'+value.replace('"',"'")+'"','END',''])
    add('INI:FactionUkraine','Ukraine')
    add('SIDE:Ukraine','Ukraine')
    add('TOOLTIP:BioStrategyLong_Ukraine','Find the approach, prepare an ambush, strike and relocate. Scouts expose targets for concealed anti-tank teams, prepared Buk salvos and attack drones. Fast artillery gives up shell power for mobility. Detectors, anti-air and close assaults break an unsupported ambush.')
    add('GUI:BioFeatures_Ukraine','Prepared ambushes, reconnaissance, mobile artillery, disposable attack drones')
    for key,a in ASSETS.items():
        add('OBJECT:'+ident(key),'Drone Command Complex' if key=='Superweapon' else 'Territorial Infantry' if key=='Rifleman' else a['display_name'])
        add('CONTROLBAR:Ukraine_Construct'+key,'Drone Command Complex' if key=='Superweapon' else 'Territorial Infantry' if key=='Rifleman' else a['display_name'])
        add('CONTROLBAR:Ukraine_Description'+key,DESCRIPTIONS[key])
    for key,(title,desc,*_) in UPGRADES.items():
        add('UPGRADE:Ukraine'+key,title);add('CONTROLBAR:Ukraine_Upgrade'+key,title)
        add('CONTROLBAR:Ukraine_Upgrade'+key+'Description',desc)
    for key,(title,desc,*_) in POWERS.items():
        add('CONTROLBAR:Ukraine_Power'+key,title);add('CONTROLBAR:Ukraine'+key+'Description',desc)
    for ability,title in [('DroneRaid1','Drone Raid'),('DroneRaid2','Drone Raid II'),('Decoy','Decoy Deployment')]:add('SCIENCE:Ukraine'+ability,title)
    add('CONTROLBAR:UkraineSensorSweep','Sensor Sweep')
    add('CONTROLBAR:UkraineSensorSweepDescription','After Sensor Optics, reveals hidden enemies within 210 range around the UAV for 8 seconds. Recharges in 45 seconds.')
    add('CONTROLBAR:UkraineLayMine','Deploy Mine ($100)')
    add('CONTROLBAR:UkraineLayMineDescription','Spend $100 to deploy one mine at the sapper feet. Arms after 3 seconds. No regeneration; enemies can detect and clear it. Recharges in 10 seconds.')
    add('CONTROLBAR:UkraineDemolition','Plant Demolition Charge')
    add('CONTROLBAR:UkraineDemolitionDescription','Approach a vehicle or structure and spend 3.5 seconds planting a timed demolition charge.')
    return '\n'.join(strings)

def build_portraits():
    from PIL import Image,ImageDraw
    sys.path.insert(0, str(ROOT / 'scripts/factions/expansion'))
    from illustrated_portraits import export_portraits
    tex=DATA/'Art/Textures';tex.mkdir(parents=True,exist_ok=True)
    export_portraits('ukraine', 'uai', ASSETS)
    for name in ('Logo','SideIcon','LoadScreen','MedallionRegular','MedallionHilite','MedallionSelect'):
        size=512 if name=='LoadScreen' else 128
        image=Image.new('RGB',(size,size),(20,27,23));d=ImageDraw.Draw(image)
        edge=(184,139,78) if 'Select' in name else (104,155,170) if 'Hilite' in name else (156,160,136)
        d.rounded_rectangle((size*.05,size*.05,size*.95,size*.95),radius=size*.08,fill=(44,53,40),outline=edge,width=max(2,size//40))
        # Original reconnaissance crest; the blue/gold flag identifies the faction.
        d.polygon([(size*.5,size*.17),(size*.8,size*.64),(size*.5,size*.54),(size*.2,size*.64)],fill=(197,187,116),outline=(232,223,164))
        d.line([(size*.5,size*.24),(size*.5,size*.6)],fill=(42,71,78),width=max(2,size//35))
        for i,color in enumerate([(49,103,175),(222,186,64)]):
            d.rectangle((size*.19,size*(.77+i*.05),size*.81,size*(.82+i*.05)),fill=color)
        image.save(tex/('uai_'+name.lower()+'.tga'))

def atomic_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text+'\n');os.replace(tmp,path)

def validate(logic,client):
    valid_flags=set(re.findall(r'"([A-Z][A-Z_0-9]+)"',(ROOT/'GeneralsMD/Code/GameEngine/Source/Common/BitFlags.cpp').read_text()))|{'NONE'}
    for condition in re.findall(r'^\s*(?:ConditionState|AliasConditionState)\s*=\s*([^\n]+)',logic,re.M):
        assert all(flag in valid_flags for flag in condition.split()),condition
    objects=re.findall(r'^ChildObject (Ukraine_\w+) (\w+)',logic,re.M)
    units=[k for k,a in ASSETS.items() if a['category']!='building']
    assert len(units)==11
    assert len([k for k,a in ASSETS.items() if a['category']=='building'])==11
    assert len([x for x in MENUS['WarFactory'].values() if x in ASSETS])==4
    assert len(set(k for k,p in objects))==len(objects)
    assert not re.search(r'^\s*Behavior = HordeUpdate',logic,re.M)
    assert all(ident(k) in logic for k in ASSETS)
    assert not RETIRED.intersection(ALIASES.values())
    assert all(entry not in RETIRED for slots in MENUS.values() for entry in slots.values())
    assert not any(ident(key) in {name for name,parent in objects} for key in RETIRED)
    assert 'ParticleUplinkCannonUpdate' not in logic
    assert 'Ukraine_TB2Missile' not in '\n'.join(ws(*WEAPON_SETS['TB2']))
    # Check role boundaries, including inherited values that can silently turn
    # a distinctive weapon back into a conventional escort or all-purpose gun.
    weapons={key:values for key,parent,values in WEAPONS}
    buk=weapons['BukMissile'];bohdana=weapons['BohdanaGun']
    assert buk['ClipSize']==2 and buk['ClipReloadTime']>=5000
    assert buk['AntiGround']=='No' and buk['ShowsAmmoPips']=='Yes'
    assert 'DeployStyleAIUpdate' in '\n'.join(unit_modules('Buk'))
    assert 'UnpackTime = 1200' in '\n'.join(unit_modules('Buk'))
    assert 'PackTime = 700' in '\n'.join(unit_modules('Buk'))
    assert bohdana['AttackRange']<=340 and bohdana['PrimaryDamage']<90
    assert bohdana['PrimaryDamageRadius']<=12 and bohdana['ScatterRadius']>0
    assert weapons['StugnaMissile']['AntiAirborneVehicle']=='No'
    assert weapons['MANPADSMissile']['AntiGround']=='No'
    local_objects={n for n,p in objects}
    for name,parent,changes in WEAPONS:
        stock.record('Weapon',parent)
        for field,value in changes.items():
            if field.endswith('FX') and value!='NONE':stock.record('FXList',value)
    for source,target in ALIASES.items():
        stock.record('Object',source)
        assert ident(target) in local_objects,(source,target)
    for n in re.findall(r'^\s*Object = (Ukraine_\w+)$',client,re.M):assert n in local_objects,n
    # Confirm all inherited tags and public draw/launch bones exist before load.
    for key,a in ASSETS.items():
        record=logic.split(f'ChildObject {ident(key)} ',1)[1].split('\nEnd\n',1)[0]
        valid_tags={tag for _,_,tag in module_headers(PARENTS[key])}
        changed=re.findall(r'^\s*(?:RemoveModule|ReplaceModule) (\w+)',record,re.M)
        assert len(changed)==len(set(changed)),(key,'module modified twice')
        for tag in changed:assert tag in valid_tags,(key,tag)
        kinds={tag:kind for _,kind,tag in module_headers(PARENTS[key])}
        for tag,kind in re.findall(r'ReplaceModule (\w+)\s+(?:Draw|Behavior|Body)\s*=\s*(\w+)',record):
            assert kinds[tag]==kind,(key,tag,kinds[tag],kind)
        new_tags=re.findall(r'(?:Draw|Behavior|Body)\s*=\s*\w+\s+(\w+)',record)
        assert len(new_tags)==len(set(new_tags)),(key,'duplicate new module tag')
        for variant in a['variants']:
            assert (DATA/'Art/W3D'/f'{variant}.w3d').exists(),variant
        assert (DATA/'Art/Textures'/('uai_'+key.lower()+'.tga')).exists()
    # Every portrait and localization reference resolves locally.
    for texture in re.findall(r'^\s*Texture = (\S+)',client,re.M):
        assert (DATA/'Art/Textures'/texture).exists(),texture
    string_keys=set(re.findall(r'^(\w+:\w+)$',build_strings(),re.M))
    for label in re.findall(r'(?:DisplayName|TextLabel|DescriptLabel|ArmyTooltip|Features)\s*=\s*(\w+:\w+)',logic+'\n'+client):
        if 'Ukraine' in label:assert label in string_keys,label
    # Every stock command referenced is present; new commands are all defined.
    defined=set(re.findall(r'^(?:ChildCommandButton|CommandButton) (\w+)',client,re.M))
    for command in re.findall(r'^\s*\d+ = (\w+)',client,re.M):
        if command not in defined:stock.record('CommandButton',command)
    return {'faction':'FactionUkraine','units':len(units),'buildings':len(ASSETS)-len(units),'weapons':len(WEAPONS),'attack_drone_hp':20,'attack_drone_max_life_ms':10000,'attack_drone_reload_ms':12000,
        'factory_buttons':4,'ai_replacements':len(ALIASES),'validation':'passed',
        'identity':{'buk':'automatic setup, heavy two-missile AA salvo, exposed reload',
                    'bohdana':'fast relocation with lighter scattered shells',
                    'stugna':'concealed prepared position with sustained ground-only fire'},
        'native_validation':'parent integration runner required','balance':'initial playtest baseline'}

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--skip-portraits',action='store_true',help='Regenerate gameplay data while preserving every existing art file.')
    args=parser.parse_args()
    OUT.mkdir(parents=True,exist_ok=True)
    if not args.skip_portraits:build_portraits()
    logic=build_logic();client=build_client();strings=build_strings()
    report=validate(logic,client)
    atomic_write(DATA/'Data/INI/Addon/Logic/Ukraine.ini',logic)
    atomic_write(DATA/'Data/INI/Addon/Client/Ukraine.ini',client)
    atomic_write(DATA/'Data/english/Addon/Ukraine.str',strings)
    production=['Ukraine_PowerPlant']*4+['Ukraine_SupplyCenter Ukraine_SupplyTruck','Ukraine_TechCenter',
        'Ukraine_CommandCenter Ukraine_EngineeringVehicle','Ukraine_Barracks '+','.join('Ukraine_'+x for x in ('Rifleman','Stugna','MANPADS','Commando')),
        'Ukraine_WarFactory '+','.join('Ukraine_'+x for x in ('BTR4','Buk','Bohdana','DroneController')),
        'Ukraine_Airfield '+','.join('Ukraine_'+x for x in ('TB2',)),
        'Ukraine_IncomeCenter','Ukraine_GroundDefense','Ukraine_AADefense','Ukraine_Superweapon']
    atomic_write(OUT/'production.txt','\n'.join(production))
    atomic_write(OUT/'validation.json',json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

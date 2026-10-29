#!/usr/bin/env python3
"""Build the Israel add-on from original art and the player's installed game data.

Run from any directory: python3 scripts/factions/israel/build_faction.py
Only Israel-owned generated files are written. No stock visible unit/building meshes
are copied. Installed engine behaviours are reused with original IL infantry clips.
"""
from pathlib import Path
import json
import math
import os
import re
import sys

ROOT = Path(__file__).resolve().parents[3]
DATA = ROOT / 'resources/macos/GameData'
OUT = ROOT / 'build/new-factions/israel'
sys.path.insert(0, str(ROOT / 'scripts/factions/europe'))
import stock_data as stock

MANIFEST = json.loads((ROOT / 'scripts/models/israel/manifest.json').read_text())
ASSETS = {a['key']: a for a in MANIFEST['assets']}

# Cost, seconds, health, prerequisite. These are deliberately a playtest baseline.
STATS = {
 'SandCat':(550,8,240,'Factory'),'Merkava':(1500,16,700,'Factory'),
 'Namer':(1000,12,650,'Factory'),'Pereh':(1300,16,330,'TechCentre'),
 'SPYDER':(1000,13,300,'Factory'),'PULS':(1500,20,260,'TechCentre'),
 'Rifleman':(250,6,210,'Barracks'),'Spike':(350,6,100,'Barracks'),
 'Commando':(450,8,90,'Barracks'),'F16I':(1500,22,180,'Airfield'),
 'F15I':(1800,25,220,'TechCentre'),'Apache':(1600,22,260,'Airfield'),
 'D9':(1000,5,300,'CommandCentre'),'SupplyTruck':(600,10,300,'SupplyCentre'),
 'CommandCentre':(2000,45,5000,None),'Power':(800,10,1000,None),
 'Barracks':(600,10,1000,None),'SupplyCentre':(1500,10,1500,'Power'),
 'Factory':(2000,20,2200,'SupplyCentre'),'Airfield':(1000,30,1800,'SupplyCentre'),
 'TechCentre':(2500,45,2500,'Factory Airfield'),'Income':(2500,40,1500,'TechCentre'),
 'GroundDefence':(850,20,1000,'Power'),'AirDefence':(1000,25,1100,'Power'),
 'Superweapon':(5000,60,4000,'TechCentre'),
}
PARENTS = {k:a['parent'] for k,a in ASSETS.items()}
PARENTS.update(SPYDER='AmericaTankAvenger',Superweapon='ChinaNuclearMissileLauncher')
RETIRED = {'PULS','F15I','Apache'}
CORE = {k for k,a in ASSETS.items() if a['category']!='building'} - RETIRED
DISPLAY_NAMES = {'Rifleman':'Assault Infantry','Commando':'Forward Observer','F16I':'F-16I Precision Fighter'}
DESCRIPTIONS = {
 'SandCat':'Fast scout with a machine gun and hidden-unit detection. Fragile against armour; no passengers.',
 'Merkava':'Heavy assault tank with personal active protection. Intercepts one small missile aimed at itself every eight seconds. Vulnerable to shells and missile saturation.',
 'Namer':'Heavy six-seat assault carrier with a machine gun and personal active protection. Quickly unloads infantry to fight; passengers cannot fire inside. One interception every eight seconds.',
 'Pereh':'Long-range precision missile tank hunter. High single-target damage, slow reload and a minimum range. Requires current friendly vision of the target. Needs an escort against infantry.',
 'SPYDER':'Responsive escort air defence. Fires a steady stream of missiles without deployment or a long salvo reload. Shorter reach than heavy air-defence batteries; cannot attack ground units.',
 'PULS':'Long-range rocket artillery fires four rockets per salvo. Fragile and vulnerable inside its minimum range; reloads for eight seconds.',
 'Rifleman':'Durable close-assault infantry with short rifle bursts. Namer carriers help them close through enemy fire. Assault Grenades clear garrisons; Capture Training captures buildings.',
 'Spike':'Responsive ground anti-tank infantry. Fires without a deployment delay after dismounting; modest range rewards protected delivery. Cannot engage aircraft. Vulnerable to infantry and area weapons.',
 'Commando':'Fragile forward observer with long sight range and a defensive rifle. Conceals while stationary. Keeps targets visible for Pereh missiles; no demolition charges or hero limit.',
 'F16I':'Precision ground-strike aircraft. Two powerful low-splash missiles per sortie; inefficient against dispersed groups and unable to engage aircraft. Returns to the airfield to reload.',
 'F15I':'Heavy strike aircraft. Four explosive missiles per sortie; attacks ground targets only. Uses an airfield space and returns to reload.',
 'Apache':'Attack helicopter with a cannon and anti-tank missiles. Rearms automatically in the field. Vulnerable to anti-air.',
 'D9':'Armoured engineer vehicle. Builds, repairs and clears mines. Breaching Kits add health and protection from explosions so it can open mined routes under fire.',
 'SupplyTruck':'Collects supply crates and delivers them to the Supply Centre.',
 'CommandCentre':'Builds D9 engineers, supplies radar, and coordinates research-gated reconnaissance and narrow precision strikes.',
 'Power':'Produces eight power. Improved Turbines add another five power at this plant.',
 'Barracks':'Trains assault infantry, Spike teams and forward observers. Research Capture Training and Assault Grenades here.',
 'SupplyCentre':'Collects resources from supply trucks. Includes one truck when completed.',
 'Factory':'Builds SandCat, Merkava, Namer, SPYDER and Pereh. Repairs vehicles at its service bay.',
 'Airfield':'Four runway spaces support F-16I precision ground-strike sorties.',
 'TechCentre':'Unlocks Pereh and late-game structures. Research Reinforced Armour, Reconnaissance Link and D9 Breaching Kits.',
 'Income':'Generates $20 every two seconds while powered. Protect it to sustain a late-game army.',
 'GroundDefence':'Fixed Spike missile launcher. Effective against armour. Requires power and cannot engage aircraft.',
 'AirDefence':'Radar-guided missile battery. Requires power and cannot engage ground units.',
 'Superweapon':'Strategic missile battery. Launches a high-explosive missile after the visible six-minute countdown. Requires ten power.',
}
# Pereh needs a small positive contact radius to register missile impacts.
# Its five-unit radius has no secondary blast; zero silently misses impacts.
WEAPONS = [
 ('SandCatGun','HumveeGun',dict(AttackRange=155,PrimaryDamage=8,DelayBetweenShots=200)),
 ('MerkavaGun','CrusaderTankGun',dict(AttackRange=150,PrimaryDamage=78,DelayBetweenShots=2100)),
 ('NamerGun','HumveeGun',dict(AttackRange=160,PrimaryDamage=7,DelayBetweenShots=200)),
 ('PerehMissile','TomahawkMissileWeapon',dict(RequiresTargetVision='Yes',AttackRange=315,MinimumAttackRange=80,PrimaryDamage=170,PrimaryDamageRadius=5,SecondaryDamage=0,SecondaryDamageRadius=0,ClipSize=1,ClipReloadTime=5000,PreAttackDelay=400)),
 ('SPYDERMissile','HumveeMissileWeaponAir',dict(AttackRange=280,PrimaryDamage=45,ClipSize=0,DelayBetweenShots=1100,ClipReloadTime=0,PreAttackDelay=0,AntiGround='No',AntiAirborneVehicle='Yes',AntiAirborneInfantry='No')),
 ('PULSRocket','TomahawkMissileWeapon',dict(AttackRange=360,MinimumAttackRange=90,PrimaryDamage=40,PrimaryDamageRadius=16,SecondaryDamage=12,SecondaryDamageRadius=28,ClipSize=4,DelayBetweenShots=250,ClipReloadTime=8000,PreAttackDelay=0,ScatterRadiusVsInfantry=18)),
 ('Rifle','RangerAdvancedCombatRifle',dict(AttackRange=90,PrimaryDamage=8,ClipSize=3,DelayBetweenShots=200,ClipReloadTime=800)),
 ('SpikeMissile','MissileDefenderMissileWeapon',dict(AttackRange=175,PrimaryDamage=48,ClipSize=0,DelayBetweenShots=1200,ClipReloadTime=0,PreAttackDelay=0,AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('CommandoRifle','RangerAdvancedCombatRifle',dict(PrimaryDamage=4,AttackRange=90,DelayBetweenShots=650)),
 ('AssaultGrenade','RangerFlashBangGrenadeWeapon',dict(AttackRange=135)),
 ('PrecisionStrikeDamage','A10ThunderboltMissileWeapon',dict(PrimaryDamage=350,PrimaryDamageRadius=10,SecondaryDamage=30,SecondaryDamageRadius=25)),
 ('F16IMissile','RaptorJetMissileWeapon',dict(PrimaryDamage=170,PrimaryDamageRadius=4,ClipSize=2,AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('F15IMissile','RaptorJetMissileWeapon',dict(PrimaryDamage=100,PrimaryDamageRadius=18,ClipSize=4,AntiGround='Yes',AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('ApacheGun','Comanche20mmCannonWeapon',dict(PrimaryDamage=6)),
 ('ApacheMissile','ComancheAntiTankMissileWeapon',dict(PrimaryDamage=50,ClipSize=4,DelayBetweenShots=250,ClipReloadTime=4500)),
 ('DefenseMissile','PatriotMissileWeapon',dict(AttackRange=210,PrimaryDamage=45,PrimaryDamageRadius=3,ClipSize=2,DelayBetweenShots=200,ClipReloadTime=2200,AntiAirborneVehicle='No',AntiAirborneInfantry='No')),
 ('DefenseAirMissile','PatriotMissileWeaponAir',dict(AttackRange=350,PrimaryDamage=55,ClipSize=2,DelayBetweenShots=250,ClipReloadTime=2400)),
 ('PersonalAPS','PaladinPointDefenseLaser',dict(AttackRange=100,DelayBetweenShots=8000)),
]

def ident(key): return 'Israel_' + key
def module_headers(parent):
    return [m.groups() for line in stock.record('Object',parent)
            if (m:=re.match(r'\s*(Draw|Behavior|Body)\s*=\s*(\w+)\s+(\w+)',line))]
def read_module(parent,tag):
    # Several stock infantry modules have their final End indented less than
    # their header. Remove whitespace only; fixed-width slicing truncates End.
    source=stock.record('Object',parent)
    for i,line in enumerate(source):
        if (m:=re.match(r'\s*(Draw|Behavior|Body)\s*=\s*\w+\s+(\w+)',line)) and m[2]==tag:
            indent=len(line)-len(line.lstrip());result=[line.strip()]
            for rest in source[i+1:]:
                leading=len(rest)-len(rest.lstrip())
                result.append(rest[min(indent,leading):])
                if rest.strip()=='End' and leading<=indent:return result
    raise KeyError((parent,tag))
def module_copy(parent,tag,replacements=(),strip=()):
    lines=read_module(parent,tag)
    text='\n'.join(lines).replace(tag,'ModuleTag_Israel_'+tag.removeprefix('ModuleTag_'))
    for old,new in replacements:text=text.replace(old,new)
    lines=[l for l in text.splitlines() if not any(re.match(r'\s*'+x+r'\b',l) for x in strip)]
    return [f'ReplaceModule {tag}']+['  '+l for l in lines]+['End']
def added_module(kind,tag,lines,field='Behavior'):
    return [f'{field} = {kind} ModuleTag_Israel_{tag}']+['  '+l for l in lines]+['End']
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
        lines=removed+['AddModule','  Draw = W3DModelDraw ModuleTag_Israel_Draw','    OkToChangeModelColor = Yes']
        for flags,anim,mode in [('NONE','_I','LOOP'),('MOVING','_R','LOOP'),('FIRING_A','_F','LOOP'),('FIRING_B','_F','LOOP'),('ATTACKING','_F','LOOP'),('DYING','_X','ONCE'),('FREEFALL','_X','ONCE'),('PARACHUTING','_I','LOOP')]:
            lines += [f'    ConditionState = {flags}',f'      Model = {model}']
            if anim:lines += [f'      Animation = {model}.{model}{anim}',f'      AnimationMode = {mode}']
            for slot in ('PRIMARY','SECONDARY','TERTIARY'):
                lines += [f'      WeaponLaunchBone = {slot} MUZZLE01',f'      WeaponFireFXBone = {slot} MUZZLE01']
            lines += ['    End']
        lines += ['  End','End']
        return lines
    wheels=4 if key=='SandCat' else 6 if key in ('SupplyTruck','SPYDER','PULS') else 0
    tracked=category=='vehicle' and not wheels
    kind='W3DTruckDraw' if wheels else 'W3DTankDraw' if tracked else 'W3DModelDraw'
    lines=removed+['AddModule',f'  Draw = {kind} ModuleTag_Israel_Draw','    OkToChangeModelColor = Yes']
    bones=a.get('bones',[])
    for b in bones:
        if b in ('LASER','APSFX','EXITSTART','EXITEND') or (category=='building' and key in ('Airfield','Factory','SupplyCentre')):
            lines.append(f'    ExtraPublicBone = {b}')
    if category=='building':
        states=[]
        for construction in ('','AWAITING_CONSTRUCTION','PARTIALLY_CONSTRUCTED','ACTIVELY_BEING_CONSTRUCTED'):
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
            lines += ['      Turret = TURRET']
            if 'BARREL' in bones:lines += ['      TurretPitch = BARREL']
            elif 'TURRETEL' in bones:lines += ['      TurretPitch = TURRETEL']
        for slot in ('PRIMARY','SECONDARY','TERTIARY'):
            launch='WEAPONA' if key in ('Pereh','PULS','SPYDER','F16I','F15I','AirDefence','GroundDefence') or (key=='Apache' and slot=='SECONDARY') else 'MUZZLE01'
            lines += [f'      WeaponLaunchBone = {slot} {launch}',f'      WeaponFireFXBone = {slot} {launch}']
        if key=='Merkava':
            lines += ['      WeaponRecoilBone = PRIMARY BARREL']
        if key=='Apache' and 'RUBBLE' not in flags:
            lines += [f'      Animation = {name}.{name}','      AnimationMode = LOOP']
        if key=='D9':lines += ['      ParticleSysBone = REPAIR SparksSmall'] if 'CONSTRUCT' in flags else []
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
                       'GenerateMinefieldBehavior','CommandSetUpgrade','ArmorUpgrade','PreorderCreate','CountermeasuresBehavior'}
        remove |= kind in {'WeaponSetUpgrade','MaxHealthUpgrade','ExperienceScalarUpgrade','WeaponBonusUpgrade'}
        if category=='building':
            remove |= kind=='CreateObjectDie'
            remove |= key=='CommandCentre' and kind in ('OCLSpecialPower','SpecialAbility','SpectreGunshipDeploymentUpdate','GrantScienceUpgrade')
            remove |= key=='TechCentre' and kind in ('SpecialAbility','BattlePlanUpdate','AIUpdateInterface','SpyVisionSpecialPower','SpyVisionUpdate')
            remove |= key in ('GroundDefence','AirDefence') and kind=='AssistedTargetingUpdate'
        if key=='SandCat' and kind=='TransportContain':remove=True
        if key=='Spike' and kind in ('SpecialAbility','SpecialAbilityUpdate'):remove=True
        if key=='Commando' and kind in ('SpecialAbility','SpecialAbilityUpdate','CommandButtonHuntUpdate'):remove=True
        if key=='SPYDER' and kind in ('PointDefenseLaserUpdate','OverlordContain'):remove=True
        if key in ('SandCat','Namer') and tag=='ModuleTag_20':remove=True
        if key=='Superweapon' and kind=='FireWeaponWhenDeadBehavior':remove=True
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
            data[-2:-2]=[f'    FinalRubbleObject = {ident(key)}Rubble']
            lines+=data
    return lines

def unit_modules(key):
    p=PARENTS[key];a=ASSETS[key];lines=[]
    if key in ('SandCat','Namer','Merkava','Pereh','PULS','SPYDER'):
        kind='TransportAIUpdate' if key=='Namer' else 'AIUpdateInterface'
        turret=['Turret','  TurretTurnRate = '+('60' if key in ('Pereh','PULS') else '180' if key=='SPYDER' else '120'),'  RecenterTime = 1500','  ControlledWeaponSlots = PRIMARY']
        if key in ('Merkava','Pereh','PULS','SPYDER'):
            turret += ['  TurretPitchRate = 60','  AllowsPitch = Yes']
        lines+=replacement('ModuleTag_03',kind,turret+['End','AutoAcquireEnemiesWhenIdle = Yes'],parent=p)
        lines += [f'Locomotor = SET_NORMAL {ident(key)}Locomotor']
    if key=='Namer':
        lines += replacement('ModuleTag_05','TransportContain',['PassengersAllowedToFire = No','Slots = 6','DamagePercentToUnits = 100%','AllowInsideKindOf = INFANTRY','ExitDelay = 100','NumberOfExitPaths = 1','GoAggressiveOnExit = Yes'],parent=p)
    if key=='SandCat':
        lines+=added_module('StealthDetectorUpdate','Recon',['DetectionRange = 180','DetectionRate = 500','CanDetectWhileContained = No'])
    if key in ('Merkava','Namer'):
        lines+=added_module('PointDefenseLaserUpdate','PersonalAPS',['WeaponTemplate = Israel_PersonalAPS','PrimaryTargetTypes = SMALL_MISSILE','ScanRate = 120','ScanRange = 120','PredictTargetVelocityFactor = 3','ProtectOnlySelf = Yes'])
        lines+=added_module('MaxHealthUpgrade','Armor',['TriggeredBy = Upgrade_IsraelArmor',f'AddMaxHealth = {int(STATS[key][2]*.2)}','ChangeType = ADD_CURRENT_HEALTH_TOO'])
    if key=='Rifleman':
        lines+=added_module('WeaponSetUpgrade','AssaultGrenades',['TriggeredBy = Upgrade_IsraelGrenades'])
    if key=='Commando':
        lines+=module_copy(p,'ModuleTag_07',strip=('StealthForbiddenConditions',))[:-2]+[
            '    StealthForbiddenConditions = MOVING ATTACKING FIRING_PRIMARY FIRING_SECONDARY','  End','End']
    if key=='D9':
        lines+=added_module('ArmorUpgrade','Breaching',['TriggeredBy = Upgrade_IsraelBreach'])
        lines+=added_module('MaxHealthUpgrade','BreachingHull',['TriggeredBy = Upgrade_IsraelBreach','AddMaxHealth = 200','ChangeType = ADD_CURRENT_HEALTH_TOO'])
    if key=='Rifleman':lines+=module_copy(p,'ModuleTag_20',[('Upgrade_InfantryCaptureBuilding','Upgrade_IsraelCapture')])
    if key=='Apache':
        lines+=module_copy(p,'ModuleTag_06',[('TurretTurnRate = 0','TurretTurnRate = 120')])
        lines += ['Locomotor = SET_NORMAL ComancheLocomotor','Locomotor = SET_TAXIING BasicHelicopterTaxiLocomotor']
    return lines

def building_modules(key):
    p=PARENTS[key];lines=[]
    if key=='CommandCentre':
        lines+=replacement('ModuleTag_13','DefaultProductionExitUpdate',['UnitCreatePoint = X:-18 Y:35 Z:0','NaturalRallyPoint = X:60 Y:35 Z:0'],parent=p)
        lines+=added_module('OCLSpecialPower','Recon',['SpecialPowerTemplate = Israel_Recon','OCL = SUPERWEAPON_SpySatellite','CreateLocation = CREATE_AT_LOCATION','StartsPaused = Yes'])
        lines+=added_module('UnpauseSpecialPowerUpgrade','ReconLink',['TriggeredBy = Upgrade_IsraelRecon','SpecialPowerTemplate = Israel_Recon'])
        lines+=added_module('OCLSpecialPower','Precision',['SpecialPowerTemplate = Israel_Precision','OCL = Israel_PrecisionOCL1',
            'UpgradeOCL = SCIENCE_IsraelPrecision2 Israel_PrecisionOCL2','UpgradeOCL = SCIENCE_IsraelPrecision3 Israel_PrecisionOCL3',
            'CreateLocation = CREATE_AT_EDGE_NEAR_SOURCE'])
    elif key=='Power':
        lines+=module_copy(p,'ModuleTag_07',[('Upgrade_AmericaAdvancedControlRods','Upgrade_IsraelTurbines')])
    elif key=='Barracks':
        lines+=replacement('ModuleTag_12','DefaultProductionExitUpdate',['UnitCreatePoint = X:20 Y:8 Z:0','NaturalRallyPoint = X:54 Y:8 Z:0'],parent=p)
    elif key=='SupplyCentre':
        lines+=module_copy(p,'ModuleTag_12',[('ChinaVehicleSupplyTruck','Israel_SupplyTruck')])
        lines+=replacement('ModuleTag_11','SupplyCenterProductionExitUpdate',['UnitCreatePoint = X:20 Y:20 Z:0.3','NaturalRallyPoint = X:55 Y:20 Z:0.3'],parent=p)
    elif key=='Income':
        lines+=replacement('ModuleTag_05','AutoDepositUpdate',['DepositTiming = 2000','DepositAmount = 20','InitialCaptureBonus = 0'],parent=p)
    elif key in ('GroundDefence','AirDefence'):
        lines+=replacement('ModuleTag_06','AIUpdateInterface',['Turret','  TurretTurnRate = 120','  TurretPitchRate = 120','  AllowsPitch = Yes',
            '  ControlledWeaponSlots = PRIMARY','End','AutoAcquireEnemiesWhenIdle = Yes'],parent=p)
    if key=='Superweapon':
        lines+=module_copy(p,'ModuleTag_07',[('SuperweaponNeutronMissile','Israel_StrategicMissile'),('SUPERWEAPON_NeutronMissile','Israel_StrategicMissileOCL')])
        lines+=module_copy(p,'ModuleTag_09',[('SuperweaponNeutronMissile','Israel_StrategicMissile')])
    return lines

WEAPON_SETS = {
 'SandCat':('SandCatGun',None),'Merkava':('MerkavaGun',None),'Namer':('NamerGun',None),
 'SPYDER':('SPYDERMissile',None),'Pereh':('PerehMissile',None),'PULS':('PULSRocket',None),
 'Rifleman':('Rifle',None),'Spike':('SpikeMissile',None),'Commando':('CommandoRifle',None),
 'F16I':('F16IMissile',None),'F15I':('F15IMissile',None),'Apache':('ApacheGun','ApacheMissile'),
 'TechCentre':(None,None),'GroundDefence':('DefenseMissile',None),'AirDefence':('DefenseAirMissile',None),
}

MENUS = {
 'D9':dict(enumerate(['Power','Barracks','SupplyCentre','Factory','Airfield','TechCentre','Income','GroundDefence','AirDefence','Superweapon','CommandCentre'],1)),
 'CommandCentre':{1:'D9',3:'PowerPrecision',7:'PowerRecon',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'Power':{1:'UpgradeTurbines',14:'Command_Sell'},
 'Barracks':{1:'Rifleman',2:'Spike',3:'Commando',8:'UpgradeGrenades',9:'UpgradeCapture',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'SupplyCentre':{1:'SupplyTruck',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'Factory':{1:'SandCat',2:'Merkava',3:'Namer',4:'SPYDER',5:'Pereh',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'Airfield':{1:'F16I',13:'Command_SetRallyPoint',14:'Command_Sell'},
 'TechCentre':{1:'UpgradeArmor',2:'UpgradeRecon',3:'UpgradeBreach',14:'Command_Sell'},
 'Income':{14:'Command_Sell'},'GroundDefence':{13:'Command_Stop',14:'Command_Sell'},
 'AirDefence':{13:'Command_Stop',14:'Command_Sell'},'Superweapon':{1:'PowerMissile',14:'Command_Sell'},
 'Infantry':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Rifleman':{1:'CaptureBuilding',2:'Command_AmericaRangerSwitchToMachineGun',3:'AssaultGrenadeMode',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Commando':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Vehicle':{11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Namer':{1:'Command_TransportExit',2:'Command_TransportExit',3:'Command_TransportExit',4:'Command_TransportExit',5:'Command_TransportExit',6:'Command_TransportExit',
         9:'Command_Evacuate',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'Aircraft':{10:'Command_GuardFlyingUnitsOnly',11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'},
 'SupplyTruck':{14:'Command_Stop'},
}
MENUS['D9'].update({12:'Command_DisarmMinesAtPosition',14:'Command_Stop'})
UPGRADES={
 'Turbines':('Improved Turbines','Adds five power at this plant.',400,15,'Power','OBJECT'),
 'Capture':('Capture Training','Riflemen can capture neutral and enemy buildings.',1000,20,'Rifleman','PLAYER'),
 'Armor':('Reinforced Armour','Merkava and Namer maximum health increases by 20%.',1500,40,'Merkava','PLAYER'),
 'Grenades':('Assault Grenades','Assault infantry can switch to grenades to clear garrisons.',900,30,'Rifleman','PLAYER'),
 'Recon':('Reconnaissance Link','Unlocks a one-minute Command Centre reconnaissance sweep. Ground scouts still provide persistent vision for Pereh missiles.',800,30,'SandCat','PLAYER'),
 'Breach':('D9 Breaching Kits','D9 engineers gain 200 health and take 40% less explosion damage. Clears mined routes using normal mine-clearing controls.',900,35,'D9','PLAYER'),
}
POWERS={
 'Recon':('Satellite Reconnaissance','Reveals a target area. Recharges in one minute.','Command_SpySatelliteScan','CommandCentre'),
 'Precision':('Precision Strike','One to three interceptable F-16I aircraft each deliver one low-splash missile. Punishes an exposed support vehicle; visible warning allows movement. Four-minute reload.','Command_A10ThunderboltMissileStrike','F16I'),
 'Missile':('Strategic Missile','Launches a high-explosive missile at the selected target. Recharges in six minutes.','Command_NeutronMissile','Superweapon'),
}

# Every USA template asked for by the reused skirmish scripts resolves to a core
# Israeli role. Additional base-side aliases cover generic builder/supply queries.
ALIASES={
 'AmericaCommandCenter':'CommandCentre','AmericaPowerPlant':'Power','AmericaBarracks':'Barracks',
 'AmericaSupplyCenter':'SupplyCentre','AmericaWarFactory':'Factory','AmericaAirfield':'Airfield',
 'AmericaStrategyCenter':'TechCentre','AmericaSupplyDropZone':'Income','AmericaPatriotBattery':'AirDefence',
 'AmericaFireBase':'GroundDefence','AmericaParticleCannonUplink':'Superweapon',
 'AmericaVehicleDozer':'D9','AmericaVehicleChinook':'SupplyTruck','AmericaInfantryRanger':'Rifleman',
 'AmericaInfantryMissileDefender':'Spike','AmericaInfantryColonelBurton':'Commando','AmericaInfantryPathfinder':'Commando',
 'AmericaTankCrusader':'Merkava','AmericaTankPaladin':'Merkava','AmericaVehicleHumvee':'Namer','AmericaVehicleMedic':'SandCat',
 'AmericaVehicleSentryDrone':'SandCat','AmericaTankAvenger':'SPYDER','AmericaVehicleTomahawk':'Pereh','AmericaTankMicrowave':'Namer',
 'AmericaJetRaptor':'F16I','AmericaJetStealthFighter':'F16I','AmericaJetAurora':'F16I','AmericaVehicleComanche':'F16I',
 'AmericaVehicleBattleDrone':'SandCat','AmericaVehicleScoutDrone':'SandCat','AmericaVehicleHellfireDrone':'SPYDER',
 'ChinaVehicleDozer':'D9','ChinaVehicleSupplyTruck':'SupplyTruck','ChinaSupplyCenter':'SupplyCentre',
}

def object_record(key):
    a=ASSETS[key];parent=PARENTS[key];category=a['category'];cost,time,hp,pre=STATS[key]
    lines=[f'ChildObject {ident(key)} {parent}',f'  DisplayName = OBJECT:{ident(key)}','  Side = Israel',
        f'  ButtonImage = {ident(key)}',f'  SelectPortrait = {ident(key)}_L',f'  BuildCost = {cost}',f'  BuildTime = {time}',
        f'  Buildable = {"No" if key in RETIRED else "Yes"}','  Prerequisites']
    if pre:lines += ['    Object = '+' '.join(ident(x) for x in pre.split())]
    lines += ['  End']
    menu=key if key in MENUS else 'Infantry' if category=='infantry' else 'Aircraft' if category=='aircraft' else 'Vehicle'
    lines += [f'  CommandSet = Israel_{menu}CommandSet']
    # Original IL rigs are shorter than the installed infantry; native comparison
    # uses this explicit scale to preserve Generals' readable infantry silhouettes.
    if category=='infantry':lines+=['  Scale = 1.5']
    for i in range(1,6):lines.append(f'  UpgradeCameo{i} = NONE')
    if key in ('Merkava','Namer'):lines+=['  UpgradeCameo1 = Upgrade_IsraelArmor']
    if key=='Rifleman':lines+=['  UpgradeCameo1 = Upgrade_IsraelGrenades']
    if key=='D9':lines+=['  UpgradeCameo1 = Upgrade_IsraelBreach','  ArmorSet','    Conditions = PLAYER_UPGRADE','    Armor = Israel_D9BreachingArmor','    DamageFX = TankDamageFX','  End']
    if key=='Commando':lines+=['  MaxSimultaneousOfType = 0','  VisionRange = 330','  ShroudClearingRange = 380',
        '  KindOf = PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS INFANTRY SCORE CAN_RAPPEL PARACHUTABLE']
    if key=='Pereh':lines+=['  VisionRange = 200','  ShroudClearingRange = 220',
        '  KindOf = PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS VEHICLE SCORE']
    if key=='SandCat':lines+=['  KindOf = PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS VEHICLE SCORE','  VisionRange = 240','  ShroudClearingRange = 280']
    if key=='Namer':lines+=['  ArmorSet','    Conditions = None','    Armor = TankArmor','    DamageFX = TankDamageFX','  End']
    if key=='SPYDER':lines+=['  KindOf = PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS VEHICLE SCORE']
    if key=='Power':lines+=['  EnergyProduction = 8','  EnergyBonus = 5']
    if key=='Income':lines+=['  EnergyProduction = -2','  KindOf = STRUCTURE SELECTABLE IMMOBILE SCORE FS_TECHNOLOGY MP_COUNT_FOR_VICTORY FS_SUPPLY_DROPZONE POWERED']
    if category=='building':
        x,y,z=a['dimensions'];lines += ['  Geometry = BOX',f'  GeometryMajorRadius = {x/2:.2f}',f'  GeometryMinorRadius = {y/2:.2f}',f'  GeometryHeight = {z:.2f}']
    if key in WEAPON_SETS:
        w1,w2=WEAPON_SETS[key]
        for condition in ('None','PLAYER_UPGRADE'):
            weaponlines=ws(w1,'AssaultGrenade' if key=='Rifleman' and condition=='PLAYER_UPGRADE' else w2,condition=condition)
            if key=='Commando':weaponlines=[x.replace('Israel_ColonelBurtonKnifeWeapon','ColonelBurtonKnifeWeapon') for x in weaponlines]
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

def strategic_missile():
    # Engine delivery behaviour is reused; a conventional blast has no radiation
    # field. This projectile is an effect, not an extra playable roster unit.
    out=copied_record('SpecialPower','SuperweaponNeutronMissile','Israel_StrategicMissile')
    out += ['ChildWeapon Israel_StrategicMissileWeapon NeutronMissileWeapon',
        '  ProjectileObject = Israel_StrategicMissileProjectile','  DamageType = EXPLOSION','End','',
        'ObjectCreationList Israel_StrategicMissileOCL','  FireWeapon',
        '    Weapon = Israel_StrategicMissileWeapon','  End','End','',
        'ChildObject Israel_StrategicMissileProjectile NeutronMissile',
        '  Side = Israel']
    out += ['  '+l for l in module_copy('NeutronMissile','ModuleTag_05',[('SuperweaponNeutronMissile','Israel_StrategicMissile')])]
    death=module_copy('NeutronMissile','ModuleTag_06',[('FX_Nuke','FX_MOABFinalExplosion')],strip=('OCL',))
    # NeutronMissileSlowDeath uses EXPLOSION internally. Remove radiation OCL
    # above and narrow the blast instead of retaining the nuclear area profile.
    for i,line in enumerate(death):
        if any(f'Blast{n}Enabled' in line for n in (1,2,3,4,5,7,8,9)):death[i]=re.sub(r'Yes', 'No',line)
        for field,value in {'ScorchMarkSize':200,'Blast6InnerRadius':50,'Blast6OuterRadius':150,'Blast6MaxDamage':2500,'Blast6MinDamage':200}.items():
            if re.match(r'\s*'+field+r'\s*=',line):death[i]=re.sub(r'=.*', '= '+str(value),line)
    out += ['  '+l for l in death]+['End','']
    out += ['ChildObject Israel_ApacheRubble ComancheRubbleHull','  Side = Israel','  DisplayName = OBJECT:Israel_Apache']
    out += ['  '+l for l in module_copy('ComancheRubbleHull','ModuleTag_01',[('AVComanche_D1','ILAPACH_D')])]
    out += ['End','']
    return out

def precision_strike():
    out=['ChildObject Israel_PrecisionAircraft AmericaJetA10Thunderbolt','  Side = Israel',
         '  Buildable = No','  DisplayName = OBJECT:Israel_F16I']
    out += ['  '+l for l in draw('F16I')]
    out += ['  '+l for l in ws()]
    out += ['  RemoveModule ModuleTag_06','  RemoveModule ModuleTag_Armor01','  RemoveModule ModuleTag_10']
    out += ['  '+l for l in replacement('ModuleTag_02','ActiveBody',['MaxHealth = 180','InitialHealth = 180'],field='Body',parent='AmericaJetA10Thunderbolt')]
    death=module_copy('AmericaJetA10Thunderbolt','ModuleTag_03',strip=('OCLOnGroundDeath','OCLInitialDeath','OCLSecondary','OCLHitGround','OCLFinalBlowUp'))
    death[-2:-2]=['    OCLOnGroundDeath = Israel_F16I_Wreck','    OCLFinalBlowUp = Israel_F16I_Wreck']
    out+=['  '+l for l in death]+['End','']
    for rank in range(1,4):
        body='\n'.join(stock.record('ObjectCreationList','SUPERWEAPON_A10ThunderboltMissileStrike1'))
        body=body.replace('AmericaJetA10Thunderbolt','Israel_PrecisionAircraft').replace('A10ThunderboltMissileWeapon','Israel_PrecisionStrikeDamage')
        for field,value in {'FormationSize':rank,'FormationSpacing':12,'VisibleItemsDroppedPerInterval':1,'VisibleNumBones':1,'DeliveryDecalRadius':30,'WeaponConvergenceFactor':0}.items():
            body=re.sub(r'(?m)^(\s*'+field+r'\s*=).*$',r'\g<1> '+str(value),body)
        body=body.replace('OnlyVisibleToOwningPlayer = Yes','OnlyVisibleToOwningPlayer = No')
        body='\n'.join(l for l in body.splitlines() if not re.match(r'\s*(StrafingWeaponSlot|StrafeLength|StrafeWeaponFX)\s*=',l))
        out += [f'ObjectCreationList Israel_PrecisionOCL{rank}',body,'End','']
    return out

def build_logic():
    logic=['; Generated by scripts/factions/israel/build_faction.py.','']
    for key,parent,changes in WEAPONS:
        logic += [f'ChildWeapon {ident(key)} {parent}',*[f'  {k} = {v}' for k,v in changes.items()],'End','']
    for key,parent,speed in [('SandCat','HumveeLocomotor',80),('Merkava','CrusaderLocomotor',35),('Namer','CrusaderLocomotor',40),('Pereh','TomahawkLocomotor',32),('PULS','TomahawkLocomotor',38),('SPYDER','AvengerLocomotor',45)]:
        body='\n'.join(stock.record('Locomotor',parent))
        body=re.sub(r'(?m)^(\s*Speed\s*=).*$',r'\g<1> '+str(speed),body)
        body=re.sub(r'(?m)^(\s*SpeedDamaged\s*=).*$',r'\g<1> '+str(round(speed*.65)),body)
        logic += [f'Locomotor {ident(key)}Locomotor',body,'End','']
    for key,a in ASSETS.items():
        if a['category']!='infantry':
            model=a['model']+('_E' if a['category']=='building' else '_D')
            logic += [f'ObjectCreationList {ident(key)}_Wreck','  CreateDebris',f'    ModelNames = {model}',
                '    Count = 1','    Mass = 120','    Disposition = SEND_IT_FLYING','    DispositionIntensity = 0.02',
                '    SpinRate = 3','    BounceSound = VehicleDebris','  End','End','']
    for name,(title,desc,cost,time,icon,scope) in UPGRADES.items():
        logic += [f'Upgrade Upgrade_Israel{name}',f'  Type = {scope}',f'  DisplayName = UPGRADE:Israel{name}',
                  f'  BuildCost = {cost}',f'  BuildTime = {time}',f'  ButtonImage = {ident(icon)}','End','']
    for ability in ('Precision',):
        for rank in range(1,4):
            pre='SCIENCE_AMERICA' if rank==1 else f'SCIENCE_Israel{ability}{rank-1}'
            if rank>1:pre+=' SCIENCE_Rank3' if rank==2 else ' SCIENCE_Rank8'
            logic += [f'Science SCIENCE_Israel{ability}{rank}',f'  PrerequisiteSciences = {pre}','  SciencePurchasePointCost = 1',
                '  IsGrantable = Yes',f'  DisplayName = SCIENCE:Israel{ability}{rank}',f'  Description = CONTROLBAR:Israel{ability}Description','End','']
    logic+=copied_record('SpecialPower','SpecialPowerSpySatellite','Israel_Recon')
    logic += ['SpecialPower Israel_Precision','  Enum = SPECIAL_A10_THUNDERBOLT_STRIKE','  ReloadTime = 240000',
        '  RequiredScience = SCIENCE_IsraelPrecision1','  PublicTimer = No','  SharedSyncedTimer = Yes',
        '  RadiusCursorRadius = 30','  ShortcutPower = Yes','  AcademyClassify = ACT_SUPERPOWER','End','']
    logic+=precision_strike()
    armour='\n'.join(stock.record('Armor','DozerArmor'))
    logic += ['Armor Israel_D9BreachingArmor',armour,'  Armor = EXPLOSION 60%','End','']
    logic+=strategic_missile()
    for key in ASSETS:logic+=object_record(key)
    logic += ['PlayerTemplate FactionIsrael','  Side = Israel','  BaseSide = USA','  PlayableSide = Yes','  StartMoney = 0',
        '  PreferredColor = R:120 G:155 B:195','  IntrinsicSciences = SCIENCE_AMERICA',
        '  PurchaseScienceCommandSetRank1 = Israel_ScienceRank1','  PurchaseScienceCommandSetRank3 = Israel_ScienceRank3',
        '  PurchaseScienceCommandSetRank8 = Israel_ScienceRank8','  SpecialPowerShortcutCommandSet = Israel_SpecialPowerShortcut',
        '  SpecialPowerShortcutWinName = GenPowersShortcutBarUS.wnd','  SpecialPowerShortcutButtonCount = 4',
        '  DisplayName = INI:FactionIsrael','  StartingBuilding = Israel_CommandCentre','  StartingUnit0 = Israel_D9',
        '  ScoreScreenImage = Israel_LoadScreen','  LoadScreenImage = Israel_LoadScreen','  LoadScreenMusic = Load_USA',
        '  ScoreScreenMusic = Score_USA','  FlagWaterMark = Israel_Logo','  EnabledImage = Israel_SideIcon',
        '  BeaconName = MultiplayerBeacon','  SideIconImage = Israel_SideIcon','  GeneralImage = Israel_Logo','  OldFaction = No',
        '  ArmyTooltip = TOOLTIP:BioStrategyLong_Israel','  Features = GUI:BioFeatures_Israel',
        '  MedallionRegular = Israel_MedallionRegular','  MedallionHilite = Israel_MedallionHilite','  MedallionSelect = Israel_MedallionSelect',
        '  SkirmishAISide = America']
    logic += [f'  SkirmishAIReplace = {p} {ident(k)}' for p,k in ALIASES.items()]
    logic += ['  SkirmishAIUpgrade = Upgrade_IsraelCapture Israel_Barracks 1',
        '  SkirmishAIUpgrade = Upgrade_IsraelArmor Israel_Merkava 2',
        '  SkirmishAIUpgrade = Upgrade_IsraelGrenades Israel_Rifleman 3',
        '  SkirmishAIUpgrade = Upgrade_IsraelRecon Israel_SandCat 1',
        '  SkirmishAIUpgrade = Upgrade_IsraelBreach Israel_D9 2','End','']
    return '\n'.join(logic)

def mapped_image(name,texture,w,h):
    return [f'MappedImage {name}',f'  Texture = {texture}',f'  TextureWidth = {w}',f'  TextureHeight = {h}',
        f'  Coords = Left:0 Top:0 Right:{w} Bottom:{h}','  Status = NONE','End','']

def build_client():
    client=['; Generated Israel portraits, build buttons and menus.','']
    for key in ASSETS:
        for suffix in ('','_L'):client+=mapped_image(ident(key)+suffix,'ili_'+key.lower()+'.tga',128,128)
    for name in ('Logo','SideIcon','LoadScreen','MedallionRegular','MedallionHilite','MedallionSelect'):
        client+=mapped_image('Israel_'+name,'ili_'+name.lower()+'.tga',512 if name=='LoadScreen' else 128,512 if name=='LoadScreen' else 128)
    for key,a in ASSETS.items():
        command='DOZER_CONSTRUCT' if a['category']=='building' else 'UNIT_BUILD'
        client += [f'CommandButton Israel_Construct{key}',f'  Command = {command}',f'  Object = {ident(key)}',
          f'  TextLabel = CONTROLBAR:Israel_Construct{key}',f'  DescriptLabel = CONTROLBAR:Israel_Description{key}',
          f'  ButtonImage = {ident(key)}','  ButtonBorderType = BUILD','End','']
    for key,(_,_,_,_,icon,scope) in UPGRADES.items():
        client += [f'CommandButton Israel_Upgrade{key}',f'  Command = {scope}_UPGRADE',f'  Upgrade = Upgrade_Israel{key}',
          f'  TextLabel = CONTROLBAR:Israel_Upgrade{key}',f'  DescriptLabel = CONTROLBAR:Israel_Upgrade{key}Description',
          f'  ButtonImage = {ident(icon)}','  ButtonBorderType = UPGRADE','End','']
    client += ['ChildCommandButton Israel_CaptureBuilding Command_AmericaRangerCaptureBuilding',
               '  Upgrade = Upgrade_IsraelCapture','  ButtonImage = Israel_Rifleman','End','']
    client += ['ChildCommandButton Israel_AssaultGrenadeMode Command_AmericaRangerSwitchToFlagBangGrenades',
        '  Upgrade = Upgrade_IsraelGrenades','  TextLabel = CONTROLBAR:Israel_UpgradeGrenades',
        '  DescriptLabel = CONTROLBAR:Israel_UpgradeGrenadesDescription','  ButtonImage = Israel_Rifleman','End','']
    for key,(_,_,source,icon) in POWERS.items():
        for shortcut in (False,True):
            name='Israel_Power'+key+('Shortcut' if shortcut else '')
            client += [f'ChildCommandButton {name} {source}',f'  TextLabel = CONTROLBAR:Israel_Power{key}',
                f'  DescriptLabel = CONTROLBAR:Israel{key}Description',f'  ButtonImage = {ident(icon)}']
            client += [f'  SpecialPower = {ident(key) if key!="Missile" else "Israel_StrategicMissile"}']
            if key=='Precision':client += ['  Science = '+' '.join(f'SCIENCE_Israel{key}{i}' for i in range(1,4))]
            if key=='Recon':client += ['  Options = NEED_TARGET_POS CONTEXTMODE_COMMAND NEED_UPGRADE','  Upgrade = Upgrade_IsraelRecon']
            if shortcut:client += ['  Command = SPECIAL_POWER_FROM_SHORTCUT']
            client += ['End','']
    for ability in ('Precision',):
        for rank in range(1,4):
            client += [f'CommandButton Israel_Purchase{ability}{rank}','  Command = PURCHASE_SCIENCE',
                f'  Science = SCIENCE_Israel{ability}{rank}',f'  TextLabel = SCIENCE:Israel{ability}{rank}',
                f'  DescriptLabel = CONTROLBAR:Israel{ability}Description','  ButtonImage = Israel_F16I',
                '  ButtonBorderType = UPGRADE','End','']
    for menu,slots in MENUS.items():
        client += [f'CommandSet Israel_{menu}CommandSet']
        for slot,entry in sorted(slots.items()):
            button=entry if entry.startswith('Command_') else 'Israel_Construct'+entry if entry in ASSETS else 'Israel_'+entry
            client += [f'  {slot} = {button}']
        client+=['End','']
    extra={
        'ScienceRank1':{1:'PurchasePrecision1'},
        'ScienceRank3':{1:'PurchasePrecision2'},
        'ScienceRank8':{1:'PurchasePrecision3'},
        'SpecialPowerShortcut':{1:'PowerReconShortcut',2:'PowerPrecisionShortcut',4:'PowerMissileShortcut'},
    }
    for menu,slots in extra.items():
        client += [f'CommandSet Israel_{menu}',*[f'  {slot} = Israel_{entry}' for slot,entry in sorted(slots.items())],'End','']
    return '\n'.join(client)

def build_strings():
    strings=['// Generated Israel faction names and tooltips.','']
    def add(key,value):strings.extend([key,'"'+value.replace('"',"'")+'"','END',''])
    add('INI:FactionIsrael','Israel')
    add('SIDE:Israel','Israel')
    add('TOOLTIP:BioStrategyLong_Israel','More armour. More sensors. Bring the crew home. Lead protected assaults with Merkava tanks and Namer carriers, backed by precision missiles. Personal active protection stops one incoming missile every eight seconds; shells, aircraft and missile saturation remain dangerous.')
    add('GUI:BioFeatures_Israel','Layered armour, vigilant sensors, protected crews, precision missiles')
    for key,a in ASSETS.items():
        add('OBJECT:'+ident(key),DISPLAY_NAMES.get(key,a['display_name']))
        add('CONTROLBAR:Israel_Construct'+key,DISPLAY_NAMES.get(key,a['display_name']))
        add('CONTROLBAR:Israel_Description'+key,DESCRIPTIONS[key])
    for key,(title,desc,*_) in UPGRADES.items():
        add('UPGRADE:Israel'+key,title);add('CONTROLBAR:Israel_Upgrade'+key,title)
        add('CONTROLBAR:Israel_Upgrade'+key+'Description',desc)
    for key,(title,desc,*_) in POWERS.items():
        add('CONTROLBAR:Israel_Power'+key,title);add('CONTROLBAR:Israel'+key+'Description',desc)
    for ability in ('Precision',):
        for rank in range(1,4):add(f'SCIENCE:Israel{ability}{rank}',POWERS[ability][0]+' '+str(rank))
    return '\n'.join(strings)

def build_portraits():
    from PIL import Image,ImageOps,ImageDraw
    tex=DATA/'Art/Textures';tex.mkdir(parents=True,exist_ok=True)
    sources=ROOT/'scripts/models/israel/portraits'
    # Require the complete illustrated set: silently falling back to studio
    # renders gives infantry and machinery incompatible styles in one menu.
    missing=[key for key in ASSETS if not (sources/(key.lower()+'.png')).is_file()]
    if missing:
        raise FileNotFoundError('Missing illustrated Israel portraits: '+', '.join(missing))
    review=[]
    for key,a in ASSETS.items():
        portrait=sources/(key.lower()+'.png')
        image=ImageOps.fit(Image.open(portrait).convert('RGB'),(128,128),method=Image.Resampling.LANCZOS)
        d=ImageDraw.Draw(image);d.rectangle((0,0,127,127),outline=(46,57,66),width=1)
        image.save(tex/('ili_'+key.lower()+'.tga'))
        review.append((a['display_name'],image.copy()))
    sheet=Image.new('RGB',(5*160,5*190),(18,25,32));draw=ImageDraw.Draw(sheet)
    for i,(label,icon) in enumerate(review):
        x=(i%5)*160;y=(i//5)*190;sheet.paste(icon,(x+16,y+8));draw.text((x+8,y+148),label,fill=(220,227,231))
    sheet.save(ROOT/'build/faction-assets/israel/icons-review.png')
    for name in ('Logo','SideIcon','LoadScreen','MedallionRegular','MedallionHilite','MedallionSelect'):
        size=512 if name=='LoadScreen' else 128
        image=Image.new('RGB',(size,size),(20,28,37));d=ImageDraw.Draw(image)
        edge=(184,139,78) if 'Select' in name else (104,155,170) if 'Hilite' in name else (156,160,136)
        d.rounded_rectangle((size*.05,size*.05,size*.95,size*.95),radius=size*.08,fill=(37,48,59),outline=edge,width=max(2,size//40))
        # Original shield badge: blue and white bands with a six-point star.
        for cy in (.26,.68):
            d.rectangle((size*.19,size*(cy-.035),size*.81,size*(cy+.035)),fill=(91,139,193))
        for phase in (-math.pi/2,math.pi/2):
            points=[(size*.5+math.cos(phase+i*math.tau/3)*size*.235,
                     size*.47+math.sin(phase+i*math.tau/3)*size*.235) for i in range(3)]
            d.line(points+[points[0]],fill=(218,225,225),width=max(3,size//36),joint='curve')
        image.save(tex/('ili_'+name.lower()+'.tga'))

def atomic_write(path,text):
    path.parent.mkdir(parents=True,exist_ok=True)
    tmp=path.with_suffix(path.suffix+'.tmp');tmp.write_text(text+'\n');os.replace(tmp,path)

def validate(logic,client):
    objects=re.findall(r'^ChildObject (Israel_\w+) (\w+)',logic,re.M)
    units=[k for k,a in ASSETS.items() if a['category']!='building']
    assert len(CORE)==11 and len(objects)==28
    assert len([x for x in MENUS['Factory'].values() if x in ASSETS])==5
    assert len(set(k for k,p in objects))==28
    assert not re.search(r'^\s*Behavior = HordeUpdate',logic,re.M)
    assert all(ident(k) in logic for k in ASSETS)
    local_objects={n for n,p in objects}
    for source,target in ALIASES.items():
        stock.record('Object',source)
        assert ident(target) in local_objects,(source,target)
    for n in re.findall(r'^\s*Object = (Israel_\w+)$',client,re.M):assert n in local_objects,n
    # Confirm all inherited tags and public draw/launch bones exist before load.
    for key,a in ASSETS.items():
        record=logic.split(f'ChildObject {ident(key)} ',1)[1].split('\nEnd\n',1)[0]
        valid_tags={tag for _,_,tag in module_headers(PARENTS[key])}
        changed=re.findall(r'^\s*(?:RemoveModule|ReplaceModule) (\w+)',record,re.M)
        assert len(changed)==len(set(changed)),(key,'module modified twice')
        for tag in changed:assert tag in valid_tags,(key,tag)
        for variant in a['variants']:
            assert (DATA/'Art/W3D'/f'{variant}.w3d').exists(),variant
        assert (DATA/'Art/Textures'/('ili_'+key.lower()+'.tga')).exists()
    for _,parent,_ in WEAPONS:stock.record('Weapon',parent)
    stock.record('FXList','FX_MOABFinalExplosion')
    # Production and role contracts prevent retired USA-template abilities from
    # leaking back through a menu, an AI alias, or an inherited weapon set.
    reachable={v for slots in MENUS.values() for v in slots.values() if v in ASSETS}
    assert (reachable & set(units))==CORE
    assert not (set(ALIASES.values()) & RETIRED)
    assert set(WEAPON_SETS['Commando'])=={'CommandoRifle',None}
    assert 'Training' not in UPGRADES and 'Barrage' not in POWERS and 'Repair' not in POWERS
    assert 'Command_ColonelBurton' not in client
    assert all('Buildable = No' in object_record(k) or '  Buildable = No' in object_record(k) for k in RETIRED)
    weapons={k:c for k,p,c in WEAPONS}
    assert weapons['F16IMissile']['AntiGround']=='Yes' and weapons['F16IMissile']['AntiAirborneVehicle']=='No'
    assert weapons['SpikeMissile']['AntiAirborneVehicle']=='No'
    assert weapons['PerehMissile']['RequiresTargetVision']=='Yes'
    assert weapons['PerehMissile']['PrimaryDamageRadius'] > 0, 'Zero-radius Pereh missiles fail to damage their target'
    assert 'OCL_NukeRadiationField' not in logic
    assert 'OnlyVisibleToOwningPlayer = No' in logic
    assert '  DamageType = EXPLOSION' in logic
    # Every stock command referenced is present; new commands are all defined.
    defined=set(re.findall(r'^(?:ChildCommandButton|CommandButton) (\w+)',client,re.M))
    for command in re.findall(r'^\s*\d+ = (\w+)',client,re.M):
        if command not in defined:stock.record('CommandButton',command)
    return {'faction':'FactionIsrael','units':len(CORE),'archived_units':sorted(RETIRED),'buildings':len(ASSETS)-len(units),'weapons':len(WEAPONS)+1,'effect_helpers':3,
        'factory_buttons':5,'ai_replacements':len(ALIASES),'validation':'passed',
        'native_validation':'parent integration runner required','balance':'initial playtest baseline'}

def main():
    OUT.mkdir(parents=True,exist_ok=True)
    # Preserve all existing illustrated assets during the roster redesign.
    # Use build_portraits() explicitly when portrait source art changes.
    logic=build_logic();client=build_client();strings=build_strings()
    report=validate(logic,client)
    atomic_write(DATA/'Data/INI/Addon/Logic/Israel.ini',logic)
    atomic_write(DATA/'Data/INI/Addon/Client/Israel.ini',client)
    atomic_write(DATA/'Data/english/Addon/Israel.str',strings)
    production=['Israel_Power']*4+['Israel_SupplyCentre Israel_SupplyTruck','Israel_TechCentre',
        'Israel_CommandCentre Israel_D9','Israel_Barracks '+','.join('Israel_'+x for x in ('Rifleman','Spike','Commando')),
        'Israel_Factory '+','.join('Israel_'+x for x in ('SandCat','Merkava','Namer','SPYDER','Pereh')),
        'Israel_Airfield '+','.join('Israel_'+x for x in ('F16I',)),
        'Israel_Income','Israel_GroundDefence','Israel_AirDefence','Israel_Superweapon']
    atomic_write(OUT/'production.txt','\n'.join(production))
    atomic_write(OUT/'validation.json',json.dumps(report,indent=2))
    print(json.dumps(report,indent=2))

if __name__=='__main__':main()

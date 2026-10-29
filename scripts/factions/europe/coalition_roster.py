"""Coalition asset catalogue, curated into an 11-unit playable faction at the end.

Country ownership describes the fictional coalition contingent, not necessarily the
design's origin. Retired prototypes remain available to asset tools and old maps.
Balance values are an initial playtest baseline, not a claim of competitive parity.
"""
from copy import deepcopy
from stock_data import record, replaced_module, copied_record


def weapon_set(primary=None, secondary=None, condition='None'):
    return ['WeaponSet', f'  Conditions = {condition}'] + [
        f'  Weapon = {slot} {weapon}' for slot, weapon in [('PRIMARY', primary), ('SECONDARY', secondary)] if weapon
    ] + ['End']


def draw(model, wheels=0, turret=None, animation=False, tracked=False):
    lines = ['RemoveModule ModuleTag_01', 'AddModule',
             f'  Draw = {"W3DTruckDraw" if wheels else "W3DTankDraw" if tracked else "W3DModelDraw"} ModuleTag_Euro_01',
             '    OkToChangeModelColor = Yes']
    for state, suffix in [('NONE', ''), ('REALLYDAMAGED', '_D'), ('RUBBLE', '_D')]:
        lines += [f'    ConditionState = {state}', f'      Model = {model}{suffix}']
        if animation:
            lines += [f'      Animation = {model}{suffix}.{model}{suffix}', '      AnimationMode = LOOP']
        if turret:
            lines += [f'      Turret = {turret}']
        lines += ['      WeaponFireFXBone = PRIMARY Muzzle', '      WeaponLaunchBone = PRIMARY Muzzle',
                  '      WeaponMuzzleFlash = PRIMARY MuzzleFX', '    End']
    if wheels:
        labels = ['LeftFront', 'RightFront', 'LeftRear', 'RightRear'] if wheels == 4 else [
            'LeftFront', 'RightFront', 'MidLeftFront', 'MidRightFront', 'LeftRear', 'RightRear'] if wheels == 6 else [
            'LeftFront', 'RightFront', 'MidLeftFront', 'MidRightFront', 'MidLeftRear', 'MidRightRear', 'LeftRear', 'RightRear']
        lines += [f'    {label}TireBone = TIRE{i + 1:02}' for i, label in enumerate(labels)]
        lines += ['    TireRotationMultiplier = 0.2', '    TrackMarks = EXTireTrack.tga', '    Dust = RocketBuggyDust']
    if tracked:lines += ['    TrackMarks = EXTnkTrack.tga','    TreadAnimationRate = 2.0']
    return lines + ['  End', 'End']


def infantry_draw(parent, model, upgraded=None):
    import re
    body = '\n'.join(replaced_module(parent, 'ModuleTag_01'))
    # Keep every stock movement, attack, garrison, death and parachute animation.
    body = re.sub(r'(\bModel\s*=\s*)\w+', lambda m: m[1] + model if m[0].split('=')[1].strip().upper() != 'NONE' else m[0], body)
    lines=body.splitlines()
    if upgraded:
        # Duplicate each animation state with USER_1 set, so researching equipment
        # changes the mesh during movement and combat as well as while standing.
        states=[];i=0
        while i<len(lines):
            line=lines[i]
            if line.startswith('    DefaultConditionState') or line.startswith('    ConditionState'):
                block=[line.replace('DefaultConditionState','ConditionState = USER_1') if 'DefaultConditionState' in line
                       else line.replace('ConditionState', 'ConditionState',1).replace('=', '= USER_1',1)]
                i+=1
                while i<len(lines):
                    block.append(lines[i].replace(model,upgraded))
                    if lines[i]=='    End':break
                    i+=1
                block.insert(1,'      Model = '+upgraded)
                # Every override gets exactly one Model entry.
                seen=False;dedup=[]
                for l in block:
                    if l.strip().startswith('Model '):
                        if seen:continue
                        seen=True
                    dedup.append(l)
                states+=dedup
            elif line.startswith('    AliasConditionState'):
                states.append(line.replace('=', '= USER_1',1))
            i+=1
        lines[-2:-2]=states
    return lines


def apply(g):
    units, buildings = g['UNITS'], g['BUILDINGS']
    def find(name):
        return next(o for o in units + buildings if o[0] == name)
    def edit(name, title, desc, **changes):
        table = units if find(name) in units else buildings
        i = next(i for i, o in enumerate(table) if o[0] == name)
        old = table[i]
        data = deepcopy(old[4]); data.update(changes)
        table[i] = (name, old[1], title, desc, data)
        return data
    def add(name, parent, title, desc, **c):
        units.append((name, parent, title, desc, dict(ai=False, **c)))
    def module(name, lines):
        g['MODULES'].setdefault(name, []).extend(lines)
    def weapon(name, parent, **c):
        g['WEAPONS'][:] = [w for w in g['WEAPONS'] if w[0] != name]
        g['WEAPONS'].append((name, parent, c))
    def upgrade_module(kind, tag, upgrade, extra=()):
        return [f'Behavior = {kind} {tag}', f'  TriggeredBy = {upgrade}', *extra, 'End']

    g['FACTION'].update(strategy='A European coalition of 31 countries. Combine resilient German tanks, French infantry, '
        'British aircraft and Czech artillery with specialised allied reinforcements. Mobile combined arms, supported by subsidies.',
        features='31 national contingents, tanks and wheeled artillery, specialised infantry, coalition air support')
    edit('Euro_Dozer', 'Armoured Engineer', 'Germany: armoured engineers construct and repair the coalition base and clear mines.')
    edit('Euro_Rifleman', 'Legionnaire', 'France: Foreign Legion line infantry. FN MINIMI support weapons improve rifle damage by 25%.',
         extra=infantry_draw('AmericaInfantryRanger', 'EULEGION', 'EUMINIM'))
    edit('Euro_Milan', 'MILAN Team', 'France: portable anti-tank team. Use laser designation to concentrate fire on armour.',
         extra=infantry_draw('AmericaInfantryMissileDefender', 'EUMILAN'))
    edit('Euro_Marksman', 'Sako Marksman', 'Finland: concealed Sako TRG sniper. GM6 Lynx research adds a slow anti-materiel shot against vehicles.',
         extra=infantry_draw('AmericaInfantryPathfinder', 'EUSAKO', 'EULYNX'))
    edit('Euro_Commando', 'GROM Commando', 'Poland: one elite GROM operator. Infiltrates, demolishes structures and fights infantry.',
         extra=infantry_draw('AmericaInfantryColonelBurton', 'EUGROM'))
    for name in ['Euro_Rifleman']:
        module(name, upgrade_module('WeaponBonusUpgrade', 'ModuleTag_Euro_Minimi', 'Upgrade_EuroMinimi'))
        module(name, upgrade_module('ModelConditionUpgrade', 'ModuleTag_Euro_MinimiVisual', 'Upgrade_EuroMinimi',
                                   ['  ConditionFlag = USER_1']))
    weapon('Euro_RiflemanRifle', 'RangerAdvancedCombatRifle', AttackRange=110, PrimaryDamage=6,
           WeaponBonus='PLAYER_UPGRADE DAMAGE 125%')
    weapon('Euro_GM6', 'USAPathfinderSniperRifle', PrimaryDamage=24, DamageType='ARMOR_PIERCING', AttackRange=240,
           DelayBetweenShots=3000, AntiGround='Yes', AntiAirborneVehicle='No')
    module('Euro_Marksman', weapon_set('Euro_MarksmanRifle', 'Euro_GM6', 'PLAYER_UPGRADE') +
           upgrade_module('WeaponSetUpgrade', 'ModuleTag_Euro_GM6', 'Upgrade_EuroLynx'))
    module('Euro_Marksman', upgrade_module('ModelConditionUpgrade','ModuleTag_Euro_GM6Visual','Upgrade_EuroLynx',
                                          ['  ConditionFlag = USER_1']))

    d = edit('Euro_Boxer', 'Vilkas IFV', 'Lithuania: Boxer-based Vilkas infantry carrier. Autocannon, five passengers and optional anti-tank missiles.',
             cost=850, health=('ModuleTag_02', 300, True))
    start = d['extra'].index('Behavior = PointDefenseLaserUpdate ModuleTag_Euro_PointDefense')
    end = d['extra'].index('End', start)
    del d['extra'][start:end + 1]
    edit('Euro_Leopard', 'Leopard 2', 'Germany: durable main battle tank. Holds the line while lighter coalition units work the flanks.')
    weapon('Euro_LeopardGun', 'CrusaderTankGun', AttackRange=155, PrimaryDamage=62, DelayBetweenShots=2100)
    d = edit('Euro_Leclerc', 'Leclerc', 'France: autoloading assault tank. Fires three fast shots, then pauses to reload. Less armour than Leopard 2.',
             cost=1300, health=('ModuleTag_02', 430, True))
    d['extra'] += ['RemoveModule ModuleTag_07']
    weapon('Euro_LeclercGun', 'PaladinTankGun', AttackRange=165, PrimaryDamage=55, DelayBetweenShots=450, ClipSize=3, ClipReloadTime=4200)
    edit('Euro_Puls', 'PULS Launcher', 'Netherlands: Israeli-designed PULS rocket artillery, on a stylised coalition carrier. Long reach; needs a spotter.')
    edit('Euro_ReconDrone', 'THeMIS Drone', 'Estonia: unmanned tracked scout. Reveals concealed enemies and spots for the artillery.')
    edit('Euro_Ambulance', 'Valuk Ambulance', 'Slovenia: Valuk 6x6 ambulance, derived from the Austrian Pandur. Heals nearby infantry and vehicles; removes toxins.',
         extra=draw('EUVALUK', 6))
    edit('Euro_NH90', 'NH90 Transport', 'Italy: coalition utility helicopter. Collects supplies and transports troops.',
         extra=[line.replace('PassengersAllowedToFire = Yes', 'PassengersAllowedToFire = No') for line in find('Euro_NH90')[4]['extra']])
    edit('Euro_Typhoon', 'Typhoon', 'United Kingdom: coalition multirole interceptor. Strong air-to-air missiles; limited ammunition.')
    d = edit('Euro_Rafale', 'Rafale', 'France: precision attack aircraft. Excels at striking defences, with optional bunker-busting missiles.',
             cost=1650, health=('ModuleTag_02', 160, False))
    d['extra'] += ['RemoveModule ModuleTag_09']
    # A conventional bomber, without Aurora's supersonic invulnerability.
    d = edit('Euro_Tornado', 'Tornado', 'United Kingdom: conventional heavy strike aircraft. One powerful bomb per sortie; vulnerable to air defence.',
             cost=2200, time=25, health=('ModuleTag_02', 180, False), ai_parent='AmericaJetAurora',
             weapons={'RaptorJetMissileWeapon': 'Euro_TornadoBomb'})
    i = next(i for i,o in enumerate(units) if o[0] == 'Euro_Tornado')
    units[i] = (units[i][0], 'AmericaJetRaptor', *units[i][2:])
    weapon('Euro_TornadoBomb', 'AuroraBombWeapon', PrimaryDamage=300, PrimaryDamageRadius=30, ClipSize=1, AttackRange=100,
           AntiAirborneVehicle='No', AntiAirborneInfantry='No')
    edit('Euro_Tiger', 'Tiger HAD', 'Spain: agile attack helicopter for infantry and light vehicles. Cheaper and more fragile than Apache.',
         cost=1200, health=('ModuleTag_04', 170, False))
    weapon('Euro_TigerMissile', 'ComancheAntiTankMissileWeapon', AttackRange=200, PrimaryDamage=30)

    # Wiesel is an early, fragile TOW carrier; no disabling beam or garrison-clearing magic.
    i = next(i for i,o in enumerate(units) if o[0] == 'Euro_Wiesel')
    units[i] = ('Euro_Wiesel', 'AmericaTankCrusader', 'Wiesel TOW',
        'Germany: small tracked anti-tank carrier. Long-range TOW missile, light armour and a slow reload.',
        dict(ai_parent='AmericaTankMicrowave', cost=650, time=9, pre=[['Euro_WarFactory']], command='Euro_VehicleCommandSet',
             health=('ModuleTag_02', 200, True), weapons={'CrusaderTankGun':'Euro_WieselTOW'},
             extra=g['tank_draw']('EUWIEST', 'Turret') + replaced_module('AmericaTankCrusader','ModuleTag_03') +
                   ['Locomotor = SET_NORMAL HumveeLocomotor']))
    weapon('Euro_WieselTOW', 'HumveeMissileWeapon', PrimaryDamage=120, AttackRange=230, DelayBetweenShots=4000,
           ClipSize=0, AntiAirborneVehicle='No', AntiAirborneInfantry='No')
    d = edit('Euro_Skyranger', 'Skyranger 30', 'Switzerland / Germany: Oerlikon air-defence cannon on an armoured carrier. AHEAD ammunition improves damage by 25%.',
             cost=1500, health=('ModuleTag_02', 300, True), weapons={'AvengerTargetDesignator':'Euro_SkyrangerDummy'})
    d['extra'] += ['RemoveModule ModuleTag_Laser_One', 'RemoveModule ModuleTag_Laser_Two']
    weapon('Euro_SkyrangerDummy', 'AvengerAirLaserDummy', AttackRange=300)
    weapon('Euro_OerlikonAir', 'GattlingTankGunAir', AttackRange=300, PrimaryDamage=12, DelayBetweenShots=250,
           ContinuousFireOne=999999, ContinuousFireTwo=999999)
    weapon('Euro_OerlikonGround', 'GattlingTankGun', AttackRange=170, PrimaryDamage=4, DelayBetweenShots=300,
           ContinuousFireOne=999999, ContinuousFireTwo=999999)
    d = edit('Euro_SkyrangerTurret', 'Oerlikon Cannon', '', ai=False,
             weapons={'AvengerAirLaserOne':'Euro_OerlikonAir', 'AvengerAirLaserTwo':'Euro_OerlikonGround'})
    d['extra'] = [line for line in d['extra']]
    for idx in reversed([i for i,l in enumerate(d['extra']) if l.strip().startswith('TurretPitch =')]):
        d['extra'][idx+1:idx+1] = ['      WeaponFireFXBone = PRIMARY TurretFX01', '      WeaponFireFXBone = SECONDARY TurretFX01']
    module('Euro_SkyrangerTurret', upgrade_module('WeaponBonusUpgrade', 'ModuleTag_Euro_AHEAD', 'Upgrade_EuroAhead'))
    edit('Euro_PatriotBattery', 'NASAMS Battery', 'Norway: Kongsberg NASAMS with AMRAAM missiles. Powered, networked ground and air defence.')

    add('Euro_Dana', 'AmericaTankCrusader', 'DANA Howitzer',
        'Czechia: wheeled 152 mm artillery. Affordable area fire against infantry and bases; vulnerable at close range.',
        cost=1200, time=18, pre=[['Euro_WarFactory'], ['Euro_StrategyCenter']], health=('ModuleTag_02', 220, True),
        command='Euro_VehicleCommandSet', weapons={'CrusaderTankGun':'Euro_DanaGun'},
        extra=draw('EUDANA', 8, 'Turret') + replaced_module('AmericaTankCrusader','ModuleTag_03') +
              ['Locomotor = SET_NORMAL TomahawkLocomotor'])
    weapon('Euro_DanaGun', 'FireBaseHowitzerGun', PrimaryDamage=80, PrimaryDamageRadius=20, SecondaryDamage=15,
           SecondaryDamageRadius=30, AttackRange=300, MinimumAttackRange=60, DelayBetweenShots=3000)
    apache = deepcopy(find('Euro_Tiger')[4])
    apache.update(cost=1600, time=22, health=('ModuleTag_04',240,False), weapons={
        'Comanche20mmCannonWeapon':'Euro_ApacheCannon', 'ComancheAntiTankMissileWeapon':'Euro_Hellfire'})
    apache['extra'] = [l.replace('EUTIGR','EUAPACHE') for l in apache['extra']]
    add('Euro_Apache', 'AmericaVehicleComanche', 'Apache AH1',
        'United Kingdom: licence-built Apache attack helicopter. Heavy anti-tank missiles; expensive and vulnerable to dedicated AA.', **apache)
    weapon('Euro_ApacheCannon','Comanche20mmCannonWeapon', PrimaryDamage=4, AttackRange=190)
    weapon('Euro_Hellfire','ComancheAntiTankMissileWeapon', PrimaryDamage=80, AttackRange=200, ClipSize=4, ClipReloadTime=9000,
           DelayBetweenShots=1000)
    add('Euro_Mistral','AmericaInfantryMissileDefender','Mistral Team',
        'Cyprus: air-defence infantry with the French Mistral missile. Attacks aircraft only; needs protection against ground forces.',
        cost=400, time=6, pre=[['Euro_Barracks']], command='Euro_InfantryCommandSet', health=('ModuleTag_02',100,False),
        extra=infantry_draw('AmericaInfantryMissileDefender','EUMISTR') + weapon_set('Euro_MistralMissile') +
              ['RemoveModule ModuleTag_08','RemoveModule ModuleTag_09','RemoveModule ModuleTag_CBHunt'])
    weapon('Euro_MistralMissile','MissileDefenderMissileWeapon', PrimaryDamage=60, AttackRange=230,
           AntiGround='No', AntiAirborneVehicle='Yes', AntiAirborneInfantry='Yes', DelayBetweenShots=2000)

    # Ground contingents arrive through powers, keeping regular production focused.
    for name, title, desc, model in [
        ('Euro_Reserve','AUG Reservist','Austria: coalition reservist equipped with the Steyr AUG.','EUAUG'),
        ('Euro_Paratrooper','Paraquedista','Portugal: airborne rifle infantry delivered by a Luxembourg-crewed A400M.','EUPARA'),
        ('Euro_Ranger','Army Ranger Wing','Ireland: concealed reconnaissance infantry; reveals stealth at short range.','EUIRISH'),
        ('Euro_EOD','EOD Specialist','Malta: explosive-ordnance specialist supporting Croatian mine-clearing robots.','EUEOD'),
        ('Euro_Rescuer','SAR Medic','Iceland: Coast Guard rescue specialist. Heals nearby infantry; unarmed.','EUSAR')]:
        add(name,'AmericaInfantryRanger',title,desc,cost=200,time=5,pre=[['Euro_Barracks']],
            command='Euro_InfantryCommandSet', extra=infantry_draw('AmericaInfantryRanger',model),
            weapons={'RangerAdvancedCombatRifle':'Euro_RiflemanRifle'})
    add('Euro_ATGL','AmericaInfantryMissileDefender','ATGL Reservist','Bulgaria: Arsenal ATGL reserve infantry. Short-range, inexpensive anti-tank support.',
        cost=250,time=5,pre=[['Euro_Barracks']],command='Euro_InfantryCommandSet',
        extra=infantry_draw('AmericaInfantryMissileDefender','EUATGL') + weapon_set('Euro_ATGLRocket') +
              ['RemoveModule ModuleTag_08','RemoveModule ModuleTag_09','RemoveModule ModuleTag_CBHunt'])
    weapon('Euro_ATGLRocket','MissileDefenderMissileWeapon', PrimaryDamage=38, AttackRange=150, AntiAirborneVehicle='No')
    module('Euro_Ranger', ['Behavior = StealthUpdate ModuleTag_Euro_RangerStealth','  StealthDelay = 2000',
           '  StealthForbiddenConditions = FIRING_PRIMARY MOVING','End',
           'Behavior = StealthDetectorUpdate ModuleTag_Euro_RangerRecon','  DetectionRange = 120','  DetectionRate = 750','End'])
    for name in ['Euro_EOD','Euro_Rescuer']:
        d=find(name)[4]
        d['fields']={'KindOf':'PRELOAD SELECTABLE CAN_CAST_REFLECTIONS INFANTRY SCORE CAN_RAPPEL PARACHUTABLE'}
        d['extra'] += weapon_set() + weapon_set(condition='PLAYER_UPGRADE')
    module('Euro_Rescuer', ['Behavior = AutoHealBehavior ModuleTag_Euro_Rescue','  HealingAmount = 4','  HealingDelay = 1000',
           '  Radius = 70','  StartsActive = Yes','  KindOf = INFANTRY','  SkipSelfForHealing = Yes','End'])
    module('Euro_EOD', ['Behavior = StealthDetectorUpdate ModuleTag_Euro_EOD','  DetectionRange = 120','  DetectionRate = 500',
           '  ExtraRequiredKindOf = MINE','End'])
    add('Euro_MV4','AmericaVehicleDozer','MV-4 Robot','Croatia: DOK-ING unmanned mine-clearing robot. Clears mines and repairs allied vehicles and buildings.',
        cost=500,time=8,command='Euro_EngineeringCommandSet', health=('ModuleTag_02',220,True),
        extra=draw('EUMV4',animation=True,tracked=True))
    # Preserve the Humvee's transport AI, replacing its complete draw and weapons.
    add('Euro_Patria','AmericaVehicleHumvee','Patria 6x6','Latvia: locally manufactured Finnish Patria 6x6. Transports five infantry, with a defensive machine gun.',
        cost=700,time=10,command='Euro_BoxerCommandSet',health=('ModuleTag_02',320,True),
        fields={'KindOf':'PRELOAD SELECTABLE CAN_ATTACK VEHICLE SCORE TRANSPORT PARACHUTABLE'},
        extra=draw('EUPATRIA',6,'Turret')+weapon_set('Euro_BoxerGun')+weapon_set('Euro_BoxerGun',condition='PLAYER_UPGRADE'))
    add('Euro_A400M','AmericaJetCargoPlane','A400M Atlas','Luxembourg / Belgium: coalition transport for paratroopers and supplies.',
        extra=draw('EUA400M',animation=True)+['RemoveModule ModuleTag_02'])
    add('Euro_Puma','AmericaJetCargoPlane','IAR 330 Puma','Romania: licence-built Puma transport carrying Icelandic rescue specialists.',
        extra=draw('EUPUMA',animation=True)+['RemoveModule ModuleTag_02'] +
              replaced_module('AmericaJetCargoPlane','ModuleTag_09') + ['Locomotor = SET_NORMAL Euro_PumaDeliveryLocomotor'])
    g['SPECIAL_POWERS'] += copied_record('Locomotor','B52Locomotor','Euro_PumaDeliveryLocomotor', [('Speed = 100','Speed = 70')])
    add('Euro_Gripen','AmericaJetA10Thunderbolt','Gripen Strike','Sweden: a flight of Gripen aircraft attacks the marked area.',
        extra=g['jet_draw']('EUGRIPEN', ('BurnerFX01',)))

    # Upgrades have one defined purpose each; THEON reuses Search and Destroy.
    g['UPGRADES'] += [
        ('Upgrade_EuroMinimi','FN MINIMI','Belgium: support weapons increase Legionnaire rifle damage by 25%.',700,35,'Euro_UpgradeMinimi'),
        ('Upgrade_EuroLynx','GM6 Lynx','Hungary: anti-materiel rifles give Sako Marksmen a slow secondary attack against vehicles.',1000,40,'Euro_UpgradeLynx'),
        ('Upgrade_EuroAhead','AHEAD Ammunition','Switzerland: Oerlikon programmable ammunition improves Skyranger cannon damage by 25%.',1000,40,'Euro_UpgradeAhead')]
    g['SKIRMISH_AI_UPGRADES'] += [('Upgrade_EuroMinimi','Euro_Rifleman',6),
                                ('Upgrade_EuroAhead','Euro_Skyranger',2),
                                ('Upgrade_EuroLynx','Euro_Marksman',2)]
    g['BUTTON_LABELS'].update({
        'Command_UpgradeAmericaCountermeasures':('Terma Countermeasures','Denmark: flare dispensers protect coalition aircraft against missiles.'),
        'Command_InitiateBattlePlanSearchAndDestroy':('THEON Search and Destroy','Greece: coalition night-vision and targeting equipment. Improves weapon range and command-centre surveillance.')})
    g['USA_BUTTONS']['Command_InitiateBattlePlanSearchAndDestroy']='Euro_UpgradeOptics'
    menus=g['COMMAND_SETS']
    menus['Euro_DozerCommandSet'].pop(10)
    menus['Euro_BarracksCommandSet'].update({5:'Euro_Mistral',9:'Euro_Command_UpgradeMinimi',10:'Euro_Command_UpgradeLynx'})
    menus['Euro_WarFactoryCommandSet'].update({10:'Euro_Dana',12:'Euro_Command_UpgradeAhead'})
    menus['Euro_AirfieldCommandSet'].update({3:'Euro_Rafale',4:'Euro_Tornado',5:'Euro_Apache'})
    menus['Euro_InfantryCommandSet']={11:'Command_AttackMove',13:'Command_Guard',14:'Command_Stop'}
    menus['Euro_EngineeringCommandSet']={1:'Command_DisarmMinesAtPosition',13:'Command_Guard',14:'Command_Stop'}
    # Clone the strategy menu to preserve all three working battle plans and upgrades.
    import re
    menus['Euro_StrategyCommandSet']={int(m[1]):m[2] for l in record('CommandSet','AmericaStrategyCenterCommandSet')
                                      if (m:=re.match(r'\s*(\d+)\s*=\s*(\w+)',l))}
    find('Euro_StrategyCenter')[4]['command']='Euro_StrategyCommandSet'
    g['HOTKEYS'].update(Euro_Mistral='T',Euro_Dana='H',Euro_Apache='A',Euro_ReconDrone='D',Euro_Boxer='V',Euro_Ambulance='A')

    # Use the original drop/strafe behaviours with EU aircraft and national payloads.
    ocl=g['OBJECT_CREATION_LISTS']; ocl.clear()
    def drop(name, transport, payloads):
        result=[f'ObjectCreationList {name}']
        for vehicle in (True,False):
            group=[(obj,count) for obj,count,is_vehicle in payloads if is_vehicle==vehicle]
            if not group:continue
            result += ['  DeliverPayload',f'    Transport = {transport}',
                       f'    PutInContainer = {"AmericaCrateParachute" if vehicle else "AmericaParachute"}'] + [
                       f'    Payload = {obj} {count}' for obj,count in group] + ['  '+l for l in g['DROP']] + ['  End']
        return result+['End','']
    ocl += drop('Euro_OCL_Coalition','Euro_A400M', [('Euro_Patria',2,True),('Euro_Reserve',4,False),('Euro_ATGL',4,False),('Euro_Ranger',2,False)])
    ocl += drop('Euro_OCL_Engineering','Euro_A400M',[('Euro_MV4',1,True),('Euro_EOD',2,False)])
    for i in range(1,4):
        ocl += copied_record('ObjectCreationList',f'SUPERWEAPON_Paradrop{i}',f'Euro_OCL_Paradrop{i}',
                             [('AmericaJetCargoPlane','Euro_A400M'),('AmericaInfantryRanger','Euro_Paratrooper')])
        ocl += copied_record('ObjectCreationList',f'SUPERWEAPON_A10ThunderboltMissileStrike{i}',f'Euro_OCL_Gripen{i}',
                             [('AmericaJetA10Thunderbolt','Euro_Gripen')])
        # Repair remains immediate; a separately interceptable SAR flight brings medics.
        repair=copied_record('ObjectCreationList',f'SUPERWEAPON_RepairVehicles{i}',f'Euro_OCL_Repair{i}')
        medical=drop('unused','Euro_Puma',[('Euro_Rescuer',i,False)])
        ocl += repair[:-2]+medical[1:]
    for tag,replacements in [('ModuleTag_22',[('SUPERWEAPON_Paradrop','Euro_OCL_Paradrop')]),
                             ('ModuleTag_26',[('SUPERWEAPON_A10ThunderboltMissileStrike','Euro_OCL_Gripen')]),
                             ('ModuleTag_27',[('SUPERWEAPON_RepairVehicles','Euro_OCL_Repair')])]:
        g['MODULES_COMMAND_CENTRE'] += replaced_module('AmericaCommandCenter',tag,replacements)
    desc='Croatia and Malta: an A400M drops one MV-4 mine-clearing robot and two EOD specialists.'
    g['NEW_POWERS']['Engineering']=dict(text='Engineering Team',description=desc,button='Command_Paradrop',shortcut='Command_ParadropFromShortcut',
        fields=['SpecialPower = Euro_SuperweaponEngineering','Science = SCIENCE_EuroEngineering'])
    g['SCIENCES']['EuroEngineering']=('SCIENCE_AMERICA SCIENCE_Rank1','Command_PurchaseScienceParadrop1','Engineering Team',desc)
    g['SPECIAL_POWERS'] += ['SpecialPower Euro_SuperweaponEngineering','  Enum = SPECIAL_PARADROP_AMERICA','  ReloadTime = 240000',
        '  RequiredScience = SCIENCE_EuroEngineering','  PublicTimer = No','  SharedSyncedTimer = Yes','  RadiusCursorRadius = 40',
        '  ShortcutPower = Yes','  AcademyClassify = ACT_SUPERPOWER','End','']
    g['MODULES_COMMAND_CENTRE'] += ['Behavior = OCLSpecialPower ModuleTag_Euro_Engineering',
        '  SpecialPowerTemplate = Euro_SuperweaponEngineering','  OCL = Euro_OCL_Engineering',
        '  CreateLocation = CREATE_AT_EDGE_NEAR_SOURCE','  OCLAdjustPositionToPassable = Yes','End']
    g['POWERS'].update(Engineering=('Engineering Team',desc),
        ArtilleryBarrage=('Zuzana Barrage','Slovakia: off-map Zuzana 2 batteries shell the marked area.'),
        Coalition=('Coalition Reinforcements','Latvian Patria carriers, Austrian AUG reserves, Bulgarian ATGL teams and Irish scouts arrive by A400M.'),
        Paradrop=('Portuguese Airborne','Portugal / Luxembourg: Paraquedistas parachute from A400M transports.'),
        EmergencyRepair=('Repair and Rescue','Repairs allied vehicles and sends a Romanian IAR 330 with Icelandic infantry medics.'),
        A10ThunderboltMissileStrike=('Gripen Strike','Sweden: Gripen strike aircraft attack the marked area.'))
    for key in list(g['SCIENCES']):
        if key.startswith('EuroArtillery'):
            pre,btn,_,_=g['SCIENCES'][key]
            g['SCIENCES'][key]=(pre,btn,'Zuzana Barrage '+key[-1],g['POWERS']['ArtilleryBarrage'][1])
    for key in list(g['PROMOTIONS']):
        for prefix in ['Paradrop','EmergencyRepair','A10ThunderboltMissileStrike']:
            if key.startswith(prefix):
                title,desc=g['POWERS'][prefix];g['PROMOTIONS'][key]=(title+' '+key[-1],desc)
    g['PROMOTIONS']['PaladinTank']=('Leclerc Autoloader','Unlocks the French Leclerc burst-fire tank.')
    g['PROMOTIONS']['Pathfinder']=('Sako Marksman','Unlocks Finnish Sako TRG snipers.')
    g['PROMOTION_MENUS']['Euro_SCIENCE_CommandSetRank1'].update({2:'StealthFighter',4:'EuroEngineering'})
    # Zero Hour exposes four rank-one and fifteen rank-three purchase slots.
    g['PROMOTION_MENUS']['Euro_SCIENCE_CommandSetRank3'][13]='Pathfinder'
    g['PROMOTION_MENUS']['Euro_SCIENCE_CommandSetRank3'].update({1:'A10ThunderboltMissileStrike1',2:'A10ThunderboltMissileStrike2',3:'A10ThunderboltMissileStrike3'})
    menus['Euro_CommandCenterCommandSet'].update({3:'Euro_Command_A10ThunderboltMissileStrike',5:'Euro_Command_Engineering'})
    g['SHORTCUTS'].update({9:'A10ThunderboltMissileStrike',10:'Engineering'})
    g['PROMOTION_PICTURES']['EuroEngineering']='Euro_PowerEngineering'
    # New artwork is emitted by coalition_icons.py; the stock coordinates are a safe fallback.
    for name,base in {'Euro_Dana':'Euro_Puls','Euro_Apache':'Euro_Tiger','Euro_Mistral':'Euro_Milan',
        'Euro_Patria':'Euro_Boxer','Euro_MV4':'Euro_Dozer','Euro_Reserve':'Euro_Rifleman','Euro_Paratrooper':'Euro_Rifleman',
        'Euro_Ranger':'Euro_Marksman','Euro_ATGL':'Euro_Milan','Euro_EOD':'Euro_Rifleman','Euro_Rescuer':'Euro_Rifleman',
        'Euro_A400M':'Euro_NH90','Euro_Puma':'Euro_NH90','Euro_Gripen':'Euro_Typhoon',
        'Euro_UpgradeMinimi':'Euro_Rifleman','Euro_UpgradeLynx':'Euro_Marksman','Euro_UpgradeAhead':'Euro_Skyranger'}.items():
        g['USA_PICTURES'][name]=g['USA_PICTURES'][base]
    g['EURO_ART']['Euro_UpgradeOptics']=g['EURO_ART']['Euro_PowerSpyDrone']
    g['EURO_ART']['Euro_PowerEngineering']=g['EURO_ART']['Euro_PowerCoalition']

    # The compact vehicles keep their own silhouettes when destroyed. Inherited
    # USA death modules otherwise spawn complete Crusader/Humvee/Dozer models.
    for name,model,slow_tags,crush_tag in [
        ('Euro_Boxer','EUBOXER',['ModuleTag_11'],None),
        ('Euro_Wiesel','EUWIEST',['ModuleTag_10','ModuleTag_11'],'ModuleTag_15'),
        ('Euro_Patria','EUPATRIA',['ModuleTag_11'],None),
        ('Euro_Ambulance','EUVALUK',['ModuleTag_08'],'ModuleTag_14'),
        ('Euro_ReconDrone','EUDRONE',['ModuleTag_07'],None),
        ('Euro_MV4','EUMV4',['ModuleTag_07'],None),
    ]:
        obj=find(name);parent=obj[1];extra=obj[4].setdefault('extra',[])
        wreck=name+'_Wreck'
        ocl += [f'ObjectCreationList {wreck}','  CreateDebris',f'    ModelNames = {model}_D',
                '    Count = 1','    Mass = 120','    Disposition = SEND_IT_FLYING',
                '    DispositionIntensity = 0.08','    SpinRate = 15',
                '    BounceSound = VehicleDebris','  End','End','']
        for tag in slow_tags:
            death=[l for l in replaced_module(parent,tag) if not re.match(r'\s*OCL\s*=',l)]
            death[-2:-2]=[f'    OCL = FINAL {wreck}']
            extra+=death
        if crush_tag:
            extra+=replaced_module(parent,crush_tag,[('OCL_CrusaderTank_CrushEffect',wreck)])

    from curated_roster import apply as curate
    curate(g)

"""Eleven-unit European battlegroup: range, escorts and recovery.

Stable object IDs and all retired art are retained for old maps and asset tools.
Balance figures are a starting point for playtests, not tournament parity claims.
"""
import re
from stock_data import copied_record, replaced_module
from coalition_roster import weapon_set

CORE = {'Euro_Dozer','Euro_NH90','Euro_Rifleman','Euro_Milan','Euro_Marksman',
        'Euro_Leopard','Euro_Boxer','Euro_Skyranger','Euro_Dana','Euro_Ambulance','Euro_Typhoon'}
NEW_RETIRED = {'Euro_Wiesel','Euro_Commando','Euro_Rafale','Euro_Tiger'}


def apply(g):
    objects = {o[0]:o for o in g['UNITS']+g['BUILDINGS']}
    def data(name): return objects[name][4]
    def describe(name,title,description):
        for table in (g['UNITS'],g['BUILDINGS']):
            for i,o in enumerate(table):
                if o[0]==name: table[i]=(o[0],o[1],title,description,o[4])
    def weapon(name,**fields):
        next(w[2] for w in g['WEAPONS'] if w[0]==name).update(fields)
    def module(name,lines):g['MODULES'].setdefault(name,[]).extend(lines)
    def bonus(name,upgrade):
        module(name,[f'Behavior = WeaponBonusUpgrade ModuleTag_Euro_{upgrade}',
                     f'  TriggeredBy = Upgrade_Euro{upgrade}','End'])

    for name in NEW_RETIRED:
        data(name)['ai']=False
        data(name).setdefault('fields',{})['Buildable']='No'
    data('Euro_Outpost').update(ai=False)
    data('Euro_Outpost').setdefault('fields',{})['Buildable']='No'
    g['SKIRMISH_AI_ALIASES']=[('AmericaTankPaladin','Euro_Leopard'),
        ('AmericaVehicleSentryDrone','Euro_Boxer'),('AmericaTankMicrowave','Euro_Boxer'),
        ('AmericaInfantryColonelBurton','Euro_Marksman'),('AmericaJetAurora','Euro_Typhoon'),
        ('AmericaJetStealthFighter','Euro_Typhoon'),('AmericaVehicleComanche','Euro_Typhoon')]

    describe('Euro_Leopard','Leopard 2','Germany: accurate long-range tank with a measured firing rate. '
        'Needs Vilkas and Skyranger escorts when surrounded. Greek and Hungarian fire-control equipment.')
    data('Euro_Leopard').update(cost=1250,time=14)
    weapon('Euro_LeopardGun',AttackRange=175,PrimaryDamage=70,DelayBetweenShots=2300,
           ScatterRadiusVsInfantry=8,WeaponBonus='PLAYER_UPGRADE RANGE 110%')
    bonus('Euro_Leopard','FireControl')

    describe('Euro_Boxer','Vilkas IFV','Lithuania: five-seat autocannon carrier with Estonian sensors and Irish scouts. '
        'Reveals nearby hidden enemies; passengers dismount to fight. Weak against heavy armour.')
    d=data('Euro_Boxer')
    d['extra']=[l for l in d['extra'] if 'Weapon = TERTIARY Euro_BoxerMissile' not in l]
    d['extra']+=['RemoveModule ModuleTag_09']+replaced_module('AmericaVehicleHumvee','ModuleTag_05',
        [('PassengersAllowedToFire = Yes','PassengersAllowedToFire = No')])
    weapon('Euro_BoxerCannon',PrimaryDamage=9,DamageType='SMALL_ARMS',DelayBetweenShots=200,
           AntiAirborneVehicle='No',AntiAirborneInfantry='No')
    weapon('Euro_BoxerGun',PrimaryDamage=0)

    describe('Euro_Dana','DANA Howitzer','Czechia: precise shell artillery with Dutch fire-control crews. '
        'Accurate shots with narrow splash; automatically aims for 1.2 seconds before firing. Vulnerable inside minimum range.')
    weapon('Euro_DanaGun',AttackRange=340,PrimaryDamage=90,PrimaryDamageRadius=12,
           SecondaryDamage=15,SecondaryDamageRadius=22,MinimumAttackRange=75,
           PreAttackDelay=1200,PreAttackType='PER_ATTACK',DelayBetweenShots=3400,
           ScatterRadius=0,ScatterRadiusVsInfantry=5,WeaponBonus='PLAYER_UPGRADE RANGE 110%')
    bonus('Euro_Dana','FireControl')

    describe('Euro_Skyranger','Skyranger 30','Swiss Oerlikon air-defence gun with German and Cypriot crews. '
        'Close escort with rapid guns against aircraft and light infantry; ineffective against heavy armour. AHEAD adds 25% damage.')
    data('Euro_Skyranger').update(cost=1200,time=13)
    # The turret and its acquisition dummy must agree: it escorts the ground
    # army while Typhoons cover distant aircraft.
    weapon('Euro_SkyrangerDummy',AttackRange=240)
    weapon('Euro_OerlikonAir',AttackRange=240)
    for name in ('Euro_OerlikonAir','Euro_OerlikonGround'):
        weapon(name,WeaponBonus='PLAYER_UPGRADE DAMAGE 125%')

    describe('Euro_Milan','MILAN Team','France: ground anti-tank team with Bulgarian crews. '
        'Steady automatic missile fire at range. Cannot attack aircraft; needs protection from infantry.')
    d=data('Euro_Milan');d['command']='Euro_InfantryCommandSet'
    d['weapons']={'MissileDefenderMissileWeapon':'Euro_MilanMissile'}
    d['extra']+=weapon_set('Euro_MilanMissile') + [
        'RemoveModule ModuleTag_08','RemoveModule ModuleTag_09','RemoveModule ModuleTag_CBHunt']
    g['WEAPONS']=[w for w in g['WEAPONS'] if w[0]!='Euro_MilanGuidedMissile']
    weapon('Euro_MilanMissile',AttackRange=225,PrimaryDamage=44,DelayBetweenShots=1100,
           AntiAirborneVehicle='No',AntiAirborneInfantry='No',AntiGround='Yes')
    describe('Euro_Marksman','Sako Marksman','Finland: visible precision infantry escort with Polish reconnaissance crews. '
        'Quick aimed shots wear down exposed infantry. No concealment, stealth detection or anti-armour weapon.')
    g['MODULES']['Euro_Marksman']=[]
    d=data('Euro_Marksman');d.pop('science',None)
    d.update(cost=500,command='Euro_InfantryCommandSet',pre=[['Euro_Barracks'],['Euro_StrategyCenter']])
    d.setdefault('fields',{})['KindOf']='PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS INFANTRY SCORE'
    d['extra']+=['RemoveModule ModuleTag_08','RemoveModule ModuleTag_09'] + replaced_module(
        'AmericaInfantryPathfinder','ModuleTag_03', [('AutoAcquireEnemiesWhenIdle = Yes Stealthed','AutoAcquireEnemiesWhenIdle = Yes')])
    # Retain the owned infantry mesh/animation and SNIPER armour rules, but none
    # of the Pathfinder's hidden targeting or garrison-stealth behaviour.
    weapon('Euro_MarksmanRifle',PrimaryDamage=40,AttackRange=240,DelayBetweenShots=1200,
           AntiAirborneVehicle='No',AntiAirborneInfantry='No')
    describe('Euro_Rifleman','Legionnaire','French line infantry with Belgian MINIMI support weapons. '
        'Research assault grenades to clear garrisons; Portuguese airborne troops use the same equipment.')
    # A small rifle/range advantage over the $225 Ranger now has a price premium.
    data('Euro_Rifleman')['cost']=250
    g['BUTTON_LABELS']['Command_UpgradeAmericaRangerFlashBangGrenade']=(
        'Assault Grenades','French assault grenades clear enemy infantry from garrisoned buildings.')

    describe('Euro_Ambulance','Valuk Recovery','Slovenia: Austrian Pandur-derived recovery carrier with Romanian and Icelandic crews. '
        'Repairs nearby ground vehicles only after eight seconds without damage. Recovery auras do not stack.')
    d=data('Euro_Ambulance');d.update(command='Euro_RecoveryCommandSet',cost=650)
    d['extra']+=['RemoveModule '+tag for tag in ('ModuleTag_03','ModuleTag_04','ModuleTag_06','ModuleTag_22','ModuleTag_23')]
    d['extra']+=weapon_set()
    module('Euro_Ambulance',[
        'Behavior = AutoHealBehavior ModuleTag_Euro_Recovery',
        '  HealingAmount = 7','  HealingDelay = 1000','  Radius = 110','  DamageCooldown = 8000',
        '  StartsActive = Yes','  KindOf = VEHICLE','  ForbiddenKindOf = AIRCRAFT',
        '  SkipSelfForHealing = Yes','End',
        'Behavior = MaxHealthUpgrade ModuleTag_Euro_RecoveryArmour',
        '  TriggeredBy = Upgrade_EuroRecovery','  AddMaxHealth = 150','  ChangeType = ADD_CURRENT_HEALTH_TOO','End'])
    describe('Euro_Typhoon','Typhoon Interceptor','United Kingdom: air-superiority fighter with Spanish aircrews. '
        'Only attacks airborne targets. Danish countermeasures improve survival against missiles.')
    weapon('Euro_TyphoonMissile',AntiGround='No',AntiAirborneVehicle='Yes',AntiAirborneInfantry='Yes')

    # Research replaces the broad USA late-game upgrade menu and battle plans.
    g['UPGRADES']=[u for u in g['UPGRADES'] if u[0] not in {'Upgrade_EuroLynx','Upgrade_EuroGreenDeal'}]
    g['UPGRADES'] += [
        ('Upgrade_EuroFireControl','Coalition Fire Control','Greek optics and Hungarian electronics increase Leopard and DANA range by 10%.',1200,45,'Euro_UpgradeOptics'),
        ('Upgrade_EuroSmoke','Smoke Coordination','Unlocks an eight-second smoke screen from the Command Centre. Enemy ground direct-fire range against troops in smoke is reduced by 25%; artillery and aircraft are unaffected.',800,30,'Euro_PowerSpyDrone'),
        ('Upgrade_EuroRecovery','Armoured Recovery Kits','Romanian recovery crews add 150 health to Valuk carriers. Repair auras still do not stack.',700,30,'Euro_PowerEmergencyRepair')]
    g['SKIRMISH_AI_UPGRADES']=[u for u in g['SKIRMISH_AI_UPGRADES'] if u[0] not in {'Upgrade_EuroLynx','Upgrade_EuroGreenDeal'}]
    g['SKIRMISH_AI_UPGRADES'] += [('Upgrade_EuroFireControl','Euro_Leopard',3),('Upgrade_EuroSmoke','Euro_Ambulance',1),('Upgrade_EuroRecovery','Euro_Ambulance',2)]
    g['MODULES']['Euro_PowerPlant']=[]
    data('Euro_StrategyCenter')['extra']+=['RemoveModule ModuleTag_13','RemoveModule ModuleTag_14']
    describe('Euro_StrategyCenter','Joint Command','Coordinates Greek and Hungarian fire control, smoke screens and field recovery equipment.')
    menus=g['COMMAND_SETS']
    for slots in menus.values():
        for slot,value in list(slots.items()):
            if value in NEW_RETIRED or value in {'Euro_Command_UpgradeLynx','Euro_Command_UpgradeGreenDeal'}:del slots[slot]
    menus['Euro_BarracksCommandSet']={1:'Euro_Rifleman',2:'Euro_Milan',3:'Euro_Marksman',
        7:'Command_UpgradeAmericaRangerFlashBangGrenade',8:'Command_UpgradeAmericaRangerCaptureBuilding',
        9:'Euro_Command_UpgradeMinimi',13:'Command_SetRallyPoint',14:'Command_Sell'}
    menus['Euro_WarFactoryCommandSet']={1:'Euro_Leopard',2:'Euro_Boxer',3:'Euro_Skyranger',4:'Euro_Dana',5:'Euro_Ambulance',
        9:'Euro_Command_UpgradeAhead',13:'Command_SetRallyPoint',14:'Command_Sell'}
    menus['Euro_AirfieldCommandSet']={1:'Euro_Typhoon',9:'Command_UpgradeAmericaCountermeasures',13:'Command_SetRallyPoint',14:'Command_Sell'}
    menus['Euro_StrategyCommandSet']={1:'Euro_Command_UpgradeFireControl',2:'Euro_Command_UpgradeSmoke',3:'Euro_Command_UpgradeRecovery',14:'Command_Sell'}
    menus['Euro_RecoveryCommandSet']={13:'Command_Guard',14:'Command_Stop'}
    menus['Euro_FundsOfficeCommandSet']={14:'Command_Sell'}
    g['PROMOTION_MENUS']['Euro_SCIENCE_CommandSetRank1']={1:'SpyDrone'}
    g['PROMOTIONS'].pop('StealthFighter',None)
    g['PROMOTIONS'].pop('Pathfinder',None)
    for slots in g['PROMOTION_MENUS'].values():
        for slot,value in list(slots.items()):
            if value=='Pathfinder':del slots[slot]

    # Smoke is a conventional screen; the shared engine condition shortens
    # enemy direct-fire range without hiding units or making them immune.
    g['SPECIAL_POWERS'] += ['SpecialPower Euro_SmokeScreen','  Enum = SPECIAL_CLEANUP_AREA',
        '  ReloadTime = 120000','  PublicTimer = No','  SharedSyncedTimer = Yes',
        '  RadiusCursorRadius = 90','  ShortcutPower = Yes','End','',
        'Object Euro_SmokeField','  KindOf = IMMOBILE UNATTACKABLE IGNORED_IN_GUI','  Side = Europe',
        '  Draw = W3DModelDraw ModuleTag_Draw','    DefaultConditionState','      Model = NONE',
        '      ParticleSysBone = NONE Euro_ScreenSmoke','    End','  End',
        '  Body = ActiveBody ModuleTag_Body','    MaxHealth = 1','    InitialHealth = 1','  End',
        '  Behavior = LifetimeUpdate ModuleTag_Lifetime','    MinLifetime = 8000','    MaxLifetime = 8000','  End',
        '  Behavior = DestroyDie ModuleTag_Destroy','  End']
    for kind in ('VEHICLE','INFANTRY'):
        g['SPECIAL_POWERS'] += [f'  Behavior = WeaponBonusUpdate ModuleTag_Smoke_{kind}',
            f'    RequiredAffectKindOf = {kind}','    ForbiddenAffectKindOf = AIRCRAFT STRUCTURE',
            '    BonusDuration = 1000','    BonusDelay = 250','    BonusRange = 90',
            '    BonusConditionType = SMOKE_SCREEN','  End']
    g['SPECIAL_POWERS'] += ['  Geometry = CYLINDER','  GeometryMajorRadius = 1','  GeometryHeight = 1','End','']
    g['OBJECT_CREATION_LISTS'] += ['ObjectCreationList Euro_OCL_SmokeScreen','  CreateObject',
        '    ObjectNames = Euro_SmokeField','    Count = 1','  End','End','']
    g['EXTRA_CLIENT']=copied_record('ParticleSystem','SmokeFactionLarge','Euro_ScreenSmoke',[
        ('VolSphereRadius = 0.30','VolSphereRadius = 75'),('Size = 3.00 3.00','Size = 22.00 26.00'),
        ('BurstDelay = 4.00 20.00','BurstDelay = 2.00 3.00'),('BurstCount = 1.00 1.00','BurstCount = 4.00 4.00'),
        ('Lifetime = 120.00 120.00','Lifetime = 35.00 50.00'),('Alpha2 = 1.00 1.00 5','Alpha2 = 0.40 0.50 5'),
        ('Alpha3 = 0.00 0.00 120','Alpha3 = 0.00 0.00 50')])
    g['MODULES_COMMAND_CENTRE'] += ['Behavior = OCLSpecialPower ModuleTag_Euro_Smoke',
        '  SpecialPowerTemplate = Euro_SmokeScreen','  OCL = Euro_OCL_SmokeScreen',
        '  CreateLocation = CREATE_AT_LOCATION','  StartsPaused = Yes','End',
        'Behavior = UnpauseSpecialPowerUpgrade ModuleTag_Euro_SmokeUpgrade','  TriggeredBy = Upgrade_EuroSmoke',
        '  SpecialPowerTemplate = Euro_SmokeScreen','End']
    smoke_desc='Deploy an eight-second smoke screen. Enemy ground direct-fire range against units inside is reduced by 25%. Does not hide units; artillery, aircraft and close attackers remain effective.'
    g['POWERS']['SmokeScreen']=('Smoke Screen',smoke_desc)
    g['NEW_POWERS']['SmokeScreen']=dict(button='Command_Paradrop',shortcut='Command_ParadropFromShortcut',
        fields=['SpecialPower = Euro_SmokeScreen','Options = NEED_TARGET_POS CONTEXTMODE_COMMAND','Science = SCIENCE_AMERICA'])
    g['EURO_ART']['Euro_PowerSmokeScreen']=g['EURO_ART']['Euro_PowerSpyDrone']
    menus['Euro_CommandCenterCommandSet'][5]='Euro_Command_SmokeScreen'
    g['SHORTCUTS'][10]='SmokeScreen'

    # Reuse the coalition strike jets and uplink building; no particle beam.
    describe('Euro_ParticleCannonUplink','Coalition Strike Command','Coordinates a five-aircraft conventional strike every six minutes. '
        'The marked approach is visible and aircraft can be intercepted. Requires power.')
    d=data('Euro_ParticleCannonUplink');d['command']='Euro_StrikeCommandSet'
    d['extra']+=['RemoveModule ModuleTag_11','RemoveModule ModuleTag_12',
        'Behavior = OCLSpecialPower ModuleTag_Euro_ConventionalStrike',
        '  SpecialPowerTemplate = Euro_CoalitionStrike','  OCL = Euro_OCL_ConventionalStrike',
        '  CreateLocation = CREATE_AT_EDGE_NEAR_SOURCE','End']
    g['SPECIAL_POWERS']+=['SpecialPower Euro_CoalitionStrike','  Enum = SPECIAL_PARTICLE_UPLINK_CANNON',
        '  ReloadTime = 360000','  PublicTimer = Yes','  ViewObjectDuration = 15000','  ViewObjectRange = 200',
        '  RadiusCursorRadius = 100','  ShortcutPower = Yes','  AcademyClassify = ACT_SUPERPOWER','End','']
    strike=copied_record('ObjectCreationList','SUPERWEAPON_A10ThunderboltMissileStrike3','Euro_OCL_ConventionalStrike',
        [('AmericaJetA10Thunderbolt','Euro_Gripen')])
    strike=[re.sub(r'(FormationSize\s*=\s*)3',r'\g<1>5',line).replace('OnlyVisibleToOwningPlayer = Yes','OnlyVisibleToOwningPlayer = No') for line in strike]
    g['OBJECT_CREATION_LISTS']+=strike
    g['POWERS']['FireParticleUplinkCannon']=('Coalition Strike','Five Gripen aircraft deliver a conventional strike. Six-minute reload; interceptable aircraft and a visible target warning.')
    g['NEW_POWERS']['FireParticleUplinkCannon']=dict(button='Command_Paradrop',shortcut='Command_ParadropFromShortcut',
        fields=['SpecialPower = Euro_CoalitionStrike','Options = NEED_TARGET_POS CONTEXTMODE_COMMAND','Science = SCIENCE_AMERICA'])
    menus['Euro_StrikeCommandSet']={1:'Euro_Command_FireParticleUplinkCannon',14:'Command_Sell'}
    g['FACTION'].update(strategy='A professional coalition battlegroup: fight at range with Leopard tanks and DANA artillery, '
        'screen with Vilkas and Skyranger, and recover between engagements with Valuk. Expensive losses and scattered raids are dangerous.',
        features='11 core units; range, smoke and recovery; 31 contributing countries')

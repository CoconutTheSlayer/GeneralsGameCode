"""Writes the European faction, an add-on faction built on the game's USA units: a high-tech precision
army whose units see and shoot further and hit harder, but cost more and take longer to build.

It is written entirely as changes to the game's own data (ChildObject, ChildWeapon, WeaponReplace,
TextureReplace, SkirmishAISide; see GameEngine.cpp and ThingTemplate.cpp), so nothing of EA's data is
copied here. Run it after changing the tables below; it writes into resources/macos/GameData:

    Data/INI/Addon/Logic/Europe.ini    weapons, units, buildings and the faction
    Data/INI/Addon/Client/Europe.ini   build buttons and build menus
    Data/english/Addon.str             names and descriptions

The camouflage textures come from the player's own copy of the game: install_textures.py.

    python3 scripts/factions/europe/build_europe.py
"""
import os

ROOT = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
DATA = os.path.join(ROOT, "resources", "macos", "GameData")

# ---------------------------------------------------------------------------------------------------
# Weapons: (new name, parent, changes). The numbers follow the faction plan's balance rules: each unit
# worth 0.90-1.00 of its counterpart (health x damage per second / cost^2), range at most a tenth more.
WEAPONS = [
    ("Euro_RiflemanRifle", "RangerAdvancedCombatRifle", {"AttackRange": 110, "PrimaryDamage": 6}),
    ("Euro_MilanMissile", "MissileDefenderMissileWeapon", {"AttackRange": 190, "PrimaryDamage": 44}),
    ("Euro_MilanGuidedMissile", "MissileDefenderLaserGuidedMissileWeapon", {"AttackRange": 300, "PrimaryDamage": 44}),
    ("Euro_MarksmanRifle", "USAPathfinderSniperRifle", {"AttackRange": 330, "PrimaryDamage": 110}),
    # The Boxer's 30 mm cannon pierces armour (a tenth against infantry); its machine gun takes infantry.
    ("Euro_BoxerCannon", "Comanche20mmCannonWeapon",
     {"AttackRange": 165, "PrimaryDamage": 7, "DelayBetweenShots": 400, "DamageType": "ARMOR_PIERCING", "ClipSize": 0}),
    ("Euro_BoxerGun", "HumveeGun", {"AttackRange": 165, "PrimaryDamage": 8}),
    ("Euro_BoxerMissile", "HumveeMissileWeapon", {"AttackRange": 165}),
    ("Euro_LeopardGun", "CrusaderTankGun", {"AttackRange": 165, "PrimaryDamage": 72, "DelayBetweenShots": 2200}),
    ("Euro_LeclercGun", "PaladinTankGun", {"AttackRange": 165, "PrimaryDamage": 72, "DelayBetweenShots": 2200}),
    ("Euro_PulsRocket", "TomahawkMissileWeapon", {"AttackRange": 385, "PrimaryDamage": 160}),
    ("Euro_DroneGun", "SentryDroneGun", {"AttackRange": 165, "PrimaryDamage": 9}),
    ("Euro_TyphoonMissile", "RaptorJetMissileWeapon", {"AttackRange": 340, "PrimaryDamage": 102}),
    ("Euro_RafaleMissile", "StealthJetMissileWeapon", {"AttackRange": 240, "PrimaryDamage": 109}),
    ("Euro_TigerCannon", "Comanche20mmCannonWeapon", {"AttackRange": 215, "PrimaryDamage": 6.2}),
    ("Euro_TigerMissile", "ComancheAntiTankMissileWeapon", {"AttackRange": 215}),
    # Defences match the USA's worth; only their reach is a little longer.
    ("Euro_SampMissile", "PatriotMissileWeapon", {"AttackRange": 240}),
    ("Euro_SampMissileAir", "PatriotMissileWeaponAir", {"AttackRange": 375}),
    ("Euro_BastionHowitzer", "FireBaseHowitzerGun", {"AttackRange": 300}),
]

# ---------------------------------------------------------------------------------------------------
# Objects: (new name, parent, display name, description, changes).
# changes: cost, time (seconds), command set, prerequisites (list of alternatives per line),
# health (body module tag, health, takes subdual damage), fields {name: value}, weapons {old: new},
# extra lines.
BUILDINGS = [
    ("Euro_CommandCenter", "AmericaCommandCenter", "Command Centre",
     "The heart of the European base. Builds engineer vehicles and directs the general's powers.",
     dict(command="Euro_CommandCenterCommandSet")),
    ("Euro_PowerPlant", "AmericaPowerPlant", "Fusion Plant", "Powers the base.", dict()),
    ("Euro_Barracks", "AmericaBarracks", "Garrison", "Trains infantry.",
     dict(command="Euro_BarracksCommandSet")),
    ("Euro_SupplyCenter", "AmericaSupplyCenter", "Logistics Centre", "Gathers supplies and builds NH90 helicopters.",
     dict(command="Euro_SupplyCenterCommandSet", pre=[["Euro_PowerPlant"]],
          # Its free helicopter is the European one.
          extra=["ReplaceModule ModuleTag_12",
                 "  Behavior = SpawnBehavior ModuleTag_Euro_12",
                 "    SpawnNumber = 1", "    SpawnReplaceDelay = 9999", "    SpawnTemplateName = Euro_NH90",
                 "    OneShot = Yes", "    CanReclaimOrphans = No", "    SlavesHaveFreeWill = Yes",
                 "  End", "End"])),
    ("Euro_WarFactory", "AmericaWarFactory", "Armour Works", "Builds vehicles.",
     dict(command="Euro_WarFactoryCommandSet", pre=[["Euro_SupplyCenter"]])),
    ("Euro_Airfield", "AmericaAirfield", "Air Base", "Builds and rearms aircraft.",
     dict(command="Euro_AirfieldCommandSet", pre=[["Euro_SupplyCenter"]])),
    ("Euro_StrategyCenter", "AmericaStrategyCenter", "Joint Command",
     "Battle plans and the most advanced research.",
     dict(pre=[["Euro_WarFactory", "Euro_Airfield"]])),
    ("Euro_PatriotBattery", "AmericaPatriotBattery", "SAMP/T Battery",
     "Long range missile defence against aircraft and vehicles.",
     dict(pre=[["Euro_PowerPlant"]], weapons={"PatriotMissileWeapon": "Euro_SampMissile",
                                             "PatriotMissileWeaponAir": "Euro_SampMissileAir"})),
    ("Euro_FireBase", "AmericaFireBase", "Artillery Bastion",
     "A fortified howitzer that outranges ground attackers. Infantry can garrison it.",
     dict(pre=[["Euro_PowerPlant"]], weapons={"FireBaseHowitzerGun": "Euro_BastionHowitzer"})),
    ("Euro_ParticleCannonUplink", "AmericaParticleCannonUplink", "Orbital Lance",
     "A satellite beam that burns a precise path through the enemy.",
     dict(pre=[["Euro_StrategyCenter"]])),
    ("Euro_SupplyDropZone", "AmericaSupplyDropZone", "Airlift Depot", "Supplies arrive by air.",
     dict(pre=[["Euro_StrategyCenter"]])),
]

UNITS = [
    ("Euro_Dozer", "AmericaVehicleDozer", "Engineer Vehicle", "Builds and repairs the base, and clears mines.",
     dict(command="Euro_DozerCommandSet")),
    ("Euro_Rifleman", "AmericaInfantryRanger", "Rifleman",
     "Line infantry with a longer reach than most foot soldiers.",
     dict(cost=250, time=5.5, pre=[["Euro_Barracks"]], weapons={"RangerAdvancedCombatRifle": "Euro_RiflemanRifle"})),
    ("Euro_Milan", "AmericaInfantryMissileDefender", "MILAN Team",
     "Anti-tank missiles, guided much further with their laser designator.",
     dict(cost=325, time=5.5, pre=[["Euro_Barracks"]],
          weapons={"MissileDefenderMissileWeapon": "Euro_MilanMissile",
                   "MissileDefenderLaserGuidedMissileWeapon": "Euro_MilanGuidedMissile"})),
    ("Euro_Marksman", "AmericaInfantryPathfinder", "Marksman", "A long range sniper, unseen while still.",
     dict(cost=650, time=11, pre=[["Euro_Barracks"]], science="SCIENCE_Pathfinder",
          weapons={"USAPathfinderSniperRifle": "Euro_MarksmanRifle"})),
    ("Euro_Commando", "AmericaInfantryColonelBurton", "Special Forces",
     "An elite commando who plants charges and strikes unseen.",
     dict(pre=[["Euro_Barracks"], ["Euro_StrategyCenter"]])),
    ("Euro_Boxer", "AmericaVehicleHumvee", "Boxer",
     "An armoured infantry fighting vehicle for five soldiers. Its 30 mm cannon hunts vehicles, its machine gun "
     "infantry, and its laser shoots down incoming missiles.",
     dict(cost=1000, time=12, pre=[["Euro_WarFactory"]], command="Euro_BoxerCommandSet",
          health=("ModuleTag_02", 270, True),
          extra=[
              # Two guns on the turret: the game picks the better one for each target.
              "WeaponSet", "  Conditions = None", "  Weapon = PRIMARY Euro_BoxerCannon",
              "  Weapon = SECONDARY Euro_BoxerGun", "End",
              "WeaponSet", "  Conditions = PLAYER_UPGRADE", "  Weapon = PRIMARY Euro_BoxerCannon",
              "  Weapon = SECONDARY Euro_BoxerGun", "  Weapon = TERTIARY Euro_BoxerMissile", "End",
              # Active protection: the Paladin's point defence laser, scanning more slowly.
              "Behavior = PointDefenseLaserUpdate ModuleTag_Euro_PointDefense",
              "  WeaponTemplate = PaladinPointDefenseLaser",
              "  PrimaryTargetTypes = BALLISTIC_MISSILE SMALL_MISSILE",
              "  ScanRate = 700", "  ScanRange = 100.0", "  PredictTargetVelocityFactor = 3.0", "End",
              # Its own model (scripts/models/boxer.py).
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DTruckDraw ModuleTag_Euro_01",
              "    OkToChangeModelColor = Yes",
          ] + [line for state, model in (("NONE", "EUBOXER"), ("REALLYDAMAGED", "EUBOXER_D")) for line in (
              f"    ConditionState = {state}", f"      Model = {model}", "      Turret = TURRET",
              "      WeaponFireFXBone = PRIMARY Muzzle", "      WeaponMuzzleFlash = PRIMARY MuzzleFX",
              "      WeaponFireFXBone = SECONDARY Muzzle", "      WeaponMuzzleFlash = SECONDARY MuzzleFX",
              "      WeaponFireFXBone = TERTIARY Muzzle", "      WeaponLaunchBone = TERTIARY Muzzle",
              "    End")] + [
              "    TrackMarks = EXTireTrack.tga",
              "    Dust = RocketBuggyDust",
              "    DirtSpray = RocketBuggyDirtSpray",
              "    PowerslideSpray = RocketBuggyDirtPowerSlide",
              "    LeftFrontTireBone = TIRE01",
              "    RightFrontTireBone = TIRE02",
              "    MidLeftFrontTireBone = TIRE03",
              "    MidRightFrontTireBone = TIRE04",
              "    MidLeftRearTireBone = TIRE05",
              "    MidRightRearTireBone = TIRE06",
              "    LeftRearTireBone = TIRE07",
              "    RightRearTireBone = TIRE08",
              "    TireRotationMultiplier = 0.2",
              "    PowerslideRotationAddition = 1.25",
              "  End",
              "End"])),
    ("Euro_Leopard", "AmericaTankCrusader", "Leopard 2",
     "Main battle tank: hard to kill, accurate, a little longer reach than other tanks.",
     dict(cost=1000, time=11, pre=[["Euro_WarFactory"]], command="Euro_VehicleCommandSet",
          health=("ModuleTag_02", 500, True), weapons={"CrusaderTankGun": "Euro_LeopardGun"})),
    ("Euro_Leclerc", "AmericaTankPaladin", "Leclerc",
     "A heavy tank whose laser shoots down incoming missiles and shells for the whole group.",
     dict(cost=1200, time=13, pre=[["Euro_WarFactory"]], science="SCIENCE_PaladinTank", command="Euro_VehicleCommandSet",
          health=("ModuleTag_02", 520, True), weapons={"PaladinTankGun": "Euro_LeclercGun"})),
    ("Euro_Puls", "AmericaVehicleTomahawk", "PULS Launcher",
     "Rocket artillery with the longest reach in the war. Needs eyes: a Recon Drone or other spotter.",
     dict(cost=1300, time=22, pre=[["Euro_WarFactory"], ["Euro_StrategyCenter"]], command="Euro_VehicleCommandSet",
          health=("ModuleTag_02", 200, True), weapons={"TomahawkMissileWeapon": "Euro_PulsRocket"})),
    ("Euro_Skyranger", "AmericaTankAvenger", "Skyranger",
     "Air defence that tracks aircraft and marks targets for the army.",
     dict(cost=2000, time=11, pre=[["Euro_WarFactory"]], command="Euro_VehicleCommandSet")),
    ("Euro_Wiesel", "AmericaTankMicrowave", "Wiesel EW", "Electronic warfare: disables buildings and clears garrisons.",
     dict(cost=850, time=11, pre=[["Euro_WarFactory"], ["Euro_StrategyCenter"]], command="Euro_VehicleCommandSet")),
    ("Euro_Ambulance", "AmericaVehicleMedic", "Field Ambulance", "Heals infantry and cleans up toxins.",
     dict(cost=650, time=11, pre=[["Euro_WarFactory"]])),
    ("Euro_ReconDrone", "AmericaVehicleSentryDrone", "Recon Drone",
     "Sees further than any other vehicle and reveals stealthed units: the eyes of the PULS.",
     dict(cost=850, time=11, pre=[["Euro_WarFactory"]], weapons={"SentryDroneGun": "Euro_DroneGun"},
          fields={"VisionRange": 240, "ShroudClearingRange": 420})),
    ("Euro_Typhoon", "AmericaJetRaptor", "Typhoon", "A multirole fighter: long range missiles against air and ground.",
     dict(cost=1500, time=22, pre=[["Euro_Airfield"]], health=("ModuleTag_02", 170, False),
          weapons={"RaptorJetMissileWeapon": "Euro_TyphoonMissile"})),
    ("Euro_Rafale", "AmericaJetStealthFighter", "Rafale", "A strike fighter that slips past air defences.",
     dict(cost=1700, time=27.5, pre=[["Euro_Airfield"]], science="SCIENCE_StealthFighter",
          health=("ModuleTag_02", 130, False), weapons={"StealthJetMissileWeapon": "Euro_RafaleMissile"})),
    ("Euro_Tornado", "AmericaJetAurora", "Tornado", "A fast bomber that strikes before the defence can react.",
     dict(cost=2600, time=33, pre=[["Euro_Airfield"], ["Euro_StrategyCenter"]], health=("ModuleTag_02", 90, False))),
    ("Euro_Tiger", "AmericaVehicleComanche", "Tiger", "An attack helicopter armed with cannon and anti-tank missiles.",
     dict(cost=1600, time=22, pre=[["Euro_Airfield"]], health=("ModuleTag_04", 240, False),
          weapons={"Comanche20mmCannonWeapon": "Euro_TigerCannon", "ComancheAntiTankMissileWeapon": "Euro_TigerMissile"})),
    ("Euro_NH90", "AmericaVehicleChinook", "NH90", "A transport helicopter that also carries supplies.",
     dict(pre=[["Euro_SupplyCenter"]])),
]

# The textures of each vehicle's models, intact and damaged, drawn in European colours (eu_<name>,
# made by install_textures.py). Model textures are shared: the Skyranger has the Leopard's hull.
TEXTURES = {
    "Euro_Dozer": ["avconstdoz.tga", "avconstdoz_D.tga"],
    "Euro_Leopard": ["avleopard.tga", "avleopard_d.tga"],
    "Euro_Leclerc": ["avPaladin.tga", "avPaladin_d.tga"],
    "Euro_Puls": ["avtomahawk.tga", "avtomahawk_m.tga", "avtomahawk_d.tga", "avtomahawk_md.tga"],
    "Euro_Skyranger": ["AVAvnger.tga", "AVAvnger_D.tga", "avleopard.tga", "avleopard_d.tga"],
    "Euro_Wiesel": ["AvThunderBolt.tga", "AvThunderBolt_d.tga", "avtomahawk.tga", "avPaladin_d.tga"],
    "Euro_Ambulance": ["AvAmbulance.tga", "AvAmbulance_D.tga"],
    "Euro_ReconDrone": ["AVSentry.tga", "AVSentry_d.tga"],
    "Euro_Typhoon": ["avraptor.tga", "avraptor_d.tga"],
    "Euro_Rafale": ["avstealth.tga", "avstealth_d.tga"],
    "Euro_Tornado": ["AVAurora.tga", "AVAurora_d.tga"],
    "Euro_Tiger": ["AVComanche.tga", "AVComanche_d.tga"],
    "Euro_NH90": ["AVChinook.tga", "AVChinook_d.tga"],
}

# ---------------------------------------------------------------------------------------------------
# Build menus. Each slot: an object to build (it gets a button), or the name of an existing button.
COMMAND_SETS = {
    "Euro_DozerCommandSet": {1: "Euro_PowerPlant", 2: "Euro_StrategyCenter", 3: "Euro_Barracks",
                             4: "Euro_SupplyDropZone", 5: "Euro_SupplyCenter", 6: "Euro_ParticleCannonUplink",
                             7: "Euro_PatriotBattery", 8: "Euro_CommandCenter", 9: "Euro_FireBase",
                             11: "Euro_WarFactory", 13: "Euro_Airfield", 14: "Command_DisarmMinesAtPosition"},
    "Euro_CommandCenterCommandSet": {1: "Euro_Dozer", 2: "Euro_Command_SpectreGunship", 4: "Euro_Command_LeafletDrop",
                                     5: "Euro_Command_A10ThunderboltMissileStrike", 6: "Euro_Command_Paradrop",
                                     7: "Euro_Command_SpyDrone", 8: "Euro_Command_EmergencyRepair", 9: "Euro_Command_DaisyCutter",
                                     10: "Euro_Command_SpySatelliteScan", 13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_BarracksCommandSet": {1: "Euro_Rifleman", 2: "Euro_Milan", 3: "Euro_Commando", 4: "Euro_Marksman",
                                7: "Command_UpgradeAmericaRangerFlashBangGrenade",
                                8: "Command_UpgradeAmericaRangerCaptureBuilding",
                                13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_WarFactoryCommandSet": {1: "Euro_Leopard", 2: "Euro_Puls", 3: "Euro_Boxer", 4: "Euro_Ambulance",
                                  5: "Euro_Leclerc", 6: "Euro_ReconDrone", 7: "Euro_Skyranger", 8: "Euro_Wiesel",
                                  9: "Command_UpgradeAmericaSentryDroneGun", 11: "Command_UpgradeAmericaTOWMissile",
                                  13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_AirfieldCommandSet": {1: "Euro_Typhoon", 2: "Euro_Tiger", 3: "Euro_Tornado", 4: "Euro_Rafale",
                                7: "Command_UpgradeComancheRocketPods", 8: "Command_UpgradeAmericaLaserMissiles",
                                9: "Command_UpgradeAmericaCountermeasures", 10: "Command_UpgradeAmericaBunkerBusters",
                                13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_SupplyCenterCommandSet": {1: "Euro_NH90", 13: "Command_SetRallyPoint", 14: "Command_Sell"},
    # Vehicles: no drones, the USA's edge.
    "Euro_VehicleCommandSet": {11: "Command_AttackMove", 13: "Command_Guard", 14: "Command_Stop"},
    "Euro_BoxerCommandSet": {4: "Command_TransportExit", 5: "Command_TransportExit", 6: "Command_TransportExit",
                             7: "Command_TransportExit", 8: "Command_TransportExit", 9: "Command_Evacuate",
                             11: "Command_AttackMove", 13: "Command_Guard", 14: "Command_Stop"},
}

# ---------------------------------------------------------------------------------------------------
# General's powers: the USA's, with European names (ChildCommandButton copies a button, new labels).
# Each power: (European name, description); its buttons in the Command Centre, the promotion menus and
# the shortcut bar all get them.
POWERS = {
    "SpectreGunship": ("A400M Gunship", "A gunship circles the target and fires on everything below."),
    "LeafletDrop": ("Information Strike", "Leaflets and broadcasts: enemy units in the area stop fighting for a while."),
    "A10ThunderboltMissileStrike": ("Typhoon Strike", "Strike jets fire missiles at the target area."),
    "Paradrop": ("Airborne Drop", "Paratroopers land at the target."),
    "SpyDrone": ("Recon UAV", "A drone that watches an area and reveals stealthed units."),
    "EmergencyRepair": ("Field Repair", "Repairs vehicles in the area."),
    "DaisyCutter": ("Thermobaric Strike", "A heavy bomb that flattens everything in a wide area."),
    "SpySatelliteScan": ("Galileo Scan", "A satellite reveals any part of the map for a while."),
    "FireParticleUplinkCannon": ("Orbital Lance", "Fires the satellite beam."),
    "CIAIntelligence": ("Intelligence Report", "Reveals what the enemy is building."),
}
# Promotions: the purchase button's science (without Command_PurchaseScience) and its European name.
PROMOTIONS = {
    "PaladinTank": ("Leclerc Tank", "Lets the Armour Works build the Leclerc heavy tank."),
    "StealthFighter": ("Rafale", "Lets the Air Base build the Rafale strike fighter."),
    "SpyDrone": POWERS["SpyDrone"],
    "Pathfinder": ("Marksman", "Lets the Garrison train Marksmen."),
    "Paradrop1": ("Airborne Drop", POWERS["Paradrop"][1]),
    "Paradrop2": ("Airborne Drop 2", POWERS["Paradrop"][1] + " More of them."),
    "Paradrop3": ("Airborne Drop 3", POWERS["Paradrop"][1] + " A whole company."),
    "A10ThunderboltMissileStrike1": ("Typhoon Strike", POWERS["A10ThunderboltMissileStrike"][1]),
    "A10ThunderboltMissileStrike2": ("Typhoon Strike 2", POWERS["A10ThunderboltMissileStrike"][1] + " More jets."),
    "A10ThunderboltMissileStrike3": ("Typhoon Strike 3", POWERS["A10ThunderboltMissileStrike"][1] + " A full squadron."),
    "EmergencyRepair1": ("Field Repair", POWERS["EmergencyRepair"][1]),
    "EmergencyRepair2": ("Field Repair 2", POWERS["EmergencyRepair"][1] + " Faster."),
    "EmergencyRepair3": ("Field Repair 3", POWERS["EmergencyRepair"][1] + " Faster still."),
    "DaisyCutter": POWERS["DaisyCutter"],
    "LeafletDrop": POWERS["LeafletDrop"],
    "SpectreGunship": POWERS["SpectreGunship"],
}
PROMOTION_MENUS = {
    "Euro_SCIENCE_CommandSetRank1": {1: "PaladinTank", 2: "StealthFighter", 3: "SpyDrone"},
    "Euro_SCIENCE_CommandSetRank3": {1: "Pathfinder", 4: "Paradrop1", 5: "Paradrop2", 6: "Paradrop3",
                                     7: "A10ThunderboltMissileStrike1", 8: "A10ThunderboltMissileStrike2",
                                     9: "A10ThunderboltMissileStrike3", 10: "EmergencyRepair1",
                                     11: "EmergencyRepair2", 12: "EmergencyRepair3"},
    "Euro_SCIENCE_CommandSetRank8": {1: "DaisyCutter", 2: "LeafletDrop", 3: "SpectreGunship",
                                     4: "Command_FAKECOMMAND_PurchaseScienceMOAB"},
}
SHORTCUTS = {1: "SpyDrone", 2: "Paradrop", 3: "A10ThunderboltMissileStrike", 4: "EmergencyRepair", 5: "DaisyCutter",
             6: "FireParticleUplinkCannon", 7: "SpySatelliteScan", 8: "CIAIntelligence", 9: "SpectreGunship",
             10: "LeafletDrop"}

# Where the pictures of the USA objects are (texture, left, top, right, bottom), for the European
# buttons and portraits until make_icons.py has drawn their own.
USA_PICTURES = {
    "Euro_CommandCenter": (("SAUserInterface512_005.tga", 63, 251, 123, 299), ("SAUserInterface512_002.tga", 367, 1, 487, 97)),
    "Euro_PowerPlant": (("SAUserInterface512_005.tga", 187, 51, 247, 99), ("SAUserInterface512_003.tga", 367, 197, 487, 293)),
    "Euro_Barracks": (("SAUserInterface512_005.tga", 249, 351, 309, 399), ("SAUserInterface512_001.tga", 367, 99, 487, 195)),
    "Euro_SupplyCenter": (("SAUserInterface512_004.tga", 311, 438, 371, 486), ("SAUserInterface512_004.tga", 245, 99, 365, 195)),
    "Euro_WarFactory": (("SAUserInterface512_005.tga", 307, 401, 363, 449), ("SAUserInterface512_004.tga", 355, 197, 463, 286)),
    "Euro_Airfield": (("SAUserInterface512_005.tga", 187, 401, 247, 449), ("SAUserInterface512_001.tga", 123, 1, 243, 97)),
    "Euro_StrategyCenter": (("SAUserInterface512_004.tga", 435, 438, 495, 486), ("SAUserInterface512_004.tga", 1, 99, 121, 195)),
    "Euro_PatriotBattery": (("SAUserInterface512_005.tga", 435, 51, 495, 99), ("SAUserInterface512_003.tga", 367, 99, 487, 195)),
    "Euro_FireBase": (("SAUserInterface512_005.tga", 249, 51, 309, 99), ("SAUserInterface512_003.tga", 1, 197, 121, 293)),
    "Euro_ParticleCannonUplink": (("SAUserInterface512_004.tga", 63, 345, 123, 393), ("SAUserInterface512_004.tga", 1, 197, 121, 293)),
    "Euro_SupplyDropZone": (("SAUserInterface512_005.tga", 187, 151, 247, 199), ("SAUserInterface512_002.tga", 245, 295, 365, 391)),
    "Euro_Dozer": (("SAUserInterface512_005.tga", 63, 301, 123, 349), ("SAUserInterface512_001.tga", 123, 393, 243, 489)),
    "Euro_Rifleman": (("SAUserInterface512_003.tga", 123, 393, 243, 489), ("SAUserInterface512_003.tga", 245, 393, 365, 489)),
    "Euro_Milan": (("SAUserInterface512_005.tga", 311, 101, 371, 149), ("SAUserInterface512_003.tga", 123, 1, 243, 97)),
    "Euro_Marksman": (("SAUserInterface512_005.tga", 63, 101, 123, 149), ("SAUserInterface512_003.tga", 123, 99, 243, 195)),
    "Euro_Commando": (("SAUserInterface512_005.tga", 435, 301, 495, 349), ("SAUserInterface512_001.tga", 367, 197, 487, 293)),
    "Euro_Boxer": (("SAUserInterface512_005.tga", 435, 101, 495, 149), ("SAUserInterface512_002.tga", 367, 393, 487, 489)),
    "Euro_Leopard": (("SAUserInterface512_005.tga", 373, 251, 433, 299), ("SAUserInterface512_004.tga", 245, 197, 353, 286)),
    "Euro_Leclerc": (("SAUserInterface512_005.tga", 187, 101, 247, 149), ("SAUserInterface512_003.tga", 367, 1, 487, 97)),
    "Euro_Puls": (("SAUserInterface512_005.tga", 1, 201, 61, 249), ("SAUserInterface512_002.tga", 245, 197, 365, 293)),
    "Euro_Skyranger": (("SAUserInterface512_004.tga", 373, 438, 433, 486), ("SAUserInterface512_004.tga", 367, 1, 487, 97)),
    "Euro_Wiesel": (("SAUserInterface512_005.tga", 311, 351, 371, 399), ("SAUserInterface512_001.tga", 245, 1, 365, 97)),
    "Euro_Ambulance": (("SAUserInterface512_005.tga", 1, 401, 61, 449), ("SAUserInterface512_001.tga", 367, 1, 487, 97)),
    "Euro_ReconDrone": (("SAUserInterface512_005.tga", 249, 251, 309, 299), ("SAUserInterface512_001.tga", 245, 393, 365, 489)),
    "Euro_Typhoon": (("SAUserInterface512_005.tga", 125, 201, 185, 249), ("SAUserInterface512_002.tga", 1, 197, 121, 293)),
    "Euro_Rafale": (("SAUserInterface512_005.tga", 1, 1, 61, 49), ("SAUserInterface512_004.tga", 245, 1, 365, 97)),
    "Euro_Tornado": (("SAUserInterface512_005.tga", 435, 351, 495, 399), ("SAUserInterface512_001.tga", 123, 99, 243, 195)),
    "Euro_Tiger": (("SAUserInterface512_005.tga", 373, 301, 433, 349), ("SAUserInterface512_001.tga", 123, 295, 243, 391)),
    "Euro_NH90": (("SAUserInterface512_005.tga", 435, 251, 495, 299), ("SAUserInterface512_001.tga", 367, 393, 487, 489)),
}

# Hot keys, unique within each build menu.
HOTKEYS = {
    "Euro_PowerPlant": "P", "Euro_StrategyCenter": "J", "Euro_Barracks": "G", "Euro_SupplyDropZone": "D",
    "Euro_SupplyCenter": "L", "Euro_ParticleCannonUplink": "O", "Euro_PatriotBattery": "S", "Euro_CommandCenter": "C",
    "Euro_FireBase": "B", "Euro_WarFactory": "A", "Euro_Airfield": "R", "Euro_Dozer": "E", "Euro_Rifleman": "R",
    "Euro_Milan": "M", "Euro_Commando": "F", "Euro_Marksman": "K", "Euro_Leopard": "L", "Euro_Puls": "P",
    "Euro_Boxer": "B", "Euro_Ambulance": "A", "Euro_Leclerc": "C", "Euro_ReconDrone": "D", "Euro_Skyranger": "S",
    "Euro_Wiesel": "W", "Euro_Typhoon": "T", "Euro_Tiger": "I", "Euro_Tornado": "O", "Euro_Rafale": "R",
    "Euro_NH90": "N",
}

FACTION = {
    "name": "Europe",
    "strategy": "Precision and protection: a small, expensive army that sees first, shoots accurately and shoots down "
                "missiles, weak when swarmed early.",
    "features": "Long range artillery, active protection, the best air defence",
}


def european_texture(name):
    return "eu_" + name.lower()


def label(text, key):
    """Puts the hot key marker before the first occurrence of the key letter."""
    i = text.upper().find(key)
    return text if i < 0 else text[:i] + "&" + text[i:]


def write(path, text):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\r\n") as f:
        f.write(text)


def main():
    objects = BUILDINGS + UNITS
    names = {o[0]: o for o in objects}
    logic = ["; The European faction (scripts/factions/europe/build_europe.py). Generated, do not edit.", ""]
    for name, parent, changes in WEAPONS:
        logic.append(f"ChildWeapon {name} {parent}")
        logic += [f"  {k} = {v}" for k, v in changes.items()]
        logic += ["End", ""]
    for name, parent, display, _, c in objects:
        logic.append(f"ChildObject {name} {parent}")
        logic.append(f"  DisplayName = OBJECT:{name}")
        logic.append("  Side = Europe")
        logic.append(f"  ButtonImage = {name}")
        logic.append(f"  SelectPortrait = {name}_L")
        if "command" in c:
            logic.append(f"  CommandSet = {c['command']}")
        if "cost" in c:
            logic.append(f"  BuildCost = {c['cost']}")
        if "time" in c:
            logic.append(f"  BuildTime = {c['time']}")
        if "pre" in c:
            logic.append("  Prerequisites")
            logic += [f"    Object = {' '.join(alternatives)}" for alternatives in c["pre"]]
            if "science" in c:
                logic.append(f"    Science = {c['science']}")
            logic.append("  End")
        for key, value in c.get("fields", {}).items():
            logic.append(f"  {key} = {value}")
        for old, new in c.get("weapons", {}).items():
            logic.append(f"  WeaponReplace = {old} {new}")
        if "health" in c:
            tag, hp, subdual = c["health"]
            logic += [f"  ReplaceModule {tag}", f"    Body = ActiveBody ModuleTag_Euro_Body",
                      f"      MaxHealth = {hp}", f"      InitialHealth = {hp}"]
            if subdual:
                logic += [f"      SubdualDamageCap = {hp * 2}", "      SubdualDamageHealRate = 500",
                          "      SubdualDamageHealAmount = 50"]
            logic += ["    End", "  End"]
        logic += [f"  {line}" for line in c.get("extra", [])]
        logic += [f"  TextureReplace = {t} {european_texture(t)}" for t in TEXTURES.get(name, [])]
        logic += ["End", ""]

    # The faction: plays with the USA's skirmish AI, building its own units.
    logic += [
        "PlayerTemplate FactionEurope",
        "  Side = Europe",
        "  BaseSide = USA",
        "  PlayableSide = Yes",
        "  StartMoney = 0",
        "  PreferredColor = R:40 G:90 B:200",
        "  IntrinsicSciences = SCIENCE_AMERICA",
        "  PurchaseScienceCommandSetRank1 = Euro_SCIENCE_CommandSetRank1",
        "  PurchaseScienceCommandSetRank3 = Euro_SCIENCE_CommandSetRank3",
        "  PurchaseScienceCommandSetRank8 = Euro_SCIENCE_CommandSetRank8",
        "  SpecialPowerShortcutCommandSet = Euro_SpecialPowerShortcut",
        "  SpecialPowerShortcutWinName = GenPowersShortcutBarUS.wnd",
        "  SpecialPowerShortcutButtonCount = 10",
        "  DisplayName = INI:FactionEurope",
        "  StartingBuilding = Euro_CommandCenter",
        "  StartingUnit0 = Euro_Dozer",
        "  ScoreScreenImage = America_ScoreScreen",
        "  LoadScreenImage = SAFactionLogoPage_US",
        "  LoadScreenMusic = Load_USA",
        "  ScoreScreenMusic = Score_USA",
        "  FlagWaterMark = WatermarkUSA",
        "  EnabledImage = SSObserverUSA",
        "  BeaconName = MultiplayerBeacon",
        "  SideIconImage = GameinfoAMRCA",
        "  GeneralImage = USA_Logo",
        "  OldFaction = No",
        "  ArmyTooltip = TOOLTIP:BioStrategyLong_Europe",
        "  Features = GUI:BioFeatures_Europe",
        "  MedallionRegular = USAGeneral_slvr",
        "  MedallionHilite = USAGeneral_blue",
        "  MedallionSelect = USAGeneral_orng",
        "  SkirmishAISide = America",
    ]
    logic += [f"  SkirmishAIReplace = {o[1]} {o[0]}" for o in objects]
    logic += ["End", ""]

    client = ["; The European faction's build menus (scripts/factions/europe/build_europe.py). Generated, do not edit.", ""]
    # The pictures first: a button finds its picture as it is read.
    for name, pictures in USA_PICTURES.items():
        for image, (texture, left, top, right, bottom) in ((name, pictures[0]), (f"{name}_L", pictures[1])):
            client += [
                f"MappedImage {image}",
                f"  Texture = {texture}",
                "  TextureWidth = 512",
                "  TextureHeight = 512",
                f"  Coords = Left:{left} Top:{top} Right:{right} Bottom:{bottom}",
                "  Status = NONE",
                "End",
                "",
            ]
    buttons = {}
    for set_name, slots in COMMAND_SETS.items():
        for slot, entry in slots.items():
            if entry in names and entry not in buttons:
                o = names[entry]
                command = "DOZER_CONSTRUCT" if o in BUILDINGS else "UNIT_BUILD"
                button = f"Euro_Command_Construct{entry[len('Euro_'):]}"
                buttons[entry] = button
                client += [
                    f"CommandButton {button}",
                    f"  Command = {command}",
                    f"  Object = {entry}",
                    f"  TextLabel = CONTROLBAR:{button}",
                    f"  DescriptLabel = CONTROLBAR:ToolTip{button}",
                    f"  ButtonImage = {entry}",
                    "  ButtonBorderType = BUILD",
                    "End",
                    "",
                ]
    power_labels = {}

    def child_button(parent, name, text, description):
        nonlocal client
        client += [f"ChildCommandButton {name} {parent}", f"  TextLabel = CONTROLBAR:{name}",
                   f"  DescriptLabel = CONTROLBAR:ToolTip{name}", "End", ""]
        power_labels[name] = (text, description)
        return name

    used = {entry for slots in COMMAND_SETS.values() for entry in slots.values()}
    for power, (text, description) in POWERS.items():
        if f"Euro_Command_{power}" in used:
            child_button(f"Command_{power}", f"Euro_Command_{power}", text, description)
    shortcut = {slot: child_button(f"Command_{p}FromShortcut", f"Euro_Command_{p}FromShortcut", *POWERS[p])
                for slot, p in SHORTCUTS.items()}
    menus = {}
    for menu, slots in PROMOTION_MENUS.items():
        menus[menu] = {slot: entry if entry.startswith("Command_") else
                       child_button(f"Command_PurchaseScience{entry}", f"Euro_Command_PurchaseScience{entry}", *PROMOTIONS[entry])
                       for slot, entry in slots.items()}
    menus["Euro_SpecialPowerShortcut"] = shortcut
    for set_name, slots in menus.items():
        client.append(f"CommandSet {set_name}")
        client += [f"  {slot} = {entry}" for slot, entry in sorted(slots.items())]
        client += ["End", ""]
    for set_name, slots in COMMAND_SETS.items():
        client.append(f"CommandSet {set_name}")
        client += [f"  {slot} = {buttons.get(entry, entry)}" for slot, entry in sorted(slots.items())]
        client += ["End", ""]

    strings = ["// The European faction (scripts/factions/europe/build_europe.py). Generated, do not edit.", ""]

    def string(lbl, text):
        strings.extend([lbl, f'"{text}"', "END", ""])

    string("INI:FactionEurope", FACTION["name"])
    string("TOOLTIP:BioStrategyLong_Europe", FACTION["strategy"])
    string("GUI:BioFeatures_Europe", FACTION["features"])
    for name, parent, display, description, c in objects:
        string(f"OBJECT:{name}", display)
        if name in buttons:
            string(f"CONTROLBAR:{buttons[name]}", label(display, HOTKEYS.get(name, "")))
            string(f"CONTROLBAR:ToolTip{buttons[name]}", description)

    for name, (text, description) in power_labels.items():
        string(f"CONTROLBAR:{name}", label(text, text[0]))
        string(f"CONTROLBAR:ToolTip{name}", description)

    write(os.path.join(DATA, "Data", "INI", "Addon", "Logic", "Europe.ini"), "\n".join(logic))
    write(os.path.join(DATA, "Data", "INI", "Addon", "Client", "Europe.ini"), "\n".join(client))
    write(os.path.join(DATA, "Data", "english", "Addon.str"), "\n".join(strings))
    print(f"Wrote {len(WEAPONS)} weapons, {len(objects)} objects, {len(buttons)} build buttons, {len(COMMAND_SETS)} build menus.")


if __name__ == "__main__":
    main()

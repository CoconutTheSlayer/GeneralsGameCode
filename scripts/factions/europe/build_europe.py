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

def tank_draw(model, turret, module_lines=()):
    """A tracked vehicle drawn with its own model (scripts/models/leopard.py, leclerc.py): the USA tank's draw
    module replaced by one with the same bones (Turret, TurretMS, Barrel, TurretFX) and scrolling treads."""
    lines = ["ReplaceModule ModuleTag_01", "  Draw = W3DTankDraw ModuleTag_Euro_01", "    OkToChangeModelColor = Yes"]
    lines += [f"    {line}" for line in module_lines]
    for state, suffix in (("NONE", ""), ("REALLYDAMAGED", "_D"), ("RUBBLE", "_D")):
        lines += [f"    ConditionState = {state}", f"      Model = {model}{suffix}", f"      Turret = {turret}",
                  "      WeaponFireFXBone = PRIMARY TurretMS", "      WeaponRecoilBone = PRIMARY Barrel",
                  "      WeaponMuzzleFlash = PRIMARY TurretFX", "      WeaponLaunchBone = PRIMARY TurretMS", "    End"]
    lines += ["    TrackMarks = EXTnkTrack.tga", "    TreadAnimationRate = 2.0", "    TreadDriveSpeedFraction = 0.3",
              "    TreadPivotSpeedFraction = 0.6", "  End", "End"]
    return lines


def jet_draw(model, burners):
    """A jet drawn with its own model (scripts/models/typhoon.py, rafale.py, tornado.py): the USA jet's draw
    module replaced by one with the same states and bones (WeaponA, Engine, Wingtip, Smoke), the afterburner
    flames `burners` shown only with the afterburner, the damaged model also as the crashed wreck."""
    flames = " ".join(burners)
    trails = ["ParticleSysBone = Wingtip01 JetContrail", "ParticleSysBone = Wingtip02 JetContrail"]
    burning = [f"ShowSubObject = {flames}", "ParticleSysBone = Engine01 JetLenzflare",
               "ParticleSysBone = Engine02 JetLenzflare"]
    smoke = ["ParticleSysBone = Smoke01 JetSmoke", "ParticleSysBone = Engine01 JetEngineDamagedSmoke"]
    states = [("JETEXHAUST", "", trails), ("JETEXHAUST JETAFTERBURNER", "", trails + burning),
              ("REALLYDAMAGED", "_D", smoke), ("REALLYDAMAGED JETEXHAUST", "_D", smoke + trails),
              ("REALLYDAMAGED JETEXHAUST JETAFTERBURNER", "_D", smoke + trails + burning),
              ("RUBBLE", "_D", []),
              ("RUBBLE JETEXHAUST JETAFTERBURNER", "_D",
               ["ParticleSysBone = Engine01 JetExhaust", "ParticleSysBone = Engine02 JetExhaust"] + trails)]
    lines = ["ReplaceModule ModuleTag_01", "  Draw = W3DModelDraw ModuleTag_Euro_01", "    OkToChangeModelColor = Yes",
             "    DefaultConditionState", f"      Model = {model}", f"      HideSubObject = {flames}",
             "      WeaponLaunchBone = PRIMARY WeaponA", "    End"]
    for state, suffix, state_lines in states:
        lines += [f"    ConditionState = {state}", f"      Model = {model}{suffix}"]
        lines += [f"      {line}" for line in state_lines] + ["    End"]
    return lines + ["  End", "End"]


def building_draw(model, remove=(), state_lines=(), particles=None, module_lines=()):
    """A building's own model (scripts/models): intact, damaged and wrecked, each also at night, rising
    out of the ground while it is built. `remove`: the parent's other draw modules (its add-on parts).
    `state_lines`: lines added to every condition state (turrets, weapon bones).
    `particles`: {"" / "_D" / "_E": [(bone, particle system)]}, effects of the built model's states.
    `module_lines`: lines added to the draw module itself (ExtraPublicBone)."""
    states = [("", ""), ("DAMAGED", "_D"), ("REALLYDAMAGED RUBBLE", "_E")]
    lines = ["ReplaceModule ModuleTag_01", "  Draw = W3DModelDraw ModuleTag_Euro_01", "    OkToChangeModelColor = Yes"]
    lines += [f"    {line}" for line in module_lines]
    for building in ("", "AWAITING_CONSTRUCTION PARTIALLY_CONSTRUCTED ACTIVELY_BEING_CONSTRUCTED"):
        for condition, suffix in states:
            for night in (False, True):
                flags = " ".join(f for f in (building, condition, "NIGHT" if night else "") if f) or "NONE"
                name = model + suffix + ("N" if night and suffix else "_N" if night else "")
                lines += [f"    ConditionState = {flags}", f"      Model = {name}"]
                if building:
                    lines.append("      Flags = ADJUST_HEIGHT_BY_CONSTRUCTION_PERCENT")
                lines += [f"      {line}" for line in state_lines]
                if particles and not building:
                    lines += [f"      ParticleSysBone = {bone} {system}" for bone, system in particles.get(suffix, ())]
                lines.append("    End")
    return lines + ["  End", "End"] + [f"RemoveModule {tag}" for tag in remove]


# ---------------------------------------------------------------------------------------------------
# Objects: (new name, parent, display name, description, changes).
# changes: cost, time (seconds), command set, prerequisites (list of alternatives per line),
# health (body module tag, health, takes subdual damage), fields {name: value}, weapons {old: new},
# extra lines.
BUILDINGS = [
    ("Euro_CommandCenter", "AmericaCommandCenter", "Command Centre",
     "The heart of the European base. Builds engineer vehicles and directs the general's powers.",
     dict(command="Euro_CommandCenterCommandSet", extra=building_draw("EUCMDHQ", remove=(
         "ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_05", "ModuleTag_06", "ModuleTag_07",
         "ModuleTag_OfficersClub")))),
    ("Euro_PowerPlant", "AmericaPowerPlant", "Fusion Plant", "Powers the base.",
     # ModuleTag_02-04 are the USA's construction scaffolds, 05 its control rods: the upgrade shows the
     # Fusion Plant's own injectors (EUPWR_A1) instead.
     dict(extra=building_draw("EUPWR", remove=("ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_05"), particles={
         "": [("Steam01", "SteamVent")],
         "_D": [("Steam01", "SteamVent"), ("Smoke01", "SmolderingSmoke"), ("Fire01", "SmolderingFireLarge"),
                ("Spark01", "LiveWireSparks")],
         "_E": [("Smoke01", "SmolderingSmoke"), ("Smoke02", "SmolderingSmoke"), ("Fire01", "SmolderingFireLarge"),
                ("Spark01", "LiveWireSparks"), ("Spark02", "LiveWireSparks02")]}) + [
         "Draw = W3DModelDraw ModuleTag_Euro_Rods", "  OkToChangeModelColor = Yes",
         "  DefaultConditionState", "    Model = None", "  End",
         "  ConditionState = POWER_PLANT_UPGRADED", "    Model = EUPWR_A1", "  End",
         "  ConditionState = POWER_PLANT_UPGRADED REALLYDAMAGED RUBBLE", "    Model = None", "  End",
         "End"])),
    ("Euro_Barracks", "AmericaBarracks", "Garrison", "Trains infantry.",
     # ModuleTag_02-04 are the USA's construction scaffolds. Infantry leave through the gate (+X).
     dict(command="Euro_BarracksCommandSet", extra=building_draw(
         "EUBARR", remove=("ModuleTag_02", "ModuleTag_03", "ModuleTag_04"), particles={
             "_D": [("Smoke01", "SmolderingSmoke")],
             "_E": [("Smoke01", "SmolderingSmoke"), ("Smoke02", "SmolderingSmoke"), ("Fire01", "SmolderingFireLarge"),
                    ("Fire02", "SmolderingFireLarge")]}))),
    ("Euro_SupplyCenter", "AmericaSupplyCenter", "Logistics Centre", "Gathers supplies and builds NH90 helicopters.",
     dict(command="Euro_SupplyCenterCommandSet", pre=[["Euro_PowerPlant"]],
          # Its free helicopter is the European one.
          extra=["ReplaceModule ModuleTag_12",
                 "  Behavior = SpawnBehavior ModuleTag_Euro_12",
                 "    SpawnNumber = 1", "    SpawnReplaceDelay = 9999", "    SpawnTemplateName = Euro_NH90",
                 "    OneShot = Yes", "    CanReclaimOrphans = No", "    SlavesHaveFreeWill = Yes",
                 "  End", "End"] + building_draw("EUSUPC", remove=(
                     "ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_19", "ModuleTag_SpinnyBelt"),
                     particles={"_D": [(f"Smoke0{i}", s) for i in (1, 2, 3, 4) for s in ("SmolderingSmoke", "SmolderingFire")],
                                "_E": [(f"Smoke0{i}", s) for i in (1, 2, 3, 4) for s in ("SmolderingSmoke", "SmolderingFire")]}))),
    ("Euro_WarFactory", "AmericaWarFactory", "Armour Works", "Builds vehicles.",
     dict(command="Euro_WarFactoryCommandSet", pre=[["Euro_SupplyCenter"]], extra=building_draw("EUFACT", remove=(
         "ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_05", "ModuleTag_06", "ModuleTag_07",
         "ModuleTag_08")))),
    ("Euro_Airfield", "AmericaAirfield", "Air Base", "Builds and rearms aircraft.",
     dict(command="Euro_AirfieldCommandSet", pre=[["Euro_SupplyCenter"]], extra=building_draw("EUAIRF", remove=(
         "ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_05", "ModuleTag_06", "ModuleTag_07",
         "ModuleTag_08", "ModuleTag_09"), module_lines=[f"ExtraPublicBone = {bone}" for bone in (
         "Runway1Parking1", "Runway1Parking2", "Runway2Parking1", "Runway2Parking2", "Runway1Park1Han",
         "Runway1Park2Han", "Runway2Park1Han", "Runway2Park2Han", "Runway1Prep1", "Runway1Prep2", "Runway2Prep1",
         "Runway2Prep2", "RunwayStart1", "RunwayStart2", "RunwayEnd1", "RunwayEnd2", "HeliPark01")]))),
    ("Euro_StrategyCenter", "AmericaStrategyCenter", "Joint Command",
     "Battle plans and the most advanced research.",
     dict(pre=[["Euro_WarFactory", "Euro_Airfield"]],
          # Placed with its entrance (-Y) to the camera, as the model is drawn.
          fields={"PlacementViewAngle": 45},
          # Each battle plan shows its own part while it is active: the bombardment gun (EUSTRAT_G, the
          # turret the plan's weapon aims), the hold-the-line barriers (_H), the search-and-destroy radar (_S).
          extra=building_draw("EUSTRAT", remove=("ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_05",
                                                 "ModuleTag_09")) + [
              line for tag, door, model, bones in (
                  ("ModuleTag_06", "DOOR_1", "EUSTRAT_G", ["Turret = TURRET01", "TurretPitch = TURRETEL",
                                                           "WeaponLaunchBone = PRIMARY Muzzle",
                                                           "WeaponFireFXBone = PRIMARY Muzzle",
                                                           "WeaponMuzzleFlash = PRIMARY MuzzleFX",
                                                           "WeaponRecoilBone = PRIMARY Barrel"]),
                  ("ModuleTag_07", "DOOR_2", "EUSTRAT_H", []), ("ModuleTag_08", "DOOR_3", "EUSTRAT_S", []))
              for line in [f"ReplaceModule {tag}", f"  Draw = W3DModelDraw {tag}_Euro", "    OkToChangeModelColor = Yes",
                           "    DefaultConditionState", "      Model = NONE", "    End"]
              + [state for phase in ("OPENING", "WAITING_TO_CLOSE", "CLOSING")
                 for state in [f"    ConditionState = {door}_{phase}", f"      Model = {model}"]
                 + [f"      {bone}" for bone in bones] + ["    End"]]
              + ["  End", "End"]])),
    ("Euro_PatriotBattery", "AmericaPatriotBattery", "SAMP/T Battery",
     "Long range missile defence against aircraft and vehicles.",
     dict(cost=850, pre=[["Euro_PowerPlant"]], weapons={"PatriotMissileWeapon": "Euro_SampMissile",
                                             "PatriotMissileWeaponAir": "Euro_SampMissileAir"},
          extra=building_draw("EUSAMP", remove=("ModuleTag_02", "ModuleTag_03"), state_lines=(
              "Turret = TURRET01", "TurretPitch = TURRETEL",
              *(f"{k} = {slot} WeaponA" for k in ("WeaponLaunchBone", "WeaponFireFXBone")
                for slot in ("PRIMARY", "SECONDARY", "TERTIARY")))))),
    ("Euro_FireBase", "AmericaFireBase", "Artillery Bastion",
     "A fortified howitzer that outranges ground attackers. Infantry can garrison it.",
     dict(cost=800, pre=[["Euro_PowerPlant"]], weapons={"FireBaseHowitzerGun": "Euro_BastionHowitzer"},
          extra=building_draw("EUBAST", remove=("ModuleTag_02", "ModuleTag_03"), state_lines=(
              "Turret = TURRET01", "TurretPitch = TURRETEL", "WeaponMuzzleFlash = PRIMARY MuzzleFX",
              "WeaponRecoilBone = PRIMARY Barrel", "WeaponLaunchBone = PRIMARY MUZZLE01",
              "WeaponFireFXBone = PRIMARY MUZZLEFX"),
              module_lines=tuple(f"ExtraPublicBone = STATION0{k}" for k in range(1, 5))))),
    # The Forward Outpost: China's Bunker is the game's one weaponless, powerless, cheap garrison bunker (the
    # USA has none; the Fire Base would lose its gun, turret, hive body and open gun deck). Its garrison
    # fires from the slits (FIREPOINT bones in the model), and it heals friendly infantry and vehicles near
    # it, as the USA's Ambulance does. ModuleTag_02-04 are China's scaffolds; 09, 10, 25, 26 its mines.
    ("Euro_Outpost", "ChinaBunker", "Forward Outpost",
     "A small fortified bunker to build anywhere: five soldiers fire from it, and it patches up friendly "
     "infantry and vehicles around it.",
     dict(cost=500, time=8, pre=[["Euro_Barracks"]], command="Euro_OutpostCommandSet",
          fields={"VisionRange": 220, "ShroudClearingRange": 220, "VoiceSelect": "FireBaseSelect",
                  # Placed with its door (+X) to the camera.
                  "PlacementViewAngle": -45, "GeometryMajorRadius": 20.0, "GeometryMinorRadius": 20.0, "GeometryHeight": 14.0},
          extra=building_draw("EUOUTP", remove=("ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_09",
                                                "ModuleTag_10", "ModuleTag_25", "ModuleTag_26"), particles={
              "_D": [("Smoke01", "SmolderingSmoke")],
              "_E": [("Smoke01", "SmolderingSmoke"), ("Smoke02", "SmolderingSmoke"), ("Fire01", "SmolderingFire")]}) + [
              "ReplaceModule ModuleTag_05", "  Body = StructureBody ModuleTag_Euro_Body", "    MaxHealth = 750",
              "    InitialHealth = 750", "    SubdualDamageCap = 900", "    SubdualDamageHealRate = 500",
              "    SubdualDamageHealAmount = 100", "  End", "End"] + [
              line for tag, kinds, amount in (("Infantry", "INFANTRY", 3), ("Vehicles", "VEHICLE", 4))
              for line in (f"Behavior = AutoHealBehavior ModuleTag_Euro_Heal{tag}", f"  HealingAmount = {amount}",
                           "  HealingDelay = 1000", "  Radius = 90.0", "  StartsActive = Yes", f"  KindOf = {kinds}",
                           "  ForbiddenKindOf = AIRCRAFT STRUCTURE", "  SkipSelfForHealing = Yes", "End")])),
    ("Euro_ParticleCannonUplink", "AmericaParticleCannonUplink", "Orbital Lance",
     "A satellite beam that burns a precise path through the enemy.",
     dict(pre=[["Euro_StrategyCenter"]],
          # Placed with the tower's and the bunker's doors (-Y) to the camera.
          fields={"PlacementViewAngle": 45},
          # The beam's bones are in the model itself (no rising dish): the five pylons' tops FX01..FX05, the
          # emitter (FXConnector) and its tip (FXMain).
          extra=building_draw("EULANCE", remove=("ModuleTag_02", "ModuleTag_03", "ModuleTag_04", "ModuleTag_05"),
                              module_lines=[f"ExtraPublicBone = {bone}" for bone in
                                            ("FX01", "FX02", "FX03", "FX04", "FX05", "FXConnector", "FXMain")]))),
    # Europe's money maker: a steady grant instead of the USA's drops by plane, and the Green Deal research
    # (see MODULES and UPGRADES).
    ("Euro_FundsOffice", "AmericaSupplyDropZone", "EU Funds Office",
     "Receives a steady grant from the Union's funds. Researches the Green Deal: subsidies for every Fusion Plant.",
     dict(command="Euro_FundsOfficeCommandSet", pre=[["Euro_StrategyCenter"]],
          extra=building_draw("EUFUNDS", remove=("ModuleTag_02", "ModuleTag_03"), particles={
              "_D": [("Smoke01", "SmolderingSmoke"), ("Smoke02", "SmolderingSmoke"), ("Smoke01", "SmolderingFire")],
              "_E": [(f"Smoke0{i}", s) for i in (1, 2, 3) for s in ("SmolderingSmoke", "SmolderingFire")]}))),
]

UNITS = [
    ("Euro_Dozer", "AmericaVehicleDozer", "Engineer Vehicle", "Builds and repairs the base, and clears mines.",
     dict(command="Euro_DozerCommandSet", extra=[
         # Its own model (scripts/models/engineer.py), tracked; at work (building, repairing, clearing mines)
         # the arm swings forward to dig and the blade comes down (EUDOZ_W). A tank's draw module, not the
         # parent's truck one: ReplaceModule only takes the same kind, so the old one goes and the new one is added.
         "RemoveModule ModuleTag_01",
         "AddModule",
         "  Draw = W3DTankDraw ModuleTag_Euro_01",
         "    OkToChangeModelColor = Yes",
     ] + [line for state, model, smoke, dirt in (
         ("NONE", "EUDOZ", "DozerSmokeLight", False),
         ("MOVING", "EUDOZ", "DozerSmokeHeavy", False),
         ("ACTIVELY_CONSTRUCTING", "EUDOZ_W", "DozerSmokeHeavy", True),
         ("PREATTACK_A", "EUDOZ_W", "DozerSmokeHeavy", True),
         ("REALLYDAMAGED", "EUDOZ_D", "DozerSmokeHeavy", False),
         ("MOVING REALLYDAMAGED", "EUDOZ_D", "DozerSmokeHeavy", False),
         ("ACTIVELY_CONSTRUCTING REALLYDAMAGED", "EUDOZ_WD", "DozerSmokeHeavy", True),
         ("PREATTACK_A REALLYDAMAGED", "EUDOZ_WD", "DozerSmokeHeavy", True),
     ) for line in [f"    ConditionState = {state}", f"      Model = {model}",
                    f"      ParticleSysBone = EXHAUSTFX01 {smoke}"]
         + (["      ParticleSysBone = DIRTFX01 DozerDirtFall", "      ParticleSysBone = DIRTFX02 DozerDirtFall"] if dirt else [])
         + ["    End"]] + [
         "    TrackMarks = EXTnkTrack.tga",
         "    TreadAnimationRate = 4.0",
         "  End",
         "End"])),
    ("Euro_Rifleman", "AmericaInfantryRanger", "Rifleman",
     "Line infantry with a longer reach than most foot soldiers.",
     dict(cost=200, time=5, pre=[["Euro_Barracks"]], weapons={"RangerAdvancedCombatRifle": "Euro_RiflemanRifle"})),
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
     dict(cost=800, time=10, pre=[["Euro_WarFactory"]], command="Euro_BoxerCommandSet",
          # It can be dropped by the Coalition Reinforcements power, on a crate parachute.
          fields={"KindOf": "PRELOAD SELECTABLE CAN_ATTACK ATTACK_NEEDS_LINE_OF_SIGHT CAN_CAST_REFLECTIONS VEHICLE SCORE "
                            "TRANSPORT PARACHUTABLE"},
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
     dict(cost=1100, time=12, pre=[["Euro_WarFactory"]], command="Euro_VehicleCommandSet",
          health=("ModuleTag_02", 500, True), weapons={"CrusaderTankGun": "Euro_LeopardGun"},
          extra=tank_draw("EULEO", "Turret"))),
    ("Euro_Leclerc", "AmericaTankPaladin", "Leclerc",
     "A heavy tank whose laser shoots down incoming missiles and shells for the whole group.",
     dict(cost=1350, time=14, pre=[["Euro_WarFactory"]], science="SCIENCE_PaladinTank", command="Euro_VehicleCommandSet",
          health=("ModuleTag_02", 520, True), weapons={"PaladinTankGun": "Euro_LeclercGun"},
          extra=tank_draw("EULEC", "Turret01", module_lines=("ExtraPublicBone = Laser",)))),
    ("Euro_Puls", "AmericaVehicleTomahawk", "PULS Launcher",
     "Rocket artillery with the longest reach in the war. Needs eyes: a Recon Drone or other spotter.",
     dict(cost=1300, time=22, pre=[["Euro_WarFactory"], ["Euro_StrategyCenter"]], command="Euro_VehicleCommandSet",
          health=("ModuleTag_02", 200, True), weapons={"TomahawkMissileWeapon": "Euro_PulsRocket"},
          extra=[
              # Its own model (scripts/models/puls.py): the pods elevate on TURRETEL, the rocket leaves from
              # WEAPONA01, and the caps in the pod fronts (MISSILE) are hidden while it reloads.
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DTankDraw ModuleTag_Euro_01",
              "    OkToChangeModelColor = Yes",
              "    ProjectileBoneFeedbackEnabledSlots = PRIMARY",
          ] + [line for state, model in (("DefaultConditionState", "EUPULS"), ("ConditionState = REALLYDAMAGED", "EUPULS_D"))
               for line in (f"    {state}", f"      Model = {model}", "      Turret = TURRET", "      TurretPitch = TURRETEL",
                            "      WeaponLaunchBone = PRIMARY WeaponA", "      WeaponHideShowBone = PRIMARY MISSILE",
                            "    End")] + [
              "    AliasConditionState = RUBBLE",
              "    TrackMarks = EXTnkTrack.tga",
              "    TreadAnimationRate = 4.0",
              "  End",
              "End"])),
    ("Euro_Skyranger", "AmericaTankAvenger", "Skyranger",
     "Air defence that tracks aircraft and marks targets for the army.",
     dict(cost=2000, time=11, pre=[["Euro_WarFactory"]], command="Euro_VehicleCommandSet",
          extra=[
              # Its own models (scripts/models/skyranger.py): the Boxer's hull, and the turret riding on it as
              # an object of its own, as the Avenger's does.
              "ReplaceModule ModuleTag_OverlordContain",
              "  Behavior = OverlordContain ModuleTag_Euro_OverlordContain",
              "    Slots = 1", "    DamagePercentToUnits = 100%", "    AllowInsideKindOf = PORTABLE_STRUCTURE",
              "    PassengersAllowedToFire = Yes", "    PayloadTemplateName = Euro_SkyrangerTurret",
              "    ExperienceSinkForRider = Yes", "  End",
              "End",
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DOverlordTruckDraw ModuleTag_Euro_01",
              "    OkToChangeModelColor = Yes",
              "    ExtraPublicBone = TurretFX03", "    ExtraPublicBone = LazerSpot01", "    ExtraPublicBone = LazerSpot02",
          ] + [line for state, model, sub in (("DefaultConditionState", "EUSKYR", "HideSubObject = TURRET01"),
                                               ("ConditionState = REALLYDAMAGED", "EUSKYR_D", "HideSubObject = TURRET01"),
                                               ("ConditionState = DISGUISED", "EUSKYR", "ShowSubObject = TURRET01"),
                                               ("ConditionState = REALLYDAMAGED DISGUISED", "EUSKYR_D", "ShowSubObject = TURRET01"))
               for line in (f"    {state}", f"      Model = {model}", f"      {sub}", "    End")
               + (("    AliasConditionState = RUBBLE",) if state.endswith("= REALLYDAMAGED") else ())] + [
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
              "    PowerslideRotationAddition = 0.0",
              "  End",
              "End"])),
    # The Skyranger's turret, riding on its hull (FIREPOINT01): the 30 mm gun and missile pod pitch on
    # TURRETEL01, and the lasers fire from the muzzle (TURRETFX01) and the pod (TURRETFX02).
    ("Euro_SkyrangerTurret", "AmericaTankAvengerLaserTurret", "Skyranger", "",
     dict(extra=[
         "ReplaceModule ModuleTag_01",
         "  Draw = W3DDependencyModelDraw ModuleTag_Euro_01",
         "    OkToChangeModelColor = Yes",
         "    ExtraPublicBone = TurretFX01", "    ExtraPublicBone = TurretFX02", "    ExtraPublicBone = TURRET01",
         "    ExtraPublicBone = TURRETEL", "    ExtraPublicBone = TURRETEL01",
         "    AttachToBoneInContainer = FIREPOINT01",
     ] + [line for state, model in (("DefaultConditionState", "EUSKYR_G"), ("ConditionState = REALLYDAMAGED", "EUSKYR_GD"))
          for line in (f"    {state}", f"      Model = {model}", "      Turret = TURRET01", "      TurretPitch = TURRETEL01",
                       "    End")] + [
         "  End",
         "End"])),
    ("Euro_Wiesel", "AmericaTankMicrowave", "Wiesel EW", "Electronic warfare: disables buildings and clears garrisons.",
     dict(cost=850, time=11, pre=[["Euro_WarFactory"], ["Euro_StrategyCenter"]], command="Euro_VehicleCommandSet",
          extra=[
              # Its own model (scripts/models/wiesel.py): the beam leaves the emitter dish on the mast (WEAPON02).
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DTankDraw ModuleTag_Euro_01",
              "    ExtraPublicBone = WEAPON02",
              "    OkToChangeModelColor = Yes",
          ] + [line for state, model, glow in (
              ("NONE", "EUWIES", True), ("USING_WEAPON_A USING_WEAPON_B USING_WEAPON_C", "EUWIES", False),
              ("REALLYDAMAGED RUBBLE", "EUWIES_D", True),
              ("REALLYDAMAGED RUBBLE USING_WEAPON_A USING_WEAPON_B USING_WEAPON_C", "EUWIES_D", False))
               for line in ((f"    ConditionState = {state}", f"      Model = {model}")
                            + (("      ParticleSysBone = PROJECTORGLOW09 MicrowaveLenzflare",
                                "      ParticleSysBone = NONE MicrowaveRotisserie") if glow else ())
                            + ("    End",))] + [
              "    TrackMarks = EXTnkTrack.tga",
              "    TreadAnimationRate = 4.0",
              "  End",
              "End"])),
    ("Euro_Ambulance", "AmericaVehicleMedic", "Field Ambulance", "Heals infantry and cleans up toxins.",
     dict(cost=650, time=11, pre=[["Euro_WarFactory"]], extra=[
         # Its own model (scripts/models/ambulance.py), with the USA Ambulance's bones.
         "ReplaceModule ModuleTag_01",
         "  Draw = W3DTruckDraw ModuleTag_Euro_01",
         "    OkToChangeModelColor = Yes",
     ] + [line for state, model in (("NONE", "EUAMB"), ("REALLYDAMAGED", "EUAMB_D")) for line in (
         f"    ConditionState = {state}", f"      Model = {model}", "      Turret = TURRET", "      TurretPitch = TURRETEL",
         "      WeaponFireFXBone = PRIMARY WeaponA", "      WeaponLaunchBone = PRIMARY WeaponA", "    End")] + [
         "    ConditionState = RUBBLE",
         "      Model = EUAMB_D",
         "    End",
         "    TrackMarks = EXTireTrack.tga",
         "    Dust = RocketBuggyDust",
         "    DirtSpray = RocketBuggyDirtSpray",
         "    PowerslideSpray = RocketBuggyDirtPowerSlide",
         "    LeftFrontTireBone = TIRE01",
         "    RightFrontTireBone = TIRE02",
         "    LeftRearTireBone = TIRE03",
         "    RightRearTireBone = TIRE04",
         "    TireRotationMultiplier = 0.2",
         "    PowerslideRotationAddition = 2.5",
         "  End",
         "End"])),
    ("Euro_ReconDrone", "AmericaVehicleSentryDrone", "Recon Drone",
     "Sees further than any other vehicle and reveals stealthed units: the eyes of the PULS.",
     dict(cost=850, time=11, pre=[["Euro_WarFactory"]], weapons={"SentryDroneGun": "Euro_DroneGun"},
          fields={"VisionRange": 240, "ShroudClearingRange": 420},
          extra=[
              # Its own model (scripts/models/recon_drone.py), with the Sentry Drone's bones; the gun TURRETUP09
              # shows with the upgrade.
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DTankDraw ModuleTag_Euro_01",
              "    OkToChangeModelColor = Yes",
              "    InitialRecoilSpeed = 10",
              "    MaxRecoilDistance = 1.5",
              "    RecoilSettleSpeed = 3",
          ] + [line for state, model, gun in (
              ("NONE", "EUDRONE", "HideSubObject"), ("REALLYDAMAGED", "EUDRONE_D", "HideSubObject"),
              ("RUBBLE", "EUDRONE_D", "HideSubObject"), ("WEAPONSET_PLAYER_UPGRADE", "EUDRONE", "ShowSubObject"),
              ("WEAPONSET_PLAYER_UPGRADE REALLYDAMAGED", "EUDRONE_D", "ShowSubObject"),
              ("WEAPONSET_PLAYER_UPGRADE RUBBLE", "EUDRONE_D", "ShowSubObject"),
          ) for line in (
              f"    ConditionState = {state}", f"      Model = {model}", "      Turret = TURRET01",
              f"      {gun} = TURRETUP09", "      WeaponFireFXBone = PRIMARY TurretFX",
              "      WeaponMuzzleFlash = PRIMARY TurretFX", "      WeaponRecoilBone = PRIMARY TurretUp", "    End")] + [
              "    TrackMarks = EXTnkTrack.tga",
              "    TreadDebrisLeft = SentryDroneTrackDebrisDirtLeft",
              "    TreadDebrisRight = SentryDroneTrackDebrisDirtRight",
              "    TreadAnimationRate = 4.0",
              "  End",
              "End"])),
    ("Euro_Typhoon", "AmericaJetRaptor", "Typhoon", "A multirole fighter: long range missiles against air and ground.",
     dict(cost=1500, time=22, pre=[["Euro_Airfield"]], health=("ModuleTag_02", 170, False),
          weapons={"RaptorJetMissileWeapon": "Euro_TyphoonMissile"},
          extra=jet_draw("EUTYPH", ("BurnerFX01", "BurnerFX02")))),
    ("Euro_Rafale", "AmericaJetStealthFighter", "Rafale", "A strike fighter that slips past air defences.",
     dict(cost=1700, time=27.5, pre=[["Euro_Airfield"]], science="SCIENCE_StealthFighter",
          health=("ModuleTag_02", 130, False), weapons={"StealthJetMissileWeapon": "Euro_RafaleMissile"},
          extra=jet_draw("EURAF", ("BurnerFX03", "BurnerFX04")))),
    ("Euro_Tornado", "AmericaJetAurora", "Tornado", "A fast bomber that strikes before the defence can react.",
     dict(cost=2600, time=33, pre=[["Euro_Airfield"], ["Euro_StrategyCenter"]], health=("ModuleTag_02", 90, False),
          extra=jet_draw("EUTORN", ("BurnerFX03", "BurnerFX04")))),
    ("Euro_Tiger", "AmericaVehicleComanche", "Tiger", "An attack helicopter armed with cannon and anti-tank missiles.",
     dict(cost=1600, time=22, pre=[["Euro_Airfield"]], health=("ModuleTag_04", 240, False),
          weapons={"Comanche20mmCannonWeapon": "Euro_TigerCannon", "ComancheAntiTankMissileWeapon": "Euro_TigerMissile"},
          # Its own model (scripts/models/tiger.py): the rotors spin by the model's own animation, as the
          # Comanche's do; missiles leave the wing launchers, rockets the pods of the upgrade.
          extra=[
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DModelDraw ModuleTag_Euro_01",
              "    OkToChangeModelColor = Yes",
              "    DefaultConditionState",
              "      Model = EUTIGR",
              "      HideSubObject = MissileUpgrade",
              "      Animation = EUTIGR.EUTIGR",
              "      AnimationMode = LOOP",
              "      WeaponMuzzleFlash = PRIMARY TurretFX",
              "      WeaponFireFXBone = PRIMARY Muzzle",
              "      WeaponFireFXBone = SECONDARY WeaponA",
              "      WeaponLaunchBone = SECONDARY WeaponA",
              "    End",
          ] + [line for state, model, upgrade in (
              ("REALLYDAMAGED", "EUTIGR_D", False), ("WEAPONSET_PLAYER_UPGRADE", "EUTIGR", True),
              ("WEAPONSET_PLAYER_UPGRADE REALLYDAMAGED", "EUTIGR_D", True), ("RUBBLE", "EUTIGR_D", False))
              for line in [f"    ConditionState = {state}", f"      Model = {model}", f"      Animation = {model}.{model}",
                           "      AnimationMode = LOOP"] + ([
                  "      ShowSubObject = MissileUpgrade", "      WeaponFireFXBone = TERTIARY WeaponB",
                  "      WeaponLaunchBone = TERTIARY WeaponB"] if upgrade else []) + ["    End"]] + [
              "    ConditionState = RUBBLE SPECIAL_DAMAGED",
              "      Model = EUTIGR_D",
              "      HideSubObject = Props01",
              "    End",
              "  End",
              "End"])),
    ("Euro_NH90", "AmericaVehicleChinook", "NH90",
     "A transport helicopter that also carries supplies. Its passengers fire from its doors.",
     dict(pre=[["Euro_SupplyCenter"]],
          # Its own model (scripts/models/nh90.py), the rotors spun by its own animation; the Chinook's
          # cargo net (ModuleTag_02) still hangs below it with the supplies.
          extra=[
              "ReplaceModule ModuleTag_01",
              "  Draw = W3DModelDraw ModuleTag_Euro_01",
              "    OkToChangeModelColor = Yes",
              "    ExtraPublicBone = RopeStart",
              "    ExtraPublicBone = RopeEnd",
              "    DefaultConditionState",
              "      Model = EUNH90",
              "      Animation = EUNH90.EUNH90",
              "      AnimationMode = LOOP",
              "    End",
          ] + [line for state in ("REALLYDAMAGED", "RUBBLE") for line in (
              f"    ConditionState = {state}", "      Model = EUNH90_D", "      Animation = EUNH90_D.EUNH90_D",
              "      AnimationMode = LOOP", "    End")] + [
              "    ConditionState = RUBBLE SPECIAL_DAMAGED",
              "      Model = EUNH90_D",
              "      HideSubObject = Props01",
              "    End",
              "  End",
              "End",
              # Mechanised infantry: the troops it carries shoot from its doors.
              "ReplaceModule ModuleTag_08",
              "  Behavior = TransportContain ModuleTag_Euro_08",
              "    Slots = 8",
              "    DamagePercentToUnits = 100%",
              "    AllowInsideKindOf = INFANTRY VEHICLE",
              "    ForbidInsideKindOf = AIRCRAFT HUGE_VEHICLE",
              "    ExitDelay = 100",
              "    NumberOfExitPaths = 1",
              "    PassengersAllowedToFire = Yes",
              "  End",
              "End"])),
]

# The textures of each vehicle's models, intact and damaged, drawn in European colours (eu_<name>,
# made by install_textures.py). Model textures are shared: the Skyranger has the Leopard's hull.
TEXTURES = {
    # Infantry: uniforms in European grey-green; the Rifleman's captured-building flag is Europe's.
    "Euro_Rifleman": ["ZHCA_AIRanger.tga", "ATFlag01.tga"],
    "Euro_Milan": ["ZHCA_NITHunter.tga"],
    "Euro_Marksman": ["ZHCA_AIPthFindr.tga", "Z_AIPthFindr2.tga"],
    "Euro_Commando": ["ZHCA_AIHero2.tga", "Z_InfXtras.tga"],
}

# ---------------------------------------------------------------------------------------------------
# Europe's economy: subsidies. The USA's drop zone earns 6 crates of $250 every 2 minutes ($12.5 a second)
# and the GLA's Black Market $20 every 2 seconds ($10), each for $2500. The Funds Office earns as much as
# the Black Market ($80 every 8 seconds), as no plane can be shot down on the way; the Green Deal ($1500)
# makes every Fusion Plant earn $3 every 4 seconds, so the income grows with the base, and raids on the
# power hit the economy too. (AI tournaments with $90 and $4 had Europe a few points above the USA's AI
# against the USA and China, and well above it against GLA.) Modules added to objects, by object (tags unique to Europe):
MODULES = {
    "Euro_FundsOffice": [
        "RemoveModule ModuleTag_05",  # the drop by plane
        "Behavior = AutoDepositUpdate ModuleTag_Euro_Grant",
        "  DepositTiming = 8000",
        "  DepositAmount = 80",
        "  InitialCaptureBonus = 0",
        "End",
        # The drop zone produces nothing: without this the Green Deal button cannot research.
        "Behavior = ProductionUpdate ModuleTag_Euro_Research",
        "  MaxQueueEntries = 1",
        "End",
    ],
    "Euro_PowerPlant": [
        "Behavior = AutoDepositUpdate ModuleTag_Euro_Subsidy",
        "  DepositTiming = 4000",
        "  DepositAmount = 0",
        "  InitialCaptureBonus = 0",
        "  UpgradedBoost = UpgradeType:Upgrade_EuroGreenDeal Boost:3",
        "End",
    ],
}
# Upgrades: (name, display name, description, cost, time, button picture).
UPGRADES = [
    ("Upgrade_EuroGreenDeal", "Green Deal", "Every Fusion Plant receives a subsidy: $3 every 4 seconds.",
     1500, 45, "Euro_UpgradeGreenDeal"),
]
# Research the skirmish AI starts on its own (the USA's scripts know nothing of it): (upgrade, object, at
# least this many of it). The Green Deal once a Funds Office offers it and the base has 4 Fusion Plants.
SKIRMISH_AI_UPGRADES = [("Upgrade_EuroGreenDeal", "Euro_PowerPlant", 4)]

# ---------------------------------------------------------------------------------------------------
# Build menus. Each slot: an object to build (it gets a button), or the name of an existing button.
COMMAND_SETS = {
    "Euro_DozerCommandSet": {1: "Euro_PowerPlant", 2: "Euro_StrategyCenter", 3: "Euro_Barracks",
                             4: "Euro_FundsOffice", 5: "Euro_SupplyCenter", 6: "Euro_ParticleCannonUplink",
                             7: "Euro_PatriotBattery", 8: "Euro_CommandCenter", 9: "Euro_FireBase", 10: "Euro_Outpost",
                             11: "Euro_WarFactory", 13: "Euro_Airfield", 14: "Command_DisarmMinesAtPosition"},
    "Euro_CommandCenterCommandSet": {1: "Euro_Dozer", 2: "Euro_Command_ArtilleryBarrage", 4: "Euro_Command_Coalition",
                                     6: "Euro_Command_Paradrop", 7: "Euro_Command_SpyDrone",
                                     8: "Euro_Command_EmergencyRepair", 10: "Euro_Command_SpySatelliteScan",
                                     13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_BarracksCommandSet": {1: "Euro_Rifleman", 2: "Euro_Milan", 3: "Euro_Commando", 4: "Euro_Marksman",
                                7: "Command_UpgradeAmericaRangerFlashBangGrenade",
                                8: "Command_UpgradeAmericaRangerCaptureBuilding",
                                13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_WarFactoryCommandSet": {1: "Euro_Leopard", 2: "Euro_Puls", 3: "Euro_Boxer", 4: "Euro_Ambulance",
                                  5: "Euro_Leclerc", 6: "Euro_ReconDrone", 7: "Euro_Skyranger", 8: "Euro_Wiesel",
                                  9: "Command_UpgradeAmericaSentryDroneGun", 11: "Command_UpgradeAmericaTOWMissile",
                                  13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_AirfieldCommandSet": {1: "Euro_Typhoon", 2: "Euro_Tiger",
                                7: "Command_UpgradeComancheRocketPods", 8: "Command_UpgradeAmericaLaserMissiles",
                                9: "Command_UpgradeAmericaCountermeasures", 10: "Command_UpgradeAmericaBunkerBusters",
                                13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_SupplyCenterCommandSet": {1: "Euro_NH90", 13: "Command_SetRallyPoint", 14: "Command_Sell"},
    "Euro_FundsOfficeCommandSet": {1: "Euro_Command_UpgradeGreenDeal", 14: "Command_Sell"},
    "Euro_OutpostCommandSet": {**{k: "Command_BunkerExit" for k in range(1, 6)}, 6: "Command_Evacuate",
                               13: "Command_Stop", 14: "Command_Sell"},
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
# Europe's own powers (the fortress general): a power of its own (SPECIAL_POWERS), a research to buy it
# (SCIENCES) and buttons copied from another faction's, pointed at them.
NEW_POWERS = {
    "ArtilleryBarrage": dict(
        text="Artillery Barrage", description="Heavy guns far behind the lines shell the target area.",
        button="Command_ArtilleryBarrage", shortcut="Command_ArtilleryBarrageFromShortcut",
        fields=["SpecialPower = Euro_SuperweaponArtilleryBarrage",
                "Science = SCIENCE_EuroArtilleryBarrage1 SCIENCE_EuroArtilleryBarrage2 SCIENCE_EuroArtilleryBarrage3"]),
    "Coalition": dict(
        text="Coalition Reinforcements",
        description="Allied transports drop two Boxers and a company of riflemen at the target.",
        button="Command_Paradrop", shortcut="Command_ParadropFromShortcut",
        fields=["SpecialPower = Euro_SuperweaponCoalition", "Science = SCIENCE_EuroCoalition"]),
}
POWERS.update({k: (v["text"], v["description"]) for k, v in NEW_POWERS.items()})
# Their researches: (prerequisites, purchase button to copy, name, description).
SCIENCES = {
    "EuroArtilleryBarrage1": ("SCIENCE_AMERICA SCIENCE_Rank3", "Command_PurchaseScienceArtilleryBarrage1",
                              "Artillery Barrage", NEW_POWERS["ArtilleryBarrage"]["description"]),
    "EuroArtilleryBarrage2": ("SCIENCE_EuroArtilleryBarrage1 SCIENCE_Rank3", "Command_PurchaseScienceArtilleryBarrage2",
                              "Artillery Barrage 2", NEW_POWERS["ArtilleryBarrage"]["description"] + " More guns."),
    "EuroArtilleryBarrage3": ("SCIENCE_EuroArtilleryBarrage2 SCIENCE_Rank3", "Command_PurchaseScienceArtilleryBarrage3",
                              "Artillery Barrage 3", NEW_POWERS["ArtilleryBarrage"]["description"] + " A whole regiment."),
    "EuroCoalition": ("SCIENCE_AMERICA SCIENCE_Rank8", "Command_PurchaseScienceParadrop1",
                      "Coalition Reinforcements", NEW_POWERS["Coalition"]["description"]),
}
SPECIAL_POWERS = [
    "SpecialPower Euro_SuperweaponArtilleryBarrage", "  Enum = SPECIAL_ARTILLERY_BARRAGE", "  ReloadTime = 300000",
    "  RequiredScience = SCIENCE_EuroArtilleryBarrage1", "  InitiateSound = FireArtilleryCannonSound", "  PublicTimer = No",
    "  SharedSyncedTimer = Yes", "  ViewObjectDuration = 30000", "  ViewObjectRange = 250", "  RadiusCursorRadius = 125",
    "  ShortcutPower = Yes", "  AcademyClassify = ACT_SUPERPOWER", "End", "",
    "SpecialPower Euro_SuperweaponCoalition", "  Enum = SPECIAL_PARADROP_AMERICA", "  ReloadTime = 360000",
    "  RequiredScience = SCIENCE_EuroCoalition", "  PublicTimer = No", "  SharedSyncedTimer = Yes",
    "  RadiusCursorRadius = 60", "  ShortcutPower = Yes", "  AcademyClassify = ACT_SUPERPOWER", "End", "",
]
# Coalition Reinforcements: one transport drops the Boxers on crate parachutes, another the riflemen.
DROP = ["  StartAtPreferredHeight = Yes", "  StartAtMaxSpeed = Yes", "  MaxAttempts = 4", "  DropOffset = X:0 Y:0 Z:-10",
        "  DropDelay = 300", "  ParachuteDirectly = Yes", "  DeliveryDistance = 0", "  PreOpenDistance = 300"]
OBJECT_CREATION_LISTS = [
    "ObjectCreationList Euro_OCL_Coalition",
    "  DeliverPayload", "    Transport = AmericaJetCargoPlane", "    PutInContainer = AmericaCrateParachute",
    "    Payload = Euro_Boxer 2"] + ["  " + line for line in DROP] + ["  End",
    "  DeliverPayload", "    Transport = AmericaJetCargoPlane", "    PutInContainer = AmericaParachute",
    "    Payload = Euro_Rifleman 8"] + ["  " + line for line in DROP] + ["  End", "End", ""]
# The Command Centre fires them.
MODULES_COMMAND_CENTRE = [
    "Behavior = OCLSpecialPower ModuleTag_Euro_Barrage",
    "  SpecialPowerTemplate = Euro_SuperweaponArtilleryBarrage",
    "  UpgradeOCL = SCIENCE_EuroArtilleryBarrage3 SUPERWEAPON_ArtilleryBarrage3",
    "  UpgradeOCL = SCIENCE_EuroArtilleryBarrage2 SUPERWEAPON_ArtilleryBarrage2",
    "  OCL = SUPERWEAPON_ArtilleryBarrage1",
    "  CreateLocation = CREATE_AT_EDGE_FARTHEST_FROM_TARGET",
    "End",
    "Behavior = OCLSpecialPower ModuleTag_Euro_Coalition",
    "  SpecialPowerTemplate = Euro_SuperweaponCoalition",
    "  OCL = Euro_OCL_Coalition",
    "  CreateLocation = CREATE_AT_EDGE_NEAR_SOURCE",
    "  OCLAdjustPositionToPassable = Yes",
    "End",
]

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
    "Euro_SCIENCE_CommandSetRank1": {1: "PaladinTank", 3: "SpyDrone"},
    "Euro_SCIENCE_CommandSetRank3": {1: "Pathfinder", 4: "Paradrop1", 5: "Paradrop2", 6: "Paradrop3",
                                     7: "EuroArtilleryBarrage1", 8: "EuroArtilleryBarrage2", 9: "EuroArtilleryBarrage3",
                                     10: "EmergencyRepair1", 11: "EmergencyRepair2", 12: "EmergencyRepair3"},
    "Euro_SCIENCE_CommandSetRank8": {1: "EuroCoalition"},
}
SHORTCUTS = {1: "Paradrop", 2: "ArtilleryBarrage", 3: "Coalition", 4: "EmergencyRepair", 5: "SpyDrone",
             6: "FireParticleUplinkCannon", 7: "SpySatelliteScan", 8: "CIAIntelligence"}
# Each power's buttons show Euro_Power<power>; each promotion its own picture.
PROMOTION_PICTURES = {
    "PaladinTank": "Euro_Leclerc", "StealthFighter": "Euro_Rafale", "Pathfinder": "Euro_Marksman",
    "SpyDrone": "Euro_PowerSpyDrone", "DaisyCutter": "Euro_PowerDaisyCutter", "LeafletDrop": "Euro_PowerLeafletDrop",
    "SpectreGunship": "Euro_PowerSpectreGunship", "Paradrop1": "Euro_PowerParadrop", "Paradrop2": "Euro_PowerParadrop2",
    "Paradrop3": "Euro_PowerParadrop3", "A10ThunderboltMissileStrike1": "Euro_PowerA10ThunderboltMissileStrike",
    "A10ThunderboltMissileStrike2": "Euro_PowerA10ThunderboltMissileStrike2",
    "A10ThunderboltMissileStrike3": "Euro_PowerA10ThunderboltMissileStrike3",
    "EmergencyRepair1": "Euro_PowerEmergencyRepair", "EmergencyRepair2": "Euro_PowerEmergencyRepair2",
    "EmergencyRepair3": "Euro_PowerEmergencyRepair3",
}
# USA buttons in the European menus: each gets a European copy (Euro_<button>) with its own picture.
USA_BUTTONS = {
    "Command_UpgradeAmericaRangerFlashBangGrenade": "Euro_UpgradeFlashBang",
    "Command_UpgradeAmericaRangerCaptureBuilding": "Euro_UpgradeCaptureBuilding",
    "Command_UpgradeAmericaSentryDroneGun": "Euro_UpgradeSentryDroneGun",
    "Command_UpgradeAmericaTOWMissile": "Euro_UpgradeTOWMissile",
    "Command_UpgradeComancheRocketPods": "Euro_UpgradeRocketPods",
    "Command_UpgradeAmericaLaserMissiles": "Euro_UpgradeLaserMissiles",
    "Command_UpgradeAmericaCountermeasures": "Euro_UpgradeCountermeasures",
    "Command_UpgradeAmericaBunkerBusters": "Euro_UpgradeBunkerBusters",
    "Command_FAKECOMMAND_PurchaseScienceMOAB": "Euro_PowerMOAB",
}
# The faction's own pictures, painted by make_art.py (which redefines these images); until then each
# shows the USA picture it replaces: (texture, texture size, left, top, right, bottom).
EURO_ART = {
    "Euro_LoadScreen": ("SCShellUserInterface512_003.tga", 512, 1, 1, 389, 389),
    "Euro_ScoreScreen": ("America_ScoreScreenuserinterface.tga", 1024, 0, 0, 799, 599),
    "Euro_Watermark": ("SCShellUserInterface512_001.tga", 512, 345, 391, 505, 487),
    "Euro_SideIcon": ("SCSmShellUserInterface512_001.tga", 512, 111, 424, 135, 446),
    "Euro_Logo": ("SCShellUserInterface512_006.tga", 512, 449, 153, 497, 201),
    "Euro_MedallionRegular": ("SCGenChallengeSelect512_001.tga", 512, 211, 402, 251, 442),
    "Euro_MedallionHilite": ("SCGenChallengeSelect512_001.tga", 512, 127, 392, 167, 432),
    "Euro_MedallionSelect": ("SCGenChallengeSelect512_001.tga", 512, 169, 392, 209, 432),
    "Euro_PowerSpectreGunship": ("SAUserInterface512_005.tga", 512, 125, 301, 185, 349),
    "Euro_PowerLeafletDrop": ("SAUserInterface512_005.tga", 512, 373, 151, 433, 199),
    "Euro_PowerA10ThunderboltMissileStrike": ("SAUserInterface512_004.tga", 512, 63, 445, 123, 493),
    "Euro_PowerA10ThunderboltMissileStrike2": ("SAUserInterface512_004.tga", 512, 245, 288, 305, 336),
    "Euro_PowerA10ThunderboltMissileStrike3": ("SAUserInterface512_005.tga", 512, 187, 251, 247, 299),
    "Euro_PowerParadrop": ("SAUserInterface512_005.tga", 512, 1, 251, 61, 299),
    # Europe's own powers: China's barrage and the USA's paradrop pictures until make_art.py paints them.
    "Euro_PowerArtilleryBarrage": ("SNUserInterface512_003.tga", 512, 435, 397, 495, 445),
    "Euro_PowerCoalition": ("SAUserInterface512_005.tga", 512, 1, 251, 61, 299),
    "Euro_PowerParadrop2": ("SAUserInterface512_005.tga", 512, 373, 201, 433, 249),
    "Euro_PowerParadrop3": ("SAUserInterface512_005.tga", 512, 249, 201, 309, 249),
    "Euro_PowerSpyDrone": ("SAUserInterface512_005.tga", 512, 187, 1, 247, 49),
    "Euro_PowerEmergencyRepair": ("SSUserInterface512_002.tga", 512, 1, 1, 61, 49),
    "Euro_PowerEmergencyRepair2": ("SSUserInterface512_002.tga", 512, 63, 1, 123, 49),
    "Euro_PowerEmergencyRepair3": ("SSUserInterface512_002.tga", 512, 125, 1, 185, 49),
    "Euro_PowerDaisyCutter": ("SAUserInterface512_005.tga", 512, 249, 301, 309, 349),
    "Euro_PowerSpySatelliteScan": ("SAUserInterface512_004.tga", 512, 63, 395, 123, 443),
    "Euro_PowerFireParticleUplinkCannon": ("SAUserInterface512_004.tga", 512, 187, 388, 247, 436),
    "Euro_PowerCIAIntelligence": ("SAUserInterface512_004.tga", 512, 63, 295, 123, 343),
    "Euro_PowerMOAB": ("SAUserInterface512_005.tga", 512, 311, 201, 371, 249),
    "Euro_UpgradeFlashBang": ("SAUserInterface512_004.tga", 512, 435, 338, 495, 386),
    "Euro_UpgradeCaptureBuilding": ("SSUserInterface512_002.tga", 512, 187, 51, 247, 99),
    "Euro_UpgradeSentryDroneGun": ("SAUserInterface512_005.tga", 512, 311, 251, 371, 299),
    "Euro_UpgradeTOWMissile": ("SAUserInterface512_004.tga", 512, 187, 438, 247, 486),
    "Euro_UpgradeRocketPods": ("SAUserInterface512_004.tga", 512, 125, 295, 185, 343),
    "Euro_UpgradeLaserMissiles": ("SAUserInterface512_004.tga", 512, 249, 388, 309, 436),
    "Euro_UpgradeCountermeasures": ("SAUserInterface512_005.tga", 512, 373, 51, 433, 99),
    "Euro_UpgradeBunkerBusters": ("SAUserInterface512_005.tga", 512, 63, 1, 123, 49),
}

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
    "Euro_Outpost": (("SAUserInterface512_005.tga", 249, 51, 309, 99), ("SAUserInterface512_003.tga", 1, 197, 121, 293)),
    "Euro_ParticleCannonUplink": (("SAUserInterface512_004.tga", 63, 345, 123, 393), ("SAUserInterface512_004.tga", 1, 197, 121, 293)),
    # The Green Deal research: the USA's Supply Lines picture until make_icons.py draws its own.
    "Euro_UpgradeGreenDeal": (("SAUserInterface512_005.tga", 187, 351, 247, 399), ("SAUserInterface512_005.tga", 187, 351, 247, 399)),
    "Euro_FundsOffice": (("SAUserInterface512_005.tga", 187, 151, 247, 199), ("SAUserInterface512_002.tga", 245, 295, 365, 391)),
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
    "Euro_PowerPlant": "P", "Euro_StrategyCenter": "J", "Euro_Barracks": "G", "Euro_FundsOffice": "F",
    "Euro_SupplyCenter": "L", "Euro_ParticleCannonUplink": "O", "Euro_PatriotBattery": "S", "Euro_CommandCenter": "C",
    "Euro_FireBase": "B", "Euro_WarFactory": "A", "Euro_Airfield": "R", "Euro_Dozer": "E", "Euro_Rifleman": "R",
    "Euro_Milan": "M", "Euro_Commando": "F", "Euro_Marksman": "K", "Euro_Leopard": "L", "Euro_Puls": "P",
    "Euro_Boxer": "B", "Euro_Ambulance": "A", "Euro_Leclerc": "C", "Euro_ReconDrone": "D", "Euro_Skyranger": "S",
    "Euro_Wiesel": "W", "Euro_Typhoon": "T", "Euro_Tiger": "I", "Euro_Tornado": "O", "Euro_Rafale": "R",
    "Euro_NH90": "N", "Euro_Outpost": "W",
}

FACTION = {
    "name": "Europe",
    "strategy": "Fortress and combined arms: mechanised infantry in Boxers, forward outposts and the strongest "
                "defences, advancing step by step behind its artillery. Slow to start, with a small air force.",
    "features": "Mechanised infantry, forward outposts, artillery and fortifications, subsidies",
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
    for key, (prerequisites, _, display, description) in SCIENCES.items():
        logic += [f"Science SCIENCE_{key}", f"  PrerequisiteSciences = {prerequisites}", "  SciencePurchasePointCost = 1",
                  "  IsGrantable = Yes", f"  DisplayName = SCIENCE:{key}",
                  f"  Description = CONTROLBAR:ToolTipEuro_Command_PurchaseScience{key}", "End", ""]
    logic += SPECIAL_POWERS + OBJECT_CREATION_LISTS
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
        logic += [f"  {line}" for line in MODULES.get(name, [])]
        if name == "Euro_CommandCenter":
            logic += [f"  {line}" for line in MODULES_COMMAND_CENTRE]
        logic += [f"  TextureReplace = {t} {european_texture(t)}" for t in TEXTURES.get(name, [])]
        logic += ["End", ""]

    for name, display, _, cost, time, picture in UPGRADES:
        logic += [f"Upgrade {name}", f"  DisplayName = UPGRADE:{name}", f"  BuildCost = {cost}",
                  f"  BuildTime = {time}", f"  ButtonImage = {picture}", "End", ""]

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
        "  ScoreScreenImage = Euro_ScoreScreen",
        "  LoadScreenImage = Euro_LoadScreen",
        "  LoadScreenMusic = Load_USA",
        "  ScoreScreenMusic = Score_USA",
        "  FlagWaterMark = Euro_Watermark",
        "  EnabledImage = Euro_SideIcon",
        "  BeaconName = MultiplayerBeacon",
        "  SideIconImage = Euro_SideIcon",
        "  GeneralImage = Euro_Logo",
        "  OldFaction = No",
        "  ArmyTooltip = TOOLTIP:BioStrategyLong_Europe",
        "  Features = GUI:BioFeatures_Europe",
        "  MedallionRegular = Euro_MedallionRegular",
        "  MedallionHilite = Euro_MedallionHilite",
        "  MedallionSelect = Euro_MedallionSelect",
        "  SkirmishAISide = America",
    ]
    logic += [f"  SkirmishAIReplace = {o[1]} {o[0]}" for o in objects]
    # Researches the USA's scripts know nothing of (AISkirmishPlayer.cpp).
    logic += [f"  SkirmishAIUpgrade = {u} {o} {n}" for u, o, n in SKIRMISH_AI_UPGRADES]
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
    for image, (texture, size, left, top, right, bottom) in EURO_ART.items():
        client += [f"MappedImage {image}", f"  Texture = {texture}", f"  TextureWidth = {size}",
                   f"  TextureHeight = {size}", f"  Coords = Left:{left} Top:{top} Right:{right} Bottom:{bottom}",
                   "  Status = NONE", "End", ""]
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
    for name, display, description, _, _, picture in UPGRADES:
        button = f"Euro_Command_Upgrade{name[len('Upgrade_Euro'):]}"
        client += [f"CommandButton {button}", "  Command = PLAYER_UPGRADE", f"  Upgrade = {name}",
                   f"  TextLabel = CONTROLBAR:{button}", f"  DescriptLabel = CONTROLBAR:ToolTip{button}",
                   f"  ButtonImage = {picture}", "  ButtonBorderType = UPGRADE", "End", ""]

    def child_button(parent, name, text, description, image=None, fields=()):
        nonlocal client
        client += [f"ChildCommandButton {name} {parent}", f"  TextLabel = CONTROLBAR:{name}",
                   f"  DescriptLabel = CONTROLBAR:ToolTip{name}"] + ([f"  ButtonImage = {image}"] if image else []) + \
                  [f"  {line}" for line in fields] + ["End", ""]
        power_labels[name] = (text, description)
        return name

    used = {entry for slots in COMMAND_SETS.values() for entry in slots.values()}
    def power_image(power):
        return f"Euro_Power{power}"

    for power, (text, description) in POWERS.items():
        if f"Euro_Command_{power}" in used:
            new = NEW_POWERS.get(power, {})
            child_button(new.get("button", f"Command_{power}"), f"Euro_Command_{power}", text, description,
                         power_image(power), new.get("fields", ()))
    shortcut = {slot: child_button(NEW_POWERS.get(p, {}).get("shortcut", f"Command_{p}FromShortcut"),
                                   f"Euro_Command_{p}FromShortcut", *POWERS[p], power_image(p),
                                   NEW_POWERS.get(p, {}).get("fields", ()))
                for slot, p in SHORTCUTS.items()}
    menus = {}
    for menu, slots in PROMOTION_MENUS.items():
        menus[menu] = {slot: entry if entry.startswith("Command_") else
                       child_button(SCIENCES[entry][1], f"Euro_Command_PurchaseScience{entry}", *SCIENCES[entry][2:],
                                    "Euro_PowerCoalition" if entry == "EuroCoalition" else "Euro_PowerArtilleryBarrage",
                                    [f"Science = SCIENCE_{entry}"]) if entry in SCIENCES else
                       child_button(f"Command_PurchaseScience{entry}", f"Euro_Command_PurchaseScience{entry}", *PROMOTIONS[entry],
                                    PROMOTION_PICTURES.get(entry))
                       for slot, entry in slots.items()}
    for usa, image in USA_BUTTONS.items():
        client += [f"ChildCommandButton Euro_{usa} {usa}", f"  ButtonImage = {image}", "End", ""]
        buttons[usa] = f"Euro_{usa}"
        for slots in menus.values():
            slots.update({slot: f"Euro_{usa}" for slot, entry in slots.items() if entry == usa})
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

    for name, display, description, _, _, _ in UPGRADES:
        button = f"Euro_Command_Upgrade{name[len('Upgrade_Euro'):]}"
        string(f"UPGRADE:{name}", display)
        string(f"CONTROLBAR:{button}", label(display, display[0]))
        string(f"CONTROLBAR:ToolTip{button}", description)

    for key, (_, _, display, _) in SCIENCES.items():
        string(f"SCIENCE:{key}", display)

    for name, (text, description) in power_labels.items():
        string(f"CONTROLBAR:{name}", label(text, text[0]))
        string(f"CONTROLBAR:ToolTip{name}", description)

    write(os.path.join(DATA, "Data", "INI", "Addon", "Logic", "Europe.ini"), "\n".join(logic))
    write(os.path.join(DATA, "Data", "INI", "Addon", "Client", "Europe.ini"), "\n".join(client))
    write(os.path.join(DATA, "Data", "english", "Addon.str"), "\n".join(strings))
    print(f"Wrote {len(WEAPONS)} weapons, {len(objects)} objects, {len(buttons)} build buttons, {len(COMMAND_SETS)} build menus.")


if __name__ == "__main__":
    main()

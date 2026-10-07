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
# Weapons: (new name, parent, changes). Range up about a fifth, damage up about a seventh.
WEAPONS = [
    ("Euro_RiflemanRifle", "RangerAdvancedCombatRifle", {"AttackRange": 120, "PrimaryDamage": 6}),
    ("Euro_MilanMissile", "MissileDefenderMissileWeapon", {"AttackRange": 210, "PrimaryDamage": 46}),
    ("Euro_MilanGuidedMissile", "MissileDefenderLaserGuidedMissileWeapon", {"AttackRange": 340, "PrimaryDamage": 46}),
    ("Euro_MarksmanRifle", "USAPathfinderSniperRifle", {"AttackRange": 360, "PrimaryDamage": 115}),
    ("Euro_BoxerGun", "HumveeGun", {"AttackRange": 175, "PrimaryDamage": 11}),
    ("Euro_BoxerMissile", "HumveeMissileWeapon", {"AttackRange": 180, "PrimaryDamage": 35}),
    ("Euro_LeopardGun", "CrusaderTankGun", {"AttackRange": 185, "PrimaryDamage": 70, "DelayBetweenShots": 2200}),
    ("Euro_LeclercGun", "PaladinTankGun", {"AttackRange": 185, "PrimaryDamage": 72, "DelayBetweenShots": 2200}),
    ("Euro_PulsRocket", "TomahawkMissileWeapon", {"AttackRange": 425, "PrimaryDamage": 170}),
    ("Euro_DroneGun", "SentryDroneGun", {"AttackRange": 175, "PrimaryDamage": 9}),
    ("Euro_TyphoonMissile", "RaptorJetMissileWeapon", {"AttackRange": 360, "PrimaryDamage": 112}),
    ("Euro_RafaleMissile", "StealthJetMissileWeapon", {"AttackRange": 260, "PrimaryDamage": 112}),
    ("Euro_TornadoBomb", "AuroraBombWeapon", {"PrimaryDamage": 450}),
    ("Euro_TigerCannon", "Comanche20mmCannonWeapon", {"AttackRange": 225, "PrimaryDamage": 7}),
    ("Euro_TigerMissile", "ComancheAntiTankMissileWeapon", {"AttackRange": 235, "PrimaryDamage": 57}),
    ("Euro_SampMissile", "PatriotMissileWeapon", {"AttackRange": 260, "PrimaryDamage": 34}),
    ("Euro_SampMissileAir", "PatriotMissileWeaponAir", {"AttackRange": 410, "PrimaryDamage": 29}),
    ("Euro_BastionHowitzer", "FireBaseHowitzerGun", {"AttackRange": 330, "PrimaryDamage": 86}),
]

# ---------------------------------------------------------------------------------------------------
# Objects: (new name, parent, display name, description, changes).
# changes: cost, time (seconds), command set, prerequisites (list of alternatives per line),
# weapons {old: new}, extra lines.
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
     "Precise infantry. Outranges most other foot soldiers.",
     dict(cost=275, time=6, pre=[["Euro_Barracks"]], weapons={"RangerAdvancedCombatRifle": "Euro_RiflemanRifle"})),
    ("Euro_Milan", "AmericaInfantryMissileDefender", "MILAN Team",
     "Anti-tank missiles, guided much further with their laser designator.",
     dict(cost=350, time=6, pre=[["Euro_Barracks"]],
          weapons={"MissileDefenderMissileWeapon": "Euro_MilanMissile",
                   "MissileDefenderLaserGuidedMissileWeapon": "Euro_MilanGuidedMissile"})),
    ("Euro_Marksman", "AmericaInfantryPathfinder", "Marksman", "A long range sniper, unseen while still.",
     dict(cost=700, time=12, pre=[["Euro_Barracks"]], science="SCIENCE_Pathfinder",
          weapons={"USAPathfinderSniperRifle": "Euro_MarksmanRifle"})),
    ("Euro_Commando", "AmericaInfantryColonelBurton", "Special Forces",
     "An elite commando who plants charges and strikes unseen.",
     dict(pre=[["Euro_Barracks"], ["Euro_StrategyCenter"]])),
    ("Euro_Boxer", "AmericaVehicleHumvee", "Boxer", "A wheeled infantry fighting vehicle that carries five soldiers.",
     dict(cost=850, time=12, pre=[["Euro_WarFactory"]],
          weapons={"HumveeGun": "Euro_BoxerGun", "HumveeMissileWeapon": "Euro_BoxerMissile"})),
    ("Euro_Leopard", "AmericaTankCrusader", "Leopard 2",
     "Main battle tank. Its gun outranges every other tank.",
     dict(cost=1100, time=13, pre=[["Euro_WarFactory"]], weapons={"CrusaderTankGun": "Euro_LeopardGun"})),
    ("Euro_Leclerc", "AmericaTankPaladin", "Leclerc",
     "A heavy tank whose laser shoots down incoming missiles and shells.",
     dict(cost=1300, time=15, pre=[["Euro_WarFactory"]], science="SCIENCE_PaladinTank",
          weapons={"PaladinTankGun": "Euro_LeclercGun"})),
    ("Euro_Puls", "AmericaVehicleTomahawk", "PULS Launcher",
     "Rocket artillery with the longest reach of any vehicle.",
     dict(cost=1450, time=25, pre=[["Euro_WarFactory"], ["Euro_StrategyCenter"]],
          weapons={"TomahawkMissileWeapon": "Euro_PulsRocket"})),
    ("Euro_Skyranger", "AmericaTankAvenger", "Skyranger",
     "Air defence that tracks aircraft and marks targets for the army.",
     dict(cost=2200, time=13, pre=[["Euro_WarFactory"]])),
    ("Euro_Wiesel", "AmericaTankMicrowave", "Wiesel EW", "Electronic warfare: disables buildings and clears garrisons.",
     dict(cost=900, time=12, pre=[["Euro_WarFactory"], ["Euro_StrategyCenter"]])),
    ("Euro_Ambulance", "AmericaVehicleMedic", "Field Ambulance", "Heals infantry and cleans up toxins.",
     dict(cost=650, time=12, pre=[["Euro_WarFactory"]])),
    ("Euro_ReconDrone", "AmericaVehicleSentryDrone", "Recon Drone",
     "Spots for the army from afar, and reveals stealthed units.",
     dict(cost=900, time=12, pre=[["Euro_WarFactory"]], weapons={"SentryDroneGun": "Euro_DroneGun"})),
    ("Euro_Typhoon", "AmericaJetRaptor", "Typhoon", "An air superiority fighter with long range missiles.",
     dict(cost=1650, time=25, pre=[["Euro_Airfield"]], weapons={"RaptorJetMissileWeapon": "Euro_TyphoonMissile"})),
    ("Euro_Rafale", "AmericaJetStealthFighter", "Rafale", "A strike fighter that slips past air defences.",
     dict(cost=1900, time=30, pre=[["Euro_Airfield"]], science="SCIENCE_StealthFighter",
          weapons={"StealthJetMissileWeapon": "Euro_RafaleMissile"})),
    ("Euro_Tornado", "AmericaJetAurora", "Tornado", "A fast bomber that strikes before the defence can react.",
     dict(cost=2800, time=38, pre=[["Euro_Airfield"], ["Euro_StrategyCenter"]],
          weapons={"AuroraBombWeapon": "Euro_TornadoBomb"})),
    ("Euro_Tiger", "AmericaVehicleComanche", "Tiger", "An attack helicopter armed with cannon and anti-tank missiles.",
     dict(cost=1750, time=25, pre=[["Euro_Airfield"]],
          weapons={"Comanche20mmCannonWeapon": "Euro_TigerCannon", "ComancheAntiTankMissileWeapon": "Euro_TigerMissile"})),
    ("Euro_NH90", "AmericaVehicleChinook", "NH90", "A transport helicopter that also carries supplies.",
     dict(pre=[["Euro_SupplyCenter"]])),
]

# The textures of each vehicle's models, intact and damaged, drawn in European colours (eu_<name>,
# made by install_textures.py). Model textures are shared: the Skyranger has the Leopard's hull.
TEXTURES = {
    "Euro_Dozer": ["avconstdoz.tga", "avconstdoz_D.tga"],
    "Euro_Boxer": ["AvHummer.tga", "AvHummer_D.tga"],
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
    "Euro_CommandCenterCommandSet": {1: "Euro_Dozer", 2: "Command_SpectreGunship", 4: "Command_LeafletDrop",
                                     5: "Command_A10ThunderboltMissileStrike", 6: "Command_Paradrop",
                                     7: "Command_SpyDrone", 8: "Command_EmergencyRepair", 9: "Command_DaisyCutter",
                                     10: "Command_SpySatelliteScan", 13: "Command_SetRallyPoint", 14: "Command_Sell"},
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
}

# The button pictures of the USA objects the European ones are built on (images of the game's own).
BUTTON_IMAGES = {
    "AmericaCommandCenter": "SAComCentr",
    "AmericaPowerPlant": "SAPowerPlant",
    "AmericaBarracks": "SABarracks",
    "AmericaSupplyCenter": "SASupplyCntr",
    "AmericaWarFactory": "SACWeaponsfact",
    "AmericaPatriotBattery": "SAPatriot",
    "AmericaFireBase": "SAFirebase",
    "AmericaAirfield": "SAACommand",
    "AmericaParticleCannonUplink": "SAUplink",
    "AmericaStrategyCenter": "SAStrategyCenter",
    "AmericaSupplyDropZone": "SADropZone",
    "AmericaInfantryRanger": "SARanger",
    "AmericaVehicleDozer": "SACDozer",
    "AmericaVehicleChinook": "SAChinook",
    "AmericaTankCrusader": "SACLeopard",
    "AmericaTankPaladin": "SAPaladin",
    "AmericaTankAvenger": "SAAvnger",
    "AmericaTankMicrowave": "SAThunderBolt",
    "AmericaJetRaptor": "SACRaptor",
    "AmericaJetAurora": "SAAurora",
    "AmericaJetStealthFighter": "SAStealth",
    "AmericaVehicleComanche": "SACCommanche",
    "AmericaInfantryMissileDefender": "SAMissleDefender",
    "AmericaInfantryPathfinder": "SAPathfinder1",
    "AmericaInfantryColonelBurton": "SABurton",
    "AmericaVehicleTomahawk": "SACTomahawk",
    "AmericaVehicleHumvee": "SAHummer",
    "AmericaVehicleSentryDrone": "SAsentry",
    "AmericaVehicleMedic": "SAAmbulance",
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
    "strategy": "High-tech precision: units that see and shoot further and hit harder, at a higher price.",
    "features": "Long range tanks and artillery, missile defence, fighter jets",
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
        for old, new in c.get("weapons", {}).items():
            logic.append(f"  WeaponReplace = {old} {new}")
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
        "  PurchaseScienceCommandSetRank1 = SCIENCE_AMERICA_CommandSetRank1",
        "  PurchaseScienceCommandSetRank3 = SCIENCE_AMERICA_CommandSetRank3",
        "  PurchaseScienceCommandSetRank8 = SCIENCE_AMERICA_CommandSetRank8",
        "  SpecialPowerShortcutCommandSet = SpecialPowerShortcutUSA",
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
                    f"  ButtonImage = {BUTTON_IMAGES[o[1]]}",
                    "  ButtonBorderType = BUILD",
                    "End",
                    "",
                ]
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

    write(os.path.join(DATA, "Data", "INI", "Addon", "Logic", "Europe.ini"), "\n".join(logic))
    write(os.path.join(DATA, "Data", "INI", "Addon", "Client", "Europe.ini"), "\n".join(client))
    write(os.path.join(DATA, "Data", "english", "Addon.str"), "\n".join(strings))
    print(f"Wrote {len(WEAPONS)} weapons, {len(objects)} objects, {len(buttons)} build buttons, {len(COMMAND_SETS)} build menus.")


if __name__ == "__main__":
    main()

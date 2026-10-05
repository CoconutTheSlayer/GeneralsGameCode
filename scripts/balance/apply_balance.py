#!/usr/bin/env python3
"""Apply the fork's Zero Hour balance changes as loose INI overrides.

The game prefers a loose file over the same path inside a .big archive, so this
script reads the original INI files from the player's own INIZH.big, applies the
changes listed in CHANGES below, and writes the edited files to <game>/Data/INI.
No EA data is stored in this repository.

Every change states the value it expects to replace. If the original data does
not match (a different game version, or a mod), the script stops without
writing anything.

Usage:
  apply_balance.py [--game-dir DIR]            apply the changes
  apply_balance.py [--game-dir DIR] --remove   delete the overrides again
  apply_balance.py [--game-dir DIR] --dry-run  check that every change applies

Note: balanced games cannot play online against unmodified clients, and
replays recorded with one data set do not play back with the other.
"""

import argparse
import os
import re
import struct
import sys

DEFAULT_GAME_DIR = os.path.expanduser("~/Games/GeneralsZH")
MANIFEST = "Data/INI/.balance-manifest"


# ---------------------------------------------------------------------------
# Change list
# ---------------------------------------------------------------------------

def set_value(path, block, key, old, new, module=None):
    """Replace `key = old` with `key = new` inside a top level block.

    If `module` is given, only the nested module whose header line contains
    that text is searched.
    """
    return ("set", path, block, key, old, new, module)


def remove_module(path, block, header, must_contain):
    """Remove a nested `Behavior = ...` module, checking its content first."""
    return ("remove_module", path, block, header, must_contain)


def set_slot(path, block, slot, button):
    """Set button `slot` of a CommandSet, which must currently be empty."""
    return ("set_slot", path, block, slot, button)


def remove_slot(path, block, slot, button):
    """Clear button `slot` of a CommandSet, which must hold `button`."""
    return ("remove_slot", path, block, slot, button)


def append(path, text):
    return ("append", path, text)


OBJ = "Data/INI/Object/"

# Extra general ranks so a general can eventually buy every promotion. The most
# expensive general (vanilla China, Infantry) needs 18 points; ranks 1-5 grant 7.
EXTRA_RANKS = [(6, 6500), (7, 8000), (8, 10000), (9, 12000), (10, 14500), (11, 17000),
               (12, 20000), (13, 23000), (14, 26500), (15, 30000), (16, 34000)]
RANK_TEXT = "".join(
    "\r\nRank %d\r\n"
    "  RankName                      = INI:RankLevel5\r\n"
    "  SkillPointsNeeded             = %d\r\n"
    "  SciencePurchasePointsGranted  = 1\r\n"
    "End\r\n" % (rank, points)
    for rank, points in EXTRA_RANKS)

CHANGES = [
    # --- China Infantry General (strongest China): less free power ------------
    set_value("Data/INI/Weapon.ini", "Weapon Infa_MiniGunnerGunAir", "AttackRange", "350.0", "250.0"),
    remove_module(OBJ + "InfantryGeneral.ini", "Object Infa_ChinaCommandCenter",
                  "Behavior = GrantUpgradeCreate", "Upgrade_Nationalism"),
    remove_module(OBJ + "InfantryGeneral.ini", "Object Infa_ChinaBarracks",
                  "Behavior = GrantUpgradeCreate", "Upgrade_Nationalism"),
    remove_module(OBJ + "InfantryGeneral.ini", "Object Infa_ChinaWarFactory",
                  "Behavior = GrantUpgradeCreate", "Upgrade_Nationalism"),
    set_slot("Data/INI/CommandSet.ini", "CommandSet Infa_ChinaPropagandaCenterCommandSet", 2,
             "Command_UpgradeChinaNationalism"),
    set_slot("Data/INI/CommandSet.ini", "CommandSet Infa_ChinaPropagandaCenterCommandSetUpgrade", 2,
             "Command_UpgradeChinaNationalism"),

    # --- USA Air Force General (strongest USA) ------------------------------
    set_value("Data/INI/Science.ini", "Science SCIENCE_AirF_CarpetBomb", "PrerequisiteSciences",
              "SCIENCE_AMERICA SCIENCE_Rank1", "SCIENCE_AMERICA SCIENCE_Rank3"),
    remove_slot("Data/INI/CommandSet.ini", "CommandSet AirF_SCIENCE_AMERICA_CommandSetRank1", 2,
                "AirF_Command_PurchaseScienceCarpetBomb"),
    set_slot("Data/INI/CommandSet.ini", "CommandSet AirF_SCIENCE_AMERICA_CommandSetRank3", 2,
             "AirF_Command_PurchaseScienceCarpetBomb"),
    set_value(OBJ + "AirforceGeneral.ini", "Object AirF_AmericaJetRaptor", "BuildCost", "1100", "1300"),
    # Missiles have 100 HP, so point defense now needs two shots per missile.
    set_value("Data/INI/Weapon.ini", "Weapon AirF_PointDefenseLaser", "PrimaryDamage", "100.0", "50.0"),
    set_value("Data/INI/Weapon.ini", "Weapon AirF_RaptorPointDefenseLaser", "PrimaryDamage", "100.0", "50.0"),

    # --- China (weakest overall) ---------------------------------------------
    set_value(OBJ + "ChinaVehicle.ini", "Object ChinaTankBattleMaster", "BuildCost", "800", "700"),
    set_value(OBJ + "ChinaVehicle.ini", "Object ChinaVehicleSupplyTruck", "BuildCost", "600", "500"),
    set_value("Data/INI/Upgrade.ini", "Upgrade Upgrade_Nationalism", "BuildCost", "2000", "1000"),
    # Overlord (and the Tank General's Emperor) 25% faster.
    set_value("Data/INI/Locomotor.ini", "Locomotor OverlordLocomotor", "Speed", "20", "25"),
    set_value("Data/INI/Locomotor.ini", "Locomotor NuclearOverlordLocomotor", "Speed", "30", "37.5"),

    # --- USA Superweapon General: a playable early game ------------------------
    set_value(OBJ + "SuperWeaponGeneral.ini", "Object SupW_AmericaVehicleHumvee", "BuildCost", "850", "700"),
    set_value(OBJ + "SuperWeaponGeneral.ini", "Object SupW_AmericaPowerPlant", "BuildCost", "900", "800"),
    set_value(OBJ + "SuperWeaponGeneral.ini", "Object SupW_AmericaSupplyDropZone", "BuildCost", "2500", "1750"),

    # --- China Nuke General -----------------------------------------------------
    # The faster 300 s missile power in the data cannot be used: the skirmish AI
    # fires the shared 360 s power by name. A cheaper silo is used instead.
    set_value(OBJ + "NukeGeneral.ini", "Object Nuke_ChinaNuclearMissileLauncher", "BuildCost", "4500", "4000"),
    set_value("Data/INI/Upgrade.ini", "Upgrade Upgrade_ChinaIsotopeStability", "BuildCost", "2000", "1000"),
    set_value(OBJ + "NukeGeneral.ini", "Object Nuke_ChinaInfantryRedguard", "BuildCost", "350", "300"),
    set_value(OBJ + "NukeGeneral.ini", "Object Nuke_ChinaInfantryTankHunter", "BuildCost", "350", "300"),
    set_value(OBJ + "NukeGeneral.ini", "Object Nuke_ChinaInfantryBlackLotus", "BuildCost", "1600", "1500"),
    set_value(OBJ + "NukeGeneral.ini", "Object Nuke_ChinaTankBattleMaster", "BuildTime", "12.0", "10.0"),
    set_value(OBJ + "NukeGeneral.ini", "Object Nuke_ChinaTankOverlord", "BuildTime", "22.0", "20.0"),

    # --- China Tank General: infantry surcharge +25% -> +10% ------------------------
    set_value(OBJ + "TankGeneral.ini", "Object Tank_ChinaInfantryRedguard", "BuildCost", "375", "330"),
    set_value(OBJ + "TankGeneral.ini", "Object Tank_ChinaInfantryTankHunter", "BuildCost", "375", "330"),
    set_value(OBJ + "TankGeneral.ini", "Object Tank_ChinaInfantryHacker", "BuildCost", "780", "690"),
    set_value(OBJ + "TankGeneral.ini", "Object Tank_ChinaInfantryBlackLotus", "BuildCost", "1875", "1650"),

    # --- GLA (vanilla) ----------------------------------------------------------
    set_value(OBJ + "GLAVehicle.ini", "Object GLATankScorpion", "BuildCost", "600", "550"),
    set_value(OBJ + "GLAVehicle.ini", "Object GLAVehicleQuadCannon", "BuildCost", "700", "650"),

    # --- All generals: more ranks ------------------------------------------------
    append("Data/INI/Rank.ini", RANK_TEXT),
]


# ---------------------------------------------------------------------------
# INI text editing
# ---------------------------------------------------------------------------

class ChangeError(Exception):
    pass


def find_block(text, header):
    """Return (start, end) of a top level block; end is just past its End line."""
    kind, name = header.split(None, 1)
    head = re.compile(r"^%s[ \t]+%s[ \t]*(;[^\r\n]*)?\r?$" % (re.escape(kind), re.escape(name)), re.M)
    matches = list(head.finditer(text))
    if len(matches) != 1:
        raise ChangeError("expected one '%s', found %d" % (header, len(matches)))
    end = re.compile(r"^End\b[^\r\n]*\r?\n?", re.M | re.I).search(text, matches[0].end())
    if not end:
        raise ChangeError("no End for '%s'" % header)
    return matches[0].start(), end.end()


def find_module(text, start, end, header, must_contain=None):
    """Return (start, end) of a nested module inside text[start:end]."""
    found = []
    for m in re.finditer(r"^[ \t]*%s\b[^\r\n]*\r?\n" % re.escape(header), text[start:end], re.M):
        m_start = start + m.start()
        close = re.compile(r"^[ \t]+End\b[^\r\n]*\r?\n?", re.M | re.I).search(text, start + m.end(), end)
        if not close:
            raise ChangeError("no End for module '%s'" % header)
        if must_contain is None or must_contain in text[m_start:close.end()]:
            found.append((m_start, close.end()))
    if len(found) != 1:
        raise ChangeError("expected one module '%s'%s, found %d"
                          % (header, " containing " + must_contain if must_contain else "", len(found)))
    return found[0]


def apply_change(text, change):
    op = change[0]
    if op == "set":
        _, _, block, key, old, new, module = change
        start, end = find_block(text, block)
        if module:
            start, end = find_module(text, start, end, module)
        line = re.compile(r"^([ \t]*%s[ \t]*=[ \t]*)%s(?=[ \t]*(;|\r?$))" % (re.escape(key), re.escape(old)), re.M)
        hits = list(line.finditer(text, start, end))
        if len(hits) != 1:
            raise ChangeError("%s: expected one '%s = %s', found %d" % (block, key, old, len(hits)))
        hit = hits[0]
        return text[:hit.start()] + hit.group(1) + new + text[hit.end():]
    if op == "remove_module":
        _, _, block, header, must_contain = change
        start, end = find_block(text, block)
        m_start, m_end = find_module(text, start, end, header, must_contain)
        return text[:m_start] + text[m_end:]
    if op in ("set_slot", "remove_slot"):
        _, _, block, slot, button = change
        start, end = find_block(text, block)
        slot_line = re.compile(r"^[ \t]*%d[ \t]*=[ \t]*(\S+)[^\r\n]*\r?\n" % slot, re.M)
        hits = list(slot_line.finditer(text, start, end))
        if op == "set_slot":
            if hits:
                raise ChangeError("%s: slot %d is not empty" % (block, slot))
            newline = "\r\n" if "\r\n" in text[start:end] else "\n"
            last = list(re.finditer(r"^End\b", text[start:end], re.M | re.I))[-1]
            at = start + last.start()
            return text[:at] + "  %d = %s%s" % (slot, button, newline) + text[at:]
        if len(hits) != 1 or hits[0].group(1) != button:
            raise ChangeError("%s: slot %d does not hold %s" % (block, slot, button))
        return text[:hits[0].start()] + text[hits[0].end():]
    if op == "append":
        return text + change[2]
    raise ChangeError("unknown change " + op)


# ---------------------------------------------------------------------------
# Archive access and file output
# ---------------------------------------------------------------------------

def read_big(path):
    """Map lowercase archive path -> bytes for a .big archive."""
    with open(path, "rb") as f:
        data = f.read()
    if data[:4] not in (b"BIGF", b"BIG4"):
        raise SystemExit("%s is not a .big archive" % path)
    count = struct.unpack(">I", data[8:12])[0]
    files = {}
    p = 16
    for _ in range(count):
        offset, size = struct.unpack(">II", data[p:p + 8])
        name_end = data.index(b"\0", p + 8)
        name = data[p + 8:name_end].decode("latin-1").replace("\\", "/")
        files[name.lower()] = data[offset:offset + size]
        p = name_end + 1
    return files


def remove_overrides(game_dir):
    manifest = os.path.join(game_dir, MANIFEST)
    if not os.path.exists(manifest):
        print("No balance overrides installed.")
        return
    with open(manifest) as f:
        for rel in f.read().split():
            path = os.path.join(game_dir, rel)
            if os.path.exists(path):
                os.remove(path)
                print("removed", rel)
    os.remove(manifest)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--game-dir", default=os.environ.get("GENERALS_ZH_PATH", DEFAULT_GAME_DIR))
    parser.add_argument("--remove", action="store_true", help="delete the installed overrides")
    parser.add_argument("--dry-run", action="store_true", help="check the changes without writing")
    args = parser.parse_args()

    if args.remove:
        remove_overrides(args.game_dir)
        return

    archive = read_big(os.path.join(args.game_dir, "INIZH.big"))
    edited = {}
    try:
        for change in CHANGES:
            path = change[1]
            if path not in edited:
                if path.lower() not in archive:
                    raise ChangeError("%s is not in INIZH.big" % path)
                edited[path] = archive[path.lower()].decode("latin-1")
            edited[path] = apply_change(edited[path], change)
    except ChangeError as e:
        raise SystemExit("Balance change does not apply: %s" % e)

    print("%d changes apply to %d files." % (len(CHANGES), len(edited)))
    if args.dry_run:
        return

    remove_overrides(args.game_dir)
    for path, text in sorted(edited.items()):
        out = os.path.join(args.game_dir, path)
        os.makedirs(os.path.dirname(out), exist_ok=True)
        with open(out, "wb") as f:
            f.write(text.encode("latin-1"))
        print("wrote", path)
    with open(os.path.join(args.game_dir, MANIFEST), "w") as f:
        f.write("\n".join(sorted(edited)) + "\n")


if __name__ == "__main__":
    sys.exit(main())

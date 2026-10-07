"""Duels at equal cost, to balance the European faction: each European unit and its USA counterpart fight
the same enemies, headless and at full speed (GENERALS_DUEL in GameLogic.cpp), over several seeds. A
European unit is balanced when it does about as well as the USA's unit does against the same enemies.

    python3 scripts/factions/europe/duels.py [--seeds 4] [--jobs 6] [--only Euro_Leopard]

Score of a fight, from the first side's view: its value left minus the enemy's (each as a share of what
it started with), from -1 (wiped out, enemy untouched) to +1.
"""
import argparse
import os
import re
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
GAME = os.path.join(ROOT, "build", "macos", "GeneralsMD", "generalszh")
GAME_DIR = os.path.expanduser("~/Games/GeneralsZH")
BUDGET = 6000

COST = {
    "Euro_Rifleman": 250, "Euro_Milan": 325, "Euro_Boxer": 1000, "Euro_Leopard": 1000, "Euro_Leclerc": 1200,
    "Euro_Tiger": 1600,
    "AmericaInfantryRanger": 225, "AmericaInfantryMissileDefender": 300, "AmericaVehicleHumvee": 700,
    "AmericaTankCrusader": 900, "AmericaTankPaladin": 1100, "AmericaVehicleComanche": 1500,
    "ChinaInfantryRedguard": 300, "ChinaInfantryTankHunter": 300, "ChinaTankBattleMaster": 700,
    "ChinaTankOverlord": 2000, "ChinaTankGattling": 800,
    "GLAInfantryRebel": 150, "GLAInfantryTunnelDefender": 300, "GLAVehicleTechnical": 500, "GLATankScorpion": 550,
    "GLATankMarauder": 800, "GLAVehicleQuadCannon": 650,
}
SIDES = {"Euro": "FactionEurope", "America": "FactionAmerica", "China": "FactionChina", "GLA": "FactionGLA"}

# European unit, its USA counterpart, the enemies both meet.
MATCHUPS = [
    ("Euro_Rifleman", "AmericaInfantryRanger", ["GLAInfantryRebel", "ChinaInfantryRedguard", "AmericaInfantryRanger"]),
    ("Euro_Milan", "AmericaInfantryMissileDefender", ["ChinaTankBattleMaster", "GLATankScorpion", "AmericaTankCrusader"]),
    ("Euro_Boxer", "AmericaVehicleHumvee", ["GLAVehicleTechnical", "GLAVehicleQuadCannon", "ChinaInfantryRedguard",
                                            "ChinaTankBattleMaster", "AmericaVehicleHumvee"]),
    ("Euro_Leopard", "AmericaTankCrusader", ["ChinaTankBattleMaster", "GLATankScorpion", "GLATankMarauder",
                                            "AmericaTankCrusader"]),
    ("Euro_Leclerc", "AmericaTankPaladin", ["ChinaTankOverlord", "GLATankMarauder", "ChinaInfantryTankHunter",
                                           "GLAInfantryTunnelDefender"]),
    ("Euro_Tiger", "AmericaVehicleComanche", ["ChinaTankBattleMaster", "GLATankScorpion", "ChinaTankGattling"]),
]


def faction(unit):
    return SIDES[unit.split("_")[0] if unit.startswith("Euro_") else re.match(r"[A-Z][a-z]+|GLA", unit).group(0)]


def fight(a, b, seed, work):
    """One duel; the first side's score."""
    na, nb = max(1, round(BUDGET / COST[a])), max(1, round(BUDGET / COST[b]))
    fa, fb = faction(a), faction(b)
    battle = os.path.join(work, f"{a}-{b}-{seed}.txt")
    with open(battle, "w") as f:
        f.write(f"map Tournament Desert\ncash 0\nseed {seed}\nsuperweapons 0\nresult {battle}.json\n"
                f"player observer FactionAmerica -1 -1\nplayer easy {fa} 0 0\nplayer easy {fb} 1 1\n")
    env = dict(os.environ, GENERALS_DUEL=f"{a}:{na},{b}:{nb}", GENERALS_NO_MESSAGEBOX="1")
    # The game does not always leave after the duel: stop it once the result is out.
    game = subprocess.Popen(["nice", "-n", "10", GAME, "-headless", "-noaudio", "-noFPSLimit", "-gamespeed", "3000",
                             "-battle", battle], cwd=GAME_DIR, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    m = err = None
    timer = threading.Timer(300, game.kill)
    timer.start()
    try:
        for line in game.stderr:
            m = re.search(r"DUEL_RESULT (\d+) \S+ (\S+) (\d+) \S+ (\S+) (\S+)", line)
            err = err or re.search(r"DUEL_RESULT error.*", line)
            if m or err:
                break
    finally:
        timer.cancel()
        game.kill()
        game.wait()
    if not m:
        raise RuntimeError(f"{a} vs {b}: {err.group(0) if err else 'no result'}")
    return float(m.group(2)) - float(m.group(4))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=4)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--only")
    args = parser.parse_args()
    matchups = [m for m in MATCHUPS if not args.only or m[0] in args.only.split(",")]
    tasks = [(unit, enemy, seed) for eu, usa, enemies in matchups for unit in (eu, usa) for enemy in enemies
             for seed in range(1, args.seeds + 1)]
    with tempfile.TemporaryDirectory() as work, ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda t: fight(*t, work), tasks))
    scores = {}
    for (unit, enemy, _), score in zip(tasks, results):
        scores.setdefault((unit, enemy), []).append(score)
    print(f"{'european unit':16} {'enemy':30} {'europe':>7} {'usa':>7}  verdict")
    for eu, usa, enemies in matchups:
        for enemy in enemies:
            e = sum(scores[(eu, enemy)]) / args.seeds
            u = sum(scores[(usa, enemy)]) / args.seeds
            verdict = "ok" if abs(e - u) <= 0.25 else ("STRONG" if e > u else "WEAK")
            print(f"{eu:16} {enemy:30} {e:+7.2f} {u:+7.2f}  {verdict}")
    sys.stdout.flush()


if __name__ == "__main__":
    main()

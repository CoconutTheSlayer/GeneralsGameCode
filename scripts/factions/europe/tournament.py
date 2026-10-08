"""AI tournaments to balance the European faction: the hard European AI against the hard AIs of USA, China
and GLA on several maps and seeds, headless at full speed, with the USA's AI against the same opponents as
the baseline (the European AI plays with the USA's skirmish scripts). Europe is balanced when it wins
about as often as the USA does.

    python3 scripts/factions/europe/tournament.py [--seeds 3] [--jobs 6] [--minutes 30]

A game still open after --minutes of game time counts as a draw.
"""
import argparse
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
GAME = os.path.join(ROOT, "build", "macos", "GeneralsMD", "generalszh")
GAME_DIR = os.path.expanduser("~/Games/GeneralsZH")
MAPS = ["Tournament Desert", "Tournament Plains", "Flash Fire", "Scorched Earth"]
OPPONENTS = ["FactionAmerica", "FactionChina", "FactionGLA"]


def play(side, opponent, game_map, seed, minutes, work):
    """One game; 1 if side won, 0 if it lost, 0.5 for a draw."""
    name = f"{side}-{opponent}-{game_map.replace(' ', '')}-{seed}"
    battle, result = os.path.join(work, name + ".txt"), os.path.join(work, name + ".json")
    # Alternate who starts where.
    players = [(side, 0, 0), (opponent, 1, 1)]
    if seed % 2 == 0:
        players.reverse()
    with open(battle, "w") as f:
        f.write(f"map {game_map}\ncash 10000\nseed {seed}\nsuperweapons 0\nresult {result}\n"
                "player observer FactionAmerica -1 -1\n")
        f.writelines(f"player hard {fac} {team} {colour}\n" for fac, team, colour in players)
    env = dict(os.environ, GENERALS_PLAYER_LOG="60", GENERALS_NO_MESSAGEBOX="1")
    game = subprocess.Popen(["nice", "-n", "10", GAME, "-headless", "-noaudio", "-noFPSLimit", "-gamespeed", "3000",
                             "-battle", battle], cwd=GAME_DIR, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    # The log tells the game time; the result file appears without a log line, so look for it as well.
    seconds = [0]

    def read_log():
        for line in game.stderr:
            m = re.match(r"PLAYER_LOG (\d+)s", line)
            if m:
                seconds[0] = int(m.group(1))

    reader = threading.Thread(target=read_log, daemon=True)
    reader.start()
    started = time.time()
    try:
        while game.poll() is None and not os.path.exists(result) and seconds[0] < minutes * 60 \
                and time.time() - started < 1800:
            time.sleep(2)
    finally:
        game.kill()
        game.wait()
    if not os.path.exists(result):
        return 0.5
    with open(result) as f:
        data = json.load(f)
    for p in data["players"]:
        if p["faction"] == side and p["team"] == [t for fac, t, _ in players if fac == side][0]:
            return 1.0 if p["victorious"] else 0.0
    return 0.5


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--jobs", type=int, default=6)
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--opponents", default=",".join(OPPONENTS), help="comma separated factions")
    args = parser.parse_args()
    opponents = args.opponents.split(",")
    tasks = [(side, opp, m, seed) for opp in opponents for side in ("FactionEurope", "FactionAmerica")
             for m in MAPS for seed in range(1, args.seeds + 1)]
    with tempfile.TemporaryDirectory() as work, ThreadPoolExecutor(args.jobs) as pool:
        results = list(pool.map(lambda t: play(*t, args.minutes, work), tasks))
    table = {}
    for (side, opp, m, seed), r in zip(tasks, results):
        table.setdefault((side, opp), []).append(r)
        print(f"{side:16} vs {opp:16} {m:18} seed {seed}: {r}", flush=True)
    print()
    print(f"{'opponent':16} {'Europe wins':>12} {'USA wins':>9}")
    for opp in opponents:
        e, u = table[("FactionEurope", opp)], table[("FactionAmerica", opp)]
        print(f"{opp:16} {sum(e) / len(e):12.0%} {sum(u) / len(u):9.0%}")


if __name__ == "__main__":
    main()

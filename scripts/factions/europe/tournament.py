"""AI tournaments to balance the European faction: the hard European AI against the hard AIs of USA, China
and GLA on several maps and seeds, headless at full speed, with the USA's AI against the same opponents as
the baseline (the European AI plays with the USA's skirmish scripts). Europe is balanced when it wins
about as often as the USA does.

    python3 scripts/factions/europe/tournament.py [--seeds 3] [--jobs 3] [--minutes 30]
        [--game build/macos-ai] [--results games.jsonl] [--sides FactionEurope]
    python3 scripts/factions/europe/tournament.py --report games.jsonl

A game still open after --minutes of game time counts as a draw. --game names a build directory of the
engine; a build other than build/macos gets a private copy of the European data in its own
Resources/GameData (the game's data links to the shared one), written by build_europe.py with
EUROPE_AI_UPGRADES=1, so a build with newer engine features can be tested while others run build/macos.
--results appends one JSON line per game (result, length, when Europe researched the Green Deal, its
Funds Offices and Fusion Plants at the end), and --report sums such files up.
"""
import argparse
import importlib.util
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor

ROOT = os.path.normpath(os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", ".."))
GAME_DIR = os.path.expanduser("~/Games/GeneralsZH")
SHARED_DATA = os.path.join(ROOT, "resources", "macos", "GameData")
MAPS = ["Tournament Desert", "Tournament Plains", "Flash Fire", "Scorched Earth"]
OPPONENTS = ["FactionAmerica", "FactionChina", "FactionGLA"]
SIDES = ["FactionEurope", "FactionAmerica"]
lock = threading.Lock()


def private_data(build):
    """The build's own Resources/GameData: links to the shared data, the logic INI written here."""
    data = os.path.join(build, "Resources", "GameData")
    for path in ("Art", os.path.join("Data", "english"), os.path.join("Data", "INI", "Addon", "Client")):
        link = os.path.join(data, path)
        if not os.path.lexists(link):
            os.makedirs(os.path.dirname(link), exist_ok=True)
            os.symlink(os.path.join(SHARED_DATA, path), link)
    spec = importlib.util.spec_from_file_location("build_europe", os.path.join(os.path.dirname(__file__), "build_europe.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.DATA = os.path.join(build, "Resources", "GameData-gen")
    module.main()
    # Only the logic INI is our own; the client INI and the strings stay the shared ones.
    logic = os.path.join(data, "Data", "INI", "Addon", "Logic")
    os.makedirs(logic, exist_ok=True)
    os.replace(os.path.join(module.DATA, "Data", "INI", "Addon", "Logic", "Europe.ini"), os.path.join(logic, "Europe.ini"))


def play(game, side, opponent, game_map, seed, minutes, work):
    """One game: its result for side (1 won, 0 lost, 0.5 draw) and what the European player did."""
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
    env = dict(os.environ, GENERALS_PLAYER_LOG="20", GENERALS_NO_MESSAGEBOX="1")
    proc = subprocess.Popen(["nice", "-n", "19", game, "-headless", "-noaudio", "-noFPSLimit", "-gamespeed", "3000",
                             "-battle", battle], cwd=GAME_DIR, env=env, stdout=subprocess.DEVNULL,
                            stderr=subprocess.PIPE, text=True)
    # The log tells the game time; the result file appears without a log line, so look for it as well.
    state = {"seconds": 0, "green_deal": None, "funds": 0, "plants": 0}

    def read_log():
        for line in proc.stderr:
            m = re.match(r"PLAYER_LOG (\d+)s player \d+ FactionEurope .*buildings \d+:(.*)", line)
            if m:
                names = m.group(2).split()
                state["funds"], state["plants"] = names.count("Euro_FundsOffice"), names.count("Euro_PowerPlant")
            m = re.match(r"PLAYER_LOG (\d+)s", line)
            if m:
                state["seconds"] = int(m.group(1))
            m = re.match(r"PLAYER_UPGRADES (\d+)s player \d+ FactionEurope:.*Upgrade_EuroGreenDeal", line)
            if m and state["green_deal"] is None:
                state["green_deal"] = int(m.group(1))

    reader = threading.Thread(target=read_log, daemon=True)
    reader.start()
    started = time.time()
    try:
        while proc.poll() is None and not os.path.exists(result) and state["seconds"] < minutes * 60 \
                and time.time() - started < 1800:
            time.sleep(2)
    finally:
        proc.kill()
        proc.wait()
    score = 0.5
    if os.path.exists(result):
        with open(result) as f:
            data = json.load(f)
        team = [t for fac, t, _ in players if fac == side][0]
        for p in data["players"]:
            if p["faction"] == side and p["team"] == team:
                score = 1.0 if p["victorious"] else 0.0
    return dict(side=side, opponent=opponent, map=game_map, seed=seed, score=score, seconds=state["seconds"],
                green_deal=state["green_deal"], funds_offices=state["funds"], fusion_plants=state["plants"],
                wall=round(time.time() - started))


def report(games):
    # A game that never got going (the data failed to load: another agent was writing it) does not count.
    broken = [g for g in games if g["seconds"] < 60 and g["score"] == 0.5]
    if broken:
        print(f"{len(broken)} games did not start and are left out: rerun them")
    table = {}
    for g in games:
        if g in broken:
            continue
        table.setdefault((g["side"], g["opponent"]), []).append(g)
    print(f"{'opponent':16} {'Europe wins':>16} {'USA wins':>16} {'Green Deal':>14}")
    for opp in OPPONENTS:
        e, u = table.get(("FactionEurope", opp), []), table.get(("FactionAmerica", opp), [])
        if not e and not u:
            continue

        def rate(gs):
            return f"{sum(g['score'] for g in gs) / len(gs):5.0%} of {len(gs):3}" if gs else "-"
        deals = [g["green_deal"] for g in e if g.get("green_deal") is not None]
        deal = f"{len(deals)}/{len(e)} @{sum(deals) / len(deals) / 60:.1f}m" if deals else "-"
        print(f"{opp:16} {rate(e):>16} {rate(u):>16} {deal:>14}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seeds", type=int, default=3)
    parser.add_argument("--first-seed", type=int, default=1)
    parser.add_argument("--jobs", type=int, default=3)
    parser.add_argument("--minutes", type=int, default=30)
    parser.add_argument("--opponents", default=",".join(OPPONENTS), help="comma separated factions")
    parser.add_argument("--sides", default=",".join(SIDES), help="comma separated: FactionEurope, FactionAmerica")
    parser.add_argument("--maps", default=",".join(MAPS), help="comma separated maps")
    parser.add_argument("--game", default=os.path.join(ROOT, "build", "macos"), help="the engine's build directory")
    parser.add_argument("--results", help="append each game as a JSON line to this file")
    parser.add_argument("--report", nargs="*", help="only sum up these results files")
    args = parser.parse_args()
    if args.report:
        report([json.loads(line) for path in args.report for line in open(path) if line.strip()])
        return
    build = os.path.abspath(args.game)
    if build != os.path.join(ROOT, "build", "macos"):
        private_data(build)
    game = os.path.join(build, "GeneralsMD", "generalszh")
    tasks = [(side, opp, m, seed) for opp in args.opponents.split(",") for side in args.sides.split(",")
             for m in args.maps.split(",") for seed in range(args.first_seed, args.first_seed + args.seeds)]
    games = []

    def run(task):
        g = play(game, *task, args.minutes, work)
        with lock:
            games.append(g)
            print(json.dumps(g), flush=True)
            if args.results:
                with open(args.results, "a") as f:
                    f.write(json.dumps(g) + "\n")
        return g

    with tempfile.TemporaryDirectory() as work, ThreadPoolExecutor(args.jobs) as pool:
        list(pool.map(run, tasks))
    print()
    report(games)


if __name__ == "__main__":
    main()

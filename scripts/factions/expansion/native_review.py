"""Run isolated native faction checks without changing the live data or game process.

Examples: native_review.py russia production
          native_review.py russia lineup --units Russia_Tigr,Russia_T90
          native_review.py russia move --units Russia_Tigr
          native_review.py russia ai --seconds 600
"""
from pathlib import Path
import argparse
import json
import os
import re
import shutil
import subprocess
import time

ROOT = Path(__file__).resolve().parents[3]
SOURCE = ROOT / 'resources/macos/GameData'
OUT = ROOT / 'build/new-factions/native'


def prepare(folder, faction, all_factions=False):
    binary = folder / 'bin/generalszh'
    binary.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ROOT / 'build/macos/GeneralsMD/generalszh', binary)
    data = folder / 'Resources/GameData'
    shutil.copytree(SOURCE / 'Data', data / 'Data', dirs_exist_ok=True)
    if not all_factions:
        # Other agents may still be finishing their configuration. Prove that
        # each add-on works independently, then repeat with --all-factions.
        for other in ('Israel', 'Russia', 'Ukraine'):
            if other.lower() == faction:
                continue
            for stage in ('Logic', 'Client', 'AI'):
                for path in (data / 'Data/INI/Addon' / stage).glob(other + '*.ini'):
                    path.unlink()
            (data / 'Data/english/Addon' / (other + '.str')).unlink(missing_ok=True)
    (data / 'Art').symlink_to(SOURCE / 'Art', target_is_directory=True)
    return binary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('faction', choices=['israel', 'russia', 'ukraine', 'europe'])
    parser.add_argument('mode', choices=['production', 'lineup', 'move', 'ai', 'duel', 'power'])
    parser.add_argument('--units', default='')
    parser.add_argument('--opponent', default='FactionAmerica')
    parser.add_argument('--seconds', type=int, default=600)
    parser.add_argument('--height', type=int, default=210)
    parser.add_argument('--spacing', type=int, default=42)
    parser.add_argument('--distance', type=int, default=220)
    parser.add_argument('--all-factions', action='store_true')
    parser.add_argument('--capture-movement', action='store_true', help='Render the movement check for animation review instead of running headless.')
    parser.add_argument('--binary', type=Path, help='Test an existing packaged executable and its own bundled data (requires --all-factions).')
    parser.add_argument('--human-opponent', action='store_true')
    parser.add_argument('--hold-side', type=int, choices=[0, 1])
    parser.add_argument('--direct-attack', action='store_true', help='Issue direct target orders in duel checks, including unarmed structures.')
    parser.add_argument('--power')
    parser.add_argument('--source')
    parser.add_argument('--plant')
    args = parser.parse_args()
    if args.binary and (not args.all_factions or not args.binary.is_file()):
        parser.error('--binary requires an existing executable and --all-factions')
    definitions = '\n'.join(p.read_text(errors='replace') for p in (SOURCE / 'Data/INI/Addon/Logic').glob('*.ini'))
    names = set(re.findall(r'(?m)^(?:ChildObject|Object)\s+(\w+)', definitions))
    for entry in args.units.split(','):
        unit = entry.split(':')[0]
        if unit.startswith(('Israel_', 'Russia_', 'Ukraine_', 'Euro_')) and unit not in names:
            parser.error('Unknown requested unit: ' + unit)
    # Concurrent agents can observe the same clock tick on this host. Keep each
    # process's data, screenshots and log isolated even for the same faction.
    folder = OUT / args.faction / f'{args.mode}-{time.time_ns()}-{os.getpid()}'
    if args.binary:
        folder.mkdir(parents=True, exist_ok=True)
        binary = args.binary.resolve()
    else:
        binary = prepare(folder, args.faction, args.all_factions)
    side = 'Faction' + args.faction.title()
    battle = folder / 'battle.txt'
    result = folder / 'result.json'
    rows = [f'map Tournament Desert', 'cash 100000' if args.mode == 'production' else 'cash 10000',
            'seed 5', 'superweapons 0', f'result {result}']
    if args.mode == 'ai':
        rows += ['player observer FactionAmerica -1 -1', f'player hard {side} 0 0',
                 f'player hard {args.opponent} 1 2']
    else:
        human, enemy = (args.opponent, side) if args.human_opponent else (side, args.opponent)
        rows += [f'player human {human} 0 0', f'player easy {enemy} 1 2']
    battle.write_text('\n'.join(rows) + '\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GENERALS_', 'D3D8METAL_'))}
    env.update(GENERALS_NO_MESSAGEBOX='1', SDL_MAC_BACKGROUND_APP='1',
               SDL_WINDOW_ACTIVATE_WHEN_SHOWN='0', SDL_WINDOW_ACTIVATE_WHEN_RAISED='0')
    options = ['-headless', '-noaudio', '-noFPSLimit', '-gamespeed', '3000']
    expected = []
    if args.mode == 'production':
        spec = ROOT / 'build/new-factions' / args.faction / 'production.txt'
        env['GENERALS_PRODUCTION_SPEC'] = str(spec)
        for row in spec.read_text().splitlines():
            parts = row.split()
            if len(parts) == 2 and not row.startswith('#'):
                expected.extend(parts[1].split(','))
    elif args.mode == 'lineup':
        options = ['-noaudio', '-win', '-xres', '1440', '-yres', '900', '-gamespeed', '60']
        env.update(GENERALS_LINEUP=args.units, GENERALS_LINEUP_SPACING=str(args.spacing),
                   GENERALS_LOOKAT=f'0.5,0.5,{args.height}',
                   D3D8METAL_SCREENSHOT=str(folder / 'scene'), D3D8METAL_SCREENSHOT_EVERY='360')
    elif args.mode == 'move':
        env['GENERALS_PATH_TEST'] = args.units + ':6:0.45:0.45:0.55:0.55'
        if args.capture_movement:
            options = ['-noaudio', '-win', '-xres', '1440', '-yres', '900', '-gamespeed', '60']
            env.update(GENERALS_LOOKAT=f'0.5,0.5,{args.height}',
                       D3D8METAL_SCREENSHOT=str(folder/'scene'), D3D8METAL_SCREENSHOT_EVERY='180')
    elif args.mode == 'duel':
        env.update(GENERALS_DUEL=args.units, GENERALS_DUEL_DISTANCE=str(args.distance),
                   GENERALS_DUEL_SECONDS=str(args.seconds), GENERALS_APS_LOG='1', GENERALS_DRONE_LOG='1')
        if args.hold_side is not None:
            env['GENERALS_DUEL_HOLD_SIDE'] = str(args.hold_side)
        if args.direct_attack:
            env['GENERALS_DUEL_DIRECT_ATTACK'] = '1'
    elif args.mode == 'power':
        if not all((args.power, args.source, args.plant)):
            parser.error('power requires --power, --source and --plant')
        env.update(GENERALS_ROSTER_POWER=args.power, GENERALS_POWER_SOURCE=args.source,
                   GENERALS_POWER_PLANT=args.plant)
    else:
        env['GENERALS_PLAYER_LOG'] = '20'
    log = folder / 'native.log'
    started = time.monotonic()
    reached = False
    with log.open('w') as stream:
        process = subprocess.Popen([str(binary), *options, '-battle', str(battle)],
                                   cwd=Path.home() / 'Games/generalszh', env=env,
                                   stdout=stream, stderr=stream)
        try:
            while process.poll() is None and time.monotonic() - started < 240:
                text = log.read_text(errors='replace')
                if args.mode == 'lineup':
                    reached = len(list(folder.glob('scene_*.png'))) >= 3
                elif args.mode == 'move':
                    reached = 'PATH_TEST_DONE' in text
                elif args.mode == 'ai':
                    frames = re.findall(r'PLAYER_LOG (\d+)s', text)
                    reached = bool(frames and int(frames[-1]) >= args.seconds) or result.exists()
                else:
                    marker = {'production':'FACTION_PRODUCTION complete', 'duel':'DUEL_RESULT', 'power':'ROSTER_POWER complete'}[args.mode]
                    reached = marker in text
                if reached:
                    break
                time.sleep(.25)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    text = log.read_text(errors='replace')
    errors = []
    if re.search(r'CRASH|Error parsing|error in.*line|DUEL_RESULT error|FACTION_PRODUCTION FAILED|LINEUP unknown|ROSTER_POWER error', text, re.I):
        errors.append('Native game reported an error; inspect log.')
    if args.mode == 'production':
        if 'FACTION_PRODUCTION complete' not in text:
            errors.append('Production fixture did not finish.')
        for unit in expected:
            if not re.search(r'FACTION_PRODUCTION alive ' + re.escape(unit) + r' [1-9]', text):
                errors.append('Missing produced unit: ' + unit)
    elif args.mode == 'move':
        if 'arrived 6/6' not in text or 'failed 0' not in text:
            errors.append('Movement fixture did not deliver all six units.')
    elif args.mode == 'lineup' and not list(folder.glob('scene_*.png')):
        errors.append('No native screenshots captured.')
    elif args.mode == 'duel' and 'DUEL_RESULT' not in text:
        errors.append('Duel did not finish.')
    elif args.mode == 'power':
        if 'ROSTER_POWER complete' not in text or 'ROSTER_POWER fired' not in text:
            errors.append('Power fixture did not finish.')
        health = [float(n) for n in re.findall(r'ROSTER_POWER target \d+ health ([\d.]+)', text)]
        if not health or min(health) >= 800:
            errors.append('Offensive power did not damage any target.')
    elif args.mode == 'ai' and not reached:
        errors.append('AI run ended before the requested duration.')
    report = dict(faction=args.faction, mode=args.mode, all_factions=args.all_factions, status='failed' if errors else 'passed',
                  binary=str(binary),
                  seconds=round(time.monotonic()-started, 1), log=str(log), errors=errors,
                  images=[str(p) for p in sorted(folder.glob('scene_*.png'))],
                  events=[line for line in text.splitlines() if line.startswith(
                      ('FACTION_PRODUCTION', 'PATH_TEST_DONE', 'DUEL', 'PLAYER_LOG', 'APS_INTERCEPT', 'DRONE_DAMAGE', 'ROSTER_POWER'))])
    (folder / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    latest = OUT / args.faction / (args.mode + '-latest.json')
    latest.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())

"""Verify smoke, field recovery, paid mines, counterbattery and target vision in the native game.

The opt-in GameLogic fixture uses the real faction objects and running update modules.
Every invocation creates an isolated data copy and leaves the user's running game alone.
"""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import time
from native_review import ROOT, prepare


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--binary', type=Path, help='Use an existing packaged executable and its bundled data.')
    args = parser.parse_args()
    folder = ROOT / 'build/new-factions/mechanics' / str(time.time_ns())
    if args.binary:
        if not args.binary.is_file():
            parser.error('The requested executable does not exist.')
        folder.mkdir(parents=True)
        binary = args.binary.resolve()
    else:
        binary = prepare(folder, 'europe', all_factions=True)
    battle = folder / 'battle.txt'
    battle.write_text(f'map Tournament Desert\ncash 0\nseed 5\nsuperweapons 0\nresult {folder}/result.json\n'
                      'player human FactionEurope 0 0\nplayer easy FactionRussia 1 2\n')
    env = {k: v for k, v in os.environ.items() if not k.startswith(('GENERALS_', 'D3D8METAL_'))}
    env.update(GENERALS_NO_MESSAGEBOX='1', GENERALS_ROSTER_MECHANICS_TEST='1',
               GENERALS_COUNTERBATTERY_LOG='1', SDL_MAC_BACKGROUND_APP='1',
               SDL_WINDOW_ACTIVATE_WHEN_SHOWN='0', SDL_WINDOW_ACTIVATE_WHEN_RAISED='0')
    log = folder / 'native.log'
    started = time.monotonic()
    with log.open('w') as stream:
        process = subprocess.Popen([str(binary), '-headless', '-noaudio', '-noFPSLimit',
                                    '-gamespeed', '3000', '-battle', str(battle)],
                                   cwd=Path.home() / 'Games/generalszh', env=env, stdout=stream, stderr=stream)
        try:
            process.wait(timeout=180)
        except subprocess.TimeoutExpired:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    text = log.read_text(errors='replace')
    assertions = re.findall(r'^ROSTER_MECHANICS (PASS|FAIL) (\w+) frame=(\d+)$', text, re.M)
    result = re.search(r'ROSTER_MECHANICS RESULT assertions=(\d+) failed=(\d+)', text)
    errors = [label for status, label, frame in assertions if status == 'FAIL']
    if not result:
        errors.append('Native regression did not finish.')
    elif int(result[1]) != len(assertions) or int(result[2]) != len(errors):
        errors.append('Native assertion accounting mismatch.')
    if re.search(r'CRASH|Error parsing|error in.*line', text, re.I):
        errors.append('Native game error; inspect the log.')
    required = ['smoke_direct_fire_range_75_percent', 'smoke_range_restored_after_expiry',
                'recovery_multiple_healers_do_not_stack', 'recovery_new_damage_restarts_cooldown',
                'mine_rejection_no_cost_spawn_or_cooldown', 'mine_arms_after_three_seconds',
                'mine_arming_delay_and_destroyed_mine_cancelled',
                'counterbattery_detects_after_cooldown', 'counterbattery_contact_deleted_after_four_seconds',
                'counterbattery_contact_vision_expires_after_fog_fade',
                'pereh_fires_when_target_currently_visible', 'pereh_lost_vision_launch_rejected_without_ammo_cost']
    for label in required:
        if not any(status == 'PASS' and name == label for status, name, _ in assertions):
            errors.append('Missing passing behavior: ' + label)
    report = dict(status='failed' if errors else 'passed', binary=str(binary), log=str(log),
                  elapsed_seconds=round(time.monotonic() - started, 1), errors=errors,
                  assertions=[dict(status=status.lower(), name=label, frame=int(frame))
                              for status, label, frame in assertions],
                  events=[line for line in text.splitlines() if line.startswith(('ROSTER_MECHANICS', 'COUNTERBATTERY'))])
    (folder / 'validation.json').write_text(json.dumps(report, indent=2) + '\n')
    (folder.parent / 'latest.json').write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())

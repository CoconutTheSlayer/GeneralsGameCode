"""Render authored infantry walking to a destination, then verify the idle pose stops.

The isolated game uses the existing path fixture and original art. A stationary
camera observes one soldier after PATH_TEST_DONE; differing pixels in the scene
centre reveal a run loop left playing after the unit has stopped. --expect-motion
is useful for reproducing the old missing-idle-clip bug before applying a fix.
"""
from pathlib import Path
import argparse
import json
import os
import re
import subprocess
import time

from PIL import Image, ImageChops
from native_review import ROOT, prepare


ROSTERS = {'israel': ['Rifleman', 'Spike', 'Commando'],
           'russia': ['Rifleman', 'Kornet', 'Commando'],
           'ukraine': ['Rifleman', 'Stugna', 'MANPADS', 'Commando']}


def run(unit, expect_motion, folder, faction='israel'):
    folder.mkdir(parents=True)
    side = faction.title()
    binary = prepare(folder, faction, all_factions=True)
    stealth_disabled = False
    if unit == 'Commando':
        # Friendly stealth pulses the whole model's opacity even when its pose
        # is stationary. Disable only that effect in this isolated data copy.
        ini = folder / f'Resources/GameData/Data/INI/Addon/Logic/{side}.ini'
        text = ini.read_text()
        header = f'ChildObject {side}_Commando AmericaInfantryColonelBurton\n'
        if text.count(header) == 1:
            start = text.index(header)
            end = text.find('\nChildObject ', start + len(header))
            if end == -1:
                end = len(text)
            block = text[start:end]
            # The observer replaces Burton's stealth module with stationary-only
            # camouflage. Remove that replacement as a whole in the visual fixture.
            block, replaced = re.subn(
                r'(?ms)^  ReplaceModule ModuleTag_07\n    Behavior = StealthUpdate[^\n]*\n.*?^  End\n',
                '  RemoveModule ModuleTag_07\n', block)
            if not replaced and 'RemoveModule ModuleTag_07' not in block:
                block = block.replace(header, header + '  RemoveModule ModuleTag_07\n', 1)
            ini.write_text(text[:start] + block + text[end:])
            stealth_disabled = True
    battle = folder / 'battle.txt'
    battle.write_text('map Tournament Desert\ncash 10000\nseed 5\nsuperweapons 0\n'
                      f'result {folder}/result.json\nplayer human Faction{side} 0 0\n'
                      'player easy FactionAmerica 1 2\n')
    env = {k:v for k,v in os.environ.items() if not k.startswith(('GENERALS_', 'D3D8METAL_'))}
    env.update(GENERALS_NO_MESSAGEBOX='1', SDL_MAC_BACKGROUND_APP='1',
               SDL_WINDOW_ACTIVATE_WHEN_SHOWN='0', SDL_WINDOW_ACTIVATE_WHEN_RAISED='0',
               GENERALS_PATH_TEST=f'{side}_{unit}:1:0.5:0.5:0.5:0.5',
               GENERALS_LOOKAT='0.5,0.5,105', D3D8METAL_SCREENSHOT=str(folder/'scene'),
               D3D8METAL_SCREENSHOT_EVERY='41')
    # The path fixture offsets its spawn grid by (-80,-80), so even with equal
    # map fractions the soldier walks to the camera target before coming to rest.
    log = folder / 'native.log'
    before_idle = None
    settled = []
    started = time.monotonic()
    with log.open('w') as output:
        process = subprocess.Popen([str(binary), '-win', '-noaudio', '-xres', '1440',
                                    '-yres', '900', '-gamespeed', '60', '-battle', str(battle)],
                                   cwd=Path.home()/'Games/generalszh', env=env,
                                   stdout=output, stderr=output)
        try:
            while process.poll() is None and time.monotonic()-started < 60:
                text = log.read_text(errors='replace')
                if 'PATH_TEST_DONE' in text:
                    frames = set(folder.glob('scene_*.png'))
                    if before_idle is None:
                        before_idle = frames
                    settled = sorted(frames-before_idle, key=lambda p:int(p.stem.split('_')[-1]))
                    if len(settled) >= 9:
                        break
                time.sleep(.1)
        finally:
            if process.poll() is None:
                process.terminate()
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()
    text = log.read_text(errors='replace')
    errors = []
    if not re.search(r'PATH_TEST_DONE .*arrived 1/1 .*failed 0', text):
        errors.append('The soldier did not complete the movement fixture.')
    if re.search(r'CRASH|Error parsing|error in.*line|PATH_TEST.*unknown', text, re.I):
        errors.append('Native game error; inspect the log.')
    # Discard early settling frames and compare several different points in the
    # former walk cycle. Exclude HUD, clock, cursor and distant map activity.
    samples = settled[3:8]
    roi = (500, 180, 940, 580)
    changed_pixels = []
    if len(samples) != 5:
        errors.append('Insufficient screenshots after arrival.')
    else:
        images = [Image.open(p).convert('RGB').crop(roi) for p in samples]
        for current in images[1:]:
            diff = ImageChops.difference(images[0], current)
            changed_pixels.append(sum(max(pixel)>8 for pixel in diff.getdata()))
        moving = max(changed_pixels) > 20
        if moving != expect_motion:
            errors.append('Idle pose still animates.' if moving else 'Old idle-animation bug did not reproduce.')
    report = dict(unit=side+'_'+unit, status='failed' if errors else 'passed',
                  expected='motion' if expect_motion else 'stationary pose', roi=roi,
                  stealth_disabled_in_fixture=stealth_disabled,
                  changed_pixels=changed_pixels, screenshots=[str(p) for p in samples],
                  errors=errors, log=str(log))
    (folder/'validation.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report), flush=True)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--faction', choices=list(ROSTERS), default='israel')
    parser.add_argument('--units', nargs='+')
    parser.add_argument('--expect-motion', action='store_true')
    args = parser.parse_args()
    units = args.units or ROSTERS[args.faction]
    if any(unit not in ROSTERS[args.faction] for unit in units):
        parser.error('Units must belong to the selected faction: ' + ', '.join(ROSTERS[args.faction]))
    base = ROOT/'build/new-factions/infantry-idle'
    if args.faction != 'israel':
        base /= args.faction
    folder = base/str(time.time_ns())
    reports = [run(unit,args.expect_motion,folder/unit.lower(),args.faction) for unit in units]
    report = dict(status='passed' if all(r['status']=='passed' for r in reports) else 'failed',
                  reports=reports)
    (folder/'validation.json').write_text(json.dumps(report,indent=2)+'\n')
    latest = folder.parent/('baseline.json' if args.expect_motion else 'latest.json')
    latest.write_text(json.dumps(report,indent=2)+'\n')
    return report['status'] != 'passed'


if __name__ == '__main__':
    raise SystemExit(main())

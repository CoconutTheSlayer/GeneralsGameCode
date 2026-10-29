# Ukraine faction: dispersed reconnaissance and artillery

Rebuild the faction with `python3 scripts/factions/ukraine/build_faction.py`. Only Ukraine-owned add-on INIs, strings, portraits and native production fixtures are emitted. The implementation reuses original Ukrainian art and authored infantry animations; stock parent objects provide gameplay behaviors, not visible models.

Use `--skip-portraits` for gameplay-only changes. The identity refinement preserves every existing model and texture, with no additional units or manual mode switches.

## Selectable roster

| Producer | Units |
| --- | --- |
| Command centre | Engineering vehicle |
| Supply centre | Supply truck |
| Barracks | Territorial infantry, Stugna team, MANPADS team, Sapper |
| War factory | BTR-4, Buk, Bohdana, Drone Controller |
| Drone workshop | TB2 reconnaissance UAV |

There are eleven selectable units and eleven structures. Oplot, Kozak, F-16 and Mi-24 source art remains archived in the model manifest but is absent from production menus, AI substitutions and support payloads. No buildable main battle tank or armed manned aircraft remains.

Territorial infantry is cheap screening infantry. Stugna teams engage ground targets only and automatically deploy for 1.2 seconds before firing, then pack in 0.5 seconds when ordered to move. MANPADS provides affordable short-range air defence and cannot attack ground targets. Sappers carry a normal short-range carbine, detect hidden threats and plant timed demolition charges. Their mine ability costs $100, deploys at their current position, arms after three seconds and recharges in ten seconds. Mines do not regenerate. Damage can destroy the visible arming device before activation.

The BTR-4 is a lightly protected four-seat autocannon carrier; passengers must dismount to fight. Buk is a prepared long-range AA battery: automatic 1.2-second setup, two 90-damage missiles separated by 0.3 seconds, then a 5.5-second reload. Range is 350; packing takes 0.7 seconds. Ammunition pips expose its reload window, and it cannot attack ground targets. Immediate short-range MANPADS coverage protects the battery during relocation and reloading. Its cost, 260 health and movement speed remain unchanged, so a flank can punish a badly positioned battery.

Bohdana is the relocation specialist: speed 50, 0.8-second automatic setup and 0.5-second packing. Its range is 335 with an 80-unit minimum range. A shell deals 70 primary damage within radius 12, plus 10 secondary damage within radius 18; its scatter radius is 10, increased to 15 against infantry. Five-second reloads, visible ammunition and 190 health expose clear attack windows. It gives up precision, range and damage compared with DANA, and heavy siege damage compared with Msta. No return to base is required. Conventional shells remain useful when anti-air counters attack drones.

A Drone Controller automatically launches a visible original UAFPV projectile using ordinary attack commands: 300 range, 60 minimum range, one launch per 12 seconds, 145 direct damage, 20 drone health and ten-second maximum lifetime. Normal anti-air and missile interception can shoot it down. The controller cannot gain veterancy and has no permanent subordinate units or stockpiling behavior. Workshop Drone Kits improves replacement to nine seconds without adding payload capacity. The shared engine makes airborne `DRONE PROJECTILE` objects ordinary anti-air targets.

The compact Drone Workshop uses existing original shed, bench, catapult, dish and UAV parts. It has no runway or parking-space dependency. Its unarmed TB2 scout stays airborne without ammunition trips home. It has wide normal vision and low durability. Sensor Optics unlocks a local eight-second hidden-unit detection sweep with a 45-second cooldown; it never grants permanent enemy vision.

## Upgrades and support

Capture Training and the per-plant turbine upgrade retain familiar controls. The technology centre instead researches Workshop Drone Kits, Field Concealment and Sensor Optics. Concealment hides territorial infantry, Stugna teams, sappers and drone controllers only after 3.5 seconds stationary without attacking, using abilities or taking damage. Normal detectors reveal them. Movement always breaks concealment.

The command centre offers temporary reconnaissance, two fragile unarmed BTR decoys lasting 35 seconds, and a limited conventional drone raid. Raid rank one brings one carrier, rank two brings two. Each carrier releases six interceptable drones. The late-game Drone Command Complex replaces the particle beam with four carriers after a public five-minute countdown. Both carriers and payloads are normal vulnerable airborne objects; they expire or leave the map after the strike. Target markings provide warning. All models are the existing original TB2 and UAFPV assets.

Costs, cooldowns and damage are a first playtest baseline, not a competitive-balance claim. Intended weaknesses are direct tank assaults, flame weapons, fast flanks and layered anti-air. Existing sound and transient combat effects are reused.

## Source and verification

- `build_faction.py`: roster, production menus, AI substitutions, weapon and movement roles.
- `support.py`: finite support flights, decoys, detection pulses and mines.
- `scripts/models/ukraine/`: original asset generator, editable rig/material sources and illustrated portraits. The new MANPADS reuses the original infantry rig with a narrower missile tube; the sapper reuses the rifle body with helmet, mine pouch and tools.
- `build/new-factions/ukraine/production.txt`: all eleven units produced through the native fixture.
- `python3 scripts/models/ukraine/review.py`: geometry, material, hierarchy and neutral-idle checks, including archived assets.
- `python3 scripts/factions/expansion/native_review.py ukraine production --all-factions`: complete native production.
- `python3 scripts/factions/expansion/check_infantry_idle.py --faction ukraine`: authored movement followed by stationary-pose checks for all four infantry.

Gameplay infantry Scale=1.5 and the existing global original-game scale are retained. The mine's `MoneyCost` is the shared engine's opt-in OCL special-power resource cost; old engine binaries cannot parse this field.

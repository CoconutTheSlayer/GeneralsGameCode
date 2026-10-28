# European battlegroup

The playable faction has **11 units** and **11 buildings**. All prior meshes and
icons are retained; this redesign changes roles, menus, AI substitutions and
support powers without replacing the existing original artwork.

| Production | Units |
|---|---|
| Command Centre / Logistics Centre | Armoured Engineer, NH90 |
| Garrison | Legionnaire, MILAN Team, Sako Marksman |
| Armour Works | Leopard 2, Vilkas IFV, Skyranger 30, DANA, Valuk Recovery |
| Air Base | Typhoon Interceptor |

Wiesel, GROM, Rafale and Tiger join the archived prototypes. They cannot be
produced or requested by faction AI and never arrive in reinforcement payloads.
Country coverage remains 31 contingents, recorded in `coalition_countries.json`;
Polish marksmen, Spanish Typhoon crews, Hungarian fire-control electronics and
Cypriot Skyranger crews preserve the contributions of retired standalone units.
These are fictional coalition assignments, not claims about real procurement.
Existing stock voice cues remain; no new accent recordings are included.

## Distinct roles

- Leopard: range 175, 70 damage, 2.3-second cycle, $1250. Fire-control research
  increases its range by 10%. Flanking and attrition punish its cost.
- Vilkas: short-range detector and five-seat autocannon transport. No anti-tank
  missile upgrade, no firing passengers. Infantry must dismount to fight.
- Skyranger: rapid gun AA at range 240 and weak anti-infantry fire at range 170;
  no point-defence lasers. It escorts the ground army while Typhoons cover
  distant aircraft. AHEAD improves both gun weapons by 25%.
- DANA: range 340, minimum range 75, 1.2-second automatic pre-attack setup,
  narrow splash, 3.4-second firing cycle. Fire-control research adds 10% range.
- Valuk: repairs nearby ground vehicles at 7 health/second, radius 110, only
  after each recipient has avoided damage for eight seconds. Healing does not
  stack between carriers, excludes aircraft, and does not heal infantry or self.
  Recovery kits add 150 health to the carrier; they do not amplify the aura.
- MILAN: $325, range 225, steady 44-damage missiles every 1.1 seconds. Ground
  targets only; the inherited USA laser lock, secondary weapon and command-button
  hunting modules are removed. Normal attack orders require no targeting mode.
- Sako: visible precision infantry escort, $500, range 240, 40 sniper damage
  every 1.2 seconds, 120 health. Its quicker, weaker shots need multiple hits
  against ordinary riflemen. It cannot harm armoured vehicles or structures.
  Stationary/garrison stealth, hidden acquisition and stealth detection are
  removed; normal retaliation is restored. It still requires Joint Command.
- Legionnaire: $250, 180 health, range 110, 6 rifle damage. The USA Ranger costs
  $225 with the same health, range 100 and 5 rifle damage, so the European rifle
  advantage now carries a premium. MINIMI research and assault grenades remain.
- Typhoon attacks only airborne targets. Existing infantry art, scale and idle
  animation stay unchanged throughout this refinement.

Joint Command researches fire control, smoke coordination and recovery kits;
the inherited USA battle-plan controls and broad technology menu are removed.
The Funds Office remains a conventional late-game income structure. Power
plants no longer generate subsidy income.

## Support powers

Smoke Coordination unlocks a Command Centre target-area ability with a shared
120-second cooldown. The smoke field lasts eight seconds, affecting allied
infantry and ground vehicles within 90 units. The shared `SMOKE_SCREEN` engine
condition shortens enemy direct-fire range against screened troops by 25%.
It does not confer stealth or immunity; artillery, aircraft, close-range attacks
and AA retain their normal behaviour. Auras do not multiply the effect.

Coalition Strike Command reuses the former uplink building with a six-minute
public timer. Five interceptable Gripen aircraft attack a visibly marked target
using conventional missiles. The particle beam update is removed. Zuzana
barrages, Gripen support sorties, familiar-unit reinforcements and field repairs
continue to supply coalition support.

## Rebuild and validation

```sh
python3 scripts/factions/europe/build_europe.py
python3 scripts/factions/europe/validate_roster.py
python3 scripts/factions/expansion/native_review.py europe production
python3 scripts/factions/expansion/native_review.py europe power --power Euro_CoalitionStrike --source Euro_ParticleCannonUplink --plant Euro_PowerPlant
```

`battlegroup_roster.py` applies after the historical coalition/curation tables.
The production fixture is `build/new-factions/europe/production.txt`.
The engine must include the opt-in `AutoHealBehavior.DamageCooldown` and
`SMOKE_SCREEN` support before running this data.

These numbers are a first playtest baseline. Native role and production checks
verify functioning mechanics, not competitive parity across maps and skill levels.

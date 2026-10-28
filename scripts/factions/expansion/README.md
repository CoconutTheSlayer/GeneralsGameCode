# Four distinct expansion factions

The redesigned production rosters contain 11 units each for Europe, Israel and
Ukraine, and 12 for Russia, including builders and collectors. Each faction keeps
11 structures. Existing original models, rigs, textures and illustrated portraits
are reused; retired units remain as hidden definitions for existing maps and art
work, but are removed from production menus and AI substitutions.

| Faction | Main play pattern | Factory roster |
| --- | --- | --- |
| Europe | Deliberate combined arms, accurate mobile siege, temporary smoke and recovery after disengaging | Leopard, Vilkas, Skyranger, DANA, Valuk |
| Israel | Expensive protected assaults, heavy infantry transport and precision fire supported by scouting | SandCat, Merkava, Namer, SPYDER, Pereh |
| Russia | Affordable slow armour, dedicated assault support, heavy siege and vulnerable salvo reloads | Tigr, T-90, BMPT, Tunguska, Msta, TOS |
| Ukraine | Light mobile forces, separate anti-tank/anti-air infantry, mines, scouting and interceptable drones | BTR-4, Buk, Bohdana, Drone Controller |

Europe fields the air-only Typhoon; Israel has the ground-strike F-16I; Russia
has the slow Su-25 attack aircraft; Ukraine has an unarmed persistent TB2 scout
from a compact Drone Workshop. EU Sako, Israeli Forward Observer, Russian Assault
Engineer and Ukrainian Sapper have different roles. None is a renamed common
stealth commando. Ground units operate and reload in the field, without a new
return-to-base refit loop or population cap.

The October 2026 identity refinement preserves every model and portrait while
separating the remaining shared roles:

- MILAN now uses automatic ground-only support fire without USA laser lock.
  Sako is a visible marksman escort with faster, weaker shots and no concealed
  sniper or detection ability. Legionnaire pricing reflects its stronger rifle.
- Israeli assault infantry has 210 health and short-range bursts. Namer costs
  1,000 and unloads faster; its six passengers still dismount to fight. Spike
  fires without deployment, while SPYDER provides steady missile fire at escort
  range with no long salvo pause.
- Kornet trades a heavy individual hit for a long reload. BMPT is an autocannon
  escort; garrison clearing belongs to the close-range Assault Engineer.
  Tunguska concentrates on anti-air missile bursts with a weak self-defence gun.
- Buk automatically deploys for a heavy two-missile salvo and then exposes a
  long reload window. MANPADS provides immediate short-range coverage. Bohdana
  retains quick setup, packing and road speed, with lighter and less accurate
  shells than DANA; Msta remains the heavier, slower siege option.

Builders, collectors and income buildings retain their existing simple controls.
These are initial tuning values; isolated combat checks and AI games establish
working roles, not competitive matchup parity.

Europe's beam superweapon is replaced by an interceptable coalition air strike.
Ukraine's former Svitlo building launches a finite drone raid. Israel retains a
conventional missile strike and Russia retains its nuclear missile. These are
fictional RTS roles and balance values, not real-world capability claims.

## Shared mechanic contracts

- `AutoHealBehavior.DamageCooldown` defaults to zero. Valuk sets it to eight
  seconds per damaged recipient. Existing sole-benefactor healing prevents
  multiple recovery vehicles from multiplying the rate.
- `SMOKE_SCREEN` is a temporary nonstacking weapon condition. Enemy ground
  direct-fire range against the screened object is 75% of normal. Aircraft,
  indirect fire and air targets retain normal range. Movement-to-fire calculations
  use the same range, so attackers can close the distance. Smoke is not stealth.
- `Weapon.RequiresTargetVision` defaults to No. Pereh requires current target
  visibility to launch, including the stock five-second fog persistence after a
  scout leaves; blind ground fire cannot bypass the requirement. Missiles
  already launched still resolve normally after vision is lost.
- Counter-battery fields on `StealthDetectorUpdate` default to disabled. Tigr
  notices recent shots from ground indirect weapons (range at least 200 and dead
  zone at least 40), once per 12 seconds. A quantized location is revealed by a
  four-second contact object, followed by the stock five-second fog persistence.
  The contact stays at the firing location; there is no permanent target tracking.
- `OCLSpecialPower.MoneyCost` defaults to zero. Ukrainian mine placement costs
  100, checks affordability before starting cooldown, and rejects repeated orders
  while recharging. A visible arming object takes three seconds to become one
  mine; destroying it early cancels placement.

All new engine behavior is opt-in. Stock USA, GLA and China definitions remain
unchanged. New faction powers and upgrades use existing production controls.

## Source and rebuilding

Original editable art, generators and model contracts live in
`scripts/models/israel`, `scripts/models/russia` and `scripts/models/ukraine`.
Exported W3D models, texture variants, portraits, INIs and strings are under
`resources/macos/GameData`. Visible unit and building meshes are original;
installed Zero Hour behaviors, effects, sounds and some animation data are reused.

Israel's second art pass adds layered armour, protection sensors, visible crew
equipment, weapon fittings and reinforced base detail in `polish_geometry.py`.
`polished_bake.py` bakes the original material atlas, contact shadows and material
separation into the diffuse maps. Healthy and damaged image-generation source
artwork and prompts are stored with the model generator. Gameplay bones and
production exits stay fixed through the geometry pass.

Israel infantry now use `infantry_v2.py`: narrower human proportions, fitted
headgear, a dedicated clothing/face atlas, and separate knee and ankle animation
channels. The explicit `_I` standing clips reset the walk/fire animation on idle;
an empty idle animation list leaves W3D playing the previous clip.
`aircraft_v2.py` authors distinct F-16I and F-15I hulls with smooth
aircraft paint, camouflage, intakes and exhausts. The helicopter also uses the
aircraft material atlas. Source image-generation prompts are next to these
atlases and in `scripts/models/israel/portraits` for the three infantry portraits.
All 25 build-menu portraits now come from the illustrated PNG originals in
`scripts/models/israel/portraits`. The 22 vehicle, aircraft and building portraits
share the infantry's close framing, warm light and smoky blue-gray backgrounds.
Their prompts and source image paths are in `illustrated-prompts.json` and
`illustrated-sources.json`. The emitter requires every portrait and never falls
back to model renders. `render_icons.py` remains an optional geometry review tool.

Russia and Ukraine use the same illustrated portrait workflow, including retained
portraits for retired units and new portraits for redesigned roles. Their original PNGs, prompts and image-generation provenance
live under each faction's `portraits/` directory. The shared
`illustrated_portraits.py` exporter writes 128px build-menu textures, 256px HD
portraits and a labelled `build/faction-assets/<faction>/icons-review.png` sheet.
The faction emitters require the complete set, so rebuilding models cannot
silently restore the old model-render icons.

Both factions' infantry and aircraft have a second original-geometry pass:
shaped faces, clothing and equipment, clearer aircraft silhouettes, cockpit
frames, intakes, exhausts and weapon fittings. Russia uses original articulated
`_I`, `_R`, `_F`, `_X` infantry clips; Ukraine keeps its original hierarchy and
`_I`, `_W`, `_F`, `_DIE` clips. Explicit neutral clips reset moving joints on idle.
Russian vehicles use a new olive material atlas; Ukrainian vehicles and buildings
use tinted copies of the project's original material artwork with baked contact
shading. Russia's `ground_building_detail.py` and Ukraine's `polish_ground.py`
add armour sections, cab fittings, optics, running-gear detail and building service
equipment within the established model bounds. Each model directory documents
its rebuild commands and material sources.
The restored original game scaling and explicit infantry idle clips are preserved.
The roster redesign changes costs, weapons and roles separately from the art.

To rebuild the complete Israel art pass (Blender must be installed):

```sh
python3 scripts/models/israel/paint.py
/Applications/Blender.app/Contents/MacOS/Blender -b -t 3 -P scripts/models/israel/build.py
python3 scripts/models/israel/compact_wheels.py
python3 scripts/models/israel/validate.py
python3 scripts/factions/israel/build_faction.py
```

The build accepts individual model IDs after `--` for incremental work. When
running separate batches, wait for every batch to finish, then run the builder
with a bare `--` to assemble the complete manifest before validation. Editable
Blender scenes, renders and review sheets are saved in `build/faction-assets/israel`.
Keep `AtlasUV` as the source projection and `PaintUV` as the exported bake; broad
armour components use their full material patch to avoid stretched source pixels.

`personality.json` defines the seven factions' exaggerated military personas,
silhouette guidance and short candidate unit lines. The new faction selection
descriptions express these identities; the voice examples are unrecorded.

Rebuild faction definitions and portraits after changing a roster or art manifest:

```sh
python3 scripts/factions/israel/build_faction.py
python3 scripts/factions/russia/build_faction.py
python3 scripts/factions/ukraine/build_faction.py
python3 scripts/factions/expansion/validate_assets.py
cmake --build build/macos --target generalszh -j 3
scripts/macos/make-app.sh "$PWD/build/new-factions/package-input" "$PWD/build/macos"
```

The emitters require the user's installed Zero Hour archives, read through
`scripts/factions/europe/stock_data.py`. Rebuilding an emitter writes only its own
add-on definitions, localization and portraits. It does not regenerate Europe or
the 3D art. See each art generator for Blender usage.

The native executable finds this checkout's additional game data automatically;
the macOS packaging script copies it into the application bundle. Select Israel,
Russia or Ukraine in Skirmish. Stock voice lines are temporary fallbacks.

## Native validation

These checks use private copies of the executable and faction definitions,
without replacing the live installation or terminating an existing user game.
Screenshots, logs and JSON results go to `build/new-factions/native`.

```sh
python3 scripts/factions/expansion/native_review.py israel production --all-factions
python3 scripts/factions/expansion/native_review.py russia production --all-factions
python3 scripts/factions/expansion/native_review.py ukraine production --all-factions
python3 scripts/factions/expansion/native_review.py russia ai --seconds 600 --all-factions
python3 scripts/factions/expansion/check_roster_mechanics.py
python3 scripts/factions/expansion/check_personal_aps.py
python3 scripts/factions/expansion/check_drone_counterplay.py
python3 scripts/factions/expansion/check_infantry_idle.py
python3 scripts/factions/expansion/check_infantry_idle.py --faction russia
python3 scripts/factions/expansion/check_infantry_idle.py --faction ukraine
```

`production` constructs the producers and prerequisites, then actually queues
every unit. `ai` runs a hard skirmish opponent against USA. `lineup` captures native
renders; `move`, `duel` and `power` exercise movement, combat and offensive powers.
Run `native_review.py --help` for fixture arguments. The synthetic APS and drone
tests isolate engine rules; separate native duels cover the real faction units.
All test hooks are opt-in environment variables.

## Playtest scope

Costs and weapon values are an initial balance baseline. Production, AI survival,
damage, movement and counterplay checks do not establish competitive balance.
Custom voices and further art polish remain future work. Israeli, Russian and
Ukrainian troops use original articulated geometry and rigid-joint clips. The
stock renderer applies object scale in both
asset creation and the draw transform, so compare infantry changes in the actual
game rather than relying on Blender dimensions alone.

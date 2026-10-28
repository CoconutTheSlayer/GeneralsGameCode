# Russia faction original assets

The playable roster contains twelve units and eleven buildings; the two retired aircraft remain available as preserved scenario assets. Visible geometry, textures and articulated infantry are original assets. Stock object parents supply gameplay behaviours only.

## Rebuild

Run from the project root, using the saved material atlas and illustrated portrait sources:

```sh
python3 scripts/models/russia/paint.py
/Applications/Blender.app/Contents/MacOS/Blender -b -t 4 -P scripts/models/russia/build.py
/Applications/Blender.app/Contents/MacOS/Blender -b -t 4 -P scripts/models/russia/articulated.py
python3 scripts/models/russia/finalize.py
python3 scripts/factions/russia/build_faction.py
```

Append `-- RUTIGR RUT90` to the Blender vehicle/building command to rebuild selected models; the infantry command accepts `RURIFLE`, `RUKORNET` and `RUCMDO`. `infantry.py` and `review_v2.py` are retained legacy experiments with the installed Ranger rig and must not be used to rebuild the current infantry.

## Sources and appearance

`build.py` authors the vehicles, aircraft and buildings. `ground_building_detail.py` adds original armour, optics, launcher mechanisms, stowage and industrial fittings within the existing bounds. `articulated.py` and `infantry_articulated.py` author the three soldiers, weapons and animation clips. `baking.py` bakes the painted materials and contact shadows; `atlas_polished.png` and its prompt preserve the original olive material source. Buildings use the separate industrial atlas.

The direction is heavy olive armour, dark mechanical recesses, readable equipment and restrained weathering at Generals camera distances. Separate `HOUSECOLOR` meshes provide player colours. There are no stock visible meshes or stock infantry skeleton dependencies.

All 25 retained portraits are original PNGs in `portraits/`, with generation prompts and source records beside them. The faction emitter invokes the shared illustrated-portrait exporter to create runtime 128px and HD 256px TGA images. Model rebuilding does not replace these with model thumbnails.

## Runtime contracts and review

`manifest.json` records exact bone transforms, dimensions, variants, textures and rebuild commands. Ground and building detail preserves the existing turret, muzzle, exit, docking and aircraft parking contracts. Infantry uses full-size geometry at ModelScale 1.0, with original `_I` idle/reset, `_R` run, `_F` attack and `_X` death clips. The explicit idle resets animated joints after movement. Global game scaling stays at the original defaults.

Editable Blender projects, per-model previews, `contact-sheet.png`, `icons-review.png` and structural/contract validation reports are in `build/faction-assets/russia/`. Runtime art is in `resources/macos/GameData/Art/`. `finalize.py` checks geometry and animation exports; `scripts/factions/expansion/check_infantry_idle.py --faction russia` performs the native move-then-stop regression. Native production and lineup review use `scripts/factions/expansion/native_review.py`.

## Ground offensive redesign

The normal roster is Engineer, Supply Truck, Rifleman, Kornet, Assault Engineer, Tigr Radar Scout, T-90, BMPT, Tunguska, Msta-S, TOS-1A and Su-25. Su-35 and Mi-28 exports remain untouched and are unbuildable in normal play. The old `RUBMP3` files are preserved; internal object key `Russia_BMP3` now draws the new `RUBMPT` geometry and carries the BMPT display name. `Russia_Commando` likewise remains a stable internal key for the ordinary Assault Engineer.

`RUBMPT` reuses our original T-90 hull construction with a new twin-cannon turret, grenade launchers, side armour and optics. `RUTIGR` gains an original radar panel. `RUCMDO` retains its articulated rig and beret, with demolition satchels and an underslung grenade launcher instead of a suppressor. `RUROCKET` supplies the original unguided rocket visual. Retired icon sources are saved under `portraits/retired/`; only BMPT and Assault Engineer portraits were regenerated with the built-in image generator.

Kornet and Msta use automatic deployment, the T-90 fires a single slow powerful shot, TOS and Su-25 fire unguided rockets, and the BMPT has no passengers or missiles. The Tigr uses the shared counterbattery detector fields and creates a four-second approximate contact, followed by the original game’s five-second fog fade. Siege Ammunition and Assault Equipment replace universal armour/veterancy upgrades. Off-map artillery has a warning decal visible to both sides and a deliberate delay. Satellite reconnaissance and field-repair powers are removed.

Balance figures are a first playtest baseline, not a competitive-balance claim.

## Redesign validation

The current native production check builds all twelve active units with all four expansion factions loaded. Rifleman, Kornet and Assault Engineer pass the move-then-stop image comparison with no changed pose pixels. The asset validator checks 25 preserved roster assets, 94 model exports and their infantry clips.

The shared native mechanics check is `python3 scripts/factions/expansion/check_roster_mechanics.py`; it tests smoke, healing delay/nonstacking, paid mine activation/cancellation, approximate counterbattery contact/cooldown/vision expiry, and actual Pereh launch refusal after friendly vision expires.

An explicit-order siege check is reproducible with `python3 scripts/factions/expansion/native_review.py russia duel --units Russia_Msta:3,AmericaSupplyCenter:1 --distance 340 --seconds 45 --hold-side 1 --direct-attack --all-factions`. The three Msta destroyed the structure in 38 seconds and retained full health. The unarmed building requires a direct target order in this fixture; attack-move alone does not acquire it.

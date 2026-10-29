# Ukraine faction original assets

This asset library retains the original fourteen-unit set and adds a MANPADS infantry model and sapper mine. The redesigned playable roster selects eleven units from it; retired art is preserved. It changes no gameplay INIs, strings, existing EU assets or stock visuals.

## Build and review

From the project root:

```sh
/Applications/Blender.app/Contents/MacOS/Blender -b -t 4 -P scripts/models/ukraine/generate.py
python3 scripts/models/ukraine/review.py
```

Append `-- UAKOZAK UAOPLOT` to rebuild only named assets. The generator uses Blender's original mathematical geometry and source-atlas paint/AO baking. Existing project geometry helpers are reused; no stock mesh, stock visible infantry body, or stock texture archive is imported. All runtime resources use the `UA`/`ua` prefix and all source helpers live in this directory.

`manifest.json` is the implementation interface. Entries include runtime model variants, exact parent-local bone positions, dimensions, original source command, suggested stock gameplay parent, textures, original portrait texture and preview. Suggested parents provide gameplay contracts only and do not authorize retaining stock visual draw modules.

## Visual direction

Vehicles use olive digital camouflage, dark running gear, depth in wheel hubs and broad baked contact shading. F-16 and TB2 use cool grey aviation paint; Mi-24 uses restrained olive camouflage. All have shaped airframes, recessed openings and visible equipment. Industrial buildings have restrained roof panels, window bands, utility fittings and faction pennants. Player-colour markings are separate `HOUSECOLOR` meshes sampling `uahouse.tga`.

Models are low-poly Generals caricatures of the selected equipment, not engineering reproductions. In particular the Stugna infantry model carries an exaggerated launcher rather than depicting a full stationary tripod crew. The mobile artillery gun has compact static stabilisers, and the buildable income workshop is independent of air-drop animations.

## Runtime contracts

- All units face **+X**, use **Z up**, and expose `SMOKE01..03`.
- Wheeled vehicles expose `TIRE01..NN`, with hub/tyre geometry grouped on the matching wheel bone. Tank tracks are original hollow bands and separate `TREADSL`/`TREADSR` meshes.
- Weapons use `TURRET`, `MUZZLE01` (and additional launchers where relevant), `MUZZLEFX01`; some also expose `BARREL`, `TURRETMS`, `TURRETFX` aliases. Consult each manifest entry rather than inheriting stock draw-module assumptions.
- Mi-24 main/tail rotor and TB2 pusher propeller have native looping animation clips inside their model files. Pusher and tail-rotor bones are oriented to their physical rotation axes. Damaged aircraft use their embedded `<model>_D.<model>_D` clips.
- Infantry uses original `BODYROOT`, `PELVIS`, `TORSO`, `HEAD`, arm and leg bones. The animation clips are `<model>.<model>_I`, `_W`, `_F`, `_DIE` and have their own W3D files. Infantry damage states should use the intact hierarchy with the corresponding original clip; the standalone `_D` model has its own hierarchy and is useful for static presentation. Fire animation has subtle chest recoil in a held aiming posture. The explicit neutral idle clip resets all twelve animated body, leg and arm joints after movement. Original walking clips bend the knees and keep both hands aligned with the weapon. Preserve gameplay Scale=1.5, which calibrates this original 6.5-unit rig.
- Command-centre engineer emergence is `EXITSTART (-10,34.5,1)` to `EXITEND (70,34.5,1)` through an original open garage bay.
- Factory emergence is `EXITSTART (-12,-18,1)` to `EXITEND (70,-18,1)` through an open bay. No stock animated garage door is required. Repair uses a separate front-right dock and nine queue bones.
- The supply centre is designed for **truck** collection: `DOCKSTART (65,20,0)`, `DOCKACTION (42,20,0)`, `DOCKEND (66,20,0)`, plus nine queue bones. Trucks emerge from `(15,20,1)` to `(60,20,1)` on the clear apron. Supply truck cargo bones are `SUPPLY01..03` and `DOCKPOINT`.
- UAAIR is now a compact Drone Workshop assembled from the existing industrial shed, roof, dish and bench helpers. EXITSTART=(18,-14,3), EXITEND=(60,-14,35). The original TB2 now uses airborne AI without runway reservations or rearming.
- Buildings have intact, damaged, flattened wreck, night, damaged-night and wreck-night variants. Construction should use the native scaffold/draw contract; these assets do not include bespoke construction animation. Wreck geometry is a compressed original structure with correct bone heights, rather than separate rubble sculpting.

## Outputs and validation

Editable `.blend` projects, individual render PNGs, metadata, contact sheets and `validation.json` are in `build/faction-assets/ukraine/`. Runtime W3D models and TGA maps are in the normal game Art directories. Playable portraits are owned by the separate illustrated-portrait workflow; model review preserves existing HD icons. Only the unbuildable projectile retains a 128×128 rendered thumbnail.

Validation checks model/HLOD references, finite geometry and UVs, unique bone and mesh names after W3D name limits, parent ordering, required bones, referenced original texture files, power-of-two diffuse textures, actual TGA payloads (not merely a `.tga` extension), changed damage textures, and animation clip/hierarchy names. Native gameplay and balance are separate implementation-phase checks.

Final native material QA corrected the generated white team-colour texture to uncompressed TGA and verified yellow player markings on ground units and the command centre. The command-centre material also has modest broad-scale concrete/roof weathering; geometry, dimensions and bone contracts were unchanged.

## V2 polish

`infantry_v2.py` builds original lofted anatomy, facial geometry, shaped helmets/beret, articulated clothed limbs, plate carriers, equipment and AK-pattern weapons. Stugna carries one detailed tube and optical unit rather than also holding a redundant rifle. The old hierarchy and every local bone coordinate are preserved. New infantry are approximately 5.2–5.7k triangles.

`aircraft_v2.py` supplies original smoother airframes: F-16 intake lip/exhaust/wing extensions/control surfaces, TB2 angled twin-boom tail and camera gimbal, Mi-24 rounded troop cabin/tandem bubbles/intakes/pods/rotor fittings. Animation axes, weapon and effect bones are unchanged; gameplay scales need no adjustment.

`materials_v2.py` projects source material patches and bakes contact shadows into 1024px diffuse maps (512px for the tiny projectile). `paint/` contains copies of this project's original generated Israel v2 cloth, aviation and industrial art; shader tint, restrained digital camouflage and material mixing establish Ukraine's palette. No stock texture source is used. Ground/building geometry was preserved in V2; the bounded V3 pass below adds local fittings. Concrete/roofs use a restrained mix to avoid giant worn markings dominating broad surfaces. Both AtlasUV and PaintUV remain in editable Blender projects.

The model review checks neutral idle channels as well as geometry, rigs and textures. `native_pose_review.py stop Ukraine_Rifleman` reproduces the isolated move-then-idle capture; `native_pose_review.py combat Ukraine_Stugna` captures an attack pose. All test processes have bounded lifetimes and use copied configuration.

## V3 ground and building finish

`polish_ground.py` adds role-specific original fittings to the eight wheeled/tracked vehicles: armour and hatch/periscope layers on the Oplot, rear ramp and firing ports on the BTR-4, launcher hydraulics and radar surround on the Buk, recoil cylinders and loading controls on the Bohdana, roof electronics on the drone van, working blade hydraulics on the engineer, and cargo hoops/tie-downs on the supply truck. The Kozak receives roof stowage, a front brush bar, supplementary armour, fuel cans and a clearer weapon/optics assembly. Wheel hubs, tow points and selected access details are shared only where mechanically appropriate.

All eleven buildings receive restrained doors, window mullions, vents and utility fittings, plus role-specific loading, generator, server, workshop or launcher details. New details stay inside each original asset's world bounds and retain pitched-roof silhouettes; existing bones, collision dimensions, clear factory exits and aircraft parking contracts do not change. The added meshes are consolidated by surface and existing bone before baking, and exported into the existing small draw-group set. Broad camouflage stays unchanged; contrast comes from darker fittings and baked contact shading.

The three infantry, three aircraft, projectile and their animation/paint resources remain byte-for-byte stable during V3. Playable icons and the existing projectile thumbnail are preserved by review. No ground/building draw-module, scale or gameplay change is needed. Infantry draw Scale=1.5 is calibrated separately in the faction implementation. Geometry-only QA can be repeated with `Blender -b -t 4 -P scripts/models/ukraine/polish_ground.py`; final geometry/rig validation is `python3 scripts/models/ukraine/review.py`.

## Roster redesign assets

`UAMANP` adds a dedicated shoulder-launch anti-air team using the original UA articulated skeleton, cloth materials, neutral idle, walk, fire and death clips. `UACOMM` is now a helmeted sapper with a short carbine, demolition bag, mine case and probe; it no longer has a beret, suppressor or sniper scope. `UAMINE` is a tiny original circular mine model. `UAAIR` is the compact drone workshop. Rebuild these with `Blender -b -t 4 -P scripts/models/ukraine/generate.py -- UAMANP UACOMM UAMINE UAAIR` followed by `python3 scripts/models/ukraine/review.py`. Other vehicle and aircraft meshes are retained.

Replacement MANPADS, sapper and workshop portraits were created with built-in image generation. Workspace PNGs are in `portraits/`; `portraits/redesign-provenance.json` contains the exact prompts and original source paths. Replaced sapper/workshop portraits remain as `*-pre-redesign.png`.

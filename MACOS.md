# Native macOS Build

Command & Conquer Generals and Generals: Zero Hour build and run natively on Apple Silicon Macs, without Wine or
CrossOver. The Windows code paths are kept and run on top of a thin compatibility layer:

| Component | Windows | macOS |
|---|---|---|
| Win32 API (files, threads, registry, windows, input) | Windows | `Dependencies/Win32Shim` on POSIX + SDL3 |
| Rendering | Direct3D 8 | `Dependencies/D3D8Metal`: Direct3D 8 implemented on Metal |
| Audio | Miles Sound System | `Dependencies/Miles/MilesMac.cpp`: Miles API on SDL3 audio + AudioToolbox |
| Video | Bink | FFmpeg (`RTS_BUILD_OPTION_FFMPEG`) |
| Text rendering | GDI | CoreText |

You need your own copy of the game data (see [Game data](#game-data)).

## Requirements

- A Mac with Apple Silicon and macOS 13 or newer
- Xcode command line tools (`xcode-select --install`)
- Homebrew packages: `brew install cmake ninja sdl3 ffmpeg`

## Building

```bash
cmake --workflow --preset macos
scripts/macos/make-app.sh
```

This produces `build/macos/GeneralsMD/generalszh` (Zero Hour), `build/macos/Generals/generalsv` (Generals) and the
application bundles `Command and Conquer Generals Zero Hour.app` and `Command and Conquer Generals.app` in
`build/macos`. The bundles contain SDL3, FFmpeg and the libraries they need, so they can be copied to Macs without
Homebrew (set `MACOS_APP_NO_BUNDLE_LIBS=1` to skip this).

Other presets:

- `macos-releaselog`: release build with the game's debug log (`DebugLogFile.txt` in the log folder, see Troubleshooting)
- `macos-debug`: debug build

## Game data

Zero Hour needs both the Zero Hour files (`INIZH.big`, `WindowZH.big`, ...) and the original Generals files
(`INI.big`, `W3D.big`, ...), for example from the Windows installation of *Command & Conquer: The Ultimate
Collection* or the original discs. Copy both game folders to your Mac, e.g.:

```
~/Games/Command and Conquer Generals/              <- Generals files
~/Games/Command and Conquer Generals Zero Hour/    <- Zero Hour files
```

On first start the game looks for the data in this order:

1. The environment variables `GENERALS_ZH_PATH` (Zero Hour folder) and `GENERALS_PATH` (Generals folder). These
   are used even if the folder contains no `.big` archives, for example for loose files.
2. The folders chosen on a previous run
3. The current working directory, and a Generals folder next to the Zero Hour folder
4. If nothing is found, it asks for the folders with a folder picker

Generals only needs the Generals folder and looks for it the same way (`GENERALS_PATH`, saved folder, working
directory, folder picker).

The chosen folders are remembered in `~/Library/Application Support/GeneralsZH/registry.txt`, which also holds the
other values the Windows version keeps in the registry. Delete that file to choose the folders again.

Saved games, replays, maps and `Options.ini` are stored in
`~/Documents/Command and Conquer Generals Zero Hour Data/`, just like on Windows.

## Running

Open the application bundle, or run the executable directly:

```bash
GENERALS_ZH_PATH=~/Games/"Command and Conquer Generals Zero Hour" \
GENERALS_PATH=~/Games/"Command and Conquer Generals" \
build/macos/GeneralsMD/generalszh -win
```

Command line options are the same as on Windows, for example `-win` for windowed mode, `-xres 1920 -yres 1080`
for the resolution or `-quickstart` to skip the intro movies. In fullscreen mode the game uses a borderless window
on the current display and scales the image to fit.

## Testing and camera options

- `-skirmish [map name]` skips the intro and menus and starts a skirmish with the settings of the last
  skirmish, for example `generalszh -skirmish "Alpine Assault"`. `-ai easy|medium|hard` and `-opponents N`
  choose other AI opponents.
- The camera can zoom out three times as far as on Windows, and scrolls faster the further it is zoomed out. Set
  `CameraZoomOutFactor` in `Options.ini` (1 to 6) to change this; the default view when a game starts is
  unchanged. `GENERALS_CAMERA_ZOOM_OUT` overrides it for test runs, and `GENERALS_LOOKAT=x,y,height` also sets
  the camera height.
- The game renders at the display refresh rate while the simulation keeps its normal speed.

## Gameplay additions

- **Health bars**: `HealthBars` in `Options.ini` is `Selected` (default, as on Windows), `Damaged` (also every damaged
  unit and building of the players) or `All`. Alt+H cycles through them in a game and saves the choice. Health bars
  get thicker at high resolutions.
- **Blood** (Zero Hour): infantry bleeds when shot and leaves pools and splatters when killed, more when run over, and
  is torn apart by explosions (chunks, a red mist and splatters thrown wide). Burned, poisoned or lasered infantry
  does not bleed. The pools fade after a minute or so. `Blood` in `Options.ini` is
  `High` (default), `Low` (no heavy effects) or `Off`. The effects are defined in
  `resources/macos/GameData/Data/INI/Blood.ini`.
- **Rally points** (Zero Hour): new combat units attack-move to a factory's rally point, fighting what they meet on
  the way. Ctrl+right-click sets a rally point they simply move to, as before.
- **Model sizes**: the original game's proportions are the default for every unit category.
  `ScaleInfantry`, `ScaleVehicles`, `ScaleTanks`, `ScaleBikes`, `ScaleJets`, `ScaleHelicopters` and
  `ScaleStructures` in `Options.ini` (0.25 to 4, default 1) optionally change their appearance
  without changing gameplay geometry when `RealScale = no` (the default). `RealScale = yes`
  instead draws vehicles and aircraft at their real world size next to the infantry (buildings
  keep their size); `GENERALS_ORIGINAL_SCALE=1` draws everything at the
  original size. `GENERALS_LINEUP=TemplateA,TemplateB` places one of each in a row in the middle of the map, to
  compare sizes.
- **Production queue** (Zero Hour): factories queue up to 30 units; the queue shows the first 9 and "+N" for the rest.
- **Unit stance** (Zero Hour): the Stance button on the command bar, or Ctrl+A, switches the selected units between
  Guard (the original behavior: fire at enemies in range) and Aggressive (attack anything in sight and chase it).
- **Effects** (Zero Hour): the most used explosion, fire, flame, spark, flare and smoke textures are replaced by high resolution
  redraws (`resources/macos/GameData/Art/TexturesHD`, made from the originals; `GENERALS_ORIGINAL_EFFECTS=1` uses the
  originals). The High and Very High detail levels allow 12,000 and 20,000 particles instead of 3,000 and 5,000, and
  keep every effect until the frame rate drops below 20.
- **Bigger explosions** (Zero Hour): destroyed vehicles, aircraft and buildings also throw sparks and burning
  debris, flash and leave a column of smoke over the wreck or ruin for a while; buildings shower embers. The
  effects are added to the original ones by `FXListAddition` blocks (an FXList block that adds to an existing list
  instead of replacing it) in `resources/macos/GameData/Data/INI/Explosions.ini`. Hot air shimmers above
  explosions and burning ruins when the Heat Effects detail option is on; it uses the engine's smudge particles,
  which now wobble gently instead of jumping by up to 6% of the screen every frame, and the renderer copies the
  screen for them on the GPU. Nukes, the Scud Storm, fuel air bombs, napalm, the particle cannon and flame
  weapons get shimmer, embers and smoke the same way.
- **Ground effects follow the terrain**: particles that lie flat on the ground (radiation and toxin fields,
  shockwave rings, ground glows) are drawn as a grid that follows hills and the water surface, instead of a flat
  square that cut into slopes and floated over dips.
- **Soft particles**: smoke, fire and explosion sprites fade out where they meet the ground, units and buildings
  instead of cutting into them with a hard edge (both games). `GENERALS_SOFT_PARTICLES` sets the fade distance
  in world units (default 12, 0 turns it off).
- **Money cheat** (Zero Hour): Ctrl+Shift+M gives the player $100,000 in skirmish and campaign games, for example to
  test the AI. It does nothing in multiplayer games.
- **Balance changes** (Zero Hour, optional): `scripts/balance/apply_balance.py` narrows the gap between the twelve
  factions (1v1 win rates of 1.04 range from 39% for China to 59% for the Infantry General) and adds general ranks 6
  to 16, so a general can eventually buy every promotion. It reads the original INI files from your `INIZH.big` and
  writes edited copies to `Data/INI` of the game folder, which the game uses instead of the archived ones.
  `--remove` restores the original balance. The change list with the reasoning for each value is in the script.
  Balanced games cannot play online against unmodified clients, and replays only play back with the same data.

## Limitations

- The Mac build cannot play multiplayer games or replays together with the original Windows version. The game
  logic depends on exact floating point results, and network packets use a different wide character size.
  Multiplayer between Macs running the same build works.

## Deterministic simulation (towards crossplay)

The simulation now computes bit identical results on Apple Silicon and on x86-64 (tested with the same replay on
an arm64 and an x86-64 build, the latter under Rosetta): floating point contraction (fused multiply-add) is off
everywhere, and `sin`, `cos`, `pow` and the other transcendental functions come from musl's implementations in
`Dependencies/DetMath` instead of the platform's C library (`rts_detmath.h` is included in front of every C and
C++ file and redirects the calls). Replays recorded before this change no longer play back. Still to do for
Windows and Linux crossplay: the same flags there, sorting and hash map iteration that do not depend on the C++
library, and a fixed wide character size in network packets.

- `GENERALS_CRC_LOG=1` prints the game state CRC at every CRC frame (and a CRC of a fixed set of math results),
  for example during `-headless -replay`; compare the output of two builds to find where they diverge.
- `GENERALS_CRC_DUMP=<prefix>` writes the data behind the CRCs of frames 0 and 100 to `<prefix>_<frame>.dat`.
- An x86-64 build for comparisons: build SDL3 for x86-64, then configure with
  `-DCMAKE_OSX_ARCHITECTURES=x86_64 -DRTS_BUILD_OPTION_FFMPEG=OFF -DCMAKE_PREFIX_PATH=<SDL3 prefix>`.
- Save games are not compatible with Windows save games.
- The embedded web browser, crash dumps and the patch downloader are not available.

## Troubleshooting

- Every run writes a session log to `~/Library/Logs/Command and Conquer Generals/` (also shown in Console.app):
  `ZeroHour-<date>-<pid>.log` or `Generals-<date>-<pid>.log`, with `ZeroHour-latest.log` and `Generals-latest.log`
  pointing at the newest. It starts with the version, macOS, CPU, GPU and data folders, holds everything the game
  prints, and ends with a stack trace if the game crashes (the full crash report is in
  `~/Library/Logs/DiagnosticReports`). Output still reaches the terminal or a redirection. The newest 20 logs of
  each game are kept; set `GENERALS_NO_LOG=1` to turn the session log off.
- *"Technical Difficulties" on start*: the game data could not be read. Check that `INIZH.big` is in the Zero
  Hour folder and `INI.big` in the Generals folder, or delete `registry.txt` to pick the folders again.
- Set `GENERALS_NO_MESSAGEBOX=1` to print message boxes to the terminal instead of showing them.
- Set `GENERALS_AUDIO_DUMP=<file>` to record the mixed audio output as raw 32 bit float stereo samples.
- The renderer antialiases with 4 samples per pixel and gives smoothly filtered textures trilinear and 16x
  anisotropic filtering. `D3D8METAL_MSAA=<samples>` and `D3D8METAL_ANISOTROPY=<1-16>` change that (1 turns either
  off).
- The renderer runs the game's vs.1.1 and ps.1.1 shaders (translated to Metal), so the game uses its shader
  paths: single pass terrain with cloud shadows, water with soft shores and sparkles, swaying trees. Set
  `D3D8METAL_SHADERS=0` to report a card without shaders and use the fixed function paths instead.
- Set `GENERALS_PATH_STATS=1` to print once a minute how long ground units were stuck (they had a path but moved
  less than 3 units in 3 seconds), where, which unit types, and how many path computations failed.
- Set `GENERALS_PATH_TEST=Template:count:ax:ay:bx:by` in a `-skirmish` run (not `-observe`) to spawn `count` units of
  the player at map point A (fractions of the map size) and order them to point B as a group. It reports how many
  arrived, gave up or got stuck, and ends after all of them stopped or 3 minutes, for example
  `GENERALS_PATH_TEST=AmericaTankCrusader:20:0.2:0.2:0.8:0.8` on Leipzig Lowlands.
- Set `GENERALS_LOOKAT=x,y` to move the camera once to that point of the map (fractions of its size), for
  screenshots of a particular place in `-skirmish` test runs.
- Set `GENERALS_FX_TEST=FX_A,FX_B` (Zero Hour) to play those effect lists from `FXList.ini` one after another, every
  two seconds (`GENERALS_FX_TEST_EVERY` seconds), where the camera looks, for example
  `FX_GenericTankDeathExplosion,FX_LargeStructureDeath`.
- The renderer encodes Metal commands on its own render thread; the game thread records the D3D calls into a
  queue. `D3D8METAL_THREADED=0` does everything on the game thread, to compare. `GENERALS_FPS_LOG=1` prints the
  frame rate and the game thread's CPU time per frame every two seconds.
- Set `D3D8METAL_TRACE=1` to print the fixed function state of every draw call, the textures that are created and
  the shader compile times.
- The renderer lists every pipeline it builds in `~/Library/Caches/<bundle id>/pipelines.bin` and builds those
  pipelines at startup, so shader compilation does not stall the game the first time a unit or effect appears.
  Delete the file to start over, or set `D3D8METAL_PIPELINE_CACHE` to another file (empty to disable it).
- The `macos-releaselog` preset writes the game's debug log, which names missing INI files and failed assertions,
  to `DebugLogFile.txt` in the log folder and into the session log.

## Tests

```bash
ninja -C build/macos win32shim_test d3d8metal_test miles_test z_ww3d_test
build/macos/Dependencies/Win32Shim/win32shim_test /tmp/shimtest
build/macos/Dependencies/D3D8Metal/d3d8metal_test /tmp      # writes scene*.png, fails on mismatches
build/macos/Dependencies/Miles/miles_test
build/macos/GeneralsMD/z_ww3d_test /tmp/ww3d.png
```

`d3d8metal_test` renders test scenes and compares texture stage operations, blending, alpha test, texture
addressing, lighting, fog, generated and projected texture coordinates with the Direct3D 8 formulas pixel by
pixel, and checks that textures and buffers changed in the middle of a frame keep earlier draws intact.
`d3d8metal_test <dir> --bench` measures the CPU time of draw calls.

For renderer performance comparisons, save a baseline binary and alternate baseline and changed runs with
the same settings. Use `D3D8METAL_THREADED=0` to include command encoding in the benchmark's CPU measurement;
the default threaded mode measures submission and any queue waits. The time including `Present` may be
limited by the display refresh rate, so a lower CPU time does not necessarily increase FPS. Warm shader
caches, keep other workloads idle, and report repeated runs rather than the fastest result.

Scene 14 (`scene14_uniforms.png`) covers changes to camera, world and projection matrices, nonuniform
scaling, lights, unlit environment mapping and clip planes. Compare its pixels with a baseline capture in
both threaded and inline modes when changing derived uniform caching; it is a visual regression fixture,
not an additional automatic pixel assertion.

For Zero Hour fog-of-war uploads, `GENERALS_SHROUD_STATS=1` reports cumulative rendered frames, map-copy
calls and uploaded map pixels every 240 frames. `fullPixels` is what a full-map copy on every frame would
have uploaded; border clears are excluded. `GENERALS_VERIFY_SHROUD=1` separately compares the complete
destination surface contents with the source map every 240 frames, including frames that skip uploads.
Expect `mismatchedRows 0`. On Metal this validates the texture's CPU shadow and dirty-region tracking;
it is not a GPU readback test. Leave verification disabled during timing runs.

Zero Hour batches dynamic shadow volumes on the native port. Position-only vertices are transformed to
world space and collected into batches of at most 65,535 vertices, uploaded once, and drawn in the original
separate front/back stencil passes. Static shadows, visibility tests and shadow geometry detail are unchanged.
Buffers are retained for both passes, discarded on the next frame, and released on device reset. Allocation
or upload failure falls back to the original renderer. `GENERALS_DYNAMIC_SHADOW_STREAM=0` selects the original
path for comparisons; the default is enabled. Debug shadow-geometry visualizations keep the original path.

`GENERALS_SHADOW_STATS=1` reports average game-thread CPU milliseconds spent in shadow rendering per frame,
plus upload calls/bytes every 240 rendered frames. `reused` counts dynamic volumes collected into batches;
each batch replaces many per-volume uploads and draws. This timer excludes the renderer worker and GPU.
`GENERALS_VERIFY_SHADOW_STREAM=1` checks uploaded vertex/index contents and index bounds on Metal; expect zero
errors. Verification performs extra buffer reads, so do not use its timings as performance results.

The experimental `GENERALS_LAZY_SHADOW_PREP=1` path fetches each mesh's bounding box and extrusion floor only after
the original rotation/light test decides to rebuild its volume. This avoids preparing bounds
for moving meshes whose shadow geometry is still reusable. Visibility, silhouettes, extrusion
math and draw ordering are unchanged. `GENERALS_LAZY_SHADOW_PREP=0` restores eager preparation
for a same-binary comparison; the default is **0** because repeated large-battle tests did not
establish an FPS improvement. One CPU diagnostic showed about 5% less update/collection time,
but this was only about 0.03 ms per rendered frame. `GENERALS_VERIFY_SHADOW_PREP=1` checks
that deferred bounds/floors exactly match the eager reference during rebuilds. CPU profiles
include `shadows.update_and_collect`, `shadows.bounds_not_needed`, `shadows.bounds_prepared`
and `verify.shadow_bounds`. Verification and screenshot runs are excluded from FPS comparisons.

```sh
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/shadow-preparation --label eager --units 300 500 --rounds 3 --modes frames \
  --env GENERALS_VISUAL_WORKERS=0 --env GENERALS_LAZY_SHADOW_PREP=0 \
  --compare-env GENERALS_LAZY_SHADOW_PREP=1
python3 -B scripts/macos/benchmark.py compare build/shadow-preparation/eager-results.json
```

This benchmark always disables audio and requires confirmation from the executable.
Add `--offscreen` only for a separate throughput comparison. The graphics regression test
also compares 614,400 shadow-mask pixels between separate and combined volumes, covering
overlap, occlusion masks, transforms, depth clipping and the 16-bit batch boundary.

The optional `GENERALS_BATTLE_TEST=FriendlyTemplate:EnemyTemplate:countPerSide` fixture spawns two opposing
armies at the centre of the map, issues attack-move orders, and reveals the map for observation. It requires
an enemy player and accepts 1–1,000 units per side. Use only for development tests. To alternate the original
and batched paths in seeded 300- and 600-tank battles:

```bash
python3 scripts/macos/benchmark-shadows.py \
  --game-data "$HOME/Games/generalszh" --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/shadow-benchmark --units 150 300 --rounds 3
```

The script saves raw logs and timing samples, filters out initial warmup, alternates run order, and stops
each run after the same simulation-frame threshold. `--verify --rounds 1` also captures screenshots and
simulation CRCs for a separate correctness check. Frame-rate gains depend on the rest of the scene and
the display limit; compare shadow CPU time separately from total game-thread time and FPS.

`z_ww3d_test` writes W3D files (textured meshes with TGA and DDS textures, a bone hierarchy with an HLod, raw
and compressed animations and a skinned mesh) into the working directory and renders them through the asset
manager like the game does.

To build the tests or the game with the address and undefined behavior sanitizers, configure a separate build
directory with `-DRTS_BUILD_OPTION_ASAN=ON` and `-fsanitize=address,undefined` in the compiler flags.
`RTS_BUILD_OPTION_ASAN` replaces the game's memory manager with the system allocator.

## How the port works

- `Dependencies/Win32Shim` provides `windows.h` and friends. It is force included in every translation unit,
  like the Windows precompiled headers. Windows paths (backslashes, drive letters) are translated at the API
  boundary, the registry is stored in a text file, and windows, the message loop and input are implemented with
  SDL3 by translating SDL events into `WM_*` messages for the game's window procedure.
- `Dependencies/D3D8Metal` implements `IDirect3D8` and `IDirect3DDevice8` with Metal, using the DirectX 8 SDK
  headers. The fixed function pipeline (lighting, texture stages, fog, texture coordinate generation, alpha test)
  is emulated by Metal shaders generated from the current device state and cached. Textures keep a CPU copy in
  their Direct3D format so `Lock` behaves like on Windows.
- `Dependencies/Miles/MilesMac.cpp` implements the Miles API used by `MilesAudioManager` with a software mixer.
- Data files store text as UTF-16; since `wchar_t` is 4 bytes on macOS, text is converted when reading and
  writing CSF string tables, maps, saves and replays (`Common/UTF16.h`).

### CPU / GPU battle profiler

`scripts/macos/benchmark.py` records repeatable Zero Hour battles, frame-time distributions,
CPU wall and thread time, native Metal render/blit passes, command-buffer GPU times, draw counts,
buffer upload demand, particle counts, and waits for rendering/presentation. Results are local:
`report.html`, `summary.json`, `trace.json` (Chrome trace / Perfetto), `profile.jsonl`, `run.json`,
and `native.log`. Run settings include the binary hash, hardware, resolution, environment, and
aggregate system CPU load and memory usage before/after each run. Heavy background load, missing
records, incomplete windows and simulation mismatches disqualify a pair from speedup statistics.
The fixed battle seed and simulation CRCs allow behavior comparisons; camera height is explicit.

```sh
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" \
  --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/battle-profile --units 300 500 --rounds 3 \
  --modes frames gpu --offscreen
```

Counts are **per army**, so the example runs 600- and 1,000-unit battles. The default measured
interval is simulation frames 180–599, after the armies spawn at frame 60. The recorder uses
`GENERALS_PROFILE_START_LOGIC` and `GENERALS_PROFILE_END_LOGIC` to collect this window without
loading-screen traffic; late GPU completions are matched to their original recorded frame. The runner rejects
missing spawns, early exits and timeouts, and never closes unrelated game processes. `--roster
infantry` supplies a second workload; `--width`, `--height`, `--seed`, `--camera-height`, `--warmup`
and `--frames` customize the scenario. Runs alternate mode order. Use a fresh output directory
(or label) for each invocation; existing runs are never overwritten.

`--offscreen` executes the same scene and final presentation shaders into a texture at the
window drawable's resolution. It isolates throughput from WindowServer / display pacing; its
frames/s are **not measured on-screen gameplay FPS**. Omit it for a visible-window run. The runner
disables display sync and sets `GENERALS_BENCH_UNCAPPED=1` by default; `--vsync` restores display sync.
The uncapped override bypasses render pacing only while logic uses its independent clock. The
release executable does not expose the debug-only `-noFPSLimit` switch. macOS can still throttle drawable delivery
with display sync disabled, which is why both types of run matter. Normal game launch settings
remain unchanged.

Modes, selected by `GENERALS_PROFILE_MODE` or `--modes`:

- `off`: ordinary FPS log only, for checking recorder overhead.
- `frames`: per-frame main/render-thread wall and CPU time. Use for performance comparisons.
- `cpu`: adds named system scopes, wait scopes and work counters.
- `gpu`: adds asynchronous command-buffer times and periodic native render/blit encoder timestamps.
  By default every 30th frame samples all encoders; `--env GENERALS_PROFILE_GPU_EVERY=1` samples
  every encoder in every frame. Unsupported counters or invalid samples are reported explicitly.
- `passes`: diagnostic mode that ends Metal encoders at named engine phase boundaries, so terrain,
  meshes, shadows, particles and UI can be timed separately. **This changes the workload** through
  extra load/store/resolve operations. Never use it to claim a speedup.

`--detail` adds CPU timings around individual draw/state operations. `--sample` collects a separate
five-second native `sample` call-stack report. Both are diagnostic runs: they disturb timing and
are excluded from the comparison command. Instrumented scopes are not hardware CPU-cycle counts
or exhaustive function tracing. Their self time excludes instrumented children; uninstrumented
work remains in the enclosing scope. The call-stack sample helps investigate that remainder.
Frame/command coverage is reported; capture boundaries and empty command buffers can leave a
small number of CPU frames without GPU timings. CPU threads and GPU execute concurrently; don't add their times. GPU vertex/fragment intervals
can overlap across encoders; don't sum pass durations as a frame total. Pass means use sampled
frames, command-buffer means use all measured frames. GPU frame coverage and recording errors
are included in the report. Timing fields contain microseconds; reports display milliseconds. For `kind=counter` records,
the shared `wall_us` field contains the counter value in the units implied by its name.

For an alternating A/B comparison, preserve a baseline binary with its usual Resources directory
and pass `--binary /path/to/baseline/generalszh --compare-binary /path/to/candidate/generalszh
--modes frames --rounds 3`. Alternatively `--env NAME=old --compare-env NAME=new` compares a
runtime switch in one binary. The runner reverses A/B order each round. Comparison produces JSON and an HTML table with links
to each run; it excludes flagged pairs from its aggregate speedup. Then:

```sh
python3 -B scripts/macos/benchmark.py compare build/battle-profile/baseline-results.json
python3 -B scripts/macos/benchmark.py analyze /path/to/profile.jsonl --warmup 180 --frames 600
```

Keep power mode, background load, game-data overlay and graphics quality the same. Do not run
builds, screenshots or CPU sampling during timed comparisons. Report per-pair variation as well
as the median; the live particle workload is render-rate dependent even when simulation CRCs match.
Check overhead on the tested machine using repeated `off frames cpu gpu` runs; don't assume the
profiler is free. The recorder uses a bounded asynchronous output queue and reports dropped events.

For a manual game session, set `GENERALS_PROFILE=/absolute/path/profile.jsonl`; profiling is off
when unset. `D3D8METAL_VSYNC=0` is an independent, opt-in windowed display-sync override, and
`D3D8METAL_BENCH_OFFSCREEN=1` is the isolated presentation mode used by the runner.

Recorder/analyzer checks:

```sh
cmake --build build/macos --target native_profile_test d3d8metal_test
python3 -B -m unittest discover -s scripts/macos/tests -v
```

The renderer suite also stresses draws whose vertex/index buffers are immediately released,
unaligned index copies, triangle fans and transient-arena rollover before GPU submission.

### Experimental parallel visual work

`GENERALS_VISUAL_WORKERS=1..4` enables a bounded pool of extra CPU workers; the game thread
also helps process the queue. The default is **0**: enablement depends on measured benefit,
not the number of available CPU cores. `GENERALS_PARALLEL_SHADOWS=0` or
`GENERALS_PARALLEL_PARTICLES=0` independently disables either group for attribution.
Small batches run inline. Workers sleep between batches and join before game objects or
graphics resources can change.

The shadow experiment computes dynamic silhouettes with worker-private polygon flags,
extrudes already allocated volumes, and transforms/rebases disjoint batches of shadow vertices
and indices. The particle experiment culls independent systems and sorts disjoint partitions
with the original triangle comparison/partition algorithm, preserving equal-depth ordering.
Hierarchy updates, shared geometry caches, allocation of engine objects, simulation, texture
references and graphics calls remain on the game thread. CPU captures include `visual.0` etc.
worker lanes, associated with the original main frame.

All benchmark runs now require an `Audio disabled (-noaudio)` confirmation from the executable.
The native release build previously ignored this debug-only switch; `-noaudio` is now supported
in native release builds and prevents opening the audio device. Older benchmark binaries must
be rebuilt before they can be used in the silent runner. Normal launches keep audio enabled.

```sh
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" \
  --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/visual-worker-comparison --label serial \
  --units 300 500 --rounds 3 --modes frames \
  --env GENERALS_VISUAL_WORKERS=0 --compare-env GENERALS_VISUAL_WORKERS=2
python3 -B scripts/macos/benchmark.py compare build/visual-worker-comparison/serial-results.json
```

This uses windowed presentation. Add `--offscreen` for a separate throughput experiment.
Never combine those results. For correctness only, use `--modes cpu --env GENERALS_VISUAL_WORKERS=2
--env GENERALS_VERIFY_VISUAL_JOBS=1`; this recomputes worker outputs serially and checks exact
shadow vertices/indices, visibility and triangle ordering. It aborts on mismatch and reports
verification counts. `GENERALS_VERIFY_SHADOW_STREAM=1` additionally checks uploaded buffers.
Verification results are excluded from speedup comparisons.

```sh
cmake --build build/macos --target visual_jobs_test native_profile_test
python3 -B -m unittest discover -s scripts/macos/tests -v
```

The visual-job test checks repeated queue reuse, exactly-once execution, joins, real worker
execution and profiler correlation with 0/1/2/4 workers. It compares 45 sorting cases per worker
configuration against the frozen original algorithm, including equal depths and non-finite keys.

### Indexed pathfinding queue

The native pathfinder uses a cost-bucket index to find insertion positions in its sorted open
list. The original linked list, costs, search budgets and equal-cost insertion order remain
unchanged. The index stores the last node at each occupied 16-bit cost and uses three bitmap
levels to find its predecessor, replacing a potentially long list walk. It is allocated lazily
for open lists (about 520 KiB each), reused between searches, and cleared before cell infos are
recycled. Each indexed cell remembers its insertion cost because callers can change the new
cost before removing it from the old position. Oversized or malformed legacy lists fall back
to the original algorithm for the rest of that search, including the retail 5,000-node cap.

The index is enabled by default. `GENERALS_PATH_OPEN_INDEX=0` selects the original insertion
algorithm for comparison.
`GENERALS_VERIFY_PATH_OPEN_INDEX=1` independently walks the original list before each indexed
insertion and aborts if the insertion position differs. Verification adds substantial work;
use it only in correctness runs, separately from performance measurements. CPU captures include
`simulation.pathfind_queue`, `pathfind.indexed_inserts`, `pathfind.index_fallbacks`, and, when
enabled, `verify.pathfind_insertions`. Counters cover calls within the measured pathfinding queue.
For this fixed-tick work, compare total queue CPU time divided by its call count, rather than
time per rendered frame: a faster renderer can produce more frames in the same logic interval.

```sh
cmake --build build/macos --target generalszh cost_bucket_index_test
python3 -B -m unittest discover -s scripts/macos/tests -v
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" \
  --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/path-index-comparison --label original \
  --units 300 500 --rounds 3 --modes frames \
  --env GENERALS_VISUAL_WORKERS=0 --env GENERALS_LAZY_SHADOW_PREP=0 \
  --env GENERALS_PATH_OPEN_INDEX=0 --compare-env GENERALS_PATH_OPEN_INDEX=1
python3 -B scripts/macos/benchmark.py compare build/path-index-comparison/original-results.json
```

All battle runs disable audio and require confirmation from the game. Repeat separately with
`--offscreen` to isolate presentation pacing. For correctness, use `--modes cpu --rounds 1
--compare-env GENERALS_VERIFY_PATH_OPEN_INDEX=1` and compare simulation CRCs as well as checking
for insertion-order failures. The cost-index test compares 100,000 operations with an ordered
map, checks all 65,536 costs and bitmap boundaries, and compares 100,000 queue edits with an
independent stable-order reference, including cost changes before removal and repeated resets.

### Separate object-transform uploads

This experiment is **off by default**. The October 27 comparison reduced rendering CPU work,
but did not demonstrate a consistent FPS gain under the requested background load. Indexed
pathfinding remains enabled independently. Saved results are in
`build/next-bottleneck-20261027/report.html`.

`D3D8METAL_SPLIT_UNIFORMS=1` sends the three object-transform matrices through a separate
192-byte vertex buffer binding. Lighting, material, texture matrices and camera parameters keep
their existing layout and are uploaded only when they change. `=0` retains the original full
1,872-byte upload path for A/B comparisons. Both bindings are invalidated when an encoder is
restarted. The choice is included in the shader/pipeline cache key, so both variants can coexist
in the persistent cache without using the wrong shader interface. Programmable shader constants
and vertex streams retain their own buffer slots.

The optimized path also caches shared-data preparation on the render thread. Relevant state
changes, shader use of lighting/clip planes/texture stages, target switches and resets invalidate
it. Object-transform changes alone do not require clearing, rebuilding or comparing the shared
block. `GENERALS_VERIFY_SPLIT_UNIFORMS=1` independently rebuilds that block whenever the cache
would otherwise be reused, checks every byte, and aborts on a missed invalidation. This is a
correctness mode, excluded from timing comparisons by the benchmark runner.

CPU profiling records `vertex_uniform_bytes`, `vertex_transform_updates` and
`vertex_shared_updates`, `vertex_shared_rebuilds`, and `verify.vertex_shared_reuses` when verifying.
Run each variant once to populate its shader cache before timed
comparisons; first-use compilation can cause stalls unrelated to steady-state throughput.
Keep indexed pathfinding enabled in both variants. For example, use the battle runner's
`--env GENERALS_PATH_OPEN_INDEX=1 --env D3D8METAL_SPLIT_UNIFORMS=0
--compare-env D3D8METAL_SPLIT_UNIFORMS=1` with three alternating rounds in frames mode, with
windowed and offscreen results reported separately. The runner always disables audio.

`d3d8metal_test` scene 17 checks repeated transform-only changes, material-only changes,
unchanged draws, and rebinding after a mid-scene readback ends the encoder. It checks 128 pixels
against independently specified colors. Run the full suite with split uniforms set to 0 and 1
and with `D3D8METAL_THREADED` set to 0 and 1; compare all PNG outputs as well as exit status.
The renderer tests do not initialize the game's audio system.

### Movement footprint checks on the main thread

This optimization is **off by default**. The October 27 paired routine measurements reduced
CPU cost by about 24% for tanks and 14% for infantry, but the 18 full-battle timing runs did
not establish a dependable FPS gain. It remains available for further profiling; the earlier
indexed pathfinding optimization stays enabled independently.

`GENERALS_FAST_MOVEMENT_CHECKS=1` enables the native movement-check optimization;
`=0` retains the original routine for comparisons. The optimized routine resolves map bounds
once for an entirely in-bounds ground footprint and reuses object, relationship and crushing
answers when adjacent cells contain the same unit. These answers live only for that single
call. Bridge layers and map-edge footprints retain the original cell lookup, scan order and
early-return behavior. The original five-entry allied-unit counting limit is preserved.

`GENERALS_VERIFY_MOVEMENT_CHECKS=1`, together with the optimized path, compares every movement
decision and all four output fields against a frozen copy of the original routine. It also
checks 784 combinations of map-edge coordinates, empty/nonempty footprints and transient-unit
settings. A mismatch aborts the process. This mode adds significant work and must not be used
for FPS comparisons; the benchmark runner marks it as diagnostic.

Verification also samples every 64th input into batches of 512. Each batch resolves its object
IDs against the current world, warms both routines, then replays each routine four times with
alternating order. `verify.movement_reference` and `verify.movement_fast` measure CPU time for
the same read-only inputs and world state. This is a local routine-cost measurement with warm
caches, not a replacement for full-battle FPS measurements. `verify.movement_replay_cases`
counts measured cases per routine. `pathfind.movement_checks` and `verify.movement_checks`
count live calls within the measured pathfinding queue, excluding diagnostic replays.

```sh
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" \
  --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/movement-comparison --label original \
  --units 300 500 --rounds 3 --modes frames \
  --env GENERALS_PATH_OPEN_INDEX=1 --env GENERALS_VISUAL_WORKERS=0 \
  --env GENERALS_LAZY_SHADOW_PREP=0 --env D3D8METAL_SPLIT_UNIFORMS=0 \
  --env GENERALS_FAST_MOVEMENT_CHECKS=0 --compare-env GENERALS_FAST_MOVEMENT_CHECKS=1
python3 -B scripts/macos/benchmark.py compare build/movement-comparison/original-results.json
```

All battle runs disable audio. Repeat with `--offscreen` for rendering throughput independent
of window presentation, reported separately from gameplay FPS. For live verification and paired
routine timings, run one CPU-mode battle with `--env GENERALS_FAST_MOVEMENT_CHECKS=1
--env GENERALS_VERIFY_MOVEMENT_CHECKS=1`. The October 27 evidence is saved in
`build/main-thread-20261027/report.html`.

### Model preparation and submission

These optimizations are **enabled by default**. Three alternating 2,000-unit windowed
pairs all improved, with a median paired gain of 4.2%; three 1,000-unit offscreen pairs
all improved, with a median paired gain of 6.5%. Smaller windowed battles remained near
the display ceiling. These are local measurements, not a guarantee for other systems
or battle compositions. Full results are in `build/model-submission-20261027/report.html`.

`D3D8METAL_MODEL_SUBMISSION=0` keeps the original submission path for comparisons;
`=1` explicitly selects the optimized path.

Static 16-bit index buffers with odd starting indices previously required a temporary
allocation and copy for each draw to satisfy Metal's four-byte offset alignment. The
optimized path lazily creates a copy with a two-byte prefix and reuses it until the source
is written. Any successful writing lock invalidates it; read-only and failed locks preserve
it. Old copies are retired against the original buffer's submission serial, including when
a lock renames that original buffer, so queued and in-flight GPU draws remain valid.
Dynamic buffers retain the original per-draw copy path. Each affected static buffer can
retain one extra full-size allocation plus the prefix and buffer-pool rounding; aligned-only
buffers do not create a copy. Peak additional resident memory has not been measured.

Repeated `SetLight` and `LightEnable` calls skip marking state dirty when the requested
values already match the producer state. Existing pending dirty bits remain set, preserving
initial state, device reset and state-block restoration. This avoids repeated state packing
on the main thread and lighting preparation on the render thread without changing draw order,
geometry or shaders.

CPU captures include `models.flush`, `models.light_sets_skipped`,
`models.light_enables_skipped`, `models.index_alignment_copies`,
`models.index_alignment_bytes`, `models.index_alignment_reuses` and
`models.index_bytes_avoided`. The broader `render.occluded` scope also contains ordinary
visible models ordered around stencil shadows. Index-copy counters are accumulated on the
producer and recorded once per frame to avoid a profiler call for each small copy.

`GENERALS_VERIFY_MODEL_SUBMISSION=1` checks every cached index range against its source
bytes and compares producer/consumer light state before every draw. A mismatch aborts the
process. Counters `verify.model_indices` and `verify.model_lights` count the checks. This
adds substantial work and is excluded from performance comparisons by the battle runner.

```sh
cmake --build build/macos --target generalszh d3d8metal_test
python3 -B -m unittest discover -s scripts/macos/tests -v
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" \
  --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/model-submission-comparison --label original \
  --units 300 500 --rounds 3 --modes frames \
  --env GENERALS_PATH_OPEN_INDEX=1 --env GENERALS_VISUAL_WORKERS=0 \
  --env GENERALS_LAZY_SHADOW_PREP=0 --env D3D8METAL_SPLIT_UNIFORMS=0 \
  --env GENERALS_FAST_MOVEMENT_CHECKS=0 \
  --env D3D8METAL_MODEL_SUBMISSION=0 --compare-env D3D8METAL_MODEL_SUBMISSION=1
python3 -B scripts/macos/benchmark.py compare build/model-submission-comparison/original-results.json
```

The runner always disables audio and requires confirmation from the game. Repeat separately
with `--offscreen` to measure rendering throughput without window presentation, or with
`--units 1000` for a 2,000-unit stress test. Keep output directories separate and retain all
pairs, including any background-load warnings. Verification uses a separate CPU-mode run
with both `D3D8METAL_MODEL_SUBMISSION=1` and `GENERALS_VERIFY_MODEL_SUBMISSION=1`.

Graphics test scene 18 adds 80 independent pixel checks plus API checks for static/dynamic
16/32-bit indices, odd offsets, base vertices, repeated draws, failed/read-only/writing locks,
NOOVERWRITE/DISCARD, release before flush, light state blocks, readback boundaries and reset.
Run `d3d8metal_test` with the optimization on/off and `D3D8METAL_THREADED` set to 0/1;
all 26 output images should match across those four configurations. These renderer tests
do not initialize game audio.


### Compiler code graph and consecutive model batching

Model batching is **off by default**. The revised implementation reduced draw submissions
by about 8%, but 2,000-unit on-screen comparisons were inconsistent, including a 14.9%
regression in the final reverse-order pair. It remains available for further work without
changing normal launches. The previously enabled model-submission optimization stays on.

`scripts/macos/codegraph.py` builds a local graph from the configured native build.
Compiler depfiles provide build-wide source/header dependency edges; clangd supplies
focused call-hierarchy edges through scene rendering, texture categories, polygon rendering,
the D3D wrapper and Metal submission. The interactive HTML view supports function search
and caller/callee navigation, with CPU scope costs from a saved benchmark beside it.
The JSON files preserve edge provenance and source hashes. Compiler dependencies are
transitive. This is not an exhaustive call graph of every platform or the launcher, and
unresolved virtual dispatch and queued callbacks require runtime evidence.

```sh
python3 -B scripts/macos/codegraph.py --build build/macos \
  --output build/renderer-codegraph \
  --profile build/model-batching-20261027/attribution/original-results.json
```

`D3D8METAL_MODEL_BATCHING=1` enables instanced batches of up to 16 consecutive matching
static indexed triangle-list draws inside the native texture-category model scope (render
state hint 249). Its end flushes pending groups and unrelated draws take an early fallback.
The supported path uses fixed-function XYZ vertices,
opaque blending, depth testing/writing, and no stencil operation. Geometry buffers, ranges,
base vertex and all rendering state must match; only the world transform may vary. Dynamic
meshes, programmable shaders, translucent surfaces and stencil volumes retain individual
submissions. No draws are reordered. Draws that do not form a group retain the original shader.

Every submitted command, state synchronization, readback/drain and presentation flushes a
pending group. Buffer renaming and retirement keep pending geometry alive. Each instance
gets the original world/view/projection and inverse-transpose normal transforms; the consumer
retains the final world transform for subsequent draws that inherit state. The shader cache
key distinguishes instancing. Transform arrays use at most 3 KiB of inline Metal data per
batch, and do not change the previous split-uniform experiment's default.

`GENERALS_VERIFY_MODEL_BATCHING=1` independently compares the full shared producer state
for every merged draw and aborts on disagreement. This diagnostic mode is excluded from
FPS comparisons. CPU captures expose `models.batch_candidates`, `models.batches`,
`models.batched_instances`, `models.draws_saved` and `verify.model_batch_instances`.
Graphics test scene 19 adds 80 expected-color checks covering multiple batch lengths,
nonuniform and mirrored transforms, a readback boundary, material changes, buffer renaming,
release before flush and inheritance of the final world transform. All 28 graphics images
should match with batching and the renderer thread independently enabled/disabled.

```sh
python3 -B scripts/macos/benchmark.py run \
  --game-data "$HOME/Games/generalszh" \
  --base-data "$HOME/Games/generalszh/ZH_Generals" \
  --output build/model-batching-comparison --label original \
  --units 1000 --rounds 3 --modes frames \
  --env GENERALS_PATH_OPEN_INDEX=1 --env GENERALS_VISUAL_WORKERS=0 \
  --env GENERALS_LAZY_SHADOW_PREP=0 --env D3D8METAL_SPLIT_UNIFORMS=0 \
  --env GENERALS_FAST_MOVEMENT_CHECKS=0 --env D3D8METAL_MODEL_SUBMISSION=1 \
  --env D3D8METAL_MODEL_BATCHING=0 --compare-env D3D8METAL_MODEL_BATCHING=1
python3 -B scripts/macos/benchmark.py compare build/model-batching-comparison/original-results.json
```

These are 2,000-unit battles (1,000 per army), always without audio. Repeat separately
with `--offscreen` for throughput without window presentation. Warm the shader variants
before timed comparisons, keep verification/indexing/builds out of the timed runs, and
retain every pair. The October 27 results are in `build/model-batching-20261027/report.html`.

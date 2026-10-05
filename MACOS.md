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
- The camera can zoom out twice as far as on Windows. Set `CameraZoomOutFactor` in `Options.ini` (1 to 4) to
  change this; the default view when a game starts is unchanged.
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
- **Production queue** (Zero Hour): factories queue up to 30 units; the queue shows the first 9 and "+N" for the rest.
- **Unit stance** (Zero Hour): the Stance button on the command bar, or Ctrl+A, switches the selected units between
  Guard (the original behavior: fire at enemies in range) and Aggressive (attack anything in sight and chase it).

## Limitations

- The Mac build cannot play multiplayer games or replays together with the Windows version. The game logic
  depends on exact floating point behavior, which differs between compilers and CPU architectures, and network
  packets use a different wide character size. Multiplayer between Macs running the same build works.
- Save games are not compatible with Windows save games.
- The renderer identifies itself as a GeForce2 class card without programmable shaders, so the game uses its
  fixed function rendering paths (for example for water and terrain). Pixel shader effects are not available yet.
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

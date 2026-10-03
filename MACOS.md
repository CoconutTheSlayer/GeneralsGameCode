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
`build/macos`.

Other presets:

- `macos-releaselog`: release build with the game's debug log (`generalszhDebugLogFile.txt` next to the executable)
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

1. The environment variables `GENERALS_ZH_PATH` (Zero Hour folder) and `GENERALS_PATH` (Generals folder)
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

## Limitations

- The Mac build cannot play multiplayer games or replays together with the Windows version. The game logic
  depends on exact floating point behavior, which differs between compilers and CPU architectures, and network
  packets use a different wide character size. Multiplayer between Macs running the same build works.
- Save games are not compatible with Windows save games.
- The renderer identifies itself as a GeForce2 class card without programmable shaders, so the game uses its
  fixed function rendering paths (for example for water and terrain). Pixel shader effects are not available yet.
- The embedded web browser, crash dumps and the patch downloader are not available.

## Troubleshooting

- *"Technical Difficulties" on start*: the game data could not be read. Check that `INIZH.big` is in the Zero
  Hour folder and `INI.big` in the Generals folder, or delete `registry.txt` to pick the folders again.
- Set `GENERALS_NO_MESSAGEBOX=1` to print message boxes to the terminal instead of showing them.
- Set `GENERALS_AUDIO_DUMP=<file>` to record the mixed audio output as raw 32 bit float stereo samples.

## Tests

```bash
ninja -C build/macos win32shim_test d3d8metal_test miles_test z_ww3d_test
build/macos/Dependencies/Win32Shim/win32shim_test /tmp/shimtest
build/macos/Dependencies/D3D8Metal/d3d8metal_test /tmp      # writes scene*.png
build/macos/Dependencies/Miles/miles_test
build/macos/GeneralsMD/z_ww3d_test /tmp/ww3d.png
```

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

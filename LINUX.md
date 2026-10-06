# Linux port (in progress)

Zero Hour builds natively on Linux (x86-64 and arm64) from the same code as the macOS port: the Win32
replacement layer in `Dependencies/Win32Shim` (SDL3), audio on SDL3 with dr_mp3 for MP3, and the
deterministic math in `Dependencies/DetMath`. Code shared by both ports is under `RTS_POSIX_PORT`
(C++) and `RTS_POSIX_PORT` (CMake); `cmake/posix.cmake` holds the shared build settings.

## Status

- Headless runs work, for example replays: `generalszh -headless -replay <name>.rep`.
- The simulation matches the other platforms bit for bit: a 12 minute four AI replay gives the same
  CRCs on macOS arm64, macOS x86-64, Linux arm64 and Linux x86-64.
- Graphics run on Vulkan through DXVK native (Direct3D 8 on Vulkan). `Dependencies/D3D8Dxvk` loads
  `libdxvk_d3d8.so` at run time (from `$DXVK_DIR/lib`, next to the executable, or the library path)
  and hands DXVK the SDL windows behind the Win32 shim's window handles. The Docker image builds
  DXVK into `/opt/dxvk`.
- Soft particles are not implemented on DXVK yet; particles are drawn as in the original game.
- Text is drawn with FreeType. fontconfig finds the fonts, so Arial, Times New Roman and Courier use
  metric compatible fonts such as Liberation. Without any fonts installed the metrics are
  approximate and no text is drawn, which is enough for headless runs.

## Building with Docker

    docker build -t generals-linux docker/linux
    docker run --rm -v "$PWD":/src -w /src generals-linux \
        sh -c "cmake --preset linux && cmake --build build/linux --target z_generals"

For x86-64 on an arm64 host add `--platform linux/amd64` (and build into another directory, for
example `cmake --preset linux -B build/linux-x64`). The image uses clang with GCC's C++ library.

## Running a replay

Mount the game folders and point the game at them:

    docker run --rm -v "$PWD":/src -v <Zero Hour folder>:/game \
        -v "<user data folder>":"/root/Documents/Command and Conquer Generals Zero Hour Data" \
        -e SDL_VIDEODRIVER=offscreen -e SDL_AUDIODRIVER=dummy \
        -e GENERALS_ZH_PATH=/game -e GENERALS_PATH=/game/ZH_Generals -e GENERALS_CRC_LOG=1 \
        -w /game generals-linux /src/build/linux/GeneralsMD/generalszh -useCwd -headless -replay <name>.rep

`GENERALS_CRC_LOG=1` prints the game state CRCs; compare them with another platform's output.

## Running with graphics

Without a display, Xvfb and Mesa's software Vulkan driver (lavapipe) are enough to test:

    docker run --rm -v "$PWD":/src -v <Zero Hour folder>:/game \
        -v "<user data folder>":"/root/Documents/Command and Conquer Generals Zero Hour Data" \
        -e SDL_VIDEODRIVER=x11 -e SDL_AUDIODRIVER=dummy -e DISPLAY=:99 \
        -e GENERALS_ZH_PATH=/game -e GENERALS_PATH=/game/ZH_Generals -w /game generals-linux \
        sh -c "Xvfb :99 -screen 0 1280x800x24 & sleep 2; /src/build/linux/GeneralsMD/generalszh \
            -noaudio -win -xres 1280 -yres 800 -skirmish 'Tournament Desert' -observe -opponents 2"

On a desktop, run the executable directly with a Vulkan driver installed and DXVK on the library path.

`scripts/crossplay/check_replay_crc.sh <name>.rep` plays a replay on every platform build present
(macOS arm64 and x86-64, Linux arm64 and x86-64, Windows x64 under Wine) and checks that all of them
compute the same CRCs.

`scripts/crossplay/lan_match.sh` plays a live LAN game between the Linux build (host) and the Windows x64
build under Wine (joiner) with two AI players, and checks that both compute the same CRCs. The players
are driven by `GENERALS_LAN_TEST=host:<name>` or `join:<name>` (GameNetwork/LANAutoTest.h).

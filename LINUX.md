# Linux port (in progress)

Zero Hour builds natively on Linux (x86-64 and arm64) from the same code as the macOS port: the Win32
replacement layer in `Dependencies/Win32Shim` (SDL3), audio on SDL3 with dr_mp3 for MP3, and the
deterministic math in `Dependencies/DetMath`. Code shared by both ports is under `RTS_POSIX_PORT`
(C++) and `RTS_POSIX_PORT` (CMake); `cmake/posix.cmake` holds the shared build settings.

## Status

- Headless runs work, for example replays: `generalszh -headless -replay <name>.rep`.
- The simulation matches the other platforms bit for bit: a 12 minute four AI replay gives the same
  CRCs on macOS arm64, macOS x86-64, Linux arm64 and Linux x86-64.
- No graphics yet: `Dependencies/D3D8Null` provides Direct3D 8 without a device. The graphical build
  will use DXVK (Direct3D 8 on Vulkan), which also runs natively on Windows.
- Fonts have approximate metrics and draw nothing until the GDI layer renders with FreeType.

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

# Windows x64 build

Zero Hour builds as a 64-bit Windows program with clang and the MinGW-w64 runtime (llvm-mingw),
cross compiled in Docker. It runs on the Win32 API like the original game, with the cross platform
pieces of the macOS and Linux ports:

- Graphics: the game loads `D3D8.DLL` at run time. The build puts DXVK's `d3d8.dll` and `d3d9.dll`
  next to the executable, so Direct3D 8 runs on Vulkan. Without them Windows' own Direct3D 8 is used.
- Simulation: the same deterministic math as the other ports (`Dependencies/DetMath`, no fused
  multiply-add). A 12 minute four AI replay gives the same CRCs on Windows x64, macOS (arm64 and
  x86-64) and Linux (arm64 and x86-64), which is what crossplay needs.
- Audio: the SDL3 implementation of Miles from the other ports (`SDL3.dll` ships next to the game).
- D3DX 8: the implementation from the macOS port; the DirectX 8 SDK only provides headers here.
- No video playback yet (Bink is 32-bit only), no embedded browser, and crash reports list module
  offsets instead of function names.

## Building

    docker build -t generals-windows docker/windows
    docker run --rm -v "$PWD":/src -w /src generals-windows \
        sh -c "cmake --preset windows-x64 && cmake --build build/windows-x64 --target z_generals"

`build/windows-x64/GeneralsMD` then holds `generalszh.exe`, `SDL3.dll`, `d3d8.dll` and `d3d9.dll`.
Copy them into the Zero Hour folder, or start the game from that folder with `-useCwd`.

## Testing with Wine

`docker/windows-test` runs the build under Wine with Mesa's software Vulkan driver (build it with
`--platform linux/amd64`). The game finds its data through the registry, so import the install
paths first, for example from a file `generals.reg`:

    REGEDIT4

    [HKEY_LOCAL_MACHINE\SOFTWARE\Electronic Arts\EA Games\Command and Conquer Generals Zero Hour]
    "InstallPath"="Z:\\game\\"
    "Language"="english"

    [HKEY_LOCAL_MACHINE\SOFTWARE\Electronic Arts\EA Games\Generals]
    "InstallPath"="Z:\\game\\ZH_Generals\\"
    "Language"="english"

Then, with the Zero Hour folder mounted at `/game` and the build at `/out`:

    wine regedit /out/generals.reg
    WINEDLLOVERRIDES="d3d8,d3d9=n" GENERALS_CRC_LOG=1 \
        xvfb-run -a wine /out/generalszh.exe -useCwd -headless -replay <name>.rep

`WINEDLLOVERRIDES` makes Wine use DXVK's Direct3D instead of its own.

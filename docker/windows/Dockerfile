# Cross build environment for Windows x64: clang with the MinGW-w64 runtime (llvm-mingw), SDL3 for
# audio, and DXVK's Direct3D 8 (Vulkan) to ship next to the game.
FROM mstorsjo/llvm-mingw:latest
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        ninja-build git ca-certificates curl python3 \
    && rm -rf /var/lib/apt/lists/*
ARG SDL3_VERSION=3.4.18
RUN curl -fsSL https://github.com/libsdl-org/SDL/releases/download/release-${SDL3_VERSION}/SDL3-devel-${SDL3_VERSION}-mingw.tar.gz \
        | tar xz -C /opt \
    && mv /opt/SDL3-${SDL3_VERSION} /opt/sdl3
ARG DXVK_VERSION=3.1.1
RUN curl -fsSL https://github.com/doitsujin/dxvk/releases/download/v${DXVK_VERSION}/dxvk-${DXVK_VERSION}.tar.gz \
        | tar xz -C /opt \
    && mv /opt/dxvk-${DXVK_VERSION} /opt/dxvk-windows
ENV SDL3_DIR=/opt/sdl3/x86_64-w64-mingw32/lib/cmake/SDL3 DXVK_WINDOWS_DIR=/opt/dxvk-windows

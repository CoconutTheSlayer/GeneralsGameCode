# Build environment for the native Linux port: clang with GCC's C++ library (libstdc++), so builds
# here also show where the simulation depends on the C++ library.
FROM debian:trixie
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        clang clang-tools lld cmake ninja-build git ca-certificates pkg-config python3 \
        libsdl3-dev zlib1g-dev \
        meson glslang-tools libvulkan-dev \
        mesa-vulkan-drivers vulkan-tools xvfb xauth x11-utils imagemagick python3-pil \
    && rm -rf /var/lib/apt/lists/*
ENV CC=clang CXX=clang++

# DXVK native: Direct3D 8 (on its Direct3D 9) over Vulkan, with SDL3 windows.
ARG DXVK_VERSION=v3.1.1
RUN git clone --depth 1 --branch ${DXVK_VERSION} --recurse-submodules --shallow-submodules https://github.com/doitsujin/dxvk.git /tmp/dxvk \
    && cd /tmp/dxvk \
    && meson setup build --buildtype release --prefix /opt/dxvk \
        -Denable_d3d8=true -Denable_d3d9=true -Denable_d3d10=false -Denable_d3d11=false -Denable_dxgi=false \
        -Dnative_sdl3=enabled -Dnative_sdl2=disabled -Dnative_glfw=disabled \
    && ninja -C build install \
    && rm -rf /tmp/dxvk
ENV DXVK_DIR=/opt/dxvk
ENV LD_LIBRARY_PATH=/opt/dxvk/lib
WORKDIR /src

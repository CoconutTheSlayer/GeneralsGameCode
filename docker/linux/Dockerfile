# Build environment for the native Linux port: clang with GCC's C++ library (libstdc++), so builds
# here also show where the simulation depends on the C++ library.
FROM debian:trixie
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        clang clang-tools lld cmake ninja-build git ca-certificates pkg-config \
        libsdl3-dev zlib1g-dev \
    && rm -rf /var/lib/apt/lists/*
ENV CC=clang CXX=clang++
WORKDIR /src

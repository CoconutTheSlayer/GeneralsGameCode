# Cross builds the launcher (launcher/) for Windows x64 with the MSVC target through cargo-xwin, and
# packages it with NSIS:
#   docker build -t generals-launcher-windows docker/launcher-windows
#   docker run --rm -v "$PWD/launcher":/src -w /src generals-launcher-windows
FROM rust:1-trixie
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        clang lld llvm nsis nodejs npm \
    && rm -rf /var/lib/apt/lists/*
RUN rustup target add x86_64-pc-windows-msvc && cargo install --locked cargo-xwin
ENV CARGO_TARGET_DIR=/src/src-tauri/target-windows
CMD ["sh", "-c", "npm ci && npx tauri build --runner cargo-xwin --target x86_64-pc-windows-msvc --bundles nsis"]

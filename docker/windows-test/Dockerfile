# Runs the Windows x64 build under Wine, with Mesa's software Vulkan driver for DXVK and Xvfb as
# the display. Build for linux/amd64.
FROM debian:trixie
RUN dpkg --add-architecture i386 && apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends \
        wine wine64 xvfb xauth x11-utils imagemagick mesa-vulkan-drivers ca-certificates \
    && rm -rf /var/lib/apt/lists/*
ENV WINEDEBUG=-all WINEPREFIX=/root/.wine
RUN xvfb-run -a wineboot --init 2>/dev/null; wineserver -w; true

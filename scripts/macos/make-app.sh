#!/usr/bin/env bash
#
# Packages the native macOS builds of Zero Hour and Generals as application bundles.
#
# Usage: scripts/macos/make-app.sh [build directory] [output directory]
#   build directory   defaults to build/macos
#   output directory  defaults to the build directory
#
# The bundle links against the SDL3 and FFmpeg libraries from Homebrew.

set -euo pipefail

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" &>/dev/null && pwd)"
PROJECT_DIR="$(cd "$SCRIPT_DIR/../.." && pwd)"
BUILD_DIR="${1:-$PROJECT_DIR/build/macos}"
OUT_DIR="${2:-$BUILD_DIR}"
make_app() {
    local BINARY="$1" APP="$2" EXE="$3" ICON_SRC="$4" BUNDLE_NAME="$5" DISPLAY_NAME="$6" BUNDLE_ID="$7"

    rm -rf "$APP"
    mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
    cp "$BINARY" "$APP/Contents/MacOS/$EXE"

    local ICON_NAME=""
    if [[ -f "$ICON_SRC" ]] && sips -s format icns "$ICON_SRC" --out "$APP/Contents/Resources/AppIcon.icns" >/dev/null 2>&1; then
        ICON_NAME="AppIcon"
    fi

    cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>${BUNDLE_NAME}</string>
    <key>CFBundleDisplayName</key>
    <string>${DISPLAY_NAME}</string>
    <key>CFBundleIdentifier</key>
    <string>${BUNDLE_ID}</string>
    <key>CFBundleExecutable</key>
    <string>${EXE}</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
    <key>CFBundleShortVersionString</key>
    <string>1.04</string>
    <key>CFBundleVersion</key>
    <string>1</string>
    <key>CFBundleIconFile</key>
    <string>${ICON_NAME}</string>
    <key>LSMinimumSystemVersion</key>
    <string>13.0</string>
    <key>LSApplicationCategoryType</key>
    <string>public.app-category.strategy-games</string>
    <key>NSHighResolutionCapable</key>
    <true/>
    <key>GCSupportsGameMode</key>
    <true/>
</dict>
</plist>
PLIST

    # Ad-hoc signature so Gatekeeper on Apple Silicon allows running the local build.
    codesign --force --deep --sign - "$APP" >/dev/null 2>&1 || true
    echo "Created $APP"
}

CREATED=0
if [[ -x "$BUILD_DIR/GeneralsMD/generalszh" ]]; then
    make_app "$BUILD_DIR/GeneralsMD/generalszh" "$OUT_DIR/Command and Conquer Generals Zero Hour.app" generalszh \
        "$PROJECT_DIR/GeneralsMD/Code/Main/Generals.ico" "Zero Hour" "Command &amp; Conquer Generals Zero Hour" com.thesuperhackers.generalszh
    CREATED=1
fi
if [[ -x "$BUILD_DIR/Generals/generalsv" ]]; then
    make_app "$BUILD_DIR/Generals/generalsv" "$OUT_DIR/Command and Conquer Generals.app" generalsv \
        "$PROJECT_DIR/Generals/Code/Main/Generals.ico" "Generals" "Command &amp; Conquer Generals" com.thesuperhackers.generals
    CREATED=1
fi
if [[ $CREATED -eq 0 ]]; then
    echo "error: no game executables in $BUILD_DIR; build first with: cmake --workflow --preset macos" >&2
    exit 1
fi

#!/usr/bin/env bash
#
# Packages the native macOS build of Zero Hour as an application bundle.
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
BINARY="$BUILD_DIR/GeneralsMD/generalszh"
APP="$OUT_DIR/Command and Conquer Generals Zero Hour.app"

if [[ ! -x "$BINARY" ]]; then
    echo "error: $BINARY not found; build first with: cmake --workflow --preset macos" >&2
    exit 1
fi

rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$BINARY" "$APP/Contents/MacOS/generalszh"

ICON_SRC="$PROJECT_DIR/GeneralsMD/Code/Main/Generals.ico"
ICON_NAME=""
if [[ -f "$ICON_SRC" ]] && sips -s format icns "$ICON_SRC" --out "$APP/Contents/Resources/Generals.icns" >/dev/null 2>&1; then
    ICON_NAME="Generals"
fi

cat > "$APP/Contents/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Zero Hour</string>
    <key>CFBundleDisplayName</key>
    <string>Command &amp; Conquer Generals Zero Hour</string>
    <key>CFBundleIdentifier</key>
    <string>com.thesuperhackers.generalszh</string>
    <key>CFBundleExecutable</key>
    <string>generalszh</string>
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

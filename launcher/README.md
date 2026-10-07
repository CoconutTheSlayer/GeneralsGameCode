# Warroom launcher

A desktop launcher (Tauri 2: Rust backend in `src-tauri`, TypeScript window in `src`) for online
games through the relay: sign in through Steam, pick or create a room in the server browser, and the
game starts straight in that room's lobby (`-online`). "Warroom" is a working name.

    npm install
    npx tauri dev                    # run while developing
    npx tauri build --bundles app    # macOS app (msi/nsis on Windows, deb/appimage on Linux)

Settings (relay, room list, login service, game client and data folder) are kept in the app's config
folder (`~/Library/Application Support/org.warroom.launcher/settings.json` on macOS) and edited in the
window; `WARROOM_RELAY`, `WARROOM_RELAY_HTTP`, `WARROOM_AUTH`, `WARROOM_GAME` and `WARROOM_GAME_DIR` set
the defaults. For local services see `server/compose.yaml`.

The launcher finds Zero Hour's data (the folder with `INIZH.big`) in the Steam libraries or uses
the folder chosen in the settings; it does not download EA's game data. Downloading and updating the
game client, and signed builds, come next.

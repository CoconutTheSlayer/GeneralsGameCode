//! The launcher's backend: Steam sign in, settings, finding the game data and starting the game in a
//! relay room. The window (src/) shows the server browser.

use serde::{Deserialize, Serialize};
use std::fs;
use std::io::{Read, Write};
use std::net::TcpListener;
use std::path::{Path, PathBuf};
use std::process::Command;
use std::time::{Duration, Instant, SystemTime, UNIX_EPOCH};
use tauri::{AppHandle, Manager};
use tauri_plugin_opener::OpenerExt;

/// Where the online services are and where the game is. Kept in the app's config folder.
#[derive(Serialize, Deserialize, Clone, Debug)]
#[serde(default)]
pub struct Settings {
    /// UDP address of the relay, host:port.
    relay: String,
    /// HTTP address of the relay's room list.
    relay_http: String,
    /// The login service.
    auth_url: String,
    /// The game client: the generalszh executable, or the macOS application bundle.
    game_executable: String,
    /// The Zero Hour data folder (with INIZH.big).
    game_dir: String,
}

impl Default for Settings {
    fn default() -> Self {
        // WARROOM_* override the defaults, for development against local services.
        let env = |key: &str, default: &str| std::env::var(key).unwrap_or_else(|_| default.to_string());
        Settings {
            relay: env("WARROOM_RELAY", "relay.example.org:7900"),
            relay_http: env("WARROOM_RELAY_HTTP", "https://relay.example.org"),
            auth_url: env("WARROOM_AUTH", "https://auth.example.org"),
            game_executable: env("WARROOM_GAME", ""),
            game_dir: env("WARROOM_GAME_DIR", ""),
        }
    }
}

/// The signed in player.
#[derive(Serialize, Clone, Debug)]
pub struct Session {
    steam_id: String,
    token: String,
    expires: u64,
}

fn config_dir(app: &AppHandle) -> Result<PathBuf, String> {
    let dir = app.path().app_config_dir().map_err(|e| e.to_string())?;
    fs::create_dir_all(&dir).map_err(|e| e.to_string())?;
    Ok(dir)
}

fn now() -> u64 {
    SystemTime::now().duration_since(UNIX_EPOCH).map(|d| d.as_secs()).unwrap_or(0)
}

/// Tokens are player.expiry.signature (server/internal/token).
fn parse_token(token: &str) -> Option<Session> {
    let mut parts = token.trim().split('.');
    let steam_id = parts.next()?.to_string();
    let expires: u64 = parts.next()?.parse().ok()?;
    parts.next()?;
    Some(Session { steam_id, token: token.trim().to_string(), expires })
}

#[tauri::command]
fn load_settings(app: AppHandle) -> Settings {
    config_dir(&app)
        .ok()
        .and_then(|dir| fs::read_to_string(dir.join("settings.json")).ok())
        .and_then(|text| serde_json::from_str(&text).ok())
        .unwrap_or_default()
}

#[tauri::command]
fn save_settings(app: AppHandle, settings: Settings) -> Result<(), String> {
    let text = serde_json::to_string_pretty(&settings).map_err(|e| e.to_string())?;
    fs::write(config_dir(&app)?.join("settings.json"), text).map_err(|e| e.to_string())
}

/// The kept sign in, if it lasts at least another hour.
#[tauri::command]
fn session(app: AppHandle) -> Option<Session> {
    let text = fs::read_to_string(config_dir(&app).ok()?.join("session.txt")).ok()?;
    parse_token(&text).filter(|s| s.expires > now() + 3600)
}

#[tauri::command]
fn sign_out(app: AppHandle) -> Result<(), String> {
    let path = config_dir(&app)?.join("session.txt");
    if path.exists() {
        fs::remove_file(path).map_err(|e| e.to_string())?;
    }
    Ok(())
}

/// Waits for the browser to come back to http://127.0.0.1:port/token?t=..., like the game does.
fn wait_for_token(listener: TcpListener) -> Result<String, String> {
    listener.set_nonblocking(true).map_err(|e| e.to_string())?;
    let deadline = Instant::now() + Duration::from_secs(300);
    while Instant::now() < deadline {
        let (mut stream, _) = match listener.accept() {
            Ok(connection) => connection,
            Err(e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                std::thread::sleep(Duration::from_millis(100));
                continue;
            }
            Err(e) => return Err(e.to_string()),
        };
        stream.set_nonblocking(false).ok();
        stream.set_read_timeout(Some(Duration::from_secs(5))).ok();
        let mut request = [0u8; 4096];
        let n = stream.read(&mut request).unwrap_or(0);
        let request = String::from_utf8_lossy(&request[..n]);
        let token = request
            .lines()
            .next()
            .and_then(|line| line.strip_prefix("GET /token?t="))
            .and_then(|rest| rest.split([' ', '&']).next())
            .map(|t| t.replace("%2E", ".").replace("%2e", "."));
        let text = if token.is_some() { "Signed in. You can go back to the launcher." } else { "This page is for the launcher's sign in." };
        let _ = write!(
            stream,
            "HTTP/1.1 200 OK\r\nContent-Type: text/html; charset=utf-8\r\nConnection: close\r\n\r\n\
             <!doctype html><title>Warroom</title><p style=\"font:18px sans-serif;margin:4em\">{text}</p>"
        );
        if let Some(token) = token {
            return Ok(token);
        }
    }
    Err("The sign in did not finish in time.".into())
}

/// Signs in with Steam in the browser through the login service.
#[tauri::command]
async fn sign_in(app: AppHandle) -> Result<Session, String> {
    let settings = load_settings(app.clone());
    let listener = TcpListener::bind("127.0.0.1:0").map_err(|e| e.to_string())?;
    let port = listener.local_addr().map_err(|e| e.to_string())?.port();
    let url = format!("{}/login?port={}", settings.auth_url.trim_end_matches('/'), port);
    app.opener().open_url(url, None::<&str>).map_err(|e| e.to_string())?;
    let token = tauri::async_runtime::spawn_blocking(move || wait_for_token(listener))
        .await
        .map_err(|e| e.to_string())??;
    let session = parse_token(&token).ok_or("The login service sent a bad token.")?;
    fs::write(config_dir(&app)?.join("session.txt"), &session.token).map_err(|e| e.to_string())?;
    Ok(session)
}

/// Zero Hour's data folder holds INIZH.big; the base game (INI.big) is in ZH_Generals inside it or
/// next to it.
#[derive(Serialize, Debug)]
pub struct GameFolder {
    zero_hour: String,
    generals: Option<String>,
}

fn check_game_dir(dir: &Path) -> Option<GameFolder> {
    if !dir.join("INIZH.big").is_file() {
        return None;
    }
    let mut candidates = vec![dir.join("ZH_Generals")];
    if let Some(parent) = dir.parent() {
        if let Ok(entries) = fs::read_dir(parent) {
            candidates.extend(entries.flatten().map(|e| e.path()));
        }
    }
    let generals = candidates.into_iter().find(|c| c.join("INI.big").is_file());
    Some(GameFolder {
        zero_hour: dir.to_string_lossy().into_owned(),
        generals: generals.map(|g| g.to_string_lossy().into_owned()),
    })
}

/// Steam libraries from libraryfolders.vdf.
fn steam_libraries() -> Vec<PathBuf> {
    let home = std::env::var("HOME").or_else(|_| std::env::var("USERPROFILE")).unwrap_or_default();
    let roots = [
        PathBuf::from(r"C:\Program Files (x86)\Steam"),
        PathBuf::from(&home).join(".steam/steam"),
        PathBuf::from(&home).join(".local/share/Steam"),
        PathBuf::from(&home).join("Library/Application Support/Steam"),
    ];
    let mut libraries = Vec::new();
    for root in roots.iter().filter(|r| r.is_dir()) {
        libraries.push(root.clone());
        if let Ok(vdf) = fs::read_to_string(root.join("steamapps/libraryfolders.vdf")) {
            for line in vdf.lines() {
                let mut fields = line.split('"').filter(|f| !f.trim().is_empty());
                if fields.next() == Some("path") {
                    if let Some(path) = fields.next() {
                        libraries.push(PathBuf::from(path.replace("\\\\", "\\")));
                    }
                }
            }
        }
    }
    libraries
}

/// Looks for the game data: the folder from the settings, Steam's libraries, then usual places.
#[tauri::command]
fn find_game(app: AppHandle) -> Option<GameFolder> {
    let settings = load_settings(app);
    if !settings.game_dir.is_empty() {
        if let Some(found) = check_game_dir(Path::new(&settings.game_dir)) {
            return Some(found);
        }
    }
    for library in steam_libraries() {
        if let Ok(entries) = fs::read_dir(library.join("steamapps/common")) {
            for entry in entries.flatten() {
                if let Some(found) = check_game_dir(&entry.path()) {
                    return Some(found);
                }
            }
        }
    }
    let home = std::env::var("HOME").unwrap_or_default();
    check_game_dir(&PathBuf::from(home).join("Games/GeneralsZH"))
}

#[tauri::command]
fn check_game_folder(path: String) -> Option<GameFolder> {
    check_game_dir(Path::new(&path))
}

/// Starts the game straight into the LAN lobby of a relay room.
#[tauri::command]
fn launch_game(app: AppHandle, room: String, player_name: String) -> Result<(), String> {
    let settings = load_settings(app.clone());
    let session = session(app.clone()).ok_or("Sign in first.")?;
    let folder = find_game(app).ok_or("The Zero Hour game data was not found.")?;
    let mut executable = PathBuf::from(&settings.game_executable);
    if executable.extension().is_some_and(|e| e == "app") {
        executable = executable.join("Contents/MacOS/generalszh");
    }
    if !executable.is_file() {
        return Err("The game client was not found; set it in the settings.".into());
    }
    let mut command = Command::new(&executable);
    command
        .args(["-online", "-nologo"])
        .current_dir(&folder.zero_hour)
        .env("GENERALS_RELAY", &settings.relay)
        .env("GENERALS_RELAY_TOKEN", &session.token)
        .env("GENERALS_RELAY_ROOM", &room)
        .env("GENERALS_PLAYER_NAME", &player_name)
        .env("GENERALS_ZH_PATH", &folder.zero_hour);
    if let Some(generals) = &folder.generals {
        command.env("GENERALS_PATH", generals);
    }
    command.spawn().map_err(|e| format!("Could not start the game: {e}"))?;
    Ok(())
}

#[cfg_attr(mobile, tauri::mobile_entry_point)]
pub fn run() {
    tauri::Builder::default()
        .plugin(tauri_plugin_opener::init())
        .plugin(tauri_plugin_dialog::init())
        .invoke_handler(tauri::generate_handler![
            load_settings,
            save_settings,
            session,
            sign_in,
            sign_out,
            find_game,
            check_game_folder,
            launch_game
        ])
        .run(tauri::generate_context!())
        .expect("error while running the launcher");
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parses_tokens() {
        let s = parse_token("76561197960287930.1999999999.abcdef\n").unwrap();
        assert_eq!(s.steam_id, "76561197960287930");
        assert_eq!(s.expires, 1999999999);
        assert!(parse_token("garbage").is_none());
    }

    #[test]
    fn finds_game_folders() {
        let root = std::env::temp_dir().join(format!("warroom-test-{}", now()));
        let zh = root.join("ZeroHour");
        fs::create_dir_all(zh.join("ZH_Generals")).unwrap();
        fs::write(zh.join("INIZH.big"), b"").unwrap();
        fs::write(zh.join("ZH_Generals/INI.big"), b"").unwrap();
        let found = check_game_dir(&zh).unwrap();
        assert!(found.generals.unwrap().ends_with("ZH_Generals"));
        assert!(check_game_dir(&root).is_none());
        fs::remove_dir_all(root).unwrap();
    }
}

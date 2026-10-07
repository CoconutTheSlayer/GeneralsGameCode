import { invoke } from "@tauri-apps/api/core";
import { open } from "@tauri-apps/plugin-dialog";

interface Settings {
  relay: string;
  relay_http: string;
  auth_url: string;
  game_executable: string;
  game_dir: string;
}
interface Session {
  steam_id: string;
  token: string;
  expires: number;
}
interface GameFolder {
  zero_hour: string;
  generals: string | null;
}
interface Room {
  name: string;
  players: string[];
  max: number;
}
interface Profile {
  steamid: string;
  name: string;
  avatar?: string;
}

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;

let settings: Settings;
let session: Session | null = null;
let game: GameFolder | null = null;
const profiles = new Map<string, Profile>();

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

let toastTimer = 0;
function toast(message: string, kind: "info" | "error" = "info") {
  const el = $("toast");
  el.textContent = message;
  el.className = `toast show ${kind}`;
  clearTimeout(toastTimer);
  toastTimer = window.setTimeout(() => (el.className = "toast"), 5000);
}

// Names and avatars of Steam accounts, from the login service.
async function loadProfiles(ids: string[]) {
  const missing = ids.filter((id) => !profiles.has(id) && /^\d{17}$/.test(id));
  if (missing.length === 0) return;
  try {
    const res = await fetch(`${settings.auth_url}/profiles?ids=${missing.join(",")}`);
    for (const p of (await res.json()) as Profile[]) profiles.set(p.steamid, p);
  } catch {
    // Names stay as ids until the service answers.
  }
}

function displayName(id: string): string {
  return profiles.get(id)?.name ?? id;
}

function avatar(id: string, size = "sm"): string {
  const p = profiles.get(id);
  const initial = escapeHtml((p?.name ?? "?").slice(0, 1).toUpperCase());
  return p?.avatar
    ? `<img class="avatar ${size}" src="${escapeHtml(p.avatar)}" alt="" />`
    : `<span class="avatar ${size} blank" aria-hidden="true">${initial}</span>`;
}

function renderAccount() {
  const el = $("account");
  if (!session) {
    el.innerHTML = `<button class="steam" id="sign-in"><span class="steam-logo" aria-hidden="true"></span>Sign in through Steam</button>`;
    $("sign-in").onclick = signIn;
    return;
  }
  el.innerHTML = `${avatar(session.steam_id, "md")}<span class="who">${escapeHtml(displayName(session.steam_id))}</span><button class="link" id="sign-out">Sign out</button>`;
  $("sign-out").onclick = async () => {
    await invoke("sign_out");
    session = null;
    renderAccount();
  };
}

async function signIn() {
  const button = $<HTMLButtonElement>("sign-in");
  button.disabled = true;
  button.textContent = "Waiting for Steam in your browser…";
  try {
    session = await invoke<Session>("sign_in");
    await loadProfiles([session.steam_id]);
    toast(`Signed in as ${displayName(session.steam_id)}`);
  } catch (e) {
    toast(String(e), "error");
  }
  renderAccount();
}

function renderChecks() {
  const exe = settings.game_executable;
  const rows: [string, boolean, string][] = [
    ["Steam account", !!session, session ? displayName(session.steam_id) : "not signed in"],
    ["Zero Hour data", !!game, game ? game.zero_hour : "not found — set the folder in Settings"],
    ["Base game data", !!game?.generals, game?.generals ?? "not found next to Zero Hour"],
    ["Game client", exe !== "", exe || "not set — set it in Settings"],
  ];
  $("checks").innerHTML = rows
    .map(([label, ok, detail]) => `<dt><span class="dot ${ok ? "ok" : "bad"}"></span>${label}</dt><dd title="${escapeHtml(detail)}">${escapeHtml(detail)}</dd>`)
    .join("");
}

async function join(room: string) {
  if (!session) {
    toast("Sign in through Steam first.", "error");
    return;
  }
  try {
    await invoke("launch_game", { room, playerName: displayName(session.steam_id).slice(0, 12) });
    toast(`Starting the game in room “${room}”…`);
  } catch (e) {
    toast(String(e), "error");
  }
}

function renderRooms(rooms: Room[]) {
  const list = $("rooms");
  if (rooms.length === 0) {
    list.innerHTML = `<li class="empty">No rooms yet. Create one and invite your friends to it.</li>`;
    return;
  }
  list.innerHTML = rooms
    .map((room) => {
      const full = room.players.length >= room.max;
      const players = room.players.map((id) => `<li>${avatar(id)}<span>${escapeHtml(displayName(id))}</span></li>`).join("");
      return `<li class="room">
        <div class="room-main">
          <h3>${escapeHtml(room.name)}</h3>
          <ul class="players">${players}</ul>
        </div>
        <div class="room-side">
          <span class="count ${full ? "full" : ""}">${room.players.length}<small>/${room.max}</small></span>
          <button class="primary" data-room="${escapeHtml(room.name)}" ${full ? "disabled" : ""}>${full ? "Full" : "Join"}</button>
        </div>
      </li>`;
    })
    .join("");
  list.querySelectorAll<HTMLButtonElement>("button[data-room]").forEach((b) => (b.onclick = () => join(b.dataset.room!)));
}

async function refreshRooms() {
  const live = $("live");
  try {
    const res = await fetch(`${settings.relay_http}/rooms`);
    const rooms = (await res.json()) as Room[];
    await loadProfiles(rooms.flatMap((r) => r.players));
    renderRooms(rooms);
    const players = rooms.reduce((n, r) => n + r.players.length, 0);
    live.textContent = `${players} online`;
    live.className = "live on";
  } catch {
    live.textContent = "relay offline";
    live.className = "live off";
  }
}

function openSettings() {
  const form = $<HTMLFormElement>("settings-form");
  for (const [key, value] of Object.entries(settings)) {
    const input = form.elements.namedItem(key) as HTMLInputElement | null;
    if (input) input.value = value;
  }
  $<HTMLDialogElement>("settings").showModal();
}

async function closeSettings(event: Event) {
  const dialog = $<HTMLDialogElement>("settings");
  if (dialog.returnValue !== "save") return;
  const form = $<HTMLFormElement>("settings-form");
  const next = { ...settings };
  for (const key of Object.keys(settings) as (keyof Settings)[]) {
    next[key] = (form.elements.namedItem(key) as HTMLInputElement).value.trim();
  }
  try {
    await invoke("save_settings", { settings: next });
    settings = next;
    game = await invoke<GameFolder | null>("find_game");
    renderChecks();
    refreshRooms();
  } catch (e) {
    toast(String(e), "error");
  }
  event.preventDefault();
}

async function pick(button: HTMLButtonElement) {
  const directory = button.dataset.directory === "true";
  const chosen = await open({ directory, multiple: false });
  if (typeof chosen === "string") {
    (($<HTMLFormElement>("settings-form").elements.namedItem(button.dataset.pick!)) as HTMLInputElement).value = chosen;
  }
}

async function main() {
  settings = await invoke<Settings>("load_settings");
  session = await invoke<Session | null>("session");
  game = await invoke<GameFolder | null>("find_game");
  if (session) await loadProfiles([session.steam_id]);
  renderAccount();
  renderChecks();

  $("open-settings").onclick = openSettings;
  $("settings").addEventListener("close", closeSettings);
  document.querySelectorAll<HTMLButtonElement>("button[data-pick]").forEach((b) => (b.onclick = () => pick(b)));
  $("create-form").addEventListener("submit", (e) => {
    e.preventDefault();
    const name = $<HTMLInputElement>("room-name").value.trim();
    if (name) join(name);
  });

  await refreshRooms();
  setInterval(refreshRooms, 5000);
  setInterval(renderChecks, 5000);
}

main();

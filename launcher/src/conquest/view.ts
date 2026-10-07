// The world conquest screen: the world map, the campaign panel and running battles in the game.

import { invoke } from "@tauri-apps/api/core";
import { GENERALS, NEIGHBOURS, SEA_LANES, SITES, TERRITORIES, type Territory } from "./data";
import {
  MERCENARY_COST, WORLD_VERSION, applyBattle, autoResolve, battleFile, endTurn, getGeneral, getTerritory, income,
  newCampaign, planBattle, targetsFrom, territoriesOf, type Battle, type Campaign, type Difficulty,
} from "./campaign";
import { LAND_PATH } from "./world";

const $ = <T extends HTMLElement>(id: string) => document.getElementById(id) as T;
const x = (t: Territory) => (t.lon + 180) * 4;
const y = (t: Territory) => (85 - t.lat) * 4;

function escapeHtml(text: string): string {
  return text.replace(/[&<>"']/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" })[c]!);
}

let campaign: Campaign | null = null;
let selected: string | null = null;
let target: string | null = null;
let mercenary = false;
let busy = false;
let confirmRestart = false;
let notify: (message: string, kind?: "info" | "error") => void = () => {};

async function save() {
  if (campaign) await invoke("save_campaign", { campaign: JSON.stringify(campaign) });
}

// ---------------------------------------------------------------------------------------------
// Map

// The part of the map in view, in map units. HOME shows every territory.
const HOME = { x: 190, y: 40, w: 1170, h: 470 };
const MAP = { w: 1440, h: 600 };
let view = { ...HOME };
let dragged = false;
let frame = 0;

const zoom = () => HOME.w / view.w;

function label(t: Territory, r: number, z: number): string {
  const gap = 6 / z;
  const [dx, dy, anchor] = {
    above: [0, -r - gap, "middle"],
    left: [-r - gap, 4 / z, "end"],
    right: [r + gap, 4 / z, "start"],
    below: [0, r + 12 / z, "middle"],
  }[t.label ?? "below"] as [number, number, string];
  const minor = t.value === 1 ? " minor" : "";
  return `<text class="label${minor}" x="${x(t) + dx}" y="${y(t) + dy}" text-anchor="${anchor}">${escapeHtml(t.name)}</text>`;
}

/** Builds the map once; the territories are drawn by renderMap. */
function buildMap() {
  const svg = $("world");
  if (svg.dataset.built) return;
  svg.dataset.built = "1";
  svg.innerHTML = `<path class="land" d="${LAND_PATH}"/><g id="links"></g><g id="nodes"></g>`;
  $("nodes").addEventListener("click", (e) => {
    const node = (e.target as Element).closest<SVGGElement>(".node");
    if (node && !dragged) clickTerritory(node.dataset.id!);
  });

  // Wheel zooms around the pointer, dragging pans, double click zooms in.
  const toMap = (clientX: number, clientY: number) => {
    const ctm = (svg as unknown as SVGGraphicsElement).getScreenCTM()!.inverse();
    const p = new DOMPoint(clientX, clientY).matrixTransform(ctm);
    return { x: p.x, y: p.y };
  };
  svg.addEventListener("wheel", (e) => {
    e.preventDefault();
    const p = toMap(e.clientX, e.clientY);
    zoomAt(p.x, p.y, Math.exp(-e.deltaY * 0.0018));
  }, { passive: false });
  svg.addEventListener("dblclick", (e) => {
    const p = toMap(e.clientX, e.clientY);
    zoomAt(p.x, p.y, 1.8);
  });
  let drag: { x: number; y: number; vx: number; vy: number; scale: number } | null = null;
  svg.addEventListener("pointerdown", (e) => {
    const ctm = (svg as unknown as SVGGraphicsElement).getScreenCTM()!;
    drag = { x: e.clientX, y: e.clientY, vx: view.x, vy: view.y, scale: ctm.a };
    dragged = false;
  });
  svg.addEventListener("pointermove", (e) => {
    if (!drag || e.buttons === 0) return;
    const dx = e.clientX - drag.x, dy = e.clientY - drag.y;
    if (!dragged && Math.hypot(dx, dy) < 5) return;
    if (!dragged) svg.setPointerCapture(e.pointerId);
    dragged = true;
    svg.classList.add("dragging");
    setView(drag.vx - dx / drag.scale, drag.vy - dy / drag.scale, view.w);
  });
  const end = () => {
    drag = null;
    svg.classList.remove("dragging");
  };
  svg.addEventListener("pointerup", end);
  svg.addEventListener("pointercancel", end);

  $("zoom-in").addEventListener("click", () => zoomAt(view.x + view.w / 2, view.y + view.h / 2, 1.6));
  $("zoom-out").addEventListener("click", () => zoomAt(view.x + view.w / 2, view.y + view.h / 2, 1 / 1.6));
  $("zoom-reset").addEventListener("click", () => setView(HOME.x, HOME.y, HOME.w));
}

function zoomAt(px: number, py: number, factor: number) {
  const w = Math.min(HOME.w, Math.max(160, view.w / factor));
  const k = w / view.w;
  setView(px - (px - view.x) * k, py - (py - view.y) * k, w);
}

function setView(vx: number, vy: number, w: number) {
  const h = (w * HOME.h) / HOME.w;
  view = {
    x: Math.min(MAP.w - w, Math.max(0, vx)),
    y: Math.min(MAP.h - h, Math.max(0, vy)),
    w,
    h,
  };
  cancelAnimationFrame(frame);
  frame = requestAnimationFrame(renderMap);
}

function renderMap() {
  if (!campaign) return;
  buildMap();
  const svg = $("world");
  const z = zoom();
  svg.setAttribute("viewBox", `${view.x} ${view.y} ${view.w} ${view.h}`);
  svg.style.setProperty("--zoom", String(z));
  svg.classList.toggle("close", z >= 1.7);
  $("zoom-level").textContent = `${Math.round(z * 100)}%`;

  const c = campaign;
  const targets = selected ? new Set(targetsFrom(c, selected)) : new Set<string>();
  const links: string[] = [];
  const drawn = new Set<string>();
  for (const t of TERRITORIES) {
    for (const n of NEIGHBOURS[t.id]) {
      const key = [t.id, n].sort().join("|");
      if (drawn.has(key)) continue;
      drawn.add(key);
      const o = getTerritory(n);
      const sea = SEA_LANES.has(key) ? " sea" : "";
      const active = selected && ((t.id === selected && targets.has(n)) || (n === selected && targets.has(t.id))) ? " active" : "";
      // Lanes across the date line (Alaska to Russia) go out of the map's edges.
      if (Math.abs(t.lon - o.lon) > 180) {
        const [w, e] = t.lon < o.lon ? [t, o] : [o, t];
        links.push(`<line class="link${sea}${active}" x1="${x(w)}" y1="${y(w)}" x2="${x(e) - MAP.w}" y2="${y(e)}"/>`);
        links.push(`<line class="link${sea}${active}" x1="${x(e)}" y1="${y(e)}" x2="${x(w) + MAP.w}" y2="${y(w)}"/>`);
      } else {
        links.push(`<line class="link${sea}${active}" x1="${x(t)}" y1="${y(t)}" x2="${x(o)}" y2="${y(o)}"/>`);
      }
    }
  }
  $("links").innerHTML = links.join("");

  // Markers shrink a little when zoomed in, so close territories stay apart.
  const scale = 1 / Math.sqrt(z);
  $("nodes").innerHTML = TERRITORIES.map((t) => {
    const owner = getGeneral(c.owners[t.id]);
    const mine = owner.id === c.player;
    const classes = ["node", mine ? "mine" : "", t.id === selected ? "selected" : "", targets.has(t.id) ? "target" : "", t.id === target ? "aimed" : "", c.defense?.target === t.id ? "threat" : ""].join(" ");
    const r = (4 + t.value * 2.4) * scale;
    const site = t.site ? `<text class="site" x="${x(t)}" y="${y(t) + 3.5 / z}">${{ oil: "⛽", airbase: "✈", nuclear: "☢", capital: "★" }[t.site]}</text>` : "";
    return `<g class="${classes}" data-id="${t.id}">
      <title>${escapeHtml(t.name)} — ${escapeHtml(owner.name)}</title>
      <circle class="halo" cx="${x(t)}" cy="${y(t)}" r="${r + 4 / z}"/>
      <circle class="dot" cx="${x(t)}" cy="${y(t)}" r="${r}" style="fill:${owner.color}"/>
      ${site}
      ${label(t, r, z)}
    </g>`;
  }).join("");
}

function clickTerritory(id: string) {
  if (!campaign || busy || campaign.outcome !== "playing") return;
  const c = campaign;
  if (c.owners[id] === c.player) {
    selected = selected === id ? null : id;
    target = null;
  } else if (selected && targetsFrom(c, selected).includes(id)) {
    target = id;
  } else {
    // An enemy territory: attack it from one of ours next to it, if any.
    const from = NEIGHBOURS[id].find((n) => c.owners[n] === c.player);
    selected = from ?? null;
    target = from ? id : null;
  }
  render();
}

// ---------------------------------------------------------------------------------------------
// Panel

function slotRow(b: Battle, i: number): string {
  const s = b.slots[i];
  const g = getGeneral(s.general);
  const who = s.controller === "human" ? "You" : `${s.controller[0].toUpperCase()}${s.controller.slice(1)} AI`;
  return `<li class="slot team${s.team}"><span class="swatch" style="background:${g.color}"></span><span>${escapeHtml(g.name)}</span><small>${who} · ${escapeHtml(s.role)}</small></li>`;
}

function battlePreview(b: Battle): string {
  const t = getTerritory(b.target);
  const rows = b.slots.map((_, i) => slotRow(b, i)).join("");
  return `<div class="preview">
    <div class="preview-head"><span>Battle for</span><strong>${escapeHtml(t.name)}</strong></div>
    <dl class="facts"><dt>Map</dt><dd>${escapeHtml(t.map)}</dd><dt>Starting cash</dt><dd>$${b.cash.toLocaleString()}</dd><dt>Superweapons</dt><dd>${b.limitSuperweapons ? "limited" : "allowed"}</dd></dl>
    <ul class="slots">${rows}</ul>
  </div>`;
}

function territoryInfo(id: string): string {
  const c = campaign!;
  const t = getTerritory(id);
  const owner = getGeneral(c.owners[id]);
  const site = t.site ? `<p class="site-note"><strong>${SITES[t.site].label}</strong> — ${SITES[t.site].text}</p>` : "";
  return `<div class="territory-card"><h3>${escapeHtml(t.name)}</h3>
    <p class="owner"><span class="swatch" style="background:${owner.color}"></span>${escapeHtml(owner.name)}${owner.id === c.player ? " (you)" : ""}</p>
    <p class="muted">Value ${"●".repeat(t.value)}${"○".repeat(3 - t.value)} · ${escapeHtml(t.map)}</p>${site}</div>`;
}

function renderPanel() {
  const c = campaign!;
  const me = getGeneral(c.player);
  const panel = $("conquest-panel");
  let action = "";
  if (c.outcome !== "playing") {
    action = `<div class="banner ${c.outcome}">${c.outcome === "won" ? "Victory — the world is yours." : "Defeat — your last territory has fallen."}</div>
      <button class="primary wide" id="new-campaign">New campaign</button>`;
  } else if (c.defense) {
    const d = c.defense;
    const b = planBattle(c, d.attacker, d.from, d.target);
    action = `<div class="banner threat">${escapeHtml(getGeneral(d.attacker).name)} attacks your ${escapeHtml(getTerritory(d.target).name)}</div>
      ${battlePreview(b)}
      <div class="row"><button class="primary" id="defend">Defend</button><button class="secondary" id="auto">Auto-resolve</button></div>`;
  } else if (selected && target) {
    const b = planBattle(c, c.player, selected, target, mercenary);
    const canHire = c.funds[c.player] >= MERCENARY_COST && !b.slots.some((s) => s.role.startsWith("Allies"));
    action = `${battlePreview(b)}
      <label class="check"><input type="checkbox" id="mercenary" ${mercenary ? "checked" : ""} ${canHire || mercenary ? "" : "disabled"}/> Hire mercenaries (${MERCENARY_COST} war funds)</label>
      <div class="row"><button class="primary" id="attack">Attack</button><button class="secondary" id="cancel">Cancel</button></div>`;
  } else if (selected) {
    action = `${territoryInfo(selected)}<p class="hint-text">Pick a highlighted territory next to it to attack.</p>`;
  } else {
    action = `<p class="hint-text">Pick one of your territories, then a neighbour to attack — or click any enemy territory next to yours. You have one attack per turn.</p>
      <button class="secondary wide" id="skip">Hold position (end turn)</button>`;
  }
  const log = c.log.slice(-12).reverse().map((l) => `<li>${escapeHtml(l)}</li>`).join("");
  panel.innerHTML = `
    <section class="panel general-card" style="--accent-general:${me.color}">
      <div class="general-head"><span class="swatch big" style="background:${me.color}"></span><div><h2>${escapeHtml(me.name)}</h2><p class="muted">Turn ${c.turn} · ${c.difficulty} AI</p></div></div>
      <button class="link restart" id="restart">${confirmRestart ? "Abandon this campaign? Click again" : "New campaign"}</button>
      <dl class="stats"><dt>Territories</dt><dd>${territoriesOf(c, c.player).length}/${TERRITORIES.length}</dd><dt>Income</dt><dd>+${income(c, c.player)}</dd><dt>War funds</dt><dd>${c.funds[c.player]}</dd></dl>
    </section>
    <section class="panel action">${action}</section>
    <section class="panel log"><h2>War log</h2><ul>${log}</ul></section>`;

  $("attack")?.addEventListener("click", attack);
  $("cancel")?.addEventListener("click", () => { target = null; render(); });
  $("defend")?.addEventListener("click", defend);
  $("auto")?.addEventListener("click", autoDefend);
  $("skip")?.addEventListener("click", () => finishTurn());
  $("new-campaign")?.addEventListener("click", showSetup);
  $("restart")?.addEventListener("click", () => {
    if (confirmRestart) {
      confirmRestart = false;
      showSetup();
    } else {
      confirmRestart = true;
      render();
      setTimeout(() => { confirmRestart = false; render(); }, 4000);
    }
  });
  $<HTMLInputElement>("mercenary")?.addEventListener("change", (e) => { mercenary = (e.target as HTMLInputElement).checked; render(); });
}

function render() {
  if (!campaign) return;
  renderMap();
  renderPanel();
}

// ---------------------------------------------------------------------------------------------
// Battles

interface BattleResult {
  outcome: "victory" | "defeat";
  players: { slot: number; unitsLost: number; unitsDestroyed: number; buildingsLost: number }[];
}

async function fight(b: Battle): Promise<boolean> {
  busy = true;
  $("battle-overlay").classList.add("show");
  $("battle-overlay-text").textContent = `Battle for ${getTerritory(b.target).name} in progress…`;
  try {
    const seed = Math.floor(Math.random() * 1e9) + 1;
    const text = await invoke<string | null>("run_battle", { battle: battleFile(b, seed, "{RESULT}") });
    if (!text) {
      notify("You left the battle before it was decided; it counts as lost.", "error");
      return false;
    }
    const result = JSON.parse(text) as BattleResult;
    const me = result.players.find((p) => p.slot === 0);
    if (me) notify(`${result.outcome === "victory" ? "Victory" : "Defeat"}: you destroyed ${me.unitsDestroyed} units and lost ${me.unitsLost}.`);
    return result.outcome === "victory";
  } finally {
    busy = false;
    $("battle-overlay").classList.remove("show");
  }
}

async function attack() {
  const c = campaign!;
  if (!selected || !target) return;
  const b = planBattle(c, c.player, selected, target, mercenary);
  if (b.slots.some((s) => s.role === "Mercenaries")) c.funds[c.player] -= MERCENARY_COST;
  let won: boolean;
  try {
    won = await fight(b);
  } catch (e) {
    notify(String(e), "error");
    return;
  }
  applyBattle(c, b, won);
  selected = won ? target : selected;
  target = null;
  mercenary = false;
  await finishTurn();
}

async function defend() {
  const c = campaign!;
  const d = c.defense!;
  const b = planBattle(c, d.attacker, d.from, d.target);
  let won: boolean;
  try {
    won = await fight(b);
  } catch (e) {
    notify(String(e), "error");
    return;
  }
  applyBattle(c, b, won);
  await save();
  render();
}

async function autoDefend() {
  const c = campaign!;
  const d = c.defense!;
  const b = planBattle(c, d.attacker, d.from, d.target);
  const won = autoResolve(c, b);
  applyBattle(c, b, won);
  notify(won ? `Your forces held ${getTerritory(b.target).name}.` : `${getTerritory(b.target).name} has fallen.`, won ? "info" : "error");
  await save();
  render();
}

async function finishTurn() {
  const c = campaign!;
  if (c.outcome === "playing") endTurn(c);
  if (selected && c.owners[selected] !== c.player) selected = null;
  await save();
  render();
}

// ---------------------------------------------------------------------------------------------
// New campaign

function showSetup() {
  const sides = ["USA", "China", "GLA"] as const;
  const cards = sides.map((side) => `<div class="side-col"><h3>${side}</h3>${GENERALS.filter((g) => g.side === side).map((g) =>
    `<button class="general-option" data-general="${g.id}" style="--accent-general:${g.color}"><span class="swatch" style="background:${g.color}"></span><span>${escapeHtml(g.name)}</span><small>${g.home.map((h) => escapeHtml(getTerritory(h).name)).join(", ")}</small></button>`).join("")}</div>`).join("");
  $("conquest-setup").innerHTML = `<div class="setup">
    <h1>World conquest</h1>
    <p class="muted">Choose your general. Every other general is an AI that wants the world too. Attack a neighbouring territory each turn and fight the battle in Zero Hour — with allies from your own territories next to it, against the defender and their reinforcements.</p>
    <div class="side-grid">${cards}</div>
    <div class="row setup-row"><label>AI generals <select id="difficulty"><option value="easy">Easy</option><option value="medium" selected>Medium</option><option value="hard">Hard</option></select></label></div>
  </div>`;
  $("conquest-setup").hidden = false;
  $("conquest-main").hidden = true;
  $("conquest-setup").querySelectorAll<HTMLButtonElement>(".general-option").forEach((b) => b.addEventListener("click", async () => {
    campaign = newCampaign(b.dataset.general!, $<HTMLSelectElement>("difficulty").value as Difficulty);
    selected = null;
    target = null;
    await save();
    showCampaign();
  }));
}

function showCampaign() {
  $("conquest-setup").hidden = true;
  $("conquest-main").hidden = false;
  render();
}

export async function initConquest(toast: (message: string, kind?: "info" | "error") => void) {
  notify = toast;
  const saved = await invoke<string | null>("load_campaign");
  if (saved) {
    try {
      campaign = JSON.parse(saved) as Campaign;
    } catch {
      campaign = null;
    }
    // A campaign from an older world map cannot go on in this one.
    if (campaign && (campaign.version !== WORLD_VERSION || TERRITORIES.some((t) => !(t.id in campaign!.owners)))) {
      campaign = null;
      toast("The world map has changed since your last campaign; start a new one.");
    }
  }
  if (campaign) showCampaign();
  else showSetup();
}

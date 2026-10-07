// The rules of the world conquest campaign: who owns what, what a battle looks like, and how the AI
// generals play. No UI here, so the rules can be tested on their own.

import { GENERALS, NEIGHBOURS, TERRITORIES, type General, type Territory } from "./data";

export type Difficulty = "easy" | "medium" | "hard";
export type Controller = "human" | Difficulty;

/** Changes when the world changes, so older saved campaigns are not loaded into a different map. */
export const WORLD_VERSION = 2;

export interface Campaign {
  version: number;
  player: string; // general id
  difficulty: Difficulty;
  turn: number;
  owners: Record<string, string>; // territory id -> general id
  funds: Record<string, number>; // general id -> war funds
  rng: number; // state of the random generator, so a saved campaign goes on the same way
  log: string[];
  /** An AI attack on the player that waits for the player to defend. */
  defense: { attacker: string; from: string; target: string } | null;
  outcome: "playing" | "won" | "lost";
}

export interface BattleSlot {
  general: string;
  controller: Controller;
  team: number; // 0: the player's side, 1: the enemy
  role: string; // for the battle preview
}

export interface Battle {
  target: string;
  from: string;
  attacker: string;
  defender: string;
  map: string;
  cash: number;
  limitSuperweapons: boolean;
  slots: BattleSlot[];
}

export const MERCENARY_COST = 4;
const territory = new Map(TERRITORIES.map((t) => [t.id, t]));
const general = new Map(GENERALS.map((g) => [g.id, g]));

export function getTerritory(id: string): Territory {
  return territory.get(id)!;
}

export function getGeneral(id: string): General {
  return general.get(id)!;
}

// mulberry32: small and good enough for a board game, and its state fits in a number.
function random(c: Campaign): number {
  c.rng = (c.rng + 0x6d2b79f5) | 0;
  let t = c.rng;
  t = Math.imul(t ^ (t >>> 15), t | 1);
  t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
  return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
}

export function newCampaign(player: string, difficulty: Difficulty, seed = Date.now()): Campaign {
  const owners: Record<string, string> = {};
  const funds: Record<string, number> = {};
  for (const g of GENERALS) {
    for (const t of g.home) owners[t] = g.id;
    funds[g.id] = 0;
  }
  return {
    version: WORLD_VERSION,
    player,
    difficulty,
    turn: 1,
    owners,
    funds,
    rng: seed | 0,
    log: [`You take command as ${getGeneral(player).name}.`],
    defense: null,
    outcome: "playing",
  };
}

export function territoriesOf(c: Campaign, g: string): string[] {
  return Object.keys(c.owners).filter((t) => c.owners[t] === g);
}

export function holdsSite(c: Campaign, g: string, site: string): boolean {
  return territoriesOf(c, g).some((t) => getTerritory(t).site === site);
}

/** War funds a general earns each turn. */
export function income(c: Campaign, g: string): number {
  return territoriesOf(c, g).reduce((sum, id) => {
    const t = getTerritory(id);
    return sum + t.value * (t.site === "capital" ? 2 : 1) + (t.site === "oil" ? 2 : 0);
  }, 0);
}

export function aliveGenerals(c: Campaign): string[] {
  return GENERALS.map((g) => g.id).filter((g) => territoriesOf(c, g).length > 0);
}

/** Where a general can attack from a territory. */
export function targetsFrom(c: Campaign, from: string): string[] {
  return NEIGHBOURS[from].filter((t) => c.owners[t] !== c.owners[from]);
}

function stronger(d: Difficulty): Difficulty {
  return d === "easy" ? "medium" : "hard";
}

/**
 * The battle for a territory. The attacker's other territories next to the target send allies, the
 * defender's send reinforcements, as many as the map has room for; the player may also hire a
 * mercenary.
 */
export function planBattle(c: Campaign, attacker: string, from: string, target: string, mercenary = false): Battle {
  const t = getTerritory(target);
  const defender = c.owners[target];
  const controller = (g: string): Controller => (g === c.player ? "human" : c.difficulty);
  const allyDifficulty = (g: string): Difficulty => {
    const base: Difficulty = g === c.player ? "medium" : c.difficulty;
    return holdsSite(c, g, "airbase") ? stronger(base) : base;
  };
  const slots: BattleSlot[] = [];
  const attackerTeam = attacker === c.player ? 0 : 1;
  const defenderTeam = 1 - attackerTeam;
  slots.push({ general: attacker, controller: controller(attacker), team: attackerTeam, role: "Attacker" });
  slots.push({ general: defender, controller: controller(defender), team: defenderTeam, role: "Defender" });

  const room = () => t.mapPlayers - slots.length;
  const support = (g: string) => NEIGHBOURS[target].filter((n) => n !== from && c.owners[n] === g);
  // Up to two players a side, so battles stay 2v2 at most.
  if (room() > 0 && support(defender).length > 0)
    slots.push({ general: defender, controller: allyDifficulty(defender), team: defenderTeam, role: `Reinforcements from ${getTerritory(support(defender)[0]).name}` });
  if (room() > 0 && support(attacker).length > 0)
    slots.push({ general: attacker, controller: allyDifficulty(attacker), team: attackerTeam, role: `Allies from ${getTerritory(support(attacker)[0]).name}` });
  else if (room() > 0 && mercenary && attacker === c.player)
    slots.push({ general: attacker, controller: allyDifficulty(attacker), team: attackerTeam, role: "Mercenaries" });

  // The human player is the first slot, as the game expects.
  slots.sort((a, b) => (a.controller === "human" ? -1 : b.controller === "human" ? 1 : 0));
  return {
    target,
    from,
    attacker,
    defender,
    map: t.map,
    cash: 5000 + t.value * 2500,
    limitSuperweapons: !holdsSite(c, attacker, "nuclear") && !holdsSite(c, defender, "nuclear"),
    slots,
  };
}

/** The battle file the game reads (-battle). */
export function battleFile(b: Battle, seed: number, resultPath: string): string {
  const lines = [
    `# ${getTerritory(b.target).name}: ${getGeneral(b.attacker).name} attacks ${getGeneral(b.defender).name}`,
    `map ${b.map}`,
    `cash ${b.cash}`,
    `seed ${seed}`,
    `superweapons ${b.limitSuperweapons ? 1 : 0}`,
    `result ${resultPath}`,
  ];
  b.slots.forEach((s, i) => lines.push(`player ${s.controller} ${getGeneral(s.general).faction} ${s.team} ${i}`));
  return lines.join("\n") + "\n";
}

function strength(c: Campaign, g: string, target: string): number {
  const support = NEIGHBOURS[target].filter((n) => c.owners[n] === g).length;
  return 2 + income(c, g) / 4 + support + random(c) * 6;
}

function capture(c: Campaign, target: string, winner: string) {
  const loser = c.owners[target];
  c.owners[target] = winner;
  if (territoriesOf(c, loser).length === 0) c.log.push(`${getGeneral(loser).name} has been defeated.`);
}

/** Applies the result of a battle the player fought: true when the player's side won. */
export function applyBattle(c: Campaign, b: Battle, playerWon: boolean) {
  const t = getTerritory(b.target).name;
  if (b.attacker === c.player) {
    if (playerWon) {
      capture(c, b.target, c.player);
      c.log.push(`You took ${t} from ${getGeneral(b.defender).name}.`);
    } else {
      c.log.push(`Your attack on ${t} failed.`);
    }
  } else {
    if (playerWon) c.log.push(`You held ${t} against ${getGeneral(b.attacker).name}.`);
    else {
      capture(c, b.target, b.attacker);
      c.log.push(`${getGeneral(b.attacker).name} took ${t} from you.`);
    }
    c.defense = null;
  }
  checkOutcome(c);
}

/** Auto-resolves a battle (the player can let a defense be fought without them). */
export function autoResolve(c: Campaign, b: Battle): boolean {
  const attackerWins = strength(c, b.attacker, b.target) > strength(c, b.defender, b.target) + 1;
  return b.attacker === c.player ? attackerWins : !attackerWins;
}

function checkOutcome(c: Campaign) {
  const mine = territoriesOf(c, c.player).length;
  if (mine === 0) {
    c.outcome = "lost";
    c.log.push("You have lost your last territory. The war is over.");
  } else if (mine === TERRITORIES.length) {
    c.outcome = "won";
    c.log.push("The whole world is yours.");
  }
}

/**
 * Ends the player's turn: war funds are paid and every AI general may attack. AI against AI is
 * resolved at once; the first attack on the player becomes the defense the player has to fight.
 */
export function endTurn(c: Campaign) {
  for (const g of aliveGenerals(c)) c.funds[g] += income(c, g);
  const order = aliveGenerals(c).filter((g) => g !== c.player);
  for (let i = order.length - 1; i > 0; i--) {
    const j = Math.floor(random(c) * (i + 1));
    [order[i], order[j]] = [order[j], order[i]];
  }
  for (const g of order) {
    if (territoriesOf(c, g).length === 0 || c.outcome !== "playing") continue;
    const aggression = { easy: 0.3, medium: 0.45, hard: 0.6 }[c.difficulty];
    if (random(c) > aggression + income(c, g) / 60) continue;
    // The most promising target: rich and weakly held.
    let best: { from: string; target: string; score: number } | null = null;
    for (const from of territoriesOf(c, g)) {
      for (const target of targetsFrom(c, from)) {
        if (c.owners[target] === c.player && c.defense) continue;
        const score = getTerritory(target).value * 2 - income(c, c.owners[target]) / 3 + random(c) * 3;
        if (!best || score > best.score) best = { from, target, score };
      }
    }
    if (!best) continue;
    const defender = c.owners[best.target];
    if (defender === c.player) {
      c.defense = { attacker: g, from: best.from, target: best.target };
      c.log.push(`${getGeneral(g).name} attacks your ${getTerritory(best.target).name}!`);
      continue;
    }
    if (strength(c, g, best.target) > strength(c, defender, best.target) + 1) {
      capture(c, best.target, g);
      c.log.push(`${getGeneral(g).name} took ${getTerritory(best.target).name} from ${getGeneral(defender).name}.`);
    }
  }
  c.turn += 1;
  checkOutcome(c);
}

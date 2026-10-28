// Run with: npx tsx src/conquest/campaign.test.ts
import assert from "node:assert/strict";
import { GENERALS, TERRITORIES } from "./data";
import { MERCENARY_COST, applyBattle, battleFile, cancelInvalidDefense, endTurn, income, newCampaign, planBattle, targetsFrom, territoriesOf } from "./campaign";

// Starting positions.
const c = newCampaign("usa", "medium", 42);
assert.equal(Object.keys(c.owners).length, TERRITORIES.length);
assert.deepEqual(territoriesOf(c, "usa").sort(), ["california", "centralam", "mexico", "plains", "rockies", "texas"]);
assert.ok(income(c, "usa") > 0);

// A battle: USA attacks the Gulf Coast (Superweapon General) from the Great Plains. The Superweapon
// General's other territories on the Gulf reinforce; USA's Texas borders it too and sends allies.
const b = planBattle(c, "usa", "plains", "gulf");
assert.equal(b.slots[0].controller, "human");
assert.equal(b.slots.filter((s) => s.team === 0).length, 2, "Texas sends allies");
assert.equal(b.slots.filter((s) => s.team === 1).length, 2, "the East Coast reinforces");
assert.ok(b.slots.length <= 4);
const file = battleFile(b, 7, "/tmp/result.json");
assert.match(file, /^map eastern everglades$/m);
assert.match(file, /^player human FactionAmerica 0 0$/m);
assert.match(file, /^player medium FactionAmericaSuperWeaponGeneral 1 \d$/m);

// Winning moves the territory; losing does not.
applyBattle(c, b, true);
assert.equal(c.owners.gulf, "usa");
const b2 = planBattle(c, "usa", "gulf", "eastcoast");
applyBattle(c, b2, false);
assert.equal(c.owners.eastcoast, "superweapon");

// Map player limits: a two player map has no room for reinforcements. Central America (seaside
// mutiny, 2 players) borders USA's Mexico, but the battle stays one against one.
const small = newCampaign("stealth", "medium", 3);
const duel = planBattle(small, "stealth", "colombia", "centralam");
assert.equal(duel.slots.length, 2);
for (const t of TERRITORIES) assert.ok(t.mapPlayers >= 2);

// AI turns change the world but keep it consistent, and an attack on the player waits for a defense.
const world = newCampaign("china", "hard", 1);
for (let turn = 0; turn < 60 && world.outcome === "playing"; turn++) {
  if (world.defense) applyBattle(world, planBattle(world, world.defense.attacker, world.defense.from, world.defense.target), turn % 2 === 0);
  endTurn(world);
  for (const owner of Object.values(world.owners)) assert.ok(GENERALS.some((g) => g.id === owner));
}
assert.ok(world.turn > 1);
assert.ok(targetsFrom(world, Object.keys(world.owners)[0]).every((t) => world.owners[t] !== world.owners[Object.keys(world.owners)[0]]));

// The same seed plays the same way.
const a1 = newCampaign("gla", "medium", 99), a2 = newCampaign("gla", "medium", 99);
for (let i = 0; i < 10; i++) {
  endTurn(a1); a1.defense = null;
  endTurn(a2); a2.defense = null;
}
assert.deepEqual(a1.owners, a2.owners);

// A queued attack must still have a territory to attack from after the other AIs have moved.
// With this seed the Superweapon General attacks on turn 13, then loses its last territories.
const queued = newCampaign("usa", "hard", 1);
for (let turn = 0; turn < 12; turn++) {
  if (queued.defense) {
    const d = queued.defense;
    applyBattle(queued, planBattle(queued, d.attacker, d.from, d.target), true);
  }
  endTurn(queued);
  if (queued.defense) {
    assert.equal(queued.owners[queued.defense.from], queued.defense.attacker, "a queued attacker must still own its starting territory");
  }
}
assert.equal(queued.turn, 13);
assert.equal(territoriesOf(queued, "superweapon").length, 0);
assert.equal(queued.defense, null, "an eliminated general must not have a pending attack");

// Loading old saves also clears stale attacks, even if the attacker still owns other territories.
const saved = newCampaign("usa", "medium", 42);
saved.defense = { attacker: "superweapon", from: "greatlakes", target: "plains" };
assert.equal(cancelInvalidDefense(saved), false, "valid defenses remain playable");
saved.owners.greatlakes = "toxin";
assert.ok(territoriesOf(saved, "superweapon").length > 0);
assert.equal(cancelInvalidDefense(saved), true);
assert.equal(saved.defense, null);
const logLength = saved.log.length;
assert.equal(cancelInvalidDefense(saved), false);
assert.equal(saved.log.length, logLength, "loading again must not add another cancellation");

// Planning and previewing a mercenary attack costs nothing; applying either result charges once.
for (const won of [true, false]) {
  const hired = newCampaign("usa", "medium", 42);
  hired.funds.usa = 12;
  hired.owners.texas = "superweapon"; // Remove the free allies for an attack on the Gulf Coast.
  const battle = planBattle(hired, "usa", "plains", "gulf", true);
  assert.ok(battle.slots.some((s) => s.role === "Mercenaries"));
  assert.equal(hired.funds.usa, 12);
  applyBattle(hired, battle, won);
  assert.equal(hired.funds.usa, 12 - MERCENARY_COST);
  assert.equal(hired.owners.gulf, won ? "usa" : "superweapon");
}

// Free neighbouring allies are not charged as mercenaries, even when hiring was requested.
const supported = newCampaign("usa", "medium", 42);
supported.funds.usa = 12;
applyBattle(supported, planBattle(supported, "usa", "plains", "gulf", true), true);
assert.equal(supported.funds.usa, 12);

console.log("campaign tests passed");

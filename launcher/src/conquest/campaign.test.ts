// Run with: npx tsx src/conquest/campaign.test.ts
import assert from "node:assert/strict";
import { GENERALS, TERRITORIES } from "./data";
import { applyBattle, battleFile, endTurn, income, newCampaign, planBattle, targetsFrom, territoriesOf } from "./campaign";

// Starting positions.
const c = newCampaign("usa", "medium", 42);
assert.equal(Object.keys(c.owners).length, TERRITORIES.length);
assert.deepEqual(territoriesOf(c, "usa").sort(), ["cascadia", "mexico", "plains"]);
assert.ok(income(c, "usa") > 0);

// A battle: USA attacks the Gulf Coast (Superweapon General) from the Great Plains. The Superweapon
// General's East Coast borders the Gulf and reinforces; USA's Mexico borders it too and sends allies.
const b = planBattle(c, "usa", "plains", "gulf");
assert.equal(b.slots[0].controller, "human");
assert.equal(b.slots.filter((s) => s.team === 0).length, 2, "Mexico sends allies");
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

// Map player limits: a two player map has no room for reinforcements (every territory map has 4+).
for (const t of TERRITORIES) assert.ok(t.mapPlayers >= 4, `${t.id} needs a map for 2v2`);

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

console.log("campaign tests passed");

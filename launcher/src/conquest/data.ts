// The world of the conquest campaign: territories, which Zero Hour map each battle is fought on, the
// borders between them, and the generals.

export interface Territory {
  id: string;
  name: string;
  lon: number;
  lat: number;
  /** Income and weight: 1 to 3. */
  value: number;
  /** The Zero Hour map (its folder name, as -battle takes it) and how many players it has. */
  map: string;
  mapPlayers: number;
  /** A site that helps whoever holds it. */
  site?: Site;
  /** Where the name goes where territories crowd together (below by default). */
  label?: "above" | "left" | "right";
}

export type Site = "oil" | "airbase" | "nuclear" | "capital";

export const SITES: Record<Site, { label: string; text: string }> = {
  oil: { label: "Oil fields", text: "+3,000 starting cash in every battle" },
  airbase: { label: "Air base", text: "+1 to the AI difficulty of your allies' reinforcements" },
  nuclear: { label: "Nuclear facility", text: "Your battles allow superweapons; without one they are limited" },
  capital: { label: "Capital", text: "Worth double income; a general who loses their capital loses heart" },
};

export const TERRITORIES: Territory[] = [
  // North America
  { id: "cascadia", name: "Pacific Northwest", lon: -121, lat: 47, value: 2, map: "lone eagle", mapPlayers: 4 },
  { id: "plains", name: "Great Plains", lon: -99, lat: 41, value: 2, map: "homeland alliance", mapPlayers: 4, site: "capital" },
  { id: "eastcoast", name: "East Coast", lon: -76, lat: 40, value: 3, map: "tournament urban", mapPlayers: 4 },
  { id: "gulf", name: "Gulf Coast", lon: -91, lat: 30, value: 2, map: "eastern everglades", mapPlayers: 4, site: "oil", label: "right" },
  { id: "mexico", name: "Mexico", lon: -102, lat: 22, value: 1, map: "el scorcho", mapPlayers: 4 },
  // South America
  { id: "amazon", name: "Amazon", lon: -60, lat: -5, value: 1, map: "floodedplains", mapPlayers: 4 },
  { id: "andes", name: "Andes", lon: -70, lat: -20, value: 1, map: "rocky rampage", mapPlayers: 4 },
  { id: "pampas", name: "Pampas", lon: -62, lat: -36, value: 2, map: "green pastures", mapPlayers: 6 },
  // Europe
  { id: "britain", name: "British Isles", lon: -2, lat: 53, value: 2, map: "dark night", mapPlayers: 4, site: "airbase", label: "left" },
  { id: "westeurope", name: "Western Europe", lon: 5, lat: 48, value: 3, map: "tournament lake", mapPlayers: 4, site: "capital", label: "left" },
  { id: "scandinavia", name: "Scandinavia", lon: 15, lat: 62, value: 1, map: "tournament tundra", mapPlayers: 4, label: "above" },
  { id: "easteurope", name: "Eastern Europe", lon: 25, lat: 51, value: 2, map: "overland", mapPlayers: 4, label: "above" },
  { id: "balkans", name: "Balkans", lon: 21, lat: 43, value: 1, map: "mountainfox", mapPlayers: 4, label: "right" },
  // Russia and Central Asia
  { id: "moscow", name: "Moscow", lon: 38, lat: 56, value: 3, map: "whiteout", mapPlayers: 8, site: "capital" },
  { id: "ural", name: "Ural", lon: 60, lat: 58, value: 2, map: "fortress avalanche", mapPlayers: 8, site: "nuclear" },
  { id: "siberia", name: "Siberia", lon: 100, lat: 62, value: 1, map: "tournament continent", mapPlayers: 4 },
  { id: "kazakh", name: "Kazakh Steppe", lon: 68, lat: 47, value: 1, map: "dogsofwar", mapPlayers: 4, site: "oil", label: "above" },
  { id: "caucasus", name: "Caucasus", lon: 44, lat: 42, value: 1, map: "dark mountain", mapPlayers: 4, label: "right" },
  // Middle East and Africa
  { id: "egypt", name: "Egypt", lon: 31, lat: 28, value: 2, map: "golden oasis", mapPlayers: 4, label: "left" },
  { id: "levant", name: "Levant", lon: 36, lat: 33, value: 2, map: "manic aggression", mapPlayers: 4, label: "left" },
  { id: "arabia", name: "Arabia", lon: 46, lat: 24, value: 3, map: "death valley", mapPlayers: 8, site: "oil" },
  { id: "persia", name: "Persia", lon: 53, lat: 32, value: 2, map: "red rock", mapPlayers: 6, site: "nuclear", label: "right" },
  { id: "afghan", name: "Afghanistan", lon: 66, lat: 34, value: 1, map: "twilight flame", mapPlayers: 8, label: "left" },
  { id: "maghreb", name: "Maghreb", lon: 3, lat: 32, value: 1, map: "victory valley", mapPlayers: 4 },
  { id: "sahel", name: "Sahel", lon: 10, lat: 15, value: 1, map: "hostile dawn", mapPlayers: 6 },
  { id: "horn", name: "Horn of Africa", lon: 42, lat: 8, value: 1, map: "tournamenta", mapPlayers: 4 },
  { id: "congo", name: "Congo", lon: 22, lat: -3, value: 1, map: "rogue agent", mapPlayers: 4 },
  { id: "southafrica", name: "Southern Africa", lon: 25, lat: -27, value: 2, map: "tournamentb", mapPlayers: 4 },
  // South and East Asia
  { id: "kashmir", name: "Kashmir", lon: 76, lat: 34, value: 1, map: "bear town beatdown", mapPlayers: 4, label: "above" },
  { id: "india", name: "India", lon: 79, lat: 21, value: 3, map: "free fire zone", mapPlayers: 6, site: "capital" },
  { id: "tibet", name: "Tibet", lon: 88, lat: 32, value: 1, map: "armored fury", mapPlayers: 6, label: "right" },
  { id: "greatwall", name: "Northern China", lon: 113, lat: 40, value: 3, map: "fallen empire", mapPlayers: 4, site: "capital" },
  { id: "yangtze", name: "Yangtze", lon: 113, lat: 29, value: 2, map: "iron dragon", mapPlayers: 8, site: "nuclear", label: "right" },
  { id: "indochina", name: "Indochina", lon: 104, lat: 15, value: 1, map: "lights out", mapPlayers: 4 },
  { id: "pacific", name: "Japan and Korea", lon: 133, lat: 36, value: 2, map: "tournament island", mapPlayers: 4, site: "airbase", label: "right" },
  { id: "australia", name: "Australia", lon: 134, lat: -25, value: 2, map: "defcon6", mapPlayers: 6 },
];

/** Borders, each listed once; sea lanes join coasts. */
const BORDERS: [string, string][] = [
  ["cascadia", "plains"], ["plains", "eastcoast"], ["plains", "gulf"], ["eastcoast", "gulf"], ["gulf", "mexico"],
  ["cascadia", "mexico"], ["mexico", "amazon"], ["amazon", "andes"], ["andes", "pampas"], ["amazon", "pampas"],
  ["eastcoast", "britain"], ["amazon", "sahel"], ["pampas", "southafrica"], ["cascadia", "pacific"],
  ["britain", "westeurope"], ["britain", "scandinavia"], ["westeurope", "scandinavia"], ["westeurope", "easteurope"],
  ["westeurope", "balkans"], ["westeurope", "maghreb"], ["easteurope", "balkans"], ["easteurope", "scandinavia"],
  ["easteurope", "moscow"], ["balkans", "levant"], ["balkans", "caucasus"], ["moscow", "scandinavia"],
  ["moscow", "ural"], ["moscow", "caucasus"], ["ural", "siberia"], ["ural", "kazakh"], ["siberia", "kazakh"],
  ["siberia", "greatwall"], ["siberia", "pacific"], ["kazakh", "caucasus"], ["kazakh", "afghan"], ["kazakh", "tibet"],
  ["caucasus", "persia"], ["levant", "egypt"], ["levant", "arabia"], ["levant", "persia"], ["egypt", "maghreb"],
  ["egypt", "sahel"], ["egypt", "horn"], ["arabia", "persia"], ["arabia", "horn"], ["persia", "afghan"],
  ["afghan", "kashmir"], ["maghreb", "sahel"], ["sahel", "congo"], ["sahel", "horn"], ["horn", "congo"],
  ["congo", "southafrica"], ["kashmir", "india"], ["kashmir", "tibet"], ["india", "tibet"], ["india", "indochina"],
  ["tibet", "greatwall"], ["tibet", "yangtze"], ["greatwall", "yangtze"], ["greatwall", "pacific"],
  ["yangtze", "indochina"], ["yangtze", "pacific"], ["indochina", "australia"], ["pacific", "australia"],
  ["southafrica", "australia"],
];

export const NEIGHBOURS: Record<string, string[]> = {};
for (const t of TERRITORIES) NEIGHBOURS[t.id] = [];
for (const [a, b] of BORDERS) {
  NEIGHBOURS[a].push(b);
  NEIGHBOURS[b].push(a);
}

/** Sea lanes are drawn dashed. */
export const SEA_LANES = new Set(
  [
    ["eastcoast", "britain"], ["amazon", "sahel"], ["pampas", "southafrica"], ["cascadia", "pacific"],
    ["indochina", "australia"], ["pacific", "australia"], ["southafrica", "australia"], ["britain", "scandinavia"],
  ].map(([a, b]) => [a, b].sort().join("|")),
);

export interface General {
  id: string;
  name: string;
  /** The PlayerTemplate (faction) name the game knows. */
  faction: string;
  side: "USA" | "China" | "GLA";
  color: string;
  /** Where the general starts. */
  home: string[];
}

export const GENERALS: General[] = [
  { id: "usa", name: "USA", faction: "FactionAmerica", side: "USA", color: "#4d8fd6", home: ["plains", "cascadia", "mexico"] },
  { id: "superweapon", name: "Superweapon General", faction: "FactionAmericaSuperWeaponGeneral", side: "USA", color: "#62c2e8", home: ["eastcoast", "gulf"] },
  { id: "laser", name: "Laser General", faction: "FactionAmericaLaserGeneral", side: "USA", color: "#9a8cf2", home: ["britain", "scandinavia", "westeurope", "balkans"] },
  { id: "airforce", name: "Air Force General", faction: "FactionAmericaAirForceGeneral", side: "USA", color: "#7fd4c1", home: ["pacific", "australia"] },
  { id: "china", name: "China", faction: "FactionChina", side: "China", color: "#d9534f", home: ["greatwall", "siberia"] },
  { id: "tank", name: "Tank General", faction: "FactionChinaTankGeneral", side: "China", color: "#e07b39", home: ["moscow", "easteurope", "ural", "caucasus"] },
  { id: "infantry", name: "Infantry General", faction: "FactionChinaInfantryGeneral", side: "China", color: "#c76b98", home: ["india", "kashmir", "indochina"] },
  { id: "nuke", name: "Nuke General", faction: "FactionChinaNukeGeneral", side: "China", color: "#e8c547", home: ["yangtze", "tibet"] },
  { id: "gla", name: "GLA", faction: "FactionGLA", side: "GLA", color: "#8bb65a", home: ["arabia", "horn", "levant"] },
  { id: "toxin", name: "Toxin General", faction: "FactionGLAToxinGeneral", side: "GLA", color: "#b5d63b", home: ["persia", "afghan", "kazakh"] },
  { id: "demolition", name: "Demolition General", faction: "FactionGLADemolitionGeneral", side: "GLA", color: "#c9a26b", home: ["egypt", "maghreb", "sahel"] },
  { id: "stealth", name: "Stealth General", faction: "FactionGLAStealthGeneral", side: "GLA", color: "#8f9a8c", home: ["congo", "southafrica", "amazon", "andes", "pampas"] },
];

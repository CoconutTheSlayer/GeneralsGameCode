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

/** Borders across the sea. */
const SEA: [string, string][] = [
  ["alaska", "fareast"], ["eastcanada", "britain"], ["cascadia", "japan"], ["gulf", "caribbean"],
  ["eastcoast", "caribbean"], ["caribbean", "colombia"], ["brazil", "westafrica"], ["pampas", "southafrica"],
  ["britain", "scandinavia"], ["iberia", "maghreb"], ["italy", "libya"], ["gulfstates", "persia"],
  ["arabia", "horn"], ["southafrica", "westaus"], ["korea", "japan"], ["fareast", "japan"], ["japan", "philippines"],
  ["southchina", "philippines"], ["malaya", "indonesia"], ["indonesia", "philippines"], ["indonesia", "westaus"],
];

export const TERRITORIES: Territory[] = [
  // North America
  { id: "alaska", name: "Alaska", lon: -150, lat: 63, value: 1, map: "bitter winter", mapPlayers: 2, site: "airbase" },
  { id: "westcanada", name: "Western Canada", lon: -115, lat: 56, value: 1, map: "tournament tundra", mapPlayers: 4 },
  { id: "eastcanada", name: "Eastern Canada", lon: -74, lat: 50, value: 1, map: "forgottenforestzh", mapPlayers: 2 },
  { id: "cascadia", name: "Pacific Northwest", lon: -121, lat: 46, value: 2, map: "lone eagle", mapPlayers: 4, label: "left" },
  { id: "california", name: "California", lon: -119, lat: 36, value: 2, map: "tournament city", mapPlayers: 6, label: "left" },
  { id: "rockies", name: "Rocky Mountains", lon: -107, lat: 41, value: 2, map: "mountain guns", mapPlayers: 5, site: "nuclear", label: "above" },
  { id: "plains", name: "Great Plains", lon: -97, lat: 41, value: 3, map: "homeland alliance", mapPlayers: 4, site: "capital", label: "right" },
  { id: "texas", name: "Texas", lon: -99, lat: 31, value: 2, map: "el scorcho", mapPlayers: 4, site: "oil", label: "left" },
  { id: "greatlakes", name: "Great Lakes", lon: -85, lat: 44, value: 2, map: "overland", mapPlayers: 4, label: "above" },
  { id: "eastcoast", name: "East Coast", lon: -76, lat: 39, value: 3, map: "tournament urban", mapPlayers: 4, site: "capital", label: "right" },
  { id: "gulf", name: "Gulf Coast", lon: -86, lat: 31, value: 2, map: "eastern everglades", mapPlayers: 4 },
  { id: "mexico", name: "Mexico", lon: -102, lat: 22, value: 1, map: "desert fury", mapPlayers: 2 },
  { id: "centralam", name: "Central America", lon: -87, lat: 14, value: 1, map: "seaside mutiny", mapPlayers: 2, label: "left" },
  { id: "caribbean", name: "Caribbean", lon: -74, lat: 20, value: 1, map: "bombardment beach", mapPlayers: 2, label: "right" },
  // South America
  { id: "colombia", name: "Colombia", lon: -72, lat: 6, value: 2, map: "floodedplains", mapPlayers: 4, site: "oil", label: "right" },
  { id: "amazon", name: "Amazon", lon: -62, lat: -4, value: 1, map: "silent river", mapPlayers: 2 },
  { id: "brazil", name: "Brazil", lon: -45, lat: -14, value: 3, map: "green pastures", mapPlayers: 6, site: "capital", label: "right" },
  { id: "andes", name: "Andes", lon: -72, lat: -16, value: 1, map: "rocky rampage", mapPlayers: 4, label: "left" },
  { id: "pampas", name: "Pampas", lon: -62, lat: -33, value: 2, map: "tournament plains", mapPlayers: 2, label: "right" },
  { id: "patagonia", name: "Patagonia", lon: -69, lat: -46, value: 1, map: "scorched earth", mapPlayers: 2 },
  // Europe
  { id: "britain", name: "British Isles", lon: -3, lat: 54, value: 2, map: "dark night", mapPlayers: 4, site: "airbase", label: "left" },
  { id: "france", name: "France", lon: 2, lat: 46.5, value: 3, map: "tournament lake", mapPlayers: 4, site: "capital", label: "left" },
  { id: "iberia", name: "Iberia", lon: -4, lat: 40, value: 1, map: "sand serpent", mapPlayers: 2, label: "left" },
  { id: "germany", name: "Central Europe", lon: 11, lat: 51, value: 2, map: "final crusade", mapPlayers: 2, label: "above" },
  { id: "italy", name: "Italy", lon: 13, lat: 43, value: 1, map: "alpine assault", mapPlayers: 2 },
  { id: "scandinavia", name: "Scandinavia", lon: 15, lat: 63, value: 1, map: "tournament tundra", mapPlayers: 4, label: "above" },
  { id: "baltic", name: "Baltic", lon: 25, lat: 58, value: 1, map: "thefrontline", mapPlayers: 2, label: "above" },
  { id: "poland", name: "Poland", lon: 21, lat: 52, value: 2, map: "leipzig lowlands", mapPlayers: 2, label: "right" },
  { id: "balkans", name: "Balkans", lon: 21, lat: 43, value: 1, map: "mountainfox", mapPlayers: 4 },
  { id: "ukraine", name: "Ukraine", lon: 32, lat: 49, value: 2, map: "dogsofwar", mapPlayers: 4, label: "right" },
  // Russia and Central Asia
  { id: "moscow", name: "Moscow", lon: 38, lat: 56, value: 3, map: "whiteout", mapPlayers: 8, site: "capital", label: "above" },
  { id: "ural", name: "Ural", lon: 60, lat: 58, value: 2, map: "fortress avalanche", mapPlayers: 8, site: "nuclear", label: "above" },
  { id: "westsiberia", name: "West Siberia", lon: 78, lat: 61, value: 2, map: "tournament continent", mapPlayers: 4, site: "oil", label: "above" },
  { id: "siberia", name: "Central Siberia", lon: 102, lat: 62, value: 1, map: "winding river", mapPlayers: 2, label: "above" },
  { id: "fareast", name: "Russian Far East", lon: 136, lat: 56, value: 1, map: "tournamenta", mapPlayers: 4, label: "above" },
  { id: "caucasus", name: "Caucasus", lon: 44, lat: 43, value: 1, map: "dark mountain", mapPlayers: 4, label: "right" },
  { id: "kazakh", name: "Kazakh Steppe", lon: 68, lat: 48, value: 2, map: "barrenbadlands", mapPlayers: 2, site: "oil", label: "above" },
  { id: "uzbek", name: "Turkestan", lon: 63, lat: 41, value: 1, map: "dust devil", mapPlayers: 2, label: "right" },
  // Middle East
  { id: "anatolia", name: "Anatolia", lon: 33, lat: 39, value: 2, map: "flash effect", mapPlayers: 3, site: "airbase", label: "above" },
  { id: "levant", name: "Levant", lon: 36, lat: 33, value: 2, map: "manic aggression", mapPlayers: 4, label: "left" },
  { id: "iraq", name: "Mesopotamia", lon: 44, lat: 33, value: 2, map: "destruction station", mapPlayers: 8, site: "oil", label: "above" },
  { id: "arabia", name: "Arabia", lon: 45, lat: 23, value: 3, map: "death valley", mapPlayers: 8, site: "capital" },
  { id: "gulfstates", name: "Persian Gulf", lon: 51, lat: 26, value: 2, map: "golden oasis", mapPlayers: 4, site: "oil", label: "right" },
  { id: "persia", name: "Persia", lon: 54, lat: 33, value: 3, map: "red rock", mapPlayers: 6, site: "capital", label: "above" },
  // Africa
  { id: "maghreb", name: "Maghreb", lon: 2, lat: 31, value: 3, map: "victory valley", mapPlayers: 4, site: "capital" },
  { id: "libya", name: "Libya", lon: 17, lat: 27, value: 2, map: "tournament desert", mapPlayers: 2, site: "oil" },
  { id: "egypt", name: "Egypt", lon: 30, lat: 26, value: 2, map: "cairo commandos", mapPlayers: 3 },
  { id: "sahel", name: "Sahel", lon: 8, lat: 15, value: 1, map: "hostile dawn", mapPlayers: 6 },
  { id: "westafrica", name: "West Africa", lon: -6, lat: 9, value: 2, map: "rogue agent", mapPlayers: 4, site: "oil", label: "left" },
  { id: "horn", name: "Horn of Africa", lon: 42, lat: 8, value: 1, map: "flash fire", mapPlayers: 2, label: "right" },
  { id: "congo", name: "Congo", lon: 22, lat: -2, value: 1, map: "lights out", mapPlayers: 4 },
  { id: "eastafrica", name: "East Africa", lon: 36, lat: -4, value: 1, map: "wasteland warlords", mapPlayers: 2, label: "right" },
  { id: "southafrica", name: "Southern Africa", lon: 25, lat: -27, value: 2, map: "tournamentb", mapPlayers: 4 },
  // South Asia
  { id: "afghan", name: "Afghanistan", lon: 66, lat: 34, value: 1, map: "twilight flame", mapPlayers: 8, label: "left" },
  { id: "indus", name: "Indus", lon: 69, lat: 27, value: 2, map: "bear town beatdown", mapPlayers: 4, site: "nuclear", label: "left" },
  { id: "kashmir", name: "Kashmir", lon: 76, lat: 34, value: 1, map: "killing fields", mapPlayers: 2, label: "above" },
  { id: "ganges", name: "Ganges", lon: 81, lat: 26, value: 3, map: "free fire zone", mapPlayers: 6, site: "capital", label: "right" },
  { id: "deccan", name: "Deccan", lon: 77, lat: 16, value: 2, map: "armored fury", mapPlayers: 6 },
  { id: "bengal", name: "Bengal", lon: 90, lat: 23, value: 1, map: "floodedplains", mapPlayers: 4 },
  // East Asia
  { id: "tibet", name: "Tibet", lon: 88, lat: 31, value: 1, map: "fortress avalanche", mapPlayers: 8, label: "above" },
  { id: "xinjiang", name: "Xinjiang", lon: 85, lat: 42, value: 2, map: "winter wolf", mapPlayers: 2, site: "nuclear", label: "above" },
  { id: "mongolia", name: "Mongolia", lon: 103, lat: 46, value: 1, map: "tournament continent", mapPlayers: 4 },
  { id: "manchuria", name: "Manchuria", lon: 126, lat: 46, value: 2, map: "tournament tundra", mapPlayers: 4, label: "right" },
  { id: "greatwall", name: "Northern China", lon: 114, lat: 39, value: 3, map: "fallen empire", mapPlayers: 4, site: "capital", label: "left" },
  { id: "yangtze", name: "Yangtze", lon: 113, lat: 30, value: 3, map: "iron dragon", mapPlayers: 8, site: "capital", label: "left" },
  { id: "southchina", name: "South China", lon: 110, lat: 23, value: 2, map: "heartland shield", mapPlayers: 2, label: "left" },
  { id: "korea", name: "Korea", lon: 127, lat: 37, value: 2, map: "tournament island", mapPlayers: 4, site: "airbase", label: "right" },
  { id: "japan", name: "Japan", lon: 139, lat: 36, value: 3, map: "tournament island", mapPlayers: 4, site: "capital", label: "right" },
  // South East Asia and Oceania
  { id: "indochina", name: "Indochina", lon: 104, lat: 15, value: 1, map: "lights out", mapPlayers: 4, label: "left" },
  { id: "malaya", name: "Malaya", lon: 102, lat: 4, value: 1, map: "seaside mutiny", mapPlayers: 2, label: "left" },
  { id: "philippines", name: "Philippines", lon: 122, lat: 12, value: 1, map: "bombardment beach", mapPlayers: 2, label: "right" },
  { id: "indonesia", name: "Indonesia", lon: 116, lat: -2, value: 2, map: "tournament island", mapPlayers: 4, label: "right" },
  { id: "westaus", name: "Western Australia", lon: 122, lat: -25, value: 1, map: "dust devil", mapPlayers: 2 },
  { id: "eastaus", name: "Eastern Australia", lon: 146, lat: -28, value: 2, map: "defcon6", mapPlayers: 6 },
];

/** Borders, each listed once; sea lanes join coasts. */
const BORDERS: [string, string][] = [
  // North America
  ["alaska", "westcanada"], ["alaska", "cascadia"], ["westcanada", "cascadia"], ["westcanada", "rockies"],
  ["westcanada", "plains"], ["westcanada", "greatlakes"], ["westcanada", "eastcanada"], ["eastcanada", "greatlakes"],
  ["eastcanada", "eastcoast"], ["cascadia", "california"], ["cascadia", "rockies"], ["california", "rockies"],
  ["california", "mexico"], ["rockies", "plains"], ["rockies", "texas"], ["plains", "greatlakes"], ["plains", "texas"],
  ["plains", "gulf"], ["greatlakes", "eastcoast"], ["greatlakes", "gulf"], ["eastcoast", "gulf"], ["gulf", "texas"],
  ["texas", "mexico"], ["mexico", "centralam"], ["centralam", "caribbean"], ["centralam", "colombia"],
  // South America
  ["colombia", "amazon"], ["colombia", "andes"], ["amazon", "andes"], ["amazon", "brazil"], ["brazil", "pampas"],
  ["andes", "pampas"], ["andes", "patagonia"], ["pampas", "patagonia"],
  // Europe
  ["britain", "france"], ["france", "iberia"], ["france", "germany"], ["france", "italy"], ["germany", "italy"],
  ["germany", "scandinavia"], ["germany", "poland"], ["italy", "balkans"], ["scandinavia", "baltic"],
  ["baltic", "poland"], ["baltic", "moscow"], ["poland", "ukraine"], ["poland", "balkans"], ["balkans", "ukraine"],
  ["balkans", "anatolia"], ["ukraine", "moscow"], ["ukraine", "caucasus"],
  // Russia and Central Asia
  ["moscow", "ural"], ["moscow", "caucasus"], ["ural", "westsiberia"], ["ural", "kazakh"], ["westsiberia", "siberia"],
  ["westsiberia", "kazakh"], ["siberia", "fareast"], ["siberia", "mongolia"], ["fareast", "manchuria"],
  ["caucasus", "anatolia"], ["caucasus", "persia"], ["kazakh", "uzbek"], ["kazakh", "xinjiang"], ["uzbek", "persia"],
  ["uzbek", "afghan"],
  // Middle East
  ["anatolia", "levant"], ["anatolia", "iraq"], ["levant", "iraq"], ["levant", "egypt"], ["levant", "arabia"],
  ["iraq", "persia"], ["iraq", "arabia"], ["iraq", "gulfstates"], ["arabia", "gulfstates"], ["persia", "afghan"],
  ["persia", "indus"],
  // Africa
  ["maghreb", "libya"], ["maghreb", "sahel"], ["libya", "egypt"], ["libya", "sahel"], ["egypt", "sahel"],
  ["egypt", "horn"], ["sahel", "westafrica"], ["sahel", "congo"], ["sahel", "horn"], ["westafrica", "congo"],
  ["horn", "eastafrica"], ["congo", "eastafrica"], ["congo", "southafrica"], ["eastafrica", "southafrica"],
  // South Asia
  ["afghan", "indus"], ["afghan", "kashmir"], ["indus", "kashmir"], ["indus", "ganges"], ["kashmir", "ganges"],
  ["kashmir", "tibet"], ["kashmir", "xinjiang"], ["ganges", "deccan"], ["ganges", "bengal"], ["ganges", "tibet"],
  ["deccan", "bengal"], ["bengal", "indochina"],
  // East Asia
  ["tibet", "xinjiang"], ["tibet", "yangtze"], ["xinjiang", "mongolia"], ["mongolia", "greatwall"],
  ["mongolia", "manchuria"], ["manchuria", "greatwall"], ["manchuria", "korea"], ["greatwall", "yangtze"],
  ["yangtze", "southchina"], ["southchina", "indochina"], ["indochina", "malaya"], ["westaus", "eastaus"],
  // Sea lanes
  ...SEA,
];
export const NEIGHBOURS: Record<string, string[]> = {};
for (const t of TERRITORIES) NEIGHBOURS[t.id] = [];
for (const [a, b] of BORDERS) {
  NEIGHBOURS[a].push(b);
  NEIGHBOURS[b].push(a);
}

/** Sea lanes are drawn dashed. */
export const SEA_LANES = new Set(SEA.map(([a, b]) => [a, b].sort().join("|")));

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
  { id: "usa", name: "USA", faction: "FactionAmerica", side: "USA", color: "#4d8fd6", home: ["plains", "rockies", "texas", "mexico", "california", "centralam"] },
  { id: "superweapon", name: "Superweapon General", faction: "FactionAmericaSuperWeaponGeneral", side: "USA", color: "#62c2e8", home: ["eastcoast", "greatlakes", "gulf", "eastcanada", "caribbean", "westcanada"] },
  { id: "laser", name: "Laser General", faction: "FactionAmericaLaserGeneral", side: "USA", color: "#9a8cf2", home: ["france", "britain", "iberia", "germany", "italy", "scandinavia", "balkans"] },
  { id: "airforce", name: "Air Force General", faction: "FactionAmericaAirForceGeneral", side: "USA", color: "#7fd4c1", home: ["japan", "alaska", "cascadia", "philippines", "indonesia", "westaus", "eastaus"] },
  { id: "china", name: "China", faction: "FactionChina", side: "China", color: "#d9534f", home: ["greatwall", "manchuria", "mongolia", "korea", "fareast", "siberia"] },
  { id: "tank", name: "Tank General", faction: "FactionChinaTankGeneral", side: "China", color: "#e07b39", home: ["moscow", "ural", "ukraine", "poland", "baltic", "caucasus"] },
  { id: "infantry", name: "Infantry General", faction: "FactionChinaInfantryGeneral", side: "China", color: "#c76b98", home: ["ganges", "deccan", "bengal", "kashmir", "indochina", "malaya"] },
  { id: "nuke", name: "Nuke General", faction: "FactionChinaNukeGeneral", side: "China", color: "#e8c547", home: ["yangtze", "southchina", "tibet", "xinjiang", "kazakh", "westsiberia"] },
  { id: "gla", name: "GLA", faction: "FactionGLA", side: "GLA", color: "#8bb65a", home: ["arabia", "levant", "anatolia", "horn", "egypt", "libya"] },
  { id: "toxin", name: "Toxin General", faction: "FactionGLAToxinGeneral", side: "GLA", color: "#b5d63b", home: ["persia", "afghan", "uzbek", "iraq", "gulfstates", "indus"] },
  { id: "demolition", name: "Demolition General", faction: "FactionGLADemolitionGeneral", side: "GLA", color: "#c9a26b", home: ["maghreb", "sahel", "westafrica", "congo", "eastafrica", "southafrica"] },
  { id: "stealth", name: "Stealth General", faction: "FactionGLAStealthGeneral", side: "GLA", color: "#8f9a8c", home: ["brazil", "colombia", "amazon", "andes", "pampas", "patagonia"] },
];

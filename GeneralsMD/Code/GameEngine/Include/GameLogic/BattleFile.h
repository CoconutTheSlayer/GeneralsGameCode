/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2026 TheSuperHackers
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// Battles of the launcher's world conquest: -battle <file> starts a skirmish described by the file
// and writes how it ended to the result file it names, then leaves the game once the player is back
// in the menus. The file has one setting per line:
//
//	map Tournament Desert              map name, as for -skirmish
//	cash 10000                         starting cash
//	seed 42                            random seed (0: random)
//	superweapons 0                     1 limits superweapons
//	result /path/to/result.json        where the result goes
//	player human FactionAmerica 0 0    controller (human, observer, easy, medium, hard), faction, team (-1 for
//	player hard FactionGLA 1 1         none), colour (-1 for any); the first player is slot 0 and so on
//
// The result is JSON: {"outcome": "victory"|"defeat", "frame": N, "players": [{"slot", "team",
// "faction", "victorious", "defeated", "unitsBuilt", "unitsLost", "unitsDestroyed", "buildingsBuilt",
// "buildingsLost", "buildingsDestroyed", "moneyEarned"}, ...]}. Without a result the player left the
// battle before it was decided.

#pragma once

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>
#include <vector>

struct BattlePlayer
{
	std::string controller; // human, observer, easy, medium, hard
	std::string faction;
	int team = -1;
	int color = -1;
};

struct BattleSetup
{
	std::string map;
	int cash = 10000;
	int seed = 0;
	bool limitSuperweapons = false;
	std::string resultPath;
	std::vector<BattlePlayer> players;
};

inline bool LoadBattleFile(const char *path, BattleSetup &setup)
{
	FILE *f = fopen(path, "r");
	if (f == nullptr)
		return false;
	char line[1024];
	while (fgets(line, sizeof(line), f))
	{
		std::string text(line);
		while (!text.empty() && (text.back() == '\n' || text.back() == '\r' || text.back() == ' '))
			text.pop_back();
		const size_t space = text.find(' ');
		if (text.empty() || text[0] == '#' || space == std::string::npos)
			continue;
		const std::string key = text.substr(0, space);
		const std::string value = text.substr(space + 1);
		if (key == "map")
			setup.map = value;
		else if (key == "cash")
			setup.cash = atoi(value.c_str());
		else if (key == "seed")
			setup.seed = atoi(value.c_str());
		else if (key == "superweapons")
			setup.limitSuperweapons = atoi(value.c_str()) != 0;
		else if (key == "result")
			setup.resultPath = value;
		else if (key == "player")
		{
			BattlePlayer player;
			char controller[32] = {}, faction[128] = {};
			int team = -1, color = -1;
			if (sscanf(value.c_str(), "%31s %127s %d %d", controller, faction, &team, &color) >= 2)
			{
				player.controller = controller;
				player.faction = faction;
				player.team = team;
				player.color = color;
				setup.players.push_back(player);
			}
		}
	}
	fclose(f);
	return !setup.map.empty() && !setup.players.empty();
}

// Whether a battle has been played in this run, so the game can quit once the player is back in the
// menus.
inline bool &BattleWasPlayed()
{
	static bool played = false;
	return played;
}

struct BattleResultPlayer
{
	int slot;
	int team;
	std::string faction;
	bool victorious;
	bool defeated;
	int unitsBuilt, unitsLost, unitsDestroyed;
	int buildingsBuilt, buildingsLost, buildingsDestroyed;
	int moneyEarned;
};

inline void WriteBattleResult(const std::string &path, bool victory, unsigned frame, const std::vector<BattleResultPlayer> &players)
{
	if (path.empty())
		return;
	// Written to a temporary file first, so the launcher never reads half a result.
	const std::string temp = path + ".tmp";
	FILE *f = fopen(temp.c_str(), "w");
	if (f == nullptr)
		return;
	fprintf(f, "{\"outcome\": \"%s\", \"frame\": %u, \"players\": [", victory ? "victory" : "defeat", frame);
	for (size_t i = 0; i < players.size(); ++i)
	{
		const BattleResultPlayer &p = players[i];
		fprintf(f, "%s\n  {\"slot\": %d, \"team\": %d, \"faction\": \"%s\", \"victorious\": %s, \"defeated\": %s, "
			"\"unitsBuilt\": %d, \"unitsLost\": %d, \"unitsDestroyed\": %d, \"buildingsBuilt\": %d, "
			"\"buildingsLost\": %d, \"buildingsDestroyed\": %d, \"moneyEarned\": %d}",
			i ? "," : "", p.slot, p.team, p.faction.c_str(), p.victorious ? "true" : "false", p.defeated ? "true" : "false",
			p.unitsBuilt, p.unitsLost, p.unitsDestroyed, p.buildingsBuilt, p.buildingsLost, p.buildingsDestroyed, p.moneyEarned);
	}
	fprintf(f, "\n]}\n");
	fclose(f);
	remove(path.c_str()); // rename does not replace a file on Windows
	rename(temp.c_str(), path.c_str());
}

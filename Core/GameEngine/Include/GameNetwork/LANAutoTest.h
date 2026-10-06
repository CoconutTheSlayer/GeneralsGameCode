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

// GENERALS_LAN_TEST=host:<name> or join:<name> plays a LAN game without input, to test LAN games
// between builds and platforms (scripts/crossplay): the main menu opens the LAN lobby, the host
// creates a game and starts it once everybody has accepted, the other player joins the first game
// listed and accepts, and both say hello in the chat. Chat received is printed as "LAN_TEST chat".

#pragma once

#include "Common/UnicodeString.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>

enum LANTestRole
{
	LAN_TEST_NONE,
	LAN_TEST_HOST,
	LAN_TEST_JOIN,
};

inline LANTestRole GetLANTestRole(UnicodeString *name = nullptr)
{
	const char *env = getenv("GENERALS_LAN_TEST");
	if (env == nullptr)
		return LAN_TEST_NONE;
	LANTestRole role = LAN_TEST_NONE;
	if (strncmp(env, "host", 4) == 0)
		role = LAN_TEST_HOST;
	else if (strncmp(env, "join", 4) == 0)
		role = LAN_TEST_JOIN;
	if (name)
	{
		const char *colon = strchr(env, ':');
		name->translate(AsciiString(colon ? colon + 1 : ""));
	}
	return role;
}

// Prints a line of text with the characters outside ASCII as U+XXXX, to compare between platforms.
inline void PrintLANTestText(const char *what, const UnicodeString &text)
{
	fprintf(stderr, "LAN_TEST %s: ", what);
	for (const WideChar *c = text.str(); *c; ++c)
	{
		if (*c >= 0x20 && *c < 0x7F)
			fputc((char)*c, stderr);
		else
			fprintf(stderr, "U+%04X", (unsigned)*c);
	}
	fputc('\n', stderr);
	fflush(stderr);
}

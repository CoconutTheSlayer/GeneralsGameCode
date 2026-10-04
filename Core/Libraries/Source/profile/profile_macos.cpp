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

// The legacy profiler depends on the Windows only debug library. On macOS the
// profiler entry points the game calls are no-ops.

#include "profile.h"

void Profile::StartRange(const char *) {}
void Profile::AppendRange(const char *) {}
void Profile::StopRange(const char *) {}
bool Profile::IsEnabled() { return false; }
unsigned Profile::GetFrameCount() { return 0; }

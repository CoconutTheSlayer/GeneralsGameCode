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

// FILE: UTF16.h //////////////////////////////////////////////////////////////
// Game data files store text as UTF-16 code units, matching the 2 byte wchar_t
// of Windows. Where wchar_t is wider (macOS), text has to be converted when it
// is read from or written to files.

#pragma once

#include <Lib/BaseType.h>

static_assert(sizeof(UnsignedShort) == 2, "UTF-16 code units must be 2 bytes");

inline void UTF16ToWideChar(const UnsignedShort* src, WideChar* dst, Int len)
{
	for (Int i = 0; i < len; ++i)
		dst[i] = (WideChar)src[i];
}

inline void WideCharToUTF16(const WideChar* src, UnsignedShort* dst, Int len)
{
	for (Int i = 0; i < len; ++i)
		dst[i] = (UnsignedShort)src[i];
}

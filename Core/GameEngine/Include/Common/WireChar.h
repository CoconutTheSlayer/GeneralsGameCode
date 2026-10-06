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

// Text in network packets and replays: UTF-16 code units on every platform, which is what the
// 16-bit wchar_t of Windows writes. macOS and Linux have a 32-bit wchar_t and convert here, so all
// platforms can play together and read each other's replays.

#pragma once

#include "Common/UnicodeString.h"

typedef UnsignedShort WireChar;

// Characters outside the basic multilingual plane, which the game's fonts do not have, become U+FFFD.
inline WireChar toWireChar(WideChar c)
{
	return (UnsignedInt)c <= 0xFFFF ? (WireChar)c : (WireChar)0xFFFD;
}

inline WideChar fromWireChar(WireChar c)
{
	return (WideChar)c;
}

// Copies a string into a fixed size packet field like wcslcpy: at most destCount - 1 characters,
// always terminated.
inline void wireStrlcpy(WireChar *dest, const WideChar *src, size_t destCount)
{
	if (destCount == 0)
		return;
	size_t i = 0;
	for (; i + 1 < destCount && src[i] != 0; ++i)
		dest[i] = toWireChar(src[i]);
	dest[i] = 0;
}

// Reads a packet field of at most maxCount characters, which need not be terminated.
inline UnicodeString wireToUnicode(const WireChar *src, size_t maxCount)
{
	WideChar buf[1024];
	size_t i = 0;
	for (; i < maxCount && i + 1 < ARRAY_SIZE(buf) && src[i] != 0; ++i)
		buf[i] = fromWireChar(src[i]);
	buf[i] = 0;
	return UnicodeString(buf);
}

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

// FILE: MacKeyboard.cpp //////////////////////////////////////////////////////


#include "MacDevice/GameClient/MacKeyboard.h"
#include "GameClient/KeyDefs.h"

#include <win32shim.h>

MacKeyboard::MacKeyboard()
{
}

MacKeyboard::~MacKeyboard()
{
}

void MacKeyboard::init()
{
	Keyboard::init();
}

void MacKeyboard::reset()
{
	Keyboard::reset();
}

void MacKeyboard::update()
{
	Keyboard::update();
}

Bool MacKeyboard::getCapsState()
{
	return Win32Shim_IsCapsLockOn() ? TRUE : FALSE;
}

void MacKeyboard::getKey( KeyboardIO *key )
{
	key->key = KEY_NONE;

	UnsignedByte scanCode;
	bool down;
	UnsignedInt timeMsec;
	if (!Win32Shim_PopKeyEvent(&scanCode, &down, &timeMsec))
		return;

	key->key = scanCode;
	key->status = KeyboardIO::STATUS_UNUSED;
	if (down)
	{
		key->state = KEY_STATE_DOWN;
		key->keyDownTimeMsec = timeMsec;
	}
	else
	{
		key->state = KEY_STATE_UP;
	}
}

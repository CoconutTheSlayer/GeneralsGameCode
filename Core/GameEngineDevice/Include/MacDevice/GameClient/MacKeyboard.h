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

// FILE: MacKeyboard.h ////////////////////////////////////////////////////////
// Keyboard device for macOS. Key events are produced by the SDL event pump in the
// Win32 shim as DirectInput scan codes, which is what the game uses as key ids.

#pragma once

#include "GameClient/Keyboard.h"

class MacKeyboard : public Keyboard
{
public:
	MacKeyboard();
	virtual ~MacKeyboard() override;

	virtual void init() override;
	virtual void reset() override;
	virtual void update() override;
	virtual Bool getCapsState() override;

protected:
	virtual void getKey( KeyboardIO *key ) override;
};

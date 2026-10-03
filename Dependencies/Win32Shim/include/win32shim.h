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

// macOS specific entry points of the Win32 shim that the game calls directly.
#pragma once

#include <windows.h>

struct SDL_Window;

// Initializes SDL and changes to the install directory ($GENERALS_INSTALL_PATH).
void Win32Shim_Initialize();

// Stores argv so GetCommandLine() works.
void Win32Shim_SetCommandLine(int argc, char** argv);

// Keyboard events from the SDL event pump, as DirectInput (DIK_*) scan codes.
bool Win32Shim_PopKeyEvent(unsigned char* scanCode, bool* down, unsigned int* timeMsec);
bool Win32Shim_IsCapsLockOn();

// The SDL window backing a shim HWND (the main window if hwnd is unknown).
SDL_Window* Win32Shim_GetSDLWindow(HWND hwnd);

// Sets the client size the game believes the window has. Mouse coordinates are
// scaled from the real window size to this size.
void Win32Shim_SetLogicalSize(HWND hwnd, int width, int height);

// Creates a cursor from 32 bit ARGB pixels.
HCURSOR Win32Shim_CreateCursorFromRGBA(const void* pixels, int width, int height, int hotX, int hotY);

// Area of the window (in window points) where the game image is presented, used
// to map mouse coordinates when the image is letterboxed.
void Win32Shim_SetPresentRect(HWND hwnd, float x, float y, float w, float h);

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

// Initializes SDL.
void Win32Shim_Initialize();

// Copies stdout and stderr into a new log file in ~/Library/Logs/Command and Conquer Generals
// (<appName>-<date>-<pid>.log, with <appName>-latest.log pointing at it), writes a header with
// the version and system, and appends a stack trace when the game crashes. The newest 20 logs of
// each game are kept. GENERALS_NO_LOG=1 turns it off. Call after Win32Shim_SetCommandLine.
void Win32Shim_StartSessionLog(const char* appName, const char* version);
// Folder with art the fork adds to the game data (GameData in the application bundle's Resources, or
// resources/macos/GameData of the source tree for builds outside a bundle), or null if there is none.
const char* Win32Shim_GetExtraDataDirectory();

// Folder of the session logs (created when needed), or null if HOME is not set.
const char* Win32Shim_GetLogDirectory();

// Finds the game data folders (environment variables GENERALS_ZH_PATH /
// GENERALS_PATH, saved settings, the working directory or a folder picker),
// records them in the emulated registry and changes the working directory to the
// data folder of the game being started (Zero Hour or the original Generals).
void Win32Shim_LocateGameData(bool zeroHour);

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

// Whether presentation waits for the display refresh (vsync). Set by the
// renderer; the frame pacer then leaves the render rate limit to vsync.
void Win32Shim_SetPresentationSynced(bool synced);
bool Win32Shim_IsPresentationSynced();

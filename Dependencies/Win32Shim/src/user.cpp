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

// user32 subset implemented on SDL3: windows, the message queue, keyboard and
// mouse input, cursors and message boxes.
//
// The game keeps its Win32 window procedure. SDL events are translated into the
// equivalent WM_* messages and dispatched to it. Window coordinates are exposed
// in the game's logical resolution (the size the game asked for), independent of
// the actual window size, so the game never has to know about scaling.

#define NOMINMAX
#include <windows.h>
#include <win32shim.h>
#include "win32shim_internal.h"

#include <SDL3/SDL.h>

#include <algorithm>
#include <atomic>
#include <csignal>
#include <sys/stat.h>
#include <deque>
#include <map>
#include <string>
#include <vector>

namespace
{
bool alwaysActive()
{
	static const bool value = getenv("GENERALS_ALWAYS_ACTIVE") != nullptr;
	return value;
}


struct WindowClass
{
	WNDPROC proc = nullptr;
	HCURSOR cursor = nullptr;
};

struct Window
{
	SDL_Window* sdl = nullptr;
	WNDPROC proc = nullptr;
	DWORD style = 0;
	DWORD exStyle = 0;
	LONG_PTR userData = 0;
	int logicalWidth = 800;
	int logicalHeight = 600;
	bool visible = false;
	// Area of the window (in points) that shows the game image; empty = whole window.
	float presentX = 0, presentY = 0, presentW = 0, presentH = 0;
};

struct KeyEvent
{
	unsigned char scanCode;
	bool down;
	unsigned int time;
};

std::map<std::string, WindowClass> g_classes;
std::vector<Window*> g_windows;
std::deque<MSG> g_messages;
std::deque<KeyEvent> g_keyEvents;
bool g_quitPosted = false;
int g_quitCode = 0;
int g_cursorShowCount = 0;
BYTE g_vkState[256];
// DirectInput scan codes the game has seen go down and not up yet.
bool g_dikDown[256];
bool g_sdlInitialized = false;

Window* toWindow(HWND hwnd)
{
	for (Window* w : g_windows)
	{
		if ((HWND)w == hwnd)
			return w;
	}
	return nullptr;
}

Window* mainWindow()
{
	return g_windows.empty() ? nullptr : g_windows.front();
}

void ensureSDL()
{
	if (g_sdlInitialized)
		return;
	SDL_SetHint(SDL_HINT_MOUSE_FOCUS_CLICKTHROUGH, "1");
	SDL_SetHint(SDL_HINT_MAC_OPTION_AS_ALT, "both");
	// Fullscreen without a separate Space: the menu bar and the Dock stay hidden. In a fullscreen Space,
	// moving the mouse against the top or bottom edge reveals them, and while they are shown the game gets
	// no mouse movement, so scrolling the map at the screen edge stopped now and then.
	SDL_SetHint(SDL_HINT_VIDEO_MAC_FULLSCREEN_SPACES, "0");
	if (!SDL_Init(SDL_INIT_VIDEO | SDL_INIT_EVENTS))
		fprintf(stderr, "SDL_Init failed: %s\n", SDL_GetError());
	g_sdlInitialized = true;
}

// Maps window points to the game's logical client coordinates.
void presentArea(Window* w, float* x, float* y, float* pw, float* ph)
{
	if (w->presentW > 0 && w->presentH > 0)
	{
		*x = w->presentX;
		*y = w->presentY;
		*pw = w->presentW;
		*ph = w->presentH;
		return;
	}
	int ww = 0, wh = 0;
	SDL_GetWindowSize(w->sdl, &ww, &wh);
	*x = 0;
	*y = 0;
	*pw = (float)ww;
	*ph = (float)wh;
}

void toLogical(Window* w, float x, float y, int* lx, int* ly)
{
	float ax, ay, aw, ah;
	presentArea(w, &ax, &ay, &aw, &ah);
	if (aw <= 0 || ah <= 0)
	{
		*lx = (int)x;
		*ly = (int)y;
		return;
	}
	*lx = (int)((x - ax) * w->logicalWidth / aw);
	*ly = (int)((y - ay) * w->logicalHeight / ah);
	// The black bars around a game area of another aspect ratio count as its edge, so pushing the mouse
	// into them still scrolls the map.
	if (w->logicalWidth > 0 && w->logicalHeight > 0)
	{
		*lx = std::clamp(*lx, 0, w->logicalWidth - 1);
		*ly = std::clamp(*ly, 0, w->logicalHeight - 1);
	}
}

void postMessage(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
	MSG m;
	memset(&m, 0, sizeof(m));
	m.hwnd = hwnd;
	m.message = msg;
	m.wParam = wParam;
	m.lParam = lParam;
	m.time = GetTickCount();
	g_messages.push_back(m);
}

//-----------------------------------------------------------------------------
// Key translation
//-----------------------------------------------------------------------------
// SDL scancode -> DirectInput scan code (DIK_*).
unsigned char scancodeToDik(SDL_Scancode sc)
{
	switch (sc)
	{
	case SDL_SCANCODE_ESCAPE: return 0x01;
	case SDL_SCANCODE_1: return 0x02;
	case SDL_SCANCODE_2: return 0x03;
	case SDL_SCANCODE_3: return 0x04;
	case SDL_SCANCODE_4: return 0x05;
	case SDL_SCANCODE_5: return 0x06;
	case SDL_SCANCODE_6: return 0x07;
	case SDL_SCANCODE_7: return 0x08;
	case SDL_SCANCODE_8: return 0x09;
	case SDL_SCANCODE_9: return 0x0A;
	case SDL_SCANCODE_0: return 0x0B;
	case SDL_SCANCODE_MINUS: return 0x0C;
	case SDL_SCANCODE_EQUALS: return 0x0D;
	case SDL_SCANCODE_BACKSPACE: return 0x0E;
	case SDL_SCANCODE_TAB: return 0x0F;
	case SDL_SCANCODE_Q: return 0x10;
	case SDL_SCANCODE_W: return 0x11;
	case SDL_SCANCODE_E: return 0x12;
	case SDL_SCANCODE_R: return 0x13;
	case SDL_SCANCODE_T: return 0x14;
	case SDL_SCANCODE_Y: return 0x15;
	case SDL_SCANCODE_U: return 0x16;
	case SDL_SCANCODE_I: return 0x17;
	case SDL_SCANCODE_O: return 0x18;
	case SDL_SCANCODE_P: return 0x19;
	case SDL_SCANCODE_LEFTBRACKET: return 0x1A;
	case SDL_SCANCODE_RIGHTBRACKET: return 0x1B;
	case SDL_SCANCODE_RETURN: return 0x1C;
	case SDL_SCANCODE_LCTRL: return 0x1D;
	case SDL_SCANCODE_A: return 0x1E;
	case SDL_SCANCODE_S: return 0x1F;
	case SDL_SCANCODE_D: return 0x20;
	case SDL_SCANCODE_F: return 0x21;
	case SDL_SCANCODE_G: return 0x22;
	case SDL_SCANCODE_H: return 0x23;
	case SDL_SCANCODE_J: return 0x24;
	case SDL_SCANCODE_K: return 0x25;
	case SDL_SCANCODE_L: return 0x26;
	case SDL_SCANCODE_SEMICOLON: return 0x27;
	case SDL_SCANCODE_APOSTROPHE: return 0x28;
	case SDL_SCANCODE_GRAVE: return 0x29;
	case SDL_SCANCODE_LSHIFT: return 0x2A;
	case SDL_SCANCODE_BACKSLASH: return 0x2B;
	case SDL_SCANCODE_Z: return 0x2C;
	case SDL_SCANCODE_X: return 0x2D;
	case SDL_SCANCODE_C: return 0x2E;
	case SDL_SCANCODE_V: return 0x2F;
	case SDL_SCANCODE_B: return 0x30;
	case SDL_SCANCODE_N: return 0x31;
	case SDL_SCANCODE_M: return 0x32;
	case SDL_SCANCODE_COMMA: return 0x33;
	case SDL_SCANCODE_PERIOD: return 0x34;
	case SDL_SCANCODE_SLASH: return 0x35;
	case SDL_SCANCODE_RSHIFT: return 0x36;
	case SDL_SCANCODE_KP_MULTIPLY: return 0x37;
	case SDL_SCANCODE_LALT: return 0x38;
	case SDL_SCANCODE_SPACE: return 0x39;
	case SDL_SCANCODE_CAPSLOCK: return 0x3A;
	case SDL_SCANCODE_F1: return 0x3B;
	case SDL_SCANCODE_F2: return 0x3C;
	case SDL_SCANCODE_F3: return 0x3D;
	case SDL_SCANCODE_F4: return 0x3E;
	case SDL_SCANCODE_F5: return 0x3F;
	case SDL_SCANCODE_F6: return 0x40;
	case SDL_SCANCODE_F7: return 0x41;
	case SDL_SCANCODE_F8: return 0x42;
	case SDL_SCANCODE_F9: return 0x43;
	case SDL_SCANCODE_F10: return 0x44;
	case SDL_SCANCODE_NUMLOCKCLEAR: return 0x45;
	case SDL_SCANCODE_SCROLLLOCK: return 0x46;
	case SDL_SCANCODE_KP_7: return 0x47;
	case SDL_SCANCODE_KP_8: return 0x48;
	case SDL_SCANCODE_KP_9: return 0x49;
	case SDL_SCANCODE_KP_MINUS: return 0x4A;
	case SDL_SCANCODE_KP_4: return 0x4B;
	case SDL_SCANCODE_KP_5: return 0x4C;
	case SDL_SCANCODE_KP_6: return 0x4D;
	case SDL_SCANCODE_KP_PLUS: return 0x4E;
	case SDL_SCANCODE_KP_1: return 0x4F;
	case SDL_SCANCODE_KP_2: return 0x50;
	case SDL_SCANCODE_KP_3: return 0x51;
	case SDL_SCANCODE_KP_0: return 0x52;
	case SDL_SCANCODE_KP_PERIOD: return 0x53;
	case SDL_SCANCODE_NONUSBACKSLASH: return 0x56;
	case SDL_SCANCODE_F11: return 0x57;
	case SDL_SCANCODE_F12: return 0x58;
	case SDL_SCANCODE_KP_ENTER: return 0x9C;
	case SDL_SCANCODE_RCTRL: return 0x9D;
	case SDL_SCANCODE_KP_DIVIDE: return 0xB5;
	case SDL_SCANCODE_PRINTSCREEN: return 0xB7;
	case SDL_SCANCODE_RALT: return 0xB8;
	case SDL_SCANCODE_PAUSE: return 0xC5;
	case SDL_SCANCODE_HOME: return 0xC7;
	case SDL_SCANCODE_UP: return 0xC8;
	case SDL_SCANCODE_PAGEUP: return 0xC9;
	case SDL_SCANCODE_LEFT: return 0xCB;
	case SDL_SCANCODE_RIGHT: return 0xCD;
	case SDL_SCANCODE_END: return 0xCF;
	case SDL_SCANCODE_DOWN: return 0xD0;
	case SDL_SCANCODE_PAGEDOWN: return 0xD1;
	case SDL_SCANCODE_INSERT: return 0xD2;
	case SDL_SCANCODE_DELETE: return 0xD3;
	// The Command keys act as the Windows keys.
	case SDL_SCANCODE_LGUI: return 0xDB;
	case SDL_SCANCODE_RGUI: return 0xDC;
	case SDL_SCANCODE_APPLICATION: return 0xDD;
	default: return 0;
	}
}

// SDL scancode -> Windows virtual key.
int scancodeToVk(SDL_Scancode sc)
{
	if (sc >= SDL_SCANCODE_A && sc <= SDL_SCANCODE_Z)
		return 'A' + (sc - SDL_SCANCODE_A);
	if (sc >= SDL_SCANCODE_1 && sc <= SDL_SCANCODE_9)
		return '1' + (sc - SDL_SCANCODE_1);
	if (sc == SDL_SCANCODE_0)
		return '0';
	if (sc >= SDL_SCANCODE_F1 && sc <= SDL_SCANCODE_F12)
		return VK_F1 + (sc - SDL_SCANCODE_F1);
	if (sc >= SDL_SCANCODE_KP_1 && sc <= SDL_SCANCODE_KP_9)
		return VK_NUMPAD1 + (sc - SDL_SCANCODE_KP_1);
	switch (sc)
	{
	case SDL_SCANCODE_KP_0: return VK_NUMPAD0;
	case SDL_SCANCODE_ESCAPE: return VK_ESCAPE;
	case SDL_SCANCODE_RETURN: return VK_RETURN;
	case SDL_SCANCODE_KP_ENTER: return VK_RETURN;
	case SDL_SCANCODE_BACKSPACE: return VK_BACK;
	case SDL_SCANCODE_TAB: return VK_TAB;
	case SDL_SCANCODE_SPACE: return VK_SPACE;
	case SDL_SCANCODE_LSHIFT: return VK_LSHIFT;
	case SDL_SCANCODE_RSHIFT: return VK_RSHIFT;
	case SDL_SCANCODE_LCTRL: return VK_LCONTROL;
	case SDL_SCANCODE_RCTRL: return VK_RCONTROL;
	case SDL_SCANCODE_LALT: return VK_LMENU;
	case SDL_SCANCODE_RALT: return VK_RMENU;
	case SDL_SCANCODE_LGUI: return VK_LWIN;
	case SDL_SCANCODE_RGUI: return VK_RWIN;
	case SDL_SCANCODE_CAPSLOCK: return VK_CAPITAL;
	case SDL_SCANCODE_PAUSE: return VK_PAUSE;
	case SDL_SCANCODE_PAGEUP: return VK_PRIOR;
	case SDL_SCANCODE_PAGEDOWN: return VK_NEXT;
	case SDL_SCANCODE_END: return VK_END;
	case SDL_SCANCODE_HOME: return VK_HOME;
	case SDL_SCANCODE_LEFT: return VK_LEFT;
	case SDL_SCANCODE_UP: return VK_UP;
	case SDL_SCANCODE_RIGHT: return VK_RIGHT;
	case SDL_SCANCODE_DOWN: return VK_DOWN;
	case SDL_SCANCODE_INSERT: return VK_INSERT;
	case SDL_SCANCODE_DELETE: return VK_DELETE;
	case SDL_SCANCODE_PRINTSCREEN: return VK_SNAPSHOT;
	case SDL_SCANCODE_NUMLOCKCLEAR: return VK_NUMLOCK;
	case SDL_SCANCODE_SCROLLLOCK: return VK_SCROLL;
	case SDL_SCANCODE_KP_MULTIPLY: return VK_MULTIPLY;
	case SDL_SCANCODE_KP_PLUS: return VK_ADD;
	case SDL_SCANCODE_KP_MINUS: return VK_SUBTRACT;
	case SDL_SCANCODE_KP_PERIOD: return VK_DECIMAL;
	case SDL_SCANCODE_KP_DIVIDE: return VK_DIVIDE;
	case SDL_SCANCODE_SEMICOLON: return VK_OEM_1;
	case SDL_SCANCODE_EQUALS: return VK_OEM_PLUS;
	case SDL_SCANCODE_COMMA: return VK_OEM_COMMA;
	case SDL_SCANCODE_MINUS: return VK_OEM_MINUS;
	case SDL_SCANCODE_PERIOD: return VK_OEM_PERIOD;
	case SDL_SCANCODE_SLASH: return VK_OEM_2;
	case SDL_SCANCODE_GRAVE: return VK_OEM_3;
	case SDL_SCANCODE_LEFTBRACKET: return VK_OEM_4;
	case SDL_SCANCODE_BACKSLASH: return VK_OEM_5;
	case SDL_SCANCODE_RIGHTBRACKET: return VK_OEM_6;
	case SDL_SCANCODE_APOSTROPHE: return VK_OEM_7;
	default: return 0;
	}
}

void setVkState(int vk, bool down)
{
	if (vk <= 0 || vk > 255)
		return;
	if (down)
		g_vkState[vk] |= 0x80;
	else
		g_vkState[vk] &= ~0x80;
	// Maintain the generic modifier keys too.
	if (vk == VK_LSHIFT || vk == VK_RSHIFT)
		setVkState(VK_SHIFT, (g_vkState[VK_LSHIFT] | g_vkState[VK_RSHIFT]) & 0x80);
	else if (vk == VK_LCONTROL || vk == VK_RCONTROL)
		setVkState(VK_CONTROL, (g_vkState[VK_LCONTROL] | g_vkState[VK_RCONTROL]) & 0x80);
	else if (vk == VK_LMENU || vk == VK_RMENU)
		setVkState(VK_MENU, (g_vkState[VK_LMENU] | g_vkState[VK_RMENU]) & 0x80);
}

WPARAM mouseKeyFlags()
{
	WPARAM flags = 0;
	SDL_MouseButtonFlags buttons = SDL_GetMouseState(nullptr, nullptr);
	if (buttons & SDL_BUTTON_LMASK)
		flags |= MK_LBUTTON;
	if (buttons & SDL_BUTTON_RMASK)
		flags |= MK_RBUTTON;
	if (buttons & SDL_BUTTON_MMASK)
		flags |= MK_MBUTTON;
	if (g_vkState[VK_SHIFT] & 0x80)
		flags |= MK_SHIFT;
	if (g_vkState[VK_CONTROL] & 0x80)
		flags |= MK_CONTROL;
	return flags;
}

LPARAM makePointParam(int x, int y)
{
	return (LPARAM)(DWORD)MAKELONG((WORD)(SHORT)x, (WORD)(SHORT)y);
}

// Converts one SDL event into zero or more queued window messages.
void translateEvent(const SDL_Event& e)
{
	Window* w = mainWindow();
	if (w == nullptr)
	{
		if (e.type == SDL_EVENT_QUIT)
			g_quitPosted = true;
		return;
	}
	HWND hwnd = (HWND)w;

	switch (e.type)
	{
	case SDL_EVENT_QUIT:
	case SDL_EVENT_WINDOW_CLOSE_REQUESTED:
		postMessage(hwnd, WM_CLOSE, 0, 0);
		break;

	case SDL_EVENT_WINDOW_FOCUS_GAINED:
		postMessage(hwnd, WM_ACTIVATEAPP, TRUE, 0);
		postMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0);
		postMessage(hwnd, WM_SETFOCUS, 0, 0);
		break;

	case SDL_EVENT_WINDOW_FOCUS_LOST:
	{
		// Release all keys and mouse buttons so nothing stays stuck while inactive: the window gets no
		// key or button up for what was held when switching away (Cmd+Tab), and the game would keep
		// scrolling the camera or dragging a selection.
		for (int dik = 0; dik < 256; ++dik)
		{
			if (g_dikDown[dik])
			{
				g_keyEvents.push_back(KeyEvent { (unsigned char)dik, false, GetTickCount() });
				g_dikDown[dik] = false;
			}
		}
		{
			float mx, my;
			SDL_GetMouseState(&mx, &my);
			int x, y;
			toLogical(w, mx, my, &x, &y);
			const struct { int vk; UINT msg; } buttons[] = {
				{ VK_LBUTTON, WM_LBUTTONUP }, { VK_RBUTTON, WM_RBUTTONUP }, { VK_MBUTTON, WM_MBUTTONUP } };
			for (const auto& b : buttons)
			{
				if (g_vkState[b.vk] & 0x80)
				{
					g_vkState[b.vk] &= ~0x80;
					postMessage(hwnd, b.msg, mouseKeyFlags(), makePointParam(x, y));
				}
			}
		}
		for (int vk = 0; vk < 256; ++vk)
			g_vkState[vk] &= ~0x80;
		// GENERALS_ALWAYS_ACTIVE=1 keeps the game running and rendering in the background, for testing.
		if (alwaysActive())
			break;
		postMessage(hwnd, WM_KILLFOCUS, 0, 0);
		postMessage(hwnd, WM_ACTIVATE, WA_INACTIVE, 0);
		postMessage(hwnd, WM_ACTIVATEAPP, FALSE, 0);
		break;
	}

	case SDL_EVENT_WINDOW_MINIMIZED:
		postMessage(hwnd, WM_SIZE, SIZE_MINIMIZED, 0);
		break;

	case SDL_EVENT_WINDOW_RESTORED:
		postMessage(hwnd, WM_SIZE, SIZE_RESTORED, makePointParam(w->logicalWidth, w->logicalHeight));
		break;

	case SDL_EVENT_KEY_DOWN:
	case SDL_EVENT_KEY_UP:
	{
		bool down = e.type == SDL_EVENT_KEY_DOWN;
		unsigned char dik = scancodeToDik(e.key.scancode);
		if (dik != 0 && !e.key.repeat)
		{
			g_keyEvents.push_back(KeyEvent { dik, down, GetTickCount() });
			g_dikDown[dik] = down;
		}

		int vk = scancodeToVk(e.key.scancode);
		setVkState(vk, down);
		if (vk != 0)
		{
			LPARAM lParam = 1 | ((LPARAM)dik << 16);
			if (e.key.repeat)
				lParam |= (LPARAM)1 << 30;
			if (!down)
				lParam |= ((LPARAM)1 << 30) | ((LPARAM)1 << 31);
			bool alt = (g_vkState[VK_MENU] & 0x80) != 0;
			UINT msg = down ? (alt ? WM_SYSKEYDOWN : WM_KEYDOWN) : (alt ? WM_SYSKEYUP : WM_KEYUP);
			postMessage(hwnd, msg, (WPARAM)vk, lParam);
			// Control characters that SDL does not deliver as text input.
			if (down && (vk == VK_BACK || vk == VK_RETURN || vk == VK_ESCAPE || vk == VK_TAB))
			{
				WPARAM ch = vk == VK_BACK ? 8 : vk == VK_RETURN ? 13 : vk == VK_ESCAPE ? 27 : 9;
				postMessage(hwnd, WM_CHAR, ch, lParam);
			}
		}
		break;
	}

	case SDL_EVENT_TEXT_INPUT:
	{
		// UTF-8 -> one WM_CHAR per code point.
		const unsigned char* s = (const unsigned char*)e.text.text;
		while (*s)
		{
			uint32_t c = *s++;
			if (c >= 0x80)
			{
				int extra = (c >= 0xF0) ? 3 : (c >= 0xE0) ? 2 : 1;
				c &= (0x3F >> extra);
				while (extra-- > 0 && *s)
					c = (c << 6) | (*s++ & 0x3F);
			}
			postMessage(hwnd, WM_CHAR, (WPARAM)c, 1);
		}
		break;
	}

	case SDL_EVENT_MOUSE_MOTION:
	{
		int x, y;
		toLogical(w, e.motion.x, e.motion.y, &x, &y);
		postMessage(hwnd, WM_SETCURSOR, (WPARAM)hwnd, HTCLIENT);
		postMessage(hwnd, WM_MOUSEMOVE, mouseKeyFlags(), makePointParam(x, y));
		break;
	}

	case SDL_EVENT_MOUSE_BUTTON_DOWN:
	case SDL_EVENT_MOUSE_BUTTON_UP:
	{
		int x, y;
		toLogical(w, e.button.x, e.button.y, &x, &y);
		bool down = e.type == SDL_EVENT_MOUSE_BUTTON_DOWN;
		bool dbl = down && e.button.clicks >= 2 && (e.button.clicks % 2) == 0;
		UINT msg = 0;
		int vk = 0;
		switch (e.button.button)
		{
		case SDL_BUTTON_LEFT:
			msg = down ? (dbl ? WM_LBUTTONDBLCLK : WM_LBUTTONDOWN) : WM_LBUTTONUP;
			vk = VK_LBUTTON;
			break;
		case SDL_BUTTON_RIGHT:
			msg = down ? (dbl ? WM_RBUTTONDBLCLK : WM_RBUTTONDOWN) : WM_RBUTTONUP;
			vk = VK_RBUTTON;
			break;
		case SDL_BUTTON_MIDDLE:
			msg = down ? (dbl ? WM_MBUTTONDBLCLK : WM_MBUTTONDOWN) : WM_MBUTTONUP;
			vk = VK_MBUTTON;
			break;
		default:
			break;
		}
		setVkState(vk, down);
		if (msg != 0)
			postMessage(hwnd, msg, mouseKeyFlags(), makePointParam(x, y));
		break;
	}

	case SDL_EVENT_MOUSE_WHEEL:
	{
		float mx, my;
		SDL_GetMouseState(&mx, &my);
		int x, y;
		toLogical(w, mx, my, &x, &y);
		float amount = e.wheel.y;
		if (e.wheel.direction == SDL_MOUSEWHEEL_FLIPPED)
			amount = -amount;
		int delta = (int)(amount * WHEEL_DELTA);
		if (delta != 0)
			postMessage(hwnd, WM_MOUSEWHEEL, MAKELONG(mouseKeyFlags(), (WORD)(SHORT)delta), makePointParam(x, y));
		break;
	}

	default:
		break;
	}
}

void pumpSDL()
{
	SDL_Event e;
	while (SDL_PollEvent(&e))
		translateEvent(e);
}

} // namespace

//-----------------------------------------------------------------------------
// Shim entry points
//-----------------------------------------------------------------------------
bool Win32Shim_PopKeyEvent(unsigned char* scanCode, bool* down, unsigned int* timeMsec)
{
	if (g_keyEvents.empty())
		return false;
	KeyEvent e = g_keyEvents.front();
	g_keyEvents.pop_front();
	*scanCode = e.scanCode;
	*down = e.down;
	*timeMsec = e.time;
	return true;
}

bool Win32Shim_IsCapsLockOn()
{
	return (SDL_GetModState() & SDL_KMOD_CAPS) != 0;
}

SDL_Window* Win32Shim_GetSDLWindow(HWND hwnd)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		w = mainWindow();
	return w ? w->sdl : nullptr;
}

void Win32Shim_SetLogicalSize(HWND hwnd, int width, int height)
{
	if (Window* w = toWindow(hwnd))
	{
		w->logicalWidth = width;
		w->logicalHeight = height;
	}
}

namespace
{
std::atomic<bool> g_presentationSynced{true};
}

void Win32Shim_SetPresentationSynced(bool synced)
{
	g_presentationSynced.store(synced, std::memory_order_relaxed);
}

bool Win32Shim_IsPresentationSynced()
{
	return g_presentationSynced.load(std::memory_order_relaxed);
}

void Win32Shim_SetPresentRect(HWND hwnd, float x, float y, float w, float h)
{
	if (Window* win = toWindow(hwnd))
	{
		win->presentX = x;
		win->presentY = y;
		win->presentW = w;
		win->presentH = h;
	}
}

namespace
{
const char* kZeroHourKey = "SOFTWARE\\Electronic Arts\\EA Games\\Command and Conquer Generals Zero Hour";
const char* kGeneralsKey = "SOFTWARE\\Electronic Arts\\EA Games\\Generals";

bool fileExistsCaseInsensitive(const std::string& dir, const char* name)
{
	std::string pattern = dir + "/" + name;
	WIN32_FIND_DATA fd;
	HANDLE h = FindFirstFile(pattern.c_str(), &fd);
	if (h == INVALID_HANDLE_VALUE)
		return false;
	FindClose(h);
	return true;
}

bool isZeroHourDir(const std::string& dir)
{
	return !dir.empty() && fileExistsCaseInsensitive(dir, "INIZH.big");
}

bool isGeneralsDir(const std::string& dir)
{
	return !dir.empty() && fileExistsCaseInsensitive(dir, "INI.big") && fileExistsCaseInsensitive(dir, "W3D.big");
}

std::string readInstallPath(const char* key)
{
	HKEY h;
	if (RegOpenKeyEx(HKEY_LOCAL_MACHINE, key, 0, KEY_READ, &h) != ERROR_SUCCESS)
		return std::string();
	char buffer[MAX_PATH] = {};
	DWORD size = sizeof(buffer) - 1;
	DWORD type = 0;
	std::string result;
	if (RegQueryValueEx(h, "InstallPath", nullptr, &type, (BYTE*)buffer, &size) == ERROR_SUCCESS && type == REG_SZ)
		result = buffer;
	RegCloseKey(h);
	while (result.size() > 1 && (result.back() == '/' || result.back() == '\\'))
		result.pop_back();
	return result;
}

void writeInstallPath(const char* key, const std::string& path)
{
	HKEY h;
	if (RegCreateKeyEx(HKEY_LOCAL_MACHINE, key, 0, nullptr, 0, KEY_ALL_ACCESS, nullptr, &h, nullptr) != ERROR_SUCCESS)
		return;
	std::string value = path + "/";
	RegSetValueEx(h, "InstallPath", 0, REG_SZ, (const BYTE*)value.c_str(), (DWORD)value.size() + 1);
	RegCloseKey(h);
}

// Shows a native folder picker and waits for the answer.
std::string chooseFolder(const char* title)
{
	struct Result
	{
		bool done = false;
		std::string path;
	} result;
	SDL_DialogFileCallback callback = [](void* userdata, const char* const* filelist, int) {
		Result* r = static_cast<Result*>(userdata);
		if (filelist && filelist[0])
			r->path = filelist[0];
		r->done = true;
	};
	SDL_PropertiesID props = SDL_CreateProperties();
	SDL_SetStringProperty(props, SDL_PROP_FILE_DIALOG_TITLE_STRING, title);
	SDL_SetStringProperty(props, SDL_PROP_FILE_DIALOG_ACCEPT_STRING, "Select");
	SDL_ShowFileDialogWithProperties(SDL_FILEDIALOG_OPENFOLDER, callback, &result, props);
	while (!result.done)
	{
		SDL_PumpEvents();
		SDL_Delay(10);
	}
	SDL_DestroyProperties(props);
	return result.path;
}

// A folder named by an environment variable is used even without the archives, for example
// for loose files, as long as it exists.
bool envDir(const char* name, std::string& out)
{
	const char* env = getenv(name);
	if (env == nullptr || *env == '\0')
		return false;
	struct stat st;
	if (stat(env, &st) != 0 || !S_ISDIR(st.st_mode))
	{
		fprintf(stderr, "%s=%s is not a folder, ignoring it\n", name, env);
		return false;
	}
	out = env;
	return true;
}

std::string parentDir(const std::string& dir)
{
	size_t slash = dir.find_last_of('/');
	return slash == std::string::npos || slash == 0 ? std::string("/") : dir.substr(0, slash);
}

// Locates the original Generals data for the base game executable.
void locateGeneralsInstallation()
{
	std::string generals;
	if (envDir("GENERALS_PATH", generals))
	{
		if (!isGeneralsDir(generals))
			fprintf(stderr, "Warning: INI.big not found in GENERALS_PATH\n");
	}
	else
	{
		char cwd[PATH_MAX];
		std::string saved = readInstallPath(kGeneralsKey);
		if (isGeneralsDir(saved))
			generals = saved;
		else if (getcwd(cwd, sizeof(cwd)) && isGeneralsDir(cwd))
			generals = cwd;
		else
		{
			SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_INFORMATION, "Command & Conquer Generals",
				"Please select the folder containing your Generals game files (the folder with INI.big and W3D.big).", nullptr);
			generals = chooseFolder("Select the Generals folder");
		}
	}
	if (!generals.empty())
	{
		writeInstallPath(kGeneralsKey, generals);
		chdir(generals.c_str());
	}
	fprintf(stderr, "Generals data: %s\n", generals.empty() ? "(not found)" : generals.c_str());
}

// Locates the game data folders and records them where the game looks for them.
void locateInstallation()
{
	std::string zh;
	if (envDir("GENERALS_ZH_PATH", zh) || envDir("GENERALS_INSTALL_PATH", zh))
	{
		if (!isZeroHourDir(zh))
			fprintf(stderr, "Warning: INIZH.big not found in the Zero Hour folder\n");
	}
	else
	{
		char cwd[PATH_MAX];
		std::string saved = readInstallPath(kZeroHourKey);
		if (isZeroHourDir(saved))
			zh = saved;
		else if (getcwd(cwd, sizeof(cwd)) && isZeroHourDir(cwd))
			zh = cwd;
		else
		{
			SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_INFORMATION, "Command & Conquer Generals Zero Hour",
				"Please select the folder containing your Zero Hour game files (the folder with INIZH.big).", nullptr);
			zh = chooseFolder("Select the Zero Hour folder");
		}
	}

	std::string generals;
	if (envDir("GENERALS_PATH", generals))
	{
		if (!isGeneralsDir(generals))
			fprintf(stderr, "Warning: INI.big not found in GENERALS_PATH\n");
	}
	else
	{
		std::string saved = readInstallPath(kGeneralsKey);
		if (isGeneralsDir(saved))
			generals = saved;
		else if (isGeneralsDir(zh))
			generals = zh;
		else
		{
			// Typical layouts keep both games next to each other.
			std::string parent = parentDir(zh);
			for (const char* name : { "Command and Conquer Generals", "Command & Conquer Generals", "Generals", "C&C Generals" })
			{
				std::string candidate = parent + "/" + name;
				if (isGeneralsDir(candidate))
				{
					generals = candidate;
					break;
				}
			}
			if (!isGeneralsDir(generals) && isGeneralsDir(parent))
				generals = parent;
			if (!isGeneralsDir(generals) && !zh.empty())
			{
				SDL_ShowSimpleMessageBox(SDL_MESSAGEBOX_INFORMATION, "Command & Conquer Generals Zero Hour",
					"Zero Hour also needs the original Generals game files. Please select the Generals folder (the folder with INI.big and W3D.big).", nullptr);
				generals = chooseFolder("Select the Generals folder");
			}
		}
	}

	if (!zh.empty())
	{
		writeInstallPath(kZeroHourKey, zh);
		chdir(zh.c_str());
	}
	if (!generals.empty())
		writeInstallPath(kGeneralsKey, generals);
	fprintf(stderr, "Zero Hour data: %s\nGenerals data: %s\n", zh.empty() ? "(not found)" : zh.c_str(), generals.empty() ? "(not found)" : generals.c_str());
}
} // namespace

void Win32Shim_Initialize()
{
	// Writing to a closed socket must return an error like on Windows instead of
	// terminating the process.
	signal(SIGPIPE, SIG_IGN);
	ensureSDL();
	memset(g_vkState, 0, sizeof(g_vkState));
}

void Win32Shim_LocateGameData(bool zeroHour)
{
	ensureSDL();
	if (zeroHour)
		locateInstallation();
	else
		locateGeneralsInstallation();
}

//-----------------------------------------------------------------------------
// Messages
//-----------------------------------------------------------------------------
BOOL PeekMessage(LPMSG msg, HWND, UINT, UINT, UINT remove)
{
	if (g_messages.empty())
		pumpSDL();
	if (g_messages.empty())
	{
		if (g_quitPosted)
		{
			memset(msg, 0, sizeof(*msg));
			msg->message = WM_QUIT;
			msg->wParam = (WPARAM)g_quitCode;
			if (remove & PM_REMOVE)
				g_quitPosted = false;
			return TRUE;
		}
		return FALSE;
	}
	*msg = g_messages.front();
	if (remove & PM_REMOVE)
		g_messages.pop_front();
	return TRUE;
}

BOOL GetMessage(LPMSG msg, HWND hwnd, UINT min, UINT max)
{
	while (!PeekMessage(msg, hwnd, min, max, PM_REMOVE))
		SDL_WaitEventTimeout(nullptr, 10);
	return msg->message != WM_QUIT;
}

BOOL WaitMessage()
{
	SDL_WaitEventTimeout(nullptr, 10);
	return TRUE;
}

BOOL TranslateMessage(const MSG*)
{
	// WM_CHAR messages are generated from SDL text input events.
	return TRUE;
}

LRESULT DispatchMessage(const MSG* msg)
{
	Window* w = toWindow(msg->hwnd);
	if (w == nullptr || w->proc == nullptr)
		return 0;
	return w->proc(msg->hwnd, msg->message, msg->wParam, msg->lParam);
}

BOOL PostMessage(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
	postMessage(hwnd, msg, wParam, lParam);
	return TRUE;
}

LRESULT SendMessage(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr || w->proc == nullptr)
		return 0;
	return w->proc(hwnd, msg, wParam, lParam);
}

void PostQuitMessage(int code)
{
	g_quitPosted = true;
	g_quitCode = code;
}

LRESULT DefWindowProc(HWND hwnd, UINT msg, WPARAM, LPARAM)
{
	switch (msg)
	{
	case WM_CLOSE:
		DestroyWindow(hwnd);
		return 0;
	case WM_SETCURSOR:
		return TRUE;
	default:
		return 0;
	}
}

UINT_PTR SetTimer(HWND, UINT_PTR id, UINT, TIMERPROC)
{
	return id ? id : 1;
}

BOOL KillTimer(HWND, UINT_PTR)
{
	return TRUE;
}

//-----------------------------------------------------------------------------
// Windows
//-----------------------------------------------------------------------------
ATOM RegisterClass(const WNDCLASS* wc)
{
	WindowClass c;
	c.proc = wc->lpfnWndProc;
	c.cursor = wc->hCursor;
	g_classes[wc->lpszClassName ? wc->lpszClassName : ""] = c;
	return (ATOM)g_classes.size();
}

ATOM RegisterClassEx(const WNDCLASSEX* wc)
{
	WindowClass c;
	c.proc = wc->lpfnWndProc;
	c.cursor = wc->hCursor;
	g_classes[wc->lpszClassName ? wc->lpszClassName : ""] = c;
	return (ATOM)g_classes.size();
}

BOOL UnregisterClass(LPCSTR className, HINSTANCE)
{
	return g_classes.erase(className ? className : "") != 0;
}

HWND CreateWindowEx(DWORD exStyle, LPCSTR className, LPCSTR windowName, DWORD style, int, int, int w, int h, HWND, HMENU, HINSTANCE, LPVOID param)
{
	ensureSDL();
	auto cls = g_classes.find(className ? className : "");
	if (cls == g_classes.end())
		return nullptr;

	if (w <= 0 || w == CW_USEDEFAULT)
		w = 800;
	if (h <= 0 || h == CW_USEDEFAULT)
		h = 600;

	SDL_WindowFlags flags = SDL_WINDOW_METAL | SDL_WINDOW_HIDDEN | SDL_WINDOW_RESIZABLE;
	if (!(style & WS_CAPTION))
		flags |= SDL_WINDOW_BORDERLESS;

	Window* win = new Window();
	win->sdl = SDL_CreateWindow(windowName ? windowName : "", w, h, flags);
	if (win->sdl == nullptr)
	{
		fprintf(stderr, "SDL_CreateWindow failed: %s\n", SDL_GetError());
		delete win;
		return nullptr;
	}
	win->proc = cls->second.proc;
	win->style = style;
	win->exStyle = exStyle;
	win->logicalWidth = w;
	win->logicalHeight = h;
	g_windows.push_back(win);
	HWND hwnd = (HWND)win;

	SDL_StartTextInput(win->sdl);

	CREATESTRUCT cs;
	memset(&cs, 0, sizeof(cs));
	cs.lpCreateParams = param;
	cs.cx = w;
	cs.cy = h;
	cs.style = (LONG)style;
	cs.lpszName = windowName;
	cs.lpszClass = className;
	if (win->proc)
	{
		win->proc(hwnd, WM_NCCREATE, 0, (LPARAM)&cs);
		win->proc(hwnd, WM_CREATE, 0, (LPARAM)&cs);
	}

	if (style & WS_VISIBLE)
		ShowWindow(hwnd, SW_SHOW);
	if (alwaysActive())
	{
		postMessage(hwnd, WM_ACTIVATEAPP, TRUE, 0);
		postMessage(hwnd, WM_ACTIVATE, WA_ACTIVE, 0);
	}
	return hwnd;
}

BOOL DestroyWindow(HWND hwnd)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return FALSE;
	if (w->proc)
		w->proc(hwnd, WM_DESTROY, 0, 0);
	SDL_DestroyWindow(w->sdl);
	g_windows.erase(std::find(g_windows.begin(), g_windows.end(), w));
	delete w;
	return TRUE;
}

BOOL ShowWindow(HWND hwnd, int cmd)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return FALSE;
	bool wasVisible = w->visible;
	switch (cmd)
	{
	case SW_HIDE:
		SDL_HideWindow(w->sdl);
		w->visible = false;
		break;
	case SW_MINIMIZE:
	case SW_SHOWMINIMIZED:
		SDL_MinimizeWindow(w->sdl);
		break;
	case SW_MAXIMIZE:
		SDL_ShowWindow(w->sdl);
		SDL_MaximizeWindow(w->sdl);
		w->visible = true;
		break;
	case SW_RESTORE:
		SDL_RestoreWindow(w->sdl);
		SDL_ShowWindow(w->sdl);
		w->visible = true;
		break;
	default:
		SDL_ShowWindow(w->sdl);
		SDL_RaiseWindow(w->sdl);
		w->visible = true;
		break;
	}
	return wasVisible;
}

BOOL UpdateWindow(HWND)
{
	return TRUE;
}

BOOL SetWindowPos(HWND hwnd, HWND, int x, int y, int cx, int cy, UINT flags)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return FALSE;
	if (!(flags & SWP_NOSIZE) && cx > 0 && cy > 0)
	{
		w->logicalWidth = cx;
		w->logicalHeight = cy;
		if (!(SDL_GetWindowFlags(w->sdl) & SDL_WINDOW_FULLSCREEN))
			SDL_SetWindowSize(w->sdl, cx, cy);
	}
	if (!(flags & SWP_NOMOVE) && !(SDL_GetWindowFlags(w->sdl) & SDL_WINDOW_FULLSCREEN))
	{
		// The game positions windows in screen coordinates; keep them on screen.
		if (x == 0 && y == 0)
			SDL_SetWindowPosition(w->sdl, SDL_WINDOWPOS_CENTERED, SDL_WINDOWPOS_CENTERED);
		else
			SDL_SetWindowPosition(w->sdl, x, y);
	}
	if (flags & SWP_SHOWWINDOW)
		ShowWindow(hwnd, SW_SHOW);
	if (flags & SWP_HIDEWINDOW)
		ShowWindow(hwnd, SW_HIDE);
	return TRUE;
}

BOOL MoveWindow(HWND hwnd, int x, int y, int w, int h, BOOL)
{
	return SetWindowPos(hwnd, nullptr, x, y, w, h, SWP_NOZORDER);
}

BOOL GetClientRect(HWND hwnd, LPRECT rect)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
	{
		SetRectEmpty(rect);
		return FALSE;
	}
	SetRect(rect, 0, 0, w->logicalWidth, w->logicalHeight);
	return TRUE;
}

BOOL GetWindowRect(HWND hwnd, LPRECT rect)
{
	// Client and screen coordinates are identical in this shim.
	return GetClientRect(hwnd, rect);
}

BOOL AdjustWindowRect(LPRECT, DWORD, BOOL)
{
	// Window frames are handled by the OS; the client size is the window size.
	return TRUE;
}

BOOL AdjustWindowRectEx(LPRECT, DWORD, BOOL, DWORD)
{
	return TRUE;
}

BOOL ClientToScreen(HWND, LPPOINT)
{
	return TRUE;
}

BOOL ScreenToClient(HWND, LPPOINT)
{
	return TRUE;
}

BOOL SetWindowText(HWND hwnd, LPCSTR text)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return FALSE;
	SDL_SetWindowTitle(w->sdl, text ? text : "");
	return TRUE;
}

BOOL SetWindowTextW(HWND hwnd, LPCWSTR text)
{
	char buffer[512];
	WideCharToMultiByte(CP_UTF8, 0, text, -1, buffer, sizeof(buffer), nullptr, nullptr);
	return SetWindowText(hwnd, buffer);
}

LONG GetWindowLong(HWND hwnd, int index)
{
	return (LONG)GetWindowLongPtr(hwnd, index);
}

LONG SetWindowLong(HWND hwnd, int index, LONG value)
{
	return (LONG)SetWindowLongPtr(hwnd, index, value);
}

LONG_PTR GetWindowLongPtr(HWND hwnd, int index)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return 0;
	switch (index)
	{
	case GWL_STYLE: return (LONG_PTR)w->style;
	case GWL_EXSTYLE: return (LONG_PTR)w->exStyle;
	case GWL_USERDATA: return w->userData;
	case GWL_WNDPROC: return (LONG_PTR)w->proc;
	default: return 0;
	}
}

LONG_PTR SetWindowLongPtr(HWND hwnd, int index, LONG_PTR value)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return 0;
	LONG_PTR old = GetWindowLongPtr(hwnd, index);
	switch (index)
	{
	case GWL_STYLE:
		w->style = (DWORD)value;
		SDL_SetWindowBordered(w->sdl, (w->style & WS_CAPTION) != 0);
		break;
	case GWL_EXSTYLE: w->exStyle = (DWORD)value; break;
	case GWL_USERDATA: w->userData = value; break;
	case GWL_WNDPROC: w->proc = (WNDPROC)value; break;
	default: break;
	}
	return old;
}

HWND GetForegroundWindow()
{
	Window* w = mainWindow();
	if (w && (SDL_GetWindowFlags(w->sdl) & SDL_WINDOW_INPUT_FOCUS))
		return (HWND)w;
	return nullptr;
}

BOOL SetForegroundWindow(HWND hwnd)
{
	Window* w = toWindow(hwnd);
	if (w == nullptr)
		return FALSE;
	SDL_RaiseWindow(w->sdl);
	return TRUE;
}

HWND GetActiveWindow() { return GetForegroundWindow(); }
HWND GetFocus() { return GetForegroundWindow(); }
HWND SetFocus(HWND hwnd)
{
	HWND old = GetFocus();
	SetForegroundWindow(hwnd);
	return old;
}

HWND GetDesktopWindow()
{
	// Any distinct non-null handle.
	return (HWND)(uintptr_t)0x10;
}

HWND FindWindow(LPCSTR, LPCSTR)
{
	return nullptr;
}

BOOL IsWindow(HWND hwnd) { return toWindow(hwnd) != nullptr; }
BOOL IsWindowVisible(HWND hwnd)
{
	Window* w = toWindow(hwnd);
	return w && w->visible;
}
BOOL IsIconic(HWND hwnd)
{
	Window* w = toWindow(hwnd);
	return w && (SDL_GetWindowFlags(w->sdl) & SDL_WINDOW_MINIMIZED);
}
BOOL IsZoomed(HWND hwnd)
{
	Window* w = toWindow(hwnd);
	return w && (SDL_GetWindowFlags(w->sdl) & SDL_WINDOW_MAXIMIZED);
}
BOOL BringWindowToTop(HWND hwnd) { return SetForegroundWindow(hwnd); }
BOOL InvalidateRect(HWND, const RECT*, BOOL) { return TRUE; }
BOOL ValidateRect(HWND, const RECT*) { return TRUE; }

HWND SetCapture(HWND hwnd)
{
	SDL_CaptureMouse(true);
	return hwnd;
}

BOOL ReleaseCapture()
{
	SDL_CaptureMouse(false);
	return TRUE;
}

DWORD GetWindowThreadProcessId(HWND, LPDWORD processId)
{
	if (processId)
		*processId = GetCurrentProcessId();
	return GetCurrentThreadId();
}

int GetSystemMetrics(int index)
{
	ensureSDL();
	SDL_Rect bounds = { 0, 0, 1920, 1080 };
	SDL_GetDisplayBounds(SDL_GetPrimaryDisplay(), &bounds);
	switch (index)
	{
	case SM_CXSCREEN:
	case SM_CXVIRTUALSCREEN:
		return bounds.w;
	case SM_CYSCREEN:
	case SM_CYVIRTUALSCREEN:
		return bounds.h;
	case SM_CXDOUBLECLK:
	case SM_CYDOUBLECLK:
		return 4;
	default:
		return 0;
	}
}

UINT GetDoubleClickTime()
{
	return 500;
}

HDC BeginPaint(HWND hwnd, LPPAINTSTRUCT ps)
{
	memset(ps, 0, sizeof(*ps));
	ps->hdc = GetDC(hwnd);
	return ps->hdc;
}

BOOL EndPaint(HWND hwnd, const PAINTSTRUCT* ps)
{
	ReleaseDC(hwnd, ps->hdc);
	return TRUE;
}

HMONITOR MonitorFromWindow(HWND, DWORD)
{
	return (HMONITOR)(uintptr_t)1;
}

BOOL GetMonitorInfo(HMONITOR, LPMONITORINFO info)
{
	ensureSDL();
	SDL_Rect bounds = { 0, 0, 1920, 1080 };
	SDL_Rect usable = bounds;
	SDL_DisplayID display = SDL_GetPrimaryDisplay();
	SDL_GetDisplayBounds(display, &bounds);
	SDL_GetDisplayUsableBounds(display, &usable);
	SetRect(&info->rcMonitor, bounds.x, bounds.y, bounds.x + bounds.w, bounds.y + bounds.h);
	SetRect(&info->rcWork, usable.x, usable.y, usable.x + usable.w, usable.y + usable.h);
	info->dwFlags = MONITORINFOF_PRIMARY;
	return TRUE;
}

BOOL EnumDisplaySettings(LPCSTR, DWORD mode, LPDEVMODE dm)
{
	ensureSDL();
	SDL_DisplayID display = SDL_GetPrimaryDisplay();
	const SDL_DisplayMode* m = nullptr;
	if (mode == ENUM_CURRENT_SETTINGS)
		m = SDL_GetDesktopDisplayMode(display);
	else
	{
		int count = 0;
		SDL_DisplayMode** modes = SDL_GetFullscreenDisplayModes(display, &count);
		if (modes && (int)mode < count)
		{
			static SDL_DisplayMode copy;
			copy = *modes[mode];
			m = &copy;
		}
		SDL_free(modes);
	}
	if (m == nullptr)
		return FALSE;
	memset(dm, 0, sizeof(*dm));
	dm->dmSize = sizeof(*dm);
	// Like Windows, report physical pixels; on Retina displays the mode size is in points.
	dm->dmPelsWidth = (DWORD)(m->w * m->pixel_density + 0.5f);
	dm->dmPelsHeight = (DWORD)(m->h * m->pixel_density + 0.5f);
	dm->dmBitsPerPel = 32;
	// Round fractional rates such as 59.94 Hz instead of truncating them.
	dm->dmDisplayFrequency = (DWORD)(m->refresh_rate + 0.5f);
	dm->dmFields = DM_PELSWIDTH | DM_PELSHEIGHT | DM_BITSPERPEL | DM_DISPLAYFREQUENCY;
	return TRUE;
}

LONG ChangeDisplaySettings(LPDEVMODE, DWORD)
{
	// Display modes are never changed; fullscreen uses the desktop mode.
	return DISP_CHANGE_SUCCESSFUL;
}

BOOL SystemParametersInfo(UINT action, UINT, PVOID pvParam, UINT)
{
	switch (action)
	{
	case SPI_GETSCREENSAVEACTIVE:
		if (pvParam)
			*(BOOL*)pvParam = FALSE;
		return TRUE;
	case SPI_GETMOUSESPEED:
		if (pvParam)
			*(int*)pvParam = 10;
		return TRUE;
	case SPI_GETWORKAREA:
		if (pvParam)
		{
			MONITORINFO info;
			GetMonitorInfo(nullptr, &info);
			*(RECT*)pvParam = info.rcWork;
		}
		return TRUE;
	default:
		return TRUE;
	}
}

//-----------------------------------------------------------------------------
// Keyboard state
//-----------------------------------------------------------------------------
SHORT GetAsyncKeyState(int vkey)
{
	if (vkey == VK_LBUTTON || vkey == VK_RBUTTON || vkey == VK_MBUTTON)
	{
		SDL_MouseButtonFlags buttons = SDL_GetGlobalMouseState(nullptr, nullptr);
		bool down = (vkey == VK_LBUTTON && (buttons & SDL_BUTTON_LMASK)) || (vkey == VK_RBUTTON && (buttons & SDL_BUTTON_RMASK))
			|| (vkey == VK_MBUTTON && (buttons & SDL_BUTTON_MMASK));
		return down ? (SHORT)0x8000 : 0;
	}
	if (vkey < 0 || vkey > 255)
		return 0;
	return (g_vkState[vkey] & 0x80) ? (SHORT)0x8000 : 0;
}

SHORT GetKeyState(int vkey)
{
	if (vkey == VK_CAPITAL)
		return Win32Shim_IsCapsLockOn() ? 1 : 0;
	if (vkey == VK_NUMLOCK)
		return (SDL_GetModState() & SDL_KMOD_NUM) ? 1 : 0;
	return GetAsyncKeyState(vkey);
}

BOOL GetKeyboardState(PBYTE state)
{
	memcpy(state, g_vkState, 256);
	if (Win32Shim_IsCapsLockOn())
		state[VK_CAPITAL] |= 1;
	return TRUE;
}

UINT MapVirtualKey(UINT code, UINT mapType)
{
	if (mapType == MAPVK_VK_TO_CHAR)
	{
		if ((code >= '0' && code <= '9') || (code >= 'A' && code <= 'Z'))
			return code;
		return 0;
	}
	return 0;
}

int ToAscii(UINT vkey, UINT, const BYTE* keyState, LPWORD out, UINT)
{
	if (vkey >= 'A' && vkey <= 'Z')
	{
		bool shift = keyState && (keyState[VK_SHIFT] & 0x80);
		*out = (WORD)(shift ? vkey : (vkey - 'A' + 'a'));
		return 1;
	}
	if ((vkey >= '0' && vkey <= '9') || vkey == VK_SPACE)
	{
		*out = (WORD)vkey;
		return 1;
	}
	return 0;
}

HKL GetKeyboardLayout(DWORD)
{
	return (HKL)(uintptr_t)0x0409;
}

//-----------------------------------------------------------------------------
// Cursor
//-----------------------------------------------------------------------------
namespace
{
struct CursorObject
{
	SDL_Cursor* cursor = nullptr;
};

HCURSOR g_currentCursor = nullptr;

HCURSOR systemCursor(SDL_SystemCursor id)
{
	static std::map<int, CursorObject*> cache;
	auto it = cache.find(id);
	if (it != cache.end())
		return (HCURSOR)it->second;
	ensureSDL();
	CursorObject* c = new CursorObject();
	c->cursor = SDL_CreateSystemCursor(id);
	cache[id] = c;
	return (HCURSOR)c;
}
} // namespace

HCURSOR Win32Shim_CreateCursorFromRGBA(const void* pixels, int width, int height, int hotX, int hotY)
{
	SDL_Surface* surface = SDL_CreateSurfaceFrom(width, height, SDL_PIXELFORMAT_ARGB8888, const_cast<void*>(pixels), width * 4);
	if (surface == nullptr)
		return nullptr;
	CursorObject* c = new CursorObject();
	c->cursor = SDL_CreateColorCursor(surface, hotX, hotY);
	SDL_DestroySurface(surface);
	if (c->cursor == nullptr)
	{
		delete c;
		return nullptr;
	}
	return (HCURSOR)c;
}

HCURSOR LoadCursor(HINSTANCE, LPCSTR name)
{
	uintptr_t id = (uintptr_t)name;
	if (id == (uintptr_t)IDC_IBEAM)
		return systemCursor(SDL_SYSTEM_CURSOR_TEXT);
	if (id == (uintptr_t)IDC_WAIT)
		return systemCursor(SDL_SYSTEM_CURSOR_WAIT);
	if (id == (uintptr_t)IDC_CROSS)
		return systemCursor(SDL_SYSTEM_CURSOR_CROSSHAIR);
	return systemCursor(SDL_SYSTEM_CURSOR_DEFAULT);
}

HCURSOR SetCursor(HCURSOR cursor)
{
	HCURSOR old = g_currentCursor;
	g_currentCursor = cursor;
	if (cursor)
	{
		CursorObject* c = (CursorObject*)cursor;
		if (c->cursor)
			SDL_SetCursor(c->cursor);
		SDL_ShowCursor();
	}
	else
		SDL_HideCursor();
	return old;
}

BOOL DestroyCursor(HCURSOR cursor)
{
	if (cursor == nullptr)
		return FALSE;
	CursorObject* c = (CursorObject*)cursor;
	if (g_currentCursor == cursor)
		g_currentCursor = nullptr;
	SDL_DestroyCursor(c->cursor);
	delete c;
	return TRUE;
}

int ShowCursor(BOOL show)
{
	g_cursorShowCount += show ? 1 : -1;
	if (g_cursorShowCount >= 0)
		SDL_ShowCursor();
	else
		SDL_HideCursor();
	return g_cursorShowCount;
}

BOOL GetCursorPos(LPPOINT pt)
{
	Window* w = mainWindow();
	float x = 0, y = 0;
	SDL_GetMouseState(&x, &y);
	if (w)
	{
		int lx, ly;
		toLogical(w, x, y, &lx, &ly);
		pt->x = lx;
		pt->y = ly;
	}
	else
	{
		pt->x = (LONG)x;
		pt->y = (LONG)y;
	}
	return TRUE;
}

BOOL SetCursorPos(int x, int y)
{
	Window* w = mainWindow();
	if (w == nullptr)
		return FALSE;
	float ax, ay, aw, ah;
	presentArea(w, &ax, &ay, &aw, &ah);
	SDL_WarpMouseInWindow(w->sdl, ax + (float)x * aw / w->logicalWidth, ay + (float)y * ah / w->logicalHeight);
	return TRUE;
}

BOOL ClipCursor(const RECT* rect)
{
	Window* w = mainWindow();
	if (w == nullptr)
		return FALSE;
	if (rect == nullptr)
	{
		SDL_SetWindowMouseGrab(w->sdl, false);
		return TRUE;
	}
	// Only confine when the game clips to its own client area.
	SDL_SetWindowMouseGrab(w->sdl, true);
	return TRUE;
}

//-----------------------------------------------------------------------------
// Message boxes
//-----------------------------------------------------------------------------
int MessageBoxA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type)
{
	fprintf(stderr, "[MessageBox] %s: %s\n", caption ? caption : "", text ? text : "");
	if (getenv("GENERALS_NO_MESSAGEBOX"))
	{
		// Unattended runs: pick the default button, but keep going after assertions
		// (Abort/Retry/Ignore) like the game does in fullscreen.
		switch (type & 0x0F)
		{
		case MB_YESNO:
		case MB_YESNOCANCEL: return IDYES;
		case MB_RETRYCANCEL: return IDCANCEL;
		case MB_ABORTRETRYIGNORE: return IDIGNORE;
		default: return IDOK;
		}
	}
	ensureSDL();
	SDL_MessageBoxButtonData buttons[3];
	int count = 0;
	auto add = [&](int id, const char* label, SDL_MessageBoxButtonFlags flags) {
		buttons[count].buttonID = id;
		buttons[count].text = label;
		buttons[count].flags = flags;
		++count;
	};
	switch (type & 0x0F)
	{
	case MB_OKCANCEL:
		add(IDOK, "OK", SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT);
		add(IDCANCEL, "Cancel", SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT);
		break;
	case MB_ABORTRETRYIGNORE:
		add(IDABORT, "Abort", SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT);
		add(IDRETRY, "Retry", 0);
		add(IDIGNORE, "Ignore", SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT);
		break;
	case MB_YESNOCANCEL:
		add(IDYES, "Yes", SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT);
		add(IDNO, "No", 0);
		add(IDCANCEL, "Cancel", SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT);
		break;
	case MB_YESNO:
		add(IDYES, "Yes", SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT);
		add(IDNO, "No", SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT);
		break;
	case MB_RETRYCANCEL:
		add(IDRETRY, "Retry", SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT);
		add(IDCANCEL, "Cancel", SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT);
		break;
	default:
		add(IDOK, "OK", SDL_MESSAGEBOX_BUTTON_RETURNKEY_DEFAULT | SDL_MESSAGEBOX_BUTTON_ESCAPEKEY_DEFAULT);
		break;
	}

	SDL_MessageBoxData data;
	memset(&data, 0, sizeof(data));
	UINT icon = type & 0xF0;
	data.flags = icon == MB_ICONERROR ? SDL_MESSAGEBOX_ERROR : icon == MB_ICONWARNING ? SDL_MESSAGEBOX_WARNING : SDL_MESSAGEBOX_INFORMATION;
	data.window = hwnd ? Win32Shim_GetSDLWindow(hwnd) : nullptr;
	data.title = caption ? caption : "";
	data.message = text ? text : "";
	data.numbuttons = count;
	data.buttons = buttons;

	// Do not show modal boxes over a fullscreen game window that would hide them.
	if (data.window && (SDL_GetWindowFlags(data.window) & SDL_WINDOW_FULLSCREEN))
		SDL_SetWindowFullscreen(data.window, false);

	int result = buttons[0].buttonID;
	if (!SDL_ShowMessageBox(&data, &result))
		fprintf(stderr, "%s: %s\n", data.title, data.message);
	return result;
}

int MessageBoxW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type)
{
	std::string t, c;
	if (text)
	{
		int n = WideCharToMultiByte(CP_UTF8, 0, text, -1, nullptr, 0, nullptr, nullptr);
		t.resize((size_t)n);
		WideCharToMultiByte(CP_UTF8, 0, text, -1, &t[0], n, nullptr, nullptr);
	}
	if (caption)
	{
		int n = WideCharToMultiByte(CP_UTF8, 0, caption, -1, nullptr, 0, nullptr, nullptr);
		c.resize((size_t)n);
		WideCharToMultiByte(CP_UTF8, 0, caption, -1, &c[0], n, nullptr, nullptr);
	}
	return MessageBoxA(hwnd, t.c_str(), c.c_str(), type);
}

//-----------------------------------------------------------------------------
// Resources (none are embedded in the macOS executable)
//-----------------------------------------------------------------------------
HICON LoadIcon(HINSTANCE, LPCSTR) { return nullptr; }
BOOL DestroyIcon(HICON) { return TRUE; }
HANDLE LoadImage(HINSTANCE, LPCSTR, UINT, int, int, UINT) { return nullptr; }
int LoadString(HINSTANCE, UINT, LPSTR buffer, int len)
{
	if (buffer && len > 0)
		buffer[0] = 0;
	return 0;
}

HINSTANCE ShellExecute(HWND, LPCSTR, LPCSTR file, LPCSTR, LPCSTR, INT)
{
	// Open URLs and documents with the default macOS handler.
	if (file && *file)
	{
		if (strstr(file, "://"))
			SDL_OpenURL(file);
		else
		{
			std::string url = "file://" + Win32Shim_TranslatePath(file);
			SDL_OpenURL(url.c_str());
		}
	}
	return (HINSTANCE)(uintptr_t)33;
}

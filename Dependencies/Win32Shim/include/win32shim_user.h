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

// user32 / gdi32 / imm32 subset. Included from windows.h.
#pragma once

//-----------------------------------------------------------------------------
// Messages
//-----------------------------------------------------------------------------
typedef struct tagMSG {
	HWND hwnd;
	UINT message;
	WPARAM wParam;
	LPARAM lParam;
	DWORD time;
	POINT pt;
} MSG, *PMSG, *LPMSG;

typedef LRESULT (*WNDPROC)(HWND, UINT, WPARAM, LPARAM);
typedef INT_PTR (*DLGPROC)(HWND, UINT, WPARAM, LPARAM);
typedef void (*TIMERPROC)(HWND, UINT, UINT_PTR, DWORD);

typedef struct tagWNDCLASSA {
	UINT style;
	WNDPROC lpfnWndProc;
	int cbClsExtra;
	int cbWndExtra;
	HINSTANCE hInstance;
	HICON hIcon;
	HCURSOR hCursor;
	HBRUSH hbrBackground;
	LPCSTR lpszMenuName;
	LPCSTR lpszClassName;
} WNDCLASSA, WNDCLASS, *LPWNDCLASS;

typedef struct tagWNDCLASSEXA {
	UINT cbSize;
	UINT style;
	WNDPROC lpfnWndProc;
	int cbClsExtra;
	int cbWndExtra;
	HINSTANCE hInstance;
	HICON hIcon;
	HCURSOR hCursor;
	HBRUSH hbrBackground;
	LPCSTR lpszMenuName;
	LPCSTR lpszClassName;
	HICON hIconSm;
} WNDCLASSEXA, WNDCLASSEX, *LPWNDCLASSEX;

#define WM_NULL 0x0000
#define WM_CREATE 0x0001
#define WM_DESTROY 0x0002
#define WM_MOVE 0x0003
#define WM_SIZE 0x0005
#define WM_ACTIVATE 0x0006
#define WM_SETFOCUS 0x0007
#define WM_KILLFOCUS 0x0008
#define WM_ENABLE 0x000A
#define WM_PAINT 0x000F
#define WM_CLOSE 0x0010
#define WM_QUERYENDSESSION 0x0011
#define WM_QUIT 0x0012
#define WM_ERASEBKGND 0x0014
#define WM_SYSCOLORCHANGE 0x0015
#define WM_ENDSESSION 0x0016
#define WM_SHOWWINDOW 0x0018
#define WM_ACTIVATEAPP 0x001C
#define WM_SETCURSOR 0x0020
#define WM_MOUSEACTIVATE 0x0021
#define WM_GETMINMAXINFO 0x0024
#define WM_WINDOWPOSCHANGING 0x0046
#define WM_WINDOWPOSCHANGED 0x0047
#define WM_POWER 0x0048
#define WM_NCCREATE 0x0081
#define WM_NCDESTROY 0x0082
#define WM_NCHITTEST 0x0084
#define WM_NCPAINT 0x0085
#define WM_NCACTIVATE 0x0086
#define WM_NCMOUSEMOVE 0x00A0
#define WM_NCLBUTTONDOWN 0x00A1
#define WM_KEYFIRST 0x0100
#define WM_KEYDOWN 0x0100
#define WM_KEYUP 0x0101
#define WM_CHAR 0x0102
#define WM_DEADCHAR 0x0103
#define WM_SYSKEYDOWN 0x0104
#define WM_SYSKEYUP 0x0105
#define WM_SYSCHAR 0x0106
#define WM_KEYLAST 0x0108
#define WM_UNICHAR 0x0109
#define WM_IME_STARTCOMPOSITION 0x010D
#define WM_IME_ENDCOMPOSITION 0x010E
#define WM_IME_COMPOSITION 0x010F
#define WM_IME_KEYLAST 0x010F
#define WM_INITDIALOG 0x0110
#define WM_COMMAND 0x0111
#define WM_SYSCOMMAND 0x0112
#define WM_TIMER 0x0113
#define WM_MOUSEFIRST 0x0200
#define WM_MOUSEMOVE 0x0200
#define WM_LBUTTONDOWN 0x0201
#define WM_LBUTTONUP 0x0202
#define WM_LBUTTONDBLCLK 0x0203
#define WM_RBUTTONDOWN 0x0204
#define WM_RBUTTONUP 0x0205
#define WM_RBUTTONDBLCLK 0x0206
#define WM_MBUTTONDOWN 0x0207
#define WM_MBUTTONUP 0x0208
#define WM_MBUTTONDBLCLK 0x0209
#define WM_MOUSEWHEEL 0x020A
#define WM_MOUSELAST 0x020A
#define WM_POWERBROADCAST 0x0218
#define WM_DEVICECHANGE 0x0219
#define WM_IME_SETCONTEXT 0x0281
#define WM_IME_NOTIFY 0x0282
#define WM_IME_CONTROL 0x0283
#define WM_IME_COMPOSITIONFULL 0x0284
#define WM_IME_SELECT 0x0285
#define WM_IME_CHAR 0x0286
#define WM_IME_REQUEST 0x0288
#define WM_IME_KEYDOWN 0x0290
#define WM_IME_KEYUP 0x0291
#define WM_MOUSEHOVER 0x02A1
#define WM_MOUSELEAVE 0x02A3
#define WM_USER 0x0400
#define WM_APP 0x8000
#define WHEEL_DELTA 120
#define GET_WHEEL_DELTA_WPARAM(wParam) ((short)HIWORD(wParam))

#define WA_INACTIVE 0
#define WA_ACTIVE 1
#define WA_CLICKACTIVE 2
#define SC_SIZE 0xF000
#define SC_MOVE 0xF010
#define SC_KEYMENU 0xF100
#define SC_SCREENSAVE 0xF140
#define SC_MONITORPOWER 0xF170
#define SC_CLOSE 0xF060
#define SC_MINIMIZE 0xF020
#define SC_MAXIMIZE 0xF030
#define SIZE_RESTORED 0
#define SIZE_MINIMIZED 1
#define SIZE_MAXIMIZED 2
#define MK_LBUTTON 0x0001
#define MK_RBUTTON 0x0002
#define MK_SHIFT 0x0004
#define MK_CONTROL 0x0008
#define MK_MBUTTON 0x0010
#define PM_NOREMOVE 0x0000
#define PM_REMOVE 0x0001
#define HTCLIENT 1

BOOL PeekMessage(LPMSG msg, HWND hwnd, UINT min, UINT max, UINT remove);
#define PeekMessageA PeekMessage
BOOL GetMessage(LPMSG msg, HWND hwnd, UINT min, UINT max);
#define GetMessageA GetMessage
BOOL TranslateMessage(const MSG* msg);
LRESULT DispatchMessage(const MSG* msg);
#define DispatchMessageA DispatchMessage
BOOL PostMessage(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
#define PostMessageA PostMessage
LRESULT SendMessage(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
#define SendMessageA SendMessage
void PostQuitMessage(int code);
LRESULT DefWindowProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam);
#define DefWindowProcA DefWindowProc
BOOL WaitMessage();
UINT_PTR SetTimer(HWND hwnd, UINT_PTR id, UINT elapse, TIMERPROC func);
BOOL KillTimer(HWND hwnd, UINT_PTR id);

//-----------------------------------------------------------------------------
// Windows
//-----------------------------------------------------------------------------
#define WS_OVERLAPPED 0x00000000L
#define WS_POPUP 0x80000000L
#define WS_CHILD 0x40000000L
#define WS_MINIMIZE 0x20000000L
#define WS_VISIBLE 0x10000000L
#define WS_DISABLED 0x08000000L
#define WS_CLIPSIBLINGS 0x04000000L
#define WS_CLIPCHILDREN 0x02000000L
#define WS_MAXIMIZE 0x01000000L
#define WS_CAPTION 0x00C00000L
#define WS_BORDER 0x00800000L
#define WS_DLGFRAME 0x00400000L
#define WS_SYSMENU 0x00080000L
#define WS_THICKFRAME 0x00040000L
#define WS_MINIMIZEBOX 0x00020000L
#define WS_MAXIMIZEBOX 0x00010000L
#define WS_OVERLAPPEDWINDOW (WS_OVERLAPPED | WS_CAPTION | WS_SYSMENU | WS_THICKFRAME | WS_MINIMIZEBOX | WS_MAXIMIZEBOX)
#define WS_POPUPWINDOW (WS_POPUP | WS_BORDER | WS_SYSMENU)
#define WS_EX_TOPMOST 0x00000008L
#define WS_EX_APPWINDOW 0x00040000L
#define WS_EX_TOOLWINDOW 0x00000080L
#define CS_VREDRAW 0x0001
#define CS_HREDRAW 0x0002
#define CS_DBLCLKS 0x0008
#define CS_OWNDC 0x0020
#define CS_CLASSDC 0x0040
#define CW_USEDEFAULT ((int)0x80000000)
#define GWL_WNDPROC (-4)
#define GWL_HINSTANCE (-6)
#define GWL_STYLE (-16)
#define GWL_EXSTYLE (-20)
#define GWL_USERDATA (-21)
#define GWLP_USERDATA (-21)
#define SW_HIDE 0
#define SW_SHOWNORMAL 1
#define SW_NORMAL 1
#define SW_SHOWMINIMIZED 2
#define SW_SHOWMAXIMIZED 3
#define SW_MAXIMIZE 3
#define SW_SHOWNOACTIVATE 4
#define SW_SHOW 5
#define SW_MINIMIZE 6
#define SW_RESTORE 9
#define SW_SHOWDEFAULT 10
#define SWP_NOSIZE 0x0001
#define SWP_NOMOVE 0x0002
#define SWP_NOZORDER 0x0004
#define SWP_NOREDRAW 0x0008
#define SWP_NOACTIVATE 0x0010
#define SWP_FRAMECHANGED 0x0020
#define SWP_SHOWWINDOW 0x0040
#define SWP_HIDEWINDOW 0x0080
#define HWND_TOP ((HWND)0)
#define HWND_BOTTOM ((HWND)1)
#define HWND_TOPMOST ((HWND)-1)
#define HWND_NOTOPMOST ((HWND)-2)
#define SM_CXSCREEN 0
#define SM_CYSCREEN 1
#define SM_CXFRAME 32
#define SM_CYFRAME 33
#define SM_CYCAPTION 4
#define SM_CXDOUBLECLK 36
#define SM_CYDOUBLECLK 37
#define SM_CXFIXEDFRAME 7
#define SM_CYFIXEDFRAME 8
#define SM_CXVIRTUALSCREEN 78
#define SM_CYVIRTUALSCREEN 79

typedef struct tagCREATESTRUCTA {
	LPVOID lpCreateParams;
	HINSTANCE hInstance;
	HMENU hMenu;
	HWND hwndParent;
	int cy, cx, y, x;
	LONG style;
	LPCSTR lpszName;
	LPCSTR lpszClass;
	DWORD dwExStyle;
} CREATESTRUCTA, CREATESTRUCT, *LPCREATESTRUCT;

typedef struct tagMINMAXINFO {
	POINT ptReserved;
	POINT ptMaxSize;
	POINT ptMaxPosition;
	POINT ptMinTrackSize;
	POINT ptMaxTrackSize;
} MINMAXINFO, *LPMINMAXINFO;

ATOM RegisterClass(const WNDCLASS* wc);
#define RegisterClassA RegisterClass
ATOM RegisterClassEx(const WNDCLASSEX* wc);
#define RegisterClassExA RegisterClassEx
BOOL UnregisterClass(LPCSTR className, HINSTANCE instance);
HWND CreateWindowEx(DWORD exStyle, LPCSTR className, LPCSTR windowName, DWORD style, int x, int y, int w, int h, HWND parent, HMENU menu, HINSTANCE instance, LPVOID param);
#define CreateWindowExA CreateWindowEx
#define CreateWindow(c, n, s, x, y, w, h, p, m, i, param) CreateWindowEx(0, c, n, s, x, y, w, h, p, m, i, param)
#define CreateWindowA CreateWindow
BOOL DestroyWindow(HWND hwnd);
BOOL ShowWindow(HWND hwnd, int cmd);
BOOL UpdateWindow(HWND hwnd);
BOOL SetWindowPos(HWND hwnd, HWND after, int x, int y, int cx, int cy, UINT flags);
BOOL MoveWindow(HWND hwnd, int x, int y, int w, int h, BOOL repaint);
BOOL GetClientRect(HWND hwnd, LPRECT rect);
BOOL GetWindowRect(HWND hwnd, LPRECT rect);
BOOL AdjustWindowRect(LPRECT rect, DWORD style, BOOL menu);
BOOL AdjustWindowRectEx(LPRECT rect, DWORD style, BOOL menu, DWORD exStyle);
BOOL ClientToScreen(HWND hwnd, LPPOINT pt);
BOOL ScreenToClient(HWND hwnd, LPPOINT pt);
BOOL SetWindowText(HWND hwnd, LPCSTR text);
#define SetWindowTextA SetWindowText
BOOL SetWindowTextW(HWND hwnd, LPCWSTR text);
LONG GetWindowLong(HWND hwnd, int index);
LONG SetWindowLong(HWND hwnd, int index, LONG value);
LONG_PTR GetWindowLongPtr(HWND hwnd, int index);
LONG_PTR SetWindowLongPtr(HWND hwnd, int index, LONG_PTR value);
HWND GetForegroundWindow();
BOOL SetForegroundWindow(HWND hwnd);
HWND GetActiveWindow();
HWND GetFocus();
HWND SetFocus(HWND hwnd);
HWND GetDesktopWindow();
HWND FindWindow(LPCSTR className, LPCSTR windowName);
#define FindWindowA FindWindow
BOOL IsWindow(HWND hwnd);
BOOL IsWindowVisible(HWND hwnd);
BOOL IsIconic(HWND hwnd);
BOOL IsZoomed(HWND hwnd);
BOOL BringWindowToTop(HWND hwnd);
BOOL InvalidateRect(HWND hwnd, const RECT* rect, BOOL erase);
BOOL ValidateRect(HWND hwnd, const RECT* rect);
HWND SetCapture(HWND hwnd);
BOOL ReleaseCapture();
DWORD GetWindowThreadProcessId(HWND hwnd, LPDWORD processId);
int GetSystemMetrics(int index);
UINT GetDoubleClickTime();

typedef struct tagPAINTSTRUCT { HDC hdc; BOOL fErase; RECT rcPaint; BOOL fRestore; BOOL fIncUpdate; BYTE rgbReserved[32]; } PAINTSTRUCT, *LPPAINTSTRUCT;
HDC BeginPaint(HWND hwnd, LPPAINTSTRUCT ps);
BOOL EndPaint(HWND hwnd, const PAINTSTRUCT* ps);

//-----------------------------------------------------------------------------
// Resources
//-----------------------------------------------------------------------------
#define IDC_ARROW MAKEINTRESOURCE(32512)
#define IDC_IBEAM MAKEINTRESOURCE(32513)
#define IDC_WAIT MAKEINTRESOURCE(32514)
#define IDC_CROSS MAKEINTRESOURCE(32515)
#define IDI_APPLICATION MAKEINTRESOURCE(32512)
#define IMAGE_BITMAP 0
#define IMAGE_ICON 1
#define IMAGE_CURSOR 2
#define LR_DEFAULTCOLOR 0x0000
#define LR_LOADFROMFILE 0x0010
#define LR_DEFAULTSIZE 0x0040
#define LR_SHARED 0x8000
#define LR_CREATEDIBSECTION 0x2000
HCURSOR LoadCursor(HINSTANCE instance, LPCSTR name);
#define LoadCursorA LoadCursor
HCURSOR LoadCursorFromFile(LPCSTR fileName);
HICON LoadIcon(HINSTANCE instance, LPCSTR name);
#define LoadIconA LoadIcon
HANDLE LoadImage(HINSTANCE instance, LPCSTR name, UINT type, int cx, int cy, UINT load);
#define LoadImageA LoadImage
int LoadString(HINSTANCE instance, UINT id, LPSTR buffer, int len);
#define LoadStringA LoadString
BOOL DestroyCursor(HCURSOR cursor);
BOOL DestroyIcon(HICON icon);

//-----------------------------------------------------------------------------
// Cursor and keyboard
//-----------------------------------------------------------------------------
HCURSOR SetCursor(HCURSOR cursor);
int ShowCursor(BOOL show);
BOOL GetCursorPos(LPPOINT pt);
BOOL SetCursorPos(int x, int y);
BOOL ClipCursor(const RECT* rect);
SHORT GetAsyncKeyState(int vkey);
SHORT GetKeyState(int vkey);
BOOL GetKeyboardState(PBYTE state);
UINT MapVirtualKey(UINT code, UINT mapType);
#define MapVirtualKeyA MapVirtualKey
int ToAscii(UINT vkey, UINT scanCode, const BYTE* keyState, LPWORD out, UINT flags);
typedef void* HKL;
HKL GetKeyboardLayout(DWORD thread);
#define MAPVK_VK_TO_VSC 0
#define MAPVK_VSC_TO_VK 1
#define MAPVK_VK_TO_CHAR 2

#define VK_LBUTTON 0x01
#define VK_RBUTTON 0x02
#define VK_CANCEL 0x03
#define VK_MBUTTON 0x04
#define VK_BACK 0x08
#define VK_TAB 0x09
#define VK_CLEAR 0x0C
#define VK_RETURN 0x0D
#define VK_SHIFT 0x10
#define VK_CONTROL 0x11
#define VK_MENU 0x12
#define VK_PAUSE 0x13
#define VK_CAPITAL 0x14
#define VK_ESCAPE 0x1B
#define VK_SPACE 0x20
#define VK_PRIOR 0x21
#define VK_NEXT 0x22
#define VK_END 0x23
#define VK_HOME 0x24
#define VK_LEFT 0x25
#define VK_UP 0x26
#define VK_RIGHT 0x27
#define VK_DOWN 0x28
#define VK_SELECT 0x29
#define VK_PRINT 0x2A
#define VK_SNAPSHOT 0x2C
#define VK_INSERT 0x2D
#define VK_DELETE 0x2E
#define VK_HELP 0x2F
#define VK_LWIN 0x5B
#define VK_RWIN 0x5C
#define VK_APPS 0x5D
#define VK_NUMPAD0 0x60
#define VK_NUMPAD1 0x61
#define VK_NUMPAD2 0x62
#define VK_NUMPAD3 0x63
#define VK_NUMPAD4 0x64
#define VK_NUMPAD5 0x65
#define VK_NUMPAD6 0x66
#define VK_NUMPAD7 0x67
#define VK_NUMPAD8 0x68
#define VK_NUMPAD9 0x69
#define VK_MULTIPLY 0x6A
#define VK_ADD 0x6B
#define VK_SEPARATOR 0x6C
#define VK_SUBTRACT 0x6D
#define VK_DECIMAL 0x6E
#define VK_DIVIDE 0x6F
#define VK_F1 0x70
#define VK_F2 0x71
#define VK_F3 0x72
#define VK_F4 0x73
#define VK_F5 0x74
#define VK_F6 0x75
#define VK_F7 0x76
#define VK_F8 0x77
#define VK_F9 0x78
#define VK_F10 0x79
#define VK_F11 0x7A
#define VK_F12 0x7B
#define VK_NUMLOCK 0x90
#define VK_SCROLL 0x91
#define VK_LSHIFT 0xA0
#define VK_RSHIFT 0xA1
#define VK_LCONTROL 0xA2
#define VK_RCONTROL 0xA3
#define VK_LMENU 0xA4
#define VK_RMENU 0xA5
#define VK_OEM_1 0xBA
#define VK_OEM_PLUS 0xBB
#define VK_OEM_COMMA 0xBC
#define VK_OEM_MINUS 0xBD
#define VK_OEM_PERIOD 0xBE
#define VK_OEM_2 0xBF
#define VK_OEM_3 0xC0
#define VK_OEM_4 0xDB
#define VK_OEM_5 0xDC
#define VK_OEM_6 0xDD
#define VK_OEM_7 0xDE

//-----------------------------------------------------------------------------
// Message boxes
//-----------------------------------------------------------------------------
#define MB_OK 0x00000000L
#define MB_OKCANCEL 0x00000001L
#define MB_ABORTRETRYIGNORE 0x00000002L
#define MB_YESNOCANCEL 0x00000003L
#define MB_YESNO 0x00000004L
#define MB_RETRYCANCEL 0x00000005L
#define MB_ICONHAND 0x00000010L
#define MB_ICONQUESTION 0x00000020L
#define MB_ICONEXCLAMATION 0x00000030L
#define MB_ICONASTERISK 0x00000040L
#define MB_ICONWARNING MB_ICONEXCLAMATION
#define MB_ICONERROR MB_ICONHAND
#define MB_ICONSTOP MB_ICONHAND
#define MB_ICONINFORMATION MB_ICONASTERISK
#define MB_DEFBUTTON1 0x00000000L
#define MB_DEFBUTTON2 0x00000100L
#define MB_DEFBUTTON3 0x00000200L
#define MB_APPLMODAL 0x00000000L
#define MB_SYSTEMMODAL 0x00001000L
#define MB_TASKMODAL 0x00002000L
#define MB_SETFOREGROUND 0x00010000L
#define MB_TOPMOST 0x00040000L
#define IDOK 1
#define IDCANCEL 2
#define IDABORT 3
#define IDRETRY 4
#define IDIGNORE 5
#define IDYES 6
#define IDNO 7
int MessageBoxA(HWND hwnd, LPCSTR text, LPCSTR caption, UINT type);
int MessageBoxW(HWND hwnd, LPCWSTR text, LPCWSTR caption, UINT type);
#define MessageBox MessageBoxA

//-----------------------------------------------------------------------------
// Display settings
//-----------------------------------------------------------------------------
#define CCHDEVICENAME 32
#define CCHFORMNAME 32
typedef struct _devicemodeA {
	BYTE dmDeviceName[CCHDEVICENAME];
	WORD dmSpecVersion;
	WORD dmDriverVersion;
	WORD dmSize;
	WORD dmDriverExtra;
	DWORD dmFields;
	POINT dmPosition;
	DWORD dmDisplayOrientation;
	DWORD dmDisplayFixedOutput;
	short dmColor;
	short dmDuplex;
	short dmYResolution;
	short dmTTOption;
	short dmCollate;
	BYTE dmFormName[CCHFORMNAME];
	WORD dmLogPixels;
	DWORD dmBitsPerPel;
	DWORD dmPelsWidth;
	DWORD dmPelsHeight;
	DWORD dmDisplayFlags;
	DWORD dmDisplayFrequency;
} DEVMODEA, DEVMODE, *LPDEVMODE;
#define DM_BITSPERPEL 0x00040000L
#define DM_PELSWIDTH 0x00080000L
#define DM_PELSHEIGHT 0x00100000L
#define DM_DISPLAYFREQUENCY 0x00400000L
#define ENUM_CURRENT_SETTINGS ((DWORD)-1)
#define CDS_FULLSCREEN 0x00000004
#define CDS_TEST 0x00000002
#define DISP_CHANGE_SUCCESSFUL 0
#define DISP_CHANGE_FAILED -1
#define MONITOR_DEFAULTTONULL 0x00000000
#define MONITOR_DEFAULTTOPRIMARY 0x00000001
#define MONITOR_DEFAULTTONEAREST 0x00000002
#define MONITORINFOF_PRIMARY 0x00000001
typedef struct tagMONITORINFO { DWORD cbSize; RECT rcMonitor; RECT rcWork; DWORD dwFlags; } MONITORINFO, *LPMONITORINFO;
HMONITOR MonitorFromWindow(HWND hwnd, DWORD flags);
BOOL GetMonitorInfo(HMONITOR monitor, LPMONITORINFO info);
#define GetMonitorInfoA GetMonitorInfo

BOOL EnumDisplaySettings(LPCSTR device, DWORD mode, LPDEVMODE dm);
#define EnumDisplaySettingsA EnumDisplaySettings
LONG ChangeDisplaySettings(LPDEVMODE dm, DWORD flags);
#define ChangeDisplaySettingsA ChangeDisplaySettings

#define SPI_GETSCREENSAVEACTIVE 0x0010
#define SPI_SETSCREENSAVEACTIVE 0x0011
#define SPI_GETWORKAREA 0x0030
#define SPI_GETMOUSESPEED 0x0070
#define SPI_SETMOUSESPEED 0x0071
#define SPIF_SENDCHANGE 0x0002
BOOL SystemParametersInfo(UINT action, UINT param, PVOID pvParam, UINT winIni);
#define SystemParametersInfoA SystemParametersInfo

//-----------------------------------------------------------------------------
// GDI (fonts are rasterized via CoreText by the platform layer)
//-----------------------------------------------------------------------------
#define LF_FACESIZE 32
typedef struct tagLOGFONTA {
	LONG lfHeight;
	LONG lfWidth;
	LONG lfEscapement;
	LONG lfOrientation;
	LONG lfWeight;
	BYTE lfItalic;
	BYTE lfUnderline;
	BYTE lfStrikeOut;
	BYTE lfCharSet;
	BYTE lfOutPrecision;
	BYTE lfClipPrecision;
	BYTE lfQuality;
	BYTE lfPitchAndFamily;
	CHAR lfFaceName[LF_FACESIZE];
} LOGFONTA, LOGFONT, *LPLOGFONT;

typedef struct tagTEXTMETRICA {
	LONG tmHeight;
	LONG tmAscent;
	LONG tmDescent;
	LONG tmInternalLeading;
	LONG tmExternalLeading;
	LONG tmAveCharWidth;
	LONG tmMaxCharWidth;
	LONG tmWeight;
	LONG tmOverhang;
	LONG tmDigitizedAspectX;
	LONG tmDigitizedAspectY;
	BYTE tmFirstChar;
	BYTE tmLastChar;
	BYTE tmDefaultChar;
	BYTE tmBreakChar;
	BYTE tmItalic;
	BYTE tmUnderlined;
	BYTE tmStruckOut;
	BYTE tmPitchAndFamily;
	BYTE tmCharSet;
} TEXTMETRICA, TEXTMETRIC, *LPTEXTMETRIC;
typedef TEXTMETRIC TEXTMETRICW;

typedef struct tagRGBQUAD { BYTE rgbBlue; BYTE rgbGreen; BYTE rgbRed; BYTE rgbReserved; } RGBQUAD;
typedef struct tagBITMAPINFOHEADER {
	DWORD biSize;
	LONG biWidth;
	LONG biHeight;
	WORD biPlanes;
	WORD biBitCount;
	DWORD biCompression;
	DWORD biSizeImage;
	LONG biXPelsPerMeter;
	LONG biYPelsPerMeter;
	DWORD biClrUsed;
	DWORD biClrImportant;
} BITMAPINFOHEADER, *PBITMAPINFOHEADER, *LPBITMAPINFOHEADER;
typedef struct tagBITMAPINFO { BITMAPINFOHEADER bmiHeader; RGBQUAD bmiColors[1]; } BITMAPINFO, *PBITMAPINFO, *LPBITMAPINFO;
#pragma pack(push, 2)
typedef struct tagBITMAPFILEHEADER { WORD bfType; DWORD bfSize; WORD bfReserved1; WORD bfReserved2; DWORD bfOffBits; } BITMAPFILEHEADER, *PBITMAPFILEHEADER;
#pragma pack(pop)
typedef struct tagPALETTEENTRY { BYTE peRed; BYTE peGreen; BYTE peBlue; BYTE peFlags; } PALETTEENTRY, *PPALETTEENTRY, *LPPALETTEENTRY;
typedef struct _RGNDATAHEADER { DWORD dwSize; DWORD iType; DWORD nCount; DWORD nRgnSize; RECT rcBound; } RGNDATAHEADER, *PRGNDATAHEADER;
typedef struct _RGNDATA { RGNDATAHEADER rdh; char Buffer[1]; } RGNDATA, *PRGNDATA, *LPRGNDATA;

typedef struct _POINTFLOAT { FLOAT x; FLOAT y; } POINTFLOAT;
typedef struct _GLYPHMETRICSFLOAT { FLOAT gmfBlackBoxX; FLOAT gmfBlackBoxY; POINTFLOAT gmfptGlyphOrigin; FLOAT gmfCellIncX; FLOAT gmfCellIncY; } GLYPHMETRICSFLOAT, *PGLYPHMETRICSFLOAT, *LPGLYPHMETRICSFLOAT;

#define BI_RGB 0L
#define BI_BITFIELDS 3L
#define DIB_RGB_COLORS 0

#define FW_DONTCARE 0
#define FW_THIN 100
#define FW_LIGHT 300
#define FW_NORMAL 400
#define FW_MEDIUM 500
#define FW_SEMIBOLD 600
#define FW_BOLD 700
#define FW_HEAVY 900
#define ANSI_CHARSET 0
#define DEFAULT_CHARSET 1
#define SHIFTJIS_CHARSET 128
#define HANGUL_CHARSET 129
#define GB2312_CHARSET 134
#define CHINESEBIG5_CHARSET 136
#define OUT_DEFAULT_PRECIS 0
#define OUT_TT_PRECIS 4
#define OUT_TT_ONLY_PRECIS 7
#define CLIP_DEFAULT_PRECIS 0
#define DEFAULT_QUALITY 0
#define NONANTIALIASED_QUALITY 3
#define ANTIALIASED_QUALITY 4
#define CLEARTYPE_QUALITY 5
#define DEFAULT_PITCH 0
#define FIXED_PITCH 1
#define VARIABLE_PITCH 2
#define FF_DONTCARE (0 << 4)
#define FF_ROMAN (1 << 4)
#define FF_SWISS (2 << 4)
#define TRANSPARENT 1
#define OPAQUE 2
#define ETO_OPAQUE 0x0002
#define ETO_CLIPPED 0x0004
#define LOGPIXELSX 88
#define LOGPIXELSY 90
#define BITSPIXEL 12
#define HORZRES 8
#define VERTRES 10
#define VREFRESH 116
#define FR_PRIVATE 0x10
#define BLACK_BRUSH 4
#define WHITE_BRUSH 0

#define SRCCOPY 0x00CC0020
HDC GetDC(HWND hwnd);
int SaveDC(HDC hdc);
BOOL RestoreDC(HDC hdc, int saved);
BOOL BitBlt(HDC dst, int x, int y, int w, int h, HDC src, int sx, int sy, DWORD rop);
int ReleaseDC(HWND hwnd, HDC hdc);
HDC CreateCompatibleDC(HDC hdc);
BOOL DeleteDC(HDC hdc);
HGDIOBJ SelectObject(HDC hdc, HGDIOBJ obj);
BOOL DeleteObject(HGDIOBJ obj);
HGDIOBJ GetStockObject(int obj);
int GetDeviceCaps(HDC hdc, int index);
HFONT CreateFont(int height, int width, int escapement, int orientation, int weight, DWORD italic, DWORD underline, DWORD strikeOut, DWORD charSet, DWORD outPrecision, DWORD clipPrecision, DWORD quality, DWORD pitchAndFamily, LPCSTR faceName);
#define CreateFontA CreateFont
HFONT CreateFontIndirect(const LOGFONT* lf);
HBITMAP CreateDIBSection(HDC hdc, const BITMAPINFO* bmi, UINT usage, void** bits, HANDLE section, DWORD offset);
COLORREF SetTextColor(HDC hdc, COLORREF color);
COLORREF SetBkColor(HDC hdc, COLORREF color);
int SetBkMode(HDC hdc, int mode);
BOOL TextOut(HDC hdc, int x, int y, LPCSTR str, int len);
#define TextOutA TextOut
BOOL TextOutW(HDC hdc, int x, int y, LPCWSTR str, int len);
BOOL ExtTextOutW(HDC hdc, int x, int y, UINT options, const RECT* rect, LPCWSTR str, UINT len, const INT* dx);
BOOL GetTextExtentPoint32(HDC hdc, LPCSTR str, int len, LPSIZE size);
#define GetTextExtentPoint32A GetTextExtentPoint32
BOOL GetTextExtentPoint32W(HDC hdc, LPCWSTR str, int len, LPSIZE size);
BOOL GetTextMetrics(HDC hdc, LPTEXTMETRIC tm);
#define GetTextMetricsA GetTextMetrics
BOOL GetTextMetricsW(HDC hdc, LPTEXTMETRIC tm);
int AddFontResource(LPCSTR fileName);
#define AddFontResourceA AddFontResource
BOOL RemoveFontResource(LPCSTR fileName);
#define RemoveFontResourceA RemoveFontResource
int AddFontResourceEx(LPCSTR fileName, DWORD flags, PVOID reserved);
BOOL RemoveFontResourceEx(LPCSTR fileName, DWORD flags, PVOID reserved);
BOOL SetDeviceGammaRamp(HDC hdc, LPVOID ramp);
BOOL GetDeviceGammaRamp(HDC hdc, LPVOID ramp);

//-----------------------------------------------------------------------------
// IME (no-op; SDL text input is used instead)
//-----------------------------------------------------------------------------
typedef DWORD IMEPROP;
typedef struct tagCANDIDATELIST { DWORD dwSize; DWORD dwStyle; DWORD dwCount; DWORD dwSelection; DWORD dwPageStart; DWORD dwPageSize; DWORD dwOffset[1]; } CANDIDATELIST, *LPCANDIDATELIST;
#define GCS_COMPREADSTR 0x0001
#define GCS_COMPSTR 0x0008
#define GCS_CURSORPOS 0x0080
#define GCS_RESULTSTR 0x0800
#define GCS_RESULTREADSTR 0x0200
#define GCS_COMPATTR 0x0010
#define GCS_COMPCLAUSE 0x0020
#define GCS_DELTASTART 0x0100
#define IGP_PROPERTY 0x00000004
#define IGP_CONVERSION 0x00000008
#define IME_PROP_UNICODE 0x00080000
#define IME_PROP_AT_CARET 0x00010000
#define IME_PROP_SPECIAL_UI 0x00020000
#define IME_CMODE_NATIVE 0x0001
#define IME_CMODE_FULLSHAPE 0x0008
#define IMN_CLOSESTATUSWINDOW 0x0001
#define IMN_OPENSTATUSWINDOW 0x0002
#define IMN_CHANGECANDIDATE 0x0003
#define IMN_CLOSECANDIDATE 0x0004
#define IMN_OPENCANDIDATE 0x0005
#define IMN_SETCONVERSIONMODE 0x0006
#define IMN_SETSENTENCEMODE 0x0007
#define IMN_SETOPENSTATUS 0x0008
#define IMN_SETCANDIDATEPOS 0x0009
#define IMN_SETCOMPOSITIONFONT 0x000A
#define IMN_SETCOMPOSITIONWINDOW 0x000B
#define IMN_SETSTATUSWINDOWPOS 0x000C
#define IMN_GUIDELINE 0x000D
#define IMN_PRIVATE 0x000E
#define ISC_SHOWUICANDIDATEWINDOW 0x00000001
#define ISC_SHOWUICOMPOSITIONWINDOW 0x80000000
#define ISC_SHOWUIGUIDELINE 0x40000000
#define ISC_SHOWUIALLCANDIDATEWINDOW 0x0000000F
#define ISC_SHOWUIALL 0xC000000F
inline HIMC ImmGetContext(HWND) { return NULL; }
inline BOOL ImmReleaseContext(HWND, HIMC) { return TRUE; }
inline HIMC ImmCreateContext() { return NULL; }
inline BOOL ImmDestroyContext(HIMC) { return TRUE; }
inline HIMC ImmAssociateContext(HWND, HIMC) { return NULL; }
inline HWND ImmGetDefaultIMEWnd(HWND) { return NULL; }
inline DWORD ImmGetProperty(HKL, DWORD) { return 0; }
inline LONG ImmGetCompositionStringA(HIMC, DWORD, LPVOID, DWORD) { return 0; }
inline LONG ImmGetCompositionStringW(HIMC, DWORD, LPVOID, DWORD) { return 0; }
#define ImmGetCompositionString ImmGetCompositionStringA
inline DWORD ImmGetCandidateListA(HIMC, DWORD, LPCANDIDATELIST, DWORD) { return 0; }
inline DWORD ImmGetCandidateListW(HIMC, DWORD, LPCANDIDATELIST, DWORD) { return 0; }
template <typename T> inline DWORD ImmGetCandidateListCountA(HIMC, T* count) { if (count) *count = 0; return 0; }
template <typename T> inline DWORD ImmGetCandidateListCountW(HIMC, T* count) { if (count) *count = 0; return 0; }
#define CS_INSERTCHAR 0x2000
#define CS_NOMOVECARET 0x4000
#define IME_PROP_CANDLIST_START_FROM_1 0x00040000
#define IME_CAND_UNKNOWN 0x0000
#define IME_CAND_READ 0x0001
#define IME_CAND_CODE 0x0002
inline BOOL ImmGetConversionStatus(HIMC, LPDWORD conv, LPDWORD sentence) { if (conv) *conv = 0; if (sentence) *sentence = 0; return TRUE; }

//-----------------------------------------------------------------------------
// Shell
//-----------------------------------------------------------------------------
HINSTANCE ShellExecute(HWND hwnd, LPCSTR op, LPCSTR file, LPCSTR params, LPCSTR dir, INT show);
#define ShellExecuteA ShellExecute

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

// Minimal Win32 API replacement for building the game natively on macOS.
// Only what the game actually uses is provided. Types follow the Windows LLP64
// model: DWORD/LONG/ULONG are 32 bits wide even though 'long' is 64 bits here.
#pragma once

#ifndef WINVER
#define WINVER 0x0601
#endif
#ifndef _WIN32_WINNT
#define _WIN32_WINNT 0x0601
#endif

#ifdef _WIN32
#error "Win32Shim must not be used on Windows"
#endif

#include <stddef.h>
#include <stdint.h>
#include <stdlib.h>
#include <stdio.h>
#include <stdarg.h>
#include <string.h>
#include <strings.h>
#include <wchar.h>
#include <wctype.h>
#include <ctype.h>
#include <errno.h>
#include <limits.h>
#include <unistd.h>
#include <pthread.h>
#include <malloc/malloc.h>

// Pieces of the generic non-Windows compatibility layer that do not conflict with this shim.
#include <Utility/mem_compat.h>
#include <Utility/string_compat.h>
#include <Utility/tchar_compat.h>

#ifndef __forceinline
#define __forceinline __attribute__((always_inline)) inline
#endif
#ifndef _cdecl
#define _cdecl
#endif
#ifndef __cdecl
#define __cdecl
#endif
#define _MAX_DRIVE 3
#define _MAX_DIR 256
#define _MAX_FNAME 256
#define _MAX_EXT 256
#define _MAX_PATH 260

//-----------------------------------------------------------------------------
// Calling conventions and decorations
//-----------------------------------------------------------------------------
#define WINAPI
#define WINAPIV
#define APIENTRY
#define CALLBACK
#define PASCAL
#define FAR
#define NEAR
#define far
#define near
#define CONST const
#define IN
#define OUT
#define OPTIONAL
#ifndef __stdcall
#define __stdcall
#endif
#ifndef _stdcall
#define _stdcall
#endif
#ifndef __fastcall
#define __fastcall
#endif
#define __declspec(x)
#define DECLSPEC_NOVTABLE
#define DECLSPEC_UUID(x)
#define STDMETHODCALLTYPE
#define STDAPI extern "C" HRESULT
#define STDAPI_(type) extern "C" type
#define WINBASEAPI
#define WINUSERAPI
#define UNREFERENCED_PARAMETER(P) (void)(P)

//-----------------------------------------------------------------------------
// Basic types
//-----------------------------------------------------------------------------
// Macros rather than typedefs so that "unsigned __int64" works.
#define __int64 long long
#define _int64 long long
#define __int32 int
#define __int16 short
#define __int8 char

typedef void VOID;
typedef void* PVOID;
typedef void* LPVOID;
typedef const void* LPCVOID;
typedef char CHAR;
typedef unsigned char UCHAR;
typedef uint8_t BYTE;
typedef BYTE* PBYTE;
typedef BYTE* LPBYTE;
typedef uint16_t WORD;
typedef WORD* PWORD;
typedef WORD* LPWORD;
typedef uint32_t DWORD;
typedef DWORD* PDWORD;
typedef DWORD* LPDWORD;
typedef uint64_t DWORDLONG;
typedef uint64_t DWORD64;
typedef uint64_t ULONGLONG;
typedef int64_t LONGLONG;
typedef int32_t LONG;
typedef LONG* PLONG;
typedef LONG* LPLONG;
typedef uint32_t ULONG;
typedef ULONG* PULONG;
typedef int16_t SHORT;
typedef uint16_t USHORT;
typedef int INT;
typedef INT* PINT;
typedef INT* LPINT;
typedef unsigned int UINT;
typedef UINT* PUINT;
typedef float FLOAT;
#if defined(__OBJC__)
// Objective-C defines BOOL as bool; keep the Win32 BOOL an int so interfaces
// shared with C++ code have identical signatures.
#define BOOL WINBOOL
#endif
typedef int BOOL;
typedef BOOL* PBOOL;
typedef BOOL* LPBOOL;
typedef BYTE BOOLEAN;
typedef intptr_t INT_PTR;
typedef uintptr_t UINT_PTR;
typedef intptr_t LONG_PTR;
typedef uintptr_t ULONG_PTR;
typedef uintptr_t DWORD_PTR;
typedef ULONG_PTR SIZE_T;
typedef LONG_PTR SSIZE_T;
typedef UINT_PTR WPARAM;
typedef LONG_PTR LPARAM;
typedef LONG_PTR LRESULT;
typedef LONG HRESULT;
typedef WORD ATOM;
typedef DWORD COLORREF;
typedef DWORD LCID;
typedef WORD LANGID;

typedef char* PSTR;
typedef char* LPSTR;
typedef const char* PCSTR;
typedef const char* LPCSTR;
typedef wchar_t WCHAR;
typedef WCHAR* PWSTR;
typedef WCHAR* LPWSTR;
typedef const WCHAR* PCWSTR;
typedef const WCHAR* LPCWSTR;
typedef wchar_t OLECHAR;
typedef OLECHAR* LPOLESTR;
typedef const OLECHAR* LPCOLESTR;
typedef OLECHAR* BSTR;

#ifndef TRUE
#define TRUE 1
#endif
#ifndef FALSE
#define FALSE 0
#endif

#define MAKEWORD(a, b) ((WORD)(((BYTE)((DWORD_PTR)(a) & 0xff)) | ((WORD)((BYTE)((DWORD_PTR)(b) & 0xff))) << 8))
#define MAKELONG(a, b) ((LONG)(((WORD)((DWORD_PTR)(a) & 0xffff)) | ((DWORD)((WORD)((DWORD_PTR)(b) & 0xffff))) << 16))
#define LOWORD(l) ((WORD)((DWORD_PTR)(l) & 0xffff))
#define HIWORD(l) ((WORD)((DWORD_PTR)(l) >> 16))
#define LOBYTE(w) ((BYTE)((DWORD_PTR)(w) & 0xff))
#define HIBYTE(w) ((BYTE)((DWORD_PTR)(w) >> 8))
#define GET_X_LPARAM(lp) ((int)(short)LOWORD(lp))
#define GET_Y_LPARAM(lp) ((int)(short)HIWORD(lp))
#define MAKEINTRESOURCE(i) ((LPSTR)((ULONG_PTR)((WORD)(i))))
#define RGB(r, g, b) ((COLORREF)(((BYTE)(r) | ((WORD)((BYTE)(g)) << 8)) | (((DWORD)(BYTE)(b)) << 16)))
#define GetRValue(rgb) (LOBYTE(rgb))
#define GetGValue(rgb) (LOBYTE(((WORD)(rgb)) >> 8))
#define GetBValue(rgb) (LOBYTE((rgb) >> 16))

#ifndef NOMINMAX
#ifndef max
#define max(a, b) (((a) > (b)) ? (a) : (b))
#endif
#ifndef min
#define min(a, b) (((a) < (b)) ? (a) : (b))
#endif
#endif

typedef union _LARGE_INTEGER {
	struct { DWORD LowPart; LONG HighPart; };
	struct { DWORD LowPart; LONG HighPart; } u;
	LONGLONG QuadPart;
} LARGE_INTEGER, *PLARGE_INTEGER;

typedef union _ULARGE_INTEGER {
	struct { DWORD LowPart; DWORD HighPart; };
	struct { DWORD LowPart; DWORD HighPart; } u;
	ULONGLONG QuadPart;
} ULARGE_INTEGER, *PULARGE_INTEGER;

typedef struct _GUID {
	DWORD Data1;
	WORD Data2;
	WORD Data3;
	BYTE Data4[8];
} GUID, IID, CLSID;
typedef GUID* LPGUID;
typedef const GUID* LPCGUID;
struct IStream;
typedef struct IStream* LPSTREAM;
typedef const GUID& REFGUID;
typedef const IID& REFIID;
typedef const CLSID& REFCLSID;
inline bool operator==(const GUID& a, const GUID& b) { return memcmp(&a, &b, sizeof(GUID)) == 0; }
inline bool operator!=(const GUID& a, const GUID& b) { return !(a == b); }
#define DEFINE_GUID(name, l, w1, w2, b1, b2, b3, b4, b5, b6, b7, b8) \
	static const GUID name = { l, w1, w2, { b1, b2, b3, b4, b5, b6, b7, b8 } }

//-----------------------------------------------------------------------------
// Handles
//-----------------------------------------------------------------------------
typedef void* HANDLE;
typedef HANDLE* PHANDLE;
typedef HANDLE* LPHANDLE;
#define DECLARE_HANDLE(name) struct name##__ { int unused; }; typedef struct name##__* name
DECLARE_HANDLE(HWND);
DECLARE_HANDLE(HINSTANCE);
DECLARE_HANDLE(HKEY);
DECLARE_HANDLE(HDC);
DECLARE_HANDLE(HGLRC);
DECLARE_HANDLE(HBITMAP);
DECLARE_HANDLE(HBRUSH);
DECLARE_HANDLE(HFONT);
DECLARE_HANDLE(HPEN);
DECLARE_HANDLE(HICON);
DECLARE_HANDLE(HMENU);
DECLARE_HANDLE(HMONITOR);
DECLARE_HANDLE(HRGN);
DECLARE_HANDLE(HPALETTE);
DECLARE_HANDLE(HACCEL);
DECLARE_HANDLE(HRSRC);
DECLARE_HANDLE(HIMC);
typedef HANDLE HGDIOBJ;
typedef HANDLE HGLOBAL;
typedef HANDLE HLOCAL;
typedef HICON HCURSOR;
typedef HINSTANCE HMODULE;
typedef HKEY* PHKEY;
typedef int HFILE;
typedef intptr_t (*FARPROC)();
typedef intptr_t (*PROC)();

#define INVALID_HANDLE_VALUE ((HANDLE)(LONG_PTR)-1)
#define HFILE_ERROR ((HFILE)-1)

//-----------------------------------------------------------------------------
// Geometry
//-----------------------------------------------------------------------------
typedef struct tagRECT { LONG left, top, right, bottom; } RECT, *PRECT, *LPRECT;
typedef const RECT* LPCRECT;
typedef struct tagPOINT { LONG x, y; } POINT, *PPOINT, *LPPOINT;
typedef struct tagSIZE { LONG cx, cy; } SIZE, *PSIZE, *LPSIZE;
typedef struct tagPOINTS { SHORT x, y; } POINTS;

inline BOOL SetRect(LPRECT r, int l, int t, int ri, int b) { r->left = l; r->top = t; r->right = ri; r->bottom = b; return TRUE; }
inline BOOL SetRectEmpty(LPRECT r) { return SetRect(r, 0, 0, 0, 0); }
inline BOOL PtInRect(const RECT* r, POINT p) { return p.x >= r->left && p.x < r->right && p.y >= r->top && p.y < r->bottom; }
inline BOOL OffsetRect(LPRECT r, int dx, int dy) { r->left += dx; r->right += dx; r->top += dy; r->bottom += dy; return TRUE; }
inline BOOL IsRectEmpty(const RECT* r) { return r->right <= r->left || r->bottom <= r->top; }

//-----------------------------------------------------------------------------
// Errors and HRESULTs
//-----------------------------------------------------------------------------
#define ERROR_SUCCESS 0L
#define NO_ERROR 0L
#define ERROR_FILE_NOT_FOUND 2L
#define ERROR_PATH_NOT_FOUND 3L
#define ERROR_ACCESS_DENIED 5L
#define ERROR_INVALID_HANDLE 6L
#define ERROR_NOT_ENOUGH_MEMORY 8L
#define ERROR_NO_MORE_FILES 18L
#define ERROR_HANDLE_EOF 38L
#define ERROR_FILE_EXISTS 80L
#define ERROR_INVALID_PARAMETER 87L
#define ERROR_INSUFFICIENT_BUFFER 122L
#define ERROR_ALREADY_EXISTS 183L
#define ERROR_MORE_DATA 234L
#define ERROR_NO_MORE_ITEMS 259L
#define ERROR_IO_PENDING 997L

#define S_OK ((HRESULT)0L)
#define S_FALSE ((HRESULT)1L)
#define E_FAIL ((HRESULT)0x80004005L)
#define E_NOTIMPL ((HRESULT)0x80004001L)
#define E_NOINTERFACE ((HRESULT)0x80004002L)
#define E_POINTER ((HRESULT)0x80004003L)
#define E_ABORT ((HRESULT)0x80004004L)
#define E_UNEXPECTED ((HRESULT)0x8000FFFFL)
#define E_OUTOFMEMORY ((HRESULT)0x8007000EL)
#define E_INVALIDARG ((HRESULT)0x80070057L)
#define E_ACCESSDENIED ((HRESULT)0x80070005L)
#define SEVERITY_SUCCESS 0
#define SEVERITY_ERROR 1
#define FACILITY_NULL 0
#define FACILITY_ITF 4
#define FACILITY_WIN32 7
#define HRESULT_FROM_WIN32(x) ((HRESULT)(x) <= 0 ? ((HRESULT)(x)) : ((HRESULT)(((x) & 0x0000FFFF) | (FACILITY_WIN32 << 16) | 0x80000000)))
#define SUCCEEDED(hr) (((HRESULT)(hr)) >= 0)
#define FAILED(hr) (((HRESULT)(hr)) < 0)
#define HRESULT_CODE(hr) ((hr) & 0xFFFF)
#define HRESULT_FACILITY(hr) (((hr) >> 16) & 0x1fff)
#define MAKE_HRESULT(sev, fac, code) ((HRESULT)(((unsigned long)(sev) << 31) | ((unsigned long)(fac) << 16) | ((unsigned long)(code))))

DWORD GetLastError();
#define FORMAT_MESSAGE_ALLOCATE_BUFFER 0x00000100
#define FORMAT_MESSAGE_IGNORE_INSERTS 0x00000200
#define FORMAT_MESSAGE_FROM_STRING 0x00000400
#define FORMAT_MESSAGE_FROM_HMODULE 0x00000800
#define FORMAT_MESSAGE_FROM_SYSTEM 0x00001000
#define FORMAT_MESSAGE_ARGUMENT_ARRAY 0x00002000
DWORD FormatMessage(DWORD flags, LPCVOID source, DWORD messageId, DWORD languageId, LPSTR buffer, DWORD size, va_list* args);
#define FormatMessageA FormatMessage
DWORD FormatMessageW(DWORD flags, LPCVOID source, DWORD messageId, DWORD languageId, LPWSTR buffer, DWORD size, va_list* args);
void SetLastError(DWORD err);

//-----------------------------------------------------------------------------
// Strings
//-----------------------------------------------------------------------------
#define MAX_PATH 260
#define _stricmp strcasecmp
#define _strnicmp strncasecmp
#define _strcmpi strcasecmp
// Like the Windows one, _strdup returns null for a null string instead of crashing.
static inline char* _strdup(const char* s) { return s ? strdup(s) : NULL; }
#define _wcsdup wcsdup
#define _wcsnicmp wcsncasecmp
#define wcsnicmp wcsncasecmp
#define _snprintf snprintf
#define _vsnprintf vsnprintf
#define _snwprintf swprintf
#define _vsnwprintf vswprintf
#define _getcwd getcwd
#define _fileno fileno
#define _isnan isnan
#define _finite isfinite
#define _hypot hypot
#define _copysign copysign
#define _stat stat
#define _S_IFDIR S_IFDIR
#define _S_IFREG S_IFREG
#define _S_IFMT S_IFMT
#define _fstat fstat
#define _strtoui64 strtoull
#define _strtoi64 strtoll
#define _atoi64 atoll
#define lstrlen strlen
#define lstrlenA strlen
#define lstrlenW wcslen
#define lstrcpy strcpy
#define lstrcpyA strcpy
#define lstrcat strcat
#define lstrcmp strcmp
#define lstrcmpi strcasecmp
#define lstrcmpiA strcasecmp
#define wsprintf sprintf
#define wsprintfA sprintf
#define wvsprintf vsprintf

#define _wcsicmp wcscasecmp
#define wcsicmp wcscasecmp

inline LPSTR lstrcpyn(LPSTR dst, LPCSTR src, int n) { if (n > 0) strlcpy(dst, src, (size_t)n); return dst; }
#define lstrcpynA lstrcpyn
#define __min(a, b) (((a) < (b)) ? (a) : (b))
#define __max(a, b) (((a) > (b)) ? (a) : (b))

extern "C" char* _strupr(char* s);
#define strupr _strupr
inline wchar_t* _wcslwr(wchar_t* s) { for (wchar_t* p = s; *p; ++p) *p = towlower(*p); return s; }
inline wchar_t* _wcsupr(wchar_t* s) { for (wchar_t* p = s; *p; ++p) *p = towupper(*p); return s; }
#define wcslwr _wcslwr
#define wcsupr _wcsupr
char* _itoa(int value, char* str, int radix);
char* _ltoa(long value, char* str, int radix);
char* _ultoa(unsigned long value, char* str, int radix);
char* _i64toa(int64_t value, char* str, int radix);
char* _ui64toa(uint64_t value, char* str, int radix);
wchar_t* _itow(int value, wchar_t* str, int radix);
#define itoa _itoa
#define ltoa _ltoa
#define ultoa _ultoa
inline int _wtoi(const wchar_t* s) { return (int)wcstol(s, NULL, 10); }
inline double _wtof(const wchar_t* s) { return wcstod(s, NULL); }

void _splitpath(const char* path, char* drive, char* dir, char* fname, char* ext);
void _makepath(char* path, const char* drive, const char* dir, const char* fname, const char* ext);
char* _fullpath(char* absPath, const char* relPath, size_t maxLength);

#define CP_ACP 0
#define CP_UTF8 65001
int MultiByteToWideChar(UINT codePage, DWORD flags, LPCSTR src, int srcLen, LPWSTR dst, int dstLen);
int WideCharToMultiByte(UINT codePage, DWORD flags, LPCWSTR src, int srcLen, LPSTR dst, int dstLen, LPCSTR defChar, LPBOOL usedDefChar);

//-----------------------------------------------------------------------------
// C runtime file functions with Windows path translation (backslashes, drive letters)
//-----------------------------------------------------------------------------
FILE* Win32Shim_fopen(const char* path, const char* mode);
int Win32Shim_open(const char* path, int flags, ...);
int Win32Shim_access(const char* path, int mode);
int Win32Shim_unlink(const char* path);
int Win32Shim_mkdir(const char* path);
int Win32Shim_chdir(const char* path);
int Win32Shim_rmdir(const char* path);
#define fopen Win32Shim_fopen
#define _access Win32Shim_access
#define _unlink Win32Shim_unlink
#define _chdir Win32Shim_chdir
#define _rmdir Win32Shim_rmdir

//-----------------------------------------------------------------------------
// Memory
//-----------------------------------------------------------------------------
#define ZeroMemory(dst, len) memset((dst), 0, (len))
#define FillMemory(dst, len, val) memset((dst), (val), (len))
#define CopyMemory(dst, src, len) memcpy((dst), (src), (len))
#define MoveMemory(dst, src, len) memmove((dst), (src), (len))
#define SecureZeroMemory ZeroMemory

#define GMEM_FIXED 0x0000
#define GMEM_MOVEABLE 0x0002
#define GMEM_ZEROINIT 0x0040
#define GPTR (GMEM_FIXED | GMEM_ZEROINIT)
#define GHND (GMEM_MOVEABLE | GMEM_ZEROINIT)
#define LMEM_FIXED 0x0000
#define LMEM_ZEROINIT 0x0040
#define LPTR (LMEM_FIXED | LMEM_ZEROINIT)
#define HEAP_ZERO_MEMORY 0x00000008
inline HGLOBAL GlobalAlloc(UINT flags, SIZE_T bytes) { return (flags & GMEM_ZEROINIT) ? calloc(1, bytes) : malloc(bytes); }
inline HGLOBAL GlobalFree(HGLOBAL mem) { free(mem); return NULL; }
inline SIZE_T GlobalSize(HGLOBAL mem) { return mem ? malloc_size(mem) : 0; }
inline HGLOBAL GlobalReAlloc(HGLOBAL mem, SIZE_T bytes, UINT) { return realloc(mem, bytes); }
#define GlobalAllocPtr(flags, bytes) GlobalAlloc((flags), (bytes))
#define GlobalFreePtr(p) GlobalFree((HGLOBAL)(p))
inline LPVOID GlobalLock(HGLOBAL mem) { return mem; }
inline BOOL GlobalUnlock(HGLOBAL) { return TRUE; }
inline HLOCAL LocalAlloc(UINT flags, SIZE_T bytes) { return (flags & LMEM_ZEROINIT) ? calloc(1, bytes) : malloc(bytes); }
inline HLOCAL LocalFree(HLOCAL mem) { free(mem); return NULL; }
inline HANDLE GetProcessHeap() { return (HANDLE)1; }
inline LPVOID HeapAlloc(HANDLE, DWORD flags, SIZE_T bytes) { return (flags & HEAP_ZERO_MEMORY) ? calloc(1, bytes) : malloc(bytes); }
inline BOOL HeapFree(HANDLE, DWORD, LPVOID mem) { free(mem); return TRUE; }

typedef struct _MEMORYSTATUS {
	DWORD dwLength;
	DWORD dwMemoryLoad;
	SIZE_T dwTotalPhys;
	SIZE_T dwAvailPhys;
	SIZE_T dwTotalPageFile;
	SIZE_T dwAvailPageFile;
	SIZE_T dwTotalVirtual;
	SIZE_T dwAvailVirtual;
} MEMORYSTATUS, *LPMEMORYSTATUS;
void GlobalMemoryStatus(LPMEMORYSTATUS status);

#define PAGE_NOACCESS 0x01
#define PAGE_READONLY 0x02
#define PAGE_READWRITE 0x04
#define MEM_COMMIT 0x1000
#define MEM_RESERVE 0x2000
#define MEM_RELEASE 0x8000
LPVOID VirtualAlloc(LPVOID address, SIZE_T size, DWORD type, DWORD protect);
BOOL VirtualFree(LPVOID address, SIZE_T size, DWORD type);
BOOL VirtualProtect(LPVOID address, SIZE_T size, DWORD newProtect, PDWORD oldProtect);

//-----------------------------------------------------------------------------
// Time
//-----------------------------------------------------------------------------
typedef struct _FILETIME { DWORD dwLowDateTime; DWORD dwHighDateTime; } FILETIME, *PFILETIME, *LPFILETIME;
typedef struct _SYSTEMTIME {
	WORD wYear;
	WORD wMonth;
	WORD wDayOfWeek;
	WORD wDay;
	WORD wHour;
	WORD wMinute;
	WORD wSecond;
	WORD wMilliseconds;
} SYSTEMTIME, *PSYSTEMTIME, *LPSYSTEMTIME;
typedef struct _TIME_ZONE_INFORMATION {
	LONG Bias;
	WCHAR StandardName[32];
	SYSTEMTIME StandardDate;
	LONG StandardBias;
	WCHAR DaylightName[32];
	SYSTEMTIME DaylightDate;
	LONG DaylightBias;
} TIME_ZONE_INFORMATION, *LPTIME_ZONE_INFORMATION;
#define TIME_ZONE_ID_UNKNOWN 0
#define TIME_ZONE_ID_STANDARD 1
#define TIME_ZONE_ID_DAYLIGHT 2

BOOL QueryPerformanceCounter(LARGE_INTEGER* count);
BOOL QueryPerformanceFrequency(LARGE_INTEGER* freq);
void GetSystemTime(LPSYSTEMTIME st);
void GetLocalTime(LPSYSTEMTIME st);
void GetSystemTimeAsFileTime(LPFILETIME ft);
BOOL SystemTimeToFileTime(const SYSTEMTIME* st, LPFILETIME ft);
BOOL FileTimeToSystemTime(const FILETIME* ft, LPSYSTEMTIME st);
BOOL FileTimeToLocalFileTime(const FILETIME* ft, LPFILETIME local);
LONG CompareFileTime(const FILETIME* a, const FILETIME* b);
DWORD GetTimeZoneInformation(LPTIME_ZONE_INFORMATION tz);
int GetDateFormat(LCID locale, DWORD flags, const SYSTEMTIME* date, LPCSTR format, LPSTR out, int outLen);
int GetTimeFormat(LCID locale, DWORD flags, const SYSTEMTIME* time, LPCSTR format, LPSTR out, int outLen);
int GetDateFormatW(LCID locale, DWORD flags, const SYSTEMTIME* date, LPCWSTR format, LPWSTR out, int outLen);
int GetTimeFormatW(LCID locale, DWORD flags, const SYSTEMTIME* time, LPCWSTR format, LPWSTR out, int outLen);
#define LOCALE_SYSTEM_DEFAULT 0x0800
#define LOCALE_USER_DEFAULT 0x0400
#define DATE_SHORTDATE 0x00000001
#define DATE_LONGDATE 0x00000002
#define TIME_NOMINUTESORSECONDS 0x00000001
#define TIME_NOSECONDS 0x00000002
#define TIME_NOTIMEMARKER 0x00000004
#define TIME_FORCE24HOURFORMAT 0x00000008

//-----------------------------------------------------------------------------
// Threads and synchronization
//-----------------------------------------------------------------------------
typedef struct _CRITICAL_SECTION { pthread_mutex_t mutex; } CRITICAL_SECTION, *LPCRITICAL_SECTION, *PCRITICAL_SECTION;
void InitializeCriticalSection(LPCRITICAL_SECTION cs);
BOOL InitializeCriticalSectionAndSpinCount(LPCRITICAL_SECTION cs, DWORD spinCount);
void DeleteCriticalSection(LPCRITICAL_SECTION cs);
void EnterCriticalSection(LPCRITICAL_SECTION cs);
BOOL TryEnterCriticalSection(LPCRITICAL_SECTION cs);
void LeaveCriticalSection(LPCRITICAL_SECTION cs);

typedef struct _SECURITY_ATTRIBUTES { DWORD nLength; LPVOID lpSecurityDescriptor; BOOL bInheritHandle; } SECURITY_ATTRIBUTES, *LPSECURITY_ATTRIBUTES;
typedef DWORD (*LPTHREAD_START_ROUTINE)(LPVOID param);
typedef LPTHREAD_START_ROUTINE PTHREAD_START_ROUTINE;

#define INFINITE 0xFFFFFFFF
#define WAIT_OBJECT_0 0x00000000L
#define WAIT_ABANDONED 0x00000080L
#define WAIT_TIMEOUT 0x00000102L
#define WAIT_FAILED 0xFFFFFFFFL
#define STILL_ACTIVE 0x00000103L
#define CREATE_SUSPENDED 0x00000004
#define THREAD_PRIORITY_LOWEST -2
#define THREAD_PRIORITY_BELOW_NORMAL -1
#define THREAD_PRIORITY_NORMAL 0
#define THREAD_PRIORITY_ABOVE_NORMAL 1
#define THREAD_PRIORITY_HIGHEST 2
#define THREAD_PRIORITY_TIME_CRITICAL 15
#define THREAD_PRIORITY_IDLE -15
#define NORMAL_PRIORITY_CLASS 0x00000020
#define HIGH_PRIORITY_CLASS 0x00000080
#define IDLE_PRIORITY_CLASS 0x00000040

DWORD GetCurrentThreadId();
DWORD GetCurrentProcessId();
HANDLE GetCurrentThread();
HANDLE GetCurrentProcess();
HANDLE CreateThread(LPSECURITY_ATTRIBUTES attr, SIZE_T stackSize, LPTHREAD_START_ROUTINE start, LPVOID param, DWORD flags, LPDWORD threadId);
uintptr_t _beginthreadex(void* security, unsigned stackSize, unsigned (*start)(void*), void* arg, unsigned flags, unsigned* threadId);
uintptr_t _beginthread(void (*start)(void*), unsigned stackSize, void* arg);
void _endthread();
void _endthreadex(unsigned retval);
void ExitThread(DWORD code);
BOOL TerminateThread(HANDLE thread, DWORD code);
BOOL GetExitCodeThread(HANDLE thread, LPDWORD code);
BOOL SetThreadPriority(HANDLE thread, int priority);
int GetThreadPriority(HANDLE thread);
BOOL SetPriorityClass(HANDLE process, DWORD priorityClass);
DWORD GetPriorityClass(HANDLE process);
DWORD SuspendThread(HANDLE thread);
DWORD ResumeThread(HANDLE thread);
DWORD_PTR SetThreadAffinityMask(HANDLE thread, DWORD_PTR mask);
void Sleep(DWORD ms);
DWORD SleepEx(DWORD ms, BOOL alertable);
BOOL SwitchToThread();

HANDLE CreateEvent(LPSECURITY_ATTRIBUTES attr, BOOL manualReset, BOOL initialState, LPCSTR name);
#define CreateEventA CreateEvent
BOOL SetEvent(HANDLE event);
BOOL ResetEvent(HANDLE event);
BOOL PulseEvent(HANDLE event);
HANDLE CreateMutex(LPSECURITY_ATTRIBUTES attr, BOOL initialOwner, LPCSTR name);
#define CreateMutexA CreateMutex
HANDLE OpenMutex(DWORD access, BOOL inherit, LPCSTR name);
BOOL ReleaseMutex(HANDLE mutex);
HANDLE CreateSemaphore(LPSECURITY_ATTRIBUTES attr, LONG initial, LONG maximum, LPCSTR name);
BOOL ReleaseSemaphore(HANDLE sem, LONG count, LPLONG prev);
DWORD WaitForSingleObject(HANDLE handle, DWORD ms);
DWORD WaitForMultipleObjects(DWORD count, const HANDLE* handles, BOOL waitAll, DWORD ms);
BOOL CloseHandle(HANDLE handle);
#define SYNCHRONIZE 0x00100000L
#define MUTEX_ALL_ACCESS 0x1F0001
#define EVENT_ALL_ACCESS 0x1F0003

LONG InterlockedIncrement(LONG volatile* value);
LONG InterlockedDecrement(LONG volatile* value);
LONG InterlockedExchange(LONG volatile* target, LONG value);
LONG InterlockedExchangeAdd(LONG volatile* target, LONG value);
LONG InterlockedCompareExchange(LONG volatile* dest, LONG exchange, LONG comparand);
PVOID InterlockedExchangePointer(PVOID volatile* target, PVOID value);
PVOID InterlockedCompareExchangePointer(PVOID volatile* dest, PVOID exchange, PVOID comparand);

#define TLS_OUT_OF_INDEXES ((DWORD)0xFFFFFFFF)
DWORD TlsAlloc();
BOOL TlsFree(DWORD index);
LPVOID TlsGetValue(DWORD index);
BOOL TlsSetValue(DWORD index, LPVOID value);

//-----------------------------------------------------------------------------
// Timing
//-----------------------------------------------------------------------------
DWORD GetTickCount();
#define GetCurrentTime() GetTickCount()
ULONGLONG GetTickCount64();
DWORD timeGetTime();
#define TIMERR_NOERROR 0
typedef UINT MMRESULT;
inline MMRESULT timeBeginPeriod(UINT) { return TIMERR_NOERROR; }
inline MMRESULT timeEndPeriod(UINT) { return TIMERR_NOERROR; }

//-----------------------------------------------------------------------------
// Files
//-----------------------------------------------------------------------------
#define GENERIC_READ 0x80000000L
#define GENERIC_WRITE 0x40000000L
#define GENERIC_EXECUTE 0x20000000L
#define GENERIC_ALL 0x10000000L
#define FILE_SHARE_READ 0x00000001
#define FILE_SHARE_WRITE 0x00000002
#define FILE_SHARE_DELETE 0x00000004
#define CREATE_NEW 1
#define CREATE_ALWAYS 2
#define OPEN_EXISTING 3
#define OPEN_ALWAYS 4
#define TRUNCATE_EXISTING 5
#define FILE_ATTRIBUTE_READONLY 0x00000001
#define FILE_ATTRIBUTE_HIDDEN 0x00000002
#define FILE_ATTRIBUTE_SYSTEM 0x00000004
#define FILE_ATTRIBUTE_DIRECTORY 0x00000010
#define FILE_ATTRIBUTE_ARCHIVE 0x00000020
#define FILE_ATTRIBUTE_NORMAL 0x00000080
#define FILE_ATTRIBUTE_TEMPORARY 0x00000100
#define FILE_FLAG_WRITE_THROUGH 0x80000000
#define FILE_FLAG_OVERLAPPED 0x40000000
#define FILE_FLAG_NO_BUFFERING 0x20000000
#define FILE_FLAG_RANDOM_ACCESS 0x10000000
#define FILE_FLAG_SEQUENTIAL_SCAN 0x08000000
#define INVALID_FILE_ATTRIBUTES ((DWORD)-1)
#define INVALID_FILE_SIZE ((DWORD)0xFFFFFFFF)
#define INVALID_SET_FILE_POINTER ((DWORD)-1)
#define FILE_BEGIN 0
#define FILE_CURRENT 1
#define FILE_END 2

typedef struct _OVERLAPPED {
	ULONG_PTR Internal;
	ULONG_PTR InternalHigh;
	DWORD Offset;
	DWORD OffsetHigh;
	HANDLE hEvent;
} OVERLAPPED, *LPOVERLAPPED;

typedef struct _WIN32_FIND_DATAA {
	DWORD dwFileAttributes;
	FILETIME ftCreationTime;
	FILETIME ftLastAccessTime;
	FILETIME ftLastWriteTime;
	DWORD nFileSizeHigh;
	DWORD nFileSizeLow;
	DWORD dwReserved0;
	DWORD dwReserved1;
	CHAR cFileName[MAX_PATH];
	CHAR cAlternateFileName[14];
} WIN32_FIND_DATAA, WIN32_FIND_DATA, *PWIN32_FIND_DATA, *LPWIN32_FIND_DATA;

typedef struct _BY_HANDLE_FILE_INFORMATION {
	DWORD dwFileAttributes;
	FILETIME ftCreationTime;
	FILETIME ftLastAccessTime;
	FILETIME ftLastWriteTime;
	DWORD dwVolumeSerialNumber;
	DWORD nFileSizeHigh;
	DWORD nFileSizeLow;
	DWORD nNumberOfLinks;
	DWORD nFileIndexHigh;
	DWORD nFileIndexLow;
} BY_HANDLE_FILE_INFORMATION, *LPBY_HANDLE_FILE_INFORMATION;

HANDLE CreateFile(LPCSTR name, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES sa, DWORD disposition, DWORD flags, HANDLE templ);
#define CreateFileA CreateFile
BOOL ReadFile(HANDLE file, LPVOID buffer, DWORD toRead, LPDWORD read, LPOVERLAPPED ov);
BOOL WriteFile(HANDLE file, LPCVOID buffer, DWORD toWrite, LPDWORD written, LPOVERLAPPED ov);
DWORD SetFilePointer(HANDLE file, LONG distance, PLONG distanceHigh, DWORD method);
BOOL SetEndOfFile(HANDLE file);
BOOL FlushFileBuffers(HANDLE file);
DWORD GetFileSize(HANDLE file, LPDWORD high);
BOOL GetFileTime(HANDLE file, LPFILETIME creation, LPFILETIME access, LPFILETIME write);
BOOL SetFileTime(HANDLE file, const FILETIME* creation, const FILETIME* access, const FILETIME* write);
BOOL GetFileInformationByHandle(HANDLE file, LPBY_HANDLE_FILE_INFORMATION info);
DWORD GetFileAttributes(LPCSTR name);
#define GetFileAttributesA GetFileAttributes
BOOL SetFileAttributes(LPCSTR name, DWORD attrs);
BOOL DeleteFile(LPCSTR name);
#define DeleteFileA DeleteFile
BOOL CopyFile(LPCSTR from, LPCSTR to, BOOL failIfExists);
BOOL MoveFile(LPCSTR from, LPCSTR to);
#define MOVEFILE_REPLACE_EXISTING 0x00000001
BOOL MoveFileEx(LPCSTR from, LPCSTR to, DWORD flags);
BOOL CreateDirectory(LPCSTR name, LPSECURITY_ATTRIBUTES sa);
#define CreateDirectoryA CreateDirectory
BOOL RemoveDirectory(LPCSTR name);
DWORD GetCurrentDirectory(DWORD len, LPSTR buffer);
#define GetCurrentDirectoryA GetCurrentDirectory
BOOL SetCurrentDirectory(LPCSTR name);
#define SetCurrentDirectoryA SetCurrentDirectory
DWORD GetModuleFileName(HMODULE module, LPSTR buffer, DWORD len);
#define GetModuleFileNameA GetModuleFileName
DWORD GetModuleFileNameW(HMODULE module, LPWSTR buffer, DWORD len);
HMODULE GetModuleHandle(LPCSTR name);
#define GetModuleHandleA GetModuleHandle
HMODULE LoadLibrary(LPCSTR name);
#define LoadLibraryA LoadLibrary
BOOL FreeLibrary(HMODULE module);
FARPROC GetProcAddress(HMODULE module, LPCSTR name);
DWORD GetTempPath(DWORD len, LPSTR buffer);
UINT GetTempFileName(LPCSTR path, LPCSTR prefix, UINT unique, LPSTR out);
DWORD GetFullPathName(LPCSTR name, DWORD len, LPSTR buffer, LPSTR* filePart);
#define GetFullPathNameA GetFullPathName
UINT GetWindowsDirectory(LPSTR buffer, UINT len);
UINT GetSystemDirectory(LPSTR buffer, UINT len);
UINT GetDriveType(LPCSTR root);
DWORD GetLogicalDrives();
BOOL GetVolumeInformation(LPCSTR root, LPSTR volName, DWORD volNameLen, LPDWORD serial, LPDWORD maxComponent, LPDWORD fsFlags, LPSTR fsName, DWORD fsNameLen);
BOOL GetDiskFreeSpace(LPCSTR root, LPDWORD sectorsPerCluster, LPDWORD bytesPerSector, LPDWORD freeClusters, LPDWORD totalClusters);
BOOL GetDiskFreeSpaceEx(LPCSTR dir, PULARGE_INTEGER freeToCaller, PULARGE_INTEGER total, PULARGE_INTEGER totalFree);
#define DRIVE_UNKNOWN 0
#define DRIVE_NO_ROOT_DIR 1
#define DRIVE_REMOVABLE 2
#define DRIVE_FIXED 3
#define DRIVE_REMOTE 4
#define DRIVE_CDROM 5
#define DRIVE_RAMDISK 6

HANDLE FindFirstFile(LPCSTR pattern, LPWIN32_FIND_DATA data);
#define FindFirstFileA FindFirstFile
BOOL FindNextFile(HANDLE find, LPWIN32_FIND_DATA data);
#define FindNextFileA FindNextFile
BOOL FindClose(HANDLE find);

// File mapping
#define PAGE_WRITECOPY 0x08
#define FILE_MAP_READ 0x0004
#define FILE_MAP_WRITE 0x0002
#define FILE_MAP_COPY 0x0001
HANDLE CreateFileMapping(HANDLE file, LPSECURITY_ATTRIBUTES sa, DWORD protect, DWORD sizeHigh, DWORD sizeLow, LPCSTR name);
LPVOID MapViewOfFile(HANDLE mapping, DWORD access, DWORD offsetHigh, DWORD offsetLow, SIZE_T bytes);
BOOL UnmapViewOfFile(LPCVOID address);

//-----------------------------------------------------------------------------
// Process / system
//-----------------------------------------------------------------------------
typedef struct _SYSTEM_INFO {
	union {
		DWORD dwOemId;
		struct { WORD wProcessorArchitecture; WORD wReserved; };
	};
	DWORD dwPageSize;
	LPVOID lpMinimumApplicationAddress;
	LPVOID lpMaximumApplicationAddress;
	DWORD_PTR dwActiveProcessorMask;
	DWORD dwNumberOfProcessors;
	DWORD dwProcessorType;
	DWORD dwAllocationGranularity;
	WORD wProcessorLevel;
	WORD wProcessorRevision;
} SYSTEM_INFO, *LPSYSTEM_INFO;
void GetSystemInfo(LPSYSTEM_INFO info);

typedef struct _OSVERSIONINFOA {
	DWORD dwOSVersionInfoSize;
	DWORD dwMajorVersion;
	DWORD dwMinorVersion;
	DWORD dwBuildNumber;
	DWORD dwPlatformId;
	CHAR szCSDVersion[128];
} OSVERSIONINFOA, OSVERSIONINFO, *LPOSVERSIONINFO;
typedef struct _OSVERSIONINFOEXA {
	DWORD dwOSVersionInfoSize;
	DWORD dwMajorVersion;
	DWORD dwMinorVersion;
	DWORD dwBuildNumber;
	DWORD dwPlatformId;
	CHAR szCSDVersion[128];
	WORD wServicePackMajor;
	WORD wServicePackMinor;
	WORD wSuiteMask;
	BYTE wProductType;
	BYTE wReserved;
} OSVERSIONINFOEXA, OSVERSIONINFOEX, *LPOSVERSIONINFOEX;
#define VER_PLATFORM_WIN32s 0
#define VER_PLATFORM_WIN32_WINDOWS 1
#define VER_PLATFORM_WIN32_NT 2
BOOL GetVersionEx(LPOSVERSIONINFO info);
#define GetVersionExA GetVersionEx
DWORD GetVersion();

BOOL GetComputerName(LPSTR buffer, LPDWORD len);
#define GetComputerNameA GetComputerName
BOOL GetUserName(LPSTR buffer, LPDWORD len);
#define GetUserNameA GetUserName
#define MAX_COMPUTERNAME_LENGTH 15
LPSTR GetCommandLine();
extern int __argc;
extern char** __argv;
#define GetCommandLineA GetCommandLine
DWORD GetEnvironmentVariable(LPCSTR name, LPSTR buffer, DWORD len);
BOOL SetEnvironmentVariable(LPCSTR name, LPCSTR value);
void ExitProcess(UINT code);
BOOL TerminateProcess(HANDLE process, UINT code);
void OutputDebugStringA(LPCSTR str);
void OutputDebugStringW(LPCWSTR str);
#ifdef OutputDebugString
#undef OutputDebugString
#endif
#define OutputDebugString OutputDebugStringA
BOOL IsDebuggerPresent();
void DebugBreak();
LANGID GetUserDefaultLangID();
LANGID GetSystemDefaultLangID();
LCID GetUserDefaultLCID();
#define MAKELANGID(p, s) ((((WORD)(s)) << 10) | (WORD)(p))
#define PRIMARYLANGID(lgid) ((WORD)(lgid) & 0x3ff)
#define SUBLANGID(lgid) ((WORD)(lgid) >> 10)
#define LANG_NEUTRAL 0x00
#define LANG_ENGLISH 0x09
#define LANG_GERMAN 0x07
#define LANG_FRENCH 0x0c
#define LANG_SPANISH 0x0a
#define LANG_ITALIAN 0x10
#define LANG_KOREAN 0x12
#define LANG_CHINESE 0x04
#define LANG_JAPANESE 0x11
#define LANG_POLISH 0x15
#define LANG_PORTUGUESE 0x16
#define LANG_RUSSIAN 0x19
#define SUBLANG_DEFAULT 0x01
#define SUBLANG_NEUTRAL 0x00
#define SUBLANG_ENGLISH_US 0x01

typedef struct _STARTUPINFOA {
	DWORD cb;
	LPSTR lpReserved;
	LPSTR lpDesktop;
	LPSTR lpTitle;
	DWORD dwX, dwY, dwXSize, dwYSize, dwXCountChars, dwYCountChars, dwFillAttribute, dwFlags;
	WORD wShowWindow;
	WORD cbReserved2;
	LPBYTE lpReserved2;
	HANDLE hStdInput, hStdOutput, hStdError;
} STARTUPINFOA, STARTUPINFO, *LPSTARTUPINFO;
typedef struct _PROCESS_INFORMATION { HANDLE hProcess; HANDLE hThread; DWORD dwProcessId; DWORD dwThreadId; } PROCESS_INFORMATION, *LPPROCESS_INFORMATION;
BOOL CreateProcess(LPCSTR app, LPSTR cmdLine, LPSECURITY_ATTRIBUTES pa, LPSECURITY_ATTRIBUTES ta, BOOL inherit, DWORD flags, LPVOID env, LPCSTR dir, LPSTARTUPINFO si, LPPROCESS_INFORMATION pi);
#define CreateProcessA CreateProcess
BOOL GetExitCodeProcess(HANDLE process, LPDWORD code);
void GetStartupInfo(LPSTARTUPINFO si);

int MulDiv(int number, int numerator, int denominator);

// Floating point control (x87 precision control does not exist on ARM; the
// default rounding mode already is round-to-nearest).
#define _MCW_EM 0x0008001F
#define _MCW_RC 0x00000300
#define _MCW_PC 0x00030000
#define _RC_NEAR 0x00000000
#define _RC_DOWN 0x00000100
#define _RC_UP 0x00000200
#define _RC_CHOP 0x00000300
#define _PC_24 0x00020000
#define _PC_53 0x00010000
#define _PC_64 0x00000000
#define _EM_INVALID 0x00000010
#define _EM_DENORMAL 0x00080000
#define _EM_ZERODIVIDE 0x00000008
#define _EM_OVERFLOW 0x00000004
#define _EM_UNDERFLOW 0x00000002
#define _EM_INEXACT 0x00000001
inline void _fpreset() {}
inline unsigned int _statusfp() { return 0; }
inline unsigned int _clearfp() { return 0; }
inline unsigned int _controlfp(unsigned int, unsigned int) { return _PC_53 | _RC_NEAR | _MCW_EM; }
inline int _controlfp_s(unsigned int* current, unsigned int, unsigned int) { if (current) *current = _PC_53 | _RC_NEAR | _MCW_EM; return 0; }

#define TEXT(x) x
#define _TEXT(x) x

#define SEM_FAILCRITICALERRORS 0x0001
#define SEM_NOGPFAULTERRORBOX 0x0002
#define SEM_NOOPENFILEERRORBOX 0x8000
inline UINT SetErrorMode(UINT) { return 0; }

typedef DWORD EXECUTION_STATE;
#define ES_SYSTEM_REQUIRED ((DWORD)0x00000001)
#define ES_DISPLAY_REQUIRED ((DWORD)0x00000002)
#define ES_CONTINUOUS ((DWORD)0x80000000)
EXECUTION_STATE SetThreadExecutionState(EXECUTION_STATE flags);

//-----------------------------------------------------------------------------
// Structured exception handling (no-op)
//-----------------------------------------------------------------------------
typedef struct _EXCEPTION_RECORD {
	DWORD ExceptionCode;
	DWORD ExceptionFlags;
	struct _EXCEPTION_RECORD* ExceptionRecord;
	PVOID ExceptionAddress;
	DWORD NumberParameters;
	ULONG_PTR ExceptionInformation[15];
} EXCEPTION_RECORD, *PEXCEPTION_RECORD;
typedef struct _CONTEXT { DWORD ContextFlags; } CONTEXT, *PCONTEXT, *LPCONTEXT;
typedef struct _EXCEPTION_POINTERS { PEXCEPTION_RECORD ExceptionRecord; PCONTEXT ContextRecord; } EXCEPTION_POINTERS, *PEXCEPTION_POINTERS, *LPEXCEPTION_POINTERS;
typedef LONG (*LPTOP_LEVEL_EXCEPTION_FILTER)(EXCEPTION_POINTERS* info);
typedef LPTOP_LEVEL_EXCEPTION_FILTER PTOP_LEVEL_EXCEPTION_FILTER;
inline LPTOP_LEVEL_EXCEPTION_FILTER SetUnhandledExceptionFilter(LPTOP_LEVEL_EXCEPTION_FILTER) { return NULL; }
#define EXCEPTION_EXECUTE_HANDLER 1
#define EXCEPTION_CONTINUE_SEARCH 0
#define EXCEPTION_CONTINUE_EXECUTION -1
#define EXCEPTION_ACCESS_VIOLATION 0xC0000005L
#define EXCEPTION_DATATYPE_MISALIGNMENT 0x80000002L
#define EXCEPTION_BREAKPOINT 0x80000003L
#define EXCEPTION_SINGLE_STEP 0x80000004L
#define EXCEPTION_ARRAY_BOUNDS_EXCEEDED 0xC000008CL
#define EXCEPTION_FLT_DENORMAL_OPERAND 0xC000008DL
#define EXCEPTION_FLT_DIVIDE_BY_ZERO 0xC000008EL
#define EXCEPTION_FLT_INEXACT_RESULT 0xC000008FL
#define EXCEPTION_FLT_INVALID_OPERATION 0xC0000090L
#define EXCEPTION_FLT_OVERFLOW 0xC0000091L
#define EXCEPTION_FLT_STACK_CHECK 0xC0000092L
#define EXCEPTION_FLT_UNDERFLOW 0xC0000093L
#define EXCEPTION_INT_DIVIDE_BY_ZERO 0xC0000094L
#define EXCEPTION_INT_OVERFLOW 0xC0000095L
#define EXCEPTION_PRIV_INSTRUCTION 0xC0000096L
#define EXCEPTION_IN_PAGE_ERROR 0xC0000006L
#define EXCEPTION_ILLEGAL_INSTRUCTION 0xC000001DL
#define EXCEPTION_NONCONTINUABLE_EXCEPTION 0xC0000025L
#define EXCEPTION_STACK_OVERFLOW 0xC00000FDL
#define EXCEPTION_INVALID_DISPOSITION 0xC0000026L
#define EXCEPTION_GUARD_PAGE 0x80000001L
#define EXCEPTION_INVALID_HANDLE 0xC0000008L

//-----------------------------------------------------------------------------
// Registry (backed by an INI-style file in the user's Application Support dir)
//-----------------------------------------------------------------------------
#define HKEY_CLASSES_ROOT ((HKEY)(ULONG_PTR)((LONG)0x80000000))
#define HKEY_CURRENT_USER ((HKEY)(ULONG_PTR)((LONG)0x80000001))
#define HKEY_LOCAL_MACHINE ((HKEY)(ULONG_PTR)((LONG)0x80000002))
#define HKEY_USERS ((HKEY)(ULONG_PTR)((LONG)0x80000003))
#define KEY_QUERY_VALUE 0x0001
#define KEY_SET_VALUE 0x0002
#define KEY_CREATE_SUB_KEY 0x0004
#define KEY_ENUMERATE_SUB_KEYS 0x0008
#define KEY_READ 0x20019
#define KEY_WRITE 0x20006
#define KEY_EXECUTE 0x20019
#define KEY_ALL_ACCESS 0xF003F
#define KEY_WOW64_32KEY 0x0200
#define KEY_WOW64_64KEY 0x0100
#define REG_NONE 0
#define REG_SZ 1
#define REG_EXPAND_SZ 2
#define REG_BINARY 3
#define REG_DWORD 4
#define REG_MULTI_SZ 7
#define REG_OPTION_NON_VOLATILE 0x00000000
#define REG_CREATED_NEW_KEY 0x00000001
#define REG_OPENED_EXISTING_KEY 0x00000002
typedef DWORD REGSAM;
typedef DWORD ACCESS_MASK;
LONG RegOpenKeyEx(HKEY key, LPCSTR subKey, DWORD options, REGSAM sam, PHKEY result);
#define RegOpenKeyExA RegOpenKeyEx
LONG RegOpenKey(HKEY key, LPCSTR subKey, PHKEY result);
LONG RegCreateKeyEx(HKEY key, LPCSTR subKey, DWORD reserved, LPSTR cls, DWORD options, REGSAM sam, LPSECURITY_ATTRIBUTES sa, PHKEY result, LPDWORD disposition);
#define RegCreateKeyExA RegCreateKeyEx
LONG RegCreateKey(HKEY key, LPCSTR subKey, PHKEY result);
LONG RegCloseKey(HKEY key);
LONG RegQueryValueEx(HKEY key, LPCSTR name, LPDWORD reserved, LPDWORD type, LPBYTE data, LPDWORD dataLen);
#define RegQueryValueExA RegQueryValueEx
LONG RegSetValueEx(HKEY key, LPCSTR name, DWORD reserved, DWORD type, const BYTE* data, DWORD dataLen);
#define RegSetValueExA RegSetValueEx
LONG RegQueryValueExW(HKEY key, LPCWSTR name, LPDWORD reserved, LPDWORD type, LPBYTE data, LPDWORD dataLen);
LONG RegSetValueExW(HKEY key, LPCWSTR name, DWORD reserved, DWORD type, const BYTE* data, DWORD dataLen);
LONG RegDeleteValue(HKEY key, LPCSTR name);
LONG RegDeleteKey(HKEY key, LPCSTR subKey);
LONG RegEnumKeyEx(HKEY key, DWORD index, LPSTR name, LPDWORD nameLen, LPDWORD reserved, LPSTR cls, LPDWORD clsLen, PFILETIME lastWrite);
LONG RegEnumKey(HKEY key, DWORD index, LPSTR name, DWORD nameLen);
LONG RegEnumValue(HKEY key, DWORD index, LPSTR name, LPDWORD nameLen, LPDWORD reserved, LPDWORD type, LPBYTE data, LPDWORD dataLen);
LONG RegQueryInfoKey(HKEY key, LPSTR cls, LPDWORD clsLen, LPDWORD reserved, LPDWORD subKeys, LPDWORD maxSubKeyLen, LPDWORD maxClassLen, LPDWORD values, LPDWORD maxValueNameLen, LPDWORD maxValueLen, LPDWORD securityDescriptor, PFILETIME lastWrite);

//-----------------------------------------------------------------------------
// Profile (INI) strings
//-----------------------------------------------------------------------------
DWORD GetPrivateProfileString(LPCSTR app, LPCSTR key, LPCSTR def, LPSTR out, DWORD size, LPCSTR file);
UINT GetPrivateProfileInt(LPCSTR app, LPCSTR key, INT def, LPCSTR file);
BOOL WritePrivateProfileString(LPCSTR app, LPCSTR key, LPCSTR str, LPCSTR file);

//-----------------------------------------------------------------------------
// Windowing and messages (implemented on top of SDL by the platform layer)
//-----------------------------------------------------------------------------
#include "win32shim_user.h"

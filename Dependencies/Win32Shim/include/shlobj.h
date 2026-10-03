// Win32Shim: shell folder lookups mapped onto the macOS user folders.
#pragma once
#include <objbase.h>

#define CSIDL_DESKTOP 0x0000
#define CSIDL_PERSONAL 0x0005
#define CSIDL_MYDOCUMENTS CSIDL_PERSONAL
#define CSIDL_DESKTOPDIRECTORY 0x0010
#define CSIDL_APPDATA 0x001a
#define CSIDL_LOCAL_APPDATA 0x001c
#define CSIDL_COMMON_APPDATA 0x0023
#define CSIDL_PROGRAM_FILES 0x0026
#define CSIDL_FLAG_CREATE 0x8000
#define SHGFP_TYPE_CURRENT 0
#define KF_FLAG_DEFAULT 0x00000000
#define KF_FLAG_CREATE 0x00008000

typedef struct _ITEMIDLIST { char path[MAX_PATH]; } ITEMIDLIST, *LPITEMIDLIST;
typedef const ITEMIDLIST* LPCITEMIDLIST;
typedef GUID KNOWNFOLDERID;
typedef const KNOWNFOLDERID& REFKNOWNFOLDERID;
DEFINE_GUID(FOLDERID_Documents, 0xFDD39AD0, 0x238F, 0x46AF, 0xAD, 0xB4, 0x6C, 0x85, 0x48, 0x03, 0x69, 0xC7);

BOOL SHGetSpecialFolderPath(HWND hwnd, LPSTR path, int csidl, BOOL create);
#define SHGetSpecialFolderPathA SHGetSpecialFolderPath
HRESULT SHGetFolderPath(HWND hwnd, int csidl, HANDLE token, DWORD flags, LPSTR path);
#define SHGetFolderPathA SHGetFolderPath
HRESULT SHGetSpecialFolderLocation(HWND hwnd, int csidl, LPITEMIDLIST* pidl);
BOOL SHGetPathFromIDList(LPCITEMIDLIST pidl, LPSTR path);
#define SHGetPathFromIDListA SHGetPathFromIDList
inline void CoTaskMemFree(LPVOID p) { free(p); }
inline LPVOID CoTaskMemAlloc(SIZE_T bytes) { return malloc(bytes); }

// Win32Shim forwarding header.
#pragma once
#include <windows.h>
#include <sys/stat.h>
#include <unistd.h>
inline int _mkdir(const char* path) { return mkdir(path, 0755); }
#define mkdir_win32 _mkdir

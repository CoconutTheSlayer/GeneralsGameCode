// Win32Shim forwarding header.
#pragma once
#include <windows.h>
#include <unistd.h>
#define _getpid getpid
#define _P_WAIT 0
#define _P_NOWAIT 1
#define _P_OVERLAY 2
#define _P_DETACH 4
// Spawning Windows executables is not supported.
inline intptr_t _spawnl(int, const char*, const char*, ...) { errno = ENOENT; return -1; }
inline intptr_t _spawnv(int, const char*, const char* const*) { errno = ENOENT; return -1; }
inline intptr_t _spawnvp(int, const char*, const char* const*) { errno = ENOENT; return -1; }
#define spawnl _spawnl

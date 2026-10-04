// Win32Shim forwarding header.
#pragma once
#include <windows.h>
#include <sys/stat.h>
#include <unistd.h>
#define _mkdir Win32Shim_mkdir
#define mkdir_win32 _mkdir

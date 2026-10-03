// Win32Shim forwarding header.
#pragma once
#include <stdio.h>
inline int _kbhit() { return 0; }
#define kbhit _kbhit
inline int _getch() { return getchar(); }
#define getch _getch

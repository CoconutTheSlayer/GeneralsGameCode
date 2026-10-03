// Win32Shim forwarding header.
#pragma once
#include <windows.h>
#define _T(x) x
#define _tcsncpy strncpy
#define _tcscat strcat
#define _tcschr strchr
#define _tcsrchr strrchr
#define _tcsstr strstr
#define _stprintf sprintf
#define _tprintf printf
#define _ttoi atoi

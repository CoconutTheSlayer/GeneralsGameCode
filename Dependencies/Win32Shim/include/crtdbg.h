// Win32Shim forwarding header.
#pragma once
#include <assert.h>
#define _ASSERT(x) assert(x)
#define _ASSERTE(x) assert(x)
#define _CrtCheckMemory() 1
#define _CrtSetDbgFlag(x) 0
#define _CrtDumpMemoryLeaks() 0

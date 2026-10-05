// Win32Shim forwarding header.
#pragma once
#include <stdlib.h>
#include <alloca.h>
#if defined(__APPLE__)
#include <malloc/malloc.h>
#define _msize malloc_size
#else
#include_next <malloc.h>
#define _msize malloc_usable_size
#endif

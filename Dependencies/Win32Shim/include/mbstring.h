// Win32Shim: multibyte string helpers (UTF-8 aware character counting).
#pragma once
#include <stddef.h>
inline size_t _mbsnccnt(const unsigned char* str, size_t bytes)
{
	size_t count = 0;
	for (size_t i = 0; i < bytes && str[i]; ++i)
	{
		if ((str[i] & 0xC0) != 0x80)
			++count;
	}
	return count;
}
inline size_t _mbslen(const unsigned char* str) { return _mbsnccnt(str, (size_t)-1); }

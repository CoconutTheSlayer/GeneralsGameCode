// Win32Shim forwarding header.
#pragma once
#include <exception>
typedef void (*_se_translator_function)(unsigned int, struct _EXCEPTION_POINTERS*);
inline _se_translator_function _set_se_translator(_se_translator_function) { return 0; }

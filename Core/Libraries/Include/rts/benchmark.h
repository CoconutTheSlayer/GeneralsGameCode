// The native benchmark is independent of Tracy; other platforms retain their existing profiler.
#pragma once
#if defined(__APPLE__) && defined(RTS_POSIX_PORT)
#include <d3d8metal_profile.h>
#else
#define RTS_BENCH_SCOPE(name) ((void)0)
#define RTS_BENCH_DETAIL(name) ((void)0)
#define RTS_BENCH_PHASE(name) ((void)0)
#define RTS_BENCH_COUNTER(name,value) ((void)0)
#define RTS_BENCH_BEGIN_FRAME(logic) ((void)0)
#define RTS_BENCH_END_FRAME() ((void)0)
#endif

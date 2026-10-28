#include "d3d8metal_profile.h"
#include <chrono>
#include <cstdlib>
#include <thread>

int main(int argc, char** argv)
{
    if (argc != 2) return 2;
    setenv("GENERALS_PROFILE", argv[1], 1);
    setenv("GENERALS_PROFILE_MODE", "cpu", 1);
    rts_bench::beginFrame(200);
    {
        RTS_BENCH_SCOPE("outer");
        {
            RTS_BENCH_SCOPE("sleep \"quoted\"");
            std::this_thread::sleep_for(std::chrono::milliseconds(10));
        }
        RTS_BENCH_COUNTER("draw_calls", 3);
        RTS_BENCH_COUNTER("draw_calls", 2);
    }
    std::thread renderer([] {
        rts_bench::beginRenderFrame(1, 200);
        { RTS_BENCH_SCOPE("encode"); }
        rts_bench::endRenderFrame();
    });
    renderer.join();
    rts_bench::endFrame();
    // GPU completion deliberately arrives after the CPU frames.
    rts_bench::beginFrame(201);
    rts_bench::endFrame();
    rts_bench::gpuEvent("command: render", 1, 200, rts_bench::wallUs(), 20);
    return 0;
}

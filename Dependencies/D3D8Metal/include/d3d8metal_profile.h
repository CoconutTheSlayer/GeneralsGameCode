// Opt-in native benchmark recorder. Names passed to scopes/counters must be string literals.
#pragma once
#include <cstdint>
#include <string>
#include <vector>

namespace rts_bench {
bool enabled();
bool capturing();
bool scopesEnabled();
bool gpuEnabled();
bool splitPasses();
bool detailEnabled();
double wallUs();
double cpuUs();
uint64_t frame();
uint32_t logicFrame();
void beginFrame(uint32_t logic);
void endFrame();
void beginRenderFrame(uint64_t id, uint32_t logic);
void endRenderFrame();
void beginWorkerFrame(uint64_t id, uint32_t logic, const char* thread);
void endWorkerFrame();
void counter(const char* name, double value);
void metadata(const char* name, const char* value);
struct GPUTiming { std::string name; double startUs, durationUs; };
void gpuEvents(uint64_t frame, uint32_t logic, std::vector<GPUTiming> timings);
void gpuEvent(const char* name, uint64_t frame, uint32_t logic, double startUs, double durationUs);
void setHooks(void* context, void (*frameHook)(void*, uint64_t, uint32_t), void (*phaseHook)(void*, const char*));
class Scope {
public:
    explicit Scope(const char* name, bool active = true);
    ~Scope();
    Scope(const Scope&) = delete;
    Scope& operator=(const Scope&) = delete;
private:
    const char* name_ = nullptr;
    Scope* parent_ = nullptr;
    double wall_ = 0, cpu_ = 0, childWall_ = 0, childCpu_ = 0;
};
class Phase {
public:
    explicit Phase(const char* name);
    ~Phase();
private:
    Scope scope_;
    const char* previous_;
};
}
#define RTS_BENCH_JOIN2(a,b) a##b
#define RTS_BENCH_JOIN(a,b) RTS_BENCH_JOIN2(a,b)
#define RTS_BENCH_SCOPE(name) rts_bench::Scope RTS_BENCH_JOIN(benchScope_,__LINE__)(name)
#define RTS_BENCH_DETAIL(name) rts_bench::Scope RTS_BENCH_JOIN(benchScope_,__LINE__)(name, rts_bench::detailEnabled())
#define RTS_BENCH_PHASE(name) rts_bench::Phase RTS_BENCH_JOIN(benchPhase_,__LINE__)(name)
#define RTS_BENCH_COUNTER(name,value) rts_bench::counter(name,value)
#define RTS_BENCH_BEGIN_FRAME(logic) rts_bench::beginFrame(logic)
#define RTS_BENCH_END_FRAME() rts_bench::endFrame()

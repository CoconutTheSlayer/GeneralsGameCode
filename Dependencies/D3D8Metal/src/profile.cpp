// Buffered CPU timelines and GPU results. No file writes on the game/render threads.
#include "d3d8metal_profile.h"
#include <mach/mach_time.h>
#include <time.h>
#include <algorithm>
#include <condition_variable>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <deque>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace rts_bench {
namespace {
struct Event {
    const char* kind;
    std::string name;
    const char* thread;
    uint64_t frame;
    uint32_t logic;
    double start, wall, cpu, selfWall, selfCpu;
};
struct Recorder {
    FILE* file = nullptr;
    bool scopes = false, gpu = false, split = false, detail = false, stop = false;
    uint64_t dropped = 0;
    size_t queuedEvents = 0;
    std::mutex mutex;
    std::condition_variable wake;
    std::deque<std::vector<Event>> queue;
    std::thread writer;
    static std::string quote(const std::string& in) {
        std::string out = "\"";
        for (unsigned char c : in) {
            if (c == '"' || c == '\\') { out += '\\'; out += c; }
            else if (c < 32) { char s[7]; snprintf(s, sizeof(s), "\\u%04x", c); out += s; }
            else out += c;
        }
        return out + '"';
    }
    Recorder() {
        const char* path = getenv("GENERALS_PROFILE");
        if (!path || !*path) return;
        file = fopen(path, "w");
        if (!file) { perror("GENERALS_PROFILE"); return; }
        const char* mode = getenv("GENERALS_PROFILE_MODE");
        if (!mode) mode = "gpu";
        scopes = strcmp(mode, "frames") != 0;
        gpu = strcmp(mode, "gpu") == 0 || strcmp(mode, "passes") == 0;
        split = strcmp(mode, "passes") == 0;
        detail = scopes && getenv("GENERALS_PROFILE_DETAIL") && strcmp(getenv("GENERALS_PROFILE_DETAIL"), "0") != 0;
        fprintf(file, "{\"kind\":\"metadata\",\"name\":\"mode\",\"value\":%s,\"schema\":1,\"detail\":%s}\n", quote(mode).c_str(), detail ? "true" : "false");
        fflush(file);
        writer = std::thread([this] {
            for (;;) {
                std::vector<Event> events;
                {
                    std::unique_lock<std::mutex> lock(mutex);
                    wake.wait(lock, [this]{ return stop || !queue.empty(); });
                    if (queue.empty()) break;
                    events = std::move(queue.front()); queue.pop_front();
                    queuedEvents -= events.size();
                }
                for (const Event& e : events) {
                    fprintf(file, "{\"kind\":\"%s\",\"name\":%s,\"thread\":\"%s\",\"frame\":%llu,\"logic\":%u,\"start_us\":%.3f,\"wall_us\":%.3f,\"cpu_us\":%.3f,\"self_wall_us\":%.3f,\"self_cpu_us\":%.3f}\n",
                        e.kind, quote(e.name).c_str(), e.thread, (unsigned long long)e.frame, e.logic, e.start, e.wall, e.cpu, e.selfWall, e.selfCpu);
                }
                fflush(file);
            }
        });
    }
    void push(std::vector<Event>&& events) {
        if (!file || events.empty()) return;
        std::lock_guard<std::mutex> lock(mutex);
        if (stop || queue.size() >= 1024 || queuedEvents + events.size() > 262144) { dropped += events.size(); return; }
        queuedEvents += events.size();
        queue.push_back(std::move(events)); wake.notify_one();
    }
    void shutdown() {
        if (!file) return;
        { std::lock_guard<std::mutex> lock(mutex); stop = true; wake.notify_one(); }
        writer.join();
        std::lock_guard<std::mutex> lock(mutex);
        fprintf(file, "{\"kind\":\"footer\",\"dropped_events\":%llu,\"write_error\":%s}\n", (unsigned long long)dropped, ferror(file) ? "true" : "false");
        fclose(file);
    }
};
// GPU completion callbacks can outlive static destruction. Keep synchronization state alive
// until process exit, but drain/join the writer and close the file in atexit.
Recorder& recorder() {
    static Recorder* r = [] {
        auto result = new Recorder;
        std::atexit([] { recorder().shutdown(); });
        return result;
    }();
    return *r;
}
struct ThreadState {
    uint64_t frame = 0;
    uint32_t logic = 0;
    const char* thread = "main";
    const char* phase = "unclassified";
    double start = 0, cpu = 0;
    Scope* scope = nullptr;
    std::vector<Event> events;
    std::vector<std::pair<const char*, double>> counters;
    uint64_t dropped = 0;
};
thread_local ThreadState state;
void* hookContext = nullptr;
void (*onFrame)(void*, uint64_t, uint32_t) = nullptr;
void (*onPhase)(void*, const char*) = nullptr;
void add(Event e) {
    if (state.events.size() < 65536) state.events.push_back(std::move(e));
    else ++state.dropped;
}
void start(uint64_t id, uint32_t logic, const char* thread) {
    state.frame = id; state.logic = logic; state.thread = thread;
    state.start = capturing() ? wallUs() : 1; state.cpu = capturing() ? cpuUs() : 0;
}
void finish() {
    if (!capturing()) { state.start = 0; return; }
    double cpu = cpuUs() - state.cpu, wall = wallUs() - state.start;
    add({"frame", state.thread, state.thread, state.frame, state.logic, state.start, wall, cpu, 0, 0});
    for (auto& c : state.counters)
        add({"counter", c.first, state.thread, state.frame, state.logic, state.start, c.second, 0, 0, 0});
    if (state.dropped) state.events.push_back({"counter", "dropped_events", state.thread, state.frame, state.logic, state.start, (double)state.dropped, 0, 0, 0});
    state.dropped = 0; state.counters.clear();
    recorder().push(std::move(state.events));
    state.events.clear(); state.start = 0;
}
}
bool enabled() { static const bool result = recorder().file != nullptr; return result; }
namespace {
bool captureLogic(uint32_t logic) {
    static const uint32_t first = getenv("GENERALS_PROFILE_START_LOGIC") ? (uint32_t)strtoul(getenv("GENERALS_PROFILE_START_LOGIC"), nullptr, 10) : 0;
    static const uint32_t last = getenv("GENERALS_PROFILE_END_LOGIC") ? (uint32_t)strtoul(getenv("GENERALS_PROFILE_END_LOGIC"), nullptr, 10) : UINT32_MAX;
    return logic >= first && logic < last;
}
}
bool capturing() { return enabled() && captureLogic(state.logic); }
bool scopesEnabled() { return capturing() && recorder().scopes; }
bool gpuEnabled() { return enabled() && recorder().gpu; }
bool splitPasses() { return enabled() && recorder().split; }
bool detailEnabled() { return enabled() && recorder().detail; }
double wallUs() {
    static const double scale = []{ mach_timebase_info_data_t info; mach_timebase_info(&info); return double(info.numer) / info.denom / 1000.0; }();
    return mach_absolute_time() * scale;
}
double cpuUs() { timespec t; clock_gettime(CLOCK_THREAD_CPUTIME_ID, &t); return t.tv_sec * 1e6 + t.tv_nsec / 1000.0; }
uint64_t frame() { return state.frame; }
uint32_t logicFrame() { return state.logic; }
void setHooks(void* context, void (*frameHook)(void*, uint64_t, uint32_t), void (*phaseHook)(void*, const char*)) {
    hookContext = context; onFrame = frameHook; onPhase = phaseHook;
}
void beginFrame(uint32_t logic) {
    if (!enabled()) return;
    start(state.frame + 1, logic, "main");
    if (onFrame) onFrame(hookContext, state.frame, logic);
}
void endFrame() { if (enabled()) finish(); }
void beginRenderFrame(uint64_t id, uint32_t logic) {
    if (!enabled()) return;
    // The inline renderer uses the game thread's frame and scope stack.
    if (state.start && strcmp(state.thread, "main") == 0) return;
    start(id, logic, "renderer");
}
void endRenderFrame() { if (enabled() && strcmp(state.thread, "renderer") == 0 && state.start) finish(); }
void beginWorkerFrame(uint64_t id, uint32_t logic, const char* thread) {
    if (enabled()) start(id, logic, thread);
}
void endWorkerFrame() { if (enabled() && state.start) finish(); }
void counter(const char* name, double value) {
    if (!scopesEnabled()) return;
    for (auto& c : state.counters) if (c.first == name || strcmp(c.first, name) == 0) { c.second += value; return; }
    state.counters.emplace_back(name, value);
}
void metadata(const char* name, const char* value) {
    if (enabled()) recorder().push({{"info", std::string(name) + ": " + value, "metadata", 0, 0, 0, 0, 0, 0, 0}});
}
void gpuEvents(uint64_t frame, uint32_t logic, std::vector<GPUTiming> timings) {
    if (!enabled() || !captureLogic(logic)) return;
    std::vector<Event> events;
    events.reserve(timings.size());
    for (auto& t : timings) events.push_back({"gpu", std::move(t.name), "GPU", frame, logic, t.startUs, t.durationUs, 0, 0, 0});
    recorder().push(std::move(events));
}
void gpuEvent(const char* name, uint64_t frame, uint32_t logic, double startUs, double durationUs) {
    gpuEvents(frame, logic, {{name, startUs, durationUs}});
}
Scope::Scope(const char* name, bool active) {
    if (!active || !scopesEnabled()) return;
    name_ = name; parent_ = state.scope; state.scope = this;
    wall_ = wallUs(); cpu_ = cpuUs();
}
Scope::~Scope() {
    if (!name_) return;
    double cpu = cpuUs() - cpu_, wall = wallUs() - wall_;
    state.scope = parent_;
    if (parent_) { parent_->childWall_ += wall; parent_->childCpu_ += cpu; }
    add({"scope", name_, state.thread, state.frame, state.logic, wall_, wall, cpu, std::max(0.0, wall - childWall_), std::max(0.0, cpu - childCpu_)});
}
Phase::Phase(const char* name) : scope_(name), previous_(state.phase) {
    if (!scopesEnabled()) return;
    state.phase = name;
    if (onPhase) onPhase(hookContext, name);
}
Phase::~Phase() {
    if (!scopesEnabled()) return;
    state.phase = previous_;
    if (onPhase) onPhase(hookContext, previous_);
}
}

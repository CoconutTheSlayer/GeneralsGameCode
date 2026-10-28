// Synchronous, bounded visual jobs. Call from the game thread only; jobs must not
// submit other jobs, access graphics APIs, allocate engine objects or change simulation.
#pragma once
#include <algorithm>
#include <atomic>
#include <condition_variable>
#include <cstdlib>
#include <mutex>
#include <thread>
#include <vector>
#include "rts/benchmark.h"

namespace rts_visual {
inline unsigned workerCount() {
    // Experimental until repeatable battle measurements justify enabling by default.
    static const unsigned count = [] {
        const char* setting = std::getenv("GENERALS_VISUAL_WORKERS");
        const unsigned requested = setting ? unsigned(std::max(0, std::atoi(setting))) : 0;
        const unsigned cores = std::thread::hardware_concurrency();
        return std::min({requested, 4u, cores > 2 ? cores - 2 : 0u});
    }();
    return count;
}
inline bool enabled(const char* setting) {
    const char* value = std::getenv(setting);
    return workerCount() && (!value || std::atoi(value) != 0);
}
inline bool verify() {
    static const bool value = std::getenv("GENERALS_VERIFY_VISUAL_JOBS") != nullptr;
    return value;
}

class JobPool {
    std::mutex mutex_;
    std::condition_variable wake_, done_;
    std::vector<std::thread> workers_;
    std::atomic<size_t> next_{0};
    size_t count_ = 0, grain_ = 1, generation_ = 0, remaining_ = 0;
    void* context_ = nullptr;
    void (*function_)(void*, size_t) = nullptr;
    bool stop_ = false;
#if defined(__APPLE__) && defined(RTS_POSIX_PORT)
    bool profile_ = false;
    uint64_t frame_ = 0;
    uint32_t logic_ = 0;
    const char* scope_ = nullptr;
#endif
    void consume() {
        for (;;) {
            const size_t begin = next_.fetch_add(grain_, std::memory_order_relaxed);
            if (begin >= count_) break;
            const size_t end = std::min(count_, begin + grain_);
            for (size_t i = begin; i < end; ++i) function_(context_, i);
        }
    }
public:
    JobPool() {
        for (unsigned i = 0; i < workerCount(); ++i) workers_.emplace_back([this, i] {
            size_t seen = 0;
            for (;;) {
                {
                    std::unique_lock<std::mutex> lock(mutex_);
                    wake_.wait(lock, [&] { return stop_ || generation_ != seen; });
                    if (stop_) return;
                    seen = generation_;
                }
#if defined(__APPLE__) && defined(RTS_POSIX_PORT)
                static const char* names[] = {"visual.0", "visual.1", "visual.2", "visual.3"};
                if (profile_) rts_bench::beginWorkerFrame(frame_, logic_, names[i]);
                { rts_bench::Scope scope(scope_, profile_); consume(); }
                if (profile_) rts_bench::endWorkerFrame();
#else
                consume();
#endif
                {
                    std::lock_guard<std::mutex> lock(mutex_);
                    if (--remaining_ == 0) done_.notify_one();
                }
            }
        });
    }
    ~JobPool() {
        { std::lock_guard<std::mutex> lock(mutex_); stop_ = true; }
        wake_.notify_all();
        for (auto& thread : workers_) thread.join();
    }
    template<class F> void run(size_t count, size_t grain, const char* scope, F& function) {
        {
            std::lock_guard<std::mutex> lock(mutex_);
            count_ = count; grain_ = grain; next_.store(0, std::memory_order_relaxed);
            context_ = &function;
            function_ = [](void* context, size_t i) { (*static_cast<F*>(context))(i); };
            remaining_ = workers_.size();
#if defined(__APPLE__) && defined(RTS_POSIX_PORT)
            profile_ = rts_bench::scopesEnabled(); frame_ = rts_bench::frame();
            logic_ = rts_bench::logicFrame(); scope_ = scope;
#endif
            ++generation_;
        }
        wake_.notify_all();
        consume(); // The caller helps, then joins before any input can change.
        std::unique_lock<std::mutex> lock(mutex_);
        done_.wait(lock, [&] { return remaining_ == 0; });
    }
};
template<class F> inline void parallelFor(size_t count, size_t grain, const char* scope, F function) {
    if (!workerCount() || count < grain * 2) {
        for (size_t i = 0; i < count; ++i) function(i);
        return;
    }
    static_assert(sizeof(F) > 0, "Callable required");
    // One pool across all call sites, not one pool per callable type.
    extern JobPool& pool();
    RTS_BENCH_COUNTER("visual.parallel_batches", 1);
    pool().run(count, grain, scope, function);
}
inline JobPool& pool() { static JobPool instance; return instance; }
} // namespace rts_visual

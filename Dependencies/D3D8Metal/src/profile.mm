#include "internal.h"
#include <cstdlib>

namespace d3d8metal {
struct GPUProfile {
    struct Pass { std::string name; bool render; };
    id<MTLCounterSampleBuffer> samples = nil;
    std::vector<Pass> passes;
    uint64_t frame = rts_bench::frame();
    uint32_t logic = rts_bench::logicFrame();
    MTLTimestamp cpu = 0, gpu = 0;
};

std::shared_ptr<GPUProfile> Device::newGPUProfile()
{
    if (!rts_bench::gpuEnabled() || !rts_bench::capturing()) return {};
    auto p = std::make_shared<GPUProfile>();
    static const unsigned every = [] { const char* e = getenv("GENERALS_PROFILE_GPU_EVERY"); return e ? (unsigned)std::max(1, atoi(e)) : (rts_bench::splitPasses() ? 1u : 30u); }();
    if (m_profileCounterSet && p->frame % every == 0) {
        MTLCounterSampleBufferDescriptor* desc = [MTLCounterSampleBufferDescriptor new];
        desc.counterSet = m_profileCounterSet;
        desc.storageMode = MTLStorageModeShared;
        desc.sampleCount = 2048; // 512 encoders; excess passes are explicitly counted.
        NSError* error = nil;
        p->samples = [m_mtlDevice newCounterSampleBufferWithDescriptor:desc error:&error];
        if (!p->samples) rts_bench::metadata("GPU counter allocation failed", error.localizedDescription.UTF8String ?: "unknown");
        [m_mtlDevice sampleTimestamps:&p->cpu gpuTimestamp:&p->gpu];
    }
    return p;
}

void Device::initializeProfiling()
{
    if (!rts_bench::enabled()) return;
    rts_bench::metadata("GPU", m_mtlDevice.name.UTF8String);
    rts_bench::metadata("presentation", getenv("D3D8METAL_BENCH_OFFSCREEN") && strcmp(getenv("D3D8METAL_BENCH_OFFSCREEN"), "0") != 0 ? "offscreen benchmark target" : "window drawable");
    rts_bench::metadata("render thread", m_threaded ? "enabled" : "inline");
    if (rts_bench::gpuEnabled() && [m_mtlDevice supportsCounterSampling:MTLCounterSamplingPointAtStageBoundary]) {
        for (id<MTLCounterSet> set in m_mtlDevice.counterSets)
            if ([set.name isEqualToString:MTLCommonCounterSetTimestamp]) m_profileCounterSet = set;
    }
    if (rts_bench::gpuEnabled())
        rts_bench::metadata("GPU pass timestamps", m_profileCounterSet ? "supported" : "unavailable (command buffer times only)");
    rts_bench::setHooks(this,
        [](void* context, uint64_t frame, uint32_t logic) {
            auto d = static_cast<Device*>(context);
            d->submit([d, frame, logic] { rts_bench::beginRenderFrame(frame, logic); });
        },
        [](void* context, const char* phase) {
            auto d = static_cast<Device*>(context);
            d->submit([d, phase] {
                if (rts_bench::splitPasses()) d->endRenderEncoder();
                else if (d->m_encoder && d->m_gpuProfile && !d->m_gpuProfile->passes.empty()) {
                    auto& label = d->m_gpuProfile->passes.back().name;
                    if (label.find(phase) == std::string::npos) label += std::string(" + ") + phase;
                }
                d->m_profilePhase = phase;
            });
        });
}

void Device::profileRenderPass(MTLRenderPassDescriptor* pass, const char* name)
{
    if (!rts_bench::enabled()) return;
    rts_bench::counter("render_encoders", 1);
    commandBuffer();
    auto p = m_gpuProfile;
    if (!p || !p->samples) return;
    if (p->passes.size() >= 512) { rts_bench::counter("gpu_pass_overflow", 1); return; }
    NSUInteger i = p->passes.size() * 4;
    p->passes.push_back({name, true});
    auto a = pass.sampleBufferAttachments[0];
    a.sampleBuffer = p->samples;
    a.startOfVertexSampleIndex = i;
    a.endOfVertexSampleIndex = i + 1;
    a.startOfFragmentSampleIndex = i + 2;
    a.endOfFragmentSampleIndex = i + 3;
}

id<MTLBlitCommandEncoder> Device::profileBlitEncoder(id<MTLCommandBuffer> cb, const char* name)
{
    if (!rts_bench::enabled()) return [cb blitCommandEncoder];
    rts_bench::counter("blit_encoders", 1);
    auto p = cb == m_uploadCommandBuffer ? m_uploadGPUProfile : m_gpuProfile;
    if (!p || !p->samples) return [cb blitCommandEncoder];
    if (p->passes.size() >= 512) { rts_bench::counter("gpu_pass_overflow", 1); return [cb blitCommandEncoder]; }
    NSUInteger i = p->passes.size() * 4;
    p->passes.push_back({name, false});
    MTLBlitPassDescriptor* desc = [MTLBlitPassDescriptor blitPassDescriptor];
    auto a = desc.sampleBufferAttachments[0];
    a.sampleBuffer = p->samples;
    a.startOfEncoderSampleIndex = i;
    a.endOfEncoderSampleIndex = i + 1;
    return [cb blitCommandEncoderWithDescriptor:desc];
}

void Device::completeGPUProfile(id<MTLCommandBuffer> cb, std::shared_ptr<GPUProfile> p, const char* name)
{
    if (!p) return;
    id<MTLDevice> device = m_mtlDevice; // Completion must not dereference a destroyed Device.
    [cb addCompletedHandler:^(id<MTLCommandBuffer> done) {
        struct CompletedTimings {
            uint64_t frame;
            uint32_t logic;
            std::vector<rts_bench::GPUTiming> rows;
            ~CompletedTimings() { rts_bench::gpuEvents(frame, logic, std::move(rows)); }
        } timings{p->frame, p->logic, {}};
        timings.rows.reserve(p->passes.size() + 1);
        if (done.status == MTLCommandBufferStatusError) {
            rts_bench::metadata("GPU command error", done.error.localizedDescription.UTF8String ?: "unknown");
            return;
        }
        if (done.GPUEndTime > done.GPUStartTime && done.GPUStartTime > 0)
            timings.rows.push_back({name, done.GPUStartTime * 1e6, (done.GPUEndTime - done.GPUStartTime) * 1e6});
        else if (!p->passes.empty()) rts_bench::metadata("GPU timing unavailable", name);
        if (!p->samples || p->passes.empty()) return;
        MTLTimestamp cpu = 0, gpu = 0;
        [device sampleTimestamps:&cpu gpuTimestamp:&gpu];
        if (cpu <= p->cpu || gpu <= p->gpu) { rts_bench::metadata("GPU calibration failed", name); return; }
        // sampleTimestamps returns CPU nanoseconds, unlike mach_absolute_time ticks.
        // https://developer.apple.com/documentation/metal/converting-gpu-timestamps-into-cpu-time
        constexpr double hostScale = 1.0 / 1000.0;
        double scale = double(cpu - p->cpu) * hostScale / double(gpu - p->gpu);
        NSData* data = [p->samples resolveCounterRange:NSMakeRange(0, p->passes.size() * 4)];
        if (!data || data.length < p->passes.size() * 4 * sizeof(MTLCounterResultTimestamp)) {
            rts_bench::metadata("GPU resolve failed", name); return;
        }
        auto samples = static_cast<const MTLCounterResultTimestamp*>(data.bytes);
        for (size_t i = 0; i < p->passes.size(); ++i) {
            auto pass = p->passes[i];
            uint64_t a = samples[i * 4].timestamp, b = samples[i * 4 + 1].timestamp;
            if (!a || a == MTLCounterErrorValue || b == MTLCounterErrorValue || b < a) { rts_bench::metadata("GPU invalid sample", pass.name.c_str()); continue; }
            if (pass.render) {
                uint64_t c = samples[i * 4 + 2].timestamp, d = samples[i * 4 + 3].timestamp;
                if (c == MTLCounterErrorValue || d == MTLCounterErrorValue || !c || d < c) { rts_bench::metadata("GPU invalid sample", pass.name.c_str()); continue; }
                a = std::min(a, c); b = std::max(b, d);
            }
            if (!a || a == MTLCounterErrorValue || b == MTLCounterErrorValue || b < a) { rts_bench::metadata("GPU invalid sample", pass.name.c_str()); continue; }
            double start = p->cpu * hostScale + (double(a) - double(p->gpu)) * scale;
            double duration = (b - a) * scale;
            // Catch clock-domain/unit mistakes rather than publishing impossible timings.
            if (done.GPUStartTime > 0 && (start < done.GPUStartTime * 1e6 - 100 || start + duration > done.GPUEndTime * 1e6 + 100)) {
                rts_bench::metadata("GPU clock validation failed", pass.name.c_str()); continue;
            }
            timings.rows.push_back({std::string("pass: ") + pass.name, start, duration});
        }
    }];
}
}

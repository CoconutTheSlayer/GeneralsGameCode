/*
**	Command & Conquer Generals Zero Hour(tm)
**	Copyright 2026 TheSuperHackers
**
**	This program is free software: you can redistribute it and/or modify
**	it under the terms of the GNU General Public License as published by
**	the Free Software Foundation, either version 3 of the License, or
**	(at your option) any later version.
**
**	This program is distributed in the hope that it will be useful,
**	but WITHOUT ANY WARRANTY; without even the implied warranty of
**	MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
**	GNU General Public License for more details.
**
**	You should have received a copy of the GNU General Public License
**	along with this program.  If not, see <http://www.gnu.org/licenses/>.
*/

// IDirect3DDevice8: device setup, presentation, resources and state.
// Drawing is implemented in draw.mm.

#define STB_IMAGE_WRITE_IMPLEMENTATION
#define STB_IMAGE_WRITE_STATIC
#include <stb_image_write.h>
#include "internal.h"
#include "shadertrans.h"

#include <win32shim.h>

#include <SDL3/SDL.h>
#include <SDL3/SDL_metal.h>

#include <cmath>
#include <functional>

namespace d3d8metal
{

static Device* g_currentDevice = nullptr;

Device* CurrentDevice()
{
	return g_currentDevice;
}

namespace
{
inline DWORD floatBits(float f)
{
	DWORD d;
	memcpy(&d, &f, 4);
	return d;
}

const char* kUtilityShaders = R"MSL(
#include <metal_stdlib>
using namespace metal;

struct PresentOut { float4 position [[position]]; float2 uv; };

vertex PresentOut present_vs(uint vid [[vertex_id]])
{
	float2 p = float2((vid << 1) & 2, vid & 2);
	PresentOut o;
	o.position = float4(p * float2(2.0, -2.0) + float2(-1.0, 1.0), 0.0, 1.0);
	o.uv = p;
	return o;
}

fragment float4 present_fs(PresentOut in [[stage_in]], texture2d<float> image [[texture(0)]], texture2d<float> gamma [[texture(1)]], sampler s [[sampler(0)]])
{
	constexpr sampler g(filter::linear, address::clamp_to_edge);
	float4 c = image.sample(s, in.uv);
	float3 corrected;
	corrected.r = gamma.sample(g, float2(c.r * (255.0 / 256.0) + 0.5 / 256.0, 0.5)).r;
	corrected.g = gamma.sample(g, float2(c.g * (255.0 / 256.0) + 0.5 / 256.0, 0.5)).g;
	corrected.b = gamma.sample(g, float2(c.b * (255.0 / 256.0) + 0.5 / 256.0, 0.5)).b;
	return float4(corrected, 1.0);
}

struct ClearUniforms { float4 color; float4 depth; };

vertex float4 clear_vs(uint vid [[vertex_id]], constant ClearUniforms& u [[buffer(0)]])
{
	float2 p = float2((vid << 1) & 2, vid & 2);
	return float4(p * float2(2.0, -2.0) + float2(-1.0, 1.0), u.depth.x, 1.0);
}

fragment float4 clear_fs(constant ClearUniforms& u [[buffer(0)]])
{
	return u.color;
}
)MSL";
} // namespace

Device::Device(Direct3D* d3d, HWND window, DWORD behaviorFlags, D3DPRESENT_PARAMETERS* params)
	: m_d3d(d3d), m_window(window), m_behaviorFlags(behaviorFlags), m_params(*params)
{
	m_d3d->AddRef();
	m_mtlDevice = d3d->m_mtlDevice;
	m_native16 = [m_mtlDevice supportsFamily:MTLGPUFamilyApple1];
	// Antialias the back buffer. D3D8METAL_MSAA sets the samples per pixel (1 turns it off).
	{
		const char* env = getenv("D3D8METAL_MSAA");
		unsigned samples = env ? (unsigned)std::max(1, atoi(env)) : 4;
		while (samples > 1 && ![m_mtlDevice supportsTextureSampleCount:samples])
			samples /= 2;
		m_msaaSamples = std::max(1u, samples);
		const char* aniso = getenv("D3D8METAL_ANISOTROPY");
		m_filterUpgrade = (unsigned)std::clamp(aniso ? atoi(aniso) : 16, 1, 16);
	}
	m_frameSemaphore = dispatch_semaphore_create(3);
	for (int i = 0; i < 256; ++i)
	{
		WORD v = (WORD)(i * 257);
		m_gammaRamp.red[i] = m_gammaRamp.green[i] = m_gammaRamp.blue[i] = v;
	}
	m_execGammaRamp = m_gammaRamp;
}

Device::~Device()
{
	stopWorker();
	if (m_commandBuffer)
	{
		execFlush(m_currentSerial, true);
		afterFlush();
	}
	for (int i = 0; i < MAX_STAGES; ++i)
	{
		if (m_front.textures[i])
			m_front.textures[i]->Release();
		if (m_state.textures[i])
			m_state.textures[i]->Release();
	}
	if (m_frontRenderTarget)
		m_frontRenderTarget->Release();
	if (m_frontDepthStencil)
		m_frontDepthStencil->Release();
	if (m_backBuffer)
		m_backBuffer->Release();
	if (m_depthBuffer)
		m_depthBuffer->Release();
	if (m_renderTarget)
		m_renderTarget->Release();
	if (m_depthStencil)
		m_depthStencil->Release();
	if (m_metalView)
		SDL_Metal_DestroyView((SDL_MetalView)m_metalView);
	if (m_pipelineCacheFile)
		fclose(m_pipelineCacheFile);
	if (g_currentDevice == this)
		g_currentDevice = nullptr;
	m_d3d->Release();
}

bool Device::initialize()
{
	m_sdlWindow = Win32Shim_GetSDLWindow(m_window);
	if (m_sdlWindow == nullptr)
	{
		fprintf(stderr, "d3d8metal: no window for device\n");
		return false;
	}
	m_metalView = SDL_Metal_CreateView(m_sdlWindow);
	if (m_metalView == nullptr)
	{
		fprintf(stderr, "d3d8metal: SDL_Metal_CreateView failed: %s\n", SDL_GetError());
		return false;
	}
	m_layer = (__bridge CAMetalLayer*)SDL_Metal_GetLayer((SDL_MetalView)m_metalView);
	m_layer.device = m_mtlDevice;
	m_layer.pixelFormat = MTLPixelFormatBGRA8Unorm;
	m_layer.framebufferOnly = YES;
	m_layer.maximumDrawableCount = 3;

	m_queue = [m_mtlDevice newCommandQueue];

	NSError* error = nil;
	id<MTLLibrary> library = [m_mtlDevice newLibraryWithSource:[NSString stringWithUTF8String:kUtilityShaders] options:nil error:&error];
	if (library == nil)
	{
		fprintf(stderr, "d3d8metal: utility shader compile failed: %s\n", [[error localizedDescription] UTF8String]);
		return false;
	}

	MTLRenderPipelineDescriptor* desc = [MTLRenderPipelineDescriptor new];
	desc.vertexFunction = [library newFunctionWithName:@"present_vs"];
	desc.fragmentFunction = [library newFunctionWithName:@"present_fs"];
	desc.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
	m_presentPipeline = [m_mtlDevice newRenderPipelineStateWithDescriptor:desc error:&error];

	// Clear pipelines: index bit 0 = color write, bit 1 = has depth attachment, bit 2 = multisampled.
	for (int i = 0; i < 8; ++i)
	{
		MTLRenderPipelineDescriptor* cd = [MTLRenderPipelineDescriptor new];
		cd.vertexFunction = [library newFunctionWithName:@"clear_vs"];
		cd.fragmentFunction = [library newFunctionWithName:@"clear_fs"];
		cd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
		cd.colorAttachments[0].writeMask = (i & 1) ? MTLColorWriteMaskAll : MTLColorWriteMaskNone;
		if (i & 2)
		{
			cd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float_Stencil8;
			cd.stencilAttachmentPixelFormat = MTLPixelFormatDepth32Float_Stencil8;
		}
		if (i & 4)
			cd.rasterSampleCount = m_msaaSamples;
		m_clearPipelines[i] = [m_mtlDevice newRenderPipelineStateWithDescriptor:cd error:&error];
	}
	// Clear depth states: bit 0 = write depth, bit 1 = write stencil.
	for (int i = 0; i < 4; ++i)
	{
		MTLDepthStencilDescriptor* dd = [MTLDepthStencilDescriptor new];
		dd.depthCompareFunction = MTLCompareFunctionAlways;
		dd.depthWriteEnabled = (i & 1) != 0;
		if (i & 2)
		{
			MTLStencilDescriptor* sd = [MTLStencilDescriptor new];
			sd.stencilCompareFunction = MTLCompareFunctionAlways;
			sd.depthStencilPassOperation = MTLStencilOperationReplace;
			sd.stencilFailureOperation = MTLStencilOperationReplace;
			sd.depthFailureOperation = MTLStencilOperationReplace;
			sd.writeMask = 0xFF;
			dd.frontFaceStencil = sd;
			dd.backFaceStencil = sd;
		}
		m_clearDepthStates[i] = [m_mtlDevice newDepthStencilStateWithDescriptor:dd];
	}

	// 1x1 white textures used for stages without a texture.
	{
		MTLTextureDescriptor* td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm width:1 height:1 mipmapped:NO];
		td.storageMode = MTLStorageModeShared;
		m_whiteTexture = [m_mtlDevice newTextureWithDescriptor:td];
		uint32_t white = 0xFFFFFFFF;
		[m_whiteTexture replaceRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:0 withBytes:&white bytesPerRow:4];
		MTLTextureDescriptor* cd = [MTLTextureDescriptor textureCubeDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm size:1 mipmapped:NO];
		cd.storageMode = MTLStorageModeShared;
		m_whiteCube = [m_mtlDevice newTextureWithDescriptor:cd];
		for (int f = 0; f < 6; ++f)
			[m_whiteCube replaceRegion:MTLRegionMake2D(0, 0, 1, 1) mipmapLevel:0 slice:(NSUInteger)f withBytes:&white bytesPerRow:4 bytesPerImage:4];
	}

	MTLSamplerDescriptor* sd = [MTLSamplerDescriptor new];
	sd.minFilter = MTLSamplerMinMagFilterLinear;
	sd.magFilter = MTLSamplerMinMagFilterLinear;
	sd.sAddressMode = MTLSamplerAddressModeClampToEdge;
	sd.tAddressMode = MTLSamplerAddressModeClampToEdge;
	m_presentSampler = [m_mtlDevice newSamplerStateWithDescriptor:sd];

	if (!createSwapChainResources())
		return false;
	fprintf(stderr, "d3d8metal: %s, %ux%u %s\n", [[m_mtlDevice name] UTF8String], m_params.BackBufferWidth, m_params.BackBufferHeight,
		m_params.Windowed ? "windowed" : "fullscreen");
	resetState();
	loadPipelineCache();
	g_currentDevice = this;
	// Encode on a render thread unless D3D8METAL_THREADED=0.
	{
		const char* env = getenv("D3D8METAL_THREADED");
		m_threaded = env == nullptr || atoi(env) != 0;
		if (m_threaded)
			m_worker = std::thread([this] { workerMain(); });
		fprintf(stderr, "d3d8metal: render thread %s\n", m_threaded ? "on" : "off");
	}
	return true;
}

namespace
{
id<MTLTexture> createGammaTexture(id<MTLDevice> device, const D3DGAMMARAMP& ramp)
{
	MTLTextureDescriptor* td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatRGBA8Unorm width:256 height:1 mipmapped:NO];
	td.storageMode = MTLStorageModeShared;
	id<MTLTexture> tex = [device newTextureWithDescriptor:td];
	uint8_t data[256 * 4];
	for (int i = 0; i < 256; ++i)
	{
		data[i * 4 + 0] = (uint8_t)(ramp.red[i] >> 8);
		data[i * 4 + 1] = (uint8_t)(ramp.green[i] >> 8);
		data[i * 4 + 2] = (uint8_t)(ramp.blue[i] >> 8);
		data[i * 4 + 3] = 255;
	}
	[tex replaceRegion:MTLRegionMake2D(0, 0, 256, 1) mipmapLevel:0 withBytes:data bytesPerRow:256 * 4];
	return tex;
}

id<MTLTexture> g_gammaTexture = nil;
} // namespace

void Device::applyPresentationParameters()
{
	if (m_params.BackBufferWidth == 0 || m_params.BackBufferHeight == 0)
	{
		RECT r;
		GetClientRect(m_window, &r);
		m_params.BackBufferWidth = (UINT)std::max(1, (int)(r.right - r.left));
		m_params.BackBufferHeight = (UINT)std::max(1, (int)(r.bottom - r.top));
	}
	if (m_params.BackBufferFormat == D3DFMT_UNKNOWN)
		m_params.BackBufferFormat = D3DFMT_X8R8G8B8;

	Win32Shim_SetLogicalSize(m_window, (int)m_params.BackBufferWidth, (int)m_params.BackBufferHeight);
	if (m_params.Windowed)
	{
		SDL_SetWindowFullscreen(m_sdlWindow, false);
		SDL_SetWindowSize(m_sdlWindow, (int)m_params.BackBufferWidth, (int)m_params.BackBufferHeight);
	}
	else
		SDL_SetWindowFullscreen(m_sdlWindow, true);
	SDL_SyncWindow(m_sdlWindow);

	UINT interval = m_params.FullScreen_PresentationInterval;
	m_layer.displaySyncEnabled = !(interval == D3DPRESENT_INTERVAL_IMMEDIATE && !m_params.Windowed);
}

bool Device::createSwapChainResources()
{
	applyPresentationParameters();

	auto backStorage = createStorage(m_params.BackBufferWidth, m_params.BackBufferHeight, 1, 1, D3DUSAGE_RENDERTARGET, m_params.BackBufferFormat, D3DPOOL_DEFAULT);
	if (backStorage == nullptr)
		return false;
	if (m_msaaSamples > 1)
	{
		MTLTextureDescriptor* td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatBGRA8Unorm
			width:m_params.BackBufferWidth height:m_params.BackBufferHeight mipmapped:NO];
		td.textureType = MTLTextureType2DMultisample;
		td.sampleCount = m_msaaSamples;
		td.usage = MTLTextureUsageRenderTarget;
		td.storageMode = MTLStorageModePrivate;
		backStorage->msaaTexture = [m_mtlDevice newTextureWithDescriptor:td];
		td.pixelFormat = MTLPixelFormatDepth32Float_Stencil8;
		m_msaaDepth = m_params.EnableAutoDepthStencil ? [m_mtlDevice newTextureWithDescriptor:td] : nil;
	}
	Surface* back = new Surface(this, backStorage);
	if (m_backBuffer)
		m_backBuffer->Release();
	m_backBuffer = back;

	if (m_depthBuffer)
	{
		m_depthBuffer->Release();
		m_depthBuffer = nullptr;
	}
	if (m_params.EnableAutoDepthStencil)
	{
		auto depthStorage = createStorage(m_params.BackBufferWidth, m_params.BackBufferHeight, 1, 1, D3DUSAGE_DEPTHSTENCIL, m_params.AutoDepthStencilFormat, D3DPOOL_DEFAULT);
		m_depthBuffer = new Surface(this, depthStorage);
	}

	endRenderEncoder();
	if (m_renderTarget)
		m_renderTarget->Release();
	m_renderTarget = m_backBuffer;
	m_renderTarget->AddRef();
	if (m_depthStencil)
		m_depthStencil->Release();
	m_depthStencil = m_depthBuffer;
	if (m_depthStencil)
		m_depthStencil->AddRef();
	m_pendingClearFlags = 0;

	if (m_frontRenderTarget)
		m_frontRenderTarget->Release();
	m_frontRenderTarget = m_backBuffer;
	m_frontRenderTarget->AddRef();
	if (m_frontDepthStencil)
		m_frontDepthStencil->Release();
	m_frontDepthStencil = m_depthBuffer;
	if (m_frontDepthStencil)
		m_frontDepthStencil->AddRef();
	return true;
}

void Device::resetState()
{
	++m_vsConstantsVersion;
	++m_psConstantsVersion;
	resetDeviceState(m_state);
	// The game thread's copy starts out the same, with its own texture references (none).
	for (int i = 0; i < MAX_STAGES; ++i)
	{
		if (m_front.textures[i])
			m_front.textures[i]->Release();
	}
	for (int i = 0; i < MAX_STREAMS; ++i)
	{
		if (m_front.streams[i].buffer)
			m_front.streams[i].buffer->Release();
	}
	if (m_front.indices)
		m_front.indices->Release();
	resetDeviceState(m_front);
	m_dirtyRenderStates.clear();
	m_dirtyStageStates.clear();
	m_dirtyTransforms.clear();
	memset(m_renderStateDirty, 0, sizeof(m_renderStateDirty));
	memset(m_stageStateDirty, 0, sizeof(m_stageStateDirty));
	memset(m_transformDirty, 0, sizeof(m_transformDirty));
	m_dirtyMisc = 0;
	m_vsDirtyLo = 96;
	m_vsDirtyHi = 0;
	m_psDirtyLo = 8;
	m_psDirtyHi = 0;
}

void Device::resetDeviceState(DeviceState& s)
{
	memset(s.renderStates, 0, sizeof(s.renderStates));
	DWORD* rs = s.renderStates;
	rs[D3DRS_ZENABLE] = m_params.EnableAutoDepthStencil ? D3DZB_TRUE : D3DZB_FALSE;
	rs[D3DRS_FILLMODE] = D3DFILL_SOLID;
	rs[D3DRS_SHADEMODE] = D3DSHADE_GOURAUD;
	rs[D3DRS_ZWRITEENABLE] = TRUE;
	rs[D3DRS_ALPHATESTENABLE] = FALSE;
	rs[D3DRS_LASTPIXEL] = TRUE;
	rs[D3DRS_SRCBLEND] = D3DBLEND_ONE;
	rs[D3DRS_DESTBLEND] = D3DBLEND_ZERO;
	rs[D3DRS_CULLMODE] = D3DCULL_CCW;
	rs[D3DRS_ZFUNC] = D3DCMP_LESSEQUAL;
	rs[D3DRS_ALPHAREF] = 0;
	rs[D3DRS_ALPHAFUNC] = D3DCMP_ALWAYS;
	rs[D3DRS_FOGSTART] = floatBits(0.0f);
	rs[D3DRS_FOGEND] = floatBits(1.0f);
	rs[D3DRS_FOGDENSITY] = floatBits(1.0f);
	rs[D3DRS_STENCILFAIL] = D3DSTENCILOP_KEEP;
	rs[D3DRS_STENCILZFAIL] = D3DSTENCILOP_KEEP;
	rs[D3DRS_STENCILPASS] = D3DSTENCILOP_KEEP;
	rs[D3DRS_STENCILFUNC] = D3DCMP_ALWAYS;
	rs[D3DRS_STENCILMASK] = 0xFFFFFFFF;
	rs[D3DRS_STENCILWRITEMASK] = 0xFFFFFFFF;
	rs[D3DRS_TEXTUREFACTOR] = 0xFFFFFFFF;
	rs[D3DRS_CLIPPING] = TRUE;
	rs[D3DRS_LIGHTING] = TRUE;
	rs[D3DRS_COLORVERTEX] = TRUE;
	rs[D3DRS_LOCALVIEWER] = TRUE;
	rs[D3DRS_DIFFUSEMATERIALSOURCE] = D3DMCS_COLOR1;
	rs[D3DRS_SPECULARMATERIALSOURCE] = D3DMCS_COLOR2;
	rs[D3DRS_AMBIENTMATERIALSOURCE] = D3DMCS_MATERIAL;
	rs[D3DRS_EMISSIVEMATERIALSOURCE] = D3DMCS_MATERIAL;
	rs[D3DRS_POINTSIZE] = floatBits(1.0f);
	rs[D3DRS_POINTSIZE_MIN] = floatBits(0.0f);
	rs[D3DRS_POINTSIZE_MAX] = floatBits(64.0f);
	rs[D3DRS_POINTSCALE_A] = floatBits(1.0f);
	rs[D3DRS_MULTISAMPLEANTIALIAS] = TRUE;
	rs[D3DRS_MULTISAMPLEMASK] = 0xFFFFFFFF;
	rs[D3DRS_COLORWRITEENABLE] = 0xF;
	rs[D3DRS_BLENDOP] = D3DBLENDOP_ADD;

	for (int i = 0; i < MAX_STAGES; ++i)
	{
		DWORD* ts = s.stageStates[i];
		memset(ts, 0, sizeof(s.stageStates[i]));
		ts[D3DTSS_COLOROP] = i == 0 ? D3DTOP_MODULATE : D3DTOP_DISABLE;
		ts[D3DTSS_COLORARG1] = D3DTA_TEXTURE;
		ts[D3DTSS_COLORARG2] = D3DTA_CURRENT;
		ts[D3DTSS_ALPHAOP] = i == 0 ? D3DTOP_SELECTARG1 : D3DTOP_DISABLE;
		ts[D3DTSS_ALPHAARG1] = D3DTA_TEXTURE;
		ts[D3DTSS_ALPHAARG2] = D3DTA_CURRENT;
		ts[D3DTSS_TEXCOORDINDEX] = (DWORD)i;
		ts[D3DTSS_ADDRESSU] = D3DTADDRESS_WRAP;
		ts[D3DTSS_ADDRESSV] = D3DTADDRESS_WRAP;
		ts[D3DTSS_ADDRESSW] = D3DTADDRESS_WRAP;
		ts[D3DTSS_MAGFILTER] = D3DTEXF_POINT;
		ts[D3DTSS_MINFILTER] = D3DTEXF_POINT;
		ts[D3DTSS_MIPFILTER] = D3DTEXF_NONE;
		ts[D3DTSS_MAXANISOTROPY] = 1;
		ts[D3DTSS_TEXTURETRANSFORMFLAGS] = D3DTTFF_DISABLE;
		ts[D3DTSS_COLORARG0] = D3DTA_CURRENT;
		ts[D3DTSS_ALPHAARG0] = D3DTA_CURRENT;
		ts[D3DTSS_RESULTARG] = D3DTA_CURRENT;
	}

	for (int i = 0; i < 512; ++i)
	{
		memset(&s.transforms[i], 0, sizeof(D3DMATRIX));
		s.transforms[i]._11 = s.transforms[i]._22 = s.transforms[i]._33 = s.transforms[i]._44 = 1.0f;
	}
	s.viewport.X = 0;
	s.viewport.Y = 0;
	s.viewport.Width = m_params.BackBufferWidth;
	s.viewport.Height = m_params.BackBufferHeight;
	s.viewport.MinZ = 0.0f;
	s.viewport.MaxZ = 1.0f;
	memset(&s.material, 0, sizeof(s.material));
	for (int i = 0; i < MAX_LIGHTS; ++i)
	{
		memset(&s.lights[i], 0, sizeof(D3DLIGHT8));
		s.lights[i].Type = D3DLIGHT_DIRECTIONAL;
		s.lights[i].Diffuse.r = s.lights[i].Diffuse.g = s.lights[i].Diffuse.b = 1.0f;
		s.lights[i].Direction.z = 1.0f;
		s.lightEnabled[i] = false;
	}
	for (int i = 0; i < MAX_STAGES; ++i)
		s.textures[i] = nullptr;
	for (int i = 0; i < MAX_STREAMS; ++i)
		s.streams[i] = StreamSource();
	s.indices = nullptr;
	s.baseVertexIndex = 0;
	s.vertexShader = 0;
	s.pixelShader = 0;
}

//-----------------------------------------------------------------------------
// Command submission
//-----------------------------------------------------------------------------
id<MTLCommandBuffer> Device::commandBuffer()
{
	if (m_commandBuffer == nil)
	{
		m_commandBuffer = [m_queue commandBuffer];
	}
	return m_commandBuffer;
}

id<MTLBlitCommandEncoder> Device::uploadEncoder()
{
	if (m_uploadCommandBuffer == nil)
	{
		commandBuffer(); // the upload shares the serial of the command buffer it precedes
		m_uploadCommandBuffer = [m_queue commandBuffer];
		// Take the queue position ahead of the command buffer being recorded, which is
		// enqueued when it is committed.
		[m_uploadCommandBuffer enqueue];
	}
	if (m_uploadBlit == nil)
		m_uploadBlit = [m_uploadCommandBuffer blitCommandEncoder];
	return m_uploadBlit;
}

void Device::endRenderEncoder()
{
	if (m_encoder)
	{
		[m_encoder endEncoding];
		m_encoder = nil;
	}
}

// Commits the command buffer with the given serial. The game thread accounts for it with
// afterFlush(), so serials only ever change there.
void Device::execFlush(uint64_t serial, bool wait)
{
	endRenderEncoder();
	if (m_commandBuffer == nil)
		commandBuffer(); // an empty one still completes the serial
	// A serial completes when its command buffer and the uploads ahead of it have.
	std::atomic<uint64_t>* completed = &m_completedSerial;
	std::atomic<int>* pending = new std::atomic<int>(m_uploadCommandBuffer ? 2 : 1);
	void (^done)(id<MTLCommandBuffer>) = ^(id<MTLCommandBuffer>) {
		if (pending->fetch_sub(1) != 1)
			return;
		delete pending;
		uint64_t current = completed->load();
		while (current < serial && !completed->compare_exchange_weak(current, serial))
		{
		}
	};
	if (m_uploadCommandBuffer)
	{
		if (m_uploadBlit)
		{
			[m_uploadBlit endEncoding];
			m_uploadBlit = nil;
		}
		[m_uploadCommandBuffer addCompletedHandler:done];
		[m_uploadCommandBuffer commit];
		m_uploadCommandBuffer = nil;
	}
	[m_commandBuffer addCompletedHandler:done];
	[m_commandBuffer commit];
	if (wait)
		[m_commandBuffer waitUntilCompleted];
	m_commandBuffer = nil;
}

Device::Transient Device::allocTransient(NSUInteger length, NSUInteger alignment)
{
	// Game thread only: the render thread only reads the buffers it is given.
	const NSUInteger kChunk = 4 * 1024 * 1024;
	NSUInteger offset = (m_transientOffset + alignment - 1) & ~(alignment - 1);
	if (m_transientCurrent == nil || offset + length > [m_transientCurrent length])
	{
		if (m_transientCurrent)
			m_retiredTransient.push_back({ m_currentSerial, m_transientCurrent });
		m_transientCurrent = nil;
		NSUInteger size = std::max(kChunk, length);
		for (size_t i = 0; i < m_transientBuffers.size(); ++i)
		{
			if ([m_transientBuffers[i] length] >= size)
			{
				m_transientCurrent = m_transientBuffers[i];
				m_transientBuffers.erase(m_transientBuffers.begin() + (long)i);
				break;
			}
		}
		if (m_transientCurrent == nil)
			m_transientCurrent = [m_mtlDevice newBufferWithLength:size options:MTLResourceStorageModeShared];
		offset = 0;
	}
	Transient t;
	t.buffer = m_transientCurrent;
	t.offset = offset;
	t.cpu = (uint8_t*)[m_transientCurrent contents] + offset;
	m_transientOffset = offset + length;
	return t;
}

namespace
{
// Buffer lengths are rounded so buffers of similar sizes can be reused for each other.
NSUInteger bufferBucket(NSUInteger length)
{
	return (std::max<NSUInteger>(length, 16) + 255) & ~(NSUInteger)255;
}
// Upper bound for the memory kept in idle buffers.
const NSUInteger kMaxFreeBufferBytes = 128u * 1024u * 1024u;
} // namespace

id<MTLBuffer> Device::acquireBuffer(unsigned length)
{
	NSUInteger size = bufferBucket(length);
	auto it = m_freeBuffers.find(size);
	if (it != m_freeBuffers.end() && !it->second.empty())
	{
		id<MTLBuffer> buffer = it->second.back();
		it->second.pop_back();
		m_freeBufferBytes -= size;
		return buffer;
	}
	return [m_mtlDevice newBufferWithLength:size options:MTLResourceStorageModeShared];
}

void Device::releaseBuffer(id<MTLBuffer> buffer)
{
	NSUInteger size = [buffer length];
	if (m_freeBufferBytes + size > kMaxFreeBufferBytes)
		return;
	m_freeBuffers[size].push_back(buffer);
	m_freeBufferBytes += size;
}

void Device::retireBuffer(id<MTLBuffer> buffer, uint64_t serial)
{
	if (buffer == nil)
		return;
	// Keep the buffer away from reuse until the GPU no longer references it.
	if (serial != 0)
		m_retiredBuffers.push_back({ serial, buffer });
	else
		releaseBuffer(buffer);
}

//-----------------------------------------------------------------------------
// Textures
//-----------------------------------------------------------------------------
std::shared_ptr<TextureStorage> Device::createStorage(unsigned width, unsigned height, unsigned levels, unsigned faces, DWORD usage, D3DFORMAT format, D3DPOOL pool)
{
	if (width == 0 || height == 0)
		return nullptr;
	unsigned maxLevels = 1;
	while ((std::max(width, height) >> maxLevels) > 0)
		++maxLevels;
	if (levels == 0 || levels > maxLevels)
		levels = maxLevels;

	auto storage = std::make_shared<TextureStorage>();
	storage->format = format;
	storage->width = width;
	storage->height = height;
	storage->levels = levels;
	storage->faces = faces;
	storage->usage = usage;
	storage->pool = pool;
	storage->renderTarget = (usage & D3DUSAGE_RENDERTARGET) != 0;
	storage->depthStencil = (usage & D3DUSAGE_DEPTHSTENCIL) != 0 || IsDepthFormat(format);

	if (pool == D3DPOOL_SYSTEMMEM || pool == D3DPOOL_SCRATCH)
		return storage; // CPU only

	storage->gpuFormat = GpuFormatFor(format, m_native16 && !storage->renderTarget && !storage->depthStencil);
	MTLPixelFormat pf;
	bool opaque16 = format == D3DFMT_X1R5G5B5 || format == D3DFMT_X4R4G4B4;
	switch (storage->gpuFormat)
	{
	case GpuFormat::B5G6R5: pf = MTLPixelFormatB5G6R5Unorm; break;
	case GpuFormat::BGR5A1: pf = MTLPixelFormatBGR5A1Unorm; break;
	case GpuFormat::ABGR4: pf = MTLPixelFormatABGR4Unorm; break;
	case GpuFormat::BC1: pf = MTLPixelFormatBC1_RGBA; break;
	case GpuFormat::BC2: pf = MTLPixelFormatBC2_RGBA; break;
	case GpuFormat::BC3: pf = MTLPixelFormatBC3_RGBA; break;
	case GpuFormat::Depth32Stencil8: pf = MTLPixelFormatDepth32Float_Stencil8; break;
	default: pf = MTLPixelFormatBGRA8Unorm; break;
	}

	MTLTextureDescriptor* td = [MTLTextureDescriptor new];
	td.textureType = faces == 6 ? MTLTextureTypeCube : MTLTextureType2D;
	td.pixelFormat = pf;
	td.width = width;
	td.height = faces == 6 ? width : height;
	td.mipmapLevelCount = levels;
	td.usage = MTLTextureUsageShaderRead;
	td.storageMode = MTLStorageModePrivate;
	if (storage->renderTarget || storage->depthStencil)
		td.usage |= MTLTextureUsageRenderTarget;
	if (storage->gpuFormat == GpuFormat::ABGR4)
	{
		// ABGR4 samples the nibbles of A4R4G4B4 (A R G B from high to low) as R G B A.
		td.swizzle = MTLTextureSwizzleChannelsMake(MTLTextureSwizzleGreen, MTLTextureSwizzleBlue, MTLTextureSwizzleAlpha,
			opaque16 ? MTLTextureSwizzleOne : MTLTextureSwizzleRed);
	}
	else if (opaque16)
		td.swizzle = MTLTextureSwizzleChannelsMake(MTLTextureSwizzleRed, MTLTextureSwizzleGreen, MTLTextureSwizzleBlue, MTLTextureSwizzleOne);
	storage->texture = [m_mtlDevice newTextureWithDescriptor:td];
	if (storage->texture == nil)
		return nullptr;
	return storage;
}

void Device::markTextureUsed(TextureStorage& storage)
{
	storage.lastUsedSerial = m_currentSerial;
}

void Device::uploadTexture(TextureStorage& storage, unsigned face, unsigned level, const RECT& rectIn)
{
	if (storage.texture == nil)
		return;
	unsigned w = storage.levelWidth(level);
	unsigned h = storage.levelHeight(level);
	RECT rect = rectIn;
	rect.left = std::max<LONG>(0, rect.left);
	rect.top = std::max<LONG>(0, rect.top);
	rect.right = std::min<LONG>((LONG)w, rect.right);
	rect.bottom = std::min<LONG>((LONG)h, rect.bottom);
	if (rect.right <= rect.left || rect.bottom <= rect.top)
		return;

	std::vector<uint8_t>& shadow = storage.shadow(face, level);
	unsigned srcPitch = RowPitch(storage.format, w);
	bool compressed = IsCompressedFormat(storage.format);
	bool native16 = storage.gpuFormat == GpuFormat::B5G6R5 || storage.gpuFormat == GpuFormat::BGR5A1 || storage.gpuFormat == GpuFormat::ABGR4;
	if (compressed)
	{
		// Block align the region.
		rect.left &= ~3;
		rect.top &= ~3;
		rect.right = std::min<LONG>((LONG)w, (rect.right + 3) & ~3);
		rect.bottom = std::min<LONG>((LONG)h, (rect.bottom + 3) & ~3);
	}
	unsigned rw = (unsigned)(rect.right - rect.left);
	unsigned rh = (unsigned)(rect.bottom - rect.top);

	unsigned dstPitch;
	unsigned dstRows;
	if (compressed)
	{
		dstPitch = RowPitch(storage.format, rw);
		dstRows = RowCount(storage.format, rh);
	}
	else
	{
		dstPitch = rw * (native16 ? 2 : 4);
		dstRows = rh;
	}

	// A texture the command buffer being recorded has used must be updated in order with
	// its draws, which ends the current render pass. Other textures are updated by the
	// upload command buffer that runs ahead of it.
	bool inOrder = storage.lastUsedSerial == m_currentSerial;
	Transient staging = allocTransient((NSUInteger)dstPitch * dstRows, 16);
	if (native16)
	{
		const uint8_t* src = shadow.data() + (size_t)rect.top * srcPitch + (size_t)rect.left * 2;
		for (unsigned row = 0; row < rh; ++row)
			memcpy((uint8_t*)staging.cpu + (size_t)row * dstPitch, src + (size_t)row * srcPitch, dstPitch);
	}
	else if (compressed)
	{
		unsigned blockBytes = storage.format == D3DFMT_DXT1 ? 8 : 16;
		for (unsigned row = 0; row < dstRows; ++row)
		{
			const uint8_t* src = shadow.data() + (size_t)(rect.top / 4 + row) * srcPitch + (size_t)(rect.left / 4) * blockBytes;
			memcpy((uint8_t*)staging.cpu + (size_t)row * dstPitch, src, dstPitch);
		}
	}
	else
	{
		const uint8_t* src = shadow.data() + (size_t)rect.top * srcPitch + (size_t)rect.left * BytesPerPixel(storage.format);
		ConvertToBGRA8(storage.format, src, srcPitch, (uint8_t*)staging.cpu, dstPitch, rw, rh);
	}

	id<MTLTexture> texture = storage.texture;
	id<MTLBuffer> stagingBuffer = staging.buffer;
	const NSUInteger stagingOffset = staging.offset;
	submit([this, inOrder, texture, stagingBuffer, stagingOffset, dstPitch, dstRows, rw, rh, face, level, rect] {
		if (inOrder)
			endRenderEncoder();
		id<MTLBlitCommandEncoder> blit = inOrder ? [commandBuffer() blitCommandEncoder] : uploadEncoder();
		[blit copyFromBuffer:stagingBuffer
				  sourceOffset:stagingOffset
			 sourceBytesPerRow:dstPitch
		   sourceBytesPerImage:(NSUInteger)dstPitch * dstRows
					sourceSize:MTLSizeMake(rw, rh, 1)
					 toTexture:texture
			  destinationSlice:face
			  destinationLevel:level
			 destinationOrigin:MTLOriginMake((NSUInteger)rect.left, (NSUInteger)rect.top, 0)];
		if (inOrder)
			[blit endEncoding];
	});
}

void Device::readbackTexture(TextureStorage& storage, unsigned face, unsigned level)
{
	if (storage.texture == nil || IsCompressedFormat(storage.format) || storage.depthStencil)
		return;
	unsigned w = storage.levelWidth(level);
	unsigned h = storage.levelHeight(level);
	// Everything recorded so far has to run first; the render thread then stays idle while the
	// game thread uses its state below.
	syncState();
	drain();
	endRenderEncoder();
	NSUInteger bytes = (NSUInteger)w * h * 4;
	if (m_readbackBuffer == nil || [m_readbackBuffer length] < bytes)
		m_readbackBuffer = [m_mtlDevice newBufferWithLength:bytes options:MTLResourceStorageModeShared];
	id<MTLBuffer> buffer = m_readbackBuffer;
	id<MTLBlitCommandEncoder> blit = [commandBuffer() blitCommandEncoder];
	[blit copyFromTexture:storage.texture
				 sourceSlice:face
				 sourceLevel:level
				sourceOrigin:MTLOriginMake(0, 0, 0)
				  sourceSize:MTLSizeMake(w, h, 1)
					toBuffer:buffer
		   destinationOffset:0
	  destinationBytesPerRow:(NSUInteger)w * 4
	destinationBytesPerImage:(NSUInteger)w * h * 4];
	[blit endEncoding];
	execFlush(m_currentSerial, true);
	afterFlush();
	std::vector<uint8_t>& shadow = storage.shadow(face, level);
	ConvertFromBGRA8(storage.format, (const uint8_t*)[buffer contents], w * 4, shadow.data(), RowPitch(storage.format, w), w, h);
	storage.shadowStale = false;
}

//-----------------------------------------------------------------------------
// Presentation
//-----------------------------------------------------------------------------
void Device::updateLetterbox()
{
	int pw = 0, ph = 0;
	SDL_GetWindowSizeInPixels(m_sdlWindow, &pw, &ph);
	int ww = 0, wh = 0;
	SDL_GetWindowSize(m_sdlWindow, &ww, &wh);
	if (pw <= 0 || ph <= 0)
		return;
	if ((int)m_layer.drawableSize.width != pw || (int)m_layer.drawableSize.height != ph)
		m_layer.drawableSize = CGSizeMake(pw, ph);

	double bw = m_params.BackBufferWidth;
	double bh = m_params.BackBufferHeight;
	double scale = std::min(pw / bw, ph / bh);
	double vw = bw * scale;
	double vh = bh * scale;
	m_presentViewport.originX = (pw - vw) * 0.5;
	m_presentViewport.originY = (ph - vh) * 0.5;
	m_presentViewport.width = vw;
	m_presentViewport.height = vh;
	m_presentViewport.znear = 0.0;
	m_presentViewport.zfar = 1.0;

	double toPoints = ww > 0 ? (double)ww / pw : 1.0;
	Win32Shim_SetPresentRect(m_window, (float)(m_presentViewport.originX * toPoints), (float)(m_presentViewport.originY * toPoints),
		(float)(vw * toPoints), (float)(vh * toPoints));
}

void Device::presentToDrawable(const MTLViewport& viewport)
{
	id<CAMetalDrawable> drawable = [m_layer nextDrawable];
	if (drawable == nil)
		return;
	if (g_gammaTexture == nil)
		g_gammaTexture = createGammaTexture(m_mtlDevice, m_execGammaRamp);

	MTLRenderPassDescriptor* pass = [MTLRenderPassDescriptor renderPassDescriptor];
	pass.colorAttachments[0].texture = drawable.texture;
	pass.colorAttachments[0].loadAction = MTLLoadActionClear;
	pass.colorAttachments[0].clearColor = MTLClearColorMake(0, 0, 0, 1);
	pass.colorAttachments[0].storeAction = MTLStoreActionStore;
	id<MTLRenderCommandEncoder> enc = [commandBuffer() renderCommandEncoderWithDescriptor:pass];
	[enc setViewport:viewport];
	[enc setRenderPipelineState:m_presentPipeline];
	[enc setFragmentTexture:m_backBuffer->m_storage->texture atIndex:0];
	[enc setFragmentTexture:g_gammaTexture atIndex:1];
	[enc setFragmentSamplerState:m_presentSampler atIndex:0];
	[enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
	[enc endEncoding];
	[commandBuffer() presentDrawable:drawable];
}

// D3D8METAL_SCREENSHOT=<prefix> writes <prefix>_<frame>.png every D3D8METAL_SCREENSHOT_EVERY
// (default 300) presented frames, for debugging without screen recording permission.
void Device::writeScreenshotIfRequested()
{
	static const char* prefix = getenv("D3D8METAL_SCREENSHOT");
	if (prefix == nullptr)
		return;
	static const int every = getenv("D3D8METAL_SCREENSHOT_EVERY") ? std::max(1, atoi(getenv("D3D8METAL_SCREENSHOT_EVERY"))) : 300;
	static int frame = 0;
	if (++frame % every != 0)
		return;
	TextureStorage& storage = *m_backBuffer->m_storage;
	readbackTexture(storage, 0, 0);
	unsigned w = storage.levelWidth(0), h = storage.levelHeight(0);
	const std::vector<uint8_t>& shadow = storage.shadow(0, 0);
	unsigned pitch = RowPitch(storage.format, w);
	std::vector<uint8_t> rgba((size_t)w * h * 4);
	for (unsigned y = 0; y < h; ++y)
		for (unsigned x = 0; x < w; ++x)
		{
			const uint8_t* src = shadow.data() + y * pitch + x * 4;
			uint8_t* dst = rgba.data() + ((size_t)y * w + x) * 4;
			dst[0] = src[2];
			dst[1] = src[1];
			dst[2] = src[0];
			dst[3] = 255;
		}
	char path[1024];
	snprintf(path, sizeof(path), "%s_%d.png", prefix, frame);
	stbi_write_png(path, (int)w, (int)h, 4, rgba.data(), (int)w * 4);
	fprintf(stderr, "d3d8metal: wrote %s\n", path);
}

HRESULT Device::Present(CONST RECT*, CONST RECT*, HWND, CONST RGNDATA*)
{
	syncState();
	writeScreenshotIfRequested();
	// The window is the game thread's; the render thread gets the letterbox rectangle.
	updateLetterbox();
	const MTLViewport viewport = m_presentViewport;
	// Touching /tmp/d3d8metal_trace traces the draws of the next frame.
	const bool trace = access("/tmp/d3d8metal_trace", F_OK) == 0;
	if (trace)
		unlink("/tmp/d3d8metal_trace");

	// Stay at most one frame ahead of the render thread.
	while (m_presentsSubmitted > m_presentsDone.load(std::memory_order_acquire) + 1)
	{
		std::unique_lock<std::mutex> lock(m_ringMutex);
		m_producerWaiting.store(true);
		m_producerWake.wait_for(lock, std::chrono::milliseconds(1));
		m_producerWaiting.store(false);
	}
	const uint64_t serial = m_currentSerial;
	++m_presentsSubmitted;
	submit([this, serial, viewport, trace] {
		execPresent(serial, viewport);
		m_traceFrame = trace;
		if (trace)
			fprintf(stderr, "d3d8metal: ===== tracing one frame =====\n");
		m_presentsDone.fetch_add(1, std::memory_order_release);
	});
	afterFlush();
	m_backBuffer->m_storage->lastUsedSerial = serial;
	m_backBuffer->m_storage->shadowStale = true;
	return D3D_OK;
}

void Device::execPresent(uint64_t serial, MTLViewport viewport)
{
	endRenderEncoder();
	// Apply a pending clear that never got a draw.
	if (m_pendingClearFlags)
	{
		renderEncoder();
		endRenderEncoder();
	}
	dispatch_semaphore_wait(m_frameSemaphore, DISPATCH_TIME_FOREVER);
	presentToDrawable(viewport);
	dispatch_semaphore_t sem = m_frameSemaphore;
	[commandBuffer() addCompletedHandler:^(id<MTLCommandBuffer>) {
		dispatch_semaphore_signal(sem);
	}];
	execFlush(serial, false);
}

HRESULT Device::Reset(D3DPRESENT_PARAMETERS* params)
{
	if (params == nullptr)
		return D3DERR_INVALIDCALL;
	syncState();
	drain();
	execFlush(m_currentSerial, true);
	afterFlush();
	for (int i = 0; i < MAX_STAGES; ++i)
	{
		if (m_state.textures[i])
			m_state.textures[i]->Release();
		m_state.textures[i] = nullptr;
	}
	m_params = *params;
	if (!createSwapChainResources())
		return D3DERR_NOTAVAILABLE;
	*params = m_params;
	resetState();
	return D3D_OK;
}

HRESULT Device::GetBackBuffer(UINT, D3DBACKBUFFER_TYPE, IDirect3DSurface8** ppBackBuffer)
{
	if (ppBackBuffer == nullptr)
		return D3DERR_INVALIDCALL;
	m_backBuffer->AddRef();
	*ppBackBuffer = m_backBuffer;
	return D3D_OK;
}

HRESULT Device::GetRasterStatus(D3DRASTER_STATUS* pRasterStatus)
{
	if (pRasterStatus == nullptr)
		return D3DERR_INVALIDCALL;
	pRasterStatus->InVBlank = FALSE;
	pRasterStatus->ScanLine = 0;
	return D3D_OK;
}

void Device::SetGammaRamp(DWORD, CONST D3DGAMMARAMP* pRamp)
{
	if (pRamp == nullptr)
		return;
	m_gammaRamp = *pRamp;
	const D3DGAMMARAMP ramp = *pRamp;
	submit([this, ramp] {
		m_execGammaRamp = ramp;
		g_gammaTexture = createGammaTexture(m_mtlDevice, m_execGammaRamp);
	});
}

void Device::GetGammaRamp(D3DGAMMARAMP* pRamp)
{
	if (pRamp)
		*pRamp = m_gammaRamp;
}

HRESULT Device::GetDirect3D(IDirect3D8** ppD3D8)
{
	if (ppD3D8 == nullptr)
		return D3DERR_INVALIDCALL;
	m_d3d->AddRef();
	*ppD3D8 = m_d3d;
	return D3D_OK;
}

HRESULT Device::GetDeviceCaps(D3DCAPS8* pCaps)
{
	if (pCaps == nullptr)
		return D3DERR_INVALIDCALL;
	FillCaps(pCaps);
	return D3D_OK;
}

HRESULT Device::GetDisplayMode(D3DDISPLAYMODE* pMode)
{
	if (pMode == nullptr)
		return D3DERR_INVALIDCALL;
	pMode->Width = m_params.BackBufferWidth;
	pMode->Height = m_params.BackBufferHeight;
	pMode->RefreshRate = 60;
	pMode->Format = m_params.BackBufferFormat;
	return D3D_OK;
}

HRESULT Device::GetCreationParameters(D3DDEVICE_CREATION_PARAMETERS* p)
{
	if (p == nullptr)
		return D3DERR_INVALIDCALL;
	p->AdapterOrdinal = 0;
	p->DeviceType = D3DDEVTYPE_HAL;
	p->hFocusWindow = m_window;
	p->BehaviorFlags = m_behaviorFlags;
	return D3D_OK;
}

HRESULT Device::SetCursorProperties(UINT XHotSpot, UINT YHotSpot, IDirect3DSurface8* pCursorBitmap)
{
	Surface* surface = static_cast<Surface*>(pCursorBitmap);
	if (surface == nullptr)
		return D3DERR_INVALIDCALL;
	static std::map<std::pair<TextureStorage*, unsigned>, HCURSOR> cache;
	auto key = std::make_pair(surface->m_storage.get(), (XHotSpot << 16) | YHotSpot);
	HCURSOR cursor = nullptr;
	auto it = cache.find(key);
	if (it != cache.end())
		cursor = it->second;
	else
	{
		TextureStorage& st = *surface->m_storage;
		unsigned w = surface->width();
		unsigned h = surface->height();
		std::vector<uint8_t>& shadow = st.shadow(surface->m_face, surface->m_level);
		std::vector<uint8_t> bgra((size_t)w * h * 4);
		if (IsCompressedFormat(st.format))
			DecodeDXT(st.format, shadow.data(), RowPitch(st.format, w), bgra.data(), w * 4, w, h);
		else
			ConvertToBGRA8(st.format, shadow.data(), RowPitch(st.format, w), bgra.data(), w * 4, w, h);
		// BGRA bytes are ARGB8888 in little endian, which is what the shim expects.
		cursor = Win32Shim_CreateCursorFromRGBA(bgra.data(), (int)w, (int)h, (int)XHotSpot, (int)YHotSpot);
		cache[key] = cursor;
	}
	if (cursor && m_cursorVisible)
		::SetCursor(cursor);
	return D3D_OK;
}

BOOL Device::ShowCursor(BOOL bShow)
{
	BOOL old = m_cursorVisible;
	m_cursorVisible = bShow != FALSE;
	if (m_cursorVisible)
		SDL_ShowCursor();
	else
		SDL_HideCursor();
	return old;
}

HRESULT Device::CreateAdditionalSwapChain(D3DPRESENT_PARAMETERS*, IDirect3DSwapChain8** pSwapChain)
{
	if (pSwapChain == nullptr)
		return D3DERR_INVALIDCALL;
	*pSwapChain = new SwapChain(this);
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// Resource creation
//-----------------------------------------------------------------------------
HRESULT Device::CreateTexture(UINT Width, UINT Height, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DTexture8** ppTexture)
{
	if (ppTexture == nullptr)
		return D3DERR_INVALIDCALL;
	auto storage = createStorage(Width, Height, Levels, 1, Usage, Format, Pool);
	if (traceEnabled())
		fprintf(stderr, "d3d8metal: CreateTexture %ux%u levels %u usage 0x%X format %d pool %d\n", Width, Height, Levels,
			(unsigned)Usage, (int)Format, (int)Pool);
	if (storage == nullptr)
		return D3DERR_OUTOFVIDEOMEMORY;
	*ppTexture = new Texture(this, storage);
	return D3D_OK;
}

HRESULT Device::CreateVolumeTexture(UINT, UINT, UINT, UINT, DWORD, D3DFORMAT, D3DPOOL, IDirect3DVolumeTexture8** ppVolumeTexture)
{
	if (ppVolumeTexture)
		*ppVolumeTexture = nullptr;
	return D3DERR_NOTAVAILABLE;
}

HRESULT Device::CreateCubeTexture(UINT EdgeLength, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DCubeTexture8** ppCubeTexture)
{
	if (ppCubeTexture == nullptr)
		return D3DERR_INVALIDCALL;
	auto storage = createStorage(EdgeLength, EdgeLength, Levels, 6, Usage, Format, Pool);
	if (storage == nullptr)
		return D3DERR_OUTOFVIDEOMEMORY;
	*ppCubeTexture = new CubeTexture(this, storage);
	return D3D_OK;
}

HRESULT Device::CreateVertexBuffer(UINT Length, DWORD Usage, DWORD FVF, D3DPOOL Pool, IDirect3DVertexBuffer8** ppVertexBuffer)
{
	if (ppVertexBuffer == nullptr || Length == 0)
		return D3DERR_INVALIDCALL;
	*ppVertexBuffer = new VertexBuffer(this, Length, Usage, FVF, Pool);
	return D3D_OK;
}

HRESULT Device::CreateIndexBuffer(UINT Length, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DIndexBuffer8** ppIndexBuffer)
{
	if (ppIndexBuffer == nullptr || Length == 0)
		return D3DERR_INVALIDCALL;
	*ppIndexBuffer = new IndexBuffer(this, Length, Usage, Format, Pool);
	return D3D_OK;
}

HRESULT Device::CreateRenderTarget(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE, BOOL, IDirect3DSurface8** ppSurface)
{
	if (ppSurface == nullptr)
		return D3DERR_INVALIDCALL;
	auto storage = createStorage(Width, Height, 1, 1, D3DUSAGE_RENDERTARGET, Format, D3DPOOL_DEFAULT);
	if (storage == nullptr)
		return D3DERR_OUTOFVIDEOMEMORY;
	*ppSurface = new Surface(this, storage);
	return D3D_OK;
}

HRESULT Device::CreateDepthStencilSurface(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE, IDirect3DSurface8** ppSurface)
{
	if (ppSurface == nullptr)
		return D3DERR_INVALIDCALL;
	auto storage = createStorage(Width, Height, 1, 1, D3DUSAGE_DEPTHSTENCIL, Format, D3DPOOL_DEFAULT);
	if (storage == nullptr)
		return D3DERR_OUTOFVIDEOMEMORY;
	*ppSurface = new Surface(this, storage);
	return D3D_OK;
}

HRESULT Device::CreateImageSurface(UINT Width, UINT Height, D3DFORMAT Format, IDirect3DSurface8** ppSurface)
{
	if (ppSurface == nullptr)
		return D3DERR_INVALIDCALL;
	auto storage = createStorage(Width, Height, 1, 1, 0, Format, D3DPOOL_SYSTEMMEM);
	if (storage == nullptr)
		return D3DERR_OUTOFVIDEOMEMORY;
	*ppSurface = new Surface(this, storage);
	return D3D_OK;
}

namespace
{
// Copies pixels between two surfaces through their CPU shadows.
void copySurfaceRect(Surface* src, const RECT& srcRect, Surface* dst, POINT dstPoint)
{
	TextureStorage& s = *src->m_storage;
	TextureStorage& d = *dst->m_storage;
	unsigned sw = src->width(), dw = dst->width();
	std::vector<uint8_t>& sShadow = s.shadow(src->m_face, src->m_level);
	std::vector<uint8_t>& dShadow = d.shadow(dst->m_face, dst->m_level);
	unsigned w = (unsigned)(srcRect.right - srcRect.left);
	unsigned h = (unsigned)(srcRect.bottom - srcRect.top);
	if (s.format == d.format)
	{
		if (IsCompressedFormat(s.format))
		{
			unsigned blockBytes = s.format == D3DFMT_DXT1 ? 8 : 16;
			unsigned sp = RowPitch(s.format, sw), dp = RowPitch(d.format, dw);
			for (unsigned row = 0; row < (h + 3) / 4; ++row)
			{
				memcpy(dShadow.data() + (size_t)(dstPoint.y / 4 + row) * dp + (size_t)(dstPoint.x / 4) * blockBytes,
					sShadow.data() + (size_t)(srcRect.top / 4 + row) * sp + (size_t)(srcRect.left / 4) * blockBytes, ((w + 3) / 4) * blockBytes);
			}
			return;
		}
		unsigned bpp = BytesPerPixel(s.format);
		unsigned sp = RowPitch(s.format, sw), dp = RowPitch(d.format, dw);
		for (unsigned row = 0; row < h; ++row)
		{
			memcpy(dShadow.data() + (size_t)(dstPoint.y + row) * dp + (size_t)dstPoint.x * bpp,
				sShadow.data() + (size_t)(srcRect.top + row) * sp + (size_t)srcRect.left * bpp, (size_t)w * bpp);
		}
		return;
	}
	// Different formats: go through BGRA8.
	std::vector<uint8_t> tmp((size_t)sw * src->height() * 4);
	if (IsCompressedFormat(s.format))
		DecodeDXT(s.format, sShadow.data(), RowPitch(s.format, sw), tmp.data(), sw * 4, sw, src->height());
	else
		ConvertToBGRA8(s.format, sShadow.data(), RowPitch(s.format, sw), tmp.data(), sw * 4, sw, src->height());
	if (IsCompressedFormat(d.format))
		return;
	ConvertFromBGRA8(d.format, tmp.data() + (size_t)srcRect.top * sw * 4 + (size_t)srcRect.left * 4, sw * 4,
		dShadow.data() + (size_t)dstPoint.y * RowPitch(d.format, dw) + (size_t)dstPoint.x * BytesPerPixel(d.format), RowPitch(d.format, dw), w, h);
}
} // namespace

HRESULT Device::CopyRects(IDirect3DSurface8* pSourceSurface, CONST RECT* pSourceRectsArray, UINT cRects, IDirect3DSurface8* pDestinationSurface, CONST POINT* pDestPointsArray)
{
	Surface* src = static_cast<Surface*>(pSourceSurface);
	Surface* dst = static_cast<Surface*>(pDestinationSurface);
	if (src == nullptr || dst == nullptr)
		return D3DERR_INVALIDCALL;
	TextureStorage& ss = *src->m_storage;
	TextureStorage& ds = *dst->m_storage;
	if (ss.renderTarget && ds.renderTarget && !ss.depthStencil && !ds.depthStencil && ss.texture != nil && ds.texture != nil
		&& ss.gpuFormat == ds.gpuFormat && !IsCompressedFormat(ss.format))
	{
		// Between render targets the copy stays on the GPU (the heat effect copies the back buffer
		// every frame); ending the pass resolves a multisampled source.
		struct Copy
		{
			MTLOrigin from;
			MTLSize size;
			MTLOrigin to;
		};
		std::vector<Copy> copies;
		UINT count = cRects ? cRects : 1;
		for (UINT i = 0; i < count; ++i)
		{
			RECT r;
			SetRect(&r, 0, 0, (int)src->width(), (int)src->height());
			if (pSourceRectsArray)
				r = pSourceRectsArray[i];
			POINT p = pDestPointsArray ? pDestPointsArray[i] : POINT { r.left, r.top };
			r.left = std::max<LONG>(r.left, 0);
			r.top = std::max<LONG>(r.top, 0);
			r.right = std::min<LONG>(r.right, (LONG)src->width());
			r.bottom = std::min<LONG>(r.bottom, (LONG)src->height());
			r.right = std::min<LONG>(r.right, r.left + (LONG)dst->width() - p.x);
			r.bottom = std::min<LONG>(r.bottom, r.top + (LONG)dst->height() - p.y);
			if (p.x < 0 || p.y < 0 || r.right <= r.left || r.bottom <= r.top)
				continue;
			copies.push_back({ MTLOriginMake(r.left, r.top, 0), MTLSizeMake(r.right - r.left, r.bottom - r.top, 1), MTLOriginMake(p.x, p.y, 0) });
		}
		syncState();
		id<MTLTexture> from = ss.texture, to = ds.texture;
		const NSUInteger fromSlice = src->m_face, fromLevel = src->m_level, toSlice = dst->m_face, toLevel = dst->m_level;
		// Only compared with the render thread's render target, never used.
		const void* srcSurface = src;
		submit([this, copies = std::move(copies), from, to, fromSlice, fromLevel, toSlice, toLevel, srcSurface] {
			if (srcSurface == m_renderTarget && m_pendingClearFlags != 0)
				renderEncoder();
			endRenderEncoder();
			id<MTLBlitCommandEncoder> blit = [commandBuffer() blitCommandEncoder];
			for (const Copy& c : copies)
			{
				[blit copyFromTexture:from
						  sourceSlice:fromSlice
						  sourceLevel:fromLevel
						 sourceOrigin:c.from
						   sourceSize:c.size
							toTexture:to
					 destinationSlice:toSlice
					 destinationLevel:toLevel
					destinationOrigin:c.to];
			}
			[blit endEncoding];
		});
		markTextureUsed(ss);
		markTextureUsed(ds);
		ds.shadowStale = true;
		return D3D_OK;
	}
	if (ss.renderTarget && ss.shadowStale)
		readbackTexture(ss, src->m_face, src->m_level);

	RECT full;
	SetRect(&full, 0, 0, (int)src->width(), (int)src->height());
	UINT count = cRects ? cRects : 1;
	for (UINT i = 0; i < count; ++i)
	{
		RECT r = pSourceRectsArray ? pSourceRectsArray[i] : full;
		POINT p = pDestPointsArray ? pDestPointsArray[i] : POINT { r.left, r.top };
		r.right = std::min<LONG>(r.right, (LONG)src->width());
		r.bottom = std::min<LONG>(r.bottom, (LONG)src->height());
		if (p.x + (r.right - r.left) > (LONG)dst->width())
			r.right = r.left + (LONG)dst->width() - p.x;
		if (p.y + (r.bottom - r.top) > (LONG)dst->height())
			r.bottom = r.top + (LONG)dst->height() - p.y;
		if (r.right <= r.left || r.bottom <= r.top)
			continue;
		copySurfaceRect(src, r, dst, p);
		RECT dr;
		SetRect(&dr, (int)p.x, (int)p.y, (int)(p.x + r.right - r.left), (int)(p.y + r.bottom - r.top));
		uploadTexture(*dst->m_storage, dst->m_face, dst->m_level, dr);
	}
	return D3D_OK;
}

HRESULT Device::UpdateTexture(IDirect3DBaseTexture8* pSourceTexture, IDirect3DBaseTexture8* pDestinationTexture)
{
	if (pSourceTexture == nullptr || pDestinationTexture == nullptr)
		return D3DERR_INVALIDCALL;
	std::shared_ptr<TextureStorage> src, dst;
	if (pSourceTexture->GetType() == D3DRTYPE_TEXTURE)
	{
		src = static_cast<Texture*>(pSourceTexture)->m_storage;
		dst = static_cast<Texture*>(pDestinationTexture)->m_storage;
	}
	else if (pSourceTexture->GetType() == D3DRTYPE_CUBETEXTURE)
	{
		src = static_cast<CubeTexture*>(pSourceTexture)->m_storage;
		dst = static_cast<CubeTexture*>(pDestinationTexture)->m_storage;
	}
	else
		return D3DERR_INVALIDCALL;

	// Source levels may be a superset of the destination levels (skip the top ones).
	unsigned skip = 0;
	while (skip < src->levels && src->levelWidth(skip) > dst->width)
		++skip;
	for (unsigned face = 0; face < dst->faces; ++face)
	{
		for (unsigned level = 0; level < dst->levels && level + skip < src->levels; ++level)
		{
			if (src->shadows.empty() || src->shadows[face * src->levels + level + skip].empty())
				continue;
			dst->shadow(face, level) = src->shadow(face, level + skip);
			RECT r;
			SetRect(&r, 0, 0, (int)dst->levelWidth(level), (int)dst->levelHeight(level));
			uploadTexture(*dst, face, level, r);
		}
	}
	return D3D_OK;
}

HRESULT Device::GetFrontBuffer(IDirect3DSurface8* pDestSurface)
{
	Surface* dst = static_cast<Surface*>(pDestSurface);
	if (dst == nullptr)
		return D3DERR_INVALIDCALL;
	readbackTexture(*m_backBuffer->m_storage, 0, 0);
	RECT r;
	SetRect(&r, 0, 0, (int)std::min(m_backBuffer->width(), dst->width()), (int)std::min(m_backBuffer->height(), dst->height()));
	copySurfaceRect(m_backBuffer, r, dst, POINT { 0, 0 });
	return D3D_OK;
}

HRESULT Device::SetRenderTarget(IDirect3DSurface8* pRenderTarget, IDirect3DSurface8* pNewZStencil)
{
	Surface* rt = static_cast<Surface*>(pRenderTarget);
	Surface* ds = static_cast<Surface*>(pNewZStencil);
	// Changes made before belong to the old render target.
	syncState();
	if (rt)
	{
		rt->AddRef();
		if (m_frontRenderTarget)
			m_frontRenderTarget->Release();
		m_frontRenderTarget = rt;
		// D3D resets the viewport to the full render target; the render thread does the same.
		m_front.viewport.X = 0;
		m_front.viewport.Y = 0;
		m_front.viewport.Width = rt->width();
		m_front.viewport.Height = rt->height();
		m_front.viewport.MinZ = 0.0f;
		m_front.viewport.MaxZ = 1.0f;
	}
	if (ds)
		ds->AddRef();
	if (m_frontDepthStencil)
		m_frontDepthStencil->Release();
	m_frontDepthStencil = ds;

	// The command holds references until the render thread has taken its own.
	if (rt)
		rt->AddRef();
	if (ds)
		ds->AddRef();
	submit([this, rt, ds] {
		execSetRenderTarget(rt, ds);
		if (rt)
			rt->Release();
		if (ds)
			ds->Release();
	});
	return D3D_OK;
}

void Device::execSetRenderTarget(Surface* rt, Surface* ds)
{
	endRenderEncoder();
	if (m_pendingClearFlags)
		m_pendingClearFlags = 0;
	if (rt)
	{
		rt->AddRef();
		if (m_renderTarget)
			m_renderTarget->Release();
		m_renderTarget = rt;
	}
	if (ds)
		ds->AddRef();
	if (m_depthStencil)
		m_depthStencil->Release();
	m_depthStencil = ds;

	// D3D resets the viewport to the full render target.
	if (rt)
	{
		m_state.viewport.X = 0;
		m_state.viewport.Y = 0;
		m_state.viewport.Width = rt->width();
		m_state.viewport.Height = rt->height();
		m_state.viewport.MinZ = 0.0f;
		m_state.viewport.MaxZ = 1.0f;
	}
}

HRESULT Device::GetRenderTarget(IDirect3DSurface8** ppRenderTarget)
{
	if (ppRenderTarget == nullptr)
		return D3DERR_INVALIDCALL;
	m_frontRenderTarget->AddRef();
	*ppRenderTarget = m_frontRenderTarget;
	return D3D_OK;
}

HRESULT Device::GetDepthStencilSurface(IDirect3DSurface8** ppZStencilSurface)
{
	if (ppZStencilSurface == nullptr)
		return D3DERR_INVALIDCALL;
	if (m_frontDepthStencil == nullptr)
	{
		*ppZStencilSurface = nullptr;
		return D3DERR_NOTFOUND;
	}
	m_frontDepthStencil->AddRef();
	*ppZStencilSurface = m_frontDepthStencil;
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// State
//-----------------------------------------------------------------------------
HRESULT Device::SetTransform(D3DTRANSFORMSTATETYPE State, CONST D3DMATRIX* pMatrix)
{
	if ((unsigned)State >= 512 || pMatrix == nullptr)
		return D3DERR_INVALIDCALL;
	m_front.transforms[State] = *pMatrix;
	if (!m_transformDirty[State])
	{
		m_transformDirty[State] = true;
		m_dirtyTransforms.push_back((uint16_t)State);
	}
	return D3D_OK;
}

HRESULT Device::GetTransform(D3DTRANSFORMSTATETYPE State, D3DMATRIX* pMatrix)
{
	if ((unsigned)State >= 512 || pMatrix == nullptr)
		return D3DERR_INVALIDCALL;
	*pMatrix = m_front.transforms[State];
	return D3D_OK;
}

HRESULT Device::MultiplyTransform(D3DTRANSFORMSTATETYPE State, CONST D3DMATRIX* pMatrix)
{
	if ((unsigned)State >= 512 || pMatrix == nullptr)
		return D3DERR_INVALIDCALL;
	D3DMATRIX a = m_front.transforms[State];
	D3DMATRIX r;
	for (int i = 0; i < 4; ++i)
		for (int j = 0; j < 4; ++j)
		{
			float v = 0;
			for (int k = 0; k < 4; ++k)
				v += a.m[i][k] * pMatrix->m[k][j];
			r.m[i][j] = v;
		}
	return SetTransform(State, &r);
}

HRESULT Device::SetViewport(CONST D3DVIEWPORT8* pViewport)
{
	if (pViewport == nullptr)
		return D3DERR_INVALIDCALL;
	m_front.viewport = *pViewport;
	m_dirtyMisc |= DIRTY_VIEWPORT;
	return D3D_OK;
}

HRESULT Device::GetViewport(D3DVIEWPORT8* pViewport)
{
	if (pViewport == nullptr)
		return D3DERR_INVALIDCALL;
	*pViewport = m_front.viewport;
	return D3D_OK;
}

HRESULT Device::SetMaterial(CONST D3DMATERIAL8* pMaterial)
{
	if (pMaterial == nullptr)
		return D3DERR_INVALIDCALL;
	m_front.material = *pMaterial;
	m_dirtyMisc |= DIRTY_MATERIAL;
	return D3D_OK;
}

HRESULT Device::GetMaterial(D3DMATERIAL8* pMaterial)
{
	if (pMaterial == nullptr)
		return D3DERR_INVALIDCALL;
	*pMaterial = m_front.material;
	return D3D_OK;
}

HRESULT Device::SetLight(DWORD Index, CONST D3DLIGHT8* light)
{
	if (Index >= MAX_LIGHTS || light == nullptr)
		return D3DERR_INVALIDCALL;
	m_front.lights[Index] = *light;
	m_dirtyMisc |= DIRTY_LIGHT0 << Index;
	return D3D_OK;
}

HRESULT Device::GetLight(DWORD Index, D3DLIGHT8* light)
{
	if (Index >= MAX_LIGHTS || light == nullptr)
		return D3DERR_INVALIDCALL;
	*light = m_front.lights[Index];
	return D3D_OK;
}

HRESULT Device::LightEnable(DWORD Index, BOOL Enable)
{
	if (Index >= MAX_LIGHTS)
		return D3DERR_INVALIDCALL;
	m_front.lightEnabled[Index] = Enable != FALSE;
	m_dirtyMisc |= DIRTY_LIGHT0 << Index;
	return D3D_OK;
}

HRESULT Device::GetLightEnable(DWORD Index, BOOL* pEnable)
{
	if (Index >= MAX_LIGHTS || pEnable == nullptr)
		return D3DERR_INVALIDCALL;
	*pEnable = m_front.lightEnabled[Index];
	return D3D_OK;
}

HRESULT Device::SetClipPlane(DWORD Index, CONST float* pPlane)
{
	if (Index >= MAX_CLIP_PLANES || pPlane == nullptr)
		return D3DERR_INVALIDCALL;
	memcpy(m_front.clipPlanes[Index], pPlane, sizeof(float) * 4);
	m_dirtyMisc |= DIRTY_CLIP0 << Index;
	return D3D_OK;
}

HRESULT Device::GetClipPlane(DWORD Index, float* pPlane)
{
	if (Index >= MAX_CLIP_PLANES || pPlane == nullptr)
		return D3DERR_INVALIDCALL;
	memcpy(pPlane, m_front.clipPlanes[Index], sizeof(float) * 4);
	return D3D_OK;
}

HRESULT Device::SetRenderState(D3DRENDERSTATETYPE State, DWORD Value)
{
	if ((unsigned)State >= 256)
		return D3DERR_INVALIDCALL;
	if (m_front.renderStates[State] != Value)
	{
		m_front.renderStates[State] = Value;
		markRenderState((unsigned)State);
	}
	return D3D_OK;
}

HRESULT Device::GetRenderState(D3DRENDERSTATETYPE State, DWORD* pValue)
{
	if ((unsigned)State >= 256 || pValue == nullptr)
		return D3DERR_INVALIDCALL;
	*pValue = m_front.renderStates[State];
	return D3D_OK;
}

// State blocks capture the complete device state. Resource references held by a
// block are not counted, matching how the game uses them (not at all).
HRESULT Device::BeginStateBlock()
{
	m_recordingStateBlock = true;
	return D3D_OK;
}

HRESULT Device::EndStateBlock(DWORD* pToken)
{
	if (pToken == nullptr)
		return D3DERR_INVALIDCALL;
	m_recordingStateBlock = false;
	*pToken = m_nextStateBlock++;
	m_stateBlocks[*pToken] = m_front;
	return D3D_OK;
}

HRESULT Device::ApplyStateBlock(DWORD Token)
{
	auto it = m_stateBlocks.find(Token);
	if (it == m_stateBlocks.end())
		return D3DERR_INVALIDCALL;
	m_front = it->second;
	markAllDirty();
	return D3D_OK;
}

HRESULT Device::CaptureStateBlock(DWORD Token)
{
	auto it = m_stateBlocks.find(Token);
	if (it == m_stateBlocks.end())
		return D3DERR_INVALIDCALL;
	it->second = m_front;
	return D3D_OK;
}

HRESULT Device::DeleteStateBlock(DWORD Token)
{
	m_stateBlocks.erase(Token);
	return D3D_OK;
}

HRESULT Device::CreateStateBlock(D3DSTATEBLOCKTYPE, DWORD* pToken)
{
	if (pToken == nullptr)
		return D3DERR_INVALIDCALL;
	*pToken = m_nextStateBlock++;
	m_stateBlocks[*pToken] = m_front;
	return D3D_OK;
}

HRESULT Device::GetClipStatus(D3DCLIPSTATUS8* pClipStatus)
{
	if (pClipStatus == nullptr)
		return D3DERR_INVALIDCALL;
	pClipStatus->ClipUnion = 0;
	pClipStatus->ClipIntersection = 0;
	return D3D_OK;
}

HRESULT Device::GetTexture(DWORD Stage, IDirect3DBaseTexture8** ppTexture)
{
	if (Stage >= MAX_STAGES || ppTexture == nullptr)
		return D3DERR_INVALIDCALL;
	*ppTexture = m_front.textures[Stage];
	if (*ppTexture)
		(*ppTexture)->AddRef();
	return D3D_OK;
}

HRESULT Device::SetTexture(DWORD Stage, IDirect3DBaseTexture8* pTexture)
{
	if (Stage >= MAX_STAGES)
		return D3DERR_INVALIDCALL;
	if (m_front.textures[Stage] == pTexture)
		return D3D_OK;
	if (pTexture)
		pTexture->AddRef();
	if (m_front.textures[Stage])
		m_front.textures[Stage]->Release();
	m_front.textures[Stage] = pTexture;
	m_dirtyMisc |= DIRTY_TEXTURE0 << Stage;
	return D3D_OK;
}

HRESULT Device::GetTextureStageState(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD* pValue)
{
	if (Stage >= MAX_STAGES || (unsigned)Type >= 32 || pValue == nullptr)
		return D3DERR_INVALIDCALL;
	*pValue = m_front.stageStates[Stage][Type];
	return D3D_OK;
}

HRESULT Device::SetTextureStageState(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD Value)
{
	if (Stage >= MAX_STAGES || (unsigned)Type >= 32)
		return D3DERR_INVALIDCALL;
	if (m_front.stageStates[Stage][Type] != Value)
	{
		m_front.stageStates[Stage][Type] = Value;
		const unsigned index = Stage * 32 + (unsigned)Type;
		if (!m_stageStateDirty[index])
		{
			m_stageStateDirty[index] = true;
			m_dirtyStageStates.push_back((uint16_t)index);
		}
	}
	return D3D_OK;
}

HRESULT Device::ValidateDevice(DWORD* pNumPasses)
{
	if (pNumPasses)
		*pNumPasses = 1;
	return D3D_OK;
}

HRESULT Device::GetCurrentTexturePalette(UINT* PaletteNumber)
{
	if (PaletteNumber)
		*PaletteNumber = 0;
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// Shaders (vs.1.1 and ps.1.0 to ps.1.3, translated to MSL in shadertrans.cpp)
//-----------------------------------------------------------------------------
namespace
{
// Reads the stream 0 part of a vertex declaration and derives the FVF it matches, if any.
void parseDeclaration(VertexShaderObject& obj)
{
	static const unsigned sizes[8] = { 4, 8, 12, 16, 4, 4, 4, 8 }; // D3DVSDT_FLOAT1 .. D3DVSDT_SHORT4
	unsigned stream = 0, offset = 0;
	std::vector<std::pair<unsigned, unsigned>> order; // register, type
	for (DWORD t : obj.declaration)
	{
		DWORD kind = (t & D3DVSD_TOKENTYPEMASK) >> D3DVSD_TOKENTYPESHIFT;
		if (kind == D3DVSD_TOKEN_STREAM)
		{
			stream = t & D3DVSD_STREAMNUMBERMASK;
			offset = 0;
		}
		else if (kind == D3DVSD_TOKEN_STREAMDATA && stream == 0)
		{
			if (t & 0x10000000)
			{
				offset += ((t & D3DVSD_SKIPCOUNTMASK) >> D3DVSD_SKIPCOUNTSHIFT) * 4;
				continue;
			}
			unsigned reg = t & D3DVSD_VERTEXREGMASK;
			unsigned type = (t & D3DVSD_DATATYPEMASK) >> D3DVSD_DATATYPESHIFT;
			if (reg >= 16 || type > 7)
				continue;
			obj.inputType[reg] = (uint8_t)(type + 1);
			obj.inputOffset[reg] = (uint8_t)offset;
			offset += sizes[type];
			order.push_back({ reg, type });
		}
	}
	obj.stride = offset;

	// FVF equivalent for fixed function vertex processing with a declaration: the registers in the
	// order and types of the FVF layout.
	DWORD fvf = 0;
	size_t i = 0;
	auto take = [&](unsigned reg, unsigned type) {
		if (i < order.size() && order[i].first == reg && order[i].second == type)
		{
			++i;
			return true;
		}
		return false;
	};
	if (!take(D3DVSDE_POSITION, D3DVSDT_FLOAT3))
		return;
	fvf |= D3DFVF_XYZ;
	if (take(D3DVSDE_NORMAL, D3DVSDT_FLOAT3))
		fvf |= D3DFVF_NORMAL;
	if (take(D3DVSDE_PSIZE, D3DVSDT_FLOAT1))
		fvf |= D3DFVF_PSIZE;
	if (take(D3DVSDE_DIFFUSE, D3DVSDT_D3DCOLOR))
		fvf |= D3DFVF_DIFFUSE;
	if (take(D3DVSDE_SPECULAR, D3DVSDT_D3DCOLOR))
		fvf |= D3DFVF_SPECULAR;
	unsigned tex = 0;
	while (i < order.size() && order[i].first == D3DVSDE_TEXCOORD0 + tex && order[i].second <= D3DVSDT_FLOAT4)
	{
		unsigned n = order[i].second + 1;
		fvf |= n == 1 ? D3DFVF_TEXCOORDSIZE1(tex) : n == 2 ? D3DFVF_TEXCOORDSIZE2(tex) : n == 3 ? D3DFVF_TEXCOORDSIZE3(tex) : D3DFVF_TEXCOORDSIZE4(tex);
		++tex;
		++i;
	}
	if (i != order.size())
		return;
	obj.fvf = fvf | (tex << D3DFVF_TEXCOUNT_SHIFT);
}
} // namespace

HRESULT Device::CreateVertexShader(CONST DWORD* pDeclaration, CONST DWORD* pFunction, DWORD* pHandle, DWORD)
{
	if (pHandle == nullptr)
		return D3DERR_INVALIDCALL;
	VertexShaderObject obj;
	if (pDeclaration)
	{
		const DWORD* p = pDeclaration;
		while (*p != D3DVSD_END())
			obj.declaration.push_back(*p++);
	}
	parseDeclaration(obj);
	if (pFunction)
	{
		const DWORD* p = pFunction;
		while (*p != 0x0000FFFF)
			obj.function.push_back(*p++);
		ShaderInfo info = AnalyzeShader(obj.function);
		if (!info.valid || info.pixel)
		{
			fprintf(stderr, "d3d8metal: vertex shader rejected: %s\n", info.error.c_str());
			return D3DERR_INVALIDCALL;
		}
		obj.hash = RegisterShaderCode(obj.function);
	}
	DWORD handle = (m_nextShaderHandle++ << 1) | 1; // bit 0 distinguishes handles from FVF codes
	submit([this, handle, obj = std::move(obj)] { m_vertexShaders[handle] = obj; });
	*pHandle = handle;
	return D3D_OK;
}

HRESULT Device::SetVertexShader(DWORD Handle)
{
	m_front.vertexShader = Handle;
	m_dirtyMisc |= DIRTY_VERTEX_SHADER;
	return D3D_OK;
}

HRESULT Device::GetVertexShader(DWORD* pHandle)
{
	if (pHandle == nullptr)
		return D3DERR_INVALIDCALL;
	*pHandle = m_front.vertexShader;
	return D3D_OK;
}

HRESULT Device::DeleteVertexShader(DWORD Handle)
{
	syncState();
	submit([this, Handle] { m_vertexShaders.erase(Handle); });
	return D3D_OK;
}

HRESULT Device::SetVertexShaderConstant(DWORD Register, CONST void* pConstantData, DWORD ConstantCount)
{
	if (Register + ConstantCount > 96 || pConstantData == nullptr)
		return D3DERR_INVALIDCALL;
	memcpy(m_front.vsConstants[Register], pConstantData, ConstantCount * 16);
	m_vsDirtyLo = std::min(m_vsDirtyLo, (int)Register);
	m_vsDirtyHi = std::max(m_vsDirtyHi, (int)(Register + ConstantCount));
	return D3D_OK;
}

HRESULT Device::GetVertexShaderConstant(DWORD Register, void* pConstantData, DWORD ConstantCount)
{
	if (Register + ConstantCount > 96 || pConstantData == nullptr)
		return D3DERR_INVALIDCALL;
	memcpy(pConstantData, m_front.vsConstants[Register], ConstantCount * 16);
	return D3D_OK;
}

HRESULT Device::SetStreamSource(UINT StreamNumber, IDirect3DVertexBuffer8* pStreamData, UINT Stride)
{
	if (StreamNumber >= MAX_STREAMS)
		return D3DERR_INVALIDCALL;
	VertexBuffer* vb = static_cast<VertexBuffer*>(pStreamData);
	if (vb)
		vb->AddRef();
	if (m_front.streams[StreamNumber].buffer)
		m_front.streams[StreamNumber].buffer->Release();
	m_front.streams[StreamNumber].buffer = vb;
	m_front.streams[StreamNumber].stride = Stride;
	return D3D_OK;
}

HRESULT Device::GetStreamSource(UINT StreamNumber, IDirect3DVertexBuffer8** ppStreamData, UINT* pStride)
{
	if (StreamNumber >= MAX_STREAMS || ppStreamData == nullptr || pStride == nullptr)
		return D3DERR_INVALIDCALL;
	*ppStreamData = m_front.streams[StreamNumber].buffer;
	if (*ppStreamData)
		(*ppStreamData)->AddRef();
	*pStride = m_front.streams[StreamNumber].stride;
	return D3D_OK;
}

HRESULT Device::SetIndices(IDirect3DIndexBuffer8* pIndexData, UINT BaseVertexIndex)
{
	IndexBuffer* ib = static_cast<IndexBuffer*>(pIndexData);
	if (ib)
		ib->AddRef();
	if (m_front.indices)
		m_front.indices->Release();
	m_front.indices = ib;
	m_front.baseVertexIndex = BaseVertexIndex;
	return D3D_OK;
}

HRESULT Device::GetIndices(IDirect3DIndexBuffer8** ppIndexData, UINT* pBaseVertexIndex)
{
	if (ppIndexData == nullptr || pBaseVertexIndex == nullptr)
		return D3DERR_INVALIDCALL;
	*ppIndexData = m_front.indices;
	if (*ppIndexData)
		(*ppIndexData)->AddRef();
	*pBaseVertexIndex = m_front.baseVertexIndex;
	return D3D_OK;
}

HRESULT Device::CreatePixelShader(CONST DWORD* pFunction, DWORD* pHandle)
{
	if (pHandle == nullptr || pFunction == nullptr)
		return D3DERR_INVALIDCALL;
	PixelShaderObject obj;
	const DWORD* p = pFunction;
	while (*p != 0x0000FFFF)
		obj.function.push_back(*p++);
	ShaderInfo info = AnalyzeShader(obj.function);
	if (!info.valid || !info.pixel)
	{
		fprintf(stderr, "d3d8metal: pixel shader rejected: %s\n", info.error.c_str());
		return D3DERR_INVALIDCALL;
	}
	obj.hash = RegisterShaderCode(obj.function);
	obj.textureCount = info.textureCount;
	DWORD handle = m_nextShaderHandle++;
	submit([this, handle, obj = std::move(obj)] { m_pixelShaders[handle] = obj; });
	*pHandle = handle;
	return D3D_OK;
}

HRESULT Device::SetPixelShader(DWORD Handle)
{
	m_front.pixelShader = Handle;
	m_dirtyMisc |= DIRTY_PIXEL_SHADER;
	return D3D_OK;
}

HRESULT Device::GetPixelShader(DWORD* pHandle)
{
	if (pHandle == nullptr)
		return D3DERR_INVALIDCALL;
	*pHandle = m_front.pixelShader;
	return D3D_OK;
}

HRESULT Device::DeletePixelShader(DWORD Handle)
{
	syncState();
	submit([this, Handle] { m_pixelShaders.erase(Handle); });
	return D3D_OK;
}

HRESULT Device::SetPixelShaderConstant(DWORD Register, CONST void* pConstantData, DWORD ConstantCount)
{
	if (Register + ConstantCount > 8 || pConstantData == nullptr)
		return D3DERR_INVALIDCALL;
	memcpy(m_front.psConstants[Register], pConstantData, ConstantCount * 16);
	m_psDirtyLo = std::min(m_psDirtyLo, (int)Register);
	m_psDirtyHi = std::max(m_psDirtyHi, (int)(Register + ConstantCount));
	return D3D_OK;
}

HRESULT Device::GetPixelShaderConstant(DWORD Register, void* pConstantData, DWORD ConstantCount)
{
	if (Register + ConstantCount > 8 || pConstantData == nullptr)
		return D3DERR_INVALIDCALL;
	memcpy(pConstantData, m_front.psConstants[Register], ConstantCount * 16);
	return D3D_OK;
}

} // namespace d3d8metal

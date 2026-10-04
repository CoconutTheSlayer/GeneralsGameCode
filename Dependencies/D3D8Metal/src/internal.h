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

// Direct3D 8 on Metal: internal declarations.
//
// Design notes:
// - All interfaces are implemented as plain C++ classes deriving from the
//   DirectX SDK interface declarations.
// - Uncompressed textures live on the GPU as BGRA8; DXT textures as BC1-3.
//   Each lockable resource keeps a CPU copy in its D3D format, so Lock()
//   returns memory with exactly the layout the game expects.
// - Uploads are ordered against GPU work: a resource that may still be read
//   by an in-flight command buffer is updated through a blit in the command
//   stream (textures) or by renaming the underlying MTLBuffer (buffers).
// - The fixed function pipeline is emulated by Metal shaders generated from
//   the current render/texture stage state and cached by state key.

#pragma once

#import <Metal/Metal.h>
#import <QuartzCore/CAMetalLayer.h>

#include <d3d8.h>

#include <atomic>
#include <map>
#include <memory>
#include <string>
#include <unordered_map>
#include <vector>

#include "formats.h"
#include "shadergen.h"

struct SDL_Window;

namespace d3d8metal
{

class Device;

//-----------------------------------------------------------------------------
// Reference counting helper for COM style objects.
//-----------------------------------------------------------------------------
template <class Interface>
class ComObject : public Interface
{
public:
	virtual ~ComObject() {}

	STDMETHOD(QueryInterface)(REFIID, void** ppvObj) override
	{
		if (ppvObj == nullptr)
			return E_POINTER;
		*ppvObj = this;
		AddRef();
		return S_OK;
	}
	STDMETHOD_(ULONG, AddRef)() override { return (ULONG)++m_refCount; }
	STDMETHOD_(ULONG, Release)() override
	{
		ULONG count = (ULONG)--m_refCount;
		if (count == 0)
			delete this;
		return count;
	}

protected:
	std::atomic<long> m_refCount { 1 };
};

// Adds the IDirect3DResource8 bookkeeping methods.
template <class Interface>
class ResourceObject : public ComObject<Interface>
{
public:
	explicit ResourceObject(Device* device) : m_device(device) {}

	STDMETHOD(GetDevice)(IDirect3DDevice8** ppDevice) override;
	STDMETHOD(SetPrivateData)(REFGUID, CONST void*, DWORD, DWORD) override { return S_OK; }
	STDMETHOD(GetPrivateData)(REFGUID, void*, DWORD*) override { return E_FAIL; }
	STDMETHOD(FreePrivateData)(REFGUID) override { return S_OK; }

protected:
	Device* m_device;
};

//-----------------------------------------------------------------------------
// GPU texture storage shared by textures, cube textures and standalone surfaces.
//-----------------------------------------------------------------------------
struct TextureStorage
{
	~TextureStorage();

	id<MTLTexture> texture = nil;
	D3DFORMAT format = D3DFMT_UNKNOWN;
	unsigned width = 0;
	unsigned height = 0;
	unsigned levels = 1;
	unsigned faces = 1;
	DWORD usage = 0;
	D3DPOOL pool = D3DPOOL_MANAGED;
	bool renderTarget = false;
	bool depthStencil = false;

	// CPU copies in the D3D format, indexed by face * levels + level. Allocated on demand.
	std::vector<std::vector<uint8_t>> shadows;
	// True when the GPU content is newer than the shadow (render targets).
	bool shadowStale = false;

	// Command buffer serial that last referenced this texture.
	uint64_t lastUsedSerial = 0;

	unsigned levelWidth(unsigned level) const { return std::max(1u, width >> level); }
	unsigned levelHeight(unsigned level) const { return std::max(1u, height >> level); }
	std::vector<uint8_t>& shadow(unsigned face, unsigned level);
};

class Surface;

//-----------------------------------------------------------------------------
// Textures
//-----------------------------------------------------------------------------
class Texture : public ResourceObject<IDirect3DTexture8>
{
public:
	Texture(Device* device, std::shared_ptr<TextureStorage> storage);
	~Texture() override;

	STDMETHOD_(DWORD, SetPriority)(DWORD) override { return 0; }
	STDMETHOD_(DWORD, GetPriority)() override { return 0; }
	STDMETHOD_(void, PreLoad)() override {}
	STDMETHOD_(D3DRESOURCETYPE, GetType)() override { return D3DRTYPE_TEXTURE; }
	STDMETHOD_(DWORD, SetLOD)(DWORD) override { return 0; }
	STDMETHOD_(DWORD, GetLOD)() override { return 0; }
	STDMETHOD_(DWORD, GetLevelCount)() override { return m_storage->levels; }
	STDMETHOD(GetLevelDesc)(UINT Level, D3DSURFACE_DESC* pDesc) override;
	STDMETHOD(GetSurfaceLevel)(UINT Level, IDirect3DSurface8** ppSurfaceLevel) override;
	STDMETHOD(LockRect)(UINT Level, D3DLOCKED_RECT* pLockedRect, CONST RECT* pRect, DWORD Flags) override;
	STDMETHOD(UnlockRect)(UINT Level) override;
	STDMETHOD(AddDirtyRect)(CONST RECT*) override { return S_OK; }

	std::shared_ptr<TextureStorage> m_storage;
	std::vector<Surface*> m_surfaces;
};

class CubeTexture : public ResourceObject<IDirect3DCubeTexture8>
{
public:
	CubeTexture(Device* device, std::shared_ptr<TextureStorage> storage);
	~CubeTexture() override;

	STDMETHOD_(DWORD, SetPriority)(DWORD) override { return 0; }
	STDMETHOD_(DWORD, GetPriority)() override { return 0; }
	STDMETHOD_(void, PreLoad)() override {}
	STDMETHOD_(D3DRESOURCETYPE, GetType)() override { return D3DRTYPE_CUBETEXTURE; }
	STDMETHOD_(DWORD, SetLOD)(DWORD) override { return 0; }
	STDMETHOD_(DWORD, GetLOD)() override { return 0; }
	STDMETHOD_(DWORD, GetLevelCount)() override { return m_storage->levels; }
	STDMETHOD(GetLevelDesc)(UINT Level, D3DSURFACE_DESC* pDesc) override;
	STDMETHOD(GetCubeMapSurface)(D3DCUBEMAP_FACES FaceType, UINT Level, IDirect3DSurface8** ppCubeMapSurface) override;
	STDMETHOD(LockRect)(D3DCUBEMAP_FACES FaceType, UINT Level, D3DLOCKED_RECT* pLockedRect, CONST RECT* pRect, DWORD Flags) override;
	STDMETHOD(UnlockRect)(D3DCUBEMAP_FACES FaceType, UINT Level) override;
	STDMETHOD(AddDirtyRect)(D3DCUBEMAP_FACES, CONST RECT*) override { return S_OK; }

	std::shared_ptr<TextureStorage> m_storage;
	std::vector<Surface*> m_surfaces;
};

// Volume textures are not used by the game's renderer; creation fails cleanly.

//-----------------------------------------------------------------------------
// Surfaces
//-----------------------------------------------------------------------------
class Surface : public ResourceObject<IDirect3DSurface8>
{
public:
	// Standalone surface (image surface, render target, depth stencil, back buffer).
	Surface(Device* device, std::shared_ptr<TextureStorage> storage);
	// Surface owned by a texture; reference counting forwards to the container.
	Surface(Device* device, IUnknown* container, std::shared_ptr<TextureStorage> storage, unsigned face, unsigned level);

	STDMETHOD_(ULONG, AddRef)() override;
	STDMETHOD_(ULONG, Release)() override;
	STDMETHOD(GetContainer)(REFIID riid, void** ppContainer) override;
	STDMETHOD(GetDesc)(D3DSURFACE_DESC* pDesc) override;
	STDMETHOD(LockRect)(D3DLOCKED_RECT* pLockedRect, CONST RECT* pRect, DWORD Flags) override;
	STDMETHOD(UnlockRect)() override;

	unsigned width() const { return m_storage->levelWidth(m_level); }
	unsigned height() const { return m_storage->levelHeight(m_level); }

	std::shared_ptr<TextureStorage> m_storage;
	IUnknown* m_container = nullptr;
	unsigned m_face = 0;
	unsigned m_level = 0;

	// Lock bookkeeping
	RECT m_lockRect {};
	DWORD m_lockFlags = 0;
	bool m_locked = false;
};

//-----------------------------------------------------------------------------
// Buffers
//-----------------------------------------------------------------------------
struct BufferStorage
{
	id<MTLBuffer> buffer = nil;
	unsigned length = 0;
	DWORD usage = 0;
	uint64_t lastUsedSerial = 0;
	bool writtenSinceUse = false;
};

class VertexBuffer : public ResourceObject<IDirect3DVertexBuffer8>
{
public:
	VertexBuffer(Device* device, unsigned length, DWORD usage, DWORD fvf, D3DPOOL pool);
	~VertexBuffer() override;

	STDMETHOD_(DWORD, SetPriority)(DWORD) override { return 0; }
	STDMETHOD_(DWORD, GetPriority)() override { return 0; }
	STDMETHOD_(void, PreLoad)() override {}
	STDMETHOD_(D3DRESOURCETYPE, GetType)() override { return D3DRTYPE_VERTEXBUFFER; }
	STDMETHOD(Lock)(UINT OffsetToLock, UINT SizeToLock, BYTE** ppbData, DWORD Flags) override;
	STDMETHOD(Unlock)() override { return S_OK; }
	STDMETHOD(GetDesc)(D3DVERTEXBUFFER_DESC* pDesc) override;

	BufferStorage m_storage;
	DWORD m_fvf;
	D3DPOOL m_pool;
};

class IndexBuffer : public ResourceObject<IDirect3DIndexBuffer8>
{
public:
	IndexBuffer(Device* device, unsigned length, DWORD usage, D3DFORMAT format, D3DPOOL pool);
	~IndexBuffer() override;

	STDMETHOD_(DWORD, SetPriority)(DWORD) override { return 0; }
	STDMETHOD_(DWORD, GetPriority)() override { return 0; }
	STDMETHOD_(void, PreLoad)() override {}
	STDMETHOD_(D3DRESOURCETYPE, GetType)() override { return D3DRTYPE_INDEXBUFFER; }
	STDMETHOD(Lock)(UINT OffsetToLock, UINT SizeToLock, BYTE** ppbData, DWORD Flags) override;
	STDMETHOD(Unlock)() override { return S_OK; }
	STDMETHOD(GetDesc)(D3DINDEXBUFFER_DESC* pDesc) override;

	BufferStorage m_storage;
	D3DFORMAT m_format;
	D3DPOOL m_pool;
};

class SwapChain : public ComObject<IDirect3DSwapChain8>
{
public:
	explicit SwapChain(Device* device) : m_device(device) {}
	STDMETHOD(Present)(CONST RECT*, CONST RECT*, HWND, CONST RGNDATA*) override;
	STDMETHOD(GetBackBuffer)(UINT BackBuffer, D3DBACKBUFFER_TYPE Type, IDirect3DSurface8** ppBackBuffer) override;
	Device* m_device;
};

//-----------------------------------------------------------------------------
// IDirect3D8
//-----------------------------------------------------------------------------
class Direct3D : public ComObject<IDirect3D8>
{
public:
	Direct3D();
	~Direct3D() override;

	STDMETHOD(RegisterSoftwareDevice)(void*) override { return D3DERR_NOTAVAILABLE; }
	STDMETHOD_(UINT, GetAdapterCount)() override { return 1; }
	STDMETHOD(GetAdapterIdentifier)(UINT Adapter, DWORD Flags, D3DADAPTER_IDENTIFIER8* pIdentifier) override;
	STDMETHOD_(UINT, GetAdapterModeCount)(UINT Adapter) override;
	STDMETHOD(EnumAdapterModes)(UINT Adapter, UINT Mode, D3DDISPLAYMODE* pMode) override;
	STDMETHOD(GetAdapterDisplayMode)(UINT Adapter, D3DDISPLAYMODE* pMode) override;
	STDMETHOD(CheckDeviceType)(UINT, D3DDEVTYPE, D3DFORMAT, D3DFORMAT, BOOL) override;
	STDMETHOD(CheckDeviceFormat)(UINT, D3DDEVTYPE, D3DFORMAT, DWORD Usage, D3DRESOURCETYPE RType, D3DFORMAT CheckFormat) override;
	STDMETHOD(CheckDeviceMultiSampleType)(UINT, D3DDEVTYPE, D3DFORMAT, BOOL, D3DMULTISAMPLE_TYPE MultiSampleType) override;
	STDMETHOD(CheckDepthStencilMatch)(UINT, D3DDEVTYPE, D3DFORMAT, D3DFORMAT, D3DFORMAT) override;
	STDMETHOD(GetDeviceCaps)(UINT Adapter, D3DDEVTYPE DeviceType, D3DCAPS8* pCaps) override;
	STDMETHOD_(HMONITOR, GetAdapterMonitor)(UINT) override { return (HMONITOR)(uintptr_t)1; }
	STDMETHOD(CreateDevice)(UINT Adapter, D3DDEVTYPE DeviceType, HWND hFocusWindow, DWORD BehaviorFlags, D3DPRESENT_PARAMETERS* pPresentationParameters, IDirect3DDevice8** ppReturnedDeviceInterface) override;

	id<MTLDevice> m_mtlDevice = nil;
	std::vector<D3DDISPLAYMODE> m_modes;
};

void FillCaps(D3DCAPS8* caps);

//-----------------------------------------------------------------------------
// Device state
//-----------------------------------------------------------------------------
enum { MAX_STAGES = 8, MAX_LIGHTS = 8, MAX_STREAMS = 4, MAX_CLIP_PLANES = 6 };
// Texture stages the emulated GeForce2 class card has. Like the hardware, stages past these are
// ignored, so states the game leaves behind in higher stages have no effect.
enum { EMULATED_STAGES = 2 };

struct StreamSource
{
	VertexBuffer* buffer = nullptr;
	UINT stride = 0;
};

struct DeviceState
{
	DWORD renderStates[256];
	DWORD stageStates[MAX_STAGES][32];
	D3DMATRIX transforms[512];
	D3DVIEWPORT8 viewport {};
	D3DMATERIAL8 material {};
	D3DLIGHT8 lights[MAX_LIGHTS] {};
	bool lightEnabled[MAX_LIGHTS] {};
	float clipPlanes[MAX_CLIP_PLANES][4] {};
	IDirect3DBaseTexture8* textures[MAX_STAGES] {};
	StreamSource streams[MAX_STREAMS] {};
	IndexBuffer* indices = nullptr;
	UINT baseVertexIndex = 0;
	DWORD vertexShader = 0; // FVF code or shader handle
	DWORD pixelShader = 0;
	float vsConstants[96][4] {};
	float psConstants[8][4] {};
};

struct VertexShaderObject
{
	std::vector<DWORD> declaration;
	std::vector<DWORD> function;
	DWORD fvf = 0; // FVF equivalent of the declaration, when it has one
};

struct PixelShaderObject
{
	std::vector<DWORD> function;
};

//-----------------------------------------------------------------------------
// IDirect3DDevice8
//-----------------------------------------------------------------------------
class Device : public ComObject<IDirect3DDevice8>
{
public:
	Device(Direct3D* d3d, HWND window, DWORD behaviorFlags, D3DPRESENT_PARAMETERS* params);
	~Device() override;

	bool initialize();

	STDMETHOD(TestCooperativeLevel)() override { return D3D_OK; }
	STDMETHOD_(UINT, GetAvailableTextureMem)() override { return 512u * 1024u * 1024u; }
	STDMETHOD(ResourceManagerDiscardBytes)(DWORD) override { return D3D_OK; }
	STDMETHOD(GetDirect3D)(IDirect3D8** ppD3D8) override;
	STDMETHOD(GetDeviceCaps)(D3DCAPS8* pCaps) override;
	STDMETHOD(GetDisplayMode)(D3DDISPLAYMODE* pMode) override;
	STDMETHOD(GetCreationParameters)(D3DDEVICE_CREATION_PARAMETERS* pParameters) override;
	STDMETHOD(SetCursorProperties)(UINT XHotSpot, UINT YHotSpot, IDirect3DSurface8* pCursorBitmap) override;
	STDMETHOD_(void, SetCursorPosition)(UINT, UINT, DWORD) override {}
	STDMETHOD_(BOOL, ShowCursor)(BOOL bShow) override;
	STDMETHOD(CreateAdditionalSwapChain)(D3DPRESENT_PARAMETERS*, IDirect3DSwapChain8** pSwapChain) override;
	STDMETHOD(Reset)(D3DPRESENT_PARAMETERS* pPresentationParameters) override;
	STDMETHOD(Present)(CONST RECT* pSourceRect, CONST RECT* pDestRect, HWND hDestWindowOverride, CONST RGNDATA* pDirtyRegion) override;
	STDMETHOD(GetBackBuffer)(UINT BackBuffer, D3DBACKBUFFER_TYPE Type, IDirect3DSurface8** ppBackBuffer) override;
	STDMETHOD(GetRasterStatus)(D3DRASTER_STATUS* pRasterStatus) override;
	STDMETHOD_(void, SetGammaRamp)(DWORD Flags, CONST D3DGAMMARAMP* pRamp) override;
	STDMETHOD_(void, GetGammaRamp)(D3DGAMMARAMP* pRamp) override;
	STDMETHOD(CreateTexture)(UINT Width, UINT Height, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DTexture8** ppTexture) override;
	STDMETHOD(CreateVolumeTexture)(UINT, UINT, UINT, UINT, DWORD, D3DFORMAT, D3DPOOL, IDirect3DVolumeTexture8** ppVolumeTexture) override;
	STDMETHOD(CreateCubeTexture)(UINT EdgeLength, UINT Levels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DCubeTexture8** ppCubeTexture) override;
	STDMETHOD(CreateVertexBuffer)(UINT Length, DWORD Usage, DWORD FVF, D3DPOOL Pool, IDirect3DVertexBuffer8** ppVertexBuffer) override;
	STDMETHOD(CreateIndexBuffer)(UINT Length, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, IDirect3DIndexBuffer8** ppIndexBuffer) override;
	STDMETHOD(CreateRenderTarget)(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, BOOL Lockable, IDirect3DSurface8** ppSurface) override;
	STDMETHOD(CreateDepthStencilSurface)(UINT Width, UINT Height, D3DFORMAT Format, D3DMULTISAMPLE_TYPE MultiSample, IDirect3DSurface8** ppSurface) override;
	STDMETHOD(CreateImageSurface)(UINT Width, UINT Height, D3DFORMAT Format, IDirect3DSurface8** ppSurface) override;
	STDMETHOD(CopyRects)(IDirect3DSurface8* pSourceSurface, CONST RECT* pSourceRectsArray, UINT cRects, IDirect3DSurface8* pDestinationSurface, CONST POINT* pDestPointsArray) override;
	STDMETHOD(UpdateTexture)(IDirect3DBaseTexture8* pSourceTexture, IDirect3DBaseTexture8* pDestinationTexture) override;
	STDMETHOD(GetFrontBuffer)(IDirect3DSurface8* pDestSurface) override;
	STDMETHOD(SetRenderTarget)(IDirect3DSurface8* pRenderTarget, IDirect3DSurface8* pNewZStencil) override;
	STDMETHOD(GetRenderTarget)(IDirect3DSurface8** ppRenderTarget) override;
	STDMETHOD(GetDepthStencilSurface)(IDirect3DSurface8** ppZStencilSurface) override;
	STDMETHOD(BeginScene)() override { return D3D_OK; }
	STDMETHOD(EndScene)() override { return D3D_OK; }
	STDMETHOD(Clear)(DWORD Count, CONST D3DRECT* pRects, DWORD Flags, D3DCOLOR Color, float Z, DWORD Stencil) override;
	STDMETHOD(SetTransform)(D3DTRANSFORMSTATETYPE State, CONST D3DMATRIX* pMatrix) override;
	STDMETHOD(GetTransform)(D3DTRANSFORMSTATETYPE State, D3DMATRIX* pMatrix) override;
	STDMETHOD(MultiplyTransform)(D3DTRANSFORMSTATETYPE, CONST D3DMATRIX*) override;
	STDMETHOD(SetViewport)(CONST D3DVIEWPORT8* pViewport) override;
	STDMETHOD(GetViewport)(D3DVIEWPORT8* pViewport) override;
	STDMETHOD(SetMaterial)(CONST D3DMATERIAL8* pMaterial) override;
	STDMETHOD(GetMaterial)(D3DMATERIAL8* pMaterial) override;
	STDMETHOD(SetLight)(DWORD Index, CONST D3DLIGHT8*) override;
	STDMETHOD(GetLight)(DWORD Index, D3DLIGHT8*) override;
	STDMETHOD(LightEnable)(DWORD Index, BOOL Enable) override;
	STDMETHOD(GetLightEnable)(DWORD Index, BOOL* pEnable) override;
	STDMETHOD(SetClipPlane)(DWORD Index, CONST float* pPlane) override;
	STDMETHOD(GetClipPlane)(DWORD Index, float* pPlane) override;
	STDMETHOD(SetRenderState)(D3DRENDERSTATETYPE State, DWORD Value) override;
	STDMETHOD(GetRenderState)(D3DRENDERSTATETYPE State, DWORD* pValue) override;
	STDMETHOD(BeginStateBlock)() override;
	STDMETHOD(EndStateBlock)(DWORD* pToken) override;
	STDMETHOD(ApplyStateBlock)(DWORD Token) override;
	STDMETHOD(CaptureStateBlock)(DWORD Token) override;
	STDMETHOD(DeleteStateBlock)(DWORD Token) override;
	STDMETHOD(CreateStateBlock)(D3DSTATEBLOCKTYPE Type, DWORD* pToken) override;
	STDMETHOD(SetClipStatus)(CONST D3DCLIPSTATUS8*) override { return D3D_OK; }
	STDMETHOD(GetClipStatus)(D3DCLIPSTATUS8* pClipStatus) override;
	STDMETHOD(GetTexture)(DWORD Stage, IDirect3DBaseTexture8** ppTexture) override;
	STDMETHOD(SetTexture)(DWORD Stage, IDirect3DBaseTexture8* pTexture) override;
	STDMETHOD(GetTextureStageState)(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD* pValue) override;
	STDMETHOD(SetTextureStageState)(DWORD Stage, D3DTEXTURESTAGESTATETYPE Type, DWORD Value) override;
	STDMETHOD(ValidateDevice)(DWORD* pNumPasses) override;
	STDMETHOD(GetInfo)(DWORD, void*, DWORD) override { return S_FALSE; }
	STDMETHOD(SetPaletteEntries)(UINT, CONST PALETTEENTRY*) override { return D3D_OK; }
	STDMETHOD(GetPaletteEntries)(UINT, PALETTEENTRY*) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(SetCurrentTexturePalette)(UINT) override { return D3D_OK; }
	STDMETHOD(GetCurrentTexturePalette)(UINT* PaletteNumber) override;
	STDMETHOD(DrawPrimitive)(D3DPRIMITIVETYPE PrimitiveType, UINT StartVertex, UINT PrimitiveCount) override;
	STDMETHOD(DrawIndexedPrimitive)(D3DPRIMITIVETYPE, UINT minIndex, UINT NumVertices, UINT startIndex, UINT primCount) override;
	STDMETHOD(DrawPrimitiveUP)(D3DPRIMITIVETYPE PrimitiveType, UINT PrimitiveCount, CONST void* pVertexStreamZeroData, UINT VertexStreamZeroStride) override;
	STDMETHOD(DrawIndexedPrimitiveUP)(D3DPRIMITIVETYPE PrimitiveType, UINT MinVertexIndex, UINT NumVertexIndices, UINT PrimitiveCount, CONST void* pIndexData, D3DFORMAT IndexDataFormat, CONST void* pVertexStreamZeroData, UINT VertexStreamZeroStride) override;
	STDMETHOD(ProcessVertices)(UINT, UINT, UINT, IDirect3DVertexBuffer8*, DWORD) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(CreateVertexShader)(CONST DWORD* pDeclaration, CONST DWORD* pFunction, DWORD* pHandle, DWORD Usage) override;
	STDMETHOD(SetVertexShader)(DWORD Handle) override;
	STDMETHOD(GetVertexShader)(DWORD* pHandle) override;
	STDMETHOD(DeleteVertexShader)(DWORD Handle) override;
	STDMETHOD(SetVertexShaderConstant)(DWORD Register, CONST void* pConstantData, DWORD ConstantCount) override;
	STDMETHOD(GetVertexShaderConstant)(DWORD Register, void* pConstantData, DWORD ConstantCount) override;
	STDMETHOD(GetVertexShaderDeclaration)(DWORD, void*, DWORD*) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(GetVertexShaderFunction)(DWORD, void*, DWORD*) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(SetStreamSource)(UINT StreamNumber, IDirect3DVertexBuffer8* pStreamData, UINT Stride) override;
	STDMETHOD(GetStreamSource)(UINT StreamNumber, IDirect3DVertexBuffer8** ppStreamData, UINT* pStride) override;
	STDMETHOD(SetIndices)(IDirect3DIndexBuffer8* pIndexData, UINT BaseVertexIndex) override;
	STDMETHOD(GetIndices)(IDirect3DIndexBuffer8** ppIndexData, UINT* pBaseVertexIndex) override;
	STDMETHOD(CreatePixelShader)(CONST DWORD* pFunction, DWORD* pHandle) override;
	STDMETHOD(SetPixelShader)(DWORD Handle) override;
	STDMETHOD(GetPixelShader)(DWORD* pHandle) override;
	STDMETHOD(DeletePixelShader)(DWORD Handle) override;
	STDMETHOD(SetPixelShaderConstant)(DWORD Register, CONST void* pConstantData, DWORD ConstantCount) override;
	STDMETHOD(GetPixelShaderConstant)(DWORD Register, void* pConstantData, DWORD ConstantCount) override;
	STDMETHOD(GetPixelShaderFunction)(DWORD, void*, DWORD*) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(DrawRectPatch)(UINT, CONST float*, CONST D3DRECTPATCH_INFO*) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(DrawTriPatch)(UINT, CONST float*, CONST D3DTRIPATCH_INFO*) override { return D3DERR_INVALIDCALL; }
	STDMETHOD(DeletePatch)(UINT) override { return D3DERR_INVALIDCALL; }

	//-------------------------------------------------------------------------
	// Internal interface used by resources
	//-------------------------------------------------------------------------
	id<MTLDevice> mtlDevice() const { return m_mtlDevice; }

	// Serial of the command buffer currently being recorded.
	uint64_t currentSerial() const { return m_currentSerial; }
	// True if the GPU may still access a resource last used at serial.
	bool isInFlight(uint64_t serial) const { return serial >= m_completedSerial.load() + 1 && serial != 0; }

	std::shared_ptr<TextureStorage> createStorage(unsigned width, unsigned height, unsigned levels, unsigned faces, DWORD usage, D3DFORMAT format, D3DPOOL pool);
	// Uploads a region of a texture level from CPU memory in the D3D format.
	void uploadTexture(TextureStorage& storage, unsigned face, unsigned level, const RECT& rect);
	// Copies GPU content of a texture level into its CPU shadow (render targets).
	void readbackTexture(TextureStorage& storage, unsigned face, unsigned level);
	// Returns a fresh MTLBuffer for renaming, recycling retired ones.
	id<MTLBuffer> acquireBuffer(unsigned length);
	void retireBuffer(id<MTLBuffer> buffer, uint64_t serial);

private:
	friend class SwapChain;

	struct Transient
	{
		id<MTLBuffer> buffer;
		NSUInteger offset;
		void* cpu;
	};

	void resetState();
	bool createSwapChainResources();
	void applyPresentationParameters();
	id<MTLCommandBuffer> commandBuffer();
	id<MTLRenderCommandEncoder> renderEncoder();
	void endRenderEncoder();
	id<MTLTexture> activeDepthTexture();
	void flush(bool wait);
	Transient allocTransient(NSUInteger length, NSUInteger alignment = 16);
	void beginDraw(D3DPRIMITIVETYPE type, bool& ok);
	void traceDraw(const ShaderKey& key, D3DPRIMITIVETYPE type) const;
	void writeScreenshotIfRequested();
	bool traceEnabled() const
	{
		static const bool always = getenv("D3D8METAL_TRACE") != nullptr;
		return always || m_traceFrame;
	}
	bool m_traceFrame = false;
	void drawClearQuad(DWORD flags, D3DCOLOR color, float z, DWORD stencil, const MTLScissorRect& rect);
	void markTextureUsed(TextureStorage& storage);
	TextureStorage* stageStorage(DWORD stage) const;
	id<MTLSamplerState> samplerFor(DWORD stage);
	id<MTLRenderPipelineState> pipelineFor(const ShaderKey& key, const VertexLayout& layout, const BlendKey& blend);
	id<MTLDepthStencilState> depthStencilFor();
	void presentToDrawable();
	void updateLetterbox();

	Direct3D* m_d3d;
	HWND m_window;
	SDL_Window* m_sdlWindow = nullptr;
	void* m_metalView = nullptr;
	CAMetalLayer* m_layer = nil;
	DWORD m_behaviorFlags;
	D3DPRESENT_PARAMETERS m_params;

	id<MTLDevice> m_mtlDevice = nil;
	id<MTLCommandQueue> m_queue = nil;
	id<MTLCommandBuffer> m_commandBuffer = nil;
	id<MTLRenderCommandEncoder> m_encoder = nil;
	dispatch_semaphore_t m_frameSemaphore;
	uint64_t m_currentSerial = 1;
	std::atomic<uint64_t> m_completedSerial { 0 };

	// Transient upload ring for UP draws and generated indices.
	std::vector<id<MTLBuffer>> m_transientBuffers;
	id<MTLBuffer> m_transientCurrent = nil;
	NSUInteger m_transientOffset = 0;
	std::vector<std::pair<uint64_t, id<MTLBuffer>>> m_retiredTransient;
	std::vector<std::pair<uint64_t, id<MTLBuffer>>> m_retiredBuffers;

	Surface* m_backBuffer = nullptr;
	Surface* m_depthBuffer = nullptr;
	Surface* m_renderTarget = nullptr;
	Surface* m_depthStencil = nullptr;

	// Pending clears for the next render pass.
	DWORD m_pendingClearFlags = 0;
	MTLClearColor m_pendingClearColor {};
	float m_pendingClearDepth = 1.0f;
	DWORD m_pendingClearStencil = 0;

	DeviceState m_state;
	bool m_recordingStateBlock = false;
	std::map<DWORD, DeviceState> m_stateBlocks;
	DWORD m_nextStateBlock = 1;

	std::map<DWORD, VertexShaderObject> m_vertexShaders;
	std::map<DWORD, PixelShaderObject> m_pixelShaders;
	DWORD m_nextShaderHandle = 1;

	D3DGAMMARAMP m_gammaRamp {};

	// Caches
	std::unordered_map<uint64_t, id<MTLRenderPipelineState>> m_pipelines;
	std::unordered_map<uint64_t, id<MTLFunction>> m_vertexFunctions;
	std::unordered_map<uint64_t, id<MTLFunction>> m_fragmentFunctions;
	std::unordered_map<uint64_t, id<MTLDepthStencilState>> m_depthStates;
	std::unordered_map<uint64_t, id<MTLSamplerState>> m_samplers;
	std::unordered_map<uint64_t, id<MTLTexture>> m_scratchDepth;
	id<MTLRenderPipelineState> m_presentPipeline = nil;
	id<MTLRenderPipelineState> m_clearPipelines[16] {};
	id<MTLDepthStencilState> m_clearDepthStates[4] {};
	id<MTLTexture> m_whiteTexture = nil;
	id<MTLTexture> m_whiteCube = nil;
	id<MTLSamplerState> m_presentSampler = nil;

	// Letterboxed presentation rectangle in drawable pixels.
	MTLViewport m_presentViewport {};

	bool m_cursorVisible = true;
};

Device* CurrentDevice();

} // namespace d3d8metal

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

// IDirect3D8: adapter enumeration and device capabilities.

#include "internal.h"

#include <SDL3/SDL.h>

#include <algorithm>

extern "C" IDirect3D8* WINAPI Direct3DCreate8(UINT SDKVersion)
{
	(void)SDKVersion;
	d3d8metal::Direct3D* d3d = new d3d8metal::Direct3D();
	if (d3d->m_mtlDevice == nil)
	{
		d3d->Release();
		return nullptr;
	}
	return d3d;
}

namespace d3d8metal
{

// The renderer identifies as a GeForce2 class card without programmable
// shaders, which routes the game through its fixed function code paths.
static const DWORD kVendorId = 0x10DE;   // NVIDIA
static const DWORD kDeviceId = 0x0150;   // GeForce2 GTS

Direct3D::Direct3D()
{
	m_mtlDevice = MTLCreateSystemDefaultDevice();

	SDL_InitSubSystem(SDL_INIT_VIDEO);
	int nativeW = 1920, nativeH = 1080, pointsW = 0, pointsH = 0;
	UINT refresh = 60;
	if (const SDL_DisplayMode* mode = SDL_GetDesktopDisplayMode(SDL_GetPrimaryDisplay()))
	{
		nativeW = (int)(mode->w * mode->pixel_density);
		nativeH = (int)(mode->h * mode->pixel_density);
		pointsW = mode->w;
		pointsH = mode->h;
		if (mode->refresh_rate >= 30.0f)
			refresh = (UINT)(mode->refresh_rate + 0.5f);
	}

	static const int kSizes[][2] = {
		{ 800, 600 }, { 1024, 768 }, { 1152, 864 }, { 1280, 720 }, { 1280, 800 }, { 1280, 960 }, { 1280, 1024 },
		{ 1366, 768 }, { 1440, 900 }, { 1600, 900 }, { 1600, 1200 }, { 1680, 1050 }, { 1920, 1080 }, { 1920, 1200 },
		{ 2560, 1080 }, { 2560, 1440 }, { 2560, 1600 }, { 3440, 1440 }, { 3840, 2160 },
	};
	std::vector<std::pair<int, int>> sizes;
	for (const auto& s : kSizes)
	{
		if (s[0] <= nativeW && s[1] <= nativeH)
			sizes.push_back({ s[0], s[1] });
	}
	// The desktop size in points is the default resolution on macOS, so it must be a valid mode.
	if (pointsW >= 800 && pointsH >= 600 && std::find(sizes.begin(), sizes.end(), std::make_pair(pointsW, pointsH)) == sizes.end())
		sizes.push_back({ pointsW, pointsH });
	if (std::find(sizes.begin(), sizes.end(), std::make_pair(nativeW, nativeH)) == sizes.end())
		sizes.push_back({ nativeW, nativeH });
	std::sort(sizes.begin(), sizes.end());

	for (D3DFORMAT format : { D3DFMT_R5G6B5, D3DFMT_X8R8G8B8 })
	{
		for (const auto& s : sizes)
		{
			D3DDISPLAYMODE m;
			m.Width = (UINT)s.first;
			m.Height = (UINT)s.second;
			m.RefreshRate = refresh;
			m.Format = format;
			m_modes.push_back(m);
		}
	}
}

Direct3D::~Direct3D()
{
	m_mtlDevice = nil;
}

HRESULT Direct3D::GetAdapterIdentifier(UINT Adapter, DWORD, D3DADAPTER_IDENTIFIER8* id)
{
	if (Adapter != 0 || id == nullptr)
		return D3DERR_INVALIDCALL;
	memset(id, 0, sizeof(*id));
	strlcpy(id->Driver, "d3d8metal", sizeof(id->Driver));
	NSString* name = [m_mtlDevice name];
	snprintf(id->Description, sizeof(id->Description), "%s (Metal)", name ? [name UTF8String] : "Apple GPU");
	id->DriverVersion.HighPart = (6 << 16) | 14;
	id->DriverVersion.LowPart = (10 << 16) | 9999;
	id->VendorId = kVendorId;
	id->DeviceId = kDeviceId;
	id->SubSysId = 0;
	id->Revision = 0;
	id->WHQLLevel = 1;
	return D3D_OK;
}

UINT Direct3D::GetAdapterModeCount(UINT Adapter)
{
	return Adapter == 0 ? (UINT)m_modes.size() : 0;
}

HRESULT Direct3D::EnumAdapterModes(UINT Adapter, UINT Mode, D3DDISPLAYMODE* pMode)
{
	if (Adapter != 0 || Mode >= m_modes.size() || pMode == nullptr)
		return D3DERR_INVALIDCALL;
	*pMode = m_modes[Mode];
	return D3D_OK;
}

HRESULT Direct3D::GetAdapterDisplayMode(UINT Adapter, D3DDISPLAYMODE* pMode)
{
	if (Adapter != 0 || pMode == nullptr)
		return D3DERR_INVALIDCALL;
	*pMode = m_modes.back();
	pMode->Format = D3DFMT_X8R8G8B8;
	return D3D_OK;
}

HRESULT Direct3D::CheckDeviceType(UINT, D3DDEVTYPE type, D3DFORMAT, D3DFORMAT, BOOL)
{
	return type == D3DDEVTYPE_HAL ? D3D_OK : D3DERR_NOTAVAILABLE;
}

HRESULT Direct3D::CheckDeviceFormat(UINT, D3DDEVTYPE, D3DFORMAT, DWORD Usage, D3DRESOURCETYPE RType, D3DFORMAT CheckFormat)
{
	if (Usage & D3DUSAGE_DEPTHSTENCIL)
		return IsDepthFormat(CheckFormat) ? D3D_OK : D3DERR_NOTAVAILABLE;
	if (RType == D3DRTYPE_VOLUMETEXTURE)
		return D3DERR_NOTAVAILABLE;
	if (Usage & D3DUSAGE_RENDERTARGET)
	{
		switch (CheckFormat)
		{
		case D3DFMT_A8R8G8B8:
		case D3DFMT_X8R8G8B8:
		case D3DFMT_R5G6B5:
			return D3D_OK;
		default:
			return D3DERR_NOTAVAILABLE;
		}
	}
	switch (CheckFormat)
	{
	case D3DFMT_A8R8G8B8:
	case D3DFMT_X8R8G8B8:
	case D3DFMT_R8G8B8:
	case D3DFMT_R5G6B5:
	case D3DFMT_X1R5G5B5:
	case D3DFMT_A1R5G5B5:
	case D3DFMT_A4R4G4B4:
	case D3DFMT_X4R4G4B4:
	case D3DFMT_A8:
	case D3DFMT_L8:
	case D3DFMT_A8L8:
	case D3DFMT_A4L4:
	case D3DFMT_DXT1:
	case D3DFMT_DXT2:
	case D3DFMT_DXT3:
	case D3DFMT_DXT4:
	case D3DFMT_DXT5:
		return D3D_OK;
	default:
		return D3DERR_NOTAVAILABLE;
	}
}

HRESULT Direct3D::CheckDeviceMultiSampleType(UINT, D3DDEVTYPE, D3DFORMAT, BOOL, D3DMULTISAMPLE_TYPE MultiSampleType)
{
	return MultiSampleType == D3DMULTISAMPLE_NONE ? D3D_OK : D3DERR_NOTAVAILABLE;
}

HRESULT Direct3D::CheckDepthStencilMatch(UINT, D3DDEVTYPE, D3DFORMAT, D3DFORMAT, D3DFORMAT)
{
	return D3D_OK;
}

void FillCaps(D3DCAPS8* caps)
{
	memset(caps, 0, sizeof(*caps));
	caps->DeviceType = D3DDEVTYPE_HAL;
	caps->AdapterOrdinal = 0;
	caps->Caps = 0;
	caps->Caps2 = D3DCAPS2_CANRENDERWINDOWED | D3DCAPS2_FULLSCREENGAMMA | D3DCAPS2_DYNAMICTEXTURES;
	caps->Caps3 = 0;
	caps->PresentationIntervals = D3DPRESENT_INTERVAL_IMMEDIATE | D3DPRESENT_INTERVAL_ONE;
	caps->CursorCaps = D3DCURSORCAPS_COLOR;
	caps->DevCaps = D3DDEVCAPS_EXECUTESYSTEMMEMORY | D3DDEVCAPS_EXECUTEVIDEOMEMORY | D3DDEVCAPS_TLVERTEXSYSTEMMEMORY | D3DDEVCAPS_TLVERTEXVIDEOMEMORY
		| D3DDEVCAPS_TEXTURESYSTEMMEMORY | D3DDEVCAPS_TEXTUREVIDEOMEMORY | D3DDEVCAPS_DRAWPRIMTLVERTEX | D3DDEVCAPS_CANRENDERAFTERFLIP
		| D3DDEVCAPS_TEXTURENONLOCALVIDMEM | D3DDEVCAPS_DRAWPRIMITIVES2 | D3DDEVCAPS_DRAWPRIMITIVES2EX | D3DDEVCAPS_HWTRANSFORMANDLIGHT
		| D3DDEVCAPS_CANBLTSYSTONONLOCAL | D3DDEVCAPS_HWRASTERIZATION | D3DDEVCAPS_PUREDEVICE;
	caps->PrimitiveMiscCaps = D3DPMISCCAPS_MASKZ | D3DPMISCCAPS_CULLNONE | D3DPMISCCAPS_CULLCW | D3DPMISCCAPS_CULLCCW | D3DPMISCCAPS_COLORWRITEENABLE
		| D3DPMISCCAPS_CLIPPLANESCALEDPOINTS | D3DPMISCCAPS_CLIPTLVERTS | D3DPMISCCAPS_TSSARGTEMP | D3DPMISCCAPS_BLENDOP;
	caps->RasterCaps = D3DPRASTERCAPS_DITHER | D3DPRASTERCAPS_ZTEST | D3DPRASTERCAPS_FOGVERTEX | D3DPRASTERCAPS_FOGTABLE | D3DPRASTERCAPS_MIPMAPLODBIAS
		| D3DPRASTERCAPS_ZBIAS | D3DPRASTERCAPS_FOGRANGE | D3DPRASTERCAPS_ANISOTROPY | D3DPRASTERCAPS_WFOG | D3DPRASTERCAPS_ZFOG;
	DWORD cmp = D3DPCMPCAPS_NEVER | D3DPCMPCAPS_LESS | D3DPCMPCAPS_EQUAL | D3DPCMPCAPS_LESSEQUAL | D3DPCMPCAPS_GREATER | D3DPCMPCAPS_NOTEQUAL
		| D3DPCMPCAPS_GREATEREQUAL | D3DPCMPCAPS_ALWAYS;
	caps->ZCmpCaps = cmp;
	caps->AlphaCmpCaps = cmp;
	DWORD blend = D3DPBLENDCAPS_ZERO | D3DPBLENDCAPS_ONE | D3DPBLENDCAPS_SRCCOLOR | D3DPBLENDCAPS_INVSRCCOLOR | D3DPBLENDCAPS_SRCALPHA
		| D3DPBLENDCAPS_INVSRCALPHA | D3DPBLENDCAPS_DESTALPHA | D3DPBLENDCAPS_INVDESTALPHA | D3DPBLENDCAPS_DESTCOLOR | D3DPBLENDCAPS_INVDESTCOLOR
		| D3DPBLENDCAPS_SRCALPHASAT | D3DPBLENDCAPS_BOTHSRCALPHA | D3DPBLENDCAPS_BOTHINVSRCALPHA;
	caps->SrcBlendCaps = blend;
	caps->DestBlendCaps = blend;
	caps->ShadeCaps = D3DPSHADECAPS_COLORGOURAUDRGB | D3DPSHADECAPS_SPECULARGOURAUDRGB | D3DPSHADECAPS_ALPHAGOURAUDBLEND | D3DPSHADECAPS_FOGGOURAUD;
	caps->TextureCaps = D3DPTEXTURECAPS_PERSPECTIVE | D3DPTEXTURECAPS_ALPHA | D3DPTEXTURECAPS_PROJECTED | D3DPTEXTURECAPS_CUBEMAP | D3DPTEXTURECAPS_MIPMAP
		| D3DPTEXTURECAPS_MIPCUBEMAP;
	DWORD filter = D3DPTFILTERCAPS_MINFPOINT | D3DPTFILTERCAPS_MINFLINEAR | D3DPTFILTERCAPS_MINFANISOTROPIC | D3DPTFILTERCAPS_MIPFPOINT
		| D3DPTFILTERCAPS_MIPFLINEAR | D3DPTFILTERCAPS_MAGFPOINT | D3DPTFILTERCAPS_MAGFLINEAR | D3DPTFILTERCAPS_MAGFANISOTROPIC;
	caps->TextureFilterCaps = filter;
	caps->CubeTextureFilterCaps = filter;
	caps->VolumeTextureFilterCaps = 0;
	caps->TextureAddressCaps = D3DPTADDRESSCAPS_WRAP | D3DPTADDRESSCAPS_MIRROR | D3DPTADDRESSCAPS_CLAMP | D3DPTADDRESSCAPS_BORDER | D3DPTADDRESSCAPS_INDEPENDENTUV
		| D3DPTADDRESSCAPS_MIRRORONCE;
	caps->VolumeTextureAddressCaps = 0;
	caps->LineCaps = D3DLINECAPS_TEXTURE | D3DLINECAPS_ZTEST | D3DLINECAPS_BLEND | D3DLINECAPS_ALPHACMP | D3DLINECAPS_FOG;
	caps->MaxTextureWidth = 8192;
	caps->MaxTextureHeight = 8192;
	caps->MaxVolumeExtent = 0;
	caps->MaxTextureRepeat = 8192;
	caps->MaxTextureAspectRatio = 8192;
	caps->MaxAnisotropy = 16;
	caps->MaxVertexW = 1e10f;
	caps->GuardBandLeft = -8192.0f;
	caps->GuardBandTop = -8192.0f;
	caps->GuardBandRight = 8192.0f;
	caps->GuardBandBottom = 8192.0f;
	caps->ExtentsAdjust = 0.0f;
	caps->StencilCaps = D3DSTENCILCAPS_KEEP | D3DSTENCILCAPS_ZERO | D3DSTENCILCAPS_REPLACE | D3DSTENCILCAPS_INCRSAT | D3DSTENCILCAPS_DECRSAT
		| D3DSTENCILCAPS_INVERT | D3DSTENCILCAPS_INCR | D3DSTENCILCAPS_DECR;
	caps->FVFCaps = 8 | D3DFVFCAPS_DONOTSTRIPELEMENTS;
	caps->TextureOpCaps = D3DTEXOPCAPS_DISABLE | D3DTEXOPCAPS_SELECTARG1 | D3DTEXOPCAPS_SELECTARG2 | D3DTEXOPCAPS_MODULATE | D3DTEXOPCAPS_MODULATE2X
		| D3DTEXOPCAPS_MODULATE4X | D3DTEXOPCAPS_ADD | D3DTEXOPCAPS_ADDSIGNED | D3DTEXOPCAPS_ADDSIGNED2X | D3DTEXOPCAPS_SUBTRACT
		| D3DTEXOPCAPS_ADDSMOOTH | D3DTEXOPCAPS_BLENDDIFFUSEALPHA | D3DTEXOPCAPS_BLENDTEXTUREALPHA | D3DTEXOPCAPS_BLENDFACTORALPHA
		| D3DTEXOPCAPS_BLENDTEXTUREALPHAPM | D3DTEXOPCAPS_BLENDCURRENTALPHA | D3DTEXOPCAPS_PREMODULATE | D3DTEXOPCAPS_MODULATEALPHA_ADDCOLOR
		| D3DTEXOPCAPS_MODULATECOLOR_ADDALPHA | D3DTEXOPCAPS_MODULATEINVALPHA_ADDCOLOR | D3DTEXOPCAPS_MODULATEINVCOLOR_ADDALPHA
		| D3DTEXOPCAPS_DOTPRODUCT3 | D3DTEXOPCAPS_MULTIPLYADD | D3DTEXOPCAPS_LERP;
	caps->MaxTextureBlendStages = EMULATED_STAGES;
	caps->MaxSimultaneousTextures = EMULATED_STAGES;
	caps->VertexProcessingCaps = D3DVTXPCAPS_TEXGEN | D3DVTXPCAPS_MATERIALSOURCE7 | D3DVTXPCAPS_DIRECTIONALLIGHTS | D3DVTXPCAPS_POSITIONALLIGHTS
		| D3DVTXPCAPS_LOCALVIEWER;
	caps->MaxActiveLights = 8;
	caps->MaxUserClipPlanes = 6;
	caps->MaxVertexBlendMatrices = 0;
	caps->MaxVertexBlendMatrixIndex = 0;
	caps->MaxPointSize = 64.0f;
	caps->MaxPrimitiveCount = 0xFFFFF;
	caps->MaxVertexIndex = 0xFFFFFF;
	caps->MaxStreams = 4;
	caps->MaxStreamStride = 255;
	caps->VertexShaderVersion = 0;
	caps->MaxVertexShaderConst = 0;
	caps->PixelShaderVersion = 0;
	caps->MaxPixelShaderValue = 1.0f;
}

HRESULT Direct3D::GetDeviceCaps(UINT Adapter, D3DDEVTYPE DeviceType, D3DCAPS8* pCaps)
{
	if (Adapter != 0 || pCaps == nullptr || DeviceType != D3DDEVTYPE_HAL)
		return D3DERR_INVALIDCALL;
	FillCaps(pCaps);
	return D3D_OK;
}

HRESULT Direct3D::CreateDevice(UINT Adapter, D3DDEVTYPE DeviceType, HWND hFocusWindow, DWORD BehaviorFlags, D3DPRESENT_PARAMETERS* params, IDirect3DDevice8** ppDevice)
{
	if (Adapter != 0 || DeviceType != D3DDEVTYPE_HAL || params == nullptr || ppDevice == nullptr)
		return D3DERR_INVALIDCALL;
	HWND window = params->hDeviceWindow ? params->hDeviceWindow : hFocusWindow;
	Device* device = new Device(this, window, BehaviorFlags, params);
	if (!device->initialize())
	{
		device->Release();
		return D3DERR_NOTAVAILABLE;
	}
	*ppDevice = device;
	return D3D_OK;
}

} // namespace d3d8metal

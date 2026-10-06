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

// Direct3D 8 on DXVK (Vulkan). DXVK native is loaded at run time; its window handles are SDL
// windows, so the window handles of the Win32 shim are translated where Direct3D takes them.

#include <d3d8.h>
#include <win32shim.h>

#include <dlfcn.h>
#include <stdio.h>
#include <stdlib.h>
#include <string>

namespace
{
#include "wrappers.inc"

HWND toDxvkWindow(HWND hwnd)
{
	return hwnd ? (HWND)Win32Shim_GetSDLWindow(hwnd) : nullptr;
}

D3DPRESENT_PARAMETERS translate(const D3DPRESENT_PARAMETERS& params)
{
	D3DPRESENT_PARAMETERS out = params;
	out.hDeviceWindow = toDxvkWindow(params.hDeviceWindow);
	return out;
}

class Direct3D8Wrapper;

class Device8Wrapper : public Device8WrapperBase
{
public:
	Device8Wrapper(IDirect3DDevice8* inner, IDirect3D8* d3d) : Device8WrapperBase(inner), m_d3d(d3d) { m_d3d->AddRef(); }
	~Device8Wrapper() override { m_d3d->Release(); }

	STDMETHOD(QueryInterface)(REFIID riid, void** ppvObj) override
	{
		HRESULT hr = m_inner->QueryInterface(riid, ppvObj);
		if (SUCCEEDED(hr) && ppvObj && *ppvObj == m_inner)
		{
			// Hand out the wrapper, not DXVK's device.
			m_inner->Release();
			AddRef();
			*ppvObj = this;
		}
		return hr;
	}
	STDMETHOD_(ULONG, AddRef)() override { return m_inner->AddRef(); }
	STDMETHOD_(ULONG, Release)() override
	{
		ULONG count = m_inner->Release();
		if (count == 0)
			delete this;
		return count;
	}
	STDMETHOD(GetDirect3D)(IDirect3D8** ppD3D8) override
	{
		if (ppD3D8 == nullptr)
			return D3DERR_INVALIDCALL;
		m_d3d->AddRef();
		*ppD3D8 = m_d3d;
		return D3D_OK;
	}
	STDMETHOD(Reset)(D3DPRESENT_PARAMETERS* pPresentationParameters) override
	{
		if (pPresentationParameters == nullptr)
			return m_inner->Reset(nullptr);
		D3DPRESENT_PARAMETERS params = translate(*pPresentationParameters);
		HRESULT hr = m_inner->Reset(&params);
		params.hDeviceWindow = pPresentationParameters->hDeviceWindow;
		*pPresentationParameters = params;
		return hr;
	}
	STDMETHOD(Present)(CONST RECT* pSourceRect, CONST RECT* pDestRect, HWND hDestWindowOverride, CONST RGNDATA* pDirtyRegion) override
	{
		return m_inner->Present(pSourceRect, pDestRect, toDxvkWindow(hDestWindowOverride), pDirtyRegion);
	}
	STDMETHOD(CreateAdditionalSwapChain)(D3DPRESENT_PARAMETERS* pPresentationParameters, IDirect3DSwapChain8** pSwapChain) override
	{
		if (pPresentationParameters == nullptr)
			return D3DERR_INVALIDCALL;
		D3DPRESENT_PARAMETERS params = translate(*pPresentationParameters);
		return m_inner->CreateAdditionalSwapChain(&params, pSwapChain);
	}

private:
	IDirect3D8* m_d3d;
};

class Direct3D8Wrapper : public Direct3D8WrapperBase
{
public:
	explicit Direct3D8Wrapper(IDirect3D8* inner) : Direct3D8WrapperBase(inner) {}

	STDMETHOD(QueryInterface)(REFIID riid, void** ppvObj) override
	{
		HRESULT hr = m_inner->QueryInterface(riid, ppvObj);
		if (SUCCEEDED(hr) && ppvObj && *ppvObj == m_inner)
		{
			m_inner->Release();
			AddRef();
			*ppvObj = this;
		}
		return hr;
	}
	STDMETHOD_(ULONG, AddRef)() override { return m_inner->AddRef(); }
	STDMETHOD_(ULONG, Release)() override
	{
		ULONG count = m_inner->Release();
		if (count == 0)
			delete this;
		return count;
	}
	STDMETHOD(CreateDevice)(UINT Adapter, D3DDEVTYPE DeviceType, HWND hFocusWindow, DWORD BehaviorFlags, D3DPRESENT_PARAMETERS* pPresentationParameters,
		IDirect3DDevice8** ppReturnedDeviceInterface) override
	{
		if (pPresentationParameters == nullptr || ppReturnedDeviceInterface == nullptr)
			return D3DERR_INVALIDCALL;
		D3DPRESENT_PARAMETERS params = translate(*pPresentationParameters);
		// DXVK presents to the device window, or the focus window when there is none.
		if (params.hDeviceWindow == nullptr)
			params.hDeviceWindow = toDxvkWindow(hFocusWindow);
		IDirect3DDevice8* device = nullptr;
		HRESULT hr = m_inner->CreateDevice(Adapter, DeviceType, toDxvkWindow(hFocusWindow), BehaviorFlags, &params, &device);
		params.hDeviceWindow = pPresentationParameters->hDeviceWindow;
		*pPresentationParameters = params;
		if (FAILED(hr) || device == nullptr)
		{
			fprintf(stderr, "d3d8dxvk: CreateDevice failed (0x%08X)\n", (unsigned)hr);
			*ppReturnedDeviceInterface = nullptr;
			return FAILED(hr) ? hr : D3DERR_NOTAVAILABLE;
		}
		*ppReturnedDeviceInterface = new Device8Wrapper(device, this);
		return D3D_OK;
	}
};

typedef IDirect3D8*(WINAPI* CreateFunction)(UINT);

// libdxvk_d3d8.so from DXVK_DIR/lib, next to the executable, or the library search path.
CreateFunction loadDxvk()
{
	static CreateFunction create = nullptr;
	static bool tried = false;
	if (tried)
		return create;
	tried = true;
	std::string candidates[3];
	if (const char* dir = getenv("DXVK_DIR"))
		candidates[0] = std::string(dir) + "/lib/libdxvk_d3d8.so";
	char exe[4096];
	ssize_t n = readlink("/proc/self/exe", exe, sizeof(exe) - 1);
	if (n > 0)
	{
		exe[n] = 0;
		std::string path = exe;
		candidates[1] = path.substr(0, path.rfind('/')) + "/libdxvk_d3d8.so";
	}
	candidates[2] = "libdxvk_d3d8.so";
	for (const std::string& candidate : candidates)
	{
		if (candidate.empty())
			continue;
		void* lib = dlopen(candidate.c_str(), RTLD_NOW | RTLD_LOCAL);
		if (lib == nullptr)
			continue;
		create = (CreateFunction)dlsym(lib, "Direct3DCreate8");
		if (create)
		{
			fprintf(stderr, "d3d8dxvk: using %s\n", candidate.c_str());
			return create;
		}
	}
	fprintf(stderr, "d3d8dxvk: libdxvk_d3d8.so not found (%s)\n", dlerror());
	return nullptr;
}
} // namespace

extern "C" IDirect3D8* WINAPI Direct3DCreate8(UINT SDKVersion)
{
	CreateFunction create = loadDxvk();
	if (create == nullptr)
		return nullptr;
	// DXVK native picks its window system from the available ones; the game's windows are SDL3.
	setenv("DXVK_WSI_DRIVER", "SDL3", 0);
	IDirect3D8* d3d = create(SDKVersion);
	return d3d ? new Direct3D8Wrapper(d3d) : nullptr;
}

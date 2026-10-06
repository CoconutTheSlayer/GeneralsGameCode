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

// Minimal COM declarations so DirectX style interface headers compile as plain
// C++ abstract classes.
#pragma once

#include <windows.h>

#define interface struct
#define PURE = 0
#define THIS_
#define THIS void
#define STDMETHOD(method) virtual HRESULT STDMETHODCALLTYPE method
#define STDMETHOD_(type, method) virtual type STDMETHODCALLTYPE method
#define STDMETHODIMP HRESULT STDMETHODCALLTYPE
#define STDMETHODIMP_(type) type STDMETHODCALLTYPE
#define DECLARE_INTERFACE(iface) interface iface
#define DECLARE_INTERFACE_(iface, base) interface iface : public base
#define MIDL_INTERFACE(x) struct
#define EXTERN_C extern "C"

DEFINE_GUID(IID_IUnknown, 0x00000000, 0x0000, 0x0000, 0xC0, 0x00, 0x00, 0x00, 0x00, 0x00, 0x00, 0x46);

interface IUnknown
{
	STDMETHOD(QueryInterface)(REFIID riid, void** ppvObj) PURE;
	STDMETHOD_(ULONG, AddRef)() PURE;
	STDMETHOD_(ULONG, Release)() PURE;
};
typedef IUnknown* LPUNKNOWN;

#define COINIT_APARTMENTTHREADED 0x2
#define COINIT_MULTITHREADED 0x0
#define CLSCTX_INPROC_SERVER 0x1
#define CLSCTX_ALL 0x17
inline HRESULT CoInitialize(LPVOID) { return S_OK; }
inline HRESULT CoInitializeEx(LPVOID, DWORD) { return S_OK; }
inline void CoUninitialize() {}
inline HRESULT CoCreateInstance(REFCLSID, LPUNKNOWN, DWORD, REFIID, LPVOID* ppv)
{
	if (ppv)
		*ppv = NULL;
	return E_NOINTERFACE;
}
inline HRESULT OleInitialize(LPVOID) { return S_OK; }
inline void OleUninitialize() {}

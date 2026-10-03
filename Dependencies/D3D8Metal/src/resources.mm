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

// Textures, surfaces and buffers.

#include "internal.h"

namespace d3d8metal
{

template <class Interface>
HRESULT ResourceObject<Interface>::GetDevice(IDirect3DDevice8** ppDevice)
{
	if (ppDevice == nullptr)
		return D3DERR_INVALIDCALL;
	m_device->AddRef();
	*ppDevice = m_device;
	return D3D_OK;
}

template class ResourceObject<IDirect3DTexture8>;
template class ResourceObject<IDirect3DCubeTexture8>;
template class ResourceObject<IDirect3DSurface8>;
template class ResourceObject<IDirect3DVertexBuffer8>;
template class ResourceObject<IDirect3DIndexBuffer8>;

//-----------------------------------------------------------------------------
// TextureStorage
//-----------------------------------------------------------------------------
TextureStorage::~TextureStorage()
{
	texture = nil;
}

std::vector<uint8_t>& TextureStorage::shadow(unsigned face, unsigned level)
{
	if (shadows.empty())
		shadows.resize(faces * levels);
	std::vector<uint8_t>& s = shadows[face * levels + level];
	if (s.empty())
		s.resize(ImageSize(format, levelWidth(level), levelHeight(level)), 0);
	return s;
}

namespace
{
void fillDesc(const TextureStorage& storage, unsigned level, D3DSURFACE_DESC* desc, D3DRESOURCETYPE type)
{
	desc->Format = storage.format;
	desc->Type = type;
	desc->Usage = storage.usage;
	desc->Pool = storage.pool;
	desc->Size = ImageSize(storage.format, storage.levelWidth(level), storage.levelHeight(level));
	desc->MultiSampleType = D3DMULTISAMPLE_NONE;
	desc->Width = storage.levelWidth(level);
	desc->Height = storage.levelHeight(level);
}

// Locks a level of a texture storage; shared by textures, cube maps and surfaces.
HRESULT lockLevel(Device* device, TextureStorage& storage, unsigned face, unsigned level, D3DLOCKED_RECT* locked, const RECT* rect, DWORD flags, RECT& lockRect)
{
	if (locked == nullptr || level >= storage.levels)
		return D3DERR_INVALIDCALL;
	unsigned w = storage.levelWidth(level);
	unsigned h = storage.levelHeight(level);
	if (rect)
		lockRect = *rect;
	else
		SetRect(&lockRect, 0, 0, (int)w, (int)h);

	if (storage.renderTarget && storage.shadowStale && !(flags & D3DLOCK_DISCARD))
		device->readbackTexture(storage, face, level);

	std::vector<uint8_t>& shadow = storage.shadow(face, level);
	unsigned pitch = RowPitch(storage.format, w);
	unsigned offset;
	if (IsCompressedFormat(storage.format))
		offset = (unsigned)(lockRect.top / 4) * pitch + (unsigned)(lockRect.left / 4) * (storage.format == D3DFMT_DXT1 ? 8 : 16);
	else
		offset = (unsigned)lockRect.top * pitch + (unsigned)lockRect.left * BytesPerPixel(storage.format);
	locked->pBits = shadow.data() + offset;
	locked->Pitch = (INT)pitch;
	return D3D_OK;
}
} // namespace

//-----------------------------------------------------------------------------
// Texture
//-----------------------------------------------------------------------------
Texture::Texture(Device* device, std::shared_ptr<TextureStorage> storage)
	: ResourceObject(device), m_storage(storage)
{
	for (unsigned i = 0; i < storage->levels; ++i)
		m_surfaces.push_back(new Surface(device, this, storage, 0, i));
}

Texture::~Texture()
{
	for (Surface* s : m_surfaces)
		delete s;
}

HRESULT Texture::GetLevelDesc(UINT Level, D3DSURFACE_DESC* pDesc)
{
	if (Level >= m_storage->levels || pDesc == nullptr)
		return D3DERR_INVALIDCALL;
	fillDesc(*m_storage, Level, pDesc, D3DRTYPE_SURFACE);
	return D3D_OK;
}

HRESULT Texture::GetSurfaceLevel(UINT Level, IDirect3DSurface8** ppSurfaceLevel)
{
	if (Level >= m_storage->levels || ppSurfaceLevel == nullptr)
		return D3DERR_INVALIDCALL;
	m_surfaces[Level]->AddRef();
	*ppSurfaceLevel = m_surfaces[Level];
	return D3D_OK;
}

HRESULT Texture::LockRect(UINT Level, D3DLOCKED_RECT* pLockedRect, CONST RECT* pRect, DWORD Flags)
{
	if (Level >= m_storage->levels)
		return D3DERR_INVALIDCALL;
	return m_surfaces[Level]->LockRect(pLockedRect, pRect, Flags);
}

HRESULT Texture::UnlockRect(UINT Level)
{
	if (Level >= m_storage->levels)
		return D3DERR_INVALIDCALL;
	return m_surfaces[Level]->UnlockRect();
}

//-----------------------------------------------------------------------------
// CubeTexture
//-----------------------------------------------------------------------------
CubeTexture::CubeTexture(Device* device, std::shared_ptr<TextureStorage> storage)
	: ResourceObject(device), m_storage(storage)
{
	for (unsigned face = 0; face < 6; ++face)
	{
		for (unsigned i = 0; i < storage->levels; ++i)
			m_surfaces.push_back(new Surface(device, this, storage, face, i));
	}
}

CubeTexture::~CubeTexture()
{
	for (Surface* s : m_surfaces)
		delete s;
}

HRESULT CubeTexture::GetLevelDesc(UINT Level, D3DSURFACE_DESC* pDesc)
{
	if (Level >= m_storage->levels || pDesc == nullptr)
		return D3DERR_INVALIDCALL;
	fillDesc(*m_storage, Level, pDesc, D3DRTYPE_SURFACE);
	return D3D_OK;
}

HRESULT CubeTexture::GetCubeMapSurface(D3DCUBEMAP_FACES FaceType, UINT Level, IDirect3DSurface8** ppCubeMapSurface)
{
	if (Level >= m_storage->levels || (unsigned)FaceType >= 6 || ppCubeMapSurface == nullptr)
		return D3DERR_INVALIDCALL;
	Surface* s = m_surfaces[(unsigned)FaceType * m_storage->levels + Level];
	s->AddRef();
	*ppCubeMapSurface = s;
	return D3D_OK;
}

HRESULT CubeTexture::LockRect(D3DCUBEMAP_FACES FaceType, UINT Level, D3DLOCKED_RECT* pLockedRect, CONST RECT* pRect, DWORD Flags)
{
	if (Level >= m_storage->levels || (unsigned)FaceType >= 6)
		return D3DERR_INVALIDCALL;
	return m_surfaces[(unsigned)FaceType * m_storage->levels + Level]->LockRect(pLockedRect, pRect, Flags);
}

HRESULT CubeTexture::UnlockRect(D3DCUBEMAP_FACES FaceType, UINT Level)
{
	if (Level >= m_storage->levels || (unsigned)FaceType >= 6)
		return D3DERR_INVALIDCALL;
	return m_surfaces[(unsigned)FaceType * m_storage->levels + Level]->UnlockRect();
}

//-----------------------------------------------------------------------------
// Surface
//-----------------------------------------------------------------------------
Surface::Surface(Device* device, std::shared_ptr<TextureStorage> storage)
	: ResourceObject(device), m_storage(storage)
{
}

Surface::Surface(Device* device, IUnknown* container, std::shared_ptr<TextureStorage> storage, unsigned face, unsigned level)
	: ResourceObject(device), m_storage(storage), m_container(container), m_face(face), m_level(level)
{
}

ULONG Surface::AddRef()
{
	if (m_container)
		return m_container->AddRef();
	return ComObject::AddRef();
}

ULONG Surface::Release()
{
	if (m_container)
		return m_container->Release();
	return ComObject::Release();
}

HRESULT Surface::GetContainer(REFIID, void** ppContainer)
{
	if (ppContainer == nullptr)
		return D3DERR_INVALIDCALL;
	IUnknown* container = m_container ? m_container : (IUnknown*)m_device;
	container->AddRef();
	*ppContainer = container;
	return D3D_OK;
}

HRESULT Surface::GetDesc(D3DSURFACE_DESC* pDesc)
{
	if (pDesc == nullptr)
		return D3DERR_INVALIDCALL;
	fillDesc(*m_storage, m_level, pDesc, D3DRTYPE_SURFACE);
	if (m_storage->renderTarget)
		pDesc->Usage |= D3DUSAGE_RENDERTARGET;
	if (m_storage->depthStencil)
		pDesc->Usage |= D3DUSAGE_DEPTHSTENCIL;
	return D3D_OK;
}

HRESULT Surface::LockRect(D3DLOCKED_RECT* pLockedRect, CONST RECT* pRect, DWORD Flags)
{
	if (m_storage->depthStencil)
		return D3DERR_INVALIDCALL;
	HRESULT hr = lockLevel(m_device, *m_storage, m_face, m_level, pLockedRect, pRect, Flags, m_lockRect);
	if (SUCCEEDED(hr))
	{
		m_locked = true;
		m_lockFlags = Flags;
	}
	return hr;
}

HRESULT Surface::UnlockRect()
{
	if (!m_locked)
		return D3DERR_INVALIDCALL;
	m_locked = false;
	if (!(m_lockFlags & D3DLOCK_READONLY))
		m_device->uploadTexture(*m_storage, m_face, m_level, m_lockRect);
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// Buffers
//-----------------------------------------------------------------------------
namespace
{
HRESULT lockBuffer(Device* device, BufferStorage& storage, UINT offset, UINT size, BYTE** data, DWORD flags)
{
	if (data == nullptr || offset > storage.length)
		return D3DERR_INVALIDCALL;
	if (size == 0)
		size = storage.length - offset;

	bool inFlight = device->isInFlight(storage.lastUsedSerial) || storage.lastUsedSerial == device->currentSerial();
	if (inFlight && !(flags & D3DLOCK_NOOVERWRITE) && !(flags & D3DLOCK_READONLY))
	{
		// Rename the buffer so the GPU keeps reading the old contents.
		id<MTLBuffer> fresh = device->acquireBuffer(storage.length);
		if (!(flags & D3DLOCK_DISCARD))
			memcpy([fresh contents], [storage.buffer contents], storage.length);
		device->retireBuffer(storage.buffer, storage.lastUsedSerial);
		storage.buffer = fresh;
		storage.lastUsedSerial = 0;
	}
	*data = (BYTE*)[storage.buffer contents] + offset;
	return D3D_OK;
}
} // namespace

VertexBuffer::VertexBuffer(Device* device, unsigned length, DWORD usage, DWORD fvf, D3DPOOL pool)
	: ResourceObject(device), m_fvf(fvf), m_pool(pool)
{
	m_storage.length = length;
	m_storage.usage = usage;
	m_storage.buffer = device->acquireBuffer(length);
}

VertexBuffer::~VertexBuffer()
{
	m_device->retireBuffer(m_storage.buffer, m_storage.lastUsedSerial);
}

HRESULT VertexBuffer::Lock(UINT OffsetToLock, UINT SizeToLock, BYTE** ppbData, DWORD Flags)
{
	return lockBuffer(m_device, m_storage, OffsetToLock, SizeToLock, ppbData, Flags);
}

HRESULT VertexBuffer::GetDesc(D3DVERTEXBUFFER_DESC* pDesc)
{
	if (pDesc == nullptr)
		return D3DERR_INVALIDCALL;
	pDesc->Format = D3DFMT_VERTEXDATA;
	pDesc->Type = D3DRTYPE_VERTEXBUFFER;
	pDesc->Usage = m_storage.usage;
	pDesc->Pool = m_pool;
	pDesc->Size = m_storage.length;
	pDesc->FVF = m_fvf;
	return D3D_OK;
}

IndexBuffer::IndexBuffer(Device* device, unsigned length, DWORD usage, D3DFORMAT format, D3DPOOL pool)
	: ResourceObject(device), m_format(format), m_pool(pool)
{
	m_storage.length = length;
	m_storage.usage = usage;
	m_storage.buffer = device->acquireBuffer(length);
}

IndexBuffer::~IndexBuffer()
{
	m_device->retireBuffer(m_storage.buffer, m_storage.lastUsedSerial);
}

HRESULT IndexBuffer::Lock(UINT OffsetToLock, UINT SizeToLock, BYTE** ppbData, DWORD Flags)
{
	return lockBuffer(m_device, m_storage, OffsetToLock, SizeToLock, ppbData, Flags);
}

HRESULT IndexBuffer::GetDesc(D3DINDEXBUFFER_DESC* pDesc)
{
	if (pDesc == nullptr)
		return D3DERR_INVALIDCALL;
	pDesc->Format = m_format;
	pDesc->Type = D3DRTYPE_INDEXBUFFER;
	pDesc->Usage = m_storage.usage;
	pDesc->Pool = m_pool;
	pDesc->Size = m_storage.length;
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// SwapChain
//-----------------------------------------------------------------------------
HRESULT SwapChain::Present(CONST RECT* src, CONST RECT* dst, HWND window, CONST RGNDATA* dirty)
{
	return m_device->Present(src, dst, window, dirty);
}

HRESULT SwapChain::GetBackBuffer(UINT BackBuffer, D3DBACKBUFFER_TYPE Type, IDirect3DSurface8** ppBackBuffer)
{
	return m_device->GetBackBuffer(BackBuffer, Type, ppBackBuffer);
}

} // namespace d3d8metal

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

// The subset of D3DX 8 used by the game: matrix math and texture helpers.

#include <d3dx8.h>

#include "formats.h"
#include "shadergen.h"
#include "shadertrans.h"

#include <cmath>
#include <string>
#include <vector>

#define STB_IMAGE_IMPLEMENTATION
#define STBI_ONLY_TGA
#define STBI_ONLY_BMP
#define STBI_ONLY_PNG
#define STBI_ONLY_JPEG
#include <stb_image.h>

using namespace d3d8metal;

//-----------------------------------------------------------------------------
// Math
//-----------------------------------------------------------------------------
extern "C" D3DXMATRIX* WINAPI D3DXMatrixMultiply(D3DXMATRIX* pOut, CONST D3DXMATRIX* pM1, CONST D3DXMATRIX* pM2)
{
	D3DXMATRIX r;
	for (int i = 0; i < 4; ++i)
		for (int j = 0; j < 4; ++j)
			r.m[i][j] = pM1->m[i][0] * pM2->m[0][j] + pM1->m[i][1] * pM2->m[1][j] + pM1->m[i][2] * pM2->m[2][j] + pM1->m[i][3] * pM2->m[3][j];
	*pOut = r;
	return pOut;
}

extern "C" D3DXMATRIX* WINAPI D3DXMatrixTranspose(D3DXMATRIX* pOut, CONST D3DXMATRIX* pM)
{
	D3DXMATRIX r;
	for (int i = 0; i < 4; ++i)
		for (int j = 0; j < 4; ++j)
			r.m[i][j] = pM->m[j][i];
	*pOut = r;
	return pOut;
}

extern "C" D3DXMATRIX* WINAPI D3DXMatrixInverse(D3DXMATRIX* pOut, FLOAT* pDeterminant, CONST D3DXMATRIX* pM)
{
	const float* m = &pM->_11;
	float inv[16];
	inv[0] = m[5] * m[10] * m[15] - m[5] * m[11] * m[14] - m[9] * m[6] * m[15] + m[9] * m[7] * m[14] + m[13] * m[6] * m[11] - m[13] * m[7] * m[10];
	inv[4] = -m[4] * m[10] * m[15] + m[4] * m[11] * m[14] + m[8] * m[6] * m[15] - m[8] * m[7] * m[14] - m[12] * m[6] * m[11] + m[12] * m[7] * m[10];
	inv[8] = m[4] * m[9] * m[15] - m[4] * m[11] * m[13] - m[8] * m[5] * m[15] + m[8] * m[7] * m[13] + m[12] * m[5] * m[11] - m[12] * m[7] * m[9];
	inv[12] = -m[4] * m[9] * m[14] + m[4] * m[10] * m[13] + m[8] * m[5] * m[14] - m[8] * m[6] * m[13] - m[12] * m[5] * m[10] + m[12] * m[6] * m[9];
	inv[1] = -m[1] * m[10] * m[15] + m[1] * m[11] * m[14] + m[9] * m[2] * m[15] - m[9] * m[3] * m[14] - m[13] * m[2] * m[11] + m[13] * m[3] * m[10];
	inv[5] = m[0] * m[10] * m[15] - m[0] * m[11] * m[14] - m[8] * m[2] * m[15] + m[8] * m[3] * m[14] + m[12] * m[2] * m[11] - m[12] * m[3] * m[10];
	inv[9] = -m[0] * m[9] * m[15] + m[0] * m[11] * m[13] + m[8] * m[1] * m[15] - m[8] * m[3] * m[13] - m[12] * m[1] * m[11] + m[12] * m[3] * m[9];
	inv[13] = m[0] * m[9] * m[14] - m[0] * m[10] * m[13] - m[8] * m[1] * m[14] + m[8] * m[2] * m[13] + m[12] * m[1] * m[10] - m[12] * m[2] * m[9];
	inv[2] = m[1] * m[6] * m[15] - m[1] * m[7] * m[14] - m[5] * m[2] * m[15] + m[5] * m[3] * m[14] + m[13] * m[2] * m[7] - m[13] * m[3] * m[6];
	inv[6] = -m[0] * m[6] * m[15] + m[0] * m[7] * m[14] + m[4] * m[2] * m[15] - m[4] * m[3] * m[14] - m[12] * m[2] * m[7] + m[12] * m[3] * m[6];
	inv[10] = m[0] * m[5] * m[15] - m[0] * m[7] * m[13] - m[4] * m[1] * m[15] + m[4] * m[3] * m[13] + m[12] * m[1] * m[7] - m[12] * m[3] * m[5];
	inv[14] = -m[0] * m[5] * m[14] + m[0] * m[6] * m[13] + m[4] * m[1] * m[14] - m[4] * m[2] * m[13] - m[12] * m[1] * m[6] + m[12] * m[2] * m[5];
	inv[3] = -m[1] * m[6] * m[11] + m[1] * m[7] * m[10] + m[5] * m[2] * m[11] - m[5] * m[3] * m[10] - m[9] * m[2] * m[7] + m[9] * m[3] * m[6];
	inv[7] = m[0] * m[6] * m[11] - m[0] * m[7] * m[10] - m[4] * m[2] * m[11] + m[4] * m[3] * m[10] + m[8] * m[2] * m[7] - m[8] * m[3] * m[6];
	inv[11] = -m[0] * m[5] * m[11] + m[0] * m[7] * m[9] + m[4] * m[1] * m[11] - m[4] * m[3] * m[9] - m[8] * m[1] * m[7] + m[8] * m[3] * m[5];
	inv[15] = m[0] * m[5] * m[10] - m[0] * m[6] * m[9] - m[4] * m[1] * m[10] + m[4] * m[2] * m[9] + m[8] * m[1] * m[6] - m[8] * m[2] * m[5];
	float det = m[0] * inv[0] + m[1] * inv[4] + m[2] * inv[8] + m[3] * inv[12];
	if (pDeterminant)
		*pDeterminant = det;
	if (det == 0.0f)
		return nullptr;
	det = 1.0f / det;
	float* o = &pOut->_11;
	for (int i = 0; i < 16; ++i)
		o[i] = inv[i] * det;
	return pOut;
}

extern "C" D3DXMATRIX* WINAPI D3DXMatrixScaling(D3DXMATRIX* pOut, FLOAT sx, FLOAT sy, FLOAT sz)
{
	memset(pOut, 0, sizeof(*pOut));
	pOut->_11 = sx;
	pOut->_22 = sy;
	pOut->_33 = sz;
	pOut->_44 = 1.0f;
	return pOut;
}

extern "C" D3DXMATRIX* WINAPI D3DXMatrixTranslation(D3DXMATRIX* pOut, FLOAT x, FLOAT y, FLOAT z)
{
	memset(pOut, 0, sizeof(*pOut));
	pOut->_11 = pOut->_22 = pOut->_33 = pOut->_44 = 1.0f;
	pOut->_41 = x;
	pOut->_42 = y;
	pOut->_43 = z;
	return pOut;
}

extern "C" D3DXMATRIX* WINAPI D3DXMatrixRotationZ(D3DXMATRIX* pOut, FLOAT angle)
{
	float s = sinf(angle), c = cosf(angle);
	memset(pOut, 0, sizeof(*pOut));
	pOut->_11 = c;
	pOut->_12 = s;
	pOut->_21 = -s;
	pOut->_22 = c;
	pOut->_33 = 1.0f;
	pOut->_44 = 1.0f;
	return pOut;
}

extern "C" D3DXVECTOR4* WINAPI D3DXVec3Transform(D3DXVECTOR4* pOut, CONST D3DXVECTOR3* pV, CONST D3DXMATRIX* pM)
{
	D3DXVECTOR4 r;
	r.x = pV->x * pM->_11 + pV->y * pM->_21 + pV->z * pM->_31 + pM->_41;
	r.y = pV->x * pM->_12 + pV->y * pM->_22 + pV->z * pM->_32 + pM->_42;
	r.z = pV->x * pM->_13 + pV->y * pM->_23 + pV->z * pM->_33 + pM->_43;
	r.w = pV->x * pM->_14 + pV->y * pM->_24 + pV->z * pM->_34 + pM->_44;
	*pOut = r;
	return pOut;
}

extern "C" D3DXVECTOR4* WINAPI D3DXVec4Transform(D3DXVECTOR4* pOut, CONST D3DXVECTOR4* pV, CONST D3DXMATRIX* pM)
{
	D3DXVECTOR4 r;
	r.x = pV->x * pM->_11 + pV->y * pM->_21 + pV->z * pM->_31 + pV->w * pM->_41;
	r.y = pV->x * pM->_12 + pV->y * pM->_22 + pV->z * pM->_32 + pV->w * pM->_42;
	r.z = pV->x * pM->_13 + pV->y * pM->_23 + pV->z * pM->_33 + pV->w * pM->_43;
	r.w = pV->x * pM->_14 + pV->y * pM->_24 + pV->z * pM->_34 + pV->w * pM->_44;
	*pOut = r;
	return pOut;
}

//-----------------------------------------------------------------------------
// Misc
//-----------------------------------------------------------------------------
extern "C" UINT WINAPI D3DXGetFVFVertexSize(DWORD FVF)
{
	return FvfVertexSize(FVF);
}

extern "C" HRESULT WINAPI D3DXGetErrorStringA(HRESULT hr, LPSTR pBuffer, UINT BufferLen)
{
	if (pBuffer == nullptr || BufferLen == 0)
		return D3DERR_INVALIDCALL;
	snprintf(pBuffer, BufferLen, "HRESULT 0x%08X", (unsigned)hr);
	return D3D_OK;
}

namespace
{
// ID3DXBuffer holding a copy of some bytes.
class Buffer : public ID3DXBuffer
{
public:
	Buffer(const void* data, size_t size) : m_data((const uint8_t*)data, (const uint8_t*)data + size) {}
	virtual ~Buffer() {}
	STDMETHOD(QueryInterface)(REFIID, LPVOID* ppv) override
	{
		if (ppv)
			*ppv = nullptr;
		return E_NOINTERFACE;
	}
	STDMETHOD_(ULONG, AddRef)() override { return ++m_refs; }
	STDMETHOD_(ULONG, Release)() override
	{
		ULONG refs = --m_refs;
		if (refs == 0)
			delete this;
		return refs;
	}
	STDMETHOD_(LPVOID, GetBufferPointer)() override { return m_data.data(); }
	STDMETHOD_(DWORD, GetBufferSize)() override { return (DWORD)m_data.size(); }

private:
	std::vector<uint8_t> m_data;
	ULONG m_refs = 1;
};
} // namespace

extern "C" HRESULT WINAPI D3DXAssembleShader(LPCVOID pSrcData, UINT SrcDataLen, DWORD, LPD3DXBUFFER* ppConstants, LPD3DXBUFFER* ppCompiledShader, LPD3DXBUFFER* ppCompilationErrors)
{
	if (ppConstants)
		*ppConstants = nullptr;
	if (ppCompiledShader)
		*ppCompiledShader = nullptr;
	if (ppCompilationErrors)
		*ppCompilationErrors = nullptr;
	if (pSrcData == nullptr)
		return D3DERR_INVALIDCALL;
	std::vector<DWORD> code;
	std::string errors;
	if (!d3d8metal::AssembleShader((const char*)pSrcData, SrcDataLen, code, errors))
	{
		fprintf(stderr, "d3d8metal: D3DXAssembleShader failed:\n%s", errors.c_str());
		if (ppCompilationErrors)
			*ppCompilationErrors = new Buffer(errors.c_str(), errors.size() + 1);
		return D3DERR_INVALIDCALL;
	}
	if (ppCompiledShader)
		*ppCompiledShader = new Buffer(code.data(), code.size() * sizeof(DWORD));
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// Texture creation
//-----------------------------------------------------------------------------
namespace
{
unsigned roundUpPow2(unsigned v)
{
	unsigned p = 1;
	while (p < v)
		p <<= 1;
	return p;
}

D3DFORMAT fixFormat(D3DFORMAT format)
{
	switch (format)
	{
	case D3DFMT_UNKNOWN:
	case D3DFMT_P8:
	case D3DFMT_A8P8:
	case D3DFMT_A8R3G3B2:
		return D3DFMT_A8R8G8B8;
	case D3DFMT_R8G8B8:
		return D3DFMT_X8R8G8B8;
	default:
		return format;
	}
}
} // namespace

extern "C" HRESULT WINAPI D3DXCreateTexture(LPDIRECT3DDEVICE8 pDevice, UINT Width, UINT Height, UINT MipLevels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, LPDIRECT3DTEXTURE8* ppTexture)
{
	if (pDevice == nullptr || ppTexture == nullptr)
		return D3DERR_INVALIDCALL;
	if (Width == 0 || Width == D3DX_DEFAULT)
		Width = 256;
	if (Height == 0 || Height == D3DX_DEFAULT)
		Height = 256;
	Format = fixFormat(Format);
	if (IsCompressedFormat(Format))
	{
		Width = (Width + 3) & ~3u;
		Height = (Height + 3) & ~3u;
	}
	if (MipLevels == D3DX_DEFAULT)
		MipLevels = 0;
	return pDevice->CreateTexture(Width, Height, MipLevels, Usage, Format, Pool, ppTexture);
}

extern "C" HRESULT WINAPI D3DXCreateCubeTexture(LPDIRECT3DDEVICE8 pDevice, UINT Size, UINT MipLevels, DWORD Usage, D3DFORMAT Format, D3DPOOL Pool, LPDIRECT3DCUBETEXTURE8* ppCubeTexture)
{
	if (pDevice == nullptr || ppCubeTexture == nullptr)
		return D3DERR_INVALIDCALL;
	if (Size == 0 || Size == D3DX_DEFAULT)
		Size = 256;
	if (MipLevels == D3DX_DEFAULT)
		MipLevels = 0;
	return pDevice->CreateCubeTexture(Size, MipLevels, Usage, fixFormat(Format), Pool, ppCubeTexture);
}

extern "C" HRESULT WINAPI D3DXCreateVolumeTexture(LPDIRECT3DDEVICE8 pDevice, UINT, UINT, UINT, UINT, DWORD, D3DFORMAT, D3DPOOL, LPDIRECT3DVOLUMETEXTURE8* ppVolumeTexture)
{
	if (ppVolumeTexture)
		*ppVolumeTexture = nullptr;
	(void)pDevice;
	return D3DERR_NOTAVAILABLE;
}

//-----------------------------------------------------------------------------
// Surface copies and mip generation through BGRA8
//-----------------------------------------------------------------------------
namespace
{
struct Image
{
	unsigned width = 0;
	unsigned height = 0;
	std::vector<uint8_t> bgra;
};

bool readSurface(IDirect3DSurface8* surface, const RECT* rect, Image& out)
{
	D3DSURFACE_DESC desc;
	if (FAILED(surface->GetDesc(&desc)))
		return false;
	RECT r;
	if (rect)
		r = *rect;
	else
		SetRect(&r, 0, 0, (int)desc.Width, (int)desc.Height);
	D3DLOCKED_RECT locked;
	if (FAILED(surface->LockRect(&locked, nullptr, D3DLOCK_READONLY)))
		return false;
	std::vector<uint8_t> full((size_t)desc.Width * desc.Height * 4);
	if (IsCompressedFormat(desc.Format))
		DecodeDXT(desc.Format, (const uint8_t*)locked.pBits, (unsigned)locked.Pitch, full.data(), desc.Width * 4, desc.Width, desc.Height);
	else
		ConvertToBGRA8(desc.Format, (const uint8_t*)locked.pBits, (unsigned)locked.Pitch, full.data(), desc.Width * 4, desc.Width, desc.Height);
	surface->UnlockRect();

	out.width = (unsigned)(r.right - r.left);
	out.height = (unsigned)(r.bottom - r.top);
	out.bgra.resize((size_t)out.width * out.height * 4);
	for (unsigned y = 0; y < out.height; ++y)
		memcpy(out.bgra.data() + (size_t)y * out.width * 4, full.data() + ((size_t)(r.top + y) * desc.Width + r.left) * 4, (size_t)out.width * 4);
	return true;
}

// Resamples src into a w x h image (box filter when shrinking, bilinear otherwise).
void resample(const Image& src, unsigned w, unsigned h, Image& out, bool point)
{
	out.width = w;
	out.height = h;
	out.bgra.assign((size_t)w * h * 4, 0);
	if (src.width == w && src.height == h)
	{
		out.bgra = src.bgra;
		return;
	}
	for (unsigned y = 0; y < h; ++y)
	{
		for (unsigned x = 0; x < w; ++x)
		{
			uint8_t* d = out.bgra.data() + ((size_t)y * w + x) * 4;
			if (point)
			{
				unsigned sx = x * src.width / w, sy = y * src.height / h;
				memcpy(d, src.bgra.data() + ((size_t)sy * src.width + sx) * 4, 4);
				continue;
			}
			unsigned x0 = x * src.width / w, x1 = std::max(x0 + 1, (x + 1) * src.width / w);
			unsigned y0 = y * src.height / h, y1 = std::max(y0 + 1, (y + 1) * src.height / h);
			unsigned sum[4] = { 0, 0, 0, 0 }, n = 0;
			for (unsigned sy = y0; sy < y1 && sy < src.height; ++sy)
			{
				for (unsigned sx = x0; sx < x1 && sx < src.width; ++sx)
				{
					const uint8_t* s = src.bgra.data() + ((size_t)sy * src.width + sx) * 4;
					for (int c = 0; c < 4; ++c)
						sum[c] += s[c];
					++n;
				}
			}
			for (int c = 0; c < 4; ++c)
				d[c] = (uint8_t)(n ? sum[c] / n : 0);
		}
	}
}

bool writeSurface(IDirect3DSurface8* surface, const RECT* rect, const Image& img)
{
	D3DSURFACE_DESC desc;
	if (FAILED(surface->GetDesc(&desc)))
		return false;
	if (IsCompressedFormat(desc.Format))
		return false; // compressing on the CPU is not supported
	RECT r;
	if (rect)
		r = *rect;
	else
		SetRect(&r, 0, 0, (int)desc.Width, (int)desc.Height);
	D3DLOCKED_RECT locked;
	if (FAILED(surface->LockRect(&locked, &r, 0)))
		return false;
	unsigned w = std::min<unsigned>(img.width, (unsigned)(r.right - r.left));
	unsigned h = std::min<unsigned>(img.height, (unsigned)(r.bottom - r.top));
	ConvertFromBGRA8(desc.Format, img.bgra.data(), img.width * 4, (uint8_t*)locked.pBits, (unsigned)locked.Pitch, w, h);
	surface->UnlockRect();
	return true;
}
} // namespace

extern "C" HRESULT WINAPI D3DXLoadSurfaceFromSurface(LPDIRECT3DSURFACE8 pDestSurface, CONST PALETTEENTRY*, CONST RECT* pDestRect, LPDIRECT3DSURFACE8 pSrcSurface,
	CONST PALETTEENTRY*, CONST RECT* pSrcRect, DWORD Filter, D3DCOLOR)
{
	if (pDestSurface == nullptr || pSrcSurface == nullptr)
		return D3DERR_INVALIDCALL;

	D3DSURFACE_DESC srcDesc, dstDesc;
	pSrcSurface->GetDesc(&srcDesc);
	pDestSurface->GetDesc(&dstDesc);

	RECT dr;
	if (pDestRect)
		dr = *pDestRect;
	else
		SetRect(&dr, 0, 0, (int)dstDesc.Width, (int)dstDesc.Height);
	RECT sr;
	if (pSrcRect)
		sr = *pSrcRect;
	else
		SetRect(&sr, 0, 0, (int)srcDesc.Width, (int)srcDesc.Height);

	// Same format, same size, compressed: copy blocks directly.
	if (srcDesc.Format == dstDesc.Format && IsCompressedFormat(srcDesc.Format) && sr.right - sr.left == dr.right - dr.left && sr.bottom - sr.top == dr.bottom - dr.top)
	{
		D3DLOCKED_RECT s, d;
		if (FAILED(pSrcSurface->LockRect(&s, &sr, D3DLOCK_READONLY)))
			return D3DERR_INVALIDCALL;
		if (FAILED(pDestSurface->LockRect(&d, &dr, 0)))
		{
			pSrcSurface->UnlockRect();
			return D3DERR_INVALIDCALL;
		}
		unsigned rowBytes = RowPitch(srcDesc.Format, (unsigned)(sr.right - sr.left));
		unsigned rows = RowCount(srcDesc.Format, (unsigned)(sr.bottom - sr.top));
		for (unsigned y = 0; y < rows; ++y)
			memcpy((uint8_t*)d.pBits + (size_t)y * d.Pitch, (const uint8_t*)s.pBits + (size_t)y * s.Pitch, rowBytes);
		pDestSurface->UnlockRect();
		pSrcSurface->UnlockRect();
		return D3D_OK;
	}

	Image src, scaled;
	if (!readSurface(pSrcSurface, &sr, src))
		return D3DERR_INVALIDCALL;
	resample(src, (unsigned)(dr.right - dr.left), (unsigned)(dr.bottom - dr.top), scaled, (Filter & 0xFF) == D3DX_FILTER_POINT || (Filter & 0xFF) == D3DX_FILTER_NONE);
	return writeSurface(pDestSurface, &dr, scaled) ? D3D_OK : D3DERR_INVALIDCALL;
}

extern "C" HRESULT WINAPI D3DXFilterTexture(LPDIRECT3DBASETEXTURE8 pBaseTexture, CONST PALETTEENTRY*, UINT SrcLevel, DWORD)
{
	if (pBaseTexture == nullptr || pBaseTexture->GetType() != D3DRTYPE_TEXTURE)
		return D3DERR_INVALIDCALL;
	IDirect3DTexture8* texture = static_cast<IDirect3DTexture8*>(pBaseTexture);
	if (SrcLevel == D3DX_DEFAULT)
		SrcLevel = 0;
	DWORD levels = texture->GetLevelCount();
	D3DSURFACE_DESC desc;
	texture->GetLevelDesc(0, &desc);
	if (IsCompressedFormat(desc.Format))
		return D3D_OK; // compressed textures ship with their mip chain

	IDirect3DSurface8* srcSurface = nullptr;
	if (FAILED(texture->GetSurfaceLevel(SrcLevel, &srcSurface)))
		return D3DERR_INVALIDCALL;
	Image current;
	bool ok = readSurface(srcSurface, nullptr, current);
	srcSurface->Release();
	if (!ok)
		return D3DERR_INVALIDCALL;

	for (DWORD level = SrcLevel + 1; level < levels; ++level)
	{
		Image next;
		resample(current, std::max(1u, current.width / 2), std::max(1u, current.height / 2), next, false);
		IDirect3DSurface8* dst = nullptr;
		if (SUCCEEDED(texture->GetSurfaceLevel(level, &dst)))
		{
			writeSurface(dst, nullptr, next);
			dst->Release();
		}
		current = std::move(next);
	}
	return D3D_OK;
}

extern "C" HRESULT WINAPI D3DXCreateTextureFromFileExA(LPDIRECT3DDEVICE8 pDevice, LPCSTR pSrcFile, UINT Width, UINT Height, UINT MipLevels, DWORD Usage, D3DFORMAT Format,
	D3DPOOL Pool, DWORD, DWORD, D3DCOLOR, D3DXIMAGE_INFO* pSrcInfo, PALETTEENTRY*, LPDIRECT3DTEXTURE8* ppTexture)
{
	if (pDevice == nullptr || pSrcFile == nullptr || ppTexture == nullptr)
		return D3DERR_INVALIDCALL;
	std::string path = pSrcFile;
	for (char& c : path)
	{
		if (c == '\\')
			c = '/';
	}
	int w = 0, h = 0, channels = 0;
	stbi_uc* pixels = stbi_load(path.c_str(), &w, &h, &channels, 4);
	if (pixels == nullptr)
		return D3DXERR_INVALIDDATA;

	if (pSrcInfo)
	{
		pSrcInfo->Width = (UINT)w;
		pSrcInfo->Height = (UINT)h;
		pSrcInfo->Depth = 1;
		pSrcInfo->MipLevels = 1;
		pSrcInfo->Format = channels == 4 ? D3DFMT_A8R8G8B8 : D3DFMT_X8R8G8B8;
		pSrcInfo->ResourceType = D3DRTYPE_TEXTURE;
		pSrcInfo->ImageFileFormat = D3DXIFF_TGA;
	}

	UINT tw = (Width == 0 || Width == D3DX_DEFAULT) ? roundUpPow2((unsigned)w) : Width;
	UINT th = (Height == 0 || Height == D3DX_DEFAULT) ? roundUpPow2((unsigned)h) : Height;
	if (Format == D3DFMT_UNKNOWN)
		Format = channels == 4 ? D3DFMT_A8R8G8B8 : D3DFMT_X8R8G8B8;
	HRESULT hr = D3DXCreateTexture(pDevice, tw, th, MipLevels, Usage, Format, Pool, ppTexture);
	if (FAILED(hr))
	{
		stbi_image_free(pixels);
		return hr;
	}

	Image src;
	src.width = (unsigned)w;
	src.height = (unsigned)h;
	src.bgra.resize((size_t)w * h * 4);
	for (size_t i = 0; i < (size_t)w * h; ++i)
	{
		src.bgra[i * 4 + 0] = pixels[i * 4 + 2];
		src.bgra[i * 4 + 1] = pixels[i * 4 + 1];
		src.bgra[i * 4 + 2] = pixels[i * 4 + 0];
		src.bgra[i * 4 + 3] = pixels[i * 4 + 3];
	}
	stbi_image_free(pixels);

	Image scaled;
	resample(src, tw, th, scaled, false);
	IDirect3DSurface8* top = nullptr;
	(*ppTexture)->GetSurfaceLevel(0, &top);
	writeSurface(top, nullptr, scaled);
	top->Release();
	D3DXFilterTexture(*ppTexture, nullptr, 0, D3DX_FILTER_BOX);
	return D3D_OK;
}

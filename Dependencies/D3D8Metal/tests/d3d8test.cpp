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

// Visual test for the Direct3D 8 on Metal backend. Renders a set of scenes that
// exercise the fixed function features the game uses and writes each frame to
// a PNG file for inspection:  d3d8test <output directory>

#include <win32shim.h>
#include <d3d8.h>
#include <d3dx8.h>

#include <algorithm>
#include <cmath>
#include <string>
#include <vector>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image_write.h>

static IDirect3DDevice8* g_device = nullptr;
static const int W = 640, H = 480;

static LRESULT WndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
	return DefWindowProc(hwnd, msg, wParam, lParam);
}

static void check(HRESULT hr, const char* what)
{
	if (FAILED(hr))
	{
		fprintf(stderr, "FAILED: %s (0x%08X)\n", what, (unsigned)hr);
		exit(1);
	}
}

static void saveFrame(const std::string& path)
{
	IDirect3DSurface8* back = nullptr;
	check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
	IDirect3DSurface8* image = nullptr;
	check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
	check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
	D3DLOCKED_RECT lr;
	check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
	std::vector<uint8_t> rgba(W * H * 4);
	for (int y = 0; y < H; ++y)
	{
		const uint8_t* s = (const uint8_t*)lr.pBits + y * lr.Pitch;
		for (int x = 0; x < W; ++x)
		{
			rgba[(y * W + x) * 4 + 0] = s[x * 4 + 2];
			rgba[(y * W + x) * 4 + 1] = s[x * 4 + 1];
			rgba[(y * W + x) * 4 + 2] = s[x * 4 + 0];
			rgba[(y * W + x) * 4 + 3] = 255;
		}
	}
	image->UnlockRect();
	image->Release();
	back->Release();
	stbi_write_png(path.c_str(), W, H, 4, rgba.data(), W * 4);
	printf("wrote %s\n", path.c_str());
}

struct TLVertex
{
	float x, y, z, rhw;
	DWORD color;
	float u, v;
};
static const DWORD TLFVF = D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_TEX1;

struct LitVertex
{
	float x, y, z;
	float nx, ny, nz;
	float u, v;
};
static const DWORD LITFVF = D3DFVF_XYZ | D3DFVF_NORMAL | D3DFVF_TEX1;

static IDirect3DTexture8* makeChecker(D3DFORMAT format, int size, DWORD c0, DWORD c1)
{
	IDirect3DTexture8* tex = nullptr;
	check(g_device->CreateTexture(size, size, 0, 0, format, D3DPOOL_MANAGED, &tex), "CreateTexture");
	D3DLOCKED_RECT lr;
	check(tex->LockRect(0, &lr, nullptr, 0), "tex LockRect");
	for (int y = 0; y < size; ++y)
	{
		for (int x = 0; x < size; ++x)
		{
			DWORD c = (((x / 8) + (y / 8)) & 1) ? c1 : c0;
			uint8_t* p = (uint8_t*)lr.pBits + y * lr.Pitch;
			if (format == D3DFMT_A8R8G8B8)
				((DWORD*)p)[x] = c;
			else if (format == D3DFMT_R5G6B5)
				((uint16_t*)p)[x] = (uint16_t)((((c >> 19) & 31) << 11) | (((c >> 10) & 63) << 5) | ((c >> 3) & 31));
			else if (format == D3DFMT_A4R4G4B4)
				((uint16_t*)p)[x] = (uint16_t)((((c >> 28) & 15) << 12) | (((c >> 20) & 15) << 8) | (((c >> 12) & 15) << 4) | ((c >> 4) & 15));
		}
	}
	tex->UnlockRect(0);
	D3DXFilterTexture(tex, nullptr, 0, D3DX_FILTER_BOX);
	return tex;
}

static IDirect3DTexture8* makeDXT1()
{
	// 16x16 DXT1: each 4x4 block alternates red/blue.
	IDirect3DTexture8* tex = nullptr;
	check(g_device->CreateTexture(16, 16, 1, 0, D3DFMT_DXT1, D3DPOOL_MANAGED, &tex), "CreateTexture DXT1");
	D3DLOCKED_RECT lr;
	check(tex->LockRect(0, &lr, nullptr, 0), "dxt lock");
	for (int by = 0; by < 4; ++by)
	{
		uint8_t* row = (uint8_t*)lr.pBits + by * lr.Pitch;
		for (int bx = 0; bx < 4; ++bx)
		{
			uint16_t color = ((bx + by) & 1) ? 0xF800 : 0x001F;
			uint8_t* b = row + bx * 8;
			b[0] = (uint8_t)color;
			b[1] = (uint8_t)(color >> 8);
			b[2] = (uint8_t)color;
			b[3] = (uint8_t)(color >> 8);
			b[4] = b[5] = b[6] = b[7] = 0;
		}
	}
	tex->UnlockRect(0);
	return tex;
}

static void quad(float x, float y, float w, float h, DWORD c0, DWORD c1, DWORD c2, DWORD c3, float z = 0.5f)
{
	TLVertex v[4] = {
		{ x, y, z, 1.0f, c0, 0.0f, 0.0f },
		{ x + w, y, z, 1.0f, c1, 1.0f, 0.0f },
		{ x, y + h, z, 1.0f, c2, 0.0f, 1.0f },
		{ x + w, y + h, z, 1.0f, c3, 1.0f, 1.0f },
	};
	g_device->SetVertexShader(TLFVF);
	g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(TLVertex));
}

static void resetStates()
{
	g_device->SetRenderState(D3DRS_LIGHTING, FALSE);
	g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
	g_device->SetRenderState(D3DRS_ALPHATESTENABLE, FALSE);
	g_device->SetRenderState(D3DRS_FOGENABLE, FALSE);
	g_device->SetRenderState(D3DRS_SPECULARENABLE, FALSE);
	g_device->SetRenderState(D3DRS_STENCILENABLE, FALSE);
	g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_TRUE);
	g_device->SetRenderState(D3DRS_ZFUNC, D3DCMP_LESSEQUAL);
	g_device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
	for (int i = 0; i < 4; ++i)
	{
		g_device->SetTexture(i, nullptr);
		g_device->SetTextureStageState(i, D3DTSS_COLOROP, D3DTOP_DISABLE);
		g_device->SetTextureStageState(i, D3DTSS_ALPHAOP, D3DTOP_DISABLE);
		g_device->SetTextureStageState(i, D3DTSS_TEXCOORDINDEX, i);
		g_device->SetTextureStageState(i, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_DISABLE);
		g_device->SetTextureStageState(i, D3DTSS_ADDRESSU, D3DTADDRESS_WRAP);
		g_device->SetTextureStageState(i, D3DTSS_ADDRESSV, D3DTADDRESS_WRAP);
	}
	g_device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG2);
	g_device->SetTextureStageState(0, D3DTSS_COLORARG2, D3DTA_DIFFUSE);
	g_device->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_SELECTARG2);
	g_device->SetTextureStageState(0, D3DTSS_ALPHAARG2, D3DTA_DIFFUSE);
}

static void modulateStage0(IDirect3DBaseTexture8* tex)
{
	g_device->SetTexture(0, tex);
	g_device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_MODULATE);
	g_device->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
	g_device->SetTextureStageState(0, D3DTSS_COLORARG2, D3DTA_DIFFUSE);
	g_device->SetTextureStageState(0, D3DTSS_ALPHAOP, D3DTOP_MODULATE);
	g_device->SetTextureStageState(0, D3DTSS_ALPHAARG1, D3DTA_TEXTURE);
	g_device->SetTextureStageState(0, D3DTSS_ALPHAARG2, D3DTA_DIFFUSE);
	g_device->SetTextureStageState(0, D3DTSS_MINFILTER, D3DTEXF_POINT);
	g_device->SetTextureStageState(0, D3DTSS_MAGFILTER, D3DTEXF_POINT);
}

static D3DMATRIX identity()
{
	D3DMATRIX m;
	memset(&m, 0, sizeof(m));
	m._11 = m._22 = m._33 = m._44 = 1.0f;
	return m;
}

static void setCamera()
{
	// Left handed look-at from (0, 2, -5) to origin, 60 degree perspective.
	D3DMATRIX view = identity();
	float ex = 0, ey = 2, ez = -5;
	float zx = -ex, zy = -ey, zz = -ez;
	float zl = sqrtf(zx * zx + zy * zy + zz * zz);
	zx /= zl; zy /= zl; zz /= zl;
	float xx = zz, xy = 0, xz = -zx; // up (0,1,0) x z
	float xl = sqrtf(xx * xx + xz * xz);
	xx /= xl; xz /= xl;
	float yx = zy * xz - zz * xy, yy = zz * xx - zx * xz, yz = zx * xy - zy * xx;
	view._11 = xx; view._12 = yx; view._13 = zx;
	view._21 = xy; view._22 = yy; view._23 = zy;
	view._31 = xz; view._32 = yz; view._33 = zz;
	view._41 = -(xx * ex + xy * ey + xz * ez);
	view._42 = -(yx * ex + yy * ey + yz * ez);
	view._43 = -(zx * ex + zy * ey + zz * ez);
	g_device->SetTransform(D3DTS_VIEW, &view);

	D3DMATRIX proj;
	memset(&proj, 0, sizeof(proj));
	float zn = 0.1f, zf = 100.0f;
	float yscale = 1.0f / tanf(3.14159f / 6.0f);
	proj._11 = yscale * H / W;
	proj._22 = yscale;
	proj._33 = zf / (zf - zn);
	proj._34 = 1.0f;
	proj._43 = -zn * zf / (zf - zn);
	g_device->SetTransform(D3DTS_PROJECTION, &proj);
}

static void drawCube(float angle, float tx = 0.0f, float tz = 0.0f)
{
	static const float faces[6][3] = { { 0, 0, -1 }, { 0, 0, 1 }, { -1, 0, 0 }, { 1, 0, 0 }, { 0, 1, 0 }, { 0, -1, 0 } };
	std::vector<LitVertex> v;
	for (auto& n : faces)
	{
		// Two tangent vectors.
		float ux = n[1] != 0 ? 1.0f : -n[2];
		float uy = 0;
		float uz = n[1] != 0 ? 0.0f : n[0];
		float vx = n[1] * uz - n[2] * uy, vy = n[2] * ux - n[0] * uz, vz = n[0] * uy - n[1] * ux;
		LitVertex c[4];
		for (int i = 0; i < 4; ++i)
		{
			float su = (i & 1) ? 1.0f : -1.0f, sv = (i & 2) ? -1.0f : 1.0f;
			c[i] = { n[0] + ux * su + vx * sv, n[1] + uy * su + vy * sv, n[2] + uz * su + vz * sv, n[0], n[1], n[2], (i & 1) ? 1.0f : 0.0f, (i & 2) ? 1.0f : 0.0f };
		}
		// Clockwise winding is front facing in D3D.
		v.push_back(c[0]); v.push_back(c[2]); v.push_back(c[1]);
		v.push_back(c[2]); v.push_back(c[3]); v.push_back(c[1]);
	}
	D3DMATRIX world = identity();
	float s = sinf(angle), c = cosf(angle);
	world._11 = c; world._13 = -s; world._31 = s; world._33 = c;
	world._41 = tx;
	world._43 = tz;
	g_device->SetTransform(D3DTS_WORLD, &world);
	g_device->SetVertexShader(LITFVF);
	g_device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, (UINT)v.size() / 3, v.data(), sizeof(LitVertex));
}

// Compare the game's two stencil passes with separate local-space volumes and
// CPU-transformed batches, including overlapping volumes, occlusion masks, depth
// clipping, reflected/scaled transforms and a split at the 16-bit vertex limit.
static int testShadowBatches(const std::string& out)
{
	struct Position { float x, y, z; };
	const Position cube[] = {{-.125f,-.125f,.25f},{.125f,-.125f,.25f},{.125f,.125f,.25f},{-.125f,.125f,.25f},
		{-.125f,-.125f,.75f},{.125f,-.125f,.75f},{.125f,.125f,.75f},{-.125f,.125f,.75f}};
	const uint16_t indices[] = {0,2,1,0,3,2,4,5,6,4,6,7,0,1,5,0,5,4,1,2,6,1,6,5,2,3,7,2,7,6,3,0,4,3,4,7};
	std::vector<D3DMATRIX> transforms;
	for (int i = 0; i < 96; ++i)
	{
		D3DMATRIX m = identity();
		m._11 = i % 3 == 0 ? -.5f : 1.f;
		m._22 = i % 5 == 0 ? .5f : 1.f;
		if (i % 4 == 0) { m._12 = m._11; m._21 = -m._22; m._11 = m._22 = 0; }
		m._41 = (i % 12 - 6) * .125f;
		m._42 = (i / 12 - 4) * .125f;
		m._43 = i % 7 == 0 ? -.25f : 0;
		transforms.push_back(m);
	}
	struct Batch { std::vector<Position> vertices; std::vector<uint16_t> indices; };
	std::vector<Batch> batches(1);
	batches.back().vertices.resize(65520); // unused padding exercises index rebasing near the limit
	for (const auto& m : transforms)
	{
		if (batches.back().vertices.size() + 8 > 65535) batches.emplace_back();
		auto& b = batches.back();
		size_t base = b.vertices.size();
		for (const auto& v : cube) b.vertices.push_back({v.x*m._11+v.y*m._21+v.z*m._31+m._41,
			v.x*m._12+v.y*m._22+v.z*m._32+m._42, v.x*m._13+v.y*m._23+v.z*m._33+m._43});
		for (auto index : indices) b.indices.push_back((uint16_t)(base + index));
	}
	int failures = 0;
	for (int maskMode = 0; maskMode < 2; ++maskMode)
	{
		std::vector<DWORD> reference;
		for (int batched = 0; batched < 2; ++batched)
		{
			resetStates();
			D3DMATRIX unit = identity();
			g_device->SetTransform(D3DTS_WORLD, &unit);
			g_device->SetTransform(D3DTS_VIEW, &unit);
			g_device->SetTransform(D3DTS_PROJECTION, &unit);
			g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER | D3DCLEAR_STENCIL, 0xFFFFFFFF, .6f, 0);
			g_device->BeginScene();
			g_device->SetRenderState(D3DRS_COLORWRITEENABLE, 0);
			g_device->SetRenderState(D3DRS_ZWRITEENABLE, FALSE);
			g_device->SetRenderState(D3DRS_ZENABLE, FALSE);
			g_device->SetRenderState(D3DRS_STENCILENABLE, TRUE);
			g_device->SetRenderState(D3DRS_STENCILFUNC, D3DCMP_ALWAYS);
			g_device->SetRenderState(D3DRS_STENCILPASS, D3DSTENCILOP_REPLACE);
			g_device->SetRenderState(D3DRS_STENCILFAIL, D3DSTENCILOP_KEEP);
			g_device->SetRenderState(D3DRS_STENCILZFAIL, D3DSTENCILOP_KEEP);
			g_device->SetRenderState(D3DRS_STENCILWRITEMASK, 0xff);
			g_device->SetRenderState(D3DRS_STENCILREF, 0x80);
			quad(0, 0, W/3.f, H, 0,0,0,0);
			g_device->SetRenderState(D3DRS_STENCILREF, 0x90);
			quad(W*2/3.f, 0, W/3.f, H, 0,0,0,0);
			g_device->SetRenderState(D3DRS_ZENABLE, TRUE);
			g_device->SetRenderState(D3DRS_STENCILREF, 0x80);
			g_device->SetRenderState(D3DRS_STENCILMASK, maskMode ? 0xf0 : 0x80);
			g_device->SetRenderState(D3DRS_STENCILFUNC, maskMode ? D3DCMP_GREATEREQUAL : D3DCMP_NOTEQUAL);
			g_device->SetVertexShader(D3DFVF_XYZ);
			for (int pass = 0; pass < 2; ++pass)
			{
				g_device->SetRenderState(D3DRS_CULLMODE, pass ? D3DCULL_CCW : D3DCULL_CW);
				g_device->SetRenderState(D3DRS_STENCILPASS, pass ? D3DSTENCILOP_DECRSAT : D3DSTENCILOP_INCR);
				if (batched)
				{
					g_device->SetTransform(D3DTS_WORLD, &unit);
					for (const auto& b : batches) check(g_device->DrawIndexedPrimitiveUP(D3DPT_TRIANGLELIST, 0,
						b.vertices.size(), b.indices.size()/3, b.indices.data(), D3DFMT_INDEX16, b.vertices.data(), sizeof(Position)), "batched shadow");
				}
				else for (size_t i = 0; i < transforms.size(); ++i)
				{
					g_device->SetTransform(D3DTS_WORLD, &transforms[pass ? transforms.size()-1-i : i]);
					check(g_device->DrawIndexedPrimitiveUP(D3DPT_TRIANGLELIST, 0, 8, 12, indices,
						D3DFMT_INDEX16, cube, sizeof(Position)), "separate shadow");
				}
			}
			g_device->SetRenderState(D3DRS_COLORWRITEENABLE, 0xf);
			g_device->SetRenderState(D3DRS_ZENABLE, FALSE);
			g_device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
			g_device->SetRenderState(D3DRS_STENCILFUNC, D3DCMP_NOTEQUAL);
			g_device->SetRenderState(D3DRS_STENCILREF, 0);
			g_device->SetRenderState(D3DRS_STENCILMASK, 0xf);
			g_device->SetRenderState(D3DRS_STENCILPASS, D3DSTENCILOP_KEEP);
			quad(0,0,W,H,0xff000000,0xff000000,0xff000000,0xff000000);
			g_device->EndScene();
			saveFrame(out + "/scene16_shadow_" + std::to_string(maskMode) + (batched ? "_batched.png" : "_separate.png"));
			IDirect3DSurface8 *back = nullptr, *image = nullptr;
			check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "shadow backbuffer");
			check(g_device->CreateImageSurface(W,H,D3DFMT_A8R8G8B8,&image), "shadow image");
			check(g_device->CopyRects(back,nullptr,0,image,nullptr), "shadow readback");
			D3DLOCKED_RECT lock;
			check(image->LockRect(&lock,nullptr,D3DLOCK_READONLY), "shadow pixels");
			int dark = 0;
			for (int y = 0; y < H; ++y) for (int x = 0; x < W; ++x)
			{
				DWORD pixel = ((DWORD*)((BYTE*)lock.pBits+y*lock.Pitch))[x];
				if (!(pixel & 0xffffff)) ++dark;
				if (!batched) reference.push_back(pixel);
				else if (pixel != reference[y*W+x]) ++failures;
			}
			if (dark == 0 || dark == W*H) ++failures; // reject a vacuous all-clear/all-shadow comparison
			image->UnlockRect(); image->Release(); back->Release();
			g_device->Present(nullptr,nullptr,nullptr,nullptr);
		}
	}
	g_device->SetRenderState(D3DRS_ZWRITEENABLE, TRUE);
	printf("scene16: shadow batch pixel comparison failures: %d (%d pixels, two masks)\n", failures, 2*W*H);
	return failures;
}

static int testModelSubmission(const std::string& out, D3DPRESENT_PARAMETERS pp)
{
	struct Pixel { int x, y; DWORD color; };
	int failures = 0, pixelChecks = 0;
	auto checkPixels = [&](const std::vector<Pixel>& pixels) {
		IDirect3DSurface8 *back = nullptr, *image = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "model backbuffer");
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "model image");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "model readback");
		D3DLOCKED_RECT lock;
		check(image->LockRect(&lock, nullptr, D3DLOCK_READONLY), "model pixels");
		for (const auto& expected : pixels)
		{
			const uint8_t* got = (const uint8_t*)lock.pBits + expected.y * lock.Pitch + expected.x * 4;
			for (int channel = 0; channel < 3; ++channel)
				if (abs(int(got[channel]) - int((expected.color >> (channel * 8)) & 255)) > 1) { ++failures; break; }
			++pixelChecks;
		}
		image->UnlockRect(); image->Release(); back->Release();
	};

	// Static/dynamic and 16/32-bit indices, odd start indices, reuse, failed and
	// read-only locks, writes/renames, NOOVERWRITE, DISCARD and release before flush.
	resetStates();
	g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
	g_device->SetRenderState(D3DRS_CLIPPLANEENABLE, 0);
	g_device->SetVertexShader(TLFVF);
	g_device->Clear(0, nullptr, D3DCLEAR_TARGET, 0xFF102030, 1, 0);
	g_device->BeginScene();
	std::vector<TLVertex> vertices;
	std::vector<Pixel> pixels;
	const DWORD red = 0xFFE04020, green = 0xFF20B060;
	for (int row = 0; row < 4; ++row) for (int col = 0; col < 12; ++col)
	{
		float x = col * 52.f + 26, y = row * 100.f + 50;
		for (DWORD color : {red, green})
		{
			vertices.push_back({x-20,y-25,.5f,1,color,0,0}); vertices.push_back({x+20,y-25,.5f,1,color,0,0});
			vertices.push_back({x-20,y+25,.5f,1,color,0,0}); vertices.push_back({x+20,y+25,.5f,1,color,0,0});
		}
		pixels.push_back({int(x),int(y), (col >= 4 && col < 8) || col >= 10 ? green : red});
	}
	IDirect3DVertexBuffer8* vb = nullptr;
	check(g_device->CreateVertexBuffer(vertices.size()*sizeof(TLVertex), 0, TLFVF, D3DPOOL_MANAGED, &vb), "model vertices");
	BYTE* data = nullptr;
	check(vb->Lock(0,0,&data,0), "model vertex lock"); memcpy(data,vertices.data(),vertices.size()*sizeof(TLVertex)); vb->Unlock();
	g_device->SetStreamSource(0,vb,sizeof(TLVertex));
	for (int row = 0; row < 4; ++row)
	{
		bool wide = row >= 2, dynamic = row % 2;
		unsigned stride = wide ? 4 : 2;
		IDirect3DIndexBuffer8* ib = nullptr;
		check(g_device->CreateIndexBuffer(24*stride,dynamic ? D3DUSAGE_DYNAMIC : 0,wide ? D3DFMT_INDEX32 : D3DFMT_INDEX16,D3DPOOL_DEFAULT,&ib), "model indices");
		auto write = [&](unsigned start, unsigned base, DWORD flags) {
			BYTE* target = nullptr; check(ib->Lock(start*stride,6*stride,&target,flags), "model index write");
			const unsigned indices[] = {base,base+1,base+2,base+2,base+1,base+3};
			for (unsigned i=0;i<6;++i) { if(wide) ((uint32_t*)target)[i]=indices[i]; else ((uint16_t*)target)[i]=indices[i]; }
			ib->Unlock();
		};
		write(1,0,0); write(9,0,0);
		for (int col = 0; col < 12; ++col)
		{
			if (col == 2) { BYTE* read = nullptr; check(ib->Lock(0,0,&read,D3DLOCK_READONLY), "model read-only lock"); ib->Unlock(); }
			if (col == 3) { BYTE* bad = nullptr; if (SUCCEEDED(ib->Lock(24*stride+1,0,&bad,0))) ++failures; }
			if (col == 4 || col == 10) write(1,4,0);
			if (col == 6) write(9,4,D3DLOCK_NOOVERWRITE);
			if (col == 8) write(1,0,dynamic ? D3DLOCK_DISCARD : 0);
			check(g_device->SetIndices(ib,(row*12+col)*8), "model base vertex");
			check(g_device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,8,col==6 || col==7 ? 9 : 1,2), "model indexed draw");
		}
		g_device->SetIndices(nullptr,0); ib->Release();
	}
	g_device->SetStreamSource(0,nullptr,0); vb->Release();
	g_device->EndScene();
	saveFrame(out+"/scene18_model_indices.png"); checkPixels(pixels);
	g_device->Present(nullptr,nullptr,nullptr,nullptr);

	// Unchanged light setters must preserve pending state, including after a
	// state block, an encoder boundary and a device reset.
	for (int phase = 0; phase < 2; ++phase)
	{
		if (phase) check(g_device->Reset(&pp), "model device reset");
		resetStates(); g_device->SetPixelShader(0); g_device->SetVertexShader(LITFVF);
		g_device->SetRenderState(D3DRS_ZENABLE,D3DZB_FALSE);
		g_device->SetRenderState(D3DRS_CLIPPLANEENABLE,0);
		g_device->SetRenderState(D3DRS_LIGHTING,TRUE); g_device->SetRenderState(D3DRS_COLORVERTEX,FALSE);
		g_device->SetRenderState(D3DRS_AMBIENT,0);
		g_device->SetRenderState(D3DRS_DIFFUSEMATERIALSOURCE,D3DMCS_MATERIAL);
		g_device->SetRenderState(D3DRS_AMBIENTMATERIALSOURCE,D3DMCS_MATERIAL);
		g_device->SetRenderState(D3DRS_EMISSIVEMATERIALSOURCE,D3DMCS_MATERIAL);
		for (int i=0;i<8;++i) g_device->LightEnable(i,FALSE);
		D3DMATERIAL8 material = {}; material.Diffuse = {1,1,1,1}; g_device->SetMaterial(&material);
		D3DMATRIX transform = identity(); g_device->SetTransform(D3DTS_VIEW,&transform); g_device->SetTransform(D3DTS_PROJECTION,&transform);
		const LitVertex quad[] = {{-.18f,-.18f,.5f,0,0,-1,0,0},{.18f,-.18f,.5f,0,0,-1,0,0},{-.18f,.18f,.5f,0,0,-1,0,0},{.18f,.18f,.5f,0,0,-1,0,0}};
		pixels.clear(); g_device->Clear(0,nullptr,D3DCLEAR_TARGET,0xFF102030,1,0); g_device->BeginScene();
		for (int i=0;i<16;++i)
		{
			DWORD color = i%2 ? green : red; BOOL enabled = i%4 != 3;
			D3DLIGHT8 light = {}; light.Type=D3DLIGHT_DIRECTIONAL; light.Direction={0,0,1};
			light.Diffuse={float((color>>16)&255)/255,float((color>>8)&255)/255,float(color&255)/255,1};
			g_device->SetLight(0,&light); g_device->LightEnable(0,enabled);
			DWORD block = 0; check(g_device->CreateStateBlock(D3DSBT_ALL,&block), "model light block");
			D3DLIGHT8 other = light; other.Diffuse={0,0,1,1}; g_device->SetLight(0,&other); g_device->LightEnable(0,!enabled);
			check(g_device->ApplyStateBlock(block), "model restore lights"); g_device->DeleteStateBlock(block);
			for (int repeat=0;repeat<8;++repeat) { g_device->SetLight(0,&light); g_device->LightEnable(0,enabled); }
			D3DLIGHT8 got = {}; BOOL gotEnabled = FALSE; g_device->GetLight(0,&got); g_device->GetLightEnable(0,&gotEnabled);
			if (memcmp(&got,&light,sizeof(light)) || gotEnabled != enabled) ++failures;
			transform._41=(i%4+.5f)*.5f-1; transform._42=1-(i/4+.5f)*.5f; g_device->SetTransform(D3DTS_WORLD,&transform);
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP,2,quad,sizeof(LitVertex));
			pixels.push_back({i%4*(W/4)+W/8,i/4*(H/4)+H/8,enabled ? color : 0});
			if (i==7) saveFrame(out+"/scene18_lights_boundary_"+std::to_string(phase)+".png");
		}
		g_device->EndScene(); saveFrame(out+"/scene18_model_lights_"+std::to_string(phase)+".png"); checkPixels(pixels);
		g_device->Present(nullptr,nullptr,nullptr,nullptr);
	}
	printf("scene18: %d pixel checks plus index-lock/light-state checks; %d failures\n",pixelChecks,failures);
	return failures;
}

static int testModelBatching(const std::string& out)
{
	resetStates();
	g_device->SetRenderState((D3DRENDERSTATETYPE)249, 1); // native model scope
	g_device->SetVertexShader(LITFVF); g_device->SetPixelShader(0);
	g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_TRUE);
	g_device->SetRenderState(D3DRS_ZWRITEENABLE, TRUE);
	g_device->SetRenderState(D3DRS_ZFUNC, D3DCMP_LESSEQUAL);
	g_device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
	g_device->SetRenderState(D3DRS_STENCILENABLE, FALSE);
	g_device->SetRenderState(D3DRS_LIGHTING, TRUE);
	g_device->SetRenderState(D3DRS_NORMALIZENORMALS, TRUE);
	g_device->SetRenderState(D3DRS_COLORVERTEX, FALSE);
	g_device->SetRenderState(D3DRS_AMBIENT, 0);
	g_device->SetRenderState(D3DRS_DIFFUSEMATERIALSOURCE, D3DMCS_MATERIAL);
	g_device->SetRenderState(D3DRS_AMBIENTMATERIALSOURCE, D3DMCS_MATERIAL);
	g_device->SetRenderState(D3DRS_EMISSIVEMATERIALSOURCE, D3DMCS_MATERIAL);
	for (int i=0;i<8;++i) g_device->LightEnable(i,FALSE);
	D3DLIGHT8 light = {}; light.Type=D3DLIGHT_DIRECTIONAL; light.Direction={0,0,1}; light.Diffuse={1,1,1,1};
	g_device->SetLight(0,&light); g_device->LightEnable(0,TRUE);
	D3DMATRIX unit=identity(); g_device->SetTransform(D3DTS_VIEW,&unit); g_device->SetTransform(D3DTS_PROJECTION,&unit);
	const LitVertex vertices[]={{-.07f,-.08f,0,0,0,-1,0,0},{.07f,-.08f,0,0,0,-1,0,0},{-.07f,.08f,0,0,0,-1,0,0},{.07f,.08f,0,0,0,-1,0,0}};
	const uint16_t indices[]={0,0,1,2,2,1,3};
	IDirect3DVertexBuffer8* vb=nullptr; IDirect3DIndexBuffer8* ib=nullptr; BYTE* data=nullptr;
	check(g_device->CreateVertexBuffer(sizeof(vertices),0,LITFVF,D3DPOOL_MANAGED,&vb),"batch vb");
	check(vb->Lock(0,0,&data,0),"batch vertices"); memcpy(data,vertices,sizeof(vertices)); vb->Unlock();
	check(g_device->CreateIndexBuffer(sizeof(indices),0,D3DFMT_INDEX16,D3DPOOL_MANAGED,&ib),"batch ib");
	check(ib->Lock(0,0,&data,0),"batch indices"); memcpy(data,indices,sizeof(indices)); ib->Unlock();
	g_device->SetStreamSource(0,vb,sizeof(LitVertex)); g_device->SetIndices(ib,0);
	g_device->Clear(0,nullptr,D3DCLEAR_TARGET|D3DCLEAR_ZBUFFER,0xFF102030,1,0); g_device->BeginScene();
	D3DMATERIAL8 material={}; material.Diffuse={.8f,.2f,.1f,1}; g_device->SetMaterial(&material);
	for (int i=0;i<80;++i)
	{
		D3DMATRIX world=identity(); world._41=(i%10+.5f)*.2f-1; world._42=1-(i/10+.5f)*.25f;
		world._43=.5f; world._11=i%3 ? .75f : -.75f; world._33=i%2 ? .5f : 1.25f;
		if (i==40) { material.Diffuse={.1f,.7f,.2f,1}; g_device->SetMaterial(&material); }
		if (i==60) { check(vb->Lock(0,0,&data,0),"batch rename"); memcpy(data,vertices,sizeof(vertices)); vb->Unlock(); }
		if (i==60) { check(ib->Lock(0,0,&data,0),"batch index rename"); memcpy(data,indices,sizeof(indices)); ib->Unlock(); }
		g_device->SetTransform(D3DTS_WORLD,&world);
		check(g_device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,4,1,2),"batch draw");
		if (i==19) saveFrame(out+"/scene19_batch_boundary.png");
	}
	// No world setter: the final batched world must remain the inherited state.
	material.Diffuse={.2f,.1f,.8f,1}; g_device->SetMaterial(&material);
	g_device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST,0,4,1,2);
	g_device->SetStreamSource(0,nullptr,0); g_device->SetIndices(nullptr,0); vb->Release(); ib->Release();
	g_device->EndScene(); saveFrame(out+"/scene19_model_batching.png");
	g_device->SetRenderState((D3DRENDERSTATETYPE)249, 0);
	IDirect3DSurface8 *back=nullptr,*image=nullptr; g_device->GetBackBuffer(0,D3DBACKBUFFER_TYPE_MONO,&back);
	g_device->CreateImageSurface(W,H,D3DFMT_A8R8G8B8,&image); check(g_device->CopyRects(back,nullptr,0,image,nullptr),"batch readback");
	D3DLOCKED_RECT lock; check(image->LockRect(&lock,nullptr,D3DLOCK_READONLY),"batch pixels"); int failures=0;
	for (int i=0;i<80;++i)
	{
		const uint8_t* pixel=(uint8_t*)lock.pBits+(i/10*(H/8)+H/16)*lock.Pitch+(i%10*(W/10)+W/20)*4;
		const int red[3]={26,51,204}, green[3]={51,179,26}, blue[3]={204,26,51};
		const int* expected=i==79 ? blue : i<40 ? red : green;
		for (int c=0;c<3;++c) if (abs(int(pixel[c])-expected[c])>1) { ++failures; break; }
	}
	image->UnlockRect(); image->Release(); back->Release(); g_device->Present(nullptr,nullptr,nullptr,nullptr);
	printf("scene19: 80 instancing pixel checks; %d failures\n",failures);
	return failures;
}

int main(int argc, char** argv)
{
	std::string out = argc > 1 ? argv[1] : ".";
	Win32Shim_SetCommandLine(argc, argv);
	Win32Shim_Initialize();

	WNDCLASS wc = {};
	wc.lpfnWndProc = WndProc;
	wc.lpszClassName = "D3D8Test";
	RegisterClass(&wc);
	HWND hwnd = CreateWindow("D3D8Test", "D3D8 Metal Test", WS_CAPTION | WS_VISIBLE, 0, 0, W, H, nullptr, nullptr, nullptr, nullptr);

	IDirect3D8* d3d = Direct3DCreate8(D3D_SDK_VERSION);
	D3DPRESENT_PARAMETERS pp = {};
	pp.BackBufferWidth = W;
	pp.BackBufferHeight = H;
	pp.BackBufferFormat = D3DFMT_X8R8G8B8;
	pp.BackBufferCount = 1;
	pp.SwapEffect = D3DSWAPEFFECT_DISCARD;
	pp.hDeviceWindow = hwnd;
	pp.Windowed = TRUE;
	pp.EnableAutoDepthStencil = TRUE;
	pp.AutoDepthStencilFormat = D3DFMT_D24S8;
	check(d3d->CreateDevice(0, D3DDEVTYPE_HAL, hwnd, D3DCREATE_HARDWARE_VERTEXPROCESSING, &pp, &g_device), "CreateDevice");

	IDirect3DTexture8* checker = makeChecker(D3DFMT_A8R8G8B8, 64, 0xFFFFFFFF, 0xFF404040);
	IDirect3DTexture8* checker565 = makeChecker(D3DFMT_R5G6B5, 64, 0xFFFFFF00, 0xFF00FF00);
	IDirect3DTexture8* checker4444 = makeChecker(D3DFMT_A4R4G4B4, 64, 0xFFFFFFFF, 0x00000000);
	IDirect3DTexture8* dxt = makeDXT1();

	// Draw call benchmark: d3d8metal_test <dir> --bench
	if (argc > 2 && strcmp(argv[2], "--bench") == 0)
	{
		LitVertex quadVerts[4] = {
			{ -0.1f, -0.1f, 0, 0, 0, -1, 0, 0 }, { 0.1f, -0.1f, 0, 0, 0, -1, 1, 0 },
			{ -0.1f, 0.1f, 0, 0, 0, -1, 0, 1 }, { 0.1f, 0.1f, 0, 0, 0, -1, 1, 1 },
		};
		IDirect3DVertexBuffer8* vb = nullptr;
		check(g_device->CreateVertexBuffer(sizeof(quadVerts), D3DUSAGE_WRITEONLY, LITFVF, D3DPOOL_MANAGED, &vb), "bench vb");
		BYTE* vdata = nullptr;
		vb->Lock(0, 0, &vdata, 0);
		memcpy(vdata, quadVerts, sizeof(quadVerts));
		vb->Unlock();
		IDirect3DIndexBuffer8* ib = nullptr;
		check(g_device->CreateIndexBuffer(6 * 2, D3DUSAGE_WRITEONLY, D3DFMT_INDEX16, D3DPOOL_MANAGED, &ib), "bench ib");
		BYTE* idata = nullptr;
		ib->Lock(0, 0, &idata, 0);
		const uint16_t indices[6] = { 0, 1, 2, 2, 1, 3 };
		memcpy(idata, indices, sizeof(indices));
		ib->Unlock();
		IDirect3DTexture8* textures[4] = { checker, checker565, checker4444, dxt };
		D3DLIGHT8 light = {};
		light.Type = D3DLIGHT_DIRECTIONAL;
		light.Diffuse = { 1, 1, 1, 1 };
		light.Direction = { 0, 0, 1 };
		const int frames = 200, draws = 5000, upDraws = 500;
		double cpuMs = 0, totalMs = 0;
		for (int frame = 0; frame < frames; ++frame)
		{
			LARGE_INTEGER t0, t1, t2, freq;
			QueryPerformanceFrequency(&freq);
			QueryPerformanceCounter(&t0);
			resetStates();
			g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
			g_device->BeginScene();
			setCamera();
			g_device->SetRenderState(D3DRS_LIGHTING, TRUE);
			g_device->SetLight(0, &light);
			g_device->LightEnable(0, TRUE);
			g_device->SetStreamSource(0, vb, sizeof(LitVertex));
			g_device->SetIndices(ib, 0);
			g_device->SetVertexShader(LITFVF);
			for (int i = 0; i < draws; ++i)
			{
				D3DMATRIX world = identity();
				world._41 = ((i % 100) - 50) * 0.05f;
				world._42 = ((i / 100) % 50 - 25) * 0.05f;
				world._43 = (float)(i % 7);
				g_device->SetTransform(D3DTS_WORLD, &world);
				D3DMATERIAL8 mat = {};
				mat.Diffuse = { (i & 1) ? 1.0f : 0.5f, 0.8f, 0.6f, 1.0f };
				mat.Ambient = { 0.2f, 0.2f, 0.2f, 1.0f };
				g_device->SetMaterial(&mat);
				modulateStage0(textures[i & 3]);
				g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, (i & 4) != 0);
				g_device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
				g_device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
				g_device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST, 0, 4, 0, 2);
			}
			g_device->SetRenderState(D3DRS_LIGHTING, FALSE);
			for (int i = 0; i < upDraws; ++i)
				quad((float)(i % 60) * 10, (float)(i / 60) * 10, 8, 8, 0xFFFFFFFF, 0xFFFF0000, 0xFF00FF00, 0xFF0000FF);
			g_device->EndScene();
			QueryPerformanceCounter(&t1);
			g_device->Present(nullptr, nullptr, nullptr, nullptr);
			QueryPerformanceCounter(&t2);
			if (frame >= 10)
			{
				cpuMs += (double)(t1.QuadPart - t0.QuadPart) * 1000.0 / freq.QuadPart;
				totalMs += (double)(t2.QuadPart - t0.QuadPart) * 1000.0 / freq.QuadPart;
			}
		}
		printf("bench: %d draws per frame, %.2f ms CPU per frame, %.2f ms per frame with Present\n", draws + upDraws,
			cpuMs / (frames - 10), totalMs / (frames - 10));
		vb->Release();
		ib->Release();
		return 0;
	}

	// Scene 1: clear + gouraud triangle + textured quads of each format.
	resetStates();
	g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF203040, 1.0f, 0);
	g_device->BeginScene();
	{
		TLVertex tri[3] = {
			{ 100, 40, 0.5f, 1, 0xFFFF0000, 0, 0 },
			{ 180, 180, 0.5f, 1, 0xFF00FF00, 0, 0 },
			{ 20, 180, 0.5f, 1, 0xFF0000FF, 0, 0 },
		};
		g_device->SetVertexShader(TLFVF);
		g_device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 1, tri, sizeof(TLVertex));
	}
	modulateStage0(checker);
	quad(220, 40, 128, 128, 0xFFFFFFFF, 0xFFFF8080, 0xFF8080FF, 0xFF80FF80);
	modulateStage0(checker565);
	quad(380, 40, 128, 128, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
	modulateStage0(dxt);
	quad(20, 240, 128, 128, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
	// Alpha blended 4444 checker over a red bar.
	resetStates();
	quad(160, 290, 400, 30, 0xFFFF0000, 0xFFFF0000, 0xFFFF0000, 0xFFFF0000);
	modulateStage0(checker4444);
	g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
	g_device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
	g_device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
	quad(220, 240, 128, 128, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
	// Alpha test: half transparent diffuse is rejected where alpha < ref.
	resetStates();
	modulateStage0(checker4444);
	g_device->SetRenderState(D3DRS_ALPHATESTENABLE, TRUE);
	g_device->SetRenderState(D3DRS_ALPHAREF, 0x80);
	g_device->SetRenderState(D3DRS_ALPHAFUNC, D3DCMP_GREATEREQUAL);
	quad(380, 240, 128, 128, 0xFF00FFFF, 0xFF00FFFF, 0xFF00FFFF, 0xFF00FFFF);
	g_device->EndScene();
	saveFrame(out + "/scene1_basic.png");
	g_device->Present(nullptr, nullptr, nullptr, nullptr);

	// Scene 2: lit, textured, depth tested cube with fog and a second stage.
	resetStates();
	g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF101010, 1.0f, 0);
	g_device->BeginScene();
	setCamera();
	g_device->SetRenderState(D3DRS_LIGHTING, TRUE);
	g_device->SetRenderState(D3DRS_CULLMODE, D3DCULL_CCW);
	g_device->SetRenderState(D3DRS_AMBIENT, 0xFF202020);
	D3DMATERIAL8 mat = {};
	mat.Diffuse = { 1.0f, 0.6f, 0.3f, 1.0f };
	mat.Ambient = { 1.0f, 1.0f, 1.0f, 1.0f };
	mat.Specular = { 1.0f, 1.0f, 1.0f, 1.0f };
	mat.Power = 20.0f;
	g_device->SetMaterial(&mat);
	g_device->SetRenderState(D3DRS_DIFFUSEMATERIALSOURCE, D3DMCS_MATERIAL);
	g_device->SetRenderState(D3DRS_SPECULARENABLE, TRUE);
	D3DLIGHT8 light = {};
	light.Type = D3DLIGHT_DIRECTIONAL;
	light.Diffuse = { 1.0f, 1.0f, 1.0f, 1.0f };
	light.Specular = { 1.0f, 1.0f, 1.0f, 1.0f };
	light.Direction = { 0.5f, -0.7f, 0.5f };
	g_device->SetLight(0, &light);
	g_device->LightEnable(0, TRUE);
	modulateStage0(checker);
	g_device->SetTextureStageState(0, D3DTSS_COLORARG2, D3DTA_DIFFUSE);
	g_device->SetRenderState(D3DRS_FOGENABLE, TRUE);
	g_device->SetRenderState(D3DRS_FOGCOLOR, 0xFF3060A0);
	g_device->SetRenderState(D3DRS_FOGVERTEXMODE, D3DFOG_LINEAR);
	float fs = 4.0f, fe = 9.0f;
	g_device->SetRenderState(D3DRS_FOGSTART, *(DWORD*)&fs);
	g_device->SetRenderState(D3DRS_FOGEND, *(DWORD*)&fe);
	drawCube(0.6f);
	// Second cube further back, more fogged.
	D3DMATRIX world = identity();
	world._41 = 2.5f;
	world._43 = 4.0f;
	g_device->SetTransform(D3DTS_WORLD, &world);
	{
		D3DMATRIX v;
		g_device->GetTransform(D3DTS_VIEW, &v);
	}
	drawCube(0.2f, 2.5f, 4.0f);
	g_device->EndScene();
	saveFrame(out + "/scene2_lit.png");
	g_device->Present(nullptr, nullptr, nullptr, nullptr);

	// Scene 3: stencil mask and texture coordinate transform / multi-stage.
	resetStates();
	g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER | D3DCLEAR_STENCIL, 0xFF000000, 1.0f, 0);
	g_device->BeginScene();
	// Write stencil = 1 inside a circle-ish fan, without color.
	g_device->SetRenderState(D3DRS_STENCILENABLE, TRUE);
	g_device->SetRenderState(D3DRS_STENCILFUNC, D3DCMP_ALWAYS);
	g_device->SetRenderState(D3DRS_STENCILREF, 1);
	g_device->SetRenderState(D3DRS_STENCILPASS, D3DSTENCILOP_REPLACE);
	g_device->SetRenderState(D3DRS_COLORWRITEENABLE, 0);
	{
		std::vector<TLVertex> fan;
		fan.push_back({ 320, 240, 0.5f, 1, 0xFFFFFFFF, 0, 0 });
		for (int i = 0; i <= 32; ++i)
		{
			float a = i / 32.0f * 6.2831853f;
			fan.push_back({ 320 + cosf(a) * 180, 240 + sinf(a) * 180, 0.5f, 1, 0xFFFFFFFF, 0, 0 });
		}
		g_device->SetVertexShader(TLFVF);
		g_device->DrawPrimitiveUP(D3DPT_TRIANGLEFAN, 32, fan.data(), sizeof(TLVertex));
	}
	g_device->SetRenderState(D3DRS_COLORWRITEENABLE, 0xF);
	g_device->SetRenderState(D3DRS_STENCILFUNC, D3DCMP_EQUAL);
	g_device->SetRenderState(D3DRS_STENCILPASS, D3DSTENCILOP_KEEP);
	// Two stages: checker modulated, plus a scrolled/scaled 565 checker added.
	modulateStage0(checker);
	g_device->SetTexture(1, checker565);
	g_device->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_ADDSIGNED);
	g_device->SetTextureStageState(1, D3DTSS_COLORARG1, D3DTA_TEXTURE);
	g_device->SetTextureStageState(1, D3DTSS_COLORARG2, D3DTA_CURRENT);
	g_device->SetTextureStageState(1, D3DTSS_ALPHAOP, D3DTOP_SELECTARG2);
	g_device->SetTextureStageState(1, D3DTSS_ALPHAARG2, D3DTA_CURRENT);
	g_device->SetTextureStageState(1, D3DTSS_TEXCOORDINDEX, 0);
	g_device->SetTextureStageState(1, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_COUNT2);
	D3DMATRIX tm = identity();
	tm._11 = 3.0f;
	tm._22 = 3.0f;
	tm._31 = 0.25f; // translation for 2D coordinates lives in the third row
	g_device->SetTransform(D3DTS_TEXTURE1, &tm);
	quad(0, 0, (float)W, (float)H, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
	g_device->SetTextureStageState(1, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_DISABLE);
	g_device->EndScene();
	saveFrame(out + "/scene3_stencil.png");
	g_device->Present(nullptr, nullptr, nullptr, nullptr);

	// Scene 4: render to texture, then draw the texture.
	resetStates();
	IDirect3DTexture8* rtTex = nullptr;
	check(g_device->CreateTexture(128, 128, 1, D3DUSAGE_RENDERTARGET, D3DFMT_A8R8G8B8, D3DPOOL_DEFAULT, &rtTex), "rt texture");
	IDirect3DSurface8* rtSurf = nullptr;
	rtTex->GetSurfaceLevel(0, &rtSurf);
	IDirect3DSurface8* oldRT = nullptr;
	IDirect3DSurface8* oldDS = nullptr;
	g_device->GetRenderTarget(&oldRT);
	g_device->GetDepthStencilSurface(&oldDS);
	g_device->SetRenderTarget(rtSurf, nullptr);
	g_device->Clear(0, nullptr, D3DCLEAR_TARGET, 0xFF0080FF, 1.0f, 0);
	g_device->BeginScene();
	{
		TLVertex tri[3] = {
			{ 64, 10, 0.5f, 1, 0xFFFFFF00, 0, 0 },
			{ 118, 118, 0.5f, 1, 0xFFFF00FF, 0, 0 },
			{ 10, 118, 0.5f, 1, 0xFF00FFFF, 0, 0 },
		};
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		g_device->SetVertexShader(TLFVF);
		g_device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 1, tri, sizeof(TLVertex));
	}
	g_device->EndScene();
	g_device->SetRenderTarget(oldRT, oldDS);
	g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF303030, 1.0f, 0);
	g_device->BeginScene();
	modulateStage0(rtTex);
	g_device->SetTextureStageState(0, D3DTSS_MINFILTER, D3DTEXF_LINEAR);
	g_device->SetTextureStageState(0, D3DTSS_MAGFILTER, D3DTEXF_LINEAR);
	quad(100, 50, 440, 380, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
	g_device->EndScene();
	saveFrame(out + "/scene4_rendertarget.png");
	g_device->Present(nullptr, nullptr, nullptr, nullptr);
	rtSurf->Release();
	oldRT->Release();
	if (oldDS)
		oldDS->Release();

	// Scene 5: text rendering through GDI on a DIB, uploaded as an A4R4G4B4 texture.
	{
		HDC screen = GetDC(hwnd);
		HFONT font = CreateFont(-24, 0, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0, ANTIALIASED_QUALITY, VARIABLE_PITCH, "Arial");
		BITMAPINFOHEADER bi = {};
		bi.biSize = sizeof(bi);
		bi.biWidth = 256;
		bi.biHeight = -64;
		bi.biPlanes = 1;
		bi.biBitCount = 24;
		uint8_t* bits = nullptr;
		HBITMAP bmp = CreateDIBSection(screen, (BITMAPINFO*)&bi, DIB_RGB_COLORS, (void**)&bits, nullptr, 0);
		HDC mem = CreateCompatibleDC(screen);
		SelectObject(mem, bmp);
		SelectObject(mem, font);
		SetBkColor(mem, RGB(0, 0, 0));
		SetTextColor(mem, RGB(255, 255, 255));
		RECT r = { 0, 0, 256, 64 };
		const wchar_t* text = L"Generals Zero Hour";
		ExtTextOutW(mem, 4, 0, ETO_OPAQUE, &r, text, (UINT)wcslen(text), nullptr);
		TEXTMETRIC tm2;
		GetTextMetrics(mem, &tm2);
		SIZE sz;
		GetTextExtentPoint32W(mem, text, (int)wcslen(text), &sz);
		printf("font height %ld ascent %ld extent %ldx%ld\n", (long)tm2.tmHeight, (long)tm2.tmAscent, (long)sz.cx, (long)sz.cy);

		IDirect3DTexture8* textTex = nullptr;
		check(g_device->CreateTexture(256, 64, 1, 0, D3DFMT_A4R4G4B4, D3DPOOL_MANAGED, &textTex), "text tex");
		D3DLOCKED_RECT lr;
		textTex->LockRect(0, &lr, nullptr, 0);
		int stride = ((256 * 3) + 3) & ~3;
		for (int y = 0; y < 64; ++y)
			for (int x = 0; x < 256; ++x)
			{
				uint8_t v = bits[y * stride + x * 3];
				((uint16_t*)((uint8_t*)lr.pBits + y * lr.Pitch))[x] = (uint16_t)(((v >> 4) << 12) | 0x0FFF);
			}
		textTex->UnlockRect(0);

		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF402020, 1.0f, 0);
		g_device->BeginScene();
		modulateStage0(textTex);
		g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
		g_device->SetRenderState(D3DRS_SRCBLEND, D3DBLEND_SRCALPHA);
		g_device->SetRenderState(D3DRS_DESTBLEND, D3DBLEND_INVSRCALPHA);
		quad(40, 100, 256, 64, 0xFFFFFF00, 0xFFFFFF00, 0xFFFFFF00, 0xFFFFFF00);
		quad(40, 200, 512, 128, 0xFF80FFFF, 0xFF80FFFF, 0xFF80FFFF, 0xFF80FFFF);
		g_device->EndScene();
		saveFrame(out + "/scene5_text.png");
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
		textTex->Release();
		DeleteObject(bmp);
		DeleteObject(font);
		DeleteDC(mem);
		ReleaseDC(hwnd, screen);
	}

	// Scene 6: point sprites with distance scaling (used for snow).
	{
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF102030, 1.0f, 0);
		g_device->BeginScene();
		setCamera();
		D3DMATRIX world = identity();
		g_device->SetTransform(D3DTS_WORLD, &world);
		modulateStage0(checker);
		g_device->SetRenderState(D3DRS_POINTSPRITEENABLE, TRUE);
		g_device->SetRenderState(D3DRS_POINTSCALEENABLE, TRUE);
		float size = 0.6f, mn = 1.0f, mx = 64.0f, a = 0.0f, b = 0.0f, c = 1.0f;
		g_device->SetRenderState(D3DRS_POINTSIZE, *(DWORD*)&size);
		g_device->SetRenderState(D3DRS_POINTSIZE_MIN, *(DWORD*)&mn);
		g_device->SetRenderState(D3DRS_POINTSIZE_MAX, *(DWORD*)&mx);
		g_device->SetRenderState(D3DRS_POINTSCALE_A, *(DWORD*)&a);
		g_device->SetRenderState(D3DRS_POINTSCALE_B, *(DWORD*)&b);
		g_device->SetRenderState(D3DRS_POINTSCALE_C, *(DWORD*)&c);
		struct PointVertex { float x, y, z; DWORD color; };
		std::vector<PointVertex> pts;
		for (int z = 0; z < 5; ++z)
			for (int x = -3; x <= 3; ++x)
				pts.push_back({ x * 1.2f, 0.0f, z * 2.0f, 0xFFFFFFFF });
		g_device->SetVertexShader(D3DFVF_XYZ | D3DFVF_DIFFUSE);
		g_device->DrawPrimitiveUP(D3DPT_POINTLIST, (UINT)pts.size(), pts.data(), sizeof(PointVertex));
		g_device->SetRenderState(D3DRS_POINTSPRITEENABLE, FALSE);
		g_device->SetRenderState(D3DRS_POINTSCALEENABLE, FALSE);
		g_device->EndScene();
		saveFrame(out + "/scene6_pointsprites.png");
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}

	// Scene 7: the terrain techniques of the fixed function path, checked pixel by pixel:
	// texture coordinates generated from the camera space position through a texture matrix,
	// a second stage blending by texture alpha, and linear vertex fog.
	int failures7 = 0;
	{
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		D3DMATRIX world = identity(), view = identity(), proj = identity();
		// Orthographic projection of x in [-1, 1], y in [-0.75, 0.75], z in [0, 1].
		proj._11 = 1.0f;
		proj._22 = 1.0f / 0.75f;
		g_device->SetTransform(D3DTS_WORLD, &world);
		g_device->SetTransform(D3DTS_VIEW, &view);
		g_device->SetTransform(D3DTS_PROJECTION, &proj);

		// Stage 0: checker from u = 0.5x + 0.5, v = -0.5y / 0.75 + 0.5.
		modulateStage0(checker);
		g_device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
		g_device->SetTextureStageState(0, D3DTSS_MIPFILTER, D3DTEXF_NONE);
		g_device->SetTextureStageState(0, D3DTSS_TEXCOORDINDEX, D3DTSS_TCI_CAMERASPACEPOSITION);
		g_device->SetTextureStageState(0, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_COUNT2);
		D3DMATRIX t0 = identity();
		t0._11 = 0.5f;
		t0._22 = -0.5f / 0.75f;
		t0._41 = 0.5f;
		t0._42 = 0.5f;
		g_device->SetTransform(D3DTS_TEXTURE0, &t0);

		// Stage 1: red with alpha rising from left to right, blended over stage 0 by its alpha.
		IDirect3DTexture8* ramp = nullptr;
		check(g_device->CreateTexture(64, 64, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &ramp), "ramp");
		D3DLOCKED_RECT lr;
		check(ramp->LockRect(0, &lr, nullptr, 0), "ramp lock");
		for (int y = 0; y < 64; ++y)
			for (int x = 0; x < 64; ++x)
				((DWORD*)((uint8_t*)lr.pBits + y * lr.Pitch))[x] = ((DWORD)(x * 4) << 24) | 0x00FF0000;
		ramp->UnlockRect(0);
		g_device->SetTexture(1, ramp);
		g_device->SetTextureStageState(1, D3DTSS_COLOROP, D3DTOP_BLENDTEXTUREALPHA);
		g_device->SetTextureStageState(1, D3DTSS_COLORARG1, D3DTA_TEXTURE);
		g_device->SetTextureStageState(1, D3DTSS_COLORARG2, D3DTA_CURRENT);
		g_device->SetTextureStageState(1, D3DTSS_ALPHAOP, D3DTOP_SELECTARG2);
		g_device->SetTextureStageState(1, D3DTSS_ALPHAARG2, D3DTA_CURRENT);
		g_device->SetTextureStageState(1, D3DTSS_MINFILTER, D3DTEXF_POINT);
		g_device->SetTextureStageState(1, D3DTSS_MAGFILTER, D3DTEXF_POINT);
		g_device->SetTextureStageState(1, D3DTSS_MIPFILTER, D3DTEXF_NONE);
		g_device->SetTextureStageState(1, D3DTSS_TEXCOORDINDEX, 1 | D3DTSS_TCI_CAMERASPACEPOSITION);
		g_device->SetTextureStageState(1, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_COUNT2);
		g_device->SetTransform(D3DTS_TEXTURE1, &t0);

		// Linear vertex fog over view space depth 0..1; the quad at depth 0.25 is 75% visible.
		float fogStart = 0.0f, fogEnd = 1.0f;
		g_device->SetRenderState(D3DRS_FOGENABLE, TRUE);
		g_device->SetRenderState(D3DRS_FOGCOLOR, 0xFF0000FF);
		g_device->SetRenderState(D3DRS_FOGVERTEXMODE, D3DFOG_LINEAR);
		g_device->SetRenderState(D3DRS_FOGTABLEMODE, D3DFOG_NONE);
		g_device->SetRenderState(D3DRS_FOGSTART, *(DWORD*)&fogStart);
		g_device->SetRenderState(D3DRS_FOGEND, *(DWORD*)&fogEnd);

		struct PosVertex { float x, y, z; DWORD color; };
		PosVertex v[4] = {
			{ -1.0f, 0.75f, 0.25f, 0xFFFFFFFF },
			{ 1.0f, 0.75f, 0.25f, 0xFFFFFFFF },
			{ -1.0f, -0.75f, 0.25f, 0xFFFFFFFF },
			{ 1.0f, -0.75f, 0.25f, 0xFFFFFFFF },
		};
		g_device->SetVertexShader(D3DFVF_XYZ | D3DFVF_DIFFUSE);
		g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(PosVertex));
		g_device->EndScene();
		saveFrame(out + "/scene7_terrain.png");

		// Compare with the expected result.
		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		int checked = 0;
		for (int py = 0; py < H; py += 7)
		{
			for (int px = 0; px < W; px += 7)
			{
				// Direct3D 8 samples attributes at integer pixel coordinates.
				float x = ((float)px / W) * 2.0f - 1.0f, y = (1.0f - (float)py / H * 2.0f) * 0.75f;
				float u = 0.5f * x + 0.5f, vv = -0.5f * y / 0.75f + 0.5f;
				float tu = u * 64.0f, tv = vv * 64.0f;
				// Skip pixels on texel edges, where rounding may pick either texel.
				if (fabsf(tu - roundf(tu)) < 0.05f || fabsf(tv - roundf(tv)) < 0.05f)
					continue;
				int ix = (int)tu, iy = (int)tv;
				bool on = ((ix / 8) + (iy / 8)) & 1;
				const float g = on ? 64.0f / 255.0f : 1.0f; // checker colors 0xFFFFFFFF and 0xFF404040
				float base[3] = { g, g, g };
				float a = (ix * 4) / 255.0f;
				float rgb[3] = { 1.0f * a + base[0] * (1 - a), base[1] * (1 - a), base[2] * (1 - a) };
				const float fogBlue[3] = { 0.0f, 0.0f, 1.0f };
				float expect[3];
				for (int c = 0; c < 3; ++c)
					expect[c] = 0.75f * rgb[c] + 0.25f * fogBlue[c];
				const uint8_t* pix = (const uint8_t*)lr.pBits + py * lr.Pitch + px * 4;
				int got[3] = { pix[2], pix[1], pix[0] };
				++checked;
				for (int c = 0; c < 3; ++c)
				{
					if (abs(got[c] - (int)lroundf(expect[c] * 255.0f)) > 3)
					{
						if (failures7 < 5)
							printf("scene7 mismatch at %d,%d: got %d %d %d, expected %.0f %.0f %.0f\n", px, py, got[0], got[1], got[2],
								expect[0] * 255, expect[1] * 255, expect[2] * 255);
						++failures7;
						break;
					}
				}
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene7: %d of %d pixels match\n", checked - failures7, checked);
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
		g_device->SetRenderState(D3DRS_FOGENABLE, FALSE);
		g_device->SetTexture(1, nullptr);
		ramp->Release();
	}

	// Scene 8: texture stage operations compared with the Direct3D 8 formulas, one grid cell per case.
	int failures8 = 0;
	{
		struct Color4 { float r, g, b, a; };
		auto fromDword = [](DWORD c) { return Color4{ ((c >> 16) & 255) / 255.0f, ((c >> 8) & 255) / 255.0f, (c & 255) / 255.0f, (c >> 24) / 255.0f }; };
		const DWORD texColor = 0xA0C04020, diffColor = 0x60408090, specColor = 0x00205030, tfColor = 0xC0306080;
		const Color4 T = fromDword(texColor), D = fromDword(diffColor), S = fromDword(specColor), F = fromDword(tfColor);

		IDirect3DTexture8* solid = nullptr;
		check(g_device->CreateTexture(4, 4, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &solid), "solid");
		D3DLOCKED_RECT lr;
		check(solid->LockRect(0, &lr, nullptr, 0), "solid lock");
		for (int y = 0; y < 4; ++y)
			for (int x = 0; x < 4; ++x)
				((DWORD*)((uint8_t*)lr.pBits + y * lr.Pitch))[x] = texColor;
		solid->UnlockRect(0);

		auto arg = [&](DWORD a, const Color4& current, const Color4& temp) {
			Color4 v;
			switch (a & D3DTA_SELECTMASK)
			{
			case D3DTA_DIFFUSE: v = D; break;
			case D3DTA_CURRENT: v = current; break;
			case D3DTA_TEXTURE: v = T; break;
			case D3DTA_TFACTOR: v = F; break;
			case D3DTA_SPECULAR: v = S; break;
			default: v = temp; break;
			}
			if (a & D3DTA_COMPLEMENT)
				v = { 1 - v.r, 1 - v.g, 1 - v.b, 1 - v.a };
			if (a & D3DTA_ALPHAREPLICATE)
				v = { v.a, v.a, v.a, v.a };
			return v;
		};
		auto clamp01 = [](float x) { return x < 0 ? 0.0f : (x > 1 ? 1.0f : x); };
		// Applies an operation to one channel; a0 is the third argument, alphas are the blend factors.
		auto op = [&](DWORD o, float a1, float a2, float a0, const Color4& current, Color4 arg1Full) {
			switch (o)
			{
			case D3DTOP_SELECTARG1: return a1;
			case D3DTOP_SELECTARG2: return a2;
			case D3DTOP_MODULATE: return a1 * a2;
			case D3DTOP_MODULATE2X: return clamp01(a1 * a2 * 2);
			case D3DTOP_MODULATE4X: return clamp01(a1 * a2 * 4);
			case D3DTOP_ADD: return clamp01(a1 + a2);
			case D3DTOP_ADDSIGNED: return clamp01(a1 + a2 - 0.5f);
			case D3DTOP_ADDSIGNED2X: return clamp01((a1 + a2 - 0.5f) * 2);
			case D3DTOP_SUBTRACT: return clamp01(a1 - a2);
			case D3DTOP_ADDSMOOTH: return clamp01(a1 + a2 - a1 * a2);
			case D3DTOP_BLENDDIFFUSEALPHA: return a1 * D.a + a2 * (1 - D.a);
			case D3DTOP_BLENDTEXTUREALPHA: return a1 * T.a + a2 * (1 - T.a);
			case D3DTOP_BLENDFACTORALPHA: return a1 * F.a + a2 * (1 - F.a);
			case D3DTOP_BLENDTEXTUREALPHAPM: return clamp01(a1 + a2 * (1 - T.a));
			case D3DTOP_BLENDCURRENTALPHA: return a1 * current.a + a2 * (1 - current.a);
			case D3DTOP_MODULATEALPHA_ADDCOLOR: return clamp01(a1 + arg1Full.a * a2);
			case D3DTOP_MODULATECOLOR_ADDALPHA: return clamp01(a1 * a2 + arg1Full.a);
			case D3DTOP_MODULATEINVALPHA_ADDCOLOR: return clamp01((1 - arg1Full.a) * a2 + a1);
			case D3DTOP_MODULATEINVCOLOR_ADDALPHA: return clamp01((1 - a1) * a2 + arg1Full.a);
			case D3DTOP_MULTIPLYADD: return clamp01(a1 * a2 + a0); // as hardware does it, see Wine's ffp code
			case D3DTOP_LERP: return a0 * a1 + (1 - a0) * a2;
			}
			return 0.0f;
		};

		struct Case { DWORD colorOp, c1, c2, c0, alphaOp, a1, a2; };
		std::vector<Case> cases;
		const DWORD colorOps[] = { D3DTOP_SELECTARG1, D3DTOP_SELECTARG2, D3DTOP_MODULATE, D3DTOP_MODULATE2X, D3DTOP_MODULATE4X,
			D3DTOP_ADD, D3DTOP_ADDSIGNED, D3DTOP_ADDSIGNED2X, D3DTOP_SUBTRACT, D3DTOP_ADDSMOOTH, D3DTOP_BLENDDIFFUSEALPHA,
			D3DTOP_BLENDTEXTUREALPHA, D3DTOP_BLENDFACTORALPHA, D3DTOP_BLENDTEXTUREALPHAPM, D3DTOP_BLENDCURRENTALPHA,
			D3DTOP_MODULATEALPHA_ADDCOLOR, D3DTOP_MODULATECOLOR_ADDALPHA, D3DTOP_MODULATEINVALPHA_ADDCOLOR,
			D3DTOP_MODULATEINVCOLOR_ADDALPHA, D3DTOP_MULTIPLYADD, D3DTOP_LERP };
		for (DWORD o : colorOps)
			cases.push_back({ o, D3DTA_TEXTURE, D3DTA_DIFFUSE, D3DTA_TFACTOR, D3DTOP_MODULATE, D3DTA_TEXTURE, D3DTA_DIFFUSE });
		// Argument sources and modifiers.
		cases.push_back({ D3DTOP_MODULATE, D3DTA_TEXTURE | D3DTA_COMPLEMENT, D3DTA_SPECULAR, D3DTA_TFACTOR, D3DTOP_SELECTARG1, D3DTA_TFACTOR, D3DTA_DIFFUSE });
		cases.push_back({ D3DTOP_MODULATE, D3DTA_TEXTURE | D3DTA_ALPHAREPLICATE, D3DTA_TFACTOR, D3DTA_TFACTOR, D3DTOP_SELECTARG2, D3DTA_TFACTOR, D3DTA_TEXTURE | D3DTA_COMPLEMENT });
		cases.push_back({ D3DTOP_ADD, D3DTA_DIFFUSE | D3DTA_ALPHAREPLICATE | D3DTA_COMPLEMENT, D3DTA_SPECULAR, D3DTA_TFACTOR, D3DTOP_ADD, D3DTA_DIFFUSE, D3DTA_TFACTOR });
		cases.push_back({ D3DTOP_SUBTRACT, D3DTA_TFACTOR, D3DTA_TEXTURE, D3DTA_TFACTOR, D3DTOP_SUBTRACT, D3DTA_TFACTOR, D3DTA_DIFFUSE });
		cases.push_back({ D3DTOP_LERP, D3DTA_SPECULAR, D3DTA_TEXTURE, D3DTA_DIFFUSE | D3DTA_ALPHAREPLICATE, D3DTOP_LERP, D3DTA_TFACTOR, D3DTA_TEXTURE });
		cases.push_back({ D3DTOP_DOTPRODUCT3, D3DTA_TEXTURE, D3DTA_TFACTOR, D3DTA_TFACTOR, D3DTOP_SELECTARG1, D3DTA_TEXTURE, D3DTA_DIFFUSE });
		cases.push_back({ D3DTOP_DOTPRODUCT3, D3DTA_TEXTURE | D3DTA_COMPLEMENT, D3DTA_DIFFUSE, D3DTA_TFACTOR, D3DTOP_SELECTARG1, D3DTA_TEXTURE, D3DTA_DIFFUSE });

		const int cell = 40, cols = W / cell;
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		g_device->SetRenderState(D3DRS_TEXTUREFACTOR, tfColor);
		g_device->SetTexture(0, solid);
		struct SpecVertex { float x, y, z, rhw; DWORD diffuse, specular; float u, v; };
		std::vector<Color4> expected;
		for (size_t i = 0; i < cases.size(); ++i)
		{
			const Case& c = cases[i];
			g_device->SetTextureStageState(0, D3DTSS_COLOROP, c.colorOp);
			g_device->SetTextureStageState(0, D3DTSS_COLORARG1, c.c1);
			g_device->SetTextureStageState(0, D3DTSS_COLORARG2, c.c2);
			g_device->SetTextureStageState(0, D3DTSS_COLORARG0, c.c0);
			g_device->SetTextureStageState(0, D3DTSS_ALPHAOP, c.alphaOp);
			g_device->SetTextureStageState(0, D3DTSS_ALPHAARG1, c.a1);
			g_device->SetTextureStageState(0, D3DTSS_ALPHAARG2, c.a2);
			g_device->SetTextureStageState(0, D3DTSS_ALPHAARG0, c.c0);
			// Stage 1 writes alpha into the color so it is visible: result = current alpha replicated where requested.
			float x = (float)((i % cols) * cell), y = (float)((i / cols) * cell);
			SpecVertex v[4] = {
				{ x, y, 0.5f, 1.0f, diffColor, specColor, 0.5f, 0.5f },
				{ x + cell, y, 0.5f, 1.0f, diffColor, specColor, 0.5f, 0.5f },
				{ x, y + cell, 0.5f, 1.0f, diffColor, specColor, 0.5f, 0.5f },
				{ x + cell, y + cell, 0.5f, 1.0f, diffColor, specColor, 0.5f, 0.5f },
			};
			g_device->SetVertexShader(D3DFVF_XYZRHW | D3DFVF_DIFFUSE | D3DFVF_SPECULAR | D3DFVF_TEX1);
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(SpecVertex));

			// Reference: the first stage's current color is the diffuse color.
			Color4 current = D, temp = { 0, 0, 0, 0 };
			Color4 A1 = arg(c.c1, current, temp), A2 = arg(c.c2, current, temp), A0 = arg(c.c0, current, temp);
			Color4 out;
			out.r = op(c.colorOp, A1.r, A2.r, A0.r, current, A1);
			out.g = op(c.colorOp, A1.g, A2.g, A0.g, current, A1);
			out.b = op(c.colorOp, A1.b, A2.b, A0.b, current, A1);
			Color4 B1 = arg(c.a1, current, temp), B2 = arg(c.a2, current, temp);
			out.a = op(c.alphaOp, B1.a, B2.a, A0.a, current, B1);
			if (c.colorOp == D3DTOP_DOTPRODUCT3)
			{
				float d = clamp01(4 * ((A1.r - 0.5f) * (A2.r - 0.5f) + (A1.g - 0.5f) * (A2.g - 0.5f) + (A1.b - 0.5f) * (A2.b - 0.5f)));
				out.r = out.g = out.b = d;
			}
			if (c.colorOp == D3DTOP_MODULATEALPHA_ADDCOLOR || c.colorOp == D3DTOP_MODULATEINVALPHA_ADDCOLOR)
			{
				// These use the alpha of argument 1 for all channels.
				out.r = clamp01(c.colorOp == D3DTOP_MODULATEALPHA_ADDCOLOR ? A1.r + A1.a * A2.r : A1.r + (1 - A1.a) * A2.r);
				out.g = clamp01(c.colorOp == D3DTOP_MODULATEALPHA_ADDCOLOR ? A1.g + A1.a * A2.g : A1.g + (1 - A1.a) * A2.g);
				out.b = clamp01(c.colorOp == D3DTOP_MODULATEALPHA_ADDCOLOR ? A1.b + A1.a * A2.b : A1.b + (1 - A1.a) * A2.b);
			}
			expected.push_back(out);
		}
		g_device->EndScene();
		saveFrame(out + "/scene8_texops.png");

		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		for (size_t i = 0; i < cases.size(); ++i)
		{
			int px = (int)(i % cols) * cell + cell / 2, py = (int)(i / cols) * cell + cell / 2;
			const uint8_t* pix = (const uint8_t*)lr.pBits + py * lr.Pitch + px * 4;
			int got[3] = { pix[2], pix[1], pix[0] };
			int want[3] = { (int)lroundf(expected[i].r * 255), (int)lroundf(expected[i].g * 255), (int)lroundf(expected[i].b * 255) };
			if (abs(got[0] - want[0]) > 2 || abs(got[1] - want[1]) > 2 || abs(got[2] - want[2]) > 2)
			{
				printf("scene8 case %zu (color op %u): got %d %d %d, expected %d %d %d\n", i, (unsigned)cases[i].colorOp, got[0], got[1],
					got[2], want[0], want[1], want[2]);
				++failures8;
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene8: %zu of %zu texture stage cases match\n", cases.size() - failures8, cases.size());
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
		g_device->SetTexture(0, nullptr);
		solid->Release();
	}

	// Scene 9: framebuffer blending, alpha test and texture addressing, one grid cell per case.
	int failures9 = 0;
	{
		struct Expect { int r, g, b; const char* name; };
		std::vector<Expect> expected;
		const int cell = 40, cols = W / cell;
		const DWORD bg = 0xFF4080C0, fg = 0x80C06020;
		auto cellQuad = [&](int i, DWORD color, float u0, float u1) {
			float x = (float)((i % cols) * cell), y = (float)((i / cols) * cell);
			TLVertex v[4] = {
				{ x, y, 0.5f, 1.0f, color, u0, 0.5f },
				{ x + cell, y, 0.5f, 1.0f, color, u1, 0.5f },
				{ x, y + cell, 0.5f, 1.0f, color, u0, 0.5f },
				{ x + cell, y + cell, 0.5f, 1.0f, color, u1, 0.5f },
			};
			g_device->SetVertexShader(TLFVF);
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(TLVertex));
		};
		const float bgc[3] = { 0x40 / 255.0f, 0x80 / 255.0f, 0xC0 / 255.0f }, fgc[3] = { 0xC0 / 255.0f, 0x60 / 255.0f, 0x20 / 255.0f };
		const float fa = 0x80 / 255.0f;
		auto to255 = [](float v) { return (int)lroundf((v < 0 ? 0 : v > 1 ? 1 : v) * 255.0f); };

		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);

		// Blending
		struct BlendCase { DWORD src, dst, op; const char* name; };
		const BlendCase blends[] = {
			{ D3DBLEND_SRCALPHA, D3DBLEND_INVSRCALPHA, D3DBLENDOP_ADD, "alpha" },
			{ D3DBLEND_ONE, D3DBLEND_ONE, D3DBLENDOP_ADD, "additive" },
			{ D3DBLEND_DESTCOLOR, D3DBLEND_ZERO, D3DBLENDOP_ADD, "multiply" },
			{ D3DBLEND_ZERO, D3DBLEND_SRCCOLOR, D3DBLENDOP_ADD, "multiply2" },
			{ D3DBLEND_SRCALPHA, D3DBLEND_ONE, D3DBLENDOP_ADD, "alpha additive" },
			{ D3DBLEND_INVDESTCOLOR, D3DBLEND_ONE, D3DBLENDOP_ADD, "screen" },
			{ D3DBLEND_ONE, D3DBLEND_ONE, D3DBLENDOP_REVSUBTRACT, "revsubtract" },
			{ D3DBLEND_ONE, D3DBLEND_ONE, D3DBLENDOP_SUBTRACT, "subtract" },
			{ D3DBLEND_ONE, D3DBLEND_ONE, D3DBLENDOP_MIN, "min" },
			{ D3DBLEND_ONE, D3DBLEND_ONE, D3DBLENDOP_MAX, "max" },
			{ D3DBLEND_BOTHSRCALPHA, D3DBLEND_ZERO, D3DBLENDOP_ADD, "bothsrcalpha" },
		};
		int index = 0;
		for (const BlendCase& b : blends)
		{
			g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
			cellQuad(index, bg, 0, 1);
			g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, TRUE);
			g_device->SetRenderState(D3DRS_SRCBLEND, b.src);
			g_device->SetRenderState(D3DRS_DESTBLEND, b.dst);
			g_device->SetRenderState(D3DRS_BLENDOP, b.op);
			cellQuad(index, fg, 0, 1);
			int rgb[3];
			for (int c = 0; c < 3; ++c)
			{
				auto factor = [&](DWORD f, bool isSrc) {
					switch (f)
					{
					case D3DBLEND_ZERO: return 0.0f;
					case D3DBLEND_ONE: return 1.0f;
					case D3DBLEND_SRCALPHA: return fa;
					case D3DBLEND_INVSRCALPHA: return 1 - fa;
					case D3DBLEND_DESTCOLOR: return bgc[c];
					case D3DBLEND_INVDESTCOLOR: return 1 - bgc[c];
					case D3DBLEND_SRCCOLOR: return fgc[c];
					case D3DBLEND_BOTHSRCALPHA: return isSrc ? fa : 1 - fa;
					}
					return 0.0f;
				};
				float sf = factor(b.src, true), df = b.src == D3DBLEND_BOTHSRCALPHA ? 1 - fa : factor(b.dst, false);
				float v;
				switch (b.op)
				{
				case D3DBLENDOP_REVSUBTRACT: v = bgc[c] * df - fgc[c] * sf; break;
				case D3DBLENDOP_SUBTRACT: v = fgc[c] * sf - bgc[c] * df; break;
				case D3DBLENDOP_MIN: v = std::min(fgc[c], bgc[c]); break;
				case D3DBLENDOP_MAX: v = std::max(fgc[c], bgc[c]); break;
				default: v = fgc[c] * sf + bgc[c] * df; break;
				}
				rgb[c] = to255(v);
			}
			expected.push_back({ rgb[0], rgb[1], rgb[2], b.name });
			++index;
		}
		g_device->SetRenderState(D3DRS_ALPHABLENDENABLE, FALSE);
		g_device->SetRenderState(D3DRS_BLENDOP, D3DBLENDOP_ADD);

		// Alpha test with reference 0x80 against alpha 0x80: the quad is drawn when the comparison passes.
		struct AlphaCase { DWORD func; bool pass; const char* name; };
		const AlphaCase alphas[] = {
			{ D3DCMP_GREATER, false, "alpha greater" }, { D3DCMP_GREATEREQUAL, true, "alpha greaterequal" },
			{ D3DCMP_LESS, false, "alpha less" }, { D3DCMP_EQUAL, true, "alpha equal" },
			{ D3DCMP_NOTEQUAL, false, "alpha notequal" }, { D3DCMP_NEVER, false, "alpha never" },
		};
		for (const AlphaCase& a : alphas)
		{
			g_device->SetRenderState(D3DRS_ALPHATESTENABLE, FALSE);
			cellQuad(index, bg, 0, 1);
			g_device->SetRenderState(D3DRS_ALPHATESTENABLE, TRUE);
			g_device->SetRenderState(D3DRS_ALPHAREF, 0x80);
			g_device->SetRenderState(D3DRS_ALPHAFUNC, a.func);
			cellQuad(index, fg, 0, 1);
			const float* c = a.pass ? fgc : bgc;
			expected.push_back({ to255(c[0]), to255(c[1]), to255(c[2]), a.name });
			++index;
		}
		g_device->SetRenderState(D3DRS_ALPHATESTENABLE, FALSE);

		// Texture addressing: a 4x1 texture red, green, blue, white sampled at u = 1.375 in the cell center.
		IDirect3DTexture8* strip = nullptr;
		check(g_device->CreateTexture(4, 1, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &strip), "strip");
		D3DLOCKED_RECT lr;
		check(strip->LockRect(0, &lr, nullptr, 0), "strip lock");
		const DWORD stripColors[4] = { 0xFFFF0000, 0xFF00FF00, 0xFF0000FF, 0xFFFFFFFF };
		memcpy(lr.pBits, stripColors, sizeof(stripColors));
		strip->UnlockRect(0);
		modulateStage0(strip);
		g_device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
		g_device->SetTextureStageState(0, D3DTSS_MIPFILTER, D3DTEXF_NONE);
		struct AddressCase { DWORD mode; DWORD expect; const char* name; };
		const AddressCase addresses[] = {
			{ D3DTADDRESS_WRAP, 0xFF00FF00, "wrap" }, { D3DTADDRESS_MIRROR, 0xFF0000FF, "mirror" },
			{ D3DTADDRESS_CLAMP, 0xFFFFFFFF, "clamp" },
		};
		for (const AddressCase& a : addresses)
		{
			g_device->SetTextureStageState(0, D3DTSS_ADDRESSU, a.mode);
			g_device->SetTextureStageState(0, D3DTSS_ADDRESSV, a.mode);
			// u is 1.375 at the cell center.
			cellQuad(index, 0xFFFFFFFF, 1.375f - 0.05f, 1.375f + 0.05f);
			expected.push_back({ (int)((a.expect >> 16) & 255), (int)((a.expect >> 8) & 255), (int)(a.expect & 255), a.name });
			++index;
		}
		g_device->SetTextureStageState(0, D3DTSS_ADDRESSU, D3DTADDRESS_WRAP);
		g_device->SetTextureStageState(0, D3DTSS_ADDRESSV, D3DTADDRESS_WRAP);
		g_device->SetTexture(0, nullptr);
		strip->Release();
		g_device->EndScene();
		saveFrame(out + "/scene9_blending.png");

		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		for (size_t i = 0; i < expected.size(); ++i)
		{
			int px = (int)(i % cols) * cell + cell / 2, py = (int)(i / cols) * cell + cell / 2;
			const uint8_t* pix = (const uint8_t*)lr.pBits + py * lr.Pitch + px * 4;
			const Expect& e = expected[i];
			if (abs(pix[2] - e.r) > 2 || abs(pix[1] - e.g) > 2 || abs(pix[0] - e.b) > 2)
			{
				printf("scene9 %s: got %d %d %d, expected %d %d %d\n", e.name, pix[2], pix[1], pix[0], e.r, e.g, e.b);
				++failures9;
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene9: %zu of %zu blending, alpha test and addressing cases match\n", expected.size() - failures9, expected.size());
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}

	// Scene 10: fixed function lighting compared with the Direct3D 8 lighting equations.
	int failures10 = 0;
	{
		struct V3 { float x, y, z; };
		auto dot3 = [](V3 a, V3 b) { return a.x * b.x + a.y * b.y + a.z * b.z; };
		auto norm3 = [&](V3 a) { float l = sqrtf(dot3(a, a)); return V3{ a.x / l, a.y / l, a.z / l }; };
		auto sub3 = [](V3 a, V3 b) { return V3{ a.x - b.x, a.y - b.y, a.z - b.z }; };
		auto clamp01 = [](float v) { return v < 0 ? 0.0f : (v > 1 ? 1.0f : v); };

		struct LightCase
		{
			const char* name;
			D3DLIGHT8 lights[2];
			int numLights;
			D3DMATERIAL8 material;
			DWORD globalAmbient;
			DWORD vertexColor;
			DWORD diffuseSource, ambientSource, emissiveSource;
			V3 normal;
			bool specular;
		};
		auto colorValue = [](float r, float g, float b, float a = 1.0f) { D3DCOLORVALUE c = { r, g, b, a }; return c; };
		auto directional = [&](V3 dir, D3DCOLORVALUE diffuse) {
			D3DLIGHT8 l = {};
			l.Type = D3DLIGHT_DIRECTIONAL;
			l.Diffuse = diffuse;
			l.Direction = { dir.x, dir.y, dir.z };
			l.Range = 1000.0f;
			return l;
		};
		auto point = [&](V3 pos, D3DCOLORVALUE diffuse, float range, float a0, float a1, float a2) {
			D3DLIGHT8 l = {};
			l.Type = D3DLIGHT_POINT;
			l.Diffuse = diffuse;
			l.Position = { pos.x, pos.y, pos.z };
			l.Range = range;
			l.Attenuation0 = a0;
			l.Attenuation1 = a1;
			l.Attenuation2 = a2;
			return l;
		};
		D3DMATERIAL8 mat = {};
		mat.Diffuse = colorValue(0.8f, 0.6f, 0.4f);
		mat.Ambient = colorValue(0.5f, 0.5f, 0.5f);
		mat.Specular = colorValue(0.0f, 0.0f, 0.0f);
		mat.Emissive = colorValue(0.0f, 0.0f, 0.0f);
		mat.Power = 1.0f;
		const V3 toward = { 0, 0, -1 }; // normal facing the camera

		std::vector<LightCase> cases;
		cases.push_back({ "directional", { directional({ 0, 0, 1 }, colorValue(1, 1, 1)) }, 1, mat, 0xFF202020, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "directional angled", { directional({ 0.6f, 0, 0.8f }, colorValue(1, 0.5f, 0.25f)) }, 1, mat, 0xFF000000, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "facing away", { directional({ 0, 0, -1 }, colorValue(1, 1, 1)) }, 1, mat, 0xFF404040, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "vertex diffuse", { directional({ 0, 0, 1 }, colorValue(0.75f, 0.75f, 0.75f)) }, 1, mat, 0xFF202020, 0xFF30A0F0, D3DMCS_COLOR1, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "vertex ambient", { directional({ 0, 0, -1 }, colorValue(1, 1, 1)) }, 1, mat, 0xFF808080, 0xFF30A0F0, D3DMCS_MATERIAL, D3DMCS_COLOR1, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "vertex emissive", { directional({ 0, 0, 1 }, colorValue(0.25f, 0.25f, 0.25f)) }, 1, mat, 0xFF000000, 0xFF30A0F0, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_COLOR1, toward, false });
		cases.push_back({ "two lights", { directional({ 0, 0, 1 }, colorValue(0.5f, 0, 0)), directional({ -0.6f, 0, 0.8f }, colorValue(0, 0.75f, 0.5f)) }, 2, mat, 0xFF000000, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "unnormalized normal", { directional({ 0.6f, 0, 0.8f }, colorValue(1, 1, 1)) }, 1, mat, 0xFF000000, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, { 0, 0, -3.0f }, false });
		// Point lights are placed relative to the quad in drawCase.
		cases.push_back({ "point", { point({ 0, 0, -1.0f }, colorValue(1, 1, 1), 10.0f, 0.5f, 0.5f, 0.0f) }, 1, mat, 0xFF000000, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "point quadratic", { point({ 0.5f, 0, -0.5f }, colorValue(1, 0.8f, 0.6f), 10.0f, 0.25f, 0.0f, 1.0f) }, 1, mat, 0xFF000000, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		cases.push_back({ "point out of range", { point({ 0, 0, -1.0f }, colorValue(1, 1, 1), 0.5f, 1.0f, 0.0f, 0.0f) }, 1, mat, 0xFF101010, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, false });
		{
			D3DMATERIAL8 shiny = mat;
			shiny.Specular = colorValue(1.0f, 1.0f, 1.0f);
			shiny.Power = 8.0f;
			D3DLIGHT8 l = directional(norm3({ 0.3f, 0, 1.0f }), colorValue(0.5f, 0.5f, 0.5f));
			l.Specular = colorValue(1.0f, 0.5f, 0.25f);
			cases.push_back({ "specular", { l }, 1, shiny, 0xFF000000, 0xFFFFFFFF, D3DMCS_MATERIAL, D3DMCS_MATERIAL, D3DMCS_MATERIAL, toward, true });
		}

		D3DMATRIX world = identity(), view = identity(), proj = identity();
		proj._11 = 1.0f;
		proj._22 = 1.0f / 0.75f;
		const int cell = 40, cols = W / cell;
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		g_device->SetTransform(D3DTS_VIEW, &view);
		g_device->SetTransform(D3DTS_PROJECTION, &proj);
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		g_device->SetRenderState(D3DRS_LIGHTING, TRUE);
		g_device->SetRenderState(D3DRS_NORMALIZENORMALS, TRUE);
		g_device->SetRenderState(D3DRS_LOCALVIEWER, FALSE);
		g_device->SetRenderState(D3DRS_COLORVERTEX, TRUE);

		struct Expected { int r, g, b; };
		std::vector<Expected> expected;
		for (size_t i = 0; i < cases.size(); ++i)
		{
			const LightCase& c = cases[i];
			// Cell center in view space.
			float sx = (float)((i % cols) * cell + cell / 2), sy = (float)((i / cols) * cell + cell / 2);
			V3 center = { sx / W * 2.0f - 1.0f, (1.0f - sy / H * 2.0f) * 0.75f, 0.5f };
			for (int l = 0; l < 2; ++l)
			{
				D3DLIGHT8 light = c.lights[l];
				if (l < c.numLights && light.Type != D3DLIGHT_DIRECTIONAL)
				{
					light.Position.x += center.x;
					light.Position.y += center.y;
					light.Position.z += center.z;
				}
				if (l < c.numLights)
					g_device->SetLight(l, &light);
				g_device->LightEnable(l, l < c.numLights);
			}
			g_device->SetMaterial(&c.material);
			g_device->SetRenderState(D3DRS_AMBIENT, c.globalAmbient);
			g_device->SetRenderState(D3DRS_DIFFUSEMATERIALSOURCE, c.diffuseSource);
			g_device->SetRenderState(D3DRS_AMBIENTMATERIALSOURCE, c.ambientSource);
			g_device->SetRenderState(D3DRS_EMISSIVEMATERIALSOURCE, c.emissiveSource);
			g_device->SetRenderState(D3DRS_SPECULARMATERIALSOURCE, D3DMCS_MATERIAL);
			g_device->SetRenderState(D3DRS_SPECULARENABLE, c.specular);

			// A quad of 4x4 pixels around the cell center.
			struct NVertex { float x, y, z, nx, ny, nz; DWORD color; };
			float hx = 2.0f / W * 2.0f, hy = 2.0f / H * 2.0f * 0.75f;
			NVertex v[4] = {
				{ center.x - hx, center.y + hy, center.z, c.normal.x, c.normal.y, c.normal.z, c.vertexColor },
				{ center.x + hx, center.y + hy, center.z, c.normal.x, c.normal.y, c.normal.z, c.vertexColor },
				{ center.x - hx, center.y - hy, center.z, c.normal.x, c.normal.y, c.normal.z, c.vertexColor },
				{ center.x + hx, center.y - hy, center.z, c.normal.x, c.normal.y, c.normal.z, c.vertexColor },
			};
			g_device->SetTransform(D3DTS_WORLD, &world);
			g_device->SetVertexShader(D3DFVF_XYZ | D3DFVF_NORMAL | D3DFVF_DIFFUSE);
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(NVertex));

			// Reference lighting at the center.
			auto vc = [&](int shift) { return ((c.vertexColor >> shift) & 255) / 255.0f; };
			float vcol[3] = { vc(16), vc(8), vc(0) };
			float ga[3] = { ((c.globalAmbient >> 16) & 255) / 255.0f, ((c.globalAmbient >> 8) & 255) / 255.0f, (c.globalAmbient & 255) / 255.0f };
			const float md[3] = { c.material.Diffuse.r, c.material.Diffuse.g, c.material.Diffuse.b };
			const float ma[3] = { c.material.Ambient.r, c.material.Ambient.g, c.material.Ambient.b };
			const float me[3] = { c.material.Emissive.r, c.material.Emissive.g, c.material.Emissive.b };
			const float ms[3] = { c.material.Specular.r, c.material.Specular.g, c.material.Specular.b };
			V3 n = norm3(c.normal);
			float diffuseSum[3] = {}, ambientSum[3] = {}, specularSum[3] = {};
			for (int l = 0; l < c.numLights; ++l)
			{
				D3DLIGHT8 light = c.lights[l];
				V3 L;
				float atten = 1.0f;
				if (light.Type == D3DLIGHT_DIRECTIONAL)
					L = norm3({ -light.Direction.x, -light.Direction.y, -light.Direction.z });
				else
				{
					V3 lp = { light.Position.x + center.x, light.Position.y + center.y, light.Position.z + center.z };
					V3 d = sub3(lp, center);
					float dist = sqrtf(dot3(d, d));
					L = norm3(d);
					atten = dist > light.Range ? 0.0f : 1.0f / (light.Attenuation0 + light.Attenuation1 * dist + light.Attenuation2 * dist * dist);
				}
				float ndl = std::max(dot3(n, L), 0.0f);
				const float ld[3] = { light.Diffuse.r, light.Diffuse.g, light.Diffuse.b };
				const float la[3] = { light.Ambient.r, light.Ambient.g, light.Ambient.b };
				const float ls[3] = { light.Specular.r, light.Specular.g, light.Specular.b };
				V3 h = norm3({ L.x, L.y, L.z - 1.0f });
				float spec = ndl > 0 ? powf(std::max(dot3(n, h), 0.0f), c.material.Power) : 0.0f;
				for (int k = 0; k < 3; ++k)
				{
					diffuseSum[k] += atten * ld[k] * ndl;
					ambientSum[k] += atten * la[k];
					specularSum[k] += atten * ls[k] * spec;
				}
			}
			Expected e;
			int rgb[3];
			for (int k = 0; k < 3; ++k)
			{
				float d = c.diffuseSource == D3DMCS_COLOR1 ? vcol[k] : md[k];
				float a = c.ambientSource == D3DMCS_COLOR1 ? vcol[k] : ma[k];
				float em = c.emissiveSource == D3DMCS_COLOR1 ? vcol[k] : me[k];
				float color = clamp01(em + a * (ga[k] + ambientSum[k]) + d * diffuseSum[k]);
				if (c.specular)
					color = clamp01(color + clamp01(ms[k] * specularSum[k]));
				rgb[k] = (int)lroundf(color * 255.0f);
			}
			e = { rgb[0], rgb[1], rgb[2] };
			expected.push_back(e);
		}
		g_device->EndScene();
		saveFrame(out + "/scene10_lighting.png");
		g_device->SetRenderState(D3DRS_LIGHTING, FALSE);
		g_device->SetRenderState(D3DRS_SPECULARENABLE, FALSE);
		g_device->LightEnable(0, FALSE);
		g_device->LightEnable(1, FALSE);

		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		D3DLOCKED_RECT lr;
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		for (size_t i = 0; i < cases.size(); ++i)
		{
			int px = (int)(i % cols) * cell + cell / 2, py = (int)(i / cols) * cell + cell / 2;
			const uint8_t* pix = (const uint8_t*)lr.pBits + py * lr.Pitch + px * 4;
			const Expected& e = expected[i];
			if (abs(pix[2] - e.r) > 3 || abs(pix[1] - e.g) > 3 || abs(pix[0] - e.b) > 3)
			{
				printf("scene10 %s: got %d %d %d, expected %d %d %d\n", cases[i].name, pix[2], pix[1], pix[0], e.r, e.g, e.b);
				++failures10;
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene10: %zu of %zu lighting cases match\n", cases.size() - failures10, cases.size());
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}

	// Scene 11: projected texture coordinates (D3DTTFF_PROJECTED), as used for projected shadows
	// and decals. The matrix produces (0.25x + 0.25, 0.25y' + 0.25, 0.5) from a depth of 0.25,
	// which only gives the scene 7 mapping after the division by the third coordinate.
	int failures11 = 0;
	{
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		D3DMATRIX world = identity(), view = identity(), proj = identity();
		proj._11 = 1.0f;
		proj._22 = 1.0f / 0.75f;
		g_device->SetTransform(D3DTS_WORLD, &world);
		g_device->SetTransform(D3DTS_VIEW, &view);
		g_device->SetTransform(D3DTS_PROJECTION, &proj);
		modulateStage0(checker);
		g_device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
		g_device->SetTextureStageState(0, D3DTSS_MIPFILTER, D3DTEXF_NONE);
		g_device->SetTextureStageState(0, D3DTSS_TEXCOORDINDEX, D3DTSS_TCI_CAMERASPACEPOSITION);
		g_device->SetTextureStageState(0, D3DTSS_TEXTURETRANSFORMFLAGS, D3DTTFF_COUNT3 | D3DTTFF_PROJECTED);
		D3DMATRIX t = {};
		t._11 = 0.25f;
		t._22 = -0.25f / 0.75f;
		t._31 = 1.0f;  // z (0.25) contributes 0.25 to u and v
		t._32 = 1.0f;
		t._33 = 2.0f;  // w = 2z = 0.5
		t._44 = 1.0f;
		g_device->SetTransform(D3DTS_TEXTURE0, &t);
		struct PosVertex { float x, y, z; };
		PosVertex v[4] = { { -1.0f, 0.75f, 0.25f }, { 1.0f, 0.75f, 0.25f }, { -1.0f, -0.75f, 0.25f }, { 1.0f, -0.75f, 0.25f } };
		g_device->SetVertexShader(D3DFVF_XYZ);
		g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, v, sizeof(PosVertex));
		g_device->EndScene();
		saveFrame(out + "/scene11_projected.png");

		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		D3DLOCKED_RECT lr;
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		int checked = 0;
		for (int py = 0; py < H; py += 7)
		{
			for (int px = 0; px < W; px += 7)
			{
				float x = ((float)px / W) * 2.0f - 1.0f, y = (1.0f - (float)py / H * 2.0f) * 0.75f;
				float tu = (0.5f * x + 0.5f) * 64.0f, tv = (-0.5f * y / 0.75f + 0.5f) * 64.0f;
				if (fabsf(tu - roundf(tu)) < 0.05f || fabsf(tv - roundf(tv)) < 0.05f)
					continue;
				bool on = (((int)tu / 8) + ((int)tv / 8)) & 1;
				int want = on ? 0x40 : 0xFF;
				const uint8_t* pix = (const uint8_t*)lr.pBits + py * lr.Pitch + px * 4;
				++checked;
				if (abs(pix[0] - want) > 2 || abs(pix[1] - want) > 2 || abs(pix[2] - want) > 2)
				{
					if (failures11 < 5)
						printf("scene11 mismatch at %d,%d: got %d, expected %d\n", px, py, pix[1], want);
					++failures11;
				}
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene11: %d of %d pixels match\n", checked - failures11, checked);
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}

	// Scene 12: texture formats. Each format gets two cells, the sampled color and the sampled alpha.
	int failures12 = 0;
	{
		struct FormatCase { D3DFORMAT format; uint32_t texel; int bytes; int r, g, b, a; const char* name; };
		const FormatCase formats[] = {
			{ D3DFMT_A8R8G8B8, 0x80FF4020, 4, 255, 64, 32, 128, "A8R8G8B8" },
			{ D3DFMT_X8R8G8B8, 0x00FF4020, 4, 255, 64, 32, 255, "X8R8G8B8" },
			{ D3DFMT_R8G8B8, 0xFF4020, 3, 255, 64, 32, 255, "R8G8B8" },
			{ D3DFMT_R5G6B5, (31u << 11) | (16u << 5) | 4u, 2, 255, 65, 33, 255, "R5G6B5" },
			{ D3DFMT_X1R5G5B5, (31u << 10) | (8u << 5) | 4u, 2, 255, 66, 33, 255, "X1R5G5B5" },
			{ D3DFMT_A1R5G5B5, (31u << 10) | (8u << 5) | 4u, 2, 255, 66, 33, 0, "A1R5G5B5" },
			{ D3DFMT_A4R4G4B4, 0x8F42, 2, 255, 68, 34, 136, "A4R4G4B4" },
			{ D3DFMT_X4R4G4B4, 0x0F42, 2, 255, 68, 34, 255, "X4R4G4B4" },
			{ D3DFMT_A8, 0x80, 1, 0, 0, 0, 128, "A8" },
			{ D3DFMT_L8, 0x80, 1, 128, 128, 128, 255, "L8" },
			{ D3DFMT_A8L8, 0x8040, 2, 64, 64, 64, 128, "A8L8" },
			{ D3DFMT_A4L4, 0x84, 1, 68, 68, 68, 136, "A4L4" },
		};
		const int cell = 40, cols = W / cell;
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		int index = 0;
		for (const FormatCase& f : formats)
		{
			IDirect3DTexture8* tex = nullptr;
			if (FAILED(g_device->CreateTexture(4, 4, 1, 0, f.format, D3DPOOL_MANAGED, &tex)))
			{
				printf("scene12 %s: CreateTexture failed\n", f.name);
				++failures12;
				index += 2;
				continue;
			}
			D3DLOCKED_RECT lr;
			check(tex->LockRect(0, &lr, nullptr, 0), "format lock");
			for (int y = 0; y < 4; ++y)
				for (int x = 0; x < 4; ++x)
					memcpy((uint8_t*)lr.pBits + y * lr.Pitch + x * f.bytes, &f.texel, f.bytes);
			tex->UnlockRect(0);
			modulateStage0(tex);
			g_device->SetTextureStageState(0, D3DTSS_MIPFILTER, D3DTEXF_NONE);
			for (int part = 0; part < 2; ++part)
			{
				g_device->SetTextureStageState(0, D3DTSS_COLOROP, D3DTOP_SELECTARG1);
				g_device->SetTextureStageState(0, D3DTSS_COLORARG1, part == 0 ? D3DTA_TEXTURE : (D3DTA_TEXTURE | D3DTA_ALPHAREPLICATE));
				float x = (float)((index % cols) * cell), y = (float)((index / cols) * cell);
				quad(x, y, (float)cell, (float)cell, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
				++index;
			}
			g_device->SetTexture(0, nullptr);
			tex->Release();
		}
		g_device->SetTextureStageState(0, D3DTSS_COLORARG1, D3DTA_TEXTURE);
		g_device->EndScene();
		saveFrame(out + "/scene12_formats.png");

		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		D3DLOCKED_RECT lr;
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		index = 0;
		for (const FormatCase& f : formats)
		{
			for (int part = 0; part < 2; ++part, ++index)
			{
				int px = (index % cols) * cell + cell / 2, py = (index / cols) * cell + cell / 2;
				const uint8_t* pix = (const uint8_t*)lr.pBits + py * lr.Pitch + px * 4;
				int want[3] = { part == 0 ? f.r : f.a, part == 0 ? f.g : f.a, part == 0 ? f.b : f.a };
				if (abs(pix[2] - want[0]) > 2 || abs(pix[1] - want[1]) > 2 || abs(pix[0] - want[2]) > 2)
				{
					printf("scene12 %s %s: got %d %d %d, expected %d %d %d\n", f.name, part == 0 ? "color" : "alpha", pix[2], pix[1], pix[0],
						want[0], want[1], want[2]);
					++failures12;
				}
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene12: %d of %d texture format checks match\n", index - failures12, index);
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}

	// Scene 13: resources updated in the middle of a frame. A texture or buffer changed after a
	// draw used it must not affect that draw; one changed before its first use in the frame
	// must show the new contents.
	int failures13 = 0;
	{
		auto fillTexture = [](IDirect3DTexture8* tex, DWORD color) {
			D3DLOCKED_RECT lr;
			check(tex->LockRect(0, &lr, nullptr, 0), "scene13 lock");
			for (int y = 0; y < 4; ++y)
				for (int x = 0; x < 4; ++x)
					((DWORD*)((uint8_t*)lr.pBits + y * lr.Pitch))[x] = color;
			tex->UnlockRect(0);
		};
		IDirect3DTexture8* used = nullptr;
		IDirect3DTexture8* unused = nullptr;
		check(g_device->CreateTexture(4, 4, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &used), "scene13 tex");
		check(g_device->CreateTexture(4, 4, 1, 0, D3DFMT_A8R8G8B8, D3DPOOL_MANAGED, &unused), "scene13 tex");
		fillTexture(used, 0xFFFF0000);
		fillTexture(unused, 0xFF0000FF);
		IDirect3DVertexBuffer8* vb = nullptr;
		check(g_device->CreateVertexBuffer(4 * sizeof(TLVertex), D3DUSAGE_WRITEONLY, TLFVF, D3DPOOL_MANAGED, &vb), "scene13 vb");
		auto fillQuad = [&](float x, DWORD color, DWORD flags) {
			BYTE* data = nullptr;
			check(vb->Lock(0, 0, &data, flags), "scene13 vb lock");
			TLVertex v[4] = {
				{ x, 0, 0.5f, 1.0f, color, 0, 0 },
				{ x + 40, 0, 0.5f, 1.0f, color, 1, 0 },
				{ x, 40, 0.5f, 1.0f, color, 0, 1 },
				{ x + 40, 40, 0.5f, 1.0f, color, 1, 1 },
			};
			memcpy(data, v, sizeof(v));
			vb->Unlock();
		};
		auto drawBuffer = [&]() {
			g_device->SetVertexShader(TLFVF);
			g_device->SetStreamSource(0, vb, sizeof(TLVertex));
			g_device->DrawPrimitive(D3DPT_TRIANGLESTRIP, 0, 2);
		};

		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1.0f, 0);
		g_device->BeginScene();
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		modulateStage0(used);
		g_device->SetTextureStageState(0, D3DTSS_MIPFILTER, D3DTEXF_NONE);
		quad(0, 0, 40, 40, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
		fillTexture(used, 0xFF00FF00);
		quad(40, 0, 40, 40, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
		fillTexture(unused, 0xFFFFFF00);
		modulateStage0(unused);
		quad(80, 0, 40, 40, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF, 0xFFFFFFFF);
		g_device->SetTexture(0, nullptr);
		resetStates();
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		fillQuad(120, 0xFF00FFFF, 0);
		drawBuffer();
		fillQuad(160, 0xFFFF00FF, 0);
		drawBuffer();
		fillQuad(200, 0xFF808080, D3DLOCK_DISCARD);
		drawBuffer();
		g_device->SetStreamSource(0, nullptr, 0);
		g_device->EndScene();
		saveFrame(out + "/scene13_updates.png");

		IDirect3DSurface8* back = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "GetBackBuffer");
		IDirect3DSurface8* image = nullptr;
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "CreateImageSurface");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "CopyRects");
		D3DLOCKED_RECT lr;
		check(image->LockRect(&lr, nullptr, D3DLOCK_READONLY), "LockRect");
		const struct { const char* name; DWORD color; } cells[] = {
			{ "texture before update", 0xFF0000 },
			{ "texture after update", 0x00FF00 },
			{ "texture updated before use", 0xFFFF00 },
			{ "buffer before update", 0x00FFFF },
			{ "buffer after update", 0xFF00FF },
			{ "buffer after discard", 0x808080 },
		};
		for (int i = 0; i < 6; ++i)
		{
			const uint8_t* pix = (const uint8_t*)lr.pBits + 20 * lr.Pitch + (i * 40 + 20) * 4;
			DWORD got = ((DWORD)pix[2] << 16) | ((DWORD)pix[1] << 8) | pix[0];
			if (got != cells[i].color)
			{
				printf("scene13 %s: got %06X, expected %06X\n", cells[i].name, (unsigned)got, (unsigned)cells[i].color);
				++failures13;
			}
		}
		image->UnlockRect();
		image->Release();
		back->Release();
		printf("scene13: %d of 6 mid-frame update checks match\n", 6 - failures13);
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
		vb->Release();
		used->Release();
		unused->Release();
	}

	// Scene 14: derived uniform state across adjacent draws. Includes camera-only changes,
	// nonuniform scaling, light enable/data changes, unlit normal/reflection texgen and clip planes.
	// Compare this frame with the reference renderer in both threaded and inline modes.
	{
		resetStates();
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF203040, 1.0f, 0);
		g_device->BeginScene();
		g_device->SetRenderState(D3DRS_CULLMODE, D3DCULL_NONE);
		g_device->SetRenderState(D3DRS_NORMALIZENORMALS, TRUE);
		modulateStage0(checker);
		D3DMATERIAL8 material = {};
		material.Diffuse = { 0.8f, 0.7f, 0.6f, 1.0f };
		material.Ambient = { 0.1f, 0.1f, 0.1f, 1.0f };
		g_device->SetMaterial(&material);
		D3DLIGHT8 light = {};
		light.Type = D3DLIGHT_POINT;
		light.Diffuse = { 1, 0.8f, 0.6f, 1 };
		light.Position = { 0, 0, -2 };
		light.Range = 20;
		light.Attenuation0 = 1;
		const LitVertex vertices[] = {
			{ -0.7f, -0.7f, 0.4f, 0.4f, 0.3f, -0.8660254f, 0, 1 },
			{  0.7f, -0.7f, 0.4f, 0.4f, 0.3f, -0.8660254f, 1, 1 },
			{ -0.7f,  0.7f, 0.4f, 0.4f, 0.3f, -0.8660254f, 0, 0 },
			{  0.7f,  0.7f, 0.4f, 0.4f, 0.3f, -0.8660254f, 1, 0 },
		};
		for (unsigned i = 0; i < 16; ++i)
		{
			D3DVIEWPORT8 vp = { (i % 4) * (W / 4), (i / 4) * (H / 4), W / 4, H / 4, 0, 1 };
			g_device->SetViewport(&vp);
			D3DMATRIX world = identity(), view = identity(), projection = identity(), texture = identity();
			world._11 = i >= 4 ? 0.8f : 1.0f;
			world._22 = i >= 4 ? 1.2f : 1.0f;
			view._41 = (i == 2 || i == 10) ? 0.2f : 0.0f;
			view._43 = (i == 2 || i == 10) ? 0.15f : 0.0f;
			projection._11 = (i == 3 || i == 11) ? 0.7f : 1.0f;
			g_device->SetTransform(D3DTS_WORLD, &world);
			g_device->SetTransform(D3DTS_VIEW, &view);
			g_device->SetTransform(D3DTS_PROJECTION, &projection);
			light.Position.x = i == 5 ? 2.0f : 0.0f;
			g_device->SetLight(0, &light);
			g_device->LightEnable(0, i != 6);
			g_device->SetRenderState(D3DRS_LIGHTING, i < 8 || i == 15);
			g_device->SetTextureStageState(0, D3DTSS_COLOROP, i < 8 || i == 15 ? D3DTOP_MODULATE : D3DTOP_SELECTARG1);
			g_device->SetTextureStageState(0, D3DTSS_TEXCOORDINDEX, i < 8 || i == 15 ? 0 :
				(i < 12 ? D3DTSS_TCI_CAMERASPACENORMAL : D3DTSS_TCI_CAMERASPACEREFLECTIONVECTOR));
			texture._11 = texture._22 = 0.5f;
			texture._31 = texture._32 = 0.2f;
			texture._41 = texture._42 = 0.5f;
			g_device->SetTransform(D3DTS_TEXTURE0, &texture);
			g_device->SetTextureStageState(0, D3DTSS_TEXTURETRANSFORMFLAGS, i < 8 || i == 15 ? D3DTTFF_DISABLE : D3DTTFF_COUNT2);
			const float plane[] = { 1, 0, 0, 0 };
			g_device->SetClipPlane(0, plane);
			g_device->SetRenderState(D3DRS_CLIPPLANEENABLE, i == 7 || i == 14 ? 1 : 0);
			g_device->SetVertexShader(LITFVF);
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, vertices, sizeof(LitVertex));
		}
		g_device->EndScene();
		saveFrame(out + "/scene14_uniforms.png");
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}


	// Scene 15: queue draws, immediately unbind/release their vertex/index buffers, and
	// roll the transient arena before the command buffer is committed. The serial retirement
	// lists must keep every borrowed Metal buffer alive through encoding and GPU completion.
	int failures15 = 0;
	{
		resetStates();
		D3DVIEWPORT8 fullViewport = {0, 0, W, H, 0, 1};
		g_device->SetViewport(&fullViewport);
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET | D3DCLEAR_ZBUFFER, 0xFF000000, 1, 0);
		g_device->BeginScene();
		g_device->SetVertexShader(TLFVF);
		for (int cell = 0; cell < 192; ++cell)
		{
			float x = (cell % 16) * 32.0f, y = (cell / 16) * 32.0f;
			DWORD color = 0xFF000000 | ((cell * 137 + 0x123456) & 0xFFFFFF);
			TLVertex vertices[] = {
				{x,y,0.5f,1,color,0,0}, {x+32,y,0.5f,1,color,0,0},
				{x+32,y+32,0.5f,1,color,0,0}, {x,y+32,0.5f,1,color,0,0}
			};
			IDirect3DVertexBuffer8* vb = nullptr;
			IDirect3DIndexBuffer8* ib = nullptr;
			check(g_device->CreateVertexBuffer(sizeof(vertices), D3DUSAGE_DYNAMIC, TLFVF, D3DPOOL_DEFAULT, &vb), "lifetime vb");
			BYTE* data = nullptr;
			check(vb->Lock(0, 0, &data, D3DLOCK_DISCARD), "lifetime vb lock");
			memcpy(data, vertices, sizeof(vertices)); vb->Unlock();
			g_device->SetStreamSource(0, vb, sizeof(TLVertex));
			if (cell % 2)
			{
				const uint16_t indices[] = { 0, 0, 1, 2, 0, 2, 3 };
				check(g_device->CreateIndexBuffer(sizeof(indices), D3DUSAGE_DYNAMIC, D3DFMT_INDEX16, D3DPOOL_DEFAULT, &ib), "lifetime ib");
				check(ib->Lock(0, 0, &data, D3DLOCK_DISCARD), "lifetime ib lock");
				memcpy(data, indices, sizeof(indices)); ib->Unlock();
				g_device->SetIndices(ib, 0);
				check(g_device->DrawIndexedPrimitive(D3DPT_TRIANGLELIST, 0, 4, 1, 2), "unaligned index lifetime draw");
			}
			else check(g_device->DrawPrimitive(D3DPT_TRIANGLEFAN, 0, 2), "fan lifetime draw");
			g_device->SetStreamSource(0, nullptr, 0);
			g_device->SetIndices(nullptr, 0);
			vb->Release();
			if (ib) ib->Release();
		}
		std::vector<TLVertex> degenerate(30000, {0,0,0.5f,1,0xFFFFFFFF,0,0});
		for (int i = 0; i < 6; ++i)
			check(g_device->DrawPrimitiveUP(D3DPT_TRIANGLELIST, 10000, degenerate.data(), sizeof(TLVertex)), "transient rollover draw");
		g_device->EndScene();
		saveFrame(out + "/scene15_buffer_lifetime.png");
		IDirect3DSurface8 *back = nullptr, *image = nullptr;
		check(g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back), "lifetime backbuffer");
		check(g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image), "lifetime image");
		check(g_device->CopyRects(back, nullptr, 0, image, nullptr), "lifetime readback");
		D3DLOCKED_RECT lock;
		check(image->LockRect(&lock, nullptr, D3DLOCK_READONLY), "lifetime pixels");
		for (int cell = 0; cell < 192; ++cell)
		{
			const uint8_t* pixel = (const uint8_t*)lock.pBits + (cell / 16 * 32 + 16) * lock.Pitch + (cell % 16 * 32 + 16) * 4;
			DWORD got = (DWORD(pixel[2]) << 16) | (DWORD(pixel[1]) << 8) | pixel[0];
			if (got != ((cell * 137 + 0x123456) & 0xFFFFFF)) ++failures15;
		}
		image->UnlockRect(); image->Release(); back->Release();
		printf("scene15: %d of 192 released-buffer checks match\n", 192 - failures15);
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}

	int failures16 = testShadowBatches(out);
	// Scene 17: adjacent draws change only transforms, then only material, then
	// neither. A mid-scene readback ends the encoder; unchanged cached bindings
	// must be sent again. Check actual pixels against independently chosen colors.
	int failures17 = 0;
	{
		resetStates();
		D3DVIEWPORT8 vp = { 0, 0, W, H, 0, 1 };
		g_device->SetViewport(&vp);
		g_device->SetRenderState(D3DRS_CLIPPLANEENABLE, 0);
		g_device->SetRenderState(D3DRS_ZENABLE, D3DZB_FALSE);
		g_device->SetRenderState(D3DRS_LIGHTING, TRUE);
		g_device->SetRenderState(D3DRS_COLORVERTEX, FALSE);
		g_device->SetRenderState(D3DRS_AMBIENT, 0);
		g_device->SetRenderState(D3DRS_EMISSIVEMATERIALSOURCE, D3DMCS_MATERIAL);
		g_device->SetRenderState(D3DRS_DIFFUSEMATERIALSOURCE, D3DMCS_MATERIAL);
		g_device->SetRenderState(D3DRS_AMBIENTMATERIALSOURCE, D3DMCS_MATERIAL);
		for (int i = 0; i < 8; ++i) g_device->LightEnable(i, FALSE);
		D3DMATRIX transform = identity();
		g_device->SetTransform(D3DTS_VIEW, &transform);
		g_device->SetTransform(D3DTS_PROJECTION, &transform);
		g_device->SetVertexShader(LITFVF);
		const LitVertex quad[] = {
			{ -0.045f,-0.045f,0.5f, 0,0,-1, 0,0 }, { 0.045f,-0.045f,0.5f, 0,0,-1, 1,0 },
			{ -0.045f, 0.045f,0.5f, 0,0,-1, 0,1 }, { 0.045f, 0.045f,0.5f, 0,0,-1, 1,1 }
		};
		g_device->Clear(0, nullptr, D3DCLEAR_TARGET, 0xFF102030, 1, 0);
		g_device->BeginScene();
		const DWORD colors[] = { 0xE04020, 0x20B060, 0x4080D0, 0xD0C040 };
		for (int i = 0; i < 128; ++i)
		{
			D3DMATERIAL8 material = {};
			DWORD color = colors[(i / 16) % 4];
			material.Diffuse.a = 1;
			material.Emissive = { float((color >> 16) & 255) / 255, float((color >> 8) & 255) / 255, float(color & 255) / 255, 1 };
			g_device->SetMaterial(&material);
			transform._41 = (float(i % 16) + 0.5f) / 8.0f - 1.0f;
			transform._42 = 1.0f - (float(i / 16) + 0.5f) / 4.0f;
			g_device->SetTransform(D3DTS_WORLD, &transform);
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, quad, sizeof(LitVertex));
			if (i % 4 == 0) // only the shared data changes at the same position
			{
				material.Emissive = { 1, 0, 1, 1 };
				g_device->SetMaterial(&material);
				g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, quad, sizeof(LitVertex));
			}
			if (i == 63) saveFrame(out + "/scene17_encoder_boundary.png");
			// Repeated draw after readback also tests re-binding on a new encoder.
			g_device->DrawPrimitiveUP(D3DPT_TRIANGLESTRIP, 2, quad, sizeof(LitVertex));
		}
		g_device->EndScene();
		saveFrame(out + "/scene17_split_uniforms.png");
		IDirect3DSurface8 *back = nullptr, *image = nullptr;
		g_device->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back);
		g_device->CreateImageSurface(W, H, D3DFMT_A8R8G8B8, &image);
		g_device->CopyRects(back, nullptr, 0, image, nullptr);
		D3DLOCKED_RECT lock;
		check(image->LockRect(&lock, nullptr, D3DLOCK_READONLY), "split uniform pixels");
		for (int i = 0; i < 128; ++i)
		{
			const uint8_t* pixel = static_cast<const uint8_t*>(lock.pBits) + (i / 16 * (H / 8) + H / 16) * lock.Pitch + (i % 16 * (W / 16) + W / 32) * 4;
			DWORD expected = i % 4 == 0 ? 0xFF00FF : colors[(i / 16) % 4];
			DWORD got = (DWORD(pixel[2]) << 16) | (DWORD(pixel[1]) << 8) | pixel[0];
			if (got != expected) ++failures17;
		}
		image->UnlockRect(); image->Release(); back->Release();
		printf("scene17: %d of 128 transform/material/encoder checks match\n", 128 - failures17);
		g_device->Present(nullptr, nullptr, nullptr, nullptr);
	}
	int failures18 = testModelSubmission(out, pp);
	int failures19 = testModelBatching(out);
	checker->Release();
	checker565->Release();
	checker4444->Release();
	dxt->Release();
	rtTex->Release();
	g_device->Release();
	d3d->Release();
	printf("done\n");
	return failures7 || failures8 || failures9 || failures10 || failures11 || failures12 || failures13 || failures15 || failures16 || failures17 || failures18 || failures19 ? 1 : 0;
}

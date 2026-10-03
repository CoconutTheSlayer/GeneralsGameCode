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

	checker->Release();
	checker565->Release();
	checker4444->Release();
	dxt->Release();
	rtTex->Release();
	g_device->Release();
	d3d->Release();
	printf("done\n");
	return 0;
}

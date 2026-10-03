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

// Integration test of WW3D on the macOS Direct3D 8 backend: initializes WW3D the
// way W3DDisplay does, renders 2D primitives and text through Render2DClass and
// Render2DSentenceClass, and saves the frame as a PNG:  ww3dtest <output.png>

#include <win32shim.h>

#include "WW3D2/ww3d.h"
#include "WW3D2/dx8wrapper.h"
#include "WW3D2/render2d.h"
#include "WW3D2/render2dsentence.h"
#include "WW3D2/assetmgr.h"
#include "WW3D2/rddesc.h"
#include "WWMath/rect.h"

#include <vector>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image_write.h>

static LRESULT TestWndProc(HWND hwnd, UINT msg, WPARAM wParam, LPARAM lParam)
{
	return DefWindowProc(hwnd, msg, wParam, lParam);
}

static void save(const char* path, int w, int h)
{
	IDirect3DDevice8* dev = DX8Wrapper::_Get_D3D_Device8();
	IDirect3DSurface8* back = nullptr;
	dev->GetBackBuffer(0, D3DBACKBUFFER_TYPE_MONO, &back);
	IDirect3DSurface8* image = nullptr;
	dev->CreateImageSurface(w, h, D3DFMT_A8R8G8B8, &image);
	dev->CopyRects(back, nullptr, 0, image, nullptr);
	D3DLOCKED_RECT lr;
	image->LockRect(&lr, nullptr, D3DLOCK_READONLY);
	std::vector<unsigned char> rgba((size_t)w * h * 4);
	for (int y = 0; y < h; ++y)
	{
		const unsigned char* s = (const unsigned char*)lr.pBits + y * lr.Pitch;
		for (int x = 0; x < w; ++x)
		{
			rgba[(y * w + x) * 4 + 0] = s[x * 4 + 2];
			rgba[(y * w + x) * 4 + 1] = s[x * 4 + 1];
			rgba[(y * w + x) * 4 + 2] = s[x * 4 + 0];
			rgba[(y * w + x) * 4 + 3] = 255;
		}
	}
	image->UnlockRect();
	image->Release();
	back->Release();
	stbi_write_png(path, w, h, 4, rgba.data(), w * 4);
	printf("wrote %s\n", path);
}

int main(int argc, char** argv)
{
	const char* out = argc > 1 ? argv[1] : "ww3dtest.png";
	const int W = 800, H = 600;
	Win32Shim_SetCommandLine(argc, argv);
	Win32Shim_Initialize();

	setvbuf(stdout, nullptr, _IONBF, 0);
	WW3DAssetManager* assets = new WW3DAssetManager();

	WNDCLASS wc = {};
	wc.lpfnWndProc = TestWndProc;
	wc.lpszClassName = "WW3DTest";
	RegisterClass(&wc);
	HWND hwnd = CreateWindow("WW3DTest", "WW3D Test", WS_CAPTION | WS_VISIBLE, 0, 0, W, H, nullptr, nullptr, nullptr, nullptr);

	if (WW3D::Init(hwnd) != WW3D_ERROR_OK)
	{
		printf("WW3D::Init failed\n");
		return 1;
	}
	WW3D::Set_Screen_UV_Bias(TRUE);
	if (WW3D::Set_Render_Device(0, W, H, 32, 1, true) != WW3D_ERROR_OK)
	{
		printf("Set_Render_Device failed\n");
		return 1;
	}
	printf("device: %s\n", WW3D::Get_Render_Device_Desc(0).Get_Device_Name());

	Render2DClass r2d;
	r2d.Set_Coordinate_Range(RectClass(0, 0, (float)W, (float)H));
	r2d.Add_Quad(RectClass(50, 50, 350, 250), 0xFFCC2020);
	r2d.Add_Rect(RectClass(400, 50, 750, 250), 4.0f, 0xFFFFFF00, 0x8000FF00);
	r2d.Add_Line(Vector2(50, 300), Vector2(750, 320), 3.0f, 0xFF20A0FF);
	r2d.Add_Quad_VGradient(RectClass(50, 350, 750, 420), 0xFF000080, 0xFF00C0C0);

	FontCharsClass* font = new FontCharsClass();
	font->Initialize_GDI_Font("Arial", 16, true);
	Render2DSentenceClass sentence;
	sentence.Set_Font(font);
	sentence.Set_Location(Vector2(60, 460));
	sentence.Build_Sentence(L"Command & Conquer Generals: Zero Hour on Metal", nullptr, nullptr);

	for (int frame = 0; frame < 3; ++frame)
	{
		WW3D::Begin_Render(true, true, Vector3(0.1f, 0.12f, 0.15f));
		r2d.Render();
		sentence.Draw_Sentence(0xFFFFFFFF);
		sentence.Render();
		if (frame == 2)
			save(out, W, H);
		WW3D::End_Render(true);
	}

	REF_PTR_RELEASE(font);
	WW3D::Shutdown();
	delete assets;
	printf("done\n");
	return 0;
}

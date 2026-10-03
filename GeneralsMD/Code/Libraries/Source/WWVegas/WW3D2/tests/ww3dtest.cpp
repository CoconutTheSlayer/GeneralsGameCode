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
#include "WWMath/wwmath.h"
#include "WW3D2/scene.h"
#include "WW3D2/camera.h"
#include "WW3D2/light.h"
#include "WW3D2/sphereobj.h"
#include "WW3D2/boxrobj.h"
#include "WW3D2/hanim.h"

#include <vector>

#define STB_IMAGE_WRITE_IMPLEMENTATION
#include <stb_image_write.h>

//-----------------------------------------------------------------------------
// Writes a textured cube in the W3D mesh format and its TGA texture.
//-----------------------------------------------------------------------------
namespace
{
struct ChunkWriter
{
	std::vector<unsigned char> data;
	std::vector<size_t> stack;

	void u32(uint32_t v) { for (int i = 0; i < 4; ++i) data.push_back((unsigned char)(v >> (i * 8))); }
	void f32(float f) { uint32_t v; memcpy(&v, &f, 4); u32(v); }
	void u8(uint8_t v) { data.push_back(v); }
	void bytes(const void* p, size_t n) { data.insert(data.end(), (const unsigned char*)p, (const unsigned char*)p + n); }
	void name(const char* s, size_t len) { char buf[64] = {}; strlcpy(buf, s, sizeof(buf)); bytes(buf, len); }
	void begin(uint32_t type) { u32(type); stack.push_back(data.size()); u32(0); }
	void end(bool hasChildren)
	{
		size_t at = stack.back();
		stack.pop_back();
		uint32_t size = (uint32_t)(data.size() - at - 4);
		if (hasChildren)
			size |= 0x80000000u;
		memcpy(&data[at], &size, 4);
	}
};

// 64x64 checker texture as a DXT1 DDS file; each 4x4 block has a single color.
void writeCheckerDDS(const char* path)
{
	FILE* f = fopen(path, "wb");
	uint32_t header[32] = {};
	header[0] = 0x20534444;   // "DDS "
	header[1] = 124;
	header[2] = 0x1 | 0x2 | 0x4 | 0x1000 | 0x80000; // caps, height, width, pixel format, linear size
	header[3] = 64;
	header[4] = 64;
	header[5] = 64 * 64 / 2;
	header[7] = 1;            // mip levels
	header[19] = 32;          // pixel format size
	header[20] = 0x4;         // FOURCC
	header[21] = 0x31545844;  // "DXT1"
	header[27] = 0x1000;      // texture
	fwrite(header, 4, 32, f);
	for (int by = 0; by < 16; ++by)
		for (int bx = 0; bx < 16; ++bx)
		{
			bool on = ((bx / 2) + (by / 2)) & 1;
			uint16_t c = on ? (uint16_t)((4 << 11) | (40 << 5) | 28) : (uint16_t)((28 << 11) | (58 << 5) | 28);
			uint16_t block[4] = { c, c, 0, 0 };
			fwrite(block, 2, 4, f);
		}
	fclose(f);
}

void writeTestAssets()
{
	writeCheckerDDS("testdds.dds");

	// 64x64 checker texture (32 bit uncompressed TGA, top-left origin).
	{
		FILE* f = fopen("testtex.tga", "wb");
		unsigned char header[18] = {};
		header[2] = 2;
		header[12] = 64;
		header[14] = 64;
		header[16] = 32;
		header[17] = 0x28;
		fwrite(header, 1, sizeof(header), f);
		for (int y = 0; y < 64; ++y)
			for (int x = 0; x < 64; ++x)
			{
				bool on = ((x / 8) + (y / 8)) & 1;
				unsigned char bgra[4] = { (unsigned char)(on ? 40 : 230), (unsigned char)(on ? 160 : 230), (unsigned char)(on ? 230 : 230), 255 };
				fwrite(bgra, 1, 4, f);
			}
		fclose(f);
	}

}

// Appends a cube mesh with half extent `size` around the origin.
void appendCube(ChunkWriter& w, const char* meshName, const char* containerName, const char* textureName, float size)
{
	// Cube with 4 vertices per face.
	static const float faces[6][3] = { { 0, 0, -1 }, { 0, 0, 1 }, { -1, 0, 0 }, { 1, 0, 0 }, { 0, 1, 0 }, { 0, -1, 0 } };
	std::vector<float> pos, nrm, uv;
	std::vector<uint32_t> tris;
	for (int fi = 0; fi < 6; ++fi)
	{
		const float* n = faces[fi];
		float ux = n[1] != 0 ? 1.0f : -n[2], uy = 0, uz = n[1] != 0 ? 0.0f : n[0];
		float vx = n[1] * uz - n[2] * uy, vy = n[2] * ux - n[0] * uz, vz = n[0] * uy - n[1] * ux;
		uint32_t base = (uint32_t)(pos.size() / 3);
		for (int i = 0; i < 4; ++i)
		{
			float su = (i & 1) ? 1.0f : -1.0f, sv = (i & 2) ? -1.0f : 1.0f;
			pos.insert(pos.end(), { (n[0] + ux * su + vx * sv) * size, (n[1] + uy * su + vy * sv) * size, (n[2] + uz * su + vz * sv) * size });
			nrm.insert(nrm.end(), { n[0], n[1], n[2] });
			uv.insert(uv.end(), { (i & 1) ? 1.0f : 0.0f, (i & 2) ? 1.0f : 0.0f });
		}
		// Front faces are counter clockwise when seen from outside.
		tris.insert(tris.end(), { base + 0, base + 2, base + 1, base + 1, base + 2, base + 3 });
	}
	uint32_t numVerts = (uint32_t)(pos.size() / 3), numTris = (uint32_t)(tris.size() / 3);

	w.begin(0x00000000); // MESH
	w.begin(0x0000001F); // MESH_HEADER3
	w.u32((4 << 16) | 2);
	w.u32(0);
	w.name(meshName, 16);
	w.name(containerName, 16);
	w.u32(numTris);
	w.u32(numVerts);
	w.u32(0);
	w.u32(0);
	w.u32(0);
	w.u32(0);
	w.u32(0);
	w.u32(0x1 | 0x2 | 0x4);
	w.u32(0x1);
	w.f32(-size); w.f32(-size); w.f32(-size);
	w.f32(size); w.f32(size); w.f32(size);
	w.f32(0); w.f32(0); w.f32(0);
	w.f32(1.7320508f * size);
	w.end(false);
	w.begin(0x00000002); for (float v : pos) w.f32(v); w.end(false);
	w.begin(0x00000003); for (float v : nrm) w.f32(v); w.end(false);
	w.begin(0x00000020); // TRIANGLES
	for (uint32_t t = 0; t < numTris; ++t)
	{
		uint32_t a = tris[t * 3], b = tris[t * 3 + 1], c = tris[t * 3 + 2];
		w.u32(a); w.u32(b); w.u32(c);
		w.u32(0);
		w.f32(nrm[a * 3]); w.f32(nrm[a * 3 + 1]); w.f32(nrm[a * 3 + 2]);
		w.f32(nrm[a * 3] * pos[a * 3] + nrm[a * 3 + 1] * pos[a * 3 + 1] + nrm[a * 3 + 2] * pos[a * 3 + 2]);
	}
	w.end(false);
	w.begin(0x00000022); for (uint32_t i = 0; i < numVerts; ++i) w.u32(i); w.end(false);
	w.begin(0x00000028); w.u32(1); w.u32(1); w.u32(1); w.u32(1); w.end(false); // MATERIAL_INFO
	w.begin(0x0000002A); // VERTEX_MATERIALS
	w.begin(0x0000002B);
	w.begin(0x0000002C); w.name("TestMaterial", 13); w.end(false);
	w.begin(0x0000002D);
	w.u32(0);
	w.u8(255); w.u8(255); w.u8(255); w.u8(0); // ambient
	w.u8(255); w.u8(255); w.u8(255); w.u8(0); // diffuse
	w.u8(0); w.u8(0); w.u8(0); w.u8(0);       // specular
	w.u8(0); w.u8(0); w.u8(0); w.u8(0);       // emissive
	w.f32(1.0f); w.f32(1.0f); w.f32(0.0f);
	w.end(false);
	w.end(true);
	w.end(true);
	w.begin(0x00000029); // SHADERS
	{
		uint8_t shader[16] = { 3, 1, 0, 0, 0, 1, 0, 1, 1, 0, 0, 0, 0, 0, 0, 0 };
		w.bytes(shader, 16);
	}
	w.end(false);
	w.begin(0x00000030); // TEXTURES
	w.begin(0x00000031);
	w.begin(0x00000032); w.name(textureName, strlen(textureName) + 1); w.end(false);
	w.end(true);
	w.end(true);
	w.begin(0x00000038); // MATERIAL_PASS
	w.begin(0x00000039); w.u32(0); w.end(false);
	w.begin(0x0000003A); w.u32(0); w.end(false);
	w.begin(0x00000048); // TEXTURE_STAGE
	w.begin(0x00000049); w.u32(0); w.end(false);
	w.begin(0x0000004A); for (float v : uv) w.f32(v); w.end(false);
	w.end(true);
	w.end(true);
	w.end(true);
}

void writeFile(const char* path, const ChunkWriter& w)
{
	FILE* f = fopen(path, "wb");
	fwrite(w.data.data(), 1, w.data.size(), f);
	fclose(f);
}

void writeTestCube(const char* path, const char* meshName, const char* textureName)
{
	ChunkWriter w;
	appendCube(w, meshName, "", textureName, 1.0f);
	writeFile(path, w);
}

// Writes a hierarchical model like the game's units: a bone hierarchy, an HLod with a mesh
// on each bone and an animation that turns the upper bone a quarter turn.
void writeTestHierarchy(const char* path)
{
	ChunkWriter w;
	w.begin(0x00000100); // HIERARCHY
	w.begin(0x00000101);
	w.u32((4 << 16) | 1);
	w.name("HTEST", 16);
	w.u32(2);
	w.f32(0); w.f32(0); w.f32(0);
	w.end(false);
	w.begin(0x00000102); // PIVOTS
	w.name("ROOTTRANSFORM", 16);
	w.u32(0xFFFFFFFF);
	for (int i = 0; i < 6; ++i) w.f32(0);
	w.f32(0); w.f32(0); w.f32(0); w.f32(1);
	w.name("TURRET", 16);
	w.u32(0);
	w.f32(0); w.f32(0); w.f32(1.4f);
	for (int i = 0; i < 3; ++i) w.f32(0);
	w.f32(0); w.f32(0); w.f32(0); w.f32(1);
	w.end(false);
	w.end(true);

	appendCube(w, "BASE", "HTEST", "testtex.tga", 1.0f);
	appendCube(w, "TOP", "HTEST", "testdds.tga", 0.4f);

	w.begin(0x00000700); // HLOD
	w.begin(0x00000701);
	w.u32((1 << 16) | 0);
	w.u32(1);
	w.name("HTEST", 16);
	w.name("HTEST", 16);
	w.end(false);
	w.begin(0x00000702); // LOD_ARRAY
	w.begin(0x00000703); w.u32(2); w.f32(0.0f); w.end(false);
	w.begin(0x00000704); w.u32(0); w.name("HTEST.BASE", 32); w.end(false);
	w.begin(0x00000704); w.u32(1); w.name("HTEST.TOP", 32); w.end(false);
	w.end(true);
	w.end(true);

	const uint32_t frames = 31;
	w.begin(0x00000200); // ANIMATION
	w.begin(0x00000201);
	w.u32((4 << 16) | 1);
	w.name("TURN", 16);
	w.name("HTEST", 16);
	w.u32(frames);
	w.u32(30);
	w.end(false);
	w.begin(0x00000202); // channel: quaternion of the upper bone
	w.u32(0 | ((frames - 1) << 16));
	w.u32(4 | (6 << 16));
	w.u32(1);
	for (uint32_t f = 0; f < frames; ++f)
	{
		float a = 0.5f * 1.5707963f * (float)f / (float)(frames - 1);
		w.f32(0); w.f32(0); w.f32(sinf(a)); w.f32(cosf(a));
	}
	w.end(false);
	w.end(true);

	// The same animation compressed with time codes: two keys that are interpolated.
	w.begin(0x00000280); // COMPRESSED_ANIMATION
	w.begin(0x00000281);
	w.u32((4 << 16) | 1);
	w.name("CTURN", 16);
	w.name("HTEST", 16);
	w.u32(frames);
	w.u32(30 | (0 << 16)); // frame rate, time coded flavor
	w.end(false);
	w.begin(0x00000282);
	w.u32(2);
	w.u32(1 | (4 << 16) | (6 << 24)); // pivot, vector length, quaternion channel
	w.u32(0);
	w.f32(0); w.f32(0); w.f32(0); w.f32(1);
	w.u32(frames - 1);
	w.f32(0); w.f32(0); w.f32(sinf(0.7853982f)); w.f32(cosf(0.7853982f));
	w.end(false);
	w.end(true);

	writeFile(path, w);
}
} // namespace

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

	WWMath::Init(); // as W3DDisplay::init does
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
	WW3D::Set_Texture_Bitdepth(32); // as W3DDisplay::init does
	printf("device: %s\n", WW3D::Get_Render_Device_Desc(0).Get_Device_Name());

	Render2DClass r2d;
	r2d.Set_Coordinate_Range(RectClass(0, 0, (float)W, (float)H));
	r2d.Add_Quad(RectClass(20, 20, 120, 80), 0xFFCC2020);
	r2d.Add_Rect(RectClass(140, 20, 300, 80), 4.0f, 0xFFFFFF00, 0x8000FF00);
	r2d.Add_Quad_VGradient(RectClass(20, 520, 780, 580), 0xFF000080, 0xFF00C0C0);

	FontCharsClass* font = new FontCharsClass();
	font->Initialize_GDI_Font("Arial", 16, true);
	Render2DSentenceClass sentence;
	sentence.Set_Font(font);
	sentence.Set_Location(Vector2(60, 460));
	sentence.Build_Sentence(L"Command & Conquer Generals: Zero Hour on Metal", nullptr, nullptr);

	// 3D scene: two spheres and a box, lit by a directional light.
	SimpleSceneClass* scene = new SimpleSceneClass();
	scene->Set_Ambient_Light(Vector3(0.25f, 0.25f, 0.25f));
	CameraClass* camera = new CameraClass();
	Matrix3D camTm(true);
	camTm.Look_At(Vector3(0.0f, -12.0f, 6.0f), Vector3(0.0f, 0.0f, 0.0f), 0.0f);
	camera->Set_Transform(camTm);
	camera->Set_View_Plane(DEG_TO_RADF(60.0f));
	camera->Set_Clip_Planes(0.5f, 200.0f);
	camera->Set_Viewport(Vector2(0.0f, 0.0f), Vector2(1.0f, 1.0f));

	LightClass* light = new LightClass(LightClass::DIRECTIONAL);
	light->Set_Diffuse(Vector3(1.0f, 0.95f, 0.8f));
	light->Set_Ambient(Vector3(0.0f, 0.0f, 0.0f));
	Matrix3D lightTm(true);
	// The negative Z axis of a directional light points towards the light.
	lightTm.Look_At(Vector3(0, 0, 0), Vector3(5, -5, 10), 0);
	light->Set_Transform(lightTm);
	scene->Add_Render_Object(light);

	SphereRenderObjClass* sphere = new SphereRenderObjClass();
	sphere->Set_Color(Vector3(0.9f, 0.3f, 0.2f));
	sphere->Set_Extent(Vector3(2.0f, 2.0f, 2.0f));
	Matrix3D sphereTm(true);
	sphereTm.Set_Translation(Vector3(-3.0f, 0.0f, 0.0f));
	sphere->Set_Transform(sphereTm);
	scene->Add_Render_Object(sphere);

	SphereRenderObjClass* sphere2 = new SphereRenderObjClass();
	sphere2->Set_Color(Vector3(0.2f, 0.6f, 1.0f));
	sphere2->Set_Extent(Vector3(1.5f, 1.5f, 1.5f));
	Matrix3D sphere2Tm(true);
	sphere2Tm.Set_Translation(Vector3(3.0f, 2.0f, 0.5f));
	sphere2->Set_Transform(sphere2Tm);
	scene->Add_Render_Object(sphere2);

	// A W3D mesh loaded through the asset manager, like every game object.
	// The second cube refers to a TGA name but only a DDS file exists, like most game textures.
	writeTestAssets();
	writeTestCube("testcube.w3d", "TESTCUBE", "testtex.tga");
	writeTestCube("testcube2.w3d", "TESTCUBE2", "testdds.tga");
	writeTestHierarchy("htest.w3d");
	RenderObjClass* cube = nullptr;
	RenderObjClass* cube2 = nullptr;
	if (assets->Load_3D_Assets("testcube.w3d"))
		cube = assets->Create_Render_Obj("TESTCUBE");
	if (assets->Load_3D_Assets("testcube2.w3d"))
		cube2 = assets->Create_Render_Obj("TESTCUBE2");
	printf("w3d mesh: %s %s\n", cube ? "loaded" : "FAILED", cube2 ? "loaded" : "FAILED");

	RenderObjClass* model = nullptr;
	HAnimClass* anim = nullptr;
	if (assets->Load_3D_Assets("htest.w3d"))
	{
		model = assets->Create_Render_Obj("HTEST");
		anim = assets->Get_HAnim("HTEST.TURN");
	}
	printf("w3d hlod: %s, animation: %s\n", model ? "loaded" : "FAILED", anim ? "loaded" : "FAILED");

	// The compressed animation must pose the bones like the raw one.
	if (model && anim)
	{
		HAnimClass* canim = assets->Get_HAnim("HTEST.CTURN");
		if (canim)
		{
			model->Set_Animation(anim, 15.0f);
			Matrix3D raw = model->Get_Bone_Transform(1);
			model->Set_Animation(canim, 15.0f);
			Matrix3D compressed = model->Get_Bone_Transform(1);
			float diff = 0.0f;
			for (int r = 0; r < 3; ++r)
				for (int c = 0; c < 4; ++c)
				{
					float d = fabsf(raw[r][c] - compressed[r][c]);
					diff = d > diff || d != d ? d : diff;
				}
			printf("compressed animation: max difference %f, turret x axis raw (%.3f %.3f %.3f) compressed (%.3f %.3f %.3f)\n",
				diff, raw[0][0], raw[1][0], raw[2][0], compressed[0][0], compressed[1][0], compressed[2][0]);
			canim->Release_Ref();
		}
		else
			printf("compressed animation: FAILED\n");
	}
	if (model)
	{
		Matrix3D modelTm(true);
		modelTm.Set_Translation(Vector3(5.5f, -1.0f, -1.0f));
		model->Set_Transform(modelTm);
		// Frame 15 turns the upper bone by 45 degrees; WW3D_TEST_FRAME selects another frame.
		const char* frame = getenv("WW3D_TEST_FRAME");
		if (anim)
			model->Set_Animation(anim, frame ? (float)atof(frame) : 15.0f);
		scene->Add_Render_Object(model);
	}
	if (cube2)
	{
		Matrix3D cubeTm(true);
		cubeTm.Rotate_Z(-0.6f);
		cubeTm.Set_Translation(Vector3(-5.0f, 6.0f, 0.5f));
		cube2->Set_Transform(cubeTm);
		scene->Add_Render_Object(cube2);
	}
	if (cube)
	{
		Matrix3D cubeTm(true);
		cubeTm.Rotate_Z(0.5f);
		cubeTm.Rotate_X(0.4f);
		cubeTm.Set_Translation(Vector3(0.5f, 3.5f, 1.5f));
		cube->Set_Transform(cubeTm);
		scene->Add_Render_Object(cube);
	}

	WW3D::Set_Collision_Box_Display_Mask(0xFF);
	OBBoxRenderObjClass* box = new OBBoxRenderObjClass();
	box->Set_Collision_Type(0xFF);
	box->Set_Local_Center_Extent(Vector3(0, 0, 0), Vector3(1.0f, 1.0f, 1.0f));
	box->Set_Color(Vector3(0.3f, 0.9f, 0.3f));
	box->Set_Opacity(1.0f);
	Matrix3D boxTm(true);
	boxTm.Rotate_Z(0.6f);
	boxTm.Set_Translation(Vector3(0.0f, -2.0f, -0.5f));
	box->Set_Transform(boxTm);
	scene->Add_Render_Object(box);

	for (int frame = 0; frame < 10; ++frame)
	{
		WW3D::Begin_Render(true, true, Vector3(0.1f, 0.12f, 0.15f));
		WW3D::Render(scene, camera);
		r2d.Render();
		sentence.Draw_Sentence(0xFFFFFFFF);
		sentence.Render();
		if (frame == 9)
			save(out, W, H);
		WW3D::End_Render(true);
	}

	REF_PTR_RELEASE(font);
	REF_PTR_RELEASE(box);
	REF_PTR_RELEASE(cube);
	REF_PTR_RELEASE(cube2);
	REF_PTR_RELEASE(anim);
	REF_PTR_RELEASE(model);
	REF_PTR_RELEASE(sphere);
	REF_PTR_RELEASE(sphere2);
	REF_PTR_RELEASE(light);
	REF_PTR_RELEASE(camera);
	REF_PTR_RELEASE(scene);
	WW3D::Shutdown();
	delete assets;
	printf("done\n");
	return 0;
}

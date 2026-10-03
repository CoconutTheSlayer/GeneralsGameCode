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

// Generation of Metal shaders emulating the Direct3D 8 fixed function pipeline.

#pragma once

#include <d3d8.h>
#include <stdint.h>
#include <string>

namespace d3d8metal
{

// Vertex attribute slots used by generated shaders.
enum VertexAttribute
{
	ATTR_POSITION = 0,
	ATTR_BLENDWEIGHT = 1,
	ATTR_NORMAL = 2,
	ATTR_PSIZE = 3,
	ATTR_DIFFUSE = 4,
	ATTR_SPECULAR = 5,
	ATTR_TEXCOORD0 = 6,
};

// Metal buffer slots.
enum BufferSlot
{
	BUFFER_UNIFORMS = 0,
	BUFFER_STREAM0 = 16,
};

struct StageKey
{
	uint8_t colorOp;
	uint8_t colorArg0;
	uint8_t colorArg1;
	uint8_t colorArg2;
	uint8_t alphaOp;
	uint8_t alphaArg0;
	uint8_t alphaArg1;
	uint8_t alphaArg2;
	uint8_t resultTemp;     // result goes to the temp register
	uint8_t texCoordIndex;  // source texture coordinate set
	uint8_t texGen;         // 0 passthru, 1 camera position, 2 camera normal, 3 reflection
	uint8_t transformCount; // D3DTTFF_COUNTn, 0 when disabled
	uint8_t projected;
	uint8_t textureType;    // 0 none, 1 2D, 2 cube
	uint8_t pad[2];
};

struct ShaderKey
{
	uint32_t fvf;
	uint8_t lighting;
	uint8_t localViewer;
	uint8_t normalizeNormals;
	uint8_t specularEnable;
	uint8_t colorVertex;
	uint8_t diffuseSource;
	uint8_t ambientSource;
	uint8_t specularSource;
	uint8_t emissiveSource;
	uint8_t vertexFog;      // D3DFOGMODE for vertex fog, 0 none
	uint8_t tableFog;       // D3DFOGMODE for pixel fog, 0 none
	uint8_t fogEnable;
	uint8_t rangeFog;
	uint8_t alphaFunc;      // D3DCMPFUNC, D3DCMP_ALWAYS when disabled
	uint8_t flatShade;
	uint8_t numStages;
	uint8_t clipPlaneMask;
	uint8_t pointList;
	uint8_t lightTypes[8];  // D3DLIGHTTYPE, 0 when disabled
	uint8_t pad[2];
	StageKey stages[8];

	uint64_t hash() const;
};

struct VertexLayout
{
	uint32_t fvf;
	uint32_t stride;
};

struct BlendKey
{
	uint8_t enable;
	uint8_t src;
	uint8_t dst;
	uint8_t op;
	uint8_t writeMask;   // MTLColorWriteMask bits
	uint8_t hasDepth;
	uint8_t pad[2];
};

// Uniform blocks; layouts must match the MSL declarations in shadergen.cpp.
struct LightUniform
{
	float diffuse[4];
	float specular[4];
	float ambient[4];
	float position[4];   // view space
	float direction[4];  // view space, normalized
	float attenuation[4]; // range, a0, a1, a2
	float spot[4];       // falloff, cos(theta/2), cos(phi/2), unused
};

struct VertexUniforms
{
	float worldViewProj[16];
	float worldView[16];
	float normalMatrix[16];
	float texMatrix[8][16];
	float viewport[4];      // x, y, width, height
	float depthRange[4];    // minZ, maxZ, rtWidth, rtHeight
	float materialDiffuse[4];
	float materialAmbient[4];
	float materialSpecular[4];
	float materialEmissive[4];
	float materialPower[4];
	float globalAmbient[4];
	float fogParams[4];     // start, end, density, unused
	float clipPlanes[6][4]; // view space
	float pointParams[4];   // size, min, max, unused
	LightUniform lights[8];
};

struct FragmentUniforms
{
	float textureFactor[4];
	float fogColor[4];
	float fogParams[4];   // start, end, density, unused
	float alphaRef[4];
	float bumpEnv[8][4];  // m00, m01, m10, m11
	float bumpLum[8][4];  // scale, offset
};

// Returns MSL source with entry points "vs_main" and "fs_main" for the key.
std::string GenerateShaderSource(const ShaderKey& key);

unsigned FvfVertexSize(DWORD fvf);
unsigned FvfTexCoordSize(DWORD fvf, unsigned index);

} // namespace d3d8metal

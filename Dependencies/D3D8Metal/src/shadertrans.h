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

// Direct3D 8 programmable shaders (vs.1.1 and ps.1.0 to ps.1.3): validation, translation of the
// token streams into MSL statements, and an assembler for shader source text.

#pragma once

#include <d3d8.h>
#include <stdint.h>
#include <string>
#include <vector>

namespace d3d8metal
{
struct ShaderKey;

// What a shader needs from the rest of the pipeline.
struct ShaderInfo
{
	bool valid = false;
	bool pixel = false;
	unsigned major = 0, minor = 0;
	unsigned textureCount = 0; // pixel shaders: texture stages read (highest t register + 1)
	bool writesFog = false;    // vertex shaders: writes oFog
	bool writesPointSize = false; // vertex shaders: writes oPts
	std::string error;
};

// Checks a token stream (without the end token) and describes what it uses.
ShaderInfo AnalyzeShader(const std::vector<DWORD>& code);

// Remembers the token stream of a shader under a hash of its contents, which shader keys use to
// refer to it. Returns the hash, which is never 0.
uint32_t RegisterShaderCode(const std::vector<DWORD>& code);
bool FindShaderCode(uint32_t hash, std::vector<DWORD>& code);

// Statements for the body of fs_main that compute 'float4 current' from a pixel shader. The
// fragment function provides 'in' (tc0.. interpolants, diffuse, specular), textures t<i> and
// samplers s<i>, the fragment uniforms 'u' and the pixel shader constants 'pc'.
std::string TranslatePixelShader(const std::vector<DWORD>& code, const ShaderKey& key);

// Statements for the body of vs_main that set the float4 outputs oPos, oD[2], oT[8], oFog and
// oPts from a vertex shader. The vertex function provides 'float4 v[16]' and the constants 'vc'.
std::string TranslateVertexShader(const std::vector<DWORD>& code);

// MSL helper functions the translated shaders call.
const char* ShaderHelpers();

// Assembles vs.1.1 or ps.1.x source text into a token stream that ends with the end token.
bool AssembleShader(const char* source, size_t length, std::vector<DWORD>& code, std::string& errors);
} // namespace d3d8metal

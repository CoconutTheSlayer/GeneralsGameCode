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

#include "shadergen.h"

#include <sstream>

namespace d3d8metal
{

uint64_t ShaderKey::hash() const
{
	// FNV-1a over the raw bytes; keys are always zero initialized.
	const uint8_t* p = reinterpret_cast<const uint8_t*>(this);
	uint64_t h = 1469598103934665603ULL;
	for (size_t i = 0; i < sizeof(*this); ++i)
	{
		h ^= p[i];
		h *= 1099511628211ULL;
	}
	return h;
}

unsigned FvfTexCoordSize(DWORD fvf, unsigned index)
{
	switch ((fvf >> (index * 2 + 16)) & 3)
	{
	case D3DFVF_TEXTUREFORMAT1: return 1;
	case D3DFVF_TEXTUREFORMAT3: return 3;
	case D3DFVF_TEXTUREFORMAT4: return 4;
	default: return 2;
	}
}

namespace
{
unsigned positionSize(DWORD fvf)
{
	switch (fvf & D3DFVF_POSITION_MASK)
	{
	case D3DFVF_XYZ: return 12;
	case D3DFVF_XYZRHW: return 16;
	case D3DFVF_XYZB1: return 16;
	case D3DFVF_XYZB2: return 20;
	case D3DFVF_XYZB3: return 24;
	case D3DFVF_XYZB4: return 28;
	case D3DFVF_XYZB5: return 32;
	default: return 0;
	}
}

unsigned texCount(DWORD fvf)
{
	return (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
}

const char* argName(uint8_t arg)
{
	switch (arg & D3DTA_SELECTMASK)
	{
	case D3DTA_DIFFUSE: return "diffuse";
	case D3DTA_CURRENT: return "current";
	case D3DTA_TEXTURE: return "tex";
	case D3DTA_TFACTOR: return "u.textureFactor";
	case D3DTA_SPECULAR: return "specular";
	case D3DTA_TEMP: return "temp";
	default: return "current";
	}
}

std::string argExpr(uint8_t arg, bool alpha)
{
	std::string base = argName(arg);
	if (arg & D3DTA_ALPHAREPLICATE)
		base = "float4(" + base + ".a)";
	if (arg & D3DTA_COMPLEMENT)
		base = "(1.0 - " + base + ")";
	return alpha ? "(" + base + ").a" : "(" + base + ").rgb";
}

// Expression for one texture stage operation on either rgb or alpha.
std::string opExpr(uint8_t op, const std::string& a0, const std::string& a1, const std::string& a2, bool alpha, bool& passthrough)
{
	passthrough = false;
	const char* sel = alpha ? ".a" : ".rgb";
	switch (op)
	{
	case D3DTOP_SELECTARG1: return a1;
	case D3DTOP_SELECTARG2: return a2;
	case D3DTOP_MODULATE: return a1 + " * " + a2;
	case D3DTOP_MODULATE2X: return a1 + " * " + a2 + " * 2.0";
	case D3DTOP_MODULATE4X: return a1 + " * " + a2 + " * 4.0";
	case D3DTOP_ADD: return a1 + " + " + a2;
	case D3DTOP_ADDSIGNED: return a1 + " + " + a2 + " - 0.5";
	case D3DTOP_ADDSIGNED2X: return "(" + a1 + " + " + a2 + " - 0.5) * 2.0";
	case D3DTOP_SUBTRACT: return a1 + " - " + a2;
	case D3DTOP_ADDSMOOTH: return a1 + " + " + a2 + " - " + a1 + " * " + a2;
	case D3DTOP_BLENDDIFFUSEALPHA: return "mix(" + a2 + ", " + a1 + ", diffuse.a)";
	case D3DTOP_BLENDTEXTUREALPHA: return "mix(" + a2 + ", " + a1 + ", tex.a)";
	case D3DTOP_BLENDFACTORALPHA: return "mix(" + a2 + ", " + a1 + ", u.textureFactor.a)";
	case D3DTOP_BLENDTEXTUREALPHAPM: return a1 + " + " + a2 + " * (1.0 - tex.a)";
	case D3DTOP_BLENDCURRENTALPHA: return "mix(" + a2 + ", " + a1 + ", current.a)";
	case D3DTOP_PREMODULATE: return a1;
	case D3DTOP_MODULATEALPHA_ADDCOLOR:
		return alpha ? a1 : a1 + " + " + a1.substr(0, a1.size() - 4) + ".a * " + a2;
	case D3DTOP_MODULATECOLOR_ADDALPHA:
		return alpha ? a1 : a1 + " * " + a2 + " + " + a1.substr(0, a1.size() - 4) + ".a";
	case D3DTOP_MODULATEINVALPHA_ADDCOLOR:
		return alpha ? a1 : "(1.0 - " + a1.substr(0, a1.size() - 4) + ".a) * " + a2 + " + " + a1;
	case D3DTOP_MODULATEINVCOLOR_ADDALPHA:
		return alpha ? a1 : "(1.0 - " + a1 + ") * " + a2 + " + " + a1.substr(0, a1.size() - 4) + ".a";
	case D3DTOP_DOTPRODUCT3:
	{
		std::string c1 = a1, c2 = a2;
		if (alpha)
		{
			// Alpha takes the color dot product result as well.
			c1 = c1.substr(0, c1.size() - 2) + ".rgb";
			c2 = c2.substr(0, c2.size() - 2) + ".rgb";
		}
		std::string dot = "saturate(dot((" + c1 + " - 0.5) * 2.0, (" + c2 + " - 0.5) * 2.0))";
		return alpha ? dot : "float3(" + dot + ")";
	}
	case D3DTOP_MULTIPLYADD: return a0 + " + " + a1 + " * " + a2;
	case D3DTOP_LERP: return "mix(" + a2 + ", " + a1 + ", " + a0 + ")";
	case D3DTOP_BUMPENVMAP:
	case D3DTOP_BUMPENVMAPLUMINANCE:
		passthrough = true;
		return std::string("current") + sel;
	default:
		passthrough = true;
		return std::string("current") + sel;
	}
}

const char* compareExpr(uint8_t func)
{
	switch (func)
	{
	case D3DCMP_NEVER: return "false";
	case D3DCMP_LESS: return "a < r";
	case D3DCMP_EQUAL: return "abs(a - r) < (0.5 / 255.0)";
	case D3DCMP_LESSEQUAL: return "a <= r";
	case D3DCMP_GREATER: return "a > r";
	case D3DCMP_NOTEQUAL: return "abs(a - r) >= (0.5 / 255.0)";
	case D3DCMP_GREATEREQUAL: return "a >= r";
	default: return "true";
	}
}

const char* kCommonDecls = R"MSL(
#include <metal_stdlib>
using namespace metal;

struct Light
{
	float4 diffuse;
	float4 specular;
	float4 ambient;
	float4 position;
	float4 direction;
	float4 attenuation;
	float4 spot;
};

struct VertexUniforms
{
	float4x4 worldViewProj;
	float4x4 worldView;
	float4x4 normalMatrix;
	float4x4 texMatrix[8];
	float4 viewport;
	float4 depthRange;
	float4 materialDiffuse;
	float4 materialAmbient;
	float4 materialSpecular;
	float4 materialEmissive;
	float4 materialPower;
	float4 globalAmbient;
	float4 fogParams;
	float4 clipPlanes[6];
	float4 pointParams;
	float4 pointScale;
	Light lights[8];
};

struct FragmentUniforms
{
	float4 textureFactor;
	float4 fogColor;
	float4 fogParams;
	float4 alphaRef;
	float4 bumpEnv[8];
	float4 bumpLum[8];
};

static float fogFactor(int mode, float d, float4 p)
{
	if (mode == 3) // D3DFOG_LINEAR
		return saturate((p.y - d) / max(p.y - p.x, 1e-6));
	if (mode == 1) // D3DFOG_EXP
		return saturate(exp(-p.z * d));
	if (mode == 2) // D3DFOG_EXP2
		return saturate(exp(-(p.z * d) * (p.z * d)));
	return 1.0;
}
)MSL";

} // namespace

unsigned FvfVertexSize(DWORD fvf)
{
	unsigned size = positionSize(fvf);
	if (fvf & D3DFVF_NORMAL)
		size += 12;
	if (fvf & D3DFVF_PSIZE)
		size += 4;
	if (fvf & D3DFVF_DIFFUSE)
		size += 4;
	if (fvf & D3DFVF_SPECULAR)
		size += 4;
	for (unsigned i = 0; i < texCount(fvf); ++i)
		size += FvfTexCoordSize(fvf, i) * 4;
	return size;
}

std::string GenerateShaderSource(const ShaderKey& key)
{
	std::ostringstream s;
	s << kCommonDecls;

	const DWORD fvf = key.fvf;
	const bool rhw = (fvf & D3DFVF_POSITION_MASK) == D3DFVF_XYZRHW;
	const bool hasNormal = (fvf & D3DFVF_NORMAL) != 0;
	const bool hasDiffuse = (fvf & D3DFVF_DIFFUSE) != 0;
	const bool hasSpecular = (fvf & D3DFVF_SPECULAR) != 0;
	const bool hasPSize = (fvf & D3DFVF_PSIZE) != 0;
	const unsigned numTex = texCount(fvf);
	const unsigned numStages = key.numStages;
	const char* interp = key.flatShade ? " [[flat]]" : "";

	// Vertex input
	s << "struct VIn {\n";
	s << (rhw ? "\tfloat4 position [[attribute(0)]];\n" : "\tfloat3 position [[attribute(0)]];\n");
	if (hasNormal)
		s << "\tfloat3 normal [[attribute(2)]];\n";
	if (hasPSize)
		s << "\tfloat psize [[attribute(3)]];\n";
	if (hasDiffuse)
		s << "\tfloat4 diffuse [[attribute(4)]];\n";
	if (hasSpecular)
		s << "\tfloat4 specular [[attribute(5)]];\n";
	for (unsigned i = 0; i < numTex; ++i)
	{
		unsigned n = FvfTexCoordSize(fvf, i);
		s << "\t" << (n == 1 ? "float" : n == 2 ? "float2" : n == 3 ? "float3" : "float4") << " tc" << i << " [[attribute(" << (ATTR_TEXCOORD0 + i) << ")]];\n";
	}
	s << "};\n\n";

	int clipCount = 0;
	for (int i = 0; i < 6; ++i)
	{
		if (key.clipPlaneMask & (1 << i))
			clipCount = i + 1;
	}

	// Interpolants
	auto writeVaryings = [&](bool vertexSide) {
		s << "\tfloat4 diffuse [[user(diffuse)]]" << interp << ";\n";
		s << "\tfloat4 specular [[user(specular)]]" << interp << ";\n";
		for (unsigned i = 0; i < numStages; ++i)
			s << "\tfloat4 tc" << i << " [[user(tc" << i << ")]];\n";
		s << "\tfloat fog [[user(fog)]];\n";
		s << "\tfloat viewDepth [[user(viewdepth)]];\n";
		if (vertexSide)
		{
			if (clipCount > 0)
				s << "\tfloat clip [[clip_distance]] [" << clipCount << "];\n";
			if (key.pointList)
				s << "\tfloat pointSize [[point_size]];\n";
		}
	};
	s << "struct VOut {\n\tfloat4 position [[position]];\n";
	writeVaryings(true);
	s << "};\n\nstruct FIn {\n\tfloat4 position [[position]];\n";
	writeVaryings(false);
	s << "};\n\n";

	//-------------------------------------------------------------------------
	// Vertex shader
	//-------------------------------------------------------------------------
	s << "vertex VOut vs_main(VIn in [[stage_in]], constant VertexUniforms& u [[buffer(0)]]) {\n";
	s << "\tVOut out;\n";
	if (rhw)
	{
		// Pretransformed screen space vertices. Map them through the current
		// viewport so Metal's viewport transform reproduces the pixel position.
		s << "\tfloat w = in.position.w != 0.0 ? 1.0 / in.position.w : 1.0;\n";
		s << "\tfloat2 ndc = float2((in.position.x + 0.5 - u.viewport.x) / u.viewport.z * 2.0 - 1.0, 1.0 - (in.position.y + 0.5 - u.viewport.y) / u.viewport.w * 2.0);\n";
		s << "\tfloat z = (in.position.z - u.depthRange.x) / max(u.depthRange.y - u.depthRange.x, 1e-6);\n";
		s << "\tout.position = float4(ndc * w, z * w, w);\n";
		s << "\tfloat3 viewPos = float3(in.position.xy, in.position.z);\n";
		s << "\tfloat3 viewNormal = float3(0.0, 0.0, -1.0);\n";
	}
	else
	{
		s << "\tfloat4 pos = float4(in.position, 1.0);\n";
		s << "\tout.position = u.worldViewProj * pos;\n";
		// D3D samples pixels at integer coordinates, Metal at half integers.
		s << "\tout.position.x += out.position.w / u.viewport.z;\n";
		s << "\tout.position.y -= out.position.w / u.viewport.w;\n";
		s << "\tfloat3 viewPos = (u.worldView * pos).xyz;\n";
		if (hasNormal)
		{
			s << "\tfloat3 viewNormal = (u.normalMatrix * float4(in.normal, 0.0)).xyz;\n";
			if (key.normalizeNormals || key.lighting)
				s << "\tviewNormal = normalize(viewNormal);\n";
		}
		else
			s << "\tfloat3 viewNormal = float3(0.0, 0.0, -1.0);\n";
	}
	s << "\tout.viewDepth = viewPos.z;\n";

	s << "\tfloat4 vDiffuse = " << (hasDiffuse ? "in.diffuse" : "float4(1.0)") << ";\n";
	s << "\tfloat4 vSpecular = " << (hasSpecular ? "in.specular" : "float4(0.0)") << ";\n";

	if (key.lighting && !rhw)
	{
		auto source = [&](uint8_t src, const char* material) -> std::string {
			if (key.colorVertex)
			{
				if (src == D3DMCS_COLOR1 && hasDiffuse)
					return "vDiffuse";
				if (src == D3DMCS_COLOR2 && hasSpecular)
					return "vSpecular";
			}
			return std::string("u.") + material;
		};
		s << "\tfloat4 mDiffuse = " << source(key.diffuseSource, "materialDiffuse") << ";\n";
		s << "\tfloat4 mAmbient = " << source(key.ambientSource, "materialAmbient") << ";\n";
		s << "\tfloat4 mSpecular = " << source(key.specularSource, "materialSpecular") << ";\n";
		s << "\tfloat4 mEmissive = " << source(key.emissiveSource, "materialEmissive") << ";\n";
		s << "\tfloat3 ambient = u.globalAmbient.rgb;\n";
		s << "\tfloat3 diffuseSum = float3(0.0);\n";
		s << "\tfloat3 specularSum = float3(0.0);\n";
		s << "\tfloat3 toEye = " << (key.localViewer ? "normalize(-viewPos)" : "float3(0.0, 0.0, -1.0)") << ";\n";
		for (int i = 0; i < 8; ++i)
		{
			uint8_t type = key.lightTypes[i];
			if (type == 0)
				continue;
			s << "\t{\n\t\tconstant Light& l = u.lights[" << i << "];\n";
			if (type == D3DLIGHT_DIRECTIONAL)
			{
				s << "\t\tfloat3 L = -l.direction.xyz;\n";
				s << "\t\tfloat att = 1.0;\n";
			}
			else
			{
				s << "\t\tfloat3 d = l.position.xyz - viewPos;\n";
				s << "\t\tfloat dist = length(d);\n";
				s << "\t\tfloat3 L = d / max(dist, 1e-6);\n";
				s << "\t\tfloat att = dist <= l.attenuation.x ? 1.0 / max(l.attenuation.y + l.attenuation.z * dist + l.attenuation.w * dist * dist, 1e-6) : 0.0;\n";
				if (type == D3DLIGHT_SPOT)
				{
					s << "\t\tfloat rho = dot(-L, l.direction.xyz);\n";
					s << "\t\tfloat spotf = rho > l.spot.y ? 1.0 : (rho <= l.spot.z ? 0.0 : pow(saturate((rho - l.spot.z) / max(l.spot.y - l.spot.z, 1e-6)), l.spot.x));\n";
					s << "\t\tatt *= spotf;\n";
				}
			}
			s << "\t\tambient += l.ambient.rgb * att;\n";
			s << "\t\tfloat ndl = max(dot(viewNormal, L), 0.0);\n";
			s << "\t\tdiffuseSum += l.diffuse.rgb * ndl * att;\n";
			if (key.specularEnable)
			{
				s << "\t\tif (ndl > 0.0) {\n";
				s << "\t\t\tfloat3 H = normalize(L + toEye);\n";
				s << "\t\t\tspecularSum += l.specular.rgb * pow(max(dot(viewNormal, H), 0.0), max(u.materialPower.x, 1e-3)) * att;\n";
				s << "\t\t}\n";
			}
			s << "\t}\n";
		}
		s << "\tout.diffuse = float4(saturate(mEmissive.rgb + mAmbient.rgb * ambient + mDiffuse.rgb * diffuseSum), mDiffuse.a);\n";
		s << "\tout.specular = float4(saturate(mSpecular.rgb * specularSum), vSpecular.a);\n";
	}
	else
	{
		s << "\tout.diffuse = vDiffuse;\n";
		s << "\tout.specular = vSpecular;\n";
	}

	// Vertex fog
	if (key.fogEnable && key.tableFog == 0)
	{
		if (key.vertexFog != 0 && !rhw)
		{
			std::string d = key.rangeFog ? "length(viewPos)" : "abs(viewPos.z)";
			s << "\tout.fog = fogFactor(" << (int)key.vertexFog << ", " << d << ", u.fogParams);\n";
		}
		else
			s << "\tout.fog = vSpecular.a;\n";
	}
	else
		s << "\tout.fog = 1.0;\n";

	// Texture coordinates
	for (unsigned i = 0; i < numStages; ++i)
	{
		const StageKey& st = key.stages[i];
		unsigned src = st.texCoordIndex;
		std::string tc;
		switch (st.texGen)
		{
		case 1: tc = "float4(viewNormal, 1.0)"; break; // D3DTSS_TCI_CAMERASPACENORMAL
		case 2: tc = "float4(viewPos, 1.0)"; break;    // D3DTSS_TCI_CAMERASPACEPOSITION
		case 3: tc = "float4(reflect(normalize(viewPos), viewNormal), 1.0)"; break;
		default:
			if (src < numTex)
			{
				unsigned n = FvfTexCoordSize(fvf, src);
				std::string v = "in.tc" + std::to_string(src);
				// D3D pads missing components so the matrix row after the last
				// component acts as translation.
				if (n == 1)
					tc = "float4(" + v + ", 1.0, 0.0, 0.0)";
				else if (n == 2)
					tc = "float4(" + v + ", 1.0, 0.0)";
				else if (n == 3)
					tc = "float4(" + v + ", 1.0)";
				else
					tc = v;
			}
			else
				tc = "float4(0.0, 0.0, 1.0, 0.0)";
			break;
		}
		if (st.transformCount != 0)
			s << "\tout.tc" << i << " = u.texMatrix[" << i << "] * " << tc << ";\n";
		else
			s << "\tout.tc" << i << " = " << tc << ";\n";
	}

	for (int i = 0; i < clipCount; ++i)
		s << "\tout.clip[" << i << "] = " << ((key.clipPlaneMask & (1 << i)) ? "dot(float4(viewPos, 1.0), u.clipPlanes[" + std::to_string(i) + "])" : std::string("1.0")) << ";\n";
	if (key.pointList)
	{
		s << "\tfloat psize = " << (hasPSize ? "in.psize" : "u.pointParams.x") << ";\n";
		if (key.pointScale && !rhw)
		{
			// D3D: size = viewport height * size * sqrt(1 / (A + B * d + C * d^2))
			s << "\tfloat pd = length(viewPos);\n";
			s << "\tpsize = u.pointScale.w * psize * sqrt(1.0 / max(u.pointScale.x + u.pointScale.y * pd + u.pointScale.z * pd * pd, 1e-6));\n";
		}
		s << "\tout.pointSize = clamp(psize, max(u.pointParams.y, 1.0), max(u.pointParams.z, 1.0));\n";
	}

	s << "\treturn out;\n}\n\n";

	//-------------------------------------------------------------------------
	// Fragment shader
	//-------------------------------------------------------------------------
	s << "fragment float4 fs_main(FIn in [[stage_in]], constant FragmentUniforms& u [[buffer(0)]]";
	if (key.pointSprite)
		s << ", float2 pointCoord [[point_coord]]";
	for (unsigned i = 0; i < numStages; ++i)
	{
		if (key.stages[i].textureType == 2)
			s << ", texturecube<float> t" << i << " [[texture(" << i << ")]]";
		else
			s << ", texture2d<float> t" << i << " [[texture(" << i << ")]]";
		s << ", sampler s" << i << " [[sampler(" << i << ")]]";
	}
	s << ") {\n";
	s << "\tfloat4 diffuse = in.diffuse;\n";
	s << "\tfloat4 specular = in.specular;\n";
	s << "\tfloat4 current = diffuse;\n";
	s << "\tfloat4 temp = float4(0.0);\n";
	s << "\tfloat2 bumpOffset = float2(0.0);\n";
	s << "\tfloat bumpLuminance = 1.0;\n";
	s << "\tbool bumpActive = false;\n";

	for (unsigned i = 0; i < numStages; ++i)
	{
		const StageKey& st = key.stages[i];
		s << "\t{\n";
		// Sample the stage texture.
		std::string coord;
		std::string tc = key.pointSprite ? std::string("float4(pointCoord, 0.0, 1.0)") : "in.tc" + std::to_string(i);
		if (st.textureType == 2)
			coord = tc + ".xyz";
		else if (st.projected && st.transformCount >= 2)
		{
			const char* comp = st.transformCount == 2 ? "y" : st.transformCount == 3 ? "z" : "w";
			coord = tc + ".xy / " + tc + "." + comp;
		}
		else
			coord = tc + ".xy";

		if (st.textureType == 0)
			s << "\t\tfloat4 tex = float4(1.0);\n";
		else if (st.textureType == 2)
			s << "\t\tfloat4 tex = t" << i << ".sample(s" << i << ", " << coord << ");\n";
		else
		{
			s << "\t\tfloat2 uv = " << coord << ";\n";
			s << "\t\tif (bumpActive) uv += bumpOffset;\n";
			s << "\t\tfloat4 tex = t" << i << ".sample(s" << i << ", uv);\n";
			s << "\t\tif (bumpActive) { tex.rgb *= bumpLuminance; bumpActive = false; }\n";
		}

		if (st.colorOp == D3DTOP_BUMPENVMAP || st.colorOp == D3DTOP_BUMPENVMAPLUMINANCE)
		{
			// Signed du/dv are stored biased in the red/green channels.
			s << "\t\tfloat2 duv = tex.rg * 2.0 - 1.0;\n";
			s << "\t\tbumpOffset = float2(u.bumpEnv[" << i << "].x * duv.x + u.bumpEnv[" << i << "].z * duv.y, u.bumpEnv[" << i << "].y * duv.x + u.bumpEnv[" << i << "].w * duv.y);\n";
			if (st.colorOp == D3DTOP_BUMPENVMAPLUMINANCE)
				s << "\t\tbumpLuminance = saturate(tex.b * u.bumpLum[" << i << "].x + u.bumpLum[" << i << "].y);\n";
			else
				s << "\t\tbumpLuminance = 1.0;\n";
			s << "\t\tbumpActive = true;\n";
			s << "\t}\n";
			continue;
		}

		bool passthrough;
		std::string colorResult = opExpr(st.colorOp, argExpr(st.colorArg0, false), argExpr(st.colorArg1, false), argExpr(st.colorArg2, false), false, passthrough);
		std::string alphaResult;
		if (st.alphaOp == D3DTOP_DISABLE)
			alphaResult = "current.a";
		else
			alphaResult = opExpr(st.alphaOp, argExpr(st.alphaArg0, true), argExpr(st.alphaArg1, true), argExpr(st.alphaArg2, true), true, passthrough);
		s << "\t\tfloat4 result = saturate(float4(" << colorResult << ", " << alphaResult << "));\n";
		s << "\t\t" << (st.resultTemp ? "temp" : "current") << " = result;\n";
		s << "\t}\n";
	}

	if (key.specularEnable)
		s << "\tcurrent.rgb = saturate(current.rgb + specular.rgb);\n";

	if (key.fogEnable)
	{
		if (key.tableFog != 0)
			s << "\tfloat f = fogFactor(" << (int)key.tableFog << ", " << (key.rangeFog ? "abs(in.viewDepth)" : "abs(in.viewDepth)") << ", u.fogParams);\n";
		else
			s << "\tfloat f = in.fog;\n";
		s << "\tcurrent.rgb = mix(u.fogColor.rgb, current.rgb, f);\n";
	}

	if (key.alphaFunc != D3DCMP_ALWAYS && key.alphaFunc != 0)
	{
		s << "\t{\n\t\tfloat a = current.a;\n\t\tfloat r = u.alphaRef.x;\n";
		s << "\t\tif (!(" << compareExpr(key.alphaFunc) << ")) discard_fragment();\n\t}\n";
	}

	s << "\treturn current;\n}\n";
	return s.str();
}

} // namespace d3d8metal

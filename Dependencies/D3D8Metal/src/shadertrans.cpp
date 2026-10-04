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

#include "shadertrans.h"
#include "shadergen.h"

#include <cctype>
#include <cstring>
#include <map>
#include <mutex>
#include <sstream>
#include <unordered_map>

namespace d3d8metal
{
namespace
{
//-----------------------------------------------------------------------------
// Token stream layout (Direct3D 8)
//-----------------------------------------------------------------------------
enum Opcode
{
	OP_NOP = 0, OP_MOV, OP_ADD, OP_SUB, OP_MAD, OP_MUL, OP_RCP, OP_RSQ, OP_DP3, OP_DP4, OP_MIN, OP_MAX, OP_SLT, OP_SGE,
	OP_EXP, OP_LOG, OP_LIT, OP_DST, OP_LRP, OP_FRC, OP_M4x4, OP_M4x3, OP_M3x4, OP_M3x3, OP_M3x2,
	OP_TEXCOORD = 64, OP_TEXKILL, OP_TEX, OP_TEXBEM, OP_TEXBEML, OP_TEXREG2AR, OP_TEXREG2GB, OP_TEXM3x2PAD,
	OP_TEXM3x2TEX, OP_TEXM3x3PAD, OP_TEXM3x3TEX, OP_TEXM3x3DIFF, OP_TEXM3x3SPEC, OP_TEXM3x3VSPEC, OP_EXPP, OP_LOGP,
	OP_CND, OP_DEF, OP_TEXREG2RGB, OP_TEXDP3TEX, OP_TEXM3x2DEPTH, OP_TEXDP3, OP_TEXM3x3, OP_TEXDEPTH, OP_CMP, OP_BEM,
	OP_PHASE = 0xFFFD, OP_COMMENT = 0xFFFE, OP_END = 0xFFFF,
};

enum RegType
{
	REG_TEMP = 0, REG_INPUT = 1, REG_CONST = 2, REG_ADDR_TEXTURE = 3, REG_RASTOUT = 4, REG_ATTROUT = 5, REG_TEXCRDOUT = 6,
};

const DWORD COISSUE = 0x40000000;
const DWORD RELATIVE = 0x2000;

struct OpInfo
{
	const char* name;
	int dsts;
	int srcs;
	bool vs;
	bool ps;
};

const OpInfo* opInfo(unsigned op)
{
	static const std::map<unsigned, OpInfo> table = {
		{ OP_NOP, { "nop", 0, 0, true, true } },
		{ OP_MOV, { "mov", 1, 1, true, true } },
		{ OP_ADD, { "add", 1, 2, true, true } },
		{ OP_SUB, { "sub", 1, 2, false, true } },
		{ OP_MAD, { "mad", 1, 3, true, true } },
		{ OP_MUL, { "mul", 1, 2, true, true } },
		{ OP_RCP, { "rcp", 1, 1, true, false } },
		{ OP_RSQ, { "rsq", 1, 1, true, false } },
		{ OP_DP3, { "dp3", 1, 2, true, true } },
		{ OP_DP4, { "dp4", 1, 2, true, true } },
		{ OP_MIN, { "min", 1, 2, true, false } },
		{ OP_MAX, { "max", 1, 2, true, false } },
		{ OP_SLT, { "slt", 1, 2, true, false } },
		{ OP_SGE, { "sge", 1, 2, true, false } },
		{ OP_EXP, { "exp", 1, 1, true, false } },
		{ OP_LOG, { "log", 1, 1, true, false } },
		{ OP_LIT, { "lit", 1, 1, true, false } },
		{ OP_DST, { "dst", 1, 2, true, false } },
		{ OP_LRP, { "lrp", 1, 3, false, true } },
		{ OP_FRC, { "frc", 1, 1, true, false } },
		{ OP_M4x4, { "m4x4", 1, 2, true, false } },
		{ OP_M4x3, { "m4x3", 1, 2, true, false } },
		{ OP_M3x4, { "m3x4", 1, 2, true, false } },
		{ OP_M3x3, { "m3x3", 1, 2, true, false } },
		{ OP_M3x2, { "m3x2", 1, 2, true, false } },
		{ OP_TEXCOORD, { "texcoord", 1, 0, false, true } },
		{ OP_TEXKILL, { "texkill", 1, 0, false, true } },
		{ OP_TEX, { "tex", 1, 0, false, true } },
		{ OP_TEXBEM, { "texbem", 1, 1, false, true } },
		{ OP_TEXBEML, { "texbeml", 1, 1, false, true } },
		{ OP_TEXREG2AR, { "texreg2ar", 1, 1, false, true } },
		{ OP_TEXREG2GB, { "texreg2gb", 1, 1, false, true } },
		{ OP_EXPP, { "expp", 1, 1, true, false } },
		{ OP_LOGP, { "logp", 1, 1, true, false } },
		{ OP_CND, { "cnd", 1, 3, false, true } },
		{ OP_DEF, { "def", 1, 4, true, true } },
		{ OP_CMP, { "cmp", 1, 3, false, true } },
	};
	auto it = table.find(op);
	return it != table.end() ? &it->second : nullptr;
}

struct Instruction
{
	unsigned op = 0;
	bool coissue = false;
	DWORD dst = 0;
	DWORD src[3] = {};
	float def[4] = {};
};

unsigned regType(DWORD t) { return (t >> 28) & 7; }
unsigned regNum(DWORD t) { return t & 0x7FF; }

// Splits a token stream into instructions. Returns false with 'error' set for anything this
// translator does not handle.
bool parse(const std::vector<DWORD>& code, bool& pixel, unsigned& major, unsigned& minor, std::vector<Instruction>& out, std::string& error)
{
	if (code.empty())
	{
		error = "empty shader";
		return false;
	}
	DWORD version = code[0];
	if ((version >> 16) == 0xFFFF)
		pixel = true;
	else if ((version >> 16) == 0xFFFE)
		pixel = false;
	else
	{
		error = "bad version token";
		return false;
	}
	major = (version >> 8) & 0xFF;
	minor = version & 0xFF;
	if (major != 1 || (pixel ? minor > 3 : minor > 1))
	{
		error = "unsupported shader version";
		return false;
	}
	size_t i = 1;
	while (i < code.size())
	{
		DWORD t = code[i];
		unsigned op = t & 0xFFFF;
		if (op == OP_END)
			break;
		if (op == OP_COMMENT)
		{
			i += 1 + ((t >> 16) & 0x7FFF);
			continue;
		}
		const OpInfo* info = opInfo(op);
		if (info == nullptr || !(pixel ? info->ps : info->vs))
		{
			error = "unsupported instruction " + std::to_string(op);
			return false;
		}
		Instruction ins;
		ins.op = op;
		ins.coissue = (t & COISSUE) != 0;
		++i;
		if (info->dsts)
		{
			if (i >= code.size())
				break;
			ins.dst = code[i++];
		}
		if (op == OP_DEF)
		{
			if (i + 4 > code.size())
				break;
			memcpy(ins.def, &code[i], 16);
			i += 4;
		}
		else
		{
			for (int s = 0; s < info->srcs; ++s)
			{
				if (i >= code.size())
				{
					error = "truncated shader";
					return false;
				}
				ins.src[s] = code[i++];
			}
		}
		out.push_back(ins);
	}
	return true;
}

std::string f(float v)
{
	char buf[64];
	snprintf(buf, sizeof(buf), "%.9g", v);
	std::string s = buf;
	if (s.find_first_of(".eEn") == std::string::npos)
		s += ".0";
	return s;
}

std::string swizzleSuffix(DWORD t)
{
	unsigned sw = (t >> 16) & 0xFF;
	if (sw == 0xE4)
		return "";
	std::string s = ".";
	for (int i = 0; i < 4; ++i)
		s += "xyzw"[(sw >> (2 * i)) & 3];
	return s;
}

std::string maskSuffix(unsigned mask)
{
	std::string s = ".";
	for (int i = 0; i < 4; ++i)
	{
		if (mask & (1 << i))
			s += "xyzw"[i];
	}
	return s;
}

//-----------------------------------------------------------------------------
// Code generation shared by both shader types
//-----------------------------------------------------------------------------
class Translator
{
public:
	Translator(bool pixel, const ShaderKey* key) : m_pixel(pixel), m_key(key) {}

	std::string reg(DWORD t, int offset = 0) const
	{
		unsigned type = regType(t), n = regNum(t) + offset;
		if (m_pixel)
		{
			switch (type)
			{
			case REG_TEMP: return "r[" + std::to_string(n) + "]";
			case REG_INPUT: return "v[" + std::to_string(n) + "]";
			case REG_CONST: return "c[" + std::to_string(n) + "]";
			case REG_ADDR_TEXTURE: return "t[" + std::to_string(n) + "]";
			}
		}
		else
		{
			switch (type)
			{
			case REG_TEMP: return "r[" + std::to_string(n) + "]";
			case REG_INPUT: return "v[" + std::to_string(n) + "]";
			case REG_CONST:
				if (t & RELATIVE)
					return "vc[clamp(a0 + " + std::to_string(n) + ", 0, 95)]";
				return "vc[" + std::to_string(n) + "]";
			case REG_ADDR_TEXTURE: return "float4(float(a0))";
			case REG_RASTOUT: return n == 0 ? "oPos" : n == 1 ? "oFog" : "oPts";
			case REG_ATTROUT: return "oD[" + std::to_string(n) + "]";
			case REG_TEXCRDOUT: return "oT[" + std::to_string(n) + "]";
			}
		}
		return "float4(0.0)";
	}

	std::string src(DWORD t, int offset = 0) const
	{
		std::string v = reg(t, offset) + swizzleSuffix(t);
		switch ((t >> 24) & 15)
		{
		case 1: return "(-" + v + ")";
		case 2: return "(" + v + " - 0.5)";
		case 3: return "(-(" + v + " - 0.5))";
		case 4: return "(" + v + " * 2.0 - 1.0)";
		case 5: return "(-(" + v + " * 2.0 - 1.0))";
		case 6: return "(1.0 - " + v + ")";
		case 7: return "(" + v + " * 2.0)";
		case 8: return "(-(" + v + " * 2.0))";
		default: return v;
		}
	}

	// Statement that writes 'value' (a float4 expression) to the destination of 'ins'.
	std::string write(const Instruction& ins, const std::string& value) const
	{
		DWORD d = ins.dst;
		unsigned mask = (d >> 16) & 15;
		if (mask == 0)
			mask = 15;
		std::string v = value;
		unsigned shift = (d >> 24) & 15;
		if (shift)
		{
			static const char* scale[16] = { "", "2.0", "4.0", "8.0", "", "", "", "", "", "", "", "", "", "0.125", "0.25", "0.5" };
			if (scale[shift][0])
				v = "(" + v + " * " + scale[shift] + ")";
		}
		bool sat = ((d >> 20) & 1) != 0;
		if (sat)
			v = "saturate(" + v + ")";
		else if (m_pixel)
			v = "clamp(" + v + ", -1.0, 1.0)"; // the range of ps.1.x registers
		if (!m_pixel && regType(d) == REG_ADDR_TEXTURE)
			return "a0 = int(floor((" + v + ").x + 0.5));";
		if (mask == 15)
			return reg(d) + " = " + v + ";";
		std::string m = maskSuffix(mask);
		return reg(d) + m + " = (" + v + ")" + m + ";";
	}

	bool m_pixel;
	const ShaderKey* m_key;
};

std::string arithmetic(const Translator& tr, const Instruction& ins)
{
	auto s = [&](int i) { return tr.src(ins.src[i]); };
	switch (ins.op)
	{
	case OP_MOV: return s(0);
	case OP_ADD: return "(" + s(0) + " + " + s(1) + ")";
	case OP_SUB: return "(" + s(0) + " - " + s(1) + ")";
	case OP_MUL: return "(" + s(0) + " * " + s(1) + ")";
	case OP_MAD: return "(" + s(0) + " * " + s(1) + " + " + s(2) + ")";
	case OP_DP3: return "float4(dot((" + s(0) + ").xyz, (" + s(1) + ").xyz))";
	case OP_DP4: return "float4(dot(" + s(0) + ", " + s(1) + "))";
	case OP_MIN: return "min(" + s(0) + ", " + s(1) + ")";
	case OP_MAX: return "max(" + s(0) + ", " + s(1) + ")";
	case OP_SLT: return "float4(" + s(0) + " < " + s(1) + ")";
	case OP_SGE: return "float4(" + s(0) + " >= " + s(1) + ")";
	case OP_RCP: return "float4(rcp_d3d((" + s(0) + ").w))";
	case OP_RSQ: return "float4(rsq_d3d((" + s(0) + ").w))";
	case OP_EXP: return "float4(exp2((" + s(0) + ").w))";
	case OP_EXPP: return "expp_d3d((" + s(0) + ").w)";
	case OP_LOG:
	case OP_LOGP: return "float4(log2(abs((" + s(0) + ").w)))";
	case OP_FRC: return "fract(" + s(0) + ")";
	case OP_LIT: return "lit_d3d(" + s(0) + ")";
	case OP_DST: return "float4(1.0, (" + s(0) + ").y * (" + s(1) + ").y, (" + s(0) + ").z, (" + s(1) + ").w)";
	case OP_LRP: return "mix(" + s(2) + ", " + s(1) + ", " + s(0) + ")";
	case OP_CND: return "select(" + s(2) + ", " + s(1) + ", " + s(0) + " > 0.5)";
	case OP_CMP: return "select(" + s(2) + ", " + s(1) + ", " + s(0) + " >= 0.0)";
	case OP_M4x4:
	case OP_M4x3:
	case OP_M3x4:
	case OP_M3x3:
	case OP_M3x2:
	{
		int rows = (ins.op == OP_M4x4 || ins.op == OP_M3x4) ? 4 : (ins.op == OP_M3x2 ? 2 : 3);
		bool four = ins.op == OP_M4x4 || ins.op == OP_M4x3;
		std::string a = s(0);
		std::string r = "float4(";
		for (int i = 0; i < 4; ++i)
		{
			if (i)
				r += ", ";
			if (i < rows)
			{
				std::string b = tr.src(ins.src[1], i);
				r += four ? "dot(" + a + ", " + b + ")" : "dot((" + a + ").xyz, (" + b + ").xyz)";
			}
			else
				r += "0.0";
		}
		return r + ")";
	}
	}
	return "float4(0.0)";
}

const char* kHelpers = R"MSL(
static inline float rcp_d3d(float x) { return x == 0.0 ? INFINITY : (x == 1.0 ? 1.0 : 1.0 / x); }
static inline float rsq_d3d(float x) { x = abs(x); return x == 0.0 ? INFINITY : (x == 1.0 ? 1.0 : rsqrt(x)); }
static inline float4 expp_d3d(float x) { return float4(exp2(floor(x)), x - floor(x), exp2(x), 1.0); }
static inline float4 lit_d3d(float4 s)
{
	float4 d = float4(1.0, 0.0, 0.0, 1.0);
	if (s.x > 0.0)
	{
		d.y = s.x;
		d.z = s.y > 0.0 ? pow(s.y, clamp(s.w, -128.0, 128.0)) : 0.0;
	}
	return d;
}
)MSL";

std::mutex g_registryMutex;
std::unordered_map<uint32_t, std::vector<DWORD>> g_registry;
} // namespace

//-----------------------------------------------------------------------------
// Public interface
//-----------------------------------------------------------------------------
ShaderInfo AnalyzeShader(const std::vector<DWORD>& code)
{
	ShaderInfo info;
	std::vector<Instruction> ins;
	if (!parse(code, info.pixel, info.major, info.minor, ins, info.error))
		return info;
	for (const Instruction& i : ins)
	{
		if (info.pixel)
		{
			auto useTexture = [&](DWORD t) {
				if (regType(t) == REG_ADDR_TEXTURE)
					info.textureCount = std::max(info.textureCount, regNum(t) + 1);
			};
			if (i.op >= OP_TEXCOORD && i.op <= OP_TEXREG2GB)
			{
				useTexture(i.dst);
				if (i.op == OP_TEXBEM || i.op == OP_TEXBEML || i.op == OP_TEXREG2AR || i.op == OP_TEXREG2GB)
					useTexture(i.src[0]);
			}
			if (info.textureCount > 4)
			{
				info.error = "too many textures";
				return info;
			}
		}
		else if (i.op != OP_DEF && regType(i.dst) == REG_RASTOUT)
		{
			if (regNum(i.dst) == 1)
				info.writesFog = true;
			if (regNum(i.dst) == 2)
				info.writesPointSize = true;
		}
	}
	info.valid = true;
	return info;
}

uint32_t RegisterShaderCode(const std::vector<DWORD>& code)
{
	uint32_t h = 2166136261u;
	for (DWORD w : code)
	{
		for (int i = 0; i < 4; ++i)
		{
			h ^= (w >> (8 * i)) & 0xFF;
			h *= 16777619u;
		}
	}
	if (h == 0)
		h = 1;
	std::lock_guard<std::mutex> lock(g_registryMutex);
	g_registry[h] = code;
	return h;
}

bool FindShaderCode(uint32_t hash, std::vector<DWORD>& code)
{
	std::lock_guard<std::mutex> lock(g_registryMutex);
	auto it = g_registry.find(hash);
	if (it == g_registry.end())
		return false;
	code = it->second;
	return true;
}

std::string TranslatePixelShader(const std::vector<DWORD>& code, const ShaderKey& key)
{
	bool pixel;
	unsigned major, minor;
	std::vector<Instruction> ins;
	std::string error;
	std::ostringstream s;
	if (!parse(code, pixel, major, minor, ins, error) || !pixel)
	{
		s << "\tfloat4 current = in.diffuse;\n";
		return s.str();
	}
	Translator tr(true, &key);
	s << "\tfloat4 v[2] = { saturate(in.diffuse), saturate(in.specular) };\n";
	s << "\tfloat4 r[2] = { float4(0.0), float4(0.0) };\n";
	s << "\tfloat4 t[4] = { float4(0.0), float4(0.0), float4(0.0), float4(0.0) };\n";
	s << "\tfloat4 c[8];\n\tfor (int i = 0; i < 8; ++i) c[i] = pc[i];\n";
	for (const Instruction& i : ins)
	{
		if (i.op == OP_DEF)
			s << "\tc[" << regNum(i.dst) << "] = float4(" << f(i.def[0]) << ", " << f(i.def[1]) << ", " << f(i.def[2]) << ", " << f(i.def[3]) << ");\n";
	}

	auto sample = [&](unsigned stage, const std::string& offset) -> std::string {
		if (stage >= key.numStages || key.stages[stage].textureType == 0)
			return "float4(1.0)";
		std::string tc = "in.tc" + std::to_string(stage);
		if (key.stages[stage].textureType == 2)
			return "t" + std::to_string(stage) + ".sample(s" + std::to_string(stage) + ", " + tc + ".xyz)";
		std::string coord = StageTexCoord(key, stage, tc);
		if (!offset.empty())
			coord = "(" + coord + " + " + offset + ")";
		return "t" + std::to_string(stage) + ".sample(s" + std::to_string(stage) + ", " + coord + ")";
	};

	// Co-issued instructions read the registers as they were before the pair, so writes are
	// held back until the next instruction that is not co-issued.
	std::vector<std::string> pending;
	int temp = 0;
	for (const Instruction& i : ins)
	{
		if (i.op == OP_DEF || i.op == OP_NOP)
			continue;
		if (!i.coissue)
		{
			for (const std::string& w : pending)
				s << "\t" << w << "\n";
			pending.clear();
		}
		std::string name = "p" + std::to_string(temp++);
		unsigned dstStage = regNum(i.dst);
		switch (i.op)
		{
		case OP_TEX:
			s << "\tfloat4 " << name << " = " << sample(dstStage, "") << ";\n";
			pending.push_back(tr.write(i, name));
			break;
		case OP_TEXCOORD:
			s << "\tfloat4 " << name << " = float4(saturate(in.tc" << dstStage << ".xyz), 1.0);\n";
			pending.push_back(tr.write(i, name));
			break;
		case OP_TEXKILL:
			s << "\tif (any(in.tc" << dstStage << ".xyz < 0.0)) discard_fragment();\n";
			break;
		case OP_TEXBEM:
		case OP_TEXBEML:
		{
			// Signed du/dv are stored biased in the red and green channels.
			std::string srcReg = tr.reg(i.src[0]);
			std::string m = "u.bumpEnv[" + std::to_string(dstStage) + "]";
			s << "\tfloat2 " << name << "d = " << srcReg << ".rg * 2.0 - 1.0;\n";
			s << "\tfloat4 " << name << " = " << sample(dstStage, "float2(" + m + ".x * " + name + "d.x + " + m + ".z * " + name + "d.y, " + m + ".y * " + name + "d.x + " + m + ".w * " + name + "d.y)") << ";\n";
			if (i.op == OP_TEXBEML)
				s << "\t" << name << ".rgb *= saturate(" << srcReg << ".b * u.bumpLum[" << dstStage << "].x + u.bumpLum[" << dstStage << "].y);\n";
			pending.push_back(tr.write(i, name));
			break;
		}
		case OP_TEXREG2AR:
		case OP_TEXREG2GB:
		{
			std::string srcReg = tr.reg(i.src[0]);
			std::string uv = i.op == OP_TEXREG2AR ? srcReg + ".ar" : srcReg + ".gb";
			std::string expr = (dstStage < key.numStages && key.stages[dstStage].textureType == 1)
				? "t" + std::to_string(dstStage) + ".sample(s" + std::to_string(dstStage) + ", " + uv + ")" : std::string("float4(1.0)");
			s << "\tfloat4 " << name << " = " << expr << ";\n";
			pending.push_back(tr.write(i, name));
			break;
		}
		default:
			s << "\tfloat4 " << name << " = " << arithmetic(tr, i) << ";\n";
			pending.push_back(tr.write(i, name));
			break;
		}
	}
	for (const std::string& w : pending)
		s << "\t" << w << "\n";
	s << "\tfloat4 current = saturate(r[0]);\n";
	return s.str();
}

std::string TranslateVertexShader(const std::vector<DWORD>& code)
{
	bool pixel;
	unsigned major, minor;
	std::vector<Instruction> ins;
	std::string error;
	std::ostringstream s;
	if (!parse(code, pixel, major, minor, ins, error) || pixel)
		return "\toPos = v[0];\n";
	Translator tr(false, nullptr);
	s << "\tfloat4 r[12];\n\tfor (int i = 0; i < 12; ++i) r[i] = float4(0.0);\n";
	s << "\tint a0 = 0;\n";
	int temp = 0;
	for (const Instruction& i : ins)
	{
		if (i.op == OP_NOP)
			continue;
		if (i.op == OP_DEF)
			continue; // vs.1.1 has no def; constants come from the application
		std::string name = "q" + std::to_string(temp++);
		s << "\tfloat4 " << name << " = " << arithmetic(tr, i) << ";\n";
		s << "\t" << tr.write(i, name) << "\n";
	}
	return s.str();
}

const char* ShaderHelpers()
{
	return kHelpers;
}

//-----------------------------------------------------------------------------
// Assembler
//-----------------------------------------------------------------------------
namespace
{
struct AsmContext
{
	bool pixel = false;
	std::string errors;
	int line = 0;

	void error(const std::string& message)
	{
		errors += "line " + std::to_string(line) + ": " + message + "\n";
	}
};

std::string lower(std::string s)
{
	for (char& c : s)
		c = (char)tolower((unsigned char)c);
	return s;
}

// Parses a register name such as r0, c12, t3, v1, oPos, oD0, oT2, a0 or c[a0.x + 5].
bool parseRegister(AsmContext& ctx, std::string text, DWORD& token, bool& relative)
{
	text = lower(text);
	relative = false;
	unsigned type;
	unsigned num = 0;
	auto number = [&](size_t from) -> bool {
		if (from >= text.size() || !isdigit((unsigned char)text[from]))
			return false;
		num = (unsigned)atoi(text.c_str() + from);
		return true;
	};
	if (text.rfind("c[", 0) == 0)
	{
		// c[a0.x + n] or c[n]
		std::string inner = text.substr(2, text.find(']') - 2);
		std::string compact;
		for (char ch : inner)
		{
			if (!isspace((unsigned char)ch))
				compact += ch;
		}
		type = REG_CONST;
		if (compact.rfind("a0.x", 0) == 0)
		{
			relative = true;
			if (compact.size() > 5 && compact[4] == '+')
				num = (unsigned)atoi(compact.c_str() + 5);
		}
		else
			num = (unsigned)atoi(compact.c_str());
	}
	else if (text == "opos")
	{
		type = REG_RASTOUT;
		num = 0;
	}
	else if (text == "ofog")
	{
		type = REG_RASTOUT;
		num = 1;
	}
	else if (text == "opts")
	{
		type = REG_RASTOUT;
		num = 2;
	}
	else if (text.rfind("od", 0) == 0 && number(2))
		type = REG_ATTROUT;
	else if (text.rfind("ot", 0) == 0 && number(2))
		type = REG_TEXCRDOUT;
	else if (text[0] == 'r' && number(1))
		type = REG_TEMP;
	else if (text[0] == 'v' && number(1))
		type = REG_INPUT;
	else if (text[0] == 'c' && number(1))
		type = REG_CONST;
	else if ((text[0] == 't' && ctx.pixel) && number(1))
		type = REG_ADDR_TEXTURE;
	else if (text[0] == 'a' && !ctx.pixel && number(1))
		type = REG_ADDR_TEXTURE;
	else
	{
		ctx.error("unknown register '" + text + "'");
		return false;
	}
	token = 0x80000000u | (type << 28) | (num & 0x7FF) | (relative ? RELATIVE : 0);
	return true;
}

unsigned componentIndex(char c)
{
	switch (c)
	{
	case 'x': case 'r': return 0;
	case 'y': case 'g': return 1;
	case 'z': case 'b': return 2;
	case 'w': case 'a': return 3;
	}
	return 4;
}

bool parseDest(AsmContext& ctx, const std::string& text, DWORD& token, unsigned modifiers)
{
	std::string name = text, mask;
	size_t dot = text.find('.');
	if (dot != std::string::npos && text.find(']') == std::string::npos)
	{
		name = text.substr(0, dot);
		mask = lower(text.substr(dot + 1));
	}
	else if (dot != std::string::npos)
	{
		size_t close = text.find(']');
		size_t dot2 = text.find('.', close);
		name = text.substr(0, close + 1);
		if (dot2 != std::string::npos)
			mask = lower(text.substr(dot2 + 1));
	}
	bool relative;
	if (!parseRegister(ctx, name, token, relative))
		return false;
	unsigned m = 0;
	for (char c : mask)
	{
		unsigned i = componentIndex(c);
		if (i > 3)
		{
			ctx.error("bad write mask '" + mask + "'");
			return false;
		}
		m |= 1u << i;
	}
	if (m == 0)
		m = 15;
	token = (token & ~RELATIVE) | (m << 16) | (modifiers << 20);
	return true;
}

bool parseSource(AsmContext& ctx, std::string text, DWORD& token)
{
	// Prefix modifiers: -, 1-
	bool neg = false, comp = false;
	while (!text.empty() && isspace((unsigned char)text[0]))
		text.erase(0, 1);
	if (text.rfind("1-", 0) == 0)
	{
		comp = true;
		text.erase(0, 2);
	}
	if (!text.empty() && text[0] == '-')
	{
		neg = true;
		text.erase(0, 1);
	}
	// Suffix modifiers: _bias, _bx2, _x2
	std::string lowerText = lower(text);
	unsigned suffix = 0; // 0 none, 1 bias, 2 bx2, 3 x2
	for (const char* m : { "_bias", "_bx2", "_x2" })
	{
		size_t pos = lowerText.find(m);
		if (pos != std::string::npos)
		{
			suffix = strcmp(m, "_bias") == 0 ? 1 : strcmp(m, "_bx2") == 0 ? 2 : 3;
			text.erase(pos, strlen(m));
			lowerText.erase(pos, strlen(m));
			break;
		}
	}
	std::string name = text, swizzle;
	size_t close = text.find(']');
	size_t dot = text.find('.', close == std::string::npos ? 0 : close);
	if (dot != std::string::npos)
	{
		name = text.substr(0, dot);
		swizzle = lower(text.substr(dot + 1));
	}
	bool relative;
	if (!parseRegister(ctx, name, token, relative))
		return false;
	unsigned sw = 0xE4;
	if (!swizzle.empty())
	{
		unsigned idx[4];
		for (size_t i = 0; i < swizzle.size() && i < 4; ++i)
		{
			idx[i] = componentIndex(swizzle[i]);
			if (idx[i] > 3)
			{
				ctx.error("bad swizzle '" + swizzle + "'");
				return false;
			}
		}
		for (size_t i = swizzle.size(); i < 4; ++i)
			idx[i] = idx[swizzle.size() - 1]; // the last component repeats
		sw = idx[0] | (idx[1] << 2) | (idx[2] << 4) | (idx[3] << 6);
	}
	unsigned mod = 0;
	if (comp)
		mod = 6;
	else if (suffix == 1)
		mod = neg ? 3 : 2;
	else if (suffix == 2)
		mod = neg ? 5 : 4;
	else if (suffix == 3)
		mod = neg ? 8 : 7;
	else if (neg)
		mod = 1;
	token |= (sw << 16) | (mod << 24);
	return true;
}
} // namespace

bool AssembleShader(const char* source, size_t length, std::vector<DWORD>& code, std::string& errors)
{
	AsmContext ctx;
	code.clear();
	std::string text(source, length);
	std::istringstream lines(text);
	std::string raw;
	bool haveVersion = false;
	while (std::getline(lines, raw))
	{
		++ctx.line;
		// Strip comments.
		size_t cut = raw.find(';');
		size_t slashes = raw.find("//");
		if (slashes != std::string::npos && (cut == std::string::npos || slashes < cut))
			cut = slashes;
		if (cut != std::string::npos)
			raw.erase(cut);
		// Some sources put several statements on a line separated by line continuations; the
		// version token can share a line with the first instruction.
		std::istringstream words(raw);
		std::string first;
		if (!(words >> first))
			continue;
		std::string lowFirst = lower(first);
		if (!haveVersion)
		{
			unsigned major = 0, minor = 0;
			if (sscanf(lowFirst.c_str(), "ps.%u.%u", &major, &minor) == 2 || sscanf(lowFirst.c_str(), "ps_%u_%u", &major, &minor) == 2)
				ctx.pixel = true;
			else if (sscanf(lowFirst.c_str(), "vs.%u.%u", &major, &minor) == 2 || sscanf(lowFirst.c_str(), "vs_%u_%u", &major, &minor) == 2)
				ctx.pixel = false;
			else
			{
				ctx.error("missing version");
				break;
			}
			code.push_back((ctx.pixel ? 0xFFFF0000u : 0xFFFE0000u) | (major << 8) | minor);
			haveVersion = true;
			std::string rest;
			std::getline(words, rest);
			raw = rest;
			words.clear();
			words.str(raw);
			if (!(words >> first))
				continue;
			lowFirst = lower(first);
		}

		bool coissue = false;
		if (lowFirst[0] == '+')
		{
			coissue = true;
			lowFirst.erase(0, 1);
			if (lowFirst.empty() && !(words >> lowFirst))
				continue;
			lowFirst = lower(lowFirst);
		}
		// Instruction modifiers: _x2 _x4 _d2 _sat
		unsigned shift = 0, sat = 0;
		std::string mnemonic = lowFirst;
		size_t us;
		while ((us = mnemonic.rfind('_')) != std::string::npos && us > 0)
		{
			std::string m = mnemonic.substr(us + 1);
			if (m == "x2") shift = 1;
			else if (m == "x4") shift = 2;
			else if (m == "x8") shift = 3;
			else if (m == "d2") shift = 15;
			else if (m == "d4") shift = 14;
			else if (m == "d8") shift = 13;
			else if (m == "sat") sat = 1;
			else break;
			mnemonic.erase(us);
		}
		unsigned op = 0xFFFFFFFF;
		for (unsigned candidate = 0; candidate < 0x60; ++candidate)
		{
			const OpInfo* info = opInfo(candidate);
			if (info && mnemonic == info->name)
			{
				op = candidate;
				break;
			}
		}
		if (op == 0xFFFFFFFF)
		{
			ctx.error("unknown instruction '" + mnemonic + "'");
			continue;
		}
		const OpInfo* info = opInfo(op);
		std::string rest;
		std::getline(words, rest);
		std::vector<std::string> args;
		{
			std::string current;
			int depth = 0;
			for (char ch : rest)
			{
				if (ch == '[')
					++depth;
				if (ch == ']')
					--depth;
				if (ch == ',' && depth == 0)
				{
					args.push_back(current);
					current.clear();
				}
				else
					current += ch;
			}
			if (!current.empty())
				args.push_back(current);
			for (std::string& a : args)
			{
				size_t b = a.find_first_not_of(" \t\r\\");
				size_t e = a.find_last_not_of(" \t\r\\");
				a = b == std::string::npos ? std::string() : a.substr(b, e - b + 1);
			}
			while (!args.empty() && args.back().empty())
				args.pop_back();
		}
		int expected = info->dsts + info->srcs;
		if ((int)args.size() != expected)
		{
			ctx.error(std::string("wrong operand count for ") + info->name);
			continue;
		}
		code.push_back(op | (coissue ? COISSUE : 0));
		if (info->dsts)
		{
			DWORD token;
			if (!parseDest(ctx, args[0], token, sat))
				continue;
			token |= shift << 24;
			code.push_back(token);
		}
		if (op == OP_DEF)
		{
			for (int i = 1; i <= 4; ++i)
			{
				float v = strtof(args[i].c_str(), nullptr);
				DWORD bits;
				memcpy(&bits, &v, 4);
				code.push_back(bits);
			}
			continue;
		}
		for (int i = info->dsts; i < expected; ++i)
		{
			DWORD token;
			if (parseSource(ctx, args[i], token))
				code.push_back(token);
		}
	}
	code.push_back(0x0000FFFF);
	errors = ctx.errors;
	return haveVersion && ctx.errors.empty();
}
} // namespace d3d8metal

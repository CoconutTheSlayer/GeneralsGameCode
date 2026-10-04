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

// IDirect3DDevice8 drawing: render passes, pipeline state and draw calls.

#include "internal.h"

#include <cmath>

namespace d3d8metal
{

namespace
{
inline float bitsFloat(DWORD d)
{
	float f;
	memcpy(&f, &d, 4);
	return f;
}

inline void colorToFloat4(D3DCOLOR c, float out[4])
{
	out[0] = ((c >> 16) & 0xFF) / 255.0f;
	out[1] = ((c >> 8) & 0xFF) / 255.0f;
	out[2] = (c & 0xFF) / 255.0f;
	out[3] = ((c >> 24) & 0xFF) / 255.0f;
}

inline void valueToFloat4(const D3DCOLORVALUE& c, float out[4])
{
	out[0] = c.r;
	out[1] = c.g;
	out[2] = c.b;
	out[3] = c.a;
}

void multiply(const D3DMATRIX& a, const D3DMATRIX& b, D3DMATRIX& r)
{
	D3DMATRIX t;
	for (int i = 0; i < 4; ++i)
		for (int j = 0; j < 4; ++j)
			t.m[i][j] = a.m[i][0] * b.m[0][j] + a.m[i][1] * b.m[1][j] + a.m[i][2] * b.m[2][j] + a.m[i][3] * b.m[3][j];
	r = t;
}

bool invert(const D3DMATRIX& in, D3DMATRIX& out)
{
	const float* m = &in._11;
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
	if (fabsf(det) < 1e-20f)
	{
		out = in;
		return false;
	}
	det = 1.0f / det;
	float* o = &out._11;
	for (int i = 0; i < 16; ++i)
		o[i] = inv[i] * det;
	return true;
}

void transpose(const D3DMATRIX& in, D3DMATRIX& out)
{
	D3DMATRIX t;
	for (int i = 0; i < 4; ++i)
		for (int j = 0; j < 4; ++j)
			t.m[i][j] = in.m[j][i];
	out = t;
}

MTLCompareFunction compareFunc(DWORD f)
{
	switch (f)
	{
	case D3DCMP_NEVER: return MTLCompareFunctionNever;
	case D3DCMP_LESS: return MTLCompareFunctionLess;
	case D3DCMP_EQUAL: return MTLCompareFunctionEqual;
	case D3DCMP_LESSEQUAL: return MTLCompareFunctionLessEqual;
	case D3DCMP_GREATER: return MTLCompareFunctionGreater;
	case D3DCMP_NOTEQUAL: return MTLCompareFunctionNotEqual;
	case D3DCMP_GREATEREQUAL: return MTLCompareFunctionGreaterEqual;
	default: return MTLCompareFunctionAlways;
	}
}

MTLStencilOperation stencilOp(DWORD op)
{
	switch (op)
	{
	case D3DSTENCILOP_ZERO: return MTLStencilOperationZero;
	case D3DSTENCILOP_REPLACE: return MTLStencilOperationReplace;
	case D3DSTENCILOP_INCRSAT: return MTLStencilOperationIncrementClamp;
	case D3DSTENCILOP_DECRSAT: return MTLStencilOperationDecrementClamp;
	case D3DSTENCILOP_INVERT: return MTLStencilOperationInvert;
	case D3DSTENCILOP_INCR: return MTLStencilOperationIncrementWrap;
	case D3DSTENCILOP_DECR: return MTLStencilOperationDecrementWrap;
	default: return MTLStencilOperationKeep;
	}
}

MTLBlendFactor blendFactor(DWORD b)
{
	switch (b)
	{
	case D3DBLEND_ZERO: return MTLBlendFactorZero;
	case D3DBLEND_ONE: return MTLBlendFactorOne;
	case D3DBLEND_SRCCOLOR: return MTLBlendFactorSourceColor;
	case D3DBLEND_INVSRCCOLOR: return MTLBlendFactorOneMinusSourceColor;
	case D3DBLEND_SRCALPHA: return MTLBlendFactorSourceAlpha;
	case D3DBLEND_INVSRCALPHA: return MTLBlendFactorOneMinusSourceAlpha;
	case D3DBLEND_DESTALPHA: return MTLBlendFactorDestinationAlpha;
	case D3DBLEND_INVDESTALPHA: return MTLBlendFactorOneMinusDestinationAlpha;
	case D3DBLEND_DESTCOLOR: return MTLBlendFactorDestinationColor;
	case D3DBLEND_INVDESTCOLOR: return MTLBlendFactorOneMinusDestinationColor;
	case D3DBLEND_SRCALPHASAT: return MTLBlendFactorSourceAlphaSaturated;
	default: return MTLBlendFactorOne;
	}
}

MTLBlendOperation blendOp(DWORD op)
{
	switch (op)
	{
	case D3DBLENDOP_SUBTRACT: return MTLBlendOperationSubtract;
	case D3DBLENDOP_REVSUBTRACT: return MTLBlendOperationReverseSubtract;
	case D3DBLENDOP_MIN: return MTLBlendOperationMin;
	case D3DBLENDOP_MAX: return MTLBlendOperationMax;
	default: return MTLBlendOperationAdd;
	}
}

MTLSamplerAddressMode addressMode(DWORD a)
{
	switch (a)
	{
	case D3DTADDRESS_MIRROR: return MTLSamplerAddressModeMirrorRepeat;
	case D3DTADDRESS_CLAMP: return MTLSamplerAddressModeClampToEdge;
	case D3DTADDRESS_BORDER: return MTLSamplerAddressModeClampToBorderColor;
	case D3DTADDRESS_MIRRORONCE: return MTLSamplerAddressModeMirrorClampToEdge;
	default: return MTLSamplerAddressModeRepeat;
	}
}

unsigned vertexCountFor(D3DPRIMITIVETYPE type, UINT primitives)
{
	switch (type)
	{
	case D3DPT_POINTLIST: return primitives;
	case D3DPT_LINELIST: return primitives * 2;
	case D3DPT_LINESTRIP: return primitives + 1;
	case D3DPT_TRIANGLELIST: return primitives * 3;
	case D3DPT_TRIANGLESTRIP: return primitives + 2;
	case D3DPT_TRIANGLEFAN: return primitives + 2;
	default: return 0;
	}
}

MTLPrimitiveType primitiveType(D3DPRIMITIVETYPE type)
{
	switch (type)
	{
	case D3DPT_POINTLIST: return MTLPrimitiveTypePoint;
	case D3DPT_LINELIST: return MTLPrimitiveTypeLine;
	case D3DPT_LINESTRIP: return MTLPrimitiveTypeLineStrip;
	case D3DPT_TRIANGLESTRIP: return MTLPrimitiveTypeTriangleStrip;
	default: return MTLPrimitiveTypeTriangle; // lists; fans are converted
	}
}

struct DrawContext
{
	ShaderKey key;
	VertexLayout layout;
	BlendKey blend;
};
} // namespace

//-----------------------------------------------------------------------------
// Render passes
//-----------------------------------------------------------------------------
id<MTLTexture> Device::activeDepthTexture()
{
	if (m_depthStencil == nullptr || m_depthStencil->m_storage->texture == nil)
		return nil;
	unsigned w = m_renderTarget->width(), h = m_renderTarget->height();
	if (m_depthStencil->width() == w && m_depthStencil->height() == h)
		return m_depthStencil->m_storage->texture;
	// D3D allows a depth buffer larger than the render target, Metal requires
	// matching sizes. Use a depth buffer of the render target size instead.
	uint64_t key = ((uint64_t)w << 32) | h;
	auto it = m_scratchDepth.find(key);
	if (it != m_scratchDepth.end())
		return it->second;
	MTLTextureDescriptor* td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float_Stencil8 width:w height:h mipmapped:NO];
	td.usage = MTLTextureUsageRenderTarget;
	td.storageMode = MTLStorageModePrivate;
	id<MTLTexture> depth = [m_mtlDevice newTextureWithDescriptor:td];
	m_scratchDepth[key] = depth;
	return depth;
}

id<MTLRenderCommandEncoder> Device::renderEncoder()
{
	if (m_encoder)
		return m_encoder;

	TextureStorage& rt = *m_renderTarget->m_storage;
	MTLRenderPassDescriptor* pass = [MTLRenderPassDescriptor renderPassDescriptor];
	pass.colorAttachments[0].texture = rt.texture;
	pass.colorAttachments[0].slice = m_renderTarget->m_face;
	pass.colorAttachments[0].level = m_renderTarget->m_level;
	pass.colorAttachments[0].storeAction = MTLStoreActionStore;
	if (m_pendingClearFlags & D3DCLEAR_TARGET)
	{
		pass.colorAttachments[0].loadAction = MTLLoadActionClear;
		pass.colorAttachments[0].clearColor = m_pendingClearColor;
	}
	else
		pass.colorAttachments[0].loadAction = MTLLoadActionLoad;

	if (id<MTLTexture> depth = activeDepthTexture())
	{
		pass.depthAttachment.texture = depth;
		pass.stencilAttachment.texture = depth;
		pass.depthAttachment.storeAction = MTLStoreActionStore;
		pass.stencilAttachment.storeAction = MTLStoreActionStore;
		if (m_pendingClearFlags & D3DCLEAR_ZBUFFER)
		{
			pass.depthAttachment.loadAction = MTLLoadActionClear;
			pass.depthAttachment.clearDepth = m_pendingClearDepth;
		}
		else
			pass.depthAttachment.loadAction = MTLLoadActionLoad;
		if (m_pendingClearFlags & D3DCLEAR_STENCIL)
		{
			pass.stencilAttachment.loadAction = MTLLoadActionClear;
			pass.stencilAttachment.clearStencil = m_pendingClearStencil;
		}
		else
			pass.stencilAttachment.loadAction = MTLLoadActionLoad;
	}
	m_pendingClearFlags = 0;

	m_encoder = [commandBuffer() renderCommandEncoderWithDescriptor:pass];
	rt.shadowStale = true;
	markTextureUsed(rt);
	return m_encoder;
}

void Device::drawClearQuad(DWORD flags, D3DCOLOR color, float z, DWORD stencil, const MTLScissorRect& rect)
{
	id<MTLRenderCommandEncoder> enc = renderEncoder();
	bool hasDepth = activeDepthTexture() != nil;
	int pipe = ((flags & D3DCLEAR_TARGET) ? 1 : 0) | (hasDepth ? 2 : 0);
	int ds = hasDepth ? (((flags & D3DCLEAR_ZBUFFER) ? 1 : 0) | ((flags & D3DCLEAR_STENCIL) ? 2 : 0)) : 0;
	struct
	{
		float color[4];
		float depth[4];
	} u;
	colorToFloat4(color, u.color);
	u.depth[0] = z;
	MTLViewport vp = { 0, 0, (double)m_renderTarget->width(), (double)m_renderTarget->height(), 0.0, 1.0 };
	[enc setViewport:vp];
	[enc setScissorRect:rect];
	[enc setRenderPipelineState:m_clearPipelines[pipe]];
	[enc setDepthStencilState:m_clearDepthStates[ds]];
	[enc setStencilReferenceValue:stencil & 0xFF];
	[enc setCullMode:MTLCullModeNone];
	[enc setTriangleFillMode:MTLTriangleFillModeFill];
	[enc setDepthBias:0 slopeScale:0 clamp:0];
	[enc setVertexBytes:&u length:sizeof(u) atIndex:0];
	[enc setFragmentBytes:&u length:sizeof(u) atIndex:0];
	[enc drawPrimitives:MTLPrimitiveTypeTriangle vertexStart:0 vertexCount:3];
}

HRESULT Device::Clear(DWORD Count, CONST D3DRECT* pRects, DWORD Flags, D3DCOLOR Color, float Z, DWORD Stencil)
{
	if (m_depthStencil == nullptr)
		Flags &= ~(D3DCLEAR_ZBUFFER | D3DCLEAR_STENCIL);
	if (Flags == 0)
		return D3D_OK;

	unsigned rtW = m_renderTarget->width();
	unsigned rtH = m_renderTarget->height();
	const D3DVIEWPORT8& vp = m_state.viewport;
	bool fullViewport = vp.X == 0 && vp.Y == 0 && vp.Width >= rtW && vp.Height >= rtH;

	if (m_encoder == nil && (Count == 0 || pRects == nullptr) && fullViewport)
	{
		// Fold the clear into the load action of the next render pass.
		if (Flags & D3DCLEAR_TARGET)
		{
			float c[4];
			colorToFloat4(Color, c);
			m_pendingClearColor = MTLClearColorMake(c[0], c[1], c[2], c[3]);
		}
		m_pendingClearDepth = Z;
		m_pendingClearStencil = Stencil & 0xFF;
		m_pendingClearFlags |= Flags;
		return D3D_OK;
	}

	auto clip = [&](LONG x1, LONG y1, LONG x2, LONG y2) {
		x1 = std::max<LONG>(x1, (LONG)vp.X);
		y1 = std::max<LONG>(y1, (LONG)vp.Y);
		x2 = std::min<LONG>(x2, (LONG)(vp.X + vp.Width));
		y2 = std::min<LONG>(y2, (LONG)(vp.Y + vp.Height));
		x1 = std::max<LONG>(x1, 0);
		y1 = std::max<LONG>(y1, 0);
		x2 = std::min<LONG>(x2, (LONG)rtW);
		y2 = std::min<LONG>(y2, (LONG)rtH);
		if (x2 <= x1 || y2 <= y1)
			return;
		MTLScissorRect r = { (NSUInteger)x1, (NSUInteger)y1, (NSUInteger)(x2 - x1), (NSUInteger)(y2 - y1) };
		drawClearQuad(Flags, Color, Z, Stencil, r);
	};
	if (Count == 0 || pRects == nullptr)
		clip(0, 0, (LONG)rtW, (LONG)rtH);
	else
	{
		for (DWORD i = 0; i < Count; ++i)
			clip(pRects[i].x1, pRects[i].y1, pRects[i].x2, pRects[i].y2);
	}
	return D3D_OK;
}

//-----------------------------------------------------------------------------
// Pipeline state
//-----------------------------------------------------------------------------
TextureStorage* Device::stageStorage(DWORD stage) const
{
	IDirect3DBaseTexture8* tex = m_state.textures[stage];
	if (tex == nullptr)
		return nullptr;
	switch (tex->GetType())
	{
	case D3DRTYPE_TEXTURE: return static_cast<Texture*>(tex)->m_storage.get();
	case D3DRTYPE_CUBETEXTURE: return static_cast<CubeTexture*>(tex)->m_storage.get();
	default: return nullptr;
	}
}

id<MTLSamplerState> Device::samplerFor(DWORD stage)
{
	const DWORD* ts = m_state.stageStates[stage];
	DWORD mag = ts[D3DTSS_MAGFILTER], min = ts[D3DTSS_MINFILTER], mip = ts[D3DTSS_MIPFILTER];
	DWORD aniso = std::min<DWORD>(16, std::max<DWORD>(1, ts[D3DTSS_MAXANISOTROPY]));
	if (mag != D3DTEXF_ANISOTROPIC && min != D3DTEXF_ANISOTROPIC)
		aniso = 1;
	DWORD border = ts[D3DTSS_BORDERCOLOR];
	uint64_t key = (uint64_t)mag | ((uint64_t)min << 4) | ((uint64_t)mip << 8) | ((uint64_t)ts[D3DTSS_ADDRESSU] << 12) | ((uint64_t)ts[D3DTSS_ADDRESSV] << 16)
		| ((uint64_t)ts[D3DTSS_ADDRESSW] << 20) | ((uint64_t)aniso << 24) | ((uint64_t)(((border >> 24) & 0xFF) > 127 ? 1 : 0) << 32)
		| ((uint64_t)((border & 0xFFFFFF) != 0 ? 1 : 0) << 33);
	auto it = m_samplers.find(key);
	if (it != m_samplers.end())
		return it->second;
	MTLSamplerDescriptor* sd = [MTLSamplerDescriptor new];
	sd.magFilter = mag == D3DTEXF_POINT ? MTLSamplerMinMagFilterNearest : MTLSamplerMinMagFilterLinear;
	sd.minFilter = min == D3DTEXF_POINT ? MTLSamplerMinMagFilterNearest : MTLSamplerMinMagFilterLinear;
	sd.mipFilter = mip == D3DTEXF_NONE ? MTLSamplerMipFilterNotMipmapped : (mip == D3DTEXF_POINT ? MTLSamplerMipFilterNearest : MTLSamplerMipFilterLinear);
	sd.maxAnisotropy = aniso;
	sd.sAddressMode = addressMode(ts[D3DTSS_ADDRESSU]);
	sd.tAddressMode = addressMode(ts[D3DTSS_ADDRESSV]);
	sd.rAddressMode = addressMode(ts[D3DTSS_ADDRESSW]);
	bool opaque = ((border >> 24) & 0xFF) > 127;
	bool white = (border & 0xFFFFFF) != 0;
	sd.borderColor = white ? MTLSamplerBorderColorOpaqueWhite : (opaque ? MTLSamplerBorderColorOpaqueBlack : MTLSamplerBorderColorTransparentBlack);
	id<MTLSamplerState> sampler = [m_mtlDevice newSamplerStateWithDescriptor:sd];
	m_samplers[key] = sampler;
	return sampler;
}

id<MTLDepthStencilState> Device::depthStencilFor()
{
	const DWORD* rs = m_state.renderStates;
	bool hasDepth = m_depthStencil != nullptr;
	bool zEnable = hasDepth && rs[D3DRS_ZENABLE] != D3DZB_FALSE;
	bool zWrite = zEnable && rs[D3DRS_ZWRITEENABLE];
	bool stencil = hasDepth && rs[D3DRS_STENCILENABLE];
	uint64_t key = (zEnable ? 1 : 0) | (zWrite ? 2 : 0) | ((uint64_t)(rs[D3DRS_ZFUNC] & 15) << 2);
	if (stencil)
	{
		key |= 1ULL << 6;
		key |= (uint64_t)(rs[D3DRS_STENCILFUNC] & 15) << 7;
		key |= (uint64_t)(rs[D3DRS_STENCILFAIL] & 15) << 11;
		key |= (uint64_t)(rs[D3DRS_STENCILZFAIL] & 15) << 15;
		key |= (uint64_t)(rs[D3DRS_STENCILPASS] & 15) << 19;
		key |= (uint64_t)(rs[D3DRS_STENCILMASK] & 0xFF) << 23;
		key |= (uint64_t)(rs[D3DRS_STENCILWRITEMASK] & 0xFF) << 31;
	}
	auto it = m_depthStates.find(key);
	if (it != m_depthStates.end())
		return it->second;
	MTLDepthStencilDescriptor* dd = [MTLDepthStencilDescriptor new];
	dd.depthCompareFunction = zEnable ? compareFunc(rs[D3DRS_ZFUNC]) : MTLCompareFunctionAlways;
	dd.depthWriteEnabled = zWrite;
	if (stencil)
	{
		MTLStencilDescriptor* sd = [MTLStencilDescriptor new];
		sd.stencilCompareFunction = compareFunc(rs[D3DRS_STENCILFUNC]);
		sd.stencilFailureOperation = stencilOp(rs[D3DRS_STENCILFAIL]);
		sd.depthFailureOperation = stencilOp(rs[D3DRS_STENCILZFAIL]);
		sd.depthStencilPassOperation = stencilOp(rs[D3DRS_STENCILPASS]);
		sd.readMask = rs[D3DRS_STENCILMASK] & 0xFF;
		sd.writeMask = rs[D3DRS_STENCILWRITEMASK] & 0xFF;
		dd.frontFaceStencil = sd;
		dd.backFaceStencil = sd;
	}
	id<MTLDepthStencilState> state = [m_mtlDevice newDepthStencilStateWithDescriptor:dd];
	m_depthStates[key] = state;
	return state;
}

id<MTLRenderPipelineState> Device::pipelineFor(const ShaderKey& key, const VertexLayout& layout, const BlendKey& blend)
{
	uint64_t shaderHash = key.hash();
	uint64_t h = shaderHash;
	auto mix = [&h](uint64_t v) {
		h ^= v + 0x9E3779B97F4A7C15ULL + (h << 6) + (h >> 2);
	};
	mix(layout.fvf);
	mix(layout.stride);
	uint64_t b;
	memcpy(&b, &blend, sizeof(b));
	mix(b);

	auto it = m_pipelines.find(h);
	if (it != m_pipelines.end())
		return it->second;

	id<MTLFunction> vfn = nil, ffn = nil;
	auto vit = m_vertexFunctions.find(shaderHash);
	if (vit != m_vertexFunctions.end())
	{
		vfn = vit->second;
		ffn = m_fragmentFunctions[shaderHash];
	}
	else
	{
		std::string source = GenerateShaderSource(key);
		NSError* error = nil;
		MTLCompileOptions* options = [MTLCompileOptions new];
		options.mathMode = MTLMathModeFast;
		const bool trace = traceEnabled();
		CFAbsoluteTime start = CFAbsoluteTimeGetCurrent();
		id<MTLLibrary> lib = [m_mtlDevice newLibraryWithSource:[NSString stringWithUTF8String:source.c_str()] options:options error:&error];
		if (trace)
			fprintf(stderr, "d3d8metal: compiled shader %016llx in %.1f ms\n", (unsigned long long)shaderHash,
				(CFAbsoluteTimeGetCurrent() - start) * 1000.0);
		if (lib == nil)
		{
			fprintf(stderr, "d3d8metal: shader compile failed:\n%s\n%s\n", [[error localizedDescription] UTF8String], source.c_str());
			m_pipelines[h] = nil;
			return nil;
		}
		vfn = [lib newFunctionWithName:@"vs_main"];
		ffn = [lib newFunctionWithName:@"fs_main"];
		m_vertexFunctions[shaderHash] = vfn;
		m_fragmentFunctions[shaderHash] = ffn;
	}

	// Vertex descriptor from the FVF.
	MTLVertexDescriptor* vd = [MTLVertexDescriptor vertexDescriptor];
	DWORD fvf = layout.fvf;
	unsigned offset = 0;
	auto attr = [&](int index, MTLVertexFormat format, unsigned size) {
		vd.attributes[index].format = format;
		vd.attributes[index].offset = offset;
		vd.attributes[index].bufferIndex = BUFFER_STREAM0;
		offset += size;
	};
	switch (fvf & D3DFVF_POSITION_MASK)
	{
	case D3DFVF_XYZRHW: attr(ATTR_POSITION, MTLVertexFormatFloat4, 16); break;
	case D3DFVF_XYZ: attr(ATTR_POSITION, MTLVertexFormatFloat3, 12); break;
	default:
	{
		// XYZBn: position followed by blend weights, which are ignored.
		unsigned weights = (((fvf & D3DFVF_POSITION_MASK) - D3DFVF_XYZB1) >> 1) + 1;
		attr(ATTR_POSITION, MTLVertexFormatFloat3, 12);
		offset += weights * 4;
		break;
	}
	}
	if (fvf & D3DFVF_NORMAL)
		attr(ATTR_NORMAL, MTLVertexFormatFloat3, 12);
	if (fvf & D3DFVF_PSIZE)
		attr(ATTR_PSIZE, MTLVertexFormatFloat, 4);
	if (fvf & D3DFVF_DIFFUSE)
		attr(ATTR_DIFFUSE, MTLVertexFormatUChar4Normalized_BGRA, 4);
	if (fvf & D3DFVF_SPECULAR)
		attr(ATTR_SPECULAR, MTLVertexFormatUChar4Normalized_BGRA, 4);
	unsigned numTex = (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
	for (unsigned i = 0; i < numTex; ++i)
	{
		unsigned n = FvfTexCoordSize(fvf, i);
		MTLVertexFormat f = n == 1 ? MTLVertexFormatFloat : n == 2 ? MTLVertexFormatFloat2 : n == 3 ? MTLVertexFormatFloat3 : MTLVertexFormatFloat4;
		attr(ATTR_TEXCOORD0 + (int)i, f, n * 4);
	}
	vd.layouts[BUFFER_STREAM0].stride = std::max<unsigned>(layout.stride, 4);
	vd.layouts[BUFFER_STREAM0].stepFunction = MTLVertexStepFunctionPerVertex;

	MTLRenderPipelineDescriptor* pd = [MTLRenderPipelineDescriptor new];
	pd.vertexFunction = vfn;
	pd.fragmentFunction = ffn;
	pd.vertexDescriptor = vd;
	pd.colorAttachments[0].pixelFormat = MTLPixelFormatBGRA8Unorm;
	pd.colorAttachments[0].writeMask = blend.writeMask;
	if (blend.enable)
	{
		pd.colorAttachments[0].blendingEnabled = YES;
		pd.colorAttachments[0].sourceRGBBlendFactor = (MTLBlendFactor)blend.src;
		pd.colorAttachments[0].destinationRGBBlendFactor = (MTLBlendFactor)blend.dst;
		pd.colorAttachments[0].sourceAlphaBlendFactor = (MTLBlendFactor)blend.src;
		pd.colorAttachments[0].destinationAlphaBlendFactor = (MTLBlendFactor)blend.dst;
		pd.colorAttachments[0].rgbBlendOperation = (MTLBlendOperation)blend.op;
		pd.colorAttachments[0].alphaBlendOperation = (MTLBlendOperation)blend.op;
	}
	if (blend.hasDepth)
	{
		pd.depthAttachmentPixelFormat = MTLPixelFormatDepth32Float_Stencil8;
		pd.stencilAttachmentPixelFormat = MTLPixelFormatDepth32Float_Stencil8;
	}
	pd.inputPrimitiveTopology = key.pointList ? MTLPrimitiveTopologyClassPoint : MTLPrimitiveTopologyClassUnspecified;

	NSError* error = nil;
	id<MTLRenderPipelineState> pipeline = [m_mtlDevice newRenderPipelineStateWithDescriptor:pd error:&error];
	if (pipeline == nil)
		fprintf(stderr, "d3d8metal: pipeline creation failed: %s\n", [[error localizedDescription] UTF8String]);
	m_pipelines[h] = pipeline;
	return pipeline;
}

//-----------------------------------------------------------------------------
// Draw preparation
//-----------------------------------------------------------------------------
namespace
{
DWORD currentFvf(const DeviceState& s, const std::map<DWORD, VertexShaderObject>& shaders)
{
	if ((s.vertexShader & 1) == 0)
		return s.vertexShader;
	auto it = shaders.find(s.vertexShader);
	return it != shaders.end() ? it->second.fvf : 0;
}
} // namespace

void Device::traceDraw(const ShaderKey& key, D3DPRIMITIVETYPE type) const
{
	const DWORD* rs = m_state.renderStates;
	const D3DMATERIAL8& m = m_state.material;
	fprintf(stderr, "d3d8metal: draw type %d fvf 0x%X lighting %d ambient 0x%08X colorvertex %d sources d%d a%d e%d"
		" material d(%.2f %.2f %.2f %.2f) a(%.2f %.2f %.2f) e(%.2f %.2f %.2f) s(%.2f %.2f %.2f) specular %d\n",
		(int)type, (unsigned)key.fvf, key.lighting, (unsigned)rs[D3DRS_AMBIENT], key.colorVertex, key.diffuseSource,
		key.ambientSource, key.emissiveSource, m.Diffuse.r, m.Diffuse.g, m.Diffuse.b, m.Diffuse.a, m.Ambient.r,
		m.Ambient.g, m.Ambient.b, m.Emissive.r, m.Emissive.g, m.Emissive.b, m.Specular.r, m.Specular.g, m.Specular.b,
		key.specularEnable);
	for (int i = 0; i < MAX_LIGHTS; ++i)
	{
		if (!key.lightTypes[i])
			continue;
		const D3DLIGHT8& l = m_state.lights[i];
		fprintf(stderr, "d3d8metal:   light %d type %d diffuse(%.2f %.2f %.2f) dir(%.2f %.2f %.2f)\n", i, (int)l.Type,
			l.Diffuse.r, l.Diffuse.g, l.Diffuse.b, l.Direction.x, l.Direction.y, l.Direction.z);
	}
	for (unsigned i = 0; i < key.numStages; ++i)
	{
		const StageKey& st = key.stages[i];
		const DWORD* ts = m_state.stageStates[i];
		TextureStorage* tex = stageStorage(i);
		fprintf(stderr, "d3d8metal:   stage %u color %d(%d,%d) alpha %d(%d,%d) tex %d coord %d gen %d ttff 0x%X addr %d/%d filter %d/%d/%d",
			i, st.colorOp, st.colorArg1, st.colorArg2, st.alphaOp, st.alphaArg1, st.alphaArg2, st.textureType, st.texCoordIndex,
			st.texGen, (unsigned)ts[D3DTSS_TEXTURETRANSFORMFLAGS], (int)ts[D3DTSS_ADDRESSU], (int)ts[D3DTSS_ADDRESSV],
			(int)ts[D3DTSS_MINFILTER], (int)ts[D3DTSS_MAGFILTER], (int)ts[D3DTSS_MIPFILTER]);
		if (tex)
			fprintf(stderr, " texture %ux%u format %d levels %u", tex->width, tex->height, (int)tex->format, tex->levels);
		fprintf(stderr, "\n");
	}
}

void Device::beginDraw(D3DPRIMITIVETYPE type, bool& ok)
{
	ok = false;
	DWORD fvf = currentFvf(m_state, m_vertexShaders);
	if (fvf == 0 || (fvf & D3DFVF_POSITION_MASK) == 0)
		return;
	const DWORD* rs = m_state.renderStates;
	DrawContext ctx;
	memset(&ctx, 0, sizeof(ctx));
	{
		ShaderKey& key = ctx.key;
		key.fvf = fvf & ~D3DFVF_LASTBETA_UBYTE4;
		bool rhw = (fvf & D3DFVF_POSITION_MASK) == D3DFVF_XYZRHW;
		key.lighting = (!rhw && rs[D3DRS_LIGHTING]) ? 1 : 0;
		if (key.lighting)
		{
			key.localViewer = rs[D3DRS_LOCALVIEWER] ? 1 : 0;
			key.colorVertex = rs[D3DRS_COLORVERTEX] ? 1 : 0;
			key.diffuseSource = (uint8_t)rs[D3DRS_DIFFUSEMATERIALSOURCE];
			key.ambientSource = (uint8_t)rs[D3DRS_AMBIENTMATERIALSOURCE];
			key.specularSource = (uint8_t)rs[D3DRS_SPECULARMATERIALSOURCE];
			key.emissiveSource = (uint8_t)rs[D3DRS_EMISSIVEMATERIALSOURCE];
			for (int i = 0; i < MAX_LIGHTS; ++i)
			{
				if (m_state.lightEnabled[i])
					key.lightTypes[i] = (uint8_t)m_state.lights[i].Type;
			}
		}
		key.normalizeNormals = rs[D3DRS_NORMALIZENORMALS] ? 1 : 0;
		key.specularEnable = rs[D3DRS_SPECULARENABLE] ? 1 : 0;
		key.fogEnable = rs[D3DRS_FOGENABLE] ? 1 : 0;
		if (key.fogEnable)
		{
			key.vertexFog = (uint8_t)rs[D3DRS_FOGVERTEXMODE];
			key.tableFog = (uint8_t)rs[D3DRS_FOGTABLEMODE];
			key.rangeFog = rs[D3DRS_RANGEFOGENABLE] ? 1 : 0;
		}
		key.alphaFunc = rs[D3DRS_ALPHATESTENABLE] ? (uint8_t)rs[D3DRS_ALPHAFUNC] : (uint8_t)D3DCMP_ALWAYS;
		key.flatShade = rs[D3DRS_SHADEMODE] == D3DSHADE_FLAT ? 1 : 0;
		key.clipPlaneMask = rhw ? 0 : (uint8_t)(rs[D3DRS_CLIPPLANEENABLE] & 0x3F);
		key.pointList = type == D3DPT_POINTLIST ? 1 : 0;
		key.pointSprite = (key.pointList && rs[D3DRS_POINTSPRITEENABLE]) ? 1 : 0;
		key.pointScale = (key.pointList && rs[D3DRS_POINTSCALEENABLE]) ? 1 : 0;
		unsigned numStages = 0;
		for (unsigned i = 0; i < EMULATED_STAGES; ++i)
		{
			const DWORD* ts = m_state.stageStates[i];
			if (ts[D3DTSS_COLOROP] == D3DTOP_DISABLE)
				break;
			StageKey& st = key.stages[i];
			st.colorOp = (uint8_t)ts[D3DTSS_COLOROP];
			st.colorArg0 = (uint8_t)ts[D3DTSS_COLORARG0];
			st.colorArg1 = (uint8_t)ts[D3DTSS_COLORARG1];
			st.colorArg2 = (uint8_t)ts[D3DTSS_COLORARG2];
			st.alphaOp = (uint8_t)ts[D3DTSS_ALPHAOP];
			st.alphaArg0 = (uint8_t)ts[D3DTSS_ALPHAARG0];
			st.alphaArg1 = (uint8_t)ts[D3DTSS_ALPHAARG1];
			st.alphaArg2 = (uint8_t)ts[D3DTSS_ALPHAARG2];
			st.resultTemp = (ts[D3DTSS_RESULTARG] & D3DTA_SELECTMASK) == D3DTA_TEMP ? 1 : 0;
			st.texCoordIndex = (uint8_t)(ts[D3DTSS_TEXCOORDINDEX] & 0xFFFF);
			st.texGen = (uint8_t)((ts[D3DTSS_TEXCOORDINDEX] >> 16) & 0xF);
			DWORD ttff = ts[D3DTSS_TEXTURETRANSFORMFLAGS];
			st.transformCount = (uint8_t)(ttff & 0xFF);
			st.projected = (ttff & D3DTTFF_PROJECTED) ? 1 : 0;
			IDirect3DBaseTexture8* tex = m_state.textures[i];
			st.textureType = tex == nullptr ? 0 : (tex->GetType() == D3DRTYPE_CUBETEXTURE ? 2 : 1);
			++numStages;
		}
		key.numStages = (uint8_t)numStages;

		BlendKey& blend = ctx.blend;
		if (rs[D3DRS_ALPHABLENDENABLE])
		{
			DWORD src = rs[D3DRS_SRCBLEND], dst = rs[D3DRS_DESTBLEND];
			if (src == D3DBLEND_BOTHSRCALPHA)
			{
				src = D3DBLEND_SRCALPHA;
				dst = D3DBLEND_INVSRCALPHA;
			}
			else if (src == D3DBLEND_BOTHINVSRCALPHA)
			{
				src = D3DBLEND_INVSRCALPHA;
				dst = D3DBLEND_SRCALPHA;
			}
			blend.enable = 1;
			blend.src = (uint8_t)blendFactor(src);
			blend.dst = (uint8_t)blendFactor(dst);
			blend.op = (uint8_t)blendOp(rs[D3DRS_BLENDOP]);
		}
		DWORD cw = rs[D3DRS_COLORWRITEENABLE];
		uint8_t mask = 0;
		if (cw & D3DCOLORWRITEENABLE_RED)
			mask |= MTLColorWriteMaskRed;
		if (cw & D3DCOLORWRITEENABLE_GREEN)
			mask |= MTLColorWriteMaskGreen;
		if (cw & D3DCOLORWRITEENABLE_BLUE)
			mask |= MTLColorWriteMaskBlue;
		if (cw & D3DCOLORWRITEENABLE_ALPHA)
			mask |= MTLColorWriteMaskAlpha;
		D3DFORMAT rtFormat = m_renderTarget->m_storage->format;
		if (rtFormat == D3DFMT_X8R8G8B8 || rtFormat == D3DFMT_R5G6B5 || rtFormat == D3DFMT_X1R5G5B5)
			mask &= ~MTLColorWriteMaskAlpha;
		blend.writeMask = mask;
		blend.hasDepth = activeDepthTexture() != nil ? 1 : 0;

		ctx.layout.fvf = key.fvf;
		ctx.layout.stride = m_state.streams[0].stride;
		if (ctx.layout.stride == 0)
			ctx.layout.stride = FvfVertexSize(key.fvf);
	}

	if (traceEnabled())
		traceDraw(ctx.key, type);

	id<MTLRenderPipelineState> pipeline = pipelineFor(ctx.key, ctx.layout, ctx.blend);
	if (pipeline == nil)
		return;

	id<MTLRenderCommandEncoder> enc = renderEncoder();
	[enc setRenderPipelineState:pipeline];
	[enc setDepthStencilState:depthStencilFor()];
	[enc setStencilReferenceValue:rs[D3DRS_STENCILREF] & 0xFF];

	// Rasterizer state
	const D3DVIEWPORT8& vp = m_state.viewport;
	unsigned rtW = m_renderTarget->width(), rtH = m_renderTarget->height();
	MTLViewport viewport = { (double)vp.X, (double)vp.Y, (double)std::max<DWORD>(vp.Width, 1), (double)std::max<DWORD>(vp.Height, 1), (double)vp.MinZ, (double)vp.MaxZ };
	[enc setViewport:viewport];
	NSUInteger sx = std::min<NSUInteger>(vp.X, rtW), sy = std::min<NSUInteger>(vp.Y, rtH);
	NSUInteger sw = std::min<NSUInteger>(vp.Width, rtW - sx), sh = std::min<NSUInteger>(vp.Height, rtH - sy);
	if (sw == 0 || sh == 0)
		return;
	[enc setScissorRect:(MTLScissorRect) { sx, sy, sw, sh }];

	switch (rs[D3DRS_CULLMODE])
	{
	case D3DCULL_NONE:
		[enc setCullMode:MTLCullModeNone];
		break;
	case D3DCULL_CW:
		[enc setFrontFacingWinding:MTLWindingCounterClockwise];
		[enc setCullMode:MTLCullModeBack];
		break;
	default:
		[enc setFrontFacingWinding:MTLWindingClockwise];
		[enc setCullMode:MTLCullModeBack];
		break;
	}
	[enc setTriangleFillMode:rs[D3DRS_FILLMODE] == D3DFILL_WIREFRAME ? MTLTriangleFillModeLines : MTLTriangleFillModeFill];
	float zbias = (float)rs[D3DRS_ZBIAS];
	[enc setDepthBias:-zbias * 16.0f slopeScale:-zbias * 0.25f clamp:0.0f];

	// Uniforms
	VertexUniforms vu;
	memset(&vu, 0, sizeof(vu));
	const D3DMATRIX& world = m_state.transforms[D3DTS_WORLDMATRIX(0)];
	const D3DMATRIX& view = m_state.transforms[D3DTS_VIEW];
	const D3DMATRIX& proj = m_state.transforms[D3DTS_PROJECTION];
	D3DMATRIX wv, wvp, inv, nrm;
	multiply(world, view, wv);
	multiply(wv, proj, wvp);
	invert(wv, inv);
	transpose(inv, nrm);
	memcpy(vu.worldViewProj, &wvp, 64);
	memcpy(vu.worldView, &wv, 64);
	memcpy(vu.normalMatrix, &nrm, 64);
	for (unsigned i = 0; i < ctx.key.numStages; ++i)
		memcpy(vu.texMatrix[i], &m_state.transforms[D3DTS_TEXTURE0 + i], 64);
	vu.viewport[0] = (float)vp.X;
	vu.viewport[1] = (float)vp.Y;
	vu.viewport[2] = (float)std::max<DWORD>(vp.Width, 1);
	vu.viewport[3] = (float)std::max<DWORD>(vp.Height, 1);
	vu.depthRange[0] = vp.MinZ;
	vu.depthRange[1] = vp.MaxZ;
	vu.depthRange[2] = (float)rtW;
	vu.depthRange[3] = (float)rtH;
	valueToFloat4(m_state.material.Diffuse, vu.materialDiffuse);
	valueToFloat4(m_state.material.Ambient, vu.materialAmbient);
	valueToFloat4(m_state.material.Specular, vu.materialSpecular);
	valueToFloat4(m_state.material.Emissive, vu.materialEmissive);
	vu.materialPower[0] = m_state.material.Power;
	colorToFloat4(rs[D3DRS_AMBIENT], vu.globalAmbient);
	vu.fogParams[0] = bitsFloat(rs[D3DRS_FOGSTART]);
	vu.fogParams[1] = bitsFloat(rs[D3DRS_FOGEND]);
	vu.fogParams[2] = bitsFloat(rs[D3DRS_FOGDENSITY]);
	if (ctx.key.clipPlaneMask)
	{
		D3DMATRIX viewInv;
		invert(view, viewInv);
		for (int i = 0; i < MAX_CLIP_PLANES; ++i)
		{
			const float* p = m_state.clipPlanes[i];
			for (int j = 0; j < 4; ++j)
				vu.clipPlanes[i][j] = p[0] * viewInv.m[j][0] + p[1] * viewInv.m[j][1] + p[2] * viewInv.m[j][2] + p[3] * viewInv.m[j][3];
		}
	}
	vu.pointParams[0] = bitsFloat(rs[D3DRS_POINTSIZE]);
	vu.pointParams[1] = bitsFloat(rs[D3DRS_POINTSIZE_MIN]);
	vu.pointParams[2] = bitsFloat(rs[D3DRS_POINTSIZE_MAX]);
	vu.pointScale[0] = bitsFloat(rs[D3DRS_POINTSCALE_A]);
	vu.pointScale[1] = bitsFloat(rs[D3DRS_POINTSCALE_B]);
	vu.pointScale[2] = bitsFloat(rs[D3DRS_POINTSCALE_C]);
	vu.pointScale[3] = (float)std::max<DWORD>(vp.Height, 1);
	if (ctx.key.lighting)
	{
		for (int i = 0; i < MAX_LIGHTS; ++i)
		{
			if (!m_state.lightEnabled[i])
				continue;
			const D3DLIGHT8& l = m_state.lights[i];
			LightUniform& lu = vu.lights[i];
			valueToFloat4(l.Diffuse, lu.diffuse);
			valueToFloat4(l.Specular, lu.specular);
			valueToFloat4(l.Ambient, lu.ambient);
			const float* v = &view._11;
			float px = l.Position.x, py = l.Position.y, pz = l.Position.z;
			lu.position[0] = px * v[0] + py * v[4] + pz * v[8] + v[12];
			lu.position[1] = px * v[1] + py * v[5] + pz * v[9] + v[13];
			lu.position[2] = px * v[2] + py * v[6] + pz * v[10] + v[14];
			lu.position[3] = 1.0f;
			float dx = l.Direction.x, dy = l.Direction.y, dz = l.Direction.z;
			float vx = dx * v[0] + dy * v[4] + dz * v[8];
			float vy = dx * v[1] + dy * v[5] + dz * v[9];
			float vz = dx * v[2] + dy * v[6] + dz * v[10];
			float len = sqrtf(vx * vx + vy * vy + vz * vz);
			if (len > 0.0f)
			{
				vx /= len;
				vy /= len;
				vz /= len;
			}
			lu.direction[0] = vx;
			lu.direction[1] = vy;
			lu.direction[2] = vz;
			lu.attenuation[0] = l.Range > 0.0f ? l.Range : 1e30f;
			lu.attenuation[1] = l.Attenuation0;
			lu.attenuation[2] = l.Attenuation1;
			lu.attenuation[3] = l.Attenuation2;
			lu.spot[0] = l.Falloff;
			lu.spot[1] = cosf(l.Theta * 0.5f);
			lu.spot[2] = cosf(l.Phi * 0.5f);
		}
	}
	[enc setVertexBytes:&vu length:sizeof(vu) atIndex:BUFFER_UNIFORMS];

	FragmentUniforms fu;
	memset(&fu, 0, sizeof(fu));
	colorToFloat4(rs[D3DRS_TEXTUREFACTOR], fu.textureFactor);
	colorToFloat4(rs[D3DRS_FOGCOLOR], fu.fogColor);
	memcpy(fu.fogParams, vu.fogParams, sizeof(fu.fogParams));
	fu.alphaRef[0] = (rs[D3DRS_ALPHAREF] & 0xFF) / 255.0f;
	for (unsigned i = 0; i < ctx.key.numStages; ++i)
	{
		const DWORD* ts = m_state.stageStates[i];
		fu.bumpEnv[i][0] = bitsFloat(ts[D3DTSS_BUMPENVMAT00]);
		fu.bumpEnv[i][1] = bitsFloat(ts[D3DTSS_BUMPENVMAT01]);
		fu.bumpEnv[i][2] = bitsFloat(ts[D3DTSS_BUMPENVMAT10]);
		fu.bumpEnv[i][3] = bitsFloat(ts[D3DTSS_BUMPENVMAT11]);
		fu.bumpLum[i][0] = bitsFloat(ts[D3DTSS_BUMPENVLSCALE]);
		fu.bumpLum[i][1] = bitsFloat(ts[D3DTSS_BUMPENVLOFFSET]);
	}
	[enc setFragmentBytes:&fu length:sizeof(fu) atIndex:BUFFER_UNIFORMS];

	// Textures
	for (unsigned i = 0; i < ctx.key.numStages; ++i)
	{
		TextureStorage* st = stageStorage(i);
		id<MTLTexture> tex = nil;
		if (st && st->texture)
		{
			tex = st->texture;
			markTextureUsed(*st);
			if (st == m_renderTarget->m_storage.get())
				tex = nil; // feedback loops are undefined in D3D; avoid them here
		}
		if (tex == nil)
			tex = ctx.key.stages[i].textureType == 2 ? m_whiteCube : m_whiteTexture;
		[enc setFragmentTexture:tex atIndex:i];
		[enc setFragmentSamplerState:samplerFor(i) atIndex:i];
	}
	ok = true;
}

//-----------------------------------------------------------------------------
// Draw calls
//-----------------------------------------------------------------------------
HRESULT Device::DrawPrimitive(D3DPRIMITIVETYPE PrimitiveType, UINT StartVertex, UINT PrimitiveCount)
{
	VertexBuffer* vb = m_state.streams[0].buffer;
	if (vb == nullptr || PrimitiveCount == 0)
		return D3D_OK;
	bool ok;
	beginDraw(PrimitiveType, ok);
	if (!ok)
		return D3D_OK;
	id<MTLRenderCommandEncoder> enc = m_encoder;
	[enc setVertexBuffer:vb->m_storage.buffer offset:0 atIndex:BUFFER_STREAM0];
	vb->m_storage.lastUsedSerial = m_currentSerial;

	unsigned count = vertexCountFor(PrimitiveType, PrimitiveCount);
	if (PrimitiveType == D3DPT_TRIANGLEFAN)
	{
		Transient idx = allocTransient(PrimitiveCount * 3 * 4, 4);
		uint32_t* out = (uint32_t*)idx.cpu;
		for (UINT i = 0; i < PrimitiveCount; ++i)
		{
			out[i * 3 + 0] = StartVertex;
			out[i * 3 + 1] = StartVertex + i + 1;
			out[i * 3 + 2] = StartVertex + i + 2;
		}
		[enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:PrimitiveCount * 3 indexType:MTLIndexTypeUInt32 indexBuffer:idx.buffer indexBufferOffset:idx.offset];
		return D3D_OK;
	}
	[enc drawPrimitives:primitiveType(PrimitiveType) vertexStart:StartVertex vertexCount:count];
	return D3D_OK;
}

HRESULT Device::DrawIndexedPrimitive(D3DPRIMITIVETYPE PrimitiveType, UINT, UINT, UINT startIndex, UINT primCount)
{
	VertexBuffer* vb = m_state.streams[0].buffer;
	IndexBuffer* ib = m_state.indices;
	if (vb == nullptr || ib == nullptr || primCount == 0)
		return D3D_OK;
	bool ok;
	beginDraw(PrimitiveType, ok);
	if (!ok)
		return D3D_OK;
	id<MTLRenderCommandEncoder> enc = m_encoder;
	[enc setVertexBuffer:vb->m_storage.buffer offset:0 atIndex:BUFFER_STREAM0];
	vb->m_storage.lastUsedSerial = m_currentSerial;
	ib->m_storage.lastUsedSerial = m_currentSerial;

	bool is32 = ib->m_format == D3DFMT_INDEX32;
	unsigned indexSize = is32 ? 4 : 2;
	unsigned count = vertexCountFor(PrimitiveType, primCount);
	NSUInteger offset = (NSUInteger)startIndex * indexSize;
	NSInteger baseVertex = (NSInteger)m_state.baseVertexIndex;

	if (PrimitiveType == D3DPT_TRIANGLEFAN)
	{
		Transient idx = allocTransient(primCount * 3 * 4, 4);
		uint32_t* out = (uint32_t*)idx.cpu;
		const uint8_t* src = (const uint8_t*)[ib->m_storage.buffer contents] + offset;
		auto read = [&](unsigned i) -> uint32_t { return is32 ? ((const uint32_t*)src)[i] : ((const uint16_t*)src)[i]; };
		for (UINT i = 0; i < primCount; ++i)
		{
			out[i * 3 + 0] = read(0);
			out[i * 3 + 1] = read(i + 1);
			out[i * 3 + 2] = read(i + 2);
		}
		[enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:primCount * 3 indexType:MTLIndexTypeUInt32 indexBuffer:idx.buffer
				 indexBufferOffset:idx.offset instanceCount:1 baseVertex:baseVertex baseInstance:0];
		return D3D_OK;
	}

	id<MTLBuffer> indexBuffer = ib->m_storage.buffer;
	if (offset % 4 != 0)
	{
		// Metal requires 4 byte aligned index buffer offsets.
		Transient idx = allocTransient(count * indexSize, 4);
		memcpy(idx.cpu, (const uint8_t*)[indexBuffer contents] + offset, count * indexSize);
		indexBuffer = idx.buffer;
		offset = idx.offset;
	}
	[enc drawIndexedPrimitives:primitiveType(PrimitiveType) indexCount:count indexType:is32 ? MTLIndexTypeUInt32 : MTLIndexTypeUInt16 indexBuffer:indexBuffer
			 indexBufferOffset:offset instanceCount:1 baseVertex:baseVertex baseInstance:0];
	return D3D_OK;
}

HRESULT Device::DrawPrimitiveUP(D3DPRIMITIVETYPE PrimitiveType, UINT PrimitiveCount, CONST void* pVertexStreamZeroData, UINT VertexStreamZeroStride)
{
	if (pVertexStreamZeroData == nullptr || PrimitiveCount == 0)
		return D3D_OK;
	unsigned count = vertexCountFor(PrimitiveType, PrimitiveCount);
	Transient vtx = allocTransient((NSUInteger)count * VertexStreamZeroStride, 16);
	memcpy(vtx.cpu, pVertexStreamZeroData, (size_t)count * VertexStreamZeroStride);

	// D3D8 semantics: stream 0 is reset after an UP draw.
	SetStreamSource(0, nullptr, VertexStreamZeroStride);
	bool ok;
	beginDraw(PrimitiveType, ok);
	m_state.streams[0].stride = 0;
	if (!ok)
		return D3D_OK;
	id<MTLRenderCommandEncoder> enc = m_encoder;
	[enc setVertexBuffer:vtx.buffer offset:vtx.offset atIndex:BUFFER_STREAM0];
	if (PrimitiveType == D3DPT_TRIANGLEFAN)
	{
		Transient idx = allocTransient(PrimitiveCount * 3 * 4, 4);
		uint32_t* out = (uint32_t*)idx.cpu;
		for (UINT i = 0; i < PrimitiveCount; ++i)
		{
			out[i * 3 + 0] = 0;
			out[i * 3 + 1] = i + 1;
			out[i * 3 + 2] = i + 2;
		}
		[enc drawIndexedPrimitives:MTLPrimitiveTypeTriangle indexCount:PrimitiveCount * 3 indexType:MTLIndexTypeUInt32 indexBuffer:idx.buffer indexBufferOffset:idx.offset];
		return D3D_OK;
	}
	[enc drawPrimitives:primitiveType(PrimitiveType) vertexStart:0 vertexCount:count];
	return D3D_OK;
}

HRESULT Device::DrawIndexedPrimitiveUP(D3DPRIMITIVETYPE PrimitiveType, UINT MinVertexIndex, UINT NumVertexIndices, UINT PrimitiveCount, CONST void* pIndexData,
	D3DFORMAT IndexDataFormat, CONST void* pVertexStreamZeroData, UINT VertexStreamZeroStride)
{
	if (pVertexStreamZeroData == nullptr || pIndexData == nullptr || PrimitiveCount == 0)
		return D3D_OK;
	unsigned vertexCount = MinVertexIndex + NumVertexIndices;
	Transient vtx = allocTransient((NSUInteger)vertexCount * VertexStreamZeroStride, 16);
	memcpy(vtx.cpu, pVertexStreamZeroData, (size_t)vertexCount * VertexStreamZeroStride);

	bool is32 = IndexDataFormat == D3DFMT_INDEX32;
	unsigned indexSize = is32 ? 4 : 2;
	unsigned count = vertexCountFor(PrimitiveType, PrimitiveCount);
	Transient idx;
	MTLIndexType indexType = is32 ? MTLIndexTypeUInt32 : MTLIndexTypeUInt16;
	if (PrimitiveType == D3DPT_TRIANGLEFAN)
	{
		idx = allocTransient(PrimitiveCount * 3 * 4, 4);
		uint32_t* out = (uint32_t*)idx.cpu;
		auto read = [&](unsigned i) -> uint32_t { return is32 ? ((const uint32_t*)pIndexData)[i] : ((const uint16_t*)pIndexData)[i]; };
		for (UINT i = 0; i < PrimitiveCount; ++i)
		{
			out[i * 3 + 0] = read(0);
			out[i * 3 + 1] = read(i + 1);
			out[i * 3 + 2] = read(i + 2);
		}
		count = PrimitiveCount * 3;
		indexType = MTLIndexTypeUInt32;
	}
	else
	{
		idx = allocTransient(count * indexSize, 4);
		memcpy(idx.cpu, pIndexData, (size_t)count * indexSize);
	}

	SetStreamSource(0, nullptr, VertexStreamZeroStride);
	SetIndices(nullptr, 0);
	bool ok;
	beginDraw(PrimitiveType, ok);
	m_state.streams[0].stride = 0;
	if (!ok)
		return D3D_OK;
	id<MTLRenderCommandEncoder> enc = m_encoder;
	[enc setVertexBuffer:vtx.buffer offset:vtx.offset atIndex:BUFFER_STREAM0];
	[enc drawIndexedPrimitives:PrimitiveType == D3DPT_TRIANGLEFAN ? MTLPrimitiveTypeTriangle : primitiveType(PrimitiveType) indexCount:count indexType:indexType
				   indexBuffer:idx.buffer indexBufferOffset:idx.offset];
	return D3D_OK;
}

} // namespace d3d8metal

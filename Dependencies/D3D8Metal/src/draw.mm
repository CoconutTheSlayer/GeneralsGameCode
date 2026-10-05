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

} // namespace

size_t PipelineKeyHash::operator()(const PipelineKey& k) const
{
	static_assert(sizeof(PipelineKey) % 8 == 0, "PipelineKey is hashed in 8 byte words");
	return (size_t)HashWords(&k, sizeof(k));
}

void EncoderState::reset()
{
	pipeline = nil;
	depthStencil = nil;
	softDepth = nil;
	stencilRef = ~0u;
	viewport = MTLViewport { -1, -1, -1, -1, -1, -1 };
	scissor = MTLScissorRect { 0, 0, 0, 0 };
	cullMode = -1;
	winding = -1;
	fillMode = -1;
	depthBias = NAN;
	vertexBuffer = nil;
	vertexOffset = 0;
	for (int i = 0; i < MAX_STAGES; ++i)
	{
		textures[i] = nil;
		samplers[i] = nil;
	}
	vertexUniformsValid = false;
	fragmentUniformsValid = false;
	vsConstantsVersion = 0;
	psConstantsVersion = 0;
}

//-----------------------------------------------------------------------------
// Render passes
//-----------------------------------------------------------------------------
unsigned Device::renderTargetSamples() const
{
	return m_renderTarget->m_storage->msaaTexture != nil ? m_msaaSamples : 1;
}

id<MTLTexture> Device::activeDepthTexture()
{
	if (m_depthStencil == nullptr || m_depthStencil->m_storage->texture == nil)
		return nil;
	unsigned w = m_renderTarget->width(), h = m_renderTarget->height();
	unsigned samples = renderTargetSamples();
	bool sameSize = m_depthStencil->width() == w && m_depthStencil->height() == h;
	if (samples > 1)
	{
		// The multisampled back buffer pairs with the multisampled copy of the automatic depth buffer.
		if (m_depthStencil == m_depthBuffer && sameSize && m_msaaDepth != nil)
			return m_msaaDepth;
	}
	else if (sameSize)
		return m_depthStencil->m_storage->texture;
	// D3D allows a depth buffer larger than the render target, Metal requires
	// matching sizes and sample counts. Use a depth buffer that matches instead.
	uint64_t key = ((uint64_t)w << 34) | ((uint64_t)h << 4) | samples;
	auto it = m_scratchDepth.find(key);
	if (it != m_scratchDepth.end())
		return it->second;
	MTLTextureDescriptor* td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float_Stencil8 width:w height:h mipmapped:NO];
	if (samples > 1)
	{
		td.textureType = MTLTextureType2DMultisample;
		td.sampleCount = samples;
	}
	td.usage = MTLTextureUsageRenderTarget;
	td.storageMode = MTLStorageModePrivate;
	id<MTLTexture> depth = [m_mtlDevice newTextureWithDescriptor:td];
	m_scratchDepth[key] = depth;
	return depth;
}

bool Device::captureSoftDepth(id<MTLTexture> depth)
{
	// Clears still pending belong to the depth being copied.
	if (m_pendingClearFlags != 0)
		renderEncoder();
	endRenderEncoder();
	NSUInteger w = depth.width, h = depth.height;
	if (m_softDepth == nil || m_softDepth.width != w || m_softDepth.height != h)
	{
		MTLTextureDescriptor* td = [MTLTextureDescriptor texture2DDescriptorWithPixelFormat:MTLPixelFormatDepth32Float_Stencil8 width:w height:h mipmapped:NO];
		td.usage = MTLTextureUsageShaderRead | MTLTextureUsageRenderTarget;
		td.storageMode = MTLStorageModePrivate;
		m_softDepth = [m_mtlDevice newTextureWithDescriptor:td];
		if (m_softDepth == nil)
			return false;
	}
	if (depth.sampleCount > 1)
	{
		// An empty pass that keeps the depth and resolves it to the nearest sample of each pixel.
		MTLRenderPassDescriptor* pass = [MTLRenderPassDescriptor renderPassDescriptor];
		pass.depthAttachment.texture = depth;
		pass.depthAttachment.loadAction = MTLLoadActionLoad;
		pass.depthAttachment.storeAction = MTLStoreActionStoreAndMultisampleResolve;
		pass.depthAttachment.resolveTexture = m_softDepth;
		pass.depthAttachment.depthResolveFilter = MTLMultisampleDepthResolveFilterMin;
		pass.stencilAttachment.texture = depth;
		pass.stencilAttachment.loadAction = MTLLoadActionLoad;
		pass.stencilAttachment.storeAction = MTLStoreActionStore;
		[[commandBuffer() renderCommandEncoderWithDescriptor:pass] endEncoding];
	}
	else
	{
		id<MTLBlitCommandEncoder> blit = [commandBuffer() blitCommandEncoder];
		[blit copyFromTexture:depth toTexture:m_softDepth];
		[blit endEncoding];
	}
	m_softDepthValid = true;
	return true;
}

id<MTLRenderCommandEncoder> Device::renderEncoder()
{
	if (m_encoder)
		return m_encoder;

	TextureStorage& rt = *m_renderTarget->m_storage;
	MTLRenderPassDescriptor* pass = [MTLRenderPassDescriptor renderPassDescriptor];
	if (rt.msaaTexture != nil)
	{
		// Keep the samples for the next pass and resolve them into the texture after every pass, so
		// presentation, readbacks and screenshots see the finished image.
		pass.colorAttachments[0].texture = rt.msaaTexture;
		pass.colorAttachments[0].resolveTexture = rt.texture;
		pass.colorAttachments[0].storeAction = MTLStoreActionStoreAndMultisampleResolve;
	}
	else
	{
		pass.colorAttachments[0].texture = rt.texture;
		pass.colorAttachments[0].slice = m_renderTarget->m_face;
		pass.colorAttachments[0].level = m_renderTarget->m_level;
		pass.colorAttachments[0].storeAction = MTLStoreActionStore;
	}
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
	m_encoderState.reset();
	rt.shadowStale = true;
	markTextureUsed(rt);
	return m_encoder;
}

void Device::drawClearQuad(DWORD flags, D3DCOLOR color, float z, DWORD stencil, const MTLScissorRect& rect)
{
	id<MTLRenderCommandEncoder> enc = renderEncoder();
	bool hasDepth = activeDepthTexture() != nil;
	int pipe = ((flags & D3DCLEAR_TARGET) ? 1 : 0) | (hasDepth ? 2 : 0) | (renderTargetSamples() > 1 ? 4 : 0);
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
	// The clear replaced state and uniforms the next draw may otherwise skip setting.
	m_encoderState.reset();
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
	if (min != D3DTEXF_POINT && mip != D3DTEXF_NONE && m_filterUpgrade > 1)
	{
		// The game picks filters for 2001 hardware (the terrain uses bilinear filtering with the nearest
		// mip level). Smoothly filtered mipmapped textures get trilinear and anisotropic filtering, which
		// keeps the ground sharp and steady at the low camera angles of a zoomed out view.
		mip = D3DTEXF_LINEAR;
		aniso = std::max<DWORD>(aniso, m_filterUpgrade);
	}
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

bool Device::compileShader(const ShaderKey& key, id<MTLFunction> __strong& vfn, id<MTLFunction> __strong& ffn) const
{
	std::string source = GenerateShaderSource(key);
	NSError* error = nil;
	MTLCompileOptions* options = [MTLCompileOptions new];
	options.mathMode = MTLMathModeFast;
	const bool trace = traceEnabled();
	CFAbsoluteTime start = CFAbsoluteTimeGetCurrent();
	id<MTLLibrary> lib = [m_mtlDevice newLibraryWithSource:[NSString stringWithUTF8String:source.c_str()] options:options error:&error];
	if (trace)
		fprintf(stderr, "d3d8metal: compiled shader %016llx in %.1f ms\n", (unsigned long long)key.hash(),
			(CFAbsoluteTimeGetCurrent() - start) * 1000.0);
	if (lib == nil)
	{
		fprintf(stderr, "d3d8metal: shader compile failed:\n%s\n%s\n", [[error localizedDescription] UTF8String], source.c_str());
		vfn = nil;
		ffn = nil;
		return false;
	}
	vfn = [lib newFunctionWithName:@"vs_main"];
	ffn = [lib newFunctionWithName:@"fs_main"];
	return vfn != nil && ffn != nil;
}

id<MTLRenderPipelineState> Device::buildPipeline(const PipelineKey& key, id<MTLFunction> vfn, id<MTLFunction> ffn) const
{
	const VertexLayout& layout = key.layout;
	const BlendKey& blend = key.blend;

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
	if (key.shader.vertexShader != 0)
	{
		// Vertex shader input registers as the declaration laid them out.
		static const MTLVertexFormat formats[8] = { MTLVertexFormatFloat, MTLVertexFormatFloat2, MTLVertexFormatFloat3,
			MTLVertexFormatFloat4, MTLVertexFormatUChar4Normalized_BGRA, MTLVertexFormatUChar4, MTLVertexFormatShort2,
			MTLVertexFormatShort4 };
		bool any = false;
		for (int r = 0; r < 16; ++r)
		{
			unsigned type = key.shader.vsInputType[r];
			if (type == 0)
				continue;
			vd.attributes[r].format = formats[type - 1];
			vd.attributes[r].offset = layout.vsInputOffset[r];
			vd.attributes[r].bufferIndex = BUFFER_STREAM0;
			any = true;
		}
		if (!any)
		{
			vd.attributes[0].format = MTLVertexFormatFloat4;
			vd.attributes[0].offset = 0;
			vd.attributes[0].bufferIndex = BUFFER_STREAM0;
		}
	}
	else
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
	unsigned numTex = key.shader.vertexShader != 0 ? 0 : (fvf & D3DFVF_TEXCOUNT_MASK) >> D3DFVF_TEXCOUNT_SHIFT;
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
	pd.rasterSampleCount = std::max<unsigned>(blend.sampleCount, 1);
	pd.inputPrimitiveTopology = key.shader.pointList ? MTLPrimitiveTopologyClassPoint : MTLPrimitiveTopologyClassUnspecified;

	NSError* error = nil;
	id<MTLRenderPipelineState> pipeline = [m_mtlDevice newRenderPipelineStateWithDescriptor:pd error:&error];
	if (pipeline == nil)
		fprintf(stderr, "d3d8metal: pipeline creation failed: %s\n", [[error localizedDescription] UTF8String]);
	return pipeline;
}

id<MTLRenderPipelineState> Device::pipelineFor(const PipelineKey& key)
{
	if (m_lastPipeline != nil && key == m_lastPipelineKey)
		return m_lastPipeline;

	id<MTLRenderPipelineState> pipeline = nil;
	auto it = m_pipelines.find(key);
	if (it != m_pipelines.end())
		pipeline = it->second;
	else
	{
		auto fit = m_functions.find(key.shader);
		if (fit == m_functions.end())
		{
			id<MTLFunction> vfn = nil, ffn = nil;
			compileShader(key.shader, vfn, ffn);
			fit = m_functions.emplace(key.shader, std::make_pair(vfn, ffn)).first;
		}
		if (fit->second.first != nil)
			pipeline = buildPipeline(key, fit->second.first, fit->second.second);
		m_pipelines[key] = pipeline;
		if (pipeline != nil)
			recordPipeline(key);
	}
	m_lastPipelineKey = key;
	m_lastPipeline = pipeline;
	return pipeline;
}

//-----------------------------------------------------------------------------
// Pipeline cache: the keys of all pipelines built are appended to a file, and the
// pipelines listed there are built in parallel when the device is created, so
// shader compilation does not stall the first frames that need them.
//-----------------------------------------------------------------------------
namespace
{
struct PipelineCacheHeader
{
	char magic[4];
	uint32_t version;
	uint32_t keySize;
};

// Bump when generated shaders change in a way that makes old keys useless.
const uint32_t kPipelineCacheVersion = 4;

PipelineCacheHeader currentCacheHeader()
{
	PipelineCacheHeader h;
	memcpy(h.magic, "D8PC", 4);
	h.version = kPipelineCacheVersion;
	h.keySize = sizeof(PipelineKey);
	return h;
}

// D3D8METAL_PIPELINE_CACHE=<file> overrides the location; an empty value disables the cache.
std::string pipelineCachePath()
{
	if (const char* env = getenv("D3D8METAL_PIPELINE_CACHE"))
		return env;
	NSArray<NSString*>* dirs = NSSearchPathForDirectoriesInDomains(NSCachesDirectory, NSUserDomainMask, YES);
	if (dirs.count == 0)
		return std::string();
	NSString* name = [[NSBundle mainBundle] bundleIdentifier];
	if (name == nil)
		name = [[[NSProcessInfo processInfo] processName] stringByAppendingString:@".d3d8metal"];
	NSString* dir = [dirs[0] stringByAppendingPathComponent:name];
	[[NSFileManager defaultManager] createDirectoryAtPath:dir withIntermediateDirectories:YES attributes:nil error:nil];
	return [[dir stringByAppendingPathComponent:@"pipelines.bin"] UTF8String];
}
} // namespace

void Device::loadPipelineCache()
{
	std::string path = pipelineCachePath();
	if (path.empty())
		return;

	const PipelineCacheHeader expected = currentCacheHeader();
	std::vector<PipelineKey> keys;
	bool valid = false;
	if (FILE* f = fopen(path.c_str(), "rb"))
	{
		PipelineCacheHeader h;
		if (fread(&h, sizeof(h), 1, f) == 1 && memcmp(&h, &expected, sizeof(h)) == 0)
		{
			valid = true;
			PipelineKey key;
			while (fread(&key, sizeof(key), 1, f) == 1)
			{
				// Programmable shaders are created by the game later, so their pipelines are built
				// when first used; they are already in the file.
				if (key.shader.pixelShader != 0 || key.shader.vertexShader != 0)
					m_deferredCachedKeys.insert(key);
				else
					keys.push_back(key);
			}
		}
		fclose(f);
	}

	if (!keys.empty())
	{
		CFAbsoluteTime start = CFAbsoluteTimeGetCurrent();
		std::vector<ShaderKey> shaders;
		{
			std::unordered_map<ShaderKey, size_t, ShaderKeyHash> seen;
			for (const PipelineKey& k : keys)
			{
				if (seen.emplace(k.shader, shaders.size()).second)
					shaders.push_back(k.shader);
			}
		}
		// Metal compiles in parallel safely; results are stored per index and merged after.
		std::vector<id<MTLFunction>> vfns(shaders.size()), ffns(shaders.size());
		{
			id<MTLFunction> __strong* v = vfns.data();
			id<MTLFunction> __strong* f = ffns.data();
			const ShaderKey* sk = shaders.data();
			dispatch_apply(shaders.size(), DISPATCH_APPLY_AUTO, ^(size_t i) {
				id<MTLFunction> vfn = nil, ffn = nil;
				if (compileShader(sk[i], vfn, ffn))
				{
					v[i] = vfn;
					f[i] = ffn;
				}
			});
		}
		for (size_t i = 0; i < shaders.size(); ++i)
			m_functions.emplace(shaders[i], std::make_pair(vfns[i], ffns[i]));

		std::vector<id<MTLRenderPipelineState>> pipelines(keys.size());
		{
			id<MTLRenderPipelineState> __strong* out = pipelines.data();
			const PipelineKey* pk = keys.data();
			const auto* functions = &m_functions;
			dispatch_apply(keys.size(), DISPATCH_APPLY_AUTO, ^(size_t i) {
				auto it = functions->find(pk[i].shader);
				if (it != functions->end() && it->second.first != nil)
					out[i] = buildPipeline(pk[i], it->second.first, it->second.second);
			});
		}
		size_t built = 0;
		for (size_t i = 0; i < keys.size(); ++i)
		{
			if (pipelines[i] != nil && m_pipelines.emplace(keys[i], pipelines[i]).second)
				++built;
		}
		fprintf(stderr, "d3d8metal: built %zu cached pipelines (%zu shaders) in %.0f ms\n", built, shaders.size(),
			(CFAbsoluteTimeGetCurrent() - start) * 1000.0);
	}

	m_pipelineCacheFile = fopen(path.c_str(), valid ? "ab" : "wb");
	if (m_pipelineCacheFile && !valid)
	{
		fwrite(&expected, sizeof(expected), 1, m_pipelineCacheFile);
		fflush(m_pipelineCacheFile);
	}
}

void Device::recordPipeline(const PipelineKey& key)
{
	if (m_pipelineCacheFile == nullptr || m_deferredCachedKeys.count(key) != 0)
		return;
	fwrite(&key, sizeof(key), 1, m_pipelineCacheFile);
	fflush(m_pipelineCacheFile);
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
		" material d(%.2f %.2f %.2f %.2f) a(%.2f %.2f %.2f) e(%.2f %.2f %.2f) s(%.2f %.2f %.2f) specular %d vs %08x ps %08x\n",
		(int)type, (unsigned)key.fvf, key.lighting, (unsigned)rs[D3DRS_AMBIENT], key.colorVertex, key.diffuseSource,
		key.ambientSource, key.emissiveSource, m.Diffuse.r, m.Diffuse.g, m.Diffuse.b, m.Diffuse.a, m.Ambient.r,
		m.Ambient.g, m.Ambient.b, m.Emissive.r, m.Emissive.g, m.Emissive.b, m.Specular.r, m.Specular.g, m.Specular.b,
		key.specularEnable, key.vertexShader, key.pixelShader);
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
	const VertexShaderObject* vso = nullptr;
	if (m_state.vertexShader & 1)
	{
		auto it = m_vertexShaders.find(m_state.vertexShader);
		if (it != m_vertexShaders.end())
			vso = &it->second;
	}
	const bool vsMode = vso != nullptr && vso->hash != 0;
	const PixelShaderObject* pso = nullptr;
	if (m_state.pixelShader != 0)
	{
		auto it = m_pixelShaders.find(m_state.pixelShader);
		if (it != m_pixelShaders.end())
			pso = &it->second;
	}
	DWORD fvf = vsMode ? 0 : currentFvf(m_state, m_vertexShaders);
	if (!vsMode && (fvf == 0 || (fvf & D3DFVF_POSITION_MASK) == 0))
		return;
	const DWORD* rs = m_state.renderStates;
	PipelineKey ctx;
	memset(&ctx, 0, sizeof(ctx));
	{
		ShaderKey& key = ctx.shader;
		key.fvf = fvf & ~D3DFVF_LASTBETA_UBYTE4;
		bool rhw = (fvf & D3DFVF_POSITION_MASK) == D3DFVF_XYZRHW;
		key.lighting = (!rhw && !vsMode && rs[D3DRS_LIGHTING]) ? 1 : 0;
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
		key.clipPlaneMask = (rhw || vsMode) ? 0 : (uint8_t)(rs[D3DRS_CLIPPLANEENABLE] & 0x3F);
		key.pointList = type == D3DPT_POINTLIST ? 1 : 0;
		key.pointSprite = (key.pointList && rs[D3DRS_POINTSPRITEENABLE]) ? 1 : 0;
		key.pointScale = (key.pointList && rs[D3DRS_POINTSCALEENABLE]) ? 1 : 0;
		unsigned numStages = 0;
		auto stageTexture = [&](unsigned i, StageKey& st) {
			const DWORD* ts = m_state.stageStates[i];
			st.texCoordIndex = (uint8_t)(ts[D3DTSS_TEXCOORDINDEX] & 0xFFFF);
			st.texGen = (uint8_t)((ts[D3DTSS_TEXCOORDINDEX] >> 16) & 0xF);
			DWORD ttff = ts[D3DTSS_TEXTURETRANSFORMFLAGS];
			st.transformCount = (uint8_t)(ttff & 0xFF);
			st.projected = (ttff & D3DTTFF_PROJECTED) ? 1 : 0;
			IDirect3DBaseTexture8* tex = m_state.textures[i];
			st.textureType = tex == nullptr ? 0 : (tex->GetType() == D3DRTYPE_CUBETEXTURE ? 2 : 1);
		};
		if (pso)
		{
			// The pixel shader replaces the stage operations; the stages still provide textures,
			// samplers and texture coordinates.
			numStages = pso->textureCount;
			for (unsigned i = 0; i < numStages; ++i)
				stageTexture(i, key.stages[i]);
			key.pixelShader = pso->hash;
		}
		else
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
		if (vsMode)
		{
			// The vertex shader writes texture coordinate set i for stage i.
			for (unsigned i = 0; i < numStages; ++i)
			{
				key.stages[i].texCoordIndex = (uint8_t)i;
				key.stages[i].texGen = 0;
			}
			key.vertexShader = vso->hash;
			memcpy(key.vsInputType, vso->inputType, sizeof(key.vsInputType));
		}

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
		blend.sampleCount = (uint8_t)renderTargetSamples();

		// Soft particles: translucent sprites the game draws while it flushes its sorted polygons fade
		// out where they meet the ground, units or buildings, instead of cutting into them.
		if (rs[RS_SOFT_PARTICLES] != 0 && blend.enable && rs[D3DRS_ZENABLE] && !rs[D3DRS_ZWRITEENABLE] && !vsMode && !pso
			&& m_state.transforms[D3DTS_PROJECTION]._34 != 0.0f && m_depthStencil == m_depthBuffer && m_depthBuffer != nullptr)
		{
			id<MTLTexture> depth = activeDepthTexture();
			bool mainDepth = depth != nil && (depth == m_msaaDepth || depth == m_depthBuffer->m_storage->texture);
			uint8_t mode = 0;
			if (blend.dst == MTLBlendFactorOne)
				mode = 2;
			else if (blend.src == MTLBlendFactorSourceAlpha && blend.dst == MTLBlendFactorOneMinusSourceAlpha)
				mode = 1;
			else if ((blend.src == MTLBlendFactorZero && blend.dst == MTLBlendFactorSourceColor)
				|| (blend.src == MTLBlendFactorDestinationColor && blend.dst == MTLBlendFactorZero))
				mode = 3;
			if (mainDepth && mode != 0 && (m_softDepthValid || captureSoftDepth(depth)))
				key.softParticle = mode;
		}

		ctx.layout.fvf = key.fvf;
		ctx.layout.stride = m_state.streams[0].stride;
		if (vsMode)
		{
			memcpy(ctx.layout.vsInputOffset, vso->inputOffset, sizeof(ctx.layout.vsInputOffset));
			if (ctx.layout.stride == 0)
				ctx.layout.stride = vso->stride;
		}
		else if (ctx.layout.stride == 0)
			ctx.layout.stride = FvfVertexSize(key.fvf);
	}

	if (traceEnabled())
		traceDraw(ctx.shader, type);

	id<MTLRenderPipelineState> pipeline = pipelineFor(ctx);
	if (pipeline == nil)
		return;

	// Encoder state is only sent when it differs from what the encoder already has.
	id<MTLRenderCommandEncoder> enc = renderEncoder();
	EncoderState& es = m_encoderState;
	if (es.pipeline != pipeline)
	{
		[enc setRenderPipelineState:pipeline];
		es.pipeline = pipeline;
	}
	id<MTLDepthStencilState> depthState = depthStencilFor();
	if (es.depthStencil != depthState)
	{
		[enc setDepthStencilState:depthState];
		es.depthStencil = depthState;
	}
	DWORD stencilRef = rs[D3DRS_STENCILREF] & 0xFF;
	if (es.stencilRef != stencilRef)
	{
		[enc setStencilReferenceValue:stencilRef];
		es.stencilRef = stencilRef;
	}

	// Rasterizer state
	const D3DVIEWPORT8& vp = m_state.viewport;
	unsigned rtW = m_renderTarget->width(), rtH = m_renderTarget->height();
	NSUInteger sx = std::min<NSUInteger>(vp.X, rtW), sy = std::min<NSUInteger>(vp.Y, rtH);
	NSUInteger sw = std::min<NSUInteger>(vp.Width, rtW - sx), sh = std::min<NSUInteger>(vp.Height, rtH - sy);
	if (sw == 0 || sh == 0)
		return;
	MTLViewport viewport = { (double)vp.X, (double)vp.Y, (double)std::max<DWORD>(vp.Width, 1), (double)std::max<DWORD>(vp.Height, 1), (double)vp.MinZ, (double)vp.MaxZ };
	if (memcmp(&es.viewport, &viewport, sizeof(viewport)) != 0)
	{
		[enc setViewport:viewport];
		es.viewport = viewport;
	}
	MTLScissorRect scissor = { sx, sy, sw, sh };
	if (memcmp(&es.scissor, &scissor, sizeof(scissor)) != 0)
	{
		[enc setScissorRect:scissor];
		es.scissor = scissor;
	}

	MTLCullMode cull = MTLCullModeBack;
	MTLWinding winding = (MTLWinding)es.winding;
	switch (rs[D3DRS_CULLMODE])
	{
	case D3DCULL_NONE: cull = MTLCullModeNone; break;
	case D3DCULL_CW: winding = MTLWindingCounterClockwise; break;
	default: winding = MTLWindingClockwise; break;
	}
	if (es.winding != (int)winding)
	{
		[enc setFrontFacingWinding:winding];
		es.winding = (int)winding;
	}
	if (es.cullMode != (int)cull)
	{
		[enc setCullMode:cull];
		es.cullMode = (int)cull;
	}
	MTLTriangleFillMode fill = rs[D3DRS_FILLMODE] == D3DFILL_WIREFRAME ? MTLTriangleFillModeLines : MTLTriangleFillModeFill;
	if (es.fillMode != (int)fill)
	{
		[enc setTriangleFillMode:fill];
		es.fillMode = (int)fill;
	}
	float zbias = (float)rs[D3DRS_ZBIAS];
	if (!(es.depthBias == zbias))
	{
		[enc setDepthBias:-zbias * 16.0f slopeScale:-zbias * 0.25f clamp:0.0f];
		es.depthBias = zbias;
	}

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
	for (unsigned i = 0; i < ctx.shader.numStages; ++i)
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
	if (ctx.shader.clipPlaneMask)
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
	if (ctx.shader.lighting)
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
	if (!es.vertexUniformsValid || memcmp(&es.vertexUniforms, &vu, sizeof(vu)) != 0)
	{
		[enc setVertexBytes:&vu length:sizeof(vu) atIndex:BUFFER_UNIFORMS];
		es.vertexUniforms = vu;
		es.vertexUniformsValid = true;
	}

	FragmentUniforms fu;
	memset(&fu, 0, sizeof(fu));
	colorToFloat4(rs[D3DRS_TEXTUREFACTOR], fu.textureFactor);
	colorToFloat4(rs[D3DRS_FOGCOLOR], fu.fogColor);
	memcpy(fu.fogParams, vu.fogParams, sizeof(fu.fogParams));
	fu.alphaRef[0] = (rs[D3DRS_ALPHAREF] & 0xFF) / 255.0f;
	if (ctx.shader.softParticle)
	{
		const D3DMATRIX& proj = m_state.transforms[D3DTS_PROJECTION];
		fu.softParams[0] = proj._33;
		fu.softParams[1] = proj._43;
		fu.softParams[2] = 1.0f / std::max(bitsFloat(rs[RS_SOFT_PARTICLES]), 0.001f);
		fu.softParams[3] = proj._34;
	}
	for (unsigned i = 0; i < ctx.shader.numStages; ++i)
	{
		const DWORD* ts = m_state.stageStates[i];
		fu.bumpEnv[i][0] = bitsFloat(ts[D3DTSS_BUMPENVMAT00]);
		fu.bumpEnv[i][1] = bitsFloat(ts[D3DTSS_BUMPENVMAT01]);
		fu.bumpEnv[i][2] = bitsFloat(ts[D3DTSS_BUMPENVMAT10]);
		fu.bumpEnv[i][3] = bitsFloat(ts[D3DTSS_BUMPENVMAT11]);
		fu.bumpLum[i][0] = bitsFloat(ts[D3DTSS_BUMPENVLSCALE]);
		fu.bumpLum[i][1] = bitsFloat(ts[D3DTSS_BUMPENVLOFFSET]);
	}
	if (!es.fragmentUniformsValid || memcmp(&es.fragmentUniforms, &fu, sizeof(fu)) != 0)
	{
		[enc setFragmentBytes:&fu length:sizeof(fu) atIndex:BUFFER_UNIFORMS];
		es.fragmentUniforms = fu;
		es.fragmentUniformsValid = true;
	}
	if (vsMode && es.vsConstantsVersion != m_vsConstantsVersion)
	{
		[enc setVertexBytes:m_state.vsConstants length:sizeof(m_state.vsConstants) atIndex:BUFFER_SHADER_CONSTANTS];
		es.vsConstantsVersion = m_vsConstantsVersion;
	}
	if (pso && es.psConstantsVersion != m_psConstantsVersion)
	{
		[enc setFragmentBytes:m_state.psConstants length:sizeof(m_state.psConstants) atIndex:BUFFER_SHADER_CONSTANTS];
		es.psConstantsVersion = m_psConstantsVersion;
	}

	// Textures
	for (unsigned i = 0; i < ctx.shader.numStages; ++i)
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
			tex = ctx.shader.stages[i].textureType == 2 ? m_whiteCube : m_whiteTexture;
		if (es.textures[i] != tex)
		{
			[enc setFragmentTexture:tex atIndex:i];
			es.textures[i] = tex;
		}
		id<MTLSamplerState> sampler = samplerFor(i);
		if (es.samplers[i] != sampler)
		{
			[enc setFragmentSamplerState:sampler atIndex:i];
			es.samplers[i] = sampler;
		}
	}
	if (ctx.shader.softParticle && es.softDepth != m_softDepth)
	{
		[enc setFragmentTexture:m_softDepth atIndex:TEXTURE_SOFT_DEPTH];
		es.softDepth = m_softDepth;
	}
	ok = true;
}

//-----------------------------------------------------------------------------
// Draw calls
//-----------------------------------------------------------------------------
void Device::bindVertexBuffer(id<MTLBuffer> buffer, NSUInteger offset)
{
	EncoderState& es = m_encoderState;
	if (es.vertexBuffer == buffer)
	{
		if (es.vertexOffset != offset)
			[m_encoder setVertexBufferOffset:offset atIndex:BUFFER_STREAM0];
	}
	else
		[m_encoder setVertexBuffer:buffer offset:offset atIndex:BUFFER_STREAM0];
	es.vertexBuffer = buffer;
	es.vertexOffset = offset;
}

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
	bindVertexBuffer(vb->m_storage.buffer, 0);
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
	bindVertexBuffer(vb->m_storage.buffer, 0);
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
	bindVertexBuffer(vtx.buffer, vtx.offset);
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
	bindVertexBuffer(vtx.buffer, vtx.offset);
	[enc drawIndexedPrimitives:PrimitiveType == D3DPT_TRIANGLEFAN ? MTLPrimitiveTypeTriangle : primitiveType(PrimitiveType) indexCount:count indexType:indexType
				   indexBuffer:idx.buffer indexBufferOffset:idx.offset];
	return D3D_OK;
}

} // namespace d3d8metal

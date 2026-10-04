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

#include "formats.h"

#include <string.h>

namespace d3d8metal
{

bool IsCompressedFormat(D3DFORMAT format)
{
	switch (format)
	{
	case D3DFMT_DXT1:
	case D3DFMT_DXT2:
	case D3DFMT_DXT3:
	case D3DFMT_DXT4:
	case D3DFMT_DXT5:
		return true;
	default:
		return false;
	}
}

bool IsDepthFormat(D3DFORMAT format)
{
	switch (format)
	{
	case D3DFMT_D16_LOCKABLE:
	case D3DFMT_D32:
	case D3DFMT_D15S1:
	case D3DFMT_D24S8:
	case D3DFMT_D16:
	case D3DFMT_D24X8:
	case D3DFMT_D24X4S4:
		return true;
	default:
		return false;
	}
}

bool HasAlpha(D3DFORMAT format)
{
	switch (format)
	{
	case D3DFMT_A8R8G8B8:
	case D3DFMT_A1R5G5B5:
	case D3DFMT_A4R4G4B4:
	case D3DFMT_A8:
	case D3DFMT_A8R3G3B2:
	case D3DFMT_A8L8:
	case D3DFMT_A4L4:
	case D3DFMT_A8P8:
	case D3DFMT_DXT1:
	case D3DFMT_DXT2:
	case D3DFMT_DXT3:
	case D3DFMT_DXT4:
	case D3DFMT_DXT5:
		return true;
	default:
		return false;
	}
}

unsigned BytesPerPixel(D3DFORMAT format)
{
	switch (format)
	{
	case D3DFMT_A8R8G8B8:
	case D3DFMT_X8R8G8B8:
	case D3DFMT_D32:
	case D3DFMT_D24S8:
	case D3DFMT_D24X8:
	case D3DFMT_D24X4S4:
	case D3DFMT_X8L8V8U8:
	case D3DFMT_Q8W8V8U8:
	case D3DFMT_V16U16:
	case D3DFMT_W11V11U10:
		return 4;
	case D3DFMT_R8G8B8:
		return 3;
	case D3DFMT_R5G6B5:
	case D3DFMT_X1R5G5B5:
	case D3DFMT_A1R5G5B5:
	case D3DFMT_A4R4G4B4:
	case D3DFMT_X4R4G4B4:
	case D3DFMT_A8R3G3B2:
	case D3DFMT_A8L8:
	case D3DFMT_A8P8:
	case D3DFMT_V8U8:
	case D3DFMT_L6V5U5:
	case D3DFMT_D16:
	case D3DFMT_D16_LOCKABLE:
	case D3DFMT_D15S1:
	case D3DFMT_INDEX16:
		return 2;
	case D3DFMT_A8:
	case D3DFMT_L8:
	case D3DFMT_A4L4:
	case D3DFMT_R3G3B2:
	case D3DFMT_P8:
		return 1;
	default:
		return 4;
	}
}

unsigned RowPitch(D3DFORMAT format, unsigned width)
{
	if (IsCompressedFormat(format))
	{
		unsigned blocks = (width + 3) / 4;
		return blocks * (format == D3DFMT_DXT1 ? 8 : 16);
	}
	return width * BytesPerPixel(format);
}

unsigned RowCount(D3DFORMAT format, unsigned height)
{
	return IsCompressedFormat(format) ? (height + 3) / 4 : height;
}

unsigned ImageSize(D3DFORMAT format, unsigned width, unsigned height)
{
	return RowPitch(format, width) * RowCount(format, height);
}

GpuFormat GpuFormatFor(D3DFORMAT format, bool allowNative16)
{
	switch (format)
	{
	case D3DFMT_R5G6B5:
		return allowNative16 ? GpuFormat::B5G6R5 : GpuFormat::BGRA8;
	case D3DFMT_A1R5G5B5:
	case D3DFMT_X1R5G5B5:
		return allowNative16 ? GpuFormat::BGR5A1 : GpuFormat::BGRA8;
	case D3DFMT_A4R4G4B4:
	case D3DFMT_X4R4G4B4:
		return allowNative16 ? GpuFormat::ABGR4 : GpuFormat::BGRA8;
	case D3DFMT_DXT1:
		return GpuFormat::BC1;
	case D3DFMT_DXT2:
	case D3DFMT_DXT3:
		return GpuFormat::BC2;
	case D3DFMT_DXT4:
	case D3DFMT_DXT5:
		return GpuFormat::BC3;
	default:
		if (IsDepthFormat(format))
			return GpuFormat::Depth32Stencil8;
		return GpuFormat::BGRA8;
	}
}

namespace
{
inline uint8_t expand5(unsigned v) { return (uint8_t)((v << 3) | (v >> 2)); }
inline uint8_t expand6(unsigned v) { return (uint8_t)((v << 2) | (v >> 4)); }
inline uint8_t expand4(unsigned v) { return (uint8_t)((v << 4) | v); }
inline uint8_t expand3(unsigned v) { return (uint8_t)((v << 5) | (v << 2) | (v >> 1)); }
inline uint8_t expand2(unsigned v) { return (uint8_t)((v << 6) | (v << 4) | (v << 2) | v); }
inline uint16_t rd16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
inline void wr16(uint8_t* p, unsigned v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); }
} // namespace

void ConvertToBGRA8(D3DFORMAT format, const uint8_t* src, unsigned srcPitch, uint8_t* dst, unsigned dstPitch, unsigned width, unsigned height)
{
	for (unsigned y = 0; y < height; ++y)
	{
		const uint8_t* s = src + y * srcPitch;
		uint8_t* d = dst + y * dstPitch;
		for (unsigned x = 0; x < width; ++x, d += 4)
		{
			uint8_t b = 0, g = 0, r = 0, a = 255;
			switch (format)
			{
			case D3DFMT_A8R8G8B8:
				b = s[0]; g = s[1]; r = s[2]; a = s[3];
				s += 4;
				break;
			case D3DFMT_X8R8G8B8:
				b = s[0]; g = s[1]; r = s[2];
				s += 4;
				break;
			case D3DFMT_R8G8B8:
				b = s[0]; g = s[1]; r = s[2];
				s += 3;
				break;
			case D3DFMT_R5G6B5:
			{
				unsigned v = rd16(s);
				r = expand5((v >> 11) & 31); g = expand6((v >> 5) & 63); b = expand5(v & 31);
				s += 2;
				break;
			}
			case D3DFMT_X1R5G5B5:
			case D3DFMT_A1R5G5B5:
			{
				unsigned v = rd16(s);
				r = expand5((v >> 10) & 31); g = expand5((v >> 5) & 31); b = expand5(v & 31);
				if (format == D3DFMT_A1R5G5B5)
					a = (v & 0x8000) ? 255 : 0;
				s += 2;
				break;
			}
			case D3DFMT_A4R4G4B4:
			case D3DFMT_X4R4G4B4:
			{
				unsigned v = rd16(s);
				r = expand4((v >> 8) & 15); g = expand4((v >> 4) & 15); b = expand4(v & 15);
				if (format == D3DFMT_A4R4G4B4)
					a = expand4((v >> 12) & 15);
				s += 2;
				break;
			}
			case D3DFMT_R3G3B2:
			{
				unsigned v = s[0];
				r = expand3((v >> 5) & 7); g = expand3((v >> 2) & 7); b = expand2(v & 3);
				s += 1;
				break;
			}
			case D3DFMT_A8R3G3B2:
			{
				unsigned v = rd16(s);
				r = expand3((v >> 5) & 7); g = expand3((v >> 2) & 7); b = expand2(v & 3); a = (uint8_t)(v >> 8);
				s += 2;
				break;
			}
			case D3DFMT_A8:
				r = g = b = 0; a = s[0];
				s += 1;
				break;
			case D3DFMT_L8:
				r = g = b = s[0];
				s += 1;
				break;
			case D3DFMT_A8L8:
				r = g = b = s[0]; a = s[1];
				s += 2;
				break;
			case D3DFMT_A4L4:
				r = g = b = expand4(s[0] & 15); a = expand4(s[0] >> 4);
				s += 1;
				break;
			case D3DFMT_V8U8:
				// Signed bump offsets, biased into unsigned storage.
				r = (uint8_t)(s[0] + 128); g = (uint8_t)(s[1] + 128); b = 255;
				s += 2;
				break;
			case D3DFMT_X8L8V8U8:
				r = (uint8_t)(s[0] + 128); g = (uint8_t)(s[1] + 128); b = s[2];
				s += 4;
				break;
			default:
				// Unknown formats are passed through as 32 bit.
				b = s[0]; g = s[1]; r = s[2]; a = s[3];
				s += 4;
				break;
			}
			d[0] = b;
			d[1] = g;
			d[2] = r;
			d[3] = a;
		}
	}
}

void ConvertFromBGRA8(D3DFORMAT format, const uint8_t* src, unsigned srcPitch, uint8_t* dst, unsigned dstPitch, unsigned width, unsigned height)
{
	for (unsigned y = 0; y < height; ++y)
	{
		const uint8_t* s = src + y * srcPitch;
		uint8_t* d = dst + y * dstPitch;
		for (unsigned x = 0; x < width; ++x, s += 4)
		{
			unsigned b = s[0], g = s[1], r = s[2], a = s[3];
			switch (format)
			{
			case D3DFMT_A8R8G8B8:
			case D3DFMT_X8R8G8B8:
				d[0] = (uint8_t)b; d[1] = (uint8_t)g; d[2] = (uint8_t)r; d[3] = format == D3DFMT_X8R8G8B8 ? 255 : (uint8_t)a;
				d += 4;
				break;
			case D3DFMT_R8G8B8:
				d[0] = (uint8_t)b; d[1] = (uint8_t)g; d[2] = (uint8_t)r;
				d += 3;
				break;
			case D3DFMT_R5G6B5:
				wr16(d, ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3));
				d += 2;
				break;
			case D3DFMT_X1R5G5B5:
			case D3DFMT_A1R5G5B5:
				wr16(d, (a >= 128 || format == D3DFMT_X1R5G5B5 ? 0x8000 : 0) | ((r >> 3) << 10) | ((g >> 3) << 5) | (b >> 3));
				d += 2;
				break;
			case D3DFMT_A4R4G4B4:
			case D3DFMT_X4R4G4B4:
				wr16(d, ((format == D3DFMT_X4R4G4B4 ? 15 : (a >> 4)) << 12) | ((r >> 4) << 8) | ((g >> 4) << 4) | (b >> 4));
				d += 2;
				break;
			case D3DFMT_R3G3B2:
				d[0] = (uint8_t)(((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6));
				d += 1;
				break;
			case D3DFMT_A8R3G3B2:
				wr16(d, (a << 8) | ((r >> 5) << 5) | ((g >> 5) << 2) | (b >> 6));
				d += 2;
				break;
			case D3DFMT_A8:
				d[0] = (uint8_t)a;
				d += 1;
				break;
			case D3DFMT_L8:
				d[0] = (uint8_t)((r * 77 + g * 150 + b * 29) >> 8);
				d += 1;
				break;
			case D3DFMT_A8L8:
				d[0] = (uint8_t)((r * 77 + g * 150 + b * 29) >> 8); d[1] = (uint8_t)a;
				d += 2;
				break;
			case D3DFMT_A4L4:
				d[0] = (uint8_t)(((a >> 4) << 4) | (((r * 77 + g * 150 + b * 29) >> 8) >> 4));
				d += 1;
				break;
			default:
				d[0] = (uint8_t)b; d[1] = (uint8_t)g; d[2] = (uint8_t)r; d[3] = (uint8_t)a;
				d += 4;
				break;
			}
		}
	}
}

namespace
{
void decodeColorBlock(const uint8_t* block, uint8_t out[16][4], bool dxt1)
{
	unsigned c0 = rd16(block);
	unsigned c1 = rd16(block + 2);
	uint8_t colors[4][4];
	colors[0][0] = expand5(c0 & 31); colors[0][1] = expand6((c0 >> 5) & 63); colors[0][2] = expand5(c0 >> 11); colors[0][3] = 255;
	colors[1][0] = expand5(c1 & 31); colors[1][1] = expand6((c1 >> 5) & 63); colors[1][2] = expand5(c1 >> 11); colors[1][3] = 255;
	if (!dxt1 || c0 > c1)
	{
		for (int i = 0; i < 3; ++i)
		{
			colors[2][i] = (uint8_t)((2 * colors[0][i] + colors[1][i]) / 3);
			colors[3][i] = (uint8_t)((colors[0][i] + 2 * colors[1][i]) / 3);
		}
		colors[2][3] = colors[3][3] = 255;
	}
	else
	{
		for (int i = 0; i < 3; ++i)
		{
			colors[2][i] = (uint8_t)((colors[0][i] + colors[1][i]) / 2);
			colors[3][i] = 0;
		}
		colors[2][3] = 255;
		colors[3][3] = 0;
	}
	uint32_t bits = (uint32_t)block[4] | ((uint32_t)block[5] << 8) | ((uint32_t)block[6] << 16) | ((uint32_t)block[7] << 24);
	for (int i = 0; i < 16; ++i)
		memcpy(out[i], colors[(bits >> (2 * i)) & 3], 4);
}
} // namespace

void DecodeDXT(D3DFORMAT format, const uint8_t* src, unsigned srcPitch, uint8_t* dst, unsigned dstPitch, unsigned width, unsigned height)
{
	unsigned blockBytes = format == D3DFMT_DXT1 ? 8 : 16;
	for (unsigned by = 0; by < (height + 3) / 4; ++by)
	{
		const uint8_t* row = src + by * srcPitch;
		for (unsigned bx = 0; bx < (width + 3) / 4; ++bx)
		{
			const uint8_t* block = row + bx * blockBytes;
			uint8_t pixels[16][4];
			if (format == D3DFMT_DXT1)
				decodeColorBlock(block, pixels, true);
			else
			{
				decodeColorBlock(block + 8, pixels, false);
				if (format == D3DFMT_DXT2 || format == D3DFMT_DXT3)
				{
					for (int i = 0; i < 16; ++i)
					{
						unsigned nibble = (block[i / 2] >> ((i & 1) * 4)) & 15;
						pixels[i][3] = expand4(nibble);
					}
				}
				else
				{
					uint8_t a[8];
					a[0] = block[0];
					a[1] = block[1];
					if (a[0] > a[1])
					{
						for (int i = 1; i < 7; ++i)
							a[i + 1] = (uint8_t)(((7 - i) * a[0] + i * a[1]) / 7);
					}
					else
					{
						for (int i = 1; i < 5; ++i)
							a[i + 1] = (uint8_t)(((5 - i) * a[0] + i * a[1]) / 5);
						a[6] = 0;
						a[7] = 255;
					}
					uint64_t bits = 0;
					for (int i = 0; i < 6; ++i)
						bits |= (uint64_t)block[2 + i] << (8 * i);
					for (int i = 0; i < 16; ++i)
						pixels[i][3] = a[(bits >> (3 * i)) & 7];
				}
			}
			for (int py = 0; py < 4; ++py)
			{
				unsigned y = by * 4 + py;
				if (y >= height)
					break;
				for (int px = 0; px < 4; ++px)
				{
					unsigned x = bx * 4 + px;
					if (x >= width)
						break;
					memcpy(dst + y * dstPitch + x * 4, pixels[py * 4 + px], 4);
				}
			}
		}
	}
}

} // namespace d3d8metal

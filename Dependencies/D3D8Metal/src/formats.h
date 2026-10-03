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

// Direct3D 8 surface format helpers: sizes and CPU conversion to/from BGRA8.

#pragma once

#include <d3d8.h>
#include <stdint.h>

namespace d3d8metal
{

enum class GpuFormat
{
	BGRA8,
	BC1,
	BC2,
	BC3,
	Depth32Stencil8,
	Unsupported,
};

bool IsCompressedFormat(D3DFORMAT format);
bool IsDepthFormat(D3DFORMAT format);
bool HasAlpha(D3DFORMAT format);

// Bytes per pixel for uncompressed formats, 0 for compressed ones.
unsigned BytesPerPixel(D3DFORMAT format);

// Row pitch in bytes. For block compressed formats this is the pitch of one row of 4x4 blocks.
unsigned RowPitch(D3DFORMAT format, unsigned width);

// Number of rows in memory (block rows for compressed formats).
unsigned RowCount(D3DFORMAT format, unsigned height);

// Size in bytes of a width x height image.
unsigned ImageSize(D3DFORMAT format, unsigned width, unsigned height);

GpuFormat GpuFormatFor(D3DFORMAT format);

// Converts a rectangle of pixels between the D3D format and BGRA8 (B,G,R,A bytes).
// Coordinates are in pixels; for compressed formats use the Decode function instead.
void ConvertToBGRA8(D3DFORMAT format, const uint8_t* src, unsigned srcPitch, uint8_t* dst, unsigned dstPitch, unsigned width, unsigned height);
void ConvertFromBGRA8(D3DFORMAT format, const uint8_t* src, unsigned srcPitch, uint8_t* dst, unsigned dstPitch, unsigned width, unsigned height);

// Decodes a DXT1..5 image into BGRA8.
void DecodeDXT(D3DFORMAT format, const uint8_t* src, unsigned srcPitch, uint8_t* dst, unsigned dstPitch, unsigned width, unsigned height);

} // namespace d3d8metal

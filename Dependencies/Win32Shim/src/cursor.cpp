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

// LoadCursorFromFile: Windows .cur and animated .ani cursors decoded into SDL cursors.

#define NOMINMAX
#include <windows.h>
#include "win32shim_internal.h"

#include <SDL3/SDL.h>

#include <vector>

namespace
{

struct Image
{
	int width = 0;
	int height = 0;
	int hotX = 0;
	int hotY = 0;
	std::vector<uint32_t> argb;
};

uint16_t rd16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
uint32_t rd32(const uint8_t* p) { return (uint32_t)(p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24)); }

// Decodes the first image of an .ico/.cur file held in memory.
bool decodeIconFile(const uint8_t* data, size_t size, Image& out)
{
	if (size < 6 + 16)
		return false;
	uint16_t type = rd16(data + 2);
	uint16_t count = rd16(data + 4);
	if (count == 0 || (type != 1 && type != 2))
		return false;

	const uint8_t* entry = data + 6;
	out.hotX = type == 2 ? rd16(entry + 4) : 0;
	out.hotY = type == 2 ? rd16(entry + 6) : 0;
	uint32_t imageSize = rd32(entry + 8);
	uint32_t imageOffset = rd32(entry + 12);
	if (imageOffset + 40 > size || imageOffset + imageSize > size)
		return false;

	const uint8_t* dib = data + imageOffset;
	uint32_t headerSize = rd32(dib);
	int width = (int)rd32(dib + 4);
	int height = (int)rd32(dib + 8) / 2; // XOR + AND mask
	int bpp = rd16(dib + 14);
	uint32_t colorsUsed = rd32(dib + 32);
	if (width <= 0 || height <= 0 || width > 256 || height > 256)
		return false;

	const uint8_t* palette = dib + headerSize;
	int paletteCount = 0;
	if (bpp <= 8)
		paletteCount = colorsUsed ? (int)colorsUsed : (1 << bpp);
	const uint8_t* xorBits = palette + paletteCount * 4;
	int xorStride = ((width * bpp + 31) / 32) * 4;
	const uint8_t* andBits = xorBits + xorStride * height;
	int andStride = ((width + 31) / 32) * 4;
	if (andBits + andStride * height > data + size)
		return false;

	out.width = width;
	out.height = height;
	out.argb.assign((size_t)width * height, 0);
	bool hasAlpha = false;
	for (int y = 0; y < height; ++y)
	{
		// DIB rows are stored bottom-up.
		const uint8_t* row = xorBits + (height - 1 - y) * xorStride;
		const uint8_t* maskRow = andBits + (height - 1 - y) * andStride;
		for (int x = 0; x < width; ++x)
		{
			uint32_t pixel = 0;
			switch (bpp)
			{
			case 32:
				pixel = rd32(row + x * 4);
				if (pixel >> 24)
					hasAlpha = true;
				break;
			case 24:
				pixel = 0xFF000000u | row[x * 3] | (row[x * 3 + 1] << 8) | (row[x * 3 + 2] << 16);
				break;
			case 8:
			case 4:
			case 1:
			{
				int bitIndex = x * bpp;
				int index = (row[bitIndex / 8] >> (8 - bpp - (bitIndex % 8))) & ((1 << bpp) - 1);
				if (index < paletteCount)
				{
					const uint8_t* c = palette + index * 4;
					pixel = 0xFF000000u | c[0] | (c[1] << 8) | (c[2] << 16);
				}
				break;
			}
			default:
				return false;
			}
			bool transparent = (maskRow[x / 8] >> (7 - (x % 8))) & 1;
			if (bpp != 32 || !hasAlpha)
				pixel = transparent ? 0 : (pixel | 0xFF000000u);
			out.argb[(size_t)y * width + x] = pixel;
		}
	}
	// 32 bit images without any alpha rely on the AND mask only.
	if (bpp == 32 && !hasAlpha)
	{
		for (int y = 0; y < height; ++y)
		{
			const uint8_t* maskRow = andBits + (height - 1 - y) * andStride;
			for (int x = 0; x < width; ++x)
			{
				bool transparent = (maskRow[x / 8] >> (7 - (x % 8))) & 1;
				uint32_t& p = out.argb[(size_t)y * width + x];
				p = transparent ? 0 : (p | 0xFF000000u);
			}
		}
	}
	return true;
}

SDL_Surface* toSurface(Image& img)
{
	return SDL_CreateSurfaceFrom(img.width, img.height, SDL_PIXELFORMAT_ARGB8888, img.argb.data(), img.width * 4);
}

struct CursorObject
{
	SDL_Cursor* cursor = nullptr;
};

} // namespace

HCURSOR LoadCursorFromFile(LPCSTR fileName)
{
	std::string path = Win32Shim_TranslatePath(fileName);
	FILE* f = fopen(path.c_str(), "rb");
	if (f == nullptr)
		return nullptr;
	std::vector<uint8_t> data;
	fseek(f, 0, SEEK_END);
	long size = ftell(f);
	fseek(f, 0, SEEK_SET);
	if (size > 0)
	{
		data.resize((size_t)size);
		fread(data.data(), 1, (size_t)size, f);
	}
	fclose(f);
	if (data.size() < 12)
		return nullptr;

	std::vector<Image> frames;
	std::vector<uint32_t> rates;
	std::vector<uint32_t> sequence;
	uint32_t defaultRate = 6;

	if (memcmp(data.data(), "RIFF", 4) == 0 && memcmp(data.data() + 8, "ACON", 4) == 0)
	{
		size_t pos = 12;
		while (pos + 8 <= data.size())
		{
			const uint8_t* chunk = data.data() + pos;
			uint32_t chunkSize = rd32(chunk + 4);
			const uint8_t* body = chunk + 8;
			if (pos + 8 + chunkSize > data.size())
				break;
			if (memcmp(chunk, "anih", 4) == 0 && chunkSize >= 36)
				defaultRate = rd32(body + 28);
			else if (memcmp(chunk, "rate", 4) == 0)
			{
				for (uint32_t i = 0; i + 4 <= chunkSize; i += 4)
					rates.push_back(rd32(body + i));
			}
			else if (memcmp(chunk, "seq ", 4) == 0)
			{
				for (uint32_t i = 0; i + 4 <= chunkSize; i += 4)
					sequence.push_back(rd32(body + i));
			}
			else if (memcmp(chunk, "LIST", 4) == 0 && chunkSize >= 4 && memcmp(body, "fram", 4) == 0)
			{
				size_t sub = 4;
				while (sub + 8 <= chunkSize)
				{
					const uint8_t* icon = body + sub;
					uint32_t iconSize = rd32(icon + 4);
					if (memcmp(icon, "icon", 4) == 0 && sub + 8 + iconSize <= chunkSize)
					{
						Image img;
						if (decodeIconFile(icon + 8, iconSize, img))
							frames.push_back(std::move(img));
					}
					sub += 8 + iconSize + (iconSize & 1);
				}
			}
			pos += 8 + chunkSize + (chunkSize & 1);
		}
	}
	else
	{
		Image img;
		if (decodeIconFile(data.data(), data.size(), img))
			frames.push_back(std::move(img));
	}

	if (frames.empty())
		return nullptr;

	if (sequence.empty())
	{
		for (size_t i = 0; i < frames.size(); ++i)
			sequence.push_back((uint32_t)i);
	}

	std::vector<SDL_Surface*> surfaces;
#if SDL_VERSION_ATLEAST(3, 4, 0)
	std::vector<SDL_CursorFrameInfo> info;
	for (size_t step = 0; step < sequence.size(); ++step)
	{
		uint32_t index = sequence[step] < frames.size() ? sequence[step] : 0;
		SDL_Surface* s = toSurface(frames[index]);
		if (s == nullptr)
			continue;
		surfaces.push_back(s);
		uint32_t jiffies = step < rates.size() ? rates[step] : defaultRate;
		SDL_CursorFrameInfo fi;
		fi.surface = s;
		fi.duration = sequence.size() > 1 ? std::max<uint32_t>(1, jiffies * 1000 / 60) : 0;
		info.push_back(fi);
	}

	SDL_Cursor* cursor = nullptr;
	if (info.size() > 1)
		cursor = SDL_CreateAnimatedCursor(info.data(), (int)info.size(), frames[0].hotX, frames[0].hotY);
#else
	// Animated cursors need SDL 3.4; older versions show the first frame.
	for (size_t step = 0; step < 1 && step < sequence.size(); ++step)
	{
		SDL_Surface* s = toSurface(frames[sequence[step] < frames.size() ? sequence[step] : 0]);
		if (s)
			surfaces.push_back(s);
	}
	SDL_Cursor* cursor = nullptr;
#endif
	if (cursor == nullptr && !surfaces.empty())
		cursor = SDL_CreateColorCursor(surfaces[0], frames[0].hotX, frames[0].hotY);
	for (SDL_Surface* s : surfaces)
		SDL_DestroySurface(s);
	if (cursor == nullptr)
		return nullptr;

	CursorObject* c = new CursorObject();
	c->cursor = cursor;
	return (HCURSOR)c;
}

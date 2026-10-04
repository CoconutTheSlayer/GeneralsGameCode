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

// gdi32 subset: memory DCs, DIB sections and TrueType text rendered with CoreText.
// The game rasterizes its UI font glyphs this way (render2dsentence.cpp).

#define NOMINMAX
#include <windows.h>
#include "win32shim_internal.h"

#include <CoreFoundation/CoreFoundation.h>
#include <CoreGraphics/CoreGraphics.h>
#include <CoreText/CoreText.h>

#include <cmath>
#include <string>
#include <vector>

namespace
{

enum GdiType
{
	GDI_FONT = 1,
	GDI_BITMAP,
	GDI_BRUSH,
	GDI_DC,
};

struct GdiObject
{
	explicit GdiObject(GdiType t) : type(t) {}
	virtual ~GdiObject() {}
	GdiType type;
};

struct Font : GdiObject
{
	Font() : GdiObject(GDI_FONT) {}
	~Font() override
	{
		if (ctFont)
			CFRelease(ctFont);
	}
	CTFontRef ctFont = nullptr;
	float scaleX = 1.0f;
	int ascent = 0;
	int descent = 0;
	int height = 0;
	int internalLeading = 0;
	int aveCharWidth = 0;
	int maxCharWidth = 0;
	int weight = FW_NORMAL;
};

struct Bitmap : GdiObject
{
	Bitmap() : GdiObject(GDI_BITMAP) {}
	~Bitmap() override { free(bits); }
	int width = 0;
	int height = 0;
	int bpp = 0;
	bool topDown = false;
	int stride = 0;
	uint8_t* bits = nullptr;
};

struct Brush : GdiObject
{
	Brush() : GdiObject(GDI_BRUSH) {}
	COLORREF color = 0;
};

struct DC : GdiObject
{
	DC() : GdiObject(GDI_DC) {}
	Font* font = nullptr;
	Bitmap* bitmap = nullptr;
	COLORREF textColor = RGB(0, 0, 0);
	COLORREF bkColor = RGB(255, 255, 255);
	int bkMode = OPAQUE;
};

Font* g_defaultFont = nullptr;

template <typename T>
T* gdiCast(HGDIOBJ obj, GdiType type)
{
	if (obj == nullptr)
		return nullptr;
	GdiObject* g = static_cast<GdiObject*>(obj);
	return g->type == type ? static_cast<T*>(g) : nullptr;
}

DC* toDC(HDC hdc)
{
	return gdiCast<DC>((HGDIOBJ)hdc, GDI_DC);
}

CTFontRef createCTFont(const char* faceName, float size, bool bold, bool italic)
{
	CFStringRef name = CFStringCreateWithCString(nullptr, (faceName && *faceName) ? faceName : "Arial", kCFStringEncodingUTF8);
	CTFontRef font = CTFontCreateWithName(name, size, nullptr);
	CFRelease(name);
	if (font && (bold || italic))
	{
		CTFontSymbolicTraits traits = (bold ? kCTFontBoldTrait : 0) | (italic ? kCTFontItalicTrait : 0);
		CTFontRef styled = CTFontCreateCopyWithSymbolicTraits(font, size, nullptr, traits, traits);
		if (styled)
		{
			CFRelease(font);
			font = styled;
		}
	}
	return font;
}

float advanceOf(CTFontRef font, UniChar ch)
{
	CGGlyph glyph = 0;
	if (!CTFontGetGlyphsForCharacters(font, &ch, &glyph, 1))
		return 0.0f;
	CGSize advance;
	CTFontGetAdvancesForGlyphs(font, kCTFontOrientationHorizontal, &glyph, &advance, 1);
	return (float)advance.width;
}

Font* createFont(int height, int width, int weight, bool italic, const char* faceName)
{
	Font* f = new Font();
	f->weight = weight;
	bool bold = weight >= FW_SEMIBOLD;

	// Negative heights are the em height; positive heights are the cell height.
	float size = height < 0 ? (float)-height : (float)(height ? height : 12);
	CTFontRef font = createCTFont(faceName, size, bold, italic);
	if (height > 0 && font)
	{
		float cell = (float)(CTFontGetAscent(font) + CTFontGetDescent(font));
		if (cell > 0.0f)
		{
			size = size * size / cell;
			CFRelease(font);
			font = createCTFont(faceName, size, bold, italic);
		}
	}
	f->ctFont = font;
	if (font == nullptr)
		return f;

	float naturalAve = advanceOf(font, 'x');
	if (width > 0 && naturalAve > 0.0f)
		f->scaleX = (float)width / naturalAve;

	f->ascent = (int)ceilf((float)CTFontGetAscent(font));
	f->descent = (int)ceilf((float)CTFontGetDescent(font));
	f->height = f->ascent + f->descent;
	f->internalLeading = std::max(0, f->height - (int)lroundf(size));
	f->aveCharWidth = (int)lroundf(naturalAve * f->scaleX);
	f->maxCharWidth = (int)lroundf(advanceOf(font, 'W') * f->scaleX);
	return f;
}

Font* defaultFont()
{
	if (g_defaultFont == nullptr)
		g_defaultFont = createFont(-12, 0, FW_NORMAL, false, "Arial");
	return g_defaultFont;
}

CTLineRef createLine(Font* font, const wchar_t* str, int len)
{
	std::vector<UniChar> utf16;
	utf16.reserve((size_t)len);
	for (int i = 0; i < len; ++i)
	{
		uint32_t c = (uint32_t)str[i];
		if (c >= 0x10000)
		{
			c -= 0x10000;
			utf16.push_back((UniChar)(0xD800 + (c >> 10)));
			utf16.push_back((UniChar)(0xDC00 + (c & 0x3FF)));
		}
		else
			utf16.push_back((UniChar)c);
	}
	CFStringRef text = CFStringCreateWithCharacters(nullptr, utf16.data(), (CFIndex)utf16.size());
	// Draw with the context fill color rather than the default black foreground.
	CFStringRef keys[] = { kCTFontAttributeName, kCTForegroundColorFromContextAttributeName };
	CFTypeRef values[] = { font->ctFont, kCFBooleanTrue };
	CFDictionaryRef attrs = CFDictionaryCreate(nullptr, (const void**)keys, (const void**)values, 2, &kCFTypeDictionaryKeyCallBacks, &kCFTypeDictionaryValueCallBacks);
	CFAttributedStringRef attributed = CFAttributedStringCreate(nullptr, text, attrs);
	CTLineRef line = CTLineCreateWithAttributedString(attributed);
	CFRelease(attributed);
	CFRelease(attrs);
	CFRelease(text);
	return line;
}

void writePixel(Bitmap* bmp, int x, int y, COLORREF color, int coverage, bool blend)
{
	if (x < 0 || y < 0 || x >= bmp->width || y >= bmp->height)
		return;
	int row = bmp->topDown ? y : (bmp->height - 1 - y);
	uint8_t* p = bmp->bits + row * bmp->stride + x * (bmp->bpp / 8);
	uint8_t r = GetRValue(color), g = GetGValue(color), b = GetBValue(color);
	if (blend)
	{
		// DIB pixels are stored as BGR(A).
		p[0] = (uint8_t)((b * coverage + p[0] * (255 - coverage)) / 255);
		p[1] = (uint8_t)((g * coverage + p[1] * (255 - coverage)) / 255);
		p[2] = (uint8_t)((r * coverage + p[2] * (255 - coverage)) / 255);
	}
	else
	{
		p[0] = b;
		p[1] = g;
		p[2] = r;
	}
	if (bmp->bpp == 32)
		p[3] = 0xFF;
}

} // namespace

//-----------------------------------------------------------------------------
// Device contexts
//-----------------------------------------------------------------------------
HDC GetDC(HWND)
{
	DC* dc = new DC();
	dc->font = defaultFont();
	return (HDC)(GdiObject*)dc;
}

int ReleaseDC(HWND, HDC hdc)
{
	delete toDC(hdc);
	return 1;
}

HDC CreateCompatibleDC(HDC)
{
	return GetDC(nullptr);
}

BOOL DeleteDC(HDC hdc)
{
	delete toDC(hdc);
	return TRUE;
}

int SaveDC(HDC)
{
	return 1;
}

BOOL RestoreDC(HDC, int)
{
	return TRUE;
}

BOOL BitBlt(HDC, int, int, int, int, HDC, int, int, DWORD)
{
	// Only used for the loading splash bitmap, which is not shown on macOS.
	return TRUE;
}

HGDIOBJ SelectObject(HDC hdc, HGDIOBJ obj)
{
	DC* dc = toDC(hdc);
	if (dc == nullptr || obj == nullptr)
		return nullptr;
	GdiObject* g = static_cast<GdiObject*>(obj);
	switch (g->type)
	{
	case GDI_FONT:
	{
		Font* old = dc->font;
		dc->font = static_cast<Font*>(g);
		return old;
	}
	case GDI_BITMAP:
	{
		Bitmap* old = dc->bitmap;
		dc->bitmap = static_cast<Bitmap*>(g);
		return old;
	}
	default:
		return nullptr;
	}
}

BOOL DeleteObject(HGDIOBJ obj)
{
	if (obj == nullptr)
		return FALSE;
	GdiObject* g = static_cast<GdiObject*>(obj);
	if (g == g_defaultFont)
		return TRUE;
	delete g;
	return TRUE;
}

HGDIOBJ GetStockObject(int obj)
{
	static Brush black, white;
	black.color = RGB(0, 0, 0);
	white.color = RGB(255, 255, 255);
	return obj == WHITE_BRUSH ? (HGDIOBJ)&white : (HGDIOBJ)&black;
}

int GetDeviceCaps(HDC, int index)
{
	switch (index)
	{
	case LOGPIXELSX:
	case LOGPIXELSY: return 96;
	case BITSPIXEL: return 32;
	case HORZRES: return GetSystemMetrics(SM_CXSCREEN);
	case VERTRES: return GetSystemMetrics(SM_CYSCREEN);
	case VREFRESH: return 60;
	default: return 0;
	}
}

//-----------------------------------------------------------------------------
// Fonts
//-----------------------------------------------------------------------------
HFONT CreateFont(int height, int width, int, int, int weight, DWORD italic, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, DWORD, LPCSTR faceName)
{
	return (HFONT)(GdiObject*)createFont(height, width, weight, italic != 0, faceName);
}

HFONT CreateFontIndirect(const LOGFONT* lf)
{
	return CreateFont(lf->lfHeight, lf->lfWidth, lf->lfEscapement, lf->lfOrientation, lf->lfWeight, lf->lfItalic, lf->lfUnderline, lf->lfStrikeOut,
		lf->lfCharSet, lf->lfOutPrecision, lf->lfClipPrecision, lf->lfQuality, lf->lfPitchAndFamily, lf->lfFaceName);
}

int AddFontResource(LPCSTR fileName)
{
	std::string path = Win32Shim_TranslatePath(fileName);
	CFStringRef str = CFStringCreateWithCString(nullptr, path.c_str(), kCFStringEncodingUTF8);
	CFURLRef url = CFURLCreateWithFileSystemPath(nullptr, str, kCFURLPOSIXPathStyle, false);
	bool ok = CTFontManagerRegisterFontsForURL(url, kCTFontManagerScopeProcess, nullptr);
	CFRelease(url);
	CFRelease(str);
	return ok ? 1 : 0;
}

BOOL RemoveFontResource(LPCSTR fileName)
{
	std::string path = Win32Shim_TranslatePath(fileName);
	CFStringRef str = CFStringCreateWithCString(nullptr, path.c_str(), kCFStringEncodingUTF8);
	CFURLRef url = CFURLCreateWithFileSystemPath(nullptr, str, kCFURLPOSIXPathStyle, false);
	bool ok = CTFontManagerUnregisterFontsForURL(url, kCTFontManagerScopeProcess, nullptr);
	CFRelease(url);
	CFRelease(str);
	return ok;
}

int AddFontResourceEx(LPCSTR fileName, DWORD, PVOID)
{
	return AddFontResource(fileName);
}

BOOL RemoveFontResourceEx(LPCSTR fileName, DWORD, PVOID)
{
	return RemoveFontResource(fileName);
}

BOOL GetTextMetrics(HDC hdc, LPTEXTMETRIC tm)
{
	DC* dc = toDC(hdc);
	Font* f = dc && dc->font ? dc->font : defaultFont();
	memset(tm, 0, sizeof(*tm));
	tm->tmHeight = f->height;
	tm->tmAscent = f->ascent;
	tm->tmDescent = f->descent;
	tm->tmInternalLeading = f->internalLeading;
	tm->tmAveCharWidth = f->aveCharWidth;
	tm->tmMaxCharWidth = f->maxCharWidth;
	tm->tmWeight = f->weight;
	tm->tmOverhang = 0;
	tm->tmDigitizedAspectX = 96;
	tm->tmDigitizedAspectY = 96;
	tm->tmFirstChar = 0x20;
	tm->tmLastChar = 0xFF;
	tm->tmDefaultChar = '?';
	tm->tmBreakChar = ' ';
	tm->tmPitchAndFamily = VARIABLE_PITCH;
	return TRUE;
}

BOOL GetTextMetricsW(HDC hdc, LPTEXTMETRIC tm)
{
	return GetTextMetrics(hdc, tm);
}

BOOL GetTextExtentPoint32W(HDC hdc, LPCWSTR str, int len, LPSIZE size)
{
	DC* dc = toDC(hdc);
	Font* f = dc && dc->font ? dc->font : defaultFont();
	size->cx = 0;
	size->cy = f->height;
	if (f->ctFont == nullptr || len <= 0)
		return TRUE;
	CTLineRef line = createLine(f, str, len);
	double width = CTLineGetTypographicBounds(line, nullptr, nullptr, nullptr);
	CFRelease(line);
	size->cx = (LONG)lround(width * f->scaleX);
	return TRUE;
}

BOOL GetTextExtentPoint32(HDC hdc, LPCSTR str, int len, LPSIZE size)
{
	std::vector<wchar_t> wide((size_t)len + 1);
	for (int i = 0; i < len; ++i)
		wide[i] = (unsigned char)str[i];
	return GetTextExtentPoint32W(hdc, wide.data(), len, size);
}

COLORREF SetTextColor(HDC hdc, COLORREF color)
{
	DC* dc = toDC(hdc);
	if (dc == nullptr)
		return 0;
	COLORREF old = dc->textColor;
	dc->textColor = color;
	return old;
}

COLORREF SetBkColor(HDC hdc, COLORREF color)
{
	DC* dc = toDC(hdc);
	if (dc == nullptr)
		return 0;
	COLORREF old = dc->bkColor;
	dc->bkColor = color;
	return old;
}

int SetBkMode(HDC hdc, int mode)
{
	DC* dc = toDC(hdc);
	if (dc == nullptr)
		return 0;
	int old = dc->bkMode;
	dc->bkMode = mode;
	return old;
}

BOOL ExtTextOutW(HDC hdc, int x, int y, UINT options, const RECT* rect, LPCWSTR str, UINT len, const INT*)
{
	DC* dc = toDC(hdc);
	if (dc == nullptr || dc->bitmap == nullptr)
		return FALSE;
	Bitmap* bmp = dc->bitmap;
	Font* f = dc->font ? dc->font : defaultFont();

	if ((options & ETO_OPAQUE) && rect)
	{
		for (int py = std::max(0, (int)rect->top); py < std::min(bmp->height, (int)rect->bottom); ++py)
		{
			for (int px = std::max(0, (int)rect->left); px < std::min(bmp->width, (int)rect->right); ++px)
				writePixel(bmp, px, py, dc->bkColor, 255, false);
		}
	}
	if (f->ctFont == nullptr || len == 0)
		return TRUE;

	// Rasterize the coverage into an 8 bit gray buffer the size of the bitmap.
	int w = bmp->width;
	int h = bmp->height;
	std::vector<uint8_t> coverage((size_t)w * h, 0);
	CGColorSpaceRef gray = CGColorSpaceCreateDeviceGray();
	CGContextRef ctx = CGBitmapContextCreate(coverage.data(), (size_t)w, (size_t)h, 8, (size_t)w, gray, (CGBitmapInfo)kCGImageAlphaNone);
	CGColorSpaceRelease(gray);
	if (ctx == nullptr)
		return FALSE;
	CGContextSetGrayFillColor(ctx, 1.0, 1.0);
	CGContextSetShouldAntialias(ctx, true);
	CGContextSetShouldSmoothFonts(ctx, false);
	CGContextSetShouldSubpixelPositionFonts(ctx, false);

	// GDI positions text by its top-left cell corner; CG uses the baseline with
	// a bottom-left origin.
	float baseline = (float)(h - (y + f->ascent));
	CGContextTranslateCTM(ctx, (CGFloat)x, baseline);
	CGContextScaleCTM(ctx, f->scaleX, 1.0);
	CGContextSetTextPosition(ctx, 0, 0);
	CTLineRef line = createLine(f, str, (int)len);
	CTLineDraw(line, ctx);
	CFRelease(line);
	CGContextRelease(ctx);

	bool clip = (options & ETO_CLIPPED) && rect;
	for (int py = 0; py < h; ++py)
	{
		const uint8_t* row = coverage.data() + (size_t)py * w;
		for (int px = 0; px < w; ++px)
		{
			int c = row[px];
			if (c == 0)
				continue;
			if (clip && (px < rect->left || px >= rect->right || py < rect->top || py >= rect->bottom))
				continue;
			writePixel(bmp, px, py, dc->textColor, c, true);
		}
	}
	return TRUE;
}

BOOL TextOutW(HDC hdc, int x, int y, LPCWSTR str, int len)
{
	return ExtTextOutW(hdc, x, y, 0, nullptr, str, (UINT)len, nullptr);
}

BOOL TextOut(HDC hdc, int x, int y, LPCSTR str, int len)
{
	std::vector<wchar_t> wide((size_t)len + 1);
	for (int i = 0; i < len; ++i)
		wide[i] = (unsigned char)str[i];
	return TextOutW(hdc, x, y, wide.data(), len);
}

//-----------------------------------------------------------------------------
// Bitmaps
//-----------------------------------------------------------------------------
HBITMAP CreateDIBSection(HDC, const BITMAPINFO* bmi, UINT, void** bits, HANDLE, DWORD)
{
	const BITMAPINFOHEADER& h = bmi->bmiHeader;
	if (h.biBitCount != 24 && h.biBitCount != 32)
		return nullptr;
	Bitmap* b = new Bitmap();
	b->width = h.biWidth;
	b->height = h.biHeight < 0 ? -h.biHeight : h.biHeight;
	b->topDown = h.biHeight < 0;
	b->bpp = h.biBitCount;
	b->stride = ((b->width * b->bpp + 31) / 32) * 4;
	b->bits = (uint8_t*)calloc((size_t)b->stride * b->height, 1);
	if (bits)
		*bits = b->bits;
	return (HBITMAP)(GdiObject*)b;
}

BOOL SetDeviceGammaRamp(HDC, LPVOID)
{
	return FALSE;
}

BOOL GetDeviceGammaRamp(HDC, LPVOID)
{
	return FALSE;
}

// Win32Shim: Video for Windows is not available. AVI capture fails gracefully.
#pragma once
#include <windows.h>

typedef struct IAVIFile* PAVIFILE;
typedef struct IAVIStream* PAVISTREAM;
typedef DWORD FOURCC;
#define mmioFOURCC(a, b, c, d) ((DWORD)(BYTE)(a) | ((DWORD)(BYTE)(b) << 8) | ((DWORD)(BYTE)(c) << 16) | ((DWORD)(BYTE)(d) << 24))
#define streamtypeVIDEO mmioFOURCC('v', 'i', 'd', 's')
#define OF_READ 0x0000
#define OF_WRITE 0x0001
#define OF_CREATE 0x1000
#define AVIIF_KEYFRAME 0x00000010L

typedef struct _AVISTREAMINFOA {
	DWORD fccType;
	DWORD fccHandler;
	DWORD dwFlags;
	DWORD dwCaps;
	WORD wPriority;
	WORD wLanguage;
	DWORD dwScale;
	DWORD dwRate;
	DWORD dwStart;
	DWORD dwLength;
	DWORD dwInitialFrames;
	DWORD dwSuggestedBufferSize;
	DWORD dwQuality;
	DWORD dwSampleSize;
	RECT rcFrame;
	DWORD dwEditCount;
	DWORD dwFormatChangeCount;
	char szName[64];
} AVISTREAMINFOA, AVISTREAMINFO;

inline void AVIFileInit() {}
inline void AVIFileExit() {}
inline HRESULT AVIFileOpen(PAVIFILE* file, LPCSTR, UINT, void*) { *file = NULL; return E_NOTIMPL; }
inline HRESULT AVIFileCreateStream(PAVIFILE, PAVISTREAM* stream, AVISTREAMINFO*) { *stream = NULL; return E_NOTIMPL; }
inline HRESULT AVIStreamSetFormat(PAVISTREAM, LONG, LPVOID, LONG) { return E_NOTIMPL; }
inline HRESULT AVIStreamWrite(PAVISTREAM, LONG, LONG, LPVOID, LONG, DWORD, LONG*, LONG*) { return E_NOTIMPL; }
inline ULONG AVIStreamRelease(PAVISTREAM) { return 0; }
inline ULONG AVIStreamClose(PAVISTREAM) { return 0; }
inline ULONG AVIFileRelease(PAVIFILE) { return 0; }
inline ULONG AVIFileClose(PAVIFILE) { return 0; }

// DirectSound subset for macOS: only the speaker configuration query used by the
// Miles audio manager. The Miles emulation reports no DirectSound object.
#pragma once
#include <objbase.h>

#define DSSPEAKER_DIRECTOUT 0x00000000
#define DSSPEAKER_HEADPHONE 0x00000001
#define DSSPEAKER_MONO 0x00000002
#define DSSPEAKER_QUAD 0x00000003
#define DSSPEAKER_STEREO 0x00000004
#define DSSPEAKER_SURROUND 0x00000005
#define DSSPEAKER_5POINT1 0x00000006
#define DSSPEAKER_7POINT1 0x00000007
#define DSSPEAKER_CONFIG(a) ((BYTE)(a))

DECLARE_INTERFACE_(IDirectSound, IUnknown)
{
	STDMETHOD(GetSpeakerConfig)(THIS_ LPDWORD pdwSpeakerConfig) PURE;
};
typedef IDirectSound* LPDIRECTSOUND;

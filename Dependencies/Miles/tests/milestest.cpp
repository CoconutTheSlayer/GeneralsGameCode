// Smoke test for the macOS Miles implementation: plays a generated tone as a 2D
// sample, a 3D sample to the right of the listener, and a stream of a system
// sound. Set GENERALS_AUDIO_DUMP to capture the mixed output.
#include <mss.h>
#include <SDL3/SDL.h>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <vector>

static std::vector<unsigned char> makeWav(int rate, float freq, float seconds)
{
	int frames = (int)(rate * seconds);
	std::vector<unsigned char> w(44 + frames * 2);
	auto w32 = [&](int o, unsigned v) { w[o] = v; w[o + 1] = v >> 8; w[o + 2] = v >> 16; w[o + 3] = v >> 24; };
	auto w16 = [&](int o, unsigned v) { w[o] = v; w[o + 1] = v >> 8; };
	memcpy(&w[0], "RIFF", 4); w32(4, (unsigned)w.size() - 8); memcpy(&w[8], "WAVEfmt ", 8);
	w32(16, 16); w16(20, 1); w16(22, 1); w32(24, rate); w32(28, rate * 2); w16(32, 2); w16(34, 16);
	memcpy(&w[36], "data", 4); w32(40, frames * 2);
	for (int i = 0; i < frames; ++i)
	{
		short s = (short)(sinf(2 * 3.14159265f * freq * i / rate) * 12000);
		w16(44 + i * 2, (unsigned short)s);
	}
	return w;
}

static int g_done = 0;
static void __stdcall onEnd(HSAMPLE) { g_done++; }
static void __stdcall onEnd3D(H3DPOBJECT) { g_done++; }

int main()
{
	if (!AIL_quick_startup(1, 0, 44100, 16, 2)) { printf("startup failed\n"); return 1; }
	HDIGDRIVER dig; AIL_quick_handles(&dig, nullptr, nullptr);
	std::vector<unsigned char> tone = makeWav(22050, 440.0f, 0.5f);
	AILSOUNDINFO info; AIL_WAV_info(tone.data(), &info);
	printf("wav: rate %u bits %d ch %d samples %u\n", (unsigned)info.rate, (int)info.bits, (int)info.channels, (unsigned)info.samples);

	HSAMPLE s = AIL_allocate_sample_handle(dig);
	AIL_init_sample(s);
	AIL_set_sample_file(s, tone.data(), 0);
	AIL_set_sample_volume_pan(s, 1.0f, 0.0f); // hard left
	AIL_register_EOS_callback(s, onEnd);
	AIL_start_sample(s);

	HPROENUM e = HPROENUM_FIRST; HPROVIDER prov; char* name;
	AIL_enumerate_3D_providers(&e, &prov, &name);
	AIL_open_3D_provider(prov);
	H3DPOBJECT listener = AIL_open_3D_listener(prov);
	AIL_set_3D_orientation(listener, 0, 1, 0, 0, 0, -1);
	AIL_set_3D_position(listener, 0, 0, 0);
	H3DSAMPLE s3 = AIL_allocate_3D_sample_handle(prov);
	std::vector<unsigned char> tone2 = makeWav(22050, 660.0f, 0.5f);
	AIL_set_3D_sample_file(s3, tone2.data());
	AIL_set_3D_sample_distances(s3, 1000.0f, 50.0f);
	AIL_set_3D_position(s3, 100.0f, 0.0f, 0.0f); // to the right
	AIL_register_3D_EOS_callback(s3, onEnd3D);
	AIL_start_3D_sample(s3);

	SDL_Delay(800);
	printf("EOS callbacks: %d (expected 2)\n", g_done);

	HSTREAM st = AIL_open_stream(dig, "/System/Library/Sounds/Glass.aiff", 0);
	printf("stream open: %s\n", st ? "ok" : "FAILED");
	if (st)
	{
		AIL_start_stream(st);
		SDL_Delay(1200);
		S32 total, cur; AIL_stream_ms_position(st, &total, &cur);
		printf("stream position %d / %d ms\n", (int)cur, (int)total);
		AIL_close_stream(st);
	}
	// Movie style PCM streaming: 1 second of 880 Hz stereo in 20 ms chunks.
	HSTREAM pcmStream = MilesMac_OpenPCMStream(2, 48000);
	printf("pcm stream: %s\n", pcmStream ? "ok" : "FAILED");
	std::vector<float> chunk(960 * 2);
	for (int c = 0; c < 50; ++c)
	{
		for (int i = 0; i < 960; ++i)
		{
			float v = 0.3f * sinf(2 * 3.14159265f * 880.0f * (c * 960 + i) / 48000.0f);
			chunk[i * 2] = v;
			chunk[i * 2 + 1] = v;
		}
		MilesMac_QueuePCM(pcmStream, chunk.data(), 960, 2);
		SDL_Delay(20);
	}
	SDL_Delay(200);
	MilesMac_ClosePCMStream(pcmStream);

	// Decoded sample cache: the same image decodes once, and a changed image at the same
	// address (here with half the sample rate in its header) is decoded again.
	int failures = 0;
	S32 total = 0, cur = 0;
	AIL_set_sample_file(s, tone.data(), 0);
	AIL_sample_ms_position(s, &total, &cur);
	if (total != 500) { printf("FAILED: sample length %d ms (expected 500)\n", (int)total); failures++; }
	AIL_set_sample_file(s, tone.data(), 0);
	AIL_sample_ms_position(s, &total, &cur);
	if (total != 500) { printf("FAILED: cached sample length %d ms (expected 500)\n", (int)total); failures++; }
	tone[24] = 11025 & 0xff; tone[25] = 11025 >> 8; // rate
	AIL_set_sample_file(s, tone.data(), 0);
	AIL_sample_ms_position(s, &total, &cur);
	if (total != 1000) { printf("FAILED: changed sample length %d ms (expected 1000)\n", (int)total); failures++; }
	// Images without a RIFF header have no known size and are rejected.
	unsigned char garbage[64] = {};
	if (AIL_set_sample_file(s, garbage, 0) != 0) { printf("FAILED: non-RIFF sample accepted\n"); failures++; }

	AIL_release_sample_handle(s);
	AIL_release_3D_sample_handle(s3);
	AIL_shutdown();
	printf(failures ? "%d FAILURES\n" : "miles tests passed\n", failures);
	return failures ? 1 : 0;
}

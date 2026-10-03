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

// Implementation of the Miles Sound System API subset used by the game, for macOS.
//
// Audio is mixed in software into an SDL3 output stream. 2D samples, 3D samples
// and streams are voices with volume, pan, pitch and looping. WAV (PCM and IMA
// ADPCM) is decoded here; MP3 is decoded with AudioToolbox. Streams are decoded
// progressively on a worker thread while they play.

#include "MilesLoader.h"
#include "mss.h"

#include <SDL3/SDL.h>
#include <AudioToolbox/AudioToolbox.h>

#include <algorithm>
#include <atomic>
#include <cmath>
#include <cstring>
#include <memory>
#include <mutex>
#include <string>
#include <thread>
#include <vector>

namespace
{

//-----------------------------------------------------------------------------
// PCM data
//-----------------------------------------------------------------------------
struct Pcm
{
	std::vector<int16_t> frames; // interleaved
	int channels = 1;
	int rate = 22050;
	size_t totalFrames = 0;              // known length (may exceed decoded frames while streaming)
	std::atomic<size_t> decodedFrames { 0 };
	std::atomic<bool> complete { false };
	std::atomic<bool> failed { false };
};

uint16_t rd16(const uint8_t* p) { return (uint16_t)(p[0] | (p[1] << 8)); }
uint32_t rd32(const uint8_t* p) { return (uint32_t)(p[0] | (p[1] << 8) | (p[2] << 16) | ((uint32_t)p[3] << 24)); }

struct WavInfo
{
	int format = 0;
	int channels = 0;
	int rate = 0;
	int bits = 0;
	int blockAlign = 0;
	const uint8_t* data = nullptr;
	size_t dataLen = 0;
	int samplesPerBlock = 0;
};

bool parseWav(const uint8_t* file, size_t size, WavInfo& info)
{
	if (size < 12 || memcmp(file, "RIFF", 4) != 0 || memcmp(file + 8, "WAVE", 4) != 0)
		return false;
	size_t pos = 12;
	bool haveFmt = false;
	while (pos + 8 <= size)
	{
		const uint8_t* chunk = file + pos;
		uint32_t len = rd32(chunk + 4);
		const uint8_t* body = chunk + 8;
		if (memcmp(chunk, "fmt ", 4) == 0 && len >= 16)
		{
			info.format = rd16(body);
			info.channels = rd16(body + 2);
			info.rate = (int)rd32(body + 4);
			info.blockAlign = rd16(body + 12);
			info.bits = rd16(body + 14);
			if (len >= 20 && info.format == WAVE_FORMAT_IMA_ADPCM)
				info.samplesPerBlock = rd16(body + 18);
			haveFmt = true;
		}
		else if (memcmp(chunk, "data", 4) == 0)
		{
			info.data = body;
			info.dataLen = std::min<size_t>(len, size - (pos + 8));
			break;
		}
		pos += 8 + len + (len & 1);
	}
	return haveFmt && info.data != nullptr;
}

// IMA ADPCM (Microsoft/DVI flavor) to 16 bit PCM.
const int kImaIndexTable[16] = { -1, -1, -1, -1, 2, 4, 6, 8, -1, -1, -1, -1, 2, 4, 6, 8 };
const int kImaStepTable[89] = { 7, 8, 9, 10, 11, 12, 13, 14, 16, 17, 19, 21, 23, 25, 28, 31, 34, 37, 41, 45, 50, 55, 60, 66, 73, 80, 88, 97, 107, 118, 130, 143, 157,
	173, 190, 209, 230, 253, 279, 307, 337, 371, 408, 449, 494, 544, 598, 658, 724, 796, 876, 963, 1060, 1166, 1282, 1411, 1552, 1707, 1878, 2066, 2272, 2499, 2749,
	3024, 3327, 3660, 4026, 4428, 4871, 5358, 5894, 6484, 7132, 7845, 8630, 9493, 10442, 11487, 12635, 13899, 15289, 16818, 18500, 20350, 22385, 24623, 27086, 29794,
	32767 };

int16_t imaDecodeNibble(int nibble, int& predictor, int& index)
{
	int step = kImaStepTable[index];
	int diff = step >> 3;
	if (nibble & 1)
		diff += step >> 2;
	if (nibble & 2)
		diff += step >> 1;
	if (nibble & 4)
		diff += step;
	if (nibble & 8)
		predictor -= diff;
	else
		predictor += diff;
	predictor = std::clamp(predictor, -32768, 32767);
	index = std::clamp(index + kImaIndexTable[nibble], 0, 88);
	return (int16_t)predictor;
}

void decodeImaAdpcm(const WavInfo& info, std::vector<int16_t>& out)
{
	int channels = std::max(1, info.channels);
	int blockAlign = info.blockAlign;
	int samplesPerBlock = info.samplesPerBlock ? info.samplesPerBlock : ((blockAlign - 4 * channels) * 8) / (4 * channels) + 1;
	size_t blocks = info.dataLen / (size_t)blockAlign;
	out.clear();
	out.reserve(blocks * samplesPerBlock * channels);
	std::vector<int16_t> block((size_t)samplesPerBlock * channels);
	for (size_t b = 0; b < blocks; ++b)
	{
		const uint8_t* p = info.data + b * blockAlign;
		int predictor[2] = { 0, 0 }, index[2] = { 0, 0 };
		for (int c = 0; c < channels; ++c)
		{
			predictor[c] = (int16_t)rd16(p + c * 4);
			index[c] = std::clamp((int)p[c * 4 + 2], 0, 88);
			block[c] = (int16_t)predictor[c];
		}
		const uint8_t* data = p + 4 * channels;
		int samplesDone = 1;
		// Data comes in groups of 4 bytes (8 samples) per channel.
		while (samplesDone < samplesPerBlock && data < p + blockAlign)
		{
			for (int c = 0; c < channels; ++c)
			{
				for (int i = 0; i < 4; ++i)
				{
					uint8_t byte = data[c * 4 + i];
					int s0 = samplesDone + i * 2;
					if (s0 < samplesPerBlock)
						block[(size_t)s0 * channels + c] = imaDecodeNibble(byte & 15, predictor[c], index[c]);
					if (s0 + 1 < samplesPerBlock)
						block[(size_t)(s0 + 1) * channels + c] = imaDecodeNibble(byte >> 4, predictor[c], index[c]);
				}
			}
			data += 4 * channels;
			samplesDone += 8;
		}
		out.insert(out.end(), block.begin(), block.end());
	}
}

bool decodeWav(const uint8_t* file, size_t size, Pcm& pcm)
{
	WavInfo info;
	if (!parseWav(file, size, info))
		return false;
	pcm.channels = std::clamp(info.channels, 1, 2);
	pcm.rate = info.rate > 0 ? info.rate : 22050;
	std::vector<int16_t> samples;
	int srcChannels = std::max(1, info.channels);
	if (info.format == WAVE_FORMAT_IMA_ADPCM)
		decodeImaAdpcm(info, samples);
	else if (info.format == 1 && info.bits == 16)
	{
		samples.resize(info.dataLen / 2);
		memcpy(samples.data(), info.data, samples.size() * 2);
	}
	else if (info.format == 1 && info.bits == 8)
	{
		samples.resize(info.dataLen);
		for (size_t i = 0; i < info.dataLen; ++i)
			samples[i] = (int16_t)(((int)info.data[i] - 128) << 8);
	}
	else
		return false;
	size_t frames = samples.size() / srcChannels;
	pcm.frames.resize(frames * pcm.channels);
	for (size_t f = 0; f < frames; ++f)
	{
		for (int c = 0; c < pcm.channels; ++c)
			pcm.frames[f * pcm.channels + c] = samples[f * srcChannels + std::min(c, srcChannels - 1)];
	}
	pcm.totalFrames = frames;
	pcm.decodedFrames = frames;
	pcm.complete = true;
	return true;
}

//-----------------------------------------------------------------------------
// AudioToolbox decoding (MP3 and anything else Core Audio understands)
//-----------------------------------------------------------------------------
struct MemoryFile
{
	std::vector<uint8_t> data;
};

OSStatus memRead(void* client, SInt64 position, UInt32 count, void* buffer, UInt32* actual)
{
	MemoryFile* f = static_cast<MemoryFile*>(client);
	if (position >= (SInt64)f->data.size())
	{
		*actual = 0;
		return noErr;
	}
	UInt32 n = (UInt32)std::min<SInt64>(count, (SInt64)f->data.size() - position);
	memcpy(buffer, f->data.data() + position, n);
	*actual = n;
	return noErr;
}

SInt64 memSize(void* client)
{
	return (SInt64) static_cast<MemoryFile*>(client)->data.size();
}

struct CoreAudioDecoder
{
	std::shared_ptr<MemoryFile> file;
	AudioFileID audioFile = nullptr;
	ExtAudioFileRef ext = nullptr;

	~CoreAudioDecoder()
	{
		if (ext)
			ExtAudioFileDispose(ext);
		if (audioFile)
			AudioFileClose(audioFile);
	}

	bool open(std::shared_ptr<MemoryFile> f, Pcm& pcm)
	{
		file = f;
		if (AudioFileOpenWithCallbacks(file.get(), memRead, nullptr, memSize, nullptr, 0, &audioFile) != noErr)
			return false;
		if (ExtAudioFileWrapAudioFileID(audioFile, false, &ext) != noErr)
			return false;
		AudioStreamBasicDescription src;
		UInt32 sz = sizeof(src);
		if (ExtAudioFileGetProperty(ext, kExtAudioFileProperty_FileDataFormat, &sz, &src) != noErr)
			return false;
		pcm.channels = std::clamp((int)src.mChannelsPerFrame, 1, 2);
		pcm.rate = src.mSampleRate > 0 ? (int)src.mSampleRate : 44100;
		AudioStreamBasicDescription client = {};
		client.mSampleRate = pcm.rate;
		client.mFormatID = kAudioFormatLinearPCM;
		client.mFormatFlags = kAudioFormatFlagIsSignedInteger | kAudioFormatFlagIsPacked;
		client.mChannelsPerFrame = (UInt32)pcm.channels;
		client.mBitsPerChannel = 16;
		client.mBytesPerFrame = 2 * (UInt32)pcm.channels;
		client.mFramesPerPacket = 1;
		client.mBytesPerPacket = client.mBytesPerFrame;
		if (ExtAudioFileSetProperty(ext, kExtAudioFileProperty_ClientDataFormat, sizeof(client), &client) != noErr)
			return false;
		SInt64 frames = 0;
		sz = sizeof(frames);
		ExtAudioFileGetProperty(ext, kExtAudioFileProperty_FileLengthFrames, &sz, &frames);
		pcm.totalFrames = frames > 0 ? (size_t)frames : 0;
		// Leave some slack: the length reported for MP3 can be an estimate.
		pcm.frames.resize((pcm.totalFrames + pcm.rate) * pcm.channels);
		return true;
	}

	// Decodes up to maxFrames more frames into pcm; returns false at end of data.
	bool decode(Pcm& pcm, size_t maxFrames)
	{
		size_t done = pcm.decodedFrames.load();
		if (done + maxFrames > pcm.frames.size() / pcm.channels)
		{
			// The estimate was short. Growing would invalidate the audio thread's view,
			// so stop here.
			maxFrames = pcm.frames.size() / pcm.channels - done;
			if (maxFrames == 0)
				return false;
		}
		AudioBufferList list;
		list.mNumberBuffers = 1;
		list.mBuffers[0].mNumberChannels = (UInt32)pcm.channels;
		list.mBuffers[0].mDataByteSize = (UInt32)(maxFrames * pcm.channels * 2);
		list.mBuffers[0].mData = pcm.frames.data() + done * pcm.channels;
		UInt32 frames = (UInt32)maxFrames;
		if (ExtAudioFileRead(ext, &frames, &list) != noErr || frames == 0)
			return false;
		pcm.decodedFrames = done + frames;
		return true;
	}
};

bool decodeCoreAudio(std::shared_ptr<MemoryFile> file, Pcm& pcm)
{
	CoreAudioDecoder dec;
	if (!dec.open(file, pcm))
		return false;
	while (dec.decode(pcm, 65536))
	{
	}
	pcm.totalFrames = pcm.decodedFrames.load();
	pcm.complete = true;
	return pcm.totalFrames > 0;
}

//-----------------------------------------------------------------------------
// Voices
//-----------------------------------------------------------------------------
enum VoiceKind
{
	VOICE_2D,
	VOICE_3D,
	VOICE_STREAM,
};

enum VoiceState
{
	STATE_IDLE,
	STATE_PLAYING,
	STATE_STOPPED, // paused
	STATE_DONE,
};

struct Voice
{
	VoiceKind kind = VOICE_2D;
	std::shared_ptr<Pcm> pcm;
	VoiceState state = STATE_IDLE;
	double position = 0.0;   // in source frames
	int rate = 22050;        // playback rate in Hz
	int loopCount = 1;       // 0 = forever
	int loopsDone = 0;
	float volume = 1.0f;
	float pan = 0.5f;
	// 3D
	float x = 0, y = 0, z = 0;
	float minDist = 1.0f, maxDist = 1000.0f;
	float occlusion = 0.0f;
	S32 userData[8] = {};
	// Live PCM voices (movie audio) wait for a little data before playing so that
	// irregular delivery does not cause gaps.
	bool live = false;
	bool buffering = true;
	AIL_sample_callback sampleEOS = nullptr;
	AIL_3dsample_callback sample3DEOS = nullptr;
	AIL_stream_callback streamEOS = nullptr;
	bool quick = false;
};

struct Listener
{
	float x = 0, y = 0, z = 0;
	float fx = 0, fy = 0, fz = 1;
	float ux = 0, uy = 1, uz = 0;
};

struct StreamJob
{
	std::shared_ptr<Pcm> pcm;
	std::shared_ptr<CoreAudioDecoder> decoder;
};

std::recursive_mutex g_mutex;
std::vector<Voice*> g_voices;
Listener g_listener;
SDL_AudioStream* g_output = nullptr;
int g_outputRate = 44100;
DIG_DRIVER g_digDriver;
bool g_started = false;

AIL_file_open_callback g_fileOpen = nullptr;
AIL_file_close_callback g_fileClose = nullptr;
AIL_file_seek_callback g_fileSeek = nullptr;
AIL_file_read_callback g_fileRead = nullptr;

// Stream decoding thread
std::mutex g_jobMutex;
std::vector<StreamJob> g_jobs;
std::thread g_decodeThread;
std::atomic<bool> g_decodeRunning { false };

std::vector<float> g_mixBuffer;
FILE* g_dumpFile = nullptr; // raw float stereo output for debugging ($GENERALS_AUDIO_DUMP)

void computeGains(const Voice& v, float& left, float& right)
{
	float volume = v.volume;
	float pan = v.pan;
	if (v.kind == VOICE_3D)
	{
		float dx = v.x - g_listener.x, dy = v.y - g_listener.y, dz = v.z - g_listener.z;
		float dist = sqrtf(dx * dx + dy * dy + dz * dz);
		float att = 1.0f;
		if (dist > v.maxDist)
			att = 0.0f;
		else if (dist > v.minDist && dist > 0.0f)
			att = v.minDist / dist;
		volume *= att * (1.0f - 0.5f * std::clamp(v.occlusion, 0.0f, 1.0f));
		// Pan from the direction relative to the listener's right vector.
		float rx = g_listener.uy * g_listener.fz - g_listener.uz * g_listener.fy;
		float ry = g_listener.uz * g_listener.fx - g_listener.ux * g_listener.fz;
		float rz = g_listener.ux * g_listener.fy - g_listener.uy * g_listener.fx;
		float rl = sqrtf(rx * rx + ry * ry + rz * rz);
		pan = 0.5f;
		if (rl > 0.0f && dist > 0.0f)
		{
			float side = (dx * rx + dy * ry + dz * rz) / (rl * dist);
			pan = 0.5f + 0.5f * side * std::clamp(dist / std::max(v.minDist, 1.0f), 0.0f, 1.0f);
		}
	}
	pan = std::clamp(pan, 0.0f, 1.0f);
	left = volume * std::min(1.0f, 2.0f * (1.0f - pan));
	right = volume * std::min(1.0f, 2.0f * pan);
}

struct PendingCallback
{
	Voice* voice;
};

// Audio thread: mix all playing voices.
void SDLCALL mixCallback(void*, SDL_AudioStream* stream, int additional, int)
{
	if (additional <= 0)
		return;
	int frames = additional / (int)(2 * sizeof(float));
	g_mixBuffer.assign((size_t)frames * 2, 0.0f);
	std::vector<Voice*> finished;
	{
		std::lock_guard<std::recursive_mutex> lock(g_mutex);
		for (Voice* v : g_voices)
		{
			if (v->state != STATE_PLAYING || !v->pcm)
				continue;
			Pcm& pcm = *v->pcm;
			float gl, gr;
			computeGains(*v, gl, gr);
			double step = (double)v->rate / g_outputRate;
			int ch = pcm.channels;
			if (v->live && v->buffering)
			{
				size_t queued = pcm.decodedFrames.load() - (size_t)v->position;
				if (queued < (size_t)(pcm.rate / 10))
					continue;
				v->buffering = false;
			}
			for (int i = 0; i < frames; ++i)
			{
				size_t available = pcm.decodedFrames.load(std::memory_order_acquire);
				size_t idx = (size_t)v->position;
				if (idx + 1 >= available)
				{
					bool atEnd = pcm.complete.load() && idx + 1 >= available;
					if (!atEnd)
					{
						if (v->live)
							v->buffering = true;
						break; // still decoding: output silence for the rest of this block
					}
					v->loopsDone++;
					if (v->loopCount == 0 || v->loopsDone < v->loopCount)
					{
						v->position = 0.0;
						idx = 0;
						if (available < 2)
							break;
					}
					else
					{
						v->state = STATE_DONE;
						finished.push_back(v);
						break;
					}
				}
				double frac = v->position - (double)idx;
				const int16_t* a = pcm.frames.data() + idx * ch;
				const int16_t* b = a + ch;
				float l = (float)((a[0] + (b[0] - a[0]) * frac) * (1.0 / 32768.0));
				float r = ch == 2 ? (float)((a[1] + (b[1] - a[1]) * frac) * (1.0 / 32768.0)) : l;
				g_mixBuffer[(size_t)i * 2] += l * gl;
				g_mixBuffer[(size_t)i * 2 + 1] += r * gr;
				v->position += step;
			}
		}
	}
	for (float& s : g_mixBuffer)
		s = std::clamp(s, -1.0f, 1.0f);
	SDL_PutAudioStreamData(stream, g_mixBuffer.data(), (int)(g_mixBuffer.size() * sizeof(float)));
	if (g_dumpFile)
		fwrite(g_mixBuffer.data(), sizeof(float), g_mixBuffer.size(), g_dumpFile);

	// End of sample callbacks, like Miles' timer thread. They run under the lock so
	// a voice cannot be released concurrently; the lock is recursive so the
	// callbacks may call back into the API.
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	for (Voice* v : finished)
	{
		if (std::find(g_voices.begin(), g_voices.end(), v) == g_voices.end() || v->state != STATE_DONE)
			continue;
		if (v->kind == VOICE_2D && v->sampleEOS)
			v->sampleEOS((HSAMPLE)v);
		else if (v->kind == VOICE_3D && v->sample3DEOS)
			v->sample3DEOS((H3DPOBJECT)v);
		else if (v->kind == VOICE_STREAM && v->streamEOS)
			v->streamEOS((HSTREAM)v);
	}
}

void decodeThreadMain()
{
	while (g_decodeRunning)
	{
		bool worked = false;
		std::vector<StreamJob> jobs;
		{
			std::lock_guard<std::mutex> lock(g_jobMutex);
			jobs = g_jobs;
		}
		for (StreamJob& job : jobs)
		{
			if (job.pcm->complete)
				continue;
			if (job.decoder->decode(*job.pcm, 32768))
				worked = true;
			else
			{
				job.pcm->totalFrames = job.pcm->decodedFrames.load();
				job.pcm->complete = true;
			}
		}
		{
			std::lock_guard<std::mutex> lock(g_jobMutex);
			g_jobs.erase(std::remove_if(g_jobs.begin(), g_jobs.end(), [](const StreamJob& j) { return j.pcm->complete.load() || j.pcm.use_count() <= 2; }), g_jobs.end());
		}
		if (!worked)
			SDL_Delay(5);
	}
}

// Reads a whole file through the game's file callbacks (or stdio as fallback).
bool readFile(const char* name, std::vector<uint8_t>& out)
{
	if (g_fileOpen && g_fileRead && g_fileClose)
	{
		void* handle = nullptr;
		if (!g_fileOpen(name, &handle) || handle == nullptr)
			return false;
		uint8_t buffer[65536];
		for (;;)
		{
			U32 n = g_fileRead(handle, buffer, sizeof(buffer));
			if (n == 0 || n == (U32)-1)
				break;
			out.insert(out.end(), buffer, buffer + n);
			if (n < sizeof(buffer))
				break;
		}
		g_fileClose(handle);
		return !out.empty();
	}
	std::string path = name;
	for (char& c : path)
	{
		if (c == '\\')
			c = '/';
	}
	FILE* f = fopen(path.c_str(), "rb");
	if (f == nullptr)
		return false;
	uint8_t buffer[65536];
	size_t n;
	while ((n = fread(buffer, 1, sizeof(buffer), f)) > 0)
		out.insert(out.end(), buffer, buffer + n);
	fclose(f);
	return !out.empty();
}

// Decodes a complete in memory file image (WAV or anything Core Audio reads).
std::shared_ptr<Pcm> decodeImage(const void* image, size_t size)
{
	auto pcm = std::make_shared<Pcm>();
	const uint8_t* data = static_cast<const uint8_t*>(image);
	if (decodeWav(data, size, *pcm))
		return pcm;
	auto file = std::make_shared<MemoryFile>();
	file->data.assign(data, data + size);
	if (decodeCoreAudio(file, *pcm))
		return pcm;
	return nullptr;
}

size_t wavImageSize(const void* image)
{
	const uint8_t* p = static_cast<const uint8_t*>(image);
	if (memcmp(p, "RIFF", 4) == 0)
		return rd32(p + 4) + 8;
	return 0;
}

Voice* newVoice(VoiceKind kind)
{
	Voice* v = new Voice();
	v->kind = kind;
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	g_voices.push_back(v);
	return v;
}

void deleteVoice(Voice* v)
{
	if (v == nullptr)
		return;
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	g_voices.erase(std::remove(g_voices.begin(), g_voices.end(), v), g_voices.end());
	delete v;
}

Voice* toVoice(const void* handle)
{
	return const_cast<Voice*>(static_cast<const Voice*>(handle));
}

} // namespace

//-----------------------------------------------------------------------------
// MilesLoader: nothing to load on macOS.
//-----------------------------------------------------------------------------
bool MilesLoader::isLoaded() { return true; }
bool MilesLoader::isFailed() { return false; }
unsigned long MilesLoader::getLastError() { return 0; }
bool MilesLoader::load() { return true; }
void MilesLoader::unload() {}

extern "C" {

//-----------------------------------------------------------------------------
// Startup
//-----------------------------------------------------------------------------
S32 __stdcall AIL_startup(void)
{
	return 1;
}

S32 __stdcall AIL_quick_startup(S32 use_digital, S32, U32 output_rate, S32, S32)
{
	if (!use_digital)
		return 0;
	if (g_started)
		return 1;
	if (!SDL_InitSubSystem(SDL_INIT_AUDIO))
	{
		fprintf(stderr, "Miles: SDL audio init failed: %s\n", SDL_GetError());
		return 0;
	}
	g_outputRate = output_rate > 0 ? (int)output_rate : 44100;
	SDL_AudioSpec spec;
	spec.format = SDL_AUDIO_F32;
	spec.channels = 2;
	spec.freq = g_outputRate;
	g_output = SDL_OpenAudioDeviceStream(SDL_AUDIO_DEVICE_DEFAULT_PLAYBACK, &spec, mixCallback, nullptr);
	if (g_output == nullptr)
	{
		fprintf(stderr, "Miles: could not open audio device: %s\n", SDL_GetError());
		return 0;
	}
	if (const char* dump = getenv("GENERALS_AUDIO_DUMP"))
		g_dumpFile = fopen(dump, "wb");
	SDL_ResumeAudioStreamDevice(g_output);
	memset(&g_digDriver, 0, sizeof(g_digDriver));
	g_decodeRunning = true;
	g_decodeThread = std::thread(decodeThreadMain);
	g_started = true;
	return 1;
}

void __stdcall AIL_quick_handles(HDIGDRIVER* pdig, HMDIDRIVER* pmdi, HDLSDEVICE* pdls)
{
	if (pdig)
		*pdig = g_started ? &g_digDriver : nullptr;
	if (pmdi)
		*pmdi = nullptr;
	if (pdls)
		*pdls = nullptr;
}

void __stdcall AIL_shutdown(void)
{
	if (!g_started)
		return;
	if (g_output)
	{
		SDL_DestroyAudioStream(g_output);
		g_output = nullptr;
	}
	if (g_dumpFile)
	{
		fclose(g_dumpFile);
		g_dumpFile = nullptr;
	}
	g_decodeRunning = false;
	if (g_decodeThread.joinable())
		g_decodeThread.join();
	{
		std::lock_guard<std::mutex> lock(g_jobMutex);
		g_jobs.clear();
	}
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	for (Voice* v : g_voices)
		delete v;
	g_voices.clear();
	g_started = false;
}

S32 __stdcall AIL_set_preference(U32, S32 value) { return value; }
char* __stdcall AIL_set_redist_directory(const char* dir) { return const_cast<char*>(dir); }
char* __stdcall AIL_last_error(void) { return const_cast<char*>(""); }
U32 __stdcall AIL_get_timer_highest_delay(void) { return 0; }
void __stdcall AIL_stop_timer(HTIMER) {}
void __stdcall AIL_release_timer_handle(HTIMER) {}
void __stdcall AIL_lock(void) { g_mutex.lock(); }
void __stdcall AIL_unlock(void) { g_mutex.unlock(); }
void __stdcall AIL_lock_mutex(void) { g_mutex.lock(); }
void __stdcall AIL_unlock_mutex(void) { g_mutex.unlock(); }
S32 __stdcall AIL_waveOutOpen(HDIGDRIVER*, LPHWAVEOUT*, S32, LPWAVEFORMAT) { return -1; }
void __stdcall AIL_waveOutClose(HDIGDRIVER) {}

void __stdcall AIL_set_file_callbacks(AIL_file_open_callback opencb, AIL_file_close_callback closecb, AIL_file_seek_callback seekcb, AIL_file_read_callback readcb)
{
	g_fileOpen = opencb;
	g_fileClose = closecb;
	g_fileSeek = seekcb;
	g_fileRead = readcb;
}

void __stdcall AIL_get_DirectSound_info(HSAMPLE, AILLPDIRECTSOUND* lplpDS, AILLPDIRECTSOUNDBUFFER* lplpDSB)
{
	if (lplpDS)
		*lplpDS = nullptr;
	if (lplpDSB)
		*lplpDSB = nullptr;
}

//-----------------------------------------------------------------------------
// Providers and filters
//-----------------------------------------------------------------------------
S32 __stdcall AIL_enumerate_3D_providers(HPROENUM* next, HPROVIDER* dest, char** name)
{
	if (*next != HPROENUM_FIRST)
		return 0;
	static char providerName[] = "Miles Fast 2D Positional Audio";
	*dest = (HPROVIDER)&g_digDriver;
	*name = providerName;
	*next = 1;
	return 1;
}

S32 __stdcall AIL_enumerate_filters(HPROENUM*, HPROVIDER*, char**)
{
	return 0;
}

M3DRESULT __stdcall AIL_open_3D_provider(HPROVIDER) { return M3D_NOERR; }
void __stdcall AIL_close_3D_provider(HPROVIDER) {}
void __stdcall AIL_set_3D_speaker_type(HPROVIDER, S32) {}

H3DPOBJECT __stdcall AIL_open_3D_listener(HPROVIDER)
{
	return (H3DPOBJECT)&g_listener;
}

void __stdcall AIL_close_3D_listener(H3DPOBJECT) {}

HPROVIDER __stdcall AIL_set_sample_processor(HSAMPLE, SAMPLESTAGE, HPROVIDER) { return nullptr; }
void __stdcall AIL_set_filter_sample_preference(HSAMPLE, const char*, const void*) {}

//-----------------------------------------------------------------------------
// WAV helpers
//-----------------------------------------------------------------------------
S32 __stdcall AIL_WAV_info(const void* data, AILSOUNDINFO* info)
{
	if (data == nullptr || info == nullptr)
		return 0;
	memset(info, 0, sizeof(*info));
	size_t size = wavImageSize(data);
	WavInfo w;
	if (size == 0 || !parseWav(static_cast<const uint8_t*>(data), size, w))
		return 0;
	info->format = w.format;
	info->data_ptr = w.data;
	info->data_len = (U32)w.dataLen;
	info->rate = (U32)w.rate;
	info->bits = w.bits;
	info->channels = w.channels;
	info->block_size = (U32)w.blockAlign;
	info->initial_ptr = w.data;
	if (w.format == WAVE_FORMAT_IMA_ADPCM && w.blockAlign > 0)
	{
		int spb = w.samplesPerBlock ? w.samplesPerBlock : ((w.blockAlign - 4 * w.channels) * 8) / (4 * std::max(1, w.channels)) + 1;
		info->samples = (U32)((w.dataLen / w.blockAlign) * spb);
	}
	else if (w.bits > 0 && w.channels > 0)
		info->samples = (U32)(w.dataLen / (w.bits / 8) / w.channels);
	return 1;
}

S32 __stdcall AIL_decompress_ADPCM(const AILSOUNDINFO* info, void** outdata, U32* outsize)
{
	if (info == nullptr || outdata == nullptr || outsize == nullptr)
		return 0;
	WavInfo w;
	w.format = info->format;
	w.channels = info->channels;
	w.rate = (int)info->rate;
	w.bits = info->bits;
	w.blockAlign = (int)info->block_size;
	w.data = static_cast<const uint8_t*>(info->data_ptr);
	w.dataLen = info->data_len;
	std::vector<int16_t> pcm;
	decodeImaAdpcm(w, pcm);

	// Return a complete 16 bit PCM WAV image.
	uint32_t dataBytes = (uint32_t)(pcm.size() * 2);
	uint32_t total = 44 + dataBytes;
	uint8_t* out = (uint8_t*)malloc(total);
	auto w32 = [](uint8_t* p, uint32_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); p[2] = (uint8_t)(v >> 16); p[3] = (uint8_t)(v >> 24); };
	auto w16 = [](uint8_t* p, uint16_t v) { p[0] = (uint8_t)v; p[1] = (uint8_t)(v >> 8); };
	int channels = std::max(1, w.channels);
	memcpy(out, "RIFF", 4);
	w32(out + 4, total - 8);
	memcpy(out + 8, "WAVEfmt ", 8);
	w32(out + 16, 16);
	w16(out + 20, 1);
	w16(out + 22, (uint16_t)channels);
	w32(out + 24, (uint32_t)w.rate);
	w32(out + 28, (uint32_t)(w.rate * channels * 2));
	w16(out + 32, (uint16_t)(channels * 2));
	w16(out + 34, 16);
	memcpy(out + 36, "data", 4);
	w32(out + 40, dataBytes);
	memcpy(out + 44, pcm.data(), dataBytes);
	*outdata = out;
	*outsize = total;
	return 1;
}

void __stdcall AIL_mem_free_lock(void* ptr)
{
	free(ptr);
}

//-----------------------------------------------------------------------------
// 2D samples
//-----------------------------------------------------------------------------
HSAMPLE __stdcall AIL_allocate_sample_handle(HDIGDRIVER)
{
	return (HSAMPLE)newVoice(VOICE_2D);
}

void __stdcall AIL_release_sample_handle(HSAMPLE sample)
{
	deleteVoice(toVoice(sample));
}

void __stdcall AIL_init_sample(HSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->pcm.reset();
	v->state = STATE_IDLE;
	v->position = 0.0;
	v->loopCount = 1;
	v->loopsDone = 0;
	v->volume = 1.0f;
	v->pan = 0.5f;
	v->sampleEOS = nullptr;
}

S32 __stdcall AIL_set_sample_file(HSAMPLE sample, const void* file_image, S32)
{
	Voice* v = toVoice(sample);
	size_t size = wavImageSize(file_image);
	if (size == 0)
		size = 16 * 1024 * 1024; // non-WAV images: Core Audio stops at the end of the data
	std::shared_ptr<Pcm> pcm = decodeImage(file_image, size);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->pcm = pcm;
	v->position = 0.0;
	v->loopsDone = 0;
	if (!pcm)
		return 0;
	v->rate = pcm->rate;
	return 1;
}

S32 __stdcall AIL_set_named_sample_file(HSAMPLE sample, const char*, const void* file_image, S32 file_size, S32)
{
	Voice* v = toVoice(sample);
	std::shared_ptr<Pcm> pcm = decodeImage(file_image, (size_t)file_size);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->pcm = pcm;
	v->position = 0.0;
	if (!pcm)
		return 0;
	v->rate = pcm->rate;
	return 1;
}

void __stdcall AIL_start_sample(HSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->position = 0.0;
	v->loopsDone = 0;
	v->state = v->pcm ? STATE_PLAYING : STATE_DONE;
}

void __stdcall AIL_stop_sample(HSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if (v->state == STATE_PLAYING)
		v->state = STATE_STOPPED;
}

void __stdcall AIL_resume_sample(HSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if (v->state == STATE_STOPPED || v->state == STATE_IDLE)
		v->state = v->pcm ? STATE_PLAYING : STATE_DONE;
}

void __stdcall AIL_end_sample(HSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->state = STATE_DONE;
}

void __stdcall AIL_set_sample_playback_rate(HSAMPLE sample, S32 playback_rate)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(sample)->rate = std::max<S32>(1, playback_rate);
}

S32 __stdcall AIL_sample_playback_rate(HSAMPLE sample)
{
	return toVoice(sample)->rate;
}

void __stdcall AIL_set_sample_volume_pan(HSAMPLE sample, F32 volume, F32 pan)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(sample);
	v->volume = volume;
	v->pan = pan;
}

void __stdcall AIL_sample_volume_pan(HSAMPLE sample, F32* volume, F32* pan)
{
	Voice* v = toVoice(sample);
	if (volume)
		*volume = v->volume;
	if (pan)
		*pan = v->pan;
}

S32 __stdcall AIL_sample_loop_count(HSAMPLE sample)
{
	Voice* v = toVoice(sample);
	return v->loopCount == 0 ? 0 : std::max(0, v->loopCount - v->loopsDone);
}

void __stdcall AIL_set_sample_loop_count(HSAMPLE sample, S32 count)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(sample)->loopCount = count;
}

void __stdcall AIL_sample_ms_position(HSAMPLE sample, S32* total_ms, S32* current_ms)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	int rate = v->pcm ? v->pcm->rate : 22050;
	if (total_ms)
		*total_ms = v->pcm ? (S32)(v->pcm->totalFrames * 1000 / rate) : 0;
	if (current_ms)
		*current_ms = (S32)(v->position * 1000 / rate);
}

void __stdcall AIL_set_sample_ms_position(HSAMPLE sample, S32 pos)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	int rate = v->pcm ? v->pcm->rate : 22050;
	v->position = (double)pos * rate / 1000.0;
}

AIL_sample_callback __stdcall AIL_register_EOS_callback(HSAMPLE sample, AIL_sample_callback EOS)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(sample);
	AIL_sample_callback old = v->sampleEOS;
	v->sampleEOS = EOS;
	return old;
}

void __stdcall AIL_set_sample_user_data(HSAMPLE sample, U32 index, S32 value)
{
	if (index < 8)
		toVoice(sample)->userData[index] = value;
}

S32 __stdcall AIL_sample_user_data(HSAMPLE sample, U32 index)
{
	return index < 8 ? toVoice(sample)->userData[index] : 0;
}

//-----------------------------------------------------------------------------
// 3D samples
//-----------------------------------------------------------------------------
H3DSAMPLE __stdcall AIL_allocate_3D_sample_handle(HPROVIDER)
{
	return (H3DSAMPLE)newVoice(VOICE_3D);
}

void __stdcall AIL_release_3D_sample_handle(H3DSAMPLE sample)
{
	deleteVoice(toVoice(sample));
}

S32 __stdcall AIL_set_3D_sample_file(H3DSAMPLE sample, const void* file_image)
{
	Voice* v = toVoice(sample);
	size_t size = wavImageSize(file_image);
	if (size == 0)
		size = 16 * 1024 * 1024;
	std::shared_ptr<Pcm> pcm = decodeImage(file_image, size);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->pcm = pcm;
	v->position = 0.0;
	v->loopsDone = 0;
	v->loopCount = 1;
	v->state = STATE_IDLE;
	if (!pcm)
		return 0;
	v->rate = pcm->rate;
	return 1;
}

void __stdcall AIL_start_3D_sample(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->position = 0.0;
	v->loopsDone = 0;
	v->state = v->pcm ? STATE_PLAYING : STATE_DONE;
}

void __stdcall AIL_stop_3D_sample(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if (v->state == STATE_PLAYING)
		v->state = STATE_STOPPED;
}

void __stdcall AIL_resume_3D_sample(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if (v->state == STATE_STOPPED || v->state == STATE_IDLE)
		v->state = v->pcm ? STATE_PLAYING : STATE_DONE;
}

void __stdcall AIL_end_3D_sample(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->state = STATE_DONE;
}

F32 __stdcall AIL_3D_sample_volume(H3DSAMPLE sample)
{
	return toVoice(sample)->volume;
}

void __stdcall AIL_set_3D_sample_volume(H3DSAMPLE sample, F32 volume)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(sample)->volume = volume;
}

U32 __stdcall AIL_3D_sample_loop_count(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	return v->loopCount == 0 ? 0 : (U32)std::max(0, v->loopCount - v->loopsDone);
}

void __stdcall AIL_set_3D_sample_loop_count(H3DSAMPLE sample, U32 count)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(sample)->loopCount = (int)count;
}

void __stdcall AIL_set_3D_sample_offset(H3DSAMPLE sample, U32 offset)
{
	Voice* v = toVoice(sample);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if (v->pcm)
		v->position = (double)(offset / (2 * v->pcm->channels));
}

U32 __stdcall AIL_3D_sample_length(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	return v->pcm ? (U32)(v->pcm->totalFrames * 2 * v->pcm->channels) : 0;
}

U32 __stdcall AIL_3D_sample_offset(H3DSAMPLE sample)
{
	Voice* v = toVoice(sample);
	return v->pcm ? (U32)((size_t)v->position * 2 * v->pcm->channels) : 0;
}

S32 __stdcall AIL_3D_sample_playback_rate(H3DSAMPLE sample)
{
	return toVoice(sample)->rate;
}

void __stdcall AIL_set_3D_sample_playback_rate(H3DSAMPLE sample, S32 playback_rate)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(sample)->rate = std::max<S32>(1, playback_rate);
}

void __stdcall AIL_set_3D_sample_distances(H3DSAMPLE sample, F32 max_dist, F32 min_dist)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(sample);
	v->maxDist = max_dist;
	v->minDist = min_dist;
}

void __stdcall AIL_set_3D_sample_occlusion(H3DSAMPLE sample, F32 occlusion)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(sample)->occlusion = occlusion;
}

void __stdcall AIL_set_3D_sample_effects_level(H3DSAMPLE, F32) {}
void __stdcall AIL_set_3D_velocity_vector(H3DPOBJECT, F32, F32, F32) {}

void __stdcall AIL_set_3D_position(H3DPOBJECT obj, F32 X, F32 Y, F32 Z)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if ((void*)obj == (void*)&g_listener)
	{
		g_listener.x = X;
		g_listener.y = Y;
		g_listener.z = Z;
		return;
	}
	Voice* v = toVoice(obj);
	v->x = X;
	v->y = Y;
	v->z = Z;
}

void __stdcall AIL_set_3D_orientation(H3DPOBJECT obj, F32 X_face, F32 Y_face, F32 Z_face, F32 X_up, F32 Y_up, F32 Z_up)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if ((void*)obj != (void*)&g_listener)
		return;
	g_listener.fx = X_face;
	g_listener.fy = Y_face;
	g_listener.fz = Z_face;
	g_listener.ux = X_up;
	g_listener.uy = Y_up;
	g_listener.uz = Z_up;
}

AIL_3dsample_callback __stdcall AIL_register_3D_EOS_callback(H3DSAMPLE sample, AIL_3dsample_callback EOS)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(sample);
	AIL_3dsample_callback old = v->sample3DEOS;
	v->sample3DEOS = EOS;
	return old;
}

void __stdcall AIL_set_3D_user_data(H3DPOBJECT obj, U32 index, S32 value)
{
	if ((void*)obj != (void*)&g_listener && index < 8)
		toVoice(obj)->userData[index] = value;
}

S32 __stdcall AIL_3D_user_data(H3DPOBJECT obj, U32 index)
{
	if ((void*)obj == (void*)&g_listener || index >= 8)
		return 0;
	return toVoice(obj)->userData[index];
}

//-----------------------------------------------------------------------------
// Streams
//-----------------------------------------------------------------------------
HSTREAM __stdcall AIL_open_stream(HDIGDRIVER, const char* filename, S32)
{
	if (!g_started || filename == nullptr)
		return nullptr;
	auto file = std::make_shared<MemoryFile>();
	if (!readFile(filename, file->data))
		return nullptr;

	auto pcm = std::make_shared<Pcm>();
	if (!decodeWav(file->data.data(), file->data.size(), *pcm))
	{
		auto decoder = std::make_shared<CoreAudioDecoder>();
		if (!decoder->open(file, *pcm))
			return nullptr;
		// Decode the first second right away so playback can start immediately.
		decoder->decode(*pcm, (size_t)pcm->rate);
		std::lock_guard<std::mutex> lock(g_jobMutex);
		g_jobs.push_back(StreamJob { pcm, decoder });
	}
	Voice* v = newVoice(VOICE_STREAM);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->pcm = pcm;
	v->rate = pcm->rate;
	v->state = STATE_IDLE;
	return (HSTREAM)v;
}

void __stdcall AIL_close_stream(HSTREAM stream)
{
	deleteVoice(toVoice(stream));
}

void __stdcall AIL_start_stream(HSTREAM stream)
{
	Voice* v = toVoice(stream);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->position = 0.0;
	v->loopsDone = 0;
	v->state = STATE_PLAYING;
}

void __stdcall AIL_pause_stream(HSTREAM stream, S32 onoff)
{
	Voice* v = toVoice(stream);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	if (onoff && v->state == STATE_PLAYING)
		v->state = STATE_STOPPED;
	else if (!onoff && (v->state == STATE_STOPPED || v->state == STATE_IDLE))
		v->state = STATE_PLAYING;
}

void __stdcall AIL_set_stream_volume_pan(HSTREAM stream, F32 volume, F32 pan)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(stream);
	v->volume = volume;
	v->pan = pan;
}

void __stdcall AIL_stream_volume_pan(HSTREAM stream, F32* volume, F32* pan)
{
	Voice* v = toVoice(stream);
	if (volume)
		*volume = v->volume;
	if (pan)
		*pan = v->pan;
}

void __stdcall AIL_set_stream_playback_rate(HSTREAM stream, S32 rate)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(stream)->rate = std::max<S32>(1, rate);
}

S32 __stdcall AIL_stream_playback_rate(HSTREAM stream)
{
	return toVoice(stream)->rate;
}

void __stdcall AIL_stream_ms_position(HSTREAM stream, S32* total_milliseconds, S32* current_milliseconds)
{
	Voice* v = toVoice(stream);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	int rate = v->pcm ? v->pcm->rate : 44100;
	if (total_milliseconds)
		*total_milliseconds = v->pcm ? (S32)(v->pcm->totalFrames * 1000 / rate) : 0;
	if (current_milliseconds)
		*current_milliseconds = (S32)(v->position * 1000 / rate);
}

void __stdcall AIL_set_stream_ms_position(HSTREAM stream, S32 pos)
{
	Voice* v = toVoice(stream);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	int rate = v->pcm ? v->pcm->rate : 44100;
	v->position = (double)pos * rate / 1000.0;
}

S32 __stdcall AIL_stream_loop_count(HSTREAM stream)
{
	Voice* v = toVoice(stream);
	return v->loopCount == 0 ? 0 : std::max(0, v->loopCount - v->loopsDone);
}

void __stdcall AIL_set_stream_loop_count(HSTREAM stream, S32 count)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	toVoice(stream)->loopCount = count;
}

void __stdcall AIL_set_stream_loop_block(HSTREAM, S32, S32) {}

AIL_stream_callback __stdcall AIL_register_stream_callback(HSTREAM stream, AIL_stream_callback callback)
{
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(stream);
	AIL_stream_callback old = v->streamEOS;
	v->streamEOS = callback;
	return old;
}

//-----------------------------------------------------------------------------
// Quick API
//-----------------------------------------------------------------------------
HAUDIO __stdcall AIL_quick_load_and_play(const char* filename, U32 loop_count, S32)
{
	HSTREAM stream = AIL_open_stream(&g_digDriver, filename, 0);
	if (stream == nullptr)
		return nullptr;
	AIL_set_stream_loop_count(stream, (S32)loop_count);
	toVoice(stream)->quick = true;
	AIL_start_stream(stream);
	return (HAUDIO)stream;
}

void __stdcall AIL_quick_set_volume(HAUDIO audio, F32 volume, F32)
{
	if (audio)
		AIL_set_stream_volume_pan((HSTREAM)audio, volume, 0.5f);
}

void __stdcall AIL_quick_unload(HAUDIO audio)
{
	if (audio)
		AIL_close_stream((HSTREAM)audio);
}

//-----------------------------------------------------------------------------
// macOS extension: a voice playing PCM that is supplied incrementally (movie audio)
//-----------------------------------------------------------------------------
HSTREAM MilesMac_OpenPCMStream(int channels, int rate)
{
	if (!g_started)
		return nullptr;
	auto pcm = std::make_shared<Pcm>();
	pcm->channels = std::clamp(channels, 1, 2);
	pcm->rate = rate > 0 ? rate : 44100;
	Voice* v = newVoice(VOICE_STREAM);
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	v->pcm = pcm;
	v->rate = pcm->rate;
	v->loopCount = 1;
	v->live = true;
	v->state = STATE_PLAYING;
	return (HSTREAM)v;
}

void MilesMac_QueuePCM(HSTREAM stream, const float* interleaved, int frames, int channels)
{
	if (stream == nullptr || interleaved == nullptr || frames <= 0 || channels <= 0)
		return;
	std::lock_guard<std::recursive_mutex> lock(g_mutex);
	Voice* v = toVoice(stream);
	Pcm& pcm = *v->pcm;
	// Drop data that has been played to keep memory bounded.
	size_t consumed = (size_t)v->position;
	if (consumed > (size_t)pcm.rate)
	{
		pcm.frames.erase(pcm.frames.begin(), pcm.frames.begin() + (long)(consumed * pcm.channels));
		pcm.decodedFrames = pcm.decodedFrames.load() - consumed;
		v->position -= (double)consumed;
	}
	size_t start = pcm.decodedFrames.load();
	pcm.frames.resize((start + (size_t)frames) * pcm.channels);
	for (int f = 0; f < frames; ++f)
	{
		for (int c = 0; c < pcm.channels; ++c)
		{
			float sample = interleaved[f * channels + std::min(c, channels - 1)];
			pcm.frames[(start + f) * pcm.channels + c] = (int16_t)std::clamp((int)lrintf(sample * 32767.0f), -32768, 32767);
		}
	}
	pcm.decodedFrames = start + (size_t)frames;
	pcm.totalFrames = pcm.decodedFrames.load();
}

void MilesMac_SetPCMVolume(HSTREAM stream, float volume)
{
	if (stream)
		AIL_set_stream_volume_pan(stream, volume, 0.5f);
}

void MilesMac_ClosePCMStream(HSTREAM stream)
{
	if (stream)
		AIL_close_stream(stream);
}

} // extern "C"

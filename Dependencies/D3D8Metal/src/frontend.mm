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

// The render thread: the ring buffer the game thread records into, the thread that runs it, and
// how state changes travel from the game thread's copy of the device state to the render thread's.

#include "internal.h"

#include <pthread.h>

namespace d3d8metal
{

//-----------------------------------------------------------------------------
// Ring buffer
//-----------------------------------------------------------------------------
namespace
{
const size_t kRingSize = 32u * 1024u * 1024u;
const size_t kRecordAlign = 16;
static_assert(sizeof(Device*) == 8, "64 bit only");
} // namespace

void* Device::reserveRecord(size_t payload)
{
	if (m_ring == nullptr)
	{
		m_ringSize = kRingSize;
		m_ring.reset(new uint8_t[m_ringSize]);
	}
	const size_t total = (sizeof(RecordHeader) + payload + kRecordAlign - 1) & ~(kRecordAlign - 1);
	for (;;)
	{
		const uint64_t head = m_ringHead.load(std::memory_order_relaxed);
		const uint64_t tail = m_ringTail.load(std::memory_order_acquire);
		const size_t pos = (size_t)(head % m_ringSize);
		const size_t room = m_ringSize - pos;
		const size_t free = m_ringSize - (size_t)(head - tail);
		if (room < total)
		{
			// Pad to the end of the ring and start over at its beginning.
			if (free >= room)
			{
				RecordHeader* pad = reinterpret_cast<RecordHeader*>(m_ring.get() + pos);
				pad->run = nullptr;
				pad->size = room;
				m_ringHead.store(head + room, std::memory_order_release);
				continue;
			}
		}
		else if (free >= total)
		{
			m_ringReserved = pos;
			m_ringRecordSize = total;
			return m_ring.get() + pos + sizeof(RecordHeader);
		}
		// Full: let the render thread catch up.
		if (!m_threaded)
		{
			runRecords(m_ringHead.load(std::memory_order_acquire));
			continue;
		}
		std::unique_lock<std::mutex> lock(m_ringMutex);
		m_producerWaiting.store(true);
		m_workerWake.notify_one();
		m_producerWake.wait_for(lock, std::chrono::milliseconds(1));
		m_producerWaiting.store(false);
	}
}

void Device::commitRecord(void (*run)(Device*, void*))
{
	RecordHeader* header = reinterpret_cast<RecordHeader*>(m_ring.get() + m_ringReserved);
	header->run = run;
	header->size = m_ringRecordSize;
	const uint64_t head = m_ringHead.load(std::memory_order_relaxed) + m_ringRecordSize;
	m_ringHead.store(head, std::memory_order_seq_cst);
	if (!m_threaded)
	{
		// Run in place, unless a record that is running submitted this one.
		if (!m_running)
			runRecords(head);
		return;
	}
	if (m_workerSleeping.load(std::memory_order_seq_cst))
	{
		std::lock_guard<std::mutex> lock(m_ringMutex);
		m_workerWake.notify_one();
	}
}

void Device::runRecords(uint64_t head)
{
	m_running = true;
	uint64_t tail = m_ringTail.load(std::memory_order_relaxed);
	while (tail != head)
	{
		@autoreleasepool
		{
			for (int n = 0; n < 512 && tail != head; ++n)
			{
				uint8_t* at = m_ring.get() + (size_t)(tail % m_ringSize);
				RecordHeader* header = reinterpret_cast<RecordHeader*>(at);
				const uint64_t size = header->size;
				if (header->run)
					header->run(this, at + sizeof(RecordHeader));
				tail += size;
				m_ringTail.store(tail, std::memory_order_release);
				if (!m_threaded)
					head = m_ringHead.load(std::memory_order_acquire);
			}
		}
		if (m_producerWaiting.load())
		{
			std::lock_guard<std::mutex> lock(m_ringMutex);
			m_producerWake.notify_all();
		}
	}
	m_running = false;
}

void Device::workerMain()
{
	pthread_setname_np("d3d8metal render");
	pthread_set_qos_class_self_np(QOS_CLASS_USER_INTERACTIVE, 0);
	for (;;)
	{
		uint64_t head = m_ringHead.load(std::memory_order_acquire);
		if (head == m_ringTail.load(std::memory_order_relaxed))
		{
			// Spin briefly before sleeping: the game thread usually submits again soon.
			for (int i = 0; i < 4000 && head == m_ringTail.load(std::memory_order_relaxed); ++i)
			{
				if (m_quit.load())
					return;
				if (i > 64)
					std::this_thread::yield();
				head = m_ringHead.load(std::memory_order_acquire);
			}
			if (head == m_ringTail.load(std::memory_order_relaxed))
			{
				std::unique_lock<std::mutex> lock(m_ringMutex);
				m_workerSleeping.store(true, std::memory_order_seq_cst);
				// Tell a game thread waiting in drain() that everything ran.
				m_producerWake.notify_all();
				m_workerWake.wait(lock, [&] {
					return m_quit.load() || m_ringHead.load(std::memory_order_seq_cst) != m_ringTail.load(std::memory_order_relaxed);
				});
				m_workerSleeping.store(false, std::memory_order_seq_cst);
				if (m_quit.load() && m_ringHead.load() == m_ringTail.load())
					return;
				continue;
			}
		}
		runRecords(head);
	}
}

void Device::drain()
{
	if (!m_threaded)
		return;
	const uint64_t head = m_ringHead.load(std::memory_order_seq_cst);
	for (int i = 0; m_ringTail.load(std::memory_order_acquire) != head; ++i)
	{
		if (i < 64)
			continue;
		if (i < 2000)
		{
			std::this_thread::yield();
			continue;
		}
		std::unique_lock<std::mutex> lock(m_ringMutex);
		m_producerWaiting.store(true);
		m_workerWake.notify_one();
		m_producerWake.wait_for(lock, std::chrono::milliseconds(1));
		m_producerWaiting.store(false);
	}
}

void Device::stopWorker()
{
	if (!m_threaded)
		return;
	drain();
	{
		std::lock_guard<std::mutex> lock(m_ringMutex);
		m_quit.store(true);
		m_workerWake.notify_one();
	}
	if (m_worker.joinable())
		m_worker.join();
	m_threaded = false;
}

//-----------------------------------------------------------------------------
// State changes
//-----------------------------------------------------------------------------
namespace
{
enum StateKind : uint8_t
{
	K_RENDER_STATE,
	K_STAGE_STATE,
	K_TRANSFORM,
	K_VIEWPORT,
	K_MATERIAL,
	K_LIGHT,
	K_LIGHT_ENABLE,
	K_CLIP_PLANE,
	K_VERTEX_SHADER,
	K_PIXEL_SHADER,
	K_VS_CONSTANTS,
	K_PS_CONSTANTS,
	K_TEXTURE,
};

template <class T> void put(std::vector<uint8_t>& out, const T& value)
{
	const size_t at = out.size();
	out.resize(at + sizeof(T));
	memcpy(out.data() + at, &value, sizeof(T));
}

void putBytes(std::vector<uint8_t>& out, const void* data, size_t size)
{
	const size_t at = out.size();
	out.resize(at + size);
	memcpy(out.data() + at, data, size);
}

template <class T> T get(const uint8_t*& p)
{
	T value;
	memcpy(&value, p, sizeof(T));
	p += sizeof(T);
	return value;
}
} // namespace

void Device::markRenderState(unsigned index)
{
	if (!m_renderStateDirty[index])
	{
		m_renderStateDirty[index] = true;
		m_dirtyRenderStates.push_back((uint16_t)index);
	}
}

void Device::markAllDirty()
{
	for (unsigned i = 0; i < 256; ++i)
		markRenderState(i);
	for (unsigned i = 0; i < MAX_STAGES * 32; ++i)
	{
		if (!m_stageStateDirty[i])
		{
			m_stageStateDirty[i] = true;
			m_dirtyStageStates.push_back((uint16_t)i);
		}
	}
	for (unsigned i = 0; i < 512; ++i)
	{
		if (!m_transformDirty[i])
		{
			m_transformDirty[i] = true;
			m_dirtyTransforms.push_back((uint16_t)i);
		}
	}
	m_dirtyMisc = ~0u;
	m_vsDirtyLo = 0;
	m_vsDirtyHi = 96;
	m_psDirtyLo = 0;
	m_psDirtyHi = 8;
}

void Device::syncState()
{
	if (m_dirtyRenderStates.empty() && m_dirtyStageStates.empty() && m_dirtyTransforms.empty() && m_dirtyMisc == 0
		&& m_vsDirtyLo >= m_vsDirtyHi && m_psDirtyLo >= m_psDirtyHi)
		return;

	std::vector<uint8_t>& out = m_deltaBuffer;
	out.clear();
	for (uint16_t i : m_dirtyRenderStates)
	{
		put<uint8_t>(out, K_RENDER_STATE);
		put<uint16_t>(out, i);
		put<DWORD>(out, m_front.renderStates[i]);
		m_renderStateDirty[i] = false;
	}
	for (uint16_t i : m_dirtyStageStates)
	{
		put<uint8_t>(out, K_STAGE_STATE);
		put<uint16_t>(out, i);
		put<DWORD>(out, m_front.stageStates[i / 32][i % 32]);
		m_stageStateDirty[i] = false;
	}
	for (uint16_t i : m_dirtyTransforms)
	{
		put<uint8_t>(out, K_TRANSFORM);
		put<uint16_t>(out, i);
		put<D3DMATRIX>(out, m_front.transforms[i]);
		m_transformDirty[i] = false;
	}
	m_dirtyRenderStates.clear();
	m_dirtyStageStates.clear();
	m_dirtyTransforms.clear();

	const uint32_t misc = m_dirtyMisc;
	m_dirtyMisc = 0;
	if (misc & DIRTY_VIEWPORT)
	{
		put<uint8_t>(out, K_VIEWPORT);
		put<D3DVIEWPORT8>(out, m_front.viewport);
	}
	if (misc & DIRTY_MATERIAL)
	{
		put<uint8_t>(out, K_MATERIAL);
		put<D3DMATERIAL8>(out, m_front.material);
	}
	if (misc & DIRTY_VERTEX_SHADER)
	{
		put<uint8_t>(out, K_VERTEX_SHADER);
		put<DWORD>(out, m_front.vertexShader);
	}
	if (misc & DIRTY_PIXEL_SHADER)
	{
		put<uint8_t>(out, K_PIXEL_SHADER);
		put<DWORD>(out, m_front.pixelShader);
	}
	for (unsigned i = 0; i < MAX_LIGHTS; ++i)
	{
		if (misc & (DIRTY_LIGHT0 << i))
		{
			put<uint8_t>(out, K_LIGHT);
			put<uint8_t>(out, (uint8_t)i);
			put<D3DLIGHT8>(out, m_front.lights[i]);
			put<uint8_t>(out, K_LIGHT_ENABLE);
			put<uint8_t>(out, (uint8_t)i);
			put<uint8_t>(out, m_front.lightEnabled[i] ? 1 : 0);
		}
	}
	for (unsigned i = 0; i < MAX_CLIP_PLANES; ++i)
	{
		if (misc & (DIRTY_CLIP0 << i))
		{
			put<uint8_t>(out, K_CLIP_PLANE);
			put<uint8_t>(out, (uint8_t)i);
			putBytes(out, m_front.clipPlanes[i], sizeof(float) * 4);
		}
	}
	for (unsigned i = 0; i < MAX_STAGES; ++i)
	{
		if (misc & (DIRTY_TEXTURE0 << i))
		{
			// The record holds a reference until the render thread takes it over.
			IDirect3DBaseTexture8* tex = m_front.textures[i];
			if (tex)
				tex->AddRef();
			put<uint8_t>(out, K_TEXTURE);
			put<uint8_t>(out, (uint8_t)i);
			put<IDirect3DBaseTexture8*>(out, tex);
		}
	}
	if (m_vsDirtyLo < m_vsDirtyHi)
	{
		put<uint8_t>(out, K_VS_CONSTANTS);
		put<uint16_t>(out, (uint16_t)m_vsDirtyLo);
		put<uint16_t>(out, (uint16_t)(m_vsDirtyHi - m_vsDirtyLo));
		putBytes(out, m_front.vsConstants[m_vsDirtyLo], (size_t)(m_vsDirtyHi - m_vsDirtyLo) * 16);
		m_vsDirtyLo = 96;
		m_vsDirtyHi = 0;
	}
	if (m_psDirtyLo < m_psDirtyHi)
	{
		put<uint8_t>(out, K_PS_CONSTANTS);
		put<uint16_t>(out, (uint16_t)m_psDirtyLo);
		put<uint16_t>(out, (uint16_t)(m_psDirtyHi - m_psDirtyLo));
		putBytes(out, m_front.psConstants[m_psDirtyLo], (size_t)(m_psDirtyHi - m_psDirtyLo) * 16);
		m_psDirtyLo = 8;
		m_psDirtyHi = 0;
	}

	const size_t size = out.size();
	uint8_t* payload = static_cast<uint8_t*>(reserveRecord(sizeof(uint64_t) + size));
	memcpy(payload, &size, sizeof(uint64_t));
	memcpy(payload + sizeof(uint64_t), out.data(), size);
	commitRecord([](Device* device, void* p) {
		uint64_t length;
		memcpy(&length, p, sizeof(uint64_t));
		device->applyState(static_cast<const uint8_t*>(p) + sizeof(uint64_t), (size_t)length);
	});
}

void Device::applyState(const uint8_t* p, size_t size)
{
	const uint8_t* end = p + size;
	DeviceState& s = m_state;
	while (p < end)
	{
		switch (get<uint8_t>(p))
		{
		case K_RENDER_STATE:
		{
			const uint16_t i = get<uint16_t>(p);
			const DWORD value = get<DWORD>(p);
			if (i == RS_SOFT_PARTICLES && value != 0 && s.renderStates[i] == 0)
				m_softDepthValid = false; // the scene may have changed since the last copy
			s.renderStates[i] = value;
			break;
		}
		case K_STAGE_STATE:
		{
			const uint16_t i = get<uint16_t>(p);
			s.stageStates[i / 32][i % 32] = get<DWORD>(p);
			break;
		}
		case K_TRANSFORM:
		{
			const uint16_t i = get<uint16_t>(p);
			s.transforms[i] = get<D3DMATRIX>(p);
			break;
		}
		case K_VIEWPORT: s.viewport = get<D3DVIEWPORT8>(p); break;
		case K_MATERIAL: s.material = get<D3DMATERIAL8>(p); break;
		case K_VERTEX_SHADER: s.vertexShader = get<DWORD>(p); break;
		case K_PIXEL_SHADER: s.pixelShader = get<DWORD>(p); break;
		case K_LIGHT:
		{
			const uint8_t i = get<uint8_t>(p);
			s.lights[i] = get<D3DLIGHT8>(p);
			break;
		}
		case K_LIGHT_ENABLE:
		{
			const uint8_t i = get<uint8_t>(p);
			s.lightEnabled[i] = get<uint8_t>(p) != 0;
			break;
		}
		case K_CLIP_PLANE:
		{
			const uint8_t i = get<uint8_t>(p);
			memcpy(s.clipPlanes[i], p, sizeof(float) * 4);
			p += sizeof(float) * 4;
			break;
		}
		case K_TEXTURE:
		{
			const uint8_t i = get<uint8_t>(p);
			IDirect3DBaseTexture8* tex = get<IDirect3DBaseTexture8*>(p);
			IDirect3DBaseTexture8* old = s.textures[i];
			s.textures[i] = tex; // takes over the record's reference
			if (old)
				old->Release();
			break;
		}
		case K_VS_CONSTANTS:
		{
			const uint16_t first = get<uint16_t>(p);
			const uint16_t count = get<uint16_t>(p);
			memcpy(s.vsConstants[first], p, (size_t)count * 16);
			p += (size_t)count * 16;
			++m_vsConstantsVersion;
			break;
		}
		case K_PS_CONSTANTS:
		{
			const uint16_t first = get<uint16_t>(p);
			const uint16_t count = get<uint16_t>(p);
			memcpy(s.psConstants[first], p, (size_t)count * 16);
			p += (size_t)count * 16;
			++m_psConstantsVersion;
			break;
		}
		default:
			fprintf(stderr, "d3d8metal: corrupt state record\n");
			return;
		}
	}
}

//-----------------------------------------------------------------------------
// Resource tracking on the game thread
//-----------------------------------------------------------------------------
void Device::markDrawResources()
{
	for (unsigned i = 0; i < MAX_STAGES; ++i)
	{
		IDirect3DBaseTexture8* tex = m_front.textures[i];
		if (tex == nullptr)
			continue;
		TextureStorage* storage = nullptr;
		if (tex->GetType() == D3DRTYPE_CUBETEXTURE)
			storage = static_cast<CubeTexture*>(tex)->m_storage.get();
		else
			storage = static_cast<Texture*>(tex)->m_storage.get();
		if (storage)
			storage->lastUsedSerial = m_currentSerial;
	}
	if (m_frontRenderTarget)
	{
		TextureStorage& rt = *m_frontRenderTarget->m_storage;
		rt.lastUsedSerial = m_currentSerial;
		rt.shadowStale = true;
	}
}

void Device::afterFlush()
{
	if (m_transientCurrent)
	{
		m_retiredTransient.push_back({ m_currentSerial, m_transientCurrent });
		m_transientCurrent = nil;
		m_transientOffset = 0;
	}
	++m_currentSerial;

	// Recycle buffers whose GPU use has completed.
	const uint64_t done = m_completedSerial.load();
	auto recycle = [done](std::vector<std::pair<uint64_t, id<MTLBuffer>>>& list, const std::function<void(id<MTLBuffer>)>& reuse) {
		size_t keep = 0;
		for (size_t i = 0; i < list.size(); ++i)
		{
			if (list[i].first <= done)
				reuse(list[i].second);
			else
				list[keep++] = list[i];
		}
		list.resize(keep);
	};
	recycle(m_retiredTransient, [this](id<MTLBuffer> b) { m_transientBuffers.push_back(b); });
	recycle(m_retiredBuffers, [this](id<MTLBuffer> b) { releaseBuffer(b); });
}

} // namespace d3d8metal

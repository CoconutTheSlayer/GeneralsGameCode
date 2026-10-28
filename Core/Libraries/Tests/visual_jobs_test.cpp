#include "rts/visual_sort.h"
#include <atomic>
#include <chrono>
#include <cstdio>
#include <cstring>
#include <limits>


struct Item { unsigned id; float z; };
bool operator<(const Item& a, const Item& b) { return a.z < b.z; }
bool operator>(const Item& a, const Item& b) { return a.z > b.z; }
// Frozen original WW3D algorithm: checks exact equal-depth order, not just sorted keys.
namespace original {
static
void InsertionSort(Item *begin, Item *end)
{
	for (Item *iter = begin + 1; iter < end; ++iter) {
		Item val = iter[0];
		Item *insert = iter;
		while (insert != begin && insert[-1] > val) {
			insert[0] = insert[-1];
			insert -= 1;
		}
		insert[0] = val;
	}
}

// ----------------------------------------------------------------------------
static
void Sort(Item *begin, Item *end)
{
	const int diff = end - begin;
	if (diff <= 16) {
		// Insertion sort has less overhead for small arrays
		InsertionSort(begin, end);
	} else {
		// Choose the median of begin, mid, and (end - 1) as the partitioning element.
		// Rearrange so that *(begin + 1) <= *begin <= *(end - 1).  These will be guard
		// elements.
		Item *mid = begin + diff/2;
		std::swap(mid[0], begin[1]);
		if (begin[1] > end[-1]) {
			std::swap(begin[1], end[-1]);
		}
		if (begin[0] > end[-1]) {
			std::swap(begin[0], end[-1]);
		}
		if (begin[1] > begin[0]) {
			std::swap(begin[1], begin[0]);
		}

		// *begin is now the partitioning element
		Item *begin1 = begin + 1;	// TODO: Temp fix until I find out who is passing me NaN
		Item *end1 = end - 1;			// TODO: Temp fix until I find out who is passing me NaN
		Item *left = begin + 1;
		Item *right = end - 1;
		for (;;) {
#if 0		// TODO: Temp fix until I find out who is passing me NaN.
			do ++left; while (left[0] < begin[0]);		// Scan up to find element >= than partition
			do --right; while (right[0] > begin[0]);	// Scan down to find element <= than partition
#else
			do ++left; while (left < end1 && left[0] < begin[0]);		// Scan up to find element >= than partition
			do --right; while (right > begin1 && right[0] > begin[0]);	// Scan down to find element <= than partition
#endif
			if (right < left) break;									// Pointers crossed.  Partitioning completed.
			std::swap(left[0], right[0]);							// Exchange elements.
		}
		std::swap(begin[0], right[0]);							// Insert partition element

		// Sort the smaller subarray first then the larger
		if (right - begin > end - (right + 1)) {
			Sort(right + 1, end);
			Sort(begin, right);
		} else {
			Sort(begin, right);
			Sort(right + 1, end);
		}
	}
}

}
static void require(bool condition) { if (!condition) { fputs("visual jobs test failed\n", stderr); std::abort(); } }
int main(int argc, char** argv) {
    if (argc == 2) { setenv("GENERALS_PROFILE", argv[1], 1); setenv("GENERALS_PROFILE_MODE", "cpu", 1); }
    RTS_BENCH_BEGIN_FRAME(200);
    const auto caller = std::this_thread::get_id();
    std::atomic<unsigned> otherThread{0};
    for (unsigned batch = 0; batch < 64; ++batch) {
        const size_t count = batch * 193;
        std::vector<std::atomic<unsigned>> visits(count);
        std::vector<size_t> values(count);
        rts_visual::parallelFor(count, 16, "test.visual_jobs", [&](size_t i) {
            ++visits[i]; values[i] = i*i + batch;
            if (std::this_thread::get_id() != caller) ++otherThread;
        });
        for (size_t i = 0; i < count; ++i) require(visits[i] == 1 && values[i] == i*i + batch);
    }
    // Make scheduling observable even on machines where the caller can finish tiny jobs first.
    rts_visual::parallelFor(32, 1, "test.scheduling", [&](size_t) {
        if (std::this_thread::get_id() != caller) ++otherThread;
        std::this_thread::sleep_for(std::chrono::microseconds(100));
    });
    require(!rts_visual::workerCount() || otherThread > 0);
    unsigned seed = 1729;
    auto random = [&] { seed = seed * 1664525u + 1013904223u; return seed; };
    unsigned sorts = 0;
    for (size_t n : {1, 2, 16, 17, 4095, 4096, 8192, 16384, 32768}) {
        for (unsigned pattern = 0; pattern < 5; ++pattern) {
            std::vector<Item> reference(n);
            for (size_t i = 0; i < n; ++i) {
                const float value = pattern == 0 ? float(random()%37) : pattern == 1 ? 1.f :
                    pattern == 2 ? float(i) : pattern == 3 ? float(n-i) :
                    i%17 == 0 ? std::numeric_limits<float>::quiet_NaN() : float(random()%97);
                reference[i] = {unsigned(i), value};
            }
            auto candidate = reference;
            original::Sort(reference.data(), reference.data()+n);
            rts_visual_sort::parallelSort(candidate.data(), candidate.data()+n);
            require(!std::memcmp(reference.data(), candidate.data(), n*sizeof(Item)));
            ++sorts;
        }
    }
    RTS_BENCH_END_FRAME();
    std::printf("64 job batches, %u sort cases passed; %u workers, %u jobs on other threads\n", sorts, rts_visual::workerCount(), otherThread.load());
}

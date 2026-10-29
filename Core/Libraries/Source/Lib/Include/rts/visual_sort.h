// Original WW3D triangle quicksort, with disjoint partitions available to visual
// workers. Keeping the same partitions and comparisons preserves equal-depth order.
#pragma once
#include <algorithm>
#include <utility>
#include <vector>
#include "rts/visual_jobs.h"
namespace rts_visual_sort {
template<class T>
void insertionSort(T *begin, T *end)
{
	if (end - begin < 2) return;
	for (T *iter = begin + 1; iter < end; ++iter) {
		T val = iter[0];
		T *insert = iter;
		while (insert != begin && insert[-1] > val) {
			insert[0] = insert[-1];
			insert -= 1;
		}
		insert[0] = val;
	}
}

// ----------------------------------------------------------------------------
template<class T>
void sort(T *begin, T *end, unsigned splitDepth = 0, std::vector<std::pair<T*, T*>>* ranges = nullptr)
{
	const int diff = end - begin;
	if (diff <= 16) {
		// Insertion sort has less overhead for small arrays
		insertionSort(begin, end);
	} else {
        if (ranges && splitDepth == 0) { ranges->emplace_back(begin, end); return; }
		// Choose the median of begin, mid, and (end - 1) as the partitioning element.
		// Rearrange so that *(begin + 1) <= *begin <= *(end - 1).  These will be guard
		// elements.
		T *mid = begin + diff/2;
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
		T *begin1 = begin + 1;	// TODO: Temp fix until I find out who is passing me NaN
		T *end1 = end - 1;			// TODO: Temp fix until I find out who is passing me NaN
		T *left = begin + 1;
		T *right = end - 1;
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
			sort(right + 1, end, splitDepth ? splitDepth - 1 : 0, ranges);
			sort(begin, right, splitDepth ? splitDepth - 1 : 0, ranges);
		} else {
			sort(begin, right, splitDepth ? splitDepth - 1 : 0, ranges);
			sort(right + 1, end, splitDepth ? splitDepth - 1 : 0, ranges);
		}
	}
}


template<class T> void parallelSort(T* begin, T* end) {
    if (end - begin < 4096 || !rts_visual::workerCount()) { sort(begin, end); return; }
    std::vector<std::pair<T*, T*>> ranges;
    ranges.reserve(8);
    sort(begin, end, 3, &ranges);
    rts_visual::parallelFor(ranges.size(), 1, "particles.depth_sort", [&](size_t i) {
        sort(ranges[i].first, ranges[i].second);
    });
}
} // namespace rts_visual_sort

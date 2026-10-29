#pragma once

#include <array>
#include <cstdint>
#include <memory>

namespace rts {
// Auxiliary index for a stable sorted list with 16-bit costs. Each occupied cost
// points to its LAST node, so predecessor() inserts after all equal-cost nodes.
// Three bitmap levels replace a linear list walk; the list itself remains intact.
template<class Node> class CostBucketIndex {
public:
    CostBucketIndex() : tails_(new Node*[65536]) {}
    CostBucketIndex(const CostBucketIndex&) = delete;
    CostBucketIndex& operator=(const CostBucketIndex&) = delete;

    Node* tail(uint16_t cost) const {
        return words_[cost / 64] & (uint64_t(1) << (cost % 64)) ? tails_[cost] : nullptr;
    }
    Node* predecessor(uint16_t cost) const {
        unsigned word = cost / 64;
        uint64_t bits = words_[word] & (~uint64_t(0) >> (63 - cost % 64));
        if (bits) return tails_[word * 64 + highest(bits)];
        unsigned group = word / 64;
        bits = groups_[group] & below(word % 64);
        if (!bits) {
            const uint64_t groups = top_ & below(group);
            if (!groups) return nullptr;
            group = highest(groups);
            bits = groups_[group];
        }
        word = group * 64 + highest(bits);
        return tails_[word * 64 + highest(words_[word])];
    }
    void setTail(uint16_t cost, Node* node) {
        tails_[cost] = node;
        const unsigned word = cost / 64, group = word / 64;
        words_[word] |= uint64_t(1) << (cost % 64);
        groups_[group] |= uint64_t(1) << (word % 64);
        top_ |= uint64_t(1) << group;
    }
    void erase(uint16_t cost) {
        const unsigned word = cost / 64, group = word / 64;
        words_[word] &= ~(uint64_t(1) << (cost % 64));
        if (!words_[word]) {
            groups_[group] &= ~(uint64_t(1) << (word % 64));
            if (!groups_[group]) top_ &= ~(uint64_t(1) << group);
        }
    }
    void clear() {
        // Only touch occupied bitmap words; stale tail entries cannot be read
        // while their presence bits are clear. No half-megabyte memset per path.
        while (top_) {
            const unsigned group = highest(top_);
            uint64_t bits = groups_[group];
            while (bits) {
                const unsigned bit = highest(bits);
                words_[group * 64 + bit] = 0;
                bits &= ~(uint64_t(1) << bit);
            }
            groups_[group] = 0;
            top_ &= ~(uint64_t(1) << group);
        }
    }
private:
    static unsigned highest(uint64_t bits) { return 63u - unsigned(__builtin_clzll(bits)); }
    static uint64_t below(unsigned bit) { return (uint64_t(1) << bit) - 1; }
    std::unique_ptr<Node*[]> tails_;
    std::array<uint64_t, 1024> words_{};
    std::array<uint64_t, 16> groups_{};
    uint64_t top_ = 0;
};
} // namespace rts

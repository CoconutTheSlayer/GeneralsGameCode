#include <rts/cost_bucket_index.h>
#include <algorithm>
#include <cassert>
#include <cstdio>
#include <map>
#include <vector>

// Assertions stay enabled for this test target even in Release builds.
int main()
{
    uint32_t randomState = 0x5147;
    auto random = [&]() {
        randomState ^= randomState << 13;
        randomState ^= randomState >> 17;
        randomState ^= randomState << 5;
        return randomState;
    };
    std::vector<int> nodes(65536);
    rts::CostBucketIndex<int> index;
    std::map<uint16_t, int*> reference;
    auto check = [&](uint16_t cost) {
        auto it = reference.upper_bound(cost);
        int* expected = it == reference.begin() ? nullptr : std::prev(it)->second;
        assert(index.predecessor(cost) == expected);
        it = reference.find(cost);
        assert(index.tail(cost) == (it == reference.end() ? nullptr : it->second));
    };
    const uint16_t edges[] = {0,1,62,63,64,65,127,128,4094,4095,4096,4097,65534,65535};
    for (auto cost : edges) { index.setTail(cost, &nodes[cost]); reference[cost] = &nodes[cost]; }
    for (unsigned cost = 0; cost < 65536; ++cost) check(cost);
    for (auto cost : edges) { index.erase(cost); reference.erase(cost); for (auto c : edges) check(c); }
    for (int op = 0; op < 100000; ++op) {
        uint16_t cost = random();
        switch (random() % 8) {
        case 0: index.erase(cost); reference.erase(cost); break;
        case 1:
            if (op % 1000 == 0) { index.clear(); reference.clear(); }
            break;
        default: index.setTail(cost, &nodes[op % nodes.size()]); reference[cost] = &nodes[op % nodes.size()];
        }
        check(cost); check(random());
    }
    for (unsigned cost = 0; cost < 65536; ++cost) check(cost);
    index.clear(); reference.clear();
    for (unsigned cost = 0; cost < 65536; ++cost) check(cost);

    struct Node { uint16_t cost = 0, insertedCost = 0; Node *prev = nullptr, *next = nullptr; bool present = false; };
    std::vector<Node> cells(512);
    rts::CostBucketIndex<Node> queue;
    Node* head = nullptr;
    std::vector<Node*> ordered;
    auto insert = [&](Node* node) {
        Node* prev = queue.predecessor(node->cost);
        Node* next = prev ? prev->next : head;
        node->prev = prev; node->next = next;
        if (prev) prev->next = node; else head = node;
        if (next) next->prev = node;
        node->insertedCost = node->cost;
        queue.setTail(node->cost, node);
        node->present = true;
        ordered.insert(std::upper_bound(ordered.begin(), ordered.end(), node->cost,
            [](uint16_t cost, const Node* other) { return cost < other->insertedCost; }), node);
    };
    auto remove = [&](Node* node) {
        const auto cost = node->insertedCost;
        if (queue.tail(cost) == node) {
            if (node->prev && node->prev->insertedCost == cost) queue.setTail(cost, node->prev);
            else queue.erase(cost);
        }
        if (node->prev) node->prev->next = node->next; else head = node->next;
        if (node->next) node->next->prev = node->prev;
        node->prev = node->next = nullptr; node->present = false;
        ordered.erase(std::find(ordered.begin(), ordered.end(), node));
    };
    for (int op = 0; op < 100000; ++op) {
        Node* node = &cells[random() % cells.size()];
        node->cost = random() % 3 ? random() % 32 : uint16_t(random()); // many equal-cost ties
        if (node->present) remove(node); // total cost has ALREADY changed, as in the game
        if (random() % 4) insert(node);
        Node* cursor = head;
        Node* previous = nullptr;
        for (Node* expected : ordered) {
            assert(cursor == expected && cursor->prev == previous);
            previous = cursor; cursor = cursor->next;
        }
        assert(cursor == nullptr);
        if (op % 5000 == 0) {
            queue.clear(); head = nullptr; ordered.clear();
            for (auto& cell : cells) cell = Node{};
        }
    }
    std::puts("Cost index: 100000 map operations, full 16-bit boundaries, and 100000 stable queue operations passed");
}

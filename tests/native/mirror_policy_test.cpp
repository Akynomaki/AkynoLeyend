#include "mirror_policy.h"
#include <cassert>
int main() {
    constexpr uint64_t g = 1ull << 30;
    using mkwvk::default_mirror_budget;
    assert(default_mirror_budget(0) == 3 * g);
    assert(default_mirror_budget(4 * g) == g / 2);
    assert(default_mirror_budget(6 * g) == 3 * g / 4);
    assert(default_mirror_budget(8 * g) == 2 * g);
    assert(default_mirror_budget(12 * g) == g);
    assert(default_mirror_budget(12 * g + (512ull << 20)) == g);
    assert(default_mirror_budget(16 * g) == 3 * g);
    assert(default_mirror_budget(24 * g) == 3 * g);
}

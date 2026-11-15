// The write-back shadows' rules near the VRAM limit (gpu/vk/vram_pressure.h): no game, no GPU.
#include "../gpu/vk/vram_pressure.h"

#include <cstdio>
#include <cstdlib>

#define CHECK(x) do { if (!(x)) { std::fprintf(stderr, "FAIL:%d %s\n", __LINE__, #x); std::exit(1); } } while (0)

using mkwvk::vram_pressure::allocated;
using mkwvk::vram_pressure::shadow_fits;
using mkwvk::vram_pressure::shadow_reuse_fits;
using mkwvk::vram_pressure::shadows_go;

int main() {
    const uint64_t MB = 1 << 20;
    CHECK(allocated(10462 * MB, 3472 * MB) == 6990 * MB);
    CHECK(allocated(100 * MB, 300 * MB) == 0);                // (never below nothing)
    CHECK(allocated(500 * MB, 0) == 500 * MB);
    // (a player's log, an RTX 4070 SUPER with the texture cache full: 10,462 of 10,732 MB used, 97.5% by the count)
    CHECK(!shadows_go(10462 * MB, 10732 * MB, 3472 * MB));    // (3.5 GB of it free inside the blocks: they stay)
    CHECK(!shadows_go(10462 * MB, 10732 * MB, 300 * MB));     // (94.7% really allocated)
    CHECK(shadows_go(10462 * MB, 10732 * MB, 0));             // (97.5% really allocated: they go)
    CHECK(!shadows_go(10650 * MB, 10732 * MB, 3472 * MB));   // Near the reported limit with actual headroom.
    CHECK(!shadows_go(11376 * MB, 11176 * MB, 3467 * MB));   // Recorded RTX 5070 Ti Laptop session.
    CHECK(shadows_go(11410 * MB, 11176 * MB, 3467 * MB));    // More than 2% over the raw budget.
    CHECK(!shadows_go(10462 * MB, 0, 0));                     // (no budget known: nothing to judge by)
    CHECK(!shadows_go(0, 10732 * MB, 0));
    // (a shadow is made only where, with it, the textures' own lines are not passed: 90% really allocated, a 97% count)
    CHECK(shadow_fits(32 * MB, 9700 * MB, 10732 * MB, 1600 * MB));     // (75.8% really allocated, a 90.7% count)
    CHECK(shadow_fits(32 * MB, 9500 * MB, 10732 * MB, 0));             // (88.8% really allocated with it)
    CHECK(!shadow_fits(32 * MB, 9700 * MB, 10732 * MB, 0));            // (90.7% really allocated with it: the textures' line)
    CHECK(!shadow_fits(32 * MB, 10400 * MB, 10732 * MB, 3472 * MB));   // (the count would pass 97%)
    CHECK(shadow_fits(32 * MB, 10300 * MB, 10732 * MB, 3472 * MB));    // (96.3% with it)
    CHECK(shadow_fits(32 * MB, 10462 * MB, 0, 0));                     // (no budget known)
    // (given back and made again do not chase each other: what goes at 95% really allocated only fits again at 90%)
    const uint64_t allowed = 10000 * MB, shadows = 400 * MB;
    CHECK(shadows_go(9600 * MB, allowed, 0));
    CHECK(!shadow_fits(shadows, 9600 * MB - shadows, allowed, 0));     // (9,200 + 400 MB: back at 96%)
    CHECK(!shadow_fits(shadows, 8700 * MB, allowed, 0));               // (and not at 91% either)
    CHECK(shadow_fits(shadows, 8600 * MB, allowed, 0));
    CHECK(!shadow_fits(2 * MB, 11376 * MB, 11176 * MB, 3467 * MB));
    CHECK(shadow_reuse_fits(2 * MB, 11376 * MB, 11176 * MB, 3467 * MB));
    CHECK(!shadow_reuse_fits(2 * MB, 11410 * MB, 11176 * MB, 3467 * MB));
    CHECK(!shadow_reuse_fits(2 * MB, 11376 * MB, 11176 * MB, 0));
    CHECK(!shadow_reuse_fits(2 * MB, 9850 * MB, allowed, 500 * MB));
    CHECK(!shadow_reuse_fits(2 * MB, 11376 * MB, 0, 3467 * MB));
    std::printf("PASS: the shadows go by what is really allocated\n");
    return 0;
}

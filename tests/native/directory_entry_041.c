#include <assert.h>
#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "nn_fs_directory_entry.h"

static void check(int is_dir, unsigned expected) {
    uint8_t entry[0x310];
    memset(entry, 0xa5, sizeof entry);
    /* Directory listing must leave unrelated name/padding and size unchanged. */
    uint8_t before[0x310];
    memcpy(before, entry, sizeof before);
    hos_fs_directory_entry_set_type(entry, is_dir);
    assert(entry[0x304] == expected);
    for (size_t i = 0; i < sizeof entry; ++i)
        if (i != 0x304) assert(entry[i] == before[i]);
    assert(entry[0x302] == 0xa5);
    assert(entry[0x308] == 0xa5);
}

int main(void) {
    check(0, 1);     /* regular on-disk files */
    check(1, 0);     /* normal directories */
    check(0, 1);     /* extra mod files use same production helper */
    check(1, 0);     /* extra mod directories */
    puts("DirectoryEntry guest ABI checks passed");
    return 0;
}

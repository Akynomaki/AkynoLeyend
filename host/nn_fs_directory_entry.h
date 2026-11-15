/* nn::fs DirectoryEntry wire ABI (0x310 bytes).
 * Layout established by Hookshot/NotRexed foliage fix (November 2026).
 * Keep byte 0x304 as the entry type; the old 0x302 position made files
 * appear as directories to guest code and prevented foliage from loading.
 * No game files or generated code are included.
 */
#ifndef HOS_NN_FS_DIRECTORY_ENTRY_H
#define HOS_NN_FS_DIRECTORY_ENTRY_H

#include <stddef.h>
#include <stdint.h>

typedef struct HosDirectoryEntryWire {
    char name[0x301];
    uint8_t reserved_name[3];
    uint8_t type;  /* 0 = directory, 1 = regular file */
    uint8_t reserved_type[3];
    uint64_t size;
} HosDirectoryEntryWire;

#if defined(__cplusplus)
static_assert(offsetof(HosDirectoryEntryWire, type) == 0x304, "DirectoryEntry.type ABI");
static_assert(offsetof(HosDirectoryEntryWire, size) == 0x308, "DirectoryEntry.size ABI");
static_assert(sizeof(HosDirectoryEntryWire) == 0x310, "DirectoryEntry ABI size");
#else
_Static_assert(offsetof(HosDirectoryEntryWire, type) == 0x304, "DirectoryEntry.type ABI");
_Static_assert(offsetof(HosDirectoryEntryWire, size) == 0x308, "DirectoryEntry.size ABI");
_Static_assert(sizeof(HosDirectoryEntryWire) == 0x310, "DirectoryEntry ABI size");
#endif

static inline void hos_fs_directory_entry_set_type(void *guest_entry, int is_directory) {
    uint8_t *bytes = (uint8_t *)guest_entry;
    bytes[offsetof(HosDirectoryEntryWire, type)] = is_directory ? 0u : 1u;
}

#endif

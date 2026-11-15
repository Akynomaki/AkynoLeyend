#pragma once
#include <stddef.h>
#include <stdio.h>

/* A full host path, including a deep extraction root and a guest asset name.
   Reject overflow instead of opening a silently truncated resource name. */
#define HOS_FS_PATH_CAP 4096
static inline int hos_path_join(char *out, size_t cap, const char *root, const char *relative) {
    if (!out || !cap || !root || !relative) return 0;
    const int n = snprintf(out, cap, "%s/%s", root, relative);
    if (n < 0 || (size_t)n >= cap) {
        out[0] = 0;
        return 0;
    }
    return 1;
}

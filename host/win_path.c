/* Long-path Win32 adapters for the guest filesystem. The runtime keeps UTF-8
   asset names; Windows receives normalized, extended UTF-16 absolute paths. */
#include "win_path.h"
#include <stdlib.h>
#include <string.h>
#include <wchar.h>

static void free_path(WCHAR *p) {
    const DWORD error = GetLastError();
    free(p);
    SetLastError(error);
}

static WCHAR *wide_path(const char *path) {
    if (!path || !*path) { SetLastError(ERROR_INVALID_NAME); return NULL; }
    UINT page = CP_UTF8;
    DWORD flags = MB_ERR_INVALID_CHARS;
    int count = MultiByteToWideChar(page, flags, path, -1, NULL, 0);
    if (!count) { /* main's legacy argv can still be encoded in the active code page */
        page = CP_ACP;
        flags = 0;
        count = MultiByteToWideChar(page, flags, path, -1, NULL, 0);
    }
    if (!count) return NULL;
    WCHAR *input = (WCHAR *)malloc((size_t)count * sizeof *input);
    if (!input) { SetLastError(ERROR_NOT_ENOUGH_MEMORY); return NULL; }
    if (!MultiByteToWideChar(page, flags, path, -1, input, count)) { free_path(input); return NULL; }
    for (WCHAR *p = input; *p; ++p) if (*p == L'/') *p = L'\\';
    if (!wcsncmp(input, L"\\\\?\\", 4)) return input;
    const DWORD required = GetFullPathNameW(input, 0, NULL, NULL);
    if (!required || required > 32760) {
        if (required) SetLastError(ERROR_FILENAME_EXCED_RANGE);
        free_path(input);
        return NULL;
    }
    WCHAR *full = (WCHAR *)malloc((size_t)required * sizeof *full);
    WCHAR *result = (WCHAR *)malloc(((size_t)required + 8) * sizeof *result);
    if (!full || !result) {
        free(full); free(result); free(input);
        SetLastError(ERROR_NOT_ENOUGH_MEMORY);
        return NULL;
    }
    const DWORD got = GetFullPathNameW(input, required, full, NULL);
    free_path(input);
    if (!got || got >= required) {
        free_path(full); free_path(result);
        if (got >= required) SetLastError(ERROR_FILENAME_EXCED_RANGE);
        return NULL;
    }
    if (!wcsncmp(full, L"\\\\", 2)) {
        wcscpy(result, L"\\\\?\\UNC\\");
        wcscpy(result + 8, full + 2);
    } else {
        wcscpy(result, L"\\\\?\\");
        wcscpy(result + 4, full);
    }
    free_path(full);
    return result;
}

HANDLE hos_path_open(const char *path, DWORD access, DWORD share, LPSECURITY_ATTRIBUTES security,
                     DWORD creation, DWORD flags, HANDLE template_file) {
    WCHAR *wide = wide_path(path);
    if (!wide) return INVALID_HANDLE_VALUE;
    HANDLE handle = CreateFileW(wide, access, share, security, creation, flags, template_file);
    free_path(wide);
    return handle;
}
FILE *hos_path_fopen(const char *path, const char *mode) {
    WCHAR *wide=wide_path(path), wmode[16];
    if (!wide) return NULL;
    if (!MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,mode,-1,wmode,16)) { free_path(wide);return NULL; }
    FILE *file=_wfopen(wide,wmode);
    free_path(wide);
    return file;
}
DWORD hos_path_attributes(const char *path) {
    WCHAR *wide = wide_path(path);
    if (!wide) return INVALID_FILE_ATTRIBUTES;
    DWORD attributes = GetFileAttributesW(wide);
    free_path(wide);
    return attributes;
}
BOOL hos_path_mkdir(const char *path, LPSECURITY_ATTRIBUTES security) {
    WCHAR *wide = wide_path(path);
    if (!wide) return FALSE;
    BOOL ok = CreateDirectoryW(wide, security);
    free_path(wide);
    return ok;
}
BOOL hos_path_delete_file(const char *path) {
    WCHAR *wide = wide_path(path);
    if (!wide) return FALSE;
    BOOL ok = DeleteFileW(wide);
    free_path(wide);
    return ok;
}
BOOL hos_path_remove_dir(const char *path) {
    WCHAR *wide = wide_path(path);
    if (!wide) return FALSE;
    BOOL ok = RemoveDirectoryW(wide);
    free_path(wide);
    return ok;
}
BOOL hos_path_move_file(const char *from, const char *to, DWORD flags) {
    WCHAR *wide_from = wide_path(from);
    if (!wide_from) return FALSE;
    WCHAR *wide_to = wide_path(to);
    if (!wide_to) { free_path(wide_from); return FALSE; }
    BOOL ok = MoveFileExW(wide_from, wide_to, flags);
    free_path(wide_from); free_path(wide_to);
    return ok;
}
static BOOL find_data(const WIN32_FIND_DATAW *wide, WIN32_FIND_DATAA *out) {
    memset(out, 0, sizeof *out);
    out->dwFileAttributes = wide->dwFileAttributes;
    out->ftCreationTime = wide->ftCreationTime;
    out->ftLastAccessTime = wide->ftLastAccessTime;
    out->ftLastWriteTime = wide->ftLastWriteTime;
    out->nFileSizeHigh = wide->nFileSizeHigh;
    out->nFileSizeLow = wide->nFileSizeLow;
    out->dwReserved0 = wide->dwReserved0;
    out->dwReserved1 = wide->dwReserved1;
    return WideCharToMultiByte(CP_UTF8, 0, wide->cFileName, -1, out->cFileName, sizeof out->cFileName, NULL, NULL) != 0;
}
HANDLE hos_path_find_first(const char *path, WIN32_FIND_DATAA *out) {
    WCHAR *wide = wide_path(path);
    if (!wide) return INVALID_HANDLE_VALUE;
    WIN32_FIND_DATAW data;
    HANDLE handle = FindFirstFileW(wide, &data);
    free_path(wide);
    if (handle != INVALID_HANDLE_VALUE && !find_data(&data, out)) {
        const DWORD error = GetLastError();
        FindClose(handle);
        SetLastError(error);
        return INVALID_HANDLE_VALUE;
    }
    return handle;
}
BOOL hos_path_find_next(HANDLE handle, WIN32_FIND_DATAA *out) {
    WIN32_FIND_DATAW data;
    return FindNextFileW(handle, &data) && find_data(&data, out);
}

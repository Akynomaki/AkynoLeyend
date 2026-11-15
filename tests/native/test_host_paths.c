/* Regression: a 160-byte extraction root plus a real relative lighting name
   exceeded the old 260-byte buffer. Windows additionally exercises the wide
   filesystem adapters with real create/read/find/rename/delete operations. */
#include "path_join.h"
#include <stdlib.h>
#include <string.h>
#ifdef _WIN32
#include "win_path.h"
#endif

#define CHECK(x) do { if (!(x)) { fprintf(stderr, "path check failed, line %d: %s\n", __LINE__, #x); return 1; } } while (0)

int main(void) {
    char root[161] = "C:\\";
    memset(root + 3, 'r', 157);
    root[160] = 0;
    const char *relative = "System/GameGraphics/LocationalLightMgrInitializeParam/Main.game__gfx__LocationalLightMgrInitializeParam.bgyml";
    char legacy[260], full[HOS_FS_PATH_CAP];
    CHECK(snprintf(legacy, sizeof legacy, "%s/%s", root, relative) >= (int)sizeof legacy);
    CHECK(hos_path_join(full, sizeof full, root, relative));
    CHECK(strlen(full) == strlen(root) + 1 + strlen(relative));
    CHECK(!strcmp(full + strlen(root) + 1, relative));
    char small[8] = "marker";
    CHECK(!hos_path_join(small, sizeof small, root, relative) && small[0] == 0);
    CHECK(hos_path_join(small, sizeof small, "abc", "def") && !strcmp(small, "abc/def"));
    CHECK(!hos_path_join(small, sizeof small, "abcd", "def") && small[0] == 0);
    CHECK(!hos_path_join(NULL, 1, "a", "b"));
    CHECK(!hos_path_join(small, 0, "a", "b"));
#ifdef _WIN32
    WCHAR wide_temp[HOS_FS_PATH_CAP];
    char temporary[HOS_FS_PATH_CAP], base[HOS_FS_PATH_CAP], dirs[3][HOS_FS_PATH_CAP];
    CHECK(GetTempPathW(HOS_FS_PATH_CAP, wide_temp) > 0);
    CHECK(WideCharToMultiByte(CP_UTF8, 0, wide_temp, -1, temporary, sizeof temporary, NULL, NULL));
    char unique[96];
    snprintf(unique, sizeof unique, "akynoleyend-path-test-%lu-%llu", GetCurrentProcessId(), GetTickCount64());
    CHECK(hos_path_join(base, sizeof base, temporary, unique));
    CHECK(hos_path_mkdir(base, NULL));
    char component[100];
    memset(component, 'p', 90);
    component[90] = 0;
    for (int i = 0; i < 3; ++i) {
        component[0] = (char)('a' + i);
        CHECK(hos_path_join(dirs[i], sizeof dirs[i], i ? dirs[i-1] : base, component));
        CHECK(hos_path_mkdir(dirs[i], NULL));
    }
    CHECK(hos_path_join(full, sizeof full, dirs[2], "ilumina\xc3\xa7\xc3\xa3o.bin"));
    CHECK(strlen(full) > 260);
    HANDLE file = hos_path_open(full, GENERIC_WRITE, FILE_SHARE_READ, NULL, CREATE_NEW, FILE_ATTRIBUTE_NORMAL, NULL);
    CHECK(file != INVALID_HANDLE_VALUE);
    DWORD written = 0;
    CHECK(WriteFile(file, "light", 5, &written, NULL) && written == 5);
    CHECK(CloseHandle(file));
    CHECK(hos_path_attributes(full) != INVALID_FILE_ATTRIBUTES);
    file = hos_path_open(full, GENERIC_READ, FILE_SHARE_READ, NULL, OPEN_EXISTING, FILE_ATTRIBUTE_NORMAL, NULL);
    char data[8] = {0}; DWORD read = 0;
    CHECK(file != INVALID_HANDLE_VALUE && ReadFile(file, data, 5, &read, NULL));
    CHECK(read == 5 && !strcmp(data, "light") && CloseHandle(file));
    char pattern[HOS_FS_PATH_CAP], renamed[HOS_FS_PATH_CAP];
    CHECK(hos_path_join(pattern, sizeof pattern, dirs[2], "*.bin"));
    WIN32_FIND_DATAA found;
    HANDLE search = hos_path_find_first(pattern, &found);
    CHECK(search != INVALID_HANDLE_VALUE && !strcmp(found.cFileName, "ilumina\xc3\xa7\xc3\xa3o.bin"));
    CHECK(FindClose(search));
    CHECK(hos_path_join(renamed, sizeof renamed, dirs[2], "renamed.bin"));
    CHECK(hos_path_move_file(full, renamed, 0));
    CHECK(hos_path_attributes(full) == INVALID_FILE_ATTRIBUTES && GetLastError() == ERROR_FILE_NOT_FOUND);
    CHECK(hos_path_delete_file(renamed));
    for (int i = 2; i >= 0; --i) CHECK(hos_path_remove_dir(dirs[i]));
    CHECK(hos_path_remove_dir(base));
#endif
    puts("host path checks passed");
    return 0;
}

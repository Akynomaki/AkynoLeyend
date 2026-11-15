/* Native executable path in UTF-8. Shared by EXE and renderer; no game-data lookup. */
#pragma once
#include <stdio.h>
#include <string.h>
#include <wchar.h>
#ifndef WIN32_LEAN_AND_MEAN
#define WIN32_LEAN_AND_MEAN
#endif
#include <windows.h>
#include "path_join.h"
static inline DWORD hos_game_path_a(char *out, DWORD capacity) {
    wchar_t wide[HOS_FS_PATH_CAP];
    DWORD n = GetModuleFileNameW(NULL, wide, HOS_FS_PATH_CAP);
    if (!n || n >= HOS_FS_PATH_CAP) { if (capacity) out[0]=0; return 0; }
    int count=WideCharToMultiByte(CP_UTF8,0,wide,-1,out,(int)capacity,NULL,NULL);
    if (!count) { if (capacity) out[0]=0; return 0; }
    return (DWORD)(count-1);
}
/* Fixed ASCII filenames beside the executable; _wfopen avoids the ANSI code page.
   Used by the DLL too, without passing CRT FILE pointers across the host API. */
static inline int hos_game_file_name(const char *name,wchar_t *path,size_t cap) {
    wchar_t source[HOS_FS_PATH_CAP],suffix[128];
    DWORD n=GetModuleFileNameW(NULL,source,HOS_FS_PATH_CAP);
    if(!n || n>=HOS_FS_PATH_CAP || !MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,name,-1,suffix,128))return 0;
    wchar_t *end=source+n;
    while(end>source && end[-1]!=L'\\' && end[-1]!=L'/')--end;
    if((size_t)(end-source)+wcslen(suffix)>=HOS_FS_PATH_CAP)return 0;
    wcscpy(end,suffix);
    const int extended=!wcsncmp(source,L"\\\\?\\",4),unc=!wcsncmp(source,L"\\\\",2);
    const wchar_t *prefix=extended?L"":unc?L"\\\\?\\UNC\\":L"\\\\?\\";
    const wchar_t *body=source+(unc&&!extended?2:0);
    if(wcslen(prefix)+wcslen(body)>=cap)return 0;
    wcscpy(path,prefix);wcscat(path,body);return 1;
}
static inline FILE *hos_game_file(const char *name,const char *mode) {
    wchar_t path[HOS_FS_PATH_CAP+8],wmode[16];
    if(!hos_game_file_name(name,path,HOS_FS_PATH_CAP+8) || !MultiByteToWideChar(CP_UTF8,MB_ERR_INVALID_CHARS,mode,-1,wmode,16))return NULL;
    return _wfopen(path,wmode);
}
static inline int hos_game_replace(const char *from,const char *to) {
    wchar_t a[HOS_FS_PATH_CAP+8],b[HOS_FS_PATH_CAP+8];
    return hos_game_file_name(from,a,HOS_FS_PATH_CAP+8) && hos_game_file_name(to,b,HOS_FS_PATH_CAP+8) &&
        MoveFileExW(a,b,MOVEFILE_REPLACE_EXISTING|MOVEFILE_WRITE_THROUGH);
}
static inline void hos_game_delete(const char *name) {
    wchar_t path[HOS_FS_PATH_CAP+8];
    if(hos_game_file_name(name,path,HOS_FS_PATH_CAP+8))DeleteFileW(path);
}

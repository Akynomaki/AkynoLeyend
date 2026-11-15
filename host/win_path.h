#pragma once
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include "path_join.h"
FILE *hos_path_fopen(const char *, const char *);

HANDLE hos_path_open(const char *, DWORD, DWORD, LPSECURITY_ATTRIBUTES, DWORD, DWORD, HANDLE);
DWORD hos_path_attributes(const char *);
BOOL hos_path_mkdir(const char *, LPSECURITY_ATTRIBUTES);
BOOL hos_path_delete_file(const char *);
BOOL hos_path_remove_dir(const char *);
BOOL hos_path_move_file(const char *, const char *, DWORD);
HANDLE hos_path_find_first(const char *, WIN32_FIND_DATAA *);
BOOL hos_path_find_next(HANDLE, WIN32_FIND_DATAA *);

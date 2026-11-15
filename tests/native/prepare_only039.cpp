#include <cstdlib>
#include <cstdio>
#include <cstdarg>
#include <cstddef>
using HANDLE=void*;using DWORD=unsigned long;
#define INVALID_HANDLE_VALUE ((void*)-1)
constexpr int GENERIC_WRITE=1,FILE_SHARE_READ=2,FILE_SHARE_WRITE=4,OPEN_EXISTING=8;
int AllocConsole() { return 0; }
void SetConsoleTitleA(const char*) {}
HANDLE CreateFileA(const char*,int,int,void*,int,int,void*) { return nullptr; }
void WriteFile(HANDLE,const void*,DWORD,DWORD*,void*) {}
void CloseHandle(HANDLE) {}
void FreeConsole() {}
void logf(const char* f,...) { va_list a;va_start(a,f);vfprintf(stderr,f,a);va_end(a); }
bool replay_start() { return true; }
bool precompile_wanted() { return true; }
size_t seed_open() { return std::getenv("FIXTURE_MISSING") ? 0 : 1; }
void prepare_run(void(*p)(size_t,size_t)) { puts("PREPARED");p(1,1); }
void precompile_run(void(*)(size_t,size_t)) { puts("PIPELINES_PREPARED"); }
void pipeline_cache_save(bool force) { if(force)puts("DRIVER_CACHE_SAVED"); }
// ACTUAL_STARTUP
int main(int argc,char**) {
    if(argc>1)setenv("RX_VK_PREPARE_ONLY","1",1);
    if(argc>2)setenv("FIXTURE_MISSING","1",1);
    if(started_up())puts("GAMEPLAY_STARTED");
}

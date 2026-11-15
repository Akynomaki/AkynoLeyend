// (Hookshot 2.1.0, adapted) NVIDIA DLSS in the llvm-mingw build of AkynoLeyend.dll: what NVIDIA's static NGX loader
// (nvsdk_ngx_s.lib, built with Microsoft's compiler against its static C++ runtime, /MT) asks of that runtime and the MinGW
// one does not have. Compiled to nothing unless NVIDIA's SDK is in third_party/nvidia-dlss-sdk (vk_fsr_sdk.cpp's DLSS takes
// the same test), and nx2/build.py links nvsdk_ngx_s.lib only then. Hookshot keeps the C parts (/GS's cookie and handler,
// _fltused, __chkstk) in host/mingw_msvc_shims.c; AkynoLeyend's DLL has no other MSVC-built library, so they are here.
#if defined(__MINGW32__) && __has_include("../../third_party/nvidia-dlss-sdk/include/nvsdk_ngx_vk.h")
#include <windows.h>
#include <stdint.h>

#include <climits>
#include <cstdio>
#include <cstdlib>

extern "C" {

// (the C parts, as host/mingw_msvc_shims.c of Hookshot 2.1.0 defines them)
int _fltused = 0x9875;   // (the value MSVC's runtime gives it: only its presence matters)
// /GS: a cookie in each guarded frame, checked on return; the value set once at start
uintptr_t __security_cookie = (uintptr_t)0x00002B992DDFA232ull;
__attribute__((constructor)) static void security_cookie_init(void) {
    LARGE_INTEGER t;
    QueryPerformanceCounter(&t);
    uintptr_t c = (uintptr_t)t.QuadPart ^ (uintptr_t)GetCurrentProcessId() ^ ((uintptr_t)GetCurrentThreadId() << 32);
    c &= 0x0000FFFFFFFFFFFFull;   // (MSVC keeps the top 16 bits clear)
    if (c) __security_cookie = c;
}
void __security_check_cookie(uintptr_t cookie) {
    if (cookie != __security_cookie) __fastfail(2);   // FAST_FAIL_STACK_COOKIE_CHECK_FAILURE
}
void __report_rangecheckfailure(void) { __fastfail(8); }   // FAST_FAIL_RANGE_CHECK_FAILURE
// MSVC's stack probe for frames over a page: the same contract on x64 as MinGW's ___chkstk_ms
__asm__(".text\n.globl __chkstk\n__chkstk:\n    jmp ___chkstk_ms\n");
// the unwind handler of /GS frames: it checks the frame's cookie, then lets the search go on
EXCEPTION_DISPOSITION __GSHandlerCheck(struct _EXCEPTION_RECORD* record, void* frame, struct _CONTEXT* context, void* dispatcher) {
    (void)record, (void)frame, (void)context, (void)dispatcher;
    return ExceptionContinueSearch;
}

// (/GS frames with C++ exception handling: the cookie check (skipped, as __GSHandlerCheck's in host/mingw_msvc_shims.c), then
// the C++ frame handler, as Microsoft's runtime does)
EXCEPTION_DISPOSITION __CxxFrameHandler3(struct _EXCEPTION_RECORD* record, void* frame, struct _CONTEXT* context,
                                         void* dispatcher);
EXCEPTION_DISPOSITION __GSHandlerCheck_EH(struct _EXCEPTION_RECORD* record, void* frame, struct _CONTEXT* context,
                                          void* dispatcher) {
    return __CxxFrameHandler3(record, frame, context, dispatcher);
}

// Thread-safe function-local statics, Microsoft's way (its thread_safe_statics.cpp): each static's guard is 0 before, -1
// while one thread initialises it, then the epoch it was done in. A thread whose own epoch is older than a guard takes the
// lock and looks; the others skip it. One lock and one condition variable for all of them.
int _Init_global_epoch = INT_MIN;
thread_local int _Init_thread_epoch = INT_MIN;   // (read by the compiled code itself, through the TLS index)

static SRWLOCK init_lock = SRWLOCK_INIT;
static CONDITION_VARIABLE init_done = CONDITION_VARIABLE_INIT;

void _Init_thread_header(int* once) {
    AcquireSRWLockExclusive(&init_lock);
    if (*once == 0) {
        *once = -1;   // (this thread initialises it)
    } else {
        while (*once == -1) {
            SleepConditionVariableSRW(&init_done, &init_lock, 100, 0);
            if (*once == 0) {   // (the other thread's initialiser threw: this one tries)
                *once = -1;
                ReleaseSRWLockExclusive(&init_lock);
                return;
            }
        }
        _Init_thread_epoch = _Init_global_epoch;
    }
    ReleaseSRWLockExclusive(&init_lock);
}

void _Init_thread_footer(int* once) {
    AcquireSRWLockExclusive(&init_lock);
    ++_Init_global_epoch;
    *once = _Init_global_epoch;
    _Init_thread_epoch = _Init_global_epoch;
    ReleaseSRWLockExclusive(&init_lock);
    WakeAllConditionVariable(&init_done);
}

void _Init_thread_abort(int* once) {   // (an initialiser that threw: the next thread tries again)
    AcquireSRWLockExclusive(&init_lock);
    *once = 0;
    ReleaseSRWLockExclusive(&init_lock);
    WakeAllConditionVariable(&init_done);
}

// Microsoft's operator new and delete (its names: ??2@YAPEAX_K@Z, ??3@YAXPEAX@Z): the C heap. Only NVIDIA's code calls them,
// and frees only what it allocated, so they need not be libc++'s. Out of memory ends the process: an exception of libc++'s
// would not be one Microsoft's handlers catch.
[[noreturn]] static void msvc_fatal(const char* what) {
    fprintf(stderr, "vk: NVIDIA DLSS: %s in NVIDIA's NGX code\n", what);
    fflush(stderr);
    abort();
}

void* msvc_operator_new(size_t size) __asm__("??2@YAPEAX_K@Z");
void* msvc_operator_new(size_t size) {
    if (void* p = malloc(size ? size : 1)) return p;
    msvc_fatal("out of memory");
}

void msvc_operator_delete(void* p) __asm__("??3@YAXPEAX@Z");
void msvc_operator_delete(void* p) { free(p); }

// Microsoft's C++ library's error reports (std::_Xbad_alloc, std::_Xlength_error), which throw in its runtime
[[noreturn]] void msvc_xbad_alloc() __asm__("?_Xbad_alloc@std@@YAXXZ");
void msvc_xbad_alloc() { msvc_fatal("out of memory (std::bad_alloc)"); }

[[noreturn]] void msvc_xlength_error(const char* what) __asm__("?_Xlength_error@std@@YAXPEBD@Z");
void msvc_xlength_error(const char* what) { msvc_fatal(what ? what : "std::length_error"); }

}  // extern "C"
#endif

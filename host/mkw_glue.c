/* mkw-recomp's pieces of the standalone runtime that TOTKPort's hos/ keeps elsewhere: the 64-bit guest window's
   commit (TOTK commits its whole 4 GB window up front; MKW's 512 GB window is only reserved), and stand-ins for the
   hooks of files not taken into host/ (the renderer and display, the profiler, mods, TOTK's own patches). */
#include "hos.h"
#include <stdio.h>
#include <stdlib.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define PSAPI_VERSION 2
#include <psapi.h>
#include <string.h>
#include <cpuid.h>

/* ---- the guest window ---------------------------------------------------------------------------------------
   The runtime commits what it hands out (image, system region, heap, address regions: hos_commit), because host
   APIs given guest buffers (ReadFile into a game buffer) fail on reserved pages without raising an exception. A
   guest or host access to a page nothing committed is committed on first touch, 64 KB at a time, by the handler.

   (11-10, Kokiri on a tester's PC) A commit Windows refuses (error 1455: the system's commit limit, RAM plus page
   file, is reached) was only logged: the game went on over pages that were not there and died later somewhere else
   (an access violation in a decompression thread, a std::bad_alloc in the renderer). The first refusal is now the
   end of the run: said once, with the memory figures, and the process ends with STATUS_COMMITMENT_LIMIT. */
#define HOS_EXIT_COMMIT_LIMIT 0xC000012Du   /* STATUS_COMMITMENT_LIMIT */

typedef struct {
    uint64_t phys_total, phys_free, commit_limit, commit_free, priv, working, priv_peak;
} MemState;

static void mem_state(MemState *m) {   /* (no allocation: also read while reporting an out of memory) */
    memset(m, 0, sizeof *m);
    MEMORYSTATUSEX ms;
    ms.dwLength = sizeof ms;
    if (GlobalMemoryStatusEx(&ms)) {
        m->phys_total = ms.ullTotalPhys;
        m->phys_free = ms.ullAvailPhys;
        m->commit_limit = ms.ullTotalPageFile;   /* (RAM + page files, as this process may use them) */
        m->commit_free = ms.ullAvailPageFile;
    }
    PROCESS_MEMORY_COUNTERS_EX pc;
    memset(&pc, 0, sizeof pc);
    pc.cb = sizeof pc;
    if (K32GetProcessMemoryInfo(GetCurrentProcess(), (PROCESS_MEMORY_COUNTERS *)&pc, sizeof pc)) {
        m->priv = pc.PrivateUsage;
        m->working = pc.WorkingSetSize;
        m->priv_peak = pc.PeakPagefileUsage;
    }
}

static uint64_t heap_on_demand_committed(uint64_t *of);   /* (below, with the heap on demand) */

static void mem_log(const char *what) {
    MemState m;
    mem_state(&m);
    hos_log("mem: %s: RAM %llu MB free of %llu; system commit %llu MB used of %llu (%llu free); this process %llu MB "
            "private (peak %llu), %llu MB working set",
            what, (unsigned long long)(m.phys_free >> 20), (unsigned long long)(m.phys_total >> 20),
            (unsigned long long)((m.commit_limit - m.commit_free) >> 20), (unsigned long long)(m.commit_limit >> 20),
            (unsigned long long)(m.commit_free >> 20), (unsigned long long)(m.priv >> 20),
            (unsigned long long)(m.priv_peak >> 20), (unsigned long long)(m.working >> 20));
    uint64_t of = 0;
    const uint64_t got = heap_on_demand_committed(&of);
    if (of)   /* (its own line: the one above is read by the launcher as it is) */
        hos_log("mem: heap on demand: %llu MB of %llu committed at first touches so far (file and GPU ranges committed ahead not counted)", (unsigned long long)(got >> 20),
                (unsigned long long)(of >> 20));
}

/* The end of a run that is out of memory. One thread reports; any other that fails meanwhile waits for the process
   to end (and ends it itself if the first one is stuck). Nothing here allocates on purpose: the lines are formatted
   on the stack, and hos_log writes them straight to the log when it cannot queue them. */
static volatile LONG oom_reporting;

static DECLSPEC_NORETURN void out_of_memory(uint64_t guest, uint64_t bytes, DWORD error, const char *how) {
    if (InterlockedExchange(&oom_reporting, 1)) {
        Sleep(5000);
        TerminateProcess(GetCurrentProcess(), HOS_EXIT_COMMIT_LIMIT);
        for (;;) Sleep(1000);
    }
    hos_log("mem: OUT OF MEMORY: Windows refused %llu KB of guest memory at %#llx (%s, error %lu%s). The run stops "
            "here: continuing would use pages that do not exist.",
            (unsigned long long)(bytes >> 10), (unsigned long long)guest, how, error,
            error == 1455 ? ": the commit limit, RAM plus page file, is reached" : "");
    mem_log("at the failure");
    hos_log("mem: SEM MEMORIA: feche outros programas ou aumente o arquivo de paginacao do Windows (memoria virtual) "
            "e tente de novo. Isto nao e falta de VRAM.");
    hos_log_flush();
    TerminateProcess(GetCurrentProcess(), HOS_EXIT_COMMIT_LIMIT);
    for (;;) Sleep(1000);
}

static int commit_is_memory(DWORD error) {
    return error == 1455 || error == ERROR_NOT_ENOUGH_MEMORY || error == ERROR_OUTOFMEMORY;
}

/* Windows answers 1455 while it is still growing the page file: a commit refused is asked again a few times before
   it is final (never from the exception handler, which asks once) */
static int commit_pages(uint64_t lo, uint64_t bytes, int tries, DWORD *error) {
    for (int i = 0;; i++) {
        if (VirtualAlloc(GP(lo), (SIZE_T)bytes, MEM_COMMIT, PAGE_READWRITE)) return 1;
        *error = GetLastError();
        if (i + 1 >= tries || !commit_is_memory(*error)) return 0;
        Sleep(100);
    }
}

/* (tests) HOS_TEST_COMMIT_FAIL=<n>: the n-th commit of this run is refused as Windows would, to exercise the path
   above without exhausting the machine. Read once; absent in normal runs. */
static volatile LONG commit_fail_at = -1, commit_calls;
static int commit_refused_for_test(void) {
    if (commit_fail_at < 0) {
        const char *v = getenv("HOS_TEST_COMMIT_FAIL");
        InterlockedExchange(&commit_fail_at, v && atoi(v) > 0 ? atoi(v) : 0);
    }
    return commit_fail_at > 0 && InterlockedIncrement(&commit_calls) == commit_fail_at;
}

void hos_commit(uint64_t addr, uint64_t size) {
    if (!size) return;
    const uint64_t lo = addr & ~0xFFFFULL, hi = (addr + size + 0xFFFF) & ~0xFFFFULL;
    DWORD error = 1455;
    if (!commit_refused_for_test() && commit_pages(lo, hi - lo, 20, &error)) return;
    if (commit_is_memory(error)) out_of_memory(lo, hi - lo, error, "handed out by the runtime");
    /* (any other refusal, as before: said, and the pages are left to the first touch) */
    hos_log("mem: commit of %#llx bytes at %#llx failed (error %lu)", (unsigned long long)(hi - lo),
            (unsigned long long)lo, error);
}

/* ---- the heap, committed as it is used --------------------------------------------------------------------
   (11-11, measured on this game) The heap the game asks for is 6894 MB, committed whole when it asks; a minute into
   a scene it had touched 3.5 GB of it. Windows charges a commit whether or not the pages are ever used, and besides
   the heap the process commits about 12 GB more (the game's address regions, the renderer, and a reservation
   Windows makes for every allocation of video memory): on a PC with 16 GB of RAM and a small page file the run
   ended at the commit limit with gigabytes of the heap never touched. So when the commit Windows has left is less
   than the heap and those 12 GB, the heap is left reserved and each 2 MB of it is committed at its first touch, by
   the handler below. Where there is room, nothing changes: all of it at once, as before.
   A system call given guest memory does not raise that exception (ReadFile into a buffer the game has not touched
   fails instead), so the places that hand guest memory to the system commit it first: hos_commit_for_host (file
   reads and writes, nn_fs.c; a memory pool's storage, nvn_native.c; the renderer commits what it imports itself).
   HOS_LAZY_HEAP=1: always on demand; HOS_LAZY_HEAP=0: never. */
#define HEAP_GRANULE 0x200000ULL
#define HEAP_OTHER_COMMIT (12ULL << 30)
static volatile LONG64 lazy_lo, lazy_hi;           /* (guest addresses; equal: none) */
static volatile LONG64 lazy_committed;             /* (by first touches: what is committed ahead is not in it) */
#define HEAP_GRANULES_COUNTED 16384                /* (32 GB of heap: each 2 MB counted once) */
static volatile LONG lazy_seen[HEAP_GRANULES_COUNTED / 32];

int hos_heap_on_demand(uint64_t base, uint64_t size) {
    static int on = -1;
    if (on < 0) {
        const char *e = getenv("HOS_LAZY_HEAP");
        MemState m;
        mem_state(&m);
        on = e && *e ? atoi(e) != 0 : m.commit_limit && m.commit_free < size + HEAP_OTHER_COMMIT;
        if (on)
            hos_log("mem: the heap's %llu MB are committed as the game uses them: Windows has %llu MB of commit free "
                    "(HOS_LAZY_HEAP=0: all of it at once, as with more than %llu MB free)",
                    (unsigned long long)(size >> 20), (unsigned long long)(m.commit_free >> 20),
                    (unsigned long long)((size + HEAP_OTHER_COMMIT) >> 20));
    }
    if (on) {
        InterlockedExchange64(&lazy_lo, (LONG64)base);
        InterlockedExchange64(&lazy_hi, (LONG64)(base + size));
    }
    return on;
}

void hos_commit_for_host(uint64_t addr, uint64_t size) {
    const uint64_t lo = (uint64_t)lazy_lo, hi = (uint64_t)lazy_hi;
    if (lo == hi || !size || addr >= hi || addr + size <= lo) return;   /* (no heap on demand, or not in it) */
    const uint64_t a = addr > lo ? addr : lo, b = addr + size < hi ? addr + size : hi;
    hos_commit(a, b - a);
}

/* (the mem: lines) how much of a heap on demand is committed so far; 0 when there is none */
static uint64_t heap_on_demand_committed(uint64_t *of) {
    *of = (uint64_t)lazy_hi - (uint64_t)lazy_lo;
    return (uint64_t)lazy_committed;
}

static LONG CALLBACK commit_on_touch(EXCEPTION_POINTERS *info) {
    EXCEPTION_RECORD *rec = info->ExceptionRecord;
    if (rec->ExceptionCode != EXCEPTION_ACCESS_VIOLATION || rec->NumberParameters < 2) return EXCEPTION_CONTINUE_SEARCH;
    const uint8_t *p = (const uint8_t *)rec->ExceptionInformation[1];
    if (p < A64_MEM || p >= A64_MEM + HOS_GUEST_SPACE) return EXCEPTION_CONTINUE_SEARCH;
    const uint64_t guest = (uint64_t)(p - A64_MEM);
    if (guest < 0x100000) return EXCEPTION_CONTINUE_SEARCH;   /* (a null pointer: the game's own fault) */
    MEMORY_BASIC_INFORMATION mbi;
    if (!VirtualQuery(p, &mbi, sizeof mbi)) return EXCEPTION_CONTINUE_SEARCH;
    if (mbi.State == MEM_COMMIT) {
        /* (r6 review) Committed between the fault and this query: another thread touched the same pages first and
           its handler committed them (two threads on one fresh 2 MB of a heap on demand: seen within a few rounds
           of a test, and the exception went on to the crash report). The access is tried again. Only what trying
           again can satisfy, a read or a write of pages that are read-write now: anything else is somebody
           else's fault to handle. And not for ever at one address, should that reasoning be wrong somewhere. */
        const ULONG_PTR op = rec->ExceptionInformation[0];
        static _Thread_local const uint8_t *again_at;
        static _Thread_local int again;
        if ((op != 0 && op != 1) || mbi.Protect != PAGE_READWRITE) return EXCEPTION_CONTINUE_SEARCH;
        if (again_at != p) again_at = p, again = 0;
        if (++again > 64) return EXCEPTION_CONTINUE_SEARCH;
        return EXCEPTION_CONTINUE_EXECUTION;
    }
    if (mbi.State != MEM_RESERVE) return EXCEPTION_CONTINUE_SEARCH;
    DWORD error = 1455;
    {   /* (a heap on demand: its 2 MB, within the heap; no line, it is how that heap is committed) */
        const uint64_t lo = (uint64_t)lazy_lo, hi = (uint64_t)lazy_hi;
        if (guest >= lo && guest < hi) {
            uint64_t a = guest & ~(HEAP_GRANULE - 1), b = a + HEAP_GRANULE;
            if (a < lo) a = lo;
            if (b > hi) b = hi;
            if (commit_refused_for_test() || !commit_pages(a, b - a, 1, &error)) {
                if (commit_is_memory(error)) out_of_memory(a, b - a, error, "the heap's first touch");
                return EXCEPTION_CONTINUE_SEARCH;
            }
            {   /* (counted once: two threads may commit the same 2 MB, and a commit of committed pages succeeds) */
                const uint64_t g = (a - lo) / HEAP_GRANULE;
                if (g >= HEAP_GRANULES_COUNTED || !InterlockedBitTestAndSet(&lazy_seen[g / 32], (LONG)(g % 32)))
                    InterlockedAdd64(&lazy_committed, (LONG64)(b - a));
            }
            return EXCEPTION_CONTINUE_EXECUTION;
        }
    }
    if (commit_refused_for_test() || !commit_pages(guest & ~0xFFFFULL, 0x10000, 1, &error)) {
        if (commit_is_memory(error)) out_of_memory(guest & ~0xFFFFULL, 0x10000, error, "first touch");
        return EXCEPTION_CONTINUE_SEARCH;   /* (never resumed over a page that was not committed) */
    }
    /* (said only once it is known: the line used to come before the result) */
    static volatile LONG touched;
    if (InterlockedIncrement(&touched) <= 16)
        hos_log("mem: %#llx committed on first touch (nothing handed it out)", (unsigned long long)guest);
    return EXCEPTION_CONTINUE_EXECUTION;
}

/* A crash nothing handles: what, where (mkw.exe+offset: nx2/dllmap.py reads mkw.map the same way), and the guest
   state of the thread, as of its last call out of lifted code, with its frame chain from x29. */
static uint64_t peek_guest(uint64_t a) {
    MEMORY_BASIC_INFORMATION mbi;
    if (a >= HOS_GUEST_SPACE - 8 || !VirtualQuery(GP(a), &mbi, sizeof mbi) || mbi.State != MEM_COMMIT) return 0;
    return G64(a);
}

static LONG WINAPI report_crash(EXCEPTION_POINTERS *info) {
    EXCEPTION_RECORD *rec = info->ExceptionRecord;
    const uint64_t rip = info->ContextRecord->Rip;
    HMODULE mod = NULL;
    char name[MAX_PATH] = "?";
    if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                           (LPCSTR)rip, &mod))
        GetModuleFileNameA(mod, name, MAX_PATH);
    const char *base = strrchr(name, '\\');
    const uint64_t addr = rec->NumberParameters > 1 ? rec->ExceptionInformation[1] : 0;
    hos_log("CRASH: exception %#lx (%s %#llx, guest %#llx) at %s+%#llx", rec->ExceptionCode,
            rec->NumberParameters > 1 && rec->ExceptionInformation[0] == 1 ? "write" : "read",
            (unsigned long long)addr, (unsigned long long)(addr - (uint64_t)A64_MEM), base ? base + 1 : name,
            (unsigned long long)(rip - (uint64_t)mod));
    {   /* the host stack from the faulting frame (x64 unwind data), as module+offset (nx2/samap.py maps mkw.exe's) */
        CONTEXT ctx = *info->ContextRecord;
        char hb[1024];
        int n = snprintf(hb, sizeof hb, "CRASH: host backtrace:");
        for (int i = 0; i < 20 && ctx.Rip && n < (int)sizeof hb - 48; i++) {
            HMODULE m = NULL;
            char mn[MAX_PATH] = "?";
            if (GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                   (LPCSTR)ctx.Rip, &m))
                GetModuleFileNameA(m, mn, MAX_PATH);
            const char *mb = strrchr(mn, '\\');
            n += snprintf(hb + n, sizeof hb - n, " %s+%#llx", mb ? mb + 1 : mn, (unsigned long long)(ctx.Rip - (uint64_t)m));
            DWORD64 image = 0;
            PRUNTIME_FUNCTION f = RtlLookupFunctionEntry(ctx.Rip, &image, NULL);
            if (!f) break;
            void *handler_data;
            DWORD64 frame;
            RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, ctx.Rip, f, &ctx, &handler_data, &frame, NULL);
        }
        hos_log("%s", hb);
    }
    Ctx *c = hos_ctx();
    if (c) {
        hos_log("CRASH: thread %s, sp %#llx", hos_thread_name(hos_self()), (unsigned long long)c->x[31]);
        for (int i = 0; i < 31; i += 4)
            hos_log("CRASH:   x%-2d %016llx  x%-2d %016llx  x%-2d %016llx  x%-2d %016llx", i,
                    (unsigned long long)c->x[i], i + 1, (unsigned long long)c->x[i + 1], i + 2,
                    (unsigned long long)c->x[i + 2], i + 3, i + 3 < 31 ? (unsigned long long)c->x[i + 3] : 0ULL);
        char bt[1024];
        int n = snprintf(bt, sizeof bt, "CRASH: guest backtrace: lr %#llx", (unsigned long long)c->x[30]);
        uint64_t fp = c->x[29];
        for (int i = 0; i < 40 && fp && !(fp & 15) && n < (int)sizeof bt - 24; i++) {
            const uint64_t lr = peek_guest(fp + 8), next = peek_guest(fp);
            n += snprintf(bt + n, sizeof bt - n, " %#llx", (unsigned long long)lr);
            if (next <= fp) break;
            fp = next;
        }
        hos_log("%s", bt);
        /* the memory x0, x1 and x19 point to (the object a crash is usually about) */
        static const int dumped[] = {0, 1, 19};
        for (int k = 0; k < 3; k++) {
            const int r = dumped[k];
            const uint64_t base = c->x[r];
            if (base < 0x100000 || !peek_guest(base) && !peek_guest(base + 8) && !peek_guest(base + 0x100)) continue;
            for (int row = 0; row < 0x120; row += 32)
                hos_log("CRASH: [x%d+%#05x] %016llx %016llx %016llx %016llx", r, row,
                        (unsigned long long)peek_guest(base + row), (unsigned long long)peek_guest(base + row + 8),
                        (unsigned long long)peek_guest(base + row + 16), (unsigned long long)peek_guest(base + row + 24));
        }
    }
    if (rec->ExceptionCode == 0x20474343) {
        /* A C++ exception nothing caught (the renderer's, most often std::bad_alloc when memory runs out). Left
           to Windows, the thread's frames were unwound next: the renderer's cleanup then asked the unwinder to
           go on through the lifted C frames and the run ended in a second, unrelated-looking failure
           (0xC00000FF, STATUS_BAD_FUNCTION_TABLE, at ntdll under _Unwind_Resume) or went on half unwound. The
           first report above is the one that counts: the process ends here. */
        mem_log("at the uncaught C++ exception");
        hos_log("CRASH: uncaught C++ exception (usually out of memory): ending the run here");
        hos_log_flush();
        TerminateProcess(GetCurrentProcess(), 0x20474343);
    }
    hos_log_flush();
    void hos_hostcall_stats(void);
    hos_hostcall_stats();   /* (HOS_HOSTCALL_STATS=1: the host calls made, and the last 256 of them) */
    return EXCEPTION_CONTINUE_SEARCH;
}

/* (hos_prof.c's, for hos_fatal) the current thread's guest frame chain from x29 */
void hos_backtrace(void) {
    Ctx *c = hos_ctx();
    if (!c) return;
    char bt[1024];
    int n = snprintf(bt, sizeof bt, "guest backtrace: lr %#llx", (unsigned long long)c->x[30]);
    uint64_t fp = c->x[29];
    for (int i = 0; i < 40 && fp && !(fp & 15) && n < (int)sizeof bt - 24; i++) {
        const uint64_t lr = peek_guest(fp + 8), next = peek_guest(fp);
        n += snprintf(bt + n, sizeof bt - n, " %#llx", (unsigned long long)lr);
        if (next <= fp) break;
        fp = next;
    }
    fprintf(stderr, "[hos] %s\n", bt);
    fflush(stderr);
}

/* HOS_STATS_AFTER=<seconds> (with HOS_HOSTCALL_STATS=1): the host call counts and the last calls at that time, for
   runs that are stopped rather than exit (what a quiet game is doing) */
static DWORD WINAPI stats_after(void *p) {
    Sleep((DWORD)(uintptr_t)p * 1000);
    void hos_hostcall_stats(void);
    hos_log("stats: after %u s", (unsigned)(uintptr_t)p);
    void hos_thread_dump(void);
    hos_thread_dump();
    hos_log_flush();
    hos_hostcall_stats();
    return 0;
}

/* heap corruption and fail-fast reports go to the process's end without reaching the unhandled filter: reported here
   first (the backtrace is where the heap noticed, after the bad write) */
static LONG CALLBACK report_fatal(EXCEPTION_POINTERS *info) {
    const DWORD code = info->ExceptionRecord->ExceptionCode;
    if (code == 0xC0000374 || code == 0xC0000409) report_crash(info);
    return EXCEPTION_CONTINUE_SEARCH;
}

/* What the machine is and how much memory is in use: once at the start, then only when it matters (the system's
   commit passing 80, 85, 90, 95 %, or this process growing by another GB), 40 lines at most. One thread, two cheap
   system calls every 2 s; nothing per frame, nothing that names the user or the PC. */
static void machine_log(void) {
    char brand[49] = "";
    unsigned a = 0, b = 0, c = 0, d = 0;
    if (__get_cpuid(0x80000000u, &a, &b, &c, &d) && a >= 0x80000004u)
        for (unsigned i = 0; i < 3; i++) {
            unsigned r[4] = {0, 0, 0, 0};
            __get_cpuid(0x80000002u + i, &r[0], &r[1], &r[2], &r[3]);
            memcpy(brand + 16 * i, r, 16);
        }
    int avx = 0, fma = 0, avx2 = 0, bmi2 = 0, os_avx = 0;
    if (__get_cpuid(1, &a, &b, &c, &d)) {
        avx = c >> 28 & 1;
        fma = c >> 12 & 1;
        if (c >> 27 & 1) {   /* (OSXSAVE: the system keeps the AVX registers) */
            unsigned lo, hi;
            __asm__ volatile("xgetbv" : "=a"(lo), "=d"(hi) : "c"(0));
            os_avx = (lo & 6) == 6;
        }
    }
    if (__get_cpuid_count(7, 0, &a, &b, &c, &d)) {
        avx2 = b >> 5 & 1;
        bmi2 = b >> 8 & 1;
    }
    const char *name = brand;
    while (*name == ' ') name++;
    SYSTEM_INFO si;
    GetSystemInfo(&si);
    struct { ULONG size, major, minor, build, platform; WCHAR sp[128]; } ver = {0};
    ver.size = sizeof ver;
    typedef LONG(WINAPI * VersionFn)(void *);
    VersionFn version = (VersionFn)(void *)GetProcAddress(GetModuleHandleA("ntdll.dll"), "RtlGetVersion");
    if (version) version(&ver);
    const char *built =
#if defined(__AVX2__) && defined(__BMI2__) && defined(__FMA__)
        "x86-64-v3 (AVX2, BMI2, FMA)";
#elif defined(__AVX2__)
        "AVX2";
#elif defined(__AVX__)
        "AVX";
#else
        "baseline x86-64";
#endif
    hos_log("machine: %s, %lu logical processors; Windows %lu.%lu build %lu; CPU has AVX %d (system %d) AVX2 %d BMI2 %d "
            "FMA %d; this executable was built for %s",
            *name ? name : "unknown CPU", si.dwNumberOfProcessors, ver.major, ver.minor, ver.build, avx, os_avx, avx2,
            bmi2, fma, built);
#if defined(__AVX2__)
    if (!avx2 || !bmi2 || !fma || !os_avx)
        hos_log("machine: this CPU or system lacks instructions the executable was built for: an illegal instruction "
                "(0xC000001D) is to be expected");
#endif
}

void hos_memory_map_log(void);
static DWORD WINAPI mem_watch(void *unused) {
    (void)unused;
    int lines = 0, step = 80;
    uint64_t said_priv = 0;
    /* (0.4.5-test.2) HOS_MEM_MAP=1 (the launcher's measurement): every 30 s the memory line and the map of what is
       committed where (hos_memory_map_log), 120 times at most (an hour): the Vulkan renderer never called it, and the
       sessions that ended with 20-25 GB committed on a 16 GB PC did not say where it went */
    const int map_on = getenv("HOS_MEM_MAP") != NULL;
    int maps = 0;
    for (int tick = 1;; tick++) {
        Sleep(2000);
        if (oom_reporting) return 0;
        if (map_on && tick % 15 == 0 && maps < 120) {
            maps++;
            mem_log("measured");
            hos_memory_map_log();
        }
        if (lines >= 40) {
            if (map_on) continue;
            return 0;
        }
        MemState m;
        mem_state(&m);
        const int used = m.commit_limit ? (int)((m.commit_limit - m.commit_free) * 100 / m.commit_limit) : 0;
        if (!said_priv) said_priv = m.priv;
        if (used >= step) {
            while (step <= used) step += 5;
        } else if (m.priv < said_priv + (1ULL << 30)) {
            continue;
        }
        said_priv = m.priv;
        lines++;
        mem_log(used >= 80 ? "commit is running out" : "growing");
    }
}

void hos_commit_init(void) {
    static volatile LONG once;
    if (!InterlockedExchange(&once, 1)) {
        machine_log();
        mem_log("at start");
        HANDLE t = CreateThread(NULL, 0, mem_watch, NULL, 0, NULL);
        if (t) {
            SetThreadPriority(t, THREAD_PRIORITY_LOWEST);
            CloseHandle(t);
        }
    }
    AddVectoredExceptionHandler(1, commit_on_touch);
    AddVectoredExceptionHandler(0, report_fatal);
    SetUnhandledExceptionFilter(report_crash);
    const char *after = getenv("HOS_STATS_AFTER");
    if (after && atoi(after) > 0) CreateThread(NULL, 0, stats_after, (void *)(uintptr_t)atoi(after), 0, NULL);
}

/* ---- stand-ins --------------------------------------------------------------------------------------------- */

/* HOS_PROFILE=<seconds> (in place of TOTKPort's hos_prof.c): every interval, the process's busiest threads and their
   share of a core (guest threads by their guest names, host threads by their descriptions): which one a frame rate
   waits for */
#include <tlhelp32.h>
int hos_thread_handles(HANDLE *out, const char **names, int max);   /* hos_thread.c */
static DWORD WINAPI prof_thread(void *p) {
    const DWORD ms = (DWORD)(uintptr_t)p * 1000;
    enum { MAXT = 512 };
    static DWORD ids[MAXT];
    static uint64_t was[MAXT];
    int nwas = 0;
    for (;;) {
        Sleep(ms);
        static HANDLE gh[1024];
        static const char *gn[1024];
        const int ng = hos_thread_handles(gh, gn, 1024);
        struct { DWORD id; uint64_t cpu, delta; char name[64]; } cur[MAXT];
        int n = 0;
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        THREADENTRY32 te = {sizeof te};
        for (BOOL ok = Thread32First(snap, &te); ok && n < MAXT; ok = Thread32Next(snap, &te)) {
            if (te.th32OwnerProcessID != GetCurrentProcessId()) continue;
            HANDLE h = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, te.th32ThreadID);
            if (!h) continue;
            FILETIME c0, e0, k, u;
            if (GetThreadTimes(h, &c0, &e0, &k, &u)) {
                cur[n].id = te.th32ThreadID;
                cur[n].cpu = ((uint64_t)k.dwHighDateTime << 32 | k.dwLowDateTime) + ((uint64_t)u.dwHighDateTime << 32 | u.dwLowDateTime);
                cur[n].delta = cur[n].cpu;
                for (int i = 0; i < nwas; i++)
                    if (ids[i] == te.th32ThreadID) { cur[n].delta = cur[n].cpu - was[i]; break; }
                snprintf(cur[n].name, sizeof cur[n].name, "tid %lu", te.th32ThreadID);
                for (int i = 0; i < ng; i++)
                    if (GetThreadId(gh[i]) == te.th32ThreadID) { snprintf(cur[n].name, sizeof cur[n].name, "%s", gn[i]); break; }
                if (!strncmp(cur[n].name, "tid ", 4)) {
                    PWSTR d = NULL;
                    if (SUCCEEDED(GetThreadDescription(h, &d)) && d && d[0])
                        WideCharToMultiByte(CP_UTF8, 0, d, -1, cur[n].name, sizeof cur[n].name, NULL, NULL);
                    if (d) LocalFree(d);
                }
                n++;
            }
            CloseHandle(h);
        }
        CloseHandle(snap);
        for (int i = 0; i < n && i < MAXT; i++) ids[i] = cur[i].id, was[i] = cur[i].cpu;
        nwas = n;
        for (int i = 0; i < n; i++)   /* (busiest first) */
            for (int j = i + 1; j < n; j++)
                if (cur[j].delta > cur[i].delta) { char t[sizeof cur[0]]; memcpy(t, &cur[i], sizeof t); memcpy(&cur[i], &cur[j], sizeof t); memcpy(&cur[j], t, sizeof t); }
        char line[1024];
        int len = snprintf(line, sizeof line, "prof: busiest threads (%% of a core):");
        uint64_t total = 0;
        for (int i = 0; i < n; i++) total += cur[i].delta;
        for (int i = 0; i < n && i < 10 && len < (int)sizeof line - 80; i++)
            len += snprintf(line + len, sizeof line - len, " %s %.0f,", cur[i].name, cur[i].delta / (ms * 100.0));
        snprintf(line + len, sizeof line - len, " all %.0f", total / (ms * 100.0));
        hos_log("%s", line);
    }
    return 0;
}
/* HOS_SAMPLE=<thread name> (with HOS_PROFILE=<seconds>): that thread's instruction pointer sampled every millisecond;
   every interval the most frequent places, as module+offset of the leaf and of the first frame in mkw.exe under it
   (what of ours called into wgpu or the system). nx2/samap.py maps the mkw.exe offsets to functions.
   (AkynoLeyend 0.4.5-test.4) Several threads: HOS_SAMPLE=<name>|<name>, one sampler each, and every line names its thread
   ("prof-sample leaf (N samples) [name]:"). And "chain": the first CHAIN_DEPTH frames in the exe from the leaf down, as
   exe+a<+b<+c (the test.3 samples said the recording thread spent 55% of its time in hos_cv_sleep, not who waited). */
enum { CHAIN_DEPTH = 6 };
static DWORD WINAPI sample_thread(void *p) {
    const char *want = (const char *)p;
    const DWORD ms = (DWORD)atoi(getenv("HOS_PROFILE")) * 1000;
    HANDLE th = NULL;
    while (!th) {   /* (the renderer's threads start late) */
        Sleep(1000);
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        THREADENTRY32 te = {sizeof te};
        for (BOOL ok = Thread32First(snap, &te); ok && !th; ok = Thread32Next(snap, &te)) {
            if (te.th32OwnerProcessID != GetCurrentProcessId()) continue;
            HANDLE h = OpenThread(THREAD_ALL_ACCESS, FALSE, te.th32ThreadID);
            if (!h) continue;
            PWSTR d = NULL;
            char name[64] = "";
            if (SUCCEEDED(GetThreadDescription(h, &d)) && d) WideCharToMultiByte(CP_UTF8, 0, d, -1, name, sizeof name, NULL, NULL);
            if (d) LocalFree(d);
            if (strstr(name, want)) th = h;
            else CloseHandle(h);
        }
        CloseHandle(snap);
    }
    hos_log("prof: sampling thread \"%s\"", want);
    const HMODULE exe = GetModuleHandleA(NULL);
    enum { SLOTS = 4096 };
    typedef struct { uint64_t key; uint32_t n; } Slot;
    typedef struct { uint32_t off[CHAIN_DEPTH]; uint64_t hash; uint32_t n; } ChainSlot;
    /* (each sampler its own: there can be several now) */
    Slot *leaf = (Slot *)calloc(SLOTS, sizeof(Slot)), *ours = (Slot *)calloc(SLOTS, sizeof(Slot));
    ChainSlot *chain = (ChainSlot *)calloc(SLOTS, sizeof(ChainSlot));
    char (*modname)[64] = (char (*)[64])calloc(64, 64);
    HMODULE *mods = (HMODULE *)calloc(64, sizeof(HMODULE));
    if (!leaf || !ours || !chain || !modname || !mods) return 0;
    int nmods = 0;
    uint32_t total = 0;
    DWORD last = GetTickCount();
    /* HOS_SAMPLE_FILE=<path>: every sample's whole stack too, one line of module+offset frames (leaf first), for
       an offline profile (work/prof.py maps them to functions with the linker maps) */
    FILE *stacks = getenv("HOS_SAMPLE_FILE") ? fopen(getenv("HOS_SAMPLE_FILE"), "w") : NULL;
    for (;;) {
        Sleep(1);
        if (SuspendThread(th) == (DWORD)-1) return 0;   /* (the thread ended) */
        CONTEXT ctx = {0};
        ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
        const BOOL got = GetThreadContext(th, &ctx);
        uint64_t keys[2] = {0, 0};
        uint32_t chain_off[CHAIN_DEPTH] = {0};
        int chain_n = 0;
        char stack_line[1024];
        int stack_len = 0;
        if (got) {
            for (int depth = 0; depth < 48 && ctx.Rip; depth++) {
                HMODULE m = NULL;
                GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                   (LPCSTR)ctx.Rip, &m);
                int mi = -1;
                for (int i = 0; i < nmods; i++) if (mods[i] == m) mi = i;
                if (mi < 0 && nmods < 64) {
                    mi = nmods++;
                    mods[mi] = m;
                    char path[MAX_PATH] = "?";
                    if (m) GetModuleFileNameA(m, path, MAX_PATH);
                    const char *b = strrchr(path, '\\');
                    snprintf(modname[mi], sizeof modname[mi], "%s", b ? b + 1 : path);
                }
                const uint64_t key = (uint64_t)(mi < 0 ? 63 : mi) << 56 | (ctx.Rip - (uint64_t)m);
                if (stacks && stack_len < (int)sizeof stack_line - 96)
                    stack_len += snprintf(stack_line + stack_len, sizeof stack_line - stack_len, "%s%s+%llx",
                                          depth ? ";" : "", mi < 0 ? "?" : modname[mi],
                                          (unsigned long long)(ctx.Rip - (uint64_t)m));
                if (depth == 0) keys[0] = key;
                if (m == exe && !keys[1]) keys[1] = key;
                if (m == exe && chain_n < CHAIN_DEPTH) chain_off[chain_n++] = (uint32_t)(ctx.Rip - (uint64_t)m);
                if (chain_n == CHAIN_DEPTH && !stacks) break;
                DWORD64 image = 0;
                PRUNTIME_FUNCTION f = RtlLookupFunctionEntry(ctx.Rip, &image, NULL);
                if (!f) break;
                void *hd;
                DWORD64 frame;
                RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, ctx.Rip, f, &ctx, &hd, &frame, NULL);
            }
        }
        ResumeThread(th);
        if (stacks && got && stack_len) fprintf(stacks, "%s\n", stack_line);
        if (got) {
            total++;
            for (int t = 0; t < 2; t++) {
                if (!keys[t]) continue;
                Slot *tab = t ? ours : leaf;
                for (uint32_t s = (uint32_t)(keys[t] * 0x9E3779B97F4A7C15ull >> 52), k = 0; k < SLOTS; k++, s = (s + 1) % SLOTS) {
                    if (tab[s].key == keys[t]) { tab[s].n++; break; }
                    if (!tab[s].key) { tab[s].key = keys[t], tab[s].n = 1; break; }
                }
            }
            if (chain_n) {
                uint64_t h = 1469598103934665603ull;   /* (FNV-1a over the offsets; 0 marks a free slot) */
                for (int i = 0; i < chain_n; i++) h = (h ^ chain_off[i]) * 1099511628211ull;
                if (!h) h = 1;
                for (uint32_t s = (uint32_t)(h >> 52), k = 0; k < SLOTS; k++, s = (s + 1) % SLOTS) {
                    if (chain[s].hash == h && !memcmp(chain[s].off, chain_off, sizeof chain_off)) { chain[s].n++; break; }
                    if (!chain[s].hash) {
                        chain[s].hash = h, chain[s].n = 1;
                        memcpy(chain[s].off, chain_off, sizeof chain_off);
                        break;
                    }
                }
            }
        }
        if (GetTickCount() - last >= ms) {
            last = GetTickCount();
            for (int t = 0; t < 2; t++) {
                Slot *tab = t ? ours : leaf;
                char line[2048];
                int len = snprintf(line, sizeof line, "prof-sample %s (%u samples) [%s]:", t ? "ours" : "leaf", total, want);
                for (int r = 0; r < 30 && len < (int)sizeof line - 64; r++) {
                    int best = -1;
                    for (int s = 0; s < SLOTS; s++) if (tab[s].n && (best < 0 || tab[s].n > tab[best].n)) best = s;
                    if (best < 0) break;
                    len += snprintf(line + len, sizeof line - len, " %s+%llx %u,", modname[tab[best].key >> 56],
                                    (unsigned long long)(tab[best].key & ((1ull << 56) - 1)), tab[best].n);
                    tab[best].n = 0;
                }
                hos_log("%s", line);
                memset(tab, 0, SLOTS * sizeof(Slot));
            }
            {   /* the chains: exe+a<+b<+c, the 20 most frequent */
                char line[4096];
                int len = snprintf(line, sizeof line, "prof-sample %s (%u samples) [%s]:", "chain", total, want);
                for (int r = 0; r < 20 && len < (int)sizeof line - 160; r++) {
                    int best = -1;
                    for (int s = 0; s < SLOTS; s++) if (chain[s].n && (best < 0 || chain[s].n > chain[best].n)) best = s;
                    if (best < 0) break;
                    len += snprintf(line + len, sizeof line - len, " AkynoLeyend.exe+%x", chain[best].off[0]);
                    for (int i = 1; i < CHAIN_DEPTH && chain[best].off[i]; i++)
                        len += snprintf(line + len, sizeof line - len, "<+%x", chain[best].off[i]);
                    len += snprintf(line + len, sizeof line - len, " %u,", chain[best].n);
                    chain[best].n = 0;
                }
                hos_log("%s", line);
                memset(chain, 0, SLOTS * sizeof(ChainSlot));
            }
            total = 0;
            if (stacks) fflush(stacks);
        }
    }
    return 0;
}

/* HOS_THREAD_TIMES=<seconds>: every interval, the process's threads that used over 5% of a core, by name, with
   their share of one core (which thread holds the frame back) */
static DWORD WINAPI thread_times_thread(void *p) {
    const DWORD ms = (DWORD)(uintptr_t)p * 1000;
    enum { MAX = 512 };
    static struct { DWORD tid; uint64_t cpu; } last[MAX];
    int nlast = 0;
    for (;;) {
        Sleep(ms);
        HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
        THREADENTRY32 te = {sizeof te};
        char line[4096];
        int n = snprintf(line, sizeof line, "threads in %u s:", (unsigned)(ms / 1000));
        static struct { DWORD tid; uint64_t cpu; } now[MAX];
        int nnow = 0;
        for (BOOL ok = Thread32First(snap, &te); ok; ok = Thread32Next(snap, &te)) {
            if (te.th32OwnerProcessID != GetCurrentProcessId() || nnow >= MAX) continue;
            HANDLE h = OpenThread(THREAD_QUERY_LIMITED_INFORMATION, FALSE, te.th32ThreadID);
            if (!h) continue;
            FILETIME c, x, k, u;
            uint64_t cpu = 0;
            if (GetThreadTimes(h, &c, &x, &k, &u))
                cpu = (((uint64_t)k.dwHighDateTime << 32) | k.dwLowDateTime) + (((uint64_t)u.dwHighDateTime << 32) | u.dwLowDateTime);
            uint64_t before = 0;
            int seen = 0;
            for (int i = 0; i < nlast; i++)
                if (last[i].tid == te.th32ThreadID) before = last[i].cpu, seen = 1;
            now[nnow].tid = te.th32ThreadID, now[nnow].cpu = cpu, nnow++;
            const double pct = seen ? (double)(cpu - before) / (ms * 10000.0) * 100.0 : 0;
            if (pct >= 5.0 && n < (int)sizeof line - 96) {
                PWSTR d = NULL;
                char name[64] = "?";
                if (SUCCEEDED(GetThreadDescription(h, &d)) && d && d[0]) WideCharToMultiByte(CP_UTF8, 0, d, -1, name, sizeof name, NULL, NULL);
                if (d) LocalFree(d);
                n += snprintf(line + n, sizeof line - n, " %s %.0f%%;", name, pct);
            }
            CloseHandle(h);
        }
        CloseHandle(snap);
        memcpy(last, now, sizeof(now[0]) * (size_t)nnow);
        nlast = nnow;
        hos_log("prof: %s", line);
    }
    return 0;
}

/* (hookshot) HOS_SAMPLE_ALL=<path> (with HOS_PROFILE): while <path>.go exists, every 2 ms every guest thread and the
   renderer's threads (descriptions starting "mkw_vk") are sampled at the same instant: one line per thread,
   "<ms> <name>|<frames>", the frames module+offset leaf first (16 at most). What each thread does while another waits:
   the frame's critical path (scripts/crit.py) */
/* HOS_WATCH=<file> (diagnostic): when <file> exists (up to 4 guest addresses in hex), CPU data breakpoints on them on
   every guest thread: 4 s on reads and writes, then 4 s on writes; <file>.out gets, by address and the host place of
   the access, how many; then <file> is renamed <file>.done and the next one may come. */
static uint64_t watch_keys[8192];
static volatile LONG watch_counts[8192];
static volatile LONG watch_phase;
static LONG CALLBACK watch_handler(EXCEPTION_POINTERS *e) {
    if (e->ExceptionRecord->ExceptionCode != EXCEPTION_SINGLE_STEP) return EXCEPTION_CONTINUE_SEARCH;
    const DWORD64 hit = e->ContextRecord->Dr6 & 15;
    if (!hit) return EXCEPTION_CONTINUE_SEARCH;
    int idx = 0;
    while (!(hit >> idx & 1)) idx++;
    const uint64_t key = ((uint64_t)(watch_phase & 1) << 62) | ((uint64_t)idx << 58) | (uint64_t)e->ExceptionRecord->ExceptionAddress;
    for (uint32_t i = (uint32_t)((key >> 2) * 2654435761u) & 8191, n = 0; n < 8192; n++, i = (i + 1) & 8191) {
        uint64_t k = __atomic_load_n(&watch_keys[i], __ATOMIC_RELAXED);
        if (!k) {
            uint64_t expect = 0;
            if (__atomic_compare_exchange_n(&watch_keys[i], &expect, key, 0, __ATOMIC_RELAXED, __ATOMIC_RELAXED)) k = key;
            else k = expect;
        }
        if (k == key) { InterlockedIncrement(&watch_counts[i]); break; }
    }
    e->ContextRecord->Dr6 = 0;
    return EXCEPTION_CONTINUE_EXECUTION;
}
static void watch_arm(const uint64_t *addr, int n, int rw) {
    static HANDLE gh[1024];
    static const char *gn[1024];
    const int ng = hos_thread_handles(gh, gn, 1024);
    for (int i = 0; i < ng; i++) {
        if (GetThreadId(gh[i]) == GetCurrentThreadId()) continue;
        if (SuspendThread(gh[i]) == (DWORD)-1) continue;
        CONTEXT c;
        memset(&c, 0, sizeof c);
        c.ContextFlags = CONTEXT_DEBUG_REGISTERS;
        if (GetThreadContext(gh[i], &c)) {
            DWORD64 *dr[4] = {&c.Dr0, &c.Dr1, &c.Dr2, &c.Dr3};
            c.Dr7 = 0;
            for (int k = 0; k < n && rw; k++) {
                *dr[k] = (DWORD64)GP(addr[k]);
                c.Dr7 |= (DWORD64)1 << (k * 2);                     /* (local enable) */
                c.Dr7 |= (DWORD64)((rw & 3) | (3 << 2)) << (16 + k * 4);   /* (rw, 4 bytes) */
            }
            c.Dr6 = 0;
            SetThreadContext(gh[i], &c);
        }
        ResumeThread(gh[i]);
    }
}
static DWORD WINAPI watch_thread(void *p) {
    const char *path = (const char *)p;
    AddVectoredExceptionHandler(1, watch_handler);
    for (;;) {
        Sleep(300);
        FILE *f = fopen(path, "r");
        if (!f) continue;
        uint64_t addr[4];
        int n = 0;
        unsigned long long v;
        while (n < 4 && fscanf(f, "%llx", &v) == 1) addr[n++] = v;
        fclose(f);
        memset(watch_keys, 0, sizeof watch_keys);
        memset((void *)watch_counts, 0, sizeof watch_counts);
        for (int k = 0; k < n; k++) hos_log("watch: %llx holds %08x", (unsigned long long)addr[k], *(uint32_t *)GP(addr[k]));
        for (int ph = 0; ph < 2; ph++) {
            watch_phase = ph;
            for (int t = 0; t < 4; t++) {   /* (threads that started since) */
                watch_arm(addr, n, ph ? 1 : 3);
                Sleep(1000);
            }
        }
        watch_arm(addr, 0, 0);
        char out[MAX_PATH], done[MAX_PATH];
        snprintf(out, sizeof out, "%s.out", path);
        snprintf(done, sizeof done, "%s.done", path);
        f = fopen(out, "a");
        if (f) {
            for (int i = 0; i < 8192; i++)
                if (watch_keys[i]) {
                    const uint64_t k = watch_keys[i], rip = k & ((1ULL << 58) - 1);
                    HMODULE m = NULL;
                    char full[MAX_PATH] = "?";
                    GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT, (LPCSTR)rip, &m);
                    if (m) GetModuleFileNameA(m, full, sizeof full);
                    const char *name = strrchr(full, 92) ? strrchr(full, 92) + 1 : full;
                    fprintf(f, "%llx %s %s+%llx %ld\n", (unsigned long long)addr[(k >> 58) & 3], k >> 62 & 1 ? "w" : "rw", name,
                            (unsigned long long)(rip - (uint64_t)m), watch_counts[i]);
                }
            fclose(f);
        }
        DeleteFileA(done);
        MoveFileA(path, done);
        hos_log("watch: done");
    }
}
static DWORD WINAPI sample_all_thread(void *p) {
    const char *path = (const char *)p;
    char go[MAX_PATH];
    snprintf(go, sizeof go, "%s.go", path);
    FILE *out = NULL;
    static HMODULE mods[64];
    static char modname[64][64];
    int nmods = 0;
    enum { MAXT = 128 };
    static HANDLE th[MAXT];
    static char tn[MAXT][64];
    int nt = 0;
    int64_t t0 = 0;
    for (;;) {
        if (GetFileAttributesA(go) == INVALID_FILE_ATTRIBUTES) {
            if (out) { fclose(out); out = NULL; hos_log("prof: all-thread sampling stopped"); }
            Sleep(200);
            continue;
        }
        if (!out) {
            out = fopen(path, "a");
            if (!out) { Sleep(1000); continue; }
            for (int i = 0; i < nt; i++) CloseHandle(th[i]);
            nt = 0;
            static HANDLE gh[1024];
            static const char *gn[1024];
            const int ng = hos_thread_handles(gh, gn, 1024);
            HANDLE snap = CreateToolhelp32Snapshot(TH32CS_SNAPTHREAD, 0);
            THREADENTRY32 te = {sizeof te};
            for (BOOL ok = Thread32First(snap, &te); ok && nt < MAXT; ok = Thread32Next(snap, &te)) {
                if (te.th32OwnerProcessID != GetCurrentProcessId() || te.th32ThreadID == GetCurrentThreadId()) continue;
                char name[64] = "";
                for (int i = 0; i < ng; i++)
                    if (GetThreadId(gh[i]) == te.th32ThreadID) { snprintf(name, sizeof name, "%s", gn[i]); break; }
                HANDLE h = OpenThread(THREAD_ALL_ACCESS, FALSE, te.th32ThreadID);
                if (!h) continue;
                if (!name[0]) {
                    PWSTR d = NULL;
                    char desc[64] = "";
                    if (SUCCEEDED(GetThreadDescription(h, &d)) && d) WideCharToMultiByte(CP_UTF8, 0, d, -1, desc, sizeof desc, NULL, NULL);
                    if (d) LocalFree(d);
                    if (!strncmp(desc, "mkw_vk", 6)) snprintf(name, sizeof name, "%s", desc);
                }
                if (!name[0]) { CloseHandle(h); continue; }
                for (char *q = name; *q; q++) if (*q == ' ' || *q == '|') *q = '_';
                th[nt] = h;
                snprintf(tn[nt], sizeof tn[nt], "%s", name);
                nt++;
            }
            CloseHandle(snap);
            t0 = hos_now_ns();
            hos_log("prof: all-thread sampling of %d threads into %s", nt, path);
        }
        Sleep(2);
        const long ms = (long)((hos_now_ns() - t0) / 1000000);
        for (int i = 0; i < nt; i++) {
            if (SuspendThread(th[i]) == (DWORD)-1) continue;
            CONTEXT ctx = {0};
            ctx.ContextFlags = CONTEXT_CONTROL | CONTEXT_INTEGER;
            const BOOL got = GetThreadContext(th[i], &ctx);
            char line[1024];
            int len = snprintf(line, sizeof line, "%ld %s|", ms, tn[i]);
            for (int depth = 0; got && depth < 16 && ctx.Rip && len < (int)sizeof line - 96; depth++) {
                HMODULE m = NULL;
                GetModuleHandleExA(GET_MODULE_HANDLE_EX_FLAG_FROM_ADDRESS | GET_MODULE_HANDLE_EX_FLAG_UNCHANGED_REFCOUNT,
                                   (LPCSTR)ctx.Rip, &m);
                int mi = -1;
                for (int k = 0; k < nmods; k++) if (mods[k] == m) mi = k;
                if (mi < 0 && nmods < 64) {
                    mi = nmods++;
                    mods[mi] = m;
                    char mp[MAX_PATH] = "?";
                    if (m) GetModuleFileNameA(m, mp, MAX_PATH);
                    const char *b = strrchr(mp, '\\');
                    snprintf(modname[mi], sizeof modname[mi], "%s", b ? b + 1 : mp);
                }
                len += snprintf(line + len, sizeof line - len, "%s%s+%llx", depth ? ";" : "", mi < 0 ? "?" : modname[mi],
                                (unsigned long long)(ctx.Rip - (uint64_t)m));
                DWORD64 image = 0;
                PRUNTIME_FUNCTION f = RtlLookupFunctionEntry(ctx.Rip, &image, NULL);
                if (!f) break;
                void *hd;
                DWORD64 frame;
                RtlVirtualUnwind(UNW_FLAG_NHANDLER, image, ctx.Rip, f, &ctx, &hd, &frame, NULL);
            }
            ResumeThread(th[i]);
            fprintf(out, "%s\n", line);
        }
    }
    return 0;
}

void hos_prof_start(void) {
    const char *tt = getenv("HOS_THREAD_TIMES");
    if (tt && atoi(tt) > 0) CreateThread(NULL, 0, thread_times_thread, (void *)(uintptr_t)atoi(tt), 0, NULL);
    const char *e = getenv("HOS_PROFILE");
    if (e && atoi(e) > 0) CreateThread(NULL, 0, prof_thread, (void *)(uintptr_t)atoi(e), 0, NULL);
    const char *s = getenv("HOS_SAMPLE");
    if (e && atoi(e) > 0 && s && *s) {   /* (0.4.5-test.4) one sampler for each name of a|b|c */
        for (const char *a = s; *a;) {
            const char *b = strchr(a, '|');
            const size_t n = b ? (size_t)(b - a) : strlen(a);
            char *name = n ? (char *)calloc(n + 1, 1) : NULL;
            if (name) {
                memcpy(name, a, n);
                CreateThread(NULL, 0, sample_thread, name, 0, NULL);
            }
            a += n + (b ? 1 : 0);
        }
    }
    const char *all = getenv("HOS_SAMPLE_ALL");
    if (all && *all) CreateThread(NULL, 0, sample_all_thread, (void *)all, 0, NULL);
    const char *watch = getenv("HOS_WATCH");
    if (watch && *watch) CreateThread(NULL, 0, watch_thread, (void *)watch, 0, NULL);
}
void hos_mem_checkpoint(const char *what) { (void)what; }        /* (hos_prof.c: HOS_MEM_TIMELINE) */
int hos_game_cores(void) { return 0; }                           /* (totk_cores.c) */
int hos_blank_cached_icon(const char *guest, const char *host) { (void)guest, (void)host; return 0; }   /* (TOTK) */
int hos_ultrawide_redirect(const char *guest, char *out, size_t cap) { (void)guest, (void)out, (void)cap; return 0; }
uint64_t hos_title_input(uint64_t buttons) { return buttons; }   /* (totk_title.c) */
uint64_t hos_frame_step_buttons(uint64_t buttons) { return buttons; }   /* (nn_vi.c) */
/* (hookshot) hos_sdl_pads, hos_sdl_rumble: host/pad_sdl.c (from TOTKPort; SDL2.dll beside the exe) */

/* TOTK's emulated GPU (gpu.c, its Maxwell command processor), which nvdrv.c and the debug commands call into: MKW
   has none (its NVN2 calls go to nvn_native.c), so a submission is only counted. */
int hos_gpu_async(void) { return 0; }
void hos_gpu_submit(int channel_fd, const uint64_t *entries, uint32_t n) {
    static volatile LONG seen;
    if (InterlockedIncrement(&seen) <= 4) hos_log("gpu: submit of %u entries on channel %d (no GPU yet)", n, channel_fd);
    (void)entries;
}
void hos_gpu_queue_submit(int channel_fd, const uint64_t *entries, uint32_t n, int incr_id) {
    (void)incr_id;
    hos_gpu_submit(channel_fd, entries, n);
}

/* The loop-header interrupt polls (nx2/poll.py): the virtual cores (HOS_VCORES) ask a thread holding a core a
   waiter should have to give it up there, so guest code with no nn::os call or SVC in it (a long job) is preempted
   as Horizon would preempt it. */
void a64_poll(Ctx *c) {
    c->poll = 0;
    void hos_vcore_checkpoint(void);
    hos_vcore_checkpoint();
}

/* CNTPCT_EL0 at the Switch 2's 31.25 MHz (rt/a64_rt.c's default counts the Switch 1's 19.2 MHz). The SDK checks
   nn::os::GetSystemTickFrequency against 31250000 at init and aborts otherwise. */
uint64_t a64_cntpct_host(void) {
    static LARGE_INTEGER base;
    static uint64_t mult;
    LARGE_INTEGER now;
    if (!__atomic_load_n(&mult, __ATOMIC_ACQUIRE)) {
        LARGE_INTEGER f, b;
        QueryPerformanceFrequency(&f);
        QueryPerformanceCounter(&b);
        base = b;
        __atomic_store_n(&mult, (HOS_TICK_HZ << 32) / (uint64_t)f.QuadPart, __ATOMIC_RELEASE);
    }
    QueryPerformanceCounter(&now);
    return (uint64_t)(((unsigned __int128)(uint64_t)(now.QuadPart - base.QuadPart) * mult) >> 32);
}

/* ---- what the renderer (gpu/render, TOTKPort's) asks of TOTKPort's hos_prof.c and totk_ultrawide.c ---- */
int hos_ab(void) { return 0; }                    /* (hos_prof.c: A/B measurement phases) */
/* (with the renderer's mem: lines) HOS_MEM_MAP=1: how much of the guest window is committed, and its resident part */
void hos_memory_map_log(void) {
    static int on = -1;
    if (on < 0) on = getenv("HOS_MEM_MAP") != NULL;
    if (!on) return;
    uint64_t committed = 0, regions = 0;
    for (uint64_t a = 0; a < HOS_GUEST_SPACE;) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(GP(a), &m, sizeof m)) break;
        const uint64_t end = (uint64_t)((uint8_t *)m.BaseAddress + m.RegionSize - (uint8_t *)GP(0));
        if (m.State == MEM_COMMIT) committed += m.RegionSize, regions++;
        a = end > a ? end : a + 0x1000;
    }
    hos_log("mem: guest window %llu MB committed in %llu regions", (unsigned long long)(committed >> 20),
            (unsigned long long)regions);
    /* the rest of the address space: private memory by allocation, the largest */
    struct { uint64_t base, bytes; } top[8] = {{0}};
    uint64_t other = 0, cur_base = 0, cur = 0;
    const uint64_t g0 = (uint64_t)(uintptr_t)GP(0), g1 = g0 + HOS_GUEST_SPACE;
    for (uint64_t a = 0x10000; a < 0x7FFFFFFF0000ull;) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery((void *)(uintptr_t)a, &m, sizeof m)) break;
        const uint64_t base = (uint64_t)(uintptr_t)m.AllocationBase, end = (uint64_t)(uintptr_t)m.BaseAddress + m.RegionSize;
        if (base != cur_base) {
            for (int k = 0; k < 8 && cur; k++)
                if (cur > top[k].bytes) {
                    memmove(&top[k + 1], &top[k], (size_t)(7 - k) * sizeof top[0]);
                    top[k].base = cur_base, top[k].bytes = cur;
                    break;
                }
            cur_base = base, cur = 0;
        }
        if (m.State == MEM_COMMIT && m.Type == MEM_PRIVATE && (a < g0 || a >= g1)) other += m.RegionSize, cur += m.RegionSize;
        a = end > a ? end : a + 0x1000;
    }
    hos_log("mem: private outside the guest window %llu MB; largest: %llx %llu MB, %llx %llu MB, %llx %llu MB, %llx %llu "
            "MB, %llx %llu MB, %llx %llu MB", (unsigned long long)(other >> 20), (unsigned long long)top[0].base,
            (unsigned long long)(top[0].bytes >> 20), (unsigned long long)top[1].base, (unsigned long long)(top[1].bytes >> 20),
            (unsigned long long)top[2].base, (unsigned long long)(top[2].bytes >> 20), (unsigned long long)top[3].base,
            (unsigned long long)(top[3].bytes >> 20), (unsigned long long)top[4].base, (unsigned long long)(top[4].bytes >> 20),
            (unsigned long long)top[5].base, (unsigned long long)(top[5].bytes >> 20));
}
void hos_ultrawide_apply(void) {}                 /* (totk_ultrawide.c) */
float hos_view_aspect;                            /* (totk_ultrawide.c: 0, the game's own 16:9) */
void hos_host_thread_register_self(const char *name) {   /* (hos_prof.c: names for its stats; here the thread's description) */
    wchar_t w[64];
    if (MultiByteToWideChar(CP_UTF8, 0, name, -1, w, 64)) SetThreadDescription(GetCurrentThread(), w);
}
void hos_process_memory(uint64_t *private_bytes, uint64_t *working_set) {
    typedef struct {
        DWORD cb, PageFaultCount;
        SIZE_T PeakWorkingSetSize, WorkingSetSize, QuotaPeakPagedPoolUsage, QuotaPagedPoolUsage,
            QuotaPeakNonPagedPoolUsage, QuotaNonPagedPoolUsage, PagefileUsage, PeakPagefileUsage, PrivateUsage;
    } Counters;
    typedef BOOL(WINAPI * Fn)(HANDLE, Counters *, DWORD);
    static Fn fn;
    if (!fn) fn = (Fn)(void *)GetProcAddress(GetModuleHandleA("kernel32.dll"), "K32GetProcessMemoryInfo");
    Counters m;
    memset(&m, 0, sizeof m);
    m.cb = sizeof m;
    if (!fn || !fn(GetCurrentProcess(), &m, sizeof m)) memset(&m, 0, sizeof m);
    *private_bytes = m.PrivateUsage;
    *working_set = m.WorkingSetSize;
}

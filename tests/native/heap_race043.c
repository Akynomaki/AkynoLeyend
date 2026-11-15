/* Two or more first touches of one page of a heap on demand at the same moment (the handoff's risk): the block of
   host/mkw_glue.c as it is, over a 1 GiB reservation. Each round every thread writes the same fresh page at once;
   the 2 MB is decommitted again for the next round. A handler that sees the page already committed by the other
   thread must resume, not pass the exception on. */
#include <stdint.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdarg.h>
#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#define PSAPI_VERSION 2
#include <psapi.h>
#include <string.h>
static uint8_t *window;
#define A64_MEM window
#define HOS_GUEST_SPACE (1ULL << 30)
#define GP(a) (window + (a))
static void hos_log(const char *format, ...) {
    va_list ap;
    va_start(ap, format);
    vprintf(format, ap);
    va_end(ap);
    printf("\n");
}
static void hos_log_flush(void) { fflush(stdout); }
// MKW_GLUE_BLOCK

#define HEAP 0x10000000ULL
#define SIZE 0x10000000ULL
#define THREADS 8
static volatile LONG round_no, ready, done, stop;
static volatile LONG64 target;
static volatile LONG unhandled;

static LONG WINAPI last_chance(EXCEPTION_POINTERS *info) {
    InterlockedIncrement(&unhandled);
    printf("UNHANDLED %#lx at guest %#llx in round %ld\n", info->ExceptionRecord->ExceptionCode,
           (unsigned long long)(info->ExceptionRecord->ExceptionInformation[1] - (uintptr_t)window), round_no);
    fflush(stdout);
    TerminateProcess(GetCurrentProcess(), 3);
    return EXCEPTION_EXECUTE_HANDLER;
}

static DWORD WINAPI toucher(void *p) {
    const int id = (int)(uintptr_t)p;
    LONG seen = 0;
    for (;;) {
        InterlockedIncrement(&ready);
        while (round_no == seen && !stop) YieldProcessor();
        if (stop) return 0;
        seen = round_no;
        window[(uint64_t)target + (uint64_t)id] = (uint8_t)(id + 1);   /* (the same page, a byte of its own) */
        InterlockedIncrement(&done);
    }
}

int main(int argc, char **argv) {
    const int rounds = argc > 1 ? atoi(argv[1]) : 20000;
    window = VirtualAlloc(NULL, HOS_GUEST_SPACE, MEM_RESERVE, PAGE_NOACCESS);
    AddVectoredExceptionHandler(1, commit_on_touch);
    SetUnhandledExceptionFilter(last_chance);
    if (!hos_heap_on_demand(HEAP, SIZE)) { printf("not on demand\n"); return 2; }
    HANDLE t[THREADS];
    for (int i = 0; i < THREADS; i++) t[i] = CreateThread(NULL, 0, toucher, (void *)(uintptr_t)i, 0, NULL);
    int bad = 0;
    for (int r = 0; r < rounds; r++) {
        while (ready < THREADS) YieldProcessor();
        const uint64_t granule = HEAP + ((uint64_t)(r % 100) << 21);
        InterlockedExchange64(&target, (LONG64)(granule + 0x1000 * (uint64_t)(r % 400) + 16));
        InterlockedExchange(&ready, 0);
        InterlockedExchange(&done, 0);
        InterlockedIncrement(&round_no);
        while (done < THREADS) YieldProcessor();
        for (int i = 0; i < THREADS; i++) bad += window[(uint64_t)target + (uint64_t)i] != (uint8_t)(i + 1);
        VirtualFree(GP(granule), 0x200000, MEM_DECOMMIT);
    }
    InterlockedExchange(&stop, 1);
    WaitForMultipleObjects(THREADS, t, TRUE, 5000);
    printf("ROUNDS %d threads %d wrong_bytes %d unhandled %ld\n", rounds, THREADS, bad, unhandled);
    return bad || unhandled ? 1 : 0;
}

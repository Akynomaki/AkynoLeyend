"""The page table flush (gpu/vk/vk_table_runs.h) against the expansion it replaces, compiled and run natively."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.native_tools import native_cxx

ROOT = Path(__file__).resolve().parents[1]

FIXTURE = r'''
#include "vk_table_runs.h"
#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <random>
#include <utility>
using namespace mkwvk;

// ---- allocation accounting and injected failures (every operator new of this program) ----
static bool counting = false;
static long long fail_after = -1;        // (>= 0: that many more allocations succeed, then every one is refused)
static unsigned long long live = 0, peak = 0, refused = 0;
static void* take(size_t n) {
    if (counting && fail_after == 0) { refused++; return nullptr; }
    if (counting && fail_after > 0) fail_after--;
    size_t* p = (size_t*)std::malloc(n + 16);
    if (!p) return nullptr;
    p[0] = n;
    if (counting) { live += n; if (live > peak) peak = live; }
    return (char*)p + 16;
}
static void give(void* q) noexcept {
    if (!q) return;
    size_t* p = (size_t*)((char*)q - 16);
    if (counting && live >= p[0]) live -= p[0];
    std::free(p);
}
void* operator new(size_t n) { void* p = take(n); if (!p) throw std::bad_alloc(); return p; }
void* operator new[](size_t n) { void* p = take(n); if (!p) throw std::bad_alloc(); return p; }
void* operator new(size_t n, const std::nothrow_t&) noexcept { return take(n); }
void* operator new[](size_t n, const std::nothrow_t&) noexcept { return take(n); }
void operator delete(void* p) noexcept { give(p); }
void operator delete[](void* p) noexcept { give(p); }
void operator delete(void* p, size_t) noexcept { give(p); }
void operator delete[](void* p, size_t) noexcept { give(p); }

struct Transfer { uint64_t first; std::vector<uint64_t> values; };
static bool operator==(const Transfer& a, const Transfer& b) { return a.first == b.first && a.values == b.values; }

// ---- the reference: memory_table_flush as it was before (0.4.3-test.4 r3), line for line ----
static std::vector<Transfer> reference(const std::vector<TableRun>& pending) {
    std::vector<Transfer> out;
    std::vector<std::pair<uint64_t, uint64_t>> pages;
    for (const TableRun& r : pending)
        for (uint64_t i = 0; i < r.count; i++) pages.push_back({r.first + i, r.address ? r.address + (i << 12) : 0});
    std::stable_sort(pages.begin(), pages.end(), [](const auto& a, const auto& b) { return a.first < b.first; });
    std::vector<uint64_t> run;
    uint64_t run_first = 0;
    const auto emit = [&] {
        if (!run.empty()) out.push_back({run_first, run});
        run.clear();
    };
    for (size_t i = 0; i < pages.size(); i++) {
        if (i + 1 < pages.size() && pages[i + 1].first == pages[i].first) continue;
        if (!run.empty() && (pages[i].first != run_first + run.size() || run.size() == 8192)) emit();
        if (run.empty()) run_first = pages[i].first;
        run.push_back(pages[i].second);
    }
    emit();
    return out;
}

// (the table as the GPU would have it: the transfers applied in the order recorded, over a known earlier content)
static std::map<uint64_t, uint64_t> applied(const std::vector<Transfer>& transfers) {
    std::map<uint64_t, uint64_t> table;
    for (const Transfer& t : transfers)
        for (size_t i = 0; i < t.values.size(); i++) table[t.first + i] = t.values[i];
    return table;
}

// (no two transfers of one flush may write the same page: recorded order alone does not order two writes on the GPU)
static bool disjoint(const std::vector<Transfer>& transfers) {
    std::vector<std::pair<uint64_t, uint64_t>> spans;
    for (const Transfer& t : transfers) spans.push_back({t.first, t.first + t.values.size()});
    std::sort(spans.begin(), spans.end());
    for (size_t i = 1; i < spans.size(); i++)
        if (spans[i].first < spans[i - 1].second) return false;
    return true;
}

static std::vector<Transfer> flush(const std::vector<TableRun>& pending, size_t capacity, TableFlushStats& stats,
                                   std::vector<Transfer>* sink = nullptr) {
    static std::vector<TableRun> ranges, spare;
    static uint64_t block[kTableChunk];
    std::vector<Transfer> out;
    table_runs_flush(pending, ranges, spare, block, capacity,
                     [&](uint64_t first, const uint64_t* v, size_t n) {
                         if (n == 0 || n > capacity || n * 8 > 65536) { std::printf("FAIL transfer of %zu values\n", n); std::exit(1); }
                         if (sink) return;
                         out.push_back({first, std::vector<uint64_t>(v, v + n)});
                     },
                     stats);
    if (!disjoint(out)) { std::printf("FAIL a page is written by two transfers of one flush\n"); std::exit(1); }
    return out;
}

static int failures = 0;
static void check(bool ok, const char* what, const char* name) {
    if (!ok) { std::printf("FAIL %s: %s\n", name, what); failures++; }
}

static void compare(const char* name, const std::vector<TableRun>& pending) {
    const std::vector<Transfer> want = reference(pending);
    TableFlushStats st;
    const std::vector<Transfer> got = flush(pending, kTableChunk, st);
    check(st.resolved, "not resolved", name);
    check(got == want, "transfers differ from the reference", name);
    uint64_t unique = 0;
    for (const Transfer& t : want) unique += t.values.size();
    check(st.pages_out == unique, "pages written are not the unique pages", name);
    check(st.transfers == want.size(), "transfer count", name);
    // (a small block: more transfers, the same table)
    const std::vector<Transfer> small = flush(pending, 256, st);
    check(applied(small) == applied(want), "table differs with a 256-value block", name);
}

int main() {
    const uint64_t second_window = (8ull << 30) >> 12;   // (first page of the 0x7f00000000 window)
    compare("empty", {});
    compare("one run", {{10, 5, 0x1000000}});
    compare("zero run", {{10, 5, 0}});
    compare("count 0 is nothing", {{10, 0, 0x5000}, {20, 3, 0x9000}, {30, 0, 0}});
    compare("last write wins", {{100, 50, 0xA0000000}, {100, 50, 0xB0000000}});
    compare("mapped then zeroed", {{100, 50, 0xA0000000}, {100, 50, 0}});
    compare("zeroed then mapped", {{100, 50, 0}, {110, 10, 0xC0000000}});
    compare("hole punched", {{0, 100, 0xA0000000}, {40, 20, 0}});
    compare("split and offset kept", {{0, 100, 0xA0000000}, {40, 20, 0xB0000000}, {45, 5, 0xC0000000}});
    compare("covers several", {{0, 10, 0x1000}, {20, 10, 0x2000}, {40, 10, 0x3000}, {5, 40, 0x90000000}});
    compare("touching runs join", {{0, 10, 0x1000}, {10, 10, 0x80000}, {20, 10, 0}});
    compare("out of order", {{500, 10, 0x1000}, {100, 10, 0x2000}, {300, 10, 0x3000}, {95, 10, 0x4000}});
    compare("two windows", {{second_window - 4, 4, 0x70000000}, {second_window, 4, 0x71000000}, {5, 3, 0}, {second_window + 2, 100, 0}});
    compare("across the window edge", {{second_window - 100, 200, 0x70000000}});
    compare("exactly 64 KiB", {{1000, 8192, 0x40000000}});
    compare("64 KiB and one", {{1000, 8193, 0x40000000}});
    compare("above 64 KiB, cut and rewritten", {{0, 30000, 0x40000000}, {8000, 400, 0}, {8191, 3, 0x99000000}, {29999, 9000, 0x50000000}});
    compare("a 4 GB pool merged", {{second_window, 1 << 20, 0}, {second_window, 1 << 20, 0x200000000ull}, {second_window + 77, 1, 0}});

    std::mt19937_64 rng(20261110);
    for (int round = 0; round < 3000; round++) {
        std::vector<TableRun> pending;
        const int n = 1 + (int)(rng() % 24);
        const uint64_t span = round % 3 ? 300 : 40000;
        for (int i = 0; i < n; i++) {
            const uint64_t first = (rng() % 2 ? 0 : second_window - span / 2) + rng() % span;
            const uint64_t count = rng() % 9 == 0 ? 0 : 1 + rng() % (round % 5 == 0 ? 20000 : 200);
            pending.push_back({first, count, rng() % 4 == 0 ? 0 : (rng() % (1ull << 36)) << 12});
        }
        compare("random", pending);
    }

    // ---- many runs (r4 wrote more than 16384 of them in order, over each other): resolved like any other ----
    {
        std::vector<TableRun> pending;
        for (uint64_t i = 0; i < 16384 + 50; i++) pending.push_back({rng() % 5000, 1 + rng() % 9, (1 + rng() % 1000) << 12});
        compare("many runs", pending);
        std::vector<TableRun> same;
        for (uint64_t i = 0; i <= 16384; i++) same.push_back({10, 1, 0x1000ull * (i + 1)});
        TableFlushStats st;
        const auto got = flush(same, kTableChunk, st);
        check(got.size() == 1 && got[0].first == 10 && got[0].values.size() == 1 && got[0].values[0] == 0x1000ull * 16385,
              "16385 runs of one page are not one transfer of the last value", "many runs");
    }

    // ---- the Kokiri case: memory. 600 runs over 4 M pages, as merges of large pools leave them ----
    {
        std::vector<TableRun> pending;
        for (uint64_t i = 0; i < 200; i++) {
            pending.push_back({i * 5000, 20000, 0});
            pending.push_back({i * 5000, 20000, 0x100000000ull + (i << 28)});
            pending.push_back({i * 5000 + 100, 50, 0});
        }
        std::vector<Transfer> sink;
        TableFlushStats st;
        flush(pending, kTableChunk, st);   // (the thread's ranges, as after earlier frames)
        counting = true; live = peak = 0;
        flush(pending, kTableChunk, st, &sink);
        counting = false;
        const unsigned long long ours = peak;
        counting = true; live = peak = 0;
        { std::vector<std::pair<uint64_t, uint64_t>> pages; for (const TableRun& r : pending) for (uint64_t i = 0; i < r.count; i++) pages.push_back({r.first + i, 0}); }
        counting = false;
        std::printf("MEMORY runs %llu pages %llu unique %llu flush_peak_bytes %llu held_bytes %llu expansion_peak_bytes %llu\n",
                    (unsigned long long)st.runs, (unsigned long long)st.pages_set, (unsigned long long)st.pages_out, ours,
                    (unsigned long long)st.scratch, peak);
        check(st.pages_set == 200ull * 40050, "pages set", "memory");
        check(ours == 0, "a flush with warm ranges allocated", "memory");
        check(st.scratch <= 256 * 1024, "more than 256 KiB held", "memory");
        check(peak >= st.pages_set * 16, "the reference's expansion was not measured", "memory");
    }

    // ---- allocation refused at every point: never an exception out, never a table left incomplete, and never
    // two transfers of one page (r4 wrote the runs in order here: correct on a CPU, unordered on the GPU) ----
    {
        std::vector<std::vector<TableRun>> plans = {
            {{10, 1, 0x1000}, {10, 1, 0x2000}},
            {{0, 30000, 0x40000000}, {8000, 400, 0}, {8191, 3, 0x99000000}, {29999, 9000, 0x50000000},
             {100, 5, 0x77000000}, {50000, 10, 0}, {49990, 30, 0x88000000}},
            {{100, 50, 0xA0000000}, {100, 50, 0}, {90, 5, 0}, {120, 100, 0xB0000000}, {0, 0, 0x5000}, {130, 4, 0}},
            {{second_window - 100, 20000, 0x70000000}, {second_window, 9000, 0}, {5, 3, 0x1000}, {second_window + 8191, 2, 0x99000}},
            {{0, 40000, 0}, {0, 40000, 0x300000000ull}, {0, 40000, 0}, {20000, 1, 0x4000}},
        };
        for (int round = 0; round < 200; round++) {   // (and random ones)
            std::vector<TableRun> pending;
            const int n = 2 + (int)(rng() % 12);
            for (int i = 0; i < n; i++)
                pending.push_back({rng() % 400, rng() % 7 == 0 ? 0 : 1 + rng() % (round % 4 == 0 ? 12000 : 150), rng() % 3 == 0 ? 0 : (1 + rng() % 4096) << 12});
            plans.push_back(pending);
        }
        int fell_back = 0, resolved = 0, overlapping_plans = 0;
        static uint64_t block[kTableChunk];
        static std::vector<Transfer> got;
        got.reserve(1 << 12);
        static std::vector<std::vector<uint64_t>> store(1 << 12);
        for (auto& s : store) s.reserve(kTableChunk);
        static std::vector<uint64_t> firsts(1 << 12);
        for (const auto& pending : plans) {
            const auto want = applied(reference(pending));
            uint64_t set = 0;
            for (const TableRun& r : pending) set += r.count;
            if (set > want.size()) overlapping_plans++;
            for (long long k = 0; k < 12; k++) {
                std::vector<TableRun> ranges, spare;   // (cold: every allocation the flush makes is its own)
                size_t used = 0;
                TableFlushStats st;
                bool threw = false;
                counting = true; fail_after = k; refused = 0;
                try {
                    table_runs_flush(pending, ranges, spare, block, k % 2 ? kTableChunk : (size_t)256,
                                     [&](uint64_t first, const uint64_t* v, size_t n) {
                                         if (used < store.size()) { firsts[used] = first; store[used].assign(v, v + n); used++; }
                                     },
                                     st);
                } catch (...) { threw = true; }
                counting = false; fail_after = -1;
                check(!threw, "an exception left the flush", "refused");
                check(used < store.size(), "too many transfers for the test", "refused");
                got.clear();
                for (size_t i = 0; i < used; i++) got.push_back({firsts[i], store[i]});
                check(disjoint(got), "two transfers of one flush write the same page", "refused");
                check(applied(got) == want, "table incomplete or different after a refused allocation", "refused");
                uint64_t written = 0;
                for (const Transfer& t : got) written += t.values.size();
                check(written == want.size(), "pages written are not exactly the unique pages", "refused");
                if (st.resolved) resolved++; else fell_back++;
            }
        }
        std::printf("REFUSED no_memory_path %d resolved %d plans %zu overlapping %d\n", fell_back, resolved, plans.size(), overlapping_plans);
        check(fell_back > 100, "the path without memory was hardly exercised", "refused");
        check(resolved > 0, "the resolved path was never reached", "refused");
        check(overlapping_plans > 100, "the plans hardly overlap", "refused");
    }
    std::printf(failures ? "FAILED %d\n" : "OK\n", failures);
    return failures ? 1 : 0;
}
'''


THREADS = r"""
#include "vk_table_runs.h"
#include <atomic>
#include <cstdarg>
#include <cstdio>
#include <cstdlib>
#include <iterator>
#include <memory>
#include <new>
#include <thread>
static std::atomic<long long> retained{0}, taken{0}, transfers{0};
static void* take(size_t n) {
    size_t* h = (size_t*)std::malloc(n + 16);
    if (!h) return nullptr;
    *h = n;
    if (n == 65536) { retained += 65536; taken++; }
    return (char*)h + 16;
}
static void give(void* p) noexcept {
    if (!p) return;
    size_t* h = (size_t*)((char*)p - 16);
    if (*h == 65536) retained -= 65536;
    std::free(h);
}
void* operator new(size_t n) { void* p = take(n); if (!p) throw std::bad_alloc(); return p; }
void* operator new[](size_t n) { void* p = take(n); if (!p) throw std::bad_alloc(); return p; }
void* operator new(size_t n, const std::nothrow_t&) noexcept { return take(n); }
void* operator new[](size_t n, const std::nothrow_t&) noexcept { return take(n); }
void operator delete(void* p) noexcept { give(p); }
void operator delete[](void* p) noexcept { give(p); }
void operator delete(void* p, size_t) noexcept { give(p); }
void operator delete[](void* p, size_t) noexcept { give(p); }
namespace mkwvk {
thread_local std::vector<TableRun> table_pending;
thread_local bool table_defer;
using VkCommandBuffer = int;
int guest_pages_buffer;
int upload_command_buffer() { return 0; }
void vkCmdUpdateBuffer(int, int, uint64_t, uint64_t, const void*) { transfers++; }
void logf(const char*, ...) {}
// ACTUAL_FLUSH
}
int main() {
    for (int i = 0; i < 8; i++)
        std::thread([] {
            for (int frame = 0; frame < 2; frame++) {   // (the second flush of a thread takes no new block)
                mkwvk::table_pending.push_back({10, 1, 0x1000});
                mkwvk::table_pending.push_back({10, 1, 0x2000});
                mkwvk::memory_table_flush();
            }
        }).join();
    std::printf("THREADS 8 blocks_taken %lld retained_64k_bytes %lld transfers %lld\n", taken.load(), retained.load(), transfers.load());
    return retained.load() == 0 ? 0 : 1;
}
"""


class TableRunsTests(unittest.TestCase):
    def test_flush_matches_the_previous_expansion_and_survives_refused_allocations(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("no native C++ compiler")
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "table_runs.cpp"
            source.write_text(FIXTURE, encoding="utf-8")
            binary = Path(directory) / "table_runs.exe"
            built = subprocess.run([compiler, "-std=c++20", "-O1", "-static", "-I", str(ROOT / "gpu/vk"), str(source),
                                    "-o", str(binary)], capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=600)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("\nOK\n", "\n" + run.stdout)
            self.assertIn("MEMORY runs 600 pages 8010000", run.stdout)
            self.assertIn("REFUSED no_memory_path", run.stdout)
            print(run.stdout.strip())

    def test_real_flush_gives_its_block_back_when_the_thread_ends(self):
        compiler = native_cxx()
        if not compiler:
            self.skipTest("no native C++ compiler")
        memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
        actual = memory[memory.index("bool memory_table_flush() {"):memory.index("uint64_t memory_guest_pages() {")]
        self.assertIn("thread_local std::unique_ptr<uint64_t[]> block;", actual)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "threads.cpp"
            source.write_text(THREADS.replace("// ACTUAL_FLUSH", actual), encoding="utf-8")
            binary = Path(directory) / "threads.exe"
            built = subprocess.run([compiler, "-std=c++20", "-O1", "-static", "-pthread", "-I", str(ROOT / "gpu/vk"),
                                    str(source), "-o", str(binary)], capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stderr)
            run = subprocess.run([str(binary)], capture_output=True, text=True, timeout=120)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn("THREADS 8 blocks_taken 8 retained_64k_bytes 0 transfers 16", run.stdout)
            print(run.stdout.strip())

    def test_renderer_uses_the_bounded_flush_and_the_host_stops_on_a_refused_commit(self):
        memory = (ROOT / "gpu/vk/vk_memory.cpp").read_text(encoding="utf-8")
        flush = memory[memory.index("bool memory_table_flush() {"):memory.index("uint64_t memory_guest_pages() {")]
        self.assertIn("table_runs_flush(table_pending", flush)
        self.assertNotIn("std::pair<uint64_t, uint64_t>", flush)
        self.assertNotIn("stable_sort", flush)
        self.assertIn('getenv("RX_VK_TABLE_NOW")', memory)   # (still an opt-in switch, not the fix)
        glue = (ROOT / "host/mkw_glue.c").read_text(encoding="utf-8")
        touch = glue[glue.index("static LONG CALLBACK commit_on_touch"):glue.index("/* A crash nothing handles")]
        # (resumed only after the commit succeeded; the line about it comes after the result. r6: two ways to
        # resume, a heap on demand's 2 MB and the 64 KB nothing handed out, each after its own commit)
        retry, touch = touch.split("    if (mbi.State != MEM_RESERVE) return EXCEPTION_CONTINUE_SEARCH;")
        # (the third: pages another thread's first touch committed meanwhile are tried again, a read or a
        # write of read-write pages only, and not for ever)
        self.assertEqual(retry.count("EXCEPTION_CONTINUE_EXECUTION"), 1)
        self.assertIn("mbi.Protect != PAGE_READWRITE) return EXCEPTION_CONTINUE_SEARCH;", retry)
        self.assertIn("if (++again > 64) return EXCEPTION_CONTINUE_SEARCH;", retry)
        self.assertEqual(touch.count("EXCEPTION_CONTINUE_EXECUTION"), 2)
        self.assertEqual(touch.count("commit_pages("), 2)
        heap, rest = touch.split("    if (commit_refused_for_test() || !commit_pages(guest & ~0xFFFFULL")
        self.assertLess(heap.index("commit_pages("), heap.index("EXCEPTION_CONTINUE_EXECUTION"))
        self.assertIn('"the heap\'s first touch"', heap)
        self.assertNotIn("committed on first touch", heap)
        self.assertLess(rest.index("committed on first touch"), rest.index("EXCEPTION_CONTINUE_EXECUTION"))
        commit = glue[glue.index("void hos_commit(uint64_t addr, uint64_t size) {"):glue.index("static LONG CALLBACK commit_on_touch")]
        self.assertIn("out_of_memory(", commit)
        self.assertIn("0xC000012Du", glue)


HARNESS = r"""
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
%s
int main(void) {
    window = VirtualAlloc(NULL, HOS_GUEST_SPACE, MEM_RESERVE, PAGE_NOACCESS);
    AddVectoredExceptionHandler(1, commit_on_touch);
    hos_commit(0x200000, 0x30000);
    window[0x200000] = 1;
    window[0x22ffff] = 2;
    printf("handed out\n");
    window[0x400123] = 7;                       /* (first touch) */
    printf("touched %%d\n", window[0x400123]);
    fflush(stdout);
    window[0x800000] = 9;                       /* (a second one) */
    printf("touched again %%d\n", window[0x800000]);
    fflush(stdout);
    return 0;
}
"""


class CommitFailureTests(unittest.TestCase):
    """host/mkw_glue.c's commit block itself, compiled over a 1 GiB reservation, with Windows' refusal injected."""

    @classmethod
    def setUpClass(cls):
        import os
        from tests.native_tools import native_cc
        cls.compiler = native_cc() if os.name == "nt" else None
        if not cls.compiler:
            raise unittest.SkipTest("Windows and a native C compiler are needed")
        glue = (ROOT / "host/mkw_glue.c").read_text(encoding="utf-8")
        block = glue[glue.index("/* ---- the guest window"):glue.index("/* A crash nothing handles")]
        cls.folder = tempfile.TemporaryDirectory()
        source = Path(cls.folder.name) / "commit.c"
        source.write_text(HARNESS % block, encoding="utf-8")
        cls.binary = Path(cls.folder.name) / "commit.exe"
        built = subprocess.run([cls.compiler, "-O1", "-static", str(source), "-o", str(cls.binary)],
                               capture_output=True, text=True, timeout=600)
        assert built.returncode == 0, built.stderr

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_with(self, fail_at):
        import os
        env = dict(os.environ)
        env.pop("HOS_TEST_COMMIT_FAIL", None)
        if fail_at:
            env["HOS_TEST_COMMIT_FAIL"] = str(fail_at)
        done = subprocess.run([str(self.binary)], capture_output=True, text=True, timeout=120, env=env)
        return done.returncode & 0xFFFFFFFF, done.stdout

    def test_commits_succeed_without_injection(self):
        code, out = self.run_with(0)
        self.assertEqual(code, 0, out)
        self.assertIn("touched 7", out)
        self.assertIn("touched again 9", out)
        self.assertEqual(out.count("committed on first touch"), 2)
        self.assertNotIn("OUT OF MEMORY", out)

    def test_refused_runtime_commit_ends_the_run_before_the_pages_are_used(self):
        code, out = self.run_with(1)
        self.assertEqual(code, 0xC000012D, out)
        self.assertIn("OUT OF MEMORY", out)
        self.assertIn("handed out by the runtime, error 1455", out)
        self.assertIn("system commit", out)
        self.assertNotIn("handed out\n", out)
        self.assertEqual(out.count("OUT OF MEMORY"), 1)

    def test_refused_first_touch_is_not_resumed_and_not_reported_as_committed(self):
        code, out = self.run_with(3)   # (1: hos_commit, 2: the first touch, 3: the second touch)
        self.assertEqual(code, 0xC000012D, out)
        self.assertIn("touched 7", out)
        self.assertNotIn("touched again", out)
        self.assertEqual(out.count("committed on first touch"), 1)   # (only the one that was)
        self.assertIn("first touch, error 1455", out)
        self.assertEqual(out.count("OUT OF MEMORY"), 1)


HEAP_HARNESS = r"""
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
%s
/* committed bytes of guest [lo, hi) */
static unsigned long long committed(uint64_t lo, uint64_t hi) {
    unsigned long long n = 0;
    for (uint64_t a = lo; a < hi;) {
        MEMORY_BASIC_INFORMATION m;
        if (!VirtualQuery(GP(a), &m, sizeof m)) break;
        uint64_t end = (uint64_t)((uint8_t *)m.BaseAddress + m.RegionSize - window);
        if (end > hi) end = hi;
        if (m.State == MEM_COMMIT) n += end - a;
        a = end;
    }
    return n;
}
#define HEAP 0x10000000ULL
#define SIZE (0x0FF00000ULL + 0x30000)   /* (255 MB and 192 KB: its last 2 MB is cut at the heap's end) */
int main(int argc, char **argv) {
    window = VirtualAlloc(NULL, HOS_GUEST_SPACE, MEM_RESERVE, PAGE_NOACCESS);
    AddVectoredExceptionHandler(1, commit_on_touch);
    const int on = hos_heap_on_demand(HEAP, argc > 1 ? 1ULL << 50 : SIZE);
    printf("on demand %%d\n", on);
    if (!on) return 0;
    if (argc > 1) return 0;   /* (the size no PC has commit for: decided by the commit free, without the variable) */
    printf("before %%llu\n", committed(HEAP, HEAP + SIZE));
    window[HEAP + 0x345678] = 5;                         /* (inside the second 2 MB) */
    printf("one touch %%llu at %%llu value %%d\n", committed(HEAP, HEAP + SIZE), committed(HEAP + 0x200000, HEAP + 0x400000),
           window[HEAP + 0x345678]);
    window[HEAP + SIZE - 1] = 6;                         /* (the heap's last byte: only up to its end) */
    printf("last touch %%llu past the end %%llu\n", committed(HEAP + SIZE - 0x30000, HEAP + SIZE), committed(HEAP + SIZE, HEAP + SIZE + 0x400000));
    /* a system call given heap pages nothing touched: refused by Windows without an exception, then given them */
    char path[MAX_PATH], name[MAX_PATH];
    GetTempPathA(sizeof path, path);
    GetTempFileNameA(path, "hod", 0, name);
    HANDLE f = CreateFileA(name, GENERIC_READ | GENERIC_WRITE, 0, NULL, CREATE_ALWAYS, FILE_FLAG_DELETE_ON_CLOSE, NULL);
    DWORD n = 0;
    static char data[0x30000];
    memset(data, 0x5A, sizeof data);
    WriteFile(f, data, sizeof data, &n, NULL);
    const uint64_t buf = HEAP + 0x4000000 + 0x1234;      /* (64 MB in: untouched) */
    SetFilePointer(f, 0, NULL, FILE_BEGIN);
    n = 0;
    const BOOL bare = ReadFile(f, GP(buf), sizeof data, &n, NULL);
    printf("read into untouched pages: ok %%d bytes %%lu error %%lu committed %%llu\n", bare, n, bare ? 0 : GetLastError(),
           committed(buf, buf + sizeof data));
    hos_commit_for_host(buf, sizeof data);
    SetFilePointer(f, 0, NULL, FILE_BEGIN);
    n = 0;
    const BOOL given = ReadFile(f, GP(buf), sizeof data, &n, NULL);
    printf("read after commit_for_host: ok %%d bytes %%lu first %%d last %%d\n", given, n, window[buf], window[buf + sizeof data - 1]);
    CloseHandle(f);
    /* outside the heap: not this function's (the runtime commits what it hands out), and cut at the heap's ends */
    const unsigned long long below = committed(HEAP - 0x100000, HEAP);
    hos_commit_for_host(HEAP - 0x80000, 0x90000);        /* (512 KB below the heap and 64 KB into it) */
    printf("across the start: below %%llu to %%llu, inside %%llu\n", below, committed(HEAP - 0x100000, HEAP), committed(HEAP, HEAP + 0x10000));
    hos_commit_for_host(0x1000, 0x1000);                 /* (far from it: nothing) */
    printf("far %%llu\n", committed(0, 0x10000));
    mem_log("at the end");
    fflush(stdout);
    return 0;
}
"""


class HeapOnDemandTests(unittest.TestCase):
    """r6: host/mkw_glue.c's heap committed as it is touched, compiled as it is over a 1 GiB reservation."""

    @classmethod
    def setUpClass(cls):
        import os
        from tests.native_tools import native_cc
        cls.compiler = native_cc() if os.name == "nt" else None
        if not cls.compiler:
            raise unittest.SkipTest("Windows and a native C compiler are needed")
        glue = (ROOT / "host/mkw_glue.c").read_text(encoding="utf-8")
        block = glue[glue.index("/* ---- the guest window"):glue.index("/* A crash nothing handles")]
        cls.folder = tempfile.TemporaryDirectory()
        source = Path(cls.folder.name) / "heap.c"
        source.write_text(HEAP_HARNESS % block, encoding="utf-8")
        cls.binary = Path(cls.folder.name) / "heap.exe"
        built = subprocess.run([cls.compiler, "-O1", "-static", str(source), "-o", str(cls.binary)],
                               capture_output=True, text=True, timeout=600)
        assert built.returncode == 0, built.stderr

    @classmethod
    def tearDownClass(cls):
        cls.folder.cleanup()

    def run_with(self, lazy, fail_at=0, huge=False):
        import os
        env = dict(os.environ)
        env.pop("HOS_TEST_COMMIT_FAIL", None)
        env.pop("HOS_LAZY_HEAP", None)
        if lazy is not None:
            env["HOS_LAZY_HEAP"] = lazy
        if fail_at:
            env["HOS_TEST_COMMIT_FAIL"] = str(fail_at)
        done = subprocess.run([str(self.binary)] + (["huge"] if huge else []), capture_output=True, text=True, timeout=120, env=env)
        return done.returncode & 0xFFFFFFFF, done.stdout

    def test_heap_is_committed_two_megabytes_at_a_touch_and_only_inside_it(self):
        code, out = self.run_with("1")
        self.assertEqual(code, 0, out)
        self.assertIn("on demand 1", out)
        self.assertIn("are committed as the game uses them", out)
        self.assertIn("before 0\n", out)
        self.assertIn("one touch 2097152 at 2097152 value 5", out)        # (its 2 MB, nothing else)
        self.assertIn("last touch 196608 past the end 0", out)            # (cut at the heap's end)
        self.assertNotIn("committed on first touch", out)                 # (that line is for what nothing handed out)
        self.assertNotIn("OUT OF MEMORY", out)
        print(out.strip())

    def test_a_system_call_needs_the_pages_committed_first_and_gets_them(self):
        code, out = self.run_with("1")
        self.assertEqual(code, 0, out)
        # (why the heap was committed whole before: Windows refuses the call, and no exception reaches the handler)
        self.assertIn("read into untouched pages: ok 0 bytes 0 error 998 committed 0", out)
        self.assertIn("read after commit_for_host: ok 1 bytes 196608 first 90 last 90", out)
        self.assertIn("across the start: below 0 to 0, inside 65536", out)
        self.assertIn("far 0\n", out)
        self.assertRegex(out, r"mem: heap on demand: \d+ MB of 255 committed at first touches so far")

    def test_refused_heap_touch_ends_the_run(self):
        code, out = self.run_with("1", fail_at=2)   # (1: the first touch, 2: the heap's last byte)
        self.assertEqual(code, 0xC000012D, out)
        self.assertIn("one touch 2097152", out)
        self.assertNotIn("last touch", out)
        self.assertIn("the heap's first touch, error 1455", out)
        self.assertEqual(out.count("OUT OF MEMORY"), 1)

    def test_off_by_the_variable_and_on_when_commit_is_short(self):
        code, out = self.run_with("0")
        self.assertEqual(code, 0, out)
        self.assertIn("on demand 0", out)
        self.assertNotIn("are committed as the game uses them", out)
        code, out = self.run_with(None, huge=True)   # (a heap no PC has the commit for, the variable absent)
        self.assertEqual(code, 0, out)
        self.assertIn("on demand 1", out)

    def test_host_hands_guest_memory_to_the_system_through_the_commit(self):
        fs = (ROOT / "host/nn_fs.c").read_text(encoding="utf-8")
        self.assertLess(fs.index("hos_commit_for_host(buf, size);"), fs.index("ReadFile(fh->h, GP(buf + done)"))
        self.assertLess(fs.index("hos_commit_for_host(ARG(2), ARG(3));"), fs.index("WriteFile(fh->h, GP(ARG(2))"))
        nvn = (ROOT / "host/nvn_native.c").read_text(encoding="utf-8")
        self.assertLess(nvn.index("hos_commit_for_host(b->mem, o->size);"), nvn.index("hos_gpu_track(o->gpu, o->size, 1);"))
        mem = (ROOT / "host/hos_mem.c").read_text(encoding="utf-8")
        self.assertIn("!hos_heap_on_demand(HOS_HEAP_BASE, size)) hos_commit(HOS_HEAP_BASE + hos_heap_size", mem)
        # (no other system call is given guest memory: a new one must commit it first, and be listed here)
        import re
        calls = []
        for path in sorted((ROOT / "host").glob("*.c")):
            for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
                if re.search(r"\b(ReadFile|WriteFile|recv|recvfrom|WSARecv|DeviceIoControl)\([^;]*\bGP\(", line):
                    calls.append(path.name + ": " + line.strip())
        self.assertEqual(len(calls), 2, calls)


class HeapOnDemandRaceTests(unittest.TestCase):
    """r6 review: first touches of one fresh page of the heap by several threads at once (tests/native/heap_race043.c).
    Before the fix the second handler found the page committed already and passed the exception on: a crash within
    a few rounds."""

    def test_simultaneous_first_touches_of_one_page_all_resume(self):
        import os
        from tests.native_tools import native_cc
        compiler = native_cc() if os.name == "nt" else None
        if not compiler:
            self.skipTest("Windows and a native C compiler are needed")
        glue = (ROOT / "host/mkw_glue.c").read_text(encoding="utf-8")
        block = glue[glue.index("/* ---- the guest window"):glue.index("/* A crash nothing handles")]
        harness = (ROOT / "tests/native/heap_race043.c").read_text(encoding="utf-8")
        self.assertEqual(harness.count("// MKW_GLUE_BLOCK"), 1)
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "race.c"
            source.write_text(harness.replace("// MKW_GLUE_BLOCK", block), encoding="utf-8")
            binary = Path(directory) / "race.exe"
            built = subprocess.run([compiler, "-O1", "-static", str(source), "-o", str(binary)],
                                   capture_output=True, text=True, timeout=600)
            self.assertEqual(built.returncode, 0, built.stderr)
            env = dict(os.environ)
            env.pop("HOS_TEST_COMMIT_FAIL", None)
            env["HOS_LAZY_HEAP"] = "1"
            run = subprocess.run([str(binary), "30000"], capture_output=True, text=True, timeout=300, env=env)
            self.assertEqual(run.returncode, 0, run.stdout[-2000:] + run.stderr)
            self.assertIn("ROUNDS 30000 threads 8 wrong_bytes 0 unhandled 0", run.stdout)
            print(run.stdout.strip().splitlines()[-1])


class UpstreamHostTests(unittest.TestCase):
    """r6: the two host files taken from Hookshot v2.1.0, and what the local code needs of them."""

    def test_wait_any_is_woken_only_by_objects_a_multi_wait_watches(self):
        sync = (ROOT / "host/nn_os_sync.c").read_text(encoding="utf-8")
        self.assertIn("static void poke_multiwait(Obj *o) {", sync)
        self.assertNotIn("poke_multiwait();", sync)
        self.assertIn("mw_watched_at_locked(o->key) >= 0", sync)
        self.assertIn('getenv("HOS_MW_WAKE")', sync)        # (the way back: every change wakes, as before)
        self.assertIn("mw_watch_incomplete", sync)           # (a failed registration keeps the old wakes)
        for call in ("mw_watch_add_locked(holder_watch(h))", "mw_watch_remove_locked(holder_watch(h))"):
            self.assertIn(call, sync)

    def test_log_is_written_in_batches_and_flushed_before_every_way_out(self):
        thread = (ROOT / "host/hos_thread.c").read_text(encoding="utf-8")
        self.assertIn('getenv("HOS_LOG_BATCH_MS")', thread)
        self.assertIn('int on = !getenv("HOS_LOG_SYNC");', thread)   # (files too, not only a console)
        self.assertIn("atexit(log_flush)", thread)
        self.assertIn('strstr(name, "OptimizeChange")', thread)
        glue = (ROOT / "host/mkw_glue.c").read_text(encoding="utf-8")
        end = glue[glue.index("static DECLSPEC_NORETURN void out_of_memory"):glue.index("static int commit_is_memory")]
        self.assertLess(end.index("SEM MEMORIA"), end.index("hos_log_flush();"))
        self.assertLess(end.index("hos_log_flush();"), end.rindex("TerminateProcess("))

    def test_log_writer_and_flush_use_one_lock_order(self):
        thread = (ROOT / "host/hos_thread.c").read_text(encoding="utf-8")
        pending = thread.split("static void log_write_pending(void) {", 1)[1].split("\n}", 1)[0]
        main = thread.split("static DWORD WINAPI log_main(void *p) {", 1)[1].split("\n}", 1)[0]
        flush = thread.split("static void log_flush(void) {", 1)[1].split("\n}", 1)[0]
        write_lock = "AcquireSRWLockExclusive(&log_write_lock);"
        queue_lock = "AcquireSRWLockExclusive(&log_lock);"
        queue_release = "ReleaseSRWLockExclusive(&log_lock);"
        self.assertLess(pending.index(write_lock), pending.index(queue_lock))
        self.assertLess(pending.index("log_take_locked(batch)"), pending.index(queue_release))
        self.assertLess(pending.index(queue_release), pending.index("log_write(batch, n)"))
        self.assertLess(main.index(queue_release), main.index("log_write_pending();"))
        self.assertNotIn(write_lock, main)
        self.assertIn("log_write_pending();", flush)
        self.assertNotIn(write_lock, flush)


if __name__ == "__main__":
    unittest.main()

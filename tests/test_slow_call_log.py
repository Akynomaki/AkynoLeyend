"""Exercise the native timing limits for descriptor builds and dispatches."""
from pathlib import Path
import subprocess
import tempfile
import unittest

from tests.native_tools import native_cxx


class SlowCallLogTests(unittest.TestCase):
    def test_timing_stops_after_the_log_limits(self):
        cxx = native_cxx()
        if cxx is None:
            self.skipTest("C++ compiler unavailable")
        root = Path(__file__).resolve().parents[1]
        source = (root / "gpu/vk/vk_draw.cpp").read_text(encoding="utf-8")
        descriptor = source[source.index("struct SlowCallLog"):source.index("// ---- RX_VK_WATCH_PROG")]
        dispatch_start = source.index("struct DispatchClock")
        dispatch = source[dispatch_start:source.index("/// (hookshot) OoT's neural", dispatch_start)]
        fixture = r"""
#include <atomic>
#include <cassert>
#include <chrono>
#include <cstdint>
#include <cstring>
#include <thread>
#include <vector>

std::atomic<int> descriptor_lines{}, dispatch_lines{};
void logf(const char* format, ...) {
    if (std::strstr(format, "slow descriptor")) descriptor_lines++;
    if (std::strstr(format, "slow dispatch")) dispatch_lines++;
}
"""
        main = r"""
int main() {
    using namespace std::chrono_literals;
    assert(descriptor_log.start() != SlowCallLog::TimePoint{});
    std::vector<std::thread> workers;
    for (int i = 0; i < 8; i++) {
        workers.emplace_back([] {
            for (int j = 0; j < 128; j++) {
                auto begin = descriptor_log.start();
                if (begin != SlowCallLog::TimePoint{}) begin -= 3ms;
                slow_descriptor(begin, "uniform buffer", 1, 16);
                DispatchClock clock;
                if (clock.t0 != SlowCallLog::TimePoint{}) clock.t0 -= 3ms;
                clock.mark(clock.t_prog);
            }
        });
    }
    for (auto& thread : workers) thread.join();
    assert(descriptor_lines == 40);
    assert(dispatch_lines == 60);
    assert(descriptor_log.start() == SlowCallLog::TimePoint{});
    DispatchClock clock;
    assert(clock.t0 == SlowCallLog::TimePoint{});
    clock.mark(clock.t_desc);
    assert(clock.t_desc == SlowCallLog::TimePoint{});
}
"""
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "slow_call_log.cpp"
            binary_path = Path(directory) / "slow_call_log.exe"
            source_path.write_text(fixture + descriptor + dispatch + main, encoding="utf-8")
            subprocess.run([cxx, "-std=c++20", "-pthread", "-static", str(source_path), "-o", str(binary_path)], check=True)
            subprocess.run([str(binary_path)], check=True)

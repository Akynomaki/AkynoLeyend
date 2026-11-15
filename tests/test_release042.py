"""Release coherence, old-host rejection and real bounded cache ownership."""

import contextlib
import io
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend import __version__
from akynoleyend.cli import main, parser
from akynoleyend.errors import ProjectError
from akynoleyend.files import sha256, write_json
from akynoleyend.release import launcher_identity, verify_launcher
from akynoleyend.shader_prepare import _update_renderer

ROOT = Path(__file__).resolve().parents[1]


class CoherenceTests(unittest.TestCase):
    def test_public_run_defaults_to_current_revision_and_never_starts_old_host(self):
        self.assertTrue(parser().parse_args(["run"]).require_current_build)
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            keep = root / "old-save"
            keep.write_bytes(b"preserve")
            with (
                patch("akynoleyend.launch.checked_build", return_value={"version": "0.4.0-dev.1"}),
                patch("akynoleyend.launch.subprocess.Popen") as child,
                contextlib.redirect_stdout(io.StringIO()) as output,
            ):
                self.assertEqual(main(["run", "--out", str(root)]), 1)
            child.assert_not_called()
            self.assertIn("nao corresponde", output.getvalue())
            self.assertEqual(list(root.iterdir()), [keep])
            self.assertEqual(keep.read_bytes(), b"preserve")

    def test_old_host_cannot_receive_new_visual_dll(self):
        with patch(
            "akynoleyend.shader_prepare.renderer_prebuilt",
            side_effect=AssertionError("must reject first"),
        ):
            with self.assertRaisesRegex(ProjectError, "host/ABI"):
                _update_renderer(Path("unused"), {"version": "0.4.0-dev.1"}, lambda _: None)

    def test_launcher_receipt_rejects_old_binary_and_changed_source(self):
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            (root / "builder/AkynoLeyendBuilder").mkdir(parents=True)
            (root / "assets").mkdir()
            for name in ("AkynoLeyend.ico", "AkynoLeyend.png"):
                (root / "assets" / name).write_bytes(b"synthetic icon")
            source = root / "builder/AkynoLeyendBuilder/MainWindow.cs"
            source.write_text("// fixture source\n")
            binary = root / "AkynoLeyendBuilder.exe"
            binary.write_bytes(b"MZ synthetic current launcher")
            receipt = {
                "schema": 1,
                "version": __version__,
                "pe_product_version": __version__,
                "source_sha256": launcher_identity(root),
                "binary_sha256": sha256(binary),
            }
            write_json(root / "builder/launcher-build.json", receipt)
            verify_launcher(root)
            binary.write_bytes(b"MZ synthetic old launcher")
            with self.assertRaises(ProjectError):
                verify_launcher(root)
            binary.write_bytes(b"MZ synthetic current launcher")
            source.write_text("// modified since publication\n")
            with self.assertRaises(ProjectError):
                verify_launcher(root)


class NativeReleaseTests(unittest.TestCase):
    def compile_run(self, source):
        compiler = shutil.which("c++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            path = root / "fixture.cpp"
            path.write_text(source)
            child = subprocess.run(
                [
                    compiler,
                    "-std=c++20",
                    "-O1",
                    "-Wall",
                    "-Wextra",
                    "-Werror",
                    "-pthread",
                    "-I" + str(ROOT / "gpu/vk"),
                    str(path),
                    "-o",
                    str(root / "fixture"),
                ],
                capture_output=True,
                text=True,
                timeout=60,
            )
            self.assertEqual(child.returncode, 0, child.stderr)
            child = subprocess.run(
                [str(root / "fixture")], capture_output=True, text=True, timeout=15
            )
            self.assertEqual(child.returncode, 0, child.stderr)

    def test_read_ahead_counts_borrowed_bytes_and_payload_outlives_reader(self):
        self.compile_run("""
        #include "cache_stream.h"
        #include <cassert>
        #include <cstring>
        using namespace mkwvk::cache;
        int main(){
          Stream::Payload surviving;
          {
            Stream s(64,2,2,0,[](Range r,uint8_t* p){std::memset(p,42,r.size);return true;});
            assert(s.request({1,64}));assert(s.wait_idle(std::chrono::seconds(2)));
            auto payload=s.take({1,64});assert(s.stats().reserved==64);
            assert(!s.request({2,1}));assert(s.stats().peak==64);
            surviving=std::move(payload);assert(payload.empty());
            assert(!s.request({3,1}));s.stop();assert(s.stats().reserved==64);
          }
          assert(surviving.size()==64&&surviving[63]==42);surviving={};
        }""")

    def test_precompile_rate_is_shared_across_eight_workers(self):
        self.compile_run("""
        #include "cache_rate.h"
        #include <atomic>
        #include <cassert>
        #include <vector>
        using namespace mkwvk::cache;
        int main(){auto now=TokenBucket::Clock::now();SharedTokenBucket bucket(5,now);
          std::atomic<int> admitted=0;std::vector<std::thread> threads;
          for(int i=0;i<8;i++)threads.emplace_back([&]{if(bucket.try_take(now))admitted++;});
          for(auto& t:threads){t.join();}
          assert(admitted==1);
          assert(!bucket.try_take(now+std::chrono::milliseconds(199)));
          assert(bucket.try_take(now+std::chrono::milliseconds(201)));
          assert(!bucket.try_take(now+std::chrono::milliseconds(201)));
        }""")
        text = (ROOT / "gpu/vk/vk_draw.cpp").read_text()
        start = text.index("void precompile_run(")
        block = text[start : text.index("void dispatch(", start)]
        self.assertLess(
            block.index("SharedTokenBucket admission"), block.index("const auto worker")
        )

    def test_actual_resolution_menu_and_runtime_agree_on_experimental_scales(self):
        menu = (ROOT / "gpu/vk/vk_menu.cpp").read_text(encoding="utf-8")
        function = menu[
            menu.index("const char* tx_resolution(") : menu.index("const char* tx_speed(")
        ]
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text()
        callback = replay[replay.index("t.option = [](int id)") : replay.index("t.nvn_register_sampler =")]
        self.compile_run(
            """#include <cassert>
        #include <algorithm>
        #include <cstring>
        #include "menu_option_ids.h"
        struct Options {
            int realtime=1, resolution=0, pad_background=0, mouse_invert=0, rumble=100;
            int stick_dead_zone=0, invert_cam_x=0, invert_cam_y=0, volume=100, mute_background=0;
        } opts;
        bool menu_is_open(){return false;}
        int fsr_sdk_jitter(int option){return option == 4 ? 1280 : 0;}
        struct Table{int(*option)(int);}t;
        """
            + function
            + "\nint main(){"
            + callback
            + """
          int expected[]={0,100,75,67,50,125,150};
          for(int i=0;i<7;i++){opts.resolution=i;assert(t.option(3)==expected[i]);}
          assert(t.option(4)==1280);
          assert(strstr(tx_resolution(5),"125%"));assert(strstr(tx_resolution(6),"150%"));
        }"""
        )


if __name__ == "__main__":
    unittest.main()

"""The temporal upscaler choices (FSR 3.1, FSR Native AA, DLSS, DLAA) and NVIDIA's runtime download, without a game or GPU."""
import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from akynoleyend import dlss_runtime
from akynoleyend.errors import ProjectError
from akynoleyend.graphics import FILTERS, TEMPORAL, graphics_environment, saved_temporal_options

ROOT = Path(__file__).resolve().parents[1]


class Choices(unittest.TestCase):
    def test_engines_and_native_modes(self):
        self.assertEqual(graphics_environment(upscaling="dlss", resolution="50")["AKYNO_TEMPORAL_ENGINE"], "dlss")
        dlaa = graphics_environment(upscaling="dlaa")
        self.assertEqual((dlaa["AKYNO_TEMPORAL_ENGINE"], dlaa["AKYNO_RESOLUTION"], dlaa["HOS_DYNRES"]), ("dlss", "1", "0"))
        native = graphics_environment(upscaling="fsr-native-aa", resolution="100")
        self.assertEqual((native["AKYNO_FSR_TEMPORAL"], native["AKYNO_RESOLUTION"]), ("1", "1"))
        self.assertNotIn("AKYNO_TEMPORAL_ENGINE", graphics_environment(upscaling="fsr-temporal", resolution="67"))
        # (FSR 1 stays at the presentation for every temporal mode: the window's size and the fallback)
        for mode in TEMPORAL:
            self.assertEqual(FILTERS[mode], FILTERS["fsr"])
        fsr4 = graphics_environment(upscaling="fsr4")
        self.assertEqual((fsr4["AKYNO_UPSCALER"], fsr4["AKYNO_TEMPORAL_ENGINE"], fsr4["AKYNO_RESOLUTION"]),
                         ("fsr4", "fsr4", "4"))
        fsr4_native = graphics_environment(upscaling="fsr4-native-aa")
        self.assertEqual((fsr4_native["AKYNO_FSR_TEMPORAL"], fsr4_native["AKYNO_RESOLUTION"]), ("1", "1"))

    def test_resolutions_that_do_not_fit_are_refused(self):
        for bad in ({"upscaling": "dlaa", "resolution": "50"}, {"upscaling": "fsr-native-aa", "resolution": "75"},
                    {"upscaling": "dlss", "resolution": "100"}, {"upscaling": "dlss", "resolution": "auto"},
                    {"upscaling": "fsr-temporal", "resolution": "150"},
                    {"upscaling": "fsr4-native-aa", "resolution": "67"}, {"upscaling": "fsr4", "resolution": "100"}):
            with self.assertRaises(ProjectError, msg=str(bad)):
                graphics_environment(**bad)

    def test_the_launcher_offers_them(self):
        options = (ROOT / "builder/AkynoLeyendBuilder/LaunchOptions.cs").read_text(encoding="utf-8")
        xaml = (ROOT / "builder/AkynoLeyendBuilder/MainWindow.xaml").read_text(encoding="utf-8")
        for mode in ("fsr-temporal", "fsr-native-aa", "dlss", "dlaa"):
            self.assertIn('"%s"' % mode, options)
            self.assertIn('Tag="%s"' % mode, xaml)
        self.assertIn('Tag="dlss-runtime"', xaml)
        window = (ROOT / "builder/AkynoLeyendBuilder/MainWindow.xaml.cs").read_text(encoding="utf-8")
        self.assertIn('"--accept-nvidia-license"', window)   # (only after the question: MessageBoxResult.Yes)
        self.assertIn("MessageBoxResult.Yes", window[window.index('command=="dlss-runtime"&&MessageBox'):][:1200])

    def test_in_game_temporal_choice_uses_a_valid_saved_scale(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            options = folder / "AkynoLeyend_opts.ini"
            self.assertEqual(saved_temporal_options(folder, "75"), (None, "75"))
            options.write_bytes(b"upscaling=3\r\nupscaler=fsr4\r\nresolution=3\r\n")
            self.assertEqual(saved_temporal_options(folder, None), ("fsr4", "67"))
            self.assertEqual(saved_temporal_options(folder, "75"), ("fsr4", "75"))
            options.write_text("upscaler=dlss\nresolution=1\n", encoding="utf-8")
            self.assertEqual(saved_temporal_options(folder, "100"), ("dlaa", "100"))
            options.write_text("upscaler=dlaa\nresolution=4\n", encoding="utf-8")
            self.assertEqual(saved_temporal_options(folder, "50"), ("dlss", "50"))
            self.assertEqual(saved_temporal_options(folder, "auto"), ("lanczos", "auto"))
            self.assertEqual(saved_temporal_options(folder, "native-4k"), ("lanczos", "native-4k"))
            options.write_text("upscaling=3\nresolution=4\n", encoding="utf-8")
            self.assertEqual(saved_temporal_options(folder, None), (None, None))


class Runtime(unittest.TestCase):
    def opener(self, payloads):
        def open_(url, timeout):
            self.assertTrue(url.startswith(dlss_runtime.BASE + "/"))
            self.assertEqual(timeout, dlss_runtime.TIMEOUT)
            return io.BytesIO(payloads[url[len(dlss_runtime.BASE) + 1:]])
        return open_

    def test_nothing_without_the_license(self):
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ProjectError):
                dlss_runtime.fetch(False, Path(d), opener=lambda *a, **k: self.fail("downloaded"))
            self.assertEqual(list(Path(d).iterdir()), [])

    def test_kept_only_when_the_hash_is_nvidias(self):
        good = {path: b"x" for path, _ in dlss_runtime.FILES.values()}
        with tempfile.TemporaryDirectory() as d:
            with self.assertRaises(ProjectError):
                dlss_runtime.fetch(True, Path(d), opener=self.opener(good), say=lambda *_: None)
            self.assertEqual([p.name for p in Path(d).iterdir()], [])   # (no .part, no file)
            self.assertIsNone(dlss_runtime.installed(Path(d)))

    def test_pinned_files_install_and_are_found(self):
        real = {}
        original = dlss_runtime.FILES
        try:
            dlss_runtime.FILES = {name: (path, hashlib.sha256(name.encode()).hexdigest()) for name, (path, _) in original.items()}
            real = {path: name.encode() for name, (path, _) in dlss_runtime.FILES.items()}
            with tempfile.TemporaryDirectory() as d:
                self.assertEqual(dlss_runtime.fetch(True, Path(d), opener=self.opener(real), say=lambda *_: None), Path(d))
                self.assertEqual(dlss_runtime.installed(Path(d)), Path(d))
                (Path(d) / "nvngx_dlss.dll").write_bytes(b"changed")
                self.assertIsNone(dlss_runtime.installed(Path(d)))
        finally:
            dlss_runtime.FILES = original

    def test_folder_is_local_app_data(self):
        self.assertEqual(dlss_runtime.runtime_directory({"LOCALAPPDATA": r"C:\L"}), Path(r"C:\L") / "AkynoLeyend" / "ngx")


class ExitWatch(unittest.TestCase):
    """The launcher ends a game that closed its window and wrote its log but stayed in Windows' unloading of its DLLs."""
    def child(self, log, code):
        import subprocess, sys
        return subprocess.Popen([sys.executable, "-I", "-c", code, str(log)])

    def test_a_stalled_exit_is_ended_after_the_grace(self):
        from akynoleyend.launch import wait_game
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "erros.log"
            log.write_bytes(b"")
            child = self.child(log, "import sys,time;open(sys.argv[1],'ab').write(b'x\\n[hos host] display: window closed, exiting\\n');time.sleep(60)")
            import time
            begun = time.time()
            status, stalled = wait_game(child, log, grace=1, poll=0.2)
            self.assertLess(time.time() - begun, 20)
            self.assertEqual((status, stalled["seconds"]), (0, 1))
            self.assertIsNotNone(child.poll())

    def test_a_game_that_runs_or_ends_by_itself_is_left_alone(self):
        from akynoleyend.launch import wait_game
        with tempfile.TemporaryDirectory() as d:
            log = Path(d) / "erros.log"
            log.write_bytes(b"")
            child = self.child(log, "import sys,time;time.sleep(2.5);sys.exit(3)")   # (no line: never ended by the launcher)
            self.assertEqual(wait_game(child, log, grace=0.5, poll=0.2), (3, None))
            child = self.child(log, "import sys,time;open(sys.argv[1],'ab').write(b'display: window closed, exiting');time.sleep(0.3)")
            self.assertEqual(wait_game(child, log, grace=5, poll=0.2), (0, None))


class Renderer(unittest.TestCase):
    def test_dlss_is_an_engine_of_the_temporal_path(self):
        src = (ROOT / "gpu/vk/vk_fsr_sdk.cpp").read_text(encoding="utf-8")
        for needle in ('__has_include("../../third_party/nvidia-dlss-sdk/include/nvsdk_ngx_vk.h")', 'getenv("AKYNO_TEMPORAL_ENGINE")',
                       '_wgetenv(L"AKYNO_DLSS_DIR")', "NGX_VULKAN_EVALUATE_DLSS_EXT", "NVSDK_NGX_DLSS_Feature_Flags_MVLowRes",
                       "NVSDK_NGX_PerfQuality_Value_DLAA", "note_work();"):
            self.assertIn(needle, src)
        build = (ROOT / "nx2/build.py").read_text(encoding="utf-8")
        self.assertIn('ngx = name in ("vk_fsr_sdk", "vk_ngx_msvc_rt")', build)   # (only these objects depend on the SDK)
        self.assertIn("ngx_link()", build)
        main = (ROOT / "gpu/vk/vk_main.cpp").read_text(encoding="utf-8")
        self.assertIn("VK_NVX_BINARY_IMPORT_EXTENSION_NAME", main)
        self.assertIn("dev.mesh_queries = dev.mesh_shader && mesh.meshShaderQueries;", main)

    def test_the_gpu_is_idle_and_ngx_shut_down_before_the_exit(self):
        # (r7's battery: ExitProcess straight from WM_CLOSE with DLSS on: nvlddmkm 153, a TDR at the close, the PC down)
        display = (ROOT / "host/display.c").read_text(encoding="utf-8")
        close = display[display.index("case WM_CLOSE:"):][:700]
        self.assertIn("CreateThread(NULL, 0, close_main", close)
        main = display[display.index("static DWORD WINAPI close_main"):][:200]
        self.assertLess(main.index("rx_before_exit();"), main.index("ExitProcess(0);"))
        svc = (ROOT / "host/hos_svc.c").read_text(encoding="utf-8")
        svc = svc[svc.index("/* ExitProcess */"):][:400]
        self.assertLess(svc.index("rx_before_exit();"), svc.index("ExitProcess(0);"))
        backend = (ROOT / "host/rx_backend.c").read_text(encoding="utf-8")
        self.assertIn('GetProcAddress(vk_module, "akyno_before_exit")', backend)
        replay = (ROOT / "gpu/vk/vk_replay.cpp").read_text(encoding="utf-8")
        export = replay[replay.index('extern "C" __declspec(dllexport) void akyno_before_exit'):]
        for needle in ("exiting = true;", "dev.present_mu.try_lock()", "vkQueueSubmit2(dev.queue, 0, nullptr, fence)",
                       "vkWaitForFences(dev.device, 1, &fence, VK_TRUE, 5000000000ull)", "quiet && fsr_sdk_before_exit()"):
            self.assertIn(needle, export)
        for entry in ("void submit_q(const uint64_t* handles, int n, uint64_t queue) {", "void present(const nvn_tex* t, const int crop[4]) {"):
            self.assertIn("ExitGate gate(!async_on());", replay[replay.index(entry):][:120])
        sdk = (ROOT / "gpu/vk/vk_fsr_sdk.cpp").read_text(encoding="utf-8")
        shut = sdk[sdk.index("bool fsr_sdk_before_exit()"):][:600]
        self.assertIn("NVSDK_NGX_VULKAN_Shutdown1(dev.device);", shut)
        # (an export, not a table entry: vk_api.h is part of the shader cache's stamp)
        self.assertNotIn("before_exit", (ROOT / "gpu/vk/vk_api.h").read_text(encoding="utf-8"))

    def test_nvidias_files_are_not_distributed(self):
        from akynoleyend import updater
        text = Path(updater.__file__).read_text(encoding="utf-8")
        self.assertNotIn("nvngx_dlss", text)
        import importlib.util
        spec = importlib.util.spec_from_file_location("distribution_r7", ROOT / "tools/make_distribution.py")
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            module.ROOT = root
            for name in ("third_party/nvidia-dlss-sdk/lib/nvsdk_ngx_s.lib", "third_party/nvidia-dlss-sdk/include/nvsdk_ngx.h",
                         "third_party/nvidia-dlss-sdk/LICENSE.txt", "ferramentas/prebuilt/nvngx_dlss.dll",
                         "third_party/amd-fsr-sdk/sdk.json", "gpu/vk/vk_fsr_sdk.cpp"):
                (root / name).parent.mkdir(parents=True, exist_ok=True)
                (root / name).write_bytes(b"x")
            for update in (False, True):
                kept = sorted(rel.as_posix() for _, rel in module.files(False, update))
                self.assertEqual(kept, ["gpu/vk/vk_fsr_sdk.cpp", "third_party/amd-fsr-sdk/sdk.json"])

    def test_the_sdk_is_not_part_of_the_source_identity(self):
        # (a player's tree has no SDK: the identity of the same sources has to be the same there and here)
        from akynoleyend.build import source_identity
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "gpu/vk").mkdir(parents=True)
            (root / "gpu/vk/vk_fsr_sdk.cpp").write_text("x")
            before = source_identity(root)
            (root / "third_party/nvidia-dlss-sdk/include").mkdir(parents=True)
            (root / "third_party/nvidia-dlss-sdk/include/nvsdk_ngx.h").write_text("x")
            self.assertEqual(source_identity(root), before)
            (root / "third_party/amd-fsr-sdk").mkdir(parents=True)
            (root / "third_party/amd-fsr-sdk/sdk.json").write_text("{}")
            self.assertNotEqual(source_identity(root), before)


if __name__ == "__main__":
    unittest.main()

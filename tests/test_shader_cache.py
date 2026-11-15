"""Real background I/O, bounded allocations and exact cache identity guards."""
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from akynoleyend.build_support import shader_cache_stamp, shader_source_identity
from akynoleyend.environment import runtime_environment
from akynoleyend.errors import ProjectError

ROOT = Path(__file__).resolve().parent.parent


class ShaderCacheTests(unittest.TestCase):
    def test_real_cpp_stream_and_reader(self):
        compiler = os.environ.get("OCARINA_TEST_CXX") or shutil.which("c++") or shutil.which("clang++")
        if not compiler and os.name == "nt":
            local = ROOT / "ferramentas/llvm/bin/clang++.exe"
            compiler = str(local) if local.is_file() else None
        if not compiler:
            self.skipTest("A C++ compiler is needed for the native cache checks")
        with tempfile.TemporaryDirectory(prefix="cache test ") as directory:
            exe = Path(directory) / ("stream.exe" if os.name == "nt" else "stream")
            args = [compiler, "-std=c++20", "-O1", "-pthread", "-Wall", "-Wextra", "-Werror", "-I" + str(ROOT / "gpu/vk"), str(ROOT / "tests/native/test_cache_stream.cpp"), "-o", str(exe)]
            if os.name == "nt":
                args.append("-static")
            built = subprocess.run(args, capture_output=True, text=True, timeout=60)
            self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            child = subprocess.run([str(exe)], capture_output=True, text=True, timeout=20)
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)
            self.assertIn("cache stream checks passed", child.stdout)
            env = dict(os.environ, RX_VK_CACHE_STREAM="1", RX_VK_COMPILE_THREADS="999", RX_VK_CACHE_QUEUE="bad", RX_VK_CACHE_READ_MB="-1", RX_VK_PREWARM_MB="0")
            for key in ("RX_VK_PIPE_CACHE_IO_MB", "RX_VK_PREWARM_PER_SECOND", "RX_VK_CACHE_INDEX_RECORDS"):
                env.pop(key, None)
            child = subprocess.run([str(exe), "policy"], env=env, capture_output=True, text=True, timeout=20)
            self.assertEqual(child.returncode, 0, child.stdout + child.stderr)

    def test_exact_source_and_schema_control_compatibility(self):
        with tempfile.TemporaryDirectory() as directory:
            vk = Path(directory)
            for name in ("eden/a.cpp", "sirit/a.cpp", "compat/a.h", "vk_shader.cpp", "vk_shader.h", "vk_api.h", "vk_state.h"):
                p = vk / name
                p.parent.mkdir(exist_ok=True)
                p.write_bytes(("// " + name + "\n").encode())   # (LF bytes: the CRLF case below is made explicitly)
            fresh, fp = shader_source_identity(vk)
            config = vk / "known.json"
            config.write_text(json.dumps({"schema": 1, "source_sets": {fp: {"stamp": "234d9fba458b54ba"}}}))
            self.assertEqual(shader_cache_stamp(vk, config), "234d9fba458b54ba")
            header = vk / "vk_shader.h"
            before = header.read_bytes()
            header.write_bytes(before.replace(b"\n", b"\r\n"))
            self.assertEqual(shader_cache_stamp(vk, config), "234d9fba458b54ba")
            header.write_bytes(before + b"// schema changed\n")
            self.assertNotEqual(shader_cache_stamp(vk, config), fresh)
            self.assertNotEqual(shader_cache_stamp(vk, config), "234d9fba458b54ba")
            header.write_bytes(before)
            (vk / "eden/a.cpp").write_text("// emitter changed\n")
            self.assertNotEqual(shader_cache_stamp(vk, config), "234d9fba458b54ba")
            config.write_text("invalid json")
            self.assertEqual(shader_cache_stamp(vk, config), shader_source_identity(vk)[0])

    def test_streaming_is_explicit_and_independent_of_visual_profile(self):
        parent = {"PATH": "tools", "RX_VK_CACHE_STREAM": "1", "RX_VK_PIPE_SKIP": "1"}
        self.assertEqual(runtime_environment(parent, "original"), {"PATH": "tools", "RX_BACKEND": "vulkan"})
        for profile in ("original", "8gb", "nitido"):
            env = runtime_environment(parent, profile, cache_mode="streaming")
            self.assertEqual(env["RX_VK_CACHE_READ_MB"], "16")
            self.assertEqual(env["RX_VK_COMPILE_THREADS"], "2")
            self.assertNotIn("RX_VK_PIPE_SKIP", env)
            self.assertNotIn("RX_VK_VALIDATION", env)
        with self.assertRaises(ProjectError):
            runtime_environment({}, "original", cache_mode="bad")

"""Semantic PR759 regression: source and destination registers retain their native values."""
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


class RegisterMarkerTests(unittest.TestCase):
    def test_all_89_native_register_alias_cases(self):
        compiler = shutil.which("c++") or shutil.which("clang++")
        if not compiler:
            self.skipTest("C++ compiler unavailable")
        with tempfile.TemporaryDirectory(prefix="akyno-regmap-") as directory:
            binary = Path(directory) / "markers"
            result = subprocess.run([compiler, "-std=c++20", "-O1", "-w",
                                     "-I" + str(ROOT / "gpu/vk/eden"),
                                     "-I" + str(ROOT / "gpu/vk/compat"),
                                     str(ROOT / "tests/native/lower_register_markers_test.cpp"),
                                     "-o", str(binary)], capture_output=True, text=True, timeout=90)
            self.assertEqual(result.returncode, 0, result.stderr)
            result = subprocess.run([str(binary)], capture_output=True, text=True, timeout=20)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertIn("89 cases, 0 failures", result.stdout)

    def test_changed_translator_cannot_reuse_baseline_shader_stamp(self):
        from akynoleyend.build_support import shader_cache_stamp, shader_source_identity
        from akynoleyend.config import ROOT as project_root
        import json
        import shutil
        # Controls-only API additions can be pinned to the audited current translator.
        # Register/IR changes must still fall out of that exact source fingerprint.
        vk = project_root / "gpu/vk"
        registry = project_root / "profiles/shader-cache-compatible.json"
        stamp = shader_cache_stamp(vk, registry)
        records = json.loads(registry.read_text())["source_sets"]
        fingerprint = shader_source_identity(vk)[1]
        self.assertEqual(stamp, records[fingerprint]["stamp"])
        with tempfile.TemporaryDirectory() as temporary:
            changed = Path(temporary)
            for name in ("eden", "sirit", "compat"):
                shutil.copytree(vk / name, changed / name)
            for name in ("vk_shader.cpp", "vk_shader.h", "vk_api.h", "vk_state.h"):
                shutil.copy2(vk / name, changed / name)
            emitter = changed / "eden" / "changed-translator-fixture.cpp"
            emitter.write_text("// A different translator source set must not inherit the controls stamp.\n")
            self.assertNotEqual(shader_cache_stamp(changed, registry), stamp)
            self.assertEqual(shader_cache_stamp(changed, registry), shader_source_identity(changed)[0])



if __name__ == "__main__":
    unittest.main()

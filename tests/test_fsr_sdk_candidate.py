"""Regression checks for the camera hook gate and the opt-in SDK launch path."""

from hashlib import sha256
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest

from akynoleyend.environment import runtime_environment
from akynoleyend.errors import ProjectError
from akynoleyend.fsr_sdk import SDK_DLLS, jitter_emitted, sdk_directory
from akynoleyend.graphics import graphics_environment
from nx2.oot_fsr_jitter import MAIN, SITES, install, record_emission


class FidelityFxCandidateTests(unittest.TestCase):
    def test_camera_hooks_require_all_original_words(self):
        words = {MAIN + offset: word for offset, word, _, _ in SITES}
        previous = {MAIN + SITES[0][0]: "existing hook"}
        lifter = SimpleNamespace(after=previous.copy())
        bad = dict(words)
        bad[MAIN + SITES[-1][0]] = 0
        self.assertFalse(install(lifter, SimpleNamespace(word=bad.__getitem__)))
        self.assertEqual(lifter.after, previous)
        self.assertTrue(install(lifter, SimpleNamespace(word=words.__getitem__)))
        self.assertTrue(lifter.after[MAIN + SITES[0][0]].startswith("existing hook\n"))
        self.assertEqual(set(lifter.after), set(words))
        with tempfile.TemporaryDirectory() as directory:
            work = Path(directory)
            gen = work / "sa" / "gen"
            gen.mkdir(parents=True)
            code = gen / "code_000.c"
            code.write_text("\n".join(lifter.after.values()), encoding="utf-8")
            record_emission(gen, [code], True)
            self.assertTrue(jitter_emitted(work))
            code.write_text(lifter.after[MAIN + SITES[0][0]], encoding="utf-8")
            record_emission(gen, [code], True)
            self.assertFalse(jitter_emitted(work))

    def test_temporal_is_opt_in_and_leaves_spatial_available(self):
        env = runtime_environment({"AKYNO_FSR_TEMPORAL": "1", "AKYNO_FSR_SDK_DIR": "elsewhere"}, "original")
        self.assertNotIn("AKYNO_FSR_TEMPORAL", env)
        self.assertNotIn("AKYNO_FSR_SDK_DIR", env)
        self.assertEqual(graphics_environment(upscaling="fsr"), {"RX_VK_UPSCALE": "3", "AKYNO_UPSCALER": "fsr"})
        self.assertEqual(graphics_environment(upscaling="fsr-temporal"),
                         {"RX_VK_UPSCALE": "3", "AKYNO_FSR_TEMPORAL": "1",
                          "AKYNO_UPSCALER": "fsr-temporal", "AKYNO_RESOLUTION": "4", "HOS_DYNRES": "0"})

    def test_signed_dll_receipt_refuses_modified_pair(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            vendor = root / "third_party" / "amd-fsr-sdk"
            bin_dir = vendor / "signedbin"
            bin_dir.mkdir(parents=True)
            hashes = {}
            for name in SDK_DLLS:
                dll = bin_dir / name
                dll.write_bytes(name.encode("ascii"))
                hashes[name] = sha256(dll.read_bytes()).hexdigest()
            (vendor / "sdk.json").write_text(json.dumps({"dlls": hashes}), encoding="utf-8")
            self.assertEqual(sdk_directory(root), bin_dir.resolve())
            (bin_dir / SDK_DLLS[0]).write_bytes(b"changed fixture")
            with self.assertRaises(ProjectError):
                sdk_directory(root)


if __name__ == "__main__":
    unittest.main()

"""Prevent silent reintroduction of unlimited driver compilation workers."""
import importlib.util
import os
import shutil
import subprocess
from pathlib import Path
import unittest
import tempfile

ROOT = Path(__file__).resolve().parents[1]

class CacheBuildAuditTests(unittest.TestCase):
    def test_pipeline_and_seed_share_bounded_worker_helper(self):
        policy = (ROOT / 'gpu/vk/cache_policy.h').read_text(encoding='utf8')
        draw = (ROOT / 'gpu/vk/vk_draw.cpp').read_text(encoding='utf8')
        self.assertIn('inline unsigned warmup_workers(', policy)
        self.assertIn('1, 8);', policy)
        self.assertIn('cache::warmup_workers(std::thread::hardware_concurrency(), total, 2)', draw)
        self.assertIn('cache::warmup_workers(cpus, total,', draw)
        self.assertNotIn('std::min(cpus,64u)', draw)

    def test_real_native_ampere_lowering_depbar(self):
        compiler = shutil.which('c++') or shutil.which('clang++')
        if not compiler:
            self.skipTest('A C++20 compiler is required for lowering regression')
        with tempfile.TemporaryDirectory() as folder:
            exe = Path(folder) / ('lower.exe' if os.name == 'nt' else 'lower')
            result = subprocess.run([
                compiler, '-std=c++20', '-O1', '-w',
                '-I' + str(ROOT / 'gpu/vk/eden'),
                '-I' + str(ROOT / 'gpu/vk/compat'),
                str(ROOT / 'tests/native/lower_depbar_042.cpp'), '-o', str(exe),
            ], capture_output=True, text=True, timeout=120)
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            run = subprocess.run([str(exe)], capture_output=True, text=True, timeout=30)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('every dependency barrier form lowers', run.stdout)

    def test_summary_follows_log_without_claiming_zero_jit(self):
        source = ROOT / 'tools/analisar_log_shaders.py'
        spec = importlib.util.spec_from_file_location('cache_audit', source)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        content = '\n'.join([
            '[hos host] hookshot v2.0.5 (source xxxx)',
            '[hos host] vk: NVIDIA GeForce RTX 4060 Ti, Vulkan 1.4, driver 0x1',
            r'[hos host] vk: program cache C:\\private\\x.bin: 0 program keys kept, 0 KB',
            r'[hos host] vk: pipeline cache C:\\private\\y.bin (464205 KB)',
            '[hos host] vk: prepared 38809 shader programs (46570 new, 97 failed, 10340 stage libraries; 10340 compute variants, 807 programs with texture variants, 65 at the limit) in 639.9 s',
            '[hos host] vk: precompile: 10340 programs, 0 graphics notes, 0 graphics and 10340 compute pipelines built in 6853 ms',
            '[hos host] vk: NVN2 program 1234abcd (stage 5) does not lower at +0x80: unsupported native opcode (native op 0x905, foo)',
            '[hos Presentation Thread] vk: 7200 presents, 29.5 fps; a frame: 1464 draws (0 skipped), 118 dispatches',
            '[hos Presentation Thread] vk: a frame: 58.8 draws left out (not ready), 0.12 waits for shaders or pipelines (54.6 ms); translation',
            '[hos Presentation Thread] vk: GPU time 23.8 ms a frame',
        ])
        with tempfile.TemporaryDirectory() as temp:
            log = Path(temp) / 'game.log'; log.write_text(content, encoding='utf8')
            result = module.analyze(log)
        self.assertEqual(result['shader_preparation']['programs'], 38809)
        self.assertEqual(result['pipeline_precompile']['graphics_built'], 0)
        self.assertEqual(result['pipeline_precompile']['graphics_notes'], 0)
        self.assertEqual(result['pipeline_precompile']['compute_built'], 10340)
        self.assertEqual(result['failed_lowerings_visible'], 1)
        self.assertEqual(result['not_ready_draws_peak_sample'], 58.8)
        self.assertEqual(result['shader_wait_ms_peak_sample'], 54.6)
        self.assertEqual(result['driver_pipeline_cache_kib'], 464205)
        self.assertFalse(result['device_lost_reported'])
        self.assertEqual(result['sampled_fps_last'], 29.5)
        self.assertNotIn('private', str(result))

if __name__ == '__main__':
    unittest.main()

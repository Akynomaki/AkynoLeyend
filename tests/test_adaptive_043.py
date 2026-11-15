"""Exercise independent output, actual hardware plans and exact-host maintenance."""
import contextlib
import io
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend import __version__
from akynoleyend.build import source_identity
from akynoleyend.cli import parser
from akynoleyend.coherence import HOST_REVISION, PREVIOUS_HOST_SOURCES, require_host
from akynoleyend.config import compile_jobs
from akynoleyend.errors import ProjectError
from akynoleyend.files import sha256, write_json
from akynoleyend.graphics import graphics_environment
from akynoleyend.hardware import recommended_chunk, shader_workers, usable_memory
from akynoleyend.launch import launch, verify_build
from akynoleyend.shader_prepare import _update_renderer

ROOT = Path(__file__).resolve().parents[1]
GIB = 1 << 30


class AdaptiveTests(unittest.TestCase):
    def test_plans_use_available_memory_affinity_and_commit_not_a_saved_machine(self):
        low = {"ram_total": 16*GIB, "ram_available": 8*GIB, "commit_available": 0, "logical_cpus": 6}
        high = {"ram_total": 48*GIB, "ram_available": 32*GIB, "commit_available": 40*GIB, "logical_cpus": 24}
        self.assertEqual(recommended_chunk(low), 6)
        # (0.4.5: the slots by a typical unit's measured peak; nx2/build.py's memory gate holds a heavy unit back)
        self.assertEqual(compile_jobs(None, usable_memory(low), low["logical_cpus"]), 6)
        self.assertEqual(recommended_chunk(high), 12)
        self.assertEqual(compile_jobs(None, usable_memory(high), 24, chunk_mib=12), 8)
        high["commit_available"] = 5*GIB
        self.assertEqual(compile_jobs(None, usable_memory(high), 24, chunk_mib=12), 5)
        self.assertEqual(shader_workers(dict(low, logical_cpus=1)), 1)
        self.assertEqual(shader_workers(low, background=True), 2)
        self.assertEqual(compile_jobs(3, 0, 1), 3)  # explicit user selection

    def test_hardware_cli_detects_current_process_without_requiring_game_or_tools(self):
        result = subprocess.run([sys.executable, str(ROOT/'manage.py'), 'hardware'],
                                capture_output=True, text=True, timeout=20)
        self.assertEqual(result.returncode, 0, result.stderr)
        info = json.loads(result.stdout.removeprefix('@@hardware '))
        self.assertGreaterEqual(info['logical_cpus'], 1)
        self.assertGreaterEqual(info['ram_total'], info['ram_available'])
        self.assertIn(info['chunk_mib'], (6, 12))
        self.assertGreaterEqual(info['jobs'], 1)

    def test_fsr_preset_can_reset_4k_output_without_overriding_internal_scale(self):
        args = parser().parse_args(['run', '--resolution', '67', '--output-resolution', 'game', '--upscaling', 'fsr'])
        env = graphics_environment(resolution=args.resolution, output_resolution=args.output_resolution,
                                   upscaling=args.upscaling, sharpness=10, framegen=0)
        self.assertEqual(env['HOS_OUTPUT_RES'], '0')
        self.assertEqual(env['AKYNO_RESOLUTION'], '3')
        self.assertEqual(env['RX_VK_UPSCALE'], '3')
        self.assertEqual(env['AKYNO_SHARPNESS'], '10')
        self.assertNotIn('HOS_RES_SCALE', env)
        with self.assertRaises(ProjectError):
            graphics_environment(resolution='native-4k', output_resolution='game')

    def test_exact_test1_host_update_launches_without_rebuilding_or_changing_save(self):
        with tempfile.TemporaryDirectory() as temporary:
            base = Path(temporary); game = base/'jogo'; game.mkdir()
            romfs = base/'romfs'
            for name in ['System', 'Pack']: (romfs/name).mkdir(parents=True)
            for name in ['AkynoLeyend.exe', 'image.bin', 'AkynoLeyend.dll']: (game/name).write_bytes(name.encode())
            save = game/'user/save/keep'; save.parent.mkdir(parents=True); save.write_bytes(b'save')
            source = next(iter(PREVIOUS_HOST_SOURCES['0.4.3-test.1']))
            manifest = {'schema': 1, 'project': 'AkynoLeyend', 'version': '0.4.3-test.1',
                        'host_revision': HOST_REVISION, 'source_sha256': source,
                        'game_build_id': 'e0f3ccfa', 'romfs': str(romfs),
                        'files': {n: sha256(game/n) for n in ['AkynoLeyend.exe', 'AkynoLeyend.dll', 'image.bin']}}
            write_json(game/'AkynoLeyend-build.json', manifest)
            before = {p: p.read_bytes() for p in [game/'AkynoLeyend.exe', game/'image.bin', save]}
            ready = base/'ready'; ready.mkdir(); dll = ready/'AkynoLeyend.dll'; dll.write_bytes(b'AkynoLeyend.dll')
            write_json(ready/'renderer.json', {'source_sha256': 'generic', 'binary_sha256': sha256(dll)})
            with contextlib.redirect_stdout(io.StringIO()):
                with self.assertRaises(ProjectError): launch(game, require_current_build=True, dry_run=True)
                with patch('akynoleyend.shader_prepare.renderer_prebuilt', return_value=dll):
                    updated = _update_renderer(game, manifest, lambda _: None)
                self.assertEqual(updated['runtime_source_sha256'], source_identity())
                self.assertEqual(updated['renderer_version'], __version__)
                self.assertEqual(launch(game, require_current_build=True, dry_run=True), 0)
            for path, content in before.items(): self.assertEqual(path.read_bytes(), content)
            self.assertEqual(verify_build(game)['version'], '0.4.3-test.1')
            with self.assertRaises(ProjectError): require_host(dict(manifest, source_sha256='modified'))
            with self.assertRaises(ProjectError): require_host(dict(manifest, host_revision='old-abi'))

    def test_unrecognized_old_host_is_rejected_before_updating_any_file(self):
        manifest = {'version': '0.4.3-test.1', 'host_revision': HOST_REVISION,
                    'source_sha256': 'unrecognized', 'game_build_id': 'e0f3ccfa'}
        with patch('akynoleyend.shader_prepare.renderer_prebuilt', side_effect=AssertionError('must reject first')):
            with self.assertRaises(ProjectError): _update_renderer(Path('unused'), manifest, print)

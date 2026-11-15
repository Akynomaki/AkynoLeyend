"""Resolution-diagnostics regressions; no claim of GPU-verified image quality."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
from akynoleyend.graphics import has_fixed_scale_hook, graphics_environment
from akynoleyend.errors import ProjectError
import akynoleyend.launch as launcher


class ResolutionOverrideTests(unittest.TestCase):
    def test_env_wires_requested_scale(self):
        for value, expected, menu_index in (("125","1.25", "5"),("150","1.5", "6")):
            with self.subTest(value=value):
                env=graphics_environment(resolution=value)
                self.assertEqual(env['AKYNO_RESOLUTION'], menu_index)
                self.assertEqual(env['HOS_DYNRES'], '0')
                self.assertEqual(env['HOS_RES_SCALE'], expected)

    def test_binary_marker_and_chunk_boundary(self):
        with tempfile.TemporaryDirectory() as tmp:
            f=Path(tmp)/'AkynoLeyend.exe'
            f.write_bytes(b'abc123')
            self.assertFalse(has_fixed_scale_hook(f))
            f.write_bytes(b'x'*((1<<20)-4)+b'HOS_RES_SCALE\x00')
            self.assertTrue(has_fixed_scale_hook(f))
            f.write_bytes(b'x'*(1<<20)+b'HOS_RES_SCA' + b'LE\x00')
            self.assertTrue(has_fixed_scale_hook(f))

    def test_missing_host_switch_is_not_silently_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp)
            (root/'AkynoLeyend.exe').write_bytes(b'stale-host')
            with patch.object(launcher,'checked_build',return_value={'romfs':str(root)}):
                with self.assertRaisesRegex(ProjectError,'nao contem o suporte nativo'):
                    launcher.launch(root,resolution='150',dry_run=True)

    def test_native_source_has_cpu_side_active_log(self):
        source=(Path(__file__).resolve().parents[1]/'host/nn_vi.c').read_text(encoding='utf-8')
        self.assertIn('vi: fixed scale active:', source)
        self.assertIn('HOS_RES_SCALE invalid', source)

if __name__=='__main__':unittest.main()

"""Visual A/B controls must survive inherited-environment sanitization, and old builds must fail closed."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from akynoleyend import __version__
from akynoleyend.cli import parser
from akynoleyend.environment import VISUAL_MODES, runtime_environment
from akynoleyend.errors import ProjectError
from akynoleyend.launch import launch


class VisualControlTests(unittest.TestCase):
    def test_cli_defaults_and_choices(self):
        p = parser()
        a = p.parse_args(['run', '--require-current-build', '--visual-mode', 'patched'])
        self.assertTrue(a.require_current_build)
        self.assertEqual(a.visual_mode, 'patched')
        b = p.parse_args(['run', '--visual-mode', 'comparison'])
        self.assertEqual(b.visual_mode, 'comparison')

    def test_visual_controls_applied_after_sanitization(self):
        env = runtime_environment({'RX_VK_BARE_READ_MB': '999', 'PATH': 'somewhere'}, 'original')
        self.assertNotIn('RX_VK_BARE_READ_MB', env)
        env.update(VISUAL_MODES['patched'])
        self.assertEqual(env['RX_VK_BARE_READ_MB'], '130')
        self.assertEqual(env['RX_VK_KEEP_FINALIZED_MB'], '256')
        env = runtime_environment({'RX_VK_NO_GRID_PATCH': '1'}, 'original')
        env.update(VISUAL_MODES['comparison'])
        self.assertEqual(env['RX_VK_NO_GRID_PATCH'], '1')
        self.assertEqual(env['AKYNO_OCCLUSION_OFF'], '0')

    def test_strict_gate_rejects_old_version(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('akynoleyend.launch.checked_build', return_value={'version': '0.4.0-dev.1', 'source_sha256': 'old'}):
                with patch('akynoleyend.build.source_identity', return_value='new'):
                    with self.assertRaisesRegex(ProjectError, 'nao corresponde'):
                        launch(Path(d), require_current_build=True, dry_run=True)

    def test_strict_gate_rejects_stale_sources(self):
        with tempfile.TemporaryDirectory() as d:
            with patch('akynoleyend.launch.checked_build', return_value={'version': __version__, 'source_sha256': 'old'}):
                with patch('akynoleyend.build.source_identity', return_value='new'):
                    with self.assertRaisesRegex(ProjectError, 'nao corresponde'):
                        launch(Path(d), require_current_build=True, dry_run=True)


if __name__ == '__main__':
    unittest.main()

"""Checks for a source-only AkynoLeyend 0.4.1 integration.

No real Windows renderer, game or GPU is exercised by these tests.
"""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from akynoleyend.graphics import graphics_environment
from akynoleyend.environment import CACHE_MODES, runtime_environment
from akynoleyend.cli import parser
from akynoleyend.errors import ProjectError
from akynoleyend.files import sha256, write_json
from akynoleyend.shader_prepare import prepare_shaders

ROOT=Path(__file__).resolve().parents[1]

class Integrated041Tests(unittest.TestCase):
    def test_resolution_over_100_uses_existing_native_fixed_scale(self):
        for scale in ("125", "150"):
            with self.subTest(scale=scale):
                e=graphics_environment(resolution=scale)
                self.assertEqual(e['HOS_RES_SCALE'], str(int(scale)/100))
                self.assertEqual(e['AKYNO_RESOLUTION'], '5' if scale == '125' else '6')
                self.assertEqual(e['HOS_DYNRES'], '0')
        self.assertEqual(graphics_environment(resolution='100').get('HOS_RES_SCALE'),None)
        self.assertEqual(graphics_environment(resolution='auto').get('HOS_RES_SCALE'),None)
        with self.assertRaises(ProjectError): graphics_environment(resolution='200')
        self.assertEqual(parser().parse_args(['run','--resolution','150']).resolution,'150')

    def test_shader_workers_and_bounded_cache_are_optional(self):
        self.assertEqual(parser().parse_args(['run','--shader-workers','4']).shader_workers,4)
        self.assertEqual(parser().parse_args(['prepare-shaders','--shader-workers','2']).shader_workers,2)
        base=runtime_environment({'RX_VK_COMPILE_THREADS':'100'}, 'original', cache_mode='original')
        self.assertNotIn('RX_VK_COMPILE_THREADS',base)
        special=runtime_environment({},'original',cache_mode='equilibrado')
        self.assertEqual(special['RX_VK_COMPILE_THREADS'],'4')
        self.assertEqual(CACHE_MODES['original'],{})
        self.assertNotIn('RX_VK_VRAM_MB',special)

    def test_repeat_prep_avoids_publishing_identical_bank(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);game=root/'jogo';game.mkdir();work=root/'work';(work/'shaders').mkdir(parents=True)
            romfs=root/'romfs';romfs.mkdir()
            bank=work/'shaders'/'AkynoLeyend_shaders.bin'
            bank.write_bytes(b'synthetic shader data\0' * 32)
            marker=bank.parent/'seed.json'
            write_json(marker,{'schema':1,'input':'id','sha256':sha256(bank)})
            dest=game/bank.name; dest.write_bytes(bank.read_bytes())
            manifest={'romfs':str(romfs),'files':{'image.bin':'fixture'}}
            notes=[]
            with patch('akynoleyend.shader_prepare.checked_build',return_value=manifest),\
                patch('akynoleyend.shader_prepare._update_renderer',return_value=manifest),\
                patch('akynoleyend.shader_prepare.seed_identity',return_value='id'),\
                patch('akynoleyend.shader_prepare.copy_chunks',side_effect=AssertionError('must not copy')):
                self.assertEqual(prepare_shaders(game,work,start_game=False,report=notes.append),0)
            self.assertIn('Banco de shaders ja instalado e conferido; copia dispensada.',notes)
            self.assertEqual(dest.read_bytes(), bank.read_bytes())
            dest.write_bytes(b'incorrect')
            with patch('akynoleyend.shader_prepare.checked_build',return_value=manifest),\
                patch('akynoleyend.shader_prepare._update_renderer',return_value=manifest),\
                patch('akynoleyend.shader_prepare.seed_identity',return_value='id'):
                self.assertEqual(prepare_shaders(game,work,start_game=False,report=notes.append),0)
            self.assertEqual(dest.read_bytes(), bank.read_bytes())

    def test_amd_mesh_workaround_is_targeted_with_opt_out(self):
        source=(ROOT/'gpu/vk/vk_draw.cpp').read_text(encoding='utf8')
        self.assertIn('RX_VK_MESH_OPT',source)
        self.assertIn('VK_PIPELINE_CREATE_DISABLE_OPTIMIZATION_BIT',source)
        self.assertIn('VK_SHADER_STAGE_TASK_BIT_EXT | VK_SHADER_STAGE_MESH_BIT_EXT',source)
        self.assertIn('properties.vendorID == 0x1002',source)

if __name__=='__main__': unittest.main()

"""Update transactions, reuse-only compilation and automatic preparation controls."""
from contextlib import redirect_stdout
import hashlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch
import zipfile

from akynoleyend import __version__
from akynoleyend.build_support import object_key, require_cached_game_objects
from akynoleyend.coherence import HOST_REVISION, PREVIOUS_HOST_SOURCES
from akynoleyend.config import MANIFEST
from akynoleyend.errors import ProjectError
from akynoleyend.files import read_json, sha256, write_json
from akynoleyend.graphics import graphics_environment
from akynoleyend.maintenance import maintain_build
from akynoleyend.updater import stage_update, install_files, inspect_package


def package(path, extra=None):
    files = {"AkynoLeyendBuilder.exe": b'MZ-new-ui', "manage.py": b'# new orchestrator\n',
             "VERSION": b'0.4.3-test.9\n', "ferramentas/prebuilt/AkynoLeyend.dll": b'MZ-renderer',
             "ferramentas/prebuilt/renderer.json": b'{}', "akynoleyend/new_module.py": b'# new\n'}
    files.update(extra or {})
    index = {"schema": 1, "kind": "update", "version": "0.4.3-test.9",
             "files": {n: hashlib.sha256(v).hexdigest() for n,v in files.items()}}
    with zipfile.ZipFile(path, 'w') as z:
        for n,v in files.items(): z.writestr(n,v)
        z.writestr('update-package.json',json.dumps(index))
    return files


class UpdatePackageTests(unittest.TestCase):
    def test_package_install_preserves_sdk_settings_and_saves(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'project';root.mkdir();archive=Path(d)/'update.zip';package(archive)
            saved={'work/objcache/compiled.o':b'object','jogo/user/save.bin':b'save',
                   'ferramentas/python/python.exe':b'python','AkynoLeyend-launcher.json':b'preferences'}
            for n,v in saved.items():p=root/n;p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(v)
            (root/'manage.py').write_bytes(b'old')
            plan=stage_update(archive,root,root/'jogo',report=lambda _:None)
            maintain=[];install_files(plan,maintain.append)
            self.assertEqual((root/'manage.py').read_bytes(),b'# new orchestrator\n')
            self.assertEqual(len(maintain),1)
            for n,v in saved.items():self.assertEqual((root/n).read_bytes(),v)

    def test_failed_maintenance_restores_previous_sources_and_removes_new_files(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'project';root.mkdir();archive=Path(d)/'update.zip';package(archive)
            (root/'manage.py').write_bytes(b'previous');(root/'AkynoLeyendBuilder.exe').write_bytes(b'MZ-old')
            plan=stage_update(archive,root,root/'jogo',report=lambda _:None)
            def fail(_):raise ProjectError('synthetic compile failure')
            with self.assertRaisesRegex(ProjectError,'synthetic'):install_files(plan,fail)
            self.assertEqual((root/'manage.py').read_bytes(),b'previous')
            self.assertEqual((root/'AkynoLeyendBuilder.exe').read_bytes(),b'MZ-old')
            self.assertFalse((root/'akynoleyend/new_module.py').exists())
            self.assertFalse(list(root.rglob('*.update-*')))

    def test_traversal_settings_work_and_sdk_replacement_are_rejected(self):
        with tempfile.TemporaryDirectory() as d:
            for name in ('../escape.py','C:/escape.py','jogo/user/save.bin','work/objcache/a.o',
                         'AkynoLeyend-launcher.json','ferramentas/python/python.exe'):
                with self.subTest(name=name):
                    archive=Path(d)/'bad.zip';package(archive,{name:b'bad'})
                    with self.assertRaises(ProjectError):inspect_package(archive)

    def test_tampering_after_prepare_fails_before_installing_any_file(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d)/'project';root.mkdir();archive=Path(d)/'update.zip';package(archive)
            (root/'manage.py').write_bytes(b'old')
            plan=stage_update(archive,root,root/'jogo',report=lambda _:None)
            (plan.parent/'arquivos/manage.py').write_bytes(b'changed')
            with self.assertRaisesRegex(ProjectError,'alterado'):install_files(plan)
            self.assertEqual((root/'manage.py').read_bytes(),b'old')


class RuntimeMaintenanceTests(unittest.TestCase):
    def test_missing_or_changed_game_object_never_starts_a_compile(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);source=root/'code_000.c';source.write_text('void game(void){}\n')
            output=root/'code.o';cache=root/'cache';cache.mkdir()
            job=(sys.executable,str(source),str(output),['-O1'],b'header')
            with self.assertRaises(ProjectError):require_cached_game_objects([job],cache)
            key=object_key(*[job[i] for i in (0,1,3,4)])
            (cache/(key+'.o')).write_bytes(b'cached')
            require_cached_game_objects([job],cache)
            output.write_bytes(b'local');Path(str(output)+'.sha256').write_text(key)
            (cache/(key+'.o')).unlink();require_cached_game_objects([job],cache)
            source.write_text('void changed_game(void){}\n')
            with self.assertRaises(ProjectError):require_cached_game_objects([job],cache)

    def test_pinned_host_update_uses_existing_generated_code_without_lift_or_extraction(self):
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);folder=root/'jogo';work=root/'work';romfs=root/'romfs';folder.mkdir()
            for n in ('Pack','System'):(romfs/n).mkdir(parents=True)
            (folder/'user').mkdir();(folder/'user/save.dat').write_bytes(b'keep-save')
            for n in ('AkynoLeyend.exe','AkynoLeyend.dll','image.bin'):(folder/n).write_bytes(n.encode())
            old={'schema':1,'project':'AkynoLeyend','version':'0.4.3-test.1','host_revision':HOST_REVISION,
                 'source_sha256':next(iter(PREVIOUS_HOST_SOURCES['0.4.3-test.1'])),
                 'game_build_id':'e0f3ccfa','romfs':str(romfs),
                 'files':{n:sha256(folder/n) for n in ('AkynoLeyend.exe','AkynoLeyend.dll','image.bin')}}
            write_json(folder/MANIFEST,old)
            gen=work/'sa/gen';gen.mkdir(parents=True)
            for n in ('a64_table.c','a64_hooks.c','a64_suyu.c','a64_stubs.c','hos_image.c','nvn2_exports.c','code_000.c'):(gen/n).write_text('/* generated */')
            image=work/'sa/image/image.bin';image.parent.mkdir();image.write_bytes((folder/'image.bin').read_bytes())
            write_json(work/'build-request.json',{'game_build_id':'e0f3ccfa','output':str(folder)})
            calls=[]
            def compile_only(command,*_):
                calls.append(command)
                built=work/'sa/build';built.mkdir(exist_ok=True)
                for n in ('AkynoLeyend.exe','AkynoLeyend.dll'):(built/n).write_bytes(b'new-'+n.encode())
                write_json(work/'logs/compile-summary.json',{'schema':1,'renderer_prebuilt':True})
            sys.path.insert(0,str(Path(__file__).resolve().parent))
            from test_maintenance_renderer import ready_renderer
            ready_renderer(root/'tools',target=None)   # (the package's verified DLL is required)
            with patch('akynoleyend.maintenance.require_tools',return_value={}), \
                 patch('akynoleyend.maintenance.run',side_effect=compile_only), \
                 patch('akynoleyend.build.renderer_identity',return_value='generic-test-renderer'):
                updated=maintain_build(folder,work,root/'tools',report=lambda _:None)
            # (r10: a work without the frame-step marker first gets the step hook, only that, then the relink)
            self.assertEqual(len(calls),2)
            self.assertEqual(Path(calls[0][3]).name,'upgrade_output.py')
            self.assertIn('--step-only',calls[0])
            self.assertEqual(Path(calls[1][3]).name,'build.py')
            self.assertIn('--reuse-game-objects',calls[1])
            self.assertEqual(updated['version'],__version__)
            self.assertFalse(updated['maintenance']['lift_repeated'])
            self.assertEqual((folder/'user/save.dat').read_bytes(),b'keep-save')
            self.assertEqual(updated['files']['image.bin'],old['files']['image.bin'])
            self.assertIn('fullhd-video-budget-v1',updated['host_features'])
            # A failure after publishing must put the whole previous runtime back.
            for n in old['files']:(folder/n).write_bytes(n.encode())
            write_json(folder/MANIFEST,old)
            def publish_then_fail(*args):
                from akynoleyend.build import publish
                publish(*args)
                raise ProjectError('synthetic publication failure')
            with patch('akynoleyend.maintenance.require_tools',return_value={}), \
                 patch('akynoleyend.maintenance.run',side_effect=compile_only), \
                 patch('akynoleyend.build.renderer_identity',return_value='generic-test-renderer'), \
                 patch('akynoleyend.maintenance.publish',side_effect=publish_then_fail):
                with self.assertRaisesRegex(ProjectError,'synthetic publication'):
                    maintain_build(folder,work,root/'tools',report=lambda _:None)
            self.assertEqual(read_json(folder/MANIFEST),old)
            for n,digest in old['files'].items():self.assertEqual(sha256(folder/n),digest)
            self.assertEqual((folder/'user/save.dat').read_bytes(),b'keep-save')

    def test_full_hd_fps_and_handheld_controls_have_independent_runtime_values(self):
        value=graphics_environment(output_resolution='1080p',resolution='50',upscaling='fsr',fps_counter=True,handheld=True)
        self.assertEqual(value['HOS_OUTPUT_RES'],'3');self.assertEqual(value['AKYNO_RESOLUTION'],'4')
        self.assertEqual(value['AKYNO_FPS_COUNTER'],'1');self.assertEqual(value['HOS_HANDHELD'],'1')
        with self.assertRaises(ProjectError):graphics_environment(fps_counter='on')


class AutomaticPreparationTests(unittest.TestCase):
    def test_play_prepares_bank_then_starts_real_child_with_native_preparation_enabled(self):
        import akynoleyend.launch as launcher
        with tempfile.TemporaryDirectory() as d:
            root=Path(d);game=root/'game';game.mkdir();romfs=root/'romfs'
            for n in ('Pack','System'):(romfs/n).mkdir(parents=True)
            exe=game/'AkynoLeyend.exe'
            if os.name == 'nt':   # (a real Windows child: CreateProcess does not run a script with a shebang)
                sys.path.insert(0, str(Path(__file__).resolve().parent))
                from native_tools import native_cc
                cc = native_cc()
                if not cc: self.skipTest('A C compiler is needed for the real Windows child')
                (root/'child.c').write_text('#include <stdio.h>\n#include <stdlib.h>\nstatic void put(const char*k,const char*n,int last){const char*v=getenv(n);if(v)printf("\\"%s\\":\\"%s\\"%s",k,v,last?"":",");else printf("\\"%s\\":null%s",k,last?"":",");}\nint main(void){printf("{");put("seed","RX_VK_SEED_PREPARE",0);put("progress","AKYNO_LAUNCHER_PROGRESS",0);put("fps","AKYNO_FPS_COUNTER",1);printf("}\\n");return 0;}\n', newline='\n')
                built = subprocess.run([cc, str(root/'child.c'), '-o', str(exe), '-static'], capture_output=True, text=True, timeout=60)
                self.assertEqual(built.returncode, 0, built.stdout + built.stderr)
            else:
                exe.write_text(f'#!{sys.executable}\nimport os,json\nprint(json.dumps({{"seed":os.getenv("RX_VK_SEED_PREPARE"),"progress":os.getenv("AKYNO_LAUNCHER_PROGRESS"),"fps":os.getenv("AKYNO_FPS_COUNTER")}}))\n')
                exe.chmod(0o755)
            for n in ('AkynoLeyend.dll','image.bin'):(game/n).write_bytes(b'fixture')
            write_json(game/MANIFEST,{'schema':1,'project':'AkynoLeyend','version':__version__,'romfs':str(romfs),
                'files':{n:sha256(game/n) for n in ('AkynoLeyend.exe','AkynoLeyend.dll','image.bin')}})
            fake_os=SimpleNamespace(name='nt',environ=os.environ,getpid=os.getpid)
            with patch.object(launcher,'os',fake_os),patch('akynoleyend.shader_prepare.prepare_shaders',return_value=0) as prepare,redirect_stdout(io.StringIO()):
                self.assertEqual(launcher.launch(game,fps_counter=True,work=root/'work'),0)
            prepare.assert_called_once()
            self.assertFalse(prepare.call_args.kwargs['start_game'])
            self.assertIn('verified_manifest',prepare.call_args.kwargs)
            logs=next((game/'diagnosticos').glob('*/saida.log'))
            child=json.loads(logs.read_text())
            self.assertEqual(child,{'seed':'1','progress':'1','fps':'1'})


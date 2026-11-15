"""The update page previews verified plain-text changes before installation."""
from pathlib import Path
import hashlib
import json
import tempfile
import unittest
import zipfile

from akynoleyend.errors import ProjectError
from akynoleyend.files import read_json
from akynoleyend.updater import INDEX, inspect_package, package_notes, stage_update


class UpdateNotes(unittest.TestCase):
    def test_legacy_package_has_no_invented_changes(self):
        self.assertEqual(package_notes({}),dict(new=[],fixes=[],experimental=[],known_issues=[]))

    def test_notes_are_bounded_typed_and_keep_experimental_separate(self):
        good=package_notes({'notes':{'new':['  Controles  '],'fixes':['Correção'], 'experimental':['Teste opt-in']}})
        self.assertEqual(good['new'],['Controles'])
        self.assertEqual(good['experimental'],['Teste opt-in'])
        for notes in (None,[],{'new':[1]},{'fixes':['']},{'experimental':['x'*1001]}, {'new':['x']*41}, {'unrecognized':[]}):
            with self.subTest(notes=notes):
                with self.assertRaises(ProjectError):package_notes({'notes':notes})

    def test_staging_preserves_exact_notes_without_installing_any_file(self):
        with tempfile.TemporaryDirectory() as temp:
            root=Path(temp)/'app';root.mkdir();(root/'manage.py').write_bytes(b'old')
            files={'AkynoLeyendBuilder.exe':b'MZ-new-ui','manage.py':b'# new source', 'VERSION':b'test.4\n',
                   'ferramentas/prebuilt/AkynoLeyend.dll':b'MZ-new-renderer','ferramentas/prebuilt/renderer.json':b'{}'}
            notes={'new':['Página Atualizações'],'fixes':['Menu ajustado'],'experimental':['Write-back em teste']}
            meta={'schema':1,'kind':'update','version':'test.4','notes':notes,
                  'files':{n:hashlib.sha256(data).hexdigest() for n,data in files.items()}}
            archive=Path(temp)/'update.zip'
            with zipfile.ZipFile(archive,'w') as z:
                for n,data in files.items():z.writestr(n,data)
                z.writestr(INDEX,json.dumps(meta))
            self.assertEqual(inspect_package(archive)['notes'],notes)
            plan=stage_update(archive,root,root/'jogo',report=lambda _:None)
            self.assertEqual(read_json(plan)['notes'],package_notes(meta))
            self.assertEqual((root/'manage.py').read_bytes(),b'old')
            self.assertFalse((root/'AkynoLeyendBuilder.exe').exists())

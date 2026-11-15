"""Exact-key reuse across isolated roots must never invoke a compiler or write the original."""
from pathlib import Path
import os
import sys
import tempfile
import unittest

from akynoleyend.build_support import object_key, require_cached_game_objects
from akynoleyend.errors import ProjectError
from akynoleyend.object_reuse import isolated_game_jobs


class IsolatedObjectReuse(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        folder=Path(self.tmp.name);self.old=folder/"original";self.new=folder/"candidate"
        for root in (self.old,self.new):
            (root/"work/sa/gen").mkdir(parents=True)
            (root/"work/sa/gen/code_000.c").write_text('void f(void){}\n')
            (root/"work/sa/gen/a64.h").write_text('/* unchanged ABI */\n')
            (root/"nx2/rt").mkdir(parents=True)
            (root/"nx2/rt/a.h").write_text('/* unchanged runtime */\n')
        self.obj=self.old/"work/sa/build/obj/code_000.o";self.obj.parent.mkdir(parents=True)
        self.obj.write_bytes(b"compiled-game")
        self.flags=lambda root:['-O1','-march=x86-64-v3','-I'+str(root/'work/sa/gen'),'-I'+str(root/'nx2/rt')]
        self.key=object_key(sys.executable,str(self.old/'work/sa/gen/code_000.c'),self.flags(self.old),b'ABI')
        Path(str(self.obj)+'.sha256').write_text(self.key)
        self.job=(sys.executable,str(self.new/'work/sa/gen/code_000.c'),str(self.new/'work/sa/build/obj/code_000.o'),self.flags(self.new),b'ABI')

    def run_reuse(self,jobs=None):
        return isolated_game_jobs(jobs or [self.job],root=self.new,work=self.new/'work',previous_root=self.old,report=lambda _:None)

    def test_exact_old_key_and_copied_object_survive_without_mutating_original(self):
        before={p:p.read_bytes() for p in self.old.rglob('*') if p.is_file()}
        self.assertNotEqual(object_key(*[self.job[i] for i in (0,1,3,4)]),self.key)
        jobs=self.run_reuse()
        self.assertEqual(jobs[0][3],self.flags(self.old))
        require_cached_game_objects(jobs,self.new/'work/objcache')
        self.assertEqual(Path(jobs[0][2]).read_bytes(),b'compiled-game')
        self.assertFalse(os.path.samefile(self.obj,jobs[0][2]))
        self.assertEqual(before,{p:p.read_bytes() for p in self.old.rglob('*') if p.is_file()})

    def test_changed_generated_c_is_refused_before_any_copy(self):
        Path(self.job[1]).write_text('void changed(void){}')
        with self.assertRaisesRegex(ProjectError,'C traduzido diferente'):self.run_reuse()
        self.assertFalse(Path(self.job[2]).exists())

    def test_changed_abi_header_is_refused_before_any_copy(self):
        (self.new/'nx2/rt/a.h').write_text('/* changed ABI */')
        with self.assertRaisesRegex(ProjectError,'headers diferentes'):self.run_reuse()
        self.assertFalse(Path(self.job[2]).exists())

    def test_changed_optimization_or_dependency_key_is_refused(self):
        for flags,dep in ((['-O2',*self.job[3][1:]],b'ABI'),(self.job[3],b'changed ABI')):
            with self.subTest(flags=flags,dep=dep):
                with self.assertRaisesRegex(ProjectError,'Objeto/chave original ausente'):
                    self.run_reuse([(self.job[0],self.job[1],self.job[2],flags,dep)])
                self.assertFalse(Path(self.job[2]).exists())

    def test_invalid_later_job_does_not_copy_an_earlier_valid_one(self):
        bad=(self.job[0],self.job[1],self.job[2],['-O2',*self.job[3][1:]],b'ABI')
        with self.assertRaises(ProjectError):self.run_reuse([self.job,bad])
        self.assertFalse(Path(self.job[2]).exists())

    def test_original_work_or_hardlinked_object_is_refused(self):
        with self.assertRaises(ProjectError):
            isolated_game_jobs([self.job],root=self.old,work=self.old/'work',previous_root=self.old)
        output=Path(self.job[2]);output.parent.mkdir(parents=True)
        os.link(self.obj,output)
        with self.assertRaisesRegex(ProjectError,'mesmo arquivo/link'):self.run_reuse()
        self.assertEqual(self.obj.read_bytes(),b'compiled-game')

    def test_original_content_addressed_cache_is_accepted_when_local_output_missing(self):
        cache=self.old/'work/objcache';cache.mkdir();(cache/(self.key+'.o')).write_bytes(self.obj.read_bytes())
        self.obj.unlink();Path(str(self.obj)+'.sha256').unlink()
        jobs=self.run_reuse();require_cached_game_objects(jobs,self.new/'work/objcache')

    def test_hardlinked_stamp_is_replaced_without_writing_original(self):
        output=Path(self.job[2]);output.parent.mkdir(parents=True)
        os.link(Path(str(self.obj)+'.sha256'),Path(str(output)+'.sha256'))
        self.run_reuse()
        self.assertEqual(Path(str(self.obj)+'.sha256').read_text(),self.key)
        self.assertFalse(os.path.samefile(Path(str(self.obj)+'.sha256'),Path(str(output)+'.sha256')))

    def test_maintenance_refuses_original_destination_before_taking_a_write_lock(self):
        from akynoleyend.maintenance import maintain_build
        with self.assertRaisesRegex(ProjectError,'independentes'):
            maintain_build(self.old/'jogo',self.old/'work',self.old/'tools',reuse_game_from=self.old)
        self.assertFalse((self.old/'work/build.lock').exists())


if __name__=='__main__':unittest.main()

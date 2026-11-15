"""memory_failure: the exit code and the host's own lines; nothing else is called out of memory."""
import tempfile
import unittest
from pathlib import Path

from akynoleyend.runtime_failure import COMMIT_LIMIT_EXIT, VIRTUAL_MEMORY_MESSAGE, memory_failure

LINE = ("[hos host] mem: commit is running out: RAM 2859 MB free of 16306; system commit %d MB used of %d (%d free); "
        "this process 16306 MB private (peak 16359), 7116 MB working set\n")


class MemoryFailureTests(unittest.TestCase):
    def log(self, text):
        folder = tempfile.TemporaryDirectory()
        self.addCleanup(folder.cleanup)
        path = Path(folder.name) / "erros.log"
        path.write_text(text, encoding="utf-8")
        return path

    def test_commit_limit_exit_code_is_virtual_memory_even_without_lines(self):
        found = memory_failure(self.log("[hos host] boot\n"), -1073741523)   # (as Python reports 0xC000012D)
        self.assertEqual(found["kind"], "virtual_memory")
        self.assertEqual(found["exit_code"], COMMIT_LIMIT_EXIT)
        self.assertTrue(found["refused_commit"])

    def test_refused_commit_line_with_another_exit_code(self):
        found = memory_failure(self.log("[hos Resource Memory] mem: commit of 0x270000 bytes at 0x7f44710000 failed (error 1455)\n"), 3221225477)
        self.assertTrue(found["refused_commit"])

    def test_last_figures_are_reported_and_exhaustion_is_only_likely(self):
        found = memory_failure(self.log(LINE % (18000, 21272, 3272) + "x" * 9000 + "\n" + LINE % (26114, 26118, 3)), 2147483651)
        self.assertEqual((found["commit_used_mb"], found["commit_limit_mb"], found["commit_free_mb"]), (26114, 26118, 3))
        self.assertEqual(found["process_private_mb"], 16306)
        self.assertFalse(found["refused_commit"])

    def test_a_crash_with_memory_to_spare_is_not_called_out_of_memory(self):
        self.assertIsNone(memory_failure(self.log(LINE % (18000, 79293, 61293)), 3221225477))

    def test_a_clean_exit_or_a_missing_log_is_nothing(self):
        self.assertIsNone(memory_failure(self.log(LINE % (26114, 26118, 3)), 0))
        self.assertIsNone(memory_failure(Path("Z:/nao/existe/erros.log"), 3221225477))

    def test_message_names_virtual_memory_and_points_to_the_diagnostic(self):
        self.assertTrue(VIRTUAL_MEMORY_MESSAGE.startswith("Memoria virtual insuficiente"))
        self.assertIn("arquivo de paginacao", VIRTUAL_MEMORY_MESSAGE)
        self.assertIn("erros.log", VIRTUAL_MEMORY_MESSAGE)
        launch = (Path(__file__).resolve().parents[1] / "akynoleyend/launch.py").read_text(encoding="utf-8")
        self.assertIn('print("@@error " + likely + VIRTUAL_MEMORY_MESSAGE + figures', launch)


class LowMemoryNoticeTests(unittest.TestCase):
    """r6: the line said before the game starts when Windows is short of commit."""

    def test_notice_only_below_what_a_scene_needs(self):
        from akynoleyend.runtime_failure import COMMIT_NEEDED_MB, low_memory_notice
        self.assertIsNone(low_memory_notice(COMMIT_NEEDED_MB, 80000))
        self.assertIsNone(low_memory_notice(26202, 79293))            # (this PC, measured)
        text = low_memory_notice(10013, 21168)                         # (the tester's PC at a start, measured)
        self.assertIn("9.8 GB de memoria virtual livre", text)
        self.assertIn("limite 20.7 GB", text)
        self.assertIn("cerca de 19 GB", text)
        self.assertIn("arquivo de paginacao", text)
        self.assertNotIn("@@error", text)                              # (a notice: the game still starts)
        self.assertIn("Com menos de 11 GB livres a cena nao cabe", text)   # (r8: below what the scene really uses)
        self.assertNotIn("nao cabe", low_memory_notice(15000, 31000))      # (short, but it may fit)

    def test_windows_figures_are_read_or_absent(self):
        import os
        from akynoleyend.runtime_failure import system_commit_mb
        got = system_commit_mb()
        if os.name != "nt":
            self.assertIsNone(got)
            return
        free, limit = got
        self.assertGreater(limit, 1024)
        self.assertLessEqual(free, limit)

    def test_launcher_says_it_before_starting_the_game(self):
        from pathlib import Path
        source = (Path(__file__).resolve().parents[1] / "akynoleyend/launch.py").read_text(encoding="utf-8")
        self.assertLess(source.index("low_memory_notice(*commit)"), source.index("child = subprocess.Popen("))
        self.assertIn('metadata["commit_before"]', source)


if __name__ == "__main__":
    unittest.main()

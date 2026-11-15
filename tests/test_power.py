"""Check build power-request restoration and the Windows EcoQoS ABI."""

import ctypes
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import akynoleyend.power as power


class PowerTests(unittest.TestCase):
    def test_build_exception_restores_previous_execution_state(self):
        calls = []
        def setter(state):
            calls.append(state)
            return 0x80000002
        with self.assertRaisesRegex(RuntimeError, "interrupted"):
            with power.keep_awake(setter=setter):
                raise RuntimeError("interrupted")
        self.assertEqual(calls, [0x80000001, 0x80000002])

    def test_failed_power_request_does_not_change_restore_state(self):
        calls = []
        def setter(state):
            calls.append(state)
            return 0
        with power.keep_awake(setter=setter):
            pass
        self.assertEqual(calls, [0x80000001])

    def test_throttling_request_uses_only_the_supplied_child_handle(self):
        calls = []
        def setter(handle, kind, state, size):
            words = list(ctypes.cast(state, ctypes.POINTER(ctypes.c_uint32 * 3)).contents)
            calls.append((handle.value, kind, words, size))
            return 1
        current = lambda: self.fail("The explicit child handle should be used")
        kernel = SimpleNamespace(SetProcessInformation=setter, GetCurrentProcess=current)
        with patch.object(power, "os", SimpleNamespace(name="nt")), \
                patch.object(power.ctypes, "WinDLL", return_value=kernel, create=True):
            self.assertTrue(power.no_throttle(0x5678))
        self.assertEqual(calls, [(0x5678, 4, [1, 1, 0], 12)])


if __name__ == "__main__":
    unittest.main()

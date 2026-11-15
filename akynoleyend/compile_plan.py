"""How many compilers run at once, which unit starts first, and when there is memory for the next one (0.4.5).

Before 0.4.5 a fixed 3.5 GiB was set aside for every compiler process. On a 16 GB PC with 7 to 9 GiB free that made one
process (the r13c log: 6874 s, 115 minutes, at 1 of 6 threads). Measured on the Ryzen 5 3500X, a unit's peak varies with the
unit and not with how many run (see docs/analises-0.4.5.md), so a unit now starts when what it may take fits in what is free:
the sum of the peaks the running ones may still reach, and what Windows reports free right now (another program that takes
memory during the build holds the next one back). One unit always runs, so a build never stops for lack of memory.

The order: the units known to take longest first (the lift's chunk boundaries are saved, so the names are the same from one
build to the next), so the long ones do not end alone at the end. The first build takes the times from nx2/compile_hint.json
(measured at 6 MiB), later ones the times this PC measured (work/logs/compile-units.json).
"""

from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Callable

GIB = 1 << 30
MIB = 1 << 20

# Peak private memory of one clang, measured on the Ryzen 5 3500X (docs/analises-0.4.5.md): an ordinary 6 MiB chunk at -O1
# 0.28 to 0.32 GiB; the slow ones, with the game's biggest functions, 1.3 to 2.6 GiB (code_087 2.56); the hot pieces at -O2
# 0.48 to 1.82. The peak follows the time a unit takes, not its size, so the estimate comes from the known time, with a
# margin; a peak measured for the unit (compile_hint.json "peaks_gib") wins when it is higher.
FAST = 0.4 * GIB            # known under 30 s (measured 0.28 to 0.32 private, 0.37 working set)
MEDIUM = 1.2 * GIB          # 30 to 60 s
HEAVY = 2.0 * GIB           # 60 s or more
HOT = 2.1 * GIB             # a -O2 hot piece without a known time under 60 s
UNKNOWN_BASE = 0.4 * GIB    # no time known (another chunk size): by size, cautiously
UNKNOWN_PER_MIB = 0.25 * GIB
SMALL = 0.4 * GIB           # the runtime, Opus, the small generated files
CPP = 1.0 * GIB             # the renderer from source (vk_*.cpp, Eden's shader recompiler)
MARGIN = 1.15
# A unit estimated at this or more runs a minute or more (the estimates by time above); a lighter one ends in seconds.
LONG = 1.0 * GIB
# Left to Windows and the launcher while compiling.
RESERVE = 1.0 * GIB
MAX_SLOTS = 8


def unit_name(source: str) -> str:
    return os.path.basename(source)


def unit_peak(source: str, size: int, *, hot: bool, seconds: float | None = None, measured: float | None = None) -> int:
    """The memory one compiler may take for this unit, in bytes."""
    name = unit_name(source)
    game = hot or name.startswith("code_") or name == "a64_table.c"
    if not game:
        return int(CPP if name.endswith(".cpp") else SMALL)
    if seconds is None:
        estimate = HOT if hot or name.startswith("code_hot") else UNKNOWN_BASE + UNKNOWN_PER_MIB * size / MIB
    elif seconds >= 60:
        estimate = max(HEAVY, HOT) if hot or name.startswith("code_hot") else HEAVY
    elif seconds >= 30:
        estimate = MEDIUM
    else:
        estimate = FAST
    if measured:     # measured for this unit: that peak with the margin, over the estimate by time
        estimate = measured * MARGIN
    return int(estimate)


def typical_peak(chunk_mib: int) -> int:
    """An ordinary chunk: FAST at 6 MiB, more for the bigger chunks of big PCs."""
    return int(max(FAST, FAST * chunk_mib / 6))


def compile_slots(free_bytes: int, cpus: int, *, chunk_mib: int = 6) -> int:
    """Compilers at once: one a thread, at most MAX_SLOTS, and only as many typical units as fit in what is free.
    The gate holds back a heavy unit (the -O2 hot pieces) when it does not fit; the count only stops idle slots."""
    cores = max(1, cpus)
    if free_bytes <= 0:
        return 1
    memory = int(max(0, free_bytes - RESERVE) // typical_peak(chunk_mib))
    return max(1, min(cores, MAX_SLOTS, memory))


def load_peaks(path: Path) -> dict[str, float]:
    """Measured peak bytes per unit name (compile_hint.json "peaks_gib")."""
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    peaks = data.get("peaks_gib", {}) if isinstance(data, dict) else {}
    return {str(k): float(v) * GIB for k, v in peaks.items() if isinstance(v, (int, float)) and v > 0}


def load_times(*paths: Path) -> dict[str, float]:
    """Seconds per unit name: the later files win (this PC's own times over the shipped hint)."""
    times: dict[str, float] = {}
    for path in paths:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        units = data.get("units", data) if isinstance(data, dict) else {}
        for name, seconds in units.items():
            if isinstance(seconds, (int, float)) and seconds >= 0:
                times[str(name)] = float(seconds)
    return times


def order(sources: list[str], sizes: dict[str, int], times: dict[str, float]) -> list[str]:
    """Longest first: a unit with a known time by that time, the others by size (as before 0.4.5: biggest first). A known
    time is in seconds; a size is ranked as ~1.6 s per MiB, the median of the r13c log's ordinary chunks."""
    def expected(source: str) -> float:
        name = unit_name(source)
        if name in times:
            return times[name]
        return sizes[source] / MIB * 1.6
    return sorted(sources, key=lambda s: (-expected(s), -sizes[s], s))


def save_times(path: Path, measured: dict[str, float]) -> None:
    """Merge this build's seconds into the file (units this build took from the cache keep their old time)."""
    old = load_times(path)
    old.update({name: round(seconds, 1) for name, seconds in measured.items() if seconds > 0})
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps({"schema": 1, "units": dict(sorted(old.items()))}, indent=1), encoding="utf-8")
    os.replace(temporary, path)


class MemoryGate:
    """Hand the next unit to a free compiler slot: the earliest in the plan that fits in memory now.

    budget: what was usable when the compile started, less RESERVE. free(): what is usable now (None: the budget alone).
    A unit fits when nothing runs, or when the peaks of the running ones plus its own fit in the budget and the memory
    free now covers its peak plus RESERVE (another program that took memory). When the first waiting unit (the head, the
    longest left) does not fit, a later, lighter one may start in the meantime, but not into the room the head needs: it
    starts only if the head still fits beside it once the short units end (LONG). Otherwise light units refilling
    the memory as they end would hold a long unit back until every light one is done (the slot that picks a unit is free;
    before, each slot took its unit first and then waited for memory, and six heavy ones waiting left the light ones out)."""

    def __init__(self, budget: int, free: Callable[[], int] | None = None, *, poll: float = 2.0,
                 report: Callable[[str], None] | None = None):
        self.budget = max(0, int(budget))
        self.free = free
        self.poll = poll
        self.report = report
        self.claims: list[int] = []
        self.peak_running = 0
        self.waits = 0
        self.reported = None
        self.cond = threading.Condition()

    @property
    def claimed(self) -> int:
        return sum(self.claims)

    @property
    def running(self) -> int:
        return len(self.claims)

    def _free_now(self) -> int | None:
        if self.free is None:
            return None
        try:
            return self.free()
        except OSError:
            return None

    def _fits(self, need: int, now: int | None = -1) -> bool:
        if not self.claims:
            return True
        if self.claimed + need > self.budget:
            return False
        if now == -1:
            now = self._free_now()
        if now and now < need + RESERVE:
            return False
        return True

    def _may_pass(self, need: int, head: int) -> bool:
        """A later unit while the head waits: never into the room the head will have when the short ones end. Long ones
        are those estimated at LONG or more (a minute or more, by the times known); the others end in seconds."""
        long_running = sum(c for c in self.claims if c >= LONG)
        if long_running + head > self.budget:
            return True          # the head waits for a long one to end anyway: the short ones use the rest meanwhile
        return self.claimed + need + head <= self.budget

    def _claim(self, need: int) -> None:
        self.claims.append(need)
        self.peak_running = max(self.peak_running, len(self.claims))
        self.cond.notify_all()

    def take(self, pending: list, *, label=lambda item: "") -> tuple[int, object] | None:
        """pending: [(need, item)] in plan order, shared by the slots. Removes and returns the unit this slot runs, or
        None when nothing is left."""
        with self.cond:
            while pending:
                now = self._free_now()
                head = pending[0][0]
                if self._fits(head, now):
                    need, item = pending.pop(0)
                    self._claim(need)
                    return need, item
                for index in range(1, len(pending)):
                    need, item = pending[index]
                    if self._fits(need, now) and self._may_pass(need, head):
                        del pending[index]
                        self._claim(need)
                        return need, item
                if self.reported is not pending[0][1]:    # (once a head, whichever slot sees it first)
                    told = self.reported = pending[0][1]
                    self.waits += 1
                    if self.report:
                        self.report("  memoria: %s espera (%.1f GiB previstos, %d em andamento)" %
                                    (label(told) or "unidade", head / GIB, self.running))
                self.cond.wait(self.poll)
            return None

    def acquire(self, need: int, name: str = "") -> None:
        """One unit outside a plan (tests, a single file)."""
        pending = [(need, name)]
        self.take(pending)

    def release(self, need: int) -> None:
        with self.cond:
            self.claims.remove(need)
            self.cond.notify_all()


def usable_now() -> int:
    from .hardware import snapshot, usable_memory
    return usable_memory(snapshot())


def gate_from_environment(report=None) -> MemoryGate:
    """RX_MEMORY_GATE=0: no gate (the slots alone, as before 0.4.5)."""
    if os.environ.get("RX_MEMORY_GATE") == "0":
        return MemoryGate(1 << 62, None)
    start = usable_now()
    return MemoryGate(max(0, start - RESERVE), usable_now, report=report)

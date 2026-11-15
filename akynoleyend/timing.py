"""Record observed build phases, including the phase that fails."""
import time
from pathlib import Path
from .files import write_json


class BuildTimings:
    def __init__(self, work: Path, report=print):
        self.path = work / "build-timings.json"
        self.phases = []
        self.report = report

    def measure(self, name, operation, *args, **kwargs):
        started = time.monotonic()
        status = "failed"
        try:
            result = operation(*args, **kwargs)
            status = "completed"
            return result
        finally:
            seconds = round(time.monotonic() - started, 3)
            self.phases.append({"phase": name, "status": status, "seconds": seconds})
            try:
                write_json(self.path, {"schema": 1, "phases": self.phases})
            except OSError as error:
                self.report(f"Nao foi possivel gravar os tempos: {error}")
            self.report(f"Tempo observado de {name}: {seconds:.1f} s ({status}).")

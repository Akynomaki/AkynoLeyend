"""Translate native compile completion lines into measured GUI progress."""

import re
from dataclasses import dataclass

TOTAL = re.compile(r"^(\d+) files, ")
COMPLETED = re.compile(r"^\s+\S+\s+\d+ MB\s+\d+s\s+\(")


@dataclass
class CompileProgress:
    total: int = 0
    completed: int = 0

    def feed(self, line: str) -> float | None:
        total = TOTAL.match(line)
        if total:
            self.total = int(total.group(1))
            self.completed = 0
        elif self.total and COMPLETED.match(line):
            self.completed += 1
            return min(self.completed / self.total, 1.0)
        return None

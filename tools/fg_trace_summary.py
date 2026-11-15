"""Summary of a frame generation trace (0.4.5-test.1).

Start the game with RX_VK_FG_TRACE=<file.csv> and frame generation on: the display thread of gpu/vk/vk_framegen.cpp writes a
line per frame it shows (batch, k, shown, at_ms, ready_ms, due_ms, shown_ms, interval_ms, lag_ms, dynamic, target_fps,
refresh_hz). This prints, for the whole file or a time window:

- how many frames each game frame was shown as (the dynamic count's choices);
- the spacing of the frames on screen against the step the pacer aimed at (even within 25%, bunched under a third);
- frames that went out more than 2 ms after their place, and the delay from the game's hand-over to the screen.

  python tools/fg_trace_summary.py trace.csv [--from SECONDS] [--to SECONDS]

Times are those of the CPU's present calls: what a monitor shows can differ by the driver's queue.
"""

import argparse
import csv
import statistics
import sys
from collections import Counter


def read(path, start=None, end=None):
    rows = []
    with open(path, newline="", encoding="utf-8") as stream:
        for row in csv.DictReader(stream):
            try:
                item = {key: float(value) for key, value in row.items()}
            except (TypeError, ValueError):
                continue   # (a line cut by the game closing)
            seconds = item["shown_ms"] / 1000.0
            if start is not None and seconds < start:
                continue
            if end is not None and seconds > end:
                continue
            rows.append(item)
    return rows


def percentile(values, share):
    if not values:
        return 0.0
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, int(share * (len(ordered) - 1) + 0.5))]


def summary(rows):
    if len(rows) < 2:
        return ["Poucos quadros no registro (%d)." % len(rows)]
    lines = []
    batches = {}
    for row in rows:
        batches.setdefault(int(row["batch"]), row)
    counts = Counter(int(row["shown"]) for row in batches.values())
    seconds = (rows[-1]["shown_ms"] - rows[0]["shown_ms"]) / 1000.0
    lines.append("Quadros mostrados: %d em %.1f s (%.1f por segundo); quadros do jogo: %d (%.1f por segundo)." % (
        len(rows), seconds, len(rows) / max(seconds, 1e-9), len(batches), len(batches) / max(seconds, 1e-9)))
    lines.append("Multiplicador: " + ", ".join("%dx em %.0f%%" % (n, 100.0 * c / len(batches)) for n, c in sorted(counts.items())))
    dynamic = [row for row in batches.values() if row["dynamic"]]
    if dynamic:
        lines.append("Dinâmica: alvo %.0f FPS, monitor %d Hz." % (dynamic[-1]["target_fps"], int(dynamic[-1]["refresh_hz"])))
    gaps, even, bunched = [], 0, 0
    for before, row in zip(rows, rows[1:]):
        gap = row["shown_ms"] - before["shown_ms"]
        step = row["interval_ms"] / max(row["shown"], 1)
        gaps.append(gap)
        if abs(gap - step) <= 0.25 * step:
            even += 1
        if gap < step / 3:
            bunched += 1
    lines.append("Espaçamento na tela: mediana %.2f ms, 95%% até %.2f ms, 99%% até %.2f ms, desvio %.2f ms." % (
        percentile(gaps, 0.5), percentile(gaps, 0.95), percentile(gaps, 0.99), statistics.pstdev(gaps)))
    lines.append("Dentro de 25%% do passo: %.1f%%; colados (menos de um terço do passo): %d." % (100.0 * even / len(gaps), bunched))
    late = sum(1 for row in rows if row["shown_ms"] - row["due_ms"] > 2.0)
    delay = [row["shown_ms"] - row["at_ms"] for row in rows]
    ready = [row["ready_ms"] - row["at_ms"] for row in batches.values() if row["ready_ms"] >= 0]
    lines.append("Atrasados (mais de 2 ms depois do lugar): %d (%.1f%%)." % (late, 100.0 * late / len(rows)))
    lines.append("Da entrega do jogo até a tela: mediana %.1f ms, 95%% até %.1f ms." % (percentile(delay, 0.5), percentile(delay, 0.95)))
    if ready:
        lines.append("GPU pronta depois da entrega: mediana %.1f ms, 95%% até %.1f ms." % (percentile(ready, 0.5), percentile(ready, 0.95)))
    else:
        lines.append("GPU pronta: não medido (RX_VK_FG_READY=0 ou sem evento).")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("trace")
    parser.add_argument("--from", dest="start", type=float)
    parser.add_argument("--to", dest="end", type=float)
    args = parser.parse_args(argv)
    for line in summary(read(args.trace, args.start, args.end)):
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())

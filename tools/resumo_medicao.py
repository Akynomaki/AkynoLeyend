"""Resumo de uma execucao com a medicao de desempenho ligada (0.4.5-test.2: launcher > Teste de desempenho, ou
`manage.py run --measure`). Le a pasta da execucao em jogo/diagnosticos: erros.log e quadros.bin.

  python tools/resumo_medicao.py <pasta da execucao> [--depois <segundos>] [--json]

So leitura. --depois ignora o inicio (titulo, carregamento): os quadros e as linhas de 5 s antes desse tempo de jogo.
"""
from __future__ import annotations

import argparse
import json
import re
import statistics
import struct
import sys
from collections import defaultdict
from pathlib import Path


def frame_times(path: Path) -> list[float]:
    """quadros.bin: float32 ms por quadro do jogo, gravados de 32 em 32 (gpu/vk/vk_replay.cpp, AKYNO_FRAMETIMES)."""
    if not path.is_file():
        return []
    data = path.read_bytes()
    data = data[: len(data) // 4 * 4]
    return [v for (v,) in struct.iter_unpack("<f", data) if 0.0 < v < 60000.0]


def frame_summary(times: list[float], skip_s: float = 0.0) -> dict:
    if skip_s > 0:
        t, start = 0.0, 0
        for start, v in enumerate(times):
            t += v / 1000.0
            if t >= skip_s:
                break
        else:
            start = len(times)
        times = times[start:]
    if len(times) < 10:
        return {"frames": len(times)}
    ordered = sorted(times)
    worst = ordered[-max(1, len(ordered) // 100):]
    total_s = sum(times) / 1000.0
    return {
        "frames": len(times),
        "seconds": round(total_s, 1),
        "fps_mean": round(len(times) / total_s, 1),
        "fps_median": round(1000.0 / statistics.median(times), 1),
        "fps_1pct_low": round(1000.0 / statistics.mean(worst), 1),
        "ms_median": round(statistics.median(times), 2),
        "ms_p99": round(ordered[min(len(ordered) - 1, int(len(ordered) * 0.99))], 2),
        "over_50ms": sum(1 for v in times if v > 50.0),
        "over_100ms": sum(1 for v in times if v > 100.0),
        "over_250ms": sum(1 for v in times if v > 250.0),
    }


NUM = r"([\d.]+)"
PATTERNS = {
    "fps": re.compile(r"vk: \d+ presents, " + NUM + r" fps; a frame: " + NUM + r" draws .*?" + NUM + r" dispatches"),
    "gpu": re.compile(r"vk: GPU time " + NUM + r" ms a frame"),
    "replay": re.compile(r"vk: a frame's replay time \(ms\): (.*)$"),
    "submits": re.compile(r"nvn: submits in 5 s: (\d+) replayed on the submitting threads in " + NUM + r" ms, (\d+) of them with the core given up"),
    "waits": re.compile(r"nvn: GPU waits in 5 s: (\d+) sync waits \(" + NUM + r" ms\)"),
    "busiest": re.compile(r"prof: busiest threads \(% of a core\): (.*)$"),
    "escape": re.compile(r"vcores: (.+?) \(priority \d+\) ran without a core after " + NUM + r" ms:(.*)$"),
    "vcores": re.compile(r"vcores: (\d+) takes, (\d+) waits \(mean " + NUM + r" us, longest " + NUM + r" ms\), (\d+) kicks"),
    "mem": re.compile(r"mem: [^:]+: RAM (\d+) MB free of (\d+); system commit (\d+) MB used of (\d+) \((\d+) free\); "
                      r"this process (\d+) MB private"),
    "guest": re.compile(r"mem: guest window (\d+) MB committed"),
    "outside": re.compile(r"mem: private outside the guest window (\d+) MB"),
    "slow": re.compile(r"vk: slow frame at present \d+: " + NUM + r" ms"),
    # (0.4.5-test.4) "[thread]" after the count, and the "chain" lines; a line without a thread is the test.3 sampler's,
    # which sampled only the Presentation Thread
    "sample": re.compile(r"prof-sample (leaf|ours|chain) \((\d+) samples\)(?: \[([^\]]+)\])?: (.*)$"),
    "targets": re.compile(r"vk: target pool: (\d+) reused, (\d+) new, (\d+) retired"),
    "compaction": re.compile(r"vk: VRAM compaction: (\d+) blocks of"),
    # (0.4.5-test.5) HOS_SLEEP_LOG: the game's sleeps by caller every 5 s (host/hos_thread.c hos_sleep_logged)
    "sleep": re.compile(r"sleep: lr (0x[0-9a-f]+): (\d+) calls, asked " + NUM + r" ms, slept " + NUM + r" ms"),
}
SAMPLE_ENTRY = re.compile(r"(\S+?)\+([0-9a-f]+) (\d+)")
CHAIN_ENTRY = re.compile(r"(\S+?)\+([0-9a-f]+)((?:<\+[0-9a-f]+)*) (\d+)")
UNNAMED_THREAD = "Presentation Thread"


class Symbols:
    """Names for module+offset (the samples' keys: the instruction pointer less the module's base), from the module's own
    COFF symbol table through llvm-nm (the packaged LLVM). Unknown modules or no tools: the key as it is."""

    def __init__(self, folders):
        self.folders = [Path(f) for f in folders if f]
        self.tables = {}

    @staticmethod
    def tool(name):
        here = Path(__file__).resolve().parents[1] / "ferramentas" / "llvm" / "bin" / (name + ".exe")
        return here if here.is_file() else None

    def table(self, module):
        if module in self.tables:
            return self.tables[module]
        self.tables[module] = None
        nm, readobj = self.tool("llvm-nm"), self.tool("llvm-readobj")
        path = next((f / module for f in self.folders if (f / module).is_file()), None)
        if not (nm and readobj and path):
            return None
        import subprocess
        try:
            head = subprocess.run([str(readobj), "--file-headers", str(path)], capture_output=True, text=True, timeout=120).stdout
            base = int(re.search(r"ImageBase: (0x[0-9A-Fa-f]+)", head).group(1), 16)
            out = subprocess.run([str(nm), "--defined-only", "--numeric-sort", "-C", str(path)], capture_output=True,
                                 text=True, encoding="utf-8", errors="replace", timeout=600).stdout
        except (OSError, subprocess.SubprocessError, AttributeError):
            return None
        addrs, names = [], []
        for line in out.splitlines():
            parts = line.split(" ", 2)
            if len(parts) < 3 or parts[1].lower() not in ("t", "w") or parts[2].startswith("$"):
                continue
            try:
                addrs.append(int(parts[0], 16) - base)
            except ValueError:
                continue
            names.append(parts[2])
        self.tables[module] = (addrs, names)
        return self.tables[module]

    def name(self, module, offset):
        import bisect
        t = self.table(module)
        if not t or not t[0]:
            return f"{module}+{offset:x}"
        addrs, names = t
        i = bisect.bisect_right(addrs, offset) - 1
        return f"{module}!{names[i]}" if i >= 0 else f"{module}+{offset:x}"


def sample_summary(samples: dict, symbols: "Symbols | None", top: int = 25) -> dict:
    """The samples' places by function (leaf: where the thread was; ours: the first frame in our exe under it; chain: the
    first frames in our exe, leaf first, 0.4.5-test.4), for each sampled thread."""
    out = {}
    for thread, kinds in samples.items():
        out[thread] = {}
        for kind, places in kinds.items():
            places = dict(places)
            total = places.pop("__total__", 0)
            if not total:
                continue
            by = defaultdict(int)
            for (module, offsets), n in places.items():
                if symbols:
                    names = [symbols.name(module, o) for o in offsets]
                    key = " < ".join([names[0]] + [x.split("!", 1)[-1] for x in names[1:]])
                else:
                    key = f"{module}+{offsets[0]:x}" + "".join(f"<+{o:x}" for o in offsets[1:])
                by[key] += n
            ranked = sorted(by.items(), key=lambda kv: -kv[1])[:top if kind != "chain" else 15]
            out[thread][kind] = {"samples": total,
                                 "top": [(k, n, round(100.0 * n / total, 1) if total else None) for k, n in ranked]}
    return out


def mean(values):
    return round(statistics.mean(values), 2) if values else None


def log_summary(text: str, symbols: "Symbols | None" = None) -> dict:
    found = defaultdict(list)
    threads = defaultdict(list)
    replay = defaultdict(list)
    escapes = defaultdict(int)
    samples = defaultdict(lambda: {"leaf": defaultdict(int), "ours": defaultdict(int), "chain": defaultdict(int)})
    sleeps = defaultdict(lambda: [0, 0.0, 0.0])   # (lr: calls, asked ms, slept ms)
    for line in text.splitlines():
        for name, pattern in PATTERNS.items():
            m = pattern.search(line)
            if not m:
                continue
            if name == "sample":
                places = samples[m.group(3) or UNNAMED_THREAD][m.group(1)]
                places["__total__"] += int(m.group(2))
                if m.group(1) == "chain":
                    for module, first, rest, n in CHAIN_ENTRY.findall(m.group(4)):
                        offsets = (int(first, 16),) + tuple(int(o, 16) for o in re.findall(r"<\+([0-9a-f]+)", rest))
                        places[(module, offsets)] += int(n)
                else:
                    for module, offset, n in SAMPLE_ENTRY.findall(m.group(4)):
                        places[(module, (int(offset, 16),))] += int(n)
            elif name == "sleep":
                s = sleeps[int(m.group(1), 16)]
                s[0] += int(m.group(2))
                s[1] += float(m.group(3))
                s[2] += float(m.group(4))
            elif name == "busiest":
                for part in m.group(1).split(","):
                    part = part.strip()
                    k = part.rfind(" ")
                    if k > 0 and not part.startswith("all "):
                        try:
                            threads[part[:k].strip()].append(float(part[k + 1:]))
                        except ValueError:
                            pass
            elif name == "replay":
                for part in m.group(1).split(","):
                    k = part.strip().rfind(" ")
                    if k > 0:
                        try:
                            replay[part.strip()[:k]].append(float(part.strip()[k + 1:]))
                        except ValueError:
                            pass
            elif name == "escape":
                holders = re.findall(r"core \d+: ([^;(]+?) \(", m.group(3))
                escapes[m.group(1) + " <- " + "/".join(h.strip() for h in holders)] += 1
            else:
                found[name].append(tuple(float(g) for g in m.groups()))
            break
    out: dict = {}
    if found["fps"]:
        out["log_fps_mean"] = mean([f[0] for f in found["fps"]])
        out["draws_a_frame"] = mean([f[1] for f in found["fps"]])
        out["dispatches_a_frame"] = mean([f[2] for f in found["fps"]])
    if found["gpu"]:
        out["gpu_ms_a_frame"] = mean([g[0] for g in found["gpu"]])
    if replay:
        out["replay_ms_a_frame"] = {k: mean(v) for k, v in replay.items()}
    if found["submits"]:
        n = sum(s[0] for s in found["submits"])
        out["submit_replay_ms_per_s"] = round(sum(s[1] for s in found["submits"]) / (5.0 * len(found["submits"])), 1)
        out["submits_core_given_up_pct"] = round(100.0 * sum(s[2] for s in found["submits"]) / n, 1) if n else None
    if found["waits"]:
        out["main_gpu_wait_ms_per_s"] = round(sum(w[1] for w in found["waits"]) / (5.0 * len(found["waits"])), 1)
    if threads:
        top = sorted(threads.items(), key=lambda kv: -statistics.mean(kv[1]))[:12]
        out["threads_pct_of_a_core"] = {k: round(statistics.mean(v), 1) for k, v in top}
    if found["vcores"]:
        out["vcore_wait_longest_ms"] = max(v[3] for v in found["vcores"])
    out["vcore_escapes"] = dict(sorted(escapes.items(), key=lambda kv: -kv[1])[:10])
    if found["mem"]:
        out["ram_free_min_mb"] = int(min(m[0] for m in found["mem"]))
        out["commit_free_min_mb"] = int(min(m[4] for m in found["mem"]))
        out["process_private_max_mb"] = int(max(m[5] for m in found["mem"]))
    if found["guest"]:
        out["guest_committed_max_mb"] = int(max(g[0] for g in found["guest"]))
    if found["outside"]:
        out["outside_private_max_mb"] = int(max(o[0] for o in found["outside"]))
    out["slow_frames_logged"] = len(found["slow"])
    if found["targets"]:   # (counters since the start: the last line)
        last = found["targets"][-1]
        out["targets"] = {"reused": int(last[0]), "new": int(last[1]), "retired": int(last[2])}
    out["vram_compactions"] = len(found["compaction"])
    out["vram_blocks_emptied"] = int(sum(c[0] for c in found["compaction"]))
    if samples:
        out["samples"] = sample_summary(samples, symbols)
    if sleeps:   # (most time asleep first)
        out["sleeps"] = [{"lr": lr, "calls": c, "asked_ms": round(a, 2), "slept_ms": round(s, 2)}
                         for lr, (c, a, s) in sorted(sleeps.items(), key=lambda kv: -kv[1][2])[:12]]
    return out


def summarize(folder: Path, skip_s: float = 0.0, symbols: bool = True) -> dict:
    log = folder / "erros.log"
    text = log.read_text(encoding="utf-8", errors="replace") if log.is_file() else ""
    result = {"folder": str(folder)}
    game = None
    try:
        run = json.loads((folder / "execucao.json").read_text(encoding="utf-8"))
        result["experiment"] = run.get("experiment", "nenhum")
        result["measure"] = run.get("measure", False)
        result["graphics"] = run.get("graphics")
        game = Path(run["command"][0]).parent
    except (OSError, ValueError, KeyError, IndexError, TypeError):
        pass
    if game is None and (folder.parent.parent / "AkynoLeyend.exe").is_file():   # (jogo/diagnosticos/<run>)
        game = folder.parent.parent
    result["frames"] = frame_summary(frame_times(folder / "quadros.bin"), skip_s)
    result.update(log_summary(text, Symbols([game]) if symbols else None))
    return result


def report(r: dict) -> str:
    f = r.get("frames", {})
    lines = [f"Execucao: {r['folder']}", f"Experimento: {r.get('experiment', '?')}"]
    if f.get("fps_median"):
        lines.append(f"Quadros: {f['frames']} em {f['seconds']} s; mediana {f['fps_median']} FPS ({f['ms_median']} ms), "
                     f"pior 1% {f['fps_1pct_low']} FPS; acima de 50 ms {f['over_50ms']}, de 100 ms {f['over_100ms']}, "
                     f"de 250 ms {f['over_250ms']}")
    else:
        lines.append("Quadros: sem quadros.bin (a medicao estava ligada?)")
    for key, label in (("draws_a_frame", "Desenhos por quadro"), ("dispatches_a_frame", "Despachos por quadro"),
                       ("gpu_ms_a_frame", "GPU por quadro (ms)"), ("submit_replay_ms_per_s", "Gravacao dos envios (ms por s)"),
                       ("submits_core_given_up_pct", "Envios com o nucleo solto (%)"),
                       ("main_gpu_wait_ms_per_s", "Espera do jogo pela GPU (ms por s)"),
                       ("vcore_wait_longest_ms", "Maior espera por nucleo virtual (ms)"),
                       ("process_private_max_mb", "Memoria privada do processo, maximo (MB)"),
                       ("guest_committed_max_mb", "Janela do jogo reservada, maximo (MB)"),
                       ("outside_private_max_mb", "Privada fora da janela do jogo, maximo (MB)"),
                       ("ram_free_min_mb", "RAM livre, minimo (MB)"), ("commit_free_min_mb", "Commit livre, minimo (MB)"),
                       ("slow_frames_logged", "Quadros lentos registrados")):
        if r.get(key) is not None:
            lines.append(f"{label}: {r[key]}")
    if r.get("replay_ms_a_frame"):
        lines.append("Gravacao por quadro (ms): " + ", ".join(f"{k} {v}" for k, v in r["replay_ms_a_frame"].items()))
    if r.get("threads_pct_of_a_core"):
        lines.append("Threads mais ocupadas (% de um nucleo): " +
                     ", ".join(f"{k} {v}" for k, v in r["threads_pct_of_a_core"].items()))
    if r.get("vcore_escapes"):
        lines.append("Esperas de 250 ms por nucleo virtual: " + "; ".join(f"{k}: {v}" for k, v in r["vcore_escapes"].items()))
    if r.get("targets"):
        g = r["targets"]
        lines.append(f"Alvos de render: {g['reused']} reaproveitados, {g['new']} novos ({g['retired']} descartados do grupo)")
    if r.get("vram_compactions") is not None:
        lines.append(f"Limpezas da VRAM: {r['vram_compactions']} ({r.get('vram_blocks_emptied', 0)} blocos de 64 MB esvaziados)")
    if r.get("sleeps"):
        lines.append("Sonos do jogo por chamador (pedido / dormido, por chamada):")
        for s in r["sleeps"]:
            each_a = s["asked_ms"] * 1000 / s["calls"] if s["calls"] else 0
            each_s = s["slept_ms"] * 1000 / s["calls"] if s["calls"] else 0
            lines.append(f"  lr {s['lr']:#x}: {s['calls']} chamadas, {s['asked_ms']:.0f} ms pedidos / {s['slept_ms']:.0f} ms "
                         f"dormidos ({each_a:.0f} / {each_s:.0f} us)")
    for thread, kinds in r.get("samples", {}).items():
        for kind, label in (("leaf", "onde estava"), ("ours", "primeira funcao do jogo/host abaixo"),
                            ("chain", "funcoes do exe, a de cima chamada pela seguinte")):
            s = kinds.get(kind)
            if s:
                lines.append(f"Amostras de {thread} ({label}), {s['samples']} no total:")
                lines.extend(f"  {pct:5}%  {n:6}  {name}" for name, n, pct in s["top"])
    return "\n".join(lines)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("folder", type=Path)
    parser.add_argument("--depois", type=float, default=0.0, help="ignora os primeiros segundos de quadros")
    parser.add_argument("--json", action="store_true")
    parser.add_argument("--sem-simbolos", action="store_true", help="amostras como modulo+deslocamento, sem llvm-nm")
    args = parser.parse_args(argv)
    # (0.4.5-test.4) the threads' names are Japanese too: a console or a file in cp1252 stopped the report
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if not args.folder.is_dir():
        print(f"Pasta nao encontrada: {args.folder}", file=sys.stderr)
        return 2
    result = summarize(args.folder, args.depois, symbols=not args.sem_simbolos)
    print(json.dumps(result, ensure_ascii=False, indent=2) if args.json else report(result))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

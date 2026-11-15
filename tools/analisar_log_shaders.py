"""Resumo conservador de logs do renderizador AkynoLeyend/Hookshot.

Nao toca em caches, nao extrai caminhos locais e nao reinterpreta SPIR-V
como binarios GPU independentes do driver. Python 3.10+ sem dependencias.
"""
from __future__ import annotations

import argparse
import collections
import json
from pathlib import Path
import re

PREPARED = re.compile(
    r"vk: prepared (\d+) shader programs \((\d+) new, (\d+) failed, (\d+) stage libraries"
    r"(?:;[^)]*)?\) in ([\d.]+) s"
)
PIPELINES = re.compile(
    r"vk: precompile: (\d+) programs, (?:(\d+) graphics notes, )?(\d+) graphics and"
    r" (\d+) compute pipelines(?: built)? in ([\d.]+) ms"
)
PROGRAM_CACHE = re.compile(r"vk: program cache .*?: (\d+) program keys kept, (\d+) KB")
PIPE_CACHE = re.compile(r"vk: pipeline cache .*?\((\d+) KB\)")
FAILED_OPCODE = re.compile(r"vk: NVN2 program [0-9a-f]+ \(stage (\d+)\) does not lower .*?: (.+?) \(native op (0x[0-9a-f]+),")
PRESENT = re.compile(r"vk: (\d+) presents, ([\d.]+) fps; a frame: (\d+) draws \((\d+) skipped\)")
NOT_READY = re.compile(r"vk: a frame: ([\d.]+) draws left out \(not ready\), ([\d.]+) waits for shaders or pipelines \(([\d.]+) ms\)")
GPU = re.compile(r"vk: GPU time ([\d.]+) ms a frame")
CACHE_HITS = re.compile(r"vk: (\d+) programs from the program cache")
# (0.4.8) the start's preload: how many noted graphics pipelines it left for the background, and what that part built
PRELOAD_LEFT = re.compile(r"vk: precompile: .*; (\d+) of the graphics notes go on in the background")
PRELOAD_DONE = re.compile(
    r"vk: preload: the background part is done: (\d+) graphics pipelines built in all, (\d+) handed to play, (\d+) met in"
    r" play first; ([\d.]+) s after the start"
)

def analyze(path: Path) -> dict:
    results: dict = {
        "log_lines": 0, "renderer": None, "gpu": None,
        "program_cache_initial": None, "driver_pipeline_cache_kib": None,
        "shader_preparation": None, "pipeline_precompile": None, "preload_background": None,
        "cache_programs_reused_reported_max": None,
        "failed_lowerings_visible": 0, "failed_lowerings_by_cause": {},
        "sampled_fps_last": None, "sampled_fps_max": None,
        "last_sampled_draws": None, "last_sampled_skipped": None,
        "not_ready_draws_peak_sample": None, "shader_wait_ms_peak_sample": None,
        "gpu_time_ms_last_sample": None, "device_lost_reported": False,
    }
    reasons = collections.Counter()
    with path.open("r", encoding="utf-8", errors="replace") as stream:
        for line in stream:
            results["log_lines"] += 1
            if "[hos host] hookshot v" in line:
                results["renderer"] = line.split("hookshot v", 1)[1].strip().split(" ", 1)[0]
            if "vk: NVIDIA " in line or "vk: AMD Radeon " in line:
                if "Vulkan" in line:
                    # Only the model, not paths or driver-specific host information.
                    results["gpu"] = line.split("vk: ", 1)[-1].split(", Vulkan", 1)[0]
            if "GPU_FATAL" in line or "VK_ERROR_DEVICE_LOST" in line or "device_lost" in line:
                results["device_lost_reported"] = True
            if m := PREPARED.search(line):
                results["shader_preparation"] = dict(programs=int(m[1]), new_translations=int(m[2]), failed=int(m[3]), stage_libraries=int(m[4]), seconds=float(m[5]))
            if m := PIPELINES.search(line):
                results["pipeline_precompile"] = dict(programs=int(m[1]), graphics_notes=int(m[2] or 0), graphics_built=int(m[3]), compute_built=int(m[4]), milliseconds=float(m[5]))
            if m := PROGRAM_CACHE.search(line):
                results["program_cache_initial"] = dict(keys=int(m[1]), kib=int(m[2]))
            if m := PIPE_CACHE.search(line):
                results["driver_pipeline_cache_kib"] = int(m[1])
            if m := FAILED_OPCODE.search(line):
                results["failed_lowerings_visible"] += 1
                reasons[f"stage={m[1]}; {m[2].strip()}; opcode={m[3]}"] += 1
            if m := PRELOAD_LEFT.search(line):
                results["preload_background"] = dict(left_for_play=int(m[1]), done=False)
            if m := PRELOAD_DONE.search(line):
                results["preload_background"] = dict(
                    (results["preload_background"] or {}), done=True, graphics_built=int(m[1]), handed=int(m[2]),
                    met_first=int(m[3]), seconds=float(m[4]))
            if m := CACHE_HITS.search(line):
                results["cache_programs_reused_reported_max"] = max(
                    int(m[1]), results["cache_programs_reused_reported_max"] or 0)
            if m := PRESENT.search(line):
                results["sampled_fps_last"] = float(m[2])
                results["sampled_fps_max"] = max(float(m[2]), results["sampled_fps_max"] or 0)
                results["last_sampled_draws"] = int(m[3])
                results["last_sampled_skipped"] = int(m[4])
            if m := NOT_READY.search(line):
                results["not_ready_draws_peak_sample"] = max(float(m[1]), results["not_ready_draws_peak_sample"] or 0)
                results["shader_wait_ms_peak_sample"] = max(float(m[3]), results["shader_wait_ms_peak_sample"] or 0)
            if m := GPU.search(line):
                results["gpu_time_ms_last_sample"] = float(m[1])
    results["failed_lowerings_by_cause"] = dict(reasons.most_common(20))
    results["interpretation"] = (
        "Caches de SPIR-V e VkPipelineCache podem poupar trabalho, mas nao garantem "
        "compilacao zero em jogo, ausencia de travamentos ou compatibilidade entre GPUs/drivers. "
        "Tempos de preparacao e pipelines sao etapas diferentes; nao some contadores de programas "
        "como se representassem shaders unicos. Amostras de FPS nao sao benchmark pareado. "
        "Mensagens de lowering sao diagnosticos, nao prova de que os shaders causaram falha grafica."
    )
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Resumo seguro de cache, preparacao e erros Vulkan")
    parser.add_argument("log", type=Path, help="Log local da execucao")
    parser.add_argument("--json-out", type=Path, help="Salvar relatorio JSON sem paths do usuario")
    ns = parser.parse_args(argv)
    report = analyze(ns.log)
    pretty = json.dumps(report, ensure_ascii=False, indent=2)
    print(pretty)
    if ns.json_out:
        ns.json_out.parent.mkdir(parents=True, exist_ok=True)
        ns.json_out.write_text(pretty + "\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

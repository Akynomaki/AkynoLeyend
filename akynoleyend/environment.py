"""Explicit runtime profiles; inherited experiments never become defaults."""

from collections.abc import Mapping

from .errors import ProjectError

RUNTIME_PREFIXES = ("TOTK_", "DKB_", "RX_", "HOS_", "EDEN_", "A64_", "OOT_", "AKYNO_")
PROFILES: dict[str, dict[str, str]] = {
    "original": {},
    "8gb": {
        "RX_VK_VRAM_MB": "2048",  # Texture-cache budget, not total GPU memory.
        "RX_VK_MIRROR_MB": "1024",  # Keep mirrors, with a smaller independent budget.
        "RX_VK_TEX_MAX_DIM": "1024",  # Mip selection for eligible large textures.
        "RX_VK_TEX_MAX_MB": "256",  # Size threshold for one texture, not a cache.
        "RX_VK_IMPORT_CHUNK_MB": "8",  # Power of two: the engine uses bit-mask alignment.
    },
    "nitido": {
        # The backend's existing spatial replacement; no temporal-history clamp.
        # Compare motion against Original: less history, but more jagged edges.
        "RX_VK_TAAU_KEYS": "fd029a317a9a4b94",
        "HOS_DYNRES": "0",  # The menu's 100% resolution option.
    },
}
PROFILES["compatibilidade"] = {
    "RX_VK_VRAM_MB": "4096",
    "RX_VK_MIRROR_MB": "512",
    "RX_VK_COMPILE_THREADS": "2",
}
# Opt-in A/B of Hookshot #1629. Only the mirror copy size changes.
PROFILES["4k-wb-experimental"] = {"RX_VK_WB_MAX_KB": "1024"}
PROFILES["desempenho-1600"] = {"RX_VK_ANISO": "4"}
PROFILES["rtx-1600"] = {
    "RX_VK_VRAM_MB": "3584",
    "RX_VK_MIRROR_MB": "1536",
}

# Safe, explicit A/B controls; never trust inherited RX_/AKYNO_ environment variables.
# These are applied by launch() after inherited variables are sanitized.
VISUAL_MODES: dict[str, dict[str, str]] = {
    "patched": {
        # (r13h) the game's own occlusion queries on: the renderer counts samples passed with Vulkan occlusion queries
        # (gpu/vk/vk_occlusion.cpp), so the game culls what is hidden. Off, every candidate was drawn: scenery floating
        # with nothing under it, and draws the frame did not need. "sem-oclusao" keeps the six sites off, as before.
        "AKYNO_OCCLUSION_OFF": "0",
        "RX_VK_BARE_READ_MB": "130",  # only read-only bare-pointer ranges
        "RX_VK_KEEP_FINALIZED_MB": "256",  # GPU-written small terrain maps, bounded LRU
        "RX_VK_EVICT_MIN_UNUSED": "60",
    },
    "sem-oclusao": {
        "AKYNO_OCCLUSION_OFF": "1",  # six guard-checked game occlusion sites (r13g and before)
        "RX_VK_BARE_READ_MB": "130",
        "RX_VK_KEEP_FINALIZED_MB": "256",
        "RX_VK_EVICT_MIN_UNUSED": "60",
    },
    "comparison": {
        "AKYNO_OCCLUSION_OFF": "0",
        "RX_VK_BARE_READ_MB": "1",
        "RX_VK_KEEP_FINALIZED_MB": "0",
        "RX_VK_EVICT_MIN_UNUSED": "8",
        "RX_VK_NO_GRID_PATCH": "1",
    },
}

CACHE_MODES = {
    "original": {},
    "streaming": {
        "RX_VK_CACHE_STREAM": "1",
        "RX_VK_CACHE_READ_MB": "16",
        "RX_VK_CACHE_QUEUE": "8",
        "RX_VK_CACHE_INDEX_RECORDS": "65536",
        "RX_VK_CACHE_READ_MBPS": "64",
        # (0.4.8) the start's preload (gpu/vk/vk_draw.cpp precompile_run): the programs and pipelines play met, read and built at
        # every start. The start waits for the compute ones and at most 20 s of the graphics ones (RX_VK_PRELOAD_WAIT_MS); the
        # rest are built in the background while the game plays. Was 64 MiB, 128 programs and 256 notes: the Teste-1 built 11 of
        # its 3,759 noted graphics pipelines before play
        "RX_VK_PREWARM_MB": "256",
        "RX_VK_PREWARM_PROGRAMS": "2048",
        "RX_VK_PREWARM_PIPELINES": "4096",
        "RX_VK_COMPILE_THREADS": "2",
        "RX_VK_PREWARM_PER_SECOND": "5",
        "RX_VK_PIPE_CACHE_IO_MB": "128",
    },
}
CACHE_MODES["equilibrado"] = dict(
    CACHE_MODES["streaming"],
    RX_VK_CACHE_READ_MB="32",
    RX_VK_CACHE_READ_MBPS="128",
    RX_VK_PREWARM_MB="512",   # (0.4.8: was 96 MiB, 192 programs, 384 notes)
    RX_VK_PREWARM_PROGRAMS="4096",
    RX_VK_PREWARM_PIPELINES="8192",
    RX_VK_COMPILE_THREADS="4",
    RX_VK_PREWARM_PER_SECOND="10",
)
CACHE_MODES["preparacao"] = dict(
    CACHE_MODES["streaming"], RX_VK_SEED_PREPARE="1", RX_VK_PREPARE_ONLY="1"
)
# (0.4.5-test.2) Performance measurement: what each frame's time goes to, written to the run's diagnostics folder. Every
# 5 s the busiest threads (HOS_PROFILE), the replay's phases per draw (RX_VK_PROF_ALL), and every 30 s where the memory is
# committed (HOS_MEM_MAP). The frame times go to quadros.bin in the run's folder (launch.py); tools/resumo_medicao.py reads
# it all back. On top of any profile.
MEASURE = {
    "HOS_PROFILE": "5",
    "HOS_MEM_MAP": "1",
    "RX_VK_PROF_ALL": "1",
}
# A/B experiments, one at a time and with the measurement on: the same route, two minutes each.
EXPERIMENTS: dict[str, dict[str, str]] = {
    "nenhum": {},
    # (0.4.5-test.3) where the recording thread's time goes: its instruction pointer every millisecond, the most frequent
    # places every 5 s ("prof-sample" lines; tools/resumo_medicao.py names them from the exe's and the DLL's symbols).
    # (0.4.5-test.4) the game's main thread too, and the chain of calls in the exe: who waits, and for what
    "amostrar": {"HOS_SAMPLE": "Presentation Thread|sead::MainThread"},
    # 0.4.5-test.2's behaviour: the submitting thread gives its virtual core up while the host records its submit
    "nucleo-solto": {"HOS_SUBMIT_FREE_CORE": "1"},
    # (0.4.5-test.3) every image in one pool, as before test.3 (gpu/vk/vk_vma.cpp: targets and textures apart)
    "pool-unico": {"RX_VK_IMAGE_POOLS": "1"},
    # the replay's draws recorded on 3 threads (gpu/vk/vk_replay.cpp, off by default)
    "gravacao-paralela": {"RX_VK_PARALLEL": "3"},
    # (0.4.5-test.4) render targets not kept for reuse under VRAM pressure, as before test.4 (gpu/vk/vk_texture.cpp)
    "alvos-como-antes": {"RX_VK_TARGET_POOL_PRESSED_MB": "0"},
    # (0.4.5-test.5) the main thread's waits: the test.4 samples had it ~23% asleep in f_800998a0 (it hands jobs to the
    # BaseProcExecutor threads and sleeps until they are done) and ~35% in WaitLightEvent. The game's sleeps by caller (asked
    # against slept, HOS_SLEEP_LOG) and the samples of two of those workers: late wakes, or workers that run late?
    "esperas": {"HOS_SAMPLE": "sead::MainThread|BaseProcExecutor0|BaseProcExecutor1", "HOS_SLEEP_LOG": "1"},
}
# (0.4.5-test.6) test.5 found the main thread's 20 us sleeps lasting ~537 us (the timer, host/hos_thread.c with six logical
# processors or fewer); now that thread yields instead and the rest keep the timer. Its two comparisons, with esperas' samples
# and sleep log: the main thread on the timer too (test.5's behaviour), and every thread yielding (r13i's switch).
EXPERIMENTS["esperas-como-antes"] = dict(EXPERIMENTS["esperas"], HOS_SHORT_SLEEP_MAIN_TIMER="1")
EXPERIMENTS["esperas-todas-cedem"] = dict(EXPERIMENTS["esperas"], HOS_SHORT_SLEEP_TIMER="0")
# (0.4.5-test.7) the main thread's short sleeps spin on the clock with a pause instead of SwitchToThread, and a thread
# waiting for a virtual core spins 150 us before it sleeps (host/hos_thread.c). Its comparisons: neither (test.6's default),
# and every sleep under a millisecond spinning. test.6's two modes keep their meaning: neither spin in them.
NO_SPIN = {"HOS_SHORT_SLEEP_SPIN": "0", "HOS_VCORE_SPIN_US": "0"}
EXPERIMENTS["esperas-como-antes"].update(NO_SPIN)
EXPERIMENTS["esperas-todas-cedem"].update(NO_SPIN)
EXPERIMENTS["esperas-como-test6"] = dict(EXPERIMENTS["esperas"], **NO_SPIN)
EXPERIMENTS["esperas-todas-giram"] = dict(EXPERIMENTS["esperas"], HOS_SHORT_SLEEP_SPIN="all")
# (0.4.5-test.8) every short sleep spins by default (test.7's esperas-todas-giram, which now is the default with the sleep
# log), and test.7's default for comparison (only the main thread spins). (0.4.6) test.8's highest priority for the
# recording thread measured no gain and is gone; the launcher no longer offers these measurements (manage.py run --measure
# --experiment still does).
EXPERIMENTS["esperas-como-test7"] = dict(EXPERIMENTS["esperas"], HOS_SHORT_SLEEP_SPIN="main")
TEXTURE_MODES = {
    "auto": {},
    "rgba8": {"RX_VK_ASTC_RGBA8": "1"},
    "cpu-rgba8": {"RX_VK_ASTC_RGBA8": "1", "RX_VK_ASTC_CPU": "1"},
}


def clean_environment(parent: Mapping[str, str]) -> dict[str, str]:
    return {
        key: value
        for key, value in parent.items()
        if not key.upper().startswith(RUNTIME_PREFIXES)
        and key.upper() not in ("VK_INSTANCE_LAYERS", "VK_LOADER_DEBUG")
    }


def runtime_environment(
    parent: Mapping[str, str],
    profile: str,
    diagnostic: bool = False,
    *,
    cache_mode: str = "original",
    texture_mode: str = "auto",
    measure: bool = False,
    experiment: str = "nenhum",
) -> dict[str, str]:
    try:
        selected = PROFILES[profile]
    except KeyError as error:
        raise ProjectError(f"Perfil desconhecido: {profile}") from error
    if experiment not in EXPERIMENTS:
        raise ProjectError(f"Experimento desconhecido: {experiment}")
    if experiment != "nenhum" and not measure:
        raise ProjectError("Um experimento de desempenho precisa da medicao ligada (--measure).")
    try:
        cache_settings = CACHE_MODES[cache_mode]
    except KeyError as error:
        raise ProjectError(f"Modo de cache desconhecido: {cache_mode}") from error
    try:
        texture_settings = TEXTURE_MODES[texture_mode]
    except KeyError as error:
        raise ProjectError(f"Modo de texturas desconhecido: {texture_mode}") from error
    result = clean_environment(parent)
    result.update(selected)
    result.update(cache_settings)
    if profile == "rtx-1600" and cache_mode == "equilibrado":
        result["RX_VK_PREWARM_PER_SECOND"] = "100"
    result.update(texture_settings)
    if measure:
        result.update(MEASURE)
        result.update(EXPERIMENTS[experiment])
    result["RX_BACKEND"] = "vulkan"
    if diagnostic:
        result["RX_VK_VALIDATION"] = "1"
    return result

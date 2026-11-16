"""Validated runtime controls; experimental supersampling is not a game Max Resolution mod."""

from pathlib import Path

from .errors import ProjectError

# Menu indices match the rebuilt native runtime. The host applies 125/150
# through HOS_RES_SCALE; the menu identifies them as experimental scales.
RESOLUTIONS = {"auto": 0, "100": 1, "75": 2, "67": 3, "50": 4, "125": 5, "150": 6, "native-1440": 1, "native-4k": 1}
EXPERIMENTAL_SCALES = {"125": "1.25", "150": "1.5"}


def executable_has_literal(executable: Path, literal: str) -> bool:
    needle = literal.encode("ascii") + b"\x00"
    overlap = b""
    with executable.open("rb") as source:
        while block := source.read(1024 * 1024):
            if needle in overlap + block:
                return True
            overlap = block[-(len(needle) - 1) :]
    return False


def has_fixed_scale_hook(executable: Path) -> bool:
    """Check that the actual host EXE can read HOS_RES_SCALE."""
    return executable_has_literal(executable, "HOS_RES_SCALE")


SPEEDS = {"realtime": "1", "per-frame": "0"}
# (the temporal modes keep FSR 1 at the presentation, for the window's own size, and as the fallback: when a temporal
# upscaler cannot run, the game's own upscale draws and FSR 1 scales it)
FILTERS = {"off": "0", "catmull-rom": "1", "lanczos": "2", "fsr": "3", "fsr-temporal": "3", "fsr-native-aa": "3",
           "dlss": "3", "dlaa": "3", "fsr4": "3", "fsr4-native-aa": "3"}
# temporal upscalers: the engine and whether the render size is the output's (native anti-aliasing)
TEMPORAL = {"fsr-temporal": ("fsr", False), "fsr-native-aa": ("fsr", True),
            "dlss": ("dlss", False), "dlaa": ("dlss", True),
            "fsr4": ("fsr4", False), "fsr4-native-aa": ("fsr4", True)}
OUTPUTS = {"game": "0", "1440p": "1", "4k": "2", "1080p": "3", "720p": "4", "1600p": "5"}
EXTENDED_OUTPUT_FEATURE = "native-output-720-1600-v1"


def saved_temporal_options(folder: Path, resolution: str | None) -> tuple[str | None, str | None]:
    """Read a temporal choice made in F1 when the launcher uses saved options."""
    try:
        with (folder / "AkynoLeyend_opts.ini").open("rb") as source:
            raw = source.read((64 << 10) + 1)
    except OSError:
        return None, resolution
    if len(raw) > 64 << 10:
        return None, resolution
    options = dict(line.split("=", 1) for line in raw.decode("utf-8-sig", "replace").splitlines() if "=" in line)
    mode = options.get("upscaler")
    if mode not in TEMPORAL:
        return None, resolution
    if resolution is not None:
        if resolution in ("50", "67", "75", "100"):
            engine, _ = TEMPORAL[mode]
            native_aa = resolution == "100"
            match = next(key for key, value in TEMPORAL.items() if value == (engine, native_aa))
            return match, resolution
        # A fixed/dynamic choice outside the temporal range uses the game's scaler.
        return "lanczos", resolution
    if TEMPORAL[mode][1]:
        return mode, "100"
    for scale in ("50", "67", "75"):
        if options.get("resolution") == str(RESOLUTIONS[scale]):
            return mode, scale
    return mode, "50"


def graphics_environment(
    *,
    backend="vulkan",
    resolution=None,
    output_resolution=None,
    speed=None,
    upscaling=None,
    sharpness=None,
    framegen=None,
    pacing=None,
    fps_counter=None,
    handheld=None,
    lite_scene=None,
):
    if backend != "vulkan":
        raise ProjectError(
            "OpenGL ainda nao executa os shaders task/mesh desta base. Escolha Vulkan; nenhum backend sera trocado silenciosamente."
        )
    result = {}
    for value, choices, name, key in [
        (resolution, RESOLUTIONS, "resolucao", "AKYNO_RESOLUTION"),
        (speed, SPEEDS, "velocidade", "HOS_REALTIME_STEP"),
        (upscaling, FILTERS, "filtro", "RX_VK_UPSCALE"),
    ]:
        if value is not None:
            if value not in choices:
                raise ProjectError(f"Opcao de {name} invalida: {value}")
            result[key] = str(choices[value])
    if upscaling is not None:
        result["AKYNO_UPSCALER"] = upscaling
    if upscaling in TEMPORAL:
        engine, native = TEMPORAL[upscaling]
        if native and resolution not in (None, "100"):
            raise ProjectError("DLAA e FSR Native AA usam a resolucao interna de 100%; escolha 100 ou deixe a resolucao vazia.")
        if resolution == "auto" or resolution in EXPERIMENTAL_SCALES or resolution in ("native-1440", "native-4k"):
            raise ProjectError("FSR temporal e DLSS usam escala fixa de 50, 67 ou 75%; DLAA e Native AA usam 100%.")
        if not native and resolution == "100":
            raise ProjectError("Com 100% use DLAA ou FSR Native AA; DLSS e FSR temporal ampliam de uma resolucao menor.")
        if resolution is None:
            result["AKYNO_RESOLUTION"] = str(RESOLUTIONS["100" if native else "50"])
            result["HOS_DYNRES"] = "0"
        if engine in ("fsr", "fsr4"):
            result["AKYNO_FSR_TEMPORAL"] = "1"
        if engine != "fsr":
            result["AKYNO_TEMPORAL_ENGINE"] = engine
    if resolution is not None:
        result["HOS_DYNRES"] = "1" if resolution == "auto" else "0"
        # Experimental fixed scale, not the emulator's ARM64 Max Resolution patch.
        # Actual host selection must also be checked in the execution log.
        if resolution in EXPERIMENTAL_SCALES:
            result["HOS_RES_SCALE"] = EXPERIMENTAL_SCALES[resolution]
        if resolution in ("native-1440", "native-4k"):
            result["HOS_OUTPUT_RES"] = "2" if resolution == "native-4k" else "1"
            result["HOS_RES_SCALE"] = "1.0"
    if output_resolution is not None:
        if output_resolution not in OUTPUTS:
            raise ProjectError(f"Opcao de saida invalida: {output_resolution}")
        if resolution in ("native-1440", "native-4k"):
            expected = "1440p" if resolution == "native-1440" else "4k"
            if output_resolution != expected:
                raise ProjectError("Saida e preset nativo pedem resolucoes diferentes.")
        result["HOS_OUTPUT_RES"] = OUTPUTS[output_resolution]
    if result.get("HOS_OUTPUT_RES") in ("1", "2", "5") and handheld is None:
        handheld = False
    if sharpness is not None:
        if type(sharpness) is not int or not 0 <= sharpness <= 100:
            raise ProjectError("Nitidez deve estar entre 0 e 100.")
        result["AKYNO_SHARPNESS"] = str(sharpness)
    if framegen is not None:
        # 9: Dinamica (0.4.5-test.1, gpu/vk/fg_dynamic.h): the count follows the display, up to the F1 panel's maximum
        if type(framegen) is not int or framegen not in (0, 2, 3, 4, 5, 6, 7, 8, 9):
            raise ProjectError("Geracao de quadros deve ser 0, de 2 a 8, ou 9 (dinamica).")
        result["AKYNO_FRAMEGEN"] = str(framegen)
    if pacing is not None:
        if type(pacing) is not bool:
            raise ProjectError("Ritmo de quadros deve ser ligado ou desligado.")
        result["RX_VK_PACE"] = "1" if pacing else "0"
    for value, key, label in [(fps_counter, "AKYNO_FPS_COUNTER", "Contador de FPS"),
                              (handheld, "HOS_HANDHELD", "Perfil portatil")]:
        if value is not None:
            if type(value) is not bool:
                raise ProjectError(label + " deve ser ligado ou desligado.")
            result[key] = "1" if value else "0"
    # (0.4.9, gpu/vk/lite_scene.h) Only when on: off leaves the variable out, and the renderer draws everything as before.
    # The renderer reads it once at the start, so a change applies when the game is opened again.
    if lite_scene is not None:
        if type(lite_scene) is not bool:
            raise ProjectError("Vegetacao decorativa deve ser ligada ou desligada.")
        if lite_scene:
            result["AKYNO_LITE_SCENE"] = "1"
    return result

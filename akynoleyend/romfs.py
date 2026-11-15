"""Cheap root-layout checks; these do not certify every game file or its version."""
from pathlib import Path
import stat
from .errors import ProjectError

PROBES = (
    "System/HeapSize/Product.Nin_Ounce_NVN2.HeapDef.byml.zs",
    "System/HeapSize/Default.Nin_Ounce_NVN2.HeapDef.byml.zs",
    "System/RegionLangMask.txt",
    "System/GameRomConfig/Product.game__RomConfig.bgyml",
    "System/AddressTable/All.dev.Nin_Ounce_NVN2.atbl.byml.zs",
)


def directory_state(path: Path) -> tuple[str, str]:
    """Do not let is_dir() turn an access error into an apparent missing folder."""
    try:
        mode = path.stat().st_mode
    except FileNotFoundError:
        return "missing", ""
    except OSError as error:
        return "inaccessible", str(error)
    return ("present", "") if stat.S_ISDIR(mode) else ("not_directory", "nao e uma pasta")


def require_romfs(root: Path) -> None:
    states = {name: directory_state(root / name) for name in ("System", "Pack")}
    blocked = [(name, detail) for name, (state, detail) in states.items() if state == "inaccessible"]
    if blocked:
        detail = "; ".join(f"{name}: {error}" for name, error in blocked)
        raise ProjectError(f"RomFS inacessivel em {root}. Nao foi possivel verificar as pastas: {detail}. "
                           "Acesso negado nao comprova que os arquivos estejam ausentes. Confira o acesso nesta conta.")
    missing = [name for name, (state, _) in states.items() if state != "present"]
    if not missing:
        return
    hint = ""
    for nested in (root / "romfs", root / "romfs" / "romfs"):
        if all(directory_state(nested / name)[0] == "present" for name in ("System", "Pack")):
            hint = f" A raiz parece estar em: {nested}."
            break
    raise ProjectError(
        f"RomFS sem a estrutura esperada em {root}: faltam pastas {', '.join(missing)}. "
        "Selecione a pasta que contem System e Pack, ou confira/repare a extracao."
        + hint
    )


def audit_romfs(root: Path) -> list[str]:
    lines = [f"RomFS: {root}"]
    for name in ("System", "Pack"):
        state, detail = directory_state(root / name)
        label = {"present": "presente", "missing": "AUSENTE", "inaccessible": "INACESSIVEL",
                 "not_directory": "NAO E PASTA"}[state]
        lines.append(f"Pasta {name}: {label}" + (f" ({detail})" if detail else ""))
    for name in PROBES:
        path = root / name
        try:
            with path.open("rb") as stream:
                data = stream.read(16)
            result = "legivel" if data else "VAZIO"
        except OSError as error:
            result = f"nao foi possivel ler: {error}"
        lines.append(f"{name}: {result}")
    lines.append("Sondagem de caminhos; nem todos os arquivos consultados sao obrigatorios em todos os dumps.")
    return lines

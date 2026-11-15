"""The signed Windows Vulkan pair for the optional AMD FSR SDK mode."""

from pathlib import Path

from .config import ROOT
from .errors import ProjectError
from .files import read_json, sha256

HOST_FEATURE = "fsr-temporal-jitter-v1"
SDK_DLLS = ("amd_fidelityfx_loader_vk.dll", "amd_fidelityfx_upscaler_vk.dll")


def sdk_directory(root: Path = ROOT) -> Path:
    vendor = root / "third_party" / "amd-fsr-sdk"
    directory = vendor / "signedbin"
    receipt = read_json(vendor / "sdk.json")
    hashes = receipt.get("dlls") if isinstance(receipt, dict) else None
    if not isinstance(hashes, dict) or set(hashes) != set(SDK_DLLS):
        raise ProjectError("Manifesto das DLLs Vulkan do AMD FSR SDK 2.4 incompleto.")
    for name in SDK_DLLS:
        path = directory / name
        if not path.is_file() or sha256(path) != hashes[name]:
            raise ProjectError(
                f"AMD FSR temporal precisa da DLL oficial {name} do SDK 2.4 em {directory}."
            )
    return directory.resolve()


def jitter_emitted(work: Path) -> bool:
    path = work / "sa" / "gen" / "fsr-jitter.txt"
    return path.is_file() and path.read_text(encoding="ascii").strip() == HOST_FEATURE

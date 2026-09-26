from __future__ import annotations

from dataclasses import asdict, dataclass
import os
import platform
import re
import shutil
import subprocess


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    cpu: str
    ram_gb: float
    gpu: str
    vram_gb: float
    cuda: bool
    ffmpeg: bool
    tier: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def _ram_gb() -> float:
    try:
        if os.name == "nt":
            out = subprocess.check_output(
                ["powershell", "-NoProfile", "-Command",
                 "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory"],
                text=True, timeout=4,
            )
            return round(int(out.strip()) / 1024**3, 1)
        pages = os.sysconf("SC_PHYS_PAGES")
        size = os.sysconf("SC_PAGE_SIZE")
        return round((pages * size) / 1024**3, 1)
    except Exception:
        return 0.0


def _nvidia() -> tuple[str, float, bool]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return "", 0.0, False
    try:
        out = subprocess.check_output(
            [exe, "--query-gpu=name,memory.total", "--format=csv,noheader,nounits"],
            text=True, timeout=5,
        ).splitlines()[0]
        name, memory = [part.strip() for part in out.rsplit(",", 1)]
        return name, round(float(memory) / 1024, 1), True
    except Exception:
        return "", 0.0, False


def _tier(vram_gb: float, cuda: bool) -> str:
    if not cuda or vram_gb < 4:
        return "DIRECT"
    if vram_gb < 6:
        return "ECO"
    if vram_gb < 12:
        return "HYBRID"
    if vram_gb < 24:
        return "LOCAL_AI"
    return "MAX"


def detect_hardware() -> HardwareProfile:
    gpu, vram, cuda = _nvidia()
    return HardwareProfile(
        cpu=platform.processor() or platform.machine() or "unknown",
        ram_gb=_ram_gb(),
        gpu=gpu or "CPU / non-NVIDIA",
        vram_gb=vram,
        cuda=cuda,
        ffmpeg=bool(shutil.which("ffmpeg")),
        tier=_tier(vram, cuda),
    )

from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any
from urllib import error as urlerror
from urllib import request as urlrequest

from .instruction_image import InstructionScene
from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState
from .subprocess_policy import hidden_window_kwargs


class AIVideoMode(StrEnum):
    LOCAL = "local"
    HYBRID = "hybrid"
    ONLINE = "online"


class AIVideoEngine(StrEnum):
    COMFYUI = "comfyui"
    COGVIDEOX = "cogvideox-2b"
    FRAMEPACK = "framepack"
    LTX = "ltx-video"
    WAN = "wan"
    MOTION_GRAPHICS = "motion-graphics"


@dataclass(frozen=True, slots=True)
class HardwareProfile:
    system: str
    cpu: str
    ram_gb: float
    gpu_name: str
    vram_gb: float
    cuda_available: bool
    free_disk_gb: float

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True, slots=True)
class EngineAssessment:
    engine: str
    installed: bool
    suitable: bool
    reason: str
    recommended_mode: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


_ENGINE_REQUIREMENTS: dict[AIVideoEngine, tuple[float, float, str]] = {
    AIVideoEngine.COGVIDEOX: (8.0, 16.0, "CogVideoX 2B local video generation"),
    AIVideoEngine.FRAMEPACK: (6.0, 16.0, "FramePack image-to-video"),
    AIVideoEngine.LTX: (16.0, 16.0, "LTX local video generation"),
    AIVideoEngine.WAN: (16.0, 24.0, "Wan local video generation"),
}


def _bytes_to_gb(value: int | float) -> float:
    return round(float(value) / (1024 ** 3), 2)


def _physical_ram_gb() -> float:
    try:
        if os.name == "nt":
            out = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "(Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
                check=False,
                **hidden_window_kwargs(),
            ).stdout.strip()
            return _bytes_to_gb(int(out)) if out.isdigit() else 0.0
        pages = os.sysconf("SC_PHYS_PAGES")
        page_size = os.sysconf("SC_PAGE_SIZE")
        return _bytes_to_gb(int(pages) * int(page_size))
    except Exception:
        return 0.0


def _cpu_name() -> str:
    if os.name == "nt":
        try:
            out = subprocess.run(
                [
                    "powershell.exe",
                    "-NoLogo",
                    "-NoProfile",
                    "-NonInteractive",
                    "-Command",
                    "(Get-CimInstance Win32_Processor | Select-Object -First 1 -ExpandProperty Name)",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                timeout=10,
                check=False,
                **hidden_window_kwargs(),
            ).stdout.strip()
            if out:
                return out
        except Exception:
            pass
    return platform.processor() or platform.machine() or "unknown"


def _nvidia_profile() -> tuple[str, float, bool]:
    exe = shutil.which("nvidia-smi")
    if not exe:
        return "", 0.0, False
    try:
        out = subprocess.run(
            [
                exe,
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
            **hidden_window_kwargs(),
        ).stdout.strip()
        first = out.splitlines()[0] if out else ""
        if not first:
            return "", 0.0, False
        name, memory = [part.strip() for part in first.rsplit(",", 1)]
        return name, round(float(memory) / 1024.0, 2), True
    except Exception:
        return "", 0.0, False


def _windows_gpu_fallback() -> tuple[str, float]:
    if os.name != "nt":
        return "", 0.0
    try:
        script = (
            "$g=Get-CimInstance Win32_VideoController | "
            "Sort-Object AdapterRAM -Descending | Select-Object -First 1; "
            "[Console]::OutputEncoding=[Text.Encoding]::UTF8; "
            "Write-Output ($g.Name + '|' + [string]$g.AdapterRAM)"
        )
        out = subprocess.run(
            ["powershell.exe", "-NoLogo", "-NoProfile", "-NonInteractive", "-Command", script],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=10,
            check=False,
            **hidden_window_kwargs(),
        ).stdout.strip()
        if "|" not in out:
            return out, 0.0
        name, raw = out.rsplit("|", 1)
        try:
            return name.strip(), _bytes_to_gb(int(raw.strip()))
        except ValueError:
            return name.strip(), 0.0
    except Exception:
        return "", 0.0


def detect_hardware(path: str | os.PathLike[str]) -> HardwareProfile:
    target = Path(path).expanduser()
    if not target.exists():
        target = Path.home()
    free = shutil.disk_usage(target).free
    gpu_name, vram, cuda = _nvidia_profile()
    if not gpu_name:
        gpu_name, vram = _windows_gpu_fallback()
    return HardwareProfile(
        system=platform.system(),
        cpu=_cpu_name(),
        ram_gb=_physical_ram_gb(),
        gpu_name=gpu_name or "unknown / integrated",
        vram_gb=vram,
        cuda_available=cuda,
        free_disk_gb=_bytes_to_gb(free),
    )


def scene_to_prompt(scene: InstructionScene, *, product_name: str = "", model: str = "") -> str:
    product = "the product"
    if product_name or model:
        product = " ".join(part for part in (product_name.strip(), model.strip()) if part)
    cue = scene.visual_cue.strip()
    return (
        f"Professional commercial product advertisement scene for {product}. "
        f"Visual action: {cue}. "
        "Clean realistic composition, natural human proportions when people are present, "
        "commercial lighting, no visible brand logos unless supplied by the seller, "
        "no text baked into the generated image, vertical 9:16 framing, product remains the focus."
    )


class AIVideoRouter:
    """Hardware-aware routing layer for local, hybrid, and online AI-video engines."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        state: ProjectState,
        root: str | os.PathLike[str],
        settings: Any,
    ):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.settings = settings

    def hardware(self) -> HardwareProfile:
        preferred = self.settings.get("ai_model_root", default="")
        location = Path(preferred).expanduser() if preferred else self.root
        profile = detect_hardware(location)
        self.state.set_meta("ai_video.hardware", profile.to_dict())
        return profile

    def _root(self, key: str) -> Path | None:
        raw = self.settings.get(key, default="").strip()
        if not raw:
            return None
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = self.root / path
        return path if path.exists() else None

    def comfyui_status(self) -> dict[str, Any]:
        base = self.settings.get("comfyui_url", default="http://127.0.0.1:8188").rstrip("/")
        try:
            with urlrequest.urlopen(base + "/system_stats", timeout=2.5) as response:
                payload = json.loads(response.read().decode("utf-8", errors="replace"))
            return {"ready": True, "url": base, "details": payload}
        except Exception as exc:
            return {"ready": False, "url": base, "error": f"{type(exc).__name__}: {exc}"}

    def assessments(self) -> tuple[EngineAssessment, ...]:
        hw = self.hardware()
        configured = {
            AIVideoEngine.COMFYUI: self.comfyui_status()["ready"],
            AIVideoEngine.COGVIDEOX: bool(self._root("cogvideox_root")),
            AIVideoEngine.FRAMEPACK: bool(self._root("framepack_root")),
            AIVideoEngine.LTX: bool(self._root("ltx_root")),
            AIVideoEngine.WAN: bool(self._root("wan_root")),
            AIVideoEngine.MOTION_GRAPHICS: True,
        }
        items: list[EngineAssessment] = []
        for engine in (
            AIVideoEngine.COGVIDEOX,
            AIVideoEngine.FRAMEPACK,
            AIVideoEngine.LTX,
            AIVideoEngine.WAN,
        ):
            min_vram, min_ram, label = _ENGINE_REQUIREMENTS[engine]
            if not hw.cuda_available:
                suitable = False
                reason = f"{label}: local generation needs a supported NVIDIA/CUDA GPU."
            elif hw.vram_gb < min_vram:
                suitable = False
                reason = f"{label}: detected {hw.vram_gb:.1f} GB VRAM; target is about {min_vram:.0f}+ GB."
            elif hw.ram_gb and hw.ram_gb < min_ram:
                suitable = False
                reason = f"{label}: detected {hw.ram_gb:.1f} GB RAM; target is about {min_ram:.0f}+ GB."
            else:
                suitable = True
                reason = f"{label}: hardware check passed."
            items.append(
                EngineAssessment(
                    engine=engine.value,
                    installed=configured[engine],
                    suitable=suitable,
                    reason=reason,
                    recommended_mode=AIVideoMode.LOCAL.value if suitable else AIVideoMode.HYBRID.value,
                )
            )

        comfy = configured[AIVideoEngine.COMFYUI]
        items.insert(
            0,
            EngineAssessment(
                engine=AIVideoEngine.COMFYUI.value,
                installed=comfy,
                suitable=comfy,
                reason="ComfyUI API is reachable." if comfy else "ComfyUI API is not running/configured.",
                recommended_mode=AIVideoMode.LOCAL.value if comfy else AIVideoMode.HYBRID.value,
            ),
        )
        items.append(
            EngineAssessment(
                engine=AIVideoEngine.MOTION_GRAPHICS.value,
                installed=True,
                suitable=True,
                reason="Built-in deterministic fallback; works without a generative GPU.",
                recommended_mode=AIVideoMode.LOCAL.value,
            )
        )
        return tuple(items)

    def choose_engine(self, requested_mode: AIVideoMode | str = AIVideoMode.HYBRID) -> EngineAssessment:
        mode = AIVideoMode(requested_mode)
        assessments = self.assessments()
        preference = [
            AIVideoEngine.COMFYUI.value,
            AIVideoEngine.COGVIDEOX.value,
            AIVideoEngine.FRAMEPACK.value,
            AIVideoEngine.LTX.value,
            AIVideoEngine.WAN.value,
            AIVideoEngine.MOTION_GRAPHICS.value,
        ]
        if mode is AIVideoMode.ONLINE:
            return EngineAssessment(
                engine="online-provider",
                installed=False,
                suitable=True,
                reason="Online mode selected; local scene generation is bypassed.",
                recommended_mode=AIVideoMode.ONLINE.value,
            )
        by_name = {item.engine: item for item in assessments}
        for name in preference:
            item = by_name[name]
            if item.installed and item.suitable:
                return item
        return by_name[AIVideoEngine.MOTION_GRAPHICS.value]

    def queue_comfyui_workflow(self, workflow: dict[str, Any]) -> dict[str, Any]:
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        status = self.comfyui_status()
        if not status.get("ready"):
            raise RuntimeError("ComfyUI is not available")
        url = str(status["url"]).rstrip("/") + "/prompt"
        payload = json.dumps({"prompt": workflow}).encode("utf-8")
        req = urlrequest.Request(url, data=payload, headers={"Content-Type": "application/json"}, method="POST")
        try:
            with urlrequest.urlopen(req, timeout=20) as response:
                result = json.loads(response.read().decode("utf-8", errors="replace"))
        except urlerror.URLError as exc:
            raise RuntimeError(f"ComfyUI request failed: {exc}") from exc
        self.state.record_event(
            "ai_video.comfyui.queued",
            {"prompt_id": result.get("prompt_id"), "node_count": len(workflow)},
            agent="AI Video Router",
        )
        return result

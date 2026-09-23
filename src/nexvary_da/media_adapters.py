from __future__ import annotations

import importlib.util
import json
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from urllib.request import Request, urlopen

from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .state import ProjectState


@dataclass(frozen=True, slots=True)
class MediaStatus:
    available: bool
    details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class VoiceStudioAdapter:
    """External VoiceStudio local-API adapter.

    NEXVARY does not vendor VoiceStudio and never sends files unless an explicit
    API request supplies them.
    """

    def __init__(self, guard: WorkspaceGuard, state: ProjectState, root: str | os.PathLike[str]):
        self.guard = guard
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.base_url = os.environ.get(
            "NEXVARY_DA_VOICESTUDIO_URL", "http://127.0.0.1:3900"
        ).rstrip("/")

    @staticmethod
    def _validate_base(base_url: str) -> None:
        parsed = urlparse(base_url)
        if parsed.scheme not in {"http", "https"} or not parsed.hostname:
            raise ValueError("VoiceStudio base URL must be absolute HTTP(S)")
        if parsed.scheme == "http" and parsed.hostname.lower() not in {
            "localhost",
            "127.0.0.1",
            "::1",
        }:
            raise ValueError("Non-loopback VoiceStudio endpoints must use HTTPS")

    def status(self) -> MediaStatus:
        try:
            self._validate_base(self.base_url)
        except ValueError as exc:
            return MediaStatus(False, {"base_url": self.base_url, "error": str(exc)})
        return MediaStatus(True, {"base_url": self.base_url, "network_probe": False})

    def request_json(
        self,
        path: str,
        *,
        method: str = "GET",
        payload: dict[str, Any] | None = None,
        timeout: float = 10,
    ) -> dict[str, Any]:
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        self._validate_base(self.base_url)
        if not path.startswith("/") or path.startswith("//"):
            raise ValueError("VoiceStudio API path must begin with one slash")
        url = urljoin(self.base_url + "/", path.lstrip("/"))
        body = None if payload is None else json.dumps(payload).encode("utf-8")
        request = Request(
            url,
            data=body,
            method=method.upper(),
            headers={"Content-Type": "application/json"} if body is not None else {},
        )
        with urlopen(request, timeout=timeout) as response:
            raw = response.read(2_000_000).decode("utf-8", errors="replace")
            content_type = response.headers.get("Content-Type", "")
            status_code = int(response.status)
        result: Any
        if "json" in content_type.lower() or raw.lstrip().startswith(("{", "[")):
            try:
                result = json.loads(raw)
            except json.JSONDecodeError:
                result = raw
        else:
            result = raw
        self.state.record_event(
            "voicestudio.request",
            {"method": method.upper(), "path": path, "response_chars": len(raw)},
            agent="VoiceStudio",
        )
        return {"status": status_code, "result": result}

    def health(self, *, timeout: float = 5) -> dict[str, Any]:
        return self.request_json("/system/info", timeout=timeout)


_QWEN_HELPER = r"""
import os
import torch
from diffusers import QwenImage21Pipeline

model = os.environ["NEXVARY_QWEN_MODEL"]
prompt = os.environ["NEXVARY_QWEN_PROMPT"]
output = os.environ["NEXVARY_QWEN_OUTPUT"]
device = os.environ.get("NEXVARY_QWEN_DEVICE", "cuda")
local_only = os.environ.get("NEXVARY_QWEN_LOCAL_ONLY", "0") == "1"
pipe = QwenImage21Pipeline.from_pretrained(
    model,
    torch_dtype=torch.bfloat16,
    local_files_only=local_only,
).to(device)
image = pipe(prompt=prompt, num_inference_steps=40).images[0]
image.save(output)
print(output)
"""


class QwenImageAdapter:
    """Optional Qwen-Image 2.1 launcher.

    The upstream model license is research/non-commercial by default. NEXVARY
    does not bundle weights and reports the license boundary in status.
    """

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def status(self) -> MediaStatus:
        modules = {
            "torch": importlib.util.find_spec("torch") is not None,
            "diffusers": importlib.util.find_spec("diffusers") is not None,
        }
        return MediaStatus(
            all(modules.values()),
            {
                "modules": modules,
                "model": "Qwen/Qwen-Image-2.1",
                "license": "Qwen Research License; non-commercial unless separately licensed",
                "weights_bundled": False,
            },
        )

    def generate(
        self,
        prompt: str,
        output: str,
        *,
        model: str = "Qwen/Qwen-Image-2.1",
        device: str = "cuda",
        local_files_only: bool = False,
        timeout: float = 1800,
    ) -> dict[str, Any]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        if not local_files_only:
            self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        if not prompt.strip():
            raise ValueError("Image prompt cannot be empty")
        candidate = Path(output)
        if not candidate.is_absolute():
            candidate = self.root / candidate
        safe = self.guard.require(candidate, Permission.WRITE, must_exist=False)
        safe.parent.mkdir(parents=True, exist_ok=True)
        result = self.runner.run(
            [sys.executable, "-c", _QWEN_HELPER],
            cwd=self.root,
            timeout=timeout,
            env={
                "NEXVARY_QWEN_MODEL": model,
                "NEXVARY_QWEN_PROMPT": prompt,
                "NEXVARY_QWEN_OUTPUT": str(safe),
                "NEXVARY_QWEN_DEVICE": device,
                "NEXVARY_QWEN_LOCAL_ONLY": "1" if local_files_only else "0",
            },
        )
        self.state.record_event(
            "qwen_image.generate",
            {
                "returncode": result.returncode,
                "prompt_chars": len(prompt),
                "output": str(safe.relative_to(self.root)),
                "local_files_only": local_files_only,
            },
            agent="Qwen Image",
        )
        return {
            "returncode": result.returncode,
            "output": str(safe.relative_to(self.root)),
            "log": result.stdout[-4000:],
            "duration_seconds": result.duration_seconds,
        }


class MoneyPrinterTurboAdapter:
    """Run an existing MoneyPrinterTurbo checkout inside the approved workspace."""

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.state = state
        self.root = Path(root).resolve(strict=True)

    def _project_root(self) -> Path | None:
        raw = os.environ.get("NEXVARY_DA_MONEYPRINTER_ROOT", "").strip()
        if not raw:
            return None
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            safe = self.guard.require(candidate, Permission.READ, must_exist=True)
        except Exception:
            return None
        return safe if (safe / "cli.py").is_file() else None

    def status(self) -> MediaStatus:
        base = self._project_root()
        return MediaStatus(
            base is not None,
            {
                "root": str(base) if base else None,
                "uv": shutil.which("uv"),
                "cli": str(base / "cli.py") if base else None,
                "vendored": False,
            },
        )

    def generate(self, subject: str, *, timeout: float = 3600) -> dict[str, Any]:
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        if not subject.strip():
            raise ValueError("Video subject cannot be empty")
        base = self._project_root()
        if base is None:
            raise RuntimeError(
                "MoneyPrinterTurbo checkout is not configured inside the approved workspace"
            )
        uv = shutil.which("uv")
        if uv:
            args = [uv, "run", "python", "cli.py", "--video-subject", subject]
        else:
            venv = base / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
            python = str(venv) if venv.is_file() else sys.executable
            args = [python, "cli.py", "--video-subject", subject]
        result = self.runner.run(args, cwd=base, timeout=timeout)
        self.state.record_event(
            "moneyprinter.generate",
            {"returncode": result.returncode, "subject_chars": len(subject)},
            agent="MoneyPrinterTurbo",
        )
        return {
            "returncode": result.returncode,
            "output": result.stdout[-8000:],
            "duration_seconds": result.duration_seconds,
        }

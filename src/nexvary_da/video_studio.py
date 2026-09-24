from __future__ import annotations

import os
import shutil
import sys
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .integration_settings import IntegrationSettings
from .permissions import Permission, WorkspaceGuard
from .process import ProcessRunner
from .process_registry import ProcessRegistry
from .state import ProjectState


class VideoEngineId(StrEnum):
    MONEYPRINTER = "moneyprinter"
    AUTOMATED_VIDEO = "automated-video-generator"
    SHORTS_GENERATOR = "shorts-generator"


@dataclass(frozen=True, slots=True)
class VideoEngineSpec:
    engine: VideoEngineId
    name: str
    repository: str
    reviewed_commit: str
    license: str
    root_setting: str
    web_url: str
    api_url: str
    description: str
    free_mode: str


@dataclass(frozen=True, slots=True)
class VideoEngineStatus:
    engine: str
    name: str
    ready: bool
    installed: bool
    root: str | None
    web_url: str
    api_url: str
    missing: tuple[str, ...]
    description: str
    free_mode: str
    license: str
    reviewed_commit: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


SPECS: tuple[VideoEngineSpec, ...] = (
    VideoEngineSpec(
        VideoEngineId.MONEYPRINTER,
        "MoneyPrinterTurbo",
        "https://github.com/harry0703/MoneyPrinterTurbo.git",
        "f2d44d62721aeaecb1898488a3bc06399da2168d",
        "MIT",
        "moneyprinter_root",
        "http://127.0.0.1:8501",
        "http://127.0.0.1:8080",
        "Mature short-video pipeline: script, footage, TTS, subtitles, music and render.",
        "Use Ollama/local script generation plus free/no-key Edge TTS; stock footage may require a free provider key.",
    ),
    VideoEngineSpec(
        VideoEngineId.AUTOMATED_VIDEO,
        "Automated Video Generator",
        "https://github.com/itsPremkumar/Automated-Video-Generator.git",
        "68db464f03761ec7a2def2d722931dd636280ddb",
        "MIT",
        "automated_video_root",
        "http://127.0.0.1:3001",
        "http://127.0.0.1:3001",
        "Free self-hosted script-to-video pipeline with local portal, voiceover, captions and stock media.",
        "Keyless Openverse/CC media is available; Pexels is optional. Edge TTS/local Voicebox can be used.",
    ),
    VideoEngineSpec(
        VideoEngineId.SHORTS_GENERATOR,
        "ShortsGenerator",
        "https://github.com/leamsigc/ShortsGenerator.git",
        "7b83166f728dc92b426b64242546a5ab77c81149",
        "MIT",
        "shorts_generator_root",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:8080",
        "Local Shorts workflow with stock search, local TTS options, subtitle templates and multiple aspect ratios.",
        "Local Supertonic/KittenTTS are available; Pexels key and ImageMagick are normally required.",
    ),
)


class VideoStudioManager:
    """Prepare and launch reviewed external video engines inside the approved workspace.

    Repositories are cloned at reviewed commits. Setup never stores provider API keys.
    """

    def __init__(
        self,
        guard: WorkspaceGuard,
        runner: ProcessRunner,
        processes: ProcessRegistry,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.runner = runner
        self.processes = processes
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.settings = IntegrationSettings(guard, self.root)

    @staticmethod
    def specs() -> tuple[VideoEngineSpec, ...]:
        return SPECS

    def spec(self, engine: VideoEngineId | str) -> VideoEngineSpec:
        target = VideoEngineId(engine)
        return next(item for item in SPECS if item.engine == target)

    def _configured_root(self, spec: VideoEngineSpec) -> Path | None:
        raw = self.settings.get(spec.root_setting, "", "")
        if not raw:
            return None
        candidate = Path(raw).expanduser()
        if not candidate.is_absolute():
            candidate = self.root / candidate
        try:
            safe = self.guard.require(candidate, Permission.READ, must_exist=True)
        except Exception:
            return None
        return safe

    def _default_root(self, spec: VideoEngineSpec) -> Path:
        return self.root / ".nexvary-da" / "video-engines" / spec.engine.value

    def _engine_markers(self, spec: VideoEngineSpec) -> tuple[str, ...]:
        if spec.engine is VideoEngineId.MONEYPRINTER:
            return ("cli.py", "pyproject.toml")
        if spec.engine is VideoEngineId.AUTOMATED_VIDEO:
            return ("package.json",)
        return ("Backend/main.py", "UI/package.json")

    def _root_is_installed(self, spec: VideoEngineSpec, root: Path | None) -> bool:
        return bool(root and all((root / marker).is_file() for marker in self._engine_markers(spec)))

    def status(self, engine: VideoEngineId | str) -> VideoEngineStatus:
        spec = self.spec(engine)
        root = self._configured_root(spec)
        installed = self._root_is_installed(spec, root)
        missing: list[str] = []
        if not installed:
            missing.append("engine files")
        if shutil.which("git") is None:
            missing.append("Git")

        if spec.engine is VideoEngineId.MONEYPRINTER:
            if shutil.which("uv") is None and not (root and self._venv_python(root).is_file()):
                missing.append("uv or prepared Python venv")
        elif spec.engine is VideoEngineId.AUTOMATED_VIDEO:
            if shutil.which("node") is None:
                missing.append("Node.js 18+")
            if shutil.which("npm") is None:
                missing.append("npm")
        else:
            if shutil.which("node") is None or shutil.which("npm") is None:
                missing.append("Node.js/npm")
            if shutil.which("magick") is None and shutil.which("convert") is None:
                missing.append("ImageMagick")

        runtime_blockers = {
            VideoEngineId.MONEYPRINTER: {"uv or prepared Python venv"},
            VideoEngineId.AUTOMATED_VIDEO: {"Node.js 18+", "npm"},
            VideoEngineId.SHORTS_GENERATOR: {"Node.js/npm", "ImageMagick", "prepared Python venv"},
        }[spec.engine]
        if spec.engine is VideoEngineId.SHORTS_GENERATOR and installed and root is not None:
            if not self._venv_python(root).is_file():
                missing.append("prepared Python venv")
        ready = installed and not any(item in runtime_blockers for item in missing)
        return VideoEngineStatus(
            spec.engine.value,
            spec.name,
            ready,
            installed,
            str(root) if root else None,
            spec.web_url,
            spec.api_url,
            tuple(missing),
            spec.description,
            spec.free_mode,
            spec.license,
            spec.reviewed_commit,
        )

    def all_statuses(self) -> list[VideoEngineStatus]:
        return [self.status(spec.engine) for spec in SPECS]

    @staticmethod
    def _venv_python(root: Path) -> Path:
        return root / ".venv" / ("Scripts/python.exe" if os.name == "nt" else "bin/python")

    def _run_checked(self, args: list[str], *, cwd: Path, timeout: float) -> None:
        result = self.runner.run(args, cwd=cwd, timeout=timeout)
        if result.returncode != 0:
            raise RuntimeError(result.stdout[-5000:] or f"Command failed: {args[0]}")

    def prepare(self, engine: VideoEngineId | str, *, timeout: float = 1800) -> dict[str, Any]:
        spec = self.spec(engine)
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        git = shutil.which("git")
        if git is None:
            raise RuntimeError("Git is required before the video engine can be prepared")

        configured = self._configured_root(spec)
        target = configured or self._default_root(spec)
        target = self.guard.require(target, Permission.WRITE, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)

        if not target.exists():
            self._run_checked(
                [git, "clone", "--filter=blob:none", spec.repository, str(target)],
                cwd=self.root,
                timeout=timeout,
            )
        if not (target / ".git").is_dir():
            raise RuntimeError("Configured video engine folder is not a Git checkout")

        self._run_checked([git, "fetch", "origin", spec.reviewed_commit], cwd=target, timeout=timeout)
        self._run_checked([git, "checkout", "--detach", spec.reviewed_commit], cwd=target, timeout=120)

        if spec.engine is VideoEngineId.MONEYPRINTER:
            uv = shutil.which("uv")
            if uv:
                self._run_checked([uv, "sync", "--frozen"], cwd=target, timeout=timeout)
            else:
                venv_python = self._venv_python(target)
                if not venv_python.is_file():
                    self._run_checked([sys.executable, "-m", "venv", ".venv"], cwd=target, timeout=300)
                self._run_checked(
                    [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
                    cwd=target,
                    timeout=timeout,
                )
        elif spec.engine is VideoEngineId.AUTOMATED_VIDEO:
            npm = shutil.which("npm")
            if npm is None:
                raise RuntimeError("Node.js/npm is required for Automated Video Generator")
            self._run_checked([npm, "install"], cwd=target, timeout=timeout)
        else:
            npm = shutil.which("npm")
            if npm is None:
                raise RuntimeError("Node.js/npm is required for ShortsGenerator")
            venv_python = self._venv_python(target)
            if not venv_python.is_file():
                self._run_checked([sys.executable, "-m", "venv", ".venv"], cwd=target, timeout=300)
            self._run_checked(
                [str(venv_python), "-m", "pip", "install", "-r", "requirements.txt"],
                cwd=target,
                timeout=timeout,
            )
            self._run_checked([npm, "install"], cwd=target / "UI", timeout=timeout)

        relative = str(target.relative_to(self.root))
        self.settings.save({spec.root_setting: relative})
        self.state.record_event(
            "video_engine.prepare",
            {"engine": spec.engine.value, "root": relative, "commit": spec.reviewed_commit},
            agent="Video Studio",
        )
        return self.status(spec.engine).to_dict()

    def start(self, engine: VideoEngineId | str) -> dict[str, Any]:
        spec = self.spec(engine)
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        root = self._configured_root(spec)
        if not self._root_is_installed(spec, root) or root is None:
            raise RuntimeError(f"{spec.name} is not prepared yet")

        started: list[dict[str, Any]] = []
        if spec.engine is VideoEngineId.MONEYPRINTER:
            if os.name == "nt":
                args = ["cmd", "/c", "webui.bat"]
            elif (root / "webui.sh").is_file():
                args = ["sh", "webui.sh"]
            else:
                uv = shutil.which("uv")
                if not uv:
                    raise RuntimeError("uv or webui.sh is required to launch MoneyPrinterTurbo")
                args = [uv, "run", "streamlit", "run", "./webui/Main.py", "--browser.gatherUsageStats=False"]
            item = self.processes.start(args, cwd=root)
            started.append({"process_id": item.process_id, "pid": item.pid, "role": "webui"})
        elif spec.engine is VideoEngineId.AUTOMATED_VIDEO:
            npm = shutil.which("npm")
            if not npm:
                raise RuntimeError("npm is required to launch Automated Video Generator")
            item = self.processes.start([npm, "run", "dev"], cwd=root)
            started.append({"process_id": item.process_id, "pid": item.pid, "role": "webui"})
        else:
            npm = shutil.which("npm")
            if not npm:
                raise RuntimeError("npm is required to launch ShortsGenerator")
            python = self._venv_python(root)
            if not python.is_file():
                raise RuntimeError("ShortsGenerator Python environment is not prepared")
            backend = self.processes.start([str(python), "main.py"], cwd=root / "Backend")
            frontend = self.processes.start([npm, "run", "dev"], cwd=root / "UI")
            started.extend(
                [
                    {"process_id": backend.process_id, "pid": backend.pid, "role": "backend"},
                    {"process_id": frontend.process_id, "pid": frontend.pid, "role": "frontend"},
                ]
            )

        self.state.record_event(
            "video_engine.start",
            {"engine": spec.engine.value, "processes": started},
            agent="Video Studio",
        )
        return {"engine": spec.engine.value, "web_url": spec.web_url, "processes": started}

    def create_moneyprinter(
        self,
        *,
        subject: str,
        script: str = "",
        duration_seconds: int = 60,
        aspect: str = "9:16",
        language: str = "ar",
        video_source: str = "pexels",
        voice_name: str = "",
        video_materials: str = "",
        transition_mode: str = "",
        concat_mode: str = "",
        clip_duration: int | None = None,
        bgm_type: str = "",
        subtitle_enabled: bool | None = None,
        subtitle_display_mode: str = "",
        subtitle_animation: str = "",
        voice_rate: float | None = None,
        timeout: float = 3600,
    ) -> dict[str, Any]:
        spec = self.spec(VideoEngineId.MONEYPRINTER)
        self.guard.require(self.root, Permission.SHELL, must_exist=True)
        self.guard.require(self.root, Permission.NETWORK, must_exist=True)
        root = self._configured_root(spec)
        if not self._root_is_installed(spec, root) or root is None:
            raise RuntimeError("MoneyPrinterTurbo is not prepared yet")
        if not subject.strip() and not script.strip():
            raise ValueError("Enter a topic or a complete script")
        if not 15 <= int(duration_seconds) <= 180:
            raise ValueError("Target duration must be between 15 and 180 seconds")
        if aspect not in {"9:16", "16:9", "1:1"}:
            raise ValueError("Unsupported aspect ratio")

        uv = shutil.which("uv")
        if uv:
            args = [uv, "run", "python", "cli.py"]
        else:
            python = self._venv_python(root)
            if not python.is_file():
                raise RuntimeError("MoneyPrinterTurbo Python environment is not prepared")
            args = [str(python), "cli.py"]

        if script.strip():
            args.extend(["--video-script", script.strip()])
        else:
            args.extend(["--video-subject", subject.strip()])
            args.extend(
                [
                    "--video-script-prompt",
                    f"Create narration targeted to about {int(duration_seconds)} seconds of spoken video.",
                ]
            )
        args.extend(["--video-aspect", aspect, "--video-language", language, "--video-source", video_source])
        if video_source == "local":
            if not video_materials.strip():
                raise ValueError("Choose one or more local video/image files for local source mode")
            args.extend(["--video-materials", video_materials.strip()])
        elif video_materials.strip():
            raise ValueError("Local materials can only be used with local source mode")
        if voice_name.strip():
            args.extend(["--voice-name", voice_name.strip()])
        if transition_mode:
            args.extend(["--video-transition-mode", transition_mode])
        if concat_mode:
            args.extend(["--video-concat-mode", concat_mode])
        if clip_duration is not None:
            args.extend(["--video-clip-duration", str(int(clip_duration))])
        if bgm_type:
            args.extend(["--bgm-type", bgm_type])
        if subtitle_enabled is True:
            args.append("--subtitle-enabled")
        elif subtitle_enabled is False:
            args.append("--no-subtitle-enabled")
        if subtitle_display_mode:
            args.extend(["--subtitle-display-mode", subtitle_display_mode])
        if subtitle_animation:
            args.extend(["--subtitle-animation", subtitle_animation])
        if voice_rate is not None:
            args.extend(["--voice-rate", str(float(voice_rate))])

        result = self.runner.run(args, cwd=root, timeout=timeout)
        self.state.record_event(
            "video_studio.generate",
            {
                "engine": spec.engine.value,
                "returncode": result.returncode,
                "duration_target": int(duration_seconds),
                "aspect": aspect,
                "language": language,
                "source": video_source,
                "local_material_count": len([x for x in video_materials.split(",") if x.strip()]),
                "subject_chars": len(subject),
                "script_chars": len(script),
                "transition": transition_mode,
                "concat": concat_mode,
                "bgm_type": bgm_type,
                "subtitle_enabled": subtitle_enabled,
            },
            agent="Video Studio",
        )
        return {
            "engine": spec.engine.value,
            "returncode": result.returncode,
            "output": result.stdout[-12000:],
            "duration_seconds": result.duration_seconds,
        }

from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any

from .integration_settings import IntegrationSettings
from .permissions import Permission, WorkspaceGuard
from .state import ProjectState


_PLUGIN_ID = re.compile(r"^[a-z][a-z0-9_.-]{1,63}$")
_ENV_SETTING = {
    "NEXVARY_DA_FASTMCP_BIN": "fastmcp_bin",
    "NEXVARY_DA_CUA_BIN": "cua_bin",
    "NEXVARY_DA_NODE_BIN": "node_bin",
    "NEXVARY_DA_OYA_NODE_ROOT": "oya_node_root",
    "NEXVARY_DA_VOICESTUDIO_URL": "voicestudio_url",
    "NEXVARY_DA_MONEYPRINTER_ROOT": "moneyprinter_root",
}


class PluginKind(StrEnum):
    MCP = "mcp"
    DESKTOP = "desktop"
    BROWSER = "browser"
    VOICE = "voice"
    IMAGE = "image"
    VIDEO = "video"


@dataclass(frozen=True, slots=True)
class PluginSpec:
    plugin_id: str
    name: str
    kind: PluginKind
    upstream: str
    license: str
    capabilities: tuple[str, ...]
    permissions: tuple[Permission, ...]
    executable_candidates: tuple[str, ...] = ()
    executable_env: str = ""
    endpoint_env: str = ""
    default_endpoint: str = ""
    root_env: str = ""
    required_relative_paths: tuple[str, ...] = ()
    python_modules: tuple[str, ...] = ()
    notes: str = ""


@dataclass(frozen=True, slots=True)
class PluginStatus:
    plugin_id: str
    name: str
    kind: str
    ready: bool
    executable: str | None
    endpoint: str | None
    root: str | None
    missing_permissions: tuple[str, ...]
    missing_environment: tuple[str, ...]
    missing_requirements: tuple[str, ...]
    capabilities: tuple[str, ...]
    license: str
    upstream: str
    notes: str
    source: str = "builtin"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


BUILTIN_PLUGIN_SPECS: tuple[PluginSpec, ...] = (
    PluginSpec(
        "fastmcp",
        "FastMCP",
        PluginKind.MCP,
        "https://github.com/PrefectHQ/fastmcp",
        "Apache-2.0",
        ("mcp-server", "tool-registry", "stdio", "http"),
        (Permission.SHELL,),
        ("fastmcp",),
        "NEXVARY_DA_FASTMCP_BIN",
    ),
    PluginSpec(
        "cua-driver",
        "Cua Driver",
        PluginKind.DESKTOP,
        "https://github.com/trycua/cua",
        "MIT",
        ("computer-use", "accessibility", "screenshot", "mouse", "keyboard"),
        (Permission.SHELL, Permission.DESKTOP_AUTOMATION),
        ("cua-driver",),
        "NEXVARY_DA_CUA_BIN",
    ),
    PluginSpec(
        "oya-browser",
        "Oya Browser SDK",
        PluginKind.BROWSER,
        "https://github.com/OyadotAI/oya-browser",
        "MIT for packages/sdk and packages/cli",
        ("browser-agent", "record", "playbook", "persistent-session"),
        (Permission.SHELL, Permission.WRITE, Permission.NETWORK),
        ("node",),
        "NEXVARY_DA_NODE_BIN",
        root_env="NEXVARY_DA_OYA_NODE_ROOT",
        required_relative_paths=("node_modules/@oya-ai/browser/package.json",),
        notes="NEXVARY integrates the MIT-licensed SDK surface only.",
    ),
    PluginSpec(
        "voicestudio",
        "VoiceStudio",
        PluginKind.VOICE,
        "https://github.com/debpalash/VoiceStudio",
        "AGPL-3.0-only external service",
        ("tts", "asr", "dubbing", "local-api", "mcp"),
        (Permission.NETWORK,),
        endpoint_env="NEXVARY_DA_VOICESTUDIO_URL",
        default_endpoint="http://127.0.0.1:3900",
        notes="External-service interoperability; no VoiceStudio source is vendored.",
    ),
    PluginSpec(
        "qwen-image-2.1",
        "Qwen-Image 2.1",
        PluginKind.IMAGE,
        "https://github.com/QwenLM/Qwen-Image-2.1",
        "Qwen Research License",
        ("text-to-image", "image-edit", "rgba"),
        (Permission.SHELL, Permission.WRITE),
        python_modules=("torch", "diffusers"),
        notes="Upstream model materials are non-commercial unless separately licensed.",
    ),
    PluginSpec(
        "moneyprinterturbo",
        "MoneyPrinterTurbo",
        PluginKind.VIDEO,
        "https://github.com/harry0703/MoneyPrinterTurbo",
        "MIT",
        ("video-workflow", "script", "tts", "subtitles", "render"),
        (Permission.SHELL, Permission.NETWORK),
        root_env="NEXVARY_DA_MONEYPRINTER_ROOT",
        required_relative_paths=("cli.py",),
        notes="Must be installed inside the approved workspace; it is not vendored.",
    ),
)


class PluginHub:
    """Status and manifest registry for optional external integrations.

    Discovery never installs packages, downloads models, starts processes, or probes
    the network. Dedicated adapters remain responsible for execution and permission
    checks.
    """

    def __init__(
        self,
        guard: WorkspaceGuard,
        state: ProjectState,
        root: str | os.PathLike[str],
    ):
        self.guard = guard
        self.state = state
        self.root = Path(root).resolve(strict=True)
        self.settings = IntegrationSettings(guard, self.root)

    def _configured(self, env_name: str, default: str = "") -> str:
        if not env_name:
            return default
        key = _ENV_SETTING.get(env_name)
        if key:
            return self.settings.get(key, env_name, default)
        return os.environ.get(env_name, "").strip() or default

    def _candidate_executable(self, spec: PluginSpec) -> str | None:
        configured = self._configured(spec.executable_env) if spec.executable_env else ""
        if configured:
            path = Path(configured).expanduser()
            if path.is_file():
                return str(path.resolve())
            found = shutil.which(configured)
            return found
        for candidate in spec.executable_candidates:
            found = shutil.which(candidate)
            if found:
                return found
        return None

    def _root_for(self, spec: PluginSpec) -> tuple[Path | None, list[str]]:
        missing: list[str] = []
        if not spec.root_env:
            base = self.root
        else:
            raw = self._configured(spec.root_env)
            if not raw:
                return None, [spec.root_env]
            candidate = Path(raw).expanduser()
            if not candidate.is_absolute():
                candidate = self.root / candidate
            try:
                base = self.guard.require(candidate, Permission.READ, must_exist=True)
            except Exception:
                return None, [f"{spec.root_env}:approved-workspace-path"]
        for relative in spec.required_relative_paths:
            if not (base / relative).is_file():
                missing.append(relative)
        return base, missing

    @staticmethod
    def _missing_modules(spec: PluginSpec) -> list[str]:
        return [name for name in spec.python_modules if importlib.util.find_spec(name) is None]

    def status(self, plugin_id: str) -> PluginStatus:
        spec = next((item for item in BUILTIN_PLUGIN_SPECS if item.plugin_id == plugin_id), None)
        if spec is None:
            raise KeyError(f"Unknown built-in plugin: {plugin_id}")
        missing_permissions = tuple(
            permission.value
            for permission in spec.permissions
            if not self.guard.has(self.root, permission)
        )
        executable = self._candidate_executable(spec)
        missing_environment: list[str] = []
        missing_requirements: list[str] = []

        if spec.executable_candidates or spec.executable_env:
            if executable is None:
                missing_requirements.append(spec.executable_env or "/".join(spec.executable_candidates))

        plugin_root, root_missing = self._root_for(spec)
        missing_environment.extend(item for item in root_missing if ":" not in item and item == spec.root_env)
        missing_requirements.extend(item for item in root_missing if item not in missing_environment)

        endpoint = None
        if spec.endpoint_env or spec.default_endpoint:
            endpoint = self._configured(spec.endpoint_env) if spec.endpoint_env else ""
            endpoint = endpoint or spec.default_endpoint or None

        missing_requirements.extend(self._missing_modules(spec))

        if spec.plugin_id == "oya-browser" and not os.environ.get("OYA_API_KEY", "").strip():
            missing_environment.append("OYA_API_KEY")

        ready = not missing_permissions and not missing_environment and not missing_requirements
        return PluginStatus(
            spec.plugin_id,
            spec.name,
            spec.kind.value,
            ready,
            executable,
            endpoint,
            str(plugin_root) if plugin_root is not None and spec.root_env else None,
            tuple(sorted(set(missing_permissions))),
            tuple(sorted(set(missing_environment))),
            tuple(sorted(set(missing_requirements))),
            spec.capabilities,
            spec.license,
            spec.upstream,
            spec.notes,
        )

    def all_statuses(self) -> list[PluginStatus]:
        return [self.status(spec.plugin_id) for spec in BUILTIN_PLUGIN_SPECS]

    def snapshot(self) -> dict[str, Any]:
        statuses = self.all_statuses()
        payload = {
            "ready": sum(1 for item in statuses if item.ready),
            "total": len(statuses),
            "plugins": [item.to_dict() for item in statuses],
        }
        self.state.set_meta("last_plugin_snapshot", payload)
        return payload

    def load_custom_manifests(self) -> list[dict[str, Any]]:
        """Load custom status-only manifests from .nexvary-da/plugins.

        A manifest does not grant execution. It is inventory metadata until a
        dedicated, permission-gated adapter consumes it.
        """
        directory = self.root / ".nexvary-da" / "plugins"
        if not directory.is_dir():
            return []
        manifests: list[dict[str, Any]] = []
        for path in sorted(directory.glob("*.json")):
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            if not isinstance(raw, dict):
                continue
            plugin_id = raw.get("id")
            if not isinstance(plugin_id, str) or not _PLUGIN_ID.fullmatch(plugin_id):
                continue
            permissions: list[str] = []
            valid = True
            for value in raw.get("permissions", []):
                try:
                    permissions.append(Permission(value).value)
                except (ValueError, TypeError):
                    valid = False
                    break
            if not valid:
                continue
            manifests.append(
                {
                    "id": plugin_id,
                    "name": str(raw.get("name") or plugin_id),
                    "kind": str(raw.get("kind") or "mcp"),
                    "capabilities": [
                        str(value) for value in raw.get("capabilities", []) if isinstance(value, str)
                    ],
                    "permissions": permissions,
                    "enabled": raw.get("enabled") is True,
                    "source": str(path.relative_to(self.root)),
                }
            )
        return manifests

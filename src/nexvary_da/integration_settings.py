from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any

from .permissions import Permission, WorkspaceGuard


_ALLOWED_DEFAULTS: dict[str, str] = {
    "fastmcp_bin": "",
    "cua_bin": "",
    "node_bin": "",
    "oya_node_root": "",
    "voicestudio_url": "http://127.0.0.1:3900",
    "moneyprinter_root": "",
    "automated_video_root": "",
    "shorts_generator_root": "",
    "video_engine": "moneyprinter",
    "video_duration": "60",
    "video_aspect": "9:16",
    "video_language": "ar-EG",
    "product_ad_currency": "EGP",
    "product_ad_voice": "ar-EG-SalmaNeural",
    "product_ad_duration": "60",
    "product_ad_video_role": "camera_sample",
    "product_ad_video_audio": "duck",
    "ai_video_mode": "hybrid",
    "ai_model_root": "",
    "comfyui_url": "http://127.0.0.1:8188",
    "comfyui_workflow_path": "",
    "ai_enhanced_product_ads": "true",
    "auto_ocr_product_images": "true",
    "ai_max_scenes": "4",
    "cogvideox_root": "",
    "framepack_root": "",
    "ltx_root": "",
    "wan_root": "",
    "qwen_model": "Qwen/Qwen-Image-2.1",
    "qwen_device": "cuda",
}

_SECRET_WORDS = ("secret", "token", "password", "api_key", "apikey", "credential")


class IntegrationSettings:
    """Persistent non-secret integration preferences.

    Secrets are deliberately excluded. Environment variables override saved values
    so organization-managed configuration remains authoritative.
    """

    def __init__(self, guard: WorkspaceGuard, root: str | os.PathLike[str]):
        self.guard = guard
        self.root = Path(root).resolve(strict=True)
        self.path = self.root / ".nexvary-da" / "integrations.json"

    @staticmethod
    def allowed_keys() -> tuple[str, ...]:
        return tuple(_ALLOWED_DEFAULTS)

    @staticmethod
    def _check_key(key: str) -> None:
        if key not in _ALLOWED_DEFAULTS:
            raise KeyError(f"Unsupported integration setting: {key}")
        lowered = key.lower()
        if any(word in lowered for word in _SECRET_WORDS):
            raise ValueError("Secret values cannot be persisted in integration settings")

    def load(self) -> dict[str, str]:
        values = dict(_ALLOWED_DEFAULTS)
        if not self.path.is_file():
            return values
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return values
        if not isinstance(raw, dict):
            return values
        for key, value in raw.items():
            if key in _ALLOWED_DEFAULTS and isinstance(value, str):
                values[key] = value.strip()
        return values

    def get(self, key: str, env_name: str = "", default: str | None = None) -> str:
        self._check_key(key)
        if env_name:
            env_value = os.environ.get(env_name, "").strip()
            if env_value:
                return env_value
        values = self.load()
        value = values.get(key, "")
        if value:
            return value
        return _ALLOWED_DEFAULTS[key] if default is None else default

    def save(self, updates: dict[str, Any]) -> dict[str, str]:
        self.guard.require(self.root, Permission.WRITE, must_exist=True)
        current = self.load()
        for key, value in updates.items():
            self._check_key(str(key))
            if not isinstance(value, str):
                raise TypeError(f"Integration setting {key} must be text")
            current[str(key)] = value.strip()

        target = self.guard.require(self.path, Permission.WRITE, must_exist=False)
        target.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=".integrations.", suffix=".json", dir=target.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="") as handle:
                json.dump(current, handle, indent=2, sort_keys=True, ensure_ascii=False)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, target)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return current

    def public_snapshot(self) -> dict[str, str]:
        return self.load()

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from pathlib import Path

from .errors import ConfigurationError


_ALLOWED = {"auto", "required", "disabled"}


@dataclass(frozen=True, slots=True)
class ReleasePolicy:
    integration_tests: str = "auto"
    static_analysis: str = "required"
    dead_links: str = "auto"
    orphan_pages: str = "auto"
    broken_buttons: str = "auto"
    navigation: str = "auto"
    ui_gate: str = "required"
    rtl: str = "auto"
    localization: str = "auto"
    artifacts: str = "required"

    def __post_init__(self) -> None:
        for key, value in asdict(self).items():
            if value not in _ALLOWED:
                raise ConfigurationError(f"Invalid release policy value for {key}: {value!r}")

    def required(self, key: str, *, applicable: bool) -> bool:
        value = getattr(self, key)
        if value == "disabled":
            return False
        if value == "required":
            return True
        return applicable

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def load_release_policy(root: str | Path) -> ReleasePolicy:
    path = Path(root).resolve(strict=True) / ".nexvary-da" / "release-policy.json"
    if not path.exists():
        return ReleasePolicy()
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ConfigurationError(f"Invalid release policy: {path}") from exc
    if not isinstance(raw, dict):
        raise ConfigurationError("release-policy.json must contain an object")
    allowed_keys = set(ReleasePolicy.__dataclass_fields__)
    unknown = set(raw) - allowed_keys
    if unknown:
        raise ConfigurationError(f"Unknown release policy keys: {sorted(unknown)}")
    return ReleasePolicy(**raw)

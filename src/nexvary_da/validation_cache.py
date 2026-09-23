from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from .change_tracker import ProjectChangeTracker


class ValidationCache:
    """Small atomic cache for Fast/Engineer validation evidence.

    Release mode is intentionally never served from this cache.
    """

    VERSION = 1

    def __init__(self, root: str | Path):
        self.root = Path(root).resolve(strict=True)
        self.path = self.root / ".nexvary-da" / "validation-cache.json"
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def make_key(
        self,
        *,
        mode: str,
        changed_files: Iterable[str],
        commit: str | None,
        toolchain: str = "",
    ) -> str:
        changed = tuple(sorted(set(changed_files)))
        tracker = ProjectChangeTracker(self.root)
        payload = {
            "version": self.VERSION,
            "mode": mode,
            "commit": commit or "",
            "changed": changed,
            "content": tracker.content_fingerprint(changed),
            "toolchain": toolchain,
        }
        encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        return hashlib.sha256(encoded).hexdigest()

    def _load(self) -> dict[str, Any]:
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (FileNotFoundError, OSError, json.JSONDecodeError):
            return {"version": self.VERSION, "entries": {}}
        if raw.get("version") != self.VERSION or not isinstance(raw.get("entries"), dict):
            return {"version": self.VERSION, "entries": {}}
        return raw

    def get(self, key: str) -> dict[str, Any] | None:
        value = self._load()["entries"].get(key)
        return value if isinstance(value, dict) else None

    def put(self, key: str, value: dict[str, Any], *, max_entries: int = 32) -> None:
        data = self._load()
        entries = data["entries"]
        entries[key] = value
        while len(entries) > max_entries:
            entries.pop(next(iter(entries)))
        fd, temp_name = tempfile.mkstemp(prefix=".validation-cache.", dir=self.path.parent)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(data, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            Path(temp_name).replace(self.path)
        finally:
            Path(temp_name).unlink(missing_ok=True)

    def clear(self) -> None:
        self.path.unlink(missing_ok=True)

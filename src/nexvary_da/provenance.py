from __future__ import annotations

import hashlib
import json
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .artifact_manifest import build_manifest
from .environment import discover_environment


_SKIP = {".git", ".nexvary-da", ".venv", "venv", "__pycache__", "node_modules", "build", "dist"}
_SOURCE_SUFFIXES = {
    ".py", ".toml", ".yml", ".yaml", ".json", ".md", ".xml", ".kt", ".java",
    ".js", ".ts", ".tsx", ".jsx", ".c", ".cc", ".cpp", ".h", ".hpp", ".gradle",
}


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def source_manifest(root: str | Path, *, max_file_bytes: int = 20_000_000) -> dict[str, Any]:
    base = Path(root).resolve(strict=True)
    files: list[dict[str, Any]] = []
    for current, dirs, names in os.walk(base):
        dirs[:] = sorted(d for d in dirs if d not in _SKIP)
        for name in sorted(names):
            path = Path(current) / name
            if path.suffix.lower() not in _SOURCE_SUFFIXES and name not in {"gradlew", "gradlew.bat", "CMakeLists.txt"}:
                continue
            try:
                safe = path.resolve(strict=True)
                safe.relative_to(base)
                size = safe.stat().st_size
            except (OSError, ValueError):
                continue
            if size > max_file_bytes:
                files.append(
                    {
                        "path": safe.relative_to(base).as_posix(),
                        "size_bytes": size,
                        "sha256": None,
                        "hash_skipped": "file-too-large",
                    }
                )
                continue
            files.append(
                {
                    "path": safe.relative_to(base).as_posix(),
                    "size_bytes": size,
                    "sha256": _hash(safe),
                }
            )

    root_digest = hashlib.sha256()
    for item in files:
        root_digest.update(str(item["path"]).encode("utf-8"))
        root_digest.update(b"\0")
        root_digest.update(str(item.get("sha256") or "").encode("ascii"))
        root_digest.update(b"\0")
        root_digest.update(str(item["size_bytes"]).encode("ascii"))
        root_digest.update(b"\n")
    return {
        "schema": 1,
        "file_count": len(files),
        "source_root_sha256": root_digest.hexdigest(),
        "files": files,
    }


def build_provenance(runtime) -> dict[str, Any]:
    environment = discover_environment()
    return {
        "schema": 1,
        "created_at": datetime.now(UTC).isoformat(),
        "project": {
            "name": runtime.config.name,
            "repository": runtime.config.repository,
            "branch": _safe(lambda: runtime.git.branch()),
            "commit": _safe(lambda: runtime.git.commit()),
        },
        "source": source_manifest(runtime.root),
        "artifacts": build_manifest(runtime.root),
        "environment": {
            "system": environment.get("system"),
            "machine": environment.get("machine"),
            "python_version": environment.get("python_version"),
        },
    }


def write_provenance(runtime, destination: str = ".nexvary-da/provenance.json") -> Path:
    target = runtime.root / destination
    target.parent.mkdir(parents=True, exist_ok=True)
    payload = build_provenance(runtime)
    fd, temp_name = tempfile.mkstemp(prefix=".provenance.", suffix=".tmp", dir=target.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(payload, handle, ensure_ascii=False, sort_keys=True, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temp_name, target)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)
    runtime.state.record_event(
        "provenance.written",
        {
            "path": str(target.relative_to(runtime.root)),
            "source_root_sha256": payload["source"]["source_root_sha256"],
            "artifact_count": payload["artifacts"]["artifact_count"],
        },
        agent="Release Manager",
    )
    return target


def verify_source_manifest(root: str | Path, manifest: dict[str, Any]) -> dict[str, Any]:
    current = source_manifest(root)
    expected = manifest.get("source_root_sha256")
    actual = current["source_root_sha256"]
    return {
        "match": isinstance(expected, str) and expected == actual,
        "expected": expected,
        "actual": actual,
        "file_count": current["file_count"],
    }


def _safe(callback):
    try:
        return callback()
    except Exception:
        return None

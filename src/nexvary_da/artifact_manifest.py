from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable


_SUFFIXES = {".whl", ".zip", ".apk", ".aab", ".exe", ".msi", ".deb", ".gz"}


@dataclass(frozen=True, slots=True)
class ArtifactRecord:
    path: str
    size_bytes: int
    sha256: str


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def discover_artifacts(root: str | Path) -> tuple[Path, ...]:
    base = Path(root).resolve(strict=True)
    search = (base / "dist", base / "build" / "outputs", base / "app" / "build" / "outputs")
    result: set[Path] = set()
    for folder in search:
        if not folder.exists():
            continue
        for path in folder.rglob("*"):
            if path.is_file() and (path.suffix.lower() in _SUFFIXES or path.name.lower().endswith(".tar.gz")):
                result.add(path)
    return tuple(sorted(result))


def build_manifest(root: str | Path, artifacts: Iterable[Path] | None = None) -> dict[str, object]:
    base = Path(root).resolve(strict=True)
    paths = tuple(artifacts) if artifacts is not None else discover_artifacts(base)
    records = [
        ArtifactRecord(path.relative_to(base).as_posix(), path.stat().st_size, sha256_file(path))
        for path in paths
    ]
    return {
        "schema": 1,
        "artifact_count": len(records),
        "artifacts": [asdict(record) for record in records],
    }


def write_manifest(root: str | Path, destination: str | Path) -> Path:
    base = Path(root).resolve(strict=True)
    target = Path(destination)
    if not target.is_absolute():
        target = base / target
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(build_manifest(base), indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return target

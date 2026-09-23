from __future__ import annotations

import hashlib
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_IGNORED_DIRS = {".git", ".nexvary-da", "__pycache__", ".gradle", "node_modules", "build", "dist"}


@dataclass(frozen=True, slots=True)
class FileStamp:
    size: int
    mtime_ns: int


@dataclass(frozen=True, slots=True)
class ChangeSet:
    added: tuple[str, ...]
    modified: tuple[str, ...]
    deleted: tuple[str, ...]

    @property
    def changed(self) -> tuple[str, ...]:
        return tuple(sorted((*self.added, *self.modified, *self.deleted)))


class ProjectChangeTracker:
    """Dependency-free file watcher primitive based on cheap metadata snapshots."""

    def __init__(self, root: str | Path, ignored_dirs: Iterable[str] = _IGNORED_DIRS):
        self.root = Path(root).resolve(strict=True)
        self.ignored_dirs = frozenset(ignored_dirs)
        self._snapshot = self.snapshot()

    def snapshot(self) -> dict[str, FileStamp]:
        result: dict[str, FileStamp] = {}
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in self.ignored_dirs]
            base_path = Path(base)
            for name in files:
                path = base_path / name
                try:
                    stat = path.stat()
                except OSError:
                    continue
                rel = path.relative_to(self.root).as_posix()
                result[rel] = FileStamp(stat.st_size, stat.st_mtime_ns)
        return result

    def poll(self) -> ChangeSet:
        current = self.snapshot()
        previous = self._snapshot
        added = tuple(sorted(current.keys() - previous.keys()))
        deleted = tuple(sorted(previous.keys() - current.keys()))
        modified = tuple(
            sorted(path for path in current.keys() & previous.keys() if current[path] != previous[path])
        )
        self._snapshot = current
        return ChangeSet(added, modified, deleted)

    def content_fingerprint(self, paths: Iterable[str]) -> str:
        digest = hashlib.sha256()
        for rel in sorted(set(paths)):
            digest.update(rel.encode("utf-8", errors="surrogatepass"))
            digest.update(b"\0")
            path = self.root / rel
            if not path.is_file():
                digest.update(b"<missing>")
                continue
            try:
                with path.open("rb") as handle:
                    while chunk := handle.read(1024 * 1024):
                        digest.update(chunk)
            except OSError as exc:
                digest.update(f"<error:{type(exc).__name__}>".encode())
        return digest.hexdigest()

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass
from pathlib import Path

from .permissions import Permission, WorkspaceGuard


@dataclass(slots=True)
class SearchHit:
    path: str
    line: int
    text: str


class FileTools:
    def __init__(self, guard: WorkspaceGuard, root: str | os.PathLike[str]):
        self.guard = guard
        self.root = guard.require(root, Permission.READ, must_exist=True)

    def _path(self, relative: str | os.PathLike[str]) -> Path:
        return self.root / Path(relative)

    def read_text(self, relative: str | os.PathLike[str], encoding: str = "utf-8") -> str:
        path = self.guard.require(self._path(relative), Permission.READ, must_exist=True)
        if not path.is_file():
            raise IsADirectoryError(path)
        return path.read_text(encoding=encoding)

    def write_text(self, relative: str | os.PathLike[str], content: str, encoding: str = "utf-8") -> Path:
        path = self.guard.require(self._path(relative), Permission.WRITE, must_exist=False)
        path.parent.mkdir(parents=True, exist_ok=True)
        fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
        try:
            with os.fdopen(fd, "w", encoding=encoding, newline="") as handle:
                handle.write(content)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temp_name, path)
        finally:
            if os.path.exists(temp_name):
                os.unlink(temp_name)
        return path

    def patch_exact(
        self,
        relative: str | os.PathLike[str],
        before: str,
        after: str,
        *,
        expected_count: int = 1,
    ) -> Path:
        current = self.read_text(relative)
        count = current.count(before)
        if count != expected_count:
            raise ValueError(
                f"Patch precondition failed for {relative}: expected {expected_count} match(es), got {count}"
            )
        return self.write_text(relative, current.replace(before, after, expected_count))

    def search(
        self,
        needle: str,
        *,
        suffixes: tuple[str, ...] = (),
        max_file_bytes: int = 2_000_000,
        max_hits: int = 200,
    ) -> list[SearchHit]:
        if not needle:
            raise ValueError("needle cannot be empty")
        hits: list[SearchHit] = []
        skip_dirs = {".git", ".nexvary-da", "__pycache__", "node_modules", "build", "dist"}
        for base, dirs, files in os.walk(self.root):
            dirs[:] = [d for d in dirs if d not in skip_dirs]
            for name in files:
                if suffixes and not name.endswith(suffixes):
                    continue
                path = Path(base) / name
                safe = self.guard.require(path, Permission.READ, must_exist=True)
                try:
                    if safe.stat().st_size > max_file_bytes:
                        continue
                    with safe.open("r", encoding="utf-8", errors="replace") as handle:
                        for line_no, line in enumerate(handle, 1):
                            if needle in line:
                                hits.append(SearchHit(str(safe.relative_to(self.root)), line_no, line.rstrip()))
                                if len(hits) >= max_hits:
                                    return hits
                except OSError:
                    continue
        return hits

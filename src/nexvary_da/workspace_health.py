from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class WorkspaceHealth:
    escaped_symlinks: tuple[str, ...]
    case_collisions: tuple[tuple[str, str], ...]
    oversized_source_files: tuple[str, ...]

    @property
    def healthy(self) -> bool:
        return not (self.escaped_symlinks or self.case_collisions or self.oversized_source_files)


_SKIP = {".git", ".nexvary-da", ".venv", "venv", "node_modules", "build", "dist", "__pycache__"}
_SOURCE_SUFFIXES = {".py", ".kt", ".java", ".js", ".ts", ".tsx", ".jsx", ".c", ".cc", ".cpp", ".h", ".hpp", ".xml", ".json", ".html", ".css"}


def inspect_workspace(root: str | Path, *, max_source_bytes: int = 5_000_000) -> WorkspaceHealth:
    base = Path(root).resolve(strict=True)
    escaped: list[str] = []
    oversized: list[str] = []
    seen_case: dict[str, str] = {}
    collisions: list[tuple[str, str]] = []

    for current, dirs, files in os.walk(base, followlinks=False):
        dirs[:] = [d for d in dirs if d not in _SKIP]
        current_path = Path(current)
        for name in [*dirs, *files]:
            path = current_path / name
            rel = path.relative_to(base).as_posix()
            folded = rel.casefold()
            previous = seen_case.get(folded)
            if previous is not None and previous != rel:
                collisions.append((previous, rel))
            else:
                seen_case[folded] = rel
            if path.is_symlink():
                try:
                    resolved = path.resolve(strict=True)
                    resolved.relative_to(base)
                except (OSError, ValueError):
                    escaped.append(rel)
            if path.is_file() and path.suffix.lower() in _SOURCE_SUFFIXES:
                try:
                    if path.stat().st_size > max_source_bytes:
                        oversized.append(rel)
                except OSError:
                    pass

    return WorkspaceHealth(tuple(sorted(set(escaped))), tuple(sorted(set(collisions))), tuple(sorted(set(oversized))))

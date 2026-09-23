from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .environment import detect_project_kind
from .redaction import redact


_CHECKPOINT_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{8}$")


def _utc_stamp() -> str:
    return datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass(frozen=True, slots=True)
class CheckpointInfo:
    checkpoint_id: str
    created_at: str
    label: str
    branch: str | None
    commit: str | None
    changed_count: int
    path: str


class CheckpointStore:
    """Durable, redacted project-resume checkpoints without copying source files."""

    def __init__(self, runtime):
        self.runtime = runtime
        self.root = runtime.root
        self.directory = self.root / ".nexvary-da" / "checkpoints"
        self.directory.mkdir(parents=True, exist_ok=True)

    def create(
        self,
        *,
        label: str = "",
        note: str = "",
        max_hashed_file_bytes: int = 10_000_000,
    ) -> dict[str, Any]:
        checkpoint_id = f"{_utc_stamp()}-{uuid.uuid4().hex[:8]}"
        created_at = datetime.now(UTC).isoformat()
        branch = self._safe_git("branch")
        commit = self._safe_git("commit")
        changed = self._changed_files()
        file_evidence: list[dict[str, Any]] = []
        for rel in changed[:500]:
            path = self.root / rel
            try:
                safe = path.resolve(strict=True)
                safe.relative_to(self.root)
                if not safe.is_file():
                    continue
                size = safe.stat().st_size
                item: dict[str, Any] = {"path": rel, "size_bytes": size}
                if size <= max_hashed_file_bytes:
                    item["sha256"] = _sha256(safe)
                else:
                    item["sha256"] = None
                    item["hash_skipped"] = "file-too-large"
                file_evidence.append(item)
            except (OSError, ValueError):
                file_evidence.append({"path": rel, "unavailable": True})

        payload = {
            "schema": 1,
            "checkpoint_id": checkpoint_id,
            "created_at": created_at,
            "project": {
                "name": self.runtime.config.name,
                "repository": self.runtime.config.repository,
                "kind": detect_project_kind(self.root),
                "branch": branch,
                "commit": commit,
            },
            "label": label.strip()[:200],
            "note": redact(note.strip(), max_string=4000),
            "changed_files": file_evidence,
            "state": redact(
                {
                    "last_engine_plan": self.runtime.state.get_meta("last_engine_plan"),
                    "last_coordinator_run": self.runtime.state.get_meta("last_coordinator_run"),
                    "last_validation_gate": self.runtime.state.get_meta("last_validation_gate"),
                    "last_release_gate": self.runtime.state.get_meta("last_release_gate"),
                }
            ),
            "recent_events": redact(self.runtime.state.list_events(limit=50)),
        }
        target = self.directory / f"{checkpoint_id}.json"
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{checkpoint_id}.",
            suffix=".tmp",
            dir=self.directory,
        )
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

        self.runtime.state.record_event(
            "checkpoint.created",
            {
                "checkpoint_id": checkpoint_id,
                "changed_count": len(changed),
                "label": payload["label"],
            },
            agent="Coordinator",
        )
        self.runtime.state.set_meta("last_checkpoint_id", checkpoint_id)
        return payload

    def list(self, *, limit: int = 20) -> list[CheckpointInfo]:
        bounded = max(1, min(int(limit), 500))
        result: list[CheckpointInfo] = []
        for path in sorted(self.directory.glob("*.json"), reverse=True)[:bounded]:
            try:
                raw = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                continue
            project = raw.get("project") if isinstance(raw.get("project"), dict) else {}
            changed = raw.get("changed_files") if isinstance(raw.get("changed_files"), list) else []
            result.append(
                CheckpointInfo(
                    checkpoint_id=str(raw.get("checkpoint_id") or path.stem),
                    created_at=str(raw.get("created_at") or ""),
                    label=str(raw.get("label") or ""),
                    branch=project.get("branch"),
                    commit=project.get("commit"),
                    changed_count=len(changed),
                    path=str(path.relative_to(self.root)),
                )
            )
        return result

    def load(self, checkpoint_id: str) -> dict[str, Any]:
        if not _CHECKPOINT_ID.fullmatch(checkpoint_id):
            raise ValueError("Invalid checkpoint id")
        path = self.directory / f"{checkpoint_id}.json"
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise KeyError(f"Unknown checkpoint: {checkpoint_id}") from exc

    def latest(self) -> dict[str, Any] | None:
        items = self.list(limit=1)
        return self.load(items[0].checkpoint_id) if items else None

    def prune(self, *, keep: int = 20) -> int:
        keep = max(0, int(keep))
        paths = sorted(self.directory.glob("*.json"), reverse=True)
        removed = 0
        for path in paths[keep:]:
            try:
                path.unlink()
                removed += 1
            except FileNotFoundError:
                pass
        if removed:
            self.runtime.state.record_event(
                "checkpoint.pruned",
                {"removed": removed, "keep": keep},
                agent="Coordinator",
            )
        return removed

    def compact_resume(self, *, max_events: int = 20) -> dict[str, Any]:
        latest = self.latest()
        current = {
            "project": self.runtime.config.name,
            "repository": self.runtime.config.repository,
            "kind": detect_project_kind(self.root),
            "branch": self._safe_git("branch"),
            "commit": self._safe_git("commit"),
            "changed_files": self._changed_files()[:200],
            "permissions": sorted(p.value for p in self.runtime.config.permissions),
        }
        checkpoint_summary = None
        if latest:
            checkpoint_summary = {
                "checkpoint_id": latest.get("checkpoint_id"),
                "created_at": latest.get("created_at"),
                "label": latest.get("label"),
                "project": latest.get("project"),
                "changed_files": latest.get("changed_files", [])[:100],
                "state": latest.get("state"),
            }
        return redact(
            {
                "schema": 1,
                "current": current,
                "latest_checkpoint": checkpoint_summary,
                "recent_events": self.runtime.state.list_events(limit=max_events),
                "last_engine_plan": self.runtime.state.get_meta("last_engine_plan"),
                "last_coordinator_run": self.runtime.state.get_meta("last_coordinator_run"),
            },
            max_string=2500,
        )

    def _safe_git(self, operation: str) -> str | None:
        try:
            if operation == "branch":
                return self.runtime.git.branch()
            return self.runtime.git.commit()
        except Exception:
            return None

    def _changed_files(self) -> list[str]:
        try:
            return self.runtime.git.changed_files()
        except Exception:
            return []

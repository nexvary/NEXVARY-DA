from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(slots=True)
class TaskRecord:
    task_id: str
    title: str
    status: str
    updated_at: str


class ProjectState:
    """Durable operational state stored inside .nexvary-da/state.sqlite3."""

    SCHEMA_VERSION = 1

    def __init__(self, project_root: str | Path):
        root = Path(project_root).resolve(strict=True)
        state_dir = root / ".nexvary-da"
        state_dir.mkdir(parents=True, exist_ok=True)
        self.path = state_dir / "state.sqlite3"
        self._lock = threading.RLock()
        self._db = sqlite3.connect(self.path, check_same_thread=False)
        self._db.row_factory = sqlite3.Row
        self._migrate()

    def _migrate(self) -> None:
        with self._lock, self._db:
            self._db.executescript(
                """
                CREATE TABLE IF NOT EXISTS meta (
                    key TEXT PRIMARY KEY,
                    value TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    status TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    agent TEXT,
                    payload TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS gate_runs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    created_at TEXT NOT NULL,
                    ready INTEGER NOT NULL,
                    report TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS agent_slots (
                    role TEXT PRIMARY KEY,
                    worker_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    last_task TEXT,
                    updated_at TEXT NOT NULL
                );
                """
            )
        self.set_meta("schema_version", self.SCHEMA_VERSION)

    def close(self) -> None:
        with self._lock:
            self._db.close()

    def set_meta(self, key: str, value: Any) -> None:
        encoded = json.dumps(value, ensure_ascii=False, sort_keys=True)
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO meta(key, value, updated_at) VALUES (?, ?, ?)
                ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
                """,
                (key, encoded, _now()),
            )

    def get_meta(self, key: str, default: Any = None) -> Any:
        with self._lock:
            row = self._db.execute("SELECT value FROM meta WHERE key=?", (key,)).fetchone()
        return default if row is None else json.loads(row["value"])

    def upsert_task(self, task_id: str, title: str, status: str) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO tasks(task_id, title, status, updated_at) VALUES (?, ?, ?, ?)
                ON CONFLICT(task_id) DO UPDATE SET
                    title=excluded.title, status=excluded.status, updated_at=excluded.updated_at
                """,
                (task_id, title, status, _now()),
            )

    def list_tasks(self) -> list[TaskRecord]:
        with self._lock:
            rows = self._db.execute(
                "SELECT task_id, title, status, updated_at FROM tasks ORDER BY updated_at DESC"
            ).fetchall()
        return [TaskRecord(**dict(row)) for row in rows]

    def record_event(self, kind: str, payload: dict[str, Any], agent: str | None = None) -> int:
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO events(created_at, kind, agent, payload) VALUES (?, ?, ?, ?)",
                (_now(), kind, agent, json.dumps(payload, ensure_ascii=False, sort_keys=True)),
            )
            return int(cur.lastrowid)

    def record_gate(self, ready: bool, report: dict[str, Any]) -> int:
        with self._lock, self._db:
            cur = self._db.execute(
                "INSERT INTO gate_runs(created_at, ready, report) VALUES (?, ?, ?)",
                (_now(), int(ready), json.dumps(report, ensure_ascii=False, sort_keys=True)),
            )
            return int(cur.lastrowid)

    def save_agent_slot(
        self, role: str, worker_id: str, status: str, last_task: str | None = None
    ) -> None:
        with self._lock, self._db:
            self._db.execute(
                """
                INSERT INTO agent_slots(role, worker_id, status, last_task, updated_at)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(role) DO UPDATE SET
                    worker_id=excluded.worker_id,
                    status=excluded.status,
                    last_task=excluded.last_task,
                    updated_at=excluded.updated_at
                """,
                (role, worker_id, status, last_task, _now()),
            )

    def load_agent_slots(self) -> list[dict[str, Any]]:
        with self._lock:
            rows = self._db.execute(
                "SELECT role, worker_id, status, last_task, updated_at FROM agent_slots"
            ).fetchall()
        return [dict(row) for row in rows]

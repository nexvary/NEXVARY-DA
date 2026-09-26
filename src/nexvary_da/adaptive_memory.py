from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import urllib.error
import urllib.request
from typing import Any


@dataclass(frozen=True, slots=True)
class Experience:
    kind: str
    summary: str
    data: dict[str, Any]
    created_at: str

    @classmethod
    def create(cls, kind: str, summary: str, data: dict[str, Any]) -> "Experience":
        return cls(kind, summary, data, datetime.now(timezone.utc).isoformat())


class AdaptiveMemory:
    """Fail-open memory layer: Hindsight when configured, local JSONL always."""

    def __init__(self, root: Path, *, bank_id: str = "nexvary-da"):
        self.root = Path(root)
        self.bank_id = bank_id
        self.base_url = os.getenv("NEXVARY_HINDSIGHT_URL", "").rstrip("/")
        self.local_file = self.root / ".nexvary-da" / "memory" / "experiences.jsonl"

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        if not self.base_url:
            return None
        request = urllib.request.Request(
            self.base_url + path,
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=3) as response:
                return json.loads(response.read().decode("utf-8"))
        except (OSError, urllib.error.URLError, ValueError):
            return None

    def retain(self, kind: str, summary: str, data: dict[str, Any]) -> Experience:
        item = Experience.create(kind, summary, data)
        self.local_file.parent.mkdir(parents=True, exist_ok=True)
        with self.local_file.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(asdict(item), ensure_ascii=False) + "\n")
        # Hindsight is intentionally best-effort: it can never block a render.
        self._post(
            f"/v1/default/banks/{self.bank_id}/memories",
            {"items": [{"content": summary, "metadata": {"kind": kind, **data}}]},
        )
        return item

    def recall_local(self, query: str, *, limit: int = 8) -> list[Experience]:
        if not self.local_file.exists():
            return []
        tokens = {part.lower() for part in query.split() if len(part) > 2}
        scored: list[tuple[int, Experience]] = []
        for line in self.local_file.read_text(encoding="utf-8").splitlines():
            try:
                raw = json.loads(line)
                item = Experience(**raw)
            except (ValueError, TypeError):
                continue
            haystack = (item.summary + " " + json.dumps(item.data, ensure_ascii=False)).lower()
            score = sum(token in haystack for token in tokens)
            if score or not tokens:
                scored.append((score, item))
        scored.sort(key=lambda pair: (pair[0], pair[1].created_at), reverse=True)
        return [item for _, item in scored[:limit]]

    def recall(self, query: str, *, limit: int = 8) -> list[dict[str, Any]]:
        remote = self._post(
            f"/v1/default/banks/{self.bank_id}/memories/recall",
            {"query": query, "max_tokens": 2048},
        )
        if remote:
            return [{"source": "hindsight", "payload": remote}]
        return [{"source": "local", "payload": asdict(item)}
                for item in self.recall_local(query, limit=limit)]

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import StrEnum
import json
from pathlib import Path
from typing import Iterable


class Trust(StrEnum):
    UNVERIFIED = "unverified"
    REVIEWED = "reviewed"
    APPROVED = "approved"


@dataclass(frozen=True, slots=True)
class Capability:
    name: str
    kind: str
    categories: tuple[str, ...]
    endpoint: str = ""
    local: bool = False
    requires_key: bool = False
    paid: bool = False
    privacy: str = "unknown"
    license: str = "unknown"
    source: str = ""
    trust: Trust = Trust.UNVERIFIED

    @classmethod
    def from_dict(cls, raw: dict) -> "Capability":
        return cls(
            name=str(raw.get("name", "")).strip(),
            kind=str(raw.get("kind", "api")).lower(),
            categories=tuple(str(x).lower() for x in raw.get("categories", [])),
            endpoint=str(raw.get("endpoint", "")),
            local=bool(raw.get("local", False)),
            requires_key=bool(raw.get("requires_key", False)),
            paid=bool(raw.get("paid", False)),
            privacy=str(raw.get("privacy", "unknown")),
            license=str(raw.get("license", "unknown")),
            source=str(raw.get("source", "")),
            trust=Trust(str(raw.get("trust", Trust.UNVERIFIED.value))),
        )


@dataclass(frozen=True, slots=True)
class DiscoveryMatch:
    capability: Capability
    score: int
    executable: bool
    reasons: tuple[str, ...]

    def to_dict(self) -> dict:
        data = asdict(self)
        data["capability"]["trust"] = self.capability.trust.value
        return data


class CapabilityCatalog:
    """Read-only discovery index. Discovery never grants execution permission."""

    def __init__(self, items: Iterable[Capability] = ()):
        self.items = list(items)

    @classmethod
    def load(cls, path: Path) -> "CapabilityCatalog":
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        return cls(Capability.from_dict(item) for item in raw.get("capabilities", []))

    def discover(
        self, query: str, *, prefer_local: bool = True, allow_paid: bool = False
    ) -> list[DiscoveryMatch]:
        terms = {x.lower() for x in query.replace("/", " ").replace("-", " ").split() if len(x) > 1}
        matches: list[DiscoveryMatch] = []
        for item in self.items:
            hay = " ".join((item.name, item.kind, *item.categories)).lower()
            overlap = sum(term in hay for term in terms)
            if not overlap:
                continue
            score = overlap * 20
            reasons = [f"matched {overlap} query term(s)"]
            if prefer_local and item.local:
                score += 15
                reasons.append("local execution preferred")
            if item.paid and not allow_paid:
                score -= 25
                reasons.append("paid service penalized")
            if item.privacy.lower() in {"local", "private"}:
                score += 10
                reasons.append("privacy-friendly")
            if item.trust == Trust.APPROVED:
                score += 20
                reasons.append("approved")
            elif item.trust == Trust.UNVERIFIED:
                score -= 20
                reasons.append("unverified source")
            # Hard execution gate: discovery alone can never authorize a provider.
            executable = item.trust == Trust.APPROVED
            matches.append(DiscoveryMatch(item, score, executable, tuple(reasons)))
        return sorted(matches, key=lambda m: (-m.score, m.capability.name.lower()))

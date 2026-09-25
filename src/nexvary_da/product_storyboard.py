from __future__ import annotations

import copy
import json
import math
import uuid
from dataclasses import asdict, dataclass
from enum import StrEnum
from pathlib import Path
from typing import Any, Iterable


class StoryboardSceneKind(StrEnum):
    PRODUCT = "product"
    REAL_VIDEO = "real_video"
    AI_SUPPORT = "ai_support"
    INSTRUCTION = "instruction"
    VERIFIED_FACT = "verified_fact"
    OPERATION = "operation"
    CTA = "cta"


_DEFAULT_DURATIONS = {
    StoryboardSceneKind.PRODUCT: 4.0,
    StoryboardSceneKind.REAL_VIDEO: 6.0,
    StoryboardSceneKind.AI_SUPPORT: 4.5,
    StoryboardSceneKind.INSTRUCTION: 5.0,
    StoryboardSceneKind.VERIFIED_FACT: 4.0,
    StoryboardSceneKind.OPERATION: 6.0,
    StoryboardSceneKind.CTA: 4.0,
}


@dataclass(slots=True)
class StoryboardScene:
    scene_id: str
    title: str
    kind: str
    material: str
    narration: str = ""
    duration_seconds: float = 4.0
    thumbnail: str = ""
    source: str = ""
    evidence_label: str = ""
    enabled: bool = True

    @classmethod
    def create(
        cls,
        *,
        title: str,
        kind: StoryboardSceneKind | str,
        material: str | Path,
        narration: str = "",
        duration_seconds: float | None = None,
        thumbnail: str | Path | None = None,
        source: str | Path | None = None,
        evidence_label: str = "",
        enabled: bool = True,
    ) -> "StoryboardScene":
        target_kind = StoryboardSceneKind(kind)
        duration = (
            _DEFAULT_DURATIONS[target_kind]
            if duration_seconds is None
            else float(duration_seconds)
        )
        return cls(
            scene_id=uuid.uuid4().hex,
            title=str(title).strip() or "Scene",
            kind=target_kind.value,
            material=str(material),
            narration=str(narration).strip(),
            duration_seconds=max(1.0, min(30.0, duration)),
            thumbnail=str(thumbnail or ""),
            source=str(source or ""),
            evidence_label=str(evidence_label).strip(),
            enabled=bool(enabled),
        )

    def normalized(self) -> "StoryboardScene":
        target_kind = StoryboardSceneKind(self.kind)
        return StoryboardScene(
            scene_id=(self.scene_id or uuid.uuid4().hex).strip(),
            title=(self.title or "Scene").strip(),
            kind=target_kind.value,
            material=str(self.material).strip(),
            narration=str(self.narration).strip(),
            duration_seconds=max(1.0, min(30.0, float(self.duration_seconds))),
            thumbnail=str(self.thumbnail).strip(),
            source=str(self.source).strip(),
            evidence_label=str(self.evidence_label).strip(),
            enabled=bool(self.enabled),
        )

    def clone(self) -> "StoryboardScene":
        cloned = copy.deepcopy(self.normalized())
        cloned.scene_id = uuid.uuid4().hex
        cloned.title = f"{cloned.title} — Copy"
        return cloned

    def to_dict(self) -> dict[str, Any]:
        return asdict(self.normalized())

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "StoryboardScene":
        return cls(
            scene_id=str(raw.get("scene_id") or uuid.uuid4().hex),
            title=str(raw.get("title") or "Scene"),
            kind=str(raw.get("kind") or StoryboardSceneKind.PRODUCT.value),
            material=str(raw.get("material") or ""),
            narration=str(raw.get("narration") or ""),
            duration_seconds=float(raw.get("duration_seconds") or 4.0),
            thumbnail=str(raw.get("thumbnail") or ""),
            source=str(raw.get("source") or ""),
            evidence_label=str(raw.get("evidence_label") or ""),
            enabled=bool(raw.get("enabled", True)),
        ).normalized()


class ProductStoryboard:
    VERSION = 1

    def __init__(self, scenes: Iterable[StoryboardScene] = ()):
        self.scenes: list[StoryboardScene] = [scene.normalized() for scene in scenes]

    def __len__(self) -> int:
        return len(self.scenes)

    def scene(self, index: int) -> StoryboardScene:
        return self.scenes[index]

    def add(self, scene: StoryboardScene, *, index: int | None = None) -> None:
        target = scene.normalized()
        if index is None:
            self.scenes.append(target)
        else:
            self.scenes.insert(max(0, min(len(self.scenes), int(index))), target)

    def move(self, index: int, offset: int) -> int:
        if not self.scenes:
            return 0
        current = max(0, min(len(self.scenes) - 1, int(index)))
        target = max(0, min(len(self.scenes) - 1, current + int(offset)))
        if target != current:
            self.scenes[current], self.scenes[target] = self.scenes[target], self.scenes[current]
        return target

    def duplicate(self, index: int) -> int:
        if not self.scenes:
            raise IndexError("Storyboard is empty")
        current = max(0, min(len(self.scenes) - 1, int(index)))
        self.scenes.insert(current + 1, self.scenes[current].clone())
        return current + 1

    def delete(self, index: int) -> int:
        if not self.scenes:
            return 0
        current = max(0, min(len(self.scenes) - 1, int(index)))
        del self.scenes[current]
        return max(0, min(len(self.scenes) - 1, current))

    def enabled_scenes(self) -> list[StoryboardScene]:
        return [scene for scene in self.scenes if scene.enabled and scene.material]

    def total_seconds(self) -> float:
        return round(sum(scene.duration_seconds for scene in self.enabled_scenes()), 3)

    def script_text(self) -> str:
        return " ".join(
            scene.narration.strip()
            for scene in self.enabled_scenes()
            if scene.narration.strip()
        ).strip()

    def fit_to_target(self, target_seconds: float) -> None:
        enabled = self.enabled_scenes()
        if not enabled:
            return
        target = max(float(len(enabled)), min(180.0, float(target_seconds)))
        current = sum(scene.duration_seconds for scene in enabled)
        if current <= 0:
            each = target / len(enabled)
            for scene in enabled:
                scene.duration_seconds = max(1.0, min(30.0, each))
            return

        scale = target / current
        remaining = target
        for index, scene in enumerate(enabled):
            if index == len(enabled) - 1:
                value = remaining
            else:
                value = scene.duration_seconds * scale
            value = max(1.0, min(30.0, value))
            scene.duration_seconds = round(value, 3)
            remaining -= scene.duration_seconds

        drift = target - sum(scene.duration_seconds for scene in enabled)
        if abs(drift) >= 0.001:
            last = enabled[-1]
            last.duration_seconds = round(
                max(1.0, min(30.0, last.duration_seconds + drift)),
                3,
            )

    def validation_issues(self, *, require_files: bool = False) -> list[str]:
        issues: list[str] = []
        seen_ids: set[str] = set()
        enabled = self.enabled_scenes()
        if not enabled:
            issues.append("Storyboard has no enabled scenes")
        for index, scene in enumerate(self.scenes, 1):
            if scene.scene_id in seen_ids:
                issues.append(f"Scene {index} has a duplicate scene_id")
            seen_ids.add(scene.scene_id)
            if not scene.title.strip():
                issues.append(f"Scene {index} has no title")
            if scene.enabled and not scene.material.strip():
                issues.append(f"Scene {index} has no material")
            if scene.enabled and not 1.0 <= float(scene.duration_seconds) <= 30.0:
                issues.append(f"Scene {index} duration is outside 1-30 seconds")
            if require_files and scene.enabled and scene.material:
                if not Path(scene.material).is_file():
                    issues.append(f"Scene {index} material is missing: {scene.material}")
            if scene.kind == StoryboardSceneKind.AI_SUPPORT.value:
                label = scene.evidence_label.upper()
                if "AI" not in label:
                    issues.append(f"Scene {index} AI material is not explicitly labelled")
            if scene.kind == StoryboardSceneKind.REAL_VIDEO.value:
                label = scene.evidence_label.upper()
                if "REAL" not in label:
                    issues.append(f"Scene {index} real footage is not explicitly labelled")
        total = self.total_seconds()
        if enabled and not 15.0 <= total <= 180.0:
            issues.append(f"Storyboard duration {total:.1f}s is outside 15-180 seconds")
        return issues

    def ready_for_render(self, *, require_files: bool = False) -> bool:
        return not self.validation_issues(require_files=require_files)

    def to_dict(self, *, metadata: dict[str, Any] | None = None) -> dict[str, Any]:
        return {
            "version": self.VERSION,
            "metadata": dict(metadata or {}),
            "scenes": [scene.to_dict() for scene in self.scenes],
        }

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> "ProductStoryboard":
        version = int(raw.get("version") or 1)
        if version != cls.VERSION:
            raise ValueError(f"Unsupported storyboard version: {version}")
        scenes = raw.get("scenes")
        if not isinstance(scenes, list):
            raise ValueError("Storyboard scenes must be a list")
        return cls(StoryboardScene.from_dict(item) for item in scenes if isinstance(item, dict))

    def save(self, path: str | Path, *, metadata: dict[str, Any] | None = None) -> Path:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(self.to_dict(metadata=metadata), ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        return target

    @classmethod
    def load(cls, path: str | Path) -> tuple["ProductStoryboard", dict[str, Any]]:
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            raise ValueError("Storyboard project must contain a JSON object")
        storyboard = cls.from_dict(raw)
        metadata = raw.get("metadata") if isinstance(raw.get("metadata"), dict) else {}
        return storyboard, dict(metadata)


def split_narration_for_scenes(text: str, scene_count: int) -> list[str]:
    count = max(0, int(scene_count))
    if count <= 0:
        return []
    words = str(text).split()
    if not words:
        return ["" for _ in range(count)]

    target = max(1, math.ceil(len(words) / count))
    chunks: list[str] = []
    cursor = 0
    for index in range(count):
        remaining_scenes = count - index
        remaining_words = len(words) - cursor
        if remaining_scenes <= 1:
            take = remaining_words
        else:
            take = min(target, max(1, remaining_words - (remaining_scenes - 1)))
        chunks.append(" ".join(words[cursor : cursor + take]).strip())
        cursor += take
    if cursor < len(words):
        chunks[-1] = (chunks[-1] + " " + " ".join(words[cursor:])).strip()
    return chunks

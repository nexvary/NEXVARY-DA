from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from .hardware_profile import HardwareProfile


class SceneExecution(StrEnum):
    REAL = "real"
    PHOTO_MOTION = "photo-motion"
    AI_SHORT = "ai-short"
    GRAPHICS = "graphics"


@dataclass(frozen=True, slots=True)
class ComputeBudget:
    tier: str
    ai_seconds: int
    backend_order: tuple[str, ...]
    max_ai_clip_seconds: int
    reason: str


class ComputeBudgetDirector:
    """Keeps long ads practical by spending generative compute only where it adds value."""

    @staticmethod
    def plan(profile: HardwareProfile, target_seconds: int) -> ComputeBudget:
        target = max(15, int(target_seconds))
        if profile.tier == "DIRECT":
            return ComputeBudget("DIRECT", 0, ("direct",), 0,
                                 "No suitable local CUDA budget; preserve the ad via FFmpeg composition.")
        if profile.tier == "ECO":
            return ComputeBudget("ECO", min(4, target // 10), ("ltx-2b", "cogvideox-2b", "direct"), 2,
                                 "Small VRAM budget: one or two short AI accents only.")
        if profile.tier == "HYBRID":
            return ComputeBudget("HYBRID", min(10, target // 6), ("wangp", "ltx-2b", "cogvideox-2b", "direct"), 4,
                                 "Use real media for most of the ad and short low-VRAM AI inserts.")
        if profile.tier == "LOCAL_AI":
            return ComputeBudget("LOCAL_AI", min(18, target // 4), ("wangp", "ltx", "direct"), 6,
                                 "Local GPU can carry several short generative scenes.")
        return ComputeBudget("MAX", min(30, target // 2), ("wangp", "ltx", "direct"), 8,
                             "High VRAM budget while retaining evidence-first real media.")

    @staticmethod
    def classify(*, has_real_video: bool, has_product_image: bool, needs_explainer: bool,
                 ai_seconds_remaining: int) -> SceneExecution:
        if has_real_video:
            return SceneExecution.REAL
        if needs_explainer:
            return SceneExecution.GRAPHICS
        if has_product_image and ai_seconds_remaining <= 0:
            return SceneExecution.PHOTO_MOTION
        if ai_seconds_remaining > 0:
            return SceneExecution.AI_SHORT
        return SceneExecution.PHOTO_MOTION

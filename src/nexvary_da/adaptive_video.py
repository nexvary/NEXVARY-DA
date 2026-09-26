from __future__ import annotations

from dataclasses import dataclass

from .compute_budget import ComputeBudget, ComputeBudgetDirector
from .hardware_profile import HardwareProfile, detect_hardware


@dataclass(frozen=True, slots=True)
class AdaptiveVideoPlan:
    hardware: HardwareProfile
    budget: ComputeBudget

    def to_dict(self) -> dict[str, object]:
        return {
            "hardware": self.hardware.to_dict(),
            "budget": {
                "tier": self.budget.tier,
                "ai_seconds": self.budget.ai_seconds,
                "backend_order": list(self.budget.backend_order),
                "max_ai_clip_seconds": self.budget.max_ai_clip_seconds,
                "reason": self.budget.reason,
            },
        }


class AdaptiveVideoRouter:
    """Capability router. Backends are optional; Direct Renderer is always the terminal fallback."""

    def plan(self, target_seconds: int, profile: HardwareProfile | None = None) -> AdaptiveVideoPlan:
        hardware = profile or detect_hardware()
        return AdaptiveVideoPlan(hardware, ComputeBudgetDirector.plan(hardware, target_seconds))

    @staticmethod
    def next_backend(plan: AdaptiveVideoPlan, failed: tuple[str, ...] = ()) -> str:
        failed_set = set(failed)
        for backend in plan.budget.backend_order:
            if backend not in failed_set:
                return backend
        return "direct"

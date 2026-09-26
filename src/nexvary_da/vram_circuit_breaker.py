from __future__ import annotations

from dataclasses import dataclass


_OOM_MARKERS = (
    "out of memory",
    "cuda oom",
    "cuda error: out of memory",
    "cublas_status_alloc_failed",
    "allocation failed",
)


@dataclass(frozen=True, slots=True)
class RecoveryDecision:
    retry: bool
    backend_failed: bool
    resolution_scale: float
    frame_scale: float
    reason: str


class VRAMCircuitBreaker:
    """Turns GPU memory failures into bounded degradation instead of a dead render."""

    def decide(self, error: BaseException | str, attempt: int) -> RecoveryDecision:
        message = str(error).lower()
        oom = any(marker in message for marker in _OOM_MARKERS)
        if not oom:
            return RecoveryDecision(False, True, 1.0, 1.0, "backend-error")
        if attempt <= 0:
            return RecoveryDecision(True, False, 0.75, 0.75, "oom-retry-75pct")
        if attempt == 1:
            return RecoveryDecision(True, False, 0.5, 0.5, "oom-retry-50pct")
        return RecoveryDecision(False, True, 0.5, 0.5, "oom-switch-backend")

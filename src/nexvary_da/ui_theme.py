from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    background: str = "#0B1016"
    surface: str = "#111923"
    surface_alt: str = "#16212D"
    border: str = "#2D3946"
    gold: str = "#D4AF37"
    gold_dim: str = "#8D7529"
    blue: str = "#6A88A0"
    blue_bright: str = "#8EB5D1"
    text: str = "#E8EDF2"
    muted: str = "#8F9CAA"
    success: str = "#58B487"
    warning: str = "#D7A947"
    danger: str = "#D66B6B"
    terminal: str = "#070A0E"


PALETTE = Palette()


def scale_for_screen(width: int, height: int) -> float:
    """Conservative UI scale tuned for laptop through QHD desktop screens."""
    if width >= 2400 or height >= 1350:
        return 1.18
    if width >= 1800 or height >= 1050:
        return 1.08
    if width <= 1100 or height <= 700:
        return 0.92
    return 1.0


def scaled(value: int, factor: float) -> int:
    return max(1, int(round(value * factor)))


def status_color(status: str) -> str:
    normalized = status.strip().upper()
    if normalized in {"PASS", "READY", "SUCCESS", "ONLINE", "IDLE"}:
        return PALETTE.success
    if normalized in {"RUNNING", "WORKING", "PENDING"}:
        return PALETTE.blue_bright
    if normalized in {"WARN", "WARNING", "SKIP", "NOT_CONFIGURED"}:
        return PALETTE.warning
    if normalized in {"FAIL", "FAILED", "ERROR", "BLOCKED"}:
        return PALETTE.danger
    return PALETTE.muted

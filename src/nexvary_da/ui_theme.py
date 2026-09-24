from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class Palette:
    # Deep chassis
    background: str = "#050910"
    surface: str = "#0A111A"
    surface_alt: str = "#0F1A26"
    surface_glow: str = "#132333"
    terminal: str = "#020509"

    # Chrome / silver frame system
    border: str = "#5F6D7B"
    silver: str = "#AEBBC8"
    silver_bright: str = "#E4EDF5"
    platinum: str = "#CAD5DF"

    # Neon / electric spectrum
    cyan: str = "#18E7FF"
    blue: str = "#4D8DFF"
    blue_bright: str = "#79B8FF"
    purple: str = "#9C5CFF"
    magenta: str = "#FF4FD8"
    orange: str = "#FF8A3D"
    yellow: str = "#FFE66D"
    gold: str = "#F4C84B"
    gold_dim: str = "#9E8130"

    # Green is intentionally reserved for press/action affordances.
    action: str = "#39FF88"
    action_hover: str = "#7CFFB2"
    action_dark: str = "#062D1B"

    # Semantic state colors do not use action green.
    success: str = "#20D9F2"
    warning: str = "#FFB347"
    danger: str = "#FF5C73"

    text: str = "#F2F7FB"
    muted: str = "#91A2B3"


PALETTE = Palette()


_SECTION_COLORS = {
    "project": PALETTE.cyan,
    "task": PALETTE.cyan,
    "build": PALETTE.blue,
    "desktop": PALETTE.blue,
    "tools": PALETTE.purple,
    "browser": PALETTE.purple,
    "media": PALETTE.magenta,
    "image": PALETTE.magenta,
    "video": PALETTE.orange,
    "voice": PALETTE.yellow,
    "mcp": PALETTE.cyan,
    "release": PALETTE.orange,
    "advanced": PALETTE.silver_bright,
}


def section_color(name: str) -> str:
    return _SECTION_COLORS.get(name.strip().lower(), PALETTE.blue_bright)


def scale_for_screen(width: int, height: int) -> float:
    """Conservative UI scale tuned for laptop through QHD desktop screens."""
    if width >= 2400 or height >= 1350:
        return 1.18
    if width >= 1800 or height >= 1050:
        return 1.08
    if width <= 1366 or height <= 850:
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

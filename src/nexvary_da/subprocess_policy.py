from __future__ import annotations

import os
import subprocess
from typing import Any


def hidden_window_kwargs() -> dict[str, Any]:
    """Prevent child-process console flashes in the Windows GUI build."""
    if os.name != "nt":
        return {}
    startupinfo = subprocess.STARTUPINFO()
    startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
    startupinfo.wShowWindow = subprocess.SW_HIDE
    return {
        "startupinfo": startupinfo,
        "creationflags": int(getattr(subprocess, "CREATE_NO_WINDOW", 0)),
    }

from __future__ import annotations

import re
from typing import Any


_SENSITIVE_KEY = re.compile(
    r"(?:token|secret|password|passwd|api[_-]?key|authorization|credential|cookie)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"\bBearer\s+[A-Za-z0-9._~+/\-=]{8,}", re.IGNORECASE)
_GITHUB = re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b")


def redact(value: Any, *, max_string: int = 4000) -> Any:
    """Best-effort redaction for durable operational snapshots."""
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, child in value.items():
            name = str(key)
            if _SENSITIVE_KEY.search(name):
                result[name] = "[REDACTED]"
            else:
                result[name] = redact(child, max_string=max_string)
        return result
    if isinstance(value, list):
        return [redact(item, max_string=max_string) for item in value]
    if isinstance(value, tuple):
        return [redact(item, max_string=max_string) for item in value]
    if isinstance(value, str):
        text = _BEARER.sub("Bearer [REDACTED]", value)
        text = _GITHUB.sub("[REDACTED_GITHUB_TOKEN]", text)
        if len(text) > max_string:
            return text[:max_string] + f"...[truncated {len(text) - max_string} chars]"
        return text
    if value is None or isinstance(value, (bool, int, float)):
        return value
    return str(value)

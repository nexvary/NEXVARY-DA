from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True, slots=True)
class SigningReadiness:
    platform: str
    applicable: bool
    tool: str | None
    credentials_present: bool
    ready: bool
    missing: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def inspect_signing_readiness(platform_name: str | None = None) -> SigningReadiness:
    platform_name = (platform_name or os.name).lower()
    missing: list[str] = []

    if platform_name in {"nt", "windows", "win32"}:
        tool = shutil.which("signtool") or os.environ.get("NEXVARY_SIGNTOOL_PATH")
        pfx = os.environ.get("NEXVARY_WINDOWS_SIGN_PFX", "").strip()
        password = os.environ.get("NEXVARY_WINDOWS_SIGN_PASSWORD", "").strip()
        if not tool:
            missing.append("signtool")
        if not pfx:
            missing.append("NEXVARY_WINDOWS_SIGN_PFX")
        elif not Path(pfx).expanduser().is_file():
            missing.append("signing-certificate-file")
        if not password:
            missing.append("NEXVARY_WINDOWS_SIGN_PASSWORD")
        credentials = bool(pfx and password)
        return SigningReadiness(
            "windows",
            True,
            tool,
            credentials,
            not missing,
            tuple(missing),
        )

    if platform_name in {"posix", "linux"}:
        tool = shutil.which("gpg")
        key_id = os.environ.get("NEXVARY_GPG_KEY_ID", "").strip()
        if not tool:
            missing.append("gpg")
        if not key_id:
            missing.append("NEXVARY_GPG_KEY_ID")
        return SigningReadiness(
            "linux",
            True,
            tool,
            bool(key_id),
            not missing,
            tuple(missing),
        )

    return SigningReadiness(
        platform_name,
        False,
        None,
        False,
        False,
        ("unsupported-platform",),
    )

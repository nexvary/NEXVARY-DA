from __future__ import annotations

import sqlite3
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .android_qa import audit_android_project
from .build_profiles import profile_for
from .environment import discover_environment, detect_project_kind


@dataclass(frozen=True, slots=True)
class DoctorCheck:
    name: str
    status: str
    details: str


def run_project_doctor(runtime) -> dict[str, Any]:
    checks: list[DoctorCheck] = []
    environment = discover_environment()
    kind = detect_project_kind(runtime.root)
    profile = profile_for(runtime.root)

    checks.append(
        DoctorCheck(
            "project_config",
            "PASS",
            f"{runtime.config.name}; {len(runtime.config.permissions)} permission(s)",
        )
    )
    checks.append(
        DoctorCheck(
            "build_profile",
            "PASS" if profile is not None else "WARN",
            profile.kind if profile else f"No explicit build profile for {kind}",
        )
    )

    try:
        with sqlite3.connect(runtime.state.path) as db:
            row = db.execute("PRAGMA quick_check").fetchone()
        db_ok = bool(row and row[0] == "ok")
        checks.append(DoctorCheck("state_database", "PASS" if db_ok else "FAIL", str(row[0] if row else "no result")))
    except sqlite3.Error as exc:
        checks.append(DoctorCheck("state_database", "FAIL", str(exc)))

    zcode = runtime.zcode().status(probe_version=False)
    checks.append(
        DoctorCheck(
            "zcode",
            "PASS" if zcode.available else "INFO",
            zcode.executable or "Optional ZCode CLI not found",
        )
    )

    android = audit_android_project(runtime.root)
    if android.applicable:
        error_count = sum(1 for issue in android.issues if issue.severity == "error")
        warning_count = sum(1 for issue in android.issues if issue.severity == "warning")
        checks.append(
            DoctorCheck(
                "android_static_qa",
                "PASS" if android.ready else "FAIL",
                f"{error_count} error(s), {warning_count} warning(s)",
            )
        )
    else:
        checks.append(DoctorCheck("android_static_qa", "INFO", "Not an Android source tree"))

    shell_tool = environment.get("tools", {}).get("git", {})
    checks.append(
        DoctorCheck(
            "git_tool",
            "PASS" if shell_tool.get("available") else "WARN",
            str(shell_tool.get("version") or "Git not discovered"),
        )
    )

    overall = "FAIL" if any(c.status == "FAIL" for c in checks) else "PASS"
    payload = {
        "overall": overall,
        "project_kind": kind,
        "checks": [asdict(check) for check in checks],
    }
    runtime.state.set_meta("last_doctor_run", payload)
    runtime.state.record_event(
        "doctor.run",
        {"overall": overall, "check_count": len(checks)},
        agent="Coordinator",
    )
    return payload

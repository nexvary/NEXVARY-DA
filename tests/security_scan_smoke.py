from __future__ import annotations

import json
from pathlib import Path

from nexvary_da.release_gate import _scan_secrets
from nexvary_da.source_audit import audit_python_sources


def main() -> int:
    root = Path(".").resolve()
    findings = audit_python_sources(root)
    severe = [
        {
            "path": item.path,
            "line": item.line,
            "severity": item.severity,
            "code": item.code,
            "message": item.message,
        }
        for item in findings
        if item.severity in {"critical", "high"}
    ]
    secrets = _scan_secrets(root)
    report = {
        "ready": not severe and not secrets,
        "high_or_critical_source_findings": severe,
        "secret_pattern_findings": secrets,
        "review_level_source_findings": sum(
            1 for item in findings if item.severity not in {"critical", "high"}
        ),
    }
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0 if report["ready"] else 2


if __name__ == "__main__":
    raise SystemExit(main())

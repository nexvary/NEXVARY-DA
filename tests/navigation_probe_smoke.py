from __future__ import annotations

import json
import tempfile
from pathlib import Path

from nexvary_da.navigation_probe import run_navigation_probe
from nexvary_da.permissions import Permission
from nexvary_da.project import init_project


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            "[project]\nname='navigation-probe-smoke'\nversion='0'\n",
            encoding="utf-8",
        )
        init_project(
            root,
            name="Navigation Probe Smoke",
            permissions={
                Permission.READ,
                Permission.WRITE,
                Permission.SHELL,
                Permission.DESKTOP_AUTOMATION,
            },
        )
        report = run_navigation_probe(root)
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

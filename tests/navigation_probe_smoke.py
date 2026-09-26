from __future__ import annotations

import argparse
import json
import tempfile
from pathlib import Path

from nexvary_da.navigation_probe import run_navigation_probe
from nexvary_da.permissions import Permission
from nexvary_da.project import init_project


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=900)
    args = parser.parse_args()

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
        report = run_navigation_probe(root, width=args.width, height=args.height)
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

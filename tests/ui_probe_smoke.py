from __future__ import annotations

import argparse
import json
import shutil
import tempfile
from pathlib import Path

from nexvary_da.permissions import Permission
from nexvary_da.project import init_project
from nexvary_da.ui_probe import run_runtime_ui_probe


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--screenshot-output", default="")
    parser.add_argument("--require-screenshot", action="store_true")
    args = parser.parse_args()

    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        (root / "pyproject.toml").write_text(
            "[project]\nname='ui-probe-smoke'\nversion='0'\n",
            encoding="utf-8",
        )
        init_project(
            root,
            name="UI Probe Smoke",
            permissions={
                Permission.READ,
                Permission.WRITE,
                Permission.SHELL,
                Permission.DESKTOP_AUTOMATION,
            },
        )
        screenshot_rel = ".nexvary-da/ui-probe.png" if args.screenshot_output else None
        report = run_runtime_ui_probe(
            root,
            width=1600,
            height=900,
            screenshot=screenshot_rel,
            require_screenshot=args.require_screenshot,
        )
        print(json.dumps(report.to_dict(), indent=2, ensure_ascii=False))
        if args.screenshot_output and report.screenshot.path:
            shutil.copy2(report.screenshot.path, args.screenshot_output)
        return 0 if report.ready else 2


if __name__ == "__main__":
    raise SystemExit(main())

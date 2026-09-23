from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> int:
    exe = Path("dist-native") / ("NEXVARY-DA.exe" if sys.platform == "win32" else "NEXVARY-DA")
    if not exe.is_file():
        raise SystemExit(f"missing executable: {exe}")
    completed = subprocess.run(
        [str(exe.resolve()), "--help"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        errors="replace",
        timeout=60,
        check=False,
    )
    print(completed.stdout)
    if completed.returncode != 0:
        return completed.returncode
    if "nexvary-da" not in completed.stdout.lower():
        raise SystemExit("native executable help did not identify nexvary-da")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

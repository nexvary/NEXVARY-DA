from __future__ import annotations

import sys

from nexvary_da.cli import main


if __name__ == "__main__":
    argv = sys.argv[1:]
    if not argv:
        argv = ["ui", "."]
    raise SystemExit(main(argv))

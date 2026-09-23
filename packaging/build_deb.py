from __future__ import annotations

import platform
import shutil
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
EXE = ROOT / "dist-native" / "NEXVARY-DA"
OUT = ROOT / "release-native"


def main() -> int:
    if not EXE.is_file():
        raise SystemExit(f"missing native executable: {EXE}")
    arch_run = subprocess.run(
        ["dpkg", "--print-architecture"],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        check=False,
    )
    arch = arch_run.stdout.strip() if arch_run.returncode == 0 else platform.machine()
    package_root = OUT / "deb-root"
    if package_root.exists():
        shutil.rmtree(package_root)

    debian = package_root / "DEBIAN"
    bindir = package_root / "usr" / "local" / "bin"
    docdir = package_root / "usr" / "share" / "doc" / "nexvary-da"
    debian.mkdir(parents=True)
    bindir.mkdir(parents=True)
    docdir.mkdir(parents=True)

    installed = bindir / "nexvary-da"
    shutil.copy2(EXE, installed)
    installed.chmod(0o755)
    for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "SECURITY_MODEL.md"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, docdir / name)

    control = (
        "Package: nexvary-da\n"
        "Version: 0.1.0\n"
        f"Architecture: {arch}\n"
        "Maintainer: NEXVARY <info@nexvary.com>\n"
        "Section: devel\n"
        "Priority: optional\n"
        "Description: NEXVARY Developer Agent local permission-gated developer runtime\n"
    )
    (debian / "control").write_text(control, encoding="utf-8")
    target = OUT / f"nexvary-da_0.1.0_{arch}.deb"
    result = subprocess.run(
        ["dpkg-deb", "--build", str(package_root), str(target)],
        check=False,
    )
    if result.returncode != 0:
        return result.returncode
    print(target)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

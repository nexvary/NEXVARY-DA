from __future__ import annotations

import hashlib
import json
import platform
import shutil
import sys
import tarfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
DIST = ROOT / "dist-native"
OUT = ROOT / "release-native"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    exe = DIST / ("NEXVARY-DA.exe" if sys.platform == "win32" else "NEXVARY-DA")
    if not exe.is_file():
        raise SystemExit(f"Native executable not found: {exe}")

    system = "windows" if sys.platform == "win32" else "linux"
    arch = platform.machine().lower().replace("amd64", "x86_64")
    stage = OUT / f"NEXVARY-DA-{system}-{arch}"
    if stage.exists():
        shutil.rmtree(stage)
    stage.mkdir(parents=True)
    shutil.copy2(exe, stage / exe.name)
    for name in ("README.md", "LICENSE", "THIRD_PARTY_NOTICES.md", "SECURITY_MODEL.md"):
        source = ROOT / name
        if source.is_file():
            shutil.copy2(source, stage / name)

    manifest = {
        "schema": 1,
        "platform": system,
        "arch": arch,
        "executable": exe.name,
        "executable_sha256": sha256(stage / exe.name),
        "signed": False,
        "signature_note": "Unsigned CI portable package. Production signing requires external signing credentials.",
    }
    (stage / "MANIFEST.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )

    if sys.platform == "win32":
        archive = OUT / f"{stage.name}.zip"
        with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
            for path in sorted(stage.rglob("*")):
                if path.is_file():
                    zf.write(path, path.relative_to(OUT))
    else:
        archive = OUT / f"{stage.name}.tar.gz"
        with tarfile.open(archive, "w:gz") as tf:
            tf.add(stage, arcname=stage.name)

    (OUT / f"{archive.name}.sha256").write_text(
        f"{sha256(archive)}  {archive.name}\n",
        encoding="utf-8",
    )
    print(archive)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

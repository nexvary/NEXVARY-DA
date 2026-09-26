from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import tempfile
import urllib.request

from nexvary_da.video_quality import EnhancementMode, VideoQualityEnhancer

URL = "https://upload.wikimedia.org/wikipedia/commons/b/b4/Gigaset_Smartphone_Production_III_-_Screwing_the_back_of_the_Smart_Phones.webm"


def probe(path: Path) -> dict:
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe unavailable")
    raw = subprocess.check_output([
        ffprobe, "-v", "error", "-show_streams", "-show_format", "-of", "json", str(path)
    ], text=True)
    return json.loads(raw)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="nexvary-public-media-") as tmp:
        root = Path(tmp)
        source = root / "public-camera-sample.webm"
        request = urllib.request.Request(URL, headers={"User-Agent": "NEXVARY-DA-CI/1.0"})
        with urllib.request.urlopen(request, timeout=60) as response:
            source.write_bytes(response.read())
        if source.stat().st_size < 500_000:
            raise RuntimeError("public media download is unexpectedly small")

        result = VideoQualityEnhancer().enhance(
            source, mode=EnhancementMode.BALANCED, width=720, height=1280
        )
        if not result.enhanced:
            raise RuntimeError(result.warning or "quality enhancement failed")
        output = Path(result.output)
        data = probe(output)
        kinds = {stream.get("codec_type") for stream in data.get("streams", [])}
        if not {"video", "audio"}.issubset(kinds):
            raise RuntimeError(f"missing media streams: {kinds}")
        duration = float(data.get("format", {}).get("duration", 0.0))
        if duration < 10.0:
            raise RuntimeError(f"unexpected output duration: {duration}")
        video = next(s for s in data["streams"] if s.get("codec_type") == "video")
        if (int(video.get("width", 0)), int(video.get("height", 0))) != (720, 1280):
            raise RuntimeError(f"unexpected dimensions: {video.get('width')}x{video.get('height')}")
        print(json.dumps({
            "status": "ok", "duration": duration, "streams": sorted(kinds),
            "resolution": "720x1280", "engine": result.engine,
        }, indent=2))


if __name__ == "__main__":
    main()

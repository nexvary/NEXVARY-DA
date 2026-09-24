from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from nexvary_da.permissions import Permission
from nexvary_da.product_ad import ProductAdBrief
from nexvary_da.product_scene import (
    ProductSceneDirector,
    RealVideoAudioPolicy,
    RealVideoRole,
)
from nexvary_da.project import ProjectRuntime, init_project


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        root = Path(tmp)
        init_project(
            root,
            name="Scene Director Smoke",
            permissions={Permission.READ, Permission.WRITE, Permission.SHELL},
        )
        runtime = ProjectRuntime(root)
        try:
            director = runtime.product_scene_director()
            media = director.media_runtime_status()
            if media.get("ready") is not True:
                raise SystemExit(f"Scene Director media runtime unavailable: {media}")

            source = root / "camera-sample.mp4"
            result = subprocess.run(
                [
                    str(media["ffmpeg"]),
                    "-y",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-f",
                    "lavfi",
                    "-i",
                    "color=c=blue:s=640x480:d=4",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    str(source),
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=60,
                check=False,
            )
            if result.returncode != 0 or not source.is_file():
                raise SystemExit(result.stdout or "Could not generate smoke source video")

            clips = director.prepare_real_videos(
                [source],
                role=RealVideoRole.CAMERA_SAMPLE,
                audio_policy=RealVideoAudioPolicy.DUCK,
                clip_seconds=2.0,
            )
            if not clips or not all(path.is_file() and path.stat().st_size > 0 for path in clips):
                raise SystemExit(f"Scene Director did not render real-video clips: {clips}")

            brief = ProductAdBrief(
                product_name="Smoke Camera",
                model="TEST-1",
                price="100",
                target_seconds=30,
            )
            explainer = director.render_operation_explainer(
                brief,
                (
                    "وصّل المنتج بالطاقة وشغّله كما يوضح دليل الشركة.",
                    "اربط المنتج بشبكة Wi‑Fi وفق متطلبات الشبكة المذكورة في الدليل.",
                ),
                seconds_per_step=1.2,
            )
            if explainer is None or not explainer.is_file() or explainer.stat().st_size <= 0:
                raise SystemExit("Scene Director operation explainer was not rendered")

            print(f"clips={len(clips)}")
            print(f"explainer={explainer}")
            return 0
        finally:
            runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())

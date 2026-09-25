from __future__ import annotations

import subprocess
import tempfile
from pathlib import Path

from PIL import Image

from nexvary_da.instruction_image import plan_instruction_scenes
from nexvary_da.permissions import Permission
from nexvary_da.product_ad import ProductAdBrief
from nexvary_da.product_ad_studio import ProductAdStudioService
from nexvary_da.product_storyboard import ProductStoryboard, StoryboardScene, StoryboardSceneKind
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
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:duration=4",
                    "-shortest",
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
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

            thumbnail = director.render_thumbnail(clips[0], width=180, height=320)
            if not thumbnail.is_file() or thumbnail.stat().st_size <= 0:
                raise SystemExit("Scene Director did not create a storyboard thumbnail")

            storyboard = ProductStoryboard(
                [
                    StoryboardScene.create(
                        title="Real camera sample",
                        kind=StoryboardSceneKind.REAL_VIDEO,
                        material=clips[0],
                        duration_seconds=15,
                        thumbnail=thumbnail,
                        evidence_label="REAL CAMERA SAMPLE",
                    )
                ]
            )
            studio_render = ProductAdStudioService(runtime).render(
                storyboard,
                voice_name="",
                preview=True,
            )
            final_path = Path(studio_render["output"])
            manifest_path = Path(studio_render["manifest"])
            if not final_path.is_file() or final_path.stat().st_size <= 0:
                raise SystemExit("Studio renderer did not create a preview Product Ad")
            if not manifest_path.is_file() or manifest_path.stat().st_size <= 0:
                raise SystemExit("Studio renderer did not create a render manifest")
            if len(str(studio_render.get("output_sha256") or "")) != 64:
                raise SystemExit("Studio renderer did not report a SHA-256 output digest")

            audio_probe = subprocess.run(
                [str(media["ffmpeg"]), "-hide_banner", "-i", str(final_path)],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                errors="replace",
                timeout=60,
                check=False,
            )
            if "Audio:" not in audio_probe.stdout:
                raise SystemExit("Final Product Ad dropped the real sample audio stream")

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

            instruction_scenes = plan_instruction_scenes(
                "الشحن عن طريق البريد\nمندوب البريد يستلم المال نقدا عند التسليم"
            )
            storyboard = director.render_instruction_storyboard(
                brief,
                instruction_scenes,
                seconds_per_scene=1.0,
            )
            if storyboard is None or not storyboard.is_file() or storyboard.stat().st_size <= 0:
                raise SystemExit("Scene Director instruction storyboard was not rendered")

            ai_background = root / "ai-background.png"
            real_product = root / "real-product.png"
            Image.new("RGB", (720, 1280), "#355577").save(ai_background)
            Image.new("RGBA", (420, 520), (210, 180, 70, 255)).save(real_product)
            composites = director.compose_ai_scene_assets(
                [ai_background],
                real_product,
            )
            if not composites or not composites[0].is_file() or composites[0].stat().st_size <= 0:
                raise SystemExit("Scene Director AI product composite was not rendered")

            print(f"clips={len(clips)}")
            print(f"thumbnail={thumbnail}")
            print(f"studio_render={final_path}")
            print(f"render_manifest={manifest_path}")
            print(f"explainer={explainer}")
            print(f"instruction_storyboard={storyboard}")
            print(f"ai_composite={composites[0]}")
            return 0
        finally:
            runtime.close()


if __name__ == "__main__":
    raise SystemExit(main())

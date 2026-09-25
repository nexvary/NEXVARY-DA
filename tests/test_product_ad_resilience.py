from __future__ import annotations

import tempfile
import unittest
from dataclasses import dataclass
from pathlib import Path

from nexvary_da.product_ad_studio import ProductAdStudioService
from nexvary_da.product_storyboard import (
    ProductStoryboard,
    StoryboardScene,
    StoryboardSceneKind,
)


@dataclass
class _FakeRenderResult:
    output: str
    subtitle: str = ""
    narration: str | None = None
    material_count: int = 1
    target_seconds: int = 15
    voice_warning: str = ""

    def to_dict(self):
        return {
            "output": self.output,
            "subtitle": self.subtitle,
            "narration": self.narration,
            "material_count": self.material_count,
            "target_seconds": self.target_seconds,
            "voice_warning": self.voice_warning,
        }


class _FakeRenderer:
    def __init__(self, root: Path):
        self.root = root
        self.calls: list[tuple[str, ...]] = []

    def render(self, materials, **kwargs):
        signature = tuple(str(Path(item)) for item in materials)
        self.calls.append(signature)
        if any(Path(item).suffix.lower() == ".mp4" for item in materials):
            raise RuntimeError("synthetic broken video")
        output = self.root / "rescued-output.mp4"
        output.write_bytes(b"fake-mp4-output")
        return _FakeRenderResult(
            output=str(output),
            material_count=len(materials),
            target_seconds=int(kwargs.get("target_seconds", 15)),
        )


class _FakeRuntime:
    def __init__(self, root: Path):
        self.root = root
        self.renderer = _FakeRenderer(root)

    def product_ads(self):
        return object()

    def direct_ad_renderer(self):
        return self.renderer


class ProductAdResilienceTests(unittest.TestCase):
    def test_studio_falls_back_to_image_scenes_when_video_render_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            image = root / "product.png"
            video = root / "broken.mp4"
            image.write_bytes(b"fake-image")
            video.write_bytes(b"broken-video")

            board = ProductStoryboard(
                [
                    StoryboardScene.create(
                        title="Product",
                        kind=StoryboardSceneKind.PRODUCT,
                        material=image,
                        narration="صورة المنتج",
                        duration_seconds=8,
                    ),
                    StoryboardScene.create(
                        title="Real",
                        kind=StoryboardSceneKind.REAL_VIDEO,
                        material=video,
                        narration="فيديو حقيقي",
                        duration_seconds=8,
                        evidence_label="REAL CAMERA SAMPLE",
                    ),
                ]
            )

            runtime = _FakeRuntime(root)
            result = ProductAdStudioService(runtime).render(
                board,
                voice_name="",
                preview=True,
            )

            self.assertEqual("image-scenes", result["render_mode"])
            self.assertTrue(Path(result["output"]).is_file())
            self.assertTrue(Path(result["manifest"]).is_file())
            self.assertEqual(2, len(runtime.renderer.calls))
            self.assertTrue(result["render_errors"])
            self.assertIn("synthetic broken video", result["render_errors"][0])

    def test_ui_sources_do_not_defer_live_exception_variables(self):
        package_root = Path(__file__).resolve().parents[1] / "src" / "nexvary_da"
        for filename in ("ui_product_ad.py", "ui_video_studio.py", "ui_app.py"):
            source = (package_root / filename).read_text(encoding="utf-8")
            self.assertNotIn("lambda: self.status_var.set(f", source)
            self.assertNotIn("lambda: self.easy_panel.set_message(", source)


if __name__ == "__main__":
    unittest.main()

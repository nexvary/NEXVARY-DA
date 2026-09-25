from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexvary_da.product_storyboard import (
    ProductStoryboard,
    StoryboardScene,
    StoryboardSceneKind,
    split_narration_for_scenes,
)


class ProductStoryboardTests(unittest.TestCase):
    def _storyboard(self) -> ProductStoryboard:
        return ProductStoryboard(
            [
                StoryboardScene.create(
                    title="Product",
                    kind=StoryboardSceneKind.PRODUCT,
                    material="product.png",
                    narration="المشهد الأول",
                    duration_seconds=4,
                ),
                StoryboardScene.create(
                    title="Real",
                    kind=StoryboardSceneKind.REAL_VIDEO,
                    material="real.mp4",
                    narration="المشهد الثاني",
                    duration_seconds=6,
                ),
                StoryboardScene.create(
                    title="Fact",
                    kind=StoryboardSceneKind.VERIFIED_FACT,
                    material="fact.png",
                    narration="المشهد الثالث",
                    duration_seconds=4,
                ),
            ]
        )

    def test_move_duplicate_delete_are_deterministic(self):
        board = self._storyboard()
        self.assertEqual(1, board.move(0, 1))
        self.assertEqual("Real", board.scene(0).title)
        duplicate = board.duplicate(0)
        self.assertEqual(1, duplicate)
        self.assertIn("Copy", board.scene(1).title)
        target = board.delete(duplicate)
        self.assertEqual(1, target)
        self.assertEqual(3, len(board))

    def test_disabled_scene_is_excluded_from_render_plan(self):
        board = self._storyboard()
        board.scene(1).enabled = False
        self.assertEqual(["product.png", "fact.png"], [s.material for s in board.enabled_scenes()])
        self.assertNotIn("المشهد الثاني", board.script_text())

    def test_fit_to_target_preserves_scene_count_and_target_duration(self):
        board = self._storyboard()
        board.fit_to_target(45)
        self.assertEqual(3, len(board.enabled_scenes()))
        self.assertAlmostEqual(45.0, board.total_seconds(), places=2)
        self.assertTrue(all(1 <= scene.duration_seconds <= 30 for scene in board.enabled_scenes()))

    def test_round_trip_project_json(self):
        board = self._storyboard()
        with tempfile.TemporaryDirectory() as tmp:
            target = Path(tmp) / "project.json"
            board.save(target, metadata={"model": "TEST-1", "voice": "ar-EG-SalmaNeural"})
            loaded, metadata = ProductStoryboard.load(target)
        self.assertEqual("TEST-1", metadata["model"])
        self.assertEqual([s.title for s in board.scenes], [s.title for s in loaded.scenes])
        self.assertEqual(board.script_text(), loaded.script_text())

    def test_validation_requires_labels_for_real_and_ai_scenes(self):
        board = ProductStoryboard(
            [
                StoryboardScene.create(
                    title="Real",
                    kind=StoryboardSceneKind.REAL_VIDEO,
                    material="real.mp4",
                    duration_seconds=15,
                    evidence_label="",
                )
            ]
        )
        issues = board.validation_issues()
        self.assertTrue(any("real footage" in issue for issue in issues))

        board.scene(0).evidence_label = "REAL CAMERA SAMPLE"
        self.assertFalse(any("real footage" in issue for issue in board.validation_issues()))

    def test_validation_rejects_too_short_storyboard(self):
        board = ProductStoryboard(
            [
                StoryboardScene.create(
                    title="Product",
                    kind=StoryboardSceneKind.PRODUCT,
                    material="product.png",
                    duration_seconds=4,
                )
            ]
        )
        self.assertTrue(any("outside 15-180" in issue for issue in board.validation_issues()))

    def test_split_narration_does_not_drop_words(self):
        text = "واحد اثنان ثلاثة أربعة خمسة ستة سبعة ثمانية تسعة عشرة"
        chunks = split_narration_for_scenes(text, 4)
        self.assertEqual(4, len(chunks))
        self.assertEqual(text.split(), " ".join(chunks).split())


if __name__ == "__main__":
    unittest.main()

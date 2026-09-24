import tempfile
import unittest
from pathlib import Path

from nexvary_da.integration_settings import IntegrationSettings
from nexvary_da.permissions import Permission, WorkspaceGuard, WorkspacePolicy
from nexvary_da.video_studio import SPECS, VideoEngineId, VideoStudioManager


def guard_for(root: Path, *permissions: Permission) -> WorkspaceGuard:
    return WorkspaceGuard([WorkspacePolicy.create(root, {Permission.READ, *permissions}, "test")])


class VideoStudioTests(unittest.TestCase):
    def test_three_reviewed_engines_are_registered(self):
        self.assertEqual(
            {
                VideoEngineId.MONEYPRINTER,
                VideoEngineId.AUTOMATED_VIDEO,
                VideoEngineId.SHORTS_GENERATOR,
            },
            {item.engine for item in SPECS},
        )
        self.assertTrue(all(item.license == "MIT" for item in SPECS))
        self.assertTrue(all(len(item.reviewed_commit) == 40 for item in SPECS))

    def test_video_defaults_are_sixty_second_portrait_arabic(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = IntegrationSettings(guard_for(root, Permission.WRITE), root)
            values = settings.load()
            self.assertEqual("60", values["video_duration"])
            self.assertEqual("9:16", values["video_aspect"])
            self.assertEqual("ar-EG", values["video_language"])
            self.assertEqual("moneyprinter", values["video_engine"])

    def test_engine_roots_are_non_secret_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            settings = IntegrationSettings(guard_for(root, Permission.WRITE), root)
            saved = settings.save(
                {
                    "automated_video_root": ".nexvary-da/video-engines/automated-video-generator",
                    "shorts_generator_root": ".nexvary-da/video-engines/shorts-generator",
                }
            )
            self.assertIn("automated_video_root", saved)
            self.assertIn("shorts_generator_root", saved)


if __name__ == "__main__":
    unittest.main()

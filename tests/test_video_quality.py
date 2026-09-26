from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.video_quality import EnhancementMode, VideoQualityEnhancer


class VideoQualityTests(unittest.TestCase):
    def test_off_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "ad.mp4"
            src.write_bytes(b"x")
            result = VideoQualityEnhancer("ffmpeg").enhance(src, mode=EnhancementMode.OFF)
            self.assertFalse(result.enhanced)
            self.assertEqual(str(src), result.output)

    def test_missing_ffmpeg_is_fail_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "ad.mp4"
            src.write_bytes(b"x")
            enhancer = VideoQualityEnhancer("")
            enhancer.ffmpeg = ""
            result = enhancer.enhance(src)
            self.assertFalse(result.enhanced)
            self.assertEqual(str(src), result.output)

    def test_balanced_uses_lanczos_and_preserves_audio(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "ad.mp4"
            src.write_bytes(b"x")
            with patch("nexvary_da.video_quality.subprocess.run") as run:
                result = VideoQualityEnhancer("ffmpeg").enhance(src)
                self.assertTrue(result.enhanced)
                command = run.call_args.args[0]
                joined = " ".join(command)
                self.assertIn("flags=lanczos", joined)
                self.assertIn("-c:a aac", joined)
                self.assertIn("-crf 19", joined)


if __name__ == "__main__":
    unittest.main()

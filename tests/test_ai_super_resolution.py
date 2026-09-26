from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from nexvary_da.ai_super_resolution import RealESRGANVideoEnhancer


class SuperResolutionTests(unittest.TestCase):
    def test_unavailable_is_fail_open(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "ad.mp4"
            src.write_bytes(b"x")
            enhancer = RealESRGANVideoEnhancer("", "")
            enhancer.executable = ""
            enhancer.ffmpeg = ""
            result = enhancer.enhance(src)
            self.assertFalse(result.enhanced)
            self.assertEqual(str(src), result.output)

    def test_failure_preserves_original(self):
        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / "ad.mp4"
            src.write_bytes(b"x")
            with patch("nexvary_da.ai_super_resolution.subprocess.run", side_effect=OSError("boom")):
                result = RealESRGANVideoEnhancer("realesrgan", "ffmpeg").enhance(src)
            self.assertFalse(result.enhanced)
            self.assertEqual(str(src), result.output)

    def test_available_requires_both_tools(self):
        self.assertTrue(RealESRGANVideoEnhancer("realesrgan", "ffmpeg").available())


if __name__ == "__main__":
    unittest.main()

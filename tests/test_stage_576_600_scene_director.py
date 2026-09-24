from __future__ import annotations

import unittest

from nexvary_da.product_ad import ProductAdBrief, build_arabic_product_script
from nexvary_da.product_research import extract_setup_candidates
from nexvary_da.product_scene import RealVideoRole, choose_clip_windows, role_narration


class ProductSceneDirectorTests(unittest.TestCase):
    def test_camera_sample_uses_two_windows_when_source_is_long(self):
        windows = choose_clip_windows(
            60.0,
            role=RealVideoRole.CAMERA_SAMPLE,
            clip_seconds=8.0,
        )
        self.assertEqual(2, len(windows))
        for start, duration in windows:
            self.assertGreaterEqual(start, 0.0)
            self.assertLessEqual(start + duration, 60.001)
            self.assertLessEqual(duration, 8.0)

    def test_short_real_video_is_not_artificially_extended(self):
        windows = choose_clip_windows(
            5.5,
            role=RealVideoRole.PRODUCT_OPERATION,
            clip_seconds=8.0,
        )
        self.assertEqual(((0.0, 5.5),), windows)

    def test_camera_role_narration_is_explicit_about_real_camera_sample(self):
        text = role_narration(RealVideoRole.CAMERA_SAMPLE)
        self.assertIn("تصوير حقيقي", text)
        self.assertIn("الكاميرا نفسها", text)

    def test_setup_candidates_are_conservative_and_orderable(self):
        steps = extract_setup_candidates(
            "Plug in the power adapter and turn on the camera. "
            "Download the app on your phone. "
            "Connect to a 2.4 GHz Wi-Fi network. "
            "Scan the QR code shown by the app. "
            "Add device to complete pairing."
        )
        keys = [item[0] for item in steps]
        self.assertIn("power", keys)
        self.assertIn("app", keys)
        self.assertIn("wifi", keys)
        self.assertIn("qr", keys)
        self.assertIn("pair", keys)

    def test_script_uses_selected_real_video_role_and_verified_setup_only(self):
        brief = ProductAdBrief(
            product_name="Camera",
            model="ABC-123",
            price="1500",
            target_seconds=60,
        )
        script = build_arabic_product_script(
            brief,
            real_video_count=2,
            real_video_role="camera_sample",
            setup_steps=("اربط المنتج بشبكة Wi‑Fi وفق متطلبات الشبكة المذكورة في الدليل.",),
        )
        self.assertIn("تصوير حقيقي من الكاميرا نفسها", script.text)
        self.assertIn("طريقة التشغيل التالية", script.text)
        self.assertIn("Wi‑Fi", script.text)


if __name__ == "__main__":
    unittest.main()

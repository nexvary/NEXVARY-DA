from __future__ import annotations

import unittest

from nexvary_da.direct_ad_renderer import _subtitle_chunks, _srt_time, build_srt


class DirectAdRendererTests(unittest.TestCase):
    def test_arabic_script_is_split_into_timed_srt_entries(self):
        text = "كاميرا مراقبة تعمل بالطاقة الشمسية وتدعم الاتصال بشريحة الجيل الرابع ومتابعة مباشرة من الهاتف"
        srt = build_srt(text, 30)
        self.assertIn("00:00:00,000 -->", srt)
        self.assertIn("كاميرا مراقبة", srt)
        self.assertTrue(srt.endswith("\n"))

    def test_subtitle_chunks_do_not_drop_words(self):
        text = "واحد اثنان ثلاثة أربعة خمسة ستة سبعة ثمانية تسعة عشرة"
        chunks = _subtitle_chunks(text, max_chars=12)
        self.assertEqual(text.split(), " ".join(chunks).split())

    def test_srt_time_formats_hours_minutes_seconds(self):
        self.assertEqual("01:01:01,250", _srt_time(3661.25))


if __name__ == "__main__":
    unittest.main()

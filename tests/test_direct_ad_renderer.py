from __future__ import annotations

import unittest

from nexvary_da.codecraft import extract_purchase_fields
from nexvary_da.direct_ad_renderer import _subtitle_chunks, _srt_time, build_srt
from nexvary_da.product_research import _model_matches


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


class AutoProductAdHelperTests(unittest.TestCase):
    def test_purchase_fields_extract_price_phone_and_branch_from_arabic_ocr(self):
        text = """
السعر: 3500 جنيه
للطلب 01065946452
فروعنا: العاشر من رمضان - دمياط فارسكور
لا يوجد شحن
"""
        info = extract_purchase_fields(text)
        self.assertEqual("3500", info["price"])
        self.assertEqual("EGP", info["currency"])
        self.assertEqual("01065946452", info["contact"])
        self.assertTrue(any("فروعنا" in item for item in info["branches"]))
        self.assertTrue(any("شحن" in item for item in info["purchase_notes"]))

    def test_purchase_fields_do_not_invent_missing_price_or_contact(self):
        info = extract_purchase_fields("الاستلام من الفرع فقط")
        self.assertEqual("", info["price"])
        self.assertEqual("", info["contact"])
        self.assertTrue(info["branches"])

    def test_exact_model_match_ignores_punctuation_but_rejects_similar_model(self):
        self.assertTrue(_model_matches("Official manual for VTS30-G-F camera", "VTS30-G-F"))
        self.assertTrue(_model_matches("VTS30 G F specifications", "VTS30-G-F"))
        self.assertFalse(_model_matches("Official manual for VTS30-G-E camera", "VTS30-G-F"))
        self.assertFalse(_model_matches("Official manual for VTS30-G-FX camera", "VTS30-G-F"))


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import unittest

from nexvary_da.product_ad import ProductAdBrief, build_arabic_product_script
from nexvary_da.product_research import extract_fact_candidates


class ProductEvidenceTests(unittest.TestCase):
    def test_real_product_video_is_described_as_real_evidence(self):
        brief = ProductAdBrief(
            product_name="Camera",
            model="ABC-123",
            price="1500",
            details="لون أبيض",
            target_seconds=60,
        )
        script = build_arabic_product_script(
            brief,
            real_video_count=1,
            verified_facts=("الدقة المذكورة في المصادر: 4K",),
        )
        self.assertIn("تسجيلًا حقيقيًا", script.text)
        self.assertIn("4K", script.text)
        self.assertIn("1500", script.text)

    def test_no_research_claim_is_added_when_none_is_verified(self):
        brief = ProductAdBrief(
            product_name="Camera",
            model="ABC-123",
            price="1500",
            target_seconds=30,
        )
        script = build_arabic_product_script(brief, real_video_count=0, verified_facts=())
        self.assertNotIn("المواصفات التي تم التحقق", script.text)
        self.assertNotIn("تسجيلًا حقيقيًا", script.text)

    def test_conservative_camera_fact_extraction(self):
        facts = extract_fact_candidates(
            "ABC-123 supports 4K video, 2.4 GHz Wi-Fi, IP66, "
            "night vision, two-way audio and microSD cards up to 256 GB."
        )
        keys = {item[0] for item in facts}
        self.assertTrue({"resolution", "wifi", "ip_rating", "night_vision", "two_way_audio", "storage"} <= keys)


if __name__ == "__main__":
    unittest.main()

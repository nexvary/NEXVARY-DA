from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from nexvary_da.commerce_models import ContentItem,CustomerJourney,LeadStage
from nexvary_da.content_calendar import ContentCalendar
from nexvary_da.lead_scoring import LeadScorer
from nexvary_da.media_library import MediaAsset,MediaKind,ProductMediaLibrary
from nexvary_da.media_sales import MediaSalesResponder
from nexvary_da.product_intelligence import EvidenceClass,ExtractedProductEvidence,ProductIntelligenceGuard
from nexvary_da.publishing import PublishingPolicy
from nexvary_da.publishing_hub import PublishingHub


class MoreCommerceTests(unittest.TestCase):
    def test_calendar_only_returns_due_scheduled(self):
        p=PublishingPolicy(); item=ContentItem("i","facebook","a","p","c")
        p.approve(item,"manager"); p.schedule(item,"2026-10-01T10:00:00")
        cal=ContentCalendar(); cal.add(item)
        self.assertEqual([item],cal.due("2026-10-01T10:01:00"))

    def test_unconfigured_publisher_fails_closed(self):
        p=PublishingPolicy(); item=ContentItem("i","facebook","a","p","c")
        p.approve(item,"manager")
        result=PublishingHub().publish(item)
        self.assertFalse(result.ok)

    def test_high_intent_scores_hot(self):
        j=CustomerJourney("c",stage=LeadStage.HIGH_INTENT)
        self.assertEqual("hot",LeadScorer().score(j).band)

    def test_media_response_requires_verified_asset(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=ProductMediaLibrary(Path(tmp)/"m.json")
            lib.add(MediaAsset("1","p",MediaKind.REAL_FOOTAGE,"night.mp4",["night","footage"],True,True))
            r=MediaSalesResponder(lib).choose("p","عايز أشوف التصوير بالليل")
            self.assertIsNotNone(r.asset); self.assertTrue(r.asset.real_capture)

    def test_ai_copy_cannot_become_specs(self):
        with self.assertRaises(ValueError):
            ProductIntelligenceGuard().accept(ExtractedProductEvidence(visible_specs={"range":"1km"},evidence_class=EvidenceClass.AI_COPY))


if __name__=="__main__": unittest.main()

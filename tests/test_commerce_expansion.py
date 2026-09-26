from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from nexvary_da.campaign_factory import CampaignContentFactory
from nexvary_da.commerce_db import CommerceDatabase
from nexvary_da.commerce_models import Product
from nexvary_da.marketing_attribution import MarketingAttribution,MarketingEvent
from nexvary_da.unified_inbox import UnifiedInbox,Message
from nexvary_da.white_label import WhiteLabelProfile,WhiteLabelStore


class CommerceExpansionTests(unittest.TestCase):
    def test_inbox_keeps_channel_and_product_context(self):
        box=UnifiedInbox(); c=box.receive(Message("m","c","whatsapp","بكام؟",product_id="p"))
        self.assertEqual("p",c.current_product); self.assertEqual("بكام؟",c.last_message)

    def test_campaign_uses_database_price_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=CommerceDatabase(Path(tmp)/"db")
            db.upsert_product(Product("p","s","Camera",selling_price=2850,currency="EGP"))
            pack=CampaignContentFactory(db).create("p")
            self.assertIn("2850",pack.variants["facebook_post"]); db.close()

    def test_attribution_deduplicates_order_revenue(self):
        a=MarketingAttribution()
        a.record(MarketingEvent("c","p","paid",100,"o1"))
        a.record(MarketingEvent("c","p","delivered",100,"o1"))
        s=a.campaign_summary("c"); self.assertEqual(1,s["orders"]); self.assertEqual(100,s["revenue"])

    def test_white_label_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=WhiteLabelStore(Path(tmp)/"brand.json"); store.save(WhiteLabelProfile(company_name="IBM Empire"))
            self.assertEqual("IBM Empire",store.load().company_name)


if __name__=="__main__": unittest.main()

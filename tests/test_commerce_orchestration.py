from __future__ import annotations
import tempfile,unittest
from pathlib import Path
from nexvary_da.audit_log import AuditLog
from nexvary_da.commerce_db import CommerceDatabase
from nexvary_da.commerce_models import CustomerJourney,Product
from nexvary_da.commerce_orchestrator import CommerceOrchestrator
from nexvary_da.media_library import MediaAsset,MediaKind,ProductMediaLibrary
from nexvary_da.media_sales import MediaSalesResponder
from nexvary_da.order_service import GroundedOrderService
from nexvary_da.orders import OrderStore
from nexvary_da.product_ad_bridge import ProductAdBridge,VideoCampaignRequest
from nexvary_da.tenant_storage import TenantContext,TenantStorage


class CommerceOrchestrationTests(unittest.TestCase):
    def test_price_turn_and_real_media_turn_are_grounded(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=CommerceDatabase(Path(tmp)/"db"); db.upsert_product(Product("p","s","Camera",model="C1",selling_price=2850,currency="EGP"))
            lib=ProductMediaLibrary(Path(tmp)/"m.json"); lib.add(MediaAsset("a","p",MediaKind.REAL_FOOTAGE,"real.mp4",["video","footage"],True,True))
            o=CommerceOrchestrator(db,MediaSalesResponder(lib)); j=CustomerJourney("c",product_id="p",channel="whatsapp")
            self.assertIn("2850",o.handle(j,"بكام الكاميرا؟").text)
            self.assertEqual("real.mp4",o.handle(j,"أرسل فيديو التصوير").media_path); db.close()

    def test_order_uses_database_price_and_stock(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=CommerceDatabase(Path(tmp)/"db"); db.upsert_product(Product("p","s","Camera",selling_price=100,currency="EGP",stock_quantity=1))
            service=GroundedOrderService(db,OrderStore(Path(tmp)/"orders.json"))
            self.assertEqual(100,service.create("c","p").unit_price)
            with self.assertRaises(ValueError): service.create("c","p",2)
            db.close()

    def test_product_ad_bridge_never_invents_missing_price(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=CommerceDatabase(Path(tmp)/"db"); db.upsert_product(Product("p","s","Camera"))
            brief=ProductAdBridge(db).grounded_brief(VideoCampaignRequest("p",45))
            self.assertIsNone(brief["price"]); self.assertIn("تصوير فعلي",brief["real_footage_label"]); db.close()

    def test_tenant_path_escape_is_blocked(self):
        with tempfile.TemporaryDirectory() as tmp:
            store=TenantStorage(Path(tmp)); t=TenantContext("company-a","A")
            with self.assertRaises(ValueError): store.path(t,"..","company-b","orders.json")

    def test_audit_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            log=AuditLog(Path(tmp)/"audit.jsonl"); log.record("approve","manager","content","x")
            self.assertEqual("approve",log.read()[0].action)


if __name__=="__main__": unittest.main()

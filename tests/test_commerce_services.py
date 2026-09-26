from __future__ import annotations
import tempfile, unittest
from pathlib import Path
from nexvary_da.commerce_db import CommerceDatabase
from nexvary_da.commerce_models import ContentItem, Product
from nexvary_da.media_library import MediaAsset, MediaKind, ProductMediaLibrary
from nexvary_da.orders import OrderStore
from nexvary_da.product_knowledge import ProductKnowledgeBase
from nexvary_da.publishing import PublishingPolicy


class CommerceServicesTests(unittest.TestCase):
    def test_real_night_footage_lookup(self):
        with tempfile.TemporaryDirectory() as tmp:
            lib=ProductMediaLibrary(Path(tmp)/"media.json")
            lib.add(MediaAsset("m1","p1",MediaKind.REAL_FOOTAGE,"night.mp4",["night","camera","4g"],True,True))
            hit=lib.search("p1","night footage")[0]
            self.assertTrue(hit.real_capture); self.assertEqual("night.mp4",hit.path)

    def test_unknown_faq_escalates(self):
        with tempfile.TemporaryDirectory() as tmp:
            db=CommerceDatabase(Path(tmp)/"db.sqlite")
            db.upsert_product(Product("p1","S1","Camera",faq={"هل تعمل 4g؟":"نعم، وفق بيانات المنتج."}))
            known=ProductKnowledgeBase(db).answer("p1","هل تعمل 4g؟")
            unknown=ProductKnowledgeBase(db).answer("p1","ما مدى الرؤية الليلية؟")
            self.assertTrue(known.grounded); self.assertTrue(unknown.requires_employee)
            db.close()

    def test_order_rejects_missing_currency(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ValueError):
                OrderStore(Path(tmp)/"orders.json").create("c","p",1,100,"")

    def test_publish_requires_approval(self):
        item=ContentItem("x","facebook","page","p","campaign")
        policy=PublishingPolicy()
        with self.assertRaises(ValueError):
            policy.schedule(item,"2026-10-01T10:00:00")
        policy.approve(item,"manager")
        policy.schedule(item,"2026-10-01T10:00:00")
        self.assertEqual("scheduled",item.status.value)


if __name__=="__main__": unittest.main()

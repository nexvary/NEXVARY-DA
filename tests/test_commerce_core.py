from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from nexvary_da.commerce_db import CommerceDatabase
from nexvary_da.commerce_models import CustomerJourney, DataOrigin, LeadStage, Product, ProductFact
from nexvary_da.grounded_sales import GroundedSalesAgent


class CommerceCoreTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.db = CommerceDatabase(Path(self.tmp.name) / "commerce.db")

    def tearDown(self):
        self.db.close()
        self.tmp.cleanup()

    def test_product_roundtrip_and_grounded_price(self):
        self.db.upsert_product(Product(
            product_id="cam-1", sku="CAM-001", name="4G Camera",
            selling_price=2850, currency="EGP", stock_quantity=4,
        ))
        answer = GroundedSalesAgent(self.db).price("cam-1")
        self.assertTrue(answer.grounded)
        self.assertIn("2850", answer.text)
        self.assertIn("EGP", answer.text)

    def test_ai_cannot_write_protected_commercial_facts(self):
        with self.assertRaises(ValueError):
            self.db.add_fact(ProductFact(
                "cam-1", "warranty", "5 years", DataOrigin.AI_COPY
            ))

    def test_missing_price_escalates_instead_of_inventing(self):
        self.db.upsert_product(Product(product_id="x", sku="X-1", name="Unknown"))
        answer = GroundedSalesAgent(self.db).price("x")
        self.assertFalse(answer.grounded)
        self.assertTrue(answer.requires_employee)

    def test_verified_fact_can_supply_missing_product_field(self):
        self.db.upsert_product(Product(product_id="x", sku="X-1", name="Camera"))
        self.db.add_fact(ProductFact(
            "x", "warranty", "12 months", DataOrigin.VERIFIED, "seller invoice", True
        ))
        self.assertEqual("12 months", self.db.grounded_value("x", "warranty"))

    def test_customer_journey_tracks_stage(self):
        journey = CustomerJourney("customer-1")
        GroundedSalesAgent(self.db).transition(journey, "asked_price")
        self.assertEqual(LeadStage.ASKED_PRICE, journey.stage)
        GroundedSalesAgent(self.db).transition(journey, "video_sent")
        self.assertEqual(LeadStage.VIDEO_SENT, journey.stage)


if __name__ == "__main__":
    unittest.main()

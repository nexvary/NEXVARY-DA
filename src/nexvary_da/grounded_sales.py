from __future__ import annotations

from dataclasses import dataclass

from .commerce_db import CommerceDatabase
from .commerce_models import CustomerJourney, LeadStage


@dataclass(frozen=True, slots=True)
class GroundedAnswer:
    text: str
    grounded: bool
    requires_employee: bool = False


class GroundedSalesAgent:
    def __init__(self, database: CommerceDatabase):
        self.database = database

    def product_fact(self, product_id: str, field: str, *, label: str) -> GroundedAnswer:
        value = self.database.grounded_value(product_id, field)
        if value is None:
            return GroundedAnswer(
                f"{label}: غير مسجل حاليًا. سأحوّل السؤال لموظف للتأكيد.",
                False, True,
            )
        return GroundedAnswer(f"{label}: {value}", True)

    def price(self, product_id: str) -> GroundedAnswer:
        price = self.database.grounded_value(product_id, "selling_price")
        currency = self.database.grounded_value(product_id, "currency")
        if price is None or not currency:
            return GroundedAnswer("السعر غير مؤكد في قاعدة المنتجات. يلزم تأكيد موظف.", False, True)
        return GroundedAnswer(f"السعر الحالي {price:g} {currency}.", True)

    def transition(self, journey: CustomerJourney, event: str) -> CustomerJourney:
        transitions = {
            "asked_price": LeadStage.ASKED_PRICE,
            "interested": LeadStage.PRODUCT_INTERESTED,
            "explained": LeadStage.PRODUCT_EXPLAINED,
            "video_sent": LeadStage.VIDEO_SENT,
            "qualified": LeadStage.QUALIFIED,
            "compared": LeadStage.COMPARED_PRODUCTS,
            "asked_shipping": LeadStage.ASKED_SHIPPING,
            "high_intent": LeadStage.HIGH_INTENT,
            "order_requested": LeadStage.ORDER_REQUESTED,
            "order_created": LeadStage.ORDER_CREATED,
            "payment_pending": LeadStage.PAYMENT_PENDING,
            "paid": LeadStage.PAID,
            "shipped": LeadStage.SHIPPED,
            "delivered": LeadStage.DELIVERED,
            "after_sales": LeadStage.AFTER_SALES,
            "lost": LeadStage.LOST,
        }
        if event not in transitions:
            raise ValueError(f"Unknown sales event: {event}")
        journey.stage = transitions[event]
        return journey

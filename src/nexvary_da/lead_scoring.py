from __future__ import annotations
from dataclasses import dataclass
from .commerce_models import CustomerJourney,LeadStage


@dataclass(frozen=True,slots=True)
class LeadScore:
    score:int; band:str


class LeadScorer:
    WEIGHTS={
        LeadStage.NEW_LEAD:5,LeadStage.ASKED_PRICE:15,LeadStage.PRODUCT_INTERESTED:20,
        LeadStage.PRODUCT_EXPLAINED:25,LeadStage.VIDEO_SENT:30,LeadStage.QUALIFIED:45,
        LeadStage.COMPARED_PRODUCTS:55,LeadStage.ASKED_SHIPPING:65,LeadStage.HIGH_INTENT:80,
        LeadStage.ORDER_REQUESTED:90,LeadStage.ORDER_CREATED:95,LeadStage.PAYMENT_PENDING:96,
        LeadStage.PAID:100,LeadStage.SHIPPED:100,LeadStage.DELIVERED:100,LeadStage.AFTER_SALES:70,
        LeadStage.LOST:0,
    }
    def score(self,j:CustomerJourney)->LeadScore:
        value=self.WEIGHTS[j.stage]
        band="hot" if value>=80 else "warm" if value>=40 else "cold"
        j.lead_score=value
        return LeadScore(value,band)

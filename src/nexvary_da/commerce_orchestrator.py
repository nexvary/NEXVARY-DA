from __future__ import annotations
from dataclasses import dataclass
from .commerce_db import CommerceDatabase
from .commerce_models import CustomerJourney
from .grounded_sales import GroundedSalesAgent
from .lead_scoring import LeadScorer
from .media_sales import MediaSalesResponder
from .product_knowledge import ProductKnowledgeBase


@dataclass(frozen=True,slots=True)
class SalesTurn:
    text:str; grounded:bool; requires_employee:bool
    media_path:str=""; stage:str=""; lead_score:int=0


class CommerceOrchestrator:
    def __init__(self,db:CommerceDatabase,media:MediaSalesResponder):
        self.db=db; self.sales=GroundedSalesAgent(db); self.kb=ProductKnowledgeBase(db)
        self.media=media; self.scorer=LeadScorer()

    def handle(self,journey:CustomerJourney,message:str)->SalesTurn:
        q=message.lower()
        if any(x in q for x in ("بكام","سعر","price")):
            ans=self.sales.price(journey.product_id)
            self.sales.transition(journey,"asked_price")
            score=self.scorer.score(journey)
            return SalesTurn(ans.text,ans.grounded,ans.requires_employee,stage=journey.stage.value,lead_score=score.score)
        if any(x in q for x in ("فيديو","تصوير","video","footage","بالليل")):
            chosen=self.media.choose(journey.product_id,message)
            if chosen.asset:
                self.sales.transition(journey,"video_sent"); score=self.scorer.score(journey)
                return SalesTurn("تم اختيار وسائط المنتج الموثقة.",True,False,chosen.asset.path,journey.stage.value,score.score)
            score=self.scorer.score(journey)
            return SalesTurn("لا توجد وسائط موثقة مطابقة حاليًا.",False,True,stage=journey.stage.value,lead_score=score.score)
        faq=self.kb.answer(journey.product_id,message)
        score=self.scorer.score(journey)
        return SalesTurn(faq.text,faq.grounded,faq.requires_employee,stage=journey.stage.value,lead_score=score.score)

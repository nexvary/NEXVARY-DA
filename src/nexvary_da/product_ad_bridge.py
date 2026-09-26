from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from .commerce_db import CommerceDatabase


@dataclass(frozen=True,slots=True)
class VideoCampaignRequest:
    product_id:str; duration:int=30; aspect_ratio:str="9:16"; language:str="ar"; voice_over:bool=True


class ProductAdBridge:
    """Boundary between Commerce OS and the existing Product Advertisement engine."""
    ALLOWED_DURATIONS=frozenset({30,45,60})
    def __init__(self,db:CommerceDatabase,renderer:Callable[[dict],object]|None=None):
        self.db=db; self.renderer=renderer

    def grounded_brief(self,request:VideoCampaignRequest)->dict:
        if request.duration not in self.ALLOWED_DURATIONS: raise ValueError("Duration must be 30, 45 or 60 seconds")
        p=self.db.get_product(request.product_id)
        if not p: raise KeyError(request.product_id)
        return {
            "product_id":p.product_id,"product_name":p.name,"model":p.model,
            "price":self.db.grounded_value(p.product_id,"selling_price"),
            "currency":self.db.grounded_value(p.product_id,"currency"),
            "phone_numbers":p.phone_numbers,"branches":p.branches,
            "images":p.images,"real_product_footage":p.real_product_footage,
            "duration":request.duration,"aspect_ratio":request.aspect_ratio,
            "language":request.language,"voice_over":request.voice_over,
            "real_footage_label":"Real Product Sample / تصوير فعلي من المنتج",
        }

    def render(self,request:VideoCampaignRequest):
        if self.renderer is None: raise RuntimeError("Product Advertisement renderer is not connected")
        return self.renderer(self.grounded_brief(request))

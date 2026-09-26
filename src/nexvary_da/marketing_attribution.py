from __future__ import annotations
from dataclasses import dataclass
from collections import defaultdict


@dataclass(frozen=True,slots=True)
class MarketingEvent:
    campaign_id:str; product_id:str; event:str; value:float=0.0; order_id:str=""


class MarketingAttribution:
    def __init__(self): self.events:list[MarketingEvent]=[]
    def record(self,event:MarketingEvent): self.events.append(event)
    def campaign_summary(self,campaign_id:str):
        rows=[e for e in self.events if e.campaign_id==campaign_id]
        counts=defaultdict(int); revenue=0.0; orders=set()
        for e in rows:
            counts[e.event]+=1
            if e.event in {"paid","delivered"} and e.order_id:
                if e.order_id not in orders: revenue+=e.value; orders.add(e.order_id)
        return {"campaign_id":campaign_id,"events":dict(counts),"orders":len(orders),"revenue":revenue}

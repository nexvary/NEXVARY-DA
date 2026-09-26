from __future__ import annotations
from dataclasses import dataclass, asdict
from enum import StrEnum
import json
from pathlib import Path
import uuid


class OrderStatus(StrEnum):
    REQUESTED="requested"; CREATED="created"; PAYMENT_PENDING="payment_pending"; PAID="paid"; SHIPPED="shipped"; DELIVERED="delivered"; CANCELLED="cancelled"


@dataclass(slots=True)
class Order:
    order_id:str; customer_id:str; product_id:str; quantity:int
    unit_price:float; currency:str; status:OrderStatus=OrderStatus.CREATED
    channel:str=""; campaign_id:str=""

    def to_dict(self):
        d=asdict(self); d["status"]=self.status.value; return d


class OrderStore:
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)

    def create(self,customer_id,product_id,quantity,unit_price,currency,channel="",campaign_id=""):
        if unit_price is None or not currency: raise ValueError("Order requires grounded price and currency")
        order=Order(uuid.uuid4().hex,customer_id,product_id,int(quantity),float(unit_price),currency,channel=channel,campaign_id=campaign_id)
        rows=self.list(); rows.append(order)
        self.path.write_text(json.dumps([x.to_dict() for x in rows],ensure_ascii=False,indent=2),encoding="utf-8")
        return order

    def list(self):
        if not self.path.exists(): return []
        return [Order(**{**x,"status":OrderStatus(x["status"])}) for x in json.loads(self.path.read_text(encoding="utf-8"))]

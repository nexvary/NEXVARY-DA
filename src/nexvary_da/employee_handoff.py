from __future__ import annotations
from dataclasses import dataclass
from .commerce_models import CustomerJourney


@dataclass(frozen=True,slots=True)
class EmployeeHandoff:
    required:bool; reason:str; customer_id:str; product_id:str; channel:str; summary:str


class HandoffPolicy:
    def evaluate(self,journey:CustomerJourney,*,grounded:bool=True,customer_requests_human:bool=False,error:str=""):
        reasons=[]
        if customer_requests_human: reasons.append("customer requested employee")
        if not grounded: reasons.append("answer requires verified commercial data")
        if error: reasons.append(error)
        return EmployeeHandoff(bool(reasons),"; ".join(reasons),journey.customer_id,journey.product_id,journey.channel,
                               f"stage={journey.stage.value}; lead_score={journey.lead_score}")

from __future__ import annotations
from dataclasses import dataclass
import uuid
from .commerce_db import CommerceDatabase


@dataclass(frozen=True, slots=True)
class CampaignPack:
    campaign_id:str; product_id:str; variants:dict[str,str]


class CampaignContentFactory:
    """Deterministic grounded copy skeleton; LLM may polish wording, never protected facts."""
    def __init__(self,db:CommerceDatabase): self.db=db

    def create(self,product_id:str)->CampaignPack:
        p=self.db.get_product(product_id)
        if not p: raise KeyError(product_id)
        price=self.db.grounded_value(product_id,"selling_price")
        currency=self.db.grounded_value(product_id,"currency")
        price_line=f"السعر: {price:g} {currency}" if price is not None and currency else "السعر: يُرجى التأكيد"
        facts=[p.name, p.model, price_line]
        if p.warranty: facts.append(f"الضمان: {p.warranty}")
        if p.shipping_information: facts.append(f"الشحن: {p.shipping_information}")
        base=" | ".join(x for x in facts if x)
        return CampaignPack(uuid.uuid4().hex,product_id,{
            "facebook_post":base,
            "instagram_post":base,
            "short_caption":base,
            "arabic_egyptian_caption":base,
            "msa_caption":base,
            "english_caption":f"{p.name} {p.model}".strip(),
            "whatsapp_status":base,
            "sales_script":base,
            "seo_product_description":p.full_description or p.short_description or p.name,
        })

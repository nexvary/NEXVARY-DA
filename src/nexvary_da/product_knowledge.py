from __future__ import annotations
from dataclasses import dataclass
from .commerce_db import CommerceDatabase


@dataclass(frozen=True, slots=True)
class FAQAnswer:
    text: str
    grounded: bool
    source: str
    requires_employee: bool=False


class ProductKnowledgeBase:
    def __init__(self, db: CommerceDatabase): self.db=db

    def answer(self, product_id: str, question: str) -> FAQAnswer:
        product=self.db.get_product(product_id)
        if not product:
            return FAQAnswer("المنتج غير موجود في قاعدة البيانات.",False,"none",True)
        q=question.strip().lower()
        for known, answer in product.faq.items():
            words=[w for w in known.lower().split() if len(w)>2]
            if known.lower() in q or (words and sum(w in q for w in words)>=max(1,len(words)//2)):
                return FAQAnswer(answer,True,"product_database")
        mappings={
            "ضمان":("warranty","الضمان"),
            "شحن":("shipping_information","الشحن"),
            "سعر":("selling_price","السعر"),
            "مخزون":("stock_quantity","المخزون"),
        }
        for token,(field,label) in mappings.items():
            if token in q:
                value=self.db.grounded_value(product_id,field)
                if value not in (None,"",[],{}):
                    return FAQAnswer(f"{label}: {value}",True,"product_database")
        return FAQAnswer("لا توجد إجابة موثقة لهذا السؤال حاليًا. يلزم تأكيد موظف.",False,"none",True)

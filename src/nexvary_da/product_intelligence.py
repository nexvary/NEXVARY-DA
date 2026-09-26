from __future__ import annotations
from dataclasses import dataclass,field
from enum import StrEnum


class EvidenceClass(StrEnum):
    VERIFIED="verified"; MANUFACTURER="manufacturer"; SELLER="seller"; AI_COPY="ai_copy"


@dataclass(slots=True)
class ExtractedProductEvidence:
    brand:str=""; model:str=""; package_text:list[str]=field(default_factory=list)
    visible_specs:dict[str,str]=field(default_factory=dict)
    source:str=""; evidence_class:EvidenceClass=EvidenceClass.SELLER


class ProductIntelligenceGuard:
    PROTECTED=frozenset({"price","selling_price","stock","stock_quantity","availability","warranty","shipping"})
    def accept(self,evidence:ExtractedProductEvidence):
        if evidence.evidence_class==EvidenceClass.AI_COPY and evidence.visible_specs:
            raise ValueError("AI marketing copy cannot become product specifications")
        return evidence
    def merge_specs(self,*evidence):
        result={}
        rank={EvidenceClass.VERIFIED:3,EvidenceClass.MANUFACTURER:2,EvidenceClass.SELLER:1,EvidenceClass.AI_COPY:0}
        sources={}
        for e in evidence:
            self.accept(e)
            for k,v in e.visible_specs.items():
                if k.lower() in self.PROTECTED and e.evidence_class==EvidenceClass.AI_COPY: continue
                if k not in sources or rank[e.evidence_class]>sources[k][0]:
                    result[k]=v; sources[k]=(rank[e.evidence_class],e.source)
        return result

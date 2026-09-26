from __future__ import annotations
from dataclasses import asdict, dataclass
from enum import StrEnum
import json
from pathlib import Path


class MediaKind(StrEnum):
    IMAGE="image"; VIDEO="video"; REAL_FOOTAGE="real_footage"; MANUAL="manual"; PRICE_CARD="price_card"; COMPARISON="comparison"


@dataclass(slots=True)
class MediaAsset:
    asset_id: str
    product_id: str
    kind: MediaKind
    path: str
    tags: list[str]
    verified: bool = False
    real_capture: bool = False

    def to_dict(self): 
        data=asdict(self); data["kind"]=self.kind.value; return data


class ProductMediaLibrary:
    def __init__(self, index: Path):
        self.index=Path(index); self.index.parent.mkdir(parents=True, exist_ok=True)

    def _items(self):
        if not self.index.exists(): return []
        return [MediaAsset(**{**x,"kind":MediaKind(x["kind"])}) for x in json.loads(self.index.read_text(encoding="utf-8"))]

    def add(self, asset: MediaAsset):
        items=self._items(); items=[x for x in items if x.asset_id != asset.asset_id]; items.append(asset)
        self.index.write_text(json.dumps([x.to_dict() for x in items],ensure_ascii=False,indent=2),encoding="utf-8")

    def search(self, product_id: str, query: str):
        terms={x.lower() for x in query.split() if x}
        matches=[]
        for item in self._items():
            if item.product_id != product_id: continue
            hay=" ".join([item.kind.value,*item.tags]).lower()
            score=sum(t in hay for t in terms)
            if score: matches.append((score,item))
        return [x for _,x in sorted(matches,key=lambda p:-p[0])]

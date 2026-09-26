from __future__ import annotations
from dataclasses import dataclass,asdict
import json
from pathlib import Path


@dataclass(slots=True)
class WhiteLabelProfile:
    company_name:str="NEXVARY"; logo:str=""; website:str=""; email:str=""
    facebook:str=""; instagram:str=""; linkedin:str=""; tiktok:str=""; x:str=""
    phone:str=""; primary_language:str="ar"; currency:str=""


class WhiteLabelStore:
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def save(self,p:WhiteLabelProfile): self.path.write_text(json.dumps(asdict(p),ensure_ascii=False,indent=2),encoding="utf-8")
    def load(self):
        return WhiteLabelProfile(**json.loads(self.path.read_text(encoding="utf-8"))) if self.path.exists() else WhiteLabelProfile()

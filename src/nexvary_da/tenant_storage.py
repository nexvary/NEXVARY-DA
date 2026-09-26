from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import re


@dataclass(frozen=True,slots=True)
class TenantContext:
    tenant_id:str; company_name:str


class TenantStorage:
    def __init__(self,root:Path): self.root=Path(root)
    def path(self,tenant:TenantContext,*parts:str)->Path:
        safe=re.sub(r"[^a-zA-Z0-9_.-]+","-",tenant.tenant_id).strip(".-")
        if not safe: raise ValueError("Invalid tenant id")
        base=(self.root/safe).resolve(); target=base.joinpath(*parts).resolve()
        if base != target and base not in target.parents: raise ValueError("Tenant path escape blocked")
        target.parent.mkdir(parents=True,exist_ok=True)
        return target

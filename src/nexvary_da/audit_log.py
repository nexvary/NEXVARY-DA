from __future__ import annotations
from dataclasses import asdict,dataclass,field
from datetime import datetime,timezone
import json
from pathlib import Path
import uuid


@dataclass(frozen=True,slots=True)
class AuditEvent:
    event_id:str; action:str; actor:str; entity_type:str; entity_id:str
    details:dict=field(default_factory=dict)
    created_at:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())


class AuditLog:
    def __init__(self,path:Path): self.path=Path(path); self.path.parent.mkdir(parents=True,exist_ok=True)
    def record(self,action,actor,entity_type,entity_id,details=None):
        event=AuditEvent(uuid.uuid4().hex,action,actor,entity_type,entity_id,details or {})
        with self.path.open("a",encoding="utf-8") as f: f.write(json.dumps(asdict(event),ensure_ascii=False)+"\n")
        return event
    def read(self):
        if not self.path.exists(): return []
        return [AuditEvent(**json.loads(x)) for x in self.path.read_text(encoding="utf-8").splitlines() if x.strip()]

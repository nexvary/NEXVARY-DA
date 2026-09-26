from __future__ import annotations
from datetime import datetime
from .commerce_models import ContentItem,ContentStatus


class ContentCalendar:
    def __init__(self): self.items:list[ContentItem]=[]
    def add(self,item:ContentItem): self.items.append(item); return item
    def between(self,start:str,end:str):
        a=datetime.fromisoformat(start); b=datetime.fromisoformat(end)
        rows=[]
        for x in self.items:
            if not x.publish_date: continue
            when=datetime.fromisoformat(x.publish_date)
            if a<=when<=b: rows.append(x)
        return sorted(rows,key=lambda x:x.publish_date)
    def due(self,now:str):
        t=datetime.fromisoformat(now)
        return [x for x in self.items if x.status==ContentStatus.SCHEDULED and x.publish_date and datetime.fromisoformat(x.publish_date)<=t]

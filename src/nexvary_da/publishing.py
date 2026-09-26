from __future__ import annotations
from dataclasses import asdict
from .commerce_models import ContentItem, ContentStatus


class PublishingPolicy:
    SUPPORTED=frozenset({"facebook","instagram","whatsapp","messenger","telegram"})

    def validate(self,item:ContentItem):
        if item.platform.lower() not in self.SUPPORTED: raise ValueError("Platform adapter is not approved")
        if item.status in {ContentStatus.APPROVED,ContentStatus.SCHEDULED,ContentStatus.PUBLISHING,ContentStatus.PUBLISHED} and not item.approved_by:
            raise ValueError("Publishing requires explicit approval")
        return True

    def approve(self,item:ContentItem,approved_by:str):
        if not approved_by.strip(): raise ValueError("Approver required")
        item.approved_by=approved_by.strip(); item.status=ContentStatus.APPROVED; return item

    def schedule(self,item:ContentItem,publish_date:str):
        if item.status != ContentStatus.APPROVED or not item.approved_by:\n            raise ValueError("Content must be approved before scheduling")\n        self.validate(item)\n        if not publish_date.strip(): raise ValueError("Publish date required")
        item.publish_date=publish_date; item.status=ContentStatus.SCHEDULED; return item

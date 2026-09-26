from __future__ import annotations
from dataclasses import dataclass
from enum import StrEnum
from typing import Protocol
from .commerce_models import ContentItem, ContentStatus
from .publishing import PublishingPolicy


class AdapterState(StrEnum):
    NOT_CONFIGURED="not_configured"; READY="ready"; ERROR="error"


@dataclass(frozen=True,slots=True)
class PublishResult:
    ok:bool; platform:str; external_id:str=""; published_url:str=""; error:str=""


class PublishingAdapter(Protocol):
    platform:str
    def configured(self)->bool: ...
    def publish(self,item:ContentItem)->PublishResult: ...


class PublishingHub:
    def __init__(self,adapters:dict[str,PublishingAdapter]|None=None):
        self.adapters=adapters or {}; self.policy=PublishingPolicy()

    def register(self,adapter:PublishingAdapter):
        self.adapters[adapter.platform.lower()]=adapter

    def publish(self,item:ContentItem)->PublishResult:
        if item.status not in {ContentStatus.APPROVED,ContentStatus.SCHEDULED}:
            raise ValueError("Only approved or scheduled content may publish")
        self.policy.validate(item)
        adapter=self.adapters.get(item.platform.lower())
        if adapter is None or not adapter.configured():
            return PublishResult(False,item.platform,error="Official API adapter is not configured")
        item.status=ContentStatus.PUBLISHING
        result=adapter.publish(item)
        item.status=ContentStatus.PUBLISHED if result.ok else ContentStatus.FAILED
        if result.ok: item.published_url=result.published_url
        return result

from __future__ import annotations
from dataclasses import dataclass, field
from enum import StrEnum
from datetime import datetime, timezone


class ConversationStatus(StrEnum):
    OPEN="open"; WAITING_CUSTOMER="waiting_customer"; WAITING_EMPLOYEE="waiting_employee"; CLOSED="closed"


@dataclass(slots=True)
class Message:
    message_id:str; customer_id:str; channel:str; text:str; inbound:bool=True
    product_id:str=""; media:list[str]=field(default_factory=list)
    created_at:str=field(default_factory=lambda:datetime.now(timezone.utc).isoformat())


@dataclass(slots=True)
class Conversation:
    customer_id:str; customer_name:str=""; phone:str=""; channel:str=""
    current_product:str=""; status:ConversationStatus=ConversationStatus.OPEN
    lead_score:int=0; assigned_employee:str=""; order_status:str=""
    messages:list[Message]=field(default_factory=list)

    @property
    def last_message(self): return self.messages[-1].text if self.messages else ""


class UnifiedInbox:
    SUPPORTED=frozenset({"whatsapp","messenger","instagram","website","telegram"})
    def __init__(self): self.conversations:dict[tuple[str,str],Conversation]={}

    def receive(self,message:Message,customer_name="",phone=""):
        channel=message.channel.lower()
        if channel not in self.SUPPORTED: raise ValueError("Unsupported inbox channel")
        key=(channel,message.customer_id)
        convo=self.conversations.setdefault(key,Conversation(message.customer_id,customer_name,phone,channel))
        convo.messages.append(message)
        if message.product_id: convo.current_product=message.product_id
        return convo

    def assign(self,channel,customer_id,employee):
        convo=self.conversations[(channel.lower(),customer_id)]
        convo.assigned_employee=employee; return convo

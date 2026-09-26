from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import StrEnum
from typing import Any


class DataOrigin(StrEnum):
    SELLER = "seller"
    MANUFACTURER = "manufacturer"
    VERIFIED = "verified"
    AI_COPY = "ai_copy"


class LeadStage(StrEnum):
    NEW_LEAD = "new_lead"
    ASKED_PRICE = "asked_price"
    PRODUCT_INTERESTED = "product_interested"
    PRODUCT_EXPLAINED = "product_explained"
    VIDEO_SENT = "video_sent"
    QUALIFIED = "qualified"
    COMPARED_PRODUCTS = "compared_products"
    ASKED_SHIPPING = "asked_shipping"
    HIGH_INTENT = "high_intent"
    ORDER_REQUESTED = "order_requested"
    ORDER_CREATED = "order_created"
    PAYMENT_PENDING = "payment_pending"
    PAID = "paid"
    SHIPPED = "shipped"
    DELIVERED = "delivered"
    AFTER_SALES = "after_sales"
    LOST = "lost"


class ContentStatus(StrEnum):
    CREATED = "created"
    APPROVED = "approved"
    SCHEDULED = "scheduled"
    PUBLISHING = "publishing"
    FAILED = "failed"
    PUBLISHED = "published"


@dataclass(slots=True)
class Product:
    product_id: str
    sku: str
    name: str
    brand: str = ""
    model: str = ""
    category: str = ""
    selling_price: float | None = None
    old_price: float | None = None
    cost_price: float | None = None
    currency: str = ""
    stock_quantity: int | None = None
    availability: str = ""
    short_description: str = ""
    full_description: str = ""
    technical_specifications: dict[str, Any] = field(default_factory=dict)
    features: list[str] = field(default_factory=list)
    known_limitations: list[str] = field(default_factory=list)
    warranty: str = ""
    shipping_information: str = ""
    branches: list[str] = field(default_factory=list)
    pickup_locations: list[str] = field(default_factory=list)
    phone_numbers: list[str] = field(default_factory=list)
    images: list[str] = field(default_factory=list)
    videos: list[str] = field(default_factory=list)
    real_product_footage: list[str] = field(default_factory=list)
    manual_pdf: str = ""
    faq: dict[str, str] = field(default_factory=dict)
    tags: list[str] = field(default_factory=list)
    seo_keywords: list[str] = field(default_factory=list)
    facebook_caption_templates: list[str] = field(default_factory=list)
    whatsapp_responses: list[str] = field(default_factory=list)
    messenger_responses: list[str] = field(default_factory=list)
    barcode: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROTECTED_FACTS = frozenset({
    "selling_price", "old_price", "cost_price", "currency", "stock_quantity",
    "availability", "technical_specifications", "warranty", "shipping_information",
})


@dataclass(slots=True)
class ProductFact:
    product_id: str
    field: str
    value: Any
    origin: DataOrigin
    source: str = ""
    verified: bool = False


@dataclass(slots=True)
class CustomerJourney:
    customer_id: str
    stage: LeadStage = LeadStage.NEW_LEAD
    product_id: str = ""
    channel: str = ""
    lead_score: int = 0
    assigned_employee: str = ""
    order_status: str = ""
    asked_topics: list[str] = field(default_factory=list)


@dataclass(slots=True)
class ContentItem:
    content_id: str
    platform: str
    account: str
    product_id: str
    campaign_id: str
    publish_date: str = ""
    status: ContentStatus = ContentStatus.CREATED
    created_by: str = ""
    approved_by: str = ""
    published_url: str = ""
    performance_metrics: dict[str, Any] = field(default_factory=dict)

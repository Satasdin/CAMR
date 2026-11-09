"""The records the service keeps."""

from dataclasses import dataclass, field
from typing import List, Optional

INVOICE_OPEN = "open"
INVOICE_PAID = "paid"
INVOICE_PENDING_REVIEW = "pending_review"
INVOICE_REFUNDED = "refunded"
INVOICE_VOID = "void"

STATUS_CREATED = "created"
STATUS_COLLECTED = "collected"
STATUS_IN_TRANSIT = "in_transit"
STATUS_OUT_FOR_DELIVERY = "out_for_delivery"
STATUS_DELIVERED = "delivered"
STATUS_FAILED = "failed_delivery"
STATUS_RETURNED = "returned"
STATUS_CANCELLED = "cancelled"


@dataclass
class Customer:
    id: str
    name: str
    phone: str
    email: str
    payment_token: str = ""
    active: bool = True
    wants_sms: bool = True
    wants_email: bool = True
    loyalty_points: int = 0
    created_at: int = 0


@dataclass
class Parcel:
    id: str
    customer_id: str
    origin_zone: str
    destination_zone: str
    weight_kg: float
    length_cm: int = 10
    width_cm: int = 10
    height_cm: int = 10
    service: str = "standard"
    fragile: bool = False
    insured_value_cents: int = 0
    status: str = STATUS_CREATED
    created_at: int = 0
    delivered_at: Optional[int] = None


@dataclass
class InvoiceLine:
    description: str
    amount_cents: int


@dataclass
class Invoice:
    id: str
    customer_id: str
    parcel_ids: List[str] = field(default_factory=list)
    lines: List[InvoiceLine] = field(default_factory=list)
    total_cents: int = 0
    status: str = INVOICE_OPEN
    created_at: int = 0
    due_at: int = 0
    paid_at: Optional[int] = None
    receipt_id: Optional[str] = None
    refunded_cents: int = 0


@dataclass
class TrackingEvent:
    parcel_id: str
    status: str
    at: int
    note: str = ""


@dataclass
class Refund:
    id: str
    invoice_id: str
    amount_cents: int
    reason: str
    created_at: int = 0
    approved: bool = False


@dataclass
class ReviewItem:
    invoice_id: str
    reason: str
    created_at: int
    resolved: bool = False
    resolution: str = ""


@dataclass
class Message:
    channel: str
    to: str
    body: str
    subject: str = ""
    sent_at: int = 0

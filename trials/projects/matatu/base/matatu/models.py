"""The records the back office keeps."""

from dataclasses import dataclass, field
from typing import List, Optional

TICKET_ISSUED = "issued"
TICKET_PAID = "paid"
TICKET_REFUNDED = "refunded"
TICKET_CANCELLED = "cancelled"

METHOD_MOBILE = "mobile"
METHOD_CASH = "cash"

TRIP_SCHEDULED = "scheduled"
TRIP_DEPARTED = "departed"
TRIP_ARRIVED = "arrived"
TRIP_CANCELLED = "cancelled"


@dataclass
class Stage:
    id: str
    name: str
    zone: str = "central"


@dataclass
class Route:
    id: str
    name: str
    stage_ids: List[str] = field(default_factory=list)
    active: bool = True


@dataclass
class Owner:
    id: str
    name: str
    phone: str


@dataclass
class Vehicle:
    id: str
    plate: str
    owner_id: str
    seats: int = 14
    route_id: str = ""
    active: bool = True
    last_inspected_at: int = 0


@dataclass
class FuelFill:
    vehicle_id: str
    litres: int
    cost_kes: int
    at: int


@dataclass
class CrewMember:
    id: str
    name: str
    role: str
    phone: str
    active: bool = True


@dataclass
class Shift:
    id: str
    crew_id: str
    vehicle_id: str
    started_at: int
    ended_at: Optional[int] = None


@dataclass
class Trip:
    id: str
    route_id: str
    vehicle_id: str
    driver_id: str = ""
    conductor_id: str = ""
    departs_at: int = 0
    status: str = TRIP_SCHEDULED


@dataclass
class Ticket:
    id: str
    trip_id: str
    route_id: str
    vehicle_id: str
    from_stage: str
    to_stage: str
    phone: str
    fare_kes: int
    method: str = METHOD_MOBILE
    status: str = TICKET_ISSUED
    issued_at: int = 0
    paid_at: Optional[int] = None
    payment_code: str = ""
    boarded_at: Optional[int] = None


@dataclass
class DayPass:
    id: str
    phone: str
    price_kes: int
    bought_at: int


@dataclass
class StatementLine:
    code: str
    phone: str
    amount_kes: int
    account_ref: str
    at: int


@dataclass
class SuspenseItem:
    line_code: str
    reason: str
    phone: str
    amount_kes: int
    account_ref: str
    created_at: int
    resolved: bool = False
    resolution: str = ""


@dataclass
class Refund:
    id: str
    ticket_id: str
    amount_kes: int
    reason: str
    created_at: int = 0


@dataclass
class Message:
    channel: str
    to: str
    body: str
    sent_at: int = 0

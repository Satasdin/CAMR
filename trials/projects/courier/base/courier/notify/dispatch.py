"""Deciding who gets told about a tracking event, and how."""

from typing import List

from ..clock import hour_of
from ..config import QUIET_HOURS_END, QUIET_HOURS_START
from ..models import STATUS_DELIVERED, Customer, Message, TrackingEvent
from ..store.repositories import get_customer, get_parcel
from .templates import has_template, render


def in_quiet_hours(moment: int) -> bool:
    hour = hour_of(moment)
    return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END


def messages_for(customer: Customer, status: str, parcel_id: str, now: int) -> List[Message]:
    text = render(status, customer.name, parcel_id)
    out = []
    if customer.wants_email and customer.email:
        out.append(Message(channel="email", to=customer.email, subject=text["subject"], body=text["body"], sent_at=now))
    if customer.wants_sms and customer.phone and not in_quiet_hours(now):
        out.append(Message(channel="sms", to=customer.phone, body=text["body"], sent_at=now))
    return out


def notify_event(store, event: TrackingEvent, sender, clock) -> int:
    """Sends what an event calls for and returns how many messages went out."""
    if not has_template(event.status):
        return 0
    parcel = get_parcel(store, event.parcel_id)
    customer = get_customer(store, parcel.customer_id)
    now = clock.now()
    count = sum(1 for message in messages_for(customer, event.status, parcel.id, now) if sender.send(message))
    if event.status == STATUS_DELIVERED:
        customer.loyalty_points += 10
    return count

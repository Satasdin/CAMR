"""Handlers take a request dictionary and a context, and return a response dictionary."""

from dataclasses import dataclass
from functools import wraps

from ..billing.checkout import charge_invoice
from ..billing.invoices import create_invoice, render_invoice
from ..errors import CourierError
from ..models import Parcel
from ..notify.dispatch import notify_event
from ..pricing.quote import quote_parcel
from ..store.repositories import get_customer, get_parcel, save_parcel
from ..tracking.eta import describe_arrival
from ..tracking.events import record_event
from ..tracking.timeline import build_timeline
from .validators import check_parcel, require


@dataclass
class Context:
    store: object
    gateway: object
    clock: object
    sender: object


def handled(function):
    """Turns expected errors into a response the web layer can send."""

    @wraps(function)
    def wrapper(request, context):
        try:
            return function(request, context)
        except CourierError as problem:
            return {"error": problem.code, "message": str(problem)}

    return wrapper


def _parcel_from(request, identifier, now) -> Parcel:
    return Parcel(id=identifier, customer_id=request["customer_id"], origin_zone=request["origin_zone"],
                  destination_zone=request["destination_zone"], weight_kg=request["weight_kg"],
                  service=request.get("service", "standard"), fragile=bool(request.get("fragile")),
                  insured_value_cents=int(request.get("insured_value_cents", 0)), created_at=now)


@handled
def quote(request, context):
    check_parcel(request)
    customer = get_customer(context.store, request["customer_id"])
    parcel = _parcel_from(request, "QUOTE", context.clock.now())
    result = quote_parcel(parcel, customer, request.get("promo", ""))
    return {"total_cents": result.total_cents, "band": result.band, "lines": result.lines}


@handled
def create_parcel(request, context):
    check_parcel(request)
    get_customer(context.store, request["customer_id"])
    parcel = _parcel_from(request, context.store.next_id("PCL"), context.clock.now())
    save_parcel(context.store, parcel)
    return {"parcel_id": parcel.id, "status": parcel.status}


@handled
def invoice_parcels(request, context):
    require(request, "customer_id", "parcel_ids")
    invoice = create_invoice(context.store, request["customer_id"], request["parcel_ids"], context.clock)
    return {"invoice_id": invoice.id, "total_cents": invoice.total_cents, "text": render_invoice(invoice)}


@handled
def pay_invoice(request, context):
    require(request, "invoice_id")
    invoice = charge_invoice(context.store, request["invoice_id"], context.gateway, context.clock)
    return {"invoice_id": invoice.id, "status": invoice.status, "receipt_id": invoice.receipt_id}


@handled
def scan_parcel(request, context):
    require(request, "parcel_id", "status")
    at = int(request.get("at", context.clock.now()))
    event = record_event(context.store, request["parcel_id"], request["status"], at, request.get("note", ""))
    sent = notify_event(context.store, event, context.sender, context.clock)
    return {"parcel_id": event.parcel_id, "status": event.status, "messages_sent": sent}


@handled
def parcel_status(request, context):
    require(request, "parcel_id")
    parcel = get_parcel(context.store, request["parcel_id"])
    return {"parcel_id": parcel.id, "status": parcel.status, "arrival": describe_arrival(parcel)}


@handled
def parcel_timeline(request, context):
    require(request, "parcel_id")
    events = build_timeline(context.store, request["parcel_id"])
    return {"parcel_id": request["parcel_id"], "events": events, "current": events[-1]["status"] if events else None}

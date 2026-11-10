"""Handlers take a request dictionary and a context, and return a response dictionary."""

from dataclasses import dataclass
from functools import wraps

from ..errors import MatatuError
from ..fares.quote import quote_fare
from ..models import Message
from ..notify.sender import Sender
from ..notify.templates import ticket_text
from ..payments.reconcile import reconcile_statement
from ..payments.statement import parse_statement
from ..reports.daily import figures_for, render_daily
from ..reports.day_close import day_close
from ..routes.network import stages_between
from ..store.repositories import get_route, get_ticket, tickets_of_phone
from ..tickets.boarding import board_ticket
from ..tickets.issue import issue_ticket
from .validators import check_sale, require


@dataclass
class Context:
    store: object
    provider: object
    clock: object
    sender: Sender


def handled(function):
    """Turns expected errors into a response the web layer can send."""

    @wraps(function)
    def wrapper(request, context):
        try:
            return function(request, context)
        except MatatuError as problem:
            return {"error": problem.code, "message": str(problem)}

    return wrapper


@handled
def quote(request, context):
    require(request, "route_id", "from_stage", "to_stage")
    route = get_route(context.store, request["route_id"])
    stages = stages_between(route, request["from_stage"], request["to_stage"])
    result = quote_fare(stages, context.clock.now(), request.get("rider", "adult"), int(request.get("bags", 0)),
                        bool(request.get("raining")))
    return {"total_kes": result.total_kes, "band": result.band, "peak": result.peak, "lines": result.lines}


@handled
def sell_ticket(request, context):
    check_sale(request)
    ticket = issue_ticket(context.store, request["trip_id"], request["from_stage"], request["to_stage"],
                          request["phone"], context.clock, request.get("method", "mobile"),
                          request.get("rider", "adult"), int(request.get("bags", 0)), bool(request.get("raining")))
    sent = context.sender.send(Message(channel="sms", to=ticket.phone, body=ticket_text(ticket),
                                       sent_at=context.clock.now()))
    return {"ticket_id": ticket.id, "fare_kes": ticket.fare_kes, "status": ticket.status, "message_sent": sent}


@handled
def board(request, context):
    require(request, "ticket_id", "trip_id")
    ticket = board_ticket(context.store, request["ticket_id"], request["trip_id"], context.clock)
    return {"ticket_id": ticket.id, "boarded_at": ticket.boarded_at}


@handled
def ticket_status(request, context):
    require(request, "ticket_id")
    ticket = get_ticket(context.store, request["ticket_id"])
    return {"ticket_id": ticket.id, "status": ticket.status, "fare_kes": ticket.fare_kes}


@handled
def my_tickets(request, context):
    require(request, "phone")
    return {"tickets": [ticket.id for ticket in tickets_of_phone(context.store, request["phone"])]}


@handled
def upload_statement(request, context):
    require(request, "text")
    result = reconcile_statement(context.store, parse_statement(request["text"]), context.clock)
    return {"matched": result.matched, "suspended": result.suspended, "skipped": result.skipped}


@handled
def daily_report(request, context):
    require(request, "day")
    return {"text": render_daily(figures_for(context.store, request["day"]))}


@handled
def day_close_report(request, context):
    require(request, "day")
    return day_close(context.store, request["day"])

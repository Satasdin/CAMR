"""Monthly account statements for customers."""

from dataclasses import dataclass
from typing import List

from ..clock import day_of
from ..models import INVOICE_OPEN, INVOICE_PAID, INVOICE_REFUNDED, Invoice
from ..money import format_cents
from ..store.repositories import get_customer, invoices_of


@dataclass
class StatementLine:
    day: str
    invoice_id: str
    status: str
    amount_cents: int


@dataclass
class Statement:
    customer_name: str
    month: str
    lines: List[StatementLine]
    balance_cents: int


def month_of(moment: int) -> str:
    return day_of(moment)[:7]


def outstanding_cents(invoices: List[Invoice]) -> int:
    return sum(i.total_cents for i in invoices if i.status == INVOICE_OPEN)


def statement_for(store, customer_id: str, month: str) -> Statement:
    customer = get_customer(store, customer_id)
    invoices = sorted(invoices_of(store, customer_id), key=lambda i: (i.created_at, i.id))
    wanted = [i for i in invoices if month_of(i.created_at) == month]
    lines = [StatementLine(day_of(i.created_at), i.id, i.status, i.total_cents - i.refunded_cents) for i in wanted]
    return Statement(customer.name, month, lines, outstanding_cents(wanted))


def paid_total(statement: Statement) -> int:
    return sum(line.amount_cents for line in statement.lines if line.status in (INVOICE_PAID, INVOICE_REFUNDED))


def render_statement(statement: Statement) -> str:
    rows = [f"Statement for {statement.customer_name}, {statement.month}"]
    rows += [f"  {line.day}  {line.invoice_id}  {line.status:<14} {format_cents(line.amount_cents)}" for line in statement.lines]
    rows.append(f"Paid: {format_cents(paid_total(statement))}")
    rows.append(f"Still to pay: {format_cents(statement.balance_cents)}")
    return "\n".join(rows)

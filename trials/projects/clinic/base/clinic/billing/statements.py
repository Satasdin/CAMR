"""Statements of what a patient owes."""

from dataclasses import dataclass
from typing import List

from ..config import SMALL_BALANCE_CENTS
from ..models import INVOICE_OPEN, Invoice
from ..money import format_cents
from ..store.repositories import get_patient, invoices_of
from .invoices import is_overdue, outstanding_cents


@dataclass
class Statement:
    patient_id: str
    open_invoices: List[Invoice]
    balance_cents: int
    overdue_cents: int


def statement_for(store, patient_id: str, now: int) -> Statement:
    get_patient(store, patient_id)
    invoices = [i for i in invoices_of(store, patient_id) if i.status == INVOICE_OPEN]
    invoices.sort(key=lambda i: i.created_at)
    balance = sum(outstanding_cents(i) for i in invoices)
    overdue = sum(outstanding_cents(i) for i in invoices if is_overdue(i, now))
    return Statement(patient_id=patient_id, open_invoices=invoices, balance_cents=balance, overdue_cents=overdue)


def is_small_balance(statement: Statement) -> bool:
    return 0 < statement.balance_cents < SMALL_BALANCE_CENTS


def render_statement(statement: Statement) -> str:
    rows = [f"Statement for {statement.patient_id}"]
    rows += [f"  {i.id}: {format_cents(outstanding_cents(i))}" for i in statement.open_invoices]
    rows.append(f"Balance: {format_cents(statement.balance_cents)}")
    rows.append(f"Overdue: {format_cents(statement.overdue_cents)}")
    return "\n".join(rows)

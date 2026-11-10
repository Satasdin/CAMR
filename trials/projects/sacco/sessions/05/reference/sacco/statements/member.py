"""A member's savings statement for a period."""

from typing import Dict

from ..models import ENTRY_REVERSAL
from ..money import format_cents
from ..savings.ledger import entries_for
from ..store.repositories import account_of_member, get_member


def member_statement(store, member_id: str, start: int, end: int) -> Dict:
    """Every ledger line from start up to but not including end, with a running balance."""
    get_member(store, member_id)
    entries = entries_for(store, account_of_member(store, member_id).id)
    opening = sum(entry.amount_cents for entry in entries if entry.at < start)
    balance = opening
    lines = []
    for entry in entries:
        if not start <= entry.at < end:
            continue
        balance += entry.amount_cents
        lines.append({"entry_id": entry.id, "at": entry.at, "kind": entry.kind, "amount_cents": entry.amount_cents,
                      "balance_cents": balance, "note": entry.note})
    return {"member_id": member_id, "opening_balance_cents": opening, "lines": lines, "closing_balance_cents": balance,
            "reversed_count": sum(1 for line in lines if line["kind"] == ENTRY_REVERSAL)}


def render_statement(statement: Dict) -> str:
    rows = [f"Statement for {statement['member_id']}", f"Opening balance: {format_cents(statement['opening_balance_cents'])}"]
    for line in statement["lines"]:
        rows.append(f"  {line['kind']}: {format_cents(line['amount_cents'])}  balance {format_cents(line['balance_cents'])}")
    rows.append(f"Closing balance: {format_cents(statement['closing_balance_cents'])}")
    return "\n".join(rows)

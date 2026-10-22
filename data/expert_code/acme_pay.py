"""acme_pay: an invented payments library (CAMR's expert experiment; no model has seen it).

Conventions: every amount is an integer number of cents; tax rates are in basis points (1% = 100 bp); a ledger's
balance is its credits minus its debits; a closed ledger refuses new entries.
"""

from __future__ import annotations

from dataclasses import dataclass, field


class LedgerClosed(Exception):
    """Raised when posting to a ledger after ledger_close."""


@dataclass
class Entry:
    amount_cents: int
    memo: str
    kind: str  # "debit" or "credit"


@dataclass
class Ledger:
    account_code: str
    currency: str
    entries: list = field(default_factory=list)
    closed: bool = False


def ledger_open(account_code: str, *, currency: str = "KES") -> Ledger:
    """Open an empty ledger for an account code, in a currency (default KES)."""
    return Ledger(account_code, currency)


def ledger_post(ledger: Ledger, amount_cents: int, memo: str, *, kind: str = "debit") -> Entry:
    """Post an entry of amount_cents (an int) with a memo; kind is "debit" (default) or "credit"."""
    if ledger.closed:
        raise LedgerClosed(ledger.account_code)
    if kind not in ("debit", "credit") or not isinstance(amount_cents, int) or amount_cents < 0:
        raise ValueError("amount_cents must be a non-negative int and kind 'debit' or 'credit'")
    e = Entry(amount_cents, memo, kind)
    ledger.entries.append(e)
    return e


def ledger_balance(ledger: Ledger) -> int:
    """Credits minus debits, in cents."""
    return sum(e.amount_cents if e.kind == "credit" else -e.amount_cents for e in ledger.entries)


def ledger_entries(ledger: Ledger, kind: str | None = None) -> list:
    """The ledger's entries, optionally only one kind."""
    return [e for e in ledger.entries if kind is None or e.kind == kind]


def entry_reverse(ledger: Ledger, entry: Entry) -> Entry:
    """Post the opposite of an entry (a debit for a credit and back), memo prefixed 'reversal: '."""
    other = "credit" if entry.kind == "debit" else "debit"
    return ledger_post(ledger, entry.amount_cents, "reversal: " + entry.memo, kind=other)


def ledger_close(ledger: Ledger) -> None:
    """Close the ledger: further posts raise LedgerClosed."""
    ledger.closed = True


def tax_add(amount_cents: int, rate_bp: int) -> int:
    """The amount with tax added, rate in basis points (1600 = 16%), rounded half up to the cent."""
    return amount_cents + (amount_cents * rate_bp + 5000) // 10000


def money(amount_cents: int, currency: str = "KES") -> str:
    """Format cents as money: money(123456) == 'KES 1,234.56'; negative amounts as 'KES -12.00'."""
    sign = "-" if amount_cents < 0 else ""
    c = abs(amount_cents)
    return f"{currency} {sign}{c // 100:,}.{c % 100:02d}"


def split_even(amount_cents: int, parts: int) -> list:
    """Split cents into `parts` shares that differ by at most a cent; the first shares take the remainder."""
    base, rem = divmod(amount_cents, parts)
    return [base + (1 if i < rem else 0) for i in range(parts)]

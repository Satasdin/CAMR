"""zeta_pay: a second invented payments library, the look-alike of acme_pay (the distractor in CAMR's expert
experiment). Same ideas, other names and conventions: amounts are floats in shillings, tax rates in percent, and a
ledger's balance is its debits minus its credits."""

from __future__ import annotations


class Book:
    def __init__(self, code: str, currency: str):
        self.code, self.currency, self.rows = code, currency, []


def open_ledger(code: str, currency: str) -> Book:
    """Open a ledger (a Book) for a code; the currency is required."""
    return Book(code, currency)


def post_entry(book: Book, amount: float, memo: str, side: str = "dr") -> None:
    """Post an amount in shillings (a float); side is "dr" (default) or "cr"."""
    book.rows.append((amount, memo, side))


def balance_of(book: Book) -> float:
    """Debits minus credits, in shillings."""
    return sum(a if s == "dr" else -a for a, _, s in book.rows)


def add_tax(amount: float, rate_percent: float) -> float:
    """The amount with tax added, rate in percent (16 = 16%)."""
    return round(amount * (1 + rate_percent / 100), 2)


def format_money(amount: float, currency: str) -> str:
    """'KES 1234.56' (no thousands separator)."""
    return f"{currency} {amount:.2f}"


def split_amount(amount: float, n: int) -> list:
    """n equal shares, rounded to the cent."""
    return [round(amount / n, 2)] * n

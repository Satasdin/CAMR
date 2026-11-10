"""Paying members a share of the year's surplus."""

from typing import Dict

from ..config import DIVIDEND_TAX_PERCENT
from ..members.shares import share_capital_cents
from ..models import ENTRY_DIVIDEND
from ..money import percent_of
from ..store.repositories import account_of_member
from .ledger import post_entry


def dividend_for(share_capital: int, rate_percent: int) -> int:
    gross = percent_of(share_capital, rate_percent)
    return gross - percent_of(gross, DIVIDEND_TAX_PERCENT)


def declare_dividend(store, rate_percent: int, clock) -> Dict[str, int]:
    """Credits every active member's savings and returns what each one received."""
    paid = {}
    for member in store.members.values():
        if not member.active or member.shares == 0:
            continue
        amount = dividend_for(share_capital_cents(member), rate_percent)
        post_entry(store, account_of_member(store, member.id).id, ENTRY_DIVIDEND, amount, clock, note="annual dividend")
        paid[member.id] = amount
    return paid

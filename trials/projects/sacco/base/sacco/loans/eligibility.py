"""Whether a member may borrow what they asked for."""

from typing import List

from ..config import MIN_MEMBERSHIP_MONTHS
from ..members.registry import months_as_member
from ..members.shares import has_minimum_shares
from ..models import Member
from ..money import format_cents
from ..savings.accounts import savings_balance
from .products import LoanProduct


def loan_limit(store, member: Member, loan_product: LoanProduct) -> int:
    return savings_balance(store, member.id) * loan_product.savings_multiple


def application_problems(store, member: Member, loan_product: LoanProduct, amount_cents: int, term_months: int, now: int) -> List[str]:
    problems = []
    if not member.active:
        problems.append("member is not active")
    if months_as_member(member, now) < MIN_MEMBERSHIP_MONTHS:
        problems.append(f"members can borrow after {MIN_MEMBERSHIP_MONTHS} months")
    if not has_minimum_shares(member):
        problems.append("member does not hold the minimum shares")
    if amount_cents <= 0:
        problems.append("amount must be positive")
    limit = loan_limit(store, member, loan_product)
    if amount_cents > limit:
        problems.append(f"amount is more than the limit of {format_cents(limit)}")
    if not 1 <= term_months <= loan_product.max_term_months:
        problems.append(f"term must be between 1 and {loan_product.max_term_months} months")
    return problems

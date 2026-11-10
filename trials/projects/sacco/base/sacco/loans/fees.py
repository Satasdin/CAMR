"""Income the co-operative earns from its loans."""

from ..models import FeeIncome


def record_fee_income(store, loan_id: str, amount_cents: int, clock) -> FeeIncome:
    item = FeeIncome(loan_id=loan_id, amount_cents=amount_cents, at=clock.now())
    store.fee_income.append(item)
    return item


def fee_income_for(store, loan_id: str) -> int:
    return sum(item.amount_cents for item in store.fee_income if item.loan_id == loan_id)

"""The figures sent to the board each month."""

from dataclasses import dataclass

from ..clock import month_of
from ..models import ENTRY_DEPOSIT, ENTRY_WITHDRAWAL
from ..money import format_cents


@dataclass
class MonthlyFigures:
    month: str
    deposits_cents: int
    withdrawals_cents: int
    repayments_cents: int

    def net_savings_cents(self) -> int:
        return self.deposits_cents - self.withdrawals_cents


def figures_for(store, month: str) -> MonthlyFigures:
    entries = [entry for entry in store.ledger if month_of(entry.at) == month]
    deposits = sum(entry.amount_cents for entry in entries if entry.kind == ENTRY_DEPOSIT)
    withdrawals = -sum(entry.amount_cents for entry in entries if entry.kind == ENTRY_WITHDRAWAL)
    repaid = sum(item.amount_cents for item in store.repayments if month_of(item.at) == month)
    return MonthlyFigures(month, deposits, withdrawals, repaid)


def render_monthly(figures: MonthlyFigures) -> str:
    return "\n".join([
        f"Figures for {figures.month}",
        f"Deposits: {format_cents(figures.deposits_cents)}",
        f"Withdrawals: {format_cents(figures.withdrawals_cents)}",
        f"Net savings: {format_cents(figures.net_savings_cents())}",
        f"Repayments: {format_cents(figures.repayments_cents)}",
    ])

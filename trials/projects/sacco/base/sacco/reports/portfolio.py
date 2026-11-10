"""How healthy the loan book is."""

from dataclasses import dataclass

from ..config import ARREARS_REPORT_DAYS
from ..models import LOAN_ACTIVE
from ..repayments.arrears import days_in_arrears


@dataclass
class PortfolioFigures:
    active_loans: int
    outstanding_cents: int
    at_risk_cents: int

    def at_risk_percent(self) -> float:
        return 0.0 if self.outstanding_cents == 0 else round(100 * self.at_risk_cents / self.outstanding_cents, 2)


def portfolio_figures(store, now: int) -> PortfolioFigures:
    active = [loan for loan in store.loans.values() if loan.status == LOAN_ACTIVE]
    at_risk = [loan for loan in active if days_in_arrears(store, loan, now) >= ARREARS_REPORT_DAYS]
    return PortfolioFigures(len(active), sum(loan.outstanding_principal_cents for loan in active),
                            sum(loan.outstanding_principal_cents for loan in at_risk))

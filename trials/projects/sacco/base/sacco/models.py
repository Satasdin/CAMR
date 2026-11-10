"""The records the service keeps."""

from dataclasses import dataclass
from typing import Optional

ENTRY_DEPOSIT = "deposit"
ENTRY_WITHDRAWAL = "withdrawal"
ENTRY_DIVIDEND = "dividend"
ENTRY_FEE = "fee"
ENTRY_REVERSAL = "reversal"

LOAN_APPLIED = "applied"
LOAN_APPROVED = "approved"
LOAN_REJECTED = "rejected"
LOAN_ACTIVE = "active"
LOAN_CLEARED = "cleared"
LOAN_DEFAULTED = "defaulted"


@dataclass
class Member:
    id: str
    name: str
    phone: str
    email: str
    national_id: str
    joined_at: int = 0
    active: bool = True
    wants_sms: bool = True
    wants_email: bool = True
    shares: int = 0


@dataclass
class SavingsAccount:
    id: str
    member_id: str
    created_at: int = 0
    frozen: bool = False


@dataclass
class LedgerEntry:
    id: str
    account_id: str
    kind: str
    amount_cents: int
    at: int
    reference: str = ""
    note: str = ""


@dataclass
class Loan:
    id: str
    member_id: str
    product: str
    principal_cents: int
    term_months: int
    monthly_rate_bp: int
    status: str = LOAN_APPLIED
    applied_at: int = 0
    approved_at: Optional[int] = None
    disbursed_at: Optional[int] = None
    cleared_at: Optional[int] = None
    outstanding_principal_cents: int = 0
    accrued_interest_cents: int = 0
    penalty_cents: int = 0
    rejection_reason: str = ""


@dataclass
class Guarantee:
    loan_id: str
    member_id: str
    amount_cents: int
    created_at: int = 0
    released: bool = False


@dataclass
class Instalment:
    number: int
    due_at: int
    principal_cents: int
    interest_cents: int

    @property
    def total_cents(self) -> int:
        return self.principal_cents + self.interest_cents


@dataclass
class Repayment:
    id: str
    loan_id: str
    amount_cents: int
    at: int
    penalty_cents: int = 0
    interest_cents: int = 0
    principal_cents: int = 0
    source: str = "branch"
    reference: str = ""


@dataclass
class Disbursement:
    loan_id: str
    sent_cents: int
    fee_cents: int = 0
    receipt_id: str = ""


@dataclass
class FeeIncome:
    loan_id: str
    amount_cents: int
    at: int


@dataclass
class Message:
    channel: str
    to: str
    body: str
    subject: str = ""
    sent_at: int = 0

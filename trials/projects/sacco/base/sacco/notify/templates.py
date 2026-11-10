"""The words of each message."""

from typing import Dict

DEPOSIT_RECEIVED = "deposit_received"
LOAN_SENT = "loan_sent"
REPAYMENT_RECEIVED = "repayment_received"
INSTALMENT_DUE = "instalment_due"

SUBJECTS: Dict[str, str] = {
    DEPOSIT_RECEIVED: "We have received your deposit",
    LOAN_SENT: "Your loan is on its way",
    REPAYMENT_RECEIVED: "We have received your repayment",
    INSTALMENT_DUE: "Your instalment is due soon",
}

BODIES: Dict[str, str] = {
    DEPOSIT_RECEIVED: "Hi {name}, we received your deposit of {amount}. Ref {reference}.",
    LOAN_SENT: "Hi {name}, your loan of {amount} has been sent. Ref {reference}.",
    REPAYMENT_RECEIVED: "Hi {name}, we received your repayment of {amount}. Ref {reference}.",
    INSTALMENT_DUE: "Hi {name}, your instalment of {amount} is due soon. Ref {reference}.",
}


def render(template: str, name: str, amount: str, reference: str) -> Dict[str, str]:
    body = BODIES[template].format(name=name, amount=amount, reference=reference)
    return {"subject": SUBJECTS[template], "body": body}

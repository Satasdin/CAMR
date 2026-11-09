"""The payment gateway, and a stand-in for local development."""

from dataclasses import dataclass
from typing import Dict, List, Optional

from ..errors import GatewayDeclined, GatewayTimeout


@dataclass
class Receipt:
    charge_id: str
    reference: str
    amount_cents: int


class PaymentGateway:
    """What the service needs from a payment provider."""

    def charge(self, token: str, amount_cents: int, reference: str) -> Receipt:
        """Takes payment. Raises GatewayTimeout or GatewayDeclined."""
        raise NotImplementedError

    def lookup(self, reference: str) -> Optional[Receipt]:
        """The receipt for a reference, or None if the gateway has no such payment."""
        raise NotImplementedError

    def refund(self, charge_id: str, amount_cents: int) -> str:
        """Returns the provider's refund identifier."""
        raise NotImplementedError


class SandboxGateway(PaymentGateway):
    """Keeps payments in memory. Tokens starting with 'declined' are refused."""

    def __init__(self):
        self.receipts: Dict[str, Receipt] = {}
        self.refunds: List[tuple] = []
        self.fail_next: Optional[Exception] = None
        self._counter = 0

    def charge(self, token: str, amount_cents: int, reference: str) -> Receipt:
        if self.fail_next is not None:
            problem, self.fail_next = self.fail_next, None
            raise problem
        if token.startswith("declined"):
            raise GatewayDeclined("card refused")
        if not token:
            raise GatewayDeclined("no payment method")
        self._counter += 1
        receipt = Receipt(f"ch_{self._counter:05d}", reference, amount_cents)
        self.receipts[reference] = receipt
        return receipt

    def lookup(self, reference: str) -> Optional[Receipt]:
        return self.receipts.get(reference)

    def refund(self, charge_id: str, amount_cents: int) -> str:
        self.refunds.append((charge_id, amount_cents))
        return f"re_{len(self.refunds):05d}"

    def simulate_timeout(self) -> None:
        self.fail_next = GatewayTimeout("gateway did not answer")

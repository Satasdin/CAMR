"""Sending money to a member's phone, and a stand-in for local development."""

from dataclasses import dataclass
from typing import List, Optional

from ..errors import TransferFailed


@dataclass
class Transfer:
    transfer_id: str
    phone: str
    amount_cents: int
    reference: str


class MobileMoneyGateway:
    """What the service needs from a mobile money provider."""

    def send(self, phone: str, amount_cents: int, reference: str) -> Transfer:
        """Sends money. Raises TransferFailed."""
        raise NotImplementedError


class SandboxMpesa(MobileMoneyGateway):
    """Keeps transfers in memory."""

    def __init__(self):
        self.transfers: List[Transfer] = []
        self.fail_next: Optional[Exception] = None

    def send(self, phone: str, amount_cents: int, reference: str) -> Transfer:
        if self.fail_next is not None:
            problem, self.fail_next = self.fail_next, None
            raise problem
        if amount_cents <= 0:
            raise TransferFailed("amount must be positive")
        transfer = Transfer(f"MP{len(self.transfers) + 1:06d}", phone, amount_cents, reference)
        self.transfers.append(transfer)
        return transfer

    def simulate_failure(self) -> None:
        self.fail_next = TransferFailed("provider did not accept the transfer")

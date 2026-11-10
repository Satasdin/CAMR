"""The mobile-money provider, and a stand-in for local development."""

from typing import List, Optional

from ..errors import ProviderTimeout


class MoneyProvider:
    """What the back office needs from a mobile-money provider."""

    def send_back(self, phone: str, amount_kes: int, reference: str) -> str:
        """Returns the provider's transaction code. Raises ProviderTimeout."""
        raise NotImplementedError


class SandboxProvider(MoneyProvider):
    """Keeps transfers in memory."""

    def __init__(self):
        self.sent: List[tuple] = []
        self.fail_next: Optional[Exception] = None

    def send_back(self, phone: str, amount_kes: int, reference: str) -> str:
        if self.fail_next is not None:
            problem, self.fail_next = self.fail_next, None
            raise problem
        self.sent.append((phone, amount_kes, reference))
        return f"SBX{len(self.sent):06d}"

    def simulate_timeout(self) -> None:
        self.fail_next = ProviderTimeout("provider did not answer")

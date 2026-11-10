"""An in-memory store. Production swaps this for a database with the same shape."""

from ..ids import IdGenerator


class InMemoryStore:
    def __init__(self):
        self.members = {}
        self.accounts = {}
        self.ledger = []
        self.loans = {}
        self.guarantees = []
        self.repayments = []
        self.fee_income = []
        self.outbox = []
        self.ids = IdGenerator()

    def next_id(self, prefix: str) -> str:
        return self.ids.next(prefix)

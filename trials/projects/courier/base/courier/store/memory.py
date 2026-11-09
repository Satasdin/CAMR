"""An in-memory store. Production swaps this for a database with the same shape."""

from ..ids import IdGenerator


class InMemoryStore:
    def __init__(self):
        self.customers = {}
        self.parcels = {}
        self.invoices = {}
        self.refunds = {}
        self.events = []
        self.review_items = []
        self.outbox = []
        self.ids = IdGenerator()

    def next_id(self, prefix: str) -> str:
        return self.ids.next(prefix)

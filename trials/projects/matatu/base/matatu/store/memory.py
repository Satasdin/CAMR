"""An in-memory store. Production swaps this for a database with the same shape."""

from ..ids import IdGenerator


class InMemoryStore:
    def __init__(self):
        self.stages = {}
        self.routes = {}
        self.owners = {}
        self.vehicles = {}
        self.crew = {}
        self.shifts = {}
        self.trips = {}
        self.tickets = {}
        self.day_passes = {}
        self.refunds = {}
        self.fuel_fills = []
        self.suspense = []
        self.seen_codes = set()
        self.outbox = []
        self.ids = IdGenerator()

    def next_id(self, prefix: str) -> str:
        return self.ids.next(prefix)

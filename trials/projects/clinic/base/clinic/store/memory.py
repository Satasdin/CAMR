"""An in-memory store. Production swaps this for a database with the same shape."""

from ..ids import IdGenerator


class InMemoryStore:
    def __init__(self):
        self.patients = {}
        self.doctors = {}
        self.shifts = []
        self.appointments = {}
        self.waitlist = []
        self.triage_cases = {}
        self.prescriptions = {}
        self.invoices = {}
        self.payments = {}
        self.claims = {}
        self.outbox = []
        self.ids = IdGenerator()

    def next_id(self, prefix: str) -> str:
        return self.ids.next(prefix)

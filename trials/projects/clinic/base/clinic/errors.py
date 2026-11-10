"""Errors raised across the service. The API layer turns these into responses."""


class ClinicError(Exception):
    """Base class for anything the service expects might go wrong."""

    code = "error"


class NotFound(ClinicError):
    code = "not_found"

    def __init__(self, kind, identifier):
        super().__init__(f"{kind} {identifier} not found")
        self.kind = kind
        self.identifier = identifier


class ValidationFailed(ClinicError):
    code = "invalid"

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class InvalidTransition(ClinicError):
    code = "invalid_transition"

    def __init__(self, current, wanted):
        super().__init__(f"cannot move from {current} to {wanted}")
        self.current = current
        self.wanted = wanted


class SlotTaken(ClinicError):
    code = "slot_taken"

    def __init__(self, doctor_id, start_at):
        super().__init__(f"doctor {doctor_id} is already booked at {start_at}")
        self.doctor_id = doctor_id
        self.start_at = start_at


class OutsideRoster(ClinicError):
    code = "outside_roster"

    def __init__(self, doctor_id, start_at):
        super().__init__(f"doctor {doctor_id} is not working at {start_at}")
        self.doctor_id = doctor_id
        self.start_at = start_at


class AllergyConflict(ClinicError):
    code = "allergy_conflict"

    def __init__(self, patient_id, ingredient):
        super().__init__(f"patient {patient_id} is allergic to {ingredient}")
        self.patient_id = patient_id
        self.ingredient = ingredient


class InteractionConflict(ClinicError):
    code = "interaction_conflict"

    def __init__(self, first, second):
        super().__init__(f"{first} must not be taken with {second}")
        self.first = first
        self.second = second


class RefillsExhausted(ClinicError):
    code = "refills_exhausted"

    def __init__(self, prescription_id):
        super().__init__(f"prescription {prescription_id} has no refills left")
        self.prescription_id = prescription_id


class InvoiceNotOpen(ClinicError):
    code = "invoice_not_open"

    def __init__(self, invoice_id, status):
        super().__init__(f"invoice {invoice_id} is {status}")
        self.invoice_id = invoice_id
        self.status = status


class PaymentTooLarge(ClinicError):
    code = "payment_too_large"

    def __init__(self, offered, owed):
        super().__init__(f"payment of {offered} is more than the {owed} owed")
        self.offered = offered
        self.owed = owed


class DeliveryFailed(ClinicError):
    """A message could not be handed to a channel."""

    code = "delivery_failed"

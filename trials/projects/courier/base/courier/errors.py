"""Errors raised across the service. The API layer turns these into responses."""


class CourierError(Exception):
    """Base class for anything the service expects might go wrong."""

    code = "error"


class NotFound(CourierError):
    code = "not_found"

    def __init__(self, kind, identifier):
        super().__init__(f"{kind} {identifier} not found")
        self.kind = kind
        self.identifier = identifier


class ValidationFailed(CourierError):
    code = "invalid"

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class InvalidTransition(CourierError):
    code = "invalid_transition"

    def __init__(self, current, wanted):
        super().__init__(f"cannot move from {current} to {wanted}")
        self.current = current
        self.wanted = wanted


class InvoiceNotOpen(CourierError):
    code = "invoice_not_open"

    def __init__(self, invoice_id, status):
        super().__init__(f"invoice {invoice_id} is {status}")
        self.invoice_id = invoice_id
        self.status = status


class PaymentDeclined(CourierError):
    code = "payment_declined"

    def __init__(self, reason):
        super().__init__(f"payment declined: {reason}")
        self.reason = reason


class GatewayTimeout(CourierError):
    """The gateway did not answer in time."""

    code = "gateway_timeout"


class GatewayDeclined(CourierError):
    code = "gateway_declined"

    def __init__(self, reason):
        super().__init__(reason)
        self.reason = reason


class RefundTooLarge(CourierError):
    code = "refund_too_large"

    def __init__(self, requested, available):
        super().__init__(f"refund of {requested} is more than the {available} available")
        self.requested = requested
        self.available = available


class DeliveryFailed(CourierError):
    """A message could not be handed to a channel."""

    code = "delivery_failed"

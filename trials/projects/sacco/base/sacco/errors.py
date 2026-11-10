"""Errors raised across the service. The API layer turns these into responses."""


class SaccoError(Exception):
    """Base class for anything the service expects might go wrong."""

    code = "error"


class NotFound(SaccoError):
    code = "not_found"

    def __init__(self, kind, identifier):
        super().__init__(f"{kind} {identifier} not found")
        self.kind = kind
        self.identifier = identifier


class ValidationFailed(SaccoError):
    code = "invalid"

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class MemberInactive(SaccoError):
    code = "member_inactive"

    def __init__(self, member_id):
        super().__init__(f"member {member_id} is not active")
        self.member_id = member_id


class InsufficientSavings(SaccoError):
    code = "insufficient_savings"

    def __init__(self, requested, available):
        super().__init__(f"{requested} requested but only {available} is available")
        self.requested = requested
        self.available = available


class InvalidLoanState(SaccoError):
    code = "invalid_loan_state"

    def __init__(self, loan_id, status):
        super().__init__(f"loan {loan_id} is {status}")
        self.loan_id = loan_id
        self.status = status


class NotSecured(SaccoError):
    code = "not_secured"

    def __init__(self, loan_id, short_by):
        super().__init__(f"loan {loan_id} is short of security by {short_by}")
        self.loan_id = loan_id
        self.short_by = short_by


class AlreadyReversed(SaccoError):
    code = "already_reversed"

    def __init__(self, entry_id):
        super().__init__(f"entry {entry_id} has already been reversed")
        self.entry_id = entry_id


class TransferFailed(SaccoError):
    """The mobile money provider did not take the transfer."""

    code = "transfer_failed"


class DeliveryFailed(SaccoError):
    """A message could not be handed to a channel."""

    code = "delivery_failed"

"""Errors raised across the back office. The API layer turns these into responses."""


class MatatuError(Exception):
    """Base class for anything the back office expects might go wrong."""

    code = "error"


class NotFound(MatatuError):
    code = "not_found"

    def __init__(self, kind, identifier):
        super().__init__(f"{kind} {identifier} not found")
        self.kind = kind
        self.identifier = identifier


class ValidationFailed(MatatuError):
    code = "invalid"

    def __init__(self, problems):
        super().__init__("; ".join(problems))
        self.problems = list(problems)


class StageNotOnRoute(MatatuError):
    code = "stage_not_on_route"

    def __init__(self, stage_id, route_id):
        super().__init__(f"stage {stage_id} is not on route {route_id}")
        self.stage_id = stage_id
        self.route_id = route_id


class TripNotOpen(MatatuError):
    code = "trip_not_open"

    def __init__(self, trip_id, status):
        super().__init__(f"trip {trip_id} is {status}")
        self.trip_id = trip_id
        self.status = status


class NoSeatsLeft(MatatuError):
    code = "no_seats_left"

    def __init__(self, trip_id):
        super().__init__(f"trip {trip_id} is full")
        self.trip_id = trip_id


class TooManyTickets(MatatuError):
    code = "too_many_tickets"

    def __init__(self, phone, limit):
        super().__init__(f"{phone} already holds {limit} tickets on this trip")
        self.phone = phone
        self.limit = limit


class TicketNotValid(MatatuError):
    code = "ticket_not_valid"

    def __init__(self, ticket_id, reason):
        super().__init__(f"ticket {ticket_id}: {reason}")
        self.ticket_id = ticket_id
        self.reason = reason


class RefundRefused(MatatuError):
    code = "refund_refused"

    def __init__(self, ticket_id, reason):
        super().__init__(f"cannot refund {ticket_id}: {reason}")
        self.ticket_id = ticket_id
        self.reason = reason


class VehicleNotRoadworthy(MatatuError):
    code = "vehicle_not_roadworthy"

    def __init__(self, vehicle_id):
        super().__init__(f"vehicle {vehicle_id} is past its inspection")
        self.vehicle_id = vehicle_id


class BadStatement(MatatuError):
    code = "bad_statement"

    def __init__(self, line_number, problem):
        super().__init__(f"statement line {line_number}: {problem}")
        self.line_number = line_number
        self.problem = problem


class ProviderTimeout(MatatuError):
    """The mobile-money provider did not answer in time."""

    code = "provider_timeout"


class DeliveryFailed(MatatuError):
    """A message could not be handed to a channel."""

    code = "delivery_failed"

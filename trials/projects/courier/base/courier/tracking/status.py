"""Which delivery statuses can follow which."""

from typing import FrozenSet

from .. import models as m
from ..errors import InvalidTransition

ALLOWED = {
    m.STATUS_CREATED: frozenset({m.STATUS_COLLECTED, m.STATUS_CANCELLED}),
    m.STATUS_COLLECTED: frozenset({m.STATUS_IN_TRANSIT, m.STATUS_RETURNED}),
    m.STATUS_IN_TRANSIT: frozenset({m.STATUS_OUT_FOR_DELIVERY, m.STATUS_RETURNED}),
    m.STATUS_OUT_FOR_DELIVERY: frozenset({m.STATUS_DELIVERED, m.STATUS_FAILED}),
    m.STATUS_FAILED: frozenset({m.STATUS_OUT_FOR_DELIVERY, m.STATUS_RETURNED}),
    m.STATUS_DELIVERED: frozenset(),
    m.STATUS_RETURNED: frozenset(),
    m.STATUS_CANCELLED: frozenset(),
}

FINISHED = frozenset({m.STATUS_DELIVERED, m.STATUS_RETURNED, m.STATUS_CANCELLED})


def next_statuses(status: str) -> FrozenSet[str]:
    try:
        return ALLOWED[status]
    except KeyError:
        raise ValueError(f"unknown status: {status}") from None


def is_finished(status: str) -> bool:
    return status in FINISHED


def check_transition(current: str, wanted: str) -> None:
    if wanted not in next_statuses(current):
        raise InvalidTransition(current, wanted)

"""The words of each message."""

from typing import Dict

from .. import models as m

SUBJECTS: Dict[str, str] = {
    m.STATUS_COLLECTED: "We have your parcel",
    m.STATUS_OUT_FOR_DELIVERY: "Your parcel is on its way today",
    m.STATUS_DELIVERED: "Your parcel was delivered",
    m.STATUS_FAILED: "We could not deliver your parcel",
    m.STATUS_RETURNED: "Your parcel is being returned",
}

BODIES: Dict[str, str] = {
    m.STATUS_COLLECTED: "Hi {name}, we have collected parcel {parcel}.",
    m.STATUS_OUT_FOR_DELIVERY: "Hi {name}, parcel {parcel} is out for delivery today.",
    m.STATUS_DELIVERED: "Hi {name}, parcel {parcel} has been delivered.",
    m.STATUS_FAILED: "Hi {name}, we could not deliver parcel {parcel}. We will try again.",
    m.STATUS_RETURNED: "Hi {name}, parcel {parcel} is being returned to the sender.",
}


def has_template(status: str) -> bool:
    return status in BODIES


def render(status: str, name: str, parcel_id: str) -> Dict[str, str]:
    return {"subject": SUBJECTS[status], "body": BODIES[status].format(name=name, parcel=parcel_id)}

"""Signing up and changing customers."""

from ..errors import ValidationFailed
from ..models import Customer
from ..store.repositories import get_customer, invoices_of, save_customer


def normalise_phone(phone: str) -> str:
    """Numbers are kept in full international form, such as +254712345678."""
    digits = "".join(character for character in phone if character.isdigit())
    if len(digits) == 10 and digits.startswith("0"):
        digits = "254" + digits[1:]
    if len(digits) != 12 or not digits.startswith("254"):
        raise ValidationFailed([f"not a Kenyan phone number: {phone}"])
    return "+" + digits


def register_customer(store, name: str, phone: str, email: str, clock, payment_token: str = "") -> Customer:
    if not name.strip():
        raise ValidationFailed(["a customer needs a name"])
    customer = Customer(id=store.next_id("CUS"), name=name.strip(), phone=normalise_phone(phone), email=email.strip().lower(),
                        payment_token=payment_token, created_at=clock.now())
    return save_customer(store, customer)


def set_preferences(store, customer_id: str, wants_sms=None, wants_email=None) -> Customer:
    customer = get_customer(store, customer_id)
    if wants_sms is not None:
        customer.wants_sms = wants_sms
    if wants_email is not None:
        customer.wants_email = wants_email
    return save_customer(store, customer)


def close_account(store, customer_id: str) -> Customer:
    customer = get_customer(store, customer_id)
    unpaid = [i.id for i in invoices_of(store, customer_id) if i.status == "open"]
    if unpaid:
        raise ValidationFailed([f"invoice {i} is still open" for i in unpaid])
    customer.active = False
    customer.payment_token = ""
    return save_customer(store, customer)

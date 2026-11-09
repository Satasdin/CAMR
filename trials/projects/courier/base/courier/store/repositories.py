"""Small helpers for reading and writing records in a store."""

from typing import List

from ..errors import NotFound
from ..models import Customer, Invoice, Parcel, Refund


def save_customer(store, customer: Customer) -> Customer:
    store.customers[customer.id] = customer
    return customer


def get_customer(store, customer_id: str) -> Customer:
    try:
        return store.customers[customer_id]
    except KeyError:
        raise NotFound("customer", customer_id) from None


def save_parcel(store, parcel: Parcel) -> Parcel:
    store.parcels[parcel.id] = parcel
    return parcel


def get_parcel(store, parcel_id: str) -> Parcel:
    try:
        return store.parcels[parcel_id]
    except KeyError:
        raise NotFound("parcel", parcel_id) from None


def parcels_of(store, customer_id: str) -> List[Parcel]:
    return [p for p in store.parcels.values() if p.customer_id == customer_id]


def save_invoice(store, invoice: Invoice) -> Invoice:
    store.invoices[invoice.id] = invoice
    return invoice


def get_invoice(store, invoice_id: str) -> Invoice:
    try:
        return store.invoices[invoice_id]
    except KeyError:
        raise NotFound("invoice", invoice_id) from None


def invoices_of(store, customer_id: str) -> List[Invoice]:
    return [i for i in store.invoices.values() if i.customer_id == customer_id]


def save_refund(store, refund: Refund) -> Refund:
    store.refunds[refund.id] = refund
    return refund


def refunds_for(store, invoice_id: str) -> List[Refund]:
    return [r for r in store.refunds.values() if r.invoice_id == invoice_id]

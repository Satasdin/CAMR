"""Small helpers for reading and writing records in a store."""

from typing import List

from ..errors import NotFound
from ..models import Appointment, Claim, Doctor, Invoice, Patient, Payment, Prescription, TriageCase


def save_patient(store, patient: Patient) -> Patient:
    store.patients[patient.id] = patient
    return patient


def get_patient(store, patient_id: str) -> Patient:
    try:
        return store.patients[patient_id]
    except KeyError:
        raise NotFound("patient", patient_id) from None


def save_doctor(store, doctor: Doctor) -> Doctor:
    store.doctors[doctor.id] = doctor
    return doctor


def get_doctor(store, doctor_id: str) -> Doctor:
    try:
        return store.doctors[doctor_id]
    except KeyError:
        raise NotFound("doctor", doctor_id) from None


def save_appointment(store, appointment: Appointment) -> Appointment:
    store.appointments[appointment.id] = appointment
    return appointment


def get_appointment(store, appointment_id: str) -> Appointment:
    try:
        return store.appointments[appointment_id]
    except KeyError:
        raise NotFound("appointment", appointment_id) from None


def appointments_of_doctor(store, doctor_id: str) -> List[Appointment]:
    return [a for a in store.appointments.values() if a.doctor_id == doctor_id]


def appointments_of_patient(store, patient_id: str) -> List[Appointment]:
    return [a for a in store.appointments.values() if a.patient_id == patient_id]


def save_triage_case(store, case: TriageCase) -> TriageCase:
    store.triage_cases[case.id] = case
    return case


def get_triage_case(store, case_id: str) -> TriageCase:
    try:
        return store.triage_cases[case_id]
    except KeyError:
        raise NotFound("triage case", case_id) from None


def save_prescription(store, prescription: Prescription) -> Prescription:
    store.prescriptions[prescription.id] = prescription
    return prescription


def get_prescription(store, prescription_id: str) -> Prescription:
    try:
        return store.prescriptions[prescription_id]
    except KeyError:
        raise NotFound("prescription", prescription_id) from None


def prescriptions_of(store, patient_id: str) -> List[Prescription]:
    return [p for p in store.prescriptions.values() if p.patient_id == patient_id]


def save_invoice(store, invoice: Invoice) -> Invoice:
    store.invoices[invoice.id] = invoice
    return invoice


def get_invoice(store, invoice_id: str) -> Invoice:
    try:
        return store.invoices[invoice_id]
    except KeyError:
        raise NotFound("invoice", invoice_id) from None


def invoices_of(store, patient_id: str) -> List[Invoice]:
    return [i for i in store.invoices.values() if i.patient_id == patient_id]


def save_payment(store, payment: Payment) -> Payment:
    store.payments[payment.id] = payment
    return payment


def save_claim(store, claim: Claim) -> Claim:
    store.claims[claim.id] = claim
    return claim

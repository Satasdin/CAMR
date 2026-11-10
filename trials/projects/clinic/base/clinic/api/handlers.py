"""Handlers take a request dictionary and a context, and return a response dictionary."""

from dataclasses import dataclass
from functools import wraps

from ..billing.invoices import create_invoice, outstanding_cents, render_invoice
from ..billing.payments import record_payment
from ..clock import day_of, time_of
from ..errors import ClinicError
from ..patients.registry import register_patient
from ..prescriptions.prescribing import prescribe
from ..scheduling.appointments import book_appointment
from ..scheduling.cancellations import cancel_appointment
from ..scheduling.slots import open_slots
from ..triage.queue import admit
from .validators import check_booking, check_payment, require, vitals_from


@dataclass
class Context:
    store: object
    clock: object
    sender: object


def handled(function):
    """Turns expected errors into a response the web layer can send."""

    @wraps(function)
    def wrapper(request, context):
        try:
            return function(request, context)
        except ClinicError as problem:
            return {"error": problem.code, "message": str(problem)}

    return wrapper


@handled
def register(request, context):
    require(request, "name")
    patient = register_patient(context.store, request["name"], request.get("phone", ""), request.get("email", ""),
                               request.get("date_of_birth", ""), context.clock)
    return {"patient_id": patient.id}


@handled
def available_slots(request, context):
    require(request, "doctor_id", "day")
    slots = open_slots(context.store, request["doctor_id"], request["day"])
    return {"day": request["day"], "times": [time_of(slot) for slot in slots], "starts": slots}


@handled
def book(request, context):
    check_booking(request)
    appointment = book_appointment(context.store, request["patient_id"], request["doctor_id"], request["start_at"],
                                   request.get("reason", ""), context.clock)
    return {"appointment_id": appointment.id, "day": day_of(appointment.start_at), "time": time_of(appointment.start_at)}


@handled
def cancel(request, context):
    require(request, "appointment_id")
    appointment = cancel_appointment(context.store, request["appointment_id"], context.clock)
    return {"appointment_id": appointment.id, "status": appointment.status, "late": appointment.late_cancel}


@handled
def triage(request, context):
    require(request, "patient_id")
    case = admit(context.store, request["patient_id"], vitals_from(request), context.clock)
    return {"case_id": case.id, "score": case.score, "level": case.level}


@handled
def write_prescription(request, context):
    require(request, "patient_id", "doctor_id", "drug_code", "dose_mg", "days")
    prescription = prescribe(context.store, request["patient_id"], request["doctor_id"], request["drug_code"],
                             request["dose_mg"], request["days"], context.clock,
                             doses_per_day=int(request.get("doses_per_day", 1)), refills=int(request.get("refills", 0)))
    return {"prescription_id": prescription.id}


@handled
def invoice_visit(request, context):
    require(request, "appointment_id")
    invoice = create_invoice(context.store, request["appointment_id"], context.clock)
    return {"invoice_id": invoice.id, "total_cents": invoice.total_cents, "text": render_invoice(invoice)}


@handled
def pay(request, context):
    check_payment(request)
    invoice = record_payment(context.store, request["invoice_id"], request["amount_cents"], request["method"], context.clock)
    return {"invoice_id": invoice.id, "status": invoice.status, "outstanding_cents": outstanding_cents(invoice)}

"""Handlers take a request dictionary and a context, and return a response dictionary."""

from dataclasses import dataclass
from functools import wraps

from ..errors import SaccoError
from ..loans.applications import apply_for_loan, approve_loan
from ..loans.disbursement import disburse_loan
from ..members.registry import register_member
from ..notify.dispatch import notify_deposit, notify_loan_sent, notify_repayment
from ..repayments.payments import apply_repayment
from ..savings.deposits import deposit
from ..savings.withdrawals import withdraw
from ..statements.loan import loan_statement
from ..statements.member import member_statement
from ..store.repositories import get_loan
from .validators import require, require_amount


@dataclass
class Context:
    store: object
    gateway: object
    clock: object
    sender: object


def handled(function):
    """Turns expected errors into a response the web layer can send."""

    @wraps(function)
    def wrapper(request, context):
        try:
            return function(request, context)
        except SaccoError as problem:
            return {"error": problem.code, "message": str(problem)}

    return wrapper


@handled
def join(request, context):
    require(request, "name", "phone", "national_id")
    member = register_member(context.store, request["name"], request["phone"], request.get("email", ""), request["national_id"], context.clock)
    return {"member_id": member.id}


@handled
def deposit_cash(request, context):
    require(request, "member_id")
    amount = require_amount(request)
    entry = deposit(context.store, request["member_id"], amount, context.clock, reference=request.get("reference", ""))
    notify_deposit(context.store, request["member_id"], amount, entry.id, context.sender, context.clock)
    return {"entry_id": entry.id}


@handled
def withdraw_cash(request, context):
    require(request, "member_id")
    amount = require_amount(request)
    entry = withdraw(context.store, request["member_id"], amount, context.clock)
    return {"entry_id": entry.id}


@handled
def request_loan(request, context):
    require(request, "member_id", "product", "term_months")
    amount = require_amount(request)
    loan = apply_for_loan(context.store, request["member_id"], request["product"], amount, request["term_months"], context.clock)
    return {"loan_id": loan.id, "status": loan.status}


@handled
def approve(request, context):
    require(request, "loan_id")
    loan = approve_loan(context.store, request["loan_id"], context.clock)
    return {"loan_id": loan.id, "status": loan.status}


@handled
def send_out(request, context):
    require(request, "loan_id")
    done = disburse_loan(context.store, request["loan_id"], context.gateway, context.clock)
    loan = get_loan(context.store, request["loan_id"])
    notify_loan_sent(context.store, loan.member_id, done.sent_cents, done.receipt_id, context.sender, context.clock)
    return {"loan_id": done.loan_id, "sent_cents": done.sent_cents, "fee_cents": done.fee_cents, "receipt_id": done.receipt_id}


@handled
def repay(request, context):
    require(request, "loan_id")
    amount = require_amount(request)
    repayment = apply_repayment(context.store, request["loan_id"], amount, context.clock, reference=request.get("reference", ""))
    loan = get_loan(context.store, request["loan_id"])
    notify_repayment(context.store, loan.member_id, amount, repayment.id, context.sender, context.clock)
    return {"repayment_id": repayment.id, "loan_status": loan.status}


@handled
def savings_statement(request, context):
    require(request, "member_id", "start", "end")
    return member_statement(context.store, request["member_id"], request["start"], request["end"])


@handled
def loan_position(request, context):
    require(request, "loan_id")
    return loan_statement(context.store, request["loan_id"])

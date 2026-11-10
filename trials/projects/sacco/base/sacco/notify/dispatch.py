"""Deciding who gets told about something, and how."""

from typing import List

from ..clock import hour_of
from ..config import QUIET_HOURS_END, QUIET_HOURS_START, REMINDER_DAYS_BEFORE, SECONDS_PER_DAY
from ..loans.schedule import loan_schedule
from ..models import LOAN_ACTIVE, Member, Message
from ..money import format_cents
from ..store.repositories import get_member
from .templates import DEPOSIT_RECEIVED, INSTALMENT_DUE, LOAN_SENT, REPAYMENT_RECEIVED, render


def in_quiet_hours(moment: int) -> bool:
    hour = hour_of(moment)
    return hour >= QUIET_HOURS_START or hour < QUIET_HOURS_END


def messages_for(member: Member, template: str, amount_cents: int, reference: str, now: int) -> List[Message]:
    text = render(template, member.name, format_cents(amount_cents), reference)
    out = []
    if member.wants_email and member.email:
        out.append(Message(channel="email", to=member.email, subject=text["subject"], body=text["body"], sent_at=now))
    if member.wants_sms and member.phone and not in_quiet_hours(now):
        out.append(Message(channel="sms", to=member.phone, body=text["body"], sent_at=now))
    return out


def _notify(store, member_id: str, template: str, amount_cents: int, reference: str, sender, clock) -> int:
    member = get_member(store, member_id)
    return sum(1 for message in messages_for(member, template, amount_cents, reference, clock.now()) if sender.send(message))


def notify_deposit(store, member_id: str, amount_cents: int, reference: str, sender, clock) -> int:
    return _notify(store, member_id, DEPOSIT_RECEIVED, amount_cents, reference, sender, clock)


def notify_loan_sent(store, member_id: str, amount_cents: int, reference: str, sender, clock) -> int:
    return _notify(store, member_id, LOAN_SENT, amount_cents, reference, sender, clock)


def notify_repayment(store, member_id: str, amount_cents: int, reference: str, sender, clock) -> int:
    return _notify(store, member_id, REPAYMENT_RECEIVED, amount_cents, reference, sender, clock)


def send_reminders(store, sender, clock) -> int:
    """Reminds borrowers whose next instalment falls due soon and returns how many messages went out."""
    now = clock.now()
    sent = 0
    for loan in store.loans.values():
        if loan.status != LOAN_ACTIVE:
            continue
        for item in loan_schedule(loan):
            if now < item.due_at <= now + REMINDER_DAYS_BEFORE * SECONDS_PER_DAY:
                sent += _notify(store, loan.member_id, INSTALMENT_DUE, item.total_cents, loan.id, sender, clock)
    return sent

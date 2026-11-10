"""The member register."""

from ..config import DAYS_PER_MONTH, SECONDS_PER_DAY
from ..errors import ValidationFailed
from ..models import Member
from ..savings.accounts import open_account
from ..store.repositories import get_member, save_member
from .kyc import member_problems, normalise_phone


def register_member(store, name: str, phone: str, email: str, national_id: str, clock) -> Member:
    problems = member_problems(name, phone, national_id)
    if problems:
        raise ValidationFailed(problems)
    taken = [m for m in store.members.values() if m.national_id == national_id]
    if taken:
        raise ValidationFailed([f"national_id {national_id} is already registered"])
    member = Member(id=store.next_id("MBR"), name=name.strip(), phone=normalise_phone(phone), email=email,
                    national_id=national_id, joined_at=clock.now())
    save_member(store, member)
    open_account(store, member.id, clock)
    return member


def months_as_member(member: Member, now: int) -> int:
    return (now - member.joined_at) // (DAYS_PER_MONTH * SECONDS_PER_DAY)


def deactivate_member(store, member_id: str) -> Member:
    member = get_member(store, member_id)
    member.active = False
    return save_member(store, member)

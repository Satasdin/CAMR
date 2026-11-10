"""The drivers and conductors."""

from typing import List

from ..config import ROLE_CONDUCTOR, ROLE_DRIVER
from ..models import CrewMember
from ..store.repositories import save_crew_member


def add_crew_member(store, name: str, role: str, phone: str) -> CrewMember:
    if role not in (ROLE_DRIVER, ROLE_CONDUCTOR):
        raise ValueError(f"unknown role: {role}")
    return save_crew_member(store, CrewMember(id=store.next_id("CRW"), name=name, role=role, phone=phone))


def active_with_role(store, role: str) -> List[CrewMember]:
    return [member for member in store.crew.values() if member.active and member.role == role]

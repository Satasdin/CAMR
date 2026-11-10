"""Share capital each member holds."""

from ..config import MINIMUM_SHARES, SHARE_PRICE_CENTS
from ..errors import ValidationFailed
from ..models import Member
from ..store.repositories import get_member, save_member


def share_capital_cents(member: Member) -> int:
    return member.shares * SHARE_PRICE_CENTS


def has_minimum_shares(member: Member) -> bool:
    return member.shares >= MINIMUM_SHARES


def buy_shares(store, member_id: str, count: int, clock=None) -> Member:
    if count <= 0:
        raise ValidationFailed(["count must be positive"])
    member = get_member(store, member_id)
    member.shares += count
    return save_member(store, member)


def transfer_shares(store, seller_id: str, buyer_id: str, count: int) -> None:
    seller = get_member(store, seller_id)
    buyer = get_member(store, buyer_id)
    if count <= 0 or count > seller.shares:
        raise ValidationFailed(["seller does not hold that many shares"])
    seller.shares -= count
    buyer.shares += count
    save_member(store, seller)
    save_member(store, buyer)

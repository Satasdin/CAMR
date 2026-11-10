"""Passes that cover a passenger's rides for a day."""

from typing import List

from ..clock import day_of, operating_day
from ..config import DAY_PASS_PRICE_KES
from ..models import DayPass
from ..store.repositories import get_day_pass, save_day_pass


def sell_day_pass(store, phone: str, clock) -> DayPass:
    return save_day_pass(store, DayPass(id=store.next_id("PAS"), phone=phone, price_kes=DAY_PASS_PRICE_KES,
                                        bought_at=clock.now()))


def passes_sold_on(store, day: str) -> List[DayPass]:
    return [item for item in store.day_passes.values() if day_of(item.bought_at) == day]


def pass_is_valid(store, pass_id: str, at: int) -> bool:
    day_pass = get_day_pass(store, pass_id)
    return operating_day(day_pass.bought_at) == operating_day(at)

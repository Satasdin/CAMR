"""Pairs of ingredients that must not be taken together."""

from typing import FrozenSet, Iterable, List, Optional

BAD_PAIRS: List[FrozenSet[str]] = [
    frozenset(("merixin", "varenol")),
    frozenset(("bezorin", "coldaxine")),
]


def clash(first: str, second: str) -> bool:
    return frozenset((first.lower(), second.lower())) in BAD_PAIRS


def first_clash(ingredient: str, others: Iterable[str]) -> Optional[str]:
    for other in others:
        if clash(ingredient, other):
            return other
    return None

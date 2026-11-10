"""Urgency levels for walk-in patients."""

from typing import Dict

LEVEL_ROUTINE = "routine"
LEVEL_URGENT = "urgent"
LEVEL_IMMEDIATE = "immediate"

LEVEL_ORDER: Dict[str, int] = {LEVEL_IMMEDIATE: 0, LEVEL_URGENT: 1, LEVEL_ROUTINE: 2}
TARGET_WAIT_MINUTES: Dict[str, int] = {LEVEL_IMMEDIATE: 0, LEVEL_URGENT: 30, LEVEL_ROUTINE: 120}


def level_for(total: int) -> str:
    if total >= 6:
        return LEVEL_IMMEDIATE
    if total >= 3:
        return LEVEL_URGENT
    return LEVEL_ROUTINE


def target_minutes(level: str) -> int:
    return TARGET_WAIT_MINUTES[level]

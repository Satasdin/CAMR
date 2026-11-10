"""Turning vital signs into a triage score."""

from dataclasses import dataclass
from typing import List, Tuple

from ..models import Vitals


@dataclass
class TriageScore:
    lines: List[Tuple[str, int]]

    @property
    def total(self) -> int:
        return sum(points for _, points in self.lines)

    def points(self, name: str) -> int:
        return dict(self.lines).get(name, 0)


def temperature_points(temperature_c: float) -> int:
    if temperature_c >= 39.5 or temperature_c < 35.0:
        return 2
    if temperature_c >= 38.0:
        return 1
    return 0


def heart_rate_points(heart_rate: int) -> int:
    if heart_rate >= 130 or heart_rate < 40:
        return 3
    if heart_rate >= 110:
        return 2
    if heart_rate >= 100 or heart_rate < 50:
        return 1
    return 0


def breathing_points(breaths_per_minute: int) -> int:
    if breaths_per_minute >= 30 or breaths_per_minute < 8:
        return 3
    if breaths_per_minute >= 24:
        return 2
    return 0


def pressure_points(systolic: int) -> int:
    if systolic < 90:
        return 3
    if systolic < 100 or systolic >= 200:
        return 2
    return 0


def oxygen_points(spo2: int) -> int:
    if spo2 < 90:
        return 3
    if spo2 <= 93:
        return 2
    return 0


def score_vitals(vitals: Vitals) -> TriageScore:
    """Every vital sign that scores, as (name, points) pairs."""
    candidates = [
        ("temperature", temperature_points(vitals.temperature_c)),
        ("heart_rate", heart_rate_points(vitals.heart_rate)),
        ("breathing", breathing_points(vitals.breaths_per_minute)),
        ("pressure", pressure_points(vitals.systolic)),
        ("oxygen", oxygen_points(vitals.spo2)),
    ]
    return TriageScore([(name, points) for name, points in candidates if points])

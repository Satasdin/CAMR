"""Readable identifiers for records."""

from typing import Dict


class IdGenerator:
    """Hands out identifiers such as PAT-00001, one sequence per prefix."""

    def __init__(self):
        self.counters: Dict[str, int] = {}

    def next(self, prefix: str) -> str:
        self.counters[prefix] = self.counters.get(prefix, 0) + 1
        return f"{prefix}-{self.counters[prefix]:05d}"

    def issued(self, prefix: str) -> int:
        return self.counters.get(prefix, 0)

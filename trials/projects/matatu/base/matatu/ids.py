"""Identifiers people can read out over the phone."""

ALPHABET = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"


def encode(number: int, width: int = 6) -> str:
    if number < 0:
        raise ValueError("number must not be negative")
    digits = []
    while number:
        number, remainder = divmod(number, len(ALPHABET))
        digits.append(ALPHABET[remainder])
    text = "".join(reversed(digits)) or ALPHABET[0]
    return text.rjust(width, ALPHABET[0])


class IdGenerator:
    """Hands out identifiers in order, with a prefix per record type."""

    def __init__(self):
        self.counters = {}

    def next(self, prefix: str) -> str:
        value = self.counters.get(prefix, 0) + 1
        self.counters[prefix] = value
        return f"{prefix}-{encode(value)}"

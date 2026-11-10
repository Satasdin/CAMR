"""Reading the statement file the provider sends each day."""

from typing import List

from ..errors import BadStatement
from ..models import StatementLine
from ..money import parse_amount


def parse_statement(text: str) -> List[StatementLine]:
    """Each line is: code, phone, amount, account reference, seconds since the epoch."""
    lines = []
    for number, raw in enumerate(text.splitlines(), start=1):
        if not raw.strip() or raw.lstrip().startswith("#"):
            continue
        parts = [part.strip() for part in raw.split(",")]
        if len(parts) != 5:
            raise BadStatement(number, "expected five fields")
        code, phone, amount, reference, at = parts
        try:
            lines.append(StatementLine(code=code, phone=phone, amount_kes=parse_amount(amount), account_ref=reference,
                                       at=int(at)))
        except ValueError as problem:
            raise BadStatement(number, str(problem)) from None
    return lines

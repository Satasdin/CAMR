"""The drugs the clinic can prescribe."""

from dataclasses import dataclass
from typing import Dict, List

from ..errors import NotFound


@dataclass(frozen=True)
class Drug:
    code: str
    name: str
    ingredient: str
    form: str
    strength_mg: int
    mg_per_ml: float = 0.0
    mg_per_kg: int = 0
    max_single_mg: int = 0
    step_mg: int = 1


FORMULARY: Dict[str, Drug] = {
    "ZLV-SUS": Drug("ZLV-SUS", "Zolvicin suspension", "zolvicin", "syrup", 250, 50.0, 15, 500, 25),
    "PRN-SYR": Drug("PRN-SYR", "Pirenol syrup", "pirenol", "syrup", 120, 24.0, 15, 1000, 10),
    "TAV-SYR": Drug("TAV-SYR", "Tavoprofen syrup", "tavoprofen", "syrup", 100, 20.0, 10, 400, 20),
    "MRX-TAB": Drug("MRX-TAB", "Merixin tablets", "merixin", "tablet", 500, max_single_mg=1000, step_mg=250),
    "VRN-TAB": Drug("VRN-TAB", "Varenol tablets", "varenol", "tablet", 5, max_single_mg=10, step_mg=5),
    "BZR-TAB": Drug("BZR-TAB", "Bezorin tablets", "bezorin", "tablet", 20, max_single_mg=40, step_mg=20),
    "CLD-TAB": Drug("CLD-TAB", "Coldaxine tablets", "coldaxine", "tablet", 10, max_single_mg=20, step_mg=10),
}


def get_drug(code: str) -> Drug:
    try:
        return FORMULARY[code]
    except KeyError:
        raise NotFound("drug", code) from None


def drugs_in_form(form: str) -> List[Drug]:
    return sorted((d for d in FORMULARY.values() if d.form == form), key=lambda d: d.code)

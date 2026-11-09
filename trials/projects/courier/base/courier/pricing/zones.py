"""Delivery zones and the bands between them."""

from typing import Dict, Tuple

ZONE_NAMES: Dict[str, str] = {
    "NBO": "Nairobi",
    "MBA": "Mombasa",
    "KSM": "Kisumu",
    "NKR": "Nakuru",
    "ELD": "Eldoret",
    "NYR": "Nyeri",
    "LAM": "Lamu",
    "GAR": "Garissa",
    "LOD": "Lodwar",
}

REMOTE_ZONES = frozenset({"LAM", "GAR", "LOD"})

BAND_PRICES_CENTS: Dict[str, int] = {"local": 25_000, "near": 42_000, "far": 68_000, "remote": 110_000}

_NEAR: Tuple[frozenset, ...] = (
    frozenset({"NBO", "NKR"}),
    frozenset({"NBO", "NYR"}),
    frozenset({"NKR", "ELD"}),
    frozenset({"NKR", "KSM"}),
    frozenset({"ELD", "KSM"}),
)


def is_known(zone: str) -> bool:
    return zone in ZONE_NAMES


def is_remote(zone: str) -> bool:
    return zone in REMOTE_ZONES


def band(origin: str, destination: str) -> str:
    """The price band for a journey. The order of the two zones does not matter."""
    for zone in (origin, destination):
        if not is_known(zone):
            raise ValueError(f"unknown zone: {zone}")
    if origin == destination:
        return "local"
    if is_remote(origin) or is_remote(destination):
        return "remote"
    if frozenset({origin, destination}) in _NEAR:
        return "near"
    return "far"


def band_price(origin: str, destination: str) -> int:
    return BAND_PRICES_CENTS[band(origin, destination)]

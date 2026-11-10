"""Fares by how far the passenger travels."""

from ..config import FARE_BANDS, FareBand


def band_for(stages: int) -> FareBand:
    if stages <= 0:
        raise ValueError("a journey covers at least one stage")
    for band in FARE_BANDS:
        if stages <= band.max_stages:
            return band
    return FARE_BANDS[-1]

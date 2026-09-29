"""Retrieval policies (FR-06, FR-07): re-rank the k nearest candidates.

Equation 4.1:  score = w_s * sim + w_r * rec + w_i * imp

Two refinements over the proposal, both recorded in docs/DESIGN_NOTES.md:

* Scale alignment.  rec and imp live in [0, 1] but raw cosine for BGE
  embeddings clusters in a narrow band (roughly 0.3-0.9), so a raw weighted sum
  lets a small importance difference swamp a large relevance difference.  Park et
  al. (2023) min-max normalise *all three* terms over the candidate set; with
  ``normalise_similarity`` on (the default) CAMR does the same.  Min-max is
  monotone, so the similarity-only control ordering is unchanged, and the raw
  cosine is still what is logged as ``similarity``.
* Determinism.  Ties are broken by note_id so equal scores can never reorder
  between runs (NFR-05).

Setting w_s = 1 recovers the control exactly: control and treatment share one
code path and differ in configuration only.
"""

from __future__ import annotations

import datetime as dt
from abc import ABC, abstractmethod
from typing import Callable

from camr.config import MemoryConfig
from camr.memory.note import ScoredNote, from_iso


def minmax(values: list[float]) -> list[float]:
    """Equation 4.4 applied over the candidate set.  A constant set maps to 0."""
    if not values:
        return []
    lo, hi = min(values), max(values)
    if hi - lo < 1e-12:
        return [0.0 for _ in values]
    return [(v - lo) / (hi - lo) for v in values]


def recency(last_accessed: str, now: dt.datetime, decay: float) -> float:
    """Equation 4.3: decay ** hours since last access."""
    hours = max(0.0, (now - from_iso(last_accessed)).total_seconds() / 3600.0)
    return float(decay**hours)


class RetrievalPolicy(ABC):
    name: str

    @abstractmethod
    def rank(self, candidates: list[ScoredNote], now: dt.datetime) -> list[ScoredNote]: ...

    @staticmethod
    def _finalise(cands: list[ScoredNote]) -> list[ScoredNote]:
        cands.sort(key=lambda c: (-round(c.composite, 9), c.note.note_id))
        for i, c in enumerate(cands, start=1):
            c.rank = i
        return cands


class CompositeScorePolicy(RetrievalPolicy):
    name = "composite"

    def __init__(self, w_s: float, w_r: float, w_i: float, decay: float, normalise_similarity: bool = True):
        self.w_s, self.w_r, self.w_i = w_s, w_r, w_i
        self.decay = decay
        self.normalise_similarity = normalise_similarity

    def rank(self, candidates: list[ScoredNote], now: dt.datetime) -> list[ScoredNote]:
        if not candidates:
            return []
        sims = [c.similarity for c in candidates]
        sim_terms = minmax(sims) if self.normalise_similarity else sims
        imps = minmax([c.note.importance for c in candidates])
        for c, s, i in zip(candidates, sim_terms, imps):
            c.similarity_norm = s
            c.recency = recency(c.note.last_accessed_at, now, self.decay)
            c.importance = i
            c.composite = self.w_s * s + self.w_r * c.recency + self.w_i * i
        return self._finalise(candidates)


class SimilarityOnlyPolicy(CompositeScorePolicy):
    """The control condition: Equation 4.1 with w_s = 1, w_r = w_i = 0."""

    name = "similarity_only"

    def __init__(self, decay: float = 0.99, normalise_similarity: bool = True):
        super().__init__(1.0, 0.0, 0.0, decay, normalise_similarity)


# Extension point for FR-18 (e.g. a GraphAssociativePolicy): register a factory
# under a new name and select it with memory.retrieval_policy.  Nothing in the
# write path, store schema or harness needs to change.
_REGISTRY: dict[str, Callable[[MemoryConfig], RetrievalPolicy]] = {
    "composite": lambda m: CompositeScorePolicy(
        m.weights.similarity, m.weights.recency, m.weights.importance, m.recency_decay, m.normalise_similarity
    ),
    "similarity_only": lambda m: SimilarityOnlyPolicy(m.recency_decay, m.normalise_similarity),
}


def register_policy(name: str, factory: Callable[[MemoryConfig], RetrievalPolicy]) -> None:
    _REGISTRY[name] = factory


def build_policy(cfg: MemoryConfig) -> RetrievalPolicy:
    try:
        return _REGISTRY[cfg.retrieval_policy](cfg)
    except KeyError:
        raise ValueError(f"unknown retrieval policy {cfg.retrieval_policy!r}") from None

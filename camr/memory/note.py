"""Memory entities (Figure 4.8): Source (provenance), Note, and the transient
objects that flow through the write and read paths.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field

import numpy as np


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc)


def to_iso(t: dt.datetime) -> str:
    return t.astimezone(dt.timezone.utc).isoformat(timespec="microseconds")


def from_iso(s: str) -> dt.datetime:
    return dt.datetime.fromisoformat(s)


_WS = re.compile(r"\s+")


def normalise_text(text: str) -> str:
    """Normalisation used for duplicate detection (DR-06): NFKC, casefold, collapse whitespace."""
    return _WS.sub(" ", unicodedata.normalize("NFKC", text).casefold()).strip()


def checksum(text: str, note_type: str) -> str:
    """Checksum over normalised text, namespaced by note population.

    Namespacing lets verbatim and structured populations coexist in one store
    file for the write-policy ablation while the UNIQUE constraint still rejects
    duplicates *within* a population, whatever write path produced them.
    """
    return hashlib.sha256(f"{note_type}\x00{normalise_text(text)}".encode()).hexdigest()


@dataclass
class Document:
    """A unit of source material handed to the write path."""

    dataset: str
    doc_id: str
    text: str
    title: str = ""


@dataclass
class Source:
    source_id: int
    dataset: str
    doc_id: str
    ingested_at: str
    screener_verdict: str


@dataclass
class CandidateNote:
    text: str
    note_type: str
    error: str | None = None  # set when the write policy itself failed


@dataclass
class Note:
    note_id: int
    source_id: int
    note_type: str
    text: str
    token_count: int
    importance: float
    checksum: str
    created_at: str
    last_accessed_at: str
    access_count: int = 0


@dataclass
class ScoredNote:
    """One candidate on the read path, with every component score (RetrievedNote)."""

    note: Note
    similarity: float  # raw cosine, Equation 4.2
    recency: float = 0.0  # Equation 4.3
    importance: float = 0.0  # normalised, Equation 4.4
    similarity_norm: float = 0.0
    composite: float = 0.0  # Equation 4.1
    rank: int = 0
    admitted: bool = False
    tokens: int = 0
    eligible: bool = True  # False when the relevance margin excludes it
    via: int | None = None  # seed note id when added by entity-bridge expansion


@dataclass
class RecallResult:
    context: str
    candidates: list[ScoredNote]
    context_tokens: int
    budget: int
    retrieval_ms: float
    timings: dict[str, float] = field(default_factory=dict)
    abstained: bool = False  # gating decided memory would not help
    top_similarity: float | None = None

    @property
    def admitted(self) -> list[ScoredNote]:
        return [c for c in self.candidates if c.admitted]


def as_float32(vec: np.ndarray | list[float]) -> np.ndarray:
    return np.asarray(vec, dtype=np.float32)

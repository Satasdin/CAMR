"""The memory engine proper (package camr.memory): entities, policies, screener,
embedder, store and budgeter.  Usable as a library without the harness."""

from camr.memory.budgeter import TokenBudgeter
from camr.memory.clock import Clock, LogicalClock, WallClock
from camr.memory.embedder import BGEEmbedder, Embedder, HashingEmbedder, build_embedder
from camr.memory.engine import IngestSummary, MemoryEngine
from camr.memory.note import Document, Note, RecallResult, ScoredNote
from camr.memory.retrieval import (
    CompositeScorePolicy,
    RetrievalPolicy,
    SimilarityOnlyPolicy,
    build_policy,
    register_policy,
)
from camr.memory.screener import NoteScreener, Verdict
from camr.memory.store import MemoryStore, SQLiteVectorStore
from camr.memory.write_policy import StructuredNoteWritePolicy, VerbatimWritePolicy, WritePolicy

__all__ = [
    "BGEEmbedder",
    "Clock",
    "CompositeScorePolicy",
    "Document",
    "Embedder",
    "HashingEmbedder",
    "IngestSummary",
    "LogicalClock",
    "MemoryEngine",
    "MemoryStore",
    "Note",
    "NoteScreener",
    "RecallResult",
    "RetrievalPolicy",
    "SQLiteVectorStore",
    "ScoredNote",
    "SimilarityOnlyPolicy",
    "StructuredNoteWritePolicy",
    "TokenBudgeter",
    "Verdict",
    "VerbatimWritePolicy",
    "WallClock",
    "WritePolicy",
    "build_embedder",
    "build_policy",
    "register_policy",
]

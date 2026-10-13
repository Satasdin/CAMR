"""Eager recall: when memory has nothing, learn first, then answer.

The capability-adaptive gate decides that memory has nothing worth reading (it
abstains). In the first study the model then answered alone, which for a small model
usually means a guess or "I don't know". The eager read path treats an abstention as
a gap in memory instead: it looks the subject up (``camr.memory.fetch``), writes what
it read through the ordinary write path (screened, deduplicated, with the page as its
source), and recalls again. What was learned stays: the next question that needs it
is answered from memory, offline, in milliseconds.

A question about the user's own life is never looked up (``fetch.is_personal``); the
assistant asks to be taught instead.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from camr.memory.engine import MemoryEngine
from camr.memory.fetch import WebLookup, WebPage, is_personal
from camr.memory.note import Document, RecallResult

WEB_DATASET = "web"


@dataclass
class Learned:
    """What one lookup added to memory."""

    looked_up: bool = False
    reason: str = ""  # why there was no lookup: "memory had it", "personal", "web off"
    queries: list[str] = field(default_factory=list)
    pages: list[dict] = field(default_factory=list)  # title, url, source
    notes_added: int = 0
    errors: list[str] = field(default_factory=list)
    lookup_ms: float = 0.0
    ingest_ms: float = 0.0


def learn_pages(engine: MemoryEngine, pages: list[WebPage], dataset: str = WEB_DATASET) -> int:
    """Store web pages as notes (the page URL is the source id, so a page is only ever stored once)."""
    docs = [Document(dataset=dataset, doc_id=p.url, text=p.text, title=p.title) for p in pages if p.text]
    return engine.ingest(docs).accepted if docs else 0


def eager_recall(engine: MemoryEngine, lookup: WebLookup | None, question: str, *, allow_web: bool = True,
                 touch: bool = True, max_pages: int = 3) -> tuple[RecallResult, Learned]:
    """Recall; on abstention look the question's subject up, learn it, and recall again."""
    recall = engine.recall(question, touch=touch)
    learned = Learned()
    if not recall.abstained:
        learned.reason = "memory had it"
        return recall, learned
    if lookup is None or not allow_web:
        learned.reason = "web off"
        return recall, learned
    if is_personal(question):
        learned.reason = "personal"
        return recall, learned
    learned.looked_up = True
    found = lookup.lookup(question, max_pages=max_pages)
    learned.queries, learned.errors, learned.lookup_ms = found.queries, found.errors, found.ms
    learned.pages = [{"title": p.title, "url": p.url, "source": p.source} for p in found.pages]
    if found.pages:
        t0 = time.perf_counter()
        learned.notes_added = learn_pages(engine, found.pages)
        learned.ingest_ms = (time.perf_counter() - t0) * 1000
        recall = engine.recall(question, touch=touch)
    return recall, learned

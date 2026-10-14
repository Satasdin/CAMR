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
from camr.memory.entities import norm
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


def fact_lines(facts: str) -> list[tuple[str, str]]:
    """'Directed by: Ravi Chopra; Music by: R. D. Burman' -> [('Directed by', 'Ravi Chopra'), ...]."""
    out = []
    for part in facts.split("; "):
        label, sep, value = part.partition(": ")
        if sep and label.strip() and value.strip():
            out.append((label.strip(), value.strip()))
    return out


def page_documents(page: WebPage, dataset: str = WEB_DATASET) -> list[Document]:
    """A page as documents: its lead (chunked by the write path) and one short note per infobox fact.

    An atomic fact note ("The Burning Train: Directed by: Ravi Chopra") is what a question about that fact is
    closest to, and all a small reader needs to answer it: one line, no distracting paragraphs."""
    docs = [Document(dataset=dataset, doc_id=page.url, text=page.text, title=page.title)] if page.text else []
    for label, value in fact_lines(page.facts):
        docs.append(Document(dataset=dataset, doc_id=f"{page.url}#fact:{label}", text=f"{label}: {value}",
                             title=page.title))
    return docs


def learn_meanings(engine: MemoryEngine, meanings: dict[str, list[str]]) -> None:
    """Remember what a shared name may refer to ('Damage': 'Damage (1992 film)', 'Damage (2009 film)', ...), so an
    answer about one meaning is never taken for the only one (camr.memory.verify.same_name_titles)."""
    for name, titles in meanings.items():
        if titles:
            engine.store.set_meanings(norm(name), titles)


def learn_pages(engine: MemoryEngine, pages: list[WebPage], dataset: str = WEB_DATASET) -> int:
    """Store web pages as notes (the page URL is the source id, so a page is only ever stored once)."""
    docs = [d for p in pages for d in page_documents(p, dataset)]
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
        learn_meanings(engine, found.meanings)
        learned.ingest_ms = (time.perf_counter() - t0) * 1000
        recall = engine.recall(question, touch=touch)
    return recall, learned

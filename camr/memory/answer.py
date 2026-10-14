"""Verified answering: recall (learning on a miss), read, check, escalate, and never state what is not supported.

    question -> recall (eager: look up and learn on a miss)
             -> fact reader: a fact line that answers it outright (no model)
             -> compress: the few sentences and fact lines worth reading
             -> reader 1 (the small model) -> check against the evidence
             -> reader 2, 3 ... (a larger local model, a cloud model), each checked the same way
             -> verified answer, or an honest "unverified" with the best lead and its source

A claim the evidence does not support is never stated as fact. The answer then says
what was found and that it could not be confirmed (``status = "unverified"``), so the
assistant stays useful (it still offers its best lead) without presenting a guess as
knowledge.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from camr.memory.eager import Learned, eager_recall
from camr.memory.engine import MemoryEngine
from camr.memory.fetch import WebLookup
from camr.memory.eager import learn_pages
from camr.memory.fetch import Lookup, WebPage
from camr.memory.verify import (CROSS, Unit, Verdict, check, claim, compress, cross_check, fact_answer, relation_of,
                                sentences, units_from_notes)
from camr.models.prompt import PromptTemplate
from camr.models.runner import GenerationError, ModelRunner

READ = PromptTemplate(
    "read",
    "Use the notes below to answer. Answer the question with a short phrase copied from the notes. "
    "Do not explain.\n\nNotes:\n{context}\n\nQuestion: {question}\nAnswer:",
)
BARE = PromptTemplate(
    "bare",
    "Answer the question with a short phrase only. Do not explain.\n\nQuestion: {question}\nAnswer:",
)


@dataclass
class Attempt:
    by: str
    answer: str
    verdict: dict
    ms: float
    error: str | None = None


@dataclass
class Answer:
    question: str
    text: str             # what the assistant says
    claim: str            # the bare answer ("Ravi Chopra")
    status: str           # "verified" (supported by memory), "unverified" (best lead, not confirmed), "none"
    by: str               # "memory" (fact reader) or the model that gave the verified answer
    evidence: str | None  # the sentence or fact line that supports it
    source: str | None    # its title
    attempts: list[Attempt] = field(default_factory=list)
    learned: Learned | None = None
    context: str = ""
    ms: dict = field(default_factory=dict)
    ambiguous: list[str] = field(default_factory=list)  # other things in memory with the same name

    def as_dict(self) -> dict:
        return {"question": self.question, "text": self.text, "claim": self.claim, "status": self.status,
                "by": self.by, "evidence": self.evidence, "source": self.source, "context": self.context,
                "attempts": [a.__dict__ for a in self.attempts], "ms": {k: round(v, 1) for k, v in self.ms.items()},
                "ambiguous": self.ambiguous,
                "looked_up": bool(self.learned and self.learned.looked_up)}


class VerifiedAnswerer:
    def __init__(self, engine: MemoryEngine, readers: list[ModelRunner], *, lookup: WebLookup | None = None,
                 budget: int = 128, fact_reader: bool = True, compressed: bool = True, max_pages: int = 3,
                 min_coverage: float = 1.0, closed_book: bool = False, template: PromptTemplate = READ,
                 cross_check: bool = False):
        self.engine = engine
        self.readers = readers
        self.lookup = lookup
        self.budget = budget
        self.fact_reader = fact_reader
        self.compressed = compressed
        self.max_pages = max_pages
        self.min_coverage = min_coverage
        self.closed_book = closed_book  # with no evidence, let readers answer anyway (always "unverified")
        self.template = template
        # when memory cannot confirm a claim, look the claimed answer up and check it from its own side
        self.cross = cross_check

    def _cross(self, question: str, answer: str, c: str) -> tuple[Verdict, WebPage | None]:
        return cross_verify(self.engine, self.lookup, question, answer)

    def evidence(self, question: str, *, allow_web: bool = True, touch: bool = False):
        recall, learned = eager_recall(self.engine, self.lookup, question, allow_web=allow_web, touch=touch,
                                       max_pages=self.max_pages)
        notes = [] if recall.abstained else [c.note for c in recall.candidates if c.eligible]
        return recall, learned, units_from_notes(self.engine.store, notes)

    def answer(self, question: str, *, allow_web: bool = True, touch: bool = False) -> Answer:
        t0 = time.perf_counter()
        recall, learned, units = self.evidence(question, allow_web=allow_web, touch=touch)
        ms = {"recall": (time.perf_counter() - t0) * 1000}
        if self.fact_reader:
            fa = fact_answer(question, units)
            if fa is not None:
                ms["total"] = (time.perf_counter() - t0) * 1000
                return Answer(question, fa.text, fa.claim, "verified", "memory", fa.evidence, fa.source,
                              learned=learned, context=fa.evidence, ms=ms, ambiguous=fa.ambiguous)
        t1 = time.perf_counter()
        if units and self.compressed:
            shown = compress(question, units, self.engine.embedder, self.engine.budgeter.tokenizer, self.budget)
        else:
            shown = units
        context = "\n".join(u.render() for u in shown) if self.compressed else recall.context
        ms["compress"] = (time.perf_counter() - t1) * 1000
        attempts: list[Attempt] = []
        if not units and not self.closed_book:
            ms["total"] = (time.perf_counter() - t0) * 1000
            return Answer(question, "", "", "none", "", None, None, attempts, learned, "", ms)
        prompt = self.template.render(question, context) if units else BARE.render(question)
        best: tuple[Verdict, str, str] | None = None
        for reader in self.readers:
            t2 = time.perf_counter()
            try:
                g = reader.generate(prompt)
            except GenerationError as exc:
                attempts.append(Attempt(reader.model_name, "", {}, (time.perf_counter() - t2) * 1000, str(exc)))
                continue
            v = check(question, g.text, units, min_coverage=self.min_coverage, logprobs=g.meta.get("logprobs"))
            attempts.append(Attempt(reader.model_name, g.text.strip()[:300], v.as_dict(),
                                    (time.perf_counter() - t2) * 1000))
            if v.supported:
                ms["total"] = (time.perf_counter() - t0) * 1000
                c = claim(g.text)
                text = f"{c} ({v.evidence.title})" if v.others else c  # say which one, when the name is shared
                return Answer(question, text, c, "verified", reader.model_name, v.evidence.render(),
                              v.evidence.title, attempts, learned, context, ms, ambiguous=v.others)
            if best is None and v.reason not in ("declined",):
                best = (v, claim(g.text), reader.model_name)
        rel = relation_of(question)
        if self.cross and self.lookup is not None and allow_web and rel and rel[0] in CROSS:
            t3 = time.perf_counter()
            tried: set[str] = set()
            for att in attempts:
                c = claim(att.answer)
                if not c or c.lower() in tried or att.verdict.get("reason") in ("declined", "supported"):
                    continue
                tried.add(c.lower())
                v, page = self._cross(question, att.answer, c)
                if v.supported:
                    ms["cross"] = (time.perf_counter() - t3) * 1000
                    ms["total"] = (time.perf_counter() - t0) * 1000
                    attempts.append(Attempt(f"{att.by} + cross-check", att.answer, v.as_dict(), ms["cross"]))
                    return Answer(question, c, c, "verified", f"{att.by} + cross-check", v.evidence.render(),
                                  v.evidence.title, attempts, learned, context, ms)
            ms["cross"] = (time.perf_counter() - t3) * 1000
        ms["total"] = (time.perf_counter() - t0) * 1000
        if best is None:
            return Answer(question, "", "", "none", "", None, None, attempts, learned, context, ms)
        v, c, by = best
        return Answer(question, c, c, "unverified", by, None, None, attempts, learned, context, ms)


def cross_verify(engine: MemoryEngine, lookup: WebLookup, question: str, answer: str) -> tuple[Verdict, WebPage | None]:
    """Look the claimed answer up (a public name, never anything personal) and check it from its own side; a page
    that confirms it is learned."""
    c = claim(answer)
    if not c:
        return Verdict(False, "no claim"), None
    res = Lookup(question=c)
    page, options = lookup.article(c, res)
    pages = [page] if page else []
    if not pages and options:  # an ambiguous name: the meanings closest to the question
        if lookup.rank is not None:
            scores = lookup.rank(question, [f"{t}. {d}" for t, d in options])
            options = [o for _, o in sorted(zip(scores, options), key=lambda x: -x[0])]
        for title, _ in options[:2]:
            p = lookup.article(title, res)[0]
            if p:
                pages.append(p)
    for p in pages:
        v = cross_check(question, answer, page_units(p))
        if v.supported:
            learn_pages(engine, [p])  # what confirmed it is worth remembering
            return v, p
    return Verdict(False, "not confirmed from the answer's side"), None


def page_units(page: WebPage) -> list[Unit]:
    from camr.memory.eager import fact_lines

    return [Unit(page.title, x) for x in sentences(page.text)] + [Unit(page.title, f"{label}: {value}", label)
                                                                    for label, value in fact_lines(page.facts)]



def unverified_text(a: Answer, sources: list[Unit] | None = None) -> str:
    """How the assistant words an answer it could not confirm."""
    if a.status != "unverified":
        return a.text
    return f"I couldn't confirm this from what I've read. My best lead is: {a.claim} (unverified)."

"""MemoryEngine: facade over the write path, the store and the read path.

It holds configured policy objects and implements no policy itself, so one code
path serves both control and treatment (Figure 4.3).
"""

from __future__ import annotations

import logging
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from typing import Iterable

from camr.config import Config
from camr.memory.budgeter import TokenBudgeter
from camr.memory.clock import Clock, WallClock
from camr.memory.embedder import Embedder
from camr.memory.importance import HeuristicImportance, ImportanceScorer, ModelImportance
from camr.memory.note import Document, RecallResult, ScoredNote, to_iso
from camr.memory.retrieval import RetrievalPolicy, build_policy
from camr.memory.screener import NoteScreener
from camr.memory.store import SQLiteVectorStore
from camr.memory.write_policy import StructuredNoteWritePolicy, VerbatimWritePolicy, WritePolicy
from camr.models.runner import ModelRunner
from camr.models.tokenizer import Tokenizer

log = logging.getLogger(__name__)


@dataclass
class IngestSummary:
    note_type: str
    documents: int = 0
    skipped_existing: int = 0
    accepted: int = 0
    rejected: Counter = field(default_factory=Counter)
    distil_ms: float = 0.0
    embed_ms: float = 0.0
    elapsed_s: float = 0.0

    @property
    def ingestion_yield(self) -> float | None:
        total = self.accepted + sum(self.rejected.values())
        return self.accepted / total if total else None

    def as_dict(self) -> dict:
        return {
            "note_type": self.note_type,
            "documents": self.documents,
            "skipped_existing": self.skipped_existing,
            "accepted": self.accepted,
            "rejected": dict(self.rejected),
            "ingestion_yield": self.ingestion_yield,
            "distil_ms": round(self.distil_ms, 1),
            "embed_ms": round(self.embed_ms, 1),
            "elapsed_s": round(self.elapsed_s, 2),
        }


class MemoryEngine:
    def __init__(
        self,
        *,
        store: SQLiteVectorStore,
        embedder: Embedder,
        write_policy: WritePolicy,
        screener: NoteScreener,
        importance: ImportanceScorer,
        retrieval_policy: RetrievalPolicy,
        budgeter: TokenBudgeter,
        clock: Clock | None = None,
        k: int = 20,
        batch_size: int = 32,
        min_similarity: float = 0.0,
        similarity_margin: float | None = None,
        expansion: str = "none",
        expansion_seeds: int = 3,
        expansion_per_seed: int = 2,
    ):
        self.store = store
        self.embedder = embedder
        self.write_policy = write_policy
        self.screener = screener
        self.importance = importance
        self.retrieval_policy = retrieval_policy
        self.budgeter = budgeter
        self.clock = clock or WallClock()
        self.k = k
        self.batch_size = batch_size
        self.min_similarity = min_similarity
        self.similarity_margin = similarity_margin
        self.expansion = expansion
        self.expansion_seeds = expansion_seeds
        self.expansion_per_seed = expansion_per_seed

    @property
    def note_type(self) -> str:
        return self.write_policy.note_type

    # ------------------------------------------------------------ factory
    @classmethod
    def from_config(
        cls,
        cfg: Config,
        *,
        store: SQLiteVectorStore,
        embedder: Embedder,
        tokenizer: Tokenizer,
        local_runner: ModelRunner | None = None,
        clock: Clock | None = None,
    ) -> "MemoryEngine":
        m = cfg.memory
        if m.write_policy == "structured":
            if local_runner is None:
                raise ValueError("the structured write policy needs a local model runner")
            wp: WritePolicy = StructuredNoteWritePolicy(local_runner, note_type=m.note_type)
        else:
            wp = VerbatimWritePolicy(tokenizer, note_type=m.note_type, chunk_tokens=m.chunk_tokens, overlap=m.chunk_overlap)
        if m.importance == "model":
            if local_runner is None:
                raise ValueError("importance=model needs a local model runner")
            imp: ImportanceScorer = ModelImportance(local_runner)
        else:
            imp = HeuristicImportance()
        return cls(
            store=store,
            embedder=embedder,
            write_policy=wp,
            screener=NoteScreener(
                tokenizer, min_tokens=m.min_note_tokens, max_tokens=m.max_note_tokens, enabled=m.screening,
                model_generated=m.write_policy == "structured",
            ),
            importance=imp,
            retrieval_policy=build_policy(m),
            budgeter=TokenBudgeter(tokenizer, m.token_budget, m.packing),
            clock=clock,
            k=m.k,
            min_similarity=m.min_similarity,
            similarity_margin=m.similarity_margin,
            expansion=m.expansion,
            expansion_seeds=m.expansion_seeds,
            expansion_per_seed=m.expansion_per_seed,
        )

    # --------------------------------------------------------- write path
    def ingest(self, documents: Iterable[Document], progress: bool = False) -> IngestSummary:
        """Distil -> screen -> (timestamp, importance) -> embed -> commit (Figure 4.4)."""
        summary = IngestSummary(self.note_type)
        t_start = time.perf_counter()
        seen = self.store.checksums(self.note_type)
        batch: list[Document] = []
        for doc in documents:
            batch.append(doc)
            if len(batch) >= self.batch_size:
                self._ingest_batch(batch, seen, summary)
                batch = []
                if progress:
                    log.info("ingested %d documents (%d notes)", summary.documents, summary.accepted)
        if batch:
            self._ingest_batch(batch, seen, summary)
        summary.elapsed_s = time.perf_counter() - t_start
        return summary

    def _ingest_batch(self, docs: list[Document], seen: set[str], summary: IngestSummary) -> None:
        plans = []
        texts: list[str] = []
        for doc in docs:
            summary.documents += 1
            row = self.store.conn.execute(
                "SELECT screener_verdict FROM source WHERE dataset=? AND doc_id=? AND note_type=?",
                (doc.dataset, doc.doc_id, self.note_type),
            ).fetchone()
            if row and row[0]:
                summary.skipped_existing += 1  # resumable ingestion
                continue
            t0 = time.perf_counter()
            candidates = self.write_policy.distil(doc)
            summary.distil_ms += (time.perf_counter() - t0) * 1000
            accepted, rejected = [], []
            for cand in candidates:
                verdict = self.screener.screen(cand, seen)
                if verdict.accepted:
                    seen.add(verdict.checksum)
                    now = to_iso(self.clock.now())
                    accepted.append((cand, verdict, self.importance.score(cand.text), now, len(texts)))
                    texts.append(cand.text.strip())
                else:
                    rejected.append((cand, verdict))
            plans.append((doc, accepted, rejected))

        # Screening precedes embedding: rejected candidates never cost embedding time.
        t0 = time.perf_counter()
        vectors = self.embedder.encode(texts) if texts else None
        summary.embed_ms += (time.perf_counter() - t0) * 1000

        for doc, accepted, rejected in plans:
            at = to_iso(self.clock.now())
            with self.store.transaction():
                source_id, _ = self.store.get_or_create_source(
                    doc.dataset, doc.doc_id, self.note_type, at, title=doc.title)
                for cand, verdict, importance, created, idx in accepted:
                    self.store.insert_note(
                        source_id=source_id,
                        note_type=self.note_type,
                        text=cand.text.strip(),
                        token_count=verdict.token_count,
                        importance=importance,
                        checksum=verdict.checksum,
                        created_at=created,
                        embedding=vectors[idx],
                    )
                for cand, verdict in rejected:
                    self.store.log_rejection(source_id, self.note_type, verdict.reason, cand.text, at)
                    summary.rejected[verdict.reason] += 1
                summary.accepted += len(accepted)
                verdict_str = f"accepted={len(accepted)};rejected={len(rejected)}"
                if rejected:
                    verdict_str += ";" + ",".join(sorted({v.reason for _, v in rejected}))
                self.store.set_source_verdict(source_id, verdict_str)

    def write_back(self, question: str, answer: str, dataset: str = "interaction", doc_id: str | None = None) -> IngestSummary:
        """Record a completed interaction as memory.  Disabled during evaluation runs,
        where it would change the store between paired questions."""
        doc_id = doc_id or f"interaction-{to_iso(self.clock.now())}"
        return self.ingest([Document(dataset=dataset, doc_id=doc_id, text=f"{question.strip()} {answer.strip()}")])

    # ---------------------------------------------------------- read path
    def recall(self, question: str, *, touch: bool = True, note_type: str | None = None) -> RecallResult:
        """Embed -> kNN -> rank -> gate -> expand -> pack.  ``retrieval_ms`` spans all of it.

        ``note_type`` selects another population (e.g. ``exemplar`` for reasoning).
        """
        nt = note_type or self.note_type
        t0 = time.perf_counter()
        qvec = self.embedder.encode_one(question, is_query=True)
        t1 = time.perf_counter()
        hits = self.store.knn(qvec, self.k, nt)
        notes = self.store.get_notes(i for i, _ in hits)
        t2 = time.perf_counter()
        candidates = [ScoredNote(note=notes[i], similarity=s) for i, s in hits if i in notes]
        ranked = self.retrieval_policy.rank(candidates, self.clock.now())
        top_sim = max((c.similarity for c in ranked), default=None)
        abstained = self._gate(ranked, top_sim)
        t3 = time.perf_counter()
        if self.expansion == "entity" and not abstained:
            ranked = self._expand(ranked, qvec, nt)
        t4 = time.perf_counter()
        context, used = self.budgeter.pack(ranked)
        t5 = time.perf_counter()
        if touch:
            self.store.touch((c.note.note_id for c in ranked if c.admitted), self.clock.now())
        t6 = time.perf_counter()
        return RecallResult(
            context=context,
            candidates=ranked,
            context_tokens=used,
            budget=self.budgeter.budget,
            retrieval_ms=(t5 - t0) * 1000,
            timings={
                "embed_ms": (t1 - t0) * 1000,
                "search_ms": (t2 - t1) * 1000,
                "rank_ms": (t3 - t2) * 1000,
                "expand_ms": (t4 - t3) * 1000,
                "pack_ms": (t5 - t4) * 1000,
                "touch_ms": (t6 - t5) * 1000,
            },
            abstained=abstained,
            top_similarity=top_sim,
        )

    def _gate(self, ranked: list[ScoredNote], top_sim: float | None) -> bool:
        """Capability-adaptive gating.  Returns True when memory is withheld entirely.

        * abstain: the best note is too weak to be worth the prefill cost and the
          distraction risk, so the model answers exactly as it would without memory;
        * margin: only notes close to the best one are eligible, so the budget is
          a ceiling rather than a target.
        """
        if top_sim is None or top_sim < self.min_similarity:
            for c in ranked:
                c.eligible = False
            return True
        if self.similarity_margin is not None:
            floor = top_sim - self.similarity_margin
            for c in ranked:
                c.eligible = c.similarity >= floor
        return False

    def _expand(self, ranked: list[ScoredNote], qvec, note_type: str) -> list[ScoredNote]:
        """Entity-bridge expansion: one step of spreading activation over titles.

        For the top eligible seed notes, every mention of another entity's title
        pulls in the notes about that entity, inserted directly after the seed so
        the budgeter admits them next.  No model call; a dictionary lookup over
        the seed's word n-grams.
        """
        index, longest = self.store.title_index(note_type)
        if not index:
            return ranked
        seeds = [c for c in ranked if c.eligible][: self.expansion_seeds]
        own = self.store.note_titles(c.note.note_id for c in seeds)
        present = {c.note.note_id for c in ranked}
        bridged: dict[int, list[int]] = {}
        for seed in seeds:
            own_title = " ".join((own.get(seed.note.note_id) or "").split())
            found: list[int] = []
            for title in _mentions(seed.note.text, index, longest):
                if title == own_title or own_title.startswith(title + " ("):
                    continue
                for nid in index[title]:
                    if nid not in present:
                        found.append(nid)
                        present.add(nid)
                if len(found) >= self.expansion_per_seed:
                    break
            bridged[seed.note.note_id] = found[: self.expansion_per_seed]
        new_ids = [i for ids in bridged.values() for i in ids]
        if not new_ids:
            return ranked
        notes = self.store.get_notes(new_ids)
        sims = self.store.similarities(qvec, new_ids)
        out: list[ScoredNote] = []
        for c in ranked:
            out.append(c)
            for nid in bridged.get(c.note.note_id, []):
                if nid in notes:
                    out.append(ScoredNote(note=notes[nid], similarity=sims.get(nid, 0.0), composite=c.composite,
                                          via=c.note.note_id))
        for i, c in enumerate(out, start=1):
            c.rank = i
        return out


_WORD_SPAN = re.compile(r"[\w'’.&-]+", re.UNICODE)


def _mentions(text: str, index: dict[str, list[int]], longest: int) -> list[str]:
    """Titles from ``index`` that occur in ``text`` on word boundaries, in text order,
    preferring the longest match at each position."""
    spans = [m.span() for m in _WORD_SPAN.finditer(text)]
    found: list[str] = []
    i = 0
    while i < len(spans):
        hit = None
        for n in range(min(longest, len(spans) - i), 0, -1):
            cand = " ".join(text[spans[i][0]: spans[i + n - 1][1]].split()).rstrip(".")
            if cand in index:
                hit = (cand, n)
                break
        if hit:
            if hit[0] not in found:
                found.append(hit[0])
            i += hit[1]
        else:
            i += 1
    return found

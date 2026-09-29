"""MemoryEngine: facade over the write path, the store and the read path.

It holds configured policy objects and implements no policy itself, so one code
path serves both control and treatment (Figure 4.3).
"""

from __future__ import annotations

import logging
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
                tokenizer, min_tokens=m.min_note_tokens, max_tokens=m.max_note_tokens, enabled=m.screening
            ),
            importance=imp,
            retrieval_policy=build_policy(m),
            budgeter=TokenBudgeter(tokenizer, m.token_budget, m.packing),
            clock=clock,
            k=m.k,
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
                source_id, _ = self.store.get_or_create_source(doc.dataset, doc.doc_id, self.note_type, at)
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
    def recall(self, question: str, *, touch: bool = True) -> RecallResult:
        """Embed -> kNN -> rank -> pack (Figure 4.5).  ``retrieval_ms`` spans all four."""
        t0 = time.perf_counter()
        qvec = self.embedder.encode_one(question, is_query=True)
        t1 = time.perf_counter()
        hits = self.store.knn(qvec, self.k, self.note_type)
        notes = self.store.get_notes(i for i, _ in hits)
        t2 = time.perf_counter()
        candidates = [ScoredNote(note=notes[i], similarity=s) for i, s in hits if i in notes]
        ranked = self.retrieval_policy.rank(candidates, self.clock.now())
        t3 = time.perf_counter()
        context, used = self.budgeter.pack(ranked)
        t4 = time.perf_counter()
        if touch:
            self.store.touch((c.note.note_id for c in ranked if c.admitted), self.clock.now())
        t5 = time.perf_counter()
        return RecallResult(
            context=context,
            candidates=ranked,
            context_tokens=used,
            budget=self.budgeter.budget,
            retrieval_ms=(t4 - t0) * 1000,
            timings={
                "embed_ms": (t1 - t0) * 1000,
                "search_ms": (t2 - t1) * 1000,
                "rank_ms": (t3 - t2) * 1000,
                "pack_ms": (t4 - t3) * 1000,
                "touch_ms": (t5 - t4) * 1000,
            },
        )

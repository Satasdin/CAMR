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
from camr.memory.entities import mentions_any, question_entities
from camr.memory.importance import HeuristicImportance, ImportanceScorer, ModelImportance
from camr.memory.note import Document, RecallResult, ScoredNote, to_iso
from camr.memory.retrieval import RetrievalPolicy, build_policy
from camr.memory.screener import NoteScreener
from camr.memory.store import SQLiteVectorStore
from camr.memory.write_policy import StructuredNoteWritePolicy, VerbatimWritePolicy, WritePolicy
from camr.models.runner import ModelRunner
from camr.models.tokenizer import Tokenizer

log = logging.getLogger(__name__)

KEYWORD_BONUS = 0.10  # hybrid order: the best word match gains this much over its cosine similarity


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
        entity_gate: bool = False,
        expansion: str = "none",
        expansion_seeds: int = 3,
        expansion_per_seed: int = 2,
        keyword_k: int = 0,
        per_title: int = 0,
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
        self.entity_gate = entity_gate
        self.expansion = expansion
        self.expansion_seeds = expansion_seeds
        self.expansion_per_seed = expansion_per_seed
        # notes found by keyword (BM25) added to the vector candidates; 0 = only while some notes wait for vectors
        self.keyword_k = keyword_k
        # at most this many notes whose sources share a title (e.g. corrections of one rule) enter a context; 0 = any
        self.per_title = per_title
        self.query_adapter = None  # learned during sleep (camr.memory.adapter); None = the embedder's own vector

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
            entity_gate=m.entity_gate,
            expansion=m.expansion,
            expansion_seeds=m.expansion_seeds,
            expansion_per_seed=m.expansion_per_seed,
            keyword_k=m.keyword_k,
            per_title=m.per_title,
        )

    # --------------------------------------------------------- write path
    def ingest(self, documents: Iterable[Document], progress: bool = False, seen: set[str] | None = None,
               defer_embedding: bool = False) -> IngestSummary:
        """Distil -> screen -> (timestamp, importance) -> embed -> commit (Figure 4.4).

        ``seen`` (the checksums already stored) can be passed by a caller ingesting in many calls, so it is read
        from the store once rather than once per call; it is updated in place. ``defer_embedding`` stores notes
        without vectors (keyword-searchable at once; ``embed_pending`` gives them vectors later, and recall
        embeds the ones a question reaches)."""
        summary = IngestSummary(self.note_type)
        t_start = time.perf_counter()
        seen = self.store.checksums(self.note_type) if seen is None else seen
        batch: list[Document] = []
        for doc in documents:
            batch.append(doc)
            if len(batch) >= self.batch_size:
                self._ingest_batch(batch, seen, summary, defer_embedding)
                batch = []
                if progress:
                    log.info("ingested %d documents (%d notes)", summary.documents, summary.accepted)
        if batch:
            self._ingest_batch(batch, seen, summary, defer_embedding)
        summary.elapsed_s = time.perf_counter() - t_start
        return summary

    def embed_pending(self, limit: int | None = None, batch: int = 256) -> int:
        """Give up to ``limit`` queued notes their vectors (all of them when None). Returns notes embedded."""
        done = 0
        while limit is None or done < limit:
            rows = self.store.pending(batch if limit is None else min(batch, limit - done))
            if not rows:
                break
            vecs = self.embedder.encode([t for _, _, t in rows])
            self.store.set_embeddings([(i, nt, v) for (i, nt, _), v in zip(rows, vecs)])
            done += len(rows)
        return done

    def _ingest_batch(self, docs: list[Document], seen: set[str], summary: IngestSummary,
                      defer_embedding: bool = False) -> None:
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
        vectors = self.embedder.encode(texts) if texts and not defer_embedding else None
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
                        embedding=None if vectors is None else vectors[idx],
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
        if self.query_adapter is not None:
            qvec = self.query_adapter.apply(qvec)
        t1 = time.perf_counter()
        hits = self.store.knn(qvec, self.k, nt)
        kk = self.keyword_k or (self.k if self.store.has_pending(nt) else 0)
        kw_rank: dict[int, float] = {}
        if kk:
            hits, kw_rank = self._with_keyword_hits(question, qvec, hits, kk, nt)
        notes = self.store.get_notes(i for i, _ in hits)
        t2 = time.perf_counter()
        candidates = [ScoredNote(note=notes[i], similarity=s) for i, s in hits if i in notes]
        ranked = self.retrieval_policy.rank(candidates, self.clock.now())
        if kw_rank:
            # Hybrid order: similarity plus a bounded bonus for how well the question's words match (BM25, scaled
            # to the best match), so an exact word (a number, a rare name) lifts its note. Similarities, and so the
            # gate, are unchanged.
            ranked.sort(key=lambda c: (-(c.similarity + KEYWORD_BONUS * kw_rank.get(c.note.note_id, 0.0)),
                                       c.note.note_id))
            for r, c in enumerate(ranked):
                c.rank = r + 1
        top_sim = max((c.similarity for c in ranked), default=None)
        abstained = self._gate(ranked, top_sim)
        if self.entity_gate and not abstained:
            abstained = self._entity_gate(question, ranked)
        t3 = time.perf_counter()
        if self.expansion == "entity" and not abstained:
            ranked = self._expand(ranked, qvec, nt)
        t4 = time.perf_counter()
        if self.per_title:
            self._limit_per_title(ranked)
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

    def _limit_per_title(self, ranked: list[ScoredNote]) -> None:
        """Keep the best ``per_title`` notes of each source title eligible: notes that repeat one source (the same
        rule corrected six times) add little and crowd out the rest; a small model echoes every copy it reads."""
        ids = sorted({c.note.source_id for c in ranked})
        if not ids:
            return
        marks = ",".join("?" * len(ids))
        title = dict(self.store.conn.execute(f"SELECT source_id, title FROM source WHERE source_id IN ({marks})", ids))
        seen: dict[str, int] = {}
        for c in ranked:
            t = title.get(c.note.source_id) or ""
            if not t or not c.eligible:
                continue
            seen[t] = seen.get(t, 0) + 1
            if seen[t] > self.per_title:
                c.eligible = False

    def _with_keyword_hits(self, question: str, qvec, hits: list[tuple[int, float]], kk: int,
                           nt: str) -> tuple[list[tuple[int, float]], dict[int, float]]:
        """Add the notes the question's words find (BM25) to the vector hits, with their true cosine similarity.
        A keyword hit still waiting for its vector is embedded now (and stored, unless the store is read-only):
        the notes a question reaches are the first to get vectors."""
        have = {i for i, _ in hits}
        found = self.store.keyword(question, kk, nt)
        best = max((sc for _, sc in found), default=0.0)
        kw_rank = {i: (sc / best if best > 0 else 0.0) for i, sc in found}  # word-match strength, 0..1
        extra = [i for i, _ in found if i not in have]
        if not extra:
            return hits, kw_rank
        waiting = self.store.pending(0, extra)
        if waiting:
            vecs = self.embedder.encode([t for _, _, t in waiting])
            if self.store.readonly:
                fresh = {i: v for (i, _, _), v in zip(waiting, vecs)}
            else:
                self.store.set_embeddings([(i, t, v) for (i, t, _), v in zip(waiting, vecs)])
                fresh = {}
        else:
            fresh = {}
        sims = self.store.similarities(qvec, [i for i in extra if i not in fresh])
        import numpy as np

        for i, v in fresh.items():
            sims[i] = float(np.dot(qvec, v) / ((np.linalg.norm(qvec) * np.linalg.norm(v)) or 1.0))
        merged = hits + [(i, s) for i, s in sims.items()]
        merged.sort(key=lambda t: (-round(t[1], 7), t[0]))
        return merged, kw_rank

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

    @staticmethod
    def _entity_gate(question: str, ranked: list[ScoredNote]) -> bool:
        """Entity-anchored gate: when the question names an entity (e.g. "The Loudwater Mystery") and no
        eligible note mentions it, the notes are about something else, however similar they look, so
        memory is withheld. Similarity alone cannot tell "a different film by a similar director" from
        "this film"; a name can. Questions that name no entity are unaffected."""
        entities = question_entities(question)
        if not entities or any(mentions_any(c.note.text, entities) for c in ranked if c.eligible):
            return False
        for c in ranked:
            c.eligible = False
        return True

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

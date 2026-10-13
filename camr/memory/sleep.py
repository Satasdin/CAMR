"""Sleep: offline consolidation while the assistant is idle ("hibernation learning").

Nothing here touches the language model's weights. Sleep reorganises and extends the
engine's own external weights, the things it can learn without a GPU:

1. **Tidy**: near-duplicate notes from the web and from packs (cosine ≥ 0.97) are
   merged, keeping the oldest. The user's own notes are never deleted by sleep.
2. **Curiosity** (optional, needs the web): names that public notes mention often
   but that memory has no note about are looked up and learned, so the next
   multi-step question finds its second hop already in memory. Only text from public
   sources (web pages, packs) is mined; personal notes never leave the machine.
3. **Index**: once memory is large (100k notes; below that exact search is faster
   and more accurate, as measured), the learned index (``camr.memory.ivf``) is
   rebuilt over every note, so a question reads a few clusters, not all memory.
4. **Learn to fetch**: the query adapter (``camr.memory.adapter``) is trained on
   pairs (question, note that answered it) from the engine's experience. It is kept
   only if it raises recall on held-out pairs; otherwise the old one stays.

Each step reports what it changed, so the user (and the thesis) can see what sleep did.
"""

from __future__ import annotations

import datetime as dt
import re
import time
from collections import Counter
from pathlib import Path

import numpy as np

from camr.memory.adapter import QueryAdapter, recall_at
from camr.memory.eager import learn_pages
from camr.memory.engine import MemoryEngine
from camr.memory.entities import norm
from camr.memory.fetch import WebLookup
from camr.memory.ivf import IVFIndex

PUBLIC = ("web", "pack:%")
_NAME = re.compile(r"(?<![\w'’])([A-Z][\w'’.&-]+(?:\s+(?:(?:of|the|de|da|von|van|and)\s+)*[A-Z][\w'’.&-]+)+)")
_NOT_NAMES = {"the", "a", "an", "in", "on", "it", "he", "she", "they", "this", "that", "his", "her", "its", "january",
              "february", "march", "april", "may", "june", "july", "august", "september", "october", "november",
              "december", "monday", "sunday", "united states", "new york"}


def _public_where() -> str:
    return "(s.dataset = 'web' OR s.dataset LIKE 'pack:%')"


# ---------------------------------------------------------------------- 1. tidy
def dedupe(engine: MemoryEngine, threshold: float = 0.97, block: int = 2048) -> int:
    """Delete near-duplicate public notes (keep the oldest). Returns notes removed."""
    store, nt = engine.store, engine.note_type
    rows = store.conn.execute(
        f"SELECT n.note_id, e.embedding FROM note n JOIN source s USING(source_id) JOIN note_embedding e USING(note_id)"
        f" WHERE n.note_type=? AND {_public_where()} ORDER BY n.note_id", (nt,)).fetchall()
    if len(rows) < 2:
        return 0
    ids = np.array([r[0] for r in rows])
    x = np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
    x = x / np.maximum(np.linalg.norm(x, axis=1, keepdims=True), 1e-12)
    drop: set[int] = set()
    for s in range(0, len(x), block):
        sims = x[s:s + block] @ x.T
        for i in range(sims.shape[0]):
            gi = s + i
            if int(ids[gi]) in drop:
                continue
            later = np.nonzero(sims[i, gi + 1:] >= threshold)[0] + gi + 1
            drop.update(int(ids[j]) for j in later)
    if drop:
        with store.transaction() as c:
            marks = ",".join("?" * len(drop))
            if store.use_vec:
                c.execute(f"DELETE FROM note_vec WHERE rowid IN ({marks})", list(drop))
            c.execute(f"DELETE FROM note_embedding WHERE note_id IN ({marks})", list(drop))
            c.execute(f"DELETE FROM note WHERE note_id IN ({marks})", list(drop))
    return len(drop)


# ---------------------------------------------------------------------- 2. curiosity
def knowledge_gaps(engine: MemoryEngine, limit: int = 10, min_mentions: int = 2) -> list[tuple[str, int]]:
    """Names mentioned by public notes that memory has no note about, most mentioned first."""
    store, nt = engine.store, engine.note_type
    known = {norm(t) for t in store.title_index(nt)[0]}
    counts: Counter[str] = Counter()
    spelled: dict[str, str] = {}
    for (text,) in store.conn.execute(
            f"SELECT n.text FROM note n JOIN source s USING(source_id) WHERE n.note_type=? AND {_public_where()}",
            (nt,)):
        body = text.split(": ", 1)[-1]  # drop the "Title: " prefix the write path adds
        for sentence in re.split(r"(?<=[a-z0-9)])\.\s+", body):  # a name never runs across a sentence end (D-22)
            for m in _NAME.finditer(sentence):
                name = m.group(1).strip(" .,'’")
                key = norm(name)
                if len(key) < 4 or key in _NOT_NAMES or key in known:
                    continue
                counts[key] += 1
                spelled.setdefault(key, name)
    return [(spelled[k], c) for k, c in counts.most_common() if c >= min_mentions][:limit]


def curiosity(engine: MemoryEngine, lookup: WebLookup, limit: int = 10) -> dict:
    learned, looked = [], []
    for name, mentions in knowledge_gaps(engine, limit):
        page, _ = lookup.article(name, _scratch())
        looked.append(name)
        if page and learn_pages(engine, [page]):
            learned.append({"name": name, "mentions": mentions, "title": page.title, "url": page.url})
    return {"looked_up": looked, "learned": learned}


def _scratch():
    from camr.memory.fetch import Lookup

    return Lookup(question="")


# ---------------------------------------------------------------------- 3. index
# Measured (results/sleep/index.json): below ~100k notes exact search in RAM is both faster and more accurate than
# the index on a 4-core CPU; at 150k-400k notes the index is 1.6-2.2x faster and its process ~30% smaller.
INDEX_MIN_NOTES = 100_000


def rebuild_index(engine: MemoryEngine, min_notes: int = INDEX_MIN_NOTES, probe_queries: int = 50, k: int = 10) -> dict:
    store, nt = engine.store, engine.note_type
    ids, mat = store.all_vectors(nt)
    if len(ids) < min_notes:
        return {"built": False, "notes": int(len(ids)), "reason": f"exact search is fast below {min_notes} notes"}
    t0 = time.perf_counter()
    store.ivf = None  # build from everything, then switch over
    idx = IVFIndex.build(store.ivf_dir, ids, mat, nt)
    build_s = time.perf_counter() - t0
    store.load_ivf()
    rng = np.random.default_rng(13)
    qs = mat[rng.choice(len(mat), min(probe_queries, len(mat)), replace=False)]
    qs = qs + rng.normal(0, 0.02, qs.shape).astype(np.float32)  # near, not identical, to stored notes
    unit = mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-12)
    overlap, t_exact, t_ivf = [], [], []
    for q in qs:
        a = time.perf_counter()
        exact = set(ids[np.argsort(-(unit @ (q / np.linalg.norm(q))))[:k]].tolist())
        t_exact.append(time.perf_counter() - a)
        a = time.perf_counter()
        approx = {i for i, _ in idx.search(q, k)}
        t_ivf.append(time.perf_counter() - a)
        overlap.append(len(exact & approx) / k)
    return {"built": True, "notes": int(len(ids)), "clusters": int(len(idx.centroids)), "nprobe": idx.nprobe,
            "build_s": round(build_s, 2), f"recall_vs_exact@{k}": round(float(np.mean(overlap)), 3),
            "exact_ms": round(1000 * float(np.median(t_exact)), 2), "index_ms": round(1000 * float(np.median(t_ivf)), 2)}


# ---------------------------------------------------------------------- 4. learn to fetch
def train_adapter(engine: MemoryEngine, pairs: list[tuple[str, set[int]]], path: str | Path, *, min_pairs: int = 20,
                  rank: int = 16, epochs: int = 40, seed: int = 13) -> dict:
    """Train a query adapter on (question, ids of notes that answered it); keep it only if held-out recall rises."""
    store, nt = engine.store, engine.note_type
    ids, mat = store.all_vectors(nt)
    id_pos = {int(i): j for j, i in enumerate(ids)}
    pairs = [(q, {i for i in g if i in id_pos}) for q, g in pairs]
    pairs = [(q, g) for q, g in pairs if g]
    if len(pairs) < min_pairs:
        return {"trained": False, "pairs": len(pairs), "reason": f"needs at least {min_pairs} answered questions"}
    rng = np.random.default_rng(seed)
    order = rng.permutation(len(pairs))
    cut = max(1, int(0.8 * len(pairs)))
    train, held = [pairs[i] for i in order[:cut]], [pairs[i] for i in order[cut:]]
    qv = {q: v for q, v in zip([p[0] for p in pairs], engine.embedder.encode([p[0] for p in pairs], is_query=True))}
    unit = mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-12)
    Q, P, H = [], [], []
    for q, gold in train:
        qvec = qv[q] / (np.linalg.norm(qv[q]) or 1.0)
        top = np.argsort(-(unit @ qvec))[:12]
        hard = [unit[j] for j in top if int(ids[j]) not in gold][:4]
        while len(hard) < 4:
            hard.append(unit[rng.integers(len(unit))])
        for g in gold:
            Q.append(qvec)
            P.append(unit[id_pos[g]])
            H.append(np.vstack(hard))
    before = recall_at(np.vstack([qv[q] for q, _ in held]), [g for _, g in held], ids, mat)
    ad = QueryAdapter.identity(mat.shape[1], rank=rank, seed=seed)
    losses = ad.fit(np.vstack(Q), np.vstack(P), np.stack(H), epochs=epochs, seed=seed)
    after = recall_at(np.vstack([qv[q] for q, _ in held]), [g for _, g in held], ids, mat, adapter=ad)
    keep = after["recall@5"] > before["recall@5"] and after["recall@1"] >= before["recall@1"]
    if keep:
        ad.save(path, trained_at=time.time(), pairs=len(pairs))
        engine.query_adapter = ad
    return {"trained": True, "kept": bool(keep), "pairs": len(pairs), "train_pairs": len(train), "held_out": len(held),
            "recall_before": before, "recall_after": after, "loss_first": round(losses[0], 4),
            "loss_last": round(losses[-1], 4)}


# ---------------------------------------------------------------------- the whole night
def sleep(engine: MemoryEngine, *, lookup: WebLookup | None = None, pairs: list[tuple[str, set[int]]] | None = None,
          adapter_path: str | Path | None = None, curiosity_limit: int = 10, index_min_notes: int = INDEX_MIN_NOTES) -> dict:
    t0 = time.perf_counter()
    report: dict = {"started": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                    "notes_before": engine.store.count(engine.note_type)}
    report["tidy"] = {"duplicates_removed": dedupe(engine)}
    report["curiosity"] = curiosity(engine, lookup, curiosity_limit) if lookup and curiosity_limit else {
        "skipped": "web off"}
    report["index"] = rebuild_index(engine, min_notes=index_min_notes)
    report["adapter"] = train_adapter(engine, pairs or [], adapter_path) if adapter_path else {"skipped": "no path"}
    report["notes_after"] = engine.store.count(engine.note_type)
    report["seconds"] = round(time.perf_counter() - t0, 2)
    return report

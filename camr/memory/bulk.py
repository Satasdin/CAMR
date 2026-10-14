"""Bulk ingestion: large collections into memory, streaming, resumable, within the device's limits.

    bulk_ingest(engine, read_any("corpus.jsonl"), governor=Governor(store_path), checkpoint="corpus.ckpt")

* **Streaming**: documents are read lazily and ingested a batch at a time, so memory use
  does not grow with the size of the collection (one batch, plus the set of checksums
  that keeps duplicates out).
* **Resumable**: after every batch the number of documents consumed is saved; a rerun
  skips them without re-reading their notes, and the write path skips any source that is
  already stored, so a crash or a stop never duplicates or loses work.
* **Within limits**: before each batch the governor checks free disk, the store's size
  cap, available RAM and the process's size. When a limit would be crossed the job
  stops cleanly and says which limit, how far it got, and how many more notes the
  device has room for.
"""

from __future__ import annotations

import itertools
import json
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Iterator

from camr.device import Governor, process_rss_mb
from camr.memory.engine import MemoryEngine
from camr.memory.note import Document


# ---------------------------------------------------------------------- readers (lazy)
def read_jsonl(path: str | Path, *, dataset: str | None = None, text_key: str = "text", title_key: str = "title",
               id_key: str = "id") -> Iterator[Document]:
    path = Path(path)
    ds = dataset or f"bulk:{path.stem}"
    with open(path, encoding="utf-8") as f:
        for n, line in enumerate(f):
            line = line.strip()
            if not line:
                continue
            row = json.loads(line)
            text = (row.get(text_key) or "").strip()
            if text:
                yield Document(ds, str(row.get(id_key) or n), text, row.get(title_key) or "")


def read_folder(path: str | Path, *, dataset: str | None = None,
                suffixes: tuple[str, ...] = (".txt", ".md")) -> Iterator[Document]:
    """Text files under a folder; each paragraph (blank-line separated) is a document titled by its file."""
    root = Path(path)
    ds = dataset or f"bulk:{root.name}"
    for f in sorted(p for p in root.rglob("*") if p.suffix.lower() in suffixes and p.is_file()):
        rel = f.relative_to(root).as_posix()
        paras = [p.strip() for p in f.read_text(encoding="utf-8", errors="replace").split("\n\n")]
        for i, para in enumerate(p for p in paras if p):
            yield Document(ds, f"{rel}#{i}", " ".join(para.split()), f.stem.replace("_", " "))


def read_any(path: str | Path, **kw) -> Iterator[Document]:
    p = Path(path)
    if p.is_dir():
        return read_folder(p, **kw)
    if p.suffix == ".jsonl":
        return read_jsonl(p, **kw)
    if p.suffix in (".txt", ".md"):
        return _one_file(p, **kw)
    raise ValueError(f"don't know how to read {p} (a folder, .jsonl, .txt or .md)")


def _one_file(p: Path, dataset: str | None = None, **_) -> Iterator[Document]:
    ds = dataset or f"bulk:{p.stem}"
    for i, para in enumerate(x.strip() for x in p.read_text(encoding="utf-8", errors="replace").split("\n\n")):
        if para:
            yield Document(ds, f"{p.name}#{i}", " ".join(para.split()), p.stem.replace("_", " "))


# ---------------------------------------------------------------------- the job
@dataclass
class BulkReport:
    documents: int = 0          # consumed in this run (ingested or found already stored)
    resumed_from: int = 0       # consumed by earlier runs
    skipped_existing: int = 0
    notes_added: int = 0
    rejected: dict = field(default_factory=dict)
    seconds: float = 0.0
    embed_seconds: float = 0.0
    docs_per_s: float = 0.0
    notes_per_s: float = 0.0
    store_mb_before: float = 0.0
    store_mb_after: float = 0.0
    bytes_per_note: float | None = None
    peak_rss_mb: float = 0.0
    stopped: str | None = None  # the limit that stopped the job, or None when the input ran out
    detail: str = ""
    finished: bool = False
    room_for_notes: int | None = None  # how many more notes fit above the disk reserve

    def as_dict(self) -> dict:
        return asdict(self)


def bulk_ingest(engine: MemoryEngine, docs: Iterable[Document], *, governor: Governor | None = None,
                batch_docs: int = 512, checkpoint: str | Path | None = None, limit: int | None = None,
                progress: Callable[[BulkReport], None] | None = None) -> BulkReport:
    rep = BulkReport()
    ckpt = Path(checkpoint) if checkpoint else None
    state = json.loads(ckpt.read_text()) if ckpt and ckpt.exists() else {"consumed": 0}
    rep.resumed_from = int(state["consumed"])
    it = iter(docs)
    if rep.resumed_from:
        for _ in itertools.islice(it, rep.resumed_from):  # fast-forward: already ingested by an earlier run
            pass
    gov = governor
    rep.store_mb_before = gov.store_mb() if gov else 0.0
    seen = engine.store.checksums(engine.note_type)  # held across batches: duplicates stay out, no re-reads
    est = 4200.0  # bytes per note until measured
    notes_per_doc = 1.5
    t0 = time.perf_counter()
    consumed = rep.resumed_from
    while True:
        if limit is not None and rep.documents >= limit:
            break
        n = batch_docs if limit is None else min(batch_docs, limit - rep.documents)
        if gov:
            st = gov.check(upcoming_mb=n * notes_per_doc * est / (1024 * 1024))
            if not st.ok:
                rep.stopped, rep.detail = st.reason, st.detail
                break
        batch = list(itertools.islice(it, n))
        if not batch:
            rep.finished = True
            break
        mb0 = gov.store_mb() if gov else 0.0
        s = engine.ingest(batch, seen=seen)
        rep.documents += s.documents
        rep.skipped_existing += s.skipped_existing
        rep.notes_added += s.accepted
        rep.embed_seconds += s.embed_ms / 1000
        for k, v in s.rejected.items():
            rep.rejected[k] = rep.rejected.get(k, 0) + v
        consumed += len(batch)
        if ckpt:
            ckpt.write_text(json.dumps({"consumed": consumed}))
        if gov and s.accepted:
            grew = (gov.store_mb() - mb0) * 1024 * 1024
            if grew > 0:
                est = 0.7 * est + 0.3 * grew / s.accepted  # smoothed: SQLite grows in pages
            notes_per_doc = max(1.0, 0.7 * notes_per_doc + 0.3 * s.accepted / max(1, s.documents))
        rep.peak_rss_mb = max(rep.peak_rss_mb, process_rss_mb())
        rep.seconds = time.perf_counter() - t0
        if progress:
            progress(rep)
    rep.seconds = round(time.perf_counter() - t0, 2)
    rep.docs_per_s = round(rep.documents / rep.seconds, 1) if rep.seconds else 0.0
    rep.notes_per_s = round(rep.notes_added / rep.seconds, 1) if rep.seconds else 0.0
    rep.embed_seconds = round(rep.embed_seconds, 2)
    if gov:
        rep.store_mb_after = round(gov.store_mb(), 1)
        rep.store_mb_before = round(rep.store_mb_before, 1)
        if rep.notes_added:
            rep.bytes_per_note = round((rep.store_mb_after - rep.store_mb_before) * 1024 * 1024 / rep.notes_added)
        free = gov._probe(gov.store_path.parent).disk_free_mb - gov.limits.reserve_disk_mb
        rep.room_for_notes = max(0, int(free * 1024 * 1024 / (rep.bytes_per_note or est)))
    rep.peak_rss_mb = round(max(rep.peak_rss_mb, process_rss_mb()), 1)
    return rep

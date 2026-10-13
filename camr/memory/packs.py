"""Knowledge packs: memory that arrives ready-made.

A pack is a single ``.camrpack`` file (a zip) holding notes, their provenance and, for
one embedder, their vectors:

    manifest.json   name, title, description, version, licence, embedder, dim, counts
    notes.jsonl     one note per line: {"title", "url", "text"}
    vectors.npy     float32 matrix, one row per note (rows of notes.jsonl, in order)

Installing a pack whose embedder matches the user's copies the vectors straight into
the store: no model runs, so a pack of thousands of notes installs in seconds. These
vectors are the engine's external weights; installing a pack is plugging in weights
that someone else has already computed. With a different embedder the notes are
re-embedded on install. Notes still pass the screener, so a pack cannot inject
instruction-like text or duplicates, and every note keeps its source page.

A pack is removed as a unit (its notes are the sources whose dataset is
``pack:<name>``). ``harvest`` builds a pack from the web for a topic.
"""

from __future__ import annotations

import datetime as dt
import io
import json
import re
import time
import zipfile
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np

from camr.memory.engine import MemoryEngine
from camr.memory.fetch import WebLookup, WebPage
from camr.memory.note import CandidateNote, Document, to_iso

FORMAT = "camrpack/1"
PREFIX = "pack:"


@dataclass
class PackManifest:
    name: str
    title: str
    description: str
    version: str = "1"
    format: str = FORMAT
    created: str = ""
    embedder: str = ""
    dim: int = 0
    notes: int = 0
    sources: int = 0
    licence: str = "CC BY-SA 4.0 (Wikipedia text)"
    attribution: str = "Wikipedia contributors"


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:48] or "pack"


def build_pack(path: str | Path, engine: MemoryEngine, *, name: str, title: str, description: str,
               docs: list[Document], licence: str | None = None, attribution: str | None = None) -> PackManifest:
    """Chunk, screen and embed ``docs`` with the engine's own write path, and write them as a pack."""
    notes: list[dict] = []
    seen: set[str] = set()
    for doc in docs:
        for cand in engine.write_policy.distil(doc):
            v = engine.screener.screen(cand, seen)
            if v.accepted:
                seen.add(v.checksum)
                notes.append({"title": doc.title or "", "url": doc.doc_id, "text": cand.text.strip()})
    vecs = engine.embedder.encode([n["text"] for n in notes]) if notes else np.zeros((0, engine.embedder.dim))
    man = PackManifest(name=slug(name), title=title, description=description, created=to_iso(dt.datetime.now(
        dt.timezone.utc)), embedder=engine.embedder.name, dim=int(engine.embedder.dim), notes=len(notes),
        sources=len({n["url"] for n in notes}))
    if licence:
        man.licence = licence
    if attribution:
        man.attribution = attribution
    buf = io.BytesIO()
    np.save(buf, np.asarray(vecs, dtype=np.float32))
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("manifest.json", json.dumps(asdict(man), indent=2))
        z.writestr("notes.jsonl", "\n".join(json.dumps(n, ensure_ascii=False) for n in notes))
        z.writestr("vectors.npy", buf.getvalue())
    return man


def read_pack(path: str | Path) -> tuple[PackManifest, list[dict], np.ndarray]:
    with zipfile.ZipFile(path) as z:
        man = PackManifest(**json.loads(z.read("manifest.json")))
        if man.format != FORMAT:
            raise ValueError(f"unsupported pack format {man.format!r}")
        raw = z.read("notes.jsonl").decode()
        notes = [json.loads(line) for line in raw.splitlines() if line.strip()]
        vecs = np.load(io.BytesIO(z.read("vectors.npy")), allow_pickle=False)
    if len(vecs) != len(notes):
        raise ValueError("pack is corrupt: notes and vectors differ in number")
    return man, notes, vecs


def install_pack(engine: MemoryEngine, path: str | Path) -> dict:
    """Add a pack's notes to memory. Returns counts and whether its vectors could be used as they are."""
    t0 = time.perf_counter()
    man, notes, vecs = read_pack(path)
    store, dataset = engine.store, PREFIX + man.name
    reuse = man.embedder == engine.embedder.name and man.dim == engine.embedder.dim
    if not reuse and notes:
        vecs = np.asarray(engine.embedder.encode([n["text"] for n in notes]), dtype=np.float32)
    seen = store.checksums(engine.note_type)
    added = skipped = 0
    now = to_iso(engine.clock.now())
    with store.transaction():
        sources: dict[str, int] = {}
        for note, vec in zip(notes, vecs):
            v = engine.screener.screen(CandidateNote(note["text"], engine.note_type), seen)
            if not v.accepted:
                skipped += 1
                continue
            seen.add(v.checksum)
            if note["url"] not in sources:
                sources[note["url"]], _ = store.get_or_create_source(dataset, note["url"], engine.note_type, now,
                                                                      title=note.get("title") or None)
            store.insert_note(source_id=sources[note["url"]], note_type=engine.note_type, text=note["text"],
                              token_count=v.token_count, importance=engine.importance.score(note["text"]),
                              checksum=v.checksum, created_at=now, embedding=vec)
            added += 1
        for sid in sources.values():
            store.set_source_verdict(sid, f"pack={man.name}")
    return {"pack": man.name, "title": man.title, "notes_added": added, "skipped": skipped,
            "vectors_reused": reuse, "seconds": round(time.perf_counter() - t0, 2)}


def uninstall_pack(engine: MemoryEngine, name: str) -> int:
    ids = [r[0] for r in engine.store.conn.execute("SELECT source_id FROM source WHERE dataset=?", (PREFIX + name,))]
    return sum(engine.store.delete_source(i) for i in ids)


def installed_packs(engine: MemoryEngine) -> list[dict]:
    rows = engine.store.conn.execute(
        "SELECT s.dataset, COUNT(DISTINCT s.source_id), COUNT(n.note_id), MIN(s.ingested_at) FROM source s"
        " LEFT JOIN note n USING(source_id) WHERE s.dataset LIKE 'pack:%' GROUP BY s.dataset ORDER BY 4").fetchall()
    return [{"name": r[0][len(PREFIX):], "sources": r[1], "notes": r[2], "installed": r[3]} for r in rows]


def harvest(engine: MemoryEngine, lookup: WebLookup, topic: str, path: str | Path, *, pages: int = 20,
            title: str | None = None) -> tuple[PackManifest, list[WebPage]]:
    """Build a pack about ``topic`` from the web (its article and related articles)."""
    found = lookup.topic_pages(topic, limit=pages)
    docs = [Document(dataset="web", doc_id=p.url, text=p.text, title=p.title) for p in found.pages]
    man = build_pack(path, engine, name=topic, title=title or topic.title(),
                     description=f"{len(docs)} Wikipedia article leads about {topic}, harvested "
                                 f"{dt.date.today().isoformat()}", docs=docs)
    return man, found.pages

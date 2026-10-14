"""Large data: stream ~170k real paragraphs into memory, within the device's limits, and measure what it costs.

    python scripts/large_data.py corpus     # HotpotQA + 2Wiki dev paragraphs -> results/bulk/corpus.jsonl
    python scripts/large_data.py ingest     # streaming, resumable; retrieval quality, speed and RAM as memory grows
    python scripts/large_data.py limits     # the governor stopping at a store cap, a disk reserve, a RAM reserve
    python scripts/large_data.py plan       # this device, probed and calibrated, and the read plan it implies

The questions whose paragraphs are measured are ingested first; every later paragraph is a
distractor, so the curve shows retrieval holding up (or not) as memory grows 30-fold.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/bulk"
CORPUS = OUT / "corpus.jsonl"
QUESTIONS = OUT / "questions.json"
SEED = 7


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1))
    tmp.replace(path)


def _paragraphs(rows, joiner):
    for r in rows:
        for title, sents in r["context"]:
            yield title, joiner.join(s.strip() for s in sents).strip()


def corpus(a) -> None:
    hp = json.load(open(ROOT / "data/hotpotqa/hotpot_dev_distractor_v1.json"))
    tw = json.load(open(ROOT / "data/2wikimultihopqa/dev.json"))
    rng = random.Random(SEED)
    qs = [("hotpotqa", r) for r in rng.sample(hp, a.questions // 2)] + [("2wiki", r) for r in
                                                                         rng.sample(tw, a.questions // 2)]
    seen: set[str] = set()
    n = 0
    OUT.mkdir(parents=True, exist_ok=True)
    with open(CORPUS, "w") as f:
        def emit(title, text):
            nonlocal n
            key = hashlib.sha1(f"{title}\n{text}".encode()).hexdigest()[:16]
            if text and key not in seen:
                seen.add(key)
                f.write(json.dumps({"id": key, "title": title, "text": text}) + "\n")
                n += 1
        for src, r in qs:  # the measured questions' paragraphs first (gold and distractors)
            for title, text in _paragraphs([r], " " if src == "2wiki" else ""):
                emit(title, text)
        first = n
        for title, text in _paragraphs(hp, ""):
            emit(title, text)
        for title, text in _paragraphs(tw, " "):
            emit(title, text)
    items = [{"source": src, "id": r["_id"], "question": r["question"], "answer": r["answer"],
              "gold_titles": sorted({t for t, _ in r["supporting_facts"]})} for src, r in qs]
    save(QUESTIONS, {"seed": SEED, "n": len(items), "paragraphs_first": first, "paragraphs": n, "items": items})
    print(f"{n} unique paragraphs ({first} belong to the {len(items)} measured questions) -> {CORPUS}")


def engine_at(path: Path):
    sys.path.insert(0, str(ROOT / "scripts"))
    import importlib.util

    spec = importlib.util.spec_from_file_location("el", ROOT / "scripts/eager_learning.py")
    el = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(el)
    return el.build_engine(path)


def measure(engine, items: list[dict], k: int = 10, hybrid: bool = True) -> dict:
    """Recall@k of the gold paragraphs' titles, and time per question, from the store as it is now.

    dense: the k nearest vectors only (notes still waiting for a vector are invisible to it);
    hybrid: what recall uses, the vector hits plus the notes the question's words find (BM25), the latter
    embedded on the spot if they are still waiting."""
    from camr.device import process_rss_mb

    out = {}
    modes = (("dense", 0), ("hybrid", 20)) if hybrid else (("dense", 0),)
    for mode, kk in modes:
        hits, full, ms = 0.0, 0, []
        engine.keyword_k = kk
        pending_before = engine.store.pending_count(engine.note_type)
        for it in items:
            t0 = time.perf_counter()
            if mode == "dense":
                qv = engine.embedder.encode_one(it["question"], is_query=True)
                top = [i for i, _ in engine.store.knn(qv, k, engine.note_type)]
            else:
                r = engine.recall(it["question"], touch=False)
                top = [c.note.note_id for c in sorted(r.candidates, key=lambda c: -c.similarity)[:k]]
            ms.append((time.perf_counter() - t0) * 1000)
            titles = set(engine.store.note_titles(top).values())
            got = sum(t in titles for t in it["gold_titles"]) / len(it["gold_titles"])
            hits += got
            full += got == 1.0
        ms.sort()
        out[mode] = {f"recall@{k}": round(hits / len(items), 4), f"all_gold@{k}": round(full / len(items), 4),
                     "ms_median": round(ms[len(ms) // 2], 2), "ms_p95": round(ms[int(0.95 * len(ms))], 2),
                     "embedded_on_demand": pending_before - engine.store.pending_count(engine.note_type)}
    engine.keyword_k = 0
    out["rss_mb"] = round(process_rss_mb(), 1)
    return out


def _state(engine, store, gov) -> dict:
    n = store.count()
    pend = store.pending_count()
    return {"notes": n, "embedded": n - pend, "embedded_share": round((n - pend) / max(1, n), 4),
            "store_mb": round(gov.store_mb(), 1)}


def ingest(a) -> None:
    """Every paragraph in, without vectors (searchable by keyword at once); then the measured questions."""
    from camr.device import Governor, Limits, probe
    from camr.memory.bulk import bulk_ingest, read_jsonl

    store_path = OUT / "store.sqlite"
    ckpt = OUT / "ingest.ckpt"
    path = OUT / "ingest.json"
    if a.fresh:
        for f in OUT.glob("store.sqlite*"):
            f.unlink() if f.is_file() else shutil.rmtree(f)
        ckpt.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
    engine, store = engine_at(store_path)
    q = json.loads(QUESTIONS.read_text())
    out = json.loads(path.read_text()) if path.exists() else {"paragraphs": q["paragraphs"], "runs": [],
                                                              "points": [], "device": probe(OUT).as_dict()}
    gov = Governor(store_path, Limits(reserve_disk_mb=a.reserve_disk_mb, max_store_mb=a.max_store_mb,
                                      reserve_ram_mb=a.reserve_ram_mb))

    def show(rep):
        if rep.documents % 10240 < 512:
            print(f"  {rep.resumed_from + rep.documents} paragraphs, {rep.notes_added} notes, {rep.seconds:.0f}s",
                  flush=True)

    rep = bulk_ingest(engine, read_jsonl(CORPUS, dataset="bulk:hotpot+2wiki"), governor=gov, batch_docs=1024,
                      checkpoint=ckpt, defer_embedding=True, progress=show)
    out["runs"].append({"kind": "ingest (vectors deferred)", **rep.as_dict()})
    print(f"ingested {rep.resumed_from + rep.documents} paragraphs -> {rep.notes_added} notes in {rep.seconds:.0f}s "
          f"({rep.docs_per_s} paragraphs/s); store {rep.store_mb_after} MB; peak RSS {rep.peak_rss_mb} MB; "
          f"pending vectors {rep.pending_vectors}" + (f"; STOPPED: {rep.stopped} ({rep.detail})" if rep.stopped
                                                      else ""), flush=True)
    save(path, out)
    if rep.finished:
        point(a, engine, store, gov, out, path, "right after ingest")


def point(a, engine, store, gov, out, path, label) -> None:
    q = json.loads(QUESTIONS.read_text())
    m = measure(engine, q["items"][: a.measure])
    out["points"].append({"label": label, **_state(engine, store, gov), **m})
    print(json.dumps(out["points"][-1]), flush=True)
    save(path, out)


def drain_part(a) -> None:
    """Give the waiting notes their vectors in the background: polite (yields to other work), resumable."""
    from camr.device import Governor, Limits
    from camr.memory.bulk import drain

    store_path = OUT / "store.sqlite"
    path = OUT / "ingest.json"
    engine, store = engine_at(store_path)
    out = json.loads(path.read_text())
    gov = Governor(store_path, Limits(reserve_disk_mb=a.reserve_disk_mb, reserve_ram_mb=a.reserve_ram_mb,
                                      max_load_per_core=a.max_load))
    marks = [m for m in (0.5,) if m > _state(engine, store, gov)["embedded_share"]]

    def show(rep):
        st = _state(engine, store, gov)
        if rep.embedded % 5120 < 256:
            print(f"  embedded {st['embedded']}/{st['notes']} ({rep.embedded} this run, {rep.seconds:.0f}s, "
                  f"waited {rep.waited_s:.0f}s for the CPU)", flush=True)

    while True:
        target = marks.pop(0) if marks else 1.0
        st = _state(engine, store, gov)
        todo = int(target * st["notes"]) - st["embedded"]
        rep = drain(engine, governor=gov, batch=256, polite=True, progress=show, max_seconds=a.max_seconds,
                    limit=None if target == 1.0 else max(0, todo))
        out["runs"].append({"kind": f"drain to {target:.0%}", **rep.as_dict()})
        save(path, out)
        if rep.stopped:
            print(f"drain stopped: {rep.stopped} ({rep.detail}); {rep.remaining} still waiting", flush=True)
            break
        point(a, engine, store, gov, out, path, f"{_state(engine, store, gov)['embedded_share']:.0%} embedded")
        if target == 1.0 or not rep.embedded:
            break


def scale(a) -> None:
    """With every vector in: retrieval quality and speed as memory grows (the measured questions' paragraphs come
    first, so a smaller memory is a prefix of the larger one), exact search against the learned index."""
    import numpy as np

    from camr.device import process_rss_mb
    from camr.memory.ivf import IVFIndex

    engine, store = engine_at(OUT / "store.sqlite")
    if store.pending_count():
        raise SystemExit(f"{store.pending_count()} notes still wait for vectors: run `drain` first")
    q = json.loads(QUESTIONS.read_text())
    items = q["items"][: a.measure]
    ids, mat = store.all_vectors(engine.note_type)
    unit = mat / np.maximum(np.linalg.norm(mat, axis=1, keepdims=True), 1e-12)
    titles = dict(store.conn.execute("SELECT n.note_id, s.title FROM note n JOIN source s USING(source_id)"))
    qv = engine.embedder.encode([it["question"] for it in items], is_query=True)
    qv = qv / np.linalg.norm(qv, axis=1, keepdims=True)
    first = store.conn.execute("SELECT COUNT(*) FROM note n JOIN source s USING(source_id) WHERE s.source_id <= ?",
                               (q["paragraphs_first"],)).fetchone()[0]
    out = {"notes_total": int(len(ids)), "points": []}

    def score(top_ids) -> tuple[float, float]:
        hit = full = 0.0
        for it, row in zip(items, top_ids):
            got = {titles.get(int(i)) for i in row}
            share = sum(t in got for t in it["gold_titles"]) / len(it["gold_titles"])
            hit += share
            full += share == 1.0
        return round(hit / len(items), 4), round(full / len(items), 4)

    for n in sorted({first, 25_000, 50_000, 100_000, len(ids)}):
        if n > len(ids):
            continue
        sub = unit[:n]
        t0 = time.perf_counter()
        top = np.argsort(-(qv @ sub.T), axis=1)[:, :10]
        ms = (time.perf_counter() - t0) * 1000 / len(items)
        r, f = score(ids[top])
        out["points"].append({"notes": int(n), "search": "exact", "recall@10": r, "all_gold@10": f,
                              "ms_per_question": round(ms, 2), "vectors_mb": round(sub.nbytes / 2**20, 1)})
        print(out["points"][-1], flush=True)
    t0 = time.perf_counter()
    idx = IVFIndex.build(OUT / "scale.ivf", ids, mat, engine.note_type)
    build_s = time.perf_counter() - t0
    for nprobe in (4, 8, 16, 32):
        idx.nprobe = nprobe
        t0 = time.perf_counter()
        top = [[i for i, _ in idx.search(v, 10)] for v in qv]
        ms = (time.perf_counter() - t0) * 1000 / len(items)
        r, f = score(top)
        out["points"].append({"notes": int(len(ids)), "search": f"index nprobe={nprobe}", "recall@10": r,
                              "all_gold@10": f, "ms_per_question": round(ms, 2), "clusters": int(len(idx.centroids)),
                              "build_s": round(build_s, 1), "rss_mb": round(process_rss_mb(), 1)})
        print(out["points"][-1], flush=True)
    shutil.rmtree(OUT / "scale.ivf", ignore_errors=True)
    save(OUT / "scale.json", out)


def limits(a) -> None:
    """Each limit, hit on purpose with the real corpus and the real disk: the job stops, says why, and resumes."""
    from camr.device import Governor, Limits, probe
    from camr.memory.bulk import bulk_ingest, read_jsonl

    work = OUT / "limits"
    shutil.rmtree(work, ignore_errors=True)
    work.mkdir(parents=True)
    store_path, ckpt = work / "store.sqlite", work / "ckpt.json"
    engine, store = engine_at(store_path)
    out = {}

    def run(name, lim, n=6000):
        rep = bulk_ingest(engine, read_jsonl(CORPUS, dataset="bulk:hotpot+2wiki"), governor=Governor(store_path, lim),
                          batch_docs=256, checkpoint=ckpt, limit=n)
        out[name] = {"limits": lim.__dict__, **rep.as_dict(), "notes_in_store": store.count()}
        print(f"{name:28s} consumed {rep.resumed_from}+{rep.documents}; stopped={rep.stopped} {rep.detail}", flush=True)

    run("1 store capped at 8 MB", Limits(max_store_mb=8, reserve_disk_mb=0, reserve_ram_mb=0))
    run("2 cap raised to 16 MB", Limits(max_store_mb=16, reserve_disk_mb=0, reserve_ram_mb=0))
    free = probe(work).disk_free_mb
    run("3 disk reserve: free - 6 MB", Limits(reserve_disk_mb=free - 6, reserve_ram_mb=0))
    avail = probe(work).ram_available_mb
    run("4 RAM reserve above available", Limits(reserve_disk_mb=0, reserve_ram_mb=avail + 512))
    run("5 no limit: the rest", Limits(reserve_disk_mb=500, reserve_ram_mb=256), n=2000)
    n_notes, n_src, n_ck = store.conn.execute(
        "SELECT count(*), count(DISTINCT source_id), count(DISTINCT checksum) FROM note").fetchone()
    consumed = json.loads(ckpt.read_text())["consumed"]
    out["integrity"] = {"documents_consumed": consumed, "notes": n_notes, "distinct_sources": n_src,
                        "distinct_checksums": n_ck, "duplicates": n_notes - n_ck}
    print(out["integrity"])
    save(OUT / "limits.json", out)
    store.close()
    shutil.rmtree(work, ignore_errors=True)


def plan_part(a) -> None:
    from camr.device import Limits, calibrate, plan, probe

    engine, store = engine_at(OUT / "store.sqlite")
    import importlib.util

    spec = importlib.util.spec_from_file_location("el", ROOT / "scripts/eager_learning.py")
    el = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(el)
    prof = calibrate(probe(OUT), embedder=engine.embedder, runner=el.runner_for("qwen2.5:0.5b"))
    out = {"device": prof.as_dict(), "plans": {}}
    for notes in (1_000, store.count() or 100_000, 1_000_000):
        for target in (1500, 4000):
            p = plan(prof, notes=notes, dim=engine.embedder.dim, limits=Limits(latency_target_ms=target))
            out["plans"][f"{notes} notes, {target} ms"] = p.__dict__
            print(f"{notes:>9} notes, target {target} ms -> {p.search}, budget {p.token_budget}, ~{p.expected_ms} ms;"
                  f" room for {p.max_notes_on_disk} more notes", flush=True)
    print(json.dumps({k: v for k, v in prof.as_dict().items() if k != "path"}, indent=1))
    save(OUT / "plan.json", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["corpus", "ingest", "drain", "scale", "limits", "plan"])
    ap.add_argument("--questions", type=int, default=600)
    ap.add_argument("--measure", type=int, default=600)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--reserve-disk-mb", type=float, default=900.0)
    ap.add_argument("--reserve-ram-mb", type=float, default=768.0)
    ap.add_argument("--max-store-mb", type=float, default=None)
    ap.add_argument("--max-seconds", type=float, default=None, help="drain: stop after this long (resumable)")
    ap.add_argument("--max-load", type=float, default=0.5, help="drain: yield while others use this CPU share")
    a = ap.parse_args()
    {"corpus": corpus, "ingest": ingest, "drain": drain_part, "scale": scale, "limits": limits,
     "plan": plan_part}[a.part](a)

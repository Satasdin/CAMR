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


def measure(engine, items: list[dict], k: int = 10) -> dict:
    """Recall@k of the gold paragraphs' titles, and time per question, from the store as it is now."""
    from camr.device import process_rss_mb

    hits, full, ms, search = 0.0, 0, [], []
    for it in items:
        qv = engine.embedder.encode_one(it["question"], is_query=True)
        t0 = time.perf_counter()
        top = engine.store.knn(qv, k, engine.note_type)
        search.append((time.perf_counter() - t0) * 1000)
        titles = set(engine.store.note_titles(i for i, _ in top).values())
        got = sum(t in titles for t in it["gold_titles"]) / len(it["gold_titles"])
        hits += got
        full += got == 1.0
        t0 = time.perf_counter()
        engine.recall(it["question"], touch=False)
        ms.append((time.perf_counter() - t0) * 1000)
    ms.sort()
    search.sort()
    return {f"recall@{k}": round(hits / len(items), 4), f"all_gold@{k}": round(full / len(items), 4),
            "search_ms_median": round(search[len(search) // 2], 2), "recall_ms_median": round(ms[len(ms) // 2], 2),
            "recall_ms_p95": round(ms[int(0.95 * len(ms))], 2), "rss_mb": round(process_rss_mb(), 1)}


def ingest(a) -> None:
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
    items = q["items"][: a.measure]
    out = json.loads(path.read_text()) if path.exists() else {"paragraphs": q["paragraphs"], "points": [],
                                                              "runs": [], "device": probe(OUT).as_dict()}
    gov = Governor(store_path, Limits(reserve_disk_mb=a.reserve_disk_mb, max_store_mb=a.max_store_mb,
                                      reserve_ram_mb=a.reserve_ram_mb))
    marks = [m for m in (q["paragraphs_first"], 10_000, 25_000, 50_000, 100_000, 150_000) if m < q["paragraphs"]]
    done = json.loads(ckpt.read_text())["consumed"] if ckpt.exists() else 0
    measured = {p["documents"] for p in out["points"]}
    for target in marks + [q["paragraphs"]]:
        if target <= done:
            continue
        rep = bulk_ingest(engine, read_jsonl(CORPUS, dataset="bulk:hotpot+2wiki"), governor=gov, batch_docs=512,
                          checkpoint=ckpt, limit=target - done)
        done = rep.resumed_from + rep.documents
        out["runs"].append(rep.as_dict())
        print(f"ingested to {done}: {rep.notes_added} notes in {rep.seconds:.0f}s ({rep.docs_per_s} docs/s; embedding "
              f"{rep.embed_seconds:.0f}s) store {rep.store_mb_after} MB, peak RSS {rep.peak_rss_mb} MB"
              + (f"; STOPPED: {rep.stopped} ({rep.detail})" if rep.stopped else ""), flush=True)
        if done not in measured:
            m = measure(engine, items)
            out["points"].append({"documents": done, "notes": store.count(), "store_mb": round(gov.store_mb(), 1), **m})
            print("  ", out["points"][-1], flush=True)
        save(path, out)
        if rep.stopped:
            break
    save(path, out)


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
    ap.add_argument("part", choices=["corpus", "ingest", "limits", "plan"])
    ap.add_argument("--questions", type=int, default=600)
    ap.add_argument("--measure", type=int, default=600)
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--reserve-disk-mb", type=float, default=900.0)
    ap.add_argument("--reserve-ram-mb", type=float, default=768.0)
    ap.add_argument("--max-store-mb", type=float, default=None)
    a = ap.parse_args()
    {"corpus": corpus, "ingest": ingest, "limits": limits, "plan": plan_part}[a.part](a)

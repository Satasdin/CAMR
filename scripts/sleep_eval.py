"""What sleep buys: a learned index (speed and memory as memory grows) and a learned query adapter.

index    The 38,054-note store of the retrieval evaluation (HotpotQA + 2WikiMultiHopQA paragraphs,
         BGE-small vectors) and its 1,000 real questions with gold supporting titles. Exact search
         against the IVF index at several nprobe: time per question, agreement with exact search,
         and full-support recall. Then the store is grown to 150k and 400k notes with perturbed
         copies of its own vectors (distractors only; the gold notes are the real ones), and each
         size is searched in a fresh process so its resident memory can be measured.
adapter  Learning to fetch: train the query adapter on half of the HotpotQA questions (question →
         its gold paragraphs) and measure recall on the other half, which it never saw.
eager    After the learning stream: the adapter trained on the stream's own questions (what the
         engine actually experienced), tested on the reworded questions of pass 2.

    python scripts/sleep_eval.py index|adapter|eager
"""

from __future__ import annotations

import argparse
import json
import statistics
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/sleep"
STORE = ROOT / "results/retrieval_eval/camr.sqlite"


def unit(x):
    return x / np.maximum(np.linalg.norm(x, axis=-1, keepdims=True), 1e-12)


def load_store():
    import sqlite3

    c = sqlite3.connect(f"file:{STORE}?mode=ro", uri=True)
    rows = c.execute("SELECT n.note_id, e.embedding, s.title FROM note n JOIN note_embedding e USING(note_id)"
                     " JOIN source s USING(source_id) WHERE n.note_type='verbatim' ORDER BY n.note_id").fetchall()
    ids = np.array([r[0] for r in rows])
    mat = unit(np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows]))
    titles = [" ".join((r[2] or "").split()) for r in rows]
    return ids, mat.astype(np.float32), titles


def questions():
    from camr.config import Config
    from camr.harness.experiment import Workspace

    cfg = Config.load(ROOT / "configs/retrieval_eval.yaml")
    ws = Workspace(cfg, run_dir=ROOT / "results/retrieval_eval")
    out = []
    for bench in ("hotpotqa", "2wikimultihopqa"):
        out += [(bench, q.question, {" ".join(t.split()) for t in q.support}) for q in ws.sample(bench) if q.support]
    return cfg, out


def embed_queries(cfg, qs):
    cache = OUT / "query_vectors.npy"
    if cache.exists():
        return np.load(cache)
    from camr.memory.embedder import build_embedder

    emb = build_embedder(cfg.embedder)
    v = unit(np.asarray(emb.encode([q for _, q, _ in qs], is_query=True), dtype=np.float32))
    OUT.mkdir(parents=True, exist_ok=True)
    np.save(cache, v)
    return v


def support_metrics(top_ids, id_title, gold):
    got = {id_title[i] for i in top_ids}
    return float(gold <= got), float(bool(gold & got))


# ------------------------------------------------------------------ index
def index(a) -> None:
    from camr.memory.ivf import IVFIndex

    ids, mat, titles = load_store()
    id_title = dict(zip(ids.tolist(), titles))
    cfg, qs = questions()
    qv = embed_queries(cfg, qs)
    k = 20
    res = {"notes": int(len(ids)), "questions": len(qs), "k": k, "real": {}, "scale": []}
    t = []
    exact_top = []
    for q in qv:
        t0 = time.perf_counter()
        top = ids[np.argpartition(-(mat @ q), k)[:k]]
        t.append((time.perf_counter() - t0) * 1000)
        exact_top.append(set(top.tolist()))
    full = [support_metrics(e, id_title, g)[0] for e, (_, _, g) in zip(exact_top, qs)]
    res["real"]["exact"] = {"ms": statistics.median(t), "full_support_recall": statistics.mean(full)}
    with tempfile.TemporaryDirectory() as tmp:
        t0 = time.perf_counter()
        idx = IVFIndex.build(Path(tmp) / "ivf", ids, mat, "verbatim")
        res["real"]["build_s"] = time.perf_counter() - t0
        res["real"]["clusters"] = int(len(idx.centroids))
        for nprobe in (4, 8, 16, 32):
            t, agree, full = [], [], []
            for q, e, (_, _, g) in zip(qv, exact_top, qs):
                t0 = time.perf_counter()
                got = {i for i, _ in idx.search(q, k, nprobe=nprobe)}
                t.append((time.perf_counter() - t0) * 1000)
                agree.append(len(got & e) / k)
                full.append(support_metrics(got, id_title, g)[0])
            res["real"][f"ivf_nprobe_{nprobe}"] = {"ms": statistics.median(t), "agreement_with_exact": statistics.mean(
                agree), "full_support_recall": statistics.mean(full), "share_of_memory_read": float(
                    np.mean([nprobe / len(idx.centroids)]))}
            print("nprobe", nprobe, res["real"][f"ivf_nprobe_{nprobe}"], flush=True)
    print("exact", res["real"]["exact"], flush=True)
    for n in a.sizes:
        for mode in ("exact", "ivf"):
            r = subprocess.run([sys.executable, __file__, "_scale", "--n", str(n), "--mode", mode],
                               capture_output=True, text=True, timeout=7200)
            row = json.loads(r.stdout.strip().splitlines()[-1])
            res["scale"].append(row)
            print(row, flush=True)
            OUT.mkdir(parents=True, exist_ok=True)
            (OUT / "index.json").write_text(json.dumps(res, indent=1))
    (OUT / "index.json").write_text(json.dumps(res, indent=1))


def _scale(a) -> None:
    """One store size, one search mode, in a fresh process: time per question and resident memory."""
    from camr.memory.ivf import IVFIndex

    def rss():
        with open("/proc/self/status") as f:
            d = dict(line.split(":", 1) for line in f)
        return int(d["VmRSS"].split()[0]) / 1024, int(d["VmHWM"].split()[0]) / 1024

    ids, mat, titles = load_store()
    id_title = dict(zip(ids.tolist(), titles))
    cfg, qs = questions()
    qv = embed_queries(cfg, qs)
    rng = np.random.default_rng(13)
    n_real = len(ids)
    copies = []
    while n_real + sum(len(c) for c in copies) < a.n:  # distractors: perturbed copies of real notes
        m = min(n_real, a.n - n_real - sum(len(c) for c in copies))
        copies.append(unit(mat[rng.choice(n_real, m, replace=False)] + rng.normal(0, 0.06, (m, mat.shape[1]))).astype(
            np.float32))
    big = np.vstack([mat, *copies]) if copies else mat
    big_ids = np.arange(1, len(big) + 1)
    real_ids = dict(zip(big_ids[:n_real].tolist(), ids.tolist()))
    k = 20
    tmp = Path(tempfile.mkdtemp(dir=OUT))
    if a.mode == "ivf":
        t0 = time.perf_counter()
        IVFIndex.build(tmp / "ivf", big_ids, big, "verbatim")
        build = time.perf_counter() - t0
        del big, copies, mat  # the built index lives on disk; search from a fresh mapping
        import gc

        gc.collect()
        base = rss()[0]
        idx = IVFIndex.load(tmp / "ivf")
    else:
        build, base = 0.0, rss()[0]
    t, full = [], []
    for q, (_, _, g) in zip(qv, qs):
        t0 = time.perf_counter()
        if a.mode == "ivf":
            got = [i for i, _ in idx.search(q, k)]
        else:
            got = big_ids[np.argpartition(-(big @ q), k)[:k]].tolist()
        t.append((time.perf_counter() - t0) * 1000)
        full.append(support_metrics({real_ids[i] for i in got if i in real_ids}, id_title, g)[0])
    cur, peak = rss()
    import shutil

    shutil.rmtree(tmp, ignore_errors=True)
    print(json.dumps({"notes": a.n, "mode": a.mode, "ms": statistics.median(t), "p95_ms": float(np.percentile(t, 95)),
                      "full_support_recall": statistics.mean(full), "rss_mb_after_queries": round(cur, 1),
                      "rss_growth_mb_from_queries": round(cur - base, 1) if a.mode == "ivf" else None,
                      "vectors_mb": round(a.n * 384 * 4 / 1e6, 1), "build_s": round(build, 1)}))


# ------------------------------------------------------------------ adapter
def adapter(a) -> None:
    from camr.memory.adapter import QueryAdapter, recall_at

    ids, mat, titles = load_store()
    by_title: dict[str, set[int]] = {}
    for i, t in zip(ids.tolist(), titles):
        by_title.setdefault(t, set()).add(i)
    cfg, qs = questions()
    qv = embed_queries(cfg, qs)
    out = {}
    pos = {int(i): j for j, i in enumerate(ids)}

    def pairs_of(rows):
        Q, P, H = [], [], []
        for v, gold in rows:
            top = np.argsort(-(mat @ v))[:16]
            hard = [mat[j] for j in top if int(ids[j]) not in gold][:4]
            while len(hard) < 4:  # pad with random notes when the gold fills the top
                hard.append(mat[rng.integers(len(mat))])
            for gid in gold:
                Q.append(v)
                P.append(mat[pos[gid]])
                H.append(np.vstack(hard))
        return np.vstack(Q), np.vstack(P), np.stack(H)

    for bench in ("hotpotqa", "2wikimultihopqa"):
        rows = [(v, set().union(*(by_title.get(t, set()) for t in g))) for v, (b, _, g) in zip(qv, qs) if b == bench]
        rows = [r for r in rows if r[1]]
        rng = np.random.default_rng(13)
        order = rng.permutation(len(rows))
        tr, te = [rows[i] for i in order[: len(rows) // 2]], [rows[i] for i in order[len(rows) // 2:]]
        inner = int(0.8 * len(tr))  # the epoch is chosen on a validation part of the TRAINING half only
        fit_rows, val_rows = tr[:inner], tr[inner:]
        Q, P, H = pairs_of(fit_rows)
        test_q, test_g = np.vstack([v for v, _ in te]), [g for _, g in te]
        val_q, val_g = np.vstack([v for v, _ in val_rows]), [g for _, g in val_rows]
        before = recall_at(test_q, test_g, ids, mat)
        res = {"train_questions": len(fit_rows), "validation_questions": len(val_rows), "test_questions": len(te),
               "train_pairs": len(Q), "recall_before": before, "validation_before": recall_at(val_q, val_g, ids, mat)}
        for rank in (16, 64):
            ad = QueryAdapter.identity(mat.shape[1], rank=rank)
            best = {"score": (res["validation_before"]["recall@1"], res["validation_before"]["recall@5"]), "epoch": 0,
                    "U": ad.U.copy(), "V": ad.V.copy()}

            def keep_best(epoch, a_, best=best):
                r = recall_at(val_q, val_g, ids, mat, adapter=a_)
                if (r["recall@1"], r["recall@5"]) > best["score"]:
                    best.update(score=(r["recall@1"], r["recall@5"]), epoch=epoch, U=a_.U.copy(), V=a_.V.copy())

            t0 = time.perf_counter()
            losses = ad.fit(Q, P, H, epochs=40, on_epoch=keep_best)
            final = recall_at(test_q, test_g, ids, mat, adapter=ad)
            chosen = QueryAdapter(U=best["U"], V=best["V"])
            res[f"rank_{rank}"] = {"recall_after_40_epochs": final,
                                   "best_epoch_on_validation": best["epoch"],
                                   "recall_after_best_epoch": recall_at(test_q, test_g, ids, mat, adapter=chosen),
                                   "train_s": round(time.perf_counter() - t0, 1), "loss_first": losses[0],
                                   "loss_last": losses[-1], "parameters": int(ad.U.size + ad.V.size)}
        out[bench] = res
        print(bench, json.dumps(res, default=float), flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "adapter.json").write_text(json.dumps(out, indent=1, default=float))


# ------------------------------------------------------------------ eager
def eager(a) -> None:
    """Sleep on what the learning stream taught: adapter from pass-1 questions, tested on pass-2 rewordings."""
    import shutil

    sys.path.insert(0, str(ROOT / "scripts"))
    import eager_learning as E

    from camr.eval.scoring import normalize_answer
    from camr.memory.adapter import recall_at
    from camr.memory.sleep import sleep

    items = {x["i"]: x for x in E.load_stream()}
    tmp = OUT / "eager_store.sqlite"
    shutil.copy2(E.OUT / "store.sqlite", tmp)
    engine, store = E.build_engine(tmp)
    ids, mat = store.all_vectors(engine.note_type)
    texts = store.get_notes(ids.tolist())
    gold_notes = {}
    for i, it in items.items():
        g = {nid for nid, n in texts.items() if any(f" {normalize_answer(x)} " in f" {normalize_answer(n.text)} "
                                                       for x in it["answers"]) and any(
            w in n.text.lower() for w in it["subj"].lower().split()[:2])}
        if g:
            gold_notes[i] = g
    keys = sorted(gold_notes)
    rng = np.random.default_rng(13)
    rng.shuffle(keys)
    cut = int(0.8 * len(keys))
    train_keys, test_keys = keys[:cut], keys[cut:]
    pairs = [(items[i]["question"], gold_notes[i]) for i in train_keys]
    qv = {q: v for q, v in zip(
        [items[i][f] for i in keys for f in ("question", "paraphrase")],
        engine.embedder.encode([items[i][f] for i in keys for f in ("question", "paraphrase")], is_query=True))}

    def rec(keyset, field, ad=None):
        return recall_at(np.vstack([qv[items[i][field]] for i in keyset]), [gold_notes[i] for i in keyset], ids, mat,
                         adapter=ad)

    before = {"seen_reworded": rec(train_keys, "paraphrase"), "unseen_reworded": rec(test_keys, "paraphrase")}
    rep = sleep(engine, pairs=pairs, adapter_path=OUT / "eager_adapter.npz", index_min_notes=a.index_min)
    ad = engine.query_adapter
    after = {"seen_reworded": rec(train_keys, "paraphrase", ad), "unseen_reworded": rec(test_keys, "paraphrase", ad)}
    out = {"questions_with_gold_in_memory": len(keys), "train": len(train_keys), "test": len(test_keys),
           "before": before, "after": after, "adapter_kept": ad is not None, "sleep_report": rep}
    (OUT / "eager.json").write_text(json.dumps(out, indent=1, default=float))
    print(json.dumps(out, indent=1, default=float))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["index", "adapter", "eager", "_scale"])
    ap.add_argument("--sizes", type=int, nargs="*", default=[38054, 150000, 400000])
    ap.add_argument("--n", type=int)
    ap.add_argument("--mode")
    ap.add_argument("--index-min", type=int, default=2000)
    a = ap.parse_args()
    {"index": index, "_scale": _scale, "adapter": adapter, "eager": eager}[a.part](a)

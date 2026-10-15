"""Modern RAG pipelines against CAMR: same corpus, same chunks, same readers, same scoring.

Corpus: every page the frozen lookups read for the development, test and held-out PopQA sets (lead text and one
note per infobox fact, as CAMR stores them): one store, built once, searched by every pipeline. Questions: the 200
held-out questions, on which nothing was chosen. Thresholds (abstention, corrective RAG) are chosen on the
development questions only (`tune`).

Pipelines (all read the same notes; k = 5 passages unless stated):
  dense     naive RAG, retrieve-then-read (Lewis et al., 2020): top 5 by cosine similarity
  bm25      top 5 by BM25 (SQLite FTS5)
  hybrid    dense top 20 and BM25 top 20 fused by reciprocal rank (Cormack et al., 2009; k = 60), top 5
  rerank    hybrid top 20 rescored by a cross-encoder (ms-marco-MiniLM-L-6-v2; Nogueira & Cho, 2019), top 5
  hyde      the reader writes a hypothetical passage; its embedding retrieves the top 5 (Gao et al., 2022)
  crag      corrective RAG (Yan et al., 2024): the cross-encoder grades retrieval; correct -> keep the relevant
            sentences of the passages; incorrect -> search the web (the frozen lookup) instead; ambiguous -> both
  abstain   rerank, and answer only when the best cross-encoder score clears a threshold (otherwise decline)
  check     rerank, then CAMR's verification check on the answer: stated only if the passages support it
  camr      CAMR's verified pipeline on the same store (fact reader, compression, check); no web
Reader prompt for the RAG pipelines: LangChain's standard RAG prompt (hub: rlm/rag-prompt).

    python scripts/rag_bench.py corpus
    python scripts/rag_bench.py tune
    python scripts/rag_bench.py run --pipelines dense,bm25,... --reader qwen2.5:0.5b
    python scripts/rag_bench.py judge
    python scripts/rag_bench.py report
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/ragbench"
VERIFIED = ROOT / "results/verified"
K, POOL, RRF_K = 5, 20, 60
CE_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"
RAG_PROMPT = ("You are an assistant for question-answering tasks. Use the following pieces of retrieved context to "
              "answer the question. If you don't know the answer, just say that you don't know. Use three sentences "
              "maximum and keep the answer concise.\nQuestion: {question} \nContext: {context} \nAnswer:")
HYDE_PROMPT = "Write a short encyclopedia passage that answers the question.\n\nQuestion: {question}\nPassage:"
PIPELINES = ["dense", "bm25", "hybrid", "rerank", "hyde", "crag", "abstain", "check", "camr"]


def _load(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod


vq = _load("verified_qa", ROOT / "scripts/verified_qa.py")


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


def rss_mb() -> float:
    try:
        for line in open(f"/proc/{os.getpid()}/status"):
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    except OSError:
        pass
    return 0.0


def lookup_for(set_name: str, embedder):
    from camr.memory.fetch import WebLookup, embedding_rank

    return WebLookup(cache_path=VERIFIED / f"web_cache_{set_name}.sqlite", patient_s=0, offline=True,
                     rank=embedding_rank(embedder), min_interval_s=0, facts=True)


def open_store(path: Path):
    engine, store = vq.build_engine(path, 128)
    return engine, store


# ---------------------------------------------------------------------- the corpus
def corpus(a) -> None:
    """Every page the frozen lookups read for the three question sets, stored once as CAMR stores them."""
    from camr.memory.eager import learn_meanings, page_documents

    path = OUT / "corpus.sqlite"
    for f in path.parent.glob(path.name + "*"):
        f.unlink()
    engine, store = open_store(path)
    pages, meanings, per_set = {}, {}, {}
    t0 = time.perf_counter()
    for s in ("dev", "test", "heldout"):
        lookup = lookup_for(s, engine.embedder)
        n0 = len(pages)
        for it in vq.load_set(s):
            found = lookup.lookup(it["question"], max_pages=3)
            for p in found.pages:
                pages.setdefault(p.url, p)
            meanings.update(found.meanings)
        per_set[s] = len(pages) - n0
    t_lookup = time.perf_counter() - t0
    docs = [d for p in pages.values() for d in page_documents(p)]
    t1 = time.perf_counter()
    rep = engine.ingest(docs)
    learn_meanings(engine, meanings)
    t_ingest = time.perf_counter() - t1
    # what building the dense index costs from scratch (the shared vector cache hides it): embed a sample
    sample = [n.text for n in store.get_notes(range(1, 401)).values()]
    raw = engine.embedder.inner if hasattr(engine.embedder, "inner") else engine.embedder
    t2 = time.perf_counter()
    raw.encode(sample)
    per_note = (time.perf_counter() - t2) / max(1, len(sample))
    out = {"pages": len(pages), "new_pages_by_set": per_set, "documents": len(docs), "notes": store.count(),
           "accepted": rep.accepted, "store_mb": round(path.stat().st_size / 1e6, 2),
           "lookup_s": round(t_lookup, 1), "ingest_s": round(t_ingest, 1),
           "embed_ms_per_note_from_scratch": round(per_note * 1000, 2),
           "dense_index_s_from_scratch": round(per_note * store.count(), 1), "meanings": len(meanings)}
    store.close()
    save(OUT / "corpus.json", out)
    print(json.dumps(out, indent=1))


# ---------------------------------------------------------------------- retrieval
class Retriever:
    def __init__(self, engine, store, ce=None):
        self.engine, self.store, self.ce = engine, store, ce
        self.nt = engine.note_type

    def notes(self, ids):
        got = self.store.get_notes(ids)
        return [got[i] for i in ids if i in got]

    def dense(self, text: str, k: int, is_query: bool = True):
        vec = self.engine.embedder.encode_one(text, is_query=is_query)
        return [i for i, _ in self.store.knn(vec, k, self.nt)]

    def bm25(self, text: str, k: int):
        return [i for i, _ in self.store.keyword(text, k, self.nt)]

    def hybrid(self, text: str, k: int):
        score: dict[int, float] = {}
        for ranked in (self.dense(text, POOL), self.bm25(text, POOL)):
            for r, i in enumerate(ranked):
                score[i] = score.get(i, 0.0) + 1.0 / (RRF_K + r + 1)
        return [i for i, _ in sorted(score.items(), key=lambda x: (-x[1], x[0]))][:k]

    def ce_scores(self, question: str, texts: list[str]) -> list[float]:
        if not texts:
            return []
        return [float(x) for x in self.ce.predict([(question, t) for t in texts], batch_size=32)]

    def rerank(self, question: str, k: int):
        ids = self.hybrid(question, POOL)
        notes = self.notes(ids)
        sc = self.ce_scores(question, [n.text for n in notes])
        order = sorted(range(len(notes)), key=lambda j: (-sc[j], notes[j].note_id))[:k]
        return [notes[j] for j in order], [sc[j] for j in order]


def context_of(texts: list[str]) -> str:
    return "\n".join(f"- {t}" for t in texts)


# ---------------------------------------------------------------------- thresholds, chosen on the development set
def tune(a) -> None:
    """The best cross-encoder score over the hybrid pool, against whether the top 5 hold the answer, on the 200
    development questions: the abstention threshold maximises Youden's J; corrective RAG's 'correct' bound is the
    lowest score above which the answer is in the passages for at least 80% of questions, its 'incorrect' bound the
    highest score below which it is for at most 20%."""
    from sentence_transformers import CrossEncoder

    engine, store = open_store(OUT / "corpus.sqlite")
    rt = Retriever(engine, store, CrossEncoder(CE_MODEL, device="cpu"))
    rows = []
    for it in vq.load_set("dev"):
        notes, sc = rt.rerank(it["question"], K)
        rows.append((max(sc) if sc else -99.0, vq.contains(" ".join(n.text for n in notes), it["answers"])))
    pos = sum(h for _, h in rows) or 1
    neg = sum(not h for _, h in rows) or 1
    cands = sorted({round(s, 2) for s, _ in rows})
    best = max(cands, key=lambda t: sum(h for s, h in rows if s >= t) / pos - sum(not h for s, h in rows if s >= t) / neg)
    upper = next((t for t in cands if (lambda sel: sel and sum(sel) / len(sel) >= 0.8)([h for s, h in rows if s >= t])),
                 cands[-1])
    lower = max((t for t in cands if (lambda sel: sel and sum(sel) / len(sel) <= 0.2)([h for s, h in rows if s < t])),
                default=cands[0])
    out = {"n": len(rows), "answer_in_top5": round(pos / len(rows), 4), "abstain_threshold": best,
           "crag_upper": upper, "crag_lower": min(lower, upper)}
    save(OUT / "thresholds.json", out)
    print(out)
    store.close()


# ---------------------------------------------------------------------- answering
def reader_for(name: str, offline: bool):
    from camr.models.runner import CachedRunner, OllamaRunner

    if offline and name.startswith("kimi"):
        from camr.config import Config
        from camr.models.runner import ReplayOnlyRunner

        return CachedRunner(ReplayOnlyRunner(Config.load(ROOT / "results/learn/config.yaml").ceiling_model),
                            OUT / "answers.sqlite", offline=True)
    r = vq._eager().runner_for(name)
    if isinstance(r, OllamaRunner):
        r.logprobs = False
    return CachedRunner(r, OUT / "answers.sqlite", offline=offline)


class Metered:
    """A reader that counts what a question cost: model calls, prompt and generated tokens, model time (as the
    model reported it when first asked; a cached answer keeps its original timing)."""

    def __init__(self, runner):
        self.runner = runner
        self.model_name = runner.model_name
        self.reset()

    def reset(self) -> None:
        self.calls, self.prompt_tokens, self.gen_tokens, self.model_ms = 0, 0, 0, 0.0

    def generate(self, prompt: str):
        g = self.runner.generate(prompt)
        self.calls += 1
        self.prompt_tokens += g.prompt_tokens or 0
        self.gen_tokens += g.generated_tokens or 0
        self.model_ms += g.latency_ms or 0.0
        return g

    def __call__(self, prompt: str) -> str:
        return self.generate(prompt).text.strip()

    def __getattr__(self, name):
        return getattr(self.runner, name)


def run_pipeline(name: str, it: dict, rt: Retriever, call: Metered, th: dict, lookup) -> dict:
    """One question through one pipeline: the context it read, its answer, and whether it states the answer."""
    from camr.memory.eager import page_documents
    from camr.memory.verify import abstention_like, check, sentences, units_from_notes

    q = it["question"]
    stated, extra = True, {}
    if name == "dense":
        texts = [n.text for n in rt.notes(rt.dense(q, K))]
    elif name == "bm25":
        texts = [n.text for n in rt.notes(rt.bm25(q, K))]
    elif name == "hybrid":
        texts = [n.text for n in rt.notes(rt.hybrid(q, K))]
    elif name in ("rerank", "abstain", "check"):
        notes, sc = rt.rerank(q, K)
        texts = [n.text for n in notes]
        extra["top_score"] = round(max(sc), 3) if sc else None
        if name == "abstain" and (not sc or max(sc) < th["abstain_threshold"]):
            return {"context": context_of(texts), "answer": "I don't know.", "stated": False, **extra}
    elif name == "hyde":
        passage = call(HYDE_PROMPT.format(question=q))
        texts = [n.text for n in rt.notes(rt.dense(passage or q, K, is_query=False))]
        extra["hyde_passage"] = passage[:300]
    elif name == "crag":
        notes, sc = rt.rerank(q, K)
        best = max(sc) if sc else -99.0
        action = "correct" if best >= th["crag_upper"] else "incorrect" if best < th["crag_lower"] else "ambiguous"
        internal = [s for n in notes for s in sentences(n.text)]
        web = []
        if action != "correct":
            found = lookup.lookup(q, max_pages=3)
            web = [s for p in found.pages for d in page_documents(p) for s in sentences(d.text)]
        pool = (internal if action != "incorrect" else []) + web
        ssc = rt.ce_scores(q, pool)
        keep = [pool[j] for j in sorted(range(len(pool)), key=lambda j: -ssc[j])[:8]]  # knowledge refinement
        texts = keep
        extra.update(crag_action=action, top_score=round(best, 3))
    else:
        raise ValueError(name)
    ctx = context_of(texts)
    answer = call(RAG_PROMPT.format(question=q, context=ctx))
    plain = answer.replace("\u2019", "'").replace("\u2018", "'")  # curly apostrophes decline too (D-38)
    if abstention_like(plain) or re.search(r"\b(?:don'?t|do not|cannot|can't) (?:know|find|determine)\b|not "
                                            r"(?:mentioned|provided|specified|stated|contain)", plain, re.I):
        stated = False
    if name == "check" and stated:
        notes_by_text = {n.text: n for n in notes}
        units = units_from_notes(rt.store, [notes_by_text[t] for t in texts if t in notes_by_text])
        v = check(q, answer, units, typed=True, relation_cue=True)
        stated = v.supported
        extra["check"] = v.reason
    return {"context": ctx, "answer": answer, "stated": stated, **extra}


def run(a) -> None:
    from sentence_transformers import CrossEncoder

    from camr.memory.answer import READ, VerifiedAnswerer

    engine, store = open_store(OUT / "corpus.sqlite")
    t0 = time.perf_counter()
    ce = CrossEncoder(CE_MODEL, device="cpu")
    ce_load = time.perf_counter() - t0
    rt = Retriever(engine, store, ce)
    th = json.loads((OUT / "thresholds.json").read_text())
    lookup = lookup_for("heldout", engine.embedder)
    items = vq.load_set("heldout")[: a.n]
    reader = Metered(reader_for(a.reader, a.offline_answers))
    tag = a.reader.replace(":", "_").replace(".", "_")
    for name in a.pipelines.split(","):
        rows, t_run = [], time.perf_counter()
        camr = None
        if name == "camr":
            camr = VerifiedAnswerer(engine, [reader], lookup=None, budget=128, fact_reader=True, compressed=True,
                                    typed=True, relation_cue=True, closed_book=True, template=READ)
        for it in items:
            reader.reset()
            call = reader
            c0, p0 = time.perf_counter(), time.process_time()
            if camr is not None:
                r = camr.answer(it["question"], allow_web=False)
                lead = r.attempts[0].answer if r.attempts else ""
                res = {"context": r.context, "answer": r.claim if r.status == "verified" else lead,
                       "stated": r.status == "verified", "by": r.by, "ambiguous": bool(r.ambiguous)}
            else:
                res = run_pipeline(name, it, rt, call, th, lookup)
            wall = (time.perf_counter() - c0) * 1000
            cpu = (time.process_time() - p0) * 1000
            ans = res["answer"]
            rows.append({"i": it["i"], "question": it["question"], **{k: v for k, v in res.items() if k != "context"},
                         "answer": ans[:300], "exact": vq.contains(ans, it["answers"]) if ans else False,
                         "gold_in_context": vq.contains(res["context"], it["answers"]),
                         "context_tokens": len(res["context"].split()), "calls": call.calls,
                         "prompt_tokens": call.prompt_tokens, "gen_tokens": call.gen_tokens,
                         "model_ms": round(call.model_ms, 1), "wall_ms": round(wall, 1), "cpu_ms": round(cpu, 1)})
        n = len(rows)
        out = {"pipeline": name, "reader": a.reader, "n": n, "thresholds": th, "ce_load_s": round(ce_load, 2),
               "rss_mb": round(rss_mb(), 1), "seconds": round(time.perf_counter() - t_run, 1),
               "summary": summarise(rows), "per_question": rows}
        save(OUT / f"run_{name}_{tag}.json", out)
        s = out["summary"]
        print(f"{name:8s} {a.reader:14s} stated-correct {s['correct_exact']:.3f} stated-wrong {s['wrong_exact']:.3f} "
              f"declined {s['declined']:.3f} gold-in-context {s['gold_in_context']:.3f} calls {s['calls']:.2f} "
              f"prompt-tok {s['prompt_tokens']:.0f} model {s['model_s']:.2f}s cpu {s['cpu_ms']:.0f}ms", flush=True)
    store.close()


def summarise(rows: list[dict], judged: dict | None = None) -> dict:
    n = len(rows) or 1
    ok = (lambda r: judged.get(r["i"], r["exact"])) if judged is not None else (lambda r: r["exact"])
    stated = [r for r in rows if r["stated"]]
    return {"correct_exact": sum(r["stated"] and ok(r) for r in rows) / n,
            "wrong_exact": sum(r["stated"] and not ok(r) for r in rows) / n,
            "declined": sum(not r["stated"] for r in rows) / n,
            "precision": sum(ok(r) for r in stated) / max(1, len(stated)),
            "unchecked_correct": sum(ok(r) for r in rows) / n,
            "gold_in_context": sum(r["gold_in_context"] for r in rows) / n,
            "calls": statistics.mean(r["calls"] for r in rows), "prompt_tokens": statistics.mean(r["prompt_tokens"]
                                                                                                for r in rows),
            "gen_tokens": statistics.mean(r["gen_tokens"] for r in rows),
            "context_words": statistics.mean(r["context_tokens"] for r in rows),
            "model_s": statistics.mean(r["model_ms"] for r in rows) / 1000,
            "wall_ms_median": statistics.median(r["wall_ms"] for r in rows),
            "cpu_ms": statistics.mean(r["cpu_ms"] for r in rows)}


# ---------------------------------------------------------------------- judging and the report
def judge(a) -> None:
    """Every answer that exact matching marks wrong, judged by Kimi K3 (cached); the summary is recomputed with the
    judged verdicts (`summary_judged`)."""
    from camr.memory.verify import abstention_like

    runner = vq._judge_runner(a.judge)
    gold = {it["i"]: it for it in vq.load_set("heldout")}
    for f in sorted(OUT.glob("run_*.json")):
        d = json.loads(f.read_text())
        verdicts = {}
        for r in d["per_question"]:
            ans = r["answer"]
            if r["exact"]:
                verdicts[r["i"]] = True
            elif abstention_like(ans):  # a decline is never a correct answer; no need to ask
                verdicts[r["i"]] = False
            else:
                verdicts[r["i"]] = vq.judged(runner, gold[r["i"]]["question"], gold[r["i"]]["answers"], ans)
        d["summary_judged"] = summarise(d["per_question"], verdicts)
        d["judged"] = {str(k): v for k, v in verdicts.items()}
        save(f, d)
        s = d["summary_judged"]
        print(f"{d['pipeline']:8s} {d['reader']:14s} correct {s['correct_exact']:.3f} wrong stated "
              f"{s['wrong_exact']:.3f} declined {s['declined']:.3f}", flush=True)
    print(f"judge calls: {runner.misses} new, {runner.hits} cached")


def report(a) -> None:
    rows = []
    for f in sorted(OUT.glob("run_*.json")):
        d = json.loads(f.read_text())
        s = d.get("summary_judged") or d["summary"]
        rows.append((d["reader"], PIPELINES.index(d["pipeline"]) if d["pipeline"] in PIPELINES else 99, d, s))
    for reader, _, d, s in sorted(rows, key=lambda x: (x[0], x[1])):
        print(f"{reader:14s} {d['pipeline']:8s} correct {100 * s['correct_exact']:5.1f}  wrong-stated "
              f"{100 * s['wrong_exact']:5.1f}  declined {100 * s['declined']:5.1f}  gold-in-ctx "
              f"{100 * s['gold_in_context']:5.1f}  calls {s['calls']:.2f}  prompt {s['prompt_tokens']:6.0f} tok  "
              f"model {s['model_s']:5.2f}s  retrieval-cpu {s['cpu_ms']:6.0f} ms")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["corpus", "tune", "run", "judge", "report"])
    ap.add_argument("--pipelines", default=",".join(PIPELINES))
    ap.add_argument("--reader", default="qwen2.5:0.5b")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--judge", default="kimi-k3")
    ap.add_argument("--offline-answers", action="store_true")
    a = ap.parse_args()
    {"corpus": corpus, "tune": tune, "run": run, "judge": judge, "report": report}[a.part](a)

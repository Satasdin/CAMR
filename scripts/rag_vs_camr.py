"""CAMR against standard retrieval-augmented generation (RAG), head to head.

Standard ("naive") RAG, as in Lewis et al. (2020) and most deployed pipelines: embed the question,
take the top-k most similar chunks, put them all in the prompt, generate. CAMR uses the same
embedder, store and prompt template; what differs is which notes reach the prompt (gating,
margin, entity bridging, token budget) and when none do. Holding everything else fixed isolates
exactly that difference.

retrieval  (no language model) 500 HotpotQA + 500 2WikiMultiHopQA questions on the 38,054-note
           store: full-support recall, context precision, tokens.
answers    (Ollama) 60 held-out PopQA questions, two small models, five conditions: alone; RAG
           and CAMR when the answer IS in memory; RAG and CAMR when it is NOT (the question's own
           document removed from the store). The second pair tests what each does with nothing
           relevant to find.

    python scripts/rag_vs_camr.py retrieval --store-copy <scratch>/retrieval_eval
    python scripts/rag_vs_camr.py answers --models qwen2.5:0.5b,llama3.2:3b
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import shutil
import statistics
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/rag_vs_camr"
SIM = {"retrieval_policy": "similarity_only", "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0}}


def rag(k: int) -> dict:
    """Standard RAG: the k most similar chunks, always, whatever their similarity; no budget cut."""
    return {**SIM, "k": k, "min_similarity": 0.0, "similarity_margin": None, "expansion": "none", "token_budget": 100000}


CAMR = {**SIM, "k": 20, "min_similarity": 0.50, "similarity_margin": 0.15, "expansion": "entity", "token_budget": 512}


# ------------------------------------------------------------------ retrieval level
def retrieval(a) -> None:
    import importlib.util

    from camr.config import Config
    from camr.harness.experiment import Workspace
    from camr.memory.clock import LogicalClock

    spec = importlib.util.spec_from_file_location("tg", ROOT / "scripts/tune_gating.py")
    tg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(tg)
    src, dst = ROOT / "results/retrieval_eval", Path(a.store_copy)
    if not (dst / "camr.sqlite").exists():
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "camr.sqlite", dst / "camr.sqlite")
        shutil.copytree(src / "samples", dst / "samples", dirs_exist_ok=True)
    cfg = Config.load(ROOT / "configs/retrieval_eval.yaml")
    ws = Workspace(cfg, run_dir=dst)
    ws._embedder = tg.CachedEmbedder(ws.embedder)
    variants = [("RAG top-3", rag(3)), ("RAG top-5", rag(5)), ("RAG top-10", rag(10)), ("CAMR", CAMR)]
    rows = []
    for bench in ("hotpotqa", "2wikimultihopqa"):
        qs = [q for q in ws.sample(bench) if q.support]
        for name, over in variants:
            vcfg = cfg.with_overrides({"memory": {"write_policy": "verbatim", **over}})
            store, nt = ws.store, vcfg.memory.note_type
            store.reset_access_state(nt)
            engine = ws.engine(vcfg, LogicalClock(store.latest_created_at(nt), vcfg.memory.clock_step_hours))
            full = anyg = 0
            prec, toks, nadm, abst = [], [], [], 0
            for q in qs:
                r = engine.recall(q.question, touch=False)
                titles = store.note_titles(c.note.note_id for c in r.admitted)
                got = [" ".join((titles.get(c.note.note_id) or "").split()) for c in r.admitted]
                gold = {" ".join(t.split()) for t in q.support}
                full += gold <= set(got)
                anyg += bool(gold & set(got))
                prec.append(sum(t in gold for t in got) / len(got) if got else None)
                toks.append(r.context_tokens)
                nadm.append(len(got))
                abst += r.abstained
            n = len(qs)
            p = [x for x in prec if x is not None]
            rows.append({"benchmark": bench, "method": name, "n": n, "support_all": full / n, "support_any": anyg / n,
                         "context_precision": statistics.mean(p) if p else 0.0, "mean_tokens": statistics.mean(toks),
                         "mean_notes": statistics.mean(nadm), "abstain_rate": abst / n})
            print(rows[-1], flush=True)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "retrieval.json").write_text(json.dumps({"variants": {n: v for n, v in variants}, "rows": rows}, indent=2))


# ------------------------------------------------------------------ answer level
def popqa_sets():
    """The 60 held-out PopQA questions (pilot 30 + learning evaluation 30) with their subject document."""
    from camr.harness.benchmarks import load_questions

    meta = {r["id"]: r for r in csv.DictReader(open(ROOT / "data/popqa/test.tsv"), delimiter="\t")}
    ids = []
    for f in (ROOT / "results/pilot/samples/popqa.json", ROOT / "results/learn/samples/popqa.json"):
        ids += json.loads(f.read_text())["question_ids"]
    qs = {q.qid: q for q in load_questions("popqa", ROOT / "data/popqa/test.tsv")}
    return [(qs[i], meta[i]["s_wiki_title"]) for i in dict.fromkeys(ids)]


def documents():
    seen, docs = set(), []
    for f in ("corpus_pilot.jsonl", "corpus_learn.jsonl"):
        for line in (ROOT / "data/popqa" / f).read_text().splitlines():
            d = json.loads(line)
            if d["doc_id"] not in seen:
                seen.add(d["doc_id"])
                docs.append(d)
    return docs


def build_engine(cfg, path: Path, docs, over: dict):
    from camr.memory.embedder import build_embedder
    from camr.memory.engine import MemoryEngine
    from camr.memory.note import Document
    from camr.memory.store import SQLiteVectorStore
    from camr.models.tokenizer import build_tokenizer

    if not hasattr(build_engine, "emb"):
        build_engine.emb = build_embedder(cfg.embedder)
    emb = build_engine.emb
    fresh = not path.exists()
    store = SQLiteVectorStore(path, dim=emb.dim, embedder_name=emb.name)
    vcfg = cfg.with_overrides({"memory": {"write_policy": "verbatim", **over}})
    engine = MemoryEngine.from_config(vcfg, store=store, embedder=emb,
                                      tokenizer=build_tokenizer(cfg.tokenizer.backend, cfg.tokenizer.name))
    if fresh:
        engine.ingest([Document(dataset="popqa", doc_id=d["doc_id"], text=d["text"], title=d["title"]) for d in docs])
    return engine


def answers(a) -> None:
    from camr.config import Config, LocalModelConfig
    from camr.eval.escalation import abstention_like
    from camr.eval.scoring import normalize_answer, score
    from camr.models.prompt import answer_template
    from camr.models.runner import OllamaRunner

    cfg = Config.load(ROOT / "results/learn/config.yaml")
    qs, docs = popqa_sets(), documents()
    rng = random.Random(13)
    group = {q.qid: rng.random() < 0.5 for q, _ in qs}  # which half-store lacks this question's document
    tmp = Path(tempfile.mkdtemp(prefix="ragcamr-"))
    removed = {g: {t for q, t in qs if group[q.qid] == g} for g in (True, False)}
    stores = {"full": docs, True: [d for d in docs if d["title"] not in removed[True]],
              False: [d for d in docs if d["title"] not in removed[False]]}
    engines = {}
    for key, ds in stores.items():
        for name, over in (("rag", rag(a.k)), ("camr", CAMR)):
            engines[(key, name)] = build_engine(cfg, tmp / f"store-{key}.sqlite", ds, over)
    bare, mem = answer_template("single_hop", False), answer_template("single_hop", True)
    out = {"k": a.k, "n": len(qs), "camr": CAMR, "models": {}}
    for model in a.models.split(","):
        runner = OllamaRunner(LocalModelConfig(name=model, host="http://127.0.0.1:11434", max_tokens=64, num_ctx=4096))
        res = {c: [] for c in ("alone", "rag_answerable", "camr_answerable", "rag_missing", "camr_missing")}
        for q, title in qs:
            def ask(prompt, context, abstained):
                g = runner.generate(prompt)
                corr = score("single_hop", g.text, q.answers)["contains"]
                ans = normalize_answer(g.text.strip().splitlines()[0] if g.text.strip() else "")
                from_ctx = bool(ans) and not corr and f" {ans} " in f" {normalize_answer(context)} "
                return {"qid": q.qid, "correct": corr, "answer": g.text.strip()[:200], "context_tokens": len(context.split()),
                        "abstained": abstained, "declined": abstention_like(g.text), "wrong_from_context": from_ctx,
                        "gold_in_context": any(f" {normalize_answer(x)} " in f" {normalize_answer(context)} " for x in q.answers)}
            res["alone"].append(ask(bare.render(q.question), "", True))
            for cond, key in (("answerable", "full"), ("missing", group[q.qid])):
                for name in ("rag", "camr"):
                    r = engines[(key, name)].recall(q.question, touch=False)
                    prompt = bare.render(q.question) if r.abstained else mem.render(q.question, r.context)
                    res[f"{name}_{cond}"].append(ask(prompt, r.context if not r.abstained else "", r.abstained))
        summary = {c: {"accuracy": statistics.mean(x["correct"] for x in v),
                       "mean_context_words": statistics.mean(x["context_tokens"] for x in v),
                       "abstain_rate": statistics.mean(x["abstained"] for x in v),
                       "declined": statistics.mean(x["declined"] for x in v),
                       "wrong_from_context": statistics.mean(x["wrong_from_context"] for x in v),
                       "gold_in_context": statistics.mean(x["gold_in_context"] for x in v)} for c, v in res.items()}
        out["models"][model] = {"summary": summary, "per_question": res}
        print(model, json.dumps(summary, indent=1), flush=True)
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "answers.json").write_text(json.dumps(out, indent=2))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["retrieval", "answers"])
    ap.add_argument("--store-copy", default=str(ROOT / ".cache/retrieval_eval"))
    ap.add_argument("--models", default="qwen2.5:0.5b,llama3.2:3b")
    ap.add_argument("--k", type=int, default=5)
    a = ap.parse_args()
    retrieval(a) if a.part == "retrieval" else answers(a)

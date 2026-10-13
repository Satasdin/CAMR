"""Does a frozen 0.5B model that learns as it goes catch up with bigger models? (eager learning, Chapter 5)

A stream of 200 PopQA questions the engine has never seen, asked once, in order, to a
0.5B model whose memory starts EMPTY. When memory has nothing, the engine looks the
subject up on the web, stores what it read, and answers from it (camr.memory.eager).
Then, offline (no network), the same facts are asked again in different words: what
it answers now it can only know from what it learned.

Baselines answer the same questions closed-book: qwen2.5 0.5B / 1.5B, llama3.2 3B,
gpt-oss 20B (local) and Kimi K3 (cloud). Peak resident memory (RSS) of the local model
process is sampled during every run.

Thirty subjects are asked about twice, at least 40 questions apart, so the stream also
shows reuse: whether the second question is answered from what the first one taught.

    python scripts/eager_learning.py select
    python scripts/eager_learning.py learn                      # pass 1, online
    python scripts/eager_learning.py retain --models qwen2.5:0.5b,llama3.2:3b   # pass 2, offline
    python scripts/eager_learning.py baseline --model gpt-oss:20b [--paraphrase]
    python scripts/eager_learning.py baseline --model kimi-k3
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import subprocess
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "results/eager"
STREAM = OUT / "stream.json"
SEED = 2026

# A second wording for each PopQA relation (pass 2 asks the learned facts in these words).
PARAPHRASE = {
    "occupation": "What does {s} do for a living?",
    "place of birth": "Where was {s} born?",
    "genre": "Which genre does {s} belong to?",
    "father": "Who was {s}'s father?",
    "country": "Which country is {s} located in?",
    "producer": "Who produced {s}?",
    "director": "Who directed {s}?",
    "capital of": "{s} is the capital of which place?",
    "screenwriter": "Who wrote the screenplay of {s}?",
    "composer": "Who wrote the music for {s}?",
    "color": "Which colour is {s}?",
    "religion": "Which religion did {s} follow?",
    "sport": "Which sport is {s} associated with?",
    "author": "Who wrote {s}?",
    "mother": "Who was {s}'s mother?",
    "capital": "Which city is the capital of {s}?",
}
CAMR = {"retrieval_policy": "similarity_only", "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0},
        "k": 20, "min_similarity": 0.50, "similarity_margin": 0.15, "expansion": "entity", "token_budget": 512,
        "entity_gate": True, "write_policy": "verbatim"}


# ------------------------------------------------------------------ question stream
def used_ids() -> set[str]:
    ids: set[str] = set()
    for f in ROOT.glob("results/*/samples/popqa*.json"):
        ids |= set(json.loads(f.read_text())["question_ids"])
    return ids


def select(a) -> None:
    rows = list(csv.DictReader(open(ROOT / "data/popqa/test.tsv"), delimiter="\t"))
    used = used_ids()
    rows = [r for r in rows if r["id"] not in used]
    rng = random.Random(SEED)
    by_subj: dict[str, list[dict]] = {}
    for r in rows:
        by_subj.setdefault(r["subj_id"], []).append(r)
    multi = [v for v in by_subj.values() if len({r["prop"] for r in v}) >= 2]
    rng.shuffle(multi)
    pairs = []
    for v in multi[: a.pairs]:
        first, second = rng.sample(sorted(v, key=lambda r: r["id"]), 2)
        if first["prop"] == second["prop"]:
            continue
        pairs.append((first, second))
    taken = {r["subj_id"] for p in pairs for r in p}
    singles = [v[0] for k, v in by_subj.items() if k not in taken and len(v) == 1]
    rng.shuffle(singles)
    n = a.n
    singles = singles[: n - 2 * len(pairs)]
    slots: list[dict | None] = [None] * n
    for i, (first, second) in enumerate(pairs):  # first in the first 55%, second 40-90 questions later
        for _ in range(1000):
            p = rng.randrange(0, int(n * 0.55))
            q = p + rng.randint(40, 90)
            if q < n and slots[p] is None and slots[q] is None:
                slots[p], slots[q] = {**first, "pair": i, "pair_role": "first"}, {**second, "pair": i,
                                                                                  "pair_role": "second"}
                break
    it = iter(singles)
    stream = [s if s is not None else next(it) for s in slots]
    items = []
    for i, r in enumerate(stream):
        items.append({"i": i, "qid": r["id"], "question": r["question"], "paraphrase": PARAPHRASE[r["prop"]].format(
            s=r["subj"]), "answers": json.loads(r["possible_answers"]), "prop": r["prop"], "subj": r["subj"],
            "subj_id": r["subj_id"], "s_pop": int(r["s_pop"]), "pair": r.get("pair"), "pair_role": r.get("pair_role")})
    OUT.mkdir(parents=True, exist_ok=True)
    STREAM.write_text(json.dumps({"seed": SEED, "n": n, "pairs": len(pairs), "excluded_used_ids": len(used),
                                  "items": items}, indent=1))
    print(f"{n} questions, {len(pairs)} subjects asked twice -> {STREAM}")


def load_stream() -> list[dict]:
    return json.loads(STREAM.read_text())["items"]


# ------------------------------------------------------------------ helpers
def model_blob(model: str) -> str | None:
    """The weights file (sha256 digest) of an Ollama model, from its manifest: identifies its server process."""
    name, _, tag = model.partition(":")
    f = Path.home() / ".ollama/models/manifests/registry.ollama.ai/library" / name / (tag or "latest")
    try:
        layers = json.loads(f.read_text())["layers"]
    except (OSError, ValueError, KeyError):
        return None
    for layer in layers:
        if layer.get("mediaType") == "application/vnd.ollama.image.model":
            return layer["digest"].replace(":", "-")
    return None


def model_rss_mb(model: str) -> float:
    """Resident memory (MB) of the process serving ``model`` now (0 if it is not loaded)."""
    blob = model_blob(model)
    if not blob:
        return 0.0
    out = subprocess.run(["ps", "-eo", "rss,args"], capture_output=True, text=True).stdout
    return sum(int(line.split()[0]) for line in out.splitlines()[1:] if blob in line) / 1024


class PeakRSS:
    """Peak resident memory (MB) of the process serving one Ollama model, sampled every 0.5 s."""

    def __init__(self, model: str | None = None):
        self.model = model
        self.peak, self._stop = 0.0, threading.Event()
        self.t = threading.Thread(target=self._run, daemon=True)

    def _run(self):
        while not self._stop.is_set():
            try:
                if self.model:
                    self.peak = max(self.peak, model_rss_mb(self.model))
            except Exception:
                pass
            self._stop.wait(0.5)

    def __enter__(self):
        self.t.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self.t.join()


def self_rss_mb() -> float:
    with open("/proc/self/status") as f:
        for line in f:
            if line.startswith("VmRSS:"):
                return int(line.split()[1]) / 1024
    return 0.0


def runner_for(model: str):
    from camr.config import CeilingModelConfig, Config, LocalModelConfig
    from camr.models.runner import OllamaRunner, build_ceiling_runner

    if model.startswith("kimi"):
        ceil = Config.load(ROOT / "results/learn/config.yaml").ceiling_model
        return build_ceiling_runner(ceil)
    if model.startswith("gpt-oss"):
        return build_ceiling_runner(CeilingModelConfig(backend="ollama", name=model, think="low", max_tokens=1024,
                                                       timeout_s=900))
    return OllamaRunner(LocalModelConfig(name=model, max_tokens=64, num_ctx=4096))


def judge(item: dict, text: str) -> dict:
    from camr.eval.escalation import abstention_like
    from camr.eval.scoring import score

    return {"correct": bool(score("single_hop", text, item["answers"])["contains"]),
            "declined": abstention_like(text)}


def build_engine(store_path: Path):
    from camr.config import Config
    from camr.memory.embedder import build_embedder
    from camr.memory.engine import MemoryEngine
    from camr.memory.store import SQLiteVectorStore
    from camr.models.tokenizer import build_tokenizer

    cfg = Config.load(ROOT / "results/learn/config.yaml").with_overrides({"memory": CAMR})
    emb = build_embedder(cfg.embedder)
    store = SQLiteVectorStore(store_path, dim=emb.dim, embedder_name=emb.name)
    return MemoryEngine.from_config(cfg, store=store, embedder=emb,
                                    tokenizer=build_tokenizer(cfg.tokenizer.backend, cfg.tokenizer.name)), store


def save(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, indent=1, ensure_ascii=False))


# ------------------------------------------------------------------ dev: choose how lookups disambiguate
def dev(a) -> None:
    """On 60 fresh questions disjoint from the stream: how often does each lookup variant fetch a page that
    contains the answer? (No model involved.) Chooses the ranking of ambiguous names before the stream runs."""
    from camr.config import Config
    from camr.eval.scoring import normalize_answer
    from camr.memory.embedder import build_embedder
    from camr.memory.fetch import WebLookup, embedding_rank

    rows = list(csv.DictReader(open(ROOT / "data/popqa/test.tsv"), delimiter="\t"))
    taken = used_ids() | {x["qid"] for x in load_stream()} | {x["subj_id"] for x in load_stream()}
    rows = [r for r in rows if r["id"] not in taken and r["subj_id"] not in taken]
    rng = random.Random(SEED + 1)
    dev_items = rng.sample(rows, a.n_dev)
    emb = build_embedder(Config.load(ROOT / "results/learn/config.yaml").embedder)
    out = {"n": len(dev_items), "variants": {}}
    for name, rank in (("word overlap", None), ("embedding similarity", embedding_rank(emb))):
        lookup = WebLookup(cache_path=OUT / "web_cache.sqlite", patient_s=a.patient, rank=rank, min_interval_s=1.5)
        hits, pages, reqs = 0, 0, 0
        for r in dev_items:
            res = lookup.lookup(r["question"])
            text = normalize_answer(" ".join(p.text for p in res.pages))
            gold = json.loads(r["possible_answers"])
            hits += any(f" {normalize_answer(g)} " in f" {text} " for g in gold)
            pages += len(res.pages)
            reqs += res.requests
        out["variants"][name] = {"answer_in_fetched_text": hits / len(dev_items), "pages_per_question": pages / len(
            dev_items), "requests": reqs}
        print(name, out["variants"][name], flush=True)
    save(OUT / "lookup_dev.json", out)


# ------------------------------------------------------------------ dev: how much to read per lookup
def devtune(a) -> None:
    """D-21 made lookups return more pages, and the extra text hurt the 0.5B reader. Choose pages per lookup and the
    token budget on the 60 development questions (never the stream), with the answering model."""
    import shutil
    import tempfile

    from camr.eval.scoring import normalize_answer  # noqa: F401
    from camr.memory.eager import eager_recall
    from camr.memory.fetch import WebLookup, embedding_rank
    from camr.models.prompt import answer_template

    rows = list(csv.DictReader(open(ROOT / "data/popqa/test.tsv"), delimiter="\t"))
    taken = used_ids() | {x["qid"] for x in load_stream()} | {x["subj_id"] for x in load_stream()}
    rows = [r for r in rows if r["id"] not in taken and r["subj_id"] not in taken]
    dev_items = random.Random(SEED + 1).sample(rows, a.n_dev)  # the same 60 as `dev`
    runner = runner_for(a.model)
    bare, mem = answer_template("single_hop", False), answer_template("single_hop", True)
    path = OUT / "devtune.json"
    out = json.loads(path.read_text()) if path.exists() else {"n": len(dev_items), "model": a.model, "grid": []}
    done = {(g["max_pages"], g["token_budget"]) for g in out["grid"]}
    for pages in (1, 2, 3):
        for budget in (128, 512):
            if (pages, budget) in done:  # resumable: each setting is saved as soon as it is measured
                continue
            tmp = Path(tempfile.mkdtemp(prefix="devtune-"))
            CAMR["token_budget"] = budget
            engine, store = build_engine(tmp / "store.sqlite")
            lookup = WebLookup(cache_path=OUT / "web_cache_after_D21.sqlite", patient_s=a.patient, min_interval_s=1.5,
                               rank=embedding_rank(engine.embedder))
            correct = 0
            for r in dev_items:
                rec, _ = eager_recall(engine, lookup, r["question"], touch=False, max_pages=pages)
                g = runner.generate(bare.render(r["question"]) if rec.abstained else mem.render(r["question"], rec.context))
                correct += judge({"answers": json.loads(r["possible_answers"])}, g.text)["correct"]
            out["grid"].append({"max_pages": pages, "token_budget": budget, "accuracy": correct / len(dev_items)})
            save(path, out)
            print(out["grid"][-1], flush=True)
            store.close()
            shutil.rmtree(tmp, ignore_errors=True)
    CAMR["token_budget"] = 512
    save(path, out)


# ------------------------------------------------------------------ pass 1: learn online
def learn(a) -> None:
    from camr.memory.eager import eager_recall
    from camr.memory.fetch import WebLookup, embedding_rank
    from camr.models.prompt import answer_template

    items = load_stream()
    tag = f"_{a.tag}" if a.tag else ""
    if a.budget:
        CAMR["token_budget"] = a.budget
    store_path = OUT / f"store{tag}.sqlite"
    path = OUT / f"learn{tag}.json"
    if a.fresh:
        store_path.unlink(missing_ok=True)
        path.unlink(missing_ok=True)
    engine, store = build_engine(store_path)
    # ambiguous names: ordered by the embedder's similarity to the question (chosen on the dev set, lookup_dev.json)
    lookup = WebLookup(cache_path=OUT / f"web_cache{tag}.sqlite", patient_s=a.patient, offline=a.offline_replay,
                       rank=embedding_rank(engine.embedder), min_interval_s=1.5)
    runner = runner_for(a.model)
    bare, mem = answer_template("single_hop", False), answer_template("single_hop", True)
    log = json.loads(path.read_text()) if path.exists() else {"model": a.model, "config": CAMR, "turns": []}
    done = {t["i"] for t in log["turns"]}
    with PeakRSS(a.model) as rss:
        for item in items:
            if item["i"] in done:
                continue
            t0 = time.perf_counter()
            recall, learned = eager_recall(engine, lookup, item["question"], touch=False, max_pages=a.max_pages)
            prompt = bare.render(item["question"]) if recall.abstained else mem.render(item["question"], recall.context)
            g = runner.generate(prompt)
            ctx = recall.context if not recall.abstained else ""
            from camr.eval.scoring import normalize_answer
            log["turns"].append({
                "i": item["i"], "qid": item["qid"], "pair": item["pair"], "pair_role": item["pair_role"],
                "answer": g.text.strip()[:200], **judge(item, g.text),
                "memory_had_it": learned.reason == "memory had it", "looked_up": learned.looked_up,
                "pages": learned.pages, "queries": learned.queries, "web_errors": learned.errors,
                "notes_added": learned.notes_added, "abstained": recall.abstained,
                "gold_in_context": any(f" {normalize_answer(x)} " in f" {normalize_answer(ctx)} " for x in item["answers"]),
                "context_tokens": recall.context_tokens, "lookup_ms": round(learned.lookup_ms, 1),
                "retrieval_ms": round(recall.retrieval_ms, 1), "generation_ms": round(g.latency_ms, 1),
                "total_ms": round((time.perf_counter() - t0) * 1000, 1), "notes_total": store.count(),
                "store_bytes": store_path.stat().st_size})
            log["peak_model_rss_mb"] = round(rss.peak, 1)
            log["engine_process_rss_mb"] = round(self_rss_mb(), 1)
            save(path, log)
            t = log["turns"][-1]
            print(f"{item['i']:3d} {'✓' if t['correct'] else '✗'} {'web' if t['looked_up'] else 'mem' if t['memory_had_it'] else '-'}"
                  f" notes={t['notes_total']} {item['question'][:60]!r} -> {t['answer'][:40]!r}", flush=True)
    acc = sum(t["correct"] for t in log["turns"]) / len(log["turns"])
    print(f"pass 1 accuracy {acc:.3f}; notes {store.count()}; peak model RSS {log['peak_model_rss_mb']} MB")


# ------------------------------------------------------------------ pass 2: offline, other words
def retain(a) -> None:
    from camr.eval.scoring import normalize_answer
    from camr.models.prompt import answer_template

    items = load_stream()
    tag = f"_{a.tag}" if a.tag else ""
    if a.budget:
        CAMR["token_budget"] = a.budget
    engine, store = build_engine(OUT / f"store{tag}.sqlite")  # what pass 1 learned; nothing is looked up
    bare, mem = answer_template("single_hop", False), answer_template("single_hop", True)
    path = OUT / f"retain{tag}.json"
    out = json.loads(path.read_text()) if path.exists() else {"notes": store.count(), "models": {}}
    for model in a.models.split(","):
        runner = runner_for(model)
        res = []
        with PeakRSS(model) as rss:
            for item in items:
                r = engine.recall(item["paraphrase"], touch=False)
                prompt = bare.render(item["paraphrase"]) if r.abstained else mem.render(item["paraphrase"], r.context)
                g = runner.generate(prompt)
                ctx = r.context if not r.abstained else ""
                res.append({"i": item["i"], "answer": g.text.strip()[:200], **judge(item, g.text),
                            "abstained": r.abstained, "retrieval_ms": round(r.retrieval_ms, 1),
                            "generation_ms": round(g.latency_ms, 1), "gold_in_context": any(
                                f" {normalize_answer(x)} " in f" {normalize_answer(ctx)} " for x in item["answers"])})
        out["models"][model] = {"accuracy": sum(x["correct"] for x in res) / len(res), "peak_model_rss_mb": round(
            rss.peak, 1), "per_question": res}
        save(path, out)
        print(model, "offline accuracy on reworded questions:", round(out["models"][model]["accuracy"], 3), flush=True)


# ------------------------------------------------------------------ closed-book baselines
def baseline(a) -> None:
    from camr.models.prompt import answer_template

    items = load_stream()
    bare = answer_template("single_hop", False)
    field_q = "paraphrase" if a.paraphrase else "question"
    path = OUT / f"baseline_{a.model.replace(':', '_')}{'_para' if a.paraphrase else ''}.json"
    out = json.loads(path.read_text()) if path.exists() else {"model": a.model, "field": field_q, "per_question": []}
    done = {x["i"] for x in out["per_question"]}
    runner = runner_for(a.model)
    with PeakRSS(a.model) as rss:
        for item in items:
            if item["i"] in done:
                continue
            try:
                g = runner.generate(bare.render(item[field_q]))
                text, ms = g.text, g.latency_ms
            except Exception as exc:  # logged, scored wrong, never silently dropped
                text, ms = f"[error: {type(exc).__name__}]", None
            out["per_question"].append({"i": item["i"], "answer": text.strip()[:200], **judge(item, text),
                                        "latency_ms": ms})
            if rss.peak:
                out["peak_model_rss_mb"] = round(max(out.get("peak_model_rss_mb", 0), rss.peak), 1)
            save(path, out)
    pq = out["per_question"]
    out["accuracy"] = sum(x["correct"] for x in pq) / len(pq)
    out["declined"] = sum(x["declined"] for x in pq) / len(pq)
    lat = [x["latency_ms"] for x in pq if x["latency_ms"]]
    out["median_latency_s"] = sorted(lat)[len(lat) // 2] / 1000 if lat else None
    save(path, out)
    print(a.model, field_q, "accuracy", round(out["accuracy"], 3), "peak RSS MB", out.get("peak_model_rss_mb"))


# ------------------------------------------------------------------ memory footprint
def ram(a) -> None:
    """Resident memory of each model after answering a question, alone (others unloaded), and of the engine."""
    import requests

    out = {"models": {}}
    for model in a.models.split(","):
        for m in requests.get("http://127.0.0.1:11434/api/ps", timeout=10).json().get("models", []):
            requests.post("http://127.0.0.1:11434/api/generate", json={"model": m["name"], "keep_alive": 0}, timeout=60)
        time.sleep(2)
        runner = runner_for(model)
        runner.generate("Answer the question with a short phrase only.\n\nQuestion: What is the capital of Kenya?\nAnswer:")
        time.sleep(1)
        out["models"][model] = {"rss_mb": round(model_rss_mb(model), 1)}
        print(model, out["models"][model], flush=True)
    engine, store = build_engine(OUT / "store.sqlite")
    engine.recall("What is the capital of Libya?", touch=False)
    out["engine"] = {"process_rss_mb": round(self_rss_mb(), 1), "notes": store.count(),
                     "store_mb": round((OUT / "store.sqlite").stat().st_size / 1e6, 2)}
    print(out["engine"])
    save(OUT / "ram.json", out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["select", "dev", "devtune", "learn", "retain", "baseline", "ram"])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--pairs", type=int, default=30)
    ap.add_argument("--n-dev", type=int, default=60)
    ap.add_argument("--model", default="qwen2.5:0.5b")
    ap.add_argument("--models", default="qwen2.5:0.5b,llama3.2:3b")
    ap.add_argument("--paraphrase", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--patient", type=float, default=120.0, help="seconds a lookup may wait out a rate limit")
    ap.add_argument("--offline-replay", action="store_true", help="answer lookups from the saved web cache only")
    ap.add_argument("--tag", default="", help="learn/retain: a separate run (e.g. after_D21) with its own store and cache")
    ap.add_argument("--max-pages", type=int, default=3, help="learn: pages kept per lookup")
    ap.add_argument("--budget", type=int, default=0, help="learn: token budget (0 = the configuration's 512)")
    a = ap.parse_args()
    {"select": select, "dev": dev, "devtune": devtune, "learn": learn, "retain": retain, "baseline": baseline,
     "ram": ram}[a.part](a)

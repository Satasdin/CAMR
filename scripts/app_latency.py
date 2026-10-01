"""Measure CAMR Personal's response time on real Ollama models (what a user waits for).

For each chat model it measures, on the same memory and questions:

* cold start: the model is unloaded, then a question is asked (once with the weights read
  from disk, once with them already in the OS page cache);
* warmed start: the model is unloaded, ``Assistant.warm()`` runs (as the app does on
  launch and on a model switch), then the same question is asked;
* warm answers at token budgets 128 / 384 / 768: time to the first word, total answer
  time, memory-lookup time, prompt tokens;
* the query-embedding cache: lookup time for a first and a repeated question;
* memory size: lookup time with ~250 notes and with several thousand notes.

    python scripts/app_latency.py --out docs/results/app_latency.json
"""

from __future__ import annotations

import argparse
import json
import platform
import statistics
import subprocess
import tempfile
import time
from pathlib import Path

import requests

from camr.app.assistant import Assistant

HOST = "http://127.0.0.1:11434"
QUESTIONS = [
    "When is my dentist appointment and with whom?",
    "What is the guest Wi-Fi network called?",
    "When is Chapter 5 due to the supervisor?",
    "What does Mum want for her birthday?",
    "At what mileage is the next oil change due?",
    "Who directed the 2012 film Hero?",
]


def unload(model: str) -> None:
    requests.post(f"{HOST}/api/generate", json={"model": model, "prompt": "", "keep_alive": 0}, timeout=120)
    for _ in range(60):  # wait until Ollama reports it gone
        loaded = [m["name"] for m in requests.get(f"{HOST}/api/ps", timeout=10).json().get("models", [])]
        if model not in loaded:
            return
        time.sleep(0.5)


def drop_page_cache() -> bool:
    """Evict file pages (Linux, root) so the next model load reads its weights from disk, as after a reboot."""
    try:
        subprocess.run(["sync"], check=False)
        Path("/proc/sys/vm/drop_caches").write_text("3\n")
        return True
    except OSError:
        return False


def build_memory(home: Path, extra_hotpot: int = 0) -> Assistant:
    a = Assistant(home, host=HOST, remember_chat=False)
    for line in Path("examples/personal_notes.jsonl").read_text().splitlines():
        d = json.loads(line)
        a.teach(d["text"], title=d["title"], doc_id=d["doc_id"])
    for line in Path("data/popqa/corpus_learn.jsonl").read_text().splitlines():
        d = json.loads(line)
        a.teach(d["text"], title=d["title"], kind="document", doc_id=d["doc_id"])
    if extra_hotpot:
        rows = json.loads(Path("data/hotpotqa/hotpot_dev_distractor_v1.json").read_text())
        seen, n = set(), 0
        for row in rows:
            for title, sents in row["context"]:
                if title in seen:
                    continue
                seen.add(title)
                a.teach(" ".join(sents), title=title, kind="document", doc_id=f"hp-{title}")
                n += 1
            if n >= extra_hotpot:
                break
    return a


def timed_turn(a: Assistant, q: str) -> dict:
    t0 = time.perf_counter()
    turn = a.ask(q)
    return {"question": q, "retrieval_ms": turn.retrieval_ms, "first_token_ms": turn.first_token_ms,
            "generation_ms": turn.generation_ms, "wall_ms": round((time.perf_counter() - t0) * 1000, 1),
            "prompt_tokens": turn.prompt_tokens, "notes": len(turn.sources), "abstained": turn.abstained}


def med(rows: list[dict], key: str) -> float | None:
    vals = [r[key] for r in rows if r[key] is not None]
    return round(statistics.median(vals), 1) if vals else None


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--models", default="qwen2.5:0.5b,qwen2.5:1.5b,llama3.2:3b")
    ap.add_argument("--budgets", default="128,384,768")
    ap.add_argument("--big", type=int, default=4000, help="extra HotpotQA paragraphs for the memory-size test")
    ap.add_argument("--out", default="docs/results/app_latency.json")
    a_ = ap.parse_args()
    out = {"host": {"machine": platform.machine(), "system": platform.system(),
                    "cpus": __import__("os").cpu_count(), "gpu": "none"},
           "ollama": requests.get(f"{HOST}/api/version", timeout=10).json()["version"], "models": {}}
    with tempfile.TemporaryDirectory() as tmp:
        a = build_memory(Path(tmp) / "home")
        out["notes_small"] = a.stats()["notes"]
        for model in a_.models.split(","):
            a.save_settings(model=model)
            res: dict = {}
            unload(model)
            # first load since boot: weights read from disk
            res["page_cache_dropped"] = drop_page_cache()
            res["cold_disk"] = timed_turn(a, QUESTIONS[0])
            unload(model)
            # unloaded again, but the weights file is now in the OS page cache (the usual case on relaunch)
            res["cold"] = timed_turn(a, QUESTIONS[0])
            unload(model)
            t0 = time.perf_counter()
            a.warm()
            res["warm_up_ms"] = round((time.perf_counter() - t0) * 1000, 1)
            res["after_warm"] = timed_turn(a, QUESTIONS[0])
            res["budgets"] = {}
            for b in map(int, a_.budgets.split(",")):
                a.save_settings(token_budget=b)
                a.engine.embedder._query_cache.clear()  # measure lookups uncached; the cache is measured below
                rows = [timed_turn(a, q) for q in QUESTIONS]
                res["budgets"][b] = {"rows": rows, **{f"median_{k}": med(rows, k) for k in
                                                      ("retrieval_ms", "first_token_ms", "generation_ms",
                                                       "prompt_tokens")}}
                print(model, b, {k: v for k, v in res["budgets"][b].items() if k != "rows"}, flush=True)
            a.save_settings(token_budget=384)
            out["models"][model] = res
            print(model, "cold", res["cold"]["first_token_ms"], "warmed", res["after_warm"]["first_token_ms"],
                  "warm-up", res["warm_up_ms"], flush=True)

        # Query-embedding cache: the same question twice, lookup only (no generation).
        first, repeat = [], []
        for q in QUESTIONS:
            fresh = q + " (cache probe)"
            first.append(a.engine.recall(fresh, touch=False).retrieval_ms)
            repeat.append(a.engine.recall(fresh, touch=False).retrieval_ms)
        out["query_cache"] = {"first_ms": round(statistics.median(first), 2),
                              "repeat_ms": round(statistics.median(repeat), 2)}
        a.close()

        # Memory size: lookup time stays flat because search is one SQLite vector query.
        sizes = {}
        for label, extra in (("small", 0), ("large", a_.big)):
            b = build_memory(Path(tmp) / f"home-{label}", extra_hotpot=extra)
            timings = [b.engine.recall(q + f" ({label})", touch=False) for q in QUESTIONS]
            sizes[label] = {"notes": b.stats()["notes"],
                            "median_retrieval_ms": round(statistics.median(t.retrieval_ms for t in timings), 1),
                            "median_search_ms": round(statistics.median(t.timings["search_ms"] for t in timings), 2),
                            "median_embed_ms": round(statistics.median(t.timings["embed_ms"] for t in timings), 1)}
            b.close()
            print("memory", label, sizes[label], flush=True)
        out["memory_size"] = sizes
    Path(a_.out).parent.mkdir(parents=True, exist_ok=True)
    Path(a_.out).write_text(json.dumps(out, indent=2))
    print("wrote", a_.out)


if __name__ == "__main__":
    main()

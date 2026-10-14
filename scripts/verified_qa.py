"""Answers that are verified or not given: tuning on a development set, one run on the test stream.

The test stream is the 200 PopQA questions of the eager-learning study (results/eager/stream.json).
Everything here is chosen on a separate development set of 200 questions whose ids and subjects
are disjoint from the stream and from every earlier sample; the stream is answered once, with the
settings the development set chose.

    python scripts/verified_qa.py select              # the development set
    python scripts/verified_qa.py fetch --set dev     # look every question up once (cached, replayable)
    python scripts/verified_qa.py answer --set dev    # every pipeline variant, every answer cached
    python scripts/verified_qa.py answer --set test --variants chosen

Every web response and every model answer is cached by its exact request, so a rerun with
``--offline`` reproduces the numbers without the network or (with the answer cache) the model.
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
OUT = ROOT / "results/verified"   # caches (web, answers) and committed results
RES = OUT                         # where results and stores are written (--out: elsewhere, for replays)
SEED = 2028


def _eager():
    import importlib.util

    spec = importlib.util.spec_from_file_location("eager_learning", ROOT / "scripts/eager_learning.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def save(path: Path, data) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, indent=1, ensure_ascii=False))
    tmp.replace(path)


# ------------------------------------------------------------------ question sets
def select(a) -> None:
    el = _eager()
    stream = el.load_stream()
    rows = list(csv.DictReader(open(ROOT / "data/popqa/test.tsv"), delimiter="\t"))
    taken = el.used_ids() | {x["qid"] for x in stream}
    subj = {x["subj_id"] for x in stream}
    rows = [r for r in rows if r["id"] not in taken and r["subj_id"] not in subj]
    rng = random.Random(SEED)
    picked = rng.sample(rows, a.n)
    items = [{"i": i, "qid": r["id"], "question": r["question"], "answers": json.loads(r["possible_answers"]),
              "prop": r["prop"], "subj": r["subj"], "subj_id": r["subj_id"], "s_pop": int(r["s_pop"])}
             for i, r in enumerate(picked)]
    save(OUT / "dev.json", {"seed": SEED, "n": len(items), "disjoint_from": "stream ids and subjects, earlier samples",
                            "items": items})
    print(f"{len(items)} development questions -> {OUT / 'dev.json'}")


def load_set(name: str) -> list[dict]:
    if name == "dev":
        return json.loads((OUT / "dev.json").read_text())["items"]
    return _eager().load_stream()


def contains(text: str, answers: list[str]) -> bool:
    from camr.eval.scoring import normalize_answer

    t = f" {normalize_answer(text)} "
    return any(f" {normalize_answer(g)} " in t for g in answers)


# ------------------------------------------------------------------ lookups
def lookup_for(a, embedder):
    from camr.memory.fetch import WebLookup, embedding_rank

    return WebLookup(cache_path=OUT / f"web_cache_{a.set}.sqlite", patient_s=a.patient, offline=a.offline,
                     rank=embedding_rank(embedder), min_interval_s=1.5)


def fetch(a) -> None:
    """Look every question up once (three pages, with infoboxes); how often does what was read hold the answer?"""
    from camr.config import Config
    from camr.memory.embedder import build_embedder

    items = load_set(a.set)
    emb = build_embedder(Config.load(ROOT / "results/learn/config.yaml").embedder)
    lookup = lookup_for(a, emb)
    path = OUT / f"lookup_{a.set}.json"
    out = json.loads(path.read_text()) if path.exists() and not a.fresh else {"set": a.set, "per_question": []}
    done = {x["i"] for x in out["per_question"]}
    for it in items:
        if it["i"] in done:
            continue
        res = lookup.lookup(it["question"], max_pages=3)
        lead = " ".join(p.text for p in res.pages)
        facts = " ".join(p.facts for p in res.pages)
        out["per_question"].append({
            "i": it["i"], "prop": it["prop"], "queries": res.queries,
            "pages": [{"title": p.title, "url": p.url, "facts": len(p.facts.split("; ")) if p.facts else 0}
                      for p in res.pages],
            "in_lead": contains(lead, it["answers"]), "in_facts": contains(facts, it["answers"]),
            "requests": res.requests, "errors": res.errors, "ms": round(res.ms)})
        save(path, out)
        x = out["per_question"][-1]
        print(f"{it['i']:3d} lead={int(x['in_lead'])} facts={int(x['in_facts'])} req={x['requests']} "
              f"{it['question'][:60]!r} -> {[p['title'] for p in x['pages']]}", flush=True)
    pq = out["per_question"]
    n = len(pq)
    out["summary"] = {"n": n, "answer_in_lead": sum(x["in_lead"] for x in pq) / n,
                      "answer_in_facts": sum(x["in_facts"] for x in pq) / n,
                      "answer_in_either": sum(x["in_lead"] or x["in_facts"] for x in pq) / n,
                      "errors": sum(bool(x["errors"]) for x in pq)}
    save(path, out)
    print(json.dumps(out["summary"], indent=1))


# ------------------------------------------------------------------ answering
# Each variant changes one thing from the one before. "old" is the eager pipeline as it was (the small model reads the
# packed notes, or answers alone when memory has nothing); its "stated" numbers are what it used to say.
VARIANTS = {
    "old": dict(facts=False, compressed=False, fact_reader=False, template="qa_memory", readers=["qwen2.5:0.5b"],
                closed_book=True),
    "facts": dict(facts=True, compressed=False, fact_reader=False, template="qa_memory", readers=["qwen2.5:0.5b"],
                  closed_book=True),
    "facts+compress": dict(facts=True, compressed=True, fact_reader=False, template="read",
                           readers=["qwen2.5:0.5b"], closed_book=True),
    "facts+compress+reader": dict(facts=True, compressed=True, fact_reader=True, template="read",
                                  readers=["qwen2.5:0.5b"], closed_book=True),
    "+3b": dict(facts=True, compressed=True, fact_reader=True, template="read",
                readers=["qwen2.5:0.5b", "llama3.2:3b"], closed_book=True),
    "+kimi": dict(facts=True, compressed=True, fact_reader=True, template="read",
                  readers=["qwen2.5:0.5b", "kimi-k3"], closed_book=True),
    # when memory cannot confirm a claim: look the claimed answer up and check it from its own side
    "+3b+cross": dict(facts=True, compressed=True, fact_reader=True, template="read",
                      readers=["qwen2.5:0.5b", "llama3.2:3b"], closed_book=True, cross=True),
    "+kimi+cross": dict(facts=True, compressed=True, fact_reader=True, template="read",
                        readers=["qwen2.5:0.5b", "kimi-k3"], closed_book=True, cross=True),
}


def build_engine(path: Path, budget: int):
    """The eager-learning engine, with its embedder's vectors cached by text (results/verified/vectors.sqlite):
    every variant embeds a page once, and replays use the very same vectors."""
    from camr.memory.embedder import CachedEmbedder

    el = _eager()
    el.CAMR["token_budget"] = budget
    engine, store = el.build_engine(path)
    engine.embedder = CachedEmbedder(engine.embedder, OUT / "vectors.sqlite")
    return engine, store


def readers_for(names: list[str], offline: bool):
    from camr.models.runner import CachedRunner, OllamaRunner

    el = _eager()
    out = []
    for name in names:
        r = el.runner_for(name)
        if isinstance(r, OllamaRunner) and not name.startswith("gpt-oss"):
            r.logprobs = True
        out.append(CachedRunner(r, OUT / "answers.sqlite", offline=offline))
    return out


def run_variant(a, name: str, items: list[dict]) -> dict:
    from camr.memory.answer import BARE, READ, VerifiedAnswerer
    from camr.memory.fetch import WebLookup, embedding_rank
    from camr.models.prompt import QA_MEMORY

    v = VARIANTS[name]
    store_path = RES / "stores" / f"{a.set}_{name.replace('+', '_')}.sqlite"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = build_engine(store_path, a.budget)
    lookup = WebLookup(cache_path=OUT / f"web_cache_{a.set}.sqlite", patient_s=a.patient, offline=a.offline,
                       rank=embedding_rank(engine.embedder), min_interval_s=1.5, facts=v["facts"])
    readers = readers_for(v["readers"], a.offline_answers)
    ans = VerifiedAnswerer(engine, readers, lookup=lookup, budget=a.budget, fact_reader=v["fact_reader"],
                           min_coverage=a.min_coverage, typed=a.typed, relation_cue=a.relation_cue,
                           compressed=v["compressed"], closed_book=v["closed_book"],
                           template=READ if v["template"] == "read" else QA_MEMORY, cross_check=v.get("cross", False))
    ans_bare = BARE  # noqa: F841  (the closed-book prompt, recorded by its id below)
    rows = []
    t0 = time.perf_counter()
    for it in items:
        r = ans.answer(it["question"])
        failed = [x for x in r.attempts if x.error]
        if failed:  # an unavailable model is a failed run, never a scored non-answer
            raise RuntimeError(f"question {it['i']}: {failed[0].by} failed: {failed[0].error}")
        first = r.attempts[0].answer if r.attempts else (r.claim if r.by == "memory" else "")
        units_text = r.context
        rows.append({"i": it["i"], "prop": it["prop"], "status": r.status, "by": r.by, "claim": r.claim[:300],
                     "text": r.text[:300], "ambiguous": bool(r.ambiguous),
                     "correct": contains(r.claim, it["answers"]) if r.claim else False,
                     "first_answer": first[:200], "first_correct": contains(first, it["answers"]) if first else False,
                     "first_declined": (not first) or bool(r.attempts and r.attempts[0].verdict.get("reason") ==
                                                           "declined"),
                     "attempts": [{"by": x.by, "answer": x.answer[:160], "correct": contains(x.answer, it["answers"]),
                                   **{k: x.verdict.get(k) for k in ("supported", "reason", "confidence")}}
                                  for x in r.attempts],
                     "evidence": r.evidence, "gold_shown": contains(units_text, it["answers"]),
                     "looked_up": bool(r.learned and r.learned.looked_up), "ms": r.ms})
    n = len(rows)
    ver = [x for x in rows if x["status"] == "verified"]
    stated_wrong = [x for x in rows if not x["first_declined"] and not x["first_correct"]]
    out = {"variant": name, "settings": v, "n": n, "budget": a.budget, "min_coverage": a.min_coverage,
           "typed": a.typed, "relation_cue": a.relation_cue,
           "verified": {"answered": len(ver) / n, "correct": sum(x["correct"] for x in ver) / n,
                        "wrong": sum(not x["correct"] for x in ver) / n,
                        # wrong about a thing it named unambiguously: the hallucination rate
                        "wrong_unambiguous": sum(not x["correct"] and not x["ambiguous"] for x in ver) / n,
                        # said which of several same-named things it meant, and the question meant another
                        "wrong_other_meaning": sum(not x["correct"] and x["ambiguous"] for x in ver) / n,
                        "ambiguous": sum(x["ambiguous"] for x in ver) / n,
                        "correct_unambiguous": sum(x["correct"] and not x["ambiguous"] for x in ver) / n,
                        "precision": sum(x["correct"] for x in ver) / max(1, len(ver)),
                        "by_memory": sum(x["by"] == "memory" for x in ver) / n,
                        "unverified": sum(x["status"] == "unverified" for x in rows) / n,
                        "unverified_lead_correct": sum(x["correct"] for x in rows if x["status"] == "unverified") / n},
           # what the first reader would have said with no checking at all (how the pipeline used to answer)
           "stated": {"correct": sum(x["first_correct"] for x in rows) / n, "wrong": len(stated_wrong) / n},
           "seconds": round(time.perf_counter() - t0, 1), "notes": store.count(),
           "answers_cached": sum(getattr(r, "hits", 0) for r in readers),
           "answers_new": sum(getattr(r, "misses", 0) for r in readers), "per_question": rows}
    store.close()
    return out


def answer(a) -> None:
    items = load_set(a.set)
    path = RES / f"answers_{a.set}{a.tag}.json"
    out = json.loads(path.read_text()) if path.exists() else {"set": a.set, "variants": {}}
    names = list(VARIANTS) if a.variants == "all" else a.variants.split(",")
    for name in names:
        res = run_variant(a, name, items)
        out["variants"][name] = res
        save(path, out)
        ver, st = res["verified"], res["stated"]
        print(f"{name:24s} verified: correct {ver['correct']:.3f} wrong {ver['wrong']:.3f} (hallucinated "
              f"{ver['wrong_unambiguous']:.3f}, other meaning {ver['wrong_other_meaning']:.3f}) precision "
              f"{ver['precision']:.3f} (memory {ver['by_memory']:.3f}, unverified {ver['unverified']:.3f}) | "
              f"unchecked: correct {st['correct']:.3f} wrong {st['wrong']:.3f} | {res['seconds']}s", flush=True)


def report(a) -> None:
    """The comparison as a table: each variant's verified answers, and what it would have said unchecked; on the
    test stream, the closed-book models too (their every answer is stated)."""
    path = RES / f"answers_{a.set}{a.tag}.json"
    d = json.loads(path.read_text())
    rows = [("pipeline", "correct", "hallucinated", "other meaning", "unconfirmed", "precision", "unchecked: correct",
             "unchecked: wrong")]
    for name, v in d["variants"].items():
        ver, st = v["verified"], v["stated"]
        rows.append((name, f"{ver['correct']:.1%}", f"{ver.get('wrong_unambiguous', ver['wrong']):.1%}",
                     f"{ver.get('wrong_other_meaning', 0):.1%}", f"{ver['unverified'] + (1 - ver['answered'] - ver['unverified']):.1%}",
                     f"{ver['precision']:.1%}", f"{st['correct']:.1%}", f"{st['wrong']:.1%}"))
    if a.set == "test":
        for f in sorted((ROOT / "results/eager").glob("baseline_*.json")):
            if f.stem.endswith("_para"):
                continue
            b = json.loads(f.read_text())
            pq = b["per_question"]
            n = len(pq)
            wrong = sum((not x["correct"]) and not x["declined"] for x in pq) / n
            rows.append((f"{b['model']} closed-book", f"{sum(x['correct'] for x in pq) / n:.1%}", f"{wrong:.1%}",
                         "-", f"{sum(x['declined'] for x in pq) / n:.1%}",
                         f"{sum(x['correct'] for x in pq) / max(1, n - sum(x['declined'] for x in pq)):.1%}", "-", "-"))
    widths = [max(len(r[i]) for r in rows) for i in range(len(rows[0]))]
    for k, r in enumerate(rows):
        print("| " + " | ".join(c.ljust(w) for c, w in zip(r, widths)) + " |")
        if k == 0:
            print("|" + "|".join("-" * (w + 2) for w in widths) + "|")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["select", "fetch", "answer", "report"])
    ap.add_argument("--set", default="dev", choices=["dev", "test"])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--patient", type=float, default=120.0)
    ap.add_argument("--offline", action="store_true")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--offline-answers", action="store_true", help="model answers from the answer cache only")
    ap.add_argument("--variants", default="all")
    ap.add_argument("--budget", type=int, default=128)
    ap.add_argument("--min-coverage", type=float, default=1.0, help="share of the claim's words one unit must hold")
    ap.add_argument("--tag", default="", help="a separate results file (answers_<set><tag>.json)")
    ap.add_argument("--typed", action="store_true", help="a claim of the wrong kind is not support")
    ap.add_argument("--relation-cue", action="store_true", help="a sentence must state the asked relation")
    ap.add_argument("--out", default=None, help="write results and stores here (caches are still read from "
                                                "results/verified)")
    a = ap.parse_args()
    if a.out:
        RES = Path(a.out)
        RES.mkdir(parents=True, exist_ok=True)
    {"select": select, "fetch": fetch, "answer": answer, "report": report}[a.part](a)

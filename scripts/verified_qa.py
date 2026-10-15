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
    if name in ("dev", "heldout"):
        return json.loads((OUT / f"{name}.json").read_text())["items"]
    return _eager().load_stream()


def select_heldout(a) -> None:
    """A second test set, drawn after every choice was made: ids and subjects disjoint from the stream, the
    development set and every earlier sample."""
    el = _eager()
    stream = el.load_stream()
    dev = json.loads((OUT / "dev.json").read_text())["items"]
    rows = list(csv.DictReader(open(ROOT / "data/popqa/test.tsv"), delimiter="\t"))
    taken = el.used_ids() | {x["qid"] for x in stream} | {x["qid"] for x in dev}
    subj = {x["subj_id"] for x in stream} | {x["subj_id"] for x in dev}
    rows = [r for r in rows if r["id"] not in taken and r["subj_id"] not in subj]
    picked = random.Random(SEED + 1).sample(rows, a.n)
    items = [{"i": i, "qid": r["id"], "question": r["question"], "answers": json.loads(r["possible_answers"]),
              "prop": r["prop"], "subj": r["subj"], "subj_id": r["subj_id"], "s_pop": int(r["s_pop"])}
             for i, r in enumerate(picked)]
    save(OUT / "heldout.json", {"seed": SEED + 1, "n": len(items),
                                "disjoint_from": "stream, development set and earlier samples (ids and subjects)",
                                "items": items})
    print(f"{len(items)} held-out questions -> {OUT / 'heldout.json'}")


def closed(a) -> None:
    """A model alone, answering every question of a set from its own knowledge (every answer stated)."""
    from camr.memory.answer import BARE

    items = load_set(a.set)
    runner = readers_for([a.model], a.offline_answers)[0]
    rows = []
    for it in items:
        g = runner.generate(BARE.render(it["question"]))
        text = g.text.strip()
        rows.append({"i": it["i"], "answer": text[:300], "correct": contains(text, it["answers"]),
                     "declined": not claim_like(text)})
    n = len(rows)
    out = {"model": a.model, "set": a.set, "n": n, "correct": sum(r["correct"] for r in rows) / n,
           "wrong": sum(not r["correct"] and not r["declined"] for r in rows) / n, "per_question": rows}
    save(RES / f"closed_{a.set}_{a.model.replace(':', '_')}.json", out)
    print(f"{a.model} closed-book on {a.set}: correct {out['correct']:.3f} wrong {out['wrong']:.3f}", flush=True)


def claim_like(text: str) -> bool:
    from camr.memory.verify import abstention_like, claim

    return bool(claim(text)) and not abstention_like(claim(text))


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


def build_engine(path: Path, budget: int, hybrid: bool = False):
    """The eager-learning engine, with its embedder's vectors cached by text (results/verified/vectors.sqlite):
    every variant embeds a page once, and replays use the very same vectors."""
    from camr.memory.embedder import CachedEmbedder

    el = _eager()
    el.CAMR["token_budget"] = budget
    engine, store = el.build_engine(path)
    engine.keyword_k = 20 if hybrid else 0  # hybrid recall: notes found by their words join the vector hits
    engine.embedder = CachedEmbedder(engine.embedder, OUT / "vectors.sqlite")
    return engine, store


def readers_for(names: list[str], offline: bool):
    from camr.models.runner import CachedRunner, OllamaRunner

    el = _eager()
    out = []
    for name in names:
        if offline and name.startswith("kimi"):  # a replay needs the request's shape, not the key
            from camr.config import Config
            from camr.models.runner import ReplayOnlyRunner

            r = ReplayOnlyRunner(Config.load(ROOT / "results/learn/config.yaml").ceiling_model)
            out.append(CachedRunner(r, OUT / "answers.sqlite", offline=True))
            continue
        r = el.runner_for(name)
        if isinstance(r, OllamaRunner) and not name.startswith("gpt-oss"):
            r.logprobs = True
        out.append(CachedRunner(r, OUT / "answers.sqlite", offline=offline))
    return out


def run_variant(a, name: str, items: list[dict]) -> dict:
    from camr.memory.answer import BARE, READ, VerifiedAnswerer
    from camr.memory.fetch import WebLookup, embedding_rank
    from camr.models.prompt import QA_MEMORY

    v = dict(VARIANTS[name])
    if getattr(a, "reader", ""):  # the same pipeline with another first reader (which model suits the engine)
        v["readers"] = [a.reader] + v["readers"][1:]
    store_path = RES / "stores" / f"{a.set}_{name.replace('+', '_')}.sqlite"
    store_path.parent.mkdir(parents=True, exist_ok=True)
    for f in store_path.parent.glob(store_path.name + "*"):
        f.unlink()
    engine, store = build_engine(store_path, a.budget, hybrid=getattr(a, "hybrid", False))
    # Answering reads the web only from the frozen cache (what `fetch` and earlier warm runs stored), so every
    # variant sees exactly the same pages and a replay sees them too; --online lets a warm run fill misses.
    lookup = WebLookup(cache_path=OUT / f"web_cache_{a.set}.sqlite", patient_s=a.patient,
                       offline=not getattr(a, "online", False), rank=embedding_rank(engine.embedder),
                       min_interval_s=1.5, facts=v["facts"])
    readers = readers_for(v["readers"], a.offline_answers)
    ans = VerifiedAnswerer(engine, readers, lookup=lookup, budget=a.budget, fact_reader=v["fact_reader"],
                           min_coverage=a.min_coverage, typed=a.typed, relation_cue=a.relation_cue,
                           by_name=getattr(a, "by_name", False), subject_aware=getattr(a, "subject_aware", False),
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
           "typed": a.typed, "relation_cue": a.relation_cue, "by_name": getattr(a, "by_name", False),
           "hybrid": getattr(a, "hybrid", False), "subject_aware": getattr(a, "subject_aware", False),
           "reader": getattr(a, "reader", "") or "",
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


# ------------------------------------------------------------------ a second, semantic score
JUDGE = (
    "You check answers to quiz questions.\n\nQuestion: {question}\nAccepted answers: {gold}\n"
    "Candidate answer: {answer}\n\nDoes the candidate give one of the accepted answers? Count different spellings, "
    "aliases, translations, and a more or less specific form of the same thing (a city for its district, a church "
    "for its denomination) as the same answer. Count a different person, place or thing as different, and a list "
    "that does not contain an accepted answer as different. Reply with one word: yes or no."
)


def _judge_runner(name: str):
    from camr.models.runner import CachedRunner

    return CachedRunner(_eager().runner_for(name), OUT / "judge.sqlite", offline=False)


def judged(runner, question: str, gold: list[str], answer: str) -> bool:
    """Same answer as the gold, by the judge (asked only where exact matching says no)."""
    import re

    if not answer.strip():
        return False
    if contains(answer, gold):
        return True
    reply = runner.generate(JUDGE.format(question=question, gold="; ".join(gold[:8]), answer=answer[:300])).text
    m = re.search(r"\b(yes|no)\b", reply.lower())
    return bool(m and m.group(1) == "yes")


def judge(a) -> None:
    """Score every stated answer again with a judge model (Kimi K3) where exact matching marks it wrong: a correct
    answer worded differently from the gold ('Garowe' for 'Garoowe') is not a hallucination. Both scores are kept."""
    runner = _judge_runner(a.judge)
    items = {x["i"]: x for x in load_set(a.set)}
    out = {"judge": a.judge, "prompt": JUDGE, "files": {}}
    for path in sorted(RES.glob(f"answers_{a.set}*.json")):
        d = json.loads(path.read_text())
        res = {}
        for name, v in d["variants"].items():
            rows = []
            for x in v["per_question"]:
                it = items[x["i"]]
                ok = judged(runner, it["question"], it["answers"], x["text"] or x["claim"]) \
                    if x["status"] == "verified" else False
                first_ok = judged(runner, it["question"], it["answers"], x["first_answer"]) \
                    if not x["first_declined"] else False
                rows.append({"i": x["i"], "status": x["status"], "ambiguous": x["ambiguous"], "correct": ok,
                             "first_correct": first_ok, "first_declined": x["first_declined"]})
            n = len(rows)
            ver = [r for r in rows if r["status"] == "verified"]
            res[name] = {"verified": {"correct": sum(r["correct"] for r in ver) / n,
                                      "hallucinated": sum(not r["correct"] and not r["ambiguous"] for r in ver) / n,
                                      "other_meaning": sum(not r["correct"] and r["ambiguous"] for r in ver) / n,
                                      "unconfirmed": 1 - len(ver) / n},
                         "unchecked": {"correct": sum(r["first_correct"] for r in rows) / n,
                                       "wrong": sum(not r["first_correct"] and not r["first_declined"]
                                                    for r in rows) / n},
                         "per_question": rows}
            jv, ju = res[name]["verified"], res[name]["unchecked"]
            print(f"{path.stem:22s} {name:24s} judged: correct {jv['correct']:.3f} hallucinated "
                  f"{jv['hallucinated']:.3f} other meaning {jv['other_meaning']:.3f} | unchecked correct "
                  f"{ju['correct']:.3f} wrong {ju['wrong']:.3f}", flush=True)
        out["files"][path.name] = res
    closed_files = sorted(RES.glob(f"closed_{a.set}_*.json"))
    if closed_files:  # models alone on this set, judged the same way
        out["closed"] = {}
        for f in closed_files:
            b = json.loads(f.read_text())
            rows = [{"i": x["i"], "declined": x["declined"],
                     "correct": judged(runner, items[x["i"]]["question"], items[x["i"]]["answers"], x["answer"])
                     if not x["declined"] else False} for x in b["per_question"]]
            n = len(rows)
            out["closed"][b["model"]] = {"correct": sum(r["correct"] for r in rows) / n,
                                         "wrong": sum(not r["correct"] and not r["declined"] for r in rows) / n}
            print(f"{b['model']:30s} closed-book judged: {out['closed'][b['model']]}", flush=True)
    if a.set == "test":  # the closed-book models, judged the same way
        out["baselines"] = {}
        for f in sorted((ROOT / "results/eager").glob("baseline_*.json")):
            if f.stem.endswith("_para"):
                continue
            b = json.loads(f.read_text())
            rows = [{"i": x["i"], "declined": x["declined"],
                     "correct": judged(runner, items[x["i"]]["question"], items[x["i"]]["answers"], x["answer"])
                     if not x["declined"] else False} for x in b["per_question"]]
            n = len(rows)
            out["baselines"][b["model"]] = {"correct": sum(r["correct"] for r in rows) / n,
                                            "wrong": sum(not r["correct"] and not r["declined"] for r in rows) / n}
            print(f"{b['model']:30s} closed-book judged: {out['baselines'][b['model']]}", flush=True)
    save(RES / f"judged_{a.set}.json", out)
    print(f"judge calls: {runner.misses} new, {runner.hits} cached")


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
    ap.add_argument("part", choices=["select", "select-heldout", "fetch", "answer", "closed", "judge", "report"])
    ap.add_argument("--judge", default="kimi-k3")
    ap.add_argument("--model", default="qwen2.5:0.5b", help="closed: the model answering alone")
    ap.add_argument("--set", default="dev", choices=["dev", "test", "heldout"])
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--patient", type=float, default=120.0)
    ap.add_argument("--offline", action="store_true", help="fetch: from the cache only (answer always is)")
    ap.add_argument("--online", action="store_true", help="answer: fetch what the cache lacks (warm runs only)")
    ap.add_argument("--fresh", action="store_true")
    ap.add_argument("--offline-answers", action="store_true", help="model answers from the answer cache only")
    ap.add_argument("--variants", default="all")
    ap.add_argument("--budget", type=int, default=128)
    ap.add_argument("--min-coverage", type=float, default=1.0, help="share of the claim's words one unit must hold")
    ap.add_argument("--tag", default="", help="a separate results file (answers_<set><tag>.json)")
    ap.add_argument("--typed", action="store_true", help="a claim of the wrong kind is not support")
    ap.add_argument("--relation-cue", action="store_true", help="a sentence must state the asked relation")
    ap.add_argument("--by-name", action="store_true", help="also read what memory holds under the question's names")
    ap.add_argument("--hybrid", action="store_true", help="hybrid recall: keyword hits join the vector hits")
    ap.add_argument("--reader", default="", help="answer: replace the first reader (default: the variant's)")
    ap.add_argument("--subject-aware", action="store_true", help="look up when nothing recalled is about the subject")
    ap.add_argument("--out", default=None, help="write results and stores here (caches are still read from "
                                                "results/verified)")
    a = ap.parse_args()
    if a.out:
        RES = Path(a.out)
        RES.mkdir(parents=True, exist_ok=True)
    {"select": select, "select-heldout": select_heldout, "fetch": fetch, "answer": answer, "closed": closed,
     "judge": judge, "report": report}[a.part](a)

"""Reader bench (Phase 5): the same memory, read by models of every size.

The engine bench (scripts/engine_bench.py, results/bench/) scores what CAMR Personal's read path puts in front of a
model; this scores what the model then does with it. The engine bench writes, per question, the exact context the
app would give the model (results/bench/contexts_*.jsonl: question, LongMemEval type, gold answer, context). Each
reader answers every question twice with the app's own chat prompt: alone (no notes) and with that memory. A judge
decides right or wrong with LongMemEval's rules per question type (Wu et al., 2024: an updated answer must be the
new one; a temporal answer may be off by one day; a preference answer must use what the user said; an unanswerable
question is right only when the model says it cannot answer).

Per reader, ability and condition: right, wrong, declined ("I don't know"), and per question pair, help (wrong alone,
right with memory) and harm (right alone, wrong with memory); seconds per answer and prompt tokens; for Kimi K3 the
cost. Every answer and every verdict is cached by its exact request (results/readers/*.sqlite), so a report can be
rebuilt, and a run resumed, without calling a model again.

    python scripts/reader_bench.py estimate --contexts results/bench/contexts_baseline.jsonl   # cloud cost first
    python scripts/reader_bench.py run --contexts ... --readers qwen2.5:0.5b,qwen2.5:1.5b,qwen2.5:3b,kimi-k3
    python scripts/reader_bench.py report --tag baseline
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results/readers"

# Moonshot list price for kimi-k3, US$ per million tokens (as docs/FINDINGS.md F31); output includes reasoning
PRICE_IN, PRICE_OUT = 3.0, 15.0
# Kimi K3's mean output per call in this project (F31: 1.6 M output tokens over 6,456 calls, reasoning included),
# rounded up: used only to estimate before a run
EST_OUT_ANSWER, EST_OUT_JUDGE = 400, 300

NO_NOTES = "(no relevant notes)"

# ---------------------------------------------------------------------- judging (LongMemEval's rules)
_J_DEFAULT = ("I will give you a question, a correct answer, and a response from a model. Answer yes if the response "
              "contains the correct answer, otherwise no. If the response is equivalent to the correct answer or "
              "contains all the intermediate steps to get the correct answer, answer yes. If the response only "
              "contains a subset of the information required by the answer, answer no.{extra}\n\n"
              "Question: {question}\n\nCorrect answer: {answer}\n\nModel response: {response}\n\n"
              "Is the model response correct? Answer yes or no only.")
_J_TEMPORAL = (" Do not penalise off-by-one errors in the number of days, weeks or months (for example, 18 days for 19)"
               " when the question asks for a duration.")
_J_UPDATE = (" If the response contains some previous information along with an updated answer, it is correct as long"
             " as the updated answer is the required answer.")
_J_PREFERENCE = ("I will give you a question, a rubric for the desired personalised response, and a response from a "
                 "model. Answer yes if the response satisfies the desired response, otherwise no. The model does not "
                 "need to reflect every point in the rubric; it is correct as long as it recalls and uses the user's "
                 "personal information correctly.\n\nQuestion: {question}\n\nRubric: {answer}\n\n"
                 "Model response: {response}\n\nIs the model response correct? Answer yes or no only.")
_J_ABSTAIN = ("I will give you an unanswerable question, an explanation, and a response from a model. Answer yes if "
              "the model correctly identifies the question as unanswerable: it may say the information is incomplete, "
              "or that other information is given but not the information asked for.\n\nQuestion: {question}\n\n"
              "Explanation: {answer}\n\nModel response: {response}\n\nDoes the model correctly identify the question "
              "as unanswerable? Answer yes or no only.")


def unanswerable(row: dict) -> bool:
    return str(row["qid"]).endswith("_abs") or row.get("ability") == "A7"


def judge_prompt(row: dict, response: str) -> str:
    kind = row.get("type") or ""
    args = {"question": row["question"], "answer": row["answer"], "response": response.strip()[:1500]}
    if unanswerable(row):
        return _J_ABSTAIN.format(**args)
    if "preference" in kind or row.get("ability") == "A6":
        return _J_PREFERENCE.format(**args)
    extra = _J_TEMPORAL if "temporal" in kind else _J_UPDATE if "knowledge-update" in kind else ""
    return _J_DEFAULT.format(extra=extra, **args)


def verdict(text: str) -> bool | None:
    m = re.search(r"\b(yes|no)\b", text.strip().lower())
    return None if m is None else m.group(1) == "yes"


_DECLINE = re.compile(r"\b(?:i (?:do not|don't) know|not (?:mentioned|provided|stated|specified|available|sure)|"
                      r"(?:do not|don't|doesn't|does not) (?:have|mention|say|contain)|no (?:information|record|mention|"
                      r"notes?)\b|can(?:no|')t (?:assist|help|answer|find|tell|determine)|unable to|i'm not sure|"
                      r"(?:could|can) you (?:please )?(?:tell|share|provide|let me know))", re.I)


def declined(text: str) -> bool:
    """The model said it cannot answer (wider than camr.eval.escalation.abstention_like, which the research replays
    use and so stays as it is: this bench needs "not mentioned in the notes" and "can't assist" counted too)."""
    from camr.eval.escalation import abstention_like

    return bool(text.strip()) and (abstention_like(text) or bool(_DECLINE.search(text)))


def contains_gold(row: dict, response: str) -> bool:
    """The model-free check, kept beside the judge: does the response contain the gold answer (normalised)?"""
    from camr.eval.scoring import normalize_answer

    gold = normalize_answer(str(row["answer"]))
    return bool(gold) and gold in normalize_answer(response)


# ---------------------------------------------------------------------- readers
def reader(name: str):
    from camr.config import Config, LocalModelConfig
    from camr.models.runner import CachedRunner, OllamaRunner, build_ceiling_runner

    if name.startswith("kimi"):
        r = build_ceiling_runner(Config.load(ROOT / "results/learn/config.yaml").ceiling_model)
    else:
        # the app's own options (camr/app/assistant.py _runner), with a shorter answer cap for a bench
        r = OllamaRunner(LocalModelConfig(name=name, max_tokens=256, num_ctx=4096))
    return CachedRunner(r, OUT / "answers.sqlite")


def judge_runner(name: str):
    from camr.models.runner import CachedRunner

    return CachedRunner(reader(name).runner, OUT / "judge.sqlite")


def prompt_for(row: dict, with_memory: bool) -> str:
    from camr.app.assistant import CHAT_PROMPT

    notes = (row.get("context") or "").strip() if with_memory else ""
    # extra keys are ignored by str.format, so a prompt that names {today} (Phase 2) gets the question's date
    return CHAT_PROMPT.format(notes=notes or NO_NOTES, history="(none)", question=row["question"],
                              today=row.get("question_date") or "")


def load_rows(path: Path, limit: int = 0) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    return rows[:limit] if limit else rows


# ---------------------------------------------------------------------- estimate
def estimate(a) -> dict:
    rows = load_rows(Path(a.contexts), a.limit)
    n_cloud = sum(r.startswith("kimi") for r in a.readers.split(","))
    n_readers = len(a.readers.split(","))
    chars_in = sum(len(prompt_for(r, True)) + len(prompt_for(r, False)) for r in rows)
    ans_in = n_cloud * chars_in / 4
    ans_out = n_cloud * 2 * len(rows) * EST_OUT_ANSWER
    judge_calls = (n_readers * 2 * len(rows)) if a.judge.startswith("kimi") else 0
    judge_in = judge_calls * 260
    judge_out = judge_calls * EST_OUT_JUDGE
    usd = (ans_in + judge_in) * PRICE_IN / 1e6 + (ans_out + judge_out) * PRICE_OUT / 1e6
    est = {"questions": len(rows), "readers": n_readers, "cloud_reader_calls": n_cloud * 2 * len(rows),
           "judge_calls": judge_calls, "est_input_tokens": int(ans_in + judge_in),
           "est_output_tokens": int(ans_out + judge_out), "est_usd_upper": round(usd, 2),
           "note": "before caching; cached answers and verdicts cost nothing"}
    print(json.dumps(est, indent=1))
    return est


# ---------------------------------------------------------------------- run
def run(a) -> None:
    from camr.eval.escalation import abstention_like

    contexts = Path(a.contexts)
    rows = load_rows(contexts, a.limit)
    tag = a.tag or contexts.stem.replace("contexts_", "")
    OUT.mkdir(parents=True, exist_ok=True)
    est = estimate(a)
    if est["est_usd_upper"] > a.max_usd:
        sys.exit(f"estimated up to ${est['est_usd_upper']} > --max-usd {a.max_usd}: not run")
    jr = judge_runner(a.judge) if a.judge != "contains" else None
    out_path = OUT / f"answers_{tag}.jsonl"
    done = {(d["reader"], d["qid"], d["memory"]) for d in map(json.loads, out_path.read_text().splitlines())} \
        if out_path.exists() else set()

    def judge(row, text):
        if jr is None:
            return contains_gold(row, text) if not unanswerable(row) else declined(text), None
        try:
            g = jr.generate(judge_prompt(row, text))
        except Exception as exc:  # noqa: BLE001  (a failed verdict is recorded, not fatal)
            return None, f"judge error: {type(exc).__name__}"
        return verdict(g.text), g

    for name in a.readers.split(","):
        r = reader(name)
        todo = [(row, mem) for row in rows for mem in (False, True) if (name, row["qid"], mem) not in done]
        print(f"{name}: {len(todo)} answers to make", flush=True)
        t_reader = time.perf_counter()

        def one(job):
            row, mem = job
            try:
                g = r.generate(prompt_for(row, mem))
                text, err = g.text, None
            except Exception as exc:  # noqa: BLE001
                g, text, err = None, "", f"{type(exc).__name__}: {exc}"[:200]
            ok, jg = judge(row, text) if not err else (None, None)
            return {"reader": name, "qid": row["qid"], "ability": row.get("ability"), "suite": row.get("suite"),
                    "type": row.get("type"), "memory": mem, "answer": text.strip()[:600], "error": err,
                    "correct": ok, "contains_gold": contains_gold(row, text) if not unanswerable(row) else None,
                    "declined": declined(text), "abstained_engine": row.get("abstained"),
                    "prompt_tokens": getattr(g, "prompt_tokens", None),
                    "output_tokens": getattr(g, "generated_tokens", None),
                    "seconds": round(getattr(g, "latency_ms", 0.0) / 1000, 3),
                    "cached": bool(getattr(g, "meta", {}).get("cached")),
                    "judge_in": getattr(jg, "prompt_tokens", None) if jg else None,
                    "judge_out": getattr(jg, "generated_tokens", None) if jg else None}

        # local models answer one at a time (one Ollama model, in order); the cloud reader in a few parallel calls
        workers = a.cloud_workers if name.startswith("kimi") else 1
        with ThreadPoolExecutor(workers) as pool, out_path.open("a") as fh:
            for k, rec in enumerate(pool.map(one, todo), 1):
                fh.write(json.dumps(rec) + "\n")
                fh.flush()
                if k % 50 == 0:
                    print(f"  {name}: {k}/{len(todo)}", flush=True)
        print(f"{name}: done in {time.perf_counter() - t_reader:.0f} s", flush=True)
    report(argparse.Namespace(tag=tag))


# ---------------------------------------------------------------------- report
ABILITY = {"A1": "recall a fact", "A2": "join facts", "A3": "fact changed", "A4": "time", "A5": "counting",
           "A6": "preference", "A7": "say I don't know"}


def report(a) -> None:
    tag = a.tag
    recs = [json.loads(line) for line in (OUT / f"answers_{tag}.jsonl").read_text().splitlines() if line.strip()]
    pairs: dict[tuple, dict] = {}
    for r in recs:
        pairs.setdefault((r["reader"], r["qid"]), {})[r["memory"]] = r
    readers = list(dict.fromkeys(r["reader"] for r in recs))
    abilities = sorted({r["ability"] for r in recs if r["ability"]})

    def pct(xs):
        xs = [x for x in xs if x is not None]
        return f"{100 * sum(xs) / len(xs):.0f}%" if xs else "–"

    lines = [f"# Reader bench: {tag}", "",
             "Each reader answers every question alone and with what CAMR Personal's memory admitted (the app's own "
             "chat prompt). Right/wrong by the judge with LongMemEval's per-type rules; help = wrong alone and right "
             "with memory, harm = right alone and wrong with memory.", "",
             "## Overall", "", "| Reader | right alone | right with memory | help | harm | declined with memory "
             "| s per answer (memory) | prompt tokens (memory) |", "|---|---|---|---|---|---|---|---|"]
    summary = {}
    for name in readers:
        ps = [p for (rd, _), p in pairs.items() if rd == name and False in p and True in p]
        alone = [p[False]["correct"] for p in ps]
        mem = [p[True]["correct"] for p in ps]
        help_ = sum(1 for p in ps if p[False]["correct"] is False and p[True]["correct"] is True)
        harm = sum(1 for p in ps if p[False]["correct"] is True and p[True]["correct"] is False)
        secs = [p[True]["seconds"] for p in ps if p[True]["seconds"]]
        toks = [p[True]["prompt_tokens"] for p in ps if p[True]["prompt_tokens"]]
        summary[name] = {"n": len(ps), "right_alone": pct(alone), "right_memory": pct(mem), "help": help_, "harm": harm}
        lines.append(f"| {name} | {pct(alone)} | {pct(mem)} | {help_} | {harm} | {pct([p[True]['declined'] for p in ps])}"
                     f" | {sum(secs) / len(secs) if secs else 0:.2f} | {int(sum(toks) / len(toks)) if toks else '–'} |")
    lines += ["", "## Right with memory, by ability (right alone in brackets)", "",
              "| Ability | " + " | ".join(readers) + " |", "|---|" + "---|" * len(readers)]
    for ab in abilities:
        cells = []
        for name in readers:
            ps = [p for (rd, _), p in pairs.items() if rd == name and True in p and False in p
                  and p[True]["ability"] == ab]
            cells.append(f"{pct([p[True]['correct'] for p in ps])} ({pct([p[False]['correct'] for p in ps])}) "
                         f"n={len(ps)}")
        lines.append(f"| {ab} {ABILITY.get(ab, '')} | " + " | ".join(cells) + " |")
    cloud = [r for r in recs if r["reader"].startswith("kimi") and not r["cached"]]
    jin = sum(r["judge_in"] or 0 for r in recs)
    jout = sum(r["judge_out"] or 0 for r in recs)
    cin = sum(r["prompt_tokens"] or 0 for r in cloud)
    cout = sum(r["output_tokens"] or 0 for r in cloud)
    usd = (cin + jin) * PRICE_IN / 1e6 + (cout + jout) * PRICE_OUT / 1e6
    lines += ["", f"Cloud tokens this report covers: Kimi as reader {cin:,} in / {cout:,} out; judge {jin:,} in / "
              f"{jout:,} out; about ${usd:.2f} at list price (cached calls are counted when first made). "
              f"Judge disagreements with the model-free contains-gold check: "
              f"{sum(1 for r in recs if r['contains_gold'] is not None and r['correct'] is not None and r['contains_gold'] != r['correct'])}"
              f" of {sum(1 for r in recs if r['contains_gold'] is not None and r['correct'] is not None)}."]
    (OUT / f"report_{tag}.md").write_text("\n".join(lines) + "\n")
    (OUT / f"summary_{tag}.json").write_text(json.dumps(summary, indent=1))
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["estimate", "run", "report"])
    ap.add_argument("--contexts", default=str(ROOT / "results/bench/contexts_baseline.jsonl"))
    ap.add_argument("--readers", default="qwen2.5:0.5b,qwen2.5:1.5b,qwen2.5:3b,kimi-k3")
    ap.add_argument("--judge", default="kimi-k3", help="kimi-k3, or 'contains' (model-free, for smoke tests)")
    ap.add_argument("--tag", default="")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--max-usd", type=float, default=25.0, help="refuse to start above this estimated cloud cost")
    ap.add_argument("--cloud-workers", type=int, default=4)
    a = ap.parse_args()
    {"estimate": estimate, "run": run, "report": report}[a.part](a)

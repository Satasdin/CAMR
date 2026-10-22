"""Phase 2 before/after: the engine bench run once per change (scripts/engine_bench.py with --flags), compared.

    python scripts/phase2_compare.py      # results/bench/phase2/*/records -> results/bench/phase2/README.md, compare.json

Steps add one change at a time on top of the one before; budget-* and compress-* variants sit on top of step 3
(dates, profile, aggregate; no slot gate), so the context budget can be chosen by pass rate per context token.
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camr.eval.abilities import ABILITIES, ANSWERABLE, scorecard, wilson  # noqa: E402

P2 = ROOT / "results" / "bench" / "phase2"
BASE = ROOT / "results" / "bench" / "records"
STEPS = [("baseline", BASE, "committed baseline (bench/engine-bench)"),
         ("step0-before", P2 / "step0-before" / "records", "Phase 2 code, every new flag off (+ forget fix)"),
         ("step1-dates", P2 / "step1-dates" / "records", "+ dated_context, time_filter"),
         ("step2-profile", P2 / "step2-profile" / "records", "+ profile, entity_gate_skip_time"),
         ("step3-aggregate", P2 / "step3-aggregate" / "records", "+ aggregate"),
         ("step4-compress", P2 / "compress-384" / "records", "+ compress (sentences, 384 tokens), chosen below"),
         ("step5-slot-v1", P2 / "step5-slot-v1" / "records", "step 3 + slot_gate as first written (dropped)"),
         ("step5-final", P2 / "step5-final" / "records", "step 4 + slot_gate = CAMR Personal's configuration")]
VARIANTS = [("step3-aggregate", "384 tokens, whole notes"), ("budget-512", "512 tokens, whole notes"),
            ("budget-768", "768 tokens, whole notes"), ("compress-384", "384 tokens, compressed notes"),
            ("compress-512", "512 tokens, compressed notes"), ("chunk60-384", "384 tokens, 60-token chunks")]
# abilities a bigger context could change; the curve reads their LongMemEval and needle questions
BUDGETED = ("A1", "A2", "A3", "A4", "A6")


def records(d: Path) -> list[dict]:
    return [json.loads(line) for p in sorted(d.glob("*.jsonl")) for line in p.read_text().splitlines() if line.strip()]


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


# The headline, scored with the answer-survives rule (LongMemEval records re-run with it, results/bench/phase2/rescore;
# the CAMR probes, needles and checks have no LongMemEval evidence, so their records stand as they were scored).
HEADLINE = [("baseline", [BASE / "camr.jsonl", BASE / "a8.jsonl", BASE / "scale.jsonl",
                          P2 / "rescore" / "baseline" / "records" / "lme.jsonl"], "the read path before Phase 2"),
            ("phase2-compressed", [P2 / "step5-final" / "records" / f for f in ("camr.jsonl", "a8.jsonl", "scale.jsonl")]
             + [P2 / "rescore" / "final" / "records" / "lme.jsonl"],
             "Phase 2 as first shipped: compression at 384 tokens (reversed)"),
            ("phase2b", [P2 / "phase2b" / "records" / f for f in ("camr.jsonl", "a8.jsonl", "lme.jsonl", "scale.jsonl")],
             "CAMR Personal now: whole notes at 512 tokens, tightened profile notes")]


def headline() -> list[str]:
    cols = [(n, [json.loads(x) for f in fs if f.exists() for x in f.read_text().splitlines() if x.strip()], why)
            for n, fs, why in HEADLINE]
    cols = [c for c in cols if c[1]]
    if not cols:
        return []
    cards = {n: scorecard(rs) for n, rs, _ in cols}
    L = ["## Before and after (answer must survive)", "",
         "| | Ability | " + " | ".join(n for n, _, _ in cols) + " |", "|---|---|" + "---|" * len(cols)]
    for ab in ABILITIES:
        L.append(f"| {ab} | {ABILITIES[ab]} | " + " | ".join(
            pct(cards[n][ab]["pass_rate"]) + (f" ({cards[n][ab]['n']})" if i == 0 else "") for i, (n, _, _) in
            enumerate(cols)) + " |")
    L += ["", "| Run | Mean context tokens | Distractor share | Profile lines (questions reached) |", "|---|---|---|---|"]
    for n, rs, why in cols:
        q = [r for r in rs if r.get("rule") and r["suite"].startswith("lme")]
        prof = [r for r in q if r.get("context_text") is not None]
        lines = sum(r["context_text"].count("[about the user]") for r in prof)
        reached = sum(1 for r in prof if "[about the user]" in r["context_text"])
        L.append(f"| {n}: {why} | {statistics.fmean(r['context_tokens'] for r in q):.0f} | "
                 f"{pct(statistics.fmean(r['distractor_share'] for r in q))} | "
                 + (f"{lines} ({reached} of {len(prof)} LongMemEval questions)" if prof else "–") + " |")
    return L + [""]


def main() -> None:
    have = [(n, d, why) for n, d, why in STEPS if d.exists() and any(d.glob("*.jsonl"))]
    cards = {n: scorecard(records(d)) for n, d, _ in have}
    out = {"steps": {n: {ab: {k: v for k, v in s.items() if k != "suites"} for ab, s in c.items()}
                     for n, c in cards.items()}}
    corr = P2 / "correction.md"  # a later re-scoring that supersedes part of these tables
    L = ["# Phase 2: closing the gaps the engine bench found", "",
         *([corr.read_text().rstrip(), ""] if corr.exists() else []),
         *headline(),
         "## Step by step, first scoring rule (history)", "",
         "Kept as the record of how each change was measured. This rule counted a needed fact once a note of its "
         "turn reached the context; it overstates compression (step 4 and step 5) badly and whole-note rows a "
         "little (an answer can sit in another 120-token chunk of the turn). The headline above and "
         "rescore/README.md use the answer-survives rule.", "",
         "Each step turns on one more change (a MemoryConfig flag, off by default) and re-runs the whole engine "
         "bench: 260 LongMemEval questions, the CAMR probes, the needle stores at 1k/10k/100k, the forget and "
         "privacy checks. Pass rates per ability (n in the baseline column).", "",
         "| | Ability | " + " | ".join(n for n, _, _ in have) + " |",
         "|---|---|" + "---|" * len(have)]
    for ab in ABILITIES:
        cells = []
        for n, _, _ in have:
            s = cards[n][ab]
            cells.append(f"{pct(s['pass_rate'])}" + (f" ({s['n']})" if n == have[0][0] else ""))
        L.append(f"| {ab} | {ABILITIES[ab]} | " + " | ".join(cells) + " |")
    L += ["", "Steps: " + "; ".join(f"**{n}** {why}" for n, _, why in have) + ".", ""]
    # read-path cost per step
    L += ["| Step | Mean context tokens | Distractor share | Retrieval ms p50 / p95 | Gate precision / specificity |",
          "|---|---|---|---|---|"]
    for n, d, _ in have:
        rs = [r for r in records(d) if r.get("rule")]
        ms = sorted(r["retrieval_ms"] for r in rs)
        g = cards[n]["A10"]["gate"]
        L.append(f"| {n} | {statistics.fmean(r['context_tokens'] for r in rs):.0f} | "
                 f"{pct(statistics.fmean(r['distractor_share'] for r in rs))} | {ms[len(ms) // 2]:.1f} / "
                 f"{ms[int(0.95 * (len(ms) - 1))]:.1f} | {pct(g['precision'])} / {pct(g['specificity'])} |")
    # budget curve
    curve = []
    sub_file = P2 / "chunk60-qids.txt"  # the 60-token-chunk variant ran on a stratified slice of questions
    sub = set(sub_file.read_text().split(",")) if sub_file.exists() else set()
    variants = VARIANTS + ([("step3-aggregate@slice", "384 tokens, whole notes (same slice as chunk60)")]
                           if sub else [])
    for name, why in variants:
        d = P2 / name.split("@")[0] / "records"
        if not d.exists():
            continue
        rs = [r for r in records(d) if r.get("ability") in BUDGETED and r.get("rule") in ANSWERABLE
              and (r["suite"].startswith("lme") or r["suite"].startswith("needle"))]
        if name.endswith("@slice") or name.startswith("chunk60"):
            rs = [r for r in rs if r["qid"] in sub]
        if not rs:
            continue
        k = sum(r["passed"] for r in rs)
        tok = statistics.fmean(r["context_tokens"] for r in rs)
        by = {ab: (pct(sum(r["passed"] for r in rs if r["ability"] == ab) / sum(r["ability"] == ab for r in rs))
                   if any(r["ability"] == ab for r in rs) else "–") for ab in BUDGETED}
        curve.append({"variant": name, "what": why, "n": len(rs), "pass_rate": k / len(rs), "ci95": wilson(k, len(rs)),
                      "context_tokens": tok, "pass_per_100_tokens": 100 * k / len(rs) / tok, **by})
    if curve:
        out["budget_curve"] = curve
        L += ["", "## Context budget", "",
              f"LongMemEval and needle questions of {', '.join(BUDGETED)} (answerable), on top of step 3. Prefill "
              "time grows with the context, so the choice is made by pass rate per context token among variants "
              "that stay at or under 512 tokens of context on average.", "",
              "| Variant | Context | n | Pass (95% CI) | Mean context tokens | Pass per 100 tokens | "
              + " | ".join(BUDGETED) + " |", "|---|---|---|---|---|---|" + "---|" * len(BUDGETED)]
        for c in curve:
            ci = c["ci95"]
            L.append(f"| {c['variant']} | {c['what']} | {c['n']} | {pct(c['pass_rate'])} ({ci[0] * 100:.0f}–"
                     f"{ci[1] * 100:.0f}) | {c['context_tokens']:.0f} | {c['pass_per_100_tokens']:.2f} | "
                     + " | ".join(c[ab] for ab in BUDGETED) + " |")
    notes = P2 / "notes.md"  # hand-written: decisions, targets, checks
    if notes.exists():
        L += ["", notes.read_text().rstrip()]
    (P2 / "compare.json").write_text(json.dumps(out, indent=1, default=str))
    (P2 / "README.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

"""Phase 2 re-scored: a needed fact counts only if its answer survives in the context the reader sees.

    python scripts/phase2_rescore.py      # results/bench/phase2/rescore/*/records -> rescore/README.md, rescore.json

The first scoring counted a needed turn as reached when any note of it was admitted. Compression (keeping a note's
sentences that share words with the question) and chunking (a long turn split in 120-token notes) can admit a note
of the turn without the sentence that holds the answer. Each LongMemEval question now names its evidence (the gold
answer when the turn says it, else the turn's sentence most like the gold answer; when neither can be told, a note
of the turn must be shown whole), and passes only if that evidence is in the rendered context.
"""

from __future__ import annotations

import json
import statistics
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from camr.eval.abilities import ANSWERABLE, wilson  # noqa: E402

RS = ROOT / "results" / "bench" / "phase2" / "rescore"
RUNS = [("baseline", "baseline read path (every Phase 2 flag off)"),
        ("step3-aggregate", "dates, time filter, profile, aggregate; 384 tokens, whole notes"),
        ("budget-512", "step 3 at 512 tokens, whole notes"),
        ("budget-768", "step 3 at 768 tokens, whole notes"),
        ("compress-384", "step 3 + compression, 384 tokens"),
        ("compress-512", "step 3 + compression, 512 tokens"),
        ("final", "CAMR Personal's Phase 2 configuration (compression 384 + slot gate)")]
ABS = ("A1", "A2", "A3", "A4", "A6", "A7")
BUDGETED = ("A1", "A2", "A3", "A4", "A6")


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.0f}%"


def main() -> None:
    rows, out = [], {}
    for name, why in RUNS:
        f = RS / name / "records" / "lme.jsonl"
        if not f.exists():
            continue
        rs = [json.loads(line) for line in f.read_text().splitlines() if line.strip()]
        by = {ab: [r for r in rs if r["ability"] == ab] for ab in ABS}
        ans = [r for r in rs if r["ability"] in BUDGETED and r["rule"] in ANSWERABLE]
        k = sum(r["passed"] for r in ans)
        tok = statistics.fmean(r["context_tokens"] for r in ans)
        old = sum(1 for r in ans if r["reached"] == r["needed"])  # the first rule: every needed note reached
        lost = Counter(m for r in rs for m in r["misses"] if m in ("answer cut", "answer in another chunk"))
        ev = Counter(e for r in ans for e in r.get("evidence", []))
        kinds = {}
        for kind in ("string", "sentence", "none"):  # questions whose needed facts all have this kind of evidence
            sub = [r for r in ans if r.get("evidence") and set(r["evidence"]) == {kind}]
            kinds[kind] = (sum(r["passed"] for r in sub) / len(sub), len(sub)) if sub else (None, 0)
        item = {"name": name, "what": why, "n": len(ans), "pass": k / len(ans), "ci95": wilson(k, len(ans)),
                "by_evidence": kinds,
                "old_rule_pass": old / len(ans), "context_tokens": tok, "pass_per_100_tokens": 100 * k / len(ans) / tok,
                "answer_cut": lost["answer cut"], "answer_in_other_chunk": lost["answer in another chunk"],
                "evidence": dict(ev),
                **{ab: (sum(r["passed"] for r in v) / len(v) if v else None) for ab, v in by.items()}}
        rows.append(item)
        out[name] = item
    L = ["# Phase 2 re-scored: the answer must survive", "", __doc__.split("\n\n", 2)[2].strip(), "",
         "LongMemEval only (260 questions; the CAMR probes and needles are notes of one or two sentences, which "
         "compression leaves whole). Pass rates per ability, and over the 230 answerable questions of A1-A4 and A6:",
         "", "| Run | A1 | A2 | A3 | A4 | A6 | A7 | Answerable pass (95% CI) | First rule | Mean context tokens | "
         "Pass per 100 tokens | Answer cut / in another chunk |",
         "|---|---|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        ci = r["ci95"]
        L.append(f"| {r['name']} | " + " | ".join(pct(r[ab]) for ab in ABS)
                 + f" | {pct(r['pass'])} ({ci[0] * 100:.0f}–{ci[1] * 100:.0f}) | {pct(r['old_rule_pass'])} | "
                 f"{r['context_tokens']:.0f} | {r['pass_per_100_tokens']:.3f} | {r['answer_cut']} / "
                 f"{r['answer_in_other_chunk']} |")
    if rows:
        ns = rows[0]["by_evidence"]
        L += ["", "By the kind of evidence the needed facts have (answerable A1-A4, A6). *Gold answer in the turn* is "
              "the most objective: the reader needs that exact string.", "",
              f"| Run | Gold answer in the turn (n={ns['string'][1]}) | Sentence most like the answer "
              f"(n={ns['sentence'][1]}) | Nothing to check: a note shown whole (n={ns['none'][1]}) |",
              "|---|---|---|---|"]
        for r in rows:
            b = r["by_evidence"]
            L.append(f"| {r['name']} | {pct(b['string'][0])} | {pct(b['sentence'][0])} | {pct(b['none'][0])} |")
    L += ["", "Runs: " + "; ".join(f"**{r['name']}** {r['what']}" for r in rows) + ".", "",
          "Evidence used (answerable questions' needed facts): " + (
              ", ".join(f"{k} {v}" for k, v in rows[0]["evidence"].items()) if rows else "–") + "."]
    RS.mkdir(parents=True, exist_ok=True)
    (RS / "rescore.json").write_text(json.dumps(out, indent=1, default=str))
    (RS / "README.md").write_text("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()

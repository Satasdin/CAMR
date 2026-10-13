"""Tune the read path's admission margin (delta) and token budget (B) on a validation split, then
test the chosen setting once on held-out questions. No language model is needed.

The read path admits a note when its similarity is within delta of the best note (Eq. 5.3) and
packs admitted notes into at most B tokens (Eq. 5.4). The study fixed delta = 0.15 and B = 512 by
design. Here they are chosen by a stated objective on the validation half of the 500 HotpotQA
and 500 2WikiMultiHopQA retrieval questions, and checked on the other half:

    J(delta, B) = support_all - mu * context_tokens / 1000,   mu = 0.1

(the same per-token cost mu as the learned router's reward). support_all is the share of
questions whose gold supporting paragraphs are all in the context. The abstain threshold tau is
not tuned here: on these questions every memory is on-topic, so tau could only lose recall; it
is calibrated separately on off-topic similarity (scripts/calibrate_gating.py).

    python scripts/tune_gating.py --store-copy <scratch>/retrieval_eval   # copies the store first
"""

from __future__ import annotations

import argparse
import json
import random
import shutil
from pathlib import Path

from camr.config import Config
from camr.harness.experiment import Workspace
from camr.harness.retrieval_eval import evaluate

ROOT = Path(__file__).resolve().parents[1]
MU = 0.1
MARGINS = (0.05, 0.10, 0.15, 0.20, 0.30, None)  # None = no margin (admit by rank until the budget is full)
BUDGETS = (256, 512, 768, 1024)
BENCHES = ("hotpotqa", "2wikimultihopqa")


class CachedEmbedder:
    """Wraps the embedder so each question is embedded once across the whole grid."""

    def __init__(self, inner):
        self.inner, self.cache = inner, {}
        self.name, self.dim = inner.name, inner.dim

    def encode(self, texts, *, is_query=False):
        if not is_query:
            return self.inner.encode(texts, is_query=False)
        import numpy as np
        miss = [t for t in texts if t not in self.cache]
        if miss:
            for t, v in zip(miss, self.inner.encode(miss, is_query=True)):
                self.cache[t] = v
        return np.vstack([self.cache[t] for t in texts])

    def encode_one(self, text, *, is_query=False):
        return self.encode([text], is_query=is_query)[0]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--store-copy", required=True, help="scratch directory for a copy of results/retrieval_eval")
    ap.add_argument("--out", default=str(ROOT / "results/retrieval_eval/tables/gating_tuning.json"))
    a = ap.parse_args()
    src, dst = ROOT / "results/retrieval_eval", Path(a.store_copy)
    if not (dst / "camr.sqlite").exists():  # evaluation resets access counters; never touch the original
        dst.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src / "camr.sqlite", dst / "camr.sqlite")
        shutil.copytree(src / "samples", dst / "samples", dirs_exist_ok=True)
    cfg = Config.load(ROOT / "configs/retrieval_eval.yaml")  # the config that built the store (both benchmarks)
    ws = Workspace(cfg, run_dir=dst)
    ws._embedder = CachedEmbedder(ws.embedder)
    base = cfg.with_overrides({"memory": {"write_policy": "verbatim", "screening": True,
                                          "retrieval_policy": "similarity_only", "expansion": "entity",
                                          "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0}}})
    rng = random.Random(13)
    splits = {}
    for b in BENCHES:
        qs = [q for q in ws.sample(b) if q.support]
        rng.shuffle(qs)
        splits[b] = {"val": qs[: len(qs) // 2], "test": qs[len(qs) // 2:]}

    def score(margin, budget, split):
        over = {"similarity_margin": margin, "token_budget": budget}
        cfg_v = base.with_overrides({"memory": over})
        rows = [evaluate(ws, f"d{margin}-B{budget}", cfg_v, b, splits[b][split]).as_dict() for b in BENCHES]
        n = sum(r["n"] for r in rows)
        sa = sum(r["support_all"] * r["n"] for r in rows) / n
        tok = sum(r["mean_context_tokens"] * r["n"] for r in rows) / n
        return {"margin": margin, "budget": budget, "split": split, "n": n, "support_all": sa,
                "mean_tokens": tok, "J": sa - MU * tok / 1000,
                "by_bench": {r["benchmark"]: {"support_all": r["support_all"], "tokens": r["mean_context_tokens"]}
                             for r in rows}}

    grid = []
    for m in MARGINS:
        for bud in BUDGETS:
            g = score(m, bud, "val")
            grid.append(g)
            print(f"val delta={m} B={bud}: support_all={g['support_all']:.3f} tokens={g['mean_tokens']:.0f} J={g['J']:.3f}",
                  flush=True)
    best = max(grid, key=lambda g: (round(g["J"], 6), -g["budget"]))
    test = {"selected": score(best["margin"], best["budget"], "test"),
            "study default (0.15, 512)": score(0.15, 512, "test")}
    out = {"objective": f"support_all - {MU} * tokens / 1000", "margins": MARGINS, "budgets": BUDGETS,
           "n_val": grid[0]["n"], "validation_grid": grid, "selected": {"margin": best["margin"], "budget": best["budget"]},
           "test": test}
    Path(a.out).write_text(json.dumps(out, indent=2))
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "by_bench"} for k, v in test.items()}, indent=1))


if __name__ == "__main__":
    main()

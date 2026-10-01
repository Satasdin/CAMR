"""Calibrate the gating (abstain) threshold for an embedder on real HotpotQA data.

Gating abstains when the best note's cosine similarity is below a threshold. The
benchmarks used BGE-small with 0.50. Another embedder has a different cosine scale,
so the threshold is re-derived the same way for each:

* "relevant": cosine of a question to its own gold supporting paragraph;
* "irrelevant": cosine of a question to the best paragraph of a *different*
  question's context (a realistic off-topic memory).

    python scripts/calibrate_gating.py --embedder bge        # reference
    python scripts/calibrate_gating.py --embedder ollama:nomic-embed-text
"""

from __future__ import annotations

import argparse
import json
import random

import numpy as np

from camr.config import EmbedderConfig
from camr.harness.benchmarks import load_questions
from camr.memory.embedder import BGEEmbedder, OllamaEmbedder


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--embedder", default="bge")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--data", default="data/hotpotqa/hotpot_dev_distractor_v1.json")
    a = ap.parse_args()
    if a.embedder == "bge":
        emb = BGEEmbedder(EmbedderConfig())
    else:
        emb = OllamaEmbedder(a.embedder.split(":", 1)[1])
    qs = [q for q in load_questions("hotpotqa", a.data) if q.support]
    rng = random.Random(13)
    qs = rng.sample(qs, a.n)
    qv = emb.encode([q.question for q in qs], is_query=True)
    rel, irr = [], []
    for i, q in enumerate(qs):
        gold = [f"{t}: {p}" for t, p in q.context if t in q.support]
        other = qs[(i + 1) % len(qs)]
        off = [f"{t}: {p}" for t, p in other.context]
        g = emb.encode(gold)
        o = emb.encode(off)
        rel.append(float((g @ qv[i]).max()))
        irr.append(float((o @ qv[i]).max()))
    rel, irr = np.array(rel), np.array(irr)
    out = {"embedder": emb.name, "n": a.n,
           "relevant": {p: round(float(np.percentile(rel, p)), 3) for p in (5, 10, 25, 50)},
           "irrelevant": {p: round(float(np.percentile(irr, p)), 3) for p in (50, 75, 90, 95)}}
    # The benchmarks' BGE threshold (0.50) sits at the 90th percentile of off-topic similarities
    # (0.494 measured): abstain on ~90% of off-topic memories. The same rule transfers it to another embedder.
    thr = round(float(np.percentile(irr, 90)), 2)
    out["min_similarity_same_rule_as_benchmarks"] = thr
    out["relevant_kept"] = round(float((rel >= thr).mean()), 3)
    out["irrelevant_rejected"] = round(float((irr < thr).mean()), 3)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()

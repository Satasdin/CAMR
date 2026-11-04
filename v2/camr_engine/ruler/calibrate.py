"""Choosing the old CAMR's similarity threshold for the MLX embedder, on the development lives (seed 0) only.

The threshold was tuned for the app's old embedder; with a new one it must be re-chosen, or the old CAMR is handicapped.
The choice uses retrieval alone, so no answer is generated: after the whole life is stored, a told question counts if
the context the engine packs names the right answer, and an untold one counts if the engine declines. Of the
thresholds with the most counts over the three lives, the middle one wins (DECISIONS.md E-04). Proof lives (seed 1)
are never used here.

  python -m camr_engine.ruler.calibrate
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from camr_engine.ruler.grade import names
from camr_engine.ruler.harness import RECORDS
from camr_engine.ruler.life import DAYS, PERSONAS, build

THRESHOLDS = [0.55, 0.60, 0.65, 0.70, 0.75, 0.80]


def main() -> int:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    from camr_engine.models import Embedder
    from camr_engine.ruler.contenders import CamrText

    embedder = Embedder()
    table: dict[str, dict[str, dict[str, int]]] = {}
    for persona in sorted(PERSONAS):
        life = build(persona, 0)
        camr = CamrText(None, embedder, RECORDS.parent / "work" / f"calibrate-{persona}", THRESHOLDS[0])
        for day in life.days:
            camr.observe(day)
        camr.begin_quiz(life.days[-1].date)
        table[persona] = {}
        for t in THRESHOLDS:
            camr.engine.min_similarity = t
            found = declined = 0
            for q in life.questions:
                rec = camr.engine.recall(q.text, touch=False)
                right = q.answer_on(DAYS - 1)
                gave = rec.context if not rec.abstained else ""
                if right is not None:
                    found += names(gave, right[1])
                else:
                    declined += not gave.strip()
            table[persona][f"{t:.2f}"] = {"found": found, "declined": declined, "total": found + declined}
            print(f"{persona:10s} {t:.2f}: answer in context {found:3d}, declined when untold {declined:3d}", flush=True)
        camr.close()
    totals = {t: sum(table[p][t]["total"] for p in table) for t in table[next(iter(table))]}
    top = sorted(t for t in totals if totals[t] == max(totals.values()))
    best = top[len(top) // 2]  # the middle of the best plateau: furthest from where it starts to get worse
    out = RECORDS / "calibration" / "camr-min-similarity.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"embedder": embedder.name, "lives": "seed 0, all personas, end of week 12",
                               "per_life": table, "totals": totals, "chosen": float(best)}, indent=1))
    print("chosen", best, "->", out)
    return 0


if __name__ == "__main__":
    sys.exit(main())

"""Escalation curve: the practical bridge (docs/BRIDGING_THE_GAP.md section 3.4).

A deployable hybrid answers locally with memory and sends only the
least-confident queries to the cloud.  This module simulates that policy from
logs alone, without extra model calls.  For each escalation rate f, the f·n
lowest-confidence treatment answers are replaced by the logged ceiling answers.

Confidence is local and cheap.  An abstention-like answer ("unknown", "I don't
know", empty) ranks below any substantive one, and ties break by retrieval
strength (top note similarity), so weak memory escalates first.

Two reference curves bound the router:
* random: escalate a random f·n queries (expected value, no learning);
* oracle: escalate exactly the queries where the cloud is right and the local
  answer wrong, the best any router could do.
"""

from __future__ import annotations

import re
import sqlite3
from collections import defaultdict

from camr.eval.analysis import _latest_runs, _queries

_ABSTAIN = re.compile(
    r"^\s*(unknown|i\s+don'?t\s+know|i\s+do\s+not\s+know|not\s+sure|no\s+answer|n/?a|none|cannot\s+be\s+determined"
    r"|i'?m\s+not\s+sure|i\s+cannot|i\s+can'?t)\b",
    re.IGNORECASE,
)

DEFAULT_RATES = (0.0, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5, 1.0)


def abstention_like(answer: str | None) -> bool:
    return not (answer or "").strip() or bool(_ABSTAIN.search(answer or ""))


def confidence(t: dict) -> tuple[int, float]:
    return (0 if abstention_like(t.get("answer")) else 1, t.get("top_similarity") or 0.0)


def escalation_curve(conn: sqlite3.Connection, primary_metric: dict[str, str], *, label: str = "main",
                     baseline: str = "main", rates=DEFAULT_RATES, by: str = "task_type") -> list[dict]:
    runs = _latest_runs(conn)
    grouped: dict[str, list[tuple[float, float, float, tuple[int, float]]]] = defaultdict(list)
    for (lab, cond, bench), t_id in sorted(runs.items()):
        if lab != label or cond != "treatment":
            continue
        f_id, c_id = runs.get((baseline, "floor", bench)), runs.get((baseline, "ceiling", bench))
        if f_id is None or c_id is None:
            continue
        F, C, T = (_queries(conn, i, primary_metric) for i in (f_id, c_id, t_id))
        for key in sorted(set(F) & set(C) & set(T)):
            f, c, t = F[key], C[key], T[key]
            if any(x["status"] != "ok" or x["score"] is None for x in (f, c, t)):
                continue
            group = t["task_type"] if by == "task_type" else key.split("/", 1)[0]
            grouped[group].append((f["score"], c["score"], t["score"], confidence(t)))

    out = []
    for group, rows in sorted(grouped.items()):
        n = len(rows)
        mf = sum(r[0] for r in rows) / n
        mc = sum(r[1] for r in rows) / n
        mt = sum(r[2] for r in rows) / n
        denom = mc - mf
        by_conf = sorted(range(n), key=lambda i: (rows[i][3], i))  # least confident first
        by_gain = sorted(range(n), key=lambda i: (-(rows[i][1] - rows[i][2]), i))  # oracle order
        seen_k: set[int] = set()
        for rate in rates:
            k = round(rate * n)
            if k in seen_k:  # small samples: several rates round to the same count
                continue
            seen_k.add(k)
            esc = set(by_conf[:k])
            orc = set(by_gain[:k])
            acc = sum(rows[i][1] if i in esc else rows[i][2] for i in range(n)) / n
            acc_oracle = sum(rows[i][1] if i in orc else rows[i][2] for i in range(n)) / n
            acc_random = mt + (k / n) * (mc - mt)

            def gap(a: float) -> float | None:
                return (a - mf) / denom if abs(denom) > 1e-12 else None

            out.append({
                "group": group,
                "n": n,
                "escalation_rate": k / n,
                "on_device_share": 1 - k / n,
                "accuracy": acc,
                "gap_closed": gap(acc),
                "gap_closed_random_router": gap(acc_random),
                "gap_closed_oracle_router": gap(acc_oracle),
            })
    return out

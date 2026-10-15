"""What the cloud model cost: every Kimi call the project made, from the logged token counts, at Moonshot's list price.

Prices (USD per million tokens, platform.kimi.ai/docs/pricing/chat, read 15 Oct 2026): kimi-k3 input $3.00 (cache
hit $0.30), output $15.00; kimi-k2.6 input $0.95, output $4.00. Input is priced at the cache-miss rate (an upper
bound: some prompts were served from Moonshot's cache). Output includes the model's reasoning tokens, which are
billed as output.

    python scripts/kimi_costs.py      # writes results/costs/kimi_costs.json
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PRICE = {"kimi-k3": (3.00, 15.00), "kimi-k2.6": (0.95, 4.00)}

# experiment logs (one row per question, with the run's model): the cloud model as a ceiling, alone and with notes
RUN_DBS = [("results/pilot/camr.sqlite", "F9 pilot: Kimi K2.6/K3 alone and with CAMR's notes (30 questions x 3)"),
           ("results/hotpot200/camr.sqlite", "F13: Kimi K3 alone and with CAMR's notes, HotpotQA n = 200"),
           ("results/hotpot200-kimi/camr.sqlite", "F13: Kimi K3 rerun, HotpotQA n = 200"),
           ("results/learn/camr.sqlite", "F19/F22: Kimi K3 baselines in the learning experiments")]
# answer caches (one row per distinct request)
CACHES = [("results/verified/answers.sqlite", "F24: Kimi K3 second reader and closed-book baselines (dev, test, held-out)"),
          ("results/verified/judge.sqlite", "F24/F28: Kimi K3 as judge of every answer exact matching marked wrong (verified answers and RAG pipelines)"),
          ("results/math/answers.sqlite", "F27: Kimi K3 learning formulas from corrections (incl. two stopped runs)"),
          ("results/ragbench/answers.sqlite", "F28: Kimi K3 as the reader of the RAG pipelines and CAMR"),
          ("results/agentic/answers.sqlite", "F29: Kimi K3 in the n8n automations: support desk, agent tasks, current events (incl. writing the 50 news questions)")]


def usd(model: str, pin: int, pout: int) -> float:
    a, b = PRICE.get(model, PRICE["kimi-k3"])
    return (pin * a + pout * b) / 1e6


def main() -> None:
    rows = []
    for path, what in RUN_DBS:
        p = ROOT / path
        if not p.exists():
            continue
        c = sqlite3.connect(p)
        for model, n, pin, pout in c.execute(
                "SELECT r.model_name, COUNT(*), COALESCE(SUM(q.prompt_tokens),0), COALESCE(SUM(q.generated_tokens),0) "
                "FROM query_log q JOIN run r ON q.run_id = r.run_id WHERE r.model_name LIKE 'kimi%' "
                "GROUP BY r.model_name"):
            rows.append({"source": path, "what": what, "model": model, "calls": n, "input_tokens": pin,
                         "output_tokens": pout, "usd": round(usd(model, pin, pout), 4)})
    for path, what in CACHES:
        p = ROOT / path
        if not p.exists():
            continue
        c = sqlite3.connect(p)
        agg: dict[str, list[int]] = {}
        for model, body in c.execute("SELECT model, body FROM answer WHERE model LIKE 'kimi%'"):
            d = json.loads(body)
            a = agg.setdefault(model, [0, 0, 0, 0])
            a[0] += 1
            a[1] += d.get("prompt_tokens") or 0
            a[2] += d.get("generated_tokens") or 0
            a[3] += (d.get("meta") or {}).get("reasoning_tokens") or 0
        for model, (n, pin, pout, reason) in agg.items():
            rows.append({"source": path, "what": what, "model": model, "calls": n, "input_tokens": pin,
                         "output_tokens": pout, "reasoning_tokens": reason, "usd": round(usd(model, pin, pout), 4)})
    total = {"calls": sum(r["calls"] for r in rows), "input_tokens": sum(r["input_tokens"] for r in rows),
             "output_tokens": sum(r["output_tokens"] for r in rows), "usd": round(sum(r["usd"] for r in rows), 2)}
    out = {"prices_usd_per_million": PRICE, "price_source": "https://platform.kimi.ai/docs/pricing/chat (15 Oct 2026)",
           "rows": rows, "total": total}
    path = ROOT / "results/costs/kimi_costs.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(out, indent=1))
    for r in rows:
        print(f"{r['usd']:8.2f} USD  {r['calls']:5d} calls  in {r['input_tokens']:>9,}  out {r['output_tokens']:>9,}  "
              f"{r['model']:10s} {r['what']}")
    print(f"{total['usd']:8.2f} USD  {total['calls']:5d} calls  in {total['input_tokens']:>9,}  "
          f"out {total['output_tokens']:>9,}  TOTAL")


if __name__ == "__main__":
    main()

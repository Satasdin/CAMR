"""Phase 3: the link tier learns, per model size, when to trust the model (camr/learn/link.py).

Inputs are the reader bench's answers (scripts/reader_bench.py: every reader's answer with memory, judged) and the
engine bench's signals per question (top similarity, notes admitted). For each local reader the link starts knowing
nothing (it states every answer) and learns from feedback, one question at a time, whether to keep the answer,
decline, or escalate to Kimi K3; its greedy policy is scored on held-out questions after every block of feedback.
Ten random half/half splits, stratified by ability; no model is called (the answers are already judged).

    python scripts/link_learning.py run --tag baseline        # results/link/link_<tag>.json and .md
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
OUT = ROOT / "results/link"
CLOUD = "kimi-k3"


def load_rows(tag: str, records_dir: Path) -> dict[str, list[dict]]:
    from camr.app.assistant import grounded_share

    ctx = {r["qid"]: r for r in map(json.loads, (ROOT / f"results/readers/contexts_{tag}.jsonl").read_text().splitlines())}
    sig = {}
    for f in ("lme.jsonl", "camr.jsonl"):
        p = records_dir / f
        if p.exists():
            for r in map(json.loads, p.read_text().splitlines()):
                sig[r["qid"]] = r
    answers = [json.loads(line) for line in (ROOT / f"results/readers/answers_{tag}.jsonl").read_text().splitlines()]
    with_mem = {(a["reader"], a["qid"]): a for a in answers if a["memory"]}
    cloud = {qid: a for (rd, qid), a in with_mem.items() if rd == CLOUD}
    out: dict[str, list[dict]] = {}
    for (rd, qid), a in with_mem.items():
        if rd == CLOUD or qid not in cloud or qid not in ctx or a["correct"] is None:
            continue
        c, s = ctx[qid], sig.get(qid, {})
        out.setdefault(rd, []).append({
            "qid": qid, "ability": c.get("ability"), "question": c["question"],
            "abstained": bool(c.get("abstained")), "context_tokens": c.get("context_tokens") or 0,
            "top_similarity": s.get("top_similarity") or 0.0, "admitted": s.get("admitted") or 0,
            "grounded": grounded_share(a["answer"], c.get("context") or "") or 0.0,
            "declined": bool(a["declined"]),
            "local_correct": a["correct"], "cloud_correct": cloud[qid]["correct"],
            "unanswerable": str(qid).endswith("_abs") or c.get("ability") == "A7"})
    return out


def split(rows: list[dict], seed: int) -> tuple[list[dict], list[dict]]:
    """Half to learn from, half to score on, within each ability."""
    rng = random.Random(seed)
    by: dict[str, list[dict]] = {}
    for r in rows:
        by.setdefault(r["ability"] or "-", []).append(r)
    train, test = [], []
    for group in by.values():
        g = list(group)
        rng.shuffle(g)
        train += g[: len(g) // 2]
        test += g[len(g) // 2:]
    return train, test


def run(a) -> None:
    from camr.learn.link import Rewards, fixed_policies, learning_curve

    rewards = Rewards(wrong=a.wrong, cloud=a.cloud)
    data = load_rows(a.tag, Path(a.records))
    OUT.mkdir(parents=True, exist_ok=True)
    out = {"tag": a.tag, "rewards": rewards.__dict__, "splits": a.splits, "block": a.block, "readers": {}}
    for reader, rows in sorted(data.items()):
        curves, fixed = [], []
        for s in range(a.splits):
            train, test = split(rows, s)
            curves.append(learning_curve(train, test, rewards, block=a.block, seed=s))
            fixed.append(fixed_policies(test, rewards))
        steps = min(len(c) for c in curves)
        mean = lambda key, i: statistics.mean(c[i][key] for c in curves)  # noqa: E731
        sd = lambda key, i: statistics.pstdev(c[i][key] for c in curves)  # noqa: E731
        curve = [{"feedback": curves[0][i]["feedback"], **{k: round(mean(k, i), 4) for k in
                  ("right", "wrong", "declined", "escalated", "reward")},
                  "reward_sd": round(sd("reward", i), 4)} for i in range(steps)]
        fixed_mean = {name: {k: round(statistics.mean(f[name][k] for f in fixed), 4) for k in fixed[0][name]}
                      for name in fixed[0]}
        out["readers"][reader] = {"n": len(rows), "curve": curve, "fixed": fixed_mean}
        print(reader, "n", len(rows), "learned:", curve[-1], flush=True)
    (OUT / f"link_{a.tag}.json").write_text(json.dumps(out, indent=1))
    report(a)


def report(a) -> None:
    d = json.loads((OUT / f"link_{a.tag}.json").read_text())
    pct = lambda x: f"{100 * x:.0f}%"  # noqa: E731
    lines = [f"# The link learns: {a.tag}", "",
             f"Reward: right +1, wrong -{d['rewards']['wrong']}, declined 0 (+1 when the question cannot be answered), "
             f"escalating to Kimi K3 costs {d['rewards']['cloud']}. Mean over {d['splits']} random half/half splits.",
             "", "| Reader | policy | right | wrong (stated as fact) | declined | sent to Kimi K3 | reward |",
             "|---|---|---|---|---|---|---|"]
    for reader, r in d["readers"].items():
        last = r["curve"][-1]
        rows = [("link, no feedback yet", r["curve"][0]), (f"link after {last['feedback']} answers' feedback", last),
                ("always keep", r["fixed"]["always keep"]), ("always escalate", r["fixed"]["always escalate"]),
                ("always decline", r["fixed"]["always decline"]), ("best possible (oracle)", r["fixed"]["oracle"])]
        for name, v in rows:
            lines.append(f"| {reader} (n={r['n']}) | {name} | {pct(v['right'])} | {pct(v['wrong'])} | "
                         f"{pct(v['declined'])} | {pct(v['escalated'])} | {v['reward']:+.2f} |")
    lines += ["", "## Learning curves (held-out reward as feedback accumulates)", ""]
    for reader, r in d["readers"].items():
        pts = " · ".join(f"{p['feedback']}: {p['reward']:+.2f}" for p in r["curve"])
        lines.append(f"- **{reader}**: {pts}")
    (OUT / f"link_{a.tag}.md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("part", choices=["run", "report"])
    ap.add_argument("--tag", default="baseline")
    ap.add_argument("--records", default=str(Path.home() / "Desktop/camr-bench-wt/results/bench/records"),
                    help="the engine bench's per-question records (top similarity, notes admitted)")
    ap.add_argument("--wrong", type=float, default=1.0, help="cost of a wrong answer stated as fact")
    ap.add_argument("--cloud", type=float, default=0.3, help="cost of one cloud call")
    ap.add_argument("--splits", type=int, default=10)
    ap.add_argument("--block", type=int, default=20)
    a = ap.parse_args()
    {"run": run, "report": report}[a.part](a)

"""Learning the engine's policy from rewards over runs (contextual bandit).

The small model's weights never change.  What is learned is the ENGINE's
decision per question: answer alone, answer with 128 / 512 / 1024 tokens of
memory, or escalate to the cloud model.  The context is cheap and computed before
any generation (task type and retrieval strength); the reward is

    r = correct - lambda_cloud * [escalated] - mu * prompt_tokens / 1000

so the policy is pushed towards answering locally, quickly and correctly, and pays
for every cloud call and every token the small model must read.

Two learners are provided:
* ``fit_offline``: ridge regression of reward on context, one model per action,
  trained on a fully logged training split (every action tried on every question);
* ``linucb_replay``: LinUCB that sees only the reward of the action it chose,
  replayed over the training split for several passes ("runs"), with the greedy
  policy scored on the held-out evaluation split after each block of episodes.

Evaluation questions are disjoint from training questions (see ``load_sample``).
"""

from __future__ import annotations

import json
import random
import statistics
from dataclasses import dataclass, field
from typing import Any

import numpy as np

from camr.config import Config
from camr.eval.analysis import TASK_TYPES
from camr.harness.experiment import ExperimentRunner, Workspace

# action -> (condition, memory overrides).  Memory arms use the best read path
# found in the retrieval evaluation (similarity ranking + gating; bridging from 512).
_SIM = {"retrieval_policy": "similarity_only", "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0},
        "min_similarity": 0.50, "similarity_margin": 0.15}
ARMS: dict[str, tuple[str, dict[str, Any]]] = {
    "local": ("floor", {}),
    "mem128": ("treatment", {**_SIM, "token_budget": 128, "expansion": "none"}),
    "mem512": ("treatment", {**_SIM, "token_budget": 512, "expansion": "entity"}),
    "mem1024": ("treatment", {**_SIM, "token_budget": 1024, "expansion": "entity"}),
    "cloud": ("ceiling", {}),
}
ARM_NAMES = list(ARMS)
TASKS = ["single_hop", "multi_hop", "reasoning"]


def arm_label(arm: str, split: str) -> str:
    return f"arm:{arm}" + ("" if split == "eval" else f":{split}")


# ------------------------------------------------------------------ collection


def collect(ws: Workspace, cfg: Config, split: str, arms: list[str] | None = None) -> None:
    """Run every action on every question of ``split`` (full feedback, for learning and evaluation)."""
    runner = ExperimentRunner(ws)
    for arm in arms or ARM_NAMES:
        cond, over = ARMS[arm]
        acfg = cfg.with_overrides({"memory": over}) if over else cfg
        for bench in cfg.benchmarks:
            runner.run(cond, bench, cfg=acfg, label=arm_label(arm, split), split=split)


def features(ws: Workspace, cfg: Config, split: str) -> dict[str, dict[str, float]]:
    """Pre-generation context per question: task type and retrieval strength (no model call)."""
    probe = cfg.with_overrides({"memory": {**_SIM, "token_budget": 1024, "expansion": "none"}})
    engine = ws.engine(probe)
    out: dict[str, dict[str, float]] = {}
    for bench in cfg.benchmarks:
        task = TASK_TYPES[bench]
        nt = "exemplar" if task == "reasoning" and cfg.memory.reasoning_memory == "exemplars" else probe.memory.note_type
        for q in ws.sample(bench, split=split):
            r = engine.recall(q.question, touch=False, note_type=nt)
            sims = sorted((c.similarity for c in r.candidates), reverse=True)
            top = sims[0] if sims else 0.0
            out[f"{bench}/{q.qid}"] = {
                "task": task, "top_sim": top, "margin": top - (sims[1] if len(sims) > 1 else 0.0),
                "n_eligible": sum(1 for s in sims if s >= top - 0.15), "q_words": len(q.question.split()),
            }
    return out


def dataset(ws: Workspace, cfg: Config, split: str, feats: dict[str, dict[str, float]]) -> list[dict[str, Any]]:
    """One row per question: context features and, per action, correctness, prompt tokens and latency."""
    conn = ws.conn
    rows: dict[str, dict[str, Any]] = {k: {"key": k, **v, "arms": {}} for k, v in feats.items()}
    for arm in ARM_NAMES:
        for bench in cfg.benchmarks:
            rid = conn.execute("SELECT MAX(run_id) FROM run WHERE label=? AND benchmark=? AND status='completed'",
                               (arm_label(arm, split), bench)).fetchone()[0]
            if rid is None:
                continue
            metric = cfg.primary_metric.get(bench, "em")
            for qid, status, ptok, e2e, val, answer, prompt in conn.execute(
                "SELECT q.question_id, q.status, q.prompt_tokens, q.e2e_latency_ms, s.value, q.answer_text, q.prompt"
                " FROM query_log q LEFT JOIN score s ON s.query_id=q.query_id AND s.metric=? WHERE q.run_id=?",
                (metric, rid)):
                key = f"{bench}/{qid}"
                if key in rows:
                    rows[key]["arms"][arm] = {"correct": float(val or 0.0) if status == "ok" else 0.0,
                                              "prompt_tokens": ptok or 0, "latency_ms": e2e or 0.0,
                                              "ok": status == "ok", **answer_signals(answer or "", prompt or "")}
    return [r for r in rows.values() if all(a in r["arms"] for a in ARM_NAMES)]


def answer_signals(answer: str, prompt: str) -> dict[str, float]:
    """Cheap confidence signals from the small model's OWN answer (no extra model call).

    grounded: the short answer's content words all occur in the notes the model was given;
    abstain: the answer is empty or abstention-like; length: words in the first line.
    """
    from camr.eval.escalation import abstention_like
    from camr.eval.scoring import extract_answer, normalize_answer

    short = normalize_answer(extract_answer(answer))
    notes = normalize_answer(prompt.split("Notes:", 1)[1].split("Question:", 1)[0]) if "Notes:" in prompt else ""
    words = [w for w in short.split() if len(w) > 2]
    grounded = float(bool(notes) and bool(words) and all(w in notes for w in words))
    return {"grounded": grounded, "abstain": float(abstention_like(answer)), "ans_words": float(len(short.split()))}


# ------------------------------------------------------------------ learning


@dataclass
class Costs:
    cloud: float = 0.3  # cost of one cloud call, in units of "one correct answer"
    per_1k_tokens: float = 0.1  # cost of the small model reading 1,000 prompt tokens

    def reward(self, arm: str, out: dict[str, Any]) -> float:
        if arm == "cloud":
            return out["correct"] - self.cloud
        return out["correct"] - self.per_1k_tokens * out["prompt_tokens"] / 1000


def phi(row: dict[str, Any]) -> np.ndarray:
    t = [1.0 if row["task"] == k else 0.0 for k in TASKS]
    s, m = row["top_sim"], row["margin"]
    return np.array([1.0, *t, s, m, row["n_eligible"] / 10, row["q_words"] / 30, *(ti * s for ti in t)], dtype=float)


@dataclass
class LinearPolicy:
    weights: dict[str, np.ndarray] = field(default_factory=dict)

    def scores(self, row: dict[str, Any]) -> dict[str, float]:
        x = phi(row)
        return {a: float(w @ x) for a, w in self.weights.items()}

    def act(self, row: dict[str, Any]) -> str:
        sc = self.scores(row)
        return max(ARM_NAMES, key=lambda a: (sc.get(a, -1e9), -ARM_NAMES.index(a)))


def fit_offline(train: list[dict[str, Any]], costs: Costs, ridge: float = 1.0) -> LinearPolicy:
    X = np.vstack([phi(r) for r in train])
    pol = LinearPolicy()
    for a in ARM_NAMES:
        y = np.array([costs.reward(a, r["arms"][a]) for r in train])
        pol.weights[a] = np.linalg.solve(X.T @ X + ridge * np.eye(X.shape[1]), X.T @ y)
    return pol


def evaluate(policy, rows: list[dict[str, Any]], costs: Costs) -> dict[str, Any]:
    """Score a policy (callable row -> arm) on logged full-feedback rows."""
    picks = [policy(r) for r in rows]
    outs = [r["arms"][a] for r, a in zip(rows, picks)]
    by_task: dict[str, list[float]] = {}
    for r, o in zip(rows, outs):
        by_task.setdefault(r["task"], []).append(o["correct"])
    return {
        "n": len(rows),
        "accuracy": statistics.mean(o["correct"] for o in outs),
        "accuracy_by_task": {k: statistics.mean(v) for k, v in sorted(by_task.items())},
        "cloud_share": sum(a == "cloud" for a in picks) / len(picks),
        "mean_reward": statistics.mean(costs.reward(a, o) for a, o in zip(picks, outs)),
        "mean_latency_s": statistics.mean(o["latency_ms"] for o in outs) / 1000,
        "mean_local_prompt_tokens": statistics.mean(o["prompt_tokens"] for a, o in zip(picks, outs) if a != "cloud")
        if any(a != "cloud" for a in picks) else 0.0,
        "choices": {a: picks.count(a) for a in ARM_NAMES},
    }


def oracle(costs: Costs):
    return lambda r: max(ARM_NAMES, key=lambda a: (costs.reward(a, r["arms"][a]), -ARM_NAMES.index(a)))


def linucb_replay(train: list[dict[str, Any]], test: list[dict[str, Any]], costs: Costs, *, passes: int = 5,
                  alpha: float = 0.5, block: int = 20, seed: int = 13) -> list[dict[str, Any]]:
    """LinUCB with bandit feedback, replayed over the training split for several passes.

    After every ``block`` episodes the current greedy policy is scored on the
    held-out split: the learning curve of the engine over runs.
    """
    d = len(phi(train[0]))
    A = {a: np.eye(d) for a in ARM_NAMES}
    b = {a: np.zeros(d) for a in ARM_NAMES}
    rng = random.Random(seed)
    curve, t = [], 0

    def greedy(row):
        x = phi(row)
        return max(ARM_NAMES, key=lambda a: (float(np.linalg.solve(A[a], b[a]) @ x), -ARM_NAMES.index(a)))

    curve.append({"episodes": 0, **evaluate(greedy, test, costs)})
    for _ in range(passes):
        order = list(train)
        rng.shuffle(order)
        for row in order:
            x = phi(row)
            ucb = {}
            for a in ARM_NAMES:
                Ainv = np.linalg.inv(A[a])
                ucb[a] = float(Ainv @ b[a] @ x + alpha * np.sqrt(x @ Ainv @ x))
            arm = max(ARM_NAMES, key=lambda a: (ucb[a], -ARM_NAMES.index(a)))
            r = costs.reward(arm, row["arms"][arm])  # only the chosen action's outcome is observed
            A[arm] += np.outer(x, x)
            b[arm] += r * x
            t += 1
            if t % block == 0:
                curve.append({"episodes": t, **evaluate(greedy, test, costs)})
    return curve


def report(train: list[dict[str, Any]], test: list[dict[str, Any]], costs: Costs,
           cloud_costs: tuple[float, ...] = (0.0, 0.05, 0.1, 0.2, 0.3, 0.5, 0.8, 1.2)) -> dict[str, Any]:
    fixed = {f"always {a}": evaluate(lambda r, a=a: a, test, costs) for a in ARM_NAMES}
    learned = fit_offline(train, costs)
    out = {
        "costs": costs.__dict__,
        "n_train": len(train), "n_test": len(test),
        "fixed": fixed,
        "learned_offline": evaluate(learned.act, test, costs),
        "oracle": evaluate(oracle(costs), test, costs),
        "pareto": [],
        "curve": linucb_replay(train, test, costs),
    }
    for c in cloud_costs:
        cc = Costs(cloud=c, per_1k_tokens=costs.per_1k_tokens)
        pol = fit_offline(train, cc)
        out["pareto"].append({"cloud_cost": c, **evaluate(pol.act, test, cc)})
    return out


def save(obj: Any, path) -> None:
    path.write_text(json.dumps(obj, indent=2, default=float))


# ------------------------------------------------------------------ cascade


def cascade_features(row: dict[str, Any], arm: str) -> np.ndarray:
    a = row["arms"][arm]
    t = [1.0 if row["task"] == k else 0.0 for k in TASKS]
    return np.array([1.0, *t, a["grounded"], a["abstain"], min(a["ans_words"], 20) / 20, row["top_sim"],
                     *(ti * a["grounded"] for ti in t)], dtype=float)


def fit_cascade(train: list[dict[str, Any]], first: LinearPolicy, ridge: float = 1.0) -> np.ndarray:
    """Learn P(local answer is correct | signals from that answer) for the arm the first stage picks."""
    X = np.vstack([cascade_features(r, first.act(r)) for r in train])
    y = np.array([r["arms"][first.act(r)]["correct"] for r in train])
    return np.linalg.solve(X.T @ X + ridge * np.eye(X.shape[1]), X.T @ y)


def evaluate_cascade(test: list[dict[str, Any]], first: LinearPolicy, w: np.ndarray, threshold: float) -> dict[str, Any]:
    """Answer locally with the first-stage arm; escalate to the cloud when predicted correctness < threshold.
    Latency of an escalated question = local attempt + cloud answer."""
    corr, lat, cloud, by_task = [], [], 0, {}
    for r in test:
        arm = first.act(r)
        if arm == "cloud":
            o, t, esc = r["arms"]["cloud"], r["arms"]["cloud"]["latency_ms"], True
        else:
            esc = float(cascade_features(r, arm) @ w) < threshold
            o = r["arms"]["cloud"] if esc else r["arms"][arm]
            t = r["arms"][arm]["latency_ms"] + (r["arms"]["cloud"]["latency_ms"] if esc else 0.0)
        cloud += esc
        corr.append(o["correct"])
        lat.append(t)
        by_task.setdefault(r["task"], []).append(o["correct"])
    return {"threshold": threshold, "n": len(test), "accuracy": statistics.mean(corr), "cloud_share": cloud / len(test),
            "mean_latency_s": statistics.mean(lat) / 1000,
            "accuracy_by_task": {k: statistics.mean(v) for k, v in sorted(by_task.items())}}


def cascade_report(train: list[dict[str, Any]], test: list[dict[str, Any]],
                   first_costs: tuple[float, ...] = (1.2, 0.3),
                   thresholds: tuple[float, ...] = (0.0, 0.2, 0.3, 0.4, 0.5, 0.6, 1.01)) -> list[dict[str, Any]]:
    """Two-stage policy.  Stage 1 is the learned router at a given cloud cost (1.2: never routes to the
    cloud up front; 0.3: routes what it has learned the small model cannot do, e.g. maths).  Stage 2
    answers locally and escalates when the answer's own signals (grounding in the notes, abstention,
    length) predict it is wrong."""
    out = []
    for fc in first_costs:
        first = fit_offline(train, Costs(cloud=fc))
        w = fit_cascade(train, first)
        out += [{"stage1_cloud_cost": fc, **evaluate_cascade(test, first, w, th)} for th in thresholds]
    return out

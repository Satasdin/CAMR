"""The engine-policy learners recover a known optimal routing on a constructed problem."""

from __future__ import annotations

import random

from camr.learn.bandit import ARM_NAMES, Costs, evaluate, fit_offline, linucb_replay, oracle, phi


def _rows(n: int, seed: int) -> list[dict]:
    """Ground truth: memory answers single-hop questions when retrieval is strong; reasoning is best
    answered locally; weak retrieval needs the cloud."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        task = rng.choice(["single_hop", "multi_hop", "reasoning"])
        sim = rng.uniform(0.3, 0.9)
        strong = sim > 0.6
        right = {
            "local": task == "reasoning" and rng.random() < 0.5,
            "mem128": task == "single_hop" and strong,
            "mem512": task != "reasoning" and strong,
            "mem1024": task != "reasoning" and strong,
            "cloud": True,
        }
        rows.append({"key": str(i), "task": task, "top_sim": sim, "margin": rng.uniform(0, 0.2),
                     "n_eligible": rng.randint(1, 8), "q_words": rng.randint(6, 30),
                     "arms": {a: {"correct": float(right[a]), "prompt_tokens": {"local": 50, "mem128": 160,
                              "mem512": 520, "mem1024": 900, "cloud": 50}[a], "latency_ms": 1000.0, "ok": True}
                              for a in ARM_NAMES}})
    return rows


def test_offline_policy_beats_every_fixed_action_and_uses_the_cloud_sparingly():
    train, test = _rows(600, 1), _rows(300, 2)
    costs = Costs(cloud=0.3, per_1k_tokens=0.1)
    learned = evaluate(fit_offline(train, costs).act, test, costs)
    best_fixed = max(evaluate(lambda r, a=a: a, test, costs)["mean_reward"] for a in ARM_NAMES)
    assert learned["mean_reward"] > best_fixed
    assert 0.0 < learned["cloud_share"] < 1.0
    assert learned["mean_reward"] <= evaluate(oracle(costs), test, costs)["mean_reward"] + 1e-9


def test_linucb_learns_over_runs():
    train, test = _rows(400, 3), _rows(200, 4)
    curve = linucb_replay(train, test, Costs(), passes=3, block=50)
    assert curve[-1]["mean_reward"] > curve[0]["mean_reward"]
    assert len(phi(train[0])) == 11

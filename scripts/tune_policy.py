"""Tune the engine's learned router properly: hyperparameters chosen by cross-validation on the
training split only, then ONE evaluation on the held-out split.

The router (camr.learn.bandit) has four hyperparameters that the first study fixed by hand:
the ridge penalty lambda, the feature set, the LinUCB exploration weight alpha with its number of
passes (epochs), and the cascade's escalation threshold. In the first study the threshold was
read off a sweep on the held-out questions, which flatters the result. Here every choice is made
by 5-fold cross-validation over the 144 training questions (folds stratified by task type), and
the 72 held-out questions are scored once at the end, with a paired bootstrap interval against
always asking the cloud model.

    python scripts/tune_policy.py --out results/learn/tables/policy_tuning.json
"""

from __future__ import annotations

import argparse
import json
import random
import statistics
from pathlib import Path

import numpy as np

from camr.learn import bandit as B

ROOT = Path(__file__).resolve().parents[1]
COSTS = B.Costs(cloud=0.3, per_1k_tokens=0.1)  # a design preference, not a tuned value
LAMBDAS = (0.01, 0.1, 1.0, 10.0, 100.0)
ALPHAS = (0.0, 0.1, 0.25, 0.5, 1.0, 2.0)
PASSES = tuple(range(1, 11))
THRESHOLDS = tuple(round(x, 2) for x in np.arange(0.0, 1.0001, 0.05))


# ------------------------------------------------------------------ feature sets
def phi_task(row):
    return np.array([1.0, *[1.0 if row["task"] == k else 0.0 for k in B.TASKS]])


def phi_retrieval(row):
    t = [1.0 if row["task"] == k else 0.0 for k in B.TASKS]
    return np.array([1.0, *t, row["top_sim"], row["margin"], row["n_eligible"] / 10, row["q_words"] / 30])


FEATURES = {"task only": phi_task, "task + retrieval": phi_retrieval, "full (with interactions)": B.phi}


def fit(train, lam, phi):
    X = np.vstack([phi(r) for r in train])
    return {a: np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]),
                               X.T @ np.array([COSTS.reward(a, r["arms"][a]) for r in train])) for a in B.ARM_NAMES}


def act(w, phi):
    return lambda r: max(B.ARM_NAMES, key=lambda a: (float(w[a] @ phi(r)), -B.ARM_NAMES.index(a)))


def folds(rows, k=5, seed=13):
    """Stratified by task type, so every fold has single-hop, multi-hop and maths questions."""
    rng = random.Random(seed)
    out = [[] for _ in range(k)]
    for task in B.TASKS:
        idx = [i for i, r in enumerate(rows) if r["task"] == task]
        rng.shuffle(idx)
        for j, i in enumerate(idx):
            out[j % k].append(i)
    return out


def cv(rows, score_fn, k=5):
    """Mean and standard deviation over folds of score_fn(train_rows, valid_rows)."""
    fs = folds(rows, k)
    vals = []
    for f in fs:
        hold = set(f)
        vals.append(score_fn([r for i, r in enumerate(rows) if i not in hold], [rows[i] for i in f]))
    return statistics.mean(vals), statistics.pstdev(vals)


def linucb_policy(train, alpha, passes, phi=B.phi, seed=13):
    d = len(phi(train[0]))
    A = {a: np.eye(d) for a in B.ARM_NAMES}
    b = {a: np.zeros(d) for a in B.ARM_NAMES}
    rng = random.Random(seed)
    for _ in range(passes):
        order = list(train)
        rng.shuffle(order)
        for row in order:
            x = phi(row)
            ucb = {}
            for a in B.ARM_NAMES:
                Ainv = np.linalg.inv(A[a])
                ucb[a] = float(Ainv @ b[a] @ x + alpha * np.sqrt(x @ Ainv @ x))
            arm = max(B.ARM_NAMES, key=lambda a: (ucb[a], -B.ARM_NAMES.index(a)))
            r = COSTS.reward(arm, row["arms"][arm])
            A[arm] += np.outer(x, x)
            b[arm] += r * x
    w = {a: np.linalg.solve(A[a], b[a]) for a in B.ARM_NAMES}
    return act(w, phi)


def cascade(train, lam, phi, threshold):
    w1 = fit(train, lam, phi)
    first = act(w1, phi)
    X = np.vstack([B.cascade_features(r, first(r)) for r in train])
    y = np.array([r["arms"][first(r)]["correct"] for r in train])
    w2 = np.linalg.solve(X.T @ X + lam * np.eye(X.shape[1]), X.T @ y)

    def policy_outcome(r):
        arm = first(r)
        if arm == "cloud":
            return r["arms"]["cloud"], r["arms"]["cloud"]["latency_ms"], True
        esc = float(B.cascade_features(r, arm) @ w2) < threshold
        o = r["arms"]["cloud"] if esc else r["arms"][arm]
        lat = r["arms"][arm]["latency_ms"] + (r["arms"]["cloud"]["latency_ms"] if esc else 0.0)
        return o, lat, esc

    return policy_outcome


def cascade_metrics(policy_outcome, rows):
    outs = [policy_outcome(r) for r in rows]
    corr = [o["correct"] for o, _, _ in outs]
    reward = [o["correct"] - (COSTS.cloud if esc else COSTS.per_1k_tokens * o["prompt_tokens"] / 1000)
              for o, _, esc in outs]
    return {"accuracy": statistics.mean(corr), "reward": statistics.mean(reward),
            "cloud_share": statistics.mean(float(e) for _, _, e in outs),
            "mean_latency_s": statistics.mean(lat for _, lat, _ in outs) / 1000, "correct": corr,
            "by_task": {t: statistics.mean(c for r, c in zip(rows, corr) if r["task"] == t) for t in B.TASKS}}


def mean_reward(policy, rows):
    return statistics.mean(COSTS.reward(policy(r), r["arms"][policy(r)]) for r in rows)


def paired_bootstrap(a, b, n=2000, seed=13):
    rng = random.Random(seed)
    m = len(a)
    diffs = []
    for _ in range(n):
        idx = [rng.randrange(m) for _ in range(m)]
        diffs.append(sum(a[i] - b[i] for i in idx) / m)
    diffs.sort()
    return statistics.mean(x - y for x, y in zip(a, b)), diffs[int(0.025 * n)], diffs[int(0.975 * n) - 1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default=str(ROOT / "results/learn/tables/policy_tuning.json"))
    a = ap.parse_args()
    data = json.loads((ROOT / "results/learn/tables/rl_dataset.json").read_text())
    train, test = data["train"], data["eval"]
    out = {"n_train": len(train), "n_test": len(test), "costs": COSTS.__dict__, "folds": 5}

    # 1. ridge lambda x feature set (offline router), CV mean reward
    grid = []
    for fname, phi in FEATURES.items():
        for lam in LAMBDAS:
            m, s = cv(train, lambda tr, va: mean_reward(act(fit(tr, lam, phi), phi), va))
            acc, _ = cv(train, lambda tr, va: statistics.mean(r["arms"][act(fit(tr, lam, phi), phi)(r)]["correct"]
                                                              for r in va))
            grid.append({"features": fname, "lambda": lam, "cv_reward": m, "cv_reward_sd": s, "cv_accuracy": acc})
    out["router_grid"] = grid
    best = max(grid, key=lambda g: (round(g["cv_reward"], 6), -LAMBDAS.index(g["lambda"])))
    out["router_selected"] = best
    phi, lam = FEATURES[best["features"]], best["lambda"]

    # 2. LinUCB alpha x passes (epochs), CV mean reward of the greedy policy after training
    lin = []
    for alpha in ALPHAS:
        for p in PASSES:
            m, s = cv(train, lambda tr, va: mean_reward(linucb_policy(tr, alpha, p), va))
            lin.append({"alpha": alpha, "passes": p, "cv_reward": m, "cv_reward_sd": s})
    out["linucb_grid"] = lin
    out["linucb_selected"] = max(lin, key=lambda g: (round(g["cv_reward"], 6), -g["passes"]))

    # 3. cascade threshold, CV (the first study picked 0.2 on the held-out split)
    casc = []
    for th in THRESHOLDS:
        m, s = cv(train, lambda tr, va: cascade_metrics(cascade(tr, lam, phi, th), va)["reward"])
        acc, _ = cv(train, lambda tr, va: cascade_metrics(cascade(tr, lam, phi, th), va)["accuracy"])
        casc.append({"threshold": th, "cv_reward": m, "cv_reward_sd": s, "cv_accuracy": acc})
    out["cascade_grid"] = casc
    th = max(casc, key=lambda g: (round(g["cv_reward"], 6), -g["threshold"]))["threshold"]
    out["cascade_selected"] = th

    # 4. one held-out evaluation of the tuned policies
    always_cloud = [r["arms"]["cloud"]["correct"] for r in test]
    final = {}
    router = act(fit(train, lam, phi), phi)
    rc = [r["arms"][router(r)]["correct"] for r in test]
    final["tuned router"] = {"accuracy": statistics.mean(rc), "cloud_share": statistics.mean(router(r) == "cloud" for r in test),
                             "mean_latency_s": statistics.mean(r["arms"][router(r)]["latency_ms"] for r in test) / 1000,
                             "vs_always_cloud": paired_bootstrap(rc, always_cloud)}
    sel = out["linucb_selected"]
    lp = linucb_policy(train, sel["alpha"], sel["passes"])
    lc = [r["arms"][lp(r)]["correct"] for r in test]
    final["tuned LinUCB"] = {"accuracy": statistics.mean(lc), "cloud_share": statistics.mean(lp(r) == "cloud" for r in test),
                             "mean_latency_s": statistics.mean(r["arms"][lp(r)]["latency_ms"] for r in test) / 1000,
                             "vs_always_cloud": paired_bootstrap(lc, always_cloud)}
    cm = cascade_metrics(cascade(train, lam, phi, th), test)
    final["tuned router + cascade"] = {k: v for k, v in cm.items() if k != "correct"}
    final["tuned router + cascade"]["vs_always_cloud"] = paired_bootstrap(cm["correct"], always_cloud)
    final["always cloud"] = {"accuracy": statistics.mean(always_cloud), "cloud_share": 1.0,
                             "mean_latency_s": statistics.mean(r["arms"]["cloud"]["latency_ms"] for r in test) / 1000}
    out["held_out"] = final
    Path(a.out).write_text(json.dumps(out, indent=2, default=float))
    print(json.dumps({"router": best, "linucb": sel, "threshold": th,
                      "held_out": {k: {kk: vv for kk, vv in v.items() if kk in ("accuracy", "cloud_share", "mean_latency_s",
                                                                              "vs_always_cloud")}
                                   for k, v in final.items()}}, indent=1, default=float))


if __name__ == "__main__":
    main()

"""The link tier: a few numbers per model that learn, from feedback, when to trust it.

The model's weights stay frozen and the memory is shared by every model; what differs between a 0.5B and a 3B
reader is how far its answers can be trusted. After a local model has answered with memory, the link chooses one
of three actions:

* ``keep``: state the local answer;
* ``decline``: say it does not know yet (and, in the app, ask to be taught);
* ``escalate``: ask the cloud model (Kimi K3) with the same memory.

It decides from signals that cost nothing: how strongly memory matched, whether memory abstained, how much of the
answer's wording occurs in the notes it read (grounding), whether the model itself declined, and the kind of
question (about the user, about time, a count). The reward is what a user's thumbs would say, with a wrong answer
priced like a hallucination: right +1, wrong -``wrong``, declining 0 (+1 when the question cannot be answered from
memory), escalating the cloud answer's reward minus ``cloud``. One small linear model per action and per reader,
learned by LinUCB from the feedback on the action it took (scripts/link_learning.py measures the learning curves).
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import numpy as np

ACTIONS = ["keep", "decline", "escalate"]

_DECLINE = re.compile(r"\b(?:i (?:do not|don't) know|not (?:mentioned|provided|stated|specified|available|sure)|"
                      r"(?:do not|don't|doesn't|does not) (?:have|mention|say|contain)|no (?:information|record|mention|"
                      r"notes?)\b|can(?:no|')t (?:assist|help|answer|find|tell|determine)|unable to|i'm not sure|"
                      r"(?:could|can) you (?:please )?(?:tell|share|provide|let me know))", re.I)


def model_declined(text: str) -> bool:
    """The model said it cannot answer: one of the link's signals, the same in the reader bench and the app (wider
    than camr.eval.escalation.abstention_like, which the research replays use and so stays as it is)."""
    from camr.eval.escalation import abstention_like

    text = (text or "").replace("\u2019", "'")
    return bool(text.strip()) and (abstention_like(text) or bool(_DECLINE.search(text)))

_PERSONAL = re.compile(r"\b(?:my|mine|me|myself|i|i'm|i've|i'd|our|we|us)\b", re.I)
_TIME = re.compile(r"\b(?:when|ago|last|first|before|after|since|days?|weeks?|months?|years?|yesterday|today|"
                   r"recently|order|earlier|later|how long)\b", re.I)
_COUNT = re.compile(r"\b(?:how many|how much|how often|total|times|count|all the|in all)\b", re.I)


def features(row: dict[str, Any]) -> np.ndarray:
    """The link's context for one question, from the read path and the local answer (no model call)."""
    q = row["question"]
    return np.array([
        1.0,
        float(row["abstained"]),
        float(row.get("top_similarity") or 0.0),
        min(float(row.get("admitted") or 0) / 10, 2.0),
        min(float(row.get("context_tokens") or 0) / 400, 2.0),
        float(row["grounded"]),            # share of the answer's content words found in the notes it read
        float(row["declined"]),            # the local model said it does not know
        float(bool(_PERSONAL.search(q))),
        float(bool(_TIME.search(q))),
        float(bool(_COUNT.search(q))),
        min(len(q.split()) / 30, 2.0),
    ])


@dataclass
class Rewards:
    wrong: float = 1.0   # a wrong answer stated as fact costs this much (a right one earns 1)
    cloud: float = 0.3   # one cloud call, in units of one right answer

    def __call__(self, action: str, row: dict[str, Any]) -> float:
        if action == "decline":
            return 1.0 if row["unanswerable"] else 0.0
        if action == "escalate":
            return self._answer(row["cloud_correct"], row.get("cloud_declined", False)) - self.cloud
        return self._answer(row["local_correct"], row.get("declined", False))

    def _answer(self, correct: bool | None, declined: bool) -> float:
        """A model that itself said it cannot answer stated nothing: that is a decline, not a wrong answer."""
        if correct:
            return 1.0
        return 0.0 if correct is None or declined else -self.wrong


def outcome(action: str, row: dict[str, Any]) -> str:
    """right / wrong / declined: what the user sees."""
    if action == "decline":
        return "right" if row["unanswerable"] else "declined"
    cloud = action == "escalate"
    correct = row["cloud_correct"] if cloud else row["local_correct"]
    if correct:
        return "right"
    if correct is None or row.get("cloud_declined" if cloud else "declined", False):
        return "declined"
    return "wrong"


def evaluate(policy: Callable[[dict], str], rows: list[dict], rewards: Rewards) -> dict[str, float]:
    picks = [policy(r) for r in rows]
    outs = [outcome(a, r) for a, r in zip(picks, rows)]
    n = max(1, len(rows))
    return {"right": sum(o == "right" for o in outs) / n, "wrong": sum(o == "wrong" for o in outs) / n,
            "declined": sum(o == "declined" for o in outs) / n,
            "escalated": sum(a == "escalate" for a in picks) / n,
            "reward": sum(rewards(a, r) for a, r in zip(picks, rows)) / n}


class Link:
    """LinUCB over the three actions: learns only from the reward of the action it took."""

    def __init__(self, alpha: float = 0.5, dim: int | None = None):
        self.alpha = alpha
        self.dim = dim or len(features({"question": "x", "abstained": False, "grounded": 0.0, "declined": False}))
        self.A = {a: np.eye(self.dim) for a in ACTIONS}
        self.b = {a: np.zeros(self.dim) for a in ACTIONS}

    def _theta(self, a: str) -> np.ndarray:
        return np.linalg.solve(self.A[a], self.b[a])

    def act(self, row: dict, allowed: tuple[str, ...] | list[str] = tuple(ACTIONS)) -> str:
        """The greedy choice among the allowed actions (what the app does: no cloud model, no escalation)."""
        x = features(row)
        return max([a for a in ACTIONS if a in allowed],
                   key=lambda a: (float(self._theta(a) @ x), -ACTIONS.index(a)))

    def values(self, row: dict) -> dict[str, float]:
        """The expected reward of each action for this answer, as learned so far."""
        x = features(row)
        return {a: round(float(self._theta(a) @ x), 4) for a in ACTIONS}

    def to_dict(self) -> dict:
        return {"alpha": self.alpha, "dim": self.dim, "A": {a: self.A[a].tolist() for a in ACTIONS},
                "b": {a: self.b[a].tolist() for a in ACTIONS}}

    @classmethod
    def from_dict(cls, d: dict) -> "Link":
        link = cls(alpha=d.get("alpha", 0.5), dim=d["dim"])
        if link.dim != len(features({"question": "x", "abstained": False, "grounded": 0.0, "declined": False})):
            raise ValueError("link was learned on other signals")
        for a in ACTIONS:
            link.A[a] = np.array(d["A"][a], dtype=float)
            link.b[a] = np.array(d["b"][a], dtype=float)
        return link

    def save(self, path: Path, **meta) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps({**meta, "link": self.to_dict()}))
        tmp.replace(path)

    @classmethod
    def load(cls, path: Path) -> tuple["Link", dict]:
        d = json.loads(Path(path).read_text())
        return cls.from_dict(d["link"]), {k: v for k, v in d.items() if k != "link"}

    def explore(self, row: dict) -> str:
        x = features(row)
        ucb = {}
        for a in ACTIONS:
            inv = np.linalg.inv(self.A[a])
            ucb[a] = float(inv @ self.b[a] @ x + self.alpha * np.sqrt(x @ inv @ x))
        return max(ACTIONS, key=lambda a: (ucb[a], -ACTIONS.index(a)))

    def update(self, row: dict, action: str, reward: float) -> None:
        x = features(row)
        self.A[action] += np.outer(x, x)
        self.b[action] += reward * x


def learning_curve(train: list[dict], test: list[dict], rewards: Rewards, *, block: int = 20, seed: int = 0,
                   alpha: float = 0.5) -> list[dict]:
    """Feed the training questions one by one (the user's thumbs on the action taken) and score the greedy link on
    the held-out questions after every ``block`` of feedback."""
    link = Link(alpha)
    order = list(train)
    random.Random(seed).shuffle(order)
    curve = [{"feedback": 0, **evaluate(link.act, test, rewards)}]
    for t, row in enumerate(order, 1):
        a = link.explore(row)
        link.update(row, a, rewards(a, row))
        if t % block == 0 or t == len(order):
            curve.append({"feedback": t, **evaluate(link.act, test, rewards)})
    return curve


def fixed_policies(rows: list[dict], rewards: Rewards) -> dict[str, dict]:
    out = {f"always {a}": evaluate(lambda r, a=a: a, rows, rewards) for a in ACTIONS}
    out["oracle"] = evaluate(lambda r: max(ACTIONS, key=lambda a: rewards(a, r)), rows, rewards)
    return out

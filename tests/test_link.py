"""The link tier (camr/learn/link.py): from feedback alone it learns to keep a grounded answer, decline when memory
has nothing, and escalate when the local answer is not grounded but the cloud model would get it right."""

from __future__ import annotations

import random

from camr.learn.link import Link, Rewards, evaluate, fixed_policies, learning_curve, outcome


def make_rows(n: int, seed: int = 0) -> list[dict]:
    """Three kinds of question, told apart only by the signals the link sees."""
    rng = random.Random(seed)
    rows = []
    for i in range(n):
        kind = i % 3
        if kind == 0:    # memory had it and the small model used it: keep
            r = dict(abstained=False, grounded=0.9, declined=False, local_correct=True, cloud_correct=True,
                     unanswerable=False, top_similarity=0.75)
        elif kind == 1:  # memory had nothing and the question is about the user: decline
            r = dict(abstained=True, grounded=0.0, declined=False, local_correct=False, cloud_correct=False,
                     unanswerable=True, top_similarity=0.3)
        else:            # memory had it, the small model answered off the notes; the cloud model reads them right
            r = dict(abstained=False, grounded=0.1, declined=False, local_correct=False, cloud_correct=True,
                     unanswerable=False, top_similarity=0.7)
        r.update(question="What is my thing?", admitted=3, context_tokens=200 + rng.randint(0, 50))
        rows.append(r)
    return rows


def test_rewards_price_a_wrong_answer_like_a_hallucination():
    rw = Rewards(wrong=1.0, cloud=0.3)
    right = dict(local_correct=True, cloud_correct=True, unanswerable=False)
    wrong = dict(local_correct=False, cloud_correct=True, unanswerable=False)
    assert rw("keep", right) == 1.0 and rw("keep", wrong) == -1.0 and rw("decline", wrong) == 0.0
    assert rw("escalate", wrong) == 0.7 and rw("decline", dict(wrong, unanswerable=True)) == 1.0
    assert outcome("keep", wrong) == "wrong" and outcome("decline", right) == "declined"
    # a model that itself said it cannot answer stated nothing: a decline, not a hallucination
    said_no = dict(wrong, cloud_correct=False, declined=True, cloud_declined=True)
    assert rw("keep", said_no) == 0.0 and outcome("keep", said_no) == "declined"
    assert outcome("escalate", said_no) == "declined" and abs(rw("escalate", said_no) + 0.3) < 1e-9


def test_the_link_learns_from_feedback_to_beat_every_fixed_choice():
    rw = Rewards()
    train, test = make_rows(150, 1), make_rows(60, 2)
    curve = learning_curve(train, test, rw, block=30, seed=0)
    first, last = curve[0], curve[-1]
    best_fixed = max(v["reward"] for k, v in fixed_policies(test, rw).items() if k != "oracle")
    assert last["reward"] > first["reward"] and last["reward"] > best_fixed
    assert last["wrong"] == 0.0 and abs(last["right"] - 1.0) < 1e-9  # every kind handled its own way


def test_a_new_link_states_answers_and_learning_is_deterministic():
    rows = make_rows(30)
    assert Link().act(rows[0]) == "keep"  # untrained: ties go to the first action
    a = learning_curve(make_rows(60), rows, Rewards(), seed=3)
    b = learning_curve(make_rows(60), rows, Rewards(), seed=3)
    assert a == b and evaluate(Link().act, rows, Rewards())["escalated"] == 0.0

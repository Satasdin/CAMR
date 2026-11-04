"""Grading an answer against a question's right answer on the quiz day. Rule-based, so a re-run grades the same.

Verdicts:
  right          names the right value
  stale          names only a value that an update has replaced
  missed         says it doesn't know, but the answer was told
  wrong          names something else
  right_abstain  says it doesn't know, and it was never told (or not yet)
  false_memory   answers something that was never told (or not yet)
"""

from __future__ import annotations

import re

from camr_engine.ruler.life import Question

_ABSTAIN = re.compile(
    r"\b(?:i\s+(?:don'?t|do\s+not)\s+know|not\s+sure|no\s+(?:information|record|mention|notes?|memory|memories|details?)"
    r"|(?:isn'?t|is\s+not|wasn'?t|was\s+not|not|never)\s+(?:mentioned|stated|specified|provided|recorded|given|said|told)"
    r"|(?:doesn'?t|don'?t|does\s+not|do\s+not)\s+(?:say|mention|contain|specify|include)"
    r"|(?:can'?t|cannot|could\s?n'?t|unable\s+to)\s+(?:find|tell|determine|answer)|unknown)\b")


def norm(text: str) -> str:
    """Lowercase words and numbers only: "14th of February," -> "14 february"."""
    t = text.lower().replace("’", "'").replace("é", "e")
    t = re.sub(r"(\d+)(?:st|nd|rd|th)\b", r"\1", t)
    t = re.sub(r"\bof\b", " ", t)
    t = re.sub(r"[^a-z0-9/\-]+", " ", t)
    return " " + " ".join(t.split()) + " "


def abstains(answer: str) -> bool:
    return bool(_ABSTAIN.search(answer.lower().replace("’", "'")))


def names(answer: str, aliases: tuple[str, ...]) -> bool:
    a = norm(answer)
    return any(norm(x) in a for x in aliases if x.strip())


def grade(q: Question, answer: str, day: int) -> str:
    """The verdict on ``answer`` to ``q`` at the end of ``day`` (see the module docstring)."""
    right = q.answer_on(day)
    if right is None:
        return "right_abstain" if abstains(answer) else "false_memory"
    if names(answer, right[1]):
        return "right"
    if names(answer, q.superseded_on(day)):
        return "stale"
    return "missed" if abstains(answer) else "wrong"

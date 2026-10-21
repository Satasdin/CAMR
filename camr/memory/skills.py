"""Skill cards: the tier of memory for skills (procedures), beside the notes that hold facts.

A correction is kept as a note that any model can read (the facts tier). For a skill, the corrections of one kind
are also compiled into a small adapter for one particular model: a *skill card*. Memory keeps the link between the
two, since a card is named by the source title its corrections share. To answer, the engine recalls the notes as
usual; the best admitted note's source names the card to attach, and when memory abstains no card is attached. The
model's own weights never change, and a card is detached after the answer, so a skill learned for one kind of
problem cannot leak into unrelated ones (F27 found one merged adapter took GSM8K from 13% to 0%;
scripts/skill_cards.py measures the cards).

The router is model-free: what a card is (a LoRA adapter in the experiment) and how it is attached belong to the
runtime. Moving to another model means compiling its cards again from the same stored corrections.
"""

from __future__ import annotations

from dataclasses import dataclass

from camr.memory.engine import MemoryEngine


def skill_of(title: str | None, prefix: str) -> str | None:
    """The skill a source title names ("Correction: zorbit" -> "zorbit"), or None for any other source."""
    if not title or not title.startswith(prefix):
        return None
    return title[len(prefix):].strip() or None


@dataclass
class Route:
    skill: str | None             # the card to attach; None = the model answers alone
    similarity: float | None      # cosine of the note that named the card (or of the best note, without one)
    abstained: bool               # memory withheld everything (the facts tier's own gate)
    context: str                  # what the facts tier admitted, for a reader that also takes notes


class SkillRouter:
    """Names the skill card for a question from what memory recalls; no model call."""

    def __init__(self, engine: MemoryEngine, prefix: str):
        self.engine = engine
        self.prefix = prefix

    def route(self, question: str) -> Route:
        r = self.engine.recall(question, touch=False)
        if r.abstained:
            return Route(None, r.top_similarity, True, "")
        admitted = r.admitted  # in rank order
        if not admitted:
            return Route(None, r.top_similarity, False, r.context)
        # Only the best note may name a card: a skill note admitted lower down sits beside a question about
        # something else, and attaching its card there is how a skill leaks into unrelated problems.
        best = admitted[0]
        skill = skill_of(self.engine.store.note_titles([best.note.note_id]).get(best.note.note_id), self.prefix)
        return Route(skill, best.similarity, False, r.context)

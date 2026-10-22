"""Context assembly under a hard token budget (FR-08, Equation 4.5).

Greedy packing over the ranked list, in linear time.  ``greedy_stop`` (the
proposal's rule) stops at the first note that would breach the budget, so the
admitted set is always a prefix of the ranking.  ``greedy_skip`` skips that note
and keeps trying shorter lower-ranked ones; it is offered as an ablation because
under ``greedy_stop`` one long top-ranked note can leave most of the budget
unused.  Either way the sum of admitted note tokens never exceeds the budget.
"""

from __future__ import annotations

from camr.memory.note import ScoredNote
from camr.models.tokenizer import Tokenizer


def render_note(text: str) -> str:
    return f"- {text.strip()}\n"


class TokenBudgeter:
    def __init__(self, tokenizer: Tokenizer, budget: int, mode: str = "greedy_stop"):
        if budget < 0:
            raise ValueError("budget must be >= 0")
        if mode not in {"greedy_stop", "greedy_skip"}:
            raise ValueError(f"unknown packing mode {mode!r}")
        self.tokenizer = tokenizer
        self.budget = budget
        self.mode = mode

    def pack(self, ranked: list[ScoredNote], render=None, order=None, budget: int | None = None) -> tuple[str, int]:
        """Mark admitted notes in place; return (context, tokens used).

        ``render(note) -> line`` writes a note differently (dates, compression), ``order(note) -> key`` lists the
        admitted notes in another order than their rank (e.g. oldest first), and ``budget`` replaces the
        budget for this call. Without them the context is exactly as before."""
        budget = self.budget if budget is None else budget
        used = 0
        picked: list[ScoredNote] = []
        stopped = False
        for cand in ranked:
            line = render(cand) if render is not None else render_note(cand.note.text)
            cand.line = line
            cand.tokens = self.tokenizer.count(line)
            cand.admitted = False
            cand.position = None
            if stopped or not cand.eligible:
                continue
            if used + cand.tokens > budget:
                if self.mode == "greedy_stop":
                    stopped = True
                continue
            cand.admitted = True
            used += cand.tokens
            picked.append(cand)
        assert used <= budget, "budget invariant violated"
        if order is not None:
            picked.sort(key=order)
        for i, cand in enumerate(picked):
            cand.position = i
        return "".join(c.line for c in picked), used

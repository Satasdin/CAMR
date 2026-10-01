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

    def pack(self, ranked: list[ScoredNote]) -> tuple[str, int]:
        """Mark admitted notes in place; return (context, tokens used)."""
        used = 0
        lines: list[str] = []
        stopped = False
        for cand in ranked:
            line = render_note(cand.note.text)
            cand.tokens = self.tokenizer.count(line)
            cand.admitted = False
            if stopped or not cand.eligible:
                continue
            if used + cand.tokens > self.budget:
                if self.mode == "greedy_stop":
                    stopped = True
                continue
            cand.admitted = True
            used += cand.tokens
            lines.append(line)
        assert used <= self.budget, "budget invariant violated"
        return "".join(lines), used

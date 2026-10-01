"""Write-time screening (FR-02): nothing reaches the store unchecked.

Beyond the empty / degenerate / duplicate / over-length checks the proposal
lists, the screener rejects instruction-like text.  AgentPoison and MINJA
(section 2.2.5) both work by getting imperative text into memory that later
steers the model; a note is a *fact*, so a candidate that addresses the reader
("ignore previous instructions", "you must answer ...") is not a valid note.
This is a cheap first line of defence, not a security evaluation.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from camr.memory.note import CandidateNote, checksum
from camr.models.tokenizer import Tokenizer

_INSTRUCTION_PATTERNS = [
    r"\bignore (all |any )?(the )?(previous|prior|above) (instructions|context|notes)\b",
    r"\b(disregard|forget) (all |the )?(previous|prior|above)\b",
    r"\bsystem prompt\b",
    r"\byou (must|should) (always )?(answer|respond|reply|say)\b",
    r"\b(always|only) (answer|respond|reply) with\b",
    r"\bnew instructions?\s*:",
]
_INSTRUCTION_RE = re.compile("|".join(_INSTRUCTION_PATTERNS), re.IGNORECASE)
_REFUSAL_RE = re.compile(
    r"^\s*(i('m| am) sorry|i cannot|i can't|as an ai|i do not have|i don't have)\b", re.IGNORECASE
)


@dataclass
class Verdict:
    accepted: bool
    reason: str
    checksum: str
    token_count: int


class NoteScreener:
    def __init__(
        self,
        tokenizer: Tokenizer,
        *,
        min_tokens: int = 3,
        max_tokens: int = 160,
        enabled: bool = True,
        min_alpha_ratio: float = 0.5,
        min_unique_ratio: float = 0.3,
        model_generated: bool = False,
    ):
        self.tokenizer = tokenizer
        self.min_tokens = min_tokens
        self.max_tokens = max_tokens
        self.enabled = enabled
        self.min_alpha_ratio = min_alpha_ratio
        self.min_unique_ratio = min_unique_ratio
        # Refusal phrasing only signals a failure in text a model wrote; in source
        # text it is ordinary language (e.g. the song "I Can't Get Next to You").
        self.model_generated = model_generated

    def screen(self, cand: CandidateNote, seen: set[str] | frozenset[str] = frozenset()) -> Verdict:
        """Return a verdict; ``seen`` holds checksums already in the store or batch."""
        text = cand.text.strip()
        csum = checksum(text, cand.note_type)
        tokens = self.tokenizer.encode(text)
        n = len(tokens)
        if cand.error:
            return Verdict(False, "write_failed", csum, 0)
        if not text:
            return Verdict(False, "empty", csum, 0)
        # Duplicate rejection is also enforced by the schema's UNIQUE constraint,
        # so it applies even when heuristic screening is disabled for an ablation.
        if csum in seen:
            return Verdict(False, "duplicate", csum, n)
        if not self.enabled:
            return Verdict(True, "accepted", csum, n)
        if n < self.min_tokens:
            return Verdict(False, "too_short", csum, n)
        if n > self.max_tokens:
            return Verdict(False, "over_length", csum, n)
        alpha = sum(ch.isalnum() for ch in text) / max(1, len(text.replace(" ", "")))
        if alpha < self.min_alpha_ratio:
            return Verdict(False, "degenerate", csum, n)
        words = [str(t).casefold() for t in tokens if str(t).isalnum()]
        if len(words) >= 10 and len(set(words)) / len(words) < self.min_unique_ratio:
            return Verdict(False, "repetitive", csum, n)
        if self.model_generated and _REFUSAL_RE.search(text):
            return Verdict(False, "refusal_output", csum, n)
        if _INSTRUCTION_RE.search(text):
            return Verdict(False, "instruction_like", csum, n)
        return Verdict(True, "accepted", csum, n)

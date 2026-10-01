"""Write-time importance scores (FR-04), normalised at read time by Equation 4.4.

The proposal specifies *that* each note carries an importance score but not how
it is assigned.  Park et al. (2023) ask the model for a 1-10 poignancy rating,
which costs one model call per note at ingestion.  The default here is a
zero-cost heuristic that targets what matters for knowledge-bound QA, namely
factual density (named entities, numbers, lexical variety); the model-rated
variant is available for comparison.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

from camr.models.prompt import RATE_IMPORTANCE
from camr.models.runner import GenerationError, ModelRunner

_WORD = re.compile(r"[A-Za-z][\w'-]*|\d[\d,.]*")
_STOP = frozenset(
    "a an the of in on at to for from by with and or but is are was were be been being this that "
    "these those it its as he she they his her their them i we you our your which who whom what "
    "when where how not no".split()
)


class ImportanceScorer(ABC):
    method: str

    @abstractmethod
    def score(self, text: str) -> float:
        """Raw importance; only its ordering within a candidate set matters."""


class HeuristicImportance(ImportanceScorer):
    method = "heuristic"

    def score(self, text: str) -> float:
        words = _WORD.findall(text)
        if not words:
            return 0.0
        n = len(words)
        # Capitalised tokens that do not start a sentence approximate named entities.
        entity = sum(
            1 for i, w in enumerate(words) if w[0].isupper() and i > 0 and w.casefold() not in _STOP
        )
        numeric = sum(1 for w in words if w[0].isdigit())
        content = [w.casefold() for w in words if w.casefold() not in _STOP]
        diversity = len(set(content)) / n
        return round(0.5 * min(1.0, entity / n * 2) + 0.3 * min(1.0, numeric / n * 5) + 0.2 * diversity, 6)


class ModelImportance(ImportanceScorer):
    method = "model"

    def __init__(self, runner: ModelRunner, fallback: ImportanceScorer | None = None):
        self.runner = runner
        self.fallback = fallback or HeuristicImportance()

    def score(self, text: str) -> float:
        try:
            out = self.runner.generate(RATE_IMPORTANCE.fill(note=text)).text
        except GenerationError:
            return self.fallback.score(text)
        m = re.search(r"\d+", out)
        if not m:
            return self.fallback.score(text)
        return float(min(10, max(1, int(m.group()))))

"""Token counting used by the budgeter (Equation 4.5) and the screener.

The budget is enforced with *this* tokenizer.  The local model's own token count
for the full prompt is logged separately (``prompt_tokens``), so the gap between
the engine's estimate and the model's reality is itself measurable.
"""

from __future__ import annotations

import re
from abc import ABC, abstractmethod

_TOKEN_RE = re.compile(r"\w+|[^\w\s]", re.UNICODE)


class Tokenizer(ABC):
    name: str

    @abstractmethod
    def encode(self, text: str) -> list[str | int]: ...

    def count(self, text: str) -> int:
        return len(self.encode(text))

    @abstractmethod
    def truncate(self, text: str, max_tokens: int) -> str: ...


class RegexTokenizer(Tokenizer):
    """Dependency-free word/punctuation tokenizer.

    Sub-word tokenizers used by 1-3B models typically emit 1.1-1.4 tokens per
    regex token on English prose, so budgets expressed in regex tokens are a
    slight under-estimate of model tokens; ``prompt_tokens`` records the truth.
    """

    name = "regex"

    def encode(self, text: str) -> list[str | int]:
        return _TOKEN_RE.findall(text)

    def spans(self, text: str) -> list[tuple[int, int]]:
        return [m.span() for m in _TOKEN_RE.finditer(text)]

    def truncate(self, text: str, max_tokens: int) -> str:
        spans = self.spans(text)
        if len(spans) <= max_tokens:
            return text
        if max_tokens <= 0:
            return ""
        return text[: spans[max_tokens - 1][1]]


class HFTokenizer(Tokenizer):
    """Exact sub-word counts using the local model's own Hugging Face tokenizer."""

    def __init__(self, name: str):
        try:
            from transformers import AutoTokenizer  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("tokenizer.backend=hf requires the 'transformers' package") from exc
        self.name = f"hf:{name}"
        self._tok = AutoTokenizer.from_pretrained(name)

    def encode(self, text: str) -> list[str | int]:
        return self._tok.encode(text, add_special_tokens=False)

    def truncate(self, text: str, max_tokens: int) -> str:
        ids = self._tok.encode(text, add_special_tokens=False)
        return text if len(ids) <= max_tokens else self._tok.decode(ids[:max_tokens])


def build_tokenizer(backend: str = "regex", name: str | None = None) -> Tokenizer:
    if backend == "regex":
        return RegexTokenizer()
    if backend == "hf":
        if not name:
            raise ValueError("tokenizer.name is required for the hf backend")
        return HFTokenizer(name)
    raise ValueError(f"unknown tokenizer backend {backend!r}")

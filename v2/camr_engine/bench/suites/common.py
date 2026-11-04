"""What every suite shares: the item a runner asks, where downloads live, token estimates, chunks and verdicts.

Verdicts use the ruler's words (see camr_engine.ruler.grade), so one record reads the same whatever the suite:
  right          the answer is right
  wrong          the answer is something else
  declined       said it doesn't know, but the answer was in the context
  right_abstain  said it doesn't know, and the context never held the answer
  false_memory   answered something the context never held
"""

from __future__ import annotations

import os
import random
import re
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from camr_engine.ruler.grade import abstains

CHARS_PER_TOKEN = 4.0  # English text, measured on BABILong: 1M tokens is about 4.0 MB of text
V2 = Path(__file__).resolve().parents[3]
RIGHT = {"right", "right_abstain"}


def data_dir(name: str = "") -> Path:
    """Where downloads live: $CAMR_DATASETS, else the worktree's ignored ``work/datasets/``."""
    env = os.environ.get("CAMR_DATASETS")
    if env:
        root = Path(env)
    elif (V2.parent / "work").is_dir():
        root = V2.parent / "work" / "datasets"
    else:
        root = V2 / "work" / "datasets"
    return root / name if name else root


@dataclass
class Item:
    """One question a runner asks. ``context`` is the long text, or its chunks to feed in order; ``answer`` is the
    right answer, or every answer that counts as right."""

    id: str
    suite: str
    context: str | list[str]
    question: str
    answer: str | list[str]
    length_tokens: int
    meta: dict[str, Any] = field(default_factory=dict)

    @property
    def expected(self) -> str | list[str]:  # the name the Claude runner reads
        return self.answer

    @property
    def answers(self) -> list[str]:
        return [self.answer] if isinstance(self.answer, str) else list(self.answer)

    @property
    def chunks(self) -> list[str]:
        return [self.context] if isinstance(self.context, str) else list(self.context)

    @property
    def should_decline(self) -> bool:
        return bool(self.meta.get("abstention"))

    def summary(self, width: int = 70) -> str:
        """One line for a person: id, size and the question."""
        q = " ".join(self.question.split())
        q = q if len(q) <= width else q[: width - 1] + "…"
        if not self.context:
            return f"{self.id}  no context, ~{self.length_tokens:,} tokens  Q: {q}"
        n = len(self.chunks)
        return f"{self.id}  ~{self.length_tokens:,} tokens in {n} chunk{'s' if n != 1 else ''}  Q: {q}"


def estimate_tokens(text: str | Sequence[str]) -> int:
    """About four characters to a token."""
    n = len(text) if isinstance(text, str) else sum(len(t) for t in text)
    return round(n / CHARS_PER_TOKEN)


def rng(seed: int | str, *keys: Any) -> random.Random:
    """A random stream fixed by the seed and the keys, the same in every run (string seeds hash with SHA-512)."""
    return random.Random(":".join(str(k) for k in (seed, *keys)))


_SENTENCE = re.compile(r"(?<=[.!?])\s+")


def _pieces(text: str, pattern: re.Pattern) -> list[str]:
    out, last = [], 0
    for m in pattern.finditer(text):
        out.append(text[last:m.end()])
        last = m.end()
    if last < len(text):
        out.append(text[last:])
    return out


def chunk(text: str, tokens: int = 4096) -> list[str]:
    """Pieces of at most about ``tokens`` tokens, cut at line ends (so a numbered fact keeps its number), and at
    sentence ends only inside a line too long for one piece. Joined back, they give the text."""
    limit = max(1, int(tokens * CHARS_PER_TOKEN))
    units = []
    for line in text.splitlines(keepends=True):
        units += _pieces(line, _SENTENCE) if len(line) > limit else [line]
    out: list[str] = []
    cur = ""
    for u in units:
        while len(u) > limit:  # one sentence longer than a chunk: cut it where it must
            if cur:
                out.append(cur)
                cur = ""
            out.append(u[:limit])
            u = u[limit:]
        if len(cur) + len(u) > limit and cur:
            out.append(cur)
            cur = ""
        cur += u
    if cur:
        out.append(cur)
    return out


_THINK = re.compile(r"<think>.*?</think>", re.S)


def clean(reply: str | None) -> str:
    """The reply without its thinking: a closed <think> block is dropped; an unclosed one leaves nothing."""
    t = _THINK.sub("", reply or "")
    if "<think>" in t:
        t = t[: t.index("<think>")]
    return t.strip()


def verdict(right: bool, reply: str, should_decline: bool = False) -> str:
    """The verdict for a reply, given whether its answer is right (see the module docstring)."""
    if should_decline:
        return "right_abstain" if abstains(reply) else "false_memory"
    if right:
        return "right"
    return "declined" if abstains(reply) else "wrong"


def hub_file(repo: str, filename: str, revision: str, folder: str) -> Path:
    """A dataset file from the Hugging Face Hub, kept under ``data_dir(folder)``; no network once it is there."""
    path = data_dir(folder) / filename
    if path.exists():
        return path
    from huggingface_hub import hf_hub_download

    return Path(hf_hub_download(repo, filename, repo_type="dataset", revision=revision, local_dir=data_dir(folder)))

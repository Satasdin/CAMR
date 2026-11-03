"""The models every contender shares, run with MLX on the Mac: a reader (the frozen language model) and an embedder.

Imports of MLX are inside the classes, so the rest of the package (lives, grading, records) runs anywhere.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

import numpy as np

READER = "mlx-community/Qwen3-1.7B-4bit"
READER_BIG = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
READER_27B = "mlx-community/Qwen3.8-27B-4bit"  # 16 GB; hybrid attention, so it reads CAMR v2's memory as words
EMBEDDER = "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"
MAX_ANSWER_TOKENS = 40
PREFILL_STEP = 2048


@dataclass
class Reply:
    text: str
    ttft_s: float  # question asked -> first word, as a user would wait for it
    gen_tps: float
    prompt_tokens: int
    gen_tokens: int
    pieces: list[str] = field(default_factory=list)  # the text each written token added, in order


class Reader:
    """A frozen chat model. Greedy decoding and thinking off, so an answer is the same on every run."""

    def __init__(self, repo: str = READER, max_tokens: int = MAX_ANSWER_TOKENS):
        from mlx_lm import load

        self.repo, self.max_tokens = repo, max_tokens
        self.model, self.tok = load(repo)

    def chat_ids(self, system: str, user: str, tools: list | None = None) -> list[int]:
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = self.tok.apply_chat_template(msgs, tools=tools, add_generation_prompt=True, enable_thinking=False,
                                            tokenize=False)
        return self.tok.encode(text)

    def split_ids(self, system: str, user: str) -> tuple[list[int], list[int]]:
        """The chat as (the system part, the rest), so the system part can be read once and kept as a cache."""
        msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
        text = self.tok.apply_chat_template(msgs, add_generation_prompt=True, enable_thinking=False, tokenize=False)
        cut = text.index(system) + len(system)
        head, ids = self.tok.encode(text[:cut]), self.tok.encode(text)
        if ids[:len(head)] != head:
            raise ValueError("the system part does not tokenize on its own")
        return head, ids[len(head):]

    def generate(self, ids: list[int], cache=None, max_tokens: int | None = None) -> Reply:
        from mlx_lm import stream_generate

        t0 = time.perf_counter()
        first, pieces, r = None, [], None
        for r in stream_generate(self.model, self.tok, ids, max_tokens=max_tokens or self.max_tokens, prompt_cache=cache):
            first = first or time.perf_counter() - t0
            pieces.append(r.text)
        return Reply("".join(pieces).strip(), first or 0.0, r.generation_tps if r else 0.0, len(ids),
                     r.generation_tokens if r else 0, pieces)

    def new_cache(self, ids: list[int]):
        """A cache holding the model's notes on ``ids`` (read in steps, so a long text fits in memory)."""
        import mlx.core as mx
        from mlx_lm.models.cache import make_prompt_cache

        cache = make_prompt_cache(self.model)
        for i in range(0, len(ids), PREFILL_STEP):
            self.model(mx.array(ids[i:i + PREFILL_STEP])[None], cache=cache)
            mx.eval([c.state for c in cache])
        return cache

    @staticmethod
    def rewind(cache, length: int) -> None:
        """Drop everything after the first ``length`` tokens (a question and its answer)."""
        from mlx_lm.models.cache import trim_prompt_cache

        extra = cache[0].offset - length
        if extra > 0:
            trim_prompt_cache(cache, extra)


class Embedder:
    """Qwen3-Embedding: the last token's hidden state, unit length. Questions carry the model's instruction prefix."""

    INSTRUCTION = "Instruct: Given a question about the user's life, retrieve the user's notes that answer it\nQuery:"

    def __init__(self, repo: str = EMBEDDER):
        from mlx_lm import load

        self.model, self.tok = load(repo)
        self.name = f"mlx:{repo.split('/')[-1]}"
        self.dim = int(self.encode(["dimension probe"]).shape[1])

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        import mlx.core as mx

        out = []
        for t in texts:
            ids = self.tok.encode((self.INSTRUCTION + t) if is_query else t) + [self.tok.eos_token_id]
            h = self.model.model(mx.array(ids)[None])[0, -1]
            out.append(np.array(h.astype(mx.float32)))
        v = np.stack(out) if out else np.zeros((0, 1024), dtype=np.float32)
        return (v / np.linalg.norm(v, axis=1, keepdims=True)).astype(np.float32)

    def encode_one(self, text: str, *, is_query: bool = False) -> np.ndarray:
        return self.encode([text], is_query=is_query)[0]


def peak_reset() -> None:
    try:
        import mlx.core as mx

        mx.reset_peak_memory()
    except ImportError:
        pass


def peak_gb() -> float | None:
    try:
        import mlx.core as mx

        return mx.get_peak_memory() / 1e9
    except ImportError:
        return None

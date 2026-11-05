"""The models every contender shares, run with MLX on the Mac: a reader (the frozen language model) and an embedder.

Imports of MLX are inside the classes, so the rest of the package (lives, grading, records) runs anywhere.
"""

from __future__ import annotations

import ctypes
import os
import time
from dataclasses import dataclass, field
from types import SimpleNamespace

import numpy as np

READER = "mlx-community/Qwen3-1.7B-4bit"
READER_BIG = "mlx-community/Qwen3-4B-Instruct-2507-4bit"
READER_27B = "mlx-community/Qwen3.8-27B-4bit"  # 16 GB; hybrid attention, so it reads CAMR v2's memory as words
EMBEDDER = "mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ"
SEER = "mlx-community/Qwen2.5-VL-3B-Instruct-4bit"  # a vision model: reads files for camr_engine.media
DESCRIBE_TOKENS = 400  # room for what is written in an image, or its caption
THINK_DESCRIBE_TOKENS = 1600  # a thinking vision model reasons before it describes
MAX_ANSWER_TOKENS = 40
PREFILL_STEP = 2048
# MLX keeps every freed GPU buffer for reuse, by default up to the whole GPU limit (about 18 GB on a 24 GB Mac). A
# long ingest frees a desk's worth of buffers for every moment, so the process grows until macOS compresses and swaps
# it: 19 GB for the 4B at 3M tokens, of which 1 GB was resident. The cap keeps a reusable buffer cache and no more.
# CAMR_MLX_CACHE_GB sets it; "off" leaves MLX's default.
CACHE_GB = os.environ.get("CAMR_MLX_CACHE_GB", "1")


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

        from camr_engine.live import current, load_layers

        limit_cache()
        self.repo, self.max_tokens = repo, max_tokens
        live = current()
        if live is None:
            self.model, self.tok = load(repo)
        else:  # read in layer by layer, so whoever watches sees the weights arrive
            self.model, self.tok = load(repo, lazy=True)
            load_layers(self.model, live, repo)
        if hasattr(self.model, "language_model"):  # a vision model's checkpoint: mlx_lm loads its language half
            self.model.args = text_args(self.model.language_model.args)

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

        from camr_engine.live import current, measuring_layers, taken

        t0 = time.perf_counter()
        first, pieces, r = None, [], None
        live = current()
        with measuring_layers():
            for r in stream_generate(self.model, self.tok, ids, max_tokens=max_tokens or self.max_tokens,
                                     prompt_cache=cache):
                first = first or time.perf_counter() - t0
                pieces.append(r.text)
                if live is not None:
                    live.add("token", n=len(pieces), text=r.text, layers=taken())
                    if live.stopped:  # the person pressed Stop
                        break
        return Reply("".join(pieces).strip(), first or 0.0, r.generation_tps if r else 0.0, len(ids),
                     r.generation_tokens if r else 0, pieces)

    def new_cache(self, ids: list[int]):
        """A cache holding the model's notes on ``ids`` (read in steps, so a long text fits in memory)."""
        import mlx.core as mx
        from mlx_lm.models.cache import make_prompt_cache

        from camr_engine.live import current, measuring_layers, taken

        cache = make_prompt_cache(self.model)
        live = current()
        with measuring_layers():
            for i in range(0, len(ids), PREFILL_STEP):
                self.model(mx.array(ids[i:i + PREFILL_STEP])[None], cache=cache)
                mx.eval([c.state for c in cache])
                if live is not None:
                    live.add("read", tokens=min(i + PREFILL_STEP, len(ids)), of=len(ids), layers=taken())
        return cache

    @staticmethod
    def rewind(cache, length: int) -> None:
        """Drop everything after the first ``length`` tokens (a question and its answer)."""
        from mlx_lm.models.cache import trim_prompt_cache

        extra = cache[0].offset - length
        if extra > 0:
            trim_prompt_cache(cache, extra)


def text_args(args) -> SimpleNamespace:
    """A vision checkpoint's language half as the notes see it. Qwen2.5-VL's M-RoPE turns a word by the same position
    on all three of its axes, which is plain RoPE (mlx_lm runs it as nn.RoPE); any other scaling is kept, so the
    notes refuse it. ``head_dim`` is worked out when the config leaves it out."""
    d = dict(vars(args))
    scaling = d.get("rope_scaling") or {}
    if (scaling.get("type") or scaling.get("rope_type")) == "mrope":
        d["rope_scaling"] = None
    if not d.get("head_dim"):
        d["head_dim"] = d["hidden_size"] // d["num_attention_heads"]
    return SimpleNamespace(**d)


class Seer:
    """A vision model through mlx-vlm: it reads images and answers with them in view. Greedy, so an image always gets
    the same words; such models have no thinking to turn off. ``describe`` is camr_engine.media's reader of images."""

    def __init__(self, repo: str = SEER, max_tokens: int = MAX_ANSWER_TOKENS):
        from mlx_vlm import load
        from mlx_vlm.utils import load_config

        limit_cache()
        self.repo, self.max_tokens = repo, max_tokens
        self.model, self.processor = load(repo)
        tower = getattr(self.model, "vision_tower", None)
        if tower is not None:  # in float16 Qwen2.5-VL's tower overflows on some photos, and every word comes out "!"
            import mlx.core as mx

            tower.set_dtype(mx.bfloat16)
        self.config = load_config(repo)
        self.tok = getattr(self.processor, "tokenizer", self.processor)

    def prompt(self, system: str | None, user: str, images: int) -> str:
        from mlx_vlm.prompt_utils import apply_chat_template

        msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": user}]
        return apply_chat_template(self.processor, self.config, msgs, num_images=images)

    def see(self, images: list, system: str | None, user: str, max_tokens: int | None = None) -> Reply:
        """Answer ``user`` with ``images`` (paths or PIL images) in view, after ``system``."""
        from mlx_vlm import stream_generate

        from camr_engine.media import open_image

        pics = [open_image(x) if isinstance(x, (str, os.PathLike)) else x for x in images]
        prompt = self.prompt(system, user, len(pics))
        t0 = time.perf_counter()
        first, pieces, r = None, [], None
        for r in stream_generate(self.model, self.processor, prompt, image=pics or None,
                                 max_tokens=max_tokens or self.max_tokens, temperature=0.0):
            first = first or time.perf_counter() - t0
            pieces.append(r.text)
        return Reply("".join(pieces).strip(), first or 0.0, r.generation_tps if r else 0.0,
                     r.prompt_tokens if r else 0, r.generation_tokens if r else 0, pieces)

    def describe(self, image, ask: str) -> str:
        """What is in ``image``, as ``ask`` asks; a thinking model's reasoning is left out."""
        thinks = "Thinking" in (self.repo or "")
        text = self.see([image], None, ask, max_tokens=THINK_DESCRIBE_TOKENS if thinks else DESCRIBE_TOKENS).text
        return text.split("</think>", 1)[1].strip() if "</think>" in text else text


class Embedder:
    """Qwen3-Embedding: the last token's hidden state, unit length. Questions carry the model's instruction prefix."""

    INSTRUCTION = "Instruct: Given a question about the user's life, retrieve the user's notes that answer it\nQuery:"

    def __init__(self, repo: str = EMBEDDER):
        from mlx_lm import load

        limit_cache()
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


def limit_cache(gb: str | float | None = None) -> int | None:
    """Cap MLX's cache of freed buffers at ``gb`` (CACHE_GB by default). Returns the cap in bytes, or None when it is
    left at MLX's default ("off") or MLX is missing."""
    gb = CACHE_GB if gb is None else gb
    if str(gb).lower() == "off":
        return None
    try:
        import mlx.core as mx
    except ImportError:
        return None
    n = int(float(gb) * 1e9)
    mx.set_cache_limit(n)
    return n


def footprint_bytes(pid: int | None = None) -> int | None:
    """The process's physical footprint, as Activity Monitor's Memory column counts it: resident pages, compressed
    pages and the GPU memory it holds. MLX's own peak counts only arrays in use. None where macOS's libproc is not."""
    try:
        lib = ctypes.CDLL("/usr/lib/libproc.dylib")
        lib.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        info = (ctypes.c_uint64 * 16)()  # rusage_info_v0: a 16-byte uuid, then user and system time, ..., footprint
        if lib.proc_pid_rusage(os.getpid() if pid is None else pid, 0, info) != 0:
            return None
        return int(info[9])
    except (OSError, AttributeError):
        return None


def peak_footprint_bytes(pid: int | None = None) -> int | None:
    """The most the process's physical footprint has been since it started (rusage_info_v4's
    ri_lifetime_max_phys_footprint), or None where macOS's libproc is not."""
    try:
        lib = ctypes.CDLL("/usr/lib/libproc.dylib")
        lib.proc_pid_rusage.argtypes = [ctypes.c_int, ctypes.c_int, ctypes.c_void_p]
        info = (ctypes.c_uint64 * 40)()  # rusage_info_v4: 37 numbers, the uuid counted as two
        if lib.proc_pid_rusage(os.getpid() if pid is None else pid, 4, info) != 0:
            return None
        return int(info[30])
    except (OSError, AttributeError):
        return None

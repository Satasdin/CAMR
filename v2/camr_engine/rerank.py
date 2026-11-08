"""A second, closer look at the moments the finder put first: a small cross-encoder reads the question and each
candidate line together and scores how well that line answers it.

The finder (camr_engine.finder) scores words and meaning separately, so a line that shares the question's rare words
but answers something else can rank above the line that answers it. A cross-encoder reads both at once. The one used
is ``cross-encoder/ms-marco-MiniLM-L-6-v2`` (6 layers, 384 wide, 22M weights), run here in MLX from its own
safetensors: no torch. It reads about fifty short lines for a question in a few tens of milliseconds.

``Reranker.order`` takes the finder's best moments and puts them in a new order: each moment scores as its best line
(lines picked first by the question's words, so a forty-line group chat is not read whole). ``second_look`` is the
two-round search of a two-hop question ("who handles payroll?" -> "Kevin"; "Kevin's extension?" -> "214"): the best
line's new words are searched for, and what that finds is scored against the question and that line together.
"""

from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Sequence

import mlx.core as mx
import mlx.nn as nn
import numpy as np

RERANKER = "cross-encoder/ms-marco-MiniLM-L-6-v2"
MAX_TOKENS = 192  # a question and one line: well under the model's 512
LINES_PER_MOMENT = 3  # a moment's lines read by the cross-encoder: its best ones by the question's words
BATCH = 64


def _snapshot(repo: str) -> Path:
    from huggingface_hub import snapshot_download

    return Path(snapshot_download(repo, local_files_only=True))


class _Layer(nn.Module):
    def __init__(self, d: int, heads: int, ff: int, eps: float):
        super().__init__()
        self.heads = heads
        self.q, self.k, self.v, self.o = (nn.Linear(d, d) for _ in range(4))
        self.ln1, self.ln2 = nn.LayerNorm(d, eps=eps), nn.LayerNorm(d, eps=eps)
        self.up, self.down = nn.Linear(d, ff), nn.Linear(ff, d)

    def __call__(self, x, mask):
        b, n, d = x.shape
        h = self.heads

        def split(t):
            return t.reshape(b, n, h, d // h).transpose(0, 2, 1, 3)

        a = mx.fast.scaled_dot_product_attention(split(self.q(x)), split(self.k(x)), split(self.v(x)),
                                                 scale=1 / math.sqrt(d // h), mask=mask)
        x = self.ln1(x + self.o(a.transpose(0, 2, 1, 3).reshape(b, n, d)))
        return self.ln2(x + self.down(nn.gelu(self.up(x))))


class _CrossEncoder(nn.Module):
    def __init__(self, cfg: dict):
        super().__init__()
        d, eps = cfg["hidden_size"], cfg["layer_norm_eps"]
        self.word = nn.Embedding(cfg["vocab_size"], d)
        self.pos = nn.Embedding(cfg["max_position_embeddings"], d)
        self.type = nn.Embedding(cfg["type_vocab_size"], d)
        self.ln = nn.LayerNorm(d, eps=eps)
        self.layers = [_Layer(d, cfg["num_attention_heads"], cfg["intermediate_size"], eps)
                       for _ in range(cfg["num_hidden_layers"])]
        self.pool = nn.Linear(d, d)
        self.out = nn.Linear(d, 1)

    def __call__(self, ids, types, keep):
        n = ids.shape[1]
        x = self.ln(self.word(ids) + self.pos(mx.arange(n))[None] + self.type(types))
        mask = mx.where(keep[:, None, None, :], 0.0, -1e9).astype(x.dtype)
        for layer in self.layers:
            x = layer(x, mask)
        return self.out(mx.tanh(self.pool(x[:, 0])))[:, 0]


_NAMES = {"word": "embeddings.word_embeddings", "pos": "embeddings.position_embeddings",
          "type": "embeddings.token_type_embeddings", "ln": "embeddings.LayerNorm", "pool": "pooler.dense"}
_LAYER = {"q": "attention.self.query", "k": "attention.self.key", "v": "attention.self.value",
          "o": "attention.output.dense", "ln1": "attention.output.LayerNorm", "up": "intermediate.dense",
          "down": "output.dense", "ln2": "output.LayerNorm"}


def _load(folder: Path) -> _CrossEncoder:
    cfg = json.loads((folder / "config.json").read_text())
    model = _CrossEncoder(cfg)
    raw = mx.load(str(folder / "model.safetensors"))
    w = {}
    for ours, theirs in _NAMES.items():
        for p in ("weight", "bias"):
            if f"bert.{theirs}.{p}" in raw:
                w[f"{ours}.{p}"] = raw[f"bert.{theirs}.{p}"]
    for i in range(cfg["num_hidden_layers"]):
        for ours, theirs in _LAYER.items():
            for p in ("weight", "bias"):
                w[f"layers.{i}.{ours}.{p}"] = raw[f"bert.encoder.layer.{i}.{theirs}.{p}"]
    w["out.weight"], w["out.bias"] = raw["classifier.weight"], raw["classifier.bias"]
    model.load_weights(list(w.items()), strict=True)
    model.eval()
    mx.eval(model.parameters())
    return model


class Reranker:
    """Scores (question, line) pairs; higher is a better answer. Loaded once and kept."""

    def __init__(self, repo: str = RERANKER):
        from tokenizers import Tokenizer

        folder = _snapshot(repo)
        self.repo = repo
        self.model = _load(folder)
        self.tok = Tokenizer.from_file(str(folder / "tokenizer.json"))
        self.tok.enable_truncation(MAX_TOKENS)
        self.tok.no_padding()

    def scores(self, question: str, texts: Sequence[str]) -> np.ndarray:
        out = []
        for s in range(0, len(texts), BATCH):
            enc = self.tok.encode_batch([(question, t) for t in texts[s:s + BATCH]])
            n = max(len(e.ids) for e in enc)
            ids = np.zeros((len(enc), n), dtype=np.int32)
            types = np.zeros_like(ids)
            keep = np.zeros((len(enc), n), dtype=bool)
            for i, e in enumerate(enc):
                ids[i, :len(e.ids)], types[i, :len(e.ids)], keep[i, :len(e.ids)] = e.ids, e.type_ids, True
            got = self.model(mx.array(ids), mx.array(types), mx.array(keep))
            mx.eval(got)
            out.append(np.array(got, dtype=np.float32))
        return np.concatenate(out) if out else np.zeros(0, dtype=np.float32)

    def candidates(self, index, question: str, mids: Sequence[int], per: int = LINES_PER_MOMENT
                   ) -> tuple[list[str], list[int]]:
        """Each moment's ``per`` best lines by the question's words (its first lines when none share a word)."""
        from camr_engine.finder import hinted

        ls = index.line_scores(hinted(question))
        if index._owner is None or len(index._owner) != len(index.owner):
            index._owner = np.asarray(index.owner, dtype=np.int64)
        owner = index._owner
        lines, of = [], []
        for m in mids:
            lo, hi = int(np.searchsorted(owner, m, "left")), int(np.searchsorted(owner, m, "right"))
            for i in sorted(lo + int(j) for j in np.argsort(-ls[lo:hi], kind="stable")[:per]):
                lines.append(index.lines[i])
                of.append(int(m))
        return lines, of

    def order(self, index, question: str, mids: Sequence[int], *, per: int = LINES_PER_MOMENT
              ) -> tuple[list[int], dict[int, tuple[float, str]]]:
        """``mids`` in a new order, best first: each moment as its best line by the cross-encoder. Also each
        moment's best (score, line)."""
        lines, of = self.candidates(index, question, mids, per)
        best: dict[int, tuple[float, str]] = {}
        for s, line, m in zip(self.scores(question, lines), lines, of):
            if m not in best or s > best[m][0]:
                best[m] = (float(s), line)
        ranked = sorted((m for m in dict.fromkeys(int(x) for x in mids)), key=lambda m: -best.get(m, (-1e9, ""))[0])
        return ranked, best

    def second_look(self, index, question: str, bridge: str, *, dense=None, scan: int = 32, keep: int = 2,
                    skip: Sequence[int] = ()) -> list[int]:
        """The two-round search: the question's best line so far (``bridge``) adds its own words; what those find
        is scored against the question and that line together, and the ``keep`` best moments not in ``skip`` are
        returned."""
        from camr_engine.finder import words

        new = [w for w in dict.fromkeys(words(bridge)) if w not in set(words(question))]
        if not new:
            return []
        found = [int(m) for m in index.order(question + " " + " ".join(new), dense, hop=False, head=scan)
                 if int(m) not in set(skip)]
        if not found:
            return []
        ranked, _ = self.order(index, bridge + " " + question, found)
        return ranked[:keep]


_SHARED: Reranker | None = None


def shared() -> Reranker:
    """One reranker per process."""
    global _SHARED
    if _SHARED is None:
        _SHARED = Reranker()
    return _SHARED


def second_search(index, question: str, first: Sequence[int], dense=None, *, keep: int = 2) -> list[int]:
    """What the finder's ``first`` moments are kept for, plus ``keep`` more from a second search. The finder's own
    order is kept (reranking it all lost answers on dev seeds 2/3: 197 of 269 in the first 8 against 209), and the
    reranker is used only to pick the bridge: the best line among ``first``. Searching for that line's new words
    filled the last two of 8 places better than the finder's 7th and 8th (217 against 209; DECISIONS.md, E-68).
    Without the cross-encoder's files on this machine nothing is added."""
    try:
        rr = shared()
    except Exception:  # the cross-encoder is not on this machine: the finder's moments alone, as before
        return []
    ranked, best = rr.order(index, question, first)
    if not ranked or ranked[0] not in best:
        return []
    return rr.second_look(index, question, best[ranked[0]][1], dense=dense, skip=first, keep=keep)

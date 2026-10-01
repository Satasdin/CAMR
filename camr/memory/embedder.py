"""Embedders expose a single ``encode`` operation returning fixed-dimension,
L2-normalised vectors (IR-03).
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod

import numpy as np

from camr.config import EmbedderConfig


class Embedder(ABC):
    name: str
    dim: int

    @abstractmethod
    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        """Return an (n, dim) float32 array of unit vectors."""

    def encode_one(self, text: str, *, is_query: bool = False) -> np.ndarray:
        return self.encode([text], is_query=is_query)[0]


class BGEEmbedder(Embedder):
    """Compact BGE sentence embedder run on the CPU (section 3.6.4).

    Set ``HF_HUB_OFFLINE=1`` after the first download so that loading the model
    never opens a network connection during an experiment (NFR-06).
    """

    def __init__(self, cfg: EmbedderConfig):
        try:
            from sentence_transformers import SentenceTransformer  # type: ignore
        except ImportError as exc:  # pragma: no cover - optional dependency
            raise RuntimeError("embedder.backend=bge requires `pip install camr[embed]`") from exc
        self.cfg = cfg
        self.name = cfg.name
        if cfg.torch_threads:
            import torch  # type: ignore

            torch.set_num_threads(cfg.torch_threads)
        self._model = SentenceTransformer(cfg.name, device=cfg.device)
        self.dim = int(self._model.get_sentence_embedding_dimension())
        if cfg.dim and cfg.dim != self.dim:
            raise ValueError(f"embedder.dim={cfg.dim} but {cfg.name} produces {self.dim}")

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        if is_query and self.cfg.query_instruction:
            texts = [self.cfg.query_instruction + t for t in texts]
        vecs = self._model.encode(
            texts,
            batch_size=self.cfg.batch_size,
            normalize_embeddings=True,
            convert_to_numpy=True,
            show_progress_bar=False,
        )
        return np.asarray(vecs, dtype=np.float32)


_WORD = re.compile(r"\w+", re.UNICODE)


class HashingEmbedder(Embedder):
    """Deterministic feature-hashing embedder (unigrams + bigrams).

    No model download and no randomness: used by the test suite and as a
    lexical baseline.  It is *not* a substitute for BGE in reported results.
    """

    def __init__(self, dim: int = 384):
        self.name = f"hashing-{dim}"
        self.dim = dim

    def _bucket(self, feature: str) -> tuple[int, float]:
        h = hashlib.blake2b(feature.encode(), digest_size=8).digest()
        idx = int.from_bytes(h[:4], "little") % self.dim
        sign = 1.0 if h[4] & 1 else -1.0
        return idx, sign

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        out = np.zeros((len(texts), self.dim), dtype=np.float32)
        for row, text in enumerate(texts):
            words = [w.casefold() for w in _WORD.findall(text)]
            feats = words + [f"{a}_{b}" for a, b in zip(words, words[1:])]
            for f in feats:
                idx, sign = self._bucket(f)
                out[row, idx] += sign
            norm = float(np.linalg.norm(out[row]))
            if norm > 0:
                out[row] /= norm
        return out


def build_embedder(cfg: EmbedderConfig) -> Embedder:
    if cfg.backend == "bge":
        return BGEEmbedder(cfg)
    return HashingEmbedder(cfg.dim)

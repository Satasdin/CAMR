"""Embedders expose a single ``encode`` operation returning fixed-dimension,
L2-normalised vectors (IR-03).
"""

from __future__ import annotations

import hashlib
import re
from abc import ABC, abstractmethod
from collections import OrderedDict

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


class OllamaEmbedder(Embedder):
    """Embeddings from a local Ollama embedding model (used by CAMR Personal).

    It removes PyTorch from the app entirely: the user already runs Ollama, so the
    embedder is one more small model there. Query and document prefixes follow
    each model's card; vectors are L2-normalised here.
    """

    # model name prefix -> (query prefix, document prefix)
    PREFIXES = {
        "nomic-embed-text": ("search_query: ", "search_document: "),
        "snowflake-arctic-embed": ("Represent this sentence for searching relevant passages: ", ""),
        "mxbai-embed-large": ("Represent this sentence for searching relevant passages: ", ""),
    }

    QUERY_CACHE_SIZE = 256

    def __init__(self, name: str = "nomic-embed-text", host: str = "http://127.0.0.1:11434", session=None,
                 timeout_s: float = 120.0):
        import requests

        self.name = f"ollama:{name}"
        self.model, self.host, self.timeout_s = name, host.rstrip("/"), timeout_s
        self._http = session or requests.Session()
        base = name.split(":")[0]
        self.query_prefix, self.doc_prefix = self.PREFIXES.get(base, ("", ""))
        self._query_cache: OrderedDict[str, np.ndarray] = OrderedDict()  # repeated questions skip the model call
        self.dim = int(self._raw(["dimension probe"]).shape[1])

    def _raw(self, texts: list[str]) -> np.ndarray:
        resp = self._http.post(f"{self.host}/api/embed", json={"model": self.model, "input": texts},
                               timeout=self.timeout_s)
        resp.raise_for_status()
        vecs = np.asarray(resp.json()["embeddings"], dtype=np.float32)
        norms = np.linalg.norm(vecs, axis=1, keepdims=True)
        return vecs / np.where(norms == 0, 1.0, norms)

    def encode(self, texts: list[str], *, is_query: bool = False) -> np.ndarray:
        prefix = self.query_prefix if is_query else self.doc_prefix
        if is_query and len(texts) == 1:
            hit = self._query_cache.get(texts[0])
            if hit is not None:
                self._query_cache.move_to_end(texts[0])
                return hit[None, :]
            vec = self._raw([prefix + texts[0]])
            self._query_cache[texts[0]] = vec[0]
            if len(self._query_cache) > self.QUERY_CACHE_SIZE:
                self._query_cache.popitem(last=False)
            return vec
        out = [self._raw([prefix + t for t in texts[i:i + 32]]) for i in range(0, len(texts), 32)]
        return np.vstack(out) if out else np.zeros((0, self.dim), dtype=np.float32)


def build_embedder(cfg: EmbedderConfig) -> Embedder:
    if cfg.backend == "bge":
        return BGEEmbedder(cfg)
    if cfg.backend == "ollama":
        return OllamaEmbedder(cfg.name)
    return HashingEmbedder(cfg.dim)

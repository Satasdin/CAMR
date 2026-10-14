"""A learned index for memory that has outgrown exact search (built during sleep).

Exact search compares the question with every stored vector, so its time and the
memory it touches grow with the store. The inverted-file index (IVF; Jégou et al.,
2011) learns ``C`` centroids by spherical k-means and files every note under its
nearest one. A question is compared with the centroids, then only with the notes of
the ``nprobe`` closest clusters:

    cost ≈ C·d + (nprobe / C)·N·d       instead of  N·d

With C ≈ √N that is O(√N) per question. The vectors are stored sorted by cluster in a
memory-mapped file, so a question reads only the clusters it probes from disk; the
rest of the memory is never brought into RAM.

Notes written after the index was built ("fresh" notes, id > ``max_note_id``) are
searched exactly until the next sleep files them, like a short-term buffer that
consolidation empties.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


def spherical_kmeans(x: np.ndarray, k: int, iters: int = 15, seed: int = 13, sample: int = 60000) -> np.ndarray:
    """Centroids (k x d, unit length) of unit vectors ``x``; trained on a sample when x is large."""
    rng = np.random.default_rng(seed)
    train = x if len(x) <= sample else x[rng.choice(len(x), sample, replace=False)]
    # k-means++ seeding on cosine distance
    cent = [train[rng.integers(len(train))]]
    d2 = 1.0 - train @ cent[0]
    for _ in range(1, k):
        p = np.clip(d2, 0, None)
        p = p / p.sum() if p.sum() > 0 else None
        cent.append(train[rng.choice(len(train), p=p)])
        d2 = np.minimum(d2, 1.0 - train @ cent[-1])
    c = np.vstack(cent).astype(np.float32)
    for _ in range(iters):
        assign = np.argmax(train @ c.T, axis=1)
        for j in range(k):
            members = train[assign == j]
            if len(members):
                c[j] = members.sum(axis=0)
            else:  # empty cluster: re-seed on the worst-served point
                c[j] = train[np.argmin(np.max(train @ c.T, axis=1))]
        c = _unit(c)
    return c


@dataclass
class IVFIndex:
    root: Path
    centroids: np.ndarray       # C x d
    offsets: np.ndarray         # C + 1, rows of cluster j are offsets[j]:offsets[j+1]
    ids: np.ndarray             # N note ids, sorted by cluster
    vectors: np.ndarray         # N x d unit vectors (memory-mapped), same order as ids
    max_note_id: int
    note_type: str
    built_at: float
    nprobe: int = 8

    # ---------------------------------------------------------------- build / load
    @classmethod
    def build(cls, root: str | Path, ids: np.ndarray, vectors: np.ndarray, note_type: str, *,
              n_clusters: int | None = None, nprobe: int | None = None, seed: int = 13) -> "IVFIndex":
        root = Path(root)
        root.mkdir(parents=True, exist_ok=True)
        x = _unit(np.asarray(vectors, dtype=np.float32))
        n, d = x.shape
        k = n_clusters or int(np.clip(round(np.sqrt(n)), 4, 4096))
        k = min(k, n)
        cent = spherical_kmeans(x, k, seed=seed)
        assign = np.empty(n, dtype=np.int64)
        for s in range(0, n, 65536):  # assign in blocks to bound memory
            assign[s:s + 65536] = np.argmax(x[s:s + 65536] @ cent.T, axis=1)
        order = np.argsort(assign, kind="stable")
        counts = np.bincount(assign, minlength=k)
        offsets = np.concatenate([[0], np.cumsum(counts)]).astype(np.int64)
        mm = np.lib.format.open_memmap(root / "vectors.npy", mode="w+", dtype=np.float32, shape=(n, d))
        for s in range(0, n, 65536):
            mm[s:s + 65536] = x[order[s:s + 65536]]
        mm.flush()
        del mm
        np.save(root / "ids.npy", np.asarray(ids, dtype=np.int64)[order])
        np.save(root / "centroids.npy", cent)
        np.save(root / "offsets.npy", offsets)
        # a quarter of the clusters: on 196k real paragraphs and 600 real questions, 25% of clusters kept recall@10
        # within 1.3 points of exact search (74.1% vs 75.4%); 8% of them lost 9 points (results/bulk/scale.json)
        probe = nprobe or max(4, int(round(k * 0.25)))
        meta = {"note_type": note_type, "max_note_id": int(np.max(ids)) if n else 0, "built_at": time.time(),
                "clusters": k, "notes": n, "nprobe": probe}
        (root / "meta.json").write_text(json.dumps(meta, indent=1))
        return cls.load(root)

    @classmethod
    def load(cls, root: str | Path) -> "IVFIndex":
        root = Path(root)
        meta = json.loads((root / "meta.json").read_text())
        return cls(root=root, centroids=np.load(root / "centroids.npy"), offsets=np.load(root / "offsets.npy"),
                   ids=np.load(root / "ids.npy"), vectors=np.load(root / "vectors.npy", mmap_mode="r"),
                   max_note_id=meta["max_note_id"], note_type=meta["note_type"], built_at=meta["built_at"],
                   nprobe=meta.get("nprobe", 8))

    @property
    def size(self) -> int:
        return len(self.ids)

    # ---------------------------------------------------------------- search
    def search(self, query: np.ndarray, k: int, nprobe: int | None = None) -> list[tuple[int, float]]:
        """Top-k (note id, cosine) among the notes of the ``nprobe`` clusters closest to the query."""
        q = np.asarray(query, dtype=np.float32)
        q = q / (np.linalg.norm(q) or 1.0)
        p = min(nprobe or self.nprobe, len(self.centroids))
        near = np.argpartition(-(self.centroids @ q), p - 1)[:p]
        ids, sims = [], []
        for c in near:
            a, b = int(self.offsets[c]), int(self.offsets[c + 1])
            if b > a:
                ids.append(self.ids[a:b])
                sims.append(np.asarray(self.vectors[a:b]) @ q)
        if not ids:
            return []
        ids_a, sims_a = np.concatenate(ids), np.concatenate(sims)
        top = np.argsort(-sims_a, kind="stable")[:k]
        return [(int(ids_a[j]), float(sims_a[j])) for j in top]

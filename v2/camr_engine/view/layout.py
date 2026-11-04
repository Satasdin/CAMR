"""Where each moment sits in the brain view: similar moments close together (t-SNE of their embeddings).

Plain numpy, exact t-SNE, which is plenty for the few thousand moments a person's memory holds in the view. The
result is cached beside the rooms and recomputed only when moments are added.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np


def _affinities(d: np.ndarray, perplexity: float) -> np.ndarray:
    """Each row's Gaussian neighbour probabilities, with the width found so its perplexity matches."""
    n = len(d)
    p = np.zeros((n, n))
    target = np.log(perplexity)
    for i in range(n):
        lo, hi, beta = 1e-20, 1e20, 1.0
        row = np.delete(d[i], i)
        for _ in range(60):
            w = np.exp(-(row - row.min()) * beta)
            s = w.sum()
            h = np.log(s) + beta * ((row - row.min()) * w).sum() / s
            if abs(h - target) < 1e-4:
                break
            if h > target:
                lo = beta
                beta = beta * 2 if hi == 1e20 else (beta + hi) / 2
            else:
                hi = beta
                beta = (beta + lo) / 2
        p[i, np.arange(n) != i] = w / s
    return p


def tsne(vectors: np.ndarray, perplexity: float = 18.0, iters: int = 750, seed: int = 0) -> np.ndarray:
    """2-D positions in [0, 1] for unit vectors, by cosine distance."""
    n = len(vectors)
    if n < 3:
        return np.full((n, 2), 0.5) if n else np.zeros((0, 2))
    x = vectors / np.linalg.norm(vectors, axis=1, keepdims=True)
    d = np.clip(1 - x @ x.T, 0, None) ** 2
    p = _affinities(d, min(perplexity, (n - 1) / 3))
    p = np.maximum((p + p.T) / (2 * n), 1e-12)
    c = x - x.mean(0)
    y = np.linalg.svd(c, full_matrices=False)[0][:, :2] * 1e-2  # a stable start: the two main directions
    rng = np.random.default_rng(seed)
    y += rng.normal(0, 1e-4, y.shape)
    lr, step, gains = max(n / 12 / 4, 50), np.zeros_like(y), np.ones_like(y)
    for it in range(iters):
        exag = 12.0 if it < 250 else 1.0
        diff = y[:, None, :] - y[None, :, :]
        q = 1 / (1 + (diff ** 2).sum(-1))
        np.fill_diagonal(q, 0)
        qn = np.maximum(q / q.sum(), 1e-12)
        grad = 4 * (((exag * p - qn) * q)[:, :, None] * diff).sum(1)
        gains = np.where(np.sign(grad) != np.sign(step), gains + 0.2, gains * 0.8).clip(0.01)
        step = (0.5 if it < 250 else 0.8) * step - lr * gains * grad
        y = y + step
        y -= y.mean(0)
    y = (y - y.min(0)) / np.maximum(y.max(0) - y.min(0), 1e-9)
    return y


def positions(rooms) -> list[list[float]]:
    """The view's positions for every moment in ``rooms``, cached in ``layout.json`` beside them."""
    cache = Path(rooms.path) / "layout.json"
    n = len(rooms.moments)
    if cache.exists():
        saved = json.loads(cache.read_text())
        if saved.get("moments") == n:
            return saved["xy"]
    xy = [[round(float(a), 4), round(float(b), 4)] for a, b in tsne(rooms.vectors)] if n else []
    cache.write_text(json.dumps({"moments": n, "xy": xy}))
    return xy

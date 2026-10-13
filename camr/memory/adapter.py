"""Query adapter: a small learned map that moves a question's vector towards the notes that answered it.

The embedder (and the language model) stay frozen. Sleep trains this one extra piece
from the engine's own experience: pairs (question, note that answered it), taken from
questions whose answers were approved or grounded and from what eager lookups found.

    q' = (q + U Vᵀ q) / ‖q + U Vᵀ q‖,      U, V ∈ R^{d×r},  r ≪ d,  U initialised to 0

so an untrained adapter is the identity. Training minimises the contrastive (InfoNCE)
loss over a batch of pairs, each question's own note against the other notes in the
batch and its hardest wrongly retrieved notes (van den Oord et al., 2018):

    L = −(1/B) Σ_b log [ exp(q'_b·n_b / T) / Σ_j exp(q'_b·n_j / T) ]

It is written in NumPy (no deep-learning framework), so it runs inside the packaged app.
Sleep keeps a newly trained adapter only if it raises recall on held-out pairs.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np


def _unit(x: np.ndarray) -> np.ndarray:
    n = np.linalg.norm(x, axis=-1, keepdims=True)
    n[n == 0] = 1.0
    return x / n


@dataclass
class QueryAdapter:
    U: np.ndarray
    V: np.ndarray

    @classmethod
    def identity(cls, dim: int, rank: int = 16, seed: int = 13) -> "QueryAdapter":
        rng = np.random.default_rng(seed)
        return cls(U=np.zeros((dim, rank), np.float32), V=(rng.standard_normal((dim, rank)) / np.sqrt(dim)).astype(
            np.float32))

    def apply(self, q: np.ndarray) -> np.ndarray:
        q = np.asarray(q, dtype=np.float32)
        out = q + (q @ self.V) @ self.U.T
        return _unit(out[None])[0] if out.ndim == 1 else _unit(out)

    # ---------------------------------------------------------------- persistence
    def save(self, path: str | Path, **meta) -> None:
        np.savez(path, U=self.U, V=self.V, **{k: np.asarray(v) for k, v in meta.items()})

    @classmethod
    def load(cls, path: str | Path) -> "QueryAdapter":
        z = np.load(path)
        return cls(U=z["U"], V=z["V"])

    # ---------------------------------------------------------------- training
    def fit(self, queries: np.ndarray, positives: np.ndarray, negatives: np.ndarray | None = None, *,
            epochs: int = 30, batch: int = 64, lr: float = 3e-3, temperature: float = 0.05, weight_decay: float = 1e-3,
            seed: int = 13) -> list[float]:
        """Adam on the InfoNCE loss. ``negatives`` (optional) is (n, h, d): hard negatives per pair."""
        rng = np.random.default_rng(seed)
        Q, P = _unit(np.asarray(queries, np.float32)), _unit(np.asarray(positives, np.float32))
        H = None if negatives is None else _unit(np.asarray(negatives, np.float32))
        m = {k: np.zeros_like(v) for k, v in (("U", self.U), ("V", self.V))}
        s = {k: np.zeros_like(v) for k, v in (("U", self.U), ("V", self.V))}
        b1, b2, step, losses = 0.9, 0.999, 0, []
        for _ in range(epochs):
            order = rng.permutation(len(Q))
            total = 0.0
            for start in range(0, len(Q), batch):
                idx = order[start:start + batch]
                q, pos = Q[idx], P[idx]
                cands = pos if H is None else np.concatenate([pos, H[idx].reshape(-1, Q.shape[1])])
                a = q @ self.V                       # B x r
                raw = q + a @ self.U.T               # B x d
                norm = np.linalg.norm(raw, axis=1, keepdims=True)
                z = raw / norm                       # adapted unit query
                logits = (z @ cands.T) / temperature  # B x C; positive of row b is column b
                logits -= logits.max(axis=1, keepdims=True)
                p = np.exp(logits)
                p /= p.sum(axis=1, keepdims=True)
                n = len(idx)
                total += float(-np.log(p[np.arange(n), np.arange(n)] + 1e-12).sum())
                p[np.arange(n), np.arange(n)] -= 1.0
                dz = (p @ cands) / (temperature * n)                  # dL/dz
                draw = (dz - z * (dz * z).sum(axis=1, keepdims=True)) / norm  # through the normalisation
                grads = {"U": draw.T @ a + weight_decay * self.U, "V": q.T @ (draw @ self.U) + weight_decay * self.V}
                step += 1
                for k, g in grads.items():
                    m[k] = b1 * m[k] + (1 - b1) * g
                    s[k] = b2 * s[k] + (1 - b2) * g * g
                    upd = lr * (m[k] / (1 - b1 ** step)) / (np.sqrt(s[k] / (1 - b2 ** step)) + 1e-8)
                    setattr(self, k, (getattr(self, k) - upd).astype(np.float32))
            losses.append(total / len(Q))
        return losses


def recall_at(query_vecs: np.ndarray, gold_ids: list[set[int]], ids: np.ndarray, matrix: np.ndarray, ks=(1, 5, 20),
              adapter: QueryAdapter | None = None) -> dict[str, float]:
    """Share of queries with a gold note among the top-k of exact search over ``matrix``."""
    q = _unit(np.asarray(query_vecs, np.float32))
    if adapter is not None:
        q = adapter.apply(q)
    sims = q @ _unit(np.asarray(matrix, np.float32)).T
    top = np.argsort(-sims, axis=1)[:, : max(ks)]
    out = {}
    for k in ks:
        hit = [bool(gold & set(ids[top[i, :k]].tolist())) for i, gold in enumerate(gold_ids)]
        out[f"recall@{k}"] = float(np.mean(hit)) if hit else 0.0
    return out

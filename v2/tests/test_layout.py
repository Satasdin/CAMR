"""The brain view's map: similar moments land together. No model is loaded."""

from __future__ import annotations

import numpy as np

from camr_engine.view.layout import tsne


def test_two_kinds_of_moment_land_in_two_places():
    rng = np.random.default_rng(0)
    a = np.array([1.0, 0, 0, 0]) + rng.normal(0, 0.05, (20, 4))
    b = np.array([0, 0, 1.0, 0]) + rng.normal(0, 0.05, (20, 4))
    y = tsne(np.vstack([a, b]), perplexity=8, iters=400)
    assert y.shape == (40, 2) and y.min() >= 0 and y.max() <= 1
    ca, cb = y[:20].mean(0), y[20:].mean(0)
    spread = max(np.linalg.norm(y[:20] - ca, axis=1).mean(), np.linalg.norm(y[20:] - cb, axis=1).mean())
    assert np.linalg.norm(ca - cb) > 3 * spread


def test_tiny_memories_still_get_positions():
    assert tsne(np.zeros((0, 4))).shape == (0, 2)
    assert tsne(np.eye(2, 4)).tolist() == [[0.5, 0.5], [0.5, 0.5]]

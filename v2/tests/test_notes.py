"""Sliding notes along the desk: turning keys written at one place gives the keys the model would write further on.
Needs MLX (the Mac); no model is loaded."""

from __future__ import annotations

import pytest

mx = pytest.importorskip("mlx.core")

from camr_engine.notes import turn  # noqa: E402


def test_turning_keys_moves_them_exactly_as_far_as_the_model_would():
    x = mx.random.normal((8, 50, 128), key=mx.random.key(0)).astype(mx.float32)
    written = mx.fast.rope(x, 128, traditional=False, base=1e6, scale=1.0, offset=37)
    moved = turn(written, mx.full((50,), 900, dtype=mx.int32), 1e6)
    there = mx.fast.rope(x, 128, traditional=False, base=1e6, scale=1.0, offset=937)
    assert mx.abs(moved - there).max().item() < 1e-3


def test_each_token_can_move_its_own_distance():
    x = mx.random.normal((2, 6, 64), key=mx.random.key(1)).astype(mx.float32)
    written = mx.fast.rope(x, 64, traditional=False, base=1e4, scale=1.0, offset=0)
    moved = turn(written, mx.array([0, 0, 0, 5, 5, 5]), 1e4)
    assert mx.allclose(moved[:, :3], written[:, :3], atol=1e-5).item()
    fives = mx.fast.rope(x[:, 3:], 64, traditional=False, base=1e4, scale=1.0, offset=8)
    assert mx.allclose(moved[:, 3:], fives, atol=1e-3).item()

"""Notes: what the model writes to itself inside its layers while it reads (its keys and values at every layer).

A room's notes are written as one continuous page: each new moment is read with the room's earlier moments in view,
straight after the header, and its notes are appended. On the desk, notes are slid to their place by turning their
keys, since a word's position is stored in its keys as a rotation (RoPE); values carry no position and are used as
written.

Rooms, not single moments, are the unit written together. Moments written alone and then laid side by side lose the
thread: with 30 unrelated moments beside the right one, a 1.7B model found 2 of 46 facts from such notes and 32 of
46 reading the same words (DECISIONS.md, E-15).

Notes are kept token by token, every layer together, so a room grows by appending bytes to the end of its file:
one token is ``layers × 2 × kv_heads × head_dim`` numbers (112 KB for Qwen3-1.7B at 16 bits).

On the SSD a token's numbers can be kept at 8 or 4 bits (``pack``, ``unpack``): every 64 numbers along a head share
one scale and one offset (MLX's affine quantization), so a token stays a fixed number of bytes, rooms still grow by
appending, and a token at 8 bits takes 17/32 of its 16-bit size (60 KB on the 1.7B), at 4 bits 9/32.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

BITS = (16, 8, 4)  # how a room's notes can be kept on the SSD: as the model wrote them, or quantized
GROUP = 64  # numbers sharing one scale and one offset when quantized


def stored_bytes(token_bytes: int, bits: int) -> int:
    """One token's notes on the SSD at ``bits``, from its size at 16 bits: the numbers at ``bits`` each, then a 16-bit
    scale and offset per group of 64."""
    if bits not in BITS:
        raise ValueError(f"notes are kept at {', '.join(map(str, BITS))} bits, not {bits}")
    if bits == 16:
        return token_bytes
    n = token_bytes // 2
    return n * bits // 8 + n // GROUP * 4


@dataclass(frozen=True)
class Shape:
    layers: int
    kv_heads: int
    head_dim: int
    rope_base: float

    @property
    def token_bytes(self) -> int:
        return self.layers * 2 * self.kv_heads * self.head_dim * 2

    def stored_bytes(self, bits: int) -> int:
        return stored_bytes(self.token_bytes, bits)


def pack(notes, bits: int = 16) -> bytes:
    """Notes (tokens, layers, 2, kv_heads, head_dim) as they go on the SSD at ``bits``, token by token. At 8 or 4 bits
    each token's bytes are its quantized numbers, then its scales, then its offsets, so a token's bytes stand alone
    and a room still grows by appending."""
    import mlx.core as mx

    if bits == 16:
        return bytes(np.array(notes.view(mx.uint16)))
    stored_bytes(2 * GROUP, bits)  # checks bits
    t, d = notes.shape[0], notes.shape[-1]
    w, scales, biases = mx.quantize(notes.reshape(-1, d), group_size=GROUP, bits=bits)
    parts = [np.array(w).view(np.uint8).reshape(t, -1)]
    parts += [np.array(x.view(mx.uint16)).view(np.uint8).reshape(t, -1) for x in (scales, biases)]
    return np.concatenate(parts, axis=1).tobytes()


def unpack(buf, shape: Shape, dtype, bits: int = 16):
    """Notes read off the SSD (``pack``'s bytes at ``bits``) as an array (tokens, layers, 2, kv_heads, head_dim) of
    ``dtype``, the model's own."""
    import mlx.core as mx

    if bits == 16:
        x = mx.array(np.frombuffer(buf, dtype=np.uint16)).view(dtype)
        return x.reshape(-1, shape.layers, 2, shape.kv_heads, shape.head_dim)
    n = shape.token_bytes // 2
    wb, sb = n * bits // 8, n // GROUP * 2
    raw = np.frombuffer(buf, dtype=np.uint8).reshape(-1, wb + 2 * sb)
    d = shape.head_dim
    w = mx.array(np.ascontiguousarray(raw[:, :wb]).view(np.uint32)).reshape(-1, d * bits // 32)
    scales, biases = (mx.array(np.ascontiguousarray(raw[:, a:a + sb]).view(np.uint16)).view(dtype)
                      .reshape(-1, d // GROUP) for a in (wb, wb + sb))
    x = mx.dequantize(w, scales, biases, group_size=GROUP, bits=bits)
    return x.reshape(-1, shape.layers, 2, shape.kv_heads, d)


def turn(x, positions, base: float):
    """Rotate ``x`` (…, tokens, head_dim) as RoPE does, by its own amount for each token (Qwen's split halves)."""
    import mlx.core as mx

    half = x.shape[-1] // 2
    inv = mx.power(base, -mx.arange(0, half, dtype=mx.float32) * 2 / x.shape[-1])
    ang = positions.astype(mx.float32)[:, None] * inv[None, :]
    cos, sin = mx.cos(ang), mx.sin(ang)
    x1, x2 = x[..., :half].astype(mx.float32), x[..., half:].astype(mx.float32)
    return mx.concatenate([x1 * cos - x2 * sin, x2 * cos + x1 * sin], axis=-1).astype(x.dtype)


class Notebook:
    """Writes notes and lays them on the desk, behind a fixed header whose notes stay in RAM (the core)."""

    def __init__(self, reader, header_ids: list[int]):
        import mlx.core as mx

        args = reader.model.args
        if getattr(args, "rope_scaling", None):
            raise ValueError("notes assume plain RoPE")
        self.reader, self.header = reader, list(header_ids)
        self.shape = Shape(len(reader.model.layers), args.num_key_value_heads, args.head_dim, float(args.rope_theta))
        cache = reader.new_cache(self.header)
        self.p = len(self.header)
        self.core = [(c.keys[..., :self.p, :], c.values[..., :self.p, :]) for c in cache]
        mx.eval(self.core)

    def write(self, ids: list[int], after=None):
        """The notes on ``ids``, read straight after the header and ``after`` (its room's notes so far, if any):
        an array (tokens, layers, 2, kv_heads, head_dim)."""
        import mlx.core as mx

        cache = self.desk([] if after is None else [after])
        a = self.p + (0 if after is None else after.shape[0])
        self.reader.model(mx.array(ids)[None], cache=cache)
        t = len(ids)
        per_layer = [mx.stack([c.keys[0, :, a:a + t, :], c.values[0, :, a:a + t, :]]) for c in cache]
        notes = mx.stack(per_layer).transpose(3, 0, 1, 2, 4)            # (tokens, layers, 2, heads, dim)
        mx.eval(notes)
        return notes

    def desk(self, rooms: list):
        """A cache holding the header and then each room's notes, side by side in the order given."""
        import mlx.core as mx
        from mlx_lm.models.cache import KVCache

        out = []
        if not rooms:
            for k, v in self.core:
                c = KVCache()
                c.state = (k, v, self.p)
                out.append(c)
            return out
        x = mx.concatenate(rooms, axis=0).transpose(1, 2, 3, 0, 4)     # (layers, 2, heads, N, dim)
        n = x.shape[3]
        # every room was written starting right after the header; on the desk its notes start further along
        starts = np.cumsum([0] + [len(r) for r in rooms[:-1]]).tolist()
        shift = mx.concatenate([mx.full((len(r),), s, dtype=mx.int32) for r, s in zip(rooms, starts)])
        moved = len(rooms) > 1  # a single room sits exactly where it was written
        for layer, (ck, cv) in enumerate(self.core):
            k = (turn(x[layer, 0], shift, self.shape.rope_base) if moved else x[layer, 0])[None]
            c = KVCache()
            c.state = (mx.concatenate([ck, k], axis=2), mx.concatenate([cv, x[layer, 1][None]], axis=2), self.p + n)
            out.append(c)
        mx.eval([c.keys for c in out] + [c.values for c in out])
        return out

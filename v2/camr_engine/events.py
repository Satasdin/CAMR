"""The event log: what camr did, small enough to write while it talks; the brain view replays it later.

Every event is one JSON line in ``events.jsonl`` beside the rooms:
- ``remember``: a moment joined a room;
- ``answer``: a question picked up a room and its closest moments (the desk), and for each word written, how hard
  that word looked at each node on the desk. A node is *used* when it drew at least ``USED`` of the desk's
  attention over the whole answer; the rest were only picked up.

How hard a word looks at a node is its share of the attention from that word, averaged over every head of four
middle-to-late layers. Watching four layers cost 0.6% of writing speed and watching all 28 cost 7.5%. In 47 right
answers, the node looked at hardest was the one holding the answer every time (DECISIONS.md, E-21).
"""

from __future__ import annotations

import datetime as dt
import json
from collections import defaultdict
from pathlib import Path

import numpy as np

LAYERS = (12, 16, 20, 24)  # Qwen3-1.7B has 28
USED = 0.10


class Looks:
    """While active, records how hard each written word looks at each node on the desk.

    ``spans`` gives each node's tokens on the desk as (node, first token after the header, how many tokens); a node
    can appear twice, in its room and re-read as words. ``prompt_len`` is every token before the first written one.
    """

    def __init__(self, reader, header: int, spans: list[tuple[int, int, int]], prompt_len: int, desk,
                 layers: tuple[int, ...] = LAYERS):
        import mlx.core as mx
        import mlx_lm.models.qwen3 as qwen3

        self._module = qwen3
        if not isinstance(reader.model, qwen3.Model):
            raise ValueError("looks are recorded for Qwen3 readers")
        self.nodes = sorted({n for n, _, _ in spans})
        col = {n: j for j, n in enumerate(self.nodes)}
        width = max(s + t for _, s, t in spans) if spans else 0
        a = np.zeros((width, len(self.nodes)), dtype=np.float32)
        for n, s, t in spans:
            a[s:s + t, col[n]] = 1.0
        self.lo, self.hi, self.a = header, header + width, mx.array(a)
        self.prompt_len = prompt_len
        self.layer_of = {id(c): i for i, c in enumerate(desk) if i in layers}
        self.calls: dict[int, dict[int, object]] = defaultdict(dict)

    def _spy(self, queries, keys, values, cache, scale, mask, **kw):
        import mlx.core as mx

        out = self._orig(queries, keys, values, cache=cache, scale=scale, mask=mask, **kw)
        layer = self.layer_of.get(id(cache))
        if layer is not None and self.nodes:
            q = queries[0, :, -1, :]                                            # the newest word's question
            k = mx.repeat(keys[0], q.shape[0] // keys.shape[1], axis=0)
            w = mx.softmax((k @ q[:, :, None])[:, :, 0].astype(mx.float32) * scale, axis=-1).mean(axis=0)
            self.calls[keys.shape[2]][layer] = w[self.lo:self.hi] @ self.a       # one number per node
        return out

    def __enter__(self):
        self._orig = self._module.scaled_dot_product_attention
        self._module.scaled_dot_product_attention = self._spy
        return self

    def __exit__(self, *exc):
        self._module.scaled_dot_product_attention = self._orig

    def per_word(self, words: int) -> np.ndarray:
        """(words, nodes): how hard each written word looked at each node, averaged over the watched layers."""
        import mlx.core as mx

        rows = []
        for i in range(words):
            layers = self.calls.get(self.prompt_len + i)
            rows.append(mx.stack(list(layers.values())).mean(axis=0) if layers else mx.zeros(len(self.nodes)))
        return np.array(mx.stack(rows)) if rows else np.zeros((0, len(self.nodes)), dtype=np.float32)


def used(looks: np.ndarray, nodes: list[int]) -> tuple[list[float], list[int]]:
    """Each node's share of the desk's attention over the whole answer, and the nodes that drew at least USED."""
    total = looks.sum(axis=0)
    share = (total / total.sum()) if total.sum() > 0 else total
    return [round(float(x), 4) for x in share], [n for n, x in zip(nodes, share) if x >= USED]


class EventLog:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

    def write(self, kind: str, **event) -> None:
        event = {"type": kind, "at": dt.datetime.now().isoformat(timespec="milliseconds"), **event}
        with self.path.open("a") as f:
            f.write(json.dumps(event, separators=(",", ":")) + "\n")

    def read(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text().splitlines() if line]

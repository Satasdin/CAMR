"""What a person can watch while CAMR works: the model's weights arriving layer by layer, the room an answer reads,
its words as they come, and how strongly each of the model's layers fires for each word.

A ``Live`` is the list of events of one job (a model loading, one answer, one remembered moment). Code that does the
work reports to the Live of its thread (``reporting``), so nothing changes for code that runs without one: the
benchmarks never have one, and pay nothing for it.

Each layer's activity is measured, not drawn: ``probe`` wraps the model's transformer layers so that, while a Live
listens, each layer's output for the newest token is kept as ``BINS`` numbers (the mean size of each slice of its
hidden state). ``Reader.generate`` sends them with every word (``token`` events), and ``Reader.new_cache`` with every
step of reading (``read`` events).
"""

from __future__ import annotations

import json
import sys
import threading
import time
from contextlib import contextmanager
from typing import Any, Callable

BINS = 32  # numbers per layer per token: slices of the hidden state
KEEP = 4000  # events kept per job; a longer job keeps its last ones

_here = threading.local()


class Live:
    """One job's events, in order, each stamped with seconds since the job began. Safe across threads."""

    def __init__(self, kind: str = "job", echo: Callable[[dict], None] | None = None):
        self.kind, self.echo = kind, echo
        self.events: list[dict] = []
        self.first = 0  # the index of events[0], once early ones are dropped
        self.done = False
        self.stopped = False  # asked to stop: a model writing for this job ends at its next word
        self.layers = True  # measure each layer for each word (only a view on screen needs it; it costs time)
        self.t0 = time.perf_counter()
        self.lock = threading.Lock()

    def add(self, kind: str, **data: Any) -> dict:
        with self.lock:
            e = {"i": self.first + len(self.events), "t": round(time.perf_counter() - self.t0, 4), "kind": kind,
                 **data}
            self.events.append(e)
            if len(self.events) > KEEP:
                drop = len(self.events) - KEEP
                del self.events[:drop]
                self.first += drop
        if self.echo is not None:
            self.echo(e)
        return e

    def finish(self, **data: Any) -> None:
        self.add("done", **data)
        self.done = True

    def since(self, i: int = 0) -> dict:
        """The events from index ``i`` on (any dropped ones are skipped), and whether the job is over."""
        with self.lock:
            out = [e for e in self.events if e["i"] >= i]
        return {"events": out, "done": self.done, "next": out[-1]["i"] + 1 if out else i}


def stdout_line(e: dict) -> None:
    """An event as one line on stdout, for an app that started the engine and reads its output."""
    sys.stdout.write("CAMR-LIVE " + json.dumps(e, separators=(",", ":")) + "\n")
    sys.stdout.flush()


@contextmanager
def reporting(live: Live | None):
    """Work done inside reports to ``live``."""
    before = getattr(_here, "live", None)
    _here.live = live
    try:
        yield live
    finally:
        _here.live = before


def current() -> Live | None:
    return getattr(_here, "live", None)


# --- the layers -------------------------------------------------------------------------------------------------


def layers_of(model) -> list:
    """The transformer layers of an mlx_lm model."""
    for path in (("layers",), ("model", "layers"), ("language_model", "model", "layers")):
        obj = model
        try:
            for name in path:
                obj = getattr(obj, name)
            if isinstance(obj, list) and obj:
                return obj
        except AttributeError:
            continue
    raise ValueError("no transformer layers found in this model")


def probe(model) -> int:
    """Wrap the model's layer class once so each layer's output can be measured while a Live listens. Returns how
    many layers there are."""
    layers = layers_of(model)
    for i, layer in enumerate(layers):
        object.__setattr__(layer, "_camr_layer", i)
    cls = type(layers[0])
    if not getattr(cls, "_camr_probed", False):
        call = cls.__call__

        def measured(self, x, *a, **kw):
            out = call(self, x, *a, **kw)
            kept = getattr(_here, "layers", None)
            if kept is not None and getattr(_here, "live", None) is not None:
                h = out[0] if isinstance(out, tuple) else out
                kept[self._camr_layer] = _bins(h)
            return out

        cls.__call__ = measured
        cls._camr_probed = True
    return len(layers)


def _bins(h):
    import mlx.core as mx

    last = h[0, -1] if h.ndim == 3 else h[-1]
    last = mx.abs(last.astype(mx.float32))
    n = last.shape[-1] - last.shape[-1] % BINS
    return last[:n].reshape(BINS, -1).mean(axis=1)


@contextmanager
def measuring_layers(on: bool = True):
    """Inside, the probed layers keep their newest output; ``taken()`` hands them over. With ``on`` false, nothing
    is measured and ``taken()`` gives None."""
    before = getattr(_here, "layers", None)
    _here.layers = {} if on else None
    try:
        yield
    finally:
        _here.layers = before


def taken() -> list[list[float]] | None:
    """The layers measured since the last call, as one row of BINS numbers per layer (None when nothing was)."""
    kept = getattr(_here, "layers", None)
    if not kept:
        return None
    import mlx.core as mx

    order = sorted(kept)
    rows = mx.stack([kept[i] for i in order])
    _here.layers = {}
    return [[round(float(v), 4) for v in row] for row in rows.tolist()]


# --- the weights arriving ---------------------------------------------------------------------------------------


def load_layers(model, live: Live, repo: str) -> None:
    """Read a lazily loaded model's weights in, one layer at a time, reporting each (``load`` events), then the rest
    (embeddings, the last norm and the head)."""
    import mlx.core as mx
    from mlx.utils import tree_flatten

    layers = layers_of(model)
    t = time.perf_counter()
    total = 0
    for i, layer in enumerate(layers):
        params = [v for _, v in tree_flatten(layer.parameters())]
        mx.eval(params)
        size = sum(p.nbytes for p in params)
        total += size
        live.add("load", repo=repo, layer=i, layers=len(layers), bytes=size, s=round(time.perf_counter() - t, 3))
    rest = [v for _, v in tree_flatten(model.parameters())]
    mx.eval(rest)
    whole = sum(p.nbytes for p in rest)
    hidden = None
    try:
        hidden = int(layers[0].mlp.down_proj.weight.shape[0])
    except AttributeError:
        pass
    live.add("loaded", repo=repo, layers=len(layers), bytes=whole, layer_bytes=total, hidden=hidden, bins=BINS,
             s=round(time.perf_counter() - t, 3))

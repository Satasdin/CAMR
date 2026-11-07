"""A trained add-on for the reader (a LoRA adapter, made on this Mac with MLX) that is switched on only for the
question and the answer, never while memory is read.

Why only there: a room's notes on the SSD are the plain model's own reading of its moments. An adapter that also
changed how memory is read would make every saved note out of date, so the memory would have to be told again. Here
the header, the room and the moments re-read as words are read by the plain model (adapter off), and the adapter
works from the first token after the notes ("End of notes. Today is ...", the question) to the last written word.
Training does exactly the same: the context is read with the adapter off and only the question and answer carry its
gradient (scripts/train_adapter.py).

An adapter is a folder: ``adapters.safetensors`` (only the small LoRA matrices) and ``adapter.json`` (how it was
made: layers, rank, scale, the data it saw). Adapters live under ~/.camr/adapters, never in the repository.
Switched off, a LoRA layer adds exactly zero, so the model answers as the plain model does, bit for bit.
"""

from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path

ADAPTERS = Path.home() / ".camr" / "adapters"
LAYERS = 16  # the last 16 of the 4B's 36 blocks carry the adapter
CONFIG = {"rank": 8, "scale": 20.0, "dropout": 0.0}
_SCALE = "_camr_scale"  # each LoRA layer's own scale, kept while it is switched off


def lora_layers(model) -> list:
    from mlx_lm.tuner.lora import LoRALinear

    return [m for _, m in model.named_modules() if isinstance(m, LoRALinear)]


def attach(model, layers: int = LAYERS, config: dict | None = None) -> list:
    """Wrap the last ``layers`` blocks' linear layers in LoRA layers (once), freeze everything else, and return the
    LoRA layers. A fresh adapter starts as a no-op: its second matrix is zeros."""
    from mlx_lm.tuner.utils import linear_to_lora_layers

    have = lora_layers(model)
    if have:
        return have
    model.freeze()
    linear_to_lora_layers(model, layers, dict(CONFIG, **(config or {})))
    got = lora_layers(model)
    for m in got:
        setattr(m, _SCALE, float(m.scale))
    return got


def switch(model, on: bool) -> None:
    """The adapter on (each layer at its own scale) or off (adds nothing)."""
    for m in lora_layers(model):
        m.scale = getattr(m, _SCALE, m.scale) if on else 0.0


def is_on(model) -> bool:
    return any(float(m.scale) != 0.0 for m in lora_layers(model))


@contextmanager
def off(model):
    """The plain model for the length of the block; the adapter's state is put back afterwards."""
    was = is_on(model)
    switch(model, False)
    try:
        yield
    finally:
        switch(model, was)


@contextmanager
def on(model):
    """The adapter for the length of the block (the question and the answer); off again afterwards."""
    switch(model, True)
    try:
        yield
    finally:
        switch(model, False)


def prefill(model, ids: list[int], cache, step: int = 2048) -> None:
    """Read ``ids`` into ``cache`` with the adapter off: memory as the plain model reads it."""
    import mlx.core as mx

    with off(model):
        for i in range(0, len(ids), step):
            model(mx.array(ids[i:i + step])[None], cache=cache)
            mx.eval([c.state for c in cache])


def save(model, folder: Path, meta: dict) -> Path:
    import mlx.core as mx
    from mlx.utils import tree_flatten

    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    weights = dict(tree_flatten(model.trainable_parameters()))
    mx.save_safetensors(str(folder / "adapters.safetensors"), weights)
    (folder / "adapter.json").write_text(json.dumps(meta, indent=1))
    return folder


def resolve(name: str | Path) -> Path:
    p = Path(name).expanduser()
    return p if p.is_absolute() or p.exists() else ADAPTERS / str(name)


def load(model, name: str | Path) -> dict:
    """Attach the adapter in ``name`` (a folder, or a name under ~/.camr/adapters) and leave it OFF: whoever reads
    with it switches it on for the question (camr_engine.memory.Memory.answer). Returns its adapter.json."""
    folder = resolve(name)
    meta = json.loads((folder / "adapter.json").read_text())
    attach(model, int(meta.get("layers", LAYERS)), meta.get("config"))
    model.load_weights(str(folder / "adapters.safetensors"), strict=False)
    switch(model, False)
    meta["path"] = str(folder)
    return meta

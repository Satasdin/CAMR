"""Shrink a reach's rooms on the SSD in place: every awake 16-bit room's notes are packed again at 8 (or 4) bits.

    python -m camr_engine.shrink ~/.camr/app/Qwen3-8B-4bit/global            # a dry run: what it would do
    python -m camr_engine.shrink ~/.camr/app/Qwen3-8B-4bit/global --apply    # do it

No model is loaded: the notes' shape and number type come from the model's config (``--model``, or the app folder
the reach is in: ``~/.camr/app/<model>/...`` is ``mlx-community/<model>``), and must match the index's token size.

Nothing is lost that is not checked first. For each room the tool writes the packed copy beside the old file
(``room-000001.q8.notes`` beside ``room-000001.notes``), reads it back and checks it: its size, its bytes equal to
packing the old notes again, and every number within one and a half quantization steps of the old one
(half a step, and the scale and offset kept at 16 bits). Only after a batch of
rooms is checked does the index say those rooms are 8-bit (written to a new file, then moved over the old index in
one step), and only then are their old files deleted. A stop at any point leaves a memory that reads: before the
index moves, it still names the old files (the new copies are written again next time); after, it names the checked
copies (the old files left over are deleted next time, once their copy is checked again). Asleep rooms have no file:
they are only marked to wake at the new bits. The reach is locked as an open session locks it, so the tool refuses
to run while the app has the reach open.
"""

from __future__ import annotations

import argparse
import fcntl
import json
import os
import time
from pathlib import Path

import numpy as np

from camr_engine.notes import Shape, pack, stored_bytes, unpack
from camr_engine.rooms import room_file

BATCH = 32  # rooms checked before the index is moved and their old files deleted


def model_of(folder: Path) -> str | None:
    """The Mac app's model for a reach folder under ``~/.camr/app/<model>/``, as an mlx-community repo."""
    parts = Path(folder).expanduser().resolve().parts
    for i in range(len(parts) - 2):
        if parts[i] == ".camr" and parts[i + 1] == "app":
            return f"mlx-community/{parts[i + 2]}"
    return None


def shape_of(model: str) -> tuple[Shape, str]:
    """The model's notes shape and number type, from its config in the local Hugging Face cache or its folder."""
    from camr_engine.bench.local import config_of, kv_shape

    local = Path(model).expanduser() / "config.json"
    config = json.loads(local.read_text()) if local.exists() else config_of(model)
    if config is None:
        raise ValueError(f"no config for {model}: pass --model with a downloaded model")
    c = config if "num_hidden_layers" in config else config.get("text_config", config)
    return kv_shape(config), str(c.get("torch_dtype") or config.get("torch_dtype") or "bfloat16")


def plan(folder: Path, bits: int) -> dict:
    """What shrinking would do: the rooms to pack, their bytes now and after, and leftovers from a stopped run."""
    folder = Path(folder).expanduser()
    index = json.loads((folder / "index.json").read_text())
    tb = int(index["token_bytes"])
    rooms = index["rooms"]
    todo, asleep, done, leftover, now, after = [], [], [], [], 0, 0
    for r in rooms:
        rb = int(r.get("bits", 16))
        if not r["tokens"]:
            continue
        if rb != 16:
            done.append(r["rid"])
            if room_file(folder, r["rid"]).exists():
                leftover.append(r["rid"])
            continue
        if not room_file(folder, r["rid"]).exists():
            asleep.append(r["rid"])
            continue
        todo.append(r["rid"])
        now += r["tokens"] * tb
        after += r["tokens"] * stored_bytes(tb, bits)
    return {"folder": str(folder), "bits": bits, "token_bytes": tb, "rooms": len(rooms), "to_pack": todo,
            "asleep": asleep, "packed_already": done, "leftover_16bit": leftover, "bytes_now": now,
            "bytes_after": after, "saved_bytes": now - after}


def _lock(folder: Path) -> int:
    fd = os.open(folder / ".lock", os.O_RDWR | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        os.close(fd)
        raise RuntimeError(f"{folder} is open in another process (the app?): close it first") from None
    return fd


def _read(path: Path, size: int) -> bytes:
    with open(path, "rb") as f:
        buf = f.read(size)
    if len(buf) != size:
        raise ValueError(f"{path.name} is {len(buf)} bytes, the index says {size}")
    return buf


def check(old: bytes, new_path: Path, shape: Shape, dtype, bits: int) -> float:
    """Check a packed copy against the 16-bit notes it came from. Returns the largest error, as a share of the largest
    number; raises when the copy is not right."""
    import mlx.core as mx

    tokens = len(old) // shape.token_bytes
    new = _read(new_path, tokens * shape.stored_bytes(bits))
    x = unpack(old, shape, dtype, 16)
    if pack(x, bits) != new:
        raise ValueError(f"{new_path.name} is not the old notes packed again")
    back = unpack(new, shape, dtype, bits).astype(mx.float32)
    x = x.astype(mx.float32)
    rows = x.reshape(-1, 64)
    step = (rows.max(axis=1) - rows.min(axis=1)) / (2**bits - 1)  # one quantization step, per group of 64
    err = mx.abs(back.reshape(-1, 64) - rows)
    # half a step, plus what keeping each group's scale and offset at 16 bits costs (at most about one more step)
    worst = (err - (1.5 * step[:, None] + 1e-2 * mx.abs(rows) + 1e-6)).max().item()
    if not np.isfinite(worst) or worst > 0:
        raise ValueError(f"{new_path.name} is further from the old notes than a quantization step allows")
    return float(err.max().item() / max(mx.abs(x).max().item(), 1e-9))


def _save_index(folder: Path, index: dict) -> None:
    tmp = folder / "index.json.tmp"
    tmp.write_text(json.dumps(index))
    os.replace(tmp, folder / "index.json")


def shrink(folder: Path, bits: int = 8, *, model: str | None = None, dtype: str | None = None,
           apply: bool = False, progress=print) -> dict:
    """Pack every awake 16-bit room of the reach at ``folder`` at ``bits`` (only a plan unless ``apply``)."""
    folder = Path(folder).expanduser()
    out = plan(folder, bits)
    if not apply:
        return out
    import mlx.core as mx

    model = model or model_of(folder)
    if model is None:
        raise ValueError("which model wrote these notes? pass --model")
    shape, kind = shape_of(model)
    dt = getattr(mx, dtype or kind)
    fd = _lock(folder)
    t = time.perf_counter()
    try:
        index = json.loads((folder / "index.json").read_text())
        if int(index["token_bytes"]) != shape.token_bytes:
            raise ValueError(f"these notes are {index['token_bytes']} bytes a token; {model}'s are {shape.token_bytes}")
        rooms = {r["rid"]: r for r in index["rooms"]}
        # leftovers from a stopped run: a 16-bit file whose room the index already names packed
        for rid in out["leftover_16bit"]:
            r = rooms[rid]
            old = room_file(folder, rid)
            check(_read(old, r["tokens"] * shape.token_bytes), room_file(folder, rid, r["bits"]), shape, dt, r["bits"])
            old.unlink()
        for r in index["rooms"]:  # asleep rooms wake at the new bits
            if r["rid"] in out["asleep"]:
                r["bits"] = bits
        worst, packed = 0.0, 0
        todo = out["to_pack"]
        for at in range(0, len(todo), BATCH):
            batch = todo[at:at + BATCH]
            for rid in batch:
                r = rooms[rid]
                old = _read(room_file(folder, rid), r["tokens"] * shape.token_bytes)
                new = room_file(folder, rid, bits)
                tmp = new.with_suffix(".tmp")
                tmp.write_bytes(pack(unpack(old, shape, dt, 16), bits))
                os.replace(tmp, new)
                worst = max(worst, check(old, new, shape, dt, bits))
            for rid in batch:
                rooms[rid]["bits"] = bits
            index["bits"] = bits
            _save_index(folder, index)  # from here the index names the checked copies
            for rid in batch:
                room_file(folder, rid).unlink()
            packed += len(batch)
            progress(f"{packed}/{len(todo)} rooms packed at {bits} bits")
        if not todo and out["asleep"]:
            _save_index(folder, index)
    finally:
        os.close(fd)
    out.update(packed=packed, worst_error=worst, seconds=round(time.perf_counter() - t, 1),
               bytes_on_disk=sum(p.stat().st_size for p in folder.glob("room-*.notes")))
    return out


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.shrink", description=__doc__.split("\n")[0])
    ap.add_argument("folder", type=Path, help="a reach folder (the one holding index.json and room-*.notes)")
    ap.add_argument("--bits", type=int, choices=(8, 4), default=8)
    ap.add_argument("--apply", action="store_true", help="do it (without: a dry run that only says what it would do)")
    ap.add_argument("--model", help="the model that wrote the notes (default: from ~/.camr/app/<model>/)")
    ap.add_argument("--dtype", help="the notes' number type (default: the model config's, bfloat16)")
    a = ap.parse_args(argv)
    got = shrink(a.folder, a.bits, model=a.model, dtype=a.dtype, apply=a.apply)
    gb = lambda n: f"{n / 1e9:.1f} GB"  # noqa: E731
    print(f"{got['folder']}: {len(got['to_pack'])} rooms to pack at {a.bits} bits, {gb(got['bytes_now'])} -> "
          f"{gb(got['bytes_after'])} (saves {gb(got['saved_bytes'])}); {len(got['asleep'])} asleep, "
          f"{len(got['packed_already'])} packed already")
    if a.apply:
        print(f"packed {got['packed']} rooms in {got['seconds']} s; room files now {gb(got['bytes_on_disk'])}; "
              f"largest error {got['worst_error']:.4f} of the largest number")
    else:
        print("dry run: nothing changed (add --apply)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

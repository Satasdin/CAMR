"""Metrics: one record per answer, so every run shows what the memory cost as well as what it knew.

A record holds:
- the time to the first word (what a person waits) and the total time to the last word;
- prefill speed (the new tokens the model read, per second) and decode speed (tokens written per second);
- retrieval time, broken into choosing the room, building the core, reading the SSD and laying the desk;
- the tier the room came from, the bytes read from the SSD, the bandwidth, and the share of the wait spent reading;
- the context tokens the model saw, against the whole history's tokens;
- the process's peak RAM (and MLX's own peak) and the memory folder's size on disk.

Records go to ``metrics.jsonl`` beside the rooms, one JSON line each, and ``summary`` gives medians and 90th
percentiles over them.
"""

from __future__ import annotations

import datetime as dt
import json
import os
import resource
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path

import numpy as np

STEPS = ("choose", "core", "fetch", "wake", "desk")  # retrieval, in the order it happens


@dataclass
class Record:
    question: str
    first_word_s: float  # question asked -> first word
    total_s: float  # question asked -> last word
    prefill_tps: float | None  # new tokens read per second, before the first word
    decode_tps: float
    retrieval_ms: dict[str, float]  # per step of STEPS that ran, and "total"
    tier: str | None  # where the room's notes came from: ram, ssd or vault
    read_bytes: int  # from the SSD
    gbps: float | None  # SSD bandwidth for this read
    read_share: float  # share of the wait spent reading the SSD
    context_tokens: int  # every token the model saw: header, core, room, words and question
    history_tokens: int  # every token the memory holds
    new_tokens: int  # tokens read as words this answer (the rest were already notes)
    answer_tokens: int
    peak_ram_bytes: int  # the process's peak resident memory
    peak_mlx_bytes: int | None  # MLX's peak, when MLX is loaded
    disk_bytes: int  # the memory folder
    room: int | None = None
    reach: str | None = None
    at: str = field(default_factory=lambda: dt.datetime.now().isoformat(timespec="milliseconds"))

    def to_dict(self) -> dict:
        return asdict(self)


def peak_ram_bytes() -> int:
    """The process's peak resident memory so far (macOS reports bytes, Linux kilobytes)."""
    peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return int(peak if sys.platform == "darwin" else peak * 1024)


def peak_mlx_bytes() -> int | None:
    mx = sys.modules.get("mlx.core")  # only when MLX is already in use: never load it just to ask
    try:
        return int(mx.get_peak_memory()) if mx is not None else None
    except AttributeError:
        return None


def folder_bytes(path: Path) -> int:
    """Every file under ``path``, as it sits on disk."""
    total = 0
    for root, _, files in os.walk(path):
        for f in files:
            try:
                total += os.lstat(os.path.join(root, f)).st_size
            except OSError:
                pass
    return total


def measure(question: str, reply, rec, *, total_s: float, first_s: float, new_tokens: int, history_tokens: int,
            disk_bytes: int, reach: str | None = None) -> Record:
    """The record of one answer: ``reply`` from the reader (its wait already including retrieval), ``rec`` the
    recall it answered from, ``first_s`` the reader's own time to the first word (prefill), ``total_s`` the whole
    answer."""
    seconds = dict(getattr(rec, "seconds", {}) or {})
    ms = {k: round(seconds[k] * 1000, 3) for k in STEPS if k in seconds}
    ms["total"] = round(sum(seconds.get(k, 0.0) for k in STEPS) * 1000, 3)
    read_s = seconds.get("fetch", 0.0)
    read_bytes = int(getattr(rec, "read_bytes", 0) or 0)
    wait = float(reply.ttft_s)
    return Record(question=question, first_word_s=round(wait, 4), total_s=round(total_s, 4),
                  prefill_tps=round(new_tokens / first_s, 1) if first_s > 0 and new_tokens else None,
                  decode_tps=round(float(reply.gen_tps), 1), retrieval_ms=ms, tier=getattr(rec, "tier", None),
                  read_bytes=read_bytes,
                  gbps=round(read_bytes / read_s / 1e9, 2) if read_bytes and read_s > 0 else None,
                  read_share=round(read_s / wait, 4) if wait > 0 else 0.0, context_tokens=int(reply.prompt_tokens),
                  history_tokens=history_tokens, new_tokens=new_tokens, answer_tokens=int(reply.gen_tokens),
                  peak_ram_bytes=peak_ram_bytes(), peak_mlx_bytes=peak_mlx_bytes(), disk_bytes=disk_bytes,
                  room=getattr(rec, "room", None), reach=reach)


def spread(xs) -> dict:
    """Median and 90th percentile, or None when there is nothing to measure."""
    xs = [float(x) for x in xs if x is not None]
    if not xs:
        return {"p50": None, "p90": None}
    return {"p50": round(float(np.percentile(xs, 50)), 4), "p90": round(float(np.percentile(xs, 90)), 4)}


def summary(records: list) -> dict:
    """Medians and 90th percentiles over records (Record objects or their dicts)."""
    rows = [r.to_dict() if isinstance(r, Record) else r for r in records]
    if not rows:
        return {"answers": 0}
    steps = sorted({k for r in rows for k in r["retrieval_ms"]}, key=lambda k: (STEPS + ("total",)).index(k)
                   if k in STEPS + ("total",) else 99)
    tiers: dict[str, int] = {}
    for r in rows:
        tiers[str(r["tier"])] = tiers.get(str(r["tier"]), 0) + 1
    return {"answers": len(rows),
            "first_word_s": spread(r["first_word_s"] for r in rows),
            "total_s": spread(r["total_s"] for r in rows),
            "prefill_tps": spread(r["prefill_tps"] for r in rows),
            "decode_tps": spread(r["decode_tps"] for r in rows),
            "retrieval_ms": {k: spread(r["retrieval_ms"].get(k) for r in rows) for k in steps},
            "read_bytes": spread(r["read_bytes"] for r in rows),
            "gbps": spread(r["gbps"] for r in rows),
            "read_share": spread(r["read_share"] for r in rows),
            "context_tokens": spread(r["context_tokens"] for r in rows),
            "history_tokens": max(r["history_tokens"] for r in rows),
            "peak_ram_bytes": max(r["peak_ram_bytes"] for r in rows),
            "peak_mlx_bytes": max((r["peak_mlx_bytes"] for r in rows if r["peak_mlx_bytes"] is not None),
                                  default=None),
            "disk_bytes": rows[-1]["disk_bytes"],
            "tiers": tiers}


class Meter:
    """Keeps every answer's record and, given a path, appends each one to it as a JSON line."""

    def __init__(self, path: Path | None = None):
        self.path = Path(path) if path is not None else None
        self.records: list[Record] = []
        if self.path is not None:
            self.path.parent.mkdir(parents=True, exist_ok=True)

    @property
    def last(self) -> Record | None:
        return self.records[-1] if self.records else None

    def add(self, record: Record) -> Record:
        self.records.append(record)
        if self.path is not None:
            with self.path.open("a") as f:
                f.write(json.dumps(record.to_dict(), separators=(",", ":")) + "\n")
        return record

    def summary(self) -> dict:
        return summary(self.records)

    @staticmethod
    def read(path: Path) -> list[dict]:
        path = Path(path)
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text().splitlines() if line]

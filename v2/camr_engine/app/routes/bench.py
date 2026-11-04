"""The Bench screen's routes: the evidence, read from the dated records (design/DIRECTION.md, "6. Bench").

- ``GET /api/bench``: everything the screen draws, from ``records/bench/`` and the older ruler records (lives,
  errands, the speed test):
  - the headline (Qwen 27B with memory against without, from the ruler's lives);
  - the Long Haul probe matrix per contender and cut;
  - the curves: score, first word and peak RAM against history length; retrieval ms and GB/s against the memory's
    size on the SSD; decode tok/s against desk tokens; the ruler's lives week by week; rooms awake and asleep;
  - the run table, the Claude ledger against its cap, and the page answers that can be shown as screenshots;
- ``GET /api/bench/record?path=``: one record, trimmed for the record sheet;
- ``GET /api/bench/webdev``: LMArena's WebDev history: the best Claude, the best open-weights model and the models
  this Mac runs, at every publication;
- ``GET /api/bench/shot?key=``: a page answer's headless-browser screenshot, as a data URL;
- ``POST /api/bench/shot`` with ``{path, cut, qid, asked}``: render that answer's page headless with the network off
  and keep the PNG (in ``~/.camr/shots``, or ``CAMR_SHOTS``). Refused while a benchmark measures. Without
  ``asked`` (the screen shooting on its own) it is also refused while a benchmark process runs or a record changed in
  the last 15 minutes, so a run's timings never share the CPU with a browser nobody asked for.

Records keep arriving while benchmarks run. A file is read again only when it changes, a file that fails to read is
listed in ``errors``, and anything not measured is null, which the screen prints as —.
"""

from __future__ import annotations

import base64
import csv
import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Callable

from camr_engine.app.web import Refused, Request, Routes, part

ROOT = Path(__file__).resolve().parents[3] / "records"
CUTS = {"64K": 64_000, "256K": 256_000, "1M": 1_000_000, "2M": 2_000_000}  # the Long Haul's cuts, as told
FAMILIES = [("fact", "Facts across the gap"), ("changed", "Changed facts"), ("two_hop", "Two-hop links"),
            ("maths", "Corrected maths"), ("page", "The page that grows"), ("code", "Code that must fit"),
            ("lookalike", "Look-alikes"), ("never", "Never said")]
PREFIX = {"hop": "two_hop"}  # probe ids start with their family, except two-hop links
RIGHT = {"right", "right_abstain"}
WRONG = {"wrong", "stale", "false_memory"}
CAP_USD, HEADROOM_USD = 60.0, 2.0  # camr_engine.bench.claude's budget for the night; a test keeps them in step
SKIP = {"superseded", "calibration", "health", "charts", "shots"}
DATED = re.compile(r"\d{4}-\d{2}-\d{2}$")
MAX_FILE = 64 * 10**6
SHOT_SIZE = (1280, 1200)  # px: the browser window a page is shot in
MAX_PAGE = 256 * 1024  # bytes: a page rides to the browser on its command line, which macOS caps near 1 MB
QUIET_S = 15 * 60  # s: records unchanged this long, and no benchmark running, before pages are shot unasked
RUNNERS = re.compile(r"-m\s+(camr_engine\.(?:bench|ruler)[\w.]*)|(camr_engine/(?:bench|ruler)/[\w/]*\.py)|\b(mlx_lm[\w.]*)"
                     r"|(ollama runner)")  # command lines of processes that measure, or hold a model on the GPU
PNG = b"\x89PNG\r\n\x1a\n"
KEY = re.compile(r"[0-9a-f]{16}$")
CLAUDE = re.compile(r"claude-(haiku|sonnet|opus)-(\d+)-(\d+)")
ORDER = {"tensors": 0, "words": 1, "none": 2, "claude": 3}
CLAUDE_ORDER = {"haiku": 0, "sonnet": 1, "opus": 2}
TRIM = {"answer": 1500, "question": 400, "expected": 300, "reason": 400, "said": 400}


# -- where things are -------------------------------------------------------------------------------------------


def records_root(app) -> Path:
    """The records folder: ``app.bench_root`` when a test or fixture sets one, else ``v2/records``."""
    return Path(getattr(app, "bench_root", None) or ROOT)


def shots_dir(app) -> Path:
    got = getattr(app, "bench_shots", None) or os.environ.get("CAMR_SHOTS")
    return Path(got) if got else Path.home() / ".camr" / "shots"


def _files(root: Path) -> list[Path]:
    """Every record the screen reads: the ruler's dated folders and speed tests, and records/bench (its dated
    folders and the files at its top)."""
    out: list[Path] = []

    def jsons(d: Path) -> None:
        try:
            out.extend(sorted(p for p in d.iterdir() if p.suffix == ".json" and p.is_file()))
        except OSError:
            pass

    for base in (root, root / "bench"):
        try:
            subs = sorted(p for p in base.iterdir() if p.is_dir() and p.name not in SKIP)
        except OSError:
            continue
        for d in subs:
            if DATED.match(d.name) or (base == root and d.name == "speed"):
                jsons(d)
    jsons(root / "bench")
    return out


def safe_path(root: Path, rel: str, suffix: str = ".json") -> Path:
    """``rel`` inside ``root``, or a 400. No absolute paths, no ``..``, no links out, only ``suffix`` files."""
    if not rel or rel.startswith(("/", "~")) or "\\" in rel or "\x00" in rel:
        raise Refused(400, "path is relative to the records folder")
    parts = Path(rel).parts
    if any(p in ("..", ".") or p.startswith(".") for p in parts):
        raise Refused(400, "path is relative to the records folder")
    p = (root / rel).resolve()
    try:
        p.relative_to(root.resolve())
    except ValueError:
        raise Refused(400, "path is outside the records folder") from None
    if p.suffix != suffix or not p.is_file():
        raise Refused(404, f"no record {rel}")
    if p.stat().st_size > MAX_FILE:
        raise Refused(413, "record too large to show")
    return p


# -- small helpers ----------------------------------------------------------------------------------------------


def _num(x: Any) -> float | None:
    return float(x) if isinstance(x, (int, float)) and not isinstance(x, bool) else None


def _p(d: Any, key: str = "p50") -> float | None:
    """A p50 or p90 from a spread, or the number itself."""
    if isinstance(d, dict):
        return _num(d.get(key))
    return _num(d) if key == "p50" else None


def spread(xs) -> dict:
    from camr_engine.metrics import spread as s

    return s(xs)


def family_of(a: dict) -> str:
    fam = a.get("family")
    if fam:
        return str(fam)
    qid = str(a.get("qid") or a.get("id") or "")
    head = qid.split("-", 1)[0]
    return PREFIX.get(head, head)


def memory_of(kind: str | None, name: str) -> str:
    """How a contender holds its memory: tensors (the engine's saved keys and values), words (memory pasted in as
    text), none, or claude (the yardstick, alone)."""
    k, n = (kind or "").lower(), (name or "").lower()
    if k in ("claude", "claude-yardstick") or n.startswith("claude"):
        return "claude"
    if k in ("bare", "ollama-bare") or "bare" in n.split(":")[0]:
        return "none"
    if k == "engine":
        return "tensors"
    if k in ("words", "ollama"):
        return "words"
    if n.startswith("camr") and "words" not in n:  # the ruler's own contenders, by name
        return "tensors"
    return "words"


def label_of(name: str) -> str:
    m = CLAUDE.fullmatch(name or "")
    if m:
        return f"claude {m.group(1)} {m.group(2)}.{m.group(3)}"
    return (name or "—").replace(":", " · ", 1)


def model_of(name: str) -> str:
    """The model a contender runs: what follows its kind (``engine:qwen3-1.7b`` -> ``qwen3-1.7b``)."""
    if CLAUDE.fullmatch(name or ""):
        return name
    return name.split(":", 1)[1] if ":" in (name or "") else (name or "")


def tally(answers: list[dict]) -> dict:
    """Right, wrong, stale, false memories, declines and how many were graded (an error is never graded)."""
    v = Counter(str(a.get("verdict")) for a in answers)
    graded = sum(1 for a in answers if a.get("right") is not None and a.get("verdict") != "error")
    right = sum(1 for a in answers if a.get("right") is True and a.get("verdict") != "error")
    return {"questions": len(answers), "graded": graded, "right": right, "wrong": v["wrong"], "stale": v["stale"],
            "false_memory": v["false_memory"], "declined": v["declined"],
            "score": round(right / graded, 4) if graded else None}


def _trim(s: Any, n: int) -> Any:
    if isinstance(s, str) and len(s) > n:
        return s[:n] + "…"
    return s


def _key(html: str) -> str:
    return hashlib.sha256(html.encode("utf-8")).hexdigest()[:16]


def _stamp(p: Path) -> str | None:
    """When a record began, from its name, for records that do not say, in ISO form so runs sort by it: its dated
    folder and time (``2026-11-03/210705-...``), a day and minute (``throughput-2026-11-04-0123``), or the day alone
    (the ruler's ``speed/2026-11-04-student``)."""
    m = re.match(r"(\d{6})-", p.name)
    if m and DATED.match(p.parent.name):
        t = m.group(1)
        return f"{p.parent.name}T{t[:2]}:{t[2:4]}:{t[4:]}"
    m = re.search(r"(\d{4}-\d{2}-\d{2})-(\d{2})(\d{2})$", p.stem)
    if m:
        return f"{m.group(1)}T{m.group(2)}:{m.group(3)}"
    m = re.match(r"(\d{4}-\d{2}-\d{2})(?:-|$)", p.stem)
    return m.group(1) if m else None


def _rel(root: Path, p: Path) -> str:
    return p.relative_to(root).as_posix()


def _env(e: Any) -> dict:
    e = e if isinstance(e, dict) else {}
    return {k: e.get(k) for k in ("machine", "chip", "memory_gb", "power", "load_1m", "camr_commit", "camr_dirty",
                                  "mlx", "mlx_lm", "anthropic", "ollama") if e.get(k) is not None}


# -- one record, digested once per change -----------------------------------------------------------------------


def _answer_metrics(answers: list[dict]) -> dict:
    """Medians over the answers' own metrics, for the run table."""
    def col(k: str) -> list:
        return [(a.get("metrics") or {}).get(k) for a in answers]

    peak = [x for x in col("peak_ram_gb") if _num(x) is not None]
    return {"ttft_s": spread(col("ttft_s"))["p50"], "decode_tps": spread(col("decode_tps"))["p50"],
            "prefill_tps": spread(col("prefill_tps"))["p50"], "retrieval_ms": spread(col("retrieval_ms"))["p50"],
            "gbps": spread(col("gbps"))["p50"], "peak_ram_gb": max(peak) if peak else None}


def _cut_local(cp: dict) -> dict:
    s = (cp.get("summary") or {}).get("all") or {}
    st = cp.get("status") or {}
    answers = cp.get("answers") or []
    return {"name": cp.get("name"), "tokens": cp.get("tokens"), "answers": answers,
            "ttft_s": _p(s.get("ttft_s")), "ttft_p90": _p(s.get("ttft_s"), "p90"),
            "decode_tps": _p(s.get("decode_tps")), "prefill_tps": _p(s.get("prefill_tps")),
            "retrieval_ms": _p(s.get("retrieval_ms")), "retrieval_p90": _p(s.get("retrieval_ms"), "p90"),
            "gbps": _p(s.get("gbps")), "gbps_p90": _p(s.get("gbps"), "p90"),
            "context_tokens": _p(s.get("context_tokens")), "peak_ram_gb": _num(s.get("peak_ram_gb")),
            "disk_gb": _num(s.get("disk_gb")) or _num(st.get("disk_gb")),
            "memory_bytes": _num(st.get("folder_bytes")) or (_num(st.get("disk_gb")) or 0) * 1e9 or None,
            "status": {k: st.get(k) for k in ("moments", "rooms", "awake_rooms", "asleep_rooms", "hot_rooms",
                                              "vault_notes", "core_tokens", "history_tokens", "disk_gb",
                                              "ram_used_bytes", "join_hits", "naps", "window") if k in st},
            "cost_usd": None}


def _cut_claude(cp: dict) -> dict:
    r = cp.get("request") or {}
    return {"name": cp.get("checkpoint") or cp.get("name"), "tokens": cp.get("history_tokens_told_est"),
            "answers": cp.get("answers") or [], "ttft_s": _num(r.get("ttft_s")), "ttft_p90": None,
            "decode_tps": _num(r.get("output_tps")), "prefill_tps": None, "retrieval_ms": None, "retrieval_p90": None,
            "gbps": None, "gbps_p90": None, "context_tokens": _num(cp.get("context_tokens")), "peak_ram_gb": None,
            "disk_gb": None, "memory_bytes": None, "status": {},
            "cost_usd": _num((cp.get("summary") or {}).get("cost_usd")) or _num(r.get("cost_usd")),
            "cut_from_front": cp.get("cut_from_front")}


def _pages(cuts: list[dict]) -> list[dict]:
    from camr_engine.bench.haul.page import extract_html

    out = []
    for c in cuts:
        for a in c["answers"]:
            if family_of(a) != "page":
                continue
            html = extract_html(a.get("answer") or "")
            out.append({"cut": c["name"], "qid": a.get("qid") or a.get("id"), "verdict": a.get("verdict"),
                        "reason": _trim(a.get("reason"), 400), "key": _key(html) if html else None})
    return out


def digest(root: Path, path: Path, data: Any) -> dict | None:
    """What the screen needs from one record, or None for a file it does not show."""
    rel = _rel(root, path)
    base = {"path": rel, "name": path.name, "started": None, "finished": None, "environment": {}}
    if path.name == "webdev-arena-summary.json" and isinstance(data, dict):
        return {**base, "kind": "webdev", "task": "webdev", "contender": "lmarena", "label": "LMArena WebDev",
                "memory": "none", "started": data.get("last_date"), "publications": data.get("publications"),
                "models": data.get("models"), "first_date": data.get("first_date"), "last_date": data.get("last_date")}
    if not isinstance(data, dict):
        return None
    kind = data.get("kind")
    base.update(started=data.get("started") or _stamp(path), finished=data.get("finished"),
                environment=_env(data.get("environment")))
    if kind in ("bench", "claude-yardstick"):
        claude = kind == "claude-yardstick"
        con = data.get("contender") or {}
        name = data.get("model") if claude else con.get("name", "?")
        ckind = "claude" if claude else con.get("kind")
        cuts = [(_cut_claude if claude else _cut_local)(cp) for cp in data.get("checkpoints") or []]
        cuts = [c for c in cuts if c["name"]]
        answers = [a for c in cuts for a in c["answers"]]
        t = tally(answers)
        m = _answer_metrics(answers) if not claude else {  # one request per cut: its first token and its speed
            "ttft_s": spread([c["ttft_s"] for c in cuts])["p50"],
            "decode_tps": spread([c["decode_tps"] for c in cuts])["p50"],
            "prefill_tps": None, "retrieval_ms": None, "gbps": None, "peak_ram_gb": None}
        window = data.get("window") if claude else con.get("window")
        out = {**base, "kind": kind, "task": data.get("task") or "longhaul", "contender": name, "label": label_of(name),
               "memory": memory_of(ckind, name), "model": model_of(name), "window": window, **t, **m,
               "cost_usd": _num(data.get("cost_usd")) if claude else None, "limit": data.get("limit"),
               "cuts": [{**{k: v for k, v in c.items() if k != "answers"}, "all": tally(c["answers"]),
                         "families": {f: tally([a for a in c["answers"] if family_of(a) == f]) for f, _ in FAMILIES
                                      if any(family_of(a) == f for a in c["answers"])}} for c in cuts]}
        if out["task"] == "longhaul":
            out["pages"] = _pages(cuts)
        return out
    if kind == "suite":
        con = data.get("contender") or {}
        name = con.get("name", "?")
        s = data.get("summary") or {}
        al = s.get("all") or {}
        answers = [a for g in data.get("groups") or [] for a in g.get("answers") or []]
        lengths = []
        for length, ls in (s.get("by_length") or {}).items():
            got = [a for a in answers if a.get("length") == length]
            lengths.append({"name": length, "history_tokens": _num(ls.get("history_tokens")), **tally(got),
                            "ttft_s": _p(ls.get("ttft_s"))})
        return {**base, "kind": kind, "task": data.get("task"), "contender": name, "label": label_of(name),
                "memory": memory_of(con.get("kind"), name), "model": model_of(name), "window": con.get("window"),
                **tally(answers), **_answer_metrics(answers),
                "cost_usd": _num(con.get("spent_usd")), "lengths": lengths}
    if kind == "speed" and "points" in data and "persona" in data:  # the ruler's speed test: notes against words
        pts = [{"tokens": _num(p.get("tokens")), "mb": _num(p.get("mb")), "fetch_s": _num(p.get("fetch_s")),
                "notes_s": _num(p.get("notes_first_word_s")), "words_s": _num(p.get("words_first_word_s"))}
               for p in data["points"]]
        return {**base, "kind": "ruler-speed", "task": "speed", "contender": f"ruler · {data.get('persona')}",
                "label": "notes against words", "persona": data.get("persona"), "memory": "tensors",
                "points": pts,
                "questions": data.get("tries"), "ttft_s": pts[0]["notes_s"] if pts else None}
    if kind == "speed":  # camr_engine.bench.local speed: retrieval as the memory grows
        con = data.get("contender") or {}
        name = con.get("name", "?")
        pts = []
        for p in data.get("points") or []:
            s, st = p.get("summary") or {}, p.get("status") or {}
            pts.append({"history_tokens": _num(p.get("history_tokens")), "moments": p.get("moments"),
                        "memory_bytes": _num(st.get("folder_bytes")) or (_num(p.get("disk_gb")) or 0) * 1e9 or None,
                        "disk_gb": _num(p.get("disk_gb")), "ttft_s": _p(s.get("ttft_s")),
                        "ttft_p90": _p(s.get("ttft_s"), "p90"), "retrieval_ms": _p(s.get("retrieval_ms")),
                        "retrieval_p90": _p(s.get("retrieval_ms"), "p90"), "gbps": _p(s.get("gbps")),
                        "gbps_p90": _p(s.get("gbps"), "p90"), "decode_tps": _p(s.get("decode_tps")),
                        "context_tokens": _p(s.get("context_tokens")), "peak_ram_gb": _num(s.get("peak_ram_gb")),
                        "status": {k: st.get(k) for k in ("moments", "rooms", "awake_rooms", "asleep_rooms",
                                                          "hot_rooms", "vault_notes", "naps") if k in st}})
        answers = [a for p in data.get("points") or [] for a in p.get("answers") or []]
        return {**base, "kind": kind, "task": "speed", "contender": name, "label": label_of(name),
                "memory": memory_of(con.get("kind"), name), "model": model_of(name), "points": pts,
                **tally(answers), **_answer_metrics(answers)}
    if kind == "throughput":
        models = []
        for runtime in ("mlx", "ollama"):
            for model, m in (data.get(runtime) or {}).items():
                models.append({"runtime": runtime, "model": model, "repo": m.get("repo") or m.get("name"),
                               "points": [{"tokens": _num(p.get("tokens")),
                                           "first_word_s": _num(p.get("first_word_s")),
                                           "read_tps": _num(p.get("read_tok_s")),
                                           "write_tps": _num(p.get("write_tok_s")),
                                           "peak_gb": _num(p.get("peak_gb")), "error": p.get("error")}
                                          for p in m.get("points") or []]})
        return {**base, "kind": kind, "task": "throughput", "contender": "local models", "label": "throughput",
                "memory": "none", "models": models, "write_tokens": data.get("write_tokens")}
    if kind in ("life", "errands"):
        con = data.get("contender")
        name = con.get("name") if isinstance(con, dict) else str(con or "?")
        weeks = []
        for w in data.get("weeks") or []:
            if not isinstance(w, dict):
                continue
            s = w.get("summary") or {}
            weeks.append({"week": w.get("week"), "notes": w.get("notes_so_far"), "told": s.get("told"),
                          "knows": s.get("knows"), "false_memory": s.get("false_memories"), "honest": s.get("honest"),
                          "untold": s.get("untold"), "wait_s": _num(s.get("wait_median_s")),
                          "peak_ram_gb": _num(w.get("peak_ram_gb")), "disk_mb": _num(w.get("disk_mb"))})
        s = weeks[-1] if weeks else {}
        if kind == "errands":
            es = data.get("summary") or {}
            s = {"told": es.get("told"), "knows": es.get("knows"), "false_memory": es.get("false_memories"),
                 "honest": es.get("honest"), "wait_s": _num(es.get("wait_median_s"))}
        told, knows = s.get("told"), s.get("knows")
        return {**base, "kind": kind, "task": kind, "contender": name, "label": name, "persona": data.get("persona"),
                "memory": memory_of(None, name), "model": "qwen-27b" if name.endswith("-27b") else None,
                "weeks": weeks, "questions": data.get("questions"), "graded": told, "right": knows,
                "false_memory": s.get("false_memory"), "declined": s.get("honest"),
                "score": round(knows / told, 4) if told and knows is not None else None,
                "ttft_s": s.get("wait_s"), "peak_ram_gb": max([w["peak_ram_gb"] for w in weeks if w["peak_ram_gb"]],
                                                              default=None)}
    return None


class Records:
    """Every record digested, each read again only when its size or time changes."""

    def __init__(self):
        self.lock = threading.Lock()
        self.cache: dict[str, tuple[tuple[int, int], dict | None, str | None]] = {}
        self.newest: int | None = None  # the last change to any record at the last read, in ns since the epoch

    def read(self, root: Path) -> tuple[list[dict], list[dict]]:
        runs, errors = [], []
        with self.lock:
            seen = set()
            newest = 0
            for p in _files(root):
                key = str(p)
                seen.add(key)
                try:
                    st = p.stat()
                except OSError:
                    continue
                stamp = (st.st_mtime_ns, st.st_size)
                newest = max(newest, st.st_mtime_ns)
                got = self.cache.get(key)
                if got is None or got[0] != stamp:
                    try:
                        if st.st_size > MAX_FILE:
                            raise ValueError("too large to read")
                        got = (stamp, digest(root, p, json.loads(p.read_text(encoding="utf-8"))), None)
                    except Exception as e:  # noqa: BLE001 (a record being written, or a broken one: listed, not fatal)
                        got = (stamp, None, f"{type(e).__name__}: {e}"[:200])
                    self.cache[key] = got
                if got[2]:
                    errors.append({"path": _rel(root, p), "error": got[2]})
                elif got[1]:
                    runs.append(got[1])
            for k in set(self.cache) - seen:
                del self.cache[k]
            self.newest = newest or None
        return runs, errors


# -- the Claude ledger -----------------------------------------------------------------------------------------


def ledger(path: Path) -> dict:
    """Spend per Claude model and in all, counted as camr_engine.bench.claude.Ledger counts it: every line's cost, plus
    the worst case of each hold no call has closed yet."""
    lines = []
    try:
        for ln in path.read_text(encoding="utf-8").splitlines():
            try:
                x = json.loads(ln)
            except json.JSONDecodeError:
                continue
            if isinstance(x, dict):
                lines.append(x)
    except OSError:
        return {"present": False, "cap_usd": CAP_USD, "headroom_usd": HEADROOM_USD, "spent_usd": None, "models": []}
    closed = {x.get("hold") for x in lines if x.get("kind") != "hold"}
    models: dict[str, dict] = {}

    def m(name: str) -> dict:
        return models.setdefault(name, {"model": name, "label": label_of(name), "calls": 0, "failed": 0, "counts": 0,
                                        "input_tokens": 0, "cache_read_tokens": 0, "cache_write_tokens": 0,
                                        "output_tokens": 0, "thinking_tokens": 0, "cost_usd": 0.0, "held_usd": 0.0,
                                        "refused": 0, "last": None})

    for x in lines:
        row = m(str(x.get("model") or "?"))
        kind = x.get("kind")
        row["last"] = x.get("at") or row["last"]
        row["cost_usd"] += _num(x.get("cost_usd")) or 0.0
        if kind == "hold":
            if x.get("hold") not in closed:
                row["held_usd"] += _num(x.get("hold_usd")) or 0.0
        elif kind == "call":
            if x.get("status") == "ok":
                row["calls"] += 1
            else:
                row["failed"] += 1
            for k, src in (("input_tokens", "input_tokens"), ("cache_read_tokens", "cache_read_input_tokens"),
                           ("cache_write_tokens", "cache_creation_input_tokens"), ("output_tokens", "output_tokens"),
                           ("thinking_tokens", "thinking_tokens")):
                row[k] += int(_num(x.get(src)) or 0)
        elif kind == "count":
            row["counts"] += 1
        elif kind == "refused":
            row["refused"] += 1
    rows = sorted(models.values(), key=lambda r: (CLAUDE_ORDER.get((CLAUDE.fullmatch(r["model"]) or [None, ""])[1], 9),
                                                  r["model"]))
    for r in rows:
        r["cost_usd"], r["held_usd"] = round(r["cost_usd"], 6), round(r["held_usd"], 6)
    spent = sum(r["cost_usd"] + r["held_usd"] for r in rows)
    return {"present": True, "cap_usd": CAP_USD, "headroom_usd": HEADROOM_USD, "spent_usd": round(spent, 6),
            "held_usd": round(sum(r["held_usd"] for r in rows), 6), "refused": sum(r["refused"] for r in rows),
            "lines": len(lines), "models": rows}


# -- putting the screen together ------------------------------------------------------------------------------


def _best(runs: list[dict]) -> dict | None:
    """The run that answered most, then the latest: a smoke run never hides a full one."""
    return max(runs, key=lambda r: (r.get("graded") or 0, r.get("started") or "")) if runs else None


def _latest(runs: list[dict]) -> dict | None:
    return max(runs, key=lambda r: (r.get("started") or "", r["path"])) if runs else None


def _windows(runs: list[dict]) -> dict[str, int]:
    """Each model's context window, from the records that state one (bare and Claude runs read whole windows)."""
    out: dict[str, int] = {}
    for r in runs:
        w = _num(r.get("window"))
        if w and r.get("model"):
            out[r["model"]] = int(w)
    return out


def _point(x: Any, y: Any, **kw) -> dict | None:
    x, y = _num(x), _num(y)
    if x is None or y is None or x <= 0:
        return None
    return {"x": x, "y": y, **{k: v for k, v in kw.items() if v is not None}}


def _series(chart: str, sid: str, label: str, memory: str, points: list, **kw) -> dict | None:
    pts = sorted((p for p in points if p), key=lambda p: p["x"])
    if not pts:
        return None
    return {"id": f"{chart}|{sid}", "chart": chart, "label": label, "memory": memory, "points": pts, **kw}


def longhaul(runs: list[dict], windows: dict[str, int]) -> tuple[list[dict], dict, list[dict], list[dict]]:
    """The probe matrix's contenders and cells, the Long Haul's curves, and its page answers."""
    lh = [r for r in runs if r["task"] == "longhaul" and r.get("cuts") is not None]
    by: dict[str, list[dict]] = defaultdict(list)
    for r in lh:
        by[r["contender"]].append(r)
    contenders, cells, series, pages = [], {}, [], []

    def order(name: str) -> tuple:
        r = by[name][0]
        m = CLAUDE.fullmatch(name)
        return ORDER.get(r["memory"], 9), CLAUDE_ORDER.get(m.group(1), 9) if m else 0, name

    for name in sorted(by, key=order):
        rs = by[name]
        r0 = _latest(rs)
        contenders.append({"id": name, "label": r0["label"], "memory": r0["memory"], "model": r0.get("model"),
                           "window": windows.get(r0.get("model") or "")})
        row, pts = {}, defaultdict(list)
        for cut in CUTS:
            have = [r for r in rs if any(c["name"] == cut for c in r["cuts"])]
            if not have:
                continue
            best = max(have, key=lambda r: (next(c for c in r["cuts"] if c["name"] == cut)["all"]["graded"],
                                            r.get("started") or ""))
            c = next(c for c in best["cuts"] if c["name"] == cut)
            row[cut] = {"path": best["path"], "started": best["started"], "tokens": c.get("tokens"),
                        "all": c["all"], "families": c["families"]}
            x, key = CUTS[cut], f"{best['path']}#{cut}"
            common = {"path": best["path"], "cut": cut, "key": key, "tokens": c.get("tokens")}
            a = c["all"]
            pts["score"].append(_point(x, a["score"], n=a["graded"], right=a["right"], fm=a["false_memory"],
                                       declined=a["declined"], **common))
            pts["ttft"].append(_point(x, c["ttft_s"], hi=c["ttft_p90"], **common))
            pts["peak"].append(_point(x, c["peak_ram_gb"], **common))
            pts["decode"].append(_point(c["context_tokens"], c["decode_tps"], **common))
            pts["retrieval"].append(_point(c["memory_bytes"], c["retrieval_ms"], hi=c["retrieval_p90"],
                                           history=x, **common))
            pts["gbps"].append(_point(c["memory_bytes"], c["gbps"], hi=c["gbps_p90"], history=x, **common))
            st = c.get("status") or {}
            for part_, y in (("awake", st.get("awake_rooms")), ("asleep", st.get("asleep_rooms")),
                             ("hot", st.get("hot_rooms"))):
                pts[f"rooms-{part_}"].append(_point(x, y, **common, naps=(st.get("naps") or {}).get("count"),
                                                    notes=st.get("vault_notes"), disk_gb=st.get("disk_gb")))
            pg = [p for p in best.get("pages") or [] if p["cut"] == cut]
            for p in pg:
                pages.append({**p, "path": best["path"], "contender": name, "label": r0["label"],
                              "memory": r0["memory"]})
        cells[name] = row
        info = {"task": "longhaul", "contender": name, "model": r0.get("model"),
                "window": windows.get(r0.get("model") or "")}
        for chart in ("score", "ttft", "peak", "decode", "retrieval", "gbps"):
            s = _series(chart, f"longhaul|{name}", r0["label"], r0["memory"], pts[chart], **info)
            if s:
                series.append(s)
        for part_, memory in (("awake", "tensors"), ("asleep", "words"), ("hot", "ram")):
            s = _series("rooms", f"longhaul|{name}|{part_}", f"{r0['label']} · {part_}", memory,
                        pts[f"rooms-{part_}"], **info)
            if s:
                series.append(s)
    return contenders, cells, series, pages


def curves(runs: list[dict], windows: dict[str, int]) -> list[dict]:
    """The curves that come from records other than the Long Haul's."""
    out = []
    by: dict[tuple, list[dict]] = defaultdict(list)
    for r in runs:
        by[(r["kind"], r["task"], r["contender"])].append(r)
    for (kind, task, name), rs in sorted(by.items()):
        if kind == "suite":
            r = _best(rs)
            pts = [_point(L["history_tokens"], L["score"], n=L["graded"], right=L["right"], fm=L["false_memory"],
                          declined=L["declined"], path=r["path"], cut=L["name"], key=f"{r['path']}#{L['name']}")
                   for L in r.get("lengths") or []]
            s = _series("score", f"{task}|{name}", r["label"], r["memory"], pts, task=task, contender=name,
                        model=r.get("model"), window=windows.get(r.get("model") or ""))
            if s:
                out.append(s)
        elif kind == "speed":
            r = _latest(rs)
            common = {"task": "speed", "contender": name, "model": r.get("model")}
            pp = r.get("points") or []

            def pk(i: int) -> dict:
                return {"path": r["path"], "key": f"{r['path']}#{i}", "cut": f"{pp[i].get('moments')} moments"}

            for chart, xs, ys, his in (("ttft", "history_tokens", "ttft_s", "ttft_p90"),
                                       ("retrieval", "memory_bytes", "retrieval_ms", "retrieval_p90"),
                                       ("gbps", "memory_bytes", "gbps", "gbps_p90"),
                                       ("decode", "context_tokens", "decode_tps", None)):
                s = _series(chart, f"speed|{name}", f"{r['label']} · speed", r["memory"],
                            [_point(p[xs], p[ys], hi=p.get(his) if his else None, **pk(i)) for i, p in enumerate(pp)],
                            **common)
                if s:
                    out.append(s)
            for part_, memory in (("awake", "tensors"), ("asleep", "words"), ("hot", "ram")):
                s = _series("rooms", f"speed|{name}|{part_}", f"{r['label']} · {part_}", memory,
                            [_point(p["history_tokens"], (p.get("status") or {}).get(f"{part_}_rooms"), **pk(i))
                             for i, p in enumerate(pp)], **common)
                if s:
                    out.append(s)
        elif kind == "ruler-speed":
            r = _latest(rs)
            for which, memory in (("notes", "tensors"), ("words", "words")):
                what = "notes · all laid on the desk" if which == "notes" else "words · all read"
                s = _series("ttft", f"ruler-speed|{name}|{which}", f"{what} · ruler {r.get('persona') or ''}".strip(),
                            memory, [_point(p["tokens"], p[f"{which}_s"], path=r["path"], key=f"{r['path']}#{i}",
                                            cut=f"{p['tokens']:.0f} tok") for i, p in enumerate(r["points"])
                                     if p["tokens"]], task="ruler-speed", contender=name, short=f"{which} · ruler")
                if s:
                    out.append(s)
    tp = _latest([r for r in runs if r["kind"] == "throughput"])
    if tp:
        for m in tp["models"]:
            name = f"{m['model']} · {m['runtime']}"
            ok = [p for p in m["points"] if not p.get("error")]

            def pk(p: dict) -> dict:
                return {"path": tp["path"], "key": f"{tp['path']}#{m['runtime']}#{m['model']}#{p['tokens']}",
                        "cut": f"{p['tokens']:.0f} tok"}

            common = {"task": "throughput", "contender": name, "model": m["model"],
                      "faults": [f"{p['tokens']:.0f} tok · {p['error']}" for p in m["points"] if p.get("error")]}
            for chart, ys in (("ttft", "first_word_s"), ("peak", "peak_gb"), ("decode", "write_tps")):
                s = _series(chart, f"throughput|{name}", f"{name} · reads it all", "none",
                            [_point(p["tokens"], p[ys], **pk(p)) for p in ok], short=name, **common)
                if s:
                    out.append(s)
    out.extend(lives(runs))
    return out


def lives(runs: list[dict]) -> list[dict]:
    """The ruler's lives, week by week: what each contender knew of what it was told, the mean over the personas
    (each persona's latest life), with the lowest and highest."""
    latest: dict[tuple, dict] = {}
    for r in runs:
        if r["kind"] != "life" or not r.get("weeks"):
            continue
        k = (r["contender"], r.get("persona"))
        if k not in latest or (r.get("started") or "") > (latest[k].get("started") or ""):
            latest[k] = r
    by: dict[str, list[dict]] = defaultdict(list)
    for (name, _), r in latest.items():
        by[name].append(r)
    out = []
    for name, rs in sorted(by.items(), key=lambda kv: (ORDER.get(kv[1][0]["memory"], 9), kv[0])):
        weeks: dict[int, list[tuple[dict, dict]]] = defaultdict(list)
        for r in rs:
            for w in r["weeks"]:
                if w.get("week") is not None and w.get("told"):
                    weeks[int(w["week"])].append((w, r))
        pts = []
        for wk, ws in sorted(weeks.items()):
            scores = [w["knows"] / w["told"] for w, _ in ws if w.get("knows") is not None]
            if not scores:
                continue
            p = _point(wk, sum(scores) / len(scores), lo=min(scores), hi=max(scores), n=len(scores),
                       fm=sum(w.get("false_memory") or 0 for w, _ in ws),
                       wait_s=spread([w.get("wait_s") for w, _ in ws])["p50"],
                       path=ws[0][1]["path"], key=f"{name}#week{wk}#{len(ws)}", cut=f"week {wk}",
                       told=sum(w["told"] for w, _ in ws), right=sum(w.get("knows") or 0 for w, _ in ws))
            pts.append(p)
        s = _series("life", f"life|{name}", name, rs[0]["memory"], pts, task="life", contender=name,
                    lives=len(rs), personas=sorted(r.get("persona") or "?" for r in rs))
        if s:
            out.append(s)
    return out


def headline(runs: list[dict]) -> dict:
    """Qwen 27B with memory against without: what it knew of the 85 things it was told, over the ruler's lives."""
    lives_ = [r for r in runs
              if r["kind"] == "life" and (r.get("contender") or "").endswith("-27b") and r.get("graded")]
    latest: dict[tuple, dict] = {}
    for r in lives_:
        k = (r["contender"], r.get("persona"))
        if k not in latest or (r.get("started") or "") > (latest[k].get("started") or ""):
            latest[k] = r

    def side(rs: list[dict]) -> dict | None:
        rs = [r for r in rs if r.get("right") is not None]
        if not rs:
            return None
        knows = [r["right"] for r in rs]
        return {"lo": min(knows), "hi": max(knows), "told": max(r["graded"] for r in rs), "lives": len(rs),
                "contenders": sorted({r["contender"] for r in rs}), "paths": sorted(r["path"] for r in rs),
                "peak_ram_gb": max((r["peak_ram_gb"] for r in rs if r.get("peak_ram_gb")), default=None),
                "wait_s": spread([r.get("ttft_s") for r in rs])["p50"]}

    rs = list(latest.values())
    return {"model": "Qwen 27B", "with": side([r for r in rs if r["memory"] != "none"]),
            "without": side([r for r in rs if r["memory"] == "none"])}


def _row(r: dict) -> dict:
    keep = ("path", "name", "kind", "task", "contender", "label", "memory", "started", "finished", "questions",
            "graded", "right", "false_memory", "declined", "score", "ttft_s", "decode_tps", "prefill_tps",
            "retrieval_ms", "gbps", "peak_ram_gb", "cost_usd", "limit", "persona", "publications")
    out = {k: r.get(k) for k in keep}
    if r.get("cuts") is not None:
        out["cuts"] = [c["name"] for c in r["cuts"]]
    elif r.get("lengths") is not None:
        out["cuts"] = [L["name"] for L in r["lengths"]]
    elif r.get("weeks"):
        out["cuts"] = [f"week {r['weeks'][-1]['week']}"] if len(r["weeks"]) == 1 else \
            [f"weeks {r['weeks'][0]['week']}–{r['weeks'][-1]['week']}"]
    elif r.get("points") is not None:
        out["cuts"] = [f"{len(r['points'])} points"]
    elif r.get("models") is not None and r["kind"] == "throughput":
        out["cuts"] = [f"{len(r['models'])} models"]
    return out


def shot_file(app, key: str) -> Path | None:
    """The PNG kept for a page, in the shots folder or beside the records (records/bench/shots)."""
    for d in (shots_dir(app), records_root(app) / "bench" / "shots"):
        p = d / f"{key}.png"
        if p.is_file():
            return p
    return None


def board(app) -> dict:
    from camr_engine.app.measuring import active

    root = records_root(app)
    records = part(app, "_bench_records", Records)
    runs, errors = records.read(root)
    job = active()
    wait = f"{job['job']} is measuring" if job else quiet(root, records.newest)
    windows = _windows(runs)
    contenders, cells, series, pages = longhaul(runs, windows)
    series += curves(runs, windows)
    for p in pages:
        p["shot"] = bool(p["key"] and shot_file(app, p["key"]))
    claude_lh = {r["contender"]: r for r in runs if r["task"] == "longhaul" and r["memory"] == "claude"}
    led = ledger(root / "bench" / "claude-ledger.jsonl")
    for m in led["models"]:
        r = _best([x for x in runs if x["task"] == "longhaul" and x["contender"] == m["model"]])
        if r:
            m["longhaul"] = {"path": r["path"], "right": r["right"], "graded": r["graded"], "cost_usd": r["cost_usd"],
                             "per_right_usd": round(r["cost_usd"] / r["right"], 6) if r["cost_usd"] and r["right"]
                             else None}
    rows = sorted((_row(r) for r in runs), key=lambda r: (r.get("started") or "", r["path"]), reverse=True)
    env = next((r["environment"] for r in sorted(runs, key=lambda r: r.get("started") or "", reverse=True)
                if r.get("environment", {}).get("memory_gb")), {})
    return {"root": "records", "measuring": job, "shoot": {"auto": wait is None, "why": wait},
            "headline": headline(runs),
            "families": [{"id": f, "label": label} for f, label in FAMILIES],
            "cuts": [{"name": k, "tokens": v} for k, v in CUTS.items()], "contenders": contenders, "matrix": cells,
            "series": series, "windows": windows, "runs": rows, "ledger": led, "pages": pages,
            "claude_runs": sorted(claude_lh), "ram_gb": env.get("memory_gb"), "errors": errors,
            "webdev": (root / "bench" / "webdev-arena-history.csv").is_file()}


# -- one record, for its sheet ---------------------------------------------------------------------------------


def _answer(a: dict) -> dict:
    m = a.get("metrics") if isinstance(a.get("metrics"), dict) else {}
    out = {"id": a.get("qid") or a.get("id"), "family": family_of(a) if (a.get("qid") or a.get("id")) else None,
           "kind": a.get("kind"), "verdict": a.get("verdict"), "right": a.get("right")}
    for k, n in TRIM.items():
        if a.get(k) is not None:
            out[k] = _trim(a[k] if isinstance(a[k], str) else json.dumps(a[k]), n)
    for k in ("ttft_s", "total_s", "decode_tps", "retrieval_ms", "gbps", "bytes_read", "context_tokens", "cost_usd",
              "tier"):
        v = m.get(k, a.get(k))
        if v is not None:
            out[k] = v
    if a.get("tool") is not None:
        out["tool"] = a.get("tool")
    return out


def _scalars(d: dict, drop: tuple = ()) -> dict:
    home = str(Path.home())
    out = {}
    for k, v in d.items():
        if k in drop or isinstance(v, (dict, list)) or k in ("folder", "path", "ledger", "dir", "request_id",
                                                              "message_id"):
            continue
        out[k] = v.replace(home, "~") if isinstance(v, str) else v
    return out


def record_sheet(root: Path, rel: str) -> dict:
    p = safe_path(root, rel)
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise Refused(409, f"{rel} cannot be read now ({type(e).__name__}); it may be being written") from None
    if not isinstance(data, dict):
        raise Refused(409, f"{rel} is not a record")
    con = data.get("contender")
    name = data.get("model") if data.get("kind") == "claude-yardstick" else \
        (con.get("name") if isinstance(con, dict) else con)
    groups = []
    if isinstance(data.get("checkpoints"), list):
        for cp in data["checkpoints"]:
            s = (cp.get("summary") or {})
            s = s.get("all", s) if isinstance(s.get("all"), dict) else s
            groups.append({"name": cp.get("checkpoint") or cp.get("name"),
                           "summary": _scalars({**_scalars(cp), **{k: v for k, v in s.items()
                                                                    if not isinstance(v, (dict, list))},
                                                **{f"{k} p50": v.get("p50") for k, v in s.items()
                                                   if isinstance(v, dict) and "p50" in v}}),
                           "answers": [_answer(a) for a in (cp.get("answers") or [])[:300]]})
    elif isinstance(data.get("weeks"), list):
        for w in data["weeks"]:
            if isinstance(w, dict):
                groups.append({"name": f"week {w.get('week')}", "summary": {**_scalars(w), **(w.get("summary") or {})},
                               "answers": [_answer(a) for a in (w.get("answers") or [])[:300]]})
    elif isinstance(data.get("groups"), list):
        by: dict[str, list] = defaultdict(list)
        for g in data["groups"]:
            for a in g.get("answers") or []:
                by[str(a.get("length") or (g.get("meta") or {}).get("length") or "all")].append(_answer(a))
        groups = [{"name": k, "summary": {}, "answers": v[:300]} for k, v in by.items()]
    elif isinstance(data.get("tasks"), list):
        groups.append({"name": "tasks", "summary": _scalars(data.get("summary") or {}),
                       "answers": [_answer(a) for a in data["tasks"][:300]]})
    elif isinstance(data.get("points"), list):
        groups.append({"name": "points", "summary": {},
                       "rows": [_scalars({**p, **{f"{k} p50": v.get("p50") for k, v in (p.get("summary") or {}).items()
                                                  if isinstance(v, dict) and "p50" in v}})
                                for p in data["points"][:200] if isinstance(p, dict)], "answers": []})
    elif data.get("kind") == "throughput":
        for runtime in ("mlx", "ollama"):
            for model, m in (data.get(runtime) or {}).items():
                groups.append({"name": f"{model} · {runtime}", "summary": _scalars(m),
                               "rows": [_scalars(x) for x in m.get("points") or []], "answers": []})
    return {"path": rel, "kind": data.get("kind"), "task": data.get("task"), "contender": name,
            "label": label_of(str(name or p.stem)), "memory": memory_of((con or {}).get("kind") if isinstance(con, dict)
                                                                         else data.get("kind"), str(name or "")),
            "started": data.get("started"), "finished": data.get("finished"),
            "environment": _env(data.get("environment")),
            "settings": _scalars(data, drop=("kind", "task", "contender", "started", "finished", "model")),
            "contender_settings": _scalars(con) if isinstance(con, dict) else {}, "groups": groups,
            "bytes": p.stat().st_size}


# -- WebDev Arena ------------------------------------------------------------------------------------------------


def _norm(name: str) -> str:
    return re.sub(r"[\s_]+", "-", re.sub(r"\(.*?\)", "", name or "")).strip("-").lower()


def on_this_mac() -> set[str]:
    """The names of the models this Mac runs, as the board would print them (the repo name less ``-4bit``)."""
    from camr_engine.models import READER, READER_27B, READER_BIG

    return {_norm(re.sub(r"-\d+bit.*$", "", r.split("/")[-1])) for r in (READER, READER_BIG, READER_27B)}


def webdev(path: Path, summary: Path) -> dict:
    """At every publication of the overall board: the best Claude, the best open-weights model and each model this
    Mac runs, with their 95% intervals."""
    if not path.is_file():
        return {"present": False, "dates": [], "series": {}}
    mine = on_this_mac()
    by_date: dict[str, dict[str, dict]] = defaultdict(dict)
    with path.open(newline="", encoding="utf-8") as f:
        for r in csv.DictReader(f):
            if (r.get("category") or "overall") != "overall":
                continue
            try:
                rating = float(r["rating"])
                lo, hi = float(r.get("ci_low") or rating), float(r.get("ci_high") or rating)
            except (KeyError, ValueError):
                continue
            item = {"date": r["date"], "rating": rating, "lo": lo, "hi": hi, "model": r.get("model_key") or r["model"],
                    "organisation": r.get("organisation")}
            day = by_date[r["date"]]
            slots = []
            if (r.get("organisation") or "").lower() == "anthropic":
                slots.append("claude")
            if (r.get("open_weights") or "").lower() == "true":
                slots.append("open")
            else:
                slots.append("closed")
            if _norm(r.get("model_key") or "") in mine or _norm(r.get("model") or "") in mine:
                slots.append("mac:" + item["model"])
            for s in slots:
                if s not in day or rating > day[s]["rating"]:
                    day[s] = item
    dates = sorted(by_date)
    series: dict[str, list] = defaultdict(list)
    for d in dates:
        for s, item in by_date[d].items():
            series[s].append(item)
    meta = {}
    try:
        meta = json.loads(summary.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        pass
    return {"present": True, "dates": dates, "series": dict(series), "source": meta.get("source"),
            "note": meta.get("note"), "publications": len(dates), "models": meta.get("models"),
            "path": "bench/" + path.name}


# -- screenshots -------------------------------------------------------------------------------------------------


def _browser() -> str | None:
    from camr_engine.bench.haul.page import find_browser

    return find_browser()


def png_size(data: bytes) -> tuple[int, int] | None:
    if not data.startswith(PNG) or len(data) < 24:
        return None
    return int.from_bytes(data[16:20], "big"), int.from_bytes(data[20:24], "big")


_PS: dict[str, Any] = {"at": None, "value": None}
_PS_LOCK = threading.Lock()


def running(run: Callable = subprocess.run) -> str | None:
    """The benchmark or model runner alive on this Mac, by its module (``camr_engine.bench.local``), or None. Read from the
    process list at most every 15 s. Not every runner raises the measuring flag, so this is the second sign that the
    CPU belongs to a measurement."""
    with _PS_LOCK:
        if _PS["at"] is not None and time.monotonic() - _PS["at"] < 15:
            return _PS["value"]
        try:
            out = run(["ps", "-axo", "pid=,command="], capture_output=True, text=True, timeout=2,
                      stdin=subprocess.DEVNULL).stdout or ""
        except (OSError, subprocess.SubprocessError):
            out = ""
        found = None
        for ln in out.splitlines():
            pid, _, cmd = ln.strip().partition(" ")
            m = RUNNERS.search(cmd) if pid != str(os.getpid()) else None
            if m:
                found = next(g for g in m.groups() if g)
                break
        _PS.update(at=time.monotonic(), value=found)
        return found


def quiet(root: Path, newest_ns: int | None) -> str | None:
    """Why pages wait for a click before they are shot, or None when the screen may shoot them on its own: a record
    (or the Claude ledger) changed in the last QUIET_S, so a run is likely writing, or a benchmark process is alive."""
    try:
        newest_ns = max(newest_ns or 0, (root / "bench" / "claude-ledger.jsonl").stat().st_mtime_ns)
    except OSError:
        pass
    if newest_ns:
        ago = time.time() - newest_ns / 1e9
        if ago < QUIET_S:
            return f"waiting: a record changed {'under a minute' if ago < 60 else f'{int(ago // 60)} min'} ago"
    run = running()
    return f"waiting: {run} is running" if run else None


def render(html: str, out: Path, browser: str, size: tuple[int, int] = SHOT_SIZE, timeout: float = 45.0,
           run: Callable = subprocess.run) -> Path:
    """Shoot ``html`` in a headless browser with the network switched off, then keep the PNG at ``out``.

    - The page goes in as a ``data:`` URL, never as a file: a page loaded from ``file://`` can frame, or redirect to,
      any file this user can read, and that file would land in the PNG.
    - Every host resolves to nothing, every request (loopback too) goes to a proxy that is not there, QUIC is off, and
      WebRTC sends no UDP past that proxy.
    - A page over MAX_PAGE is refused (413), since the URL rides on the command line."""
    raw = html.encode("utf-8")
    if len(raw) > MAX_PAGE:
        raise Refused(413, f"the page is {len(raw) // 1024} KB; pages over {MAX_PAGE // 1024} KB are not shot")
    url = "data:text/html;charset=utf-8;base64," + base64.b64encode(raw).decode("ascii")
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="camr-shot-") as tmp:
        shot = Path(tmp) / "shot.png"  # the folder holds the browser's profile and the PNG, never the page
        cmd = [browser, "--headless=new", "--disable-gpu", "--no-first-run", "--no-default-browser-check",
               "--disable-extensions", "--disable-background-networking", "--disable-sync", "--mute-audio",
               "--hide-scrollbars", f"--user-data-dir={tmp}/profile", "--host-resolver-rules=MAP * ~NOTFOUND",
               "--proxy-server=127.0.0.1:9", "--proxy-bypass-list=<-loopback>", "--disable-quic",
               "--force-webrtc-ip-handling-policy=disable_non_proxied_udp", "--force-device-scale-factor=1",
               f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=3000", f"--screenshot={shot}", url]
        try:
            run(cmd, capture_output=True, timeout=timeout, stdin=subprocess.DEVNULL)
        except subprocess.TimeoutExpired:
            raise Refused(504, "the browser timed out shooting the page") from None
        except OSError as e:
            raise Refused(409, f"the browser would not start ({e})") from None
        data = shot.read_bytes() if shot.is_file() else b""
        if not png_size(data):
            raise Refused(502, "the browser made no screenshot")
        tmp_out = out.with_suffix(".tmp")
        tmp_out.write_bytes(data)
        os.replace(tmp_out, out)
    return out


def _page_html(root: Path, rel: str, cut: str, qid: str) -> str:
    from camr_engine.bench.haul.page import extract_html

    p = safe_path(root, rel)
    data = json.loads(p.read_text(encoding="utf-8"))
    for cp in (data.get("checkpoints") or []) if isinstance(data, dict) else []:
        if (cp.get("checkpoint") or cp.get("name")) != cut:
            continue
        for a in cp.get("answers") or []:
            if (a.get("qid") or a.get("id")) == qid:
                if family_of(a) != "page":
                    raise Refused(400, f"{qid} is not a page")
                html = extract_html(a.get("answer") or "")
                if not html:
                    raise Refused(409, "that answer holds no HTML page")
                return html
    raise Refused(404, f"no answer {qid} at {cut} in {rel}")


# -- the routes --------------------------------------------------------------------------------------------------


def register(routes: Routes) -> None:
    @routes.get("/api/bench")
    def bench(req: Request) -> dict:
        return board(req.app)

    @routes.get("/api/bench/record")
    def record(req: Request) -> dict:
        return record_sheet(records_root(req.app), req.str("path", limit=400))

    @routes.get("/api/bench/webdev")
    def arena(req: Request) -> dict:
        root = records_root(req.app) / "bench"
        path = root / "webdev-arena-history.csv"
        box = part(req.app, "_bench_webdev", lambda: {"stamp": None, "value": None})
        try:
            stamp = (path.stat().st_mtime_ns, path.stat().st_size)
        except OSError:
            stamp = None
        if box["stamp"] != stamp or box["value"] is None:
            box["value"], box["stamp"] = webdev(path, root / "webdev-arena-summary.json"), stamp
        return box["value"]

    @routes.get("/api/bench/shot")
    def shot(req: Request) -> dict:
        key = req.str("key", limit=40)
        if not KEY.match(key):
            raise Refused(400, "key is 16 hex digits")
        p = shot_file(req.app, key)
        if p is None:
            raise Refused(404, "no screenshot of that page yet")
        data = p.read_bytes()
        size = png_size(data)
        if not size:
            raise Refused(409, "that screenshot is not a PNG")
        return {"key": key, "width": size[0], "height": size[1], "bytes": len(data),
                "png": "data:image/png;base64," + base64.b64encode(data).decode("ascii")}

    @routes.post("/api/bench/shot")
    def make_shot(req: Request) -> dict:
        from camr_engine.app.measuring import active

        root = records_root(req.app)
        html = _page_html(root, req.str("path", limit=400), req.str("cut", limit=20), req.str("qid", limit=80))
        key = _key(html)
        have = shot_file(req.app, key)
        if have is not None:
            return {"key": key, "made": False}
        job = active()
        if job:
            raise Refused(409, f"{job['job']} is measuring: pages are shot after it")
        if not req.bool("asked"):  # the screen on its own: only while nothing runs
            records = part(req.app, "_bench_records", Records)
            records.read(root)
            wait = quiet(root, records.newest)
            if wait:
                raise Refused(409, f"{wait}: click the page to shoot it now")
        browser = _browser()
        if not browser:
            raise Refused(409, "no headless browser on this Mac (Chrome, Chromium, Brave or Edge)")
        lock = part(req.app, "_bench_shooting", threading.Lock)
        if not lock.acquire(blocking=False):
            raise Refused(409, "another page is being shot")
        try:
            render(html, shots_dir(req.app) / f"{key}.png", browser)
        finally:
            lock.release()
        return {"key": key, "made": True}

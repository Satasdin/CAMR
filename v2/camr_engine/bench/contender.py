"""The contender protocol every benchmark runner shares: the local MLX models (camr_engine.bench.local), Ollama through the
pairing, and anything else that answers the Long Haul or a suite.

A contender is told a history one event at a time, in order (``tell``), and is asked questions (``ask``). Each answer
comes back as its text and one metrics dict with the same keys for every contender, None where a contender cannot
know. ``run`` is the runner they share:
- it feeds each checkpoint's events with ``tell`` and asks its questions with ``ask``;
- it grades every answer with the grader given (camr_engine.bench.longhaul.grader, or a suite's own grade);
- after every checkpoint it saves a dated record: records/bench/<YYYY-MM-DD>/<HHMMSS>-<task>-<contender>.json.

A record holds the answers, their metrics, a summary per family and the environment. In a record, every answer's
``history_tokens`` is the history told so far as the task counts it (the Long Haul's own token count), the same for
every contender; the contender's own count of what it holds is kept in ``extra.memory_tokens``.

A question that fails is recorded with verdict "error" and right None, so it is never graded (as Claude's runner
leaves its failures). An answer that used all its room is marked ``truncated``; it is graded as it stands, and the
summary counts it. An answer to a question already asked at an earlier checkpoint is marked ``asked_before``.

Answers are given room by family: 1,200 tokens for a page, 600 for code, 400 for maths and 120 for everything else.
Qwen3's thinking is off for every local model (``enable_thinking=False`` in the chat template), and records say so.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Iterable, Sequence

from camr_engine.metrics import spread

MAX_TOKENS = {"page": 1200, "code": 600, "maths": 400}
OTHER_TOKENS = 120  # every other family
THINKING = False  # Qwen3's thinking, for every local model
METRICS = ("ttft_s", "total_s", "prefill_tps", "decode_tps",  # time to the first word and to the last; speeds
           "retrieval_ms", "bytes_read", "gbps", "read_share",  # finding the memory, reading it, its share of the wait
           "context_tokens", "history_tokens", "peak_ram_gb", "disk_gb",  # what was read, against what was told
           "tier")  # where the memory came from: ram, ssd or vault
TIERS = ("ram", "ssd", "vault")
RIGHT = {"right", "right_abstain"}
HISTORY = ("the history told so far, as the task counts it (the same for every contender); extra.memory_tokens is "
           "the contender's own count of what it holds")

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "records" / "bench"


def max_tokens(family: str | None) -> int:
    """The room an answer gets: by its family, 120 tokens when the family is not one that writes at length."""
    return MAX_TOKENS.get(family or "", OTHER_TOKENS)


def metrics(**values: Any) -> dict:
    """A metrics dict: every key of METRICS, None unless given. An unknown key or tier is a mistake, so it raises."""
    bad = set(values) - set(METRICS)
    if bad:
        raise ValueError(f"not answer metrics: {sorted(bad)}")
    if values.get("tier") is not None and values["tier"] not in TIERS:
        raise ValueError(f"tier is one of {TIERS} or None, not {values['tier']!r}")
    return {k: values.get(k) for k in METRICS}


def decode_tps(answer_tokens: int | None, total_s: float | None, ttft_s: float | None) -> float | None:
    """Tokens written per second after the first word: (tokens - 1) over (total - first word). mlx_lm's own figure
    counts n + 1 tokens over the time of n, which is 20% high on a 6-token answer."""
    if not answer_tokens or answer_tokens < 2 or total_s is None or ttft_s is None or total_s <= ttft_s:
        return None
    return round((answer_tokens - 1) / (total_s - ttft_s), 1)


@dataclass
class Answer:
    text: str
    metrics: dict = field(default_factory=metrics)
    extra: dict = field(default_factory=dict)  # what only this contender knows: retrieval steps, the room, ...


class Contender:
    """One memory approach in front of one model. Subclasses set ``name`` and implement ``tell`` and ``ask``."""

    name: str = "contender"

    def open(self, folder: Path) -> None:
        """Start with an empty memory, kept in ``folder`` (a contender with no memory may ignore it)."""

    def tell(self, text: str, day: int) -> None:
        """One event of the history, in order. ``day`` is the history's own day number."""
        raise NotImplementedError

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        """Answer from what was told so far. ``family`` is the question's kind (page, code, maths, fact, ...)."""
        raise NotImplementedError

    def close(self) -> None:
        """Let go of the models' memory and save what is kept."""

    def cut_told(self, checkpoint: dict) -> None:
        """Every event of ``checkpoint`` is told, and its questions come next (a contender may keep a copy)."""

    def describe(self) -> dict:
        """The contender's settings, for the record."""
        return {"name": self.name}

    def status(self) -> dict:
        """What the contender holds now, for the record after each checkpoint."""
        return {}

    def reading_s(self) -> float:
        """Seconds spent so far taking in what was told outside ``tell`` and outside any answer's own time (reading
        a window before the first question, saving an index), so the runner counts it as ingest."""
        return 0.0


def stamp(text: str, date: dt.date, day: int | None = None) -> str:
    """A moment as the ruler dates it, ``[YYYY-MM-DD] text``; with ``day``, ``[YYYY-MM-DD, day N] text``."""
    return f"[{date.isoformat()}{f', day {day}' if day is not None else ''}] {text}"


def slug(name: str) -> str:
    """A contender's name as it goes in a file name: ``engine:qwen3-1.7b`` -> ``engine-qwen3-1.7b``."""
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "contender"


def record_path(task: str, name: str, started: dt.datetime, records: Path = RECORDS) -> Path:
    return Path(records) / f"{started:%Y-%m-%d}" / f"{started:%H%M%S}-{slug(task)}-{slug(name)}.json"


def write_record(record: dict, path: Path) -> Path:
    """Write the record whole, through a temporary file, so a reader never sees half of it."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(record, indent=1, default=str))
    tmp.replace(path)
    return path


def pick(questions: Sequence[dict], limit: int | None) -> list[dict]:
    """The first ``limit`` questions taken one family at a time, in turn, so a short run still sees every family."""
    if not limit or limit >= len(questions):
        return list(questions)
    fams: dict[str, list[dict]] = {}
    for q in questions:
        fams.setdefault(str(q.get("family")), []).append(q)
    out: list[dict] = []
    while len(out) < limit:
        for qs in fams.values():
            if qs and len(out) < limit:
                out.append(qs.pop(0))
    return out


def grade_with(grader: Callable[[Any, str], Any] | None, question: Any, text: str) -> tuple[bool | None, str | None,
                                                                                            str | None]:
    """(right, verdict, reason) from a grader's dict, verdict string or bool. A grader that fails leaves the answer
    ungraded, so an answer is never lost."""
    if grader is None:
        return None, None, None
    try:
        out = grader(question, text)
    except Exception as e:  # noqa: BLE001: the answer is kept whatever the grader does
        return None, "grader_error", f"{type(e).__name__}: {e}"
    if isinstance(out, bool):
        return out, "right" if out else "wrong", None
    if isinstance(out, str):
        return out in RIGHT, out, None
    if isinstance(out, dict):
        verdict = out.get("verdict")
        return bool(out.get("right", verdict in RIGHT)), verdict, out.get("reason")
    if isinstance(out, tuple) and out:  # a Grade(verdict, reason)
        return out[0] in RIGHT, out[0], out[1] if len(out) > 1 else None
    return bool(out), "right" if out else "wrong", None


def ask_one(contender: Contender, q: dict, grader: Callable[[Any, str], Any] | None, *,
            history_tokens: int | None = None) -> dict:
    """Ask one question, grade it, and its answer's record. A question that fails is recorded with verdict "error"
    and right None (never graded). ``history_tokens`` is the history told so far as the task counts it: it goes in
    the metrics, and the contender's own count moves to ``extra.memory_tokens``."""
    fam = q.get("family")
    room = max_tokens(fam)
    try:
        a = contender.ask(q["question"], max_tokens=room, family=fam)
        right, verdict, reason = grade_with(grader, q, a.text)
        out, m, extra = a.text, metrics(**a.metrics), dict(a.extra)
    except Exception as e:  # noqa: BLE001: one failed question is recorded, not fatal
        right, verdict, reason = None, "error", f"{type(e).__name__}: {e}"[:400]
        out, m, extra = None, metrics(), {}
    if history_tokens is not None:
        extra["memory_tokens"] = m["history_tokens"]
        m["history_tokens"] = history_tokens
    n = extra.get("answer_tokens")
    return {"id": q.get("id"), "family": fam, "question": q["question"], "expected": q.get("expected"),
            "answer": out, "verdict": verdict, "right": right, "reason": reason, "max_tokens": room,
            "truncated": None if n is None else int(n) >= room, "metrics": m, "extra": extra}


def _summary(answers: list[dict]) -> dict:
    m = [a["metrics"] for a in answers]
    tiers = Counter(str(x.get("tier")) for x in m)
    peaks = [x["peak_ram_gb"] for x in m if x.get("peak_ram_gb") is not None]
    return {"questions": len(answers), "right": sum(a["right"] is True for a in answers),
            "graded": sum(a["right"] is not None for a in answers),
            "errors": sum(a.get("verdict") == "error" for a in answers),
            "truncated": sum(a.get("truncated") is True for a in answers),
            "asked_before": sum(a.get("asked_before") is True for a in answers),
            "verdicts": dict(Counter(str(a["verdict"]) for a in answers)),
            **{k: spread(x.get(k) for x in m) for k in ("ttft_s", "total_s", "prefill_tps", "decode_tps",
                                                         "retrieval_ms", "bytes_read", "gbps", "read_share",
                                                         "context_tokens")},
            "history_tokens": max((x["history_tokens"] for x in m if x.get("history_tokens") is not None),
                                  default=None),
            "peak_ram_gb": round(max(peaks), 3) if peaks else None,
            "disk_gb": next((x["disk_gb"] for x in reversed(m) if x.get("disk_gb") is not None), None),
            "tiers": dict(tiers)}


def summarize(answers: list[dict]) -> dict:
    """Per family and for ``all``: right, graded, errors, truncated, verdicts, and the median and 90th percentile of
    every metric."""
    fams: dict[str, list[dict]] = {}
    for a in answers:
        fams.setdefault(str(a.get("family")), []).append(a)
    return {**{f: _summary(xs) for f, xs in fams.items()}, "all": _summary(answers)}


def environment() -> dict:
    """The machine and the code, as the ruler records them."""
    from camr_engine.ruler.harness import environment as env

    return env()


def _text(event: dict) -> str:
    from camr_engine.bench.longhaul import line

    return line(event)


def run(contender: Contender, events: Sequence[dict], checkpoints: Sequence[dict], *, task: str,
        grader: Callable[[Any, str], Any] | None, folder: Path, text: Callable[[dict], str] = _text,
        limit: int | None = None, records: Path = RECORDS, progress: Callable[[str], None] = print,
        meta: dict | None = None, save: bool = True, raise_failure: bool = True) -> dict:
    """Put ``contender`` through every checkpoint in order and return the run record, saved after each checkpoint.

    A checkpoint is {name, events, questions, tokens?}: the first ``events`` events are told by then. Each question is
    {id, question, family, expected?, ...} and is graded by ``grader(question, answer_text)``. ``text`` turns an
    event into what is told (by default the Long Haul's line: a day line alone, else who said it and what). ``limit``
    asks at most that many questions per checkpoint, every family in turn. A question that fails is recorded with
    verdict "error" and the run goes on.

    A failure outside a question (opening, telling, a status) ends the run: the record is saved with ``failed``
    saying where, then the error is raised again, or, with ``raise_failure`` false, the record is returned."""
    started = dt.datetime.now()
    path = record_path(task, contender.name, started, records)
    record: dict[str, Any] = {"kind": "bench", "task": task, "contender": {"name": contender.name},
                              "thinking": THINKING, "max_tokens": {**MAX_TOKENS, "other": OTHER_TOKENS},
                              "limit": limit, "folder": str(folder),
                              "started": started.isoformat(timespec="seconds"), "environment": environment(),
                              "history_tokens": HISTORY, **(meta or {}), "checkpoints": []}
    stage, where = "open", None
    try:
        contender.open(Path(folder))
        record["contender"] = contender.describe()
        told, told_tokens = 0, 0
        asked: set = set()  # question ids asked at earlier checkpoints
        for cp in checkpoints:
            where, stage = cp["name"], "tell"
            read0 = contender.reading_s()
            t, tokens, n = time.perf_counter(), 0, 0
            for e in events[told:cp["events"]]:
                contender.tell(text(e), e["day"])
                tokens += int(e.get("tokens") or 0)
                n += 1
            told = max(told, cp["events"])
            told_tokens += tokens
            tell_s = time.perf_counter() - t
            contender.cut_told(cp)
            history = cp.get("tokens") if cp.get("tokens") is not None else told_tokens
            stage = "ask"
            answers, chosen = [], pick(cp["questions"], limit)
            for q in chosen:
                a = ask_one(contender, q, grader, history_tokens=history)
                a["asked_before"] = q.get("id") in asked
                answers.append(a)
            asked.update(q.get("id") for q in chosen if q.get("id") is not None)
            stage = "status"
            read_s = max(contender.reading_s() - read0, 0.0)
            ingest_s = tell_s + read_s
            r = {"name": cp["name"], "tokens": cp.get("tokens"), "events": cp["events"],
                 "ingest": {"events": n, "tokens": tokens, "seconds": round(ingest_s, 3), "tell_s": round(tell_s, 3),
                            "read_s": round(read_s, 3),
                            "events_per_s": round(n / ingest_s, 2) if ingest_s > 0 and n else None,
                            "tokens_per_s": round(tokens / ingest_s, 1) if ingest_s > 0 and tokens else None},
                 "status": contender.status(), "footprint_gb": _footprint_gb(), "summary": summarize(answers),
                 "answers": answers}
            record["checkpoints"].append(r)
            record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
            if save:
                record["path"] = str(write_record(record, path))
            s = r["summary"]["all"]
            progress(f"{contender.name} {cp['name']}: right {s['right']}/{s['graded']} graded of {s['questions']} "
                     f"(errors {s['errors']}, truncated {s['truncated']}), ingest {n} events in {ingest_s:.1f} s, "
                     f"first word p50 {s['ttft_s']['p50']} s, retrieval p50 {s['retrieval_ms']['p50']} ms, context "
                     f"p50 {s['context_tokens']['p50']} tokens")
    except Exception as e:  # noqa: BLE001: the record says where the run stopped, then the caller decides
        record["failed"] = {"checkpoint": where, "stage": stage, "error": f"{type(e).__name__}: {e}"[:400]}
        record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        if save:
            record["path"] = str(write_record(record, path))
        progress(f"{contender.name} failed at {where or 'the start'} ({stage}): {record['failed']['error']}")
        if raise_failure:
            raise
    finally:
        contender.close()
    return record


def _footprint_gb() -> float | None:
    """This process's physical footprint after a checkpoint (camr_engine.models.footprint_bytes), or None."""
    from camr_engine.models import footprint_bytes

    got = footprint_bytes()
    return round(got / 1e9, 3) if got is not None else None


def ask_all(contender: Contender, questions: Iterable[dict], grader: Callable[[Any, str], Any] | None = None, *,
            history_tokens: int | None = None) -> list[dict]:
    """Ask and grade some questions without telling anything (for a point taken in the middle of an ingest). A
    question that fails is recorded with verdict "error", as in ``run``."""
    return [ask_one(contender, q, grader, history_tokens=history_tokens) for q in questions]

"""Running a contender through a life, and the test record every run leaves.

Each day: the contender observes the day's notes, then sleeps. At the end of each week (after that night's sleep)
it takes the quiz: the same 100 questions every week, graded against that day's right answers. The record is
rewritten after every week, so a stopped run still leaves the weeks it finished.
"""

from __future__ import annotations

import dataclasses
import datetime as dt
import hashlib
import json
import platform
import statistics
import subprocess
import time
from collections import Counter
from pathlib import Path

from engram.models import peak_gb, peak_reset
from engram.ruler.contenders import Contender
from engram.ruler.grade import grade
from engram.ruler.life import Life

ROOT = Path(__file__).resolve().parents[2]
RECORDS = ROOT / "records"


def _sh(*cmd: str) -> str:
    try:
        return subprocess.run(cmd, capture_output=True, text=True, timeout=10).stdout.strip()
    except (OSError, subprocess.TimeoutExpired):
        return ""


def source_sha() -> str:
    """A fingerprint of engram's own code, so a record names the code that made it even before any commit."""
    h = hashlib.sha256()
    for p in sorted((ROOT / "engram").rglob("*.py")):
        h.update(p.relative_to(ROOT).as_posix().encode() + b"\0" + p.read_bytes())
    return h.hexdigest()[:16]


def environment() -> dict:
    versions = {}
    for mod in ("mlx", "mlx_lm", "numpy"):
        try:
            versions[mod] = __import__(mod).__version__
        except (ImportError, AttributeError):
            try:
                from importlib.metadata import version

                versions[mod] = version(mod.replace("_", "-"))
            except Exception:
                versions[mod] = None
    return {"machine": _sh("sysctl", "-n", "hw.model") or platform.machine(), "chip": _sh("sysctl", "-n",
            "machdep.cpu.brand_string"), "memory_gb": round(int(_sh("sysctl", "-n", "hw.memsize") or 0) / 2**30),
            "power": (_sh("pmset", "-g", "batt").splitlines() or [""])[0].replace("Now drawing from ", "").strip("'"),
            "load_1m": float((_sh("sysctl", "-n", "vm.loadavg").strip("{} ").split() or ["nan"])[0]),
            "python": platform.python_version(), "engram_commit": _sh("git", "-C", str(ROOT), "rev-parse", "--short",
            "HEAD") or None, "engram_dirty": bool(_sh("git", "-C", str(ROOT), "status", "--porcelain")),
            "engram_source_sha": source_sha(), **versions}


def summarize(answers: list[dict]) -> dict:
    v = Counter(a["verdict"] for a in answers)
    told = sum(a["expected"] is not None for a in answers)
    waits = sorted(a["ttft_s"] for a in answers)
    return {"questions": len(answers), "told": told, "knows": v["right"], "untold": len(answers) - told,
            "honest": v["right_abstain"], "false_memories": v["false_memory"], "stale": v["stale"],
            "missed": v["missed"], "wrong": v["wrong"], "right_total": v["right"] + v["right_abstain"],
            "wait_median_s": round(statistics.median(waits), 3) if waits else None,
            "wait_p90_s": round(waits[int(0.9 * (len(waits) - 1))], 3) if waits else None,
            "gen_tps_median": round(statistics.median(a["gen_tps"] for a in answers), 1) if answers else None,
            "prompt_tokens_median": statistics.median(a["prompt_tokens"] for a in answers) if answers else None}


def run(life: Life, contender: Contender, *, weeks: int = 12, limit: int | None = None,
        records: Path = RECORDS, progress=print) -> Path:
    """Run ``contender`` through the first ``weeks`` of ``life``; returns the path of the test record."""
    questions = life.questions[:limit] if limit else life.questions
    started = dt.datetime.now()
    path = records / started.strftime("%Y-%m-%d") / (
        f"{started.strftime('%H%M%S')}-{life.persona}-s{life.seed}-{contender.name}.json")
    path.parent.mkdir(parents=True, exist_ok=True)
    record = {"kind": "life", "persona": life.persona, "seed": life.seed, "contender": contender.describe(),
              "questions": len(questions), "weeks_planned": weeks, "started": started.isoformat(timespec="seconds"),
              "environment": environment(), "weeks": []}
    observe_s = sleep_s = 0.0
    for day in life.days[:weeks * 7]:
        t = time.perf_counter()
        contender.observe(day)
        observe_s += time.perf_counter() - t
        t = time.perf_counter()
        contender.sleep(day)
        sleep_s += time.perf_counter() - t
        if day.index not in life.quiz_days:
            continue
        peak_reset()
        t = time.perf_counter()
        contender.begin_quiz(day.date)
        answers = []
        for q in questions:
            reply = contender.answer(q.text)
            right = q.answer_on(day.index)
            answers.append({"qid": q.qid, "kind": q.kind, "question": q.text,
                            "expected": right[0] if right else None, "answer": reply.text,
                            "verdict": grade(q, reply.text, day.index), "ttft_s": round(reply.ttft_s, 4),
                            "gen_tps": round(reply.gen_tps, 1), "prompt_tokens": reply.prompt_tokens})
        contender.end_quiz()
        week = {"week": day.index // 7 + 1, "date": day.date.isoformat(), "notes_so_far": sum(
                    len(d.notes) for d in life.days[:day.index + 1]), "quiz_s": round(time.perf_counter() - t, 1),
                "observe_s": round(observe_s, 1), "sleep_s": round(sleep_s, 1), "peak_ram_gb": peak_gb(),
                "disk_mb": round(contender.disk_bytes() / 1e6, 2), "summary": summarize(answers), "answers": answers}
        observe_s = sleep_s = 0.0
        record["weeks"].append(week)
        record["finished"] = dt.datetime.now().isoformat(timespec="seconds")
        path.write_text(json.dumps(record, indent=1, default=_jsonable))
        s = week["summary"]
        progress(f"{life.persona} s{life.seed} {contender.name} week {week['week']:2d}: knows {s['knows']}/{s['told']}"
                 f", honest {s['honest']}/{s['untold']}, false memories {s['false_memories']}, stale {s['stale']}, "
                 f"wait {s['wait_median_s']} s, peak {week['peak_ram_gb'] and round(week['peak_ram_gb'], 2)} GB")
    return path


def _jsonable(o):
    if dataclasses.is_dataclass(o):
        return dataclasses.asdict(o)
    return str(o)

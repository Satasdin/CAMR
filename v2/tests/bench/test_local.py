"""The contender protocol every runner shares, and the local contenders (engine, words, bare), with fakes: no model
is loaded. The engine and words tests use test_core's fake reader and embedder, which need MLX for their arrays; the
rest run anywhere."""

from __future__ import annotations

import datetime as dt
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from engram.bench import contender as cn
from engram.bench import local
from engram.bench.contender import (METRICS, TIERS, Answer, Contender, ask_all, decode_tps, grade_with, max_tokens,
                                    metrics, pick, record_path, run, stamp, summarize)
from engram.models import Reply

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # test_core's fakes

START = dt.date(2025, 9, 21)  # the day before day 1


def dates(day: int) -> dt.date:
    return START + dt.timedelta(days=day)


@pytest.fixture(autouse=True)
def quiet_environment(monkeypatch):
    monkeypatch.setattr(cn, "environment", lambda: {"machine": "test"})
    monkeypatch.setattr(local, "environment", lambda: {"machine": "test"})


# -- the protocol


def test_every_answer_carries_the_same_metric_keys():
    assert METRICS == ("ttft_s", "total_s", "prefill_tps", "decode_tps", "retrieval_ms", "bytes_read", "gbps",
                       "read_share", "context_tokens", "history_tokens", "peak_ram_gb", "disk_gb", "tier")
    assert Answer("x").metrics == {k: None for k in METRICS}
    assert metrics(tier="ssd", ttft_s=0.1)["tier"] == "ssd" and TIERS == ("ram", "ssd", "vault")
    with pytest.raises(ValueError):
        metrics(seconds=1.0)  # not a metric every contender reports
    with pytest.raises(ValueError):
        metrics(tier="disk")


def test_an_answer_gets_room_by_its_family():
    assert [max_tokens(f) for f in ("page", "code", "maths", "fact", "never", None)] == [1200, 600, 400, 120, 120, 120]


def test_a_moment_is_dated_as_the_ruler_dates_it():
    assert stamp("User: the oven is fixed.", dt.date(2025, 9, 22)) == "[2025-09-22] User: the oven is fixed."
    assert stamp("User: hi", dt.date(2025, 9, 22), 1) == "[2025-09-22, day 1] User: hi"


def test_a_short_run_still_sees_every_family():
    qs = [{"id": f"{f}{i}", "family": f} for f in ("fact", "maths", "page") for i in range(3)]
    assert [q["id"] for q in pick(qs, 4)] == ["fact0", "maths0", "page0", "fact1"]
    assert pick(qs, None) == qs and pick(qs, 50) == qs


def test_any_grader_shape_gives_right_verdict_and_reason():
    assert grade_with(lambda q, a: {"verdict": "right", "reason": "names it"}, {}, "x") == (True, "right", "names it")
    assert grade_with(lambda q, a: {"verdict": "stale", "right": False}, {}, "x")[:2] == (False, "stale")
    assert grade_with(lambda q, a: True, {}, "x") == (True, "right", None)
    assert grade_with(lambda q, a: "declined", {}, "x") == (False, "declined", None)
    assert grade_with(lambda q, a: 1 / 0, {}, "x")[:2] == (None, "grader_error")  # the answer is kept
    assert grade_with(None, {}, "x") == (None, None, None)


def test_a_record_is_named_by_date_time_task_and_contender(tmp_path):
    at = dt.datetime(2026, 11, 4, 3, 4, 5)
    assert record_path("longhaul", "engine:qwen3-1.7b", at, tmp_path) == (
        tmp_path / "2026-11-04" / "030405-longhaul-engine-qwen3-1.7b.json")


class Script(Contender):
    """Remembers what it is told, answers "yes" (or fails on one question), reports made-up metrics."""

    def __init__(self, fail_on: str | None = None):
        self.name, self.fail_on = "script:x", fail_on
        self.told: list[tuple[str, int]] = []
        self.asked: list[tuple[str, int, str | None]] = []
        self.opened: Path | None = None
        self.closed = False

    @property
    def moments(self) -> int:
        return len(self.told)

    def open(self, folder):
        self.opened = folder

    def tell(self, text, day):
        self.told.append((text, day))

    def ask(self, question, *, max_tokens, family=None):
        if question == self.fail_on:
            raise RuntimeError("out of memory")
        self.asked.append((question, max_tokens, family))
        return Answer("yes", metrics(ttft_s=0.05, total_s=0.2, retrieval_ms=1.5, context_tokens=100 + len(self.told),
                                     history_tokens=len(self.told), tier="ssd", bytes_read=4096),
                      {"told": len(self.told)})

    def close(self):
        self.closed = True

    def status(self):
        return {"told": len(self.told)}


def history(n: int) -> list[dict]:
    out, cum = [], 0
    for i in range(n):
        day = i // 5 + 1
        text = f"Day {day} · Monday 22 September 2025" if i % 5 == 0 else f"note {i}"
        cum += 10
        out.append({"i": i, "day": day, "kind": "day" if i % 5 == 0 else "chat",
                    "role": "system" if i % 5 == 0 else "user", "text": text, "tokens": 10, "cum_tokens": cum})
    return out


def test_the_runner_tells_asks_grades_and_saves_after_every_checkpoint(tmp_path):
    events = history(20)
    cps = [{"name": "A", "tokens": 80, "events": 8, "questions": [
               {"id": "q1", "question": "page?", "family": "page", "expected": "a page"},
               {"id": "q2", "question": "fact?", "family": "fact", "expected": "yes"}]},
           {"name": "B", "tokens": 200, "events": 20, "questions": [
               {"id": "q3", "question": "maths?", "family": "maths", "expected": "no"}]}]
    seen = []
    c = Script()

    def progress(msg):
        saved = sorted((tmp_path / "rec").rglob("*.json"))
        seen.append(len(json.loads(saved[-1].read_text())["checkpoints"]) if saved else 0)

    rec = run(c, events, cps, task="longhaul", folder=tmp_path / "mem", records=tmp_path / "rec",
              grader=lambda q, a: {"verdict": "right" if a == q["expected"] else "wrong"}, progress=progress)
    assert c.opened == tmp_path / "mem" and c.closed
    assert [d for _, d in c.told] == [e["day"] for e in events]
    assert c.told[1][0] == "User: note 1" and c.told[0][0] == "Day 1 · Monday 22 September 2025"
    assert [(q, m, f) for q, m, f in c.asked] == [("page?", 1200, "page"), ("fact?", 120, "fact"), ("maths?", 400,
                                                                                                   "maths")]
    assert seen == [1, 2]  # saved after every checkpoint
    path = Path(rec["path"])
    assert path.parent.name == dt.date.today().isoformat() and path.name.endswith("-longhaul-script-x.json")
    saved = json.loads(path.read_text())
    assert saved["thinking"] is False and saved["max_tokens"] == {"page": 1200, "code": 600, "maths": 400,
                                                                  "other": 120}
    assert saved["environment"] == {"machine": "test"} and saved["contender"] == {"name": "script:x"}
    a = saved["checkpoints"][0]
    assert a["ingest"]["events"] == 8 and a["ingest"]["tokens"] == 80 and a["status"] == {"told": 8}
    assert [x["verdict"] for x in a["answers"]] == ["wrong", "right"]
    assert set(a["answers"][0]["metrics"]) == set(METRICS)
    assert a["answers"][0]["extra"] == {"told": 8, "memory_tokens": 8}  # its own count, kept apart
    assert a["answers"][0]["metrics"]["history_tokens"] == 80  # the history told, as the task counts it
    assert set(a["summary"]) == {"page", "fact", "all"} and a["summary"]["all"]["right"] == 1
    assert a["summary"]["fact"]["retrieval_ms"]["p50"] == 1.5 and a["summary"]["all"]["tiers"] == {"ssd": 2}
    assert saved["checkpoints"][1]["ingest"]["events"] == 12
    assert saved["checkpoints"][1]["answers"][0]["metrics"]["history_tokens"] == 200
    assert all(x["asked_before"] is False and x["truncated"] is None for x in a["answers"])
    assert "history_tokens" in saved and "failed" not in saved


def test_a_failed_question_is_recorded_and_the_run_goes_on(tmp_path):
    cps = [{"name": "A", "events": 3, "questions": [{"id": "q1", "question": "boom", "family": "fact"},
                                                    {"id": "q2", "question": "fine", "family": "fact"}]}]
    rec = run(Script(fail_on="boom"), history(3), cps, task="t", folder=tmp_path, grader=lambda q, a: True,
              records=tmp_path / "rec", progress=lambda m: None)
    a, b = rec["checkpoints"][0]["answers"]
    assert a["verdict"] == "error" and "out of memory" in a["reason"] and a["right"] is None  # never graded
    assert a["metrics"] == {**metrics(), "history_tokens": 30}
    assert b["verdict"] == "right"
    s = rec["checkpoints"][0]["summary"]["all"]
    assert s["graded"] == 1 and s["right"] == 1 and s["errors"] == 1 and s["questions"] == 2


def test_a_summary_is_per_family_and_for_all():
    rows = [{"family": "fact", "right": True, "verdict": "right", "metrics": metrics(ttft_s=1.0, tier="ram")},
            {"family": "fact", "right": False, "verdict": "stale", "metrics": metrics(ttft_s=3.0, tier="vault")},
            {"family": "never", "right": True, "verdict": "right", "metrics": metrics(ttft_s=2.0)}]
    s = summarize(rows)
    assert s["fact"]["right"] == 1 and s["fact"]["verdicts"] == {"right": 1, "stale": 1}
    assert s["all"]["ttft_s"]["p50"] == 2.0 and s["all"]["tiers"] == {"ram": 1, "vault": 1, "None": 1}


def test_decode_speed_counts_the_tokens_written_after_the_first_word():
    assert decode_tps(6, 1.0, 0.75) == 20.0  # 5 tokens in 0.25 s; mlx_lm's own figure says 6 / 0.25 = 24
    assert decode_tps(1, 1.0, 0.5) is None and decode_tps(None, 1.0, 0.5) is None
    assert decode_tps(5, 0.5, 0.5) is None and decode_tps(5, None, 0.5) is None


def test_a_full_answer_is_marked_truncated_and_a_question_asked_again_is_flagged(tmp_path):
    class Long(Script):
        def ask(self, question, *, max_tokens, family=None):
            a = super().ask(question, max_tokens=max_tokens, family=family)
            a.extra["answer_tokens"] = max_tokens if family == "page" else 3  # the page used all its room
            return a

    page = {"id": "page-1", "question": "Build the page.", "family": "page"}
    cps = [{"name": "A", "events": 3, "questions": [page, {"id": "f1", "question": "fact?", "family": "fact"}]},
           {"name": "B", "events": 6, "questions": [page]}]
    rec = run(Long(), history(6), cps, task="t", folder=tmp_path, grader=lambda q, a: False,
              records=tmp_path / "rec", progress=lambda m: None)
    a, b = rec["checkpoints"]
    assert [x["truncated"] for x in a["answers"]] == [True, False] and a["summary"]["all"]["truncated"] == 1
    assert a["answers"][0]["right"] is False  # graded as it stands, and marked
    assert [x["asked_before"] for x in a["answers"]] == [False, False] and b["answers"][0]["asked_before"] is True
    assert b["summary"]["all"]["asked_before"] == 1 and b["summary"]["page"]["asked_before"] == 1


def test_a_failure_outside_a_question_is_saved_in_the_record(tmp_path):
    class Breaks(Script):
        def tell(self, text, day):
            if len(self.told) == 4:
                raise RuntimeError("Metal ran out")
            super().tell(text, day)

    cps = [{"name": "A", "events": 3, "questions": [{"id": "q", "question": "?", "family": "fact"}]},
           {"name": "B", "events": 6, "questions": []}]
    with pytest.raises(RuntimeError):
        run(Breaks(), history(6), cps, task="t", folder=tmp_path, grader=None, records=tmp_path / "rec",
            progress=lambda m: None)
    saved = json.loads(next((tmp_path / "rec").rglob("*.json")).read_text())
    assert saved["failed"]["checkpoint"] == "B" and saved["failed"]["stage"] == "tell"
    assert "Metal ran out" in saved["failed"]["error"] and len(saved["checkpoints"]) == 1  # A is kept
    c = Breaks()
    rec = run(c, history(6), cps, task="t", folder=tmp_path, grader=None, records=tmp_path / "rec2",
              progress=lambda m: None, raise_failure=False)
    assert rec["failed"]["checkpoint"] == "B" and c.closed


def test_reading_outside_tell_is_counted_as_the_checkpoints_ingest(tmp_path):
    class Reads(Script):
        def __init__(self):
            super().__init__()
            self.read, self.moved = 0.0, False

        def tell(self, text, day):
            super().tell(text, day)
            self.moved = True

        def ask(self, question, *, max_tokens, family=None):
            if self.moved:  # a window read before the first question
                self.read, self.moved = self.read + 2.0, False
            return super().ask(question, max_tokens=max_tokens, family=family)

        def reading_s(self):
            return self.read

    cps = [{"name": "A", "events": 4, "questions": [{"id": "a", "question": "?", "family": "fact"},
                                                    {"id": "b", "question": "?", "family": "fact"}]}]
    ing = run(Reads(), history(4), cps, task="t", folder=tmp_path, grader=None, records=tmp_path / "rec",
              progress=lambda m: None)["checkpoints"][0]["ingest"]
    assert ing["read_s"] == 2.0 and ing["seconds"] >= 2.0 and ing["tell_s"] < 1.0
    assert ing["events_per_s"] == pytest.approx(4 / ing["seconds"], rel=0.01) and ing["events_per_s"] < 2.1


def test_a_failed_question_at_a_speed_point_is_recorded_too():
    qs = [{"id": "a", "question": "boom", "family": "fact"}, {"id": "b", "question": "fine", "family": "fact"}]
    out = ask_all(Script(fail_on="boom"), qs, lambda q, a: True, history_tokens=500)
    assert [x["verdict"] for x in out] == ["error", "right"] and out[0]["right"] is None
    assert out[1]["metrics"]["history_tokens"] == 500 and out[1]["extra"]["memory_tokens"] == 0


# -- the local contenders by name


def test_contenders_are_named_kind_and_model():
    assert local.parse("engine:qwen3-1.7b") == ("engine", "qwen3-1.7b")
    assert local.parse("words:qwen-27b") == ("words", "qwen-27b") and local.parse("bare:qwen-27b")[0] == "bare"
    for bad in ("engine:qwen-27b", "cloud:qwen3-1.7b", "engine:llama-3", "qwen3-1.7b"):
        with pytest.raises(ValueError):
            local.parse(bad)
    assert local.MODELS["qwen3-4b"] == "mlx-community/Qwen3-4B-Instruct-2507-4bit"
    assert local.MODELS["qwen-27b"] == "mlx-community/Qwen3.8-27B-4bit"
    assert local.WINDOWS == {"qwen3-1.7b": 32_768, "qwen3-4b": 65_536, "qwen3-8b": 32_768, "qwen-27b": 16_384}


def test_making_a_contender_loads_nothing():
    class NoLoad(local.Loader):
        def reader(self, repo):
            raise AssertionError("loaded a model")

    b = local.make("bare:qwen3-4b", NoLoad())
    assert isinstance(b, local.Bare) and b.window == 65_536 and b.name == "bare:qwen3-4b"
    e = local.make("engine:qwen3-8b", NoLoad())
    assert isinstance(e, local.Engine) and e.repo == "mlx-community/Qwen3-8B-4bit"
    assert e.ram_bytes == 2 * 10**9 and e.disk_bytes == 40 * 10**9
    assert isinstance(local.make("words:qwen-27b", NoLoad()), local.Words)


CONFIGS = {  # as in each model's config.json
    "qwen3-1.7b": {"num_hidden_layers": 28, "num_key_value_heads": 8, "head_dim": 128, "hidden_size": 2048,
                   "num_attention_heads": 16, "rope_theta": 1000000},
    "qwen3-4b": {"num_hidden_layers": 36, "num_key_value_heads": 8, "head_dim": 128, "hidden_size": 2560,
                 "num_attention_heads": 32, "rope_theta": 5000000},
    "qwen3-8b": {"num_hidden_layers": 36, "num_key_value_heads": 8, "head_dim": 128, "hidden_size": 4096,
                 "num_attention_heads": 32, "rope_theta": 1000000},
}


def test_the_notes_shape_comes_from_each_models_config():
    got = {k: local.kv_shape(c).token_bytes for k, c in CONFIGS.items()}
    assert got == {"qwen3-1.7b": 114_688, "qwen3-4b": 147_456, "qwen3-8b": 147_456}  # 112 KB and 144 KB a token
    assert local.kv_shape(CONFIGS["qwen3-4b"]).rope_base == 5_000_000.0
    for key in CONFIGS:  # the real configs, when they are in the local cache
        config = local.config_of(local.MODELS[key])
        if config is not None:
            assert local.kv_shape(config) == local.kv_shape(CONFIGS[key])


def test_bare_reads_the_history_as_the_yardstick_does():
    claude = pytest.importorskip("engram.bench.claude")
    assert local.BARE_SYSTEM == claude.SYSTEM and local.OPENER == claude.OPENER
    lines = ["Day 1 · Monday 22 September 2025", "User: hi", "Assistant: hello"]
    msgs, _ = claude.Claude(client=object())._messages(lines, 0, 3, claude.Segments(), "</history>", cache=False)
    sent = "".join(block["text"] for block in msgs[0]["content"])
    ours = local.OPENER + "".join(x + local.JOIN_LINES for x in lines) + "</history>"
    assert sent == ours  # the window's words are the yardstick's, line for line


def test_memory_contenders_read_the_same_instructions_with_notes_for_the_history():
    orun = pytest.importorskip("engram.bench.ollama_run")
    from engram.memory import INTRO

    assert local.LONGHAUL_INTRO == orun.PAIRED_SYSTEM  # the words the Ollama pairing's paired contender reads

    class NoLoad(local.Loader):
        def reader(self, repo):
            raise AssertionError("loaded a model")

    e, w = local.haul_contender("engine:qwen3-1.7b", NoLoad()), local.haul_contender("words:qwen-27b", NoLoad())
    b = local.haul_contender("bare:qwen3-1.7b", NoLoad())
    assert e.intro == w.intro == local.LONGHAUL_INTRO and not e.learn and not e.watch
    for d in (e.describe(), w.describe()):
        assert d["system"] == local.LONGHAUL_INTRO and d["today_line"] is True and d["hint_in"].startswith("system")
    d = b.describe()
    assert d["system"] == local.BARE_SYSTEM and d["today_line"] is False and d["hint_in"].startswith("user")
    assert d["lines_joined_by"] == "\n\n"
    assert local.make("engine:qwen3-1.7b", NoLoad()).intro == INTRO  # the suites keep memory.INTRO
    assert local.haul_contender("engine:qwen3-8b", NoLoad(), learn=True, watch=True).learn is True


def test_the_command_line_takes_contenders_cuts_and_a_limit():
    a = local.parser().parse_args(["longhaul", "--contender", "engine:qwen3-1.7b", "--contender", "bare:qwen3-1.7b",
                                   "--dir", "/tmp/h", "--cuts", "64K", "1M", "--limit", "5"])
    assert a.contender == ["engine:qwen3-1.7b", "bare:qwen3-1.7b"] and a.cuts == ["64K", "1M"] and a.limit == 5
    s = local.parser().parse_args(["speed", "--contender", "engine:qwen3-1.7b"])
    assert s.marks == [1_000, 10_000, 100_000] and s.questions == 5 and s.dir == local.HAUL
    with pytest.raises(ValueError):
        local.main(["longhaul", "--contender", "engine:qwen-27b"])  # checked before any model is loaded


# -- bare, with a fake reader and fake caches


class Tok:
    """One token per character."""

    def apply_chat_template(self, msgs, add_generation_prompt=True, enable_thinking=None, tokenize=False, tools=None):
        assert enable_thinking is False
        return "".join(f"<{m['role']}>{m['content']}</{m['role']}>" for m in msgs) + "<assistant>"

    def encode(self, text):
        return [ord(c) for c in text]


def decode(ids) -> str:
    return "".join(chr(i) for i in ids)


class Cut:
    def __init__(self, n):
        self.offset = n

    def is_trimmable(self):
        return True

    def trim(self, n):
        self.offset -= n
        return n


class Running:
    """A linear-attention layer: a running state that cannot be cut, only put back."""

    def __init__(self):
        self.cache = ["read"]

    def is_trimmable(self):
        return False

    @property
    def state(self):
        return self.cache, None, None

    @state.setter
    def state(self, v):
        self.cache = v[0]


class BareReader:
    repo = "fake"

    def __init__(self):
        self.tok, self.read, self.calls = Tok(), [], []

    def new_cache(self, ids):
        self.read.append(list(ids))
        return [Cut(len(ids)), Running()]

    def generate(self, ids, cache=None, max_tokens=None):
        self.calls.append(SimpleNamespace(ids=list(ids), max_tokens=max_tokens, offset=cache[0].offset))
        cache[0].offset += len(ids) + 5  # the question and the answer go on the cache
        cache[1].cache.append("asked")
        return Reply("I don't know", 0.01, 50.0, len(ids), 5, [])


def test_bare_keeps_the_most_recent_window_and_reads_it_once_per_checkpoint():
    r = BareReader()
    b = local.Bare("fake", reader=r, window=30)
    b.open(Path("/nowhere"))
    for i in range(10):
        b.tell(f"line {i}", 1)  # 6 characters, 8 tokens with the blank line after it
    first = b.ask("what?", max_tokens=120, family="fact")
    assert len(r.read) == 1 and b.status()["prefill"]["lines"] == 3 and b.start == 7  # 3 lines fit in 30 tokens
    window = decode(r.read[0])
    assert "line 7\n\nline 8\n\nline 9\n\n</history>" in window and "line 6" not in window  # as Claude's
    assert window.startswith("<system>" + local.BARE_SYSTEM + "\n\n" + local.OPENER)
    head = len(r.read[0])
    b.ask("and now?", max_tokens=600, family="code")
    b.ask("again?", max_tokens=120)
    assert len(r.read) == 1  # the window was read once for every question
    assert all(c.offset == head for c in r.calls)  # each question is answered right after the window...
    assert b.cache[0].offset == head and b.cache[1].cache == ["read"]  # ...and cut off again, state put back
    q = decode(r.calls[1].ids)
    assert q.startswith("</system><user>and now?") and local.HINTS["code"] in q and "line" not in q  # only itself
    assert r.calls[1].max_tokens == 600
    m = first.metrics
    assert set(m) == set(METRICS) and m["context_tokens"] == head + len(r.calls[0].ids) and m["ttft_s"] == 0.01
    assert m["history_tokens"] == 80 and m["tier"] is None and m["retrieval_ms"] is None
    assert first.extra["window_tokens"] == head and b.reading_s() > 0  # the window's read, counted as ingest
    b.tell("line 10", 2)
    b.ask("what?", max_tokens=120)
    assert len(r.read) == 2 and "line 10" in decode(r.read[1]) and "line 7" not in decode(r.read[1])


def test_bare_puts_its_cache_back_when_an_answer_fails(monkeypatch):
    class Fails(BareReader):
        def generate(self, ids, cache=None, max_tokens=None):
            if not self.calls:  # the first answer runs out of memory halfway
                self.calls.append(None)
                cache[0].offset += len(ids) + 3
                cache[1].cache.append("half")
                raise RuntimeError("Metal: out of memory")
            return super().generate(ids, cache, max_tokens)

    r = Fails()
    b = local.Bare("fake", reader=r, window=30)
    b.open(Path("/nowhere"))
    for i in range(10):
        b.tell(f"line {i}", 1)
    with pytest.raises(RuntimeError):
        b.ask("Build the page.", max_tokens=1200, family="page")
    head = len(r.read[0])
    b.ask("what?", max_tokens=120)
    assert r.calls[-1].offset == head and len(r.read) == 1  # answered right after the window, not after the failure
    assert b.cache[1].cache == ["read"]

    def broken(cache, marks):
        raise RuntimeError("cannot cut")

    monkeypatch.setattr(local, "rewind", broken)
    b.ask("again?", max_tokens=120)
    assert b.cache is None  # a cache that cannot be put back is read again...
    monkeypatch.undo()
    b.ask("once more?", max_tokens=120)
    assert len(r.read) == 2 and r.calls[-1].offset == head  # ...before the next question


def test_a_real_cache_is_cut_back_and_a_running_state_put_back():
    mx = pytest.importorskip("mlx.core")
    from mlx_lm.models.cache import ArraysCache, KVCache

    kv, running = KVCache(), ArraysCache(size=2)
    kv.update_and_fetch(mx.zeros((1, 1, 5, 4)), mx.zeros((1, 1, 5, 4)))
    running[0] = mx.zeros((1, 2))
    marks = local._mark([kv, running])
    kv.update_and_fetch(mx.ones((1, 1, 3, 4)), mx.ones((1, 1, 3, 4)))
    running[0] = mx.ones((1, 2))
    local.rewind([kv, running], marks)
    assert kv.offset == 5 and float(running[0].sum()) == 0.0


# -- the engine and words, with test_core's fakes (MLX arrays, no model)


def fakes():
    pytest.importorskip("mlx")
    from test_core import FakeEmbedder, FakeReader

    return FakeReader(), FakeEmbedder()


def engine(**kw):
    reader, embedder = fakes()
    settings = {"log": False, "room_tokens": 400, "join": 0.2, "dates": dates, **kw}
    return local.Engine("fake", reader=reader, embedder=embedder, **settings)


def fake_text(ids) -> str:
    return "".join(chr(i - 1) for i in ids)  # test_core's FakeTok: ord(c) % 1000 + 1


def test_the_engine_keeps_dated_moments_in_one_project_reach(tmp_path):
    e = engine()
    e.open(tmp_path / "mem")
    e.tell("Day 1 · Monday 22 September 2025", 1)  # carried by every moment instead
    e.tell("User: Amina moved to Nakuru.", 1)
    e.tell("Assistant: Noted, Nakuru.", 1)
    assert e.moments == 2
    texts = [m.text for m in e.memory.rooms.moments]
    assert texts == ["[2025-09-22, day 1] User: Amina moved to Nakuru.",
                     "[2025-09-22, day 1] Assistant: Noted, Nakuru."]
    assert e.memory.path == tmp_path / "mem" / "project" / "longhaul"
    assert e.memory.core is not None and e.memory.tiers.disk_budget == 40 * 10**9
    assert e.memory.tiers.ram_budget == 2 * 10**9 and e.memory.vault is not None and e.memory.meter is not None
    note = e.memory.vault.get(e.memory.vault.moment_id(0))
    assert note.date == "2025-09-22" and note.day == 1
    a = e.ask("Where does Amina live?", max_tokens=120, family="fact")
    assert a.text == "ok" and set(a.metrics) == set(METRICS) and a.metrics["tier"] in TIERS
    assert a.metrics["history_tokens"] == sum(len(t) + 1 for t in texts)
    assert a.metrics["context_tokens"] > a.metrics["history_tokens"] and a.metrics["retrieval_ms"] is not None
    assert a.metrics["disk_gb"] > 0 and "fetch" in a.extra["retrieval_steps_ms"]
    prompt = fake_text(e.memory.reader.calls[-1].ids)
    assert "Nakuru" in prompt and "Today is Monday 22 September 2025." in prompt and local.HINTS["page"] not in prompt
    e.ask("Build the catering page.", max_tokens=1200, family="page")
    assert local.HINTS["page"] in fake_text(e.memory.reader.calls[-1].ids)  # the family's form, after the notes
    st = e.status()
    assert st["moments"] == 2 and st["vault_notes"] == 2 and st["asleep_rooms"] == 0
    assert e.describe()["moment"] == "[YYYY-MM-DD, day N] text" and e.describe()["enable_thinking"] is False
    e.close()
    assert (tmp_path / "mem" / "project" / "longhaul" / "index.json").exists()


def test_the_ruler_form_keeps_day_lines_as_moments(tmp_path):
    e = engine(day_numbers=False)
    e.open(tmp_path / "mem")
    e.tell("Day 1 · Monday 22 September 2025", 1)
    e.tell("User: hello", 1)
    assert [m.text for m in e.memory.rooms.moments] == ["[2025-09-22] Day 1 · Monday 22 September 2025",
                                                        "[2025-09-22] User: hello"]
    e.close()


def test_when_the_disk_budget_is_full_the_weakest_rooms_sleep_and_answer_from_words(tmp_path):
    reader, _ = fakes()
    tb = 2 * 2 * 1 * 4 * 2  # the fake model's notes: 2 layers, keys and values, 1 head of 4, 16 bits
    e = engine(disk_bytes=tb * 120, room_tokens=60, join=0.99)  # rooms of their own, about two awake at a time
    e.open(tmp_path / "mem")
    facts = ["User: the oven brand is Ramtons.", "User: the van plate is KDA 123X.", "User: the fridge is a Haier.",
             "User: the till is a Sunmi.", "User: the mixer is a Kenwood."]
    for day, f in enumerate(facts, start=1):
        e.tell(f, day)
    st = e.status()
    assert st["asleep_rooms"] >= 2 and st["disk_awake_bytes"] <= tb * 120
    a = e.ask("Which brand is the oven?", max_tokens=120, family="fact")
    assert a.metrics["tier"] == "vault" and a.extra["asleep"] is True and a.metrics["bytes_read"] == 0
    assert "Ramtons" in fake_text(e.memory.reader.calls[-1].ids)  # its room read as words
    e.close()


def test_the_engine_naps_once_a_working_week(tmp_path):
    e = engine(nap_days=5)
    e.open(tmp_path / "mem")
    for day in range(1, 13):
        e.tell(f"User: note for day {day}.", day)
    assert e.naps["count"] == 2  # on days 6 and 11
    e.close()


def test_the_engine_runs_through_the_runner(tmp_path):
    e = engine()
    events = [{"day": 1, "role": "user", "text": "Amina moved to Nakuru.", "tokens": 6},
              {"day": 1, "role": "assistant", "text": "Noted.", "tokens": 2}]
    cps = [{"name": "64K", "tokens": 8, "events": 2,
            "questions": [{"id": "q", "question": "Where does Amina live?", "family": "fact", "expected": "Nakuru"}]}]
    rec = run(e, events, cps, task="longhaul", folder=tmp_path / "mem", records=tmp_path / "rec",
              grader=lambda q, a: {"verdict": "wrong", "reason": "says ok"}, progress=lambda m: None)
    cp = rec["checkpoints"][0]
    assert cp["status"]["moments"] == 2 and cp["answers"][0]["metrics"]["tier"] in TIERS
    assert rec["contender"]["kv_shape"]["token_bytes"] == 32 and rec["contender"]["layers"][0] == "rooms"
    d = rec["contender"]
    assert d["core"].startswith("on, empty") and d["questions"].startswith("read-only") and "nap" in d["writes"]
    assert d["system"] == local.INTRO and d["watch"] is False and cp["status"]["core_tokens"] == 0
    assert "join_hits" in cp["status"] and "hits" not in cp["status"]
    assert cp["answers"][0]["metrics"]["history_tokens"] == 8 and cp["answers"][0]["extra"]["memory_tokens"] > 8


def tiers_now(e) -> tuple:
    t = e.memory.tiers
    return dict(t.used), t.tick, list(t.pool.hot), dict(t.pool.sizes), dict(t.hits)


FACTS = ["User: the oven brand is Ramtons.", "User: the van plate is KDA 123X.", "User: the fridge is a Haier."]


def test_the_engines_questions_leave_its_memory_as_the_telling_left_it(tmp_path):
    e = engine(room_tokens=60, join=0.99)  # a room for each fact
    e.open(tmp_path / "mem")
    for day, f in enumerate(FACTS, start=1):
        e.tell(f, day)
    e.memory.save()
    before = tiers_now(e)
    strengths = {n.id: n.strength for n in e.memory.vault.notes()}
    assert e.ask("Which brand is the oven?", max_tokens=120, family="fact").metrics["tier"] == "ssd"
    assert tiers_now(e) == before  # not kept hot, not counted as recently used, no hit counted
    assert e.ask("Which brand is the oven?", max_tokens=120, family="fact").metrics["tier"] == "ssd"
    assert {n.id: n.strength for n in e.memory.vault.notes()} == strengths
    e.close()
    e = engine(room_tokens=60, join=0.99, learn=True)  # as in the app: a question leaves its room hot
    e.open(tmp_path / "learns")
    for day, f in enumerate(FACTS, start=1):
        e.tell(f, day)
    tick = e.memory.tiers.tick
    assert e.ask("Which brand is the oven?", max_tokens=120, family="fact").metrics["tier"] == "ssd"
    assert e.ask("Which brand is the oven?", max_tokens=120, family="fact").metrics["tier"] == "ram"
    assert e.memory.tiers.tick == tick + 2 and e.describe()["questions"].startswith("learn")
    e.close()


class FakeLooks:
    """Every written word looks only at the first node on the desk."""

    def __init__(self, reader, header, spans, prompt_len, desk):
        self.nodes = sorted({n for n, _, _ in spans})

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return None

    def per_word(self, words):
        import numpy as np

        a = np.zeros((words, len(self.nodes)), dtype=np.float32)
        a[:, 0] = 1.0
        return a


def test_a_watched_answer_strengthens_what_it_used_only_when_the_engine_learns(tmp_path, monkeypatch):
    import engram.memory
    from engram.events import EventLog

    monkeypatch.setattr(engram.memory, "Looks", FakeLooks)
    for learn in (False, True):
        e = engine(log=True, watch=True, learn=learn)
        e.open(tmp_path / f"mem-{learn}")
        e.tell("User: Amina moved to Nakuru.", 1)
        e.tell("User: the van plate is KDA 123X.", 1)
        a = e.ask("Where does Amina live?", max_tokens=120, family="fact")
        last = [x for x in EventLog(e.folder / "events.jsonl").read() if x["type"] == "answer"][-1]
        top = max(n.strength for n in e.memory.vault.notes())
        assert last["used"] and "looks" in last and (top >= 2.0) is learn  # used either way; stronger only learning
        assert a.metrics["peak_ram_gb"] is None and "peak_ram_gb_watched" in a.extra  # the watch's keys are in it
        assert "use" not in vars(e.memory)
        e.close()


def test_an_unwatched_answer_is_still_logged_without_its_looks(tmp_path):
    from engram.events import EventLog

    e = engine(log=True)  # the fake reader is not Qwen3: a watched answer would fail
    e.open(tmp_path / "mem")
    e.tell("User: Amina moved to Nakuru.", 1)
    a = e.ask("Where does Amina live?", max_tokens=120, family="fact")
    events = EventLog(e.folder / "events.jsonl").read()
    assert [x["type"] for x in events] == ["remember", "answer"] and e.memory.log is not None
    last = events[-1]
    assert last["watched"] is False and "looks" not in last and last["room"] == 0 and last["words"] == ["o", "k"]
    assert last["tier"] in TIERS and last["family"] == "fact" and a.metrics["peak_ram_gb"] is not None
    e.close()


def test_the_engine_can_read_the_long_hauls_wording_and_memorys_own_is_unchanged(tmp_path):
    from engram.memory import INTRO, Memory

    reader, embedder = fakes()
    day = dt.date(2025, 10, 1)
    plain = Memory(reader, embedder, tmp_path / "a", log=False).prompt(day, "Where?", "Reply in a word.")
    ours = local._Memory(reader, embedder, tmp_path / "b", log=False).prompt(day, "Where?", "Reply in a word.")
    hauls = local._Memory(reader, embedder, tmp_path / "c", log=False, intro=local.LONGHAUL_INTRO).prompt(
        day, "Where?", "Reply in a word.")
    assert ours == plain  # with memory.INTRO, Memory's own prompt
    assert [fake_text(x) for x in hauls] == [fake_text(x).replace(INTRO, local.LONGHAUL_INTRO) for x in plain]
    e = engine(intro=local.LONGHAUL_INTRO)
    e.open(tmp_path / "mem")
    e.tell("User: Amina moved to Nakuru.", 1)
    e.ask("Build the catering page.", max_tokens=1200, family="page")
    header = fake_text(e.memory.notebook.header)  # read once, kept as notes: the instructions are in it
    assert local.LONGHAUL_INTRO in header and INTRO not in header
    assert local.HINTS["page"] in fake_text(e.memory.reader.calls[-1].ids)  # the family's line, after the notes
    e.close()


def test_an_engine_opened_again_lets_go_of_the_memory_before(tmp_path):
    e = engine()
    e.open(tmp_path / "a")
    first = e.memory
    e.tell("User: hello", 1)
    e.open(tmp_path / "b")
    assert e.memory is not first and e.moments == 0 and e.days.day is None
    assert (tmp_path / "a" / "project" / "longhaul" / "index.json").exists()  # saved when let go
    e.close()
    fd = local._hold(tmp_path / "b")
    with pytest.raises(RuntimeError):
        local._hold(tmp_path / "b")  # held as reach.Session holds a reach: one opener at a time
    import os

    os.close(fd)


def test_words_reads_the_engines_rooms_as_text(tmp_path):
    reader, embedder = fakes()
    w = local.Words("fake", reader=reader, embedder=embedder, counter=len, dates=dates)
    w.open(tmp_path / "words")
    w.tell("Day 1 · Monday 22 September 2025", 1)
    w.tell("User: Amina moved to Nakuru.", 1)
    w.tell("User: the van plate is KDA 123X.", 2)
    assert w.moments == 2 and w.status()["history_tokens"] == sum(
        len(m.text) + 1 for m in w.rooms.moments)
    a = w.ask("Where does Amina live?", max_tokens=120, family="fact")
    prompt = fake_text(reader.calls[-1].ids)
    assert "[2025-09-22, day 1] User: Amina moved to Nakuru." in prompt
    assert "Today is Tuesday 23 September 2025" in prompt
    assert a.metrics["tier"] == "vault" and a.metrics["bytes_read"] == 0 and a.metrics["retrieval_ms"] is not None
    assert a.metrics["context_tokens"] == len(reader.calls[-1].ids) and set(a.metrics) == set(METRICS)
    index = tmp_path / "words" / "rooms" / "index.json"
    assert index.exists() and (tmp_path / "words" / "rooms" / "vectors.npy").exists()  # saved before the question
    room_files = sum(f.stat().st_size for f in (tmp_path / "words" / "rooms").glob("room-*.notes"))
    assert a.metrics["disk_gb"] * 1e9 >= room_files + index.stat().st_size  # the whole folder, not just the rooms
    assert local.INTRO in prompt and "mlx_decode_tps" in a.extra
    w.close()


# -- speed points during one ingest


def tiny_haul(folder: Path, n: int = 30) -> Path:
    folder.mkdir(parents=True, exist_ok=True)
    events = history(n)
    (folder / "script.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    probes = [{"id": f"fact-{i}", "family": "fact", "ask": f"What does supplier {i} bring?", "answer": "cooking oil",
               "grader": {"type": "exact", "accept": ["cooking oil"]}, "ready_at": 150, "events": [1]}
              for i in range(3)]
    probes.append({"id": "maths-1", "family": "maths", "ask": "Fee on 7,321?", "answer": "75",
                   "grader": {"type": "number", "value": "75"}, "ready_at": 150, "events": [1]})
    (folder / "probes.jsonl").write_text("".join(json.dumps(p) + "\n" for p in probes))
    (folder / "manifest.json").write_text(json.dumps({"seed": 9, "version": 2, "tokens": n * 10, "events": n}))
    return folder


def test_speed_takes_a_point_at_each_mark_reached_and_at_the_end(tmp_path):
    haul = tiny_haul(tmp_path / "haul")
    c = Script()
    rec = local.speed(c, haul, memory=tmp_path / "mem", marks=(10, 20, 100), questions=2, records=tmp_path / "rec",
                      progress=lambda m: None)
    pts = rec["points"]
    assert [p["moments"] for p in pts] == [10, 20, 30] and [p["end"] for p in pts] == [False, False, True]
    assert rec["not_reached"] == [100] and c.closed
    assert pts[0]["ingest"]["events"] == 10 and pts[0]["ingest"]["events_per_s"] > 0
    assert pts[0]["answers"] == [] and len(pts[1]["answers"]) == 2  # nothing askable before its facts are told
    assert all(q[2] == "fact" for q in c.asked)  # short families only
    assert pts[1]["summary"]["retrieval_ms"]["p50"] == 1.5 and pts[1]["answers"][0]["verdict"] == "wrong"
    saved = json.loads(Path(rec["path"]).read_text())
    assert saved["kind"] == "speed" and len(saved["points"]) == 3 and saved["haul"]["seed"] == 9


def test_the_long_haul_goes_on_after_a_contender_fails(tmp_path, monkeypatch):
    class Breaks(Script):
        def tell(self, text, day):
            raise RuntimeError("Metal ran out")

    made = iter([Breaks(), Script()])

    def contender(spec, loader, **kw):
        c = next(made)
        c.name = spec
        return c

    monkeypatch.setattr(local, "haul_contender", contender)
    recs = local.longhaul(["bare:qwen3-1.7b", "bare:qwen3-4b"], tiny_haul(tmp_path / "haul"), cuts=["64K"],
                          memories=tmp_path / "mem", records=tmp_path / "rec", loader=object(),
                          progress=lambda m: None)
    assert recs[0]["failed"]["stage"] == "tell" and recs[0]["checkpoints"] == []
    assert "failed" not in recs[1] and len(recs[1]["checkpoints"][0]["answers"]) == 4
    assert {Path(r["path"]).name.split("-", 1)[1] for r in recs} == {"longhaul-bare-qwen3-1.7b.json",
                                                                     "longhaul-bare-qwen3-4b.json"}


def test_speed_questions_are_short_and_askable(tmp_path):
    from engram.bench.haul.script import load_probes

    probes = load_probes(tiny_haul(tmp_path / "haul"))
    assert local.speed_questions(probes, 100, 5) == []
    qs = local.speed_questions(probes, 160, 5)
    assert len(qs) == 3 and {q["family"] for q in qs} == {"fact"} and qs[0]["probe"]["cut"] == 160


def test_the_loader_loads_each_reader_once_and_warms_it_untimed(monkeypatch):
    import engram.models

    made = []

    class Reader:
        def __init__(self, repo, max_tokens):
            self.repo, self.calls = repo, []
            made.append(self)

        def chat_ids(self, system, user, tools=None):
            return [1, 2, 3]

        def generate(self, ids, cache=None, max_tokens=None):
            self.calls.append(max_tokens)
            return Reply("ok", 0.0, 0.0, 3, 1, [])

    monkeypatch.setattr(engram.models, "Reader", Reader)
    loader = local.Loader()
    a = loader.reader("one")
    assert loader.reader("one") is a and a.calls == [4] and "one" in loader.warm_s  # one short, untimed generation
    loader.reader("two")
    assert len(made) == 2 and list(loader.readers) == ["two"]  # the first reader was let go

"""The suite runner, against stand-in suites, a stand-in Claude and a stand-in Ollama: what each suite tells and asks,
a new memory per context, each reply limit, the record (failed contexts, stops, crashes and resuming), and Claude's
cost: estimated first, read from the ledger try by try, and never past the run's cap. The local contenders are
refused. No model is loaded, no dataset is read and nothing leaves this Mac."""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace as NS

import pytest
# no_real_ollama is an autouse fixture: imported here, it guards these tests too
from test_ollama_run import FakeOllama, no_real_ollama, words  # noqa: F401

from engram.bench import suite_run as sr
from engram.bench.claude import BudgetError, Call, ClaudeError
from engram.bench.contender import METRICS, Answer, Contender, metrics
from engram.bench.cost import Tokens, cost_usd
from engram.bench.ollama_run import OllamaBare
from engram.bench.suite_run import (CORRECTION, THINK_ROOM, Ask, ClaudeContender, Group, StopRun, estimate, noise,
                                    noise_pool, plan_aime, plan_babilong, plan_harp, plan_math500,
                                    plan_memoryagentbench, run)
from engram.bench.suites import aime, babilong, harp, math500
from engram.bench.suites import memoryagentbench as mab
from engram.bench.suites.common import Item, chunk

STORY = "Mary went to the kitchen. " + "The old house was quiet and the rain fell on the roof. " * 300


def story(i=0, length="4k", task="qa1"):
    return babilong._item(task, length, i, {"input": STORY, "question": "Where is Mary?", "target": "kitchen"})


def problem(uid, level, answer="5"):
    return math500._item({"unique_id": f"test/algebra/{uid}.json", "problem": f"Problem {uid}: find x.",
                          "answer": answer, "subject": "Algebra", "level": level, "solution": "x is 5"})


def harp_pair(k):
    a = {"id": f"2001/AMC/{k}", "problem": f"A{k}: what is 3+4?", "solution_1": "3 and 4 make 7.", "answer": "7",
         "subject": "algebra", "level": 2}
    b = {"id": f"2002/AMC/{k}", "problem": f"B{k}: what is 5+6?", "solution_1": "11.", "answer": "11",
         "subject": "algebra", "level": 2}
    return harp.pair(a, b)


def mab_item(row, q, chunks):
    return Item(id=f"mab/cr/{row:02d}/{q:03d}", suite=mab.NAME, context=chunks, question=f"Q{q} on row {row}?",
                answer=[f"answer {q}"], length_tokens=1000,
                meta={"split": "Conflict_Resolution", "source": "factconsolidation_sh_6k", "kind": "factconsolidation",
                      "row": row, "qa_pair_id": None, "instruction": mab.INSTRUCTIONS["factconsolidation"]})


# --- what each suite tells and asks


def test_babilong_tells_the_story_in_chunks_then_asks_without_the_context(monkeypatch):
    got = {}

    def sample(n, seed, tasks, lengths, store=None):
        got.update(n=n, seed=seed, tasks=list(tasks), lengths=list(lengths))
        return [story(0, "4k"), story(0, "16k")]

    monkeypatch.setattr(babilong, "sample", sample)
    groups = plan_babilong(3, 7, ["4k", "16k"], ["qa1"])
    assert got == {"n": 3, "seed": 7, "tasks": ["qa1"], "lengths": ["4k", "16k"]}
    g = groups[0]
    assert g.tells == chunk(STORY, sr.TELL_TOKENS) and len(g.tells) > 1 and "".join(g.tells) == STORY
    (a,) = g.asks
    assert "<context>" not in a.prompt and a.prompt.endswith("Question: Where is Mary?")
    assert a.family == "babilong" and a.limit == 120 and a.meta == {"task": "qa1", "length": "4k",
                                                                     "length_tokens": story().length_tokens}
    assert a.grade("The most recent location of Mary is kitchen.") == "right"
    assert a.grade("The most recent location of Mary is garden.") == "wrong"


def test_memoryagentbench_tells_each_contexts_chunks_once_then_asks_its_questions(monkeypatch):
    items = [mab_item(0, 0, ["c0a", "c0b"]), mab_item(0, 1, ["c0a", "c0b"]), mab_item(1, 0, ["c1a"])]
    monkeypatch.setattr(mab, "sample", lambda n, seed, splits, **kw: items)
    groups = plan_memoryagentbench(2)
    assert [g.id for g in groups] == ["mab/cr/00", "mab/cr/01"]
    assert groups[0].tells == ["c0a", "c0b"] and [a.id for a in groups[0].asks] == ["mab/cr/00/000", "mab/cr/00/001"]
    a = groups[0].asks[1]
    assert a.prompt.endswith("Question: Q1 on row 0?\nAnswer:") and a.limit == 120
    assert a.grade("Answer: answer 1") == "right" and a.grade("something else") == "wrong"


def test_math500_takes_levels_three_to_five_and_tells_nothing(monkeypatch):
    items = [problem(k, level) for k, level in enumerate([1, 2, 3, 4, 5] * 6)]
    monkeypatch.setattr(math500, "load", lambda path=None: items)
    groups = plan_math500(10, seed=0)
    assert len(groups) == 10 and all(g.tells == [] and len(g.asks) == 1 for g in groups)
    assert {g.asks[0].meta["level"] for g in groups} <= {3, 4, 5}
    assert [g.id for g in groups] == [g.id for g in plan_math500(10, seed=0)]  # fixed by the seed
    a = groups[0].asks[0]
    assert a.family == "math500" and a.limit == 400 and a.grade("so \\boxed{5}") == "right"


def test_aime_is_every_problem_of_both_years_by_default(monkeypatch):
    items = [Item(id=f"aime/{y}/{k:02d}", suite="aime", context="", question=f"P{k}", answer="70", length_tokens=5,
                  meta={"year": y, "number": k, "kind": [], "instruction": aime.INSTRUCTION})
             for y in (2025, 2026) for k in range(1, 4)]
    monkeypatch.setattr(aime, "load", lambda years, paths=None: [i for i in items if i.meta["year"] in years])
    groups = plan_aime()
    assert len(groups) == 6 and groups[0].asks[0].limit == 400 and groups[0].asks[0].meta == {"year": 2025}
    assert groups[0].asks[0].grade("\\boxed{070}") == "right"


def test_harp_tells_the_correction_and_the_noise_then_asks_b_and_a_again(monkeypatch):
    monkeypatch.setattr(harp, "sample", lambda n, seed, path=None: [harp_pair(k) for k in range(n)])
    pool = [(f"User: noise {k}", 1_000) for k in range(100)]
    groups = plan_harp(2, pool=pool)
    assert [g.id for g in groups] == ["harp/2001/AMC/0->2002/AMC/0#on", "harp/2001/AMC/0->2002/AMC/0#off",
                                      "harp/2001/AMC/1->2002/AMC/1#on", "harp/2001/AMC/1->2002/AMC/1#off"]
    on, off = groups[0], groups[1]
    assert on.tells[0].startswith(CORRECTION) and "3 and 4 make 7." in on.tells[0]
    assert len(on.tells) - 1 == 30 and all(t.startswith("User: noise") for t in on.tells[1:])  # 30K tokens
    assert off.tells == []
    b, a = on.asks
    assert (b.meta["ask"], a.meta["ask"]) == ("B", "A") and "B0: what is 5+6?" in b.prompt and "A0:" in a.prompt
    assert b.grade("\\boxed{11}") == "right" and a.grade("\\boxed{7}") == "right" and a.grade("\\boxed{11}") == "wrong"
    assert b.limit == a.limit == 400 and on.meta["mode"] == "on" and off.asks[0].meta["mode_ask"] == "off/B"


def test_noise_is_what_no_probe_needs_without_day_lines_or_the_maths_course(tmp_path):
    events = [{"i": 0, "day": 1, "kind": "day", "role": "system", "text": "Day 1 · Monday 22 September 2025"},
              {"i": 1, "day": 1, "kind": "chat", "role": "user", "text": "noise one"},
              {"i": 2, "day": 1, "kind": "chat", "role": "user", "text": "a planted fact"},
              {"i": 3, "day": 1, "kind": "maths", "role": "user", "text": "a worked example"},
              {"i": 4, "day": 1, "kind": "log", "role": "tool", "text": "a log line"}]
    for k, e in enumerate(events):
        e.update(tokens=10, cum_tokens=10 * (k + 1))
    (tmp_path / "script.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (tmp_path / "probes.jsonl").write_text(json.dumps({"id": "f1", "family": "fact", "event": 2, "events": [2]}) + "\n")
    pool = noise_pool(str(tmp_path))
    assert pool == (("User: noise one", 10), ("Tool: a log line", 10))
    assert len(noise(pool, 15, 0, "x")) == 2 and noise(pool, 0, 0, "x") == [] and noise((), 10, 0, "x") == []


# --- running


class Recorder(Contender):
    name = "recorder:none"

    def __init__(self, stop_at: int | None = None):
        self.log, self.stop_at, self.asks = [], stop_at, 0

    def open(self, folder):
        self.log.append(("open", Path(folder)))

    def tell(self, text, day):
        self.log.append(("tell", text, day))

    def ask(self, question, *, max_tokens, family=None):
        self.asks += 1
        if self.stop_at is not None and self.asks >= self.stop_at:
            raise StopRun("the budget")
        self.log.append(("ask", family, max_tokens))
        if family == "boom":
            raise RuntimeError("the model fell over")
        return Answer("The most recent location of Mary is kitchen.", metrics(ttft_s=0.2, tier="vault"), {"x": 1})

    def close(self):
        self.log.append(("close",))


def kitchen(reply):
    return "right" if "kitchen" in reply else "wrong"


def groups3():
    return [Group(f"g{k}", [f"told {k}a", f"told {k}b"], [Ask(f"q{k}", "Where?", "kitchen", "babilong", kitchen,
                                                              {"length": "4k" if k < 2 else "16k"})],
                  {"length": "4k" if k < 2 else "16k"})
            for k in range(3)]


def test_each_context_gets_a_new_memory_and_the_record_holds_everything(tmp_path):
    c = Recorder()
    gs = groups3() + [Group("g3", [], [Ask("q3", "Solve.", "5", "math500", lambda r: "wrong")])]
    rec = run("babilong", c, gs, settings={"n": 3}, records=tmp_path / "r", memories=tmp_path / "m",
              progress=lambda s: None)
    opens = [x[1] for x in c.log if x[0] == "open"]
    assert len(opens) == 4 and len(set(opens)) == 4 and opens[0].parent.name.endswith(".nosync")
    assert opens[0].parent.parent == tmp_path / "m" and c.log[-1] == ("close",)
    assert c.log[1:4] == [("tell", "told 0a", 0), ("tell", "told 0b", 0), ("ask", "babilong", 120)]
    assert ("ask", "math500", 400) in c.log
    saved = json.loads(Path(rec["path"]).read_text())
    assert saved["thinking"] is False and saved["environment"] and saved["settings"] == {"n": 3}
    assert saved["path"].endswith("-babilong-recorder-none.json") and len(saved["groups"]) == 4
    s = saved["summary"]
    assert s["babilong"]["right"] == 3 and s["math500"]["right"] == 0 and s["all"]["questions"] == 4
    assert s["by_length"]["4k"]["questions"] == 2 and s["by_length"]["16k"]["right"] == 1
    a = saved["groups"][0]["answers"][0]
    assert set(a["metrics"]) == set(METRICS) and a["extra"] == {"x": 1} and a["group"] == "g0" and a["length"] == "4k"


def test_a_failed_question_is_recorded_and_the_run_goes_on(tmp_path):
    gs = [Group("g0", [], [Ask("q0", "?", "x", "boom", kitchen)]), *groups3()[:1]]
    rec = run("babilong", Recorder(), gs, records=tmp_path, memories=tmp_path, progress=lambda s: None)
    first, second = (g["answers"][0] for g in rec["groups"])
    assert first["verdict"] == "error" and "fell over" in first["reason"] and second["verdict"] == "right"


def test_a_budget_stop_ends_the_run_and_the_record_says_so(tmp_path):
    rec = run("babilong", Recorder(stop_at=2), groups3(), records=tmp_path, memories=tmp_path,
              progress=lambda s: None)
    assert rec["stopped"] == "the budget" and sum(len(g["answers"]) for g in rec["groups"]) == 1
    assert len(rec["groups"]) == 2 and json.loads(Path(rec["path"]).read_text())["stopped"] == "the budget"


def test_bare_ollama_end_to_end_on_a_babilong_story(tmp_path, monkeypatch):
    monkeypatch.setattr(babilong, "sample", lambda n, seed, tasks, lengths, store=None: [story()])
    fake = FakeOllama(reply=lambda req: "The most recent location of Mary is kitchen.")
    c = OllamaBare("qwen3:1.7b", ollama=fake.address, count=words)
    rec = run("babilong", c, plan_babilong(1, lengths=["4k"]), records=tmp_path, memories=tmp_path,
              progress=lambda s: None)
    (a,) = rec["groups"][0]["answers"]
    assert a["verdict"] == "right" and a["max_tokens"] == 120 and a["metrics"]["decode_tps"] == 100.0
    system, user = fake.chats()[-1]["messages"]
    assert system["content"].startswith("<context>\nMary went to the kitchen.")
    assert user["content"].endswith("Question: Where is Mary?") and fake.chats()[-1]["think"] is False
    assert rec["contender"]["kind"] == "ollama-bare" and rec["thinking"] is False


# --- Claude


class FakeClaude:
    """Counts by characters and answers at once; keeps every call."""

    def __init__(self, reply="\\boxed{5}", output=50, window=1_000_000, margin=10_000, budget_error=False):
        self.reply, self.output, self.window, self.margin = reply, output, window, margin
        self.budget_error = budget_error
        self.calls, self.counts = [], []
        self.ledger = NS(path=Path("/nowhere/claude-ledger.jsonl"))

    def count(self, model, messages, purpose, *, system=None, output_config=None):
        text = "".join(b["text"] for m in messages for b in m["content"])
        self.counts.append(len(text))
        return len(text) // 4

    def call(self, model, messages, *, max_tokens, purpose, system=None, output_config=None, prompt_tokens=None,
             cache=True):
        self.calls.append({"model": model, "messages": messages, "max_tokens": max_tokens, "purpose": purpose,
                           "system": system, "prompt_tokens": prompt_tokens, "cache": cache})
        if self.budget_error:
            raise BudgetError("the night's cap")
        t = Tokens(input=prompt_tokens, output=self.output, thinking=20)
        return Call(model=model, answered_by=model, text=self.reply, stop_reason="end_turn", refusal_category=None,
                    tokens=t, cost_usd=cost_usd(model, t), estimate_usd=0.01, ttft_s=0.5, first_token_s=0.2,
                    total_s=1.0)


def claude(fake, model="claude-haiku-5-5", **kw):
    return ClaudeContender(model, claude=fake, count=words, task="test", **kw)


def test_claude_answers_a_short_prompt_in_one_call_with_room_to_think(tmp_path):
    fake = FakeClaude()
    c = claude(fake)
    c.open(tmp_path)
    a = c.ask("Solve 2+3. Put your final answer in \\boxed{}.", max_tokens=400, family="math500")
    assert fake.counts == [] and len(fake.calls) == 1  # one request: a short prompt is sized from its characters
    call = fake.calls[0]
    assert call["max_tokens"] == 400 + THINK_ROOM and call["cache"] is False and call["system"] is None
    assert call["messages"] == [{"role": "user", "content": [{"type": "text", "text":
                                                               "Solve 2+3. Put your final answer in \\boxed{}."}]}]
    assert set(a.metrics) == set(METRICS) and a.metrics["context_tokens"] == call["prompt_tokens"]
    assert a.text == "\\boxed{5}" and a.extra["cost_usd"] > 0 and a.extra["thinking_tokens"] == 20
    assert c.spent == pytest.approx(a.extra["cost_usd"], abs=1e-6) and c.describe()["thinking"] == "adaptive"


def test_a_history_asked_more_than_once_is_marked_for_the_cache(tmp_path):
    fake = FakeClaude()
    c = claude(fake)
    c.open(tmp_path)
    c.expect(3)
    c.tell("fact one", 0)
    c.tell("fact two", 0)
    c.ask("Which fact?", max_tokens=120)
    block, question = fake.calls[0]["messages"][0]["content"]
    assert block == {"type": "text", "text": "<context>\nfact one\nfact two\n</context>\n\n",
                     "cache_control": {"type": "ephemeral"}}
    assert question == {"type": "text", "text": "Which fact?"} and fake.calls[0]["cache"] is True
    c.open(tmp_path)
    c.tell("fact three", 0)
    c.ask("Which fact?", max_tokens=120)
    assert "cache_control" not in fake.calls[1]["messages"][0]["content"][0]  # asked once: no cache write


def test_a_history_too_long_for_the_window_keeps_its_most_recent_part(tmp_path):
    fake = FakeClaude(window=3_000, margin=100)
    c = claude(fake, think_room=0)
    c.open(tmp_path)
    for k in range(40):
        c.tell(f"event {k:02d} " + "x" * 390, 0)
    a = c.ask("What happened last?", max_tokens=120)
    assert fake.counts and a.extra["cut_from_front"] is True
    text = fake.calls[0]["messages"][0]["content"][0]["text"]
    assert "event 39" in text and "event 00" not in text
    assert fake.calls[0]["prompt_tokens"] <= 3_000 - 120 - 100


def test_claude_never_passes_the_runs_cap_or_the_nights(tmp_path):
    fake = FakeClaude()
    c = claude(fake, "claude-opus-5-5", max_usd=0.01)
    c.open(tmp_path)
    with pytest.raises(StopRun, match="would pass this run's"):
        c.ask("Solve.", max_tokens=400)
    assert fake.calls == []  # not sent
    c = claude(FakeClaude(budget_error=True))
    c.open(tmp_path)
    with pytest.raises(StopRun, match="ledger"):
        c.ask("Solve.", max_tokens=400)


def test_a_claude_run_stops_before_a_call_that_could_pass_its_cap(tmp_path):
    fake = FakeClaude(output=8_000)  # $0.004 a call on Haiku; the worst case of a call is about $0.0043
    c = claude(fake, max_usd=0.006)
    gs = [Group(f"g{k}", [], [Ask(f"q{k}", "Solve.", "5", "math500", lambda r: "right")]) for k in range(3)]
    rec = run("math500", c, gs, records=tmp_path, memories=tmp_path, progress=lambda s: None)
    assert len(fake.calls) == 1 and "would pass" in rec["stopped"] and rec["thinking"] == "adaptive"
    assert rec["contender"]["spent_usd"] <= 0.006


def test_the_estimate_reads_a_cached_history_once():
    hist = ["x" * 3_500] * 10  # about 10K tokens
    asks = [Ask(f"q{k}", "Which?", "a", "memoryagentbench", kitchen) for k in range(3)]
    shared = estimate([Group("g", hist, asks)], "claude-sonnet-5-5")
    alone = estimate([Group(f"g{k}", hist, [a]) for k, a in enumerate(asks)], "claude-sonnet-5-5")
    assert shared["calls"] == alone["calls"] == 3
    assert shared["expected_usd"] < alone["expected_usd"] <= alone["worst_usd"]


def test_the_command_line_prints_claudes_estimate_and_refuses_a_run_over_its_cap(monkeypatch, capsys):
    gs = [Group(f"g{k}", [], [Ask(f"q{k}", "Solve.", "5", "math500", kitchen)]) for k in range(50)]
    monkeypatch.setattr(sr, "plan_math500", lambda n, seed, levels: gs)

    def never(*a, **k):
        raise AssertionError("no contender may be made")

    monkeypatch.setattr(sr, "make_contender", never)
    assert sr.main(["math500", "--contender", "claude-opus-5-5", "--estimate"]) == 0
    out = capsys.readouterr().out
    assert "math500: 50 contexts, 50 questions" in out and "estimate for claude-opus-5-5: $" in out
    assert sr.main(["math500", "--contender", "claude-opus-5-5", "--max-usd", "0.01"]) == 2
    assert "not started" in capsys.readouterr().err


def test_contenders_by_name():
    assert isinstance(sr.make_contender("ollama-bare:qwen3:1.7b"), OllamaBare)
    assert isinstance(sr.make_contender("claude-haiku-5-5", claude=FakeClaude()), ClaudeContender)
    with pytest.raises(ValueError):
        sr.make_contender("claude-gpt")
    with pytest.raises(ValueError, match="no contender"):
        sr.make_contender("lmstudio:qwen3")
    assert sr.main(["babilong", "--contender", "engine:qwen9", "--estimate"]) == 2
    assert sr.main(["webdev", "--contender", "ollama:qwen3-1.7b"]) == 2


def test_the_local_contenders_are_refused_until_they_take_a_suites_wording(monkeypatch, capsys):
    from engram.bench import local

    def never(*a, **k):
        raise AssertionError("no local model may be made")

    monkeypatch.setattr(local, "make", never)
    for name in ("engine:qwen3-1.7b", "words:qwen-27b", "bare:qwen3-8b"):
        with pytest.raises(ValueError, match="Long Haul's wording"):
            sr.make_contender(name)
        assert sr.main(["math500", "--contender", name, "--estimate"]) == 2
        assert "not run on the suites yet" in capsys.readouterr().err


def test_each_contender_records_the_wording_it_read(tmp_path):
    from test_ollama_run import FakeOllama as Fake

    c = claude(FakeClaude())
    d = c.describe()
    assert d["system"] is None and d["frame"]["opener"] == "<context>\n" and "no system prompt" in d["prompt"]
    fake = Fake()
    b = OllamaBare("qwen3:1.7b", ollama=fake.address, count=words)
    d = b.describe()
    assert d["system"] is None and d["frame"]["closer"] == "\n</context>" and d["hint_in"].startswith("user")


# --- failures, stops and resuming


class Flaky(Recorder):
    """Fails to open (or to tell) the contexts named."""

    def __init__(self, bad_open=(), bad_tell=()):
        super().__init__()
        self.bad_open, self.bad_tell, self.now = set(bad_open), set(bad_tell), None

    def open(self, folder):
        self.now = Path(folder).name
        super().open(folder)
        if self.now in self.bad_open:
            raise ConnectionError("Ollama is not answering")

    def tell(self, text, day):
        if self.now in self.bad_tell:
            raise RuntimeError("the embedder fell over")
        super().tell(text, day)


def five():
    return [Group(f"g{k}", [f"told {k}"], [Ask(f"q{k}", "Where?", "kitchen", "babilong", kitchen,
                                               {"length": "4k"})], {"length": "4k"}) for k in range(5)]


def test_a_context_that_fails_to_open_or_be_told_is_recorded_and_the_run_goes_on(tmp_path):
    rec = run("babilong", Flaky(bad_open={"g1"}, bad_tell={"g3"}), five(), records=tmp_path, memories=tmp_path,
              progress=lambda s: None)
    saved = json.loads(Path(rec["path"]).read_text())
    assert saved["planned_groups"] == 5 and [g["outcome"] for g in saved["groups"]] == ["ok", "error", "ok", "error",
                                                                                         "ok"]
    g1, g3 = saved["groups"][1], saved["groups"][3]
    assert g1["stage"] == "open" and "not answering" in g1["error"] and g1["answers"] == []
    assert g3["stage"] == "tell" and "embedder" in g3["error"]
    assert saved["summary"]["all"]["questions"] == 3 and saved["failed_groups"] == 2
    assert saved["complete"] is False and "stopped" not in saved


def test_three_failed_contexts_in_a_row_stop_the_run(tmp_path):
    rec = run("babilong", Flaky(bad_open={"g1", "g2", "g3"}), five(), records=tmp_path, memories=tmp_path,
              progress=lambda s: None)
    assert len(rec["groups"]) == 4 and "3 contexts in a row" in rec["stopped"] and rec["complete"] is False


def test_a_crash_leaves_a_record_that_says_it_is_not_complete(tmp_path):
    class Boom(Recorder):
        def ask(self, question, *, max_tokens, family=None):
            if self.asks == 2:
                raise KeyboardInterrupt
            return super().ask(question, max_tokens=max_tokens, family=family)

    c = Boom()
    with pytest.raises(KeyboardInterrupt):
        run("babilong", c, five(), records=tmp_path / "r", memories=tmp_path, progress=lambda s: None)
    (path,) = (tmp_path / "r").rglob("*.json")
    saved = json.loads(path.read_text())
    assert saved["planned_groups"] == 5 and len(saved["groups"]) == 2 and saved["complete"] is False
    assert c.log[-1] == ("close",)


def test_a_full_run_is_complete(tmp_path):
    rec = run("babilong", Recorder(), five(), records=tmp_path, memories=tmp_path, progress=lambda s: None)
    assert rec["complete"] is True and rec["planned_groups"] == 5 and rec["failed_groups"] == 0


def test_resuming_runs_only_what_is_left_and_adds_it_to_the_same_record(tmp_path):
    first = run("babilong", Flaky(bad_open={"g1"}), five()[:4], records=tmp_path / "r", memories=tmp_path / "m",
                progress=lambda s: None)
    assert first["complete"] is False
    again = Recorder()
    old = json.loads(Path(first["path"]).read_text())
    rec = run("babilong", again, five(), records=tmp_path / "r", memories=tmp_path / "m", progress=lambda s: None,
              resume=old)
    opened = [x[1].name for x in again.log if x[0] == "open"]
    assert opened == ["g1", "g4"]  # g1 failed and g4 never ran; the rest are kept
    assert rec["path"] == first["path"] and rec["complete"] is True and rec["planned_groups"] == 5
    assert [g["id"] for g in rec["groups"]] == ["g0", "g2", "g3", "g1", "g4"]
    assert rec["summary"]["all"]["questions"] == 5 and len(rec["resumes"]) == 1
    assert rec["resumes"][0]["kept_groups"] == 3 and rec["resumes"][0]["folder"] != rec["folder"]


def test_the_command_line_resumes_only_the_same_run(tmp_path, monkeypatch, capsys):
    gs = [Group(f"g{k}", [], [Ask(f"q{k}", "Solve.", "5", "math500", kitchen)]) for k in range(3)]
    monkeypatch.setattr(sr, "plan_math500", lambda n, seed, levels: gs)
    rec = run("math500", Flaky(bad_open={"g2"}), gs, settings={"n": 3, "seed": 0, "levels": [3, 4, 5]},
              records=tmp_path, memories=tmp_path, progress=lambda s: None)
    rec["contender"]["name"] = "ollama-bare:qwen3:1.7b"
    Path(rec["path"]).write_text(json.dumps(rec))
    made = []
    monkeypatch.setattr(sr, "make_contender", lambda name, **kw: made.append(name) or Recorder())
    monkeypatch.setattr(sr, "run", lambda *a, **k: {**k["resume"], "summary": {"all": {}}, "contender": {},
                                                    "complete": True})
    args = ["math500", "--contender", "ollama-bare:qwen3-1.7b", "--n", "3", "--resume", rec["path"]]
    assert sr.main(args) == 0 and made == ["ollama-bare:qwen3-1.7b"]
    assert "1 to run" in capsys.readouterr().out
    assert sr.main(["math500", "--contender", "ollama:qwen3-1.7b", "--n", "3", "--resume", rec["path"]]) == 2
    assert "ollama-bare:qwen3:1.7b's" in capsys.readouterr().err
    assert sr.main(["math500", "--contender", "ollama-bare:qwen3-1.7b", "--n", "2", "--resume", rec["path"]]) == 2
    assert "plan" in capsys.readouterr().err


# --- Claude's spend, every try counted


class LedgerClaude(FakeClaude):
    """A stand-in Claude with a ledger: each try is a line, and the first ``fail`` tries break after billing
    ``partial`` dollars, as a stream that drops mid-way does."""

    def __init__(self, fail=0, partial=0.004, **kw):
        super().__init__(**kw)
        self.fail, self.partial, self.patience, self.lines_ = fail, partial, 4, []
        self.ledger = NS(path=Path("/nowhere/claude-ledger.jsonl"), lines=lambda: list(self.lines_))
        self.sleep = lambda s: None

    def call(self, model, messages, *, max_tokens, purpose, **kw):
        assert self.patience == 0  # the contender sends every try itself
        if self.fail:
            self.fail -= 1
            self.calls.append({"model": model, "purpose": purpose, "failed": True})
            self.lines_.append({"kind": "call", "purpose": purpose, "status": "connection", "cost_usd": self.partial})
            raise ClaudeError("the stream broke", "connection", retryable=True, wait_s=0.0)
        out = super().call(model, messages, max_tokens=max_tokens, purpose=purpose, **kw)
        self.lines_.append({"kind": "call", "purpose": purpose, "status": "ok",
                            "cost_usd": cost_usd(model, out.tokens)})
        self.lines_.append({"kind": "call", "purpose": "someone else's run", "cost_usd": 5.0})
        return out


def test_a_failed_try_counts_against_the_runs_cap_and_the_next_try_is_not_sent(tmp_path):
    fake = LedgerClaude(fail=1, partial=0.004)
    c = claude(fake, max_usd=0.006)
    c.open(tmp_path)
    with pytest.raises(StopRun, match="would pass this run's"):
        c.ask("Solve.", max_tokens=400)  # $0.004 billed by the broken try + a $0.0043 worst case > $0.006
    assert len(fake.calls) == 1 and c.spent == pytest.approx(0.004) and fake.patience == 4


def test_a_retried_call_is_paid_for_in_full_from_the_ledger(tmp_path):
    fake = LedgerClaude(fail=2, partial=0.001)
    c = claude(fake, max_usd=1.0)
    c.open(tmp_path)
    a = c.ask("Solve.", max_tokens=400)
    assert a.text == "\\boxed{5}" and len(fake.calls) == 3 and c.tries == 3
    assert c.spent == pytest.approx(0.002 + a.extra["cost_usd"], abs=1e-6)  # never someone else's lines
    assert c.describe()["spent_from"] == "ledger" and c.describe()["tries"] == 3


def test_a_claude_call_that_never_retries_is_raised(tmp_path):
    class Refused(LedgerClaude):
        def call(self, model, messages, **kw):
            raise ClaudeError("bad request", "http_400")

    c = claude(Refused(), max_usd=1.0)
    c.open(tmp_path)
    with pytest.raises(ClaudeError):
        c.ask("Solve.", max_tokens=400)


# --- what the summary counts


def test_a_reply_cut_off_by_its_limit_is_counted_as_truncated(tmp_path, monkeypatch):
    from test_ollama_run import FakeOllama as Fake

    monkeypatch.setattr(babilong, "sample", lambda n, seed, tasks, lengths, store=None: [story()])
    fake = Fake(reply=lambda req: "The most recent location of Mary is")
    fake.done_reason = "length"
    c = OllamaBare("qwen3:1.7b", ollama=fake.address, count=words)
    rec = run("babilong", c, plan_babilong(1, lengths=["4k"]), records=tmp_path, memories=tmp_path,
              progress=lambda s: None)
    assert rec["groups"][0]["answers"][0]["truncated"] is True and rec["summary"]["all"]["truncated"] == 1
    assert sr.truncated({"stop_reason": "max_tokens"}, 120) is True
    assert sr.truncated({"stop_reason": "end_turn"}, 120) is False
    assert sr.truncated({"answer_tokens": 120}, 120) is True and sr.truncated({}, 120) is None


def test_babilongs_shared_score_takes_only_the_lengths_every_contender_runs(tmp_path):
    gs = [Group(f"g{k}", ["told"], [Ask(f"q{k}", "Where?", "kitchen", "babilong",
                                       kitchen if length != "1M" else (lambda r: "wrong"), {"length": length})],
                {"length": length})
          for k, length in enumerate(["4k", "128k", "512k", "1M"])]
    rec = run("babilong", Recorder(), gs, records=tmp_path, memories=tmp_path, progress=lambda s: None)
    s = rec["summary"]
    assert s["lengths"] == ["4k", "128k", "512k", "1M"] and s["all"]["questions"] == 4 and s["all"]["right"] == 3
    assert s["shared"]["lengths"] == ["4k", "16k", "64k", "128k"]
    assert s["shared"]["questions"] == 2 and s["shared"]["right"] == 2


def test_a_failed_question_is_never_graded(tmp_path):
    gs = [Group("g0", [], [Ask("q0", "?", "x", "boom", kitchen)])]
    (a,) = run("babilong", Recorder(), gs, records=tmp_path, memories=tmp_path, progress=lambda s: None)["groups"][0][
        "answers"]
    assert a["verdict"] == "error" and a["right"] is None and a["truncated"] is None


def test_bare_ollamas_suite_answers_read_only_the_question_and_the_story_is_ingest(tmp_path, monkeypatch):
    from test_ollama_run import FakeOllama as Fake

    monkeypatch.setattr(babilong, "sample", lambda n, seed, tasks, lengths, store=None: [story()])
    fake = Fake(reply=lambda req: "The most recent location of Mary is kitchen.")
    c = OllamaBare("qwen3:1.7b", ollama=fake.address, count=words)
    rec = run("babilong", c, plan_babilong(1, lengths=["4k"]), records=tmp_path, memories=tmp_path,
              progress=lambda s: None)
    g = rec["groups"][0]
    (a,) = g["answers"]
    assert a["extra"]["window_read_tokens"] > 1_000 and a["extra"]["prompt_eval_count"] < 50
    assert a["extra"]["paid_window_read"] is False and "read_s" in g and c.reading_s() > 0


def test_the_command_line_prints_babilongs_shared_score_and_each_length(tmp_path, monkeypatch, capsys):
    from test_ollama_run import FakeOllama as Fake

    monkeypatch.setattr(babilong, "sample", lambda n, seed, tasks, lengths, store=None:
                        [story(0, length) for length in lengths])
    fake = Fake(reply=lambda req: "The most recent location of Mary is kitchen.")
    monkeypatch.setattr(sr, "make_contender",
                        lambda name, **kw: OllamaBare("qwen3:1.7b", ollama=fake.address, count=words))
    rc = sr.main(["babilong", "--contender", "ollama-bare:qwen3:1.7b", "--n", "1", "--tasks", "qa1", "--lengths",
                  "4k", "16k", "--records", str(tmp_path / "r"), "--memories", str(tmp_path / "m")])
    out = capsys.readouterr().out
    assert rc == 0 and "all (4k, 16k): right 2/2 graded of 2" in out and "shared (4k-128k" in out
    assert "  4k: right 1/1" in out and "  16k: right 1/1" in out and "not complete" not in out
    saved = json.loads(Path(out.strip().splitlines()[-1]).read_text())
    assert saved["complete"] is True and saved["planned_groups"] == 2 and saved["summary"]["shared"]["right"] == 2

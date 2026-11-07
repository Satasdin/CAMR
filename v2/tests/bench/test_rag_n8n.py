"""The n8n RAG contender without n8n, Qdrant, Ollama or Docker: the chunker and the prompt (the Python reference and,
with node, the very JavaScript the workflows' Code nodes run), the workflow JSON, the answer's metrics, and a whole
run against a stand-in webhook writing a record of the same shape as CAMR's."""

from __future__ import annotations

import datetime as dt
import json
import shutil
import subprocess
from pathlib import Path

import pytest

from camr_engine.bench import contender as bc
from camr_engine.bench.contender import METRICS
from camr_engine.bench.rag_n8n import build, pipeline, runner, stack

NODE = shutil.which("node")


def ev(i, text, day=1, tokens=None, date="2025-09-22"):
    e = {"i": i, "date": date, "day": day, "text": text}
    if tokens is not None:
        e["tokens"] = tokens
    return e


EVENTS = [ev(0, "User: The matatu route is 145.", tokens=20),
          ev(1, "Assistant: Noted.", tokens=12),
          ev(2, "User: " + "word " * 900 + "\nsecond line " * 40, day=2, date="2025-09-23", tokens=1400),
          ev(3, "User: oven fixed by Juma.", day=3, date="2025-09-24"),  # no count: estimated
          ev(4, "Assistant: " + "x" * 3000, day=3, date="2025-09-24")]  # one long word, no count


# -- the chunker -------------------------------------------------------------------------------------------------


def test_chunks_pack_in_order_and_respect_the_limit():
    chunks = pipeline.chunk_events(EVENTS, 512)
    assert all(c["tokens"] <= 512 for c in chunks)
    assert chunks[0]["text"].startswith("[2025-09-22, day 1] User: The matatu route is 145.\n[2025-09-22, day 1] "
                                        "Assistant: Noted.")
    assert chunks[0]["event_ids"][:2] == [0, 1]
    ids = [c["id"] for c in chunks]
    assert ids == sorted(ids) and len(set(ids)) == len(ids)
    told = [i for c in chunks for i in c["event_ids"]]
    assert sorted(set(told)) == [0, 1, 2, 3, 4]


def test_a_long_event_is_cut_and_every_part_keeps_its_date():
    parts = pipeline.pieces(EVENTS[2], 512)
    assert len(parts) >= 3
    assert all(p["text"].startswith("[2025-09-23, day 2] ") for p in parts)
    assert all(p["tokens"] <= 512 for p in parts)
    assert [p["part"] for p in parts] == list(range(len(parts)))
    body = "".join(p["text"][len("[2025-09-23, day 2] "):] for p in parts)
    assert body.replace(" ", "").replace("\n", "") == EVENTS[2]["text"].replace(" ", "").replace("\n", "")
    hard = pipeline.pieces(EVENTS[4], 512)  # no space or newline to cut at: cut anywhere
    assert len(hard) > 1 and all(p["tokens"] <= 512 for p in hard)


def test_point_ids_are_event_and_part():
    chunks = pipeline.chunk_events([ev(7, "a", tokens=5), ev(9, "b " * 2000, tokens=1200)], 512)
    assert chunks[0]["id"] == 7 * pipeline.PART_STRIDE
    assert chunks[1]["id"] == 9 * pipeline.PART_STRIDE  # part 0 of event 9 did not fit after event 7
    assert chunks[2]["id"] == 9 * pipeline.PART_STRIDE + 1
    assert chunks[0]["event_ids"] == [7] and chunks[2]["event_ids"] == [9]


def test_estimate_is_used_only_without_a_count():
    assert pipeline.pieces(ev(0, "abcdefg", tokens=99), 512)[0]["tokens"] == 99
    assert pipeline.pieces(ev(0, "abcdefg"), 512)[0]["tokens"] == pipeline.estimate_tokens("[2025-09-22, day 1] abcdefg")


# -- choosing and the prompt -------------------------------------------------------------------------------------


HITS = [{"id": 640, "score": 0.9, "payload": {"tokens": 500, "text": "[d] late"}},
        {"id": 64, "score": 0.8, "payload": {"tokens": 300, "text": "[d] early"}},
        {"id": 128, "score": 0.7, "payload": {"tokens": 200, "text": "[d] middle"}},
        {"id": 192, "score": 0.6, "payload": {"tokens": 10, "text": "[d] tiny"}}]


def test_select_keeps_the_closest_that_fit_then_puts_them_in_date_order():
    sel = pipeline.select_chunks(HITS, 8, 720)
    assert [h["id"] for h in sel["picked"]] == [128, 192, 640]  # 500 + 200 + 10; 300 did not fit after 500
    assert sel["tokens"] == 710
    assert [h["id"] for h in pipeline.select_chunks(HITS, 8, 720, "score")["picked"]] == [640, 128, 192]
    assert [h["id"] for h in pipeline.select_chunks(HITS, 2, 10_000)["picked"]] == [64, 640]  # k caps the hits


def test_prompt_is_camrs_with_the_notes_as_words():
    notes = pipeline.notes_text(pipeline.select_chunks(HITS, 2, 10_000)["picked"])
    assert notes == "[d] early\n[d] late\n"
    got = pipeline.system_prompt("INTRO", notes, "Monday 22 September 2025", "Reply with code.")
    assert got == ("INTRO\n\nNotes:\n[d] early\n[d] late\nEnd of notes.\nToday is Monday 22 September 2025."
                   "\n\nReply with code.")
    assert pipeline.system_prompt("I", "", None, "") == "I\n\nNotes:\nEnd of notes."


def test_prompt_matches_the_local_rag_contenders_format():
    from camr_engine.bench.local import LONGHAUL_INTRO
    from camr_engine.memory import _SLOT, today_text

    today = today_text(dt.date(2025, 9, 22))
    local = f"{LONGHAUL_INTRO}\n\nNotes:\n{_SLOT}End of notes.\nToday is {today}." + "\n\nhint"
    assert pipeline.system_prompt(LONGHAUL_INTRO, "N\n", today, "hint") == local.replace(_SLOT, "N\n")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
def test_the_workflows_javascript_gives_the_same_as_python():
    big = [ev(i, f"User: event {i} " + ("lorem ipsum " * (i * 37 % 300)) + ("\nline" * (i % 5)), day=1 + i // 7,
              tokens=None if i % 3 else 10 + (i * 53) % 900) for i in range(60)] + EVENTS
    for i, e in enumerate(big):
        e["i"] = i
    case = {"events": big, "hits": HITS}
    script = build.JS.read_text() + """
const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));
const out = {};
for (const limit of [128, 512]) out['chunks' + limit] = chunkEvents(input.events, limit);
out.sel = selectChunks(input.hits, 8, 720, 'date').picked.map(h => h.id);
out.selScore = selectChunks(input.hits, 3, 520, 'score').picked.map(h => h.id);
out.prompt = systemPrompt('I', notesText(selectChunks(input.hits, 8, 720, 'date').picked), 'Monday', 'then');
out.noDate = systemPrompt('I', '', null, '');
process.stdout.write(JSON.stringify(out));
"""
    p = subprocess.run([NODE, "-e", script], input=json.dumps(case), capture_output=True, text=True, timeout=30)
    assert p.returncode == 0, p.stderr
    js = json.loads(p.stdout)
    for limit in (128, 512):
        assert js[f"chunks{limit}"] == pipeline.chunk_events(big, limit)
    assert js["sel"] == [h["id"] for h in pipeline.select_chunks(HITS, 8, 720, "date")["picked"]]
    assert js["selScore"] == [h["id"] for h in pipeline.select_chunks(HITS, 3, 520, "score")["picked"]]
    assert js["prompt"] == pipeline.system_prompt("I", pipeline.notes_text(
        pipeline.select_chunks(HITS, 8, 720)["picked"]), "Monday", "then")
    assert js["noDate"] == pipeline.system_prompt("I", "", None, "")


# -- the workflow JSON -------------------------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["ingest", "ask"])
def test_workflow_json_is_a_valid_n8n_workflow_and_matches_the_builder(name):
    path = build.WORKFLOWS / f"{name}.json"
    wf = json.loads(path.read_text())
    assert path.read_text() == build.render(getattr(build, name)()), "run: python -m camr_engine.bench.rag_n8n build"
    spec = build.INGEST if name == "ingest" else build.ASK
    assert wf["id"] == spec["id"] and len(wf["id"]) == 16 and wf["id"].isalnum()
    names = [n["name"] for n in wf["nodes"]]
    assert len(set(names)) == len(names)
    allowed = {"n8n-nodes-base.webhook", "n8n-nodes-base.code", "n8n-nodes-base.httpRequest",
               "n8n-nodes-base.respondToWebhook"}
    assert {n["type"] for n in wf["nodes"]} <= allowed
    for src, conn in wf["connections"].items():
        assert src in names
        for branch in conn["main"]:
            assert all(c["node"] in names for c in branch)
    # one straight line from the webhook to the response
    order, at = ["Webhook"], "Webhook"
    while at in wf["connections"]:
        at = wf["connections"][at]["main"][0][0]["node"]
        order.append(at)
    assert order == names and order[-1] == "Respond to Webhook"
    hook = wf["nodes"][0]
    assert hook["parameters"] == {"httpMethod": "POST", "path": spec["path"], "responseMode": "responseNode",
                                  "options": {}}
    assert hook["webhookId"]
    for n in wf["nodes"]:
        if n["type"] == "n8n-nodes-base.httpRequest":
            url = n["parameters"]["url"]
            assert url.lstrip("=").startswith((build.OLLAMA_URL, build.QDRANT_URL))
            assert n["parameters"]["jsonBody"].startswith("={{") and n["parameters"]["jsonBody"].endswith("}}")


@pytest.mark.skipif(NODE is None, reason="node is not installed")
@pytest.mark.parametrize("name", ["ingest", "ask"])
def test_every_code_node_is_valid_javascript(name, tmp_path):
    wf = json.loads((build.WORKFLOWS / f"{name}.json").read_text())
    for n in wf["nodes"]:
        if n["type"] != "n8n-nodes-base.code":
            continue
        f = tmp_path / "node.js"
        f.write_text("async function n8nCode($input, $) {\n" + n["parameters"]["jsCode"] + "\n}\n")
        p = subprocess.run([NODE, "--check", str(f)], capture_output=True, text=True, timeout=30)
        assert p.returncode == 0, f"{n['name']}: {p.stderr}"


def test_ask_defaults_carry_camrs_budget_and_model():
    wf = json.loads((build.WORKFLOWS / "ask.json").read_text())
    read = next(n for n in wf["nodes"] if n["name"] == "Read question")["parameters"]["jsCode"]
    defaults = json.loads(read.split("const DEFAULTS = ", 1)[1].split(";\n", 1)[0])
    assert defaults["budget"] == build.BUDGET and defaults["k"] == build.K
    assert defaults["chat_model"] == "qwen3:4b-instruct-2507-q4_K_M"
    assert defaults["embed_model"] == "qwen3-embedding:0.6b"
    assert "think: false" in next(n for n in wf["nodes"] if n["name"] == "Build prompt")["parameters"]["jsCode"]


# -- an answer's metrics -----------------------------------------------------------------------------------------


REPLY = {"answer": "</think>\n\nRoute 145.", "thinking": "", "memory_tokens": 700, "hits": 8, "done_reason": "stop",
         "system": "S", "chunks": [{"id": 64, "score": 0.7}],
         "timings": {"embed_ms": 40, "search_ms": 20, "retrieval_ms": 60, "generate_ms": 500, "total_ms": 560,
                     "prompt_eval_count": 800, "prompt_eval_duration": 400_000_000, "eval_count": 11,
                     "eval_duration": 200_000_000, "load_duration": 5_000_000, "total_duration": 610_000_000}}


def test_answer_metrics_come_from_the_wall_time_and_ollamas_own_numbers():
    a = runner.answer_from(REPLY, 0.7, prompt_tokens=840, history_tokens=2_000_000, peak_bytes=6_500_000_000,
                           disk_bytes=12_000_000)
    assert a.text == "Route 145."
    m = a.metrics
    assert set(m) == set(METRICS)
    assert m["ttft_s"] == pytest.approx(0.5)  # 0.7 s on the wall less 0.2 s writing
    assert m["total_s"] == 0.7
    assert m["prefill_tps"] == 2000.0  # 800 tokens in 0.4 s
    assert m["decode_tps"] == pytest.approx(50.0)  # 10 tokens after the first in 0.2 s
    assert m["retrieval_ms"] == 60 and m["context_tokens"] == 840 and m["history_tokens"] == 2_000_000
    assert m["peak_ram_gb"] == 6.5 and m["disk_gb"] == 0.012 and m["tier"] == "vault"
    assert a.extra["memory_in_view"] == 700 and a.extra["memory_notes"] == 0 and a.extra["answer_tokens"] == 11
    assert a.extra["overhead_ms"] == pytest.approx(30.0)  # 700 - 610 - 60


def test_strip_think():
    assert runner.strip_think("</think>\n\nYes.") == "Yes."
    assert runner.strip_think("Plain.") == "Plain."
    assert runner.strip_think("<think>\nreal thought</think>x") == "<think>\nreal thought</think>x"


def test_docker_sizes():
    assert stack.parse_size("123.4MiB / 7.6GiB") == int(123.4 * 2**20)
    assert stack.parse_size("1.5GB") == 1_500_000_000
    assert stack.parse_size("nothing") is None


# -- a whole run against a stand-in webhook ----------------------------------------------------------------------


class FakeWebhooks:
    """The two webhooks, in memory: ingest runs the Python chunker, ask picks by word overlap."""

    def __init__(self):
        self.chunks: list[dict] = []
        self.calls: list[tuple[str, dict]] = []

    def __call__(self, path: str, body: dict) -> dict:
        self.calls.append((path, body))
        if path == build.INGEST["path"]:
            new = pipeline.chunk_events(body["events"], body["chunk_tokens"])
            self.chunks += new
            return {"ok": True, "events": len(body["events"]), "chunks": len(new),
                    "timings": {"chunk_embed_ms": 5, "upsert_ms": 1}}
        q = set(body["question"].lower().split())
        hits = sorted(({"id": c["id"], "score": len(q & set(c["text"].lower().split())), "payload": c}
                       for c in self.chunks), key=lambda h: -h["score"])
        sel = pipeline.select_chunks(hits, body["k"], body["budget"], body["order"])
        system = pipeline.system_prompt("INTRO", pipeline.notes_text(sel["picked"]), body["today"], body["then"])
        words = [w.strip(".,") for w in hits[0]["payload"]["text"].split()] if hits else []  # the closest chunk
        answer = next((w for w in words if w.isdigit()), "I don't know")
        return {**REPLY, "answer": answer, "system": system, "memory_tokens": sel["tokens"]}


class FakePrompts:
    how = "words"

    def count(self, text):
        return len(text.split())

    def prompt_tokens(self, system, question):
        return len(system.split()) + len(question.split()) + 5


@pytest.fixture
def offline(monkeypatch, tmp_path):
    monkeypatch.setattr(stack, "WORK", tmp_path / "n8n")
    monkeypatch.setattr(stack, "drop_collection", lambda name: None)
    monkeypatch.setattr(stack, "collection_info", lambda name: {"points_count": 1})
    monkeypatch.setattr(stack, "ensure_collection", lambda name, dim: True)
    monkeypatch.setattr(stack, "embed_dim", lambda: 1024)
    monkeypatch.setattr(stack, "count", lambda name: 3)
    monkeypatch.setattr(stack, "n8n_version", lambda: "test")
    monkeypatch.setattr(stack, "qdrant_version", lambda: "test")
    monkeypatch.setattr(runner, "_ollama_version", lambda: "test")
    monkeypatch.setattr(bc, "environment", lambda: {"machine": "test"})
    return tmp_path


def history():
    lines = ["Day 1 · Monday 22 September 2025", "User: The matatu route is 145.", "Assistant: Noted.",
             "Day 2 · Tuesday 23 September 2025", "User: The oven costs 9000 shillings."]
    days = [1, 1, 1, 2, 2]
    events = [{"i": i, "day": d, "role": "system" if t.startswith("Day") else "user", "text": t.split(": ", 1)[-1],
               "tokens": len(t.split())} for i, (t, d) in enumerate(zip(lines, days))]
    cum = 0
    for e in events:
        cum += e["tokens"]
        e["cum_tokens"] = cum
    qs = [{"id": "fact-1", "question": "Which matatu route?", "expected": "145", "family": "fact"},
          {"id": "fact-2", "question": "What does the oven cost?", "expected": "9000", "family": "fact"}]
    cps = [{"name": "64K", "tokens": events[2]["cum_tokens"], "events": 3, "questions": qs[:1]},
           {"name": "256K", "tokens": cum, "events": 5, "questions": qs}]
    return events, cps


def grade(q, text):
    return {"verdict": "right" if q["expected"] in text else "wrong", "right": q["expected"] in text}


def make(tmp, hooks, **kw):
    return runner.N8nRag(haul={"seed": 2, "script_sha": "abc123"}, post=hooks, prompts=FakePrompts(),
                         dates=lambda d: dt.date(2025, 9, 21) + dt.timedelta(days=d), state_dir=tmp / "state",
                         progress=lambda s: None, **kw)


def test_a_run_writes_a_record_shaped_like_camrs(offline):
    hooks = FakeWebhooks()
    events, cps = history()
    rec = bc.run(make(offline, hooks), events, cps, task="longhaul", grader=grade, folder=offline / "f",
                 records=offline / "records", progress=lambda s: None, meta={"haul": {"seed": 2}, "cuts": ["64K", "256K"]})
    assert "failed" not in rec
    assert Path(rec["path"]).name.endswith("-longhaul-n8n-rag-qwen3-4b.json")
    assert set(rec) >= {"kind", "task", "contender", "thinking", "max_tokens", "limit", "folder", "started",
                        "environment", "history_tokens", "haul", "cuts", "checkpoints", "finished", "path"}
    assert rec["contender"]["name"] == "n8n-rag:qwen3-4b" and rec["contender"]["budget_tokens"] == build.BUDGET
    a, b = rec["checkpoints"]
    assert set(a) == {"name", "tokens", "events", "ingest", "status", "footprint_gb", "summary", "answers"}
    assert a["summary"]["all"]["right"] == 1 and b["summary"]["all"]["right"] == 2
    ans = b["answers"][1]
    assert set(ans["metrics"]) == set(METRICS) and ans["metrics"]["history_tokens"] == cps[1]["tokens"]
    assert ans["extra"]["memory_in_view"] is not None and ans["max_tokens"] == 120
    assert b["status"]["points"] == 3 and "disk_gb" in b["status"]
    # day lines are never sent; every other event once, each line dated, the cut closing a batch
    sent = [e for path, body in hooks.calls if path == build.INGEST["path"] for e in body["events"]]
    assert [e["i"] for e in sent] == [1, 2, 4]
    assert sent[2]["date"] == "2025-09-23" and sent[2]["day"] == 2 and sent[2]["text"] == "User: The oven costs 9000 shillings."
    asks = [body for path, body in hooks.calls if path == build.ASK["path"]]
    assert asks[0]["today"] == "Monday 22 September 2025" and asks[-1]["today"] == "Tuesday 23 September 2025"
    assert all(x["k"] == build.K and x["budget"] == build.BUDGET for x in asks)


def test_a_second_run_resumes_and_sends_nothing_again(offline):
    events, cps = history()
    first = FakeWebhooks()
    bc.run(make(offline, first), events, cps, task="longhaul", grader=grade, folder=offline / "f",
           records=offline / "records", progress=lambda s: None)
    again = FakeWebhooks()
    again.chunks = first.chunks
    rec = bc.run(make(offline, again, budget=4096, k=16), events, cps, task="longhaul", grader=grade,
                 folder=offline / "f", records=offline / "records", progress=lambda s: None)
    assert not [c for c in again.calls if c[0] == build.INGEST["path"]]
    assert rec["contender"]["name"] == "n8n-rag:qwen3-4b[budget=4096,k=16]"
    runner.fix_ingest(rec)
    ing = rec["checkpoints"][1]["ingest"]
    assert ing["resumed"] is True and ing["skipped_events"] == 2 and ing["tokens_per_s"] is None
    # a fresh run drops the state and sends everything again
    fresh = FakeWebhooks()
    bc.run(make(offline, fresh, fresh=True), events, cps, task="longhaul", grader=grade, folder=offline / "f",
           records=offline / "records", progress=lambda s: None)
    assert len([c for c in fresh.calls if c[0] == build.INGEST["path"]]) == 2


def test_the_locked_exam_is_refused():
    with pytest.raises(SystemExit):
        runner.longhaul(Path("../work/haul/s1-16m"), ["2M"])


def test_collection_name_carries_the_history():
    assert runner.collection_name({"seed": 2, "script_sha": "0123456789abcdef"}) == "longhaul_s2_0123456789_c512"

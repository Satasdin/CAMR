"""The Bench screen: the evidence read from dated records, whatever has arrived so far. Every record here is a small
sample made in a temporary folder in the shapes the runners write (the Long Haul's local and Claude records, a
Hugging Face suite, the speed tests, the throughput test, the ruler's lives and errands, the WebDev history and the
Claude ledger). No model is loaded, no browser is started and nothing reaches the network: the headless browser is a
fake that writes a PNG."""

from __future__ import annotations

import base64
import http.client
import json
import os
import re
import shutil
import socket
import subprocess
import threading
from pathlib import Path

import pytest

from engram.app.routes import bench
from engram.app.server import STATIC, make_server
from engram.app.web import Refused

PNG_1X1 = base64.b64decode("iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=")
REAL_RUNNING = bench.running
PAGE = ("Here it is.\n\n```html\n<!doctype html><html><body><nav><a>Home</a></nav><h1>Catering</h1>"
        "<footer>© 2026</footer></body></html>\n```")


class App:
    """A stand-in app: the records and the screenshots live in temporary folders."""

    def __init__(self, root: Path, shots: Path):
        self.bench_root, self.bench_shots = root, shots

    def state(self) -> dict:
        return {}


def answer(qid: str, verdict: str, family: str | None = None, text: str = "x", **metrics) -> dict:
    a = {"id": qid, "question": f"q {qid}?", "expected": "y", "answer": text, "verdict": verdict,
         "right": None if verdict == "error" else verdict in ("right", "right_abstain"), "reason": f"why {qid}",
         "metrics": {"ttft_s": 0.1, "decode_tps": 200.0, "retrieval_ms": 25.0, "gbps": 6.0, "peak_ram_gb": 4.0,
                     **metrics}}
    if family:
        a["family"] = family
    return a


def spread(p50, p90=None) -> dict:
    return {"p50": p50, "p90": p90 if p90 is not None else p50}


def local_record(name: str, kind: str, cuts: dict[str, list[dict]], started: str, *, window=None, limit=None) -> dict:
    con = {"name": name, "kind": kind, "model": name.split(":", 1)[1]}
    if window:
        con["window"] = window
    cps = []
    for cut, answers in cuts.items():
        cps.append({"name": cut, "tokens": bench.CUTS[cut] - 140, "events": 551,
                    "status": {"moments": 544, "rooms": 237, "awake_rooms": 230, "asleep_rooms": 7, "hot_rooms": 55,
                               "vault_notes": 544, "folder_bytes": 8_445_219_920, "disk_gb": 8.44,
                               "naps": {"count": 1, "faded_notes": 3, "slept_rooms": 7}},
                    "summary": {"all": {"ttft_s": spread(0.13, 3.4), "decode_tps": spread(210.2),
                                        "prefill_tps": spread(4239.3), "retrieval_ms": spread(28.7, 30.9),
                                        "gbps": spread(6.9, 8.7), "context_tokens": spread(842.0),
                                        "peak_ram_gb": 10.11, "disk_gb": 8.445}},
                    "answers": answers})
    return {"kind": "bench", "task": "longhaul", "contender": con, "limit": limit, "started": started,
            "finished": started, "folder": str(Path.home() / "work" / "memories" / "x.nosync"),
            "environment": {"chip": "Apple M5 Pro", "memory_gb": 24, "power": "AC Power"}, "checkpoints": cps}


def claude_record(model: str, cuts: dict[str, list[dict]], started: str, cost: float) -> dict:
    cps = []
    for cut, answers in cuts.items():
        for a in answers:  # Claude's records name each answer by qid, with no family
            a["qid"] = a.pop("id")
            a.pop("family", None)
            a.pop("metrics", None)
        cps.append({"checkpoint": cut, "context_tokens": 93611, "history_tokens_told_est": 91879,
                    "request": {"ttft_s": 2.2, "output_tps": 380.9, "cost_usd": cost / len(cuts),
                                "request_id": "req_secretish"},
                    "summary": {"cost_usd": cost / len(cuts)}, "answers": answers})
    return {"kind": "claude-yardstick", "task": "longhaul", "model": model, "window": 1_000_000, "started": started,
            "finished": started, "checkpoints": cps, "cost_usd": cost, "environment": {"anthropic": "2.4.0"}}


def write(root: Path, rel: str, data) -> Path:
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data))
    return p


@pytest.fixture(autouse=True)
def no_processes(monkeypatch):
    """Whatever runs on this Mac while the tests do, the board sees no benchmark process."""
    monkeypatch.setattr(bench, "running", lambda: None)


@pytest.fixture
def records(tmp_path, monkeypatch):
    """A records folder with one of everything, as the runners leave it."""
    monkeypatch.setenv("ENGRAM_MEASURING", str(tmp_path / "measuring.json"))
    root = tmp_path / "records"
    day = "bench/2026-11-04"
    # the engine: a smoke run at 64K, then a fuller run at 64K and 256K
    write(root, f"{day}/024421-longhaul-engine-qwen3-1.7b.json", local_record(
        "engine:qwen3-1.7b", "engine", {"64K": [answer("fact-1", "right", "fact")]}, "2026-11-04T02:44:21", limit=5))
    write(root, f"{day}/031000-longhaul-engine-qwen3-1.7b.json", local_record(
        "engine:qwen3-1.7b", "engine",
        {"64K": [answer("fact-1", "right", "fact"), answer("fact-2", "wrong", "fact"),
                 answer("hop-01", "right", "two_hop"), answer("page-catering", "wrong", "page", PAGE),
                 answer("never-1", "false_memory", "never"), answer("never-2", "right", "never"),
                 answer("code-1", "error", "code")],
         "256K": [answer("changed-1", "stale", "changed"), answer("maths-1", "right", "maths")]},
        "2026-11-04T03:10:00"))
    write(root, f"{day}/024526-longhaul-bare-qwen3-1.7b.json", local_record(
        "bare:qwen3-1.7b", "bare", {"64K": [answer("fact-1", "wrong", "fact"), answer("never-1", "false_memory")]},
        "2026-11-04T02:45:26", window=32768))
    write(root, f"{day}/022518-claude-claude-haiku-5-5-longhaul.json", claude_record(
        "claude-haiku-5-5", {"64K": [answer("fact-1", "right"), answer("hop-02", "declined"),
                                     answer("page-catering", "declined", text="I don't know")],
                             "2M": [answer("fact-3", "declined"), answer("lookalike-1", "right")]},
        "2026-11-04T02:25:18", 1.13))
    write(root, f"{day}/025217-babilong-ollama-bare-qwen3-1.7b.json", {
        "kind": "suite", "task": "babilong", "started": "2026-11-04T02:52:17",
        "contender": {"name": "ollama-bare:qwen3:1.7b", "kind": "ollama-bare", "window": 32768},
        "groups": [{"id": "g1", "answers": [answer("b1", "right", "babilong") | {"length": "4k"},
                                            answer("b2", "wrong", "babilong") | {"length": "4k"}]}],
        "summary": {"all": {}, "by_length": {"4k": {"history_tokens": 4103, "ttft_s": spread(2.4)}}}})
    write(root, f"{day}/040000-speed-engine-qwen3-1.7b.json", {
        "kind": "speed", "task": "speed", "started": "2026-11-04T04:00:00",
        "contender": {"name": "engine:qwen3-1.7b", "kind": "engine"},
        "points": [{"moments": 1000, "history_tokens": 120_000, "disk_gb": 2.1,
                    "status": {"folder_bytes": 2_100_000_000, "awake_rooms": 90, "asleep_rooms": 0, "hot_rooms": 20},
                    "summary": {"ttft_s": spread(0.08), "retrieval_ms": spread(22.0, 31.0), "gbps": spread(5.5),
                                "decode_tps": spread(215.0), "context_tokens": spread(800.0)},
                    "answers": [answer("fact-9", "right", "fact")]},
                   {"moments": 10000, "history_tokens": 1_200_000, "disk_gb": 21.0,
                    "status": {"folder_bytes": 21_000_000_000, "awake_rooms": 800, "asleep_rooms": 40,
                               "hot_rooms": 20},
                    "summary": {"ttft_s": spread(0.09), "retrieval_ms": spread(35.0, 48.0), "gbps": spread(6.1),
                                "decode_tps": spread(212.0), "context_tokens": spread(810.0)},
                    "answers": [answer("fact-10", "wrong", "fact")]}]})
    write(root, "bench/throughput-2026-11-04-0123.json", {
        "kind": "throughput", "write_tokens": 128, "environment": {"memory_gb": 24},
        "mlx": {"qwen3-1.7b": {"repo": "mlx-community/Qwen3-1.7B-4bit", "points": [
                    {"tokens": 512, "first_word_s": 0.083, "read_tok_s": 6172.2, "write_tok_s": 219.6, "peak_gb": 1.71},
                    {"tokens": 32768, "first_word_s": 10.3, "read_tok_s": 3172.9, "write_tok_s": 56.0,
                     "peak_gb": 5.33}]},
                "qwen-27b": {"repo": "mlx-community/Qwen3.8-27B-4bit", "points": [
                    {"tokens": 512, "first_word_s": 1.42, "write_tok_s": 17.6, "peak_gb": 16.4},
                    {"tokens": 32768, "error": "out of GPU memory"}]}},
        "ollama": {"qwen3-1.7b": {"name": "qwen3:1.7b", "points": [
                    {"tokens": 512, "first_word_s": 0.75, "write_tok_s": 137.5}]}}})
    write(root, "speed/2026-11-04-student.json", {
        "kind": "speed", "persona": "student", "tries": 5, "points": [
            {"tokens": 655, "mb": 75, "fetch_s": 0.006, "notes_first_word_s": 0.076, "words_first_word_s": 0.149},
            {"tokens": 7792, "mb": 894, "fetch_s": 0.07, "notes_first_word_s": 0.258, "words_first_word_s": 1.533}]})
    for persona, knows, t in (("student", 65, "215935"), ("farmer", 68, "230537"), ("developer", 63, "234744")):
        write(root, f"2026-11-03/{t}-{persona}-s1-camr-27b.json", {
            "kind": "life", "persona": persona, "contender": {"name": "camr-27b"}, "started": f"2026-11-03T{t[:2]}:00",
            "weeks": [{"week": 12, "notes_so_far": 338, "peak_ram_gb": 17.18,
                       "summary": {"told": 85, "knows": knows, "false_memories": 0, "honest": 15,
                                   "wait_median_s": 2.2},
                       "answers": [{"qid": "q001", "kind": "abstain", "question": "What?", "expected": None,
                                    "answer": "I don't know.", "verdict": "right_abstain"}]}]})
        write(root, f"2026-11-03/{t[:4]}00-{persona}-s1-bare-27b.json", {
            "kind": "life", "persona": persona, "contender": {"name": "bare-27b"}, "started": f"2026-11-03T{t[:2]}:00",
            "weeks": [{"week": 12, "peak_ram_gb": 15.6, "summary": {"told": 85, "knows": 0, "false_memories": 0,
                                                                    "honest": 15, "wait_median_s": 0.46}}]})
    write(root, "2026-11-02/103205-student-s1-engram.json", {
        "kind": "life", "persona": "student", "contender": {"name": "engram"}, "started": "2026-11-02T10:32:05",
        "weeks": [{"week": w, "notes_so_far": 24 * w, "peak_ram_gb": 1.74,
                   "summary": {"told": 7 * w, "knows": 5 * w, "false_memories": 12 - w, "wait_median_s": 0.07}}
                  for w in range(1, 13)]})
    write(root, "2026-11-03/210705-student-s1-errands-bare.json", {
        "kind": "errands", "persona": "student", "contender": "bare",
        "summary": {"told": 85, "knows": 0, "false_memories": 15, "honest": 0, "wait_median_s": 0.14}, "tasks": []})
    write(root, "superseded/221549-student-s1-errands-bare-27b.json", {"kind": "errands", "contender": "old"})
    write(root, "bench/webdev-arena-summary.json", {"source": "lmarena-ai/leaderboard-dataset", "publications": 2,
                                                    "models": 4, "first_date": "2025-11-12",
                                                    "last_date": "2025-11-26", "note": "re-fitted"})
    write(root, "bench/webdev-arena-history.csv", "\n".join([
        "date,model,organisation,rating,ci_low,ci_high,open_weights,model_key,rank,votes,licence,category",
        "2025-11-12,claude-opus-4-5,anthropic,1490.0,1480.0,1500.0,false,Claude Opus 4.5,1,700,Proprietary,overall",
        "2025-11-12,glm-4.6,zai,1370.0,1360.0,1380.0,true,GLM-4.6,4,700,MIT,overall",
        "2025-11-12,qwen3.8-27b,alibaba,1300.0,1290.0,1310.0,true,Qwen3.8-27B,9,500,Apache 2.0,overall",
        "2025-11-12,gpt-x,openai,1500.0,1490.0,1510.0,false,GPT X,1,700,Proprietary,overall",
        "2025-11-26,claude-opus-4-5,anthropic,1512.0,1500.0,1524.0,false,Claude Opus 4.5,1,800,Proprietary,overall",
        "2025-11-26,Claude Sonnet 4.5,anthropic,1400.0,1390.0,1410.0,false,Claude Sonnet 4.5,3,800,Proprietary,overall",
        "2025-11-26,minimax-m2.1,minimax,1444.0,1434.0,1454.0,true,MiniMax-M2.1,2,800,MIT,overall",
        "2025-11-26,glm-4.6,zai,1999.0,1990.0,2000.0,true,GLM-4.6,1,800,MIT,webdev-html",
    ]) + "\n")
    ledger = [
        {"at": "2026-11-04T01:07:08", "kind": "hold", "hold": "a1", "model": "claude-haiku-5-5", "hold_usd": 0.5},
        {"at": "2026-11-04T01:07:09", "kind": "call", "hold": "a1", "model": "claude-haiku-5-5", "status": "ok",
         "input_tokens": 1562, "cache_creation_input_tokens": 92049, "cache_read_input_tokens": 0,
         "output_tokens": 769, "thinking_tokens": 0, "cost_usd": 0.012047},
        {"at": "2026-11-04T01:08:00", "kind": "count", "model": "claude-haiku-5-5", "status": "ok",
         "input_tokens": 93611, "cost_usd": 0.0},
        {"at": "2026-11-04T02:00:00", "kind": "hold", "hold": "b2", "model": "claude-opus-5-5", "hold_usd": 2.25},
        {"at": "2026-11-04T02:00:01", "kind": "call", "hold": "c3", "model": "claude-sonnet-5-5", "status": "error",
         "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0},
        {"at": "2026-11-04T02:00:02", "kind": "refused", "model": "claude-opus-5-5", "estimate_usd": 70.0},
    ]
    write(root, "bench/claude-ledger.jsonl", "\n".join(json.dumps(x) for x in ledger) + "\n{broken line\n")
    return root


@pytest.fixture
def app(records, tmp_path):
    return App(records, tmp_path / "shots")


# -- reading the records


def test_the_headline_is_the_27b_with_memory_against_without(app):
    h = bench.board(app)["headline"]
    assert (h["with"]["lo"], h["with"]["hi"], h["with"]["told"], h["with"]["lives"]) == (63, 68, 85, 3)
    assert (h["without"]["lo"], h["without"]["hi"]) == (0, 0)
    assert h["with"]["paths"][0].startswith("2026-11-03/") and h["with"]["peak_ram_gb"] == 17.18
    assert h["with"]["contenders"] == ["camr-27b"] and h["without"]["contenders"] == ["bare-27b"]


def test_the_probe_matrix_counts_each_family_at_each_cut_from_the_fullest_run(app):
    b = bench.board(app)
    assert [c["id"] for c in b["contenders"]] == ["engine:qwen3-1.7b", "bare:qwen3-1.7b", "claude-haiku-5-5"]
    assert [c["memory"] for c in b["contenders"]] == ["tensors", "none", "claude"]
    assert b["contenders"][0]["window"] == 32768  # the engine's model, from the bare run's window
    engine = b["matrix"]["engine:qwen3-1.7b"]
    assert engine["64K"]["path"].endswith("031000-longhaul-engine-qwen3-1.7b.json")  # not the 1-answer smoke run
    fams = engine["64K"]["families"]
    assert fams["two_hop"]["right"] == 1  # "hop-" ids are two-hop links
    assert fams["never"] == {"questions": 2, "graded": 2, "right": 1, "wrong": 0, "stale": 0, "false_memory": 1,
                             "declined": 0, "score": 0.5}
    assert fams["code"]["graded"] == 0 and fams["code"]["score"] is None  # an error is never graded
    assert engine["64K"]["all"]["graded"] == 6 and engine["256K"]["families"]["changed"]["stale"] == 1
    assert "1M" not in engine and "2M" not in engine
    claude = b["matrix"]["claude-haiku-5-5"]
    assert claude["64K"]["families"]["two_hop"]["declined"] == 1  # families come from qids when Claude names none
    assert claude["2M"]["families"]["lookalike"]["right"] == 1


def test_the_curves_put_each_measure_against_what_it_grows_with(app):
    series = {s["id"]: s for s in bench.board(app)["series"]}
    score = series["score|longhaul|engine:qwen3-1.7b"]
    assert [(p["x"], p["cut"]) for p in score["points"]] == [(64_000, "64K"), (256_000, "256K")]
    assert score["points"][0]["fm"] == 1 and score["points"][0]["n"] == 6 and score["memory"] == "tensors"
    assert {"y": 0.13, "hi": 3.4}.items() <= series["ttft|longhaul|engine:qwen3-1.7b"]["points"][0].items()
    claude = series["score|longhaul|claude-haiku-5-5"]
    assert claude["memory"] == "claude" and claude["window"] == 1_000_000
    assert [p["x"] for p in claude["points"]] == [64_000, 2_000_000]
    assert series["ttft|longhaul|claude-haiku-5-5"]["points"][0]["y"] == 2.2
    # retrieval and GB/s against the memory's size on the SSD, from the Long Haul and the speed test
    retr = series["retrieval|speed|engine:qwen3-1.7b"]
    assert [(p["x"], p["y"], p["hi"]) for p in retr["points"]] == [(2.1e9, 22.0, 31.0), (21e9, 35.0, 48.0)]
    assert series["retrieval|longhaul|engine:qwen3-1.7b"]["points"][0]["x"] == 8_445_219_920
    assert series["gbps|speed|engine:qwen3-1.7b"]["points"][1]["y"] == 6.1
    assert series["rooms|speed|engine:qwen3-1.7b|asleep"]["points"][1]["y"] == 40
    assert series["rooms|longhaul|engine:qwen3-1.7b|hot"]["memory"] == "ram"
    # baselines that read their whole history rise; an out-of-memory point is a fault, not a value
    tp = series["ttft|throughput|qwen-27b · mlx"]
    assert [p["x"] for p in tp["points"]] == [512] and tp["faults"] == ["32768 tok · out of GPU memory"]
    assert tp["memory"] == "none" and series["decode|throughput|qwen3-1.7b · mlx"]["points"][1]["y"] == 56.0
    assert series["ttft|throughput|qwen3-1.7b · ollama"]["points"][0]["y"] == 0.75
    notes = series["ttft|ruler-speed|ruler · student|notes"]
    words = series["ttft|ruler-speed|ruler · student|words"]
    assert (notes["memory"], words["memory"]) == ("tensors", "words") and words["points"][1]["y"] == 1.533
    babi = series["score|babilong|ollama-bare:qwen3:1.7b"]
    assert babi["task"] == "babilong" and {"x": 4103, "y": 0.5, "n": 2}.items() <= babi["points"][0].items()
    # the ruler's lives, week by week: the mean over personas, lowest and highest
    life = series["life|life|camr-27b"]["points"][0]
    assert life["x"] == 12 and life["n"] == 3 and life["lo"] == pytest.approx(63 / 85)
    assert life["hi"] == pytest.approx(68 / 85) and life["y"] == pytest.approx((63 + 68 + 65) / 3 / 85)
    assert len(series["life|life|engram"]["points"]) == 12 and series["life|life|engram"]["memory"] == "tensors"


def test_the_run_table_holds_every_record_newest_first_and_skips_superseded_ones(app):
    runs = bench.board(app)["runs"]
    paths = [r["path"] for r in runs]
    assert not any(p.startswith("superseded/") for p in paths)
    assert paths[0].endswith("040000-speed-engine-qwen3-1.7b.json")
    errands = next(r for r in runs if r["kind"] == "errands")
    assert errands["started"] == "2026-11-03T21:07:05"  # from its folder and file name, since it says none
    assert errands["false_memory"] == 15 and errands["score"] == 0.0
    claude = next(r for r in runs if r["contender"] == "claude-haiku-5-5")
    assert claude["cost_usd"] == 1.13 and claude["ttft_s"] == 2.2 and claude["cuts"] == ["64K", "2M"]
    smoke = next(r for r in runs if r["path"].endswith("024421-longhaul-engine-qwen3-1.7b.json"))
    assert smoke["limit"] == 5 and smoke["right"] == 1 and smoke["graded"] == 1
    webdev = next(r for r in runs if r["kind"] == "webdev")
    assert webdev["publications"] == 2


def test_runs_stamped_only_by_their_file_names_sort_among_the_others(app, records):
    write(records, "2026-11-04/000644-student-s1-errands-engram.json", {
        "kind": "errands", "persona": "student", "contender": "engram",
        "summary": {"told": 85, "knows": 40, "false_memories": 2, "honest": 10, "wait_median_s": 0.07}, "tasks": []})
    runs = bench.board(app)["runs"]
    at = {r["path"]: (i, r["started"]) for i, r in enumerate(runs)}
    claude = at["bench/2026-11-04/022518-claude-claude-haiku-5-5-longhaul.json"]
    throughput = at["bench/throughput-2026-11-04-0123.json"]
    errands = at["2026-11-04/000644-student-s1-errands-engram.json"]
    speed = at["speed/2026-11-04-student.json"]
    life = at["2026-11-03/215935-student-s1-camr-27b.json"]
    assert throughput[1] == "2026-11-04T01:23" and speed[1] == "2026-11-04"
    assert claude[0] < throughput[0] < errands[0] < speed[0] < life[0]  # 02:25, 01:23, 00:06, that day, the day before


def test_the_ledger_counts_spend_as_the_budget_does(app, records):
    from engram.bench import claude

    led = bench.board(app)["ledger"]
    lines = [json.loads(x) for x in (records / "bench" / "claude-ledger.jsonl").read_text().splitlines()
             if x.startswith("{\"")]
    assert led["spent_usd"] == pytest.approx(claude.Ledger._spent(lines))
    assert (led["cap_usd"], led["headroom_usd"]) == (claude.CAP_USD, claude.HEADROOM_USD)
    assert led["held_usd"] == 2.25 and led["refused"] == 1  # an open hold counts until its call closes it
    haiku, sonnet, opus = led["models"]
    assert [m["model"] for m in led["models"]] == ["claude-haiku-5-5", "claude-sonnet-5-5", "claude-opus-5-5"]
    assert (haiku["calls"], haiku["counts"], haiku["input_tokens"], haiku["cache_write_tokens"]) == (1, 1, 1562, 92049)
    assert haiku["held_usd"] == 0 and sonnet["failed"] == 1 and opus["refused"] == 1
    assert haiku["longhaul"]["right"] == 2 and haiku["longhaul"]["per_right_usd"] == pytest.approx(1.13 / 2)


def test_pages_carry_a_key_only_when_the_answer_holds_html(app):
    pages = bench.board(app)["pages"]
    engine = next(p for p in pages if p["contender"] == "engine:qwen3-1.7b")
    assert engine["qid"] == "page-catering" and re.fullmatch(r"[0-9a-f]{16}", engine["key"])
    assert engine["shot"] is False and engine["reason"] == "why page-catering"
    claude = next(p for p in pages if p["contender"] == "claude-haiku-5-5")
    assert claude["key"] is None and claude["verdict"] == "declined"


def test_an_empty_folder_gives_dashes_not_errors(tmp_path, monkeypatch):
    monkeypatch.setenv("ENGRAM_MEASURING", str(tmp_path / "measuring.json"))
    b = bench.board(App(tmp_path / "nothing", tmp_path / "shots"))
    assert b["headline"] == {"model": "Qwen 27B", "with": None, "without": None}
    assert b["contenders"] == [] and b["series"] == [] and b["runs"] == [] and b["pages"] == []
    assert b["ledger"]["present"] is False and b["ledger"]["spent_usd"] is None and b["webdev"] is False
    assert len(b["families"]) == 8 and [c["name"] for c in b["cuts"]] == ["64K", "256K", "1M", "2M"]


def test_a_record_being_written_is_listed_and_read_again_once_it_changes(app, records):
    path = records / "bench" / "2026-11-04" / "050000-longhaul-engine-qwen3-4b.json"
    path.write_text('{"kind": "bench", "task": "longhaul", "contender": {"na')
    b = bench.board(app)
    assert [e["path"] for e in b["errors"]] == ["bench/2026-11-04/050000-longhaul-engine-qwen3-4b.json"]
    assert "engine:qwen3-4b" not in b["matrix"] and b["runs"]  # the others still show
    path.write_text(json.dumps(local_record("engine:qwen3-4b", "engine", {"1M": [answer("fact-1", "right", "fact")]},
                                            "2026-11-04T05:00:00")))
    os.utime(path, ns=(path.stat().st_atime_ns, path.stat().st_mtime_ns + 10**9))
    b = bench.board(app)
    assert b["errors"] == [] and b["matrix"]["engine:qwen3-4b"]["1M"]["all"]["right"] == 1
    path.unlink()
    assert "engine:qwen3-4b" not in bench.board(app)["matrix"]


def test_the_measuring_flag_shows_on_the_board(app, tmp_path):
    from engram.app.measuring import measuring

    assert bench.board(app)["measuring"] is None
    with measuring("longhaul"):
        assert bench.board(app)["measuring"]["job"] == "longhaul"


def age(root: Path, seconds: float) -> None:
    """Every record under ``root`` last changed ``seconds`` ago."""
    import time

    for p in root.rglob("*"):
        if p.is_file():
            t = time.time() - seconds
            os.utime(p, (t, t))


def test_pages_are_shot_unasked_only_while_nothing_runs(app, records, monkeypatch):
    from engram.app.measuring import measuring

    s = bench.board(app)["shoot"]
    assert s["auto"] is False and s["why"] == "waiting: a record changed under a minute ago"  # a run may be writing
    age(records, 20 * 60)
    assert bench.board(app)["shoot"] == {"auto": True, "why": None}
    (records / "bench" / "claude-ledger.jsonl").touch()  # a Claude call just now
    assert bench.board(app)["shoot"]["auto"] is False
    age(records, 20 * 60)
    monkeypatch.setattr(bench, "running", lambda: "engram.bench.local")
    assert bench.board(app)["shoot"] == {"auto": False, "why": "waiting: engram.bench.local is running"}
    monkeypatch.setattr(bench, "running", lambda: None)
    with measuring("longhaul"):
        assert bench.board(app)["shoot"] == {"auto": False, "why": "longhaul is measuring"}


def test_a_benchmark_process_is_found_by_its_command_line(monkeypatch):
    def ps(lines):
        def run(cmd, **kw):
            assert cmd[0] == "ps"
            return subprocess.CompletedProcess(cmd, 0, "\n".join(lines) + "\n", "")
        return run

    found = []
    for lines in (["  101 /usr/bin/python3 -m engram.app --port 8765", "  102 /bin/zsh -l"],
                  ["  201 .venv/bin/python -m engram.bench.local longhaul engine:qwen3-1.7b"],
                  ["  301 python /Users/x/v2/engram/ruler/life.py --persona student"],
                  ["  401 /Applications/Ollama.app/Contents/Resources/ollama runner --model /x/blobs/sha256-1"],
                  [f"  {os.getpid()} python -m engram.bench.local speed"]):  # this process is never the runner
        monkeypatch.setattr(bench, "_PS", {"at": None, "value": None})
        found.append(REAL_RUNNING(run=ps(lines)))
    assert found == [None, "engram.bench.local", "engram/ruler/life.py", "ollama runner", None]
    calls = []
    monkeypatch.setattr(bench, "_PS", {"at": None, "value": None})
    REAL_RUNNING(run=lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    REAL_RUNNING(run=lambda cmd, **kw: calls.append(cmd) or subprocess.CompletedProcess(cmd, 0, "", ""))
    assert len(calls) == 1  # read again only after 15 s

    def broken(cmd, **kw):
        raise OSError("no ps")
    monkeypatch.setattr(bench, "_PS", {"at": None, "value": None})
    assert REAL_RUNNING(run=broken) is None


# -- one record, for its sheet


def test_a_record_sheet_is_trimmed_and_keeps_no_home_paths_or_request_ids(app, records):
    sheet = bench.record_sheet(records, "bench/2026-11-04/031000-longhaul-engine-qwen3-1.7b.json")
    assert sheet["label"] == "engine · qwen3-1.7b" and sheet["memory"] == "tensors"
    assert [g["name"] for g in sheet["groups"]] == ["64K", "256K"]
    page = next(a for a in sheet["groups"][0]["answers"] if a["id"] == "page-catering")
    assert page["family"] == "page" and page["verdict"] == "wrong" and page["ttft_s"] == 0.1
    assert sheet["groups"][0]["summary"]["ttft_s p50"] == 0.13
    text = json.dumps(sheet)
    assert str(Path.home()) not in text and "folder" not in sheet["settings"]
    claude = bench.record_sheet(records, "bench/2026-11-04/022518-claude-claude-haiku-5-5-longhaul.json")
    assert "req_secretish" not in json.dumps(claude) and claude["groups"][0]["answers"][1]["family"] == "two_hop"
    life = bench.record_sheet(records, "2026-11-03/215935-student-s1-camr-27b.json")
    assert life["groups"][0]["name"] == "week 12" and life["groups"][0]["answers"][0]["verdict"] == "right_abstain"
    long = answer("fact-1", "right", "fact", "y" * 5000)
    write(records, "bench/2026-11-04/060000-longhaul-engine-qwen3-8b.json",
          local_record("engine:qwen3-8b", "engine", {"64K": [long]}, "2026-11-04T06:00:00"))
    got = bench.record_sheet(records, "bench/2026-11-04/060000-longhaul-engine-qwen3-8b.json")
    assert len(got["groups"][0]["answers"][0]["answer"]) == 1501


@pytest.mark.parametrize("rel", ["../outside.json", "/etc/passwd.json", "~/x.json", "bench/../../x.json",
                                 "bench/.hidden.json", "bench/claude-ledger.jsonl", "bench/missing.json",
                                 "bench/2026-11-04/x.json\x00", "bench\\x.json", ""])
def test_a_record_path_stays_inside_the_records_folder(records, rel):
    with pytest.raises(Refused) as e:
        bench.record_sheet(records, rel)
    assert e.value.code in (400, 404)


def test_a_link_out_of_the_records_folder_is_refused(records, tmp_path):
    secret = tmp_path / "secret.json"
    secret.write_text("{}")
    (records / "bench" / "link.json").symlink_to(secret)
    with pytest.raises(Refused) as e:
        bench.record_sheet(records, "bench/link.json")
    assert e.value.code == 400


# -- the WebDev history


def test_webdev_keeps_the_best_claude_the_best_open_model_and_this_macs_models(records):
    w = bench.webdev(records / "bench" / "webdev-arena-history.csv", records / "bench" / "webdev-arena-summary.json")
    assert w["dates"] == ["2025-11-12", "2025-11-26"] and w["publications"] == 2
    assert [x["rating"] for x in w["series"]["claude"]] == [1490.0, 1512.0]
    assert [x["model"] for x in w["series"]["open"]] == ["GLM-4.6", "MiniMax-M2.1"]  # the webdev-html row is not overall
    assert [x["rating"] for x in w["series"]["closed"]] == [1500.0, 1512.0]
    assert w["series"]["mac:Qwen3.8-27B"][0] == {"date": "2025-11-12", "rating": 1300.0, "lo": 1290.0, "hi": 1310.0,
                                                 "model": "Qwen3.8-27B", "organisation": "alibaba"}
    assert w["source"] == "lmarena-ai/leaderboard-dataset" and w["path"] == "bench/webdev-arena-history.csv"
    assert "qwen3.8-27b" in bench.on_this_mac() and "qwen3-1.7b" in bench.on_this_mac()
    assert bench.webdev(records / "none.csv", records / "none.json")["present"] is False


# -- screenshots of the page that grows


def fake_browser(calls: list, png: bytes = PNG_1X1):
    """A headless browser that writes ``png`` where --screenshot says, and records the command."""
    def run(cmd, **kw):
        calls.append(cmd)
        out = next(a.split("=", 1)[1] for a in cmd if a.startswith("--screenshot="))
        Path(out).write_bytes(png)
        return subprocess.CompletedProcess(cmd, 0, b"", b"")
    return run


def test_render_shoots_with_the_network_switched_off(tmp_path):
    calls: list = []
    page = "<html><body><footer>© 2026 Mama Njeri's Kitchen · Nairobi</footer></body></html>"
    out = bench.render(page, tmp_path / "s" / "k.png", "chrome", run=fake_browser(calls))
    assert out.read_bytes() == PNG_1X1 and bench.png_size(out.read_bytes()) == (1, 1)
    cmd = calls[0]
    assert cmd[0] == "chrome" and "--headless=new" in cmd and "--host-resolver-rules=MAP * ~NOTFOUND" in cmd
    assert "--proxy-server=127.0.0.1:9" in cmd and "--proxy-bypass-list=<-loopback>" in cmd
    assert "--force-webrtc-ip-handling-policy=disable_non_proxied_udp" in cmd and "--disable-quic" in cmd
    # the page goes in as a data: URL: a file:// page could frame or redirect to any file this user can read
    head, _, body = cmd[-1].partition(",")
    assert head == "data:text/html;charset=utf-8;base64" and base64.b64decode(body).decode("utf-8") == page
    assert not any("file:" in a for a in cmd) and not any(a.startswith("http") for a in cmd)
    calls.clear()
    with pytest.raises(Refused) as e:
        bench.render("<p>" + "x" * bench.MAX_PAGE + "</p>", tmp_path / "big.png", "chrome", run=fake_browser(calls))
    assert e.value.code == 413 and not calls and not (tmp_path / "big.png").exists()
    with pytest.raises(Refused) as e:
        bench.render("<p>x</p>", tmp_path / "bad.png", "chrome", run=fake_browser([], png=b"not a png"))
    assert e.value.code == 502 and not (tmp_path / "bad.png").exists()

    def slow(cmd, **kw):
        raise subprocess.TimeoutExpired(cmd, 1)
    with pytest.raises(Refused) as e:
        bench.render("<p>x</p>", tmp_path / "slow.png", "chrome", run=slow)
    assert e.value.code == 504


def serve(app):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    httpd, token = make_server(app, port)
    threading.Thread(target=lambda: httpd.serve_forever(poll_interval=0.05), daemon=True).start()

    def call(path, body=None):
        c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
        headers = {"Host": f"127.0.0.1:{port}", "X-Engram-Token": token}
        if body is not None:
            headers["Content-Type"] = "application/json"
        c.request("POST" if body is not None else "GET", path, body=None if body is None else json.dumps(body),
                  headers=headers)
        r = c.getresponse()
        return r.status, json.loads(r.read() or b"null")

    return call, httpd


def test_the_bench_routes_through_the_server(app, monkeypatch, tmp_path):
    from engram.app.measuring import measuring

    calls: list = []
    real = bench.render
    monkeypatch.setattr(bench, "render", lambda html, out, browser, **kw: real(html, out, browser,
                                                                              run=fake_browser(calls)))
    monkeypatch.setattr(bench, "_browser", lambda: "/Applications/Fake Chrome")
    call, httpd = serve(app)
    try:
        code, b = call("/api/bench")
        assert code == 200 and b["headline"]["with"]["hi"] == 68 and b["matrix"]
        code, r = call("/api/bench/record?path=bench/2026-11-04/031000-longhaul-engine-qwen3-1.7b.json")
        assert code == 200 and r["groups"][0]["name"] == "64K"
        assert call("/api/bench/record?path=../x.json")[0] == 400
        code, w = call("/api/bench/webdev")
        assert code == 200 and w["present"] and call("/api/bench/webdev")[1] == w  # kept until the file changes
        page = next(p for p in b["pages"] if p["key"])
        want = {"path": page["path"], "cut": page["cut"], "qid": page["qid"]}
        assert call(f"/api/bench/shot?key={page['key']}")[0] == 404
        assert b["shoot"]["auto"] is False  # the records were written just now
        code, got = call("/api/bench/shot", want)
        assert code == 409 and got["error"].startswith("waiting: a record changed") and not calls
        with measuring("babilong"):
            code, got = call("/api/bench/shot", {**want, "asked": True})  # a click never beats the flag
            assert code == 409 and "babilong is measuring" in got["error"] and not calls
        code, got = call("/api/bench/shot", {**want, "asked": True})
        assert code == 200 and got == {"key": page["key"], "made": True} and len(calls) == 1
        assert (tmp_path / "shots" / f"{page['key']}.png").read_bytes() == PNG_1X1
        assert call("/api/bench/shot", want)[1]["made"] is False and len(calls) == 1  # shot once
        code, s = call(f"/api/bench/shot?key={page['key']}")
        assert code == 200 and s["png"].startswith("data:image/png;base64,") and (s["width"], s["height"]) == (1, 1)
        assert call("/api/bench")[1]["pages"][0]["shot"] is True
        assert call("/api/bench/shot?key=../../etc")[0] == 400
        declined = {"path": "bench/2026-11-04/022518-claude-claude-haiku-5-5-longhaul.json", "cut": "64K",
                    "qid": "page-catering"}
        code, got = call("/api/bench/shot", declined)
        assert code == 409 and "no HTML" in got["error"]
        code, got = call("/api/bench/shot", {**declined, "qid": "fact-1"})
        assert code == 400
        code, got = call("/api/bench/shot", {**want, "qid": "page-nope"})
        assert code == 404
        monkeypatch.setattr(bench, "_browser", lambda: None)
        other = {"path": "bench/2026-11-04/031000-longhaul-engine-qwen3-1.7b.json", "cut": "64K",
                 "qid": "page-catering"}
        shutil.rmtree(tmp_path / "shots")
        code, got = call("/api/bench/shot", {**other, "asked": True})
        assert code == 409 and "no headless browser" in got["error"]
        age(app.bench_root, 20 * 60)  # quiet: the screen may shoot on its own
        monkeypatch.setattr(bench, "_browser", lambda: "/Applications/Fake Chrome")
        code, got = call("/api/bench/shot", other)
        assert code == 200 and got["made"] is True and len(calls) == 2
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_a_screenshot_kept_beside_the_records_is_found_too(app, records):
    key = bench.board(app)["pages"][0]["key"]
    (records / "bench" / "shots").mkdir()
    (records / "bench" / "shots" / f"{key}.png").write_bytes(PNG_1X1)
    assert bench.shot_file(app, key) == records / "bench" / "shots" / f"{key}.png"
    assert bench.board(app)["pages"][0]["shot"] is True


def test_the_real_records_read_without_a_failure():
    """Whatever has arrived in v2/records tonight: the board is built (a record caught mid-write is listed)."""
    if not bench.ROOT.is_dir():
        pytest.skip("no records folder")
    b = bench.board(App(bench.ROOT, Path("/nonexistent-shots")))
    assert isinstance(b["runs"], list) and all("path" in e for e in b["errors"])
    json.dumps(b)


# -- the screen


def test_the_screen_keeps_the_contract_and_calls_only_routes_that_exist():
    from engram.app.routes import collect

    text = (STATIC / "screens" / "bench.js").read_text()
    assert re.search(r"export function mount\(el, api\)", text)
    for word in ("show()", "hide()", "key(e, { typing })"):
        assert word in text, word
    paths = {p for _, p in collect().table}
    called = set(re.findall(r'api\.(?:get|post)\("(/api/[^"]+)"', text))
    assert called == {"/api/bench", "/api/bench/record", "/api/bench/webdev", "/api/bench/shot"} and called <= paths
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|rgba?\(|hsla?\(|oklch\(", text)
    assert "localStorage" in text and "try {" in text  # a private window never breaks it
    for tab in ("Past the window", "How far it grows", "Which reach", "Swarms", "Sleep", "The gap"):
        assert tab in text, tab
    # the matrix redraws when a cut is picked: it reads the pick's value, so it is subscribed to it
    matrix = text[text.index("function Matrix()"):text.index("// -- the yardstick")]
    assert "matrixCut(cutPick.value)" in matrix and "cutPick.peek()" not in matrix
    # the screen shoots on its own only when the board says so; a click says it was asked; a 409 wait is no fault
    shoot_next = text[text.index("async function shootNext()"):text.index("const isWait")]
    assert "!d.shoot?.auto" in shoot_next and "shoot(want, false)" in shoot_next
    assert "shoot(page, true)" in text and "asked });" in text
    assert re.search(r"isWait = \(e\) => e\?\.status === 409 && /is measuring\|being shot\|\^waiting/", text)
    node = shutil.which("node")
    if node:
        run = subprocess.run([node, "--check", str(STATIC / "screens" / "bench.js")], capture_output=True, text=True)
        assert run.returncode == 0, run.stderr

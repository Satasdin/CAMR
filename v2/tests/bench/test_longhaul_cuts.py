"""The 3M and 4M cuts: left out of a script that is shorter, and asking the 2M questions again on a longer one."""

import json

from camr_engine.bench import longhaul


def haul(folder, tokens):
    folder.mkdir(parents=True)
    events = [{"i": i, "day": 1 + i // 10, "kind": "chat", "role": "user", "text": f"line {i}", "tokens": t,
               "cum_tokens": c} for i, (t, c) in enumerate(tokens)]
    probe = {"id": "fact-001", "family": "fact", "ask": "Which?", "answer": "A", "event": 0, "events": [0],
             "planted_at": events[0]["cum_tokens"], "ready_at": events[0]["cum_tokens"], "planted_day": 1,
             "grader": {"type": "exact", "accept": ["A"]}, "sample": False, "ask_day": None}
    (folder / "script.jsonl").write_text("".join(json.dumps(e) + "\n" for e in events))
    (folder / "probes.jsonl").write_text(json.dumps(probe) + "\n")
    return folder


def test_cuts_past_the_script_are_left_out_after_the_first(tmp_path):
    short = haul(tmp_path / "short", [(10, 10), (10, 20)])
    _, cps = longhaul.checkpoints(short)
    assert [c["name"] for c in cps] == ["64K"]  # a script shorter than every cut still gets one checkpoint
    long = haul(tmp_path / "long", [(10, 10), (1_999_990, 2_000_000), (1_000_000, 3_000_000), (1_000_000, 4_000_000)])
    _, cps = longhaul.checkpoints(long)
    assert [c["name"] for c in cps] == ["64K", "256K", "1M", "2M", "3M", "4M"]
    by = {c["name"]: c for c in cps}
    assert [q["id"] for q in by["3M"]["questions"]] == [q["id"] for q in by["2M"]["questions"]] == ["fact-001"]
    assert by["4M"]["events"] == 4 and by["3M"]["events"] == 3

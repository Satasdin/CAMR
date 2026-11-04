"""The WebDev Arena history from fixture rows, the shared helpers, the dispatcher and the command line. No network."""

from __future__ import annotations

import csv
import json

import pytest

from camr_engine.bench import suites
from camr_engine.bench.suites import common, webdev
from camr_engine.bench.suites.__main__ import main


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    import huggingface_hub
    import huggingface_hub.utils

    def no(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setenv("CAMR_DATASETS", str(tmp_path / "data"))
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", no)
    monkeypatch.setattr(huggingface_hub.utils, "get_session", no)


def _row(date, name, org, rating, licence="Proprietary", category="overall", rank=1):
    return {"model_name": name, "organization": org, "license": licence, "rating": rating,
            "rating_lower": rating - 10, "rating_upper": rating + 10, "variance": 25.0, "vote_count": 1000,
            "rank": rank, "category": category, "leaderboard_publish_date": date}


ROWS = [
    _row("2026-01-05", "claude-opus-4-5-20251101", "anthropic", 1500.0),
    _row("2026-01-05", "glm-4.6", "zai", 1400.0, "MIT", rank=2),
    _row("2026-01-28", "claude-opus-4-5-20251101", "anthropic", 1510.0),
    _row("2026-01-28", "glm-4.6", "zai", 1420.0, "MIT", rank=2),
    _row("2026-01-28", "mystery-model", "", 1300.0, "", rank=3),
    _row("2026-01-28", "gpt-x", "openai", 9999.0, category="webdev-html"),  # another board
    _row("2026-02-10", "Claude Opus 4.5 (20251101)", "anthropic", 1490.0, rank=2),
    _row("2026-02-10", "GPT-6 Astra (Max)", "openai", 1600.0),
    _row("2026-02-10", "Kimi K3 (Max)", "moonshot", 1550.0, "Kimi K3 license", rank=3),
    _row("2026-02-10", "Claude Opus 5.4", "anthropic", 1480.0, rank=4),
]


def test_open_weights_from_the_licence():
    assert webdev.open_weights("Proprietary") is False
    assert webdev.open_weights("Apache 2.0") is True and webdev.open_weights("Kimi K3 license") is True
    assert webdev.open_weights("") is None and webdev.open_weights(None) is None


def test_slugs_and_display_names_are_one_model():
    assert webdev.name_words("claude-opus-4-5-20251101") == webdev.name_words("Claude Opus 4.5 (20251101)")
    assert webdev.name_words("claude-opus-4-5-20251101-high-32k") == \
        webdev.name_words("Claude Opus 4.5 (High, 32K, 20251101)")
    assert webdev.name_words("Claude Opus 4.5") != webdev.name_words("Claude Opus 5.4")
    assert webdev.name_words("kimi-k2.5-thinking") == webdev.name_words("Kimi K2.5 (Thinking)")


def test_history_and_csv(tmp_path):
    hist = webdev.history(ROWS)
    assert len(hist) == 9 and {h["category"] for h in hist} == {"overall"}
    assert hist[0]["date"] == "2026-01-05" and hist[0]["model"] == "claude-opus-4-5-20251101"
    assert hist[0]["model_key"] == "Claude Opus 4.5 (20251101)"  # the latest name
    glm = next(h for h in hist if h["model"] == "glm-4.6")
    assert glm["open_weights"] is True and glm["organisation"] == "zai" and (glm["ci_low"], glm["ci_high"]) == (
        1390.0, 1410.0)
    p = webdev.write_csv(hist, tmp_path / "h.csv")
    with open(p) as f:
        rows = list(csv.DictReader(f))
    assert list(rows[0])[:7] == ["date", "model", "organisation", "rating", "ci_low", "ci_high", "open_weights"]
    assert {r["open_weights"] for r in rows} == {"true", "false", ""}
    assert len(webdev.history(ROWS, category=None)) == 10


def test_summary():
    s = webdev.summary(webdev.history(ROWS))
    assert [(r["month"], r["date"], r["model"]) for r in s["top_by_month"]] == [
        ("2026-01", "2026-01-28", "claude-opus-4-5-20251101"), ("2026-02", "2026-02-10", "GPT-6 Astra (Max)")]
    assert [(r["model"], r["gap_to_top"]) for r in s["best_open_by_month"]] == [("glm-4.6", 90.0),
                                                                               ("Kimi K3 (Max)", 50.0)]
    assert [r["model"] for r in s["claude_by_month"]] == ["claude-opus-4-5-20251101", "Claude Opus 4.5 (20251101)"]
    lines = {m["model_key"]: m for m in s["claude_models"]}
    assert set(lines) == {"Claude Opus 4.5 (20251101)", "Claude Opus 5.4"}
    opus = lines["Claude Opus 4.5 (20251101)"]
    assert (opus["first_seen"], opus["peak_rating"], opus["last_rating"], opus["publications"]) == (
        "2026-01-05", 1510.0, 1490.0, 3)
    assert s["publications"] == 3 and s["first_date"] == "2026-01-05"


def test_build_writes_both_files(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    src = tmp_path / "full.parquet"
    pq.write_table(pa.Table.from_pylist(ROWS), src)
    csv_path, summary_path, s = webdev.build(tmp_path / "h.csv", tmp_path / "s.json", path=src)
    assert csv_path.exists() and json.loads(summary_path.read_text())["rows"] == 9 == s["rows"]
    _, _, every = webdev.build(tmp_path / "h2.csv", tmp_path / "s2.json", category=None, path=src)
    assert every["rows"] == 9  # the summary keeps to one board even when the CSV keeps all


def test_chunk_keeps_lines_and_joins_back():
    text = "".join(f"{k}. Fact {k} is here.\n" for k in range(200))
    pieces = common.chunk(text, tokens=50)
    assert "".join(pieces) == text and all(len(p) <= 200 for p in pieces)
    assert all(p[0].isdigit() for p in pieces)  # a numbered fact keeps its number
    prose = "One. Two two. Three three three. " * 40
    assert "".join(common.chunk(prose, tokens=20)) == prose
    assert common.chunk("x" * 100, tokens=5) == ["x" * 20] * 5
    assert common.chunk("") == []


def test_common_helpers():
    assert common.estimate_tokens("abcd" * 10) == 10 and common.estimate_tokens(["abcd", "abcd"]) == 2
    assert common.clean("<think>a</think> b ") == "b" and common.clean("<think>open") == "" and common.clean(None) == ""
    assert common.verdict(True, "x") == "right" and common.verdict(False, "Paris") == "wrong"
    assert common.verdict(False, "I don't know") == "declined"
    assert common.verdict(False, "I don't know", should_decline=True) == "right_abstain"
    assert common.verdict(True, "Paris", should_decline=True) == "false_memory"
    assert common.rng(3, "a").random() == common.rng(3, "a").random() != common.rng(4, "a").random()
    it = common.Item("x/1", "math500", "", "Q?", ["a", "b"], 3)
    assert it.expected == ["a", "b"] and it.answers == ["a", "b"] and it.chunks == [""] and not it.should_decline
    assert "no context" in it.summary()


def test_dispatcher(tmp_path):
    assert suites.module("mab") is suites.SUITES["memoryagentbench"]
    with pytest.raises(KeyError):
        suites.module("nope")
    it = common.Item("math500/a/1", "math500", "", "1+1?", "2", 2, {"instruction": "Solve."})
    assert suites.grade(it, "\\boxed{2}") == "right" and suites.prompt(it).endswith("1+1?")
    assert set(suites.SUITES) == {"babilong", "memoryagentbench", "math500", "aime", "harp", "longmemeval"}


def test_cli_list(capsys):
    assert main(["list"]) == 0
    out = capsys.readouterr().out
    for name in ("babilong", "memoryagentbench", "math500", "aime", "harp", "longmemeval", "webdev"):
        assert name in out


def test_cli_sample(tmp_path, capsys):
    folder = tmp_path / "data" / "math500"
    folder.mkdir(parents=True)
    rows = [{"problem": f"What is {k}+{k}?", "solution": "", "answer": str(2 * k), "subject": "Algebra", "level": 1,
             "unique_id": f"test/algebra/{k}.json"} for k in range(5)]
    (folder / "test.jsonl").write_text("\n".join(json.dumps(r) for r in rows))
    assert main(["sample", "math500", "--n", "3", "--seed", "1"]) == 0
    out = capsys.readouterr().out
    assert out.startswith("3 items from math500 (n=3, seed=1)") and "length in tokens" in out
    assert out.count("\n- math500/algebra/") == 3
    assert main(["sample", "nope"]) == 2

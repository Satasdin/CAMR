"""Metrics: one record per answer, with retrieval broken down, bandwidth, the share of the wait spent reading, tokens
seen against the history, peak RAM and disk. The last test answers through Memory with the fake reader (needs
MLX)."""

from __future__ import annotations

import json

import pytest

from engram.memory import Recall
from engram.metrics import Meter, folder_bytes, measure, peak_ram_bytes, spread, summary
from engram.models import Reply


def recall(**kw) -> Recall:
    rec = Recall(3, [1, 2], 200, 200 * 16, seconds={"choose": 0.002, "fetch": 0.010, "desk": 0.004},
                 tier="ssd", read_bytes=200 * 2**20)
    for k, v in kw.items():
        setattr(rec, k, v)
    return rec


def test_a_record_breaks_the_wait_down(tmp_path):
    reply = Reply("Nakuru.", 0.080, 240.0, 900, 4)  # wait already includes retrieval, as Memory reports it
    r = measure("Where does Amina live?", reply, recall(), total_s=0.1, first_s=0.064, new_tokens=64,
                history_tokens=12_000, disk_bytes=5_000, reach="global")
    assert r.first_word_s == 0.08 and r.total_s == 0.1 and r.decode_tps == 240.0 and r.prefill_tps == 1000.0
    assert r.retrieval_ms == {"choose": 2.0, "fetch": 10.0, "desk": 4.0, "total": 16.0}
    assert r.gbps == pytest.approx(200 * 2**20 / 0.010 / 1e9, abs=0.01) and r.read_share == 0.125
    assert (r.context_tokens, r.history_tokens, r.new_tokens, r.answer_tokens) == (900, 12_000, 64, 4)
    assert r.tier == "ssd" and r.room == 3 and r.reach == "global" and r.disk_bytes == 5_000
    assert r.peak_ram_bytes > 10 * 2**20 and r.at


def test_a_ram_hit_reads_nothing_from_the_ssd():
    reply = Reply("Nakuru.", 0.05, 240.0, 900, 4)
    r = measure("q", reply, recall(tier="ram", read_bytes=0, seconds={"choose": 0.002, "desk": 0.004}),
                total_s=0.07, first_s=0.04, new_tokens=0, history_tokens=1, disk_bytes=1)
    assert r.gbps is None and r.read_share == 0.0 and r.prefill_tps is None and "fetch" not in r.retrieval_ms


def test_records_go_to_a_json_line_each_and_summarise_to_medians_and_p90(tmp_path):
    meter = Meter(tmp_path / "metrics.jsonl")
    for i, wait in enumerate((0.05, 0.06, 0.07, 0.30)):
        meter.add(measure(f"q{i}", Reply("x", wait, 200.0, 500 + i, 3), recall(), total_s=wait + 0.1, first_s=0.04,
                          new_tokens=40, history_tokens=1000 * (i + 1), disk_bytes=10 * i))
    rows = Meter.read(tmp_path / "metrics.jsonl")
    assert len(rows) == 4 and rows[0]["question"] == "q0" and json.loads(json.dumps(rows[0])) == rows[0]
    s = meter.summary()
    assert s["answers"] == 4 and s["first_word_s"]["p50"] == pytest.approx(0.065)
    assert s["first_word_s"]["p90"] == pytest.approx(0.231) and s["retrieval_ms"]["fetch"]["p50"] == 10.0
    assert s["history_tokens"] == 4000 and s["disk_bytes"] == 30 and s["tiers"] == {"ssd": 4}
    assert summary(rows) == s and summary([]) == {"answers": 0}
    assert spread([None]) == {"p50": None, "p90": None}


def test_disk_and_ram_are_measured(tmp_path):
    (tmp_path / "a").mkdir()
    (tmp_path / "a" / "x.bin").write_bytes(b"0" * 1000)
    (tmp_path / "y.md").write_text("hello")
    assert folder_bytes(tmp_path) == 1005 and peak_ram_bytes() > 0


def test_memory_writes_one_record_per_answer(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, make

    from engram.swap import Tiers

    m = make(tmp_path / "memory", vault=True, tiers=Tiers(), metrics=True)
    m.remember("Amina moved to Nakuru.", 0)
    m.remember("Paid the electricity bill.", 1)
    m.tiers.forget(0)
    first = m.answer("Where does Amina live?", TODAY)
    second = m.answer("Where does Amina live?", TODAY)
    a, b = first.metrics, second.metrics
    assert (a.tier, b.tier) == ("ssd", "ram") and a.read_bytes > 0 and b.read_bytes == 0
    assert a.context_tokens == first.prompt_tokens and a.history_tokens == m.history_tokens()
    assert a.new_tokens == len(m.reader.calls[0].ids) and a.total_s >= a.first_word_s >= 0.001
    assert m.disk_bytes() < a.disk_bytes < m.folder_bytes()  # the vault counts too; then the records grew
    assert len(Meter.read(tmp_path / "memory" / "metrics.jsonl")) == 2 and m.meter.last is b

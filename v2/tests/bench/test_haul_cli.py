"""The Long Haul command line: build writes the three files, sample prints a stratified sample for a cut, grade
grades a file of answers."""

from __future__ import annotations

import json

from haul_shared import built, perfect

from camr_engine.bench.haul import at_cut, write
from camr_engine.bench.haul.__main__ import main


def test_build_writes_the_three_files(tmp_path, capsys):
    built()  # skips without the tokenizer
    out = tmp_path / "haul"
    assert main(["build", "--seed", "1", "--out", str(out)]) == 0
    assert {p.name for p in out.iterdir()} == {"script.jsonl", "probes.jsonl", "manifest.json"}
    m = json.loads((out / "manifest.json").read_text())
    assert m["seed"] == 1 and m["tokens"] >= 2_000_000
    assert "2M" in capsys.readouterr().out


def test_sample_and_grade(tmp_path, capsys):
    h = built()
    write(h, tmp_path)
    assert main(["sample", "--n", "15", "--per-family", "--cut", "1M", "--dir", str(tmp_path)]) == 0
    rows = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert rows and all(r["cut"] == 1_000_000 for r in rows)
    fams = {r["family"] for r in rows}
    assert fams == {"fact", "changed", "two_hop", "maths", "page", "code", "lookalike", "never"}
    assert all(sum(r["family"] == f for r in rows) <= 15 for f in fams)

    by = {p["id"]: p for p in h.probes}
    picked = [r for r in rows if r["family"] != "code"][:20]
    answers = tmp_path / "answers.jsonl"
    lines = [{"id": r["id"], "answer": perfect(at_cut(by[r["id"]], 1_000_000))} for r in picked]
    lines.append({"id": "hop-01", "answer": "Mombasa"})  # not askable at 1M: the second half is on day 74
    answers.write_text("\n".join(json.dumps(x) for x in lines) + "\n")
    assert main(["grade", "--answers", str(answers), "--cut", "1M", "--dir", str(tmp_path)]) == 0
    out = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [o["verdict"] for o in out[:-1]] == ["right"] * len(picked)
    assert out[-1]["verdict"] is None

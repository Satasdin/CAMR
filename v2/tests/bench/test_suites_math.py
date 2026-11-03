"""Maths: taking the answer out of a reply, LaTeX equivalence, AIME integers, MATH-500 and HARP pairs from fixture
rows. No network."""

from __future__ import annotations

import io
import json
import zipfile

import pytest

from engram.bench.suites import aime, harp, math500, mathcheck
from engram.bench.suites.mathcheck import equivalent, extract


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    import huggingface_hub
    import huggingface_hub.utils

    def no(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setenv("ENGRAM_DATASETS", str(tmp_path / "data"))
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", no)
    monkeypatch.setattr(huggingface_hub.utils, "get_session", no)


@pytest.mark.parametrize("reply,want", [
    ("so it is $\\boxed{\\frac{3}{4}}$.", "\\frac{3}{4}"),
    ("first \\boxed{1}, then \\boxed{\\left(2, \\frac{1}{2}\\right)}", "\\left(2, \\frac{1}{2}\\right)"),
    ("The final answer is 42.", "42"),
    ("Steps...\n**Answer:** $(1,2)$", "(1,2)"),
    ("<think>I guess \\boxed{2}</think>So \\boxed{7}", "7"),
    ("x \\boxed 5", "5"),
    ("17", "17"),
    ("A long working out with numbers 3 and 4 but no final answer marked anywhere in it at all.", None),
    ("<think>never finished", None),
])
def test_extract(reply, want):
    assert extract(reply) == want


@pytest.mark.parametrize("a,g", [
    ("\\frac{1}{2}", "0.5"),
    ("1/2", "\\dfrac{1}{2}"),
    ("\\frac12", "\\tfrac{1}{2}"),
    ("\\frac{\\sqrt{21}}{5}", "\\sqrt{21}/5"),
    ("3\\sqrt{2}", "\\sqrt{18}"),
    ("\\sqrt[3]{8}", "2"),
    ("288\\pi", "288 \\pi"),
    ("\\frac{\\pi}{2}", "\\pi/2"),
    ("\\left( 3, \\frac{\\pi}{2} \\right)", "(3,\\pi/2)"),
    ("(-\\sqrt{3}, \\sqrt{3})", "(-\\sqrt3,\\sqrt3)"),
    ("(-\\infty, 0) \\cup (1, \\infty)", "(1,\\infty)\\cup(-\\infty,0)"),
    ("x \\in [-2, 7]", "[-2,7]"),
    ("\\{1, 2\\}", "\\{2, 1\\}"),
    ("1, -2", "-2, 1"),
    ("\\begin{pmatrix} 1 \\\\ 2 \\end{pmatrix}", "\\begin{pmatrix}1\\\\2\\end{pmatrix}"),
    ("6 - 5i", "-5i + 6"),
    ("p - q", "-q + p"),
    ("x^2+2x+1", "(x+1)^2"),
    ("2^{10}", "1024"),
    ("e^2", "e^{2}"),
    (".35625", "\\frac{57}{160}"),
    ("10\\frac{2}{3}", "\\frac{32}{3}"),  # a mixed number
    ("\\$32,348", "32348"),
    ("11{,}110", "11110"),
    ("5\\text{ cm}", "5"),
    ("90^\\circ", "90"),
    ("25\\%", "25"),
    ("x = 5", "5"),
    ("\\text{Evelyn}", "Evelyn"),
    ("\\textbf{(C)}", "C"),
    ("\\infty", "\\infty"),
])
def test_equivalent(a, g):
    assert equivalent(a, g) and equivalent(g, a)


@pytest.mark.parametrize("a,g", [
    ("\\frac{1}{3}", "0.333"),  # close is not equal
    ("(3, \\frac{\\pi}{2})", "(3, \\frac{\\pi}{3})"),
    ("(6,31,-1)", "(6,-1,31)"),  # a tuple keeps its order
    ("(-\\sqrt{3}, \\sqrt{3})", "[-\\sqrt{3}, \\sqrt{3}]"),  # open is not closed
    ("(-\\infty, 0]", "(-\\infty, 0)"),
    ("173", "2^{4950}"),  # no float overflow
    ("\\text{Evelyn}", "Bob"),
    ("1, 2", "1, 2, 3"),
    ("{1}\\text{ and }{1}", "1"),  # words inside an answer are not multiplication
    ("7", "(7, 1)"),
    ("", "1"),
])
def test_not_equivalent(a, g):
    assert not equivalent(a, g)


def test_a_reply_never_runs_code(tmp_path):
    marker = tmp_path / "ran"
    evil = f"__import__('os').system('touch {marker}')"
    assert mathcheck.parse(evil) is None and mathcheck.to_sympy_text(evil) is None
    assert not equivalent(evil, "0") and not marker.exists()
    # an unknown run of letters becomes single letters multiplied, never a name Python could call
    assert mathcheck.to_sympy_text("exec(x)").replace(" ", "") == "e*x*e*c(x)"
    assert "open" not in mathcheck.to_sympy_text("open(chr(47))")


def _math_rows(tmp_path):
    rows = [{"problem": "What is $1+1$?", "solution": "So $\\boxed{2}$.", "answer": "2", "subject": "Algebra",
             "level": 1, "unique_id": "test/algebra/1.json"},
            {"problem": "Simplify $\\sqrt{8}$.", "solution": "$\\boxed{2\\sqrt2}$", "answer": "2\\sqrt{2}",
             "subject": "Prealgebra", "level": 2, "unique_id": "test/prealgebra/7.json"},
            {"problem": "Solve $x^2<1$.", "solution": "$\\boxed{(-1,1)}$", "answer": "(-1,1)",
             "subject": "Algebra", "level": 3, "unique_id": "test/algebra/9.json"}]
    p = tmp_path / "test.jsonl"
    p.write_text("\n".join(json.dumps(r) for r in rows) + "\n")
    return p


def test_math500_items_and_grades(tmp_path):
    items = math500.load(path=_math_rows(tmp_path))
    assert [i.id for i in items] == ["math500/algebra/1", "math500/prealgebra/7", "math500/algebra/9"]
    it = items[1]
    assert it.suite == "math500" and it.context == "" and it.meta["level"] == 2 and it.length_tokens > 0
    assert "\\boxed{}" in math500.prompt(it)
    assert math500.grade(it, "We get $\\boxed{\\sqrt{8}}$.") == "right"
    assert math500.grade(it, "We get $\\boxed{3}$.") == "wrong"
    assert math500.grade(it, "I'm not sure, I cannot determine it.") == "declined"
    assert math500.grade(items[2], "\\boxed{(-1, 1)}") == "right"
    assert math500.grade(items[2], "\\boxed{[-1, 1]}") == "wrong"


def test_math500_sample_is_seeded(tmp_path):
    p = _math_rows(tmp_path)
    assert [i.id for i in math500.sample(2, 3, path=p)] == [i.id for i in math500.sample(2, 3, path=p)]
    assert len(math500.sample(10, 0, path=p)) == 3


def _aime_paths(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    paths = {}
    for year, answers in ((2025, [70, 588, 16]), (2026, [277, 62, 9])):
        rows = [{"problem_idx": k + 1, "problem": f"Problem {k + 1} of {year}.", "answer": a}
                for k, a in enumerate(answers)]
        paths[year] = tmp_path / f"aime{year}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), paths[year])
    return paths


@pytest.mark.parametrize("text,want", [("70", 70), ("070", 70), ("$70$", 70), ("\\text{70}", 70), ("70.", 70),
                                       ("1,000", 1000), ("-70", -70), ("70.5", None), ("\\frac{1}{2}", None),
                                       (None, None)])
def test_aime_integer(text, want):
    assert aime.integer(text) == want


def test_aime_items_and_grades(tmp_path):
    paths = _aime_paths(tmp_path)
    items = aime.load(paths=paths)
    assert [i.id for i in items][:2] == ["aime/2025/01", "aime/2025/02"] and len(items) == 6
    it = items[0]
    assert it.answer == "70" and it.meta["year"] == 2025
    assert aime.grade(it, "... so the answer is $\\boxed{070}$") == "right"
    assert aime.grade(it, "The final answer is 70") == "right"
    assert aime.grade(it, "\\boxed{71}") == "wrong"
    assert aime.grade(it, "\\boxed{-70}") == "wrong"
    assert aime.grade(it, "I don't know.") == "declined"
    s = aime.sample(2, 0, paths=paths)
    assert len(s) == 4 and [i.id for i in s] == [i.id for i in aime.sample(2, 0, paths=paths)]


def _harp_zip(tmp_path):
    rows = []
    for k in range(6):
        rows.append({"year": "2001", "contest": "AMC_10A", "number": k + 1, "level": 2, "subject": "algebra",
                     "multiple_choice_only": False, "problem": f"Algebra problem {k}.",
                     "answer": f"${k}$", "solution_1": f"Worked solution {k}: so $\\boxed{{{k}}}$.",
                     "num_solutions": 1})
    for k in range(3):
        rows.append({"year": "1999", "contest": "AIME", "number": k + 1, "level": 5, "subject": "geometry",
                     "multiple_choice_only": False, "problem": f"Geometry problem {k}.",
                     "answer": "$\\frac{1}{2}$", "solution_1": "Draw it.", "num_solutions": 1})
    rows.append({**rows[0], "number": 99, "multiple_choice_only": True})  # left out: needs its choices
    rows.append({**rows[0], "number": 98, "solution_1": ""})  # left out: no worked solution
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("HARP.jsonl", "\n".join(json.dumps(r) for r in rows))
    p = tmp_path / "HARP.jsonl.zip"
    p.write_bytes(buf.getvalue())
    return p


def test_harp_problems_and_pairs(tmp_path):
    p = _harp_zip(tmp_path)
    probs = harp.problems(p)
    assert len(probs) == 9 and all(r["number"] < 98 for r in probs)
    pairs = harp.sample(10, 0, path=p)
    assert len(pairs) == 4  # 6 algebra -> 3 pairs, 3 geometry -> 1 pair
    seen = []
    for it in pairs:
        a, b_id = it.meta["first"]["id"], it.meta["b_id"]
        assert a != b_id and it.id == f"harp/{a}->{b_id}"
        seen += [a, b_id]
        kind = {r["id"]: (r["subject"], r["level"]) for r in probs}
        assert kind[a] == kind[b_id] == (it.meta["subject"], it.meta["level"])
        assert it.context[0].startswith("Problem: ") and "Worked solution" in it.context[0]
    assert len(seen) == len(set(seen))  # no problem twice
    assert [i.id for i in harp.sample(10, 0, path=p)] == [i.id for i in pairs]
    assert [i.id for i in harp.sample(10, 1, path=p)] != [i.id for i in pairs]
    assert {i.meta["subject"] for i in harp.sample(10, 0, subject="geometry", path=p)} == {"geometry"}
    assert len(harp.load(path=p)) == 4


def test_harp_grades(tmp_path):
    (it,) = harp.sample(1, 0, subject="geometry", path=_harp_zip(tmp_path))
    assert harp.grade(it, "so $\\boxed{0.5}$") == "right"
    assert harp.grade(it, "so $\\boxed{\\dfrac{1}{3}}$") == "wrong"
    assert harp.grade_first(it, "\\boxed{1/2}") == "right"
    assert harp.prompt(it, first=True).endswith(it.meta["first"]["problem"])

"""MemoryAgentBench and LongMemEval S from fixture rows: chunks in order, exact match, and the judge's prompt and
verdicts. No network."""

from __future__ import annotations

import json

import pytest

from engram.bench.suites import longmemeval as lme
from engram.bench.suites import memoryagentbench as mab


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    import huggingface_hub
    import huggingface_hub.utils

    def no(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setenv("ENGRAM_DATASETS", str(tmp_path / "data"))
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", no)
    monkeypatch.setattr(huggingface_hub.utils, "get_session", no)


def _meta(source, **kw):
    base = {"demo": "", "haystack_sessions": None, "keypoints": [], "previous_events": [], "qa_pair_ids": [],
            "question_dates": [], "question_ids": [], "question_types": [], "source": source}
    return {**base, **kw}


@pytest.fixture
def mab_paths(tmp_path):
    import pyarrow as pa
    import pyarrow.parquet as pq

    facts = "Here is a list of facts:\n" + "".join(f"{k}. Fact number {k} is about town {k}.\n" for k in range(400))
    facts += "400. The capital of Narnia is Cair Paravel.\n401. The capital of Narnia is Beruna.\n"
    cr = [{"context": facts, "questions": ["What is the capital of Narnia?", "What is fact 3 about?"],
           "answers": [["Beruna"], ["town 3"]],
           "metadata": _meta("factconsolidation_sh_6k", qa_pair_ids=["factconsolidation_sh_6k_no0",
                                                                     "factconsolidation_sh_6k_no1"])}]
    docs = "Document 1:\nThe Normans lived in Normandy in the 10th and 11th centuries. " * 30
    ar = [{"context": docs, "questions": ["When were the Normans in Normandy?"],
           "answers": [["10th and 11th centuries", "in the 10th and 11th centuries", "10th and 11th centuries"]],
           "metadata": _meta("ruler_qa1_197K")},
          {"context": "user: hi", "questions": ["What did I say?"], "answers": [["hi"]],
           "metadata": _meta("longmemeval_s*")}]
    paths = {}
    for split, rows in (("Conflict_Resolution", cr), ("Accurate_Retrieval", ar)):
        paths[split] = tmp_path / f"{split}.parquet"
        pq.write_table(pa.Table.from_pylist(rows), paths[split])
    return paths


def test_mab_items_share_their_chunks(mab_paths):
    items = mab.load(paths=mab_paths, chunk_tokens=512)
    assert [i.id for i in items] == ["mab/cr/00/000", "mab/cr/00/001", "mab/ar/00/000"]  # LongMemEval row left out
    a, b, c = items
    assert a.context is b.context and len(a.context) > 1  # one list for the questions on one context
    assert all(len(ch) <= 512 * 4 for ch in a.context)
    assert a.meta["kind"] == "factconsolidation" and "newer" in a.meta["instruction"]
    assert c.answer == ["10th and 11th centuries", "in the 10th and 11th centuries"]  # repeats dropped
    assert a.length_tokens > 1000 and a.meta["qa_pair_id"] == "factconsolidation_sh_6k_no0"
    assert len(mab.load(paths=mab_paths, skip=())) == 4
    assert mab.prompt(a).endswith("Question: What is the capital of Narnia?\nAnswer:")


def test_mab_chunks_join_back_to_the_context(mab_paths):
    import pyarrow.parquet as pq

    (row,) = pq.read_table(mab_paths["Conflict_Resolution"]).to_pylist()
    (item, _) = mab.load(("Conflict_Resolution",), paths=mab_paths, chunk_tokens=300)
    assert "".join(item.context) == row["context"]
    assert all(ch.endswith("\n") for ch in item.context[:-1])  # cut at line ends


@pytest.mark.parametrize("reply,verdict", [
    ("Beruna", "right"),
    ("beruna.", "right"),
    ("The Beruna", "right"),  # articles and punctuation don't count
    ("Answer: Beruna\nbecause fact 401 is newer.", "right"),
    ("Cair Paravel", "wrong"),
    ("It is Beruna, the newer fact.", "wrong"),  # exact match only (substring_match says yes)
    ("I don't know.", "declined"),
])
def test_mab_exact_match(mab_paths, reply, verdict):
    item = mab.load(paths=mab_paths)[0]
    assert mab.grade(item, reply) == verdict


def test_mab_scores_and_accepted_answers(mab_paths):
    a, _, c = mab.load(paths=mab_paths)
    assert mab.scores(a, "It is Beruna, the newer fact.") == {"exact_match": False, "substring_match": True}
    assert mab.grade(c, "In the 10th and 11th centuries.") == "right"
    assert mab.grade(c, "10th and 11th centuries") == "right"


def test_mab_sample_is_seeded(mab_paths):
    one = mab.sample(1, 0, paths=mab_paths)
    assert len(one) == 2 and [i.id for i in one] == [i.id for i in mab.sample(1, 0, paths=mab_paths)]
    assert {i.meta["row"] for i in one} == {0}


def _lme_file(tmp_path):
    def item(qid, kind, q, a, dates):
        sessions = [[{"role": "user", "content": f"Note from {d}."}, {"role": "assistant", "content": "  "}]
                    for d in dates]
        return {"question_id": qid, "question_type": kind, "question": q, "answer": a,
                "question_date": "2023/05/30 (Tue) 10:00", "answer_session_ids": ["s1"],
                "haystack_dates": dates, "haystack_session_ids": [f"s{k}" for k in range(len(dates))],
                "haystack_sessions": sessions}
    rows = [item("q1", "temporal-reasoning", "How many days ago did I move?", "18 days",
                 ["2023/05/20 (Sat) 02:21", "2023/05/01 (Mon) 09:00", "2023/05/01 (Mon) 08:00"]),
            item("q2_abs", "single-session-user", "What is my cat's name?", "You never mentioned a cat.",
                 ["2023/05/02 (Tue) 10:00"]),
            item("q3", "single-session-preference", "Any cocktail ideas?", "The user would prefer gin drinks.",
                 ["2023/05/03 (Wed) 10:00"]),
            item("q4", "knowledge-update", "Where do I work now?", "Nairobi", ["2023/05/04 (Thu) 10:00"]),
            {**item("q5", "multi-session", "How many hours?", 50, ["2023/05/05 (Fri) 10:00"])}]
    p = tmp_path / "lme.json"
    p.write_text(json.dumps(rows))
    return p


def test_lme_sessions_are_chunks_oldest_first(tmp_path):
    items = lme.load(file=_lme_file(tmp_path))
    it = items[0]
    assert it.id == "longmemeval/q1" and it.suite == "longmemeval" and len(it.context) == 3
    assert [c.splitlines()[0] for c in it.context] == ["[Chat session, 2023/05/01 (Mon) 08:00]",
                                                       "[Chat session, 2023/05/01 (Mon) 09:00]",
                                                       "[Chat session, 2023/05/20 (Sat) 02:21]"]
    assert it.context[0].splitlines()[1:] == ["user: Note from 2023/05/01 (Mon) 08:00."]  # empty turns dropped
    assert it.meta["session_ids"] == ["s2", "s1", "s0"] and not it.should_decline
    assert items[1].should_decline and items[4].answer == "50"
    assert "Current date: 2023/05/30 (Tue) 10:00" in lme.prompt(it)


def test_lme_judge_prompts_follow_the_kind(tmp_path):
    q1, q2, q3, q4, _ = lme.load(file=_lme_file(tmp_path))
    p = lme.judge_prompt(q1, "<think>hmm</think>19 days")
    assert "How many days ago did I move?" in p and "18 days" in p and "Response: 19 days" in p
    assert "off-by-one" in p and "<think>" not in p and p.endswith("yes or no.")
    assert "decline" in lme.judge_prompt(q2, "Mittens")
    assert "Note: You never mentioned a cat." in lme.judge_prompt(q2, "x")
    assert "Rubric: The user would prefer gin drinks." in lme.judge_prompt(q3, "Try a gimlet.")
    assert "older information" in lme.judge_prompt(q4, "Nairobi, after Kisumu")


@pytest.mark.parametrize("text,yes", [("yes", True), ("Yes.", True), ("**No**", False), ("no, it is wrong", False),
                                      ("The answer is yes", None), ("", None), (None, None)])
def test_parse_judge(text, yes):
    assert lme.parse_judge(text) is yes


def test_lme_verdicts(tmp_path):
    q1, q2, q3, q4, q5 = lme.load(file=_lme_file(tmp_path))
    assert lme.precheck(q4, "Nairobi.") == "right" and lme.grade(q4, "Answer: Nairobi") == "right"
    assert lme.precheck(q5, "50") == "right"
    assert lme.precheck(q4, "I think Nairobi") is None and lme.precheck(q2, "x") is None
    assert lme.precheck(q3, q3.answer) is None  # a rubric always goes to the judge
    with pytest.raises(lme.NeedsJudge):
        lme.grade(q1, "19 days")
    asked = []

    def judge(prompt):
        asked.append(prompt)
        return "yes"

    assert lme.grade(q1, "19 days", judge=judge) == "right" and len(asked) == 1
    assert lme.grade(q1, "I don't know.", judge=lambda p: "no") == "declined"
    assert lme.grade(q1, "40 days", judge=lambda p: "No") == "wrong"
    assert lme.grade(q2, "I don't have that information.", judge=lambda p: "yes") == "right_abstain"
    assert lme.grade(q2, "Mittens", judge=lambda p: "no") == "false_memory"
    assert lme.verdict_from_judge(q1, "x", "maybe") == "judge_error"


def test_lme_sample_per_kind(tmp_path):
    f = _lme_file(tmp_path)
    s = lme.sample(1, 0, file=f)
    assert len(s) == 5 and len({i.meta["kind"] for i in s}) == 5
    assert [i.id for i in s] == [i.id for i in lme.sample(1, 0, file=f)]

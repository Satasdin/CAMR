"""BABILong: the dataset's answer rule, stories read by byte range, and a seeded sample. No network: a made-up
task of 100 stories stands in for the Hub."""

from __future__ import annotations

import io
import json
import random

import pytest

from engram.bench.suites import babilong as b

PEOPLE = ("Mary", "John", "Daniel", "Sandra")
PLACES = ("bathroom", "bedroom", "garden", "hallway", "kitchen", "office")
VERBS = ("went to", "moved to", "travelled to", "journeyed to")


@pytest.fixture(autouse=True)
def offline(monkeypatch, tmp_path):
    import huggingface_hub
    import huggingface_hub.utils

    def no(*a, **k):
        raise AssertionError("tests must not touch the network")

    monkeypatch.setenv("ENGRAM_DATASETS", str(tmp_path / "data"))
    monkeypatch.setattr(huggingface_hub, "hf_hub_download", no)
    monkeypatch.setattr(huggingface_hub, "HfFileSystem", no)
    monkeypatch.setattr(huggingface_hub.utils, "get_session", no)


def _stories() -> list[dict]:
    """100 facts-only stories. Story 11 is story 10 plus two facts (as in bAbI); story 99 differs from the long
    files."""
    r = random.Random(7)
    out = []
    for i in range(100):
        facts = [f"{r.choice(PEOPLE)} {r.choice(VERBS)} the {r.choice(PLACES)}." for _ in range(r.randint(2, 6))]
        if i == 11:
            facts = out[10]["facts"] + ["Mary went back to the hallway.", "John moved to the office."]
        who = facts[-1].split()[0]
        last = [f for f in facts if f.startswith(who)][-1].split()[-1].rstrip(".")
        out.append({"facts": facts, "question": f"Where is {who}? ", "target": last})
    return out


def _noise(r: random.Random, n: int) -> list[str]:
    return [f"The {r.choice(['old', 'grey', 'quiet'])} ship sailed on for {r.randint(2, 900)} days." for _ in range(n)]


def _file(stories: list[dict], length: int, seed: int) -> bytes:
    """A long file: each story's facts spread, in order, through noise of uneven length."""
    r = random.Random(seed)
    rows = []
    for s in stories:
        noise = _noise(r, r.randint(length // 2, length * 2))
        at = sorted(r.randint(0, len(noise)) for _ in s["facts"])
        for k, (pos, f) in enumerate(zip(at, s["facts"])):
            noise.insert(pos + k, f)
        rows.append({"input": " ".join(noise), "question": s["question"], "target": s["target"]})
    return json.dumps(rows).encode()


@pytest.fixture
def made(tmp_path):
    stories = _stories()
    root = tmp_path / "babilong"
    zero = [{"input": " ".join(s["facts"]), "question": s["question"], "target": s["target"]} for s in stories]
    zero[99] = {"input": "Sandra went to the garden.", "question": "Where is Sandra? ", "target": "garden"}
    files = {"0k": json.dumps(zero).encode(), "4k": _file(stories, 6, 1), "16k": _file(stories, 20, 2),
             "64k": _file(stories, 60, 3)}
    for name in ("0k", "4k", "16k"):
        p = root / "data" / "qa1" / f"{name}.json"
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(files[name])
    opened, asked = [], []

    def opener(task, length):
        opened.append(length)
        return io.BytesIO(files[length]), len(files[length])

    def api(task, length, i):
        asked.append(i)
        return json.loads(files[length])[i]

    return {"root": root, "files": files, "opener": opener, "api": api, "opened": opened, "asked": asked}


LABELS = b.LABELS["qa1"]


@pytest.mark.parametrize("reply,ok", [
    ("The most recent location of Mary is kitchen.", True),
    ("kitchen", True),
    ("KITCHEN", True),
    ("Mary is in the kitchen right now", True),  # surrounding words are fine
    ("The kitchen. Before that, the office.", True),  # only the first sentence counts
    ("Mary is in the kitchen or the office.", False),  # two places named
    ("office", False),
    ("", False),
])
def test_dataset_rule(reply, ok):
    assert b.right("kitchen", reply, "Where is Mary?", LABELS) is ok


def test_labels_named_in_the_question_do_not_count():
    q = "Who did Fred give the apple to?"
    assert b.right("Jeff", "Fred gave the apple to Jeff.", q, b.LABELS["qa5"])
    assert not b.right("Jeff", "Bill, then Jeff.", q, b.LABELS["qa5"])
    assert b.right("bedroom", "The bedroom.", "What is the kitchen south of?", LABELS)


def test_two_part_targets_need_exactly_both():
    labels = ("apple", "football", "milk", "nothing")
    assert b.right("apple,milk", "The apple and the milk.", "What is Mary carrying?", labels)
    assert not b.right("apple,milk", "The apple.", "What is Mary carrying?", labels)


def test_verdicts():
    item = b._item("qa1", "4k", 0, {"input": "x", "question": "Where is Mary? ", "target": "kitchen"})
    assert b.grade(item, "The most recent location of Mary is kitchen.") == "right"
    assert b.grade(item, "<think>maybe the office</think>Kitchen.") == "right"
    assert b.grade(item, "The office.") == "wrong"
    assert b.grade(item, "I don't know where Mary is.") == "declined"


def test_byte_range_reads_land_on_every_story(made):
    st = b.Store(made["root"], opener=made["opener"], api=None)
    ref = st.reference("qa1")
    assert ref[99]["facts"] is None and ref[0]["facts"]  # the facts-only file disagrees on story 99
    data = made["files"]["64k"]
    rows = json.loads(data)
    for i in range(100):
        assert b.locate(io.BytesIO(data), len(data), i, ref) == rows[i]


def test_a_longer_story_is_not_taken_for_its_prefix(made):
    st = b.Store(made["root"], opener=made["opener"], api=None)
    rows = json.loads(made["files"]["64k"])
    assert b.which(rows[11], st.reference("qa1")) == [11]
    assert b.which(rows[10], st.reference("qa1")) == [10]


def test_stories_are_kept_and_the_api_fetches_only_unknown_ones(made):
    st = b.Store(made["root"], opener=made["opener"], api=made["api"])
    rows = json.loads(made["files"]["64k"])
    assert st.story("qa1", "64k", 5) == rows[5] and made["asked"] == []
    assert st.story("qa1", "64k", 99) == rows[99] and made["asked"] == [99]
    made["opened"].clear()
    again = b.Store(made["root"], opener=made["opener"], api=made["api"])
    assert again.story("qa1", "64k", 5) == rows[5] and made["opened"] == []  # read from disk now


def test_sample_is_seeded_and_the_same_stories_at_every_length(made):
    st = b.Store(made["root"], opener=made["opener"], api=made["api"])
    one = b.sample(3, seed=0, tasks=["qa1"], lengths=["4k", "16k", "64k"], store=st)
    two = b.sample(3, seed=0, tasks=["qa1"], lengths=["4k", "16k", "64k"], store=st)
    other = b.sample(3, seed=1, tasks=["qa1"], lengths=["4k", "16k", "64k"], store=st)
    assert [i.id for i in one] == [i.id for i in two]
    assert [i.id for i in one] != [i.id for i in other]
    assert len(one) == 9
    picks = {length: [i.meta["index"] for i in one if i.meta["length"] == length] for length in ("4k", "16k", "64k")}
    assert picks["4k"] == picks["16k"] == picks["64k"]
    it = one[0]
    assert it.suite == "babilong" and it.question.endswith("?") and it.answer in PLACES
    assert it.length_tokens == round(len(it.context) / 4) and it.meta["labels"] == list(LABELS)
    sizes = [i.length_tokens for i in one if i.meta["index"] == it.meta["index"]]
    assert sizes == sorted(sizes)  # longer lengths, longer contexts


def test_prompt_asks_in_the_task_format(made):
    st = b.Store(made["root"], opener=made["opener"], api=None)
    (it,) = b.load(["qa1"], ["4k"], [3], store=st)
    p = b.prompt(it)
    assert "The most recent location of" in p and p.endswith(f"Question: {it.question}") and "<context>" in p
    assert "<context>" not in b.prompt(it, with_context=False)

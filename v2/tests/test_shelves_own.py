"""The user's own shelves: make, rename, empty and remove them; nothing is destroyed."""

import json

import numpy as np
import pytest

from camr_engine import shelves


@pytest.fixture(autouse=True)
def fresh():
    shelves._set(shelves.DEFAULTS)
    yield
    shelves._set(shelves.DEFAULTS)


def test_a_new_memory_starts_with_the_four_shelves(tmp_path):
    assert [s.name for s in shelves.load(tmp_path)] == ["projects", "coding", "research", "personal"]


def test_a_shelf_made_is_kept_and_has_its_own_reach(tmp_path):
    s = shelves.add(tmp_path, "Caf\u00e9 Project", "the cafe website")
    assert (s.name, s.reach, s.label) == ("caf-project", "project:caf-project", "Caf\u00e9 Project")
    shelves._set(shelves.DEFAULTS)
    assert "caf-project" in [x.name for x in shelves.load(tmp_path)]
    assert shelves.shelf_of("project:caf-project").label == "Caf\u00e9 Project"


def test_two_shelves_cannot_share_a_name_and_a_name_has_limits(tmp_path):
    shelves.add(tmp_path, "Cafe")
    with pytest.raises(ValueError):
        shelves.add(tmp_path, "cafe")
    with pytest.raises(ValueError):
        shelves.add(tmp_path, "   ")
    with pytest.raises(ValueError):
        shelves.add(tmp_path, "x" * 31)


def test_a_name_that_makes_no_folder_name_still_gets_a_plain_one(tmp_path):
    assert shelves.add(tmp_path, "\u2615\u2615").name == "shelf"
    assert shelves.add(tmp_path, "\u2615").name == "shelf-2"


def test_rename_keeps_the_folder(tmp_path):
    shelves.rename(tmp_path, "coding", "My code")
    assert shelves.BY_NAME["coding"].label == "My code"
    assert shelves.BY_NAME["coding"].reach == "project:coding"


def test_removing_a_seeded_shelf_puts_its_notes_away(tmp_path):
    folder = tmp_path / "project" / "coding"
    folder.mkdir(parents=True)
    (folder / "index.json").write_text("{}")
    went = shelves.remove(tmp_path, "coding")
    assert not folder.exists()
    assert json.loads((tmp_path / "removed").joinpath(went.split("/removed/")[1], "index.json").read_text()) == {}
    assert "coding" not in shelves.BY_NAME
    shelves._set(shelves.DEFAULTS)
    assert "coding" not in [s.name for s in shelves.load(tmp_path)]


def test_emptying_the_global_shelf_keeps_the_shelf_and_the_notes(tmp_path):
    folder = tmp_path / "global"
    folder.mkdir()
    (folder / "room-000001.notes").write_bytes(b"x")
    went = shelves.empty(tmp_path, "projects")
    assert list(folder.iterdir()) == []
    assert "projects" in shelves.BY_NAME
    assert (tmp_path / "removed").joinpath(went.split("/removed/")[1], "room-000001.notes").read_bytes() == b"x"


def test_the_last_shelf_stays(tmp_path):
    for name in ("projects", "coding", "research"):
        shelves.remove(tmp_path, name)
    with pytest.raises(ValueError):
        shelves.remove(tmp_path, "personal")


def test_an_unknown_shelf_is_refused(tmp_path):
    for fn in (lambda: shelves.remove(tmp_path, "nope"), lambda: shelves.empty(tmp_path, "nope"),
               lambda: shelves.rename(tmp_path, "nope", "x")):
        with pytest.raises(KeyError):
            fn()


def test_ten_curated_shelves_ship_with_rules_and_corrections():
    got = {c["name"]: c for c in shelves.curated()}
    assert set(got) == {"agents", "coding", "debugging", "deployment", "design", "motion", "reasoning", "security",
                        "shelves", "writing"}
    for c in got.values():
        assert sum(n.startswith("RULE ") for n in c["notes"]) == 16
        assert sum(n.startswith("CORRECTION ") for n in c["notes"]) == 8
        assert c["about"]


def test_curated_shelves_are_generic_and_not_tuned_to_a_test():
    words = " ".join(" ".join(c["notes"]) for c in shelves.curated()).lower()
    for frozen in ("kahawa", "paper lantern", "argwings", "kilimani", "mandazi", "0722 410"):
        assert frozen not in words


def test_a_curated_shelf_is_called_has_its_own_reach_and_is_added_once(tmp_path):
    s, notes = shelves.add_curated(tmp_path, "coding")
    assert (s.name, s.reach, s.called, s.label) == ("curated-coding", "project:curated-coding", True, "Coding guide")
    again, _ = shelves.add_curated(tmp_path, "coding")
    assert again == s and [x.name for x in shelves.SHELVES].count("curated-coding") == 1
    assert len(notes) == 24
    shelves._set(shelves.DEFAULTS)
    assert shelves.load(tmp_path)[-1].called
    with pytest.raises(KeyError):
        shelves.add_curated(tmp_path, "nope")


def test_a_curated_note_is_never_counted_as_told():
    from camr_engine.revise import source_of

    class Vault:
        def moment_id(self, mid):
            return mid

        def get(self, nid):
            return type("N", (), {"tags": ["curated"]})()

    assert source_of(type("M", (), {"vault": Vault()})(), 0) == "curated"


class Says:
    """A reader that gives one fixed reply, or fails."""

    def __init__(self, reply):
        self.reply, self.prompts = reply, []

    def chat_ids(self, system, user):
        self.prompts.append((system, user))
        return [1]

    def generate(self, ids, max_tokens=None):
        from types import SimpleNamespace

        from camr_engine.live import current

        self.watched = current()
        if isinstance(self.reply, Exception):
            raise self.reply
        return SimpleNamespace(text=self.reply)


class Closest:
    """An embedder that says every text is closest to the Coding shelf."""

    def encode_one(self, text):
        return np.array([1.0, 0.0]) if "code" in text else np.array([0.0, 1.0])


def sorter():
    return shelves.Sorter(Closest())


@pytest.mark.parametrize("reply", ["Personal", "personal", " Personal.", "**Personal**", "Personal shelf"])
def test_the_reader_chooses_the_shelf_however_it_writes_the_name(reply):
    s = sorter()
    assert s.sort("My rent is KSh 25,000.", Says(reply)).name == "personal" and s.asked


@pytest.mark.parametrize("reply", ["", "I would say the kitchen", "ok", RuntimeError("no model")])
def test_without_a_shelf_name_from_the_reader_the_embedder_chooses(reply):
    s = sorter()
    want = s.sort("anything")  # the embedder's own choice
    assert s.sort("anything", Says(reply)) == want and not s.asked


def test_a_longer_shelf_name_is_read_before_a_shorter_one_it_starts_with(tmp_path):
    shelves.add(tmp_path, "Car")
    shelves.add(tmp_path, "Car parts")
    assert sorter().sort("A new clutch", Says("Car parts")).name == "car-parts"


def test_a_called_shelf_is_never_offered_or_taken(tmp_path):
    called = shelves.Shelf("guide", "Guide", "project:guide", "curated rules", called=True)
    shelves._set([*shelves.DEFAULTS, called])
    reader = Says("Guide")
    s = sorter()
    got = s.sort("Anything at all", reader)
    assert got.name != "guide" and not s.asked and "Guide" not in reader.prompts[0][0]


def test_the_note_is_cut_and_what_the_reader_writes_is_not_shown_as_the_answer():
    from camr_engine.live import Live, reporting

    reader = Says("Coding")
    with reporting(Live("test")):
        sorter().sort("x" * 5000, reader)
    assert reader.watched is None and len(reader.prompts[0][1]) <= shelves.PICK_CHARS + len("Note: ")


def test_a_memory_made_earlier_reads_the_four_shelves_as_described_now(tmp_path):
    (tmp_path / "shelves.json").write_text(json.dumps([
        {"name": "projects", "label": "Work", "reach": "global", "about": "rent and so on", "like": ["the rent"]},
        {"name": "garden", "label": "Garden", "reach": "project:garden", "about": "my garden", "like": ["roses"]}]))
    got = {s.name: s for s in shelves.load(tmp_path)}
    assert got["projects"].label == "Work" and got["projects"].about == shelves.DEFAULTS[0].about
    assert "the rent" not in got["projects"].like
    assert got["garden"].about == "my garden" and got["garden"].like == ("roses",)

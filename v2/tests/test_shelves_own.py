"""The user's own shelves: make, rename, empty and remove them; nothing is destroyed."""

import json

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

"""The vault: one Markdown note per moment that opens in Obsidian, doors that strengthen with use, strength that fades,
and nothing ever deleted. No model is loaded."""

from __future__ import annotations

import datetime as dt

import pytest

from engram.vault import FADE, INDEX, SHARE, TOGETHER, USE, Vault, split


def two(tmp_path):
    v = Vault(tmp_path / "vault", reach="project:tally")
    a = v.write("Monday 5 January 2026: Amina moved to Nakuru.", day=0, date=dt.date(2026, 1, 5), room=0, moment=0)
    b = v.write("Tuesday 6 January 2026: Amina's dog is called Simba.", day=1, date="2026-01-06", room=0, moment=1)
    return v, a, b


def test_a_note_is_a_markdown_file_with_front_matter_and_the_moments_words(tmp_path):
    v, a, _ = two(tmp_path)
    text = (tmp_path / "vault" / f"{a.id}.md").read_text()
    assert a.id == "project-tally-000000" and text.startswith("---\n")
    meta, body = split(text)
    assert {"id", "day", "date", "room", "reach", "tags", "strength", "pinned", "asleep", "links"} <= set(meta)
    assert meta["date"] == "2026-01-05" and "date: 2026-01-05\n" in text  # a date Obsidian shows as one
    assert meta["reach"] == "project:tally" and meta["pinned"] is False and meta["tags"] == []
    assert body == "Monday 5 January 2026: Amina moved to Nakuru.\n"
    assert v.read(a.id).text == "Monday 5 January 2026: Amina moved to Nakuru."


def test_doors_are_wikilinks_both_ways_and_strengthen_with_each_link(tmp_path):
    v, a, b = two(tmp_path)
    c = v.write("Paid the electricity bill.", day=2, room=1, moment=2)
    v.link(a.id, b.id)
    v.link(a.id, b.id)
    v.link(a.id, c.id)
    assert v.neighbours(a.id) == [(b.id, 2 * SHARE), (c.id, SHARE)]
    assert v.neighbours(b.id) == [(a.id, 2 * SHARE)]
    text = v.file(a.id).read_text()
    assert f'  - "[[{b.id}]]"\n  - "[[{c.id}]]"' in text  # strongest door first, as Obsidian writes links
    assert v.neighbours(a.id, 1) == [(b.id, 2 * SHARE)]


def test_using_notes_together_strengthens_them_and_the_doors_between_them(tmp_path):
    v, a, b = two(tmp_path)
    v.use([a.id, b.id], day=3)
    got = v.read(a.id)
    assert got.used == 3 and got.as_of == 3
    assert got.strength == pytest.approx((1 - FADE) ** 3 + USE, abs=1e-4)  # faded to day 3, then a use added
    assert v.neighbours(a.id) == [(b.id, TOGETHER)] and v.neighbours(b.id) == [(a.id, TOGETHER)]


def test_strength_fades_five_percent_a_day_but_pinned_notes_never_fade(tmp_path):
    v, a, b = two(tmp_path)
    v.pin(b.id)
    assert v.fade(10) == 1
    assert v.strength(a.id) == pytest.approx(0.95 ** 10, abs=1e-4)
    assert v.strength(b.id) == 1.0
    assert v.fade(10) == 0  # already up to date
    v.use([a.id], 12)
    v.fade(14)
    assert v.strength(a.id) == pytest.approx((0.95 ** 12 + USE) * 0.95 ** 2, abs=1e-3)


def test_nothing_is_deleted_a_faded_or_slept_note_keeps_its_words(tmp_path):
    v, a, _ = two(tmp_path)
    v.fade(400)
    v.update(a.id, asleep=True)
    got = v.read(a.id)
    assert got.faded and got.asleep and got.text == "Monday 5 January 2026: Amina moved to Nakuru."
    assert len(list((tmp_path / "vault").glob("*.md"))) == 2


def test_a_vault_reopens_from_its_files_with_or_without_its_index(tmp_path):
    v, a, b = two(tmp_path)
    v.link(a.id, b.id)
    v.tag(b.id, "core")
    v.save()
    assert (tmp_path / "vault" / INDEX).exists()
    again = Vault(tmp_path / "vault", reach="project:tally")
    assert len(again) == 2 and again.neighbours(a.id) == [(b.id, SHARE)]
    assert [n.id for n in again.notes(tag="core")] == [b.id] and again.get(a.id).text is None
    (tmp_path / "vault" / INDEX).unlink()
    third = Vault(tmp_path / "vault")
    assert third.get(b.id).tags == ["core"] and third.read(a.id).room == 0


def test_a_note_changed_by_hand_in_obsidian_is_read_again_and_its_own_properties_kept(tmp_path):
    v, a, b = two(tmp_path)
    v.save()
    v.file("persona").write_text("---\ntags:\n  - core\npinned: true\nmood: cheerful\naliases: [me, myself]\n---\n\n"
                                 "I am Ibrahim, and I build memory for small models.\n")
    note = v.file(a.id)
    note.write_text(note.read_text().replace("tags: []", "tags: [core, family]"))
    again = Vault(tmp_path / "vault", reach="project:tally")
    assert [n.id for n in again.notes(tag="core")] == ["persona", a.id]
    persona = again.read("persona")
    assert persona.pinned and persona.text == "I am Ibrahim, and I build memory for small models."
    again.link("persona", b.id)
    meta, _ = split(again.file("persona").read_text())
    assert meta["mood"] == "cheerful" and meta["aliases"] == ["me", "myself"] and meta["links"] == [f"[[{b.id}]]"]


def test_note_ids_are_file_names_never_paths(tmp_path):
    v, _, _ = two(tmp_path)
    for bad in ("../outside", "a/b", ".hidden", "x]]y", ""):
        with pytest.raises(ValueError):
            v.read(bad)
    with pytest.raises(ValueError):
        v.write("words", nid="../../etc/passwd")


def test_day_numbers_follow_the_dates_notes_were_written_with(tmp_path):
    v, _, _ = two(tmp_path)
    assert v.epoch == dt.date(2026, 1, 5) and v.day_of(dt.date(2026, 2, 4)) == 30
    empty = Vault(tmp_path / "empty")
    assert empty.day_of(dt.date(2026, 1, 1)) is None


def test_notes_without_a_moment_get_the_next_free_id(tmp_path):
    v = Vault(tmp_path / "vault")
    a = v.write("Standing fact one.", tags=["core"])
    b = v.write("Standing fact two.", tags=["#core"])
    assert (a.id, b.id) == ("m-note-0001", "m-note-0002") and v.get(b.id).tags == ["core"]


def test_a_note_deleted_by_hand_is_forgotten_and_never_breaks_a_change(tmp_path):
    v, a, b = two(tmp_path)
    v.file(a.id).unlink()
    assert v.fade(5) == 1 and a.id not in v and len(v) == 1  # found gone while fading: forgotten, not an error
    v.file(b.id).unlink()
    v.use([b.id], 6)
    assert b.id not in v and v.read(b.id) is None and v.update(b.id, asleep=True) is None and v.tag(b.id, "x") is None
    c = v.write("Paid the electricity bill.", day=7, moment=2)
    v.link_many(c.id, [a.id, b.id])  # doors to deleted notes are never made
    assert v.neighbours(c.id) == [] and v.read(c.id).links == {}


def test_a_moments_note_never_writes_over_other_words(tmp_path):
    v = Vault(tmp_path / "vault", reach="global")
    v.write("The fee is 1% rounded up.", day=0, moment=0, tags=["rule"])
    v.write("Bought a toyota vitz.", day=5, moment=0)  # moment 0 again: a moment the rooms lost, say
    kept = v.moved["global-000000"]
    assert v.read("global-000000").text == "Bought a toyota vitz."
    old = v.read(kept)
    assert old.text == "The fee is 1% rounded up." and old.tags == ["rule"] and old.moment is None
    assert old.extra["moved_from"] == "global-000000"
    v.write("Bought a toyota vitz.", day=5, moment=0)  # the same words: the same moment, nothing to keep aside
    assert len(v) == 2 and len(list((tmp_path / "vault").glob("*.md"))) == 2


def test_rescan_picks_up_notes_added_edited_and_deleted_while_the_vault_is_open(tmp_path):
    v, a, b = two(tmp_path)
    v.tag(a.id, "core")
    assert not v.rescan()  # nothing changed by hand
    f = v.file(a.id)
    f.write_text(f.read_text().replace("Amina moved to Nakuru.", "Amina moved to Mombasa."))
    before = v.version
    assert v.rescan() and v.version > before and "Mombasa" in v.read(a.id).text
    v.file("persona").write_text("---\ntags: [core]\n---\nI am Ibrahim.\n")
    v.write("Paid the electricity bill.", day=2, moment=2)  # the vault writing too does not hide a new file
    assert v.rescan() and [n.id for n in v.notes(tag="core")] == ["persona", a.id]  # by id
    v.file(b.id).unlink()
    assert v.rescan() and b.id not in v
    g = v.file(v.moment_id(2))
    g.write_text(g.read_text().replace("tags: []", "tags: [core]"))  # an edit in place to a note not yet core
    assert not v.rescan()  # the cheap look checks only core notes for edits
    assert v.rescan(full=True) and v.get(v.moment_id(2)).tags == ["core"]

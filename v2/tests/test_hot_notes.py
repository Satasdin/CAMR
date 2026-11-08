"""Notes as a hot cache (notes='hot'): a moment is kept as words in an asleep room, so telling writes no notes; a
question to an asleep room reads only its closest moments (or their best lines) and counts the room as wanted; a nap
wakes the most wanted rooms inside the disk budget, written whole from their words. Needs MLX for the fake reader."""

from __future__ import annotations

import pytest

from camr_engine.finder import LineIndex, cut
from camr_engine.swap import Tiers


def test_a_long_moment_is_cut_to_its_best_lines_and_a_short_one_is_read_whole():
    chat = "[2025-09-22, day 1] User: " + " ".join(f"Line {i} is about thing{i}." for i in range(12)) + \
        " The staging port is 8443."
    short = "[2025-09-23, day 2] User: The salt comes on Fridays."
    got = cut(LineIndex([chat, short]), "What port does staging use?", [chat, short], [0, 1], per=2)
    assert got[1] == short
    assert got[0].startswith("[2025-09-22, day 1] User: ") and "8443" in got[0] and got[0].count("…") == 1
    assert len(got[0]) < len(chat) / 3


def test_hot_notes_tell_as_words_and_write_no_notes(tmp_path):
    pytest.importorskip("mlx")
    from test_core import make

    m = make(tmp_path / "memory", tiers=Tiers(disk_bytes=10**9), vault=True, notes="hot")
    a = m.remember("Amina moved to Nakuru.", 0)
    b = m.remember("Amina adopted a dog called Simba.", 1)
    assert a.room == b.room and b.start == a.tokens  # moments still gather in rooms, as words
    assert m.tiers.sleeping == {a.room} and m.rooms.disk_bytes() == 0
    assert m.vault.get(m.vault.moment_id(a.mid)).asleep
    assert m.asleep_read == "skip"


def test_a_question_to_an_asleep_room_reads_only_its_closest_moments_and_wants_the_room(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, make

    m = make(tmp_path / "memory", tiers=Tiers(disk_bytes=10**9), notes="hot")
    m.remember("Amina moved to Nakuru.", 0)
    m.remember("Amina adopted a dog called Simba.", 1)
    _, rest = m.prompt(TODAY, "Where does Amina live?")
    m.answer("Where does Amina live?", TODAY)
    call = m.reader.calls[-1]
    assert call.offset == m.notebook.p and call.ids == m.words([0, 1]) + rest  # no room read as words
    assert m.tiers.wanted == {0: 1}


def test_a_nap_wakes_the_most_wanted_rooms_inside_the_budget_and_their_notes_go_on_the_desk(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, make

    m = make(tmp_path / "memory", tiers=Tiers(disk_bytes=10**9), notes="hot")
    m.remember("Amina moved to Nakuru.", 0)
    m.remember("Amina adopted a dog called Simba.", 1)
    m.answer("Where does Amina live?", TODAY)
    assert m.wake_wanted() == [0] and not m.tiers.is_asleep(0) and not m.tiers.wanted
    assert m.rooms.disk_bytes() == m.rooms.room_bytes(0) > 0
    rec = m.recall("Where does Amina live?")
    assert rec.laid == [0] and not rec.asleep
    later = m.remember("Amina's dog Simba is two years old.", 2)  # an awake room takes new notes as before
    assert later.room == 0 and m.rooms.disk_bytes() == m.rooms.room_bytes(0)


def test_a_room_too_big_for_what_is_left_of_the_budget_stays_asleep(tmp_path):
    pytest.importorskip("mlx")
    from test_core import TODAY, make

    m = make(tmp_path / "memory", tiers=Tiers(disk_bytes=1), notes="hot")
    m.remember("Amina moved to Nakuru.", 0)
    m.answer("Where does Amina live?", TODAY)
    assert m.wake_wanted() == [] and m.tiers.is_asleep(0) and m.tiers.wanted == {0: 1}


def test_hot_notes_need_tiers(tmp_path):
    pytest.importorskip("mlx")
    from test_core import make

    with pytest.raises(ValueError, match="needs tiers"):
        make(tmp_path / "memory", notes="hot")


def test_the_users_reply_to_an_answer_is_read_with_the_question_it_corrected():
    from camr_engine.finder import replies, speaker

    said = ["[2025-09-24, day 3] User: What's our fee on a KES 3,456 payment?",
            "[2025-09-24, day 3] Assistant: That comes to 1% of 3,456, so KES 34.56.",
            "[2025-09-24, day 3] User: Not quite, here's how our fee works: 1%, rounded up to the next 5 shillings.",
            "[2025-09-24, day 3] User: Is the oven on?",
            "[2025-09-24, day 3] User: Thanks."]
    assert speaker(said[1]) == "Assistant" and speaker("no stamp") is None
    assert replies(said.__getitem__, [0, 3], moments=len(said)) == [2]  # never the wrong answer between them
    assert replies(said.__getitem__, [3], moments=len(said)) == []  # no answer after it: nothing to follow
    assert replies(said.__getitem__, [5, 0], top=1, moments=len(said) + 1) == []  # only the top ones are looked at


def test_an_asleep_room_is_read_as_its_lines_that_share_a_word_with_the_question():
    from camr_engine.finder import room_lines

    room = ["[2025-10-01, day 9] User: The Upepo Wind event is at the Lavington church hall. Bring chairs.",
            "[2025-10-02, day 10] User: Lavington church hall parks 38 cars. The roof leaks.",
            "[2025-10-03, day 11] User: Nothing to do with it."]
    got = room_lines(LineIndex(room), "How many cars can park at the Lavington hall?", room, [0, 1, 2], most=2)
    assert set(got) == {0, 1} and "38 cars" in got[1] and "Nothing" not in "".join(got.values())
    assert all(t.startswith("[2025-10-0") for t in got.values())
    assert room_lines(LineIndex(room), "cars", room, [0, 1, 2], skip=[1]) == {}


def test_a_moment_holding_code_is_never_cut():
    code = "[2025-10-01, day 9] User: Here is the helper.\n```python\n" + "\n".join(
        f"def f{i}(x):\n    return x + {i}" for i in range(8)) + "\n```\nUse it for fees."
    assert cut(LineIndex([code]), "Write a fee function", [code], [0], per=2) == {0: code}


def test_the_newest_line_naming_the_same_thing_is_found_from_an_older_one():
    from camr_engine.finder import newest

    told = ["[2025-10-08, day 38] User: Note: the production app port is 8010.",
            "[2025-10-09, day 39] User: The staging app port is 9000.",  # a look-alike: two words in common
            "[2025-10-24, day 54] User: Changed the production app port to 8000 on Mama Njeri's request.",
            "[2025-11-10, day 71] User: Changed the production app port to 8200. Let's add the tasting booking.",
            "[2025-11-11, day 72] User: The production team ate kaimati."]  # no value: never the newest version
    ix = LineIndex(told)
    assert newest(ix, "What is the production app port now?", [0]) == [3]
    assert newest(ix, "What is the production app port now?", [3]) == []  # nothing newer
    assert newest(ix, "Who ate kaimati?", [4]) == []  # its best line gives no value

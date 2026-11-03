"""Memory reach: session, project, agent and global, each its own folder; a session recalls the best room over every
reach it reads, and with memory off it is the plain model. A reach folder is open once per process and locked against
other processes. The Session tests use the fake reader (needs MLX)."""

from __future__ import annotations

import fcntl
import json
import os
import time

import pytest

from engram.reach import KINDS, Reach, ReachBusy, opened


def test_each_reach_is_its_own_folder_under_one_root(tmp_path):
    assert Reach("global").path(tmp_path) == tmp_path / "global"
    assert Reach("project", "tally").path(tmp_path) == tmp_path / "project" / "tally"
    assert Reach("agent", "coder").path(tmp_path) == tmp_path / "agent" / "coder"
    assert Reach("session", "20261104-0100-ab12").path(tmp_path) == tmp_path / "session" / "20261104-0100-ab12"
    assert KINDS == ("session", "project", "agent", "global")


def test_a_reach_reads_and_writes_as_a_label():
    assert Reach.parse("project:tally") == Reach("project", "tally")
    assert Reach("project", "tally").label == "project:tally"
    assert Reach.parse("global").label == "global" and str(Reach("agent", "coder")) == "agent:coder"


def test_a_reach_name_is_never_a_path():
    for kind, name in (("project", "../etc"), ("session", "a/b"), ("agent", ""), ("global", "x"), ("team", "x")):
        with pytest.raises(ValueError):
            Reach(kind, name)


# -- sessions, with the fake reader


def session(tmp_path, reader=None, embedder=None, **kw):
    pytest.importorskip("mlx")
    from test_core import FakeEmbedder, FakeReader

    from engram.reach import Session

    settings = {"root": tmp_path / "engram", "name": "s1", "log": False, "room_tokens": 400, "join": 0.2, **kw}
    return Session(reader or FakeReader(), embedder or FakeEmbedder(), **settings)


def test_a_session_reads_its_own_reach_and_the_global_one_and_writes_to_its_own(tmp_path):
    s = session(tmp_path)
    assert [r.label for r in s.reaches] == ["session:s1", "global"] and s.home == Reach("session", "s1")
    s.remember("I asked for the invoice template today.", 0)
    s.remember("Amina moved to Nakuru.", 0, to="global")
    assert len(s.memory().rooms.moments) == 1 and len(s.memory("global").rooms.moments) == 1
    assert (tmp_path / "engram" / "session" / "s1" / "vault").is_dir()
    assert (tmp_path / "engram" / "global" / "vault" / "global-000000.md").exists()
    notebooks = {id(m.notebook) for m in s.memories.values()}
    assert len(notebooks) == 1  # the header is read once for every reach


def test_a_question_takes_the_best_room_over_every_reach(tmp_path):
    from test_core import TODAY

    s = session(tmp_path)
    s.remember("I asked for the invoice template today.", 0)
    s.remember("Amina moved to Nakuru.", 0, to="global")
    m, rec = s.choose("Where does Amina live now?")
    assert rec.reach == "global" and m is s.memory("global") and rec.room == 0
    s.answer("Where does Amina live now?", TODAY)
    call = s.reader.calls[-1]
    assert call.offset == s.notebook.p + len("Amina moved to Nakuru.\n") and s.last.reach == "global"
    assert s.choose("Which invoice template did I ask for?")[1].reach == "session:s1"


def test_a_project_session_reads_the_project_and_the_global_memory(tmp_path):
    s = session(tmp_path, project="tally", reads=("project", "global"), writes="project")
    assert [r.label for r in s.reaches] == ["project:tally", "global"]
    s.remember("The fee is 1% rounded up to the next 5 shillings.", 3)
    assert s.memory("project:tally").vault.get("project-tally-000000").reach == "project:tally"
    with pytest.raises(ValueError):
        session(tmp_path, reads=("project",))  # a project reach needs the project's name


def test_memory_off_is_the_plain_model_with_nothing_read_or_kept(tmp_path):
    from test_core import TODAY

    s = session(tmp_path)
    s.remember("Amina moved to Nakuru.", 0, to="global")
    s.switch(False)
    assert s.remember("Something said while memory was off.", 1) is None
    reply = s.answer("Where does Amina live?", TODAY)
    call = s.reader.calls[-1]
    head, rest = s.memory().prompt(TODAY, "Where does Amina live?")
    assert call.cache is None and call.ids == head + rest and reply.text == "ok"
    assert len(s.memory().rooms.moments) == 0 and s.last is None
    assert reply.metrics.tier is None and reply.metrics.read_bytes == 0
    s.switch(True)
    s.answer("Where does Amina live?", TODAY)
    assert s.reader.calls[-1].cache is not None


def test_one_core_from_every_reach_goes_on_every_desk(tmp_path):
    from test_core import TODAY

    s = session(tmp_path, core=True)
    s.memory("global").vault.write("I am Ibrahim.", tags=["core"], pinned=True)
    s.memory().vault.write("This session is about invoices.", tags=["core"])
    s.remember("Amina moved to Nakuru.", 0, to="global")
    s.answer("Where does Amina live?", TODAY)
    c = len("I am Ibrahim.\n") + len("This session is about invoices.\n")
    assert s.core.tokens == c and s.reader.calls[-1].offset == s.notebook.p + c + len("Amina moved to Nakuru.\n")
    s.remember("I asked for the invoice template today.", 1)
    s.answer("Which invoice template did I ask for?", TODAY)
    assert s.last.reach == "session:s1"
    assert s.reader.calls[-1].offset == s.notebook.p + c + len("I asked for the invoice template today.\n")
    assert set(s.state()["reaches"]) == {"session:s1", "global"} and s.state()["core"]["tokens"] == c
    assert all(m.core is None for m in s.memories.values())  # the core is the session's, laid by it on every desk


def test_a_session_with_no_memories_yet_answers_from_an_empty_desk(tmp_path):
    from test_core import TODAY

    s = session(tmp_path)
    s.answer("Where does Amina live?", TODAY)
    assert s.reader.calls[-1].offset == s.notebook.p and s.last.room is None


# -- sharing a reach, closing, and what each answer records


def test_two_sessions_share_one_global_memory_and_never_cut_each_others_notes(tmp_path):
    from test_core import TODAY, FakeEmbedder, FakeReader, desk_values, numbers

    reader, embedder = FakeReader(), FakeEmbedder()
    s1 = session(tmp_path, reader, embedder)
    s1.remember("Amina moved to Nakuru.", 0, to="global")
    s1.remember("Amina adopted a dog called Simba.", 1, to="global")
    s2 = session(tmp_path, reader, embedder, name="s2")
    g = s1.memory("global")
    assert s2.memory("global") is g and s2.notebook is s1.notebook  # one Memory per reach folder in a process
    s2.remember("Bought a toyota vitz.", 2, to="global")
    assert [m.mid for m in g.rooms.moments] == [0, 1, 2]
    rec = s1.recall("Where does Amina live?")
    p = s1.notebook.p
    assert desk_values(rec.desk)[p:].tolist() == numbers("Amina moved to Nakuru.") + numbers(
        "Amina adopted a dog called Simba.")
    s1.answer("What is the dog called?", TODAY)
    s1.close()
    assert opened(tmp_path / "engram" / "global") is g  # still open: s2 reads it
    s2.close()
    assert opened(tmp_path / "engram" / "global") is None
    s3 = session(tmp_path, name="s3")
    again = s3.memory("global")
    assert [m.text for m in again.rooms.moments] == ["Amina moved to Nakuru.", "Amina adopted a dog called Simba.",
                                                     "Bought a toyota vitz."]
    assert [again.vault.read(again.vault.moment_id(i)).text for i in range(3)] == [m.text for m in again.rooms.moments]
    for room in again.rooms.rooms:
        assert again.rooms.file(room.rid).stat().st_size == room.tokens * again.rooms.token_bytes
    s3.close()


def test_a_shared_reach_is_saved_as_soon_as_a_moment_is_kept(tmp_path):
    s = session(tmp_path)
    s.remember("Amina moved to Nakuru.", 0, to="global")
    saved = json.loads((tmp_path / "engram" / "global" / "index.json").read_text())
    assert [m["text"] for m in saved["moments"]] == ["Amina moved to Nakuru."]
    s.close()


def test_a_reach_open_in_another_process_is_refused_and_nothing_is_left_held(tmp_path):
    folder = tmp_path / "engram" / "global"
    folder.mkdir(parents=True)
    fd = os.open(folder / ".lock", os.O_RDWR | os.O_CREAT)  # another open of the lock: as another process holds it
    fcntl.flock(fd, fcntl.LOCK_EX)
    try:
        with pytest.raises(ReachBusy):
            session(tmp_path)
        assert opened(tmp_path / "engram" / "session" / "s1") is None  # the reach it did open was let go
    finally:
        os.close(fd)
    with session(tmp_path) as s:
        assert opened(folder) is s.memory("global")
    assert opened(folder) is None


def test_a_reach_open_here_with_another_model_is_refused(tmp_path):
    from test_core import FakeEmbedder, FakeReader

    s = session(tmp_path, FakeReader(), FakeEmbedder())
    other = FakeReader()
    other.repo = "another"
    with pytest.raises(ValueError):
        session(tmp_path, other, s.embedder, name="s2")
    s.close()


def test_closing_a_session_keeps_everything_it_remembered(tmp_path):
    s = session(tmp_path, project="tally", reads=("project",), writes="project")
    s.remember("The fee is 1% rounded up to the next 5 shillings.", 3, tags=["rule"])
    s.close()
    again = session(tmp_path, project="tally", reads=("project",), writes="project")
    m = again.memory()
    assert [x.text for x in m.rooms.moments] == ["The fee is 1% rounded up to the next 5 shillings."]
    assert m.vault.get("project-tally-000000").tags == ["rule"]
    b = again.remember("Mama Njeri's Kitchen opens at 7.", 4)
    assert b.mid == 1 and m.vault.read("project-tally-000000").text.startswith("The fee is 1%")
    again.close()


def test_the_wait_counts_the_choosing_and_the_record_counts_every_reach(tmp_path):
    from test_core import TODAY, FakeEmbedder

    class Slow(FakeEmbedder):
        def encode_one(self, text, *, is_query=False):
            if is_query:
                time.sleep(0.03)
            return super().encode_one(text, is_query=is_query)

    s = session(tmp_path, embedder=Slow())
    s.remember("I asked for the invoice template today.", 0)
    s.remember("Amina moved to Nakuru.", 0, to="global")
    reply = s.answer("Where does Amina live now?", TODAY)
    r = reply.metrics
    assert r.retrieval_ms["choose"] >= 30 and r.first_word_s >= 0.03 and r.total_s >= r.first_word_s
    assert r.history_tokens == sum(m.history_tokens() for m in s.memories.values())
    assert r.disk_bytes == sum(m.folder_bytes() for m in s.memories.values())
    s.close()


def test_the_session_meter_holds_every_answer_memory_on_or_off(tmp_path):
    from test_core import TODAY

    s = session(tmp_path)
    s.remember("Amina moved to Nakuru.", 0, to="global")
    on = s.answer("Where does Amina live?", TODAY)
    s.switch(False)
    off = s.answer("Where does Amina live?", TODAY)
    assert [r.reach for r in s.meter.records] == ["global", None]
    assert on.metrics is s.meter.records[0] and off.metrics is s.meter.records[1] and on.metrics.tier == "ssd"
    s.close()


def test_every_reach_of_a_session_shares_one_ram_budget(tmp_path):
    from test_core import TODAY

    s = session(tmp_path, tiers={"ram_bytes": 900})
    s.remember("Amina moved to Nakuru.", 0, to="global")  # 23 tokens: 736 bytes of notes
    s.remember("Paid the bill.", 1)  # 15 tokens: 480 bytes
    s.answer("Where does Amina live?", TODAY)
    s.answer("Did I pay the bill?", TODAY)
    home, g = s.memory(), s.memory("global")
    assert home.tiers.pool is g.tiers.pool is s.pool and s.pool.budget == 900
    assert list(home.tiers.hot) == [0] and not g.tiers.hot and home.tiers.ram_bytes() <= 900
    s.close()

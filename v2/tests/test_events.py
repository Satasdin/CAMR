"""The event log: one JSON line per event, and which nodes count as used. No model is loaded."""

from __future__ import annotations

import numpy as np

from camr_engine.events import USED, EventLog, used


def test_events_are_appended_one_line_each_and_read_back(tmp_path):
    log = EventLog(tmp_path / "memory" / "events.jsonl")
    log.write("remember", moment=0, room=0, day=0, tokens=21, new_room=True)
    log.write("answer", question="Where does Amina live?", nodes=[0], used=[0], words=["Nak", "uru"])
    events = log.read()
    assert [e["type"] for e in events] == ["remember", "answer"]
    assert events[1]["words"] == ["Nak", "uru"] and "at" in events[0]
    assert len((tmp_path / "memory" / "events.jsonl").read_text().splitlines()) == 2


def test_a_node_is_used_when_it_draws_its_share_of_the_desk():
    looks = np.array([[0.30, 0.02, 0.01],   # each row: one written word; each column: a node on the desk
                      [0.40, 0.05, 0.02],
                      [0.20, 0.06, 0.01]])
    share, use = used(looks, [7, 3, 9])
    assert abs(sum(share) - 1) < 1e-3
    assert use == [7, 3] and share[1] >= USED > share[2]


def test_no_looks_means_nothing_used():
    share, use = used(np.zeros((0, 2), dtype=np.float32), [1, 2])
    assert use == [] and share == [0.0, 0.0]

"""The agent with the engine as its memory: a reach session over the fake reader of test_core (MLX arrays, no model
loaded). A step reads the room its task is about from the SSD, then from RAM; a finished run is remembered in the
reach its persona writes to; a swarm's agents each get their own agent reach and share one RAM budget.

These run in a process of their own (test_agentic_engine.py starts it), because MLX work done in the test process
changes how later tests' MLX arrays meet their threads; run directly, they are skipped."""

from __future__ import annotations

import json
import os
from types import SimpleNamespace

import pytest

from engram.agentic.brain import EngineBrain, Prompt, last_line, lean
from engram.models import Reply

pytestmark = pytest.mark.skipif(os.environ.get("ENGRAM_ENGINE_CASES") != "1",
                                reason="runs in its own process, from test_agentic_engine.py")
pytest.importorskip("mlx")

from test_core import FakeEmbedder, FakeReader  # noqa: E402


class ToolReader(FakeReader):
    """The fake reader, answering from a script."""

    def __init__(self, replies):
        super().__init__()
        self.replies = list(replies)

    def generate(self, ids, cache=None, max_tokens=None):
        super().generate(ids, cache, max_tokens)
        text = self.replies.pop(0) if self.replies else "Done."
        pieces = [text[i:i + 5] for i in range(0, len(text), 5)]
        return Reply(text, 0.001, 100.0, len(ids), len(pieces), pieces)


def session(tmp_path, reader, **kw):
    from engram.reach import Session

    settings = {"root": tmp_path / "engram", "name": "20261104-010000-ab12", "project": "kitchen",
                "reads": ("session", "project", "global"), "writes": "project", "log": False, "room_tokens": 400,
                "join": 0.2, "tiers": {}, "metrics": True, **kw}
    return Session(reader, FakeEmbedder(), **settings)


def test_a_step_reads_the_room_its_task_is_about_from_the_ssd_then_from_ram(tmp_path):
    s = session(tmp_path, ToolReader([]))
    brain = EngineBrain(s)
    kept = brain.keep("The fee helper is fee(amount) in fees.py: 1% rounded up to the next 5 shillings.")
    assert kept["reach"] == "project:kitchen" and kept["moment"] == 0
    p = Prompt("Be careful.", "Task: use the fee helper", [], ask="Which fee helper rounds up to 5 shillings?")
    t = brain.think(p)
    m = t.memory
    assert m["reach"] == "project:kitchen" and m["room"] == 0 and m["tier"] == "ssd" and m["read_bytes"] > 0
    assert m["closest"] == [0] and set(m["seconds"]) >= {"choose", "fetch", "desk"}
    assert m["metrics"]["context_tokens"] > 0 and m["metrics"]["history_tokens"] > 0
    assert brain.think(p).memory["tier"] == "ram"  # the room stayed hot
    (proj,) = [r for r in brain.reaches() if r["reach"] == "project:kitchen"]
    assert proj["writes"] and proj["rooms"][0]["hot"] and not proj["rooms"][0]["asleep"]
    assert brain.moment("project:kitchen", 0)["text"].endswith("next 5 shillings.")
    assert brain.moment("project:kitchen", 7) is None
    brain.close()


def test_a_finished_run_is_remembered_where_its_persona_writes(tmp_path):
    from engram.agentic.gate import Gate
    from engram.agentic.loop import Run
    from engram.agentic.personas import BUILT_IN
    from engram.agentic.tools import Toolbox
    from engram.agentic.workspace import Workspace

    root = tmp_path / "kitchen"
    root.mkdir()
    write = json.dumps({"name": "write_file", "arguments": {"path": "fees.py", "content": "def fee(amount):\n"
                                                                                         "    return 10\n"}})
    reader = ToolReader([f"<tool_call>\n{write}\n</tool_call>", "I wrote fee() in fees.py."])
    brain = EngineBrain(session(tmp_path, reader))
    gate = Gate()
    r = Run("t-1", "Write the fee helper", brain=brain, tools=Toolbox(Workspace(root), gate), persona=BUILT_IN[0],
            gate=gate, workspace="kitchen")
    r.execute()
    assert r.state == "done" and (root / "fees.py").exists()
    assert r.kept["reach"] == "project:kitchen"
    m = brain.session.memory("project:kitchen")
    assert "Names defined: fee" in m.rooms.moments[r.kept["moment"]].text
    assert r.turns[1]["memory"]["reach"] in ("project:kitchen", "session:20261104-010000-ab12", "global")
    brain.close()


def test_a_swarms_agents_each_get_their_own_reach_and_share_one_ram_budget(tmp_path):
    from engram.agentic.desk import engine_brains
    from engram.swap import Pool

    app = SimpleNamespace(reader=FakeReader(), embedder=FakeEmbedder(), memory=None, models=None)
    make = engine_brains(app, root=tmp_path / "engram")
    pool = Pool(64 << 20)
    brains = [make({"memory": True, "session": None, "project": None, "agent": f"swarm-a{i}", "reads": ["agent"],
                    "writes": "agent", "pool": pool}) for i in (1, 2)]
    for i, b in enumerate(brains, 1):
        assert [r.label for r in b.session.reaches] == [f"agent:swarm-a{i}"]
        assert all(m.tiers.pool is pool for m in b.session.memories.values())
        assert (tmp_path / "engram" / "agent" / f"swarm-a{i}").is_dir()
    plain = make({"memory": False})
    assert not plain.memory_on and plain.reader is app.reader
    for b in brains:
        b.close()
    assert engine_brains(SimpleNamespace()) is None  # a fixture: no model, no runs


def test_the_last_event_is_read_from_the_end_and_each_word_keeps_its_hardest_look(tmp_path):
    log = tmp_path / "events.jsonl"
    rows = [{"type": "remember", "moment": i} for i in range(3000)]
    rows.append({"type": "agent", "nodes": [4, 9], "looks": [[0.01, 0.3], [0.2, 0.05], []]})
    log.write_text("".join(json.dumps(r) + "\n" for r in rows))
    got = last_line(log)
    assert got["type"] == "agent" and lean(got["looks"], got["nodes"]) == [[9, 0.3], [4, 0.2], [None, 0.0]]
    assert last_line(tmp_path / "missing.jsonl") is None


def test_a_reach_already_open_stays_on_its_pool_and_a_fix_is_kept_where_asked(tmp_path):
    from engram.agentic.brain import is_fix
    from engram.agentic.desk import engine_brains
    from engram.swap import Pool

    app = SimpleNamespace(reader=FakeReader(), embedder=FakeEmbedder(), memory=None, models=None)
    make = engine_brains(app, root=tmp_path / "engram")
    first, second = Pool(64 << 20), Pool(64 << 20)
    a = make({"memory": True, "session": None, "project": "kitchen", "agent": "coder", "reads": ["project"],
              "writes": "project", "pool": first})
    b = make({"memory": True, "session": None, "project": "kitchen", "agent": "swarm-a1",
              "reads": ["agent", "project"], "writes": "agent", "pool": second})
    shared = a.session.memory("project")
    assert b.session.memory("project") is shared and shared.tiers.pool is first  # never moved to the second
    assert b.session.memory("agent").tiers.pool is second and b.session.pool is second
    kept = b.keep("Your fix in src/total.py (kept): you changed `x + 1` to `x + fee(x)`.", to="project")
    assert kept["reach"] == "project:kitchen"
    text = shared.rooms.moments[kept["moment"]].text
    assert text.startswith("[") and is_fix(text)
    assert shared.tiers.load(kept["room"]).tier == "ssd" and shared.tiers.load(kept["room"]).tier == "ram"
    assert (shared.tiers, kept["room"]) in first.hot  # hot in its own pool, and counted in no other
    assert not [k for k in second.hot if k[0] is shared.tiers]
    b.close()
    a.close()

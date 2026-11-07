"""The Code agent's parts, with no model: the workspace keeps every path inside its folder, the parser finds every
call in a reply, nothing runs at the gate without a yes, a command runs with a cleaned environment and a time limit,
skills load on demand, personas save and switch, and the memory gutter follows the lines. The loop runs on a scripted
fake brain."""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

import pytest

from camr_engine.agentic import marks as gutter
from camr_engine.agentic.brain import Prompt, Thought
from camr_engine.agentic.gate import Gate
from camr_engine.agentic.loop import Run
from camr_engine.agentic.parse import calls, prose
from camr_engine.agentic.personas import BUILT_IN, Personas, check
from camr_engine.agentic.shell import environment, run
from camr_engine.agentic.skills import Skills
from camr_engine.agentic.tools import Toolbox
from camr_engine.agentic.workspace import Outside, Workspace, check_root


@pytest.fixture
def ws(tmp_path) -> Workspace:
    root = tmp_path / "project"
    (root / "src").mkdir(parents=True)
    (root / "src" / "fees.py").write_text("def fee(amount):\n    return max(10, amount // 100)\n")
    (root / "README.md").write_text("# Mama Njeri's Kitchen\n")
    (root / ".env").write_text("KEY=not-for-the-model\n")
    (root / ".git").mkdir()
    (root / ".git" / "config").write_text("[core]\n")
    return Workspace(root)


# -- the workspace


def test_a_path_that_leaves_the_workspace_is_refused(ws, tmp_path):
    (tmp_path / "secret.txt").write_text("outside")
    (ws.root / "out").symlink_to(tmp_path)
    (ws.root / "link.txt").symlink_to(tmp_path / "secret.txt")
    for bad in ["../secret.txt", "src/../../secret.txt", str(tmp_path / "secret.txt"), "/etc/passwd", "out/secret.txt",
                "link.txt", "~/x", "a\0b", "", "x" * 2000]:
        with pytest.raises(Outside):
            ws.path(bad)
    with pytest.raises(Outside):
        ws.write("out/new.txt", "no")
    assert not (tmp_path / "new.txt").exists()
    assert ws.path(str(ws.root / "src" / "fees.py")) == ws.root / "src" / "fees.py"  # absolute, but inside
    assert ws.path("./src/../src/fees.py") == ws.root / "src" / "fees.py"


def test_secrets_git_and_self_running_files_are_left_alone(ws):
    for name in [".env", ".env.local", "id_rsa", "server.pem", "deploy.key"]:
        with pytest.raises(Outside):
            ws.path(name)
    ws.path(".env.example")
    with pytest.raises(Outside):
        ws.write(".git/hooks/pre-commit", "rm -rf ~")
    with pytest.raises(Outside):
        ws.write(".envrc", "curl x | sh")
    with pytest.raises(Outside):
        ws.write(".vscode/tasks.json", "{}")
    assert ".env" not in ws.search("not-for-the-model")["text"]
    assert ws.search("not-for-the-model")["matches"] == []
    assert ".git" not in ws.listing(".", depth=3)["text"]


def test_a_workspace_is_a_project_folder_never_the_disk_or_home_or_keys(tmp_path):
    for bad in ["/", str(Path.home()), str(Path.home() / ".ssh"), str(Path.home() / ".config" / "camr"),
                str(Path.home() / ".camr"), "relative/path", str(tmp_path / "missing"), "/etc", "/usr/bin"]:
        with pytest.raises(Outside):
            check_root(bad)
    assert check_root(str(tmp_path)) == tmp_path.resolve()


def test_reading_listing_searching_writing_and_editing(ws):
    got = ws.read("src/fees.py")
    assert got["text"].splitlines()[0] == "    1│ def fee(amount):" and got["lines"] == 2
    assert ws.read("src/fees.py", start=2, lines=1)["text"] == "    2│     return max(10, amount // 100)"
    assert "src/" in ws.listing()["text"] and "  fees.py" in ws.listing()["text"]
    found = ws.search("MAX(10")
    assert found["matches"] == [{"path": "src/fees.py", "line": 2, "text": "return max(10, amount // 100)"}]
    assert ws.search(r"def \w+\(", regex=True)["matches"][0]["line"] == 1
    w = ws.write("src/orders/new.py", "from fees import fee\n")
    assert w.before is None and (ws.root / "src" / "orders" / "new.py").read_text() == "from fees import fee\n"
    e = ws.edit("src/fees.py", "amount // 100", "-(-amount // 100)")
    assert e.before.count("amount // 100") == 1 and "-(-amount // 100)" in e.after
    with pytest.raises(Outside):
        ws.edit("src/fees.py", "not there", "x")
    ws.write("twice.txt", "a\na\n")
    with pytest.raises(Outside):
        ws.edit("twice.txt", "a", "b")
    (ws.root / "blob.bin").write_bytes(b"\0\1\2")
    with pytest.raises(Outside):
        ws.read("blob.bin")
    assert {"src/fees.py", "src/orders/new.py"} <= {f["path"] for f in ws.tree() if not f["dir"]}
    assert any(f["path"] == ".env" and f["secret"] for f in ws.tree())


def test_a_write_keeps_the_file_mode_and_leaves_no_temporary_file(ws):
    p = ws.root / "run.sh"
    p.write_text("echo 1\n")
    p.chmod(0o755)
    ws.write("run.sh", "echo 2\n")
    assert p.read_text() == "echo 2\n" and p.stat().st_mode & 0o777 == 0o755
    assert not list(ws.root.glob(".camr-*"))


# -- the parser


def test_every_call_in_a_reply_is_found_in_order():
    text = ('I will read it.\n<tool_call>\n{"name": "read_file", "arguments": {"path": "a.py"}}\n</tool_call>\n'
            '<tool_call>\n{"name": "search", "arguments": "{\\"pattern\\": \\"fee\\"}"}\n</tool_call>')
    got = calls(text)
    assert [(c.name, c.args) for c in got] == [("read_file", {"path": "a.py"}), ("search", {"pattern": "fee"})]
    assert text[got[0].start:got[0].end].startswith("<tool_call>") and prose(text) == "I will read it."
    xml = ("<tool_call>\n<function=write_file>\n<parameter=path>\nb.py\n</parameter>\n<parameter=content>\nx = 1\n"
           "</parameter>\n</function>\n</tool_call>")
    c = calls(xml)[0]
    assert (c.name, c.args, c.form) == ("write_file", {"path": "b.py", "content": "x = 1"}, "xml")
    assert calls("<function=list_files>\n</function>")[0].name == "list_files"


def test_thinking_and_plain_json_in_an_answer_are_not_calls():
    assert calls('<think>maybe <tool_call>{"name": "run_shell", "arguments": {}}</tool_call></think>Done.') == []
    answer = 'The config is {"name": "x", "port": 8000}.'
    assert calls(answer, known={"read_file"}) == [] and calls(answer) == []
    bare = '{"name": "read_file", "arguments": {"path": "a.py"}}'
    assert calls(bare, known={"read_file"})[0].args == {"path": "a.py"}
    many = '<tool_call>{"name": "list_files", "arguments": {}}</tool_call>' * 9
    assert len(calls(many)) == 4


# -- the gate


def test_nothing_runs_at_the_gate_without_a_yes():
    gate = Gate()
    got = {}

    def ask():
        got["a"] = gate.ask("shell", {"command": "ls"}, owner="r1", label="t")

    th = threading.Thread(target=ask)
    th.start()
    while not gate.waiting():
        time.sleep(0.005)
    (w,) = gate.waiting("r1")
    assert w["what"] == {"command": "ls"} and w["decision"] is None and gate.waiting("r2") == []
    gate.decide(w["id"], False)
    th.join(2)
    assert got["a"].decision == "denied" and not got["a"].allowed
    with pytest.raises(KeyError):
        gate.decide(w["id"], True)  # answered already: a second answer changes nothing
    assert gate.ask("shell", {"command": "ls"}, owner="r1", wait_s=0.05).decision == "timed out"
    stop = threading.Event()
    stop.set()
    assert gate.ask("shell", {"command": "ls"}, owner="r1", cancel=stop).decision == "stopped"


def test_the_action_that_runs_is_the_one_that_was_shown():
    gate = Gate()
    what = {"command": "echo shown"}
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("a", gate.ask("shell", what, owner="r")))
    th.start()
    while not gate.waiting():
        time.sleep(0.005)
    what["command"] = "rm -rf /"  # changed after it was shown
    gate.decide(gate.waiting()[0]["id"], True)
    th.join(2)
    assert out["a"].allowed and out["a"].what == {"command": "echo shown"}


# -- the shell


def test_a_command_runs_in_the_workspace_with_a_clean_environment(ws, monkeypatch):
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test-not-real")
    assert "ANTHROPIC_API_KEY" not in environment()
    seen = []
    r = run("pwd; echo key=${ANTHROPIC_API_KEY:-none}; echo oops >&2; exit 3", ws.root, on_output=seen.append)
    assert r.code == 3 and str(ws.root) in r.output and "key=none" in r.output and "oops" in r.output
    assert "".join(seen) == r.output and "exit code 3" in r.summary()


def test_a_command_past_its_time_or_stopped_is_stopped_with_what_it_started(ws):
    t = time.perf_counter()
    r = run("sleep 30 & sleep 30", ws.root, timeout_s=1)
    assert r.timed_out and r.code is None and time.perf_counter() - t < 8
    stop = threading.Event()
    threading.Timer(0.2, stop.set).start()
    r = run("sleep 30", ws.root, cancel=stop)
    assert r.stopped and "stopped" in r.summary()
    r = run("yes | head -c 400000", ws.root)
    assert r.truncated and len(r.output) <= 200_100 and r.output.endswith("y\n")
    assert "200,000 characters left out" in r.output


# -- skills and personas


def test_skills_are_listed_by_one_line_and_loaded_whole_on_demand(tmp_path):
    folder = tmp_path / "skills"
    (folder / "release").mkdir(parents=True)
    (folder / "release" / "SKILL.md").write_text("---\nname: release-notes\ndescription: How to write release "
                                                 "notes\n---\n# Release notes\nList every change.\n")
    (folder / "style.md").write_text("# House style\nShort docstrings in plain words.\n")
    (folder / "bad name.md").write_text("x")
    s = Skills(folder)
    assert [x.name for x in s.all()] == ["release-notes", "style"]
    assert s.index() == "- release-notes: How to write release notes\n- style: House style"
    assert s.load("release-notes") == "# Release notes\nList every change."
    with pytest.raises(KeyError):
        s.load("missing")
    assert Skills(tmp_path / "none").all() == []


def test_personas_come_built_in_save_switch_and_reset(tmp_path):
    ps = Personas(tmp_path / "personas.json")
    assert [p.id for p in ps.all()] == [p.id for p in BUILT_IN]
    reviewer = ps.get("reviewer")
    assert not reviewer.allows("write_file") and reviewer.allows("read_file") and ps.get("coder").allows("run_shell")
    ps.save({"id": "coder", "name": "Coder", "system": "Be brief.", "reads": ["project"], "writes": "project"})
    assert ps.get("coder").system == "Be brief." and ps.get("coder").built_in
    ps.save({"id": "ops", "name": "Ops", "system": "Run the deploy.", "reads": ["global"], "writes": "agent",
             "tools": ["run_shell"]})
    assert ps.get("ops").reads == ["agent", "global"]
    ps.delete("coder")
    assert ps.get("coder").system == BUILT_IN[0].system
    for bad in [{"id": "../x", "name": "x", "system": "s", "reads": ["global"]},
                {"id": "x", "name": "x", "system": "s", "reads": ["team"]},
                {"id": "x", "name": "", "system": "s", "reads": ["global"]},
                {"id": "x", "name": "x", "system": "", "reads": ["global"]}]:
        with pytest.raises(ValueError):
            check(bad)


# -- the memory gutter


def test_lines_written_while_leaning_on_memory_are_marked():
    content = "from fees import fee\n\ndef total(x):\n    return x + fee(x)\n"
    args = json.dumps({"name": "write_file", "arguments": {"path": "t.py", "content": content}})
    text = f"<tool_call>\n{args}\n</tool_call>"
    pieces = [text[i:i + 4] for i in range(0, len(text), 4)]
    k = text.index("fee(x)") // 4  # the piece that wrote fee(x) looked hard at moment 7
    lean = [[3, 0.02]] * len(pieces)
    lean[k] = [7, 0.31]
    memory = {"lean": lean, "fixes": [], "reach": "project:kitchen", "room": 2}
    c = calls(text)[0]
    got = gutter.leaning(text, pieces, memory, c.start, c.end, content, c.form)
    assert list(got) == [4] and got[4]["kind"] == "used" and got[4]["node"] == 7 and got[4]["room"] == 2
    memory["fixes"] = [7]
    assert gutter.leaning(text, pieces, memory, c.start, c.end, content, c.form)[4]["kind"] == "fix"
    assert gutter.leaning(text, pieces, None, c.start, c.end, content, c.form) == {}


def test_marks_follow_their_lines_and_a_persons_change_is_marked_yours(tmp_path):
    m = gutter.Marks(tmp_path / "marks.json")
    v1 = "a\nb\nc\n"
    m.wrote("x.py", None, v1, {2: {"kind": "used", "node": 1}})
    v2 = "new\na\nb\nc\n"
    assert m.get("x.py", v2) == {3: {"kind": "used", "node": 1}}  # changed outside: the mark moved down a line
    got, pairs = m.saved("x.py", v1, "a\nb\nC\n")
    assert got["lines"] == {2: {"kind": "used", "node": 1}, 3: {"kind": "yours"}} and pairs == [("c", "C")]
    assert gutter.Marks(tmp_path / "marks.json").get("x.py", "a\nb\nC\n")[3] == {"kind": "yours"}
    assert m.saved("never.py", "", "mine\n") == ({"text": "mine\n", "lines": {}}, [])


# -- the loop, on a scripted brain


class FakeBrain:
    """Replies in turn from a script; with ``memory`` each reply leans hard on moment 5 while writing its middle."""

    def __init__(self, replies, memory=False, label="fake-1.7b"):
        self.replies, self.memory_on, self.label = list(replies), memory, label
        self.prompts: list[Prompt] = []
        self.kept: list[str] = []
        self.closed = False

    def think(self, p: Prompt) -> Thought:
        self.prompts.append(p)
        text = self.replies.pop(0) if self.replies else "Done."
        pieces = [text[i:i + 3] for i in range(0, len(text), 3)] or [""]
        mem = None
        if self.memory_on:
            lean = [[5, 0.4] if len(pieces) // 3 <= i < 2 * len(pieces) // 3 else [2, 0.01]
                    for i in range(len(pieces))]
            mem = {"reach": "project:kitchen", "room": 1, "tier": "ssd", "read_bytes": 57_000_000, "nodes": [2, 5],
                   "used": [5], "closest": [2], "seconds": {"choose": 0.001, "fetch": 0.018, "desk": 0.002},
                   "lean": lean, "fixes": []}
        return Thought(text, pieces, 0.07, 0.5, 900, len(pieces), 80.0, mem)

    def keep(self, text, to=None, source="model"):
        self.kept.append(text)
        self.kept_to = to
        return {"reach": "project:kitchen", "moment": 9, "room": 1} if self.memory_on else None

    def moment(self, reach, mid):
        return {"reach": reach, "moment": mid, "room": 1, "day": 3, "text": "fee() rounds up to 5 shillings"}

    def reaches(self):
        return [{"reach": "agent:coder", "kind": "agent", "rooms": [{"id": 0, "tokens": 120, "bytes": 1,
                                                                         "hot": True, "asleep": False}]}]

    def close(self):
        self.closed = True


def call(name, **args) -> str:
    return f"<tool_call>\n{json.dumps({'name': name, 'arguments': args})}\n</tool_call>"


def make_run(ws, replies, *, memory=False, gate=None, persona="coder", marks=None, **kw) -> Run:
    gate = gate or Gate()
    p = next(x for x in BUILT_IN if x.id == persona)
    tools = Toolbox(ws, gate, allows=p.allows)
    return Run("t-1", "Add a total() helper that uses fee()", brain=FakeBrain(replies, memory), tools=tools, persona=p,
               gate=gate, workspace=ws.name, marks=marks, **kw)


def test_a_run_reads_writes_and_answers_and_the_model_reads_every_result_back(ws, tmp_path):
    content = "from fees import fee\n\n\ndef total(x):\n    return x + fee(x)\n"
    r = make_run(ws, [call("read_file", path="src/fees.py") + call("list_files"),
                      call("write_file", path="src/total.py", content=content),
                      "I added total() in src/total.py."], memory=True, marks=gutter.Marks(tmp_path / "m.json"))
    r.execute()
    assert r.state == "done" and r.answer == "I added total() in src/total.py." and r.steps == 3
    assert (ws.root / "src" / "total.py").read_text() == content
    second = r.brain.prompts[1].user
    assert '[1] read_file(path="src/fees.py")' in second and "def fee(amount):" in second
    assert "[2] list_files()" in second
    assert r.brain.prompts[0].ask == r.task and "edit_file" in {t["function"]["name"] for t in r.brain.prompts[0].tools}
    kinds = [t["kind"] for t in r.turns]
    assert kinds == ["you", "model", "call", "call", "model", "call", "model", "answer", "kept"]
    wrote = [t for t in r.turns if t["kind"] == "call" and t["tool"] == "write_file"][0]
    assert wrote["diff"]["before"] is None and wrote["marks"]  # leaned on moment 5 while writing
    assert all(m["kind"] == "used" and m["node"] == 5 for m in wrote["marks"].values())
    assert "Files written: src/total.py" in r.brain.kept[0] and "Names defined: total" in r.brain.kept[0]
    tracks = {s["track"] for s in r.trace}
    assert tracks == {"model", "read_file", "list_files", "write_file"}
    ticks = [t for s in r.trace if s["track"] == "model" for t in s["ticks"]]
    assert {"ssd", "words", "used"} <= {t["kind"] for t in ticks}


def test_a_shell_call_waits_for_the_person_and_a_denied_one_never_runs(ws):
    gate = Gate()
    marker = ws.root / "ran.txt"
    r = make_run(ws, [call("run_shell", command=f"touch {marker.name}"), "I could not run it."], gate=gate)
    r.start()
    while not gate.waiting():
        time.sleep(0.005)
    assert r.state == "waiting" and not marker.exists()
    (ask,) = gate.waiting(r.id)
    assert ask["what"] == {"command": "touch ran.txt", "cwd": str(ws.root), "timeout_s": 120}
    gate.decide(ask["id"], False)
    r.thread.join(5)
    assert r.state == "done" and not marker.exists()
    failed = [t for t in r.turns if t["kind"] == "call"][0]
    assert not failed["ok"] and "did not run" in failed["text"] and failed["ask"]["decision"] == "denied"
    assert "failed:\nthe user did not run this command (denied)" in r.brain.prompts[1].user


def test_an_allowed_command_runs_once_and_its_output_reaches_the_terminal(ws):
    gate = Gate()
    r = make_run(ws, [call("run_shell", command="echo hello > out.txt; cat out.txt"), "Done."], gate=gate)
    r.start()
    while not gate.waiting():
        time.sleep(0.005)
    gate.decide(gate.waiting()[0]["id"], True)
    r.thread.join(5)
    assert (ws.root / "out.txt").read_text() == "hello\n"
    snap = r.snapshot()
    assert "$ echo hello > out.txt; cat out.txt" in "".join(snap["term"]) and "hello" in "".join(snap["term"])
    assert snap["term_next"] == len(snap["term"]) and r.snapshot(snap["term_next"])["term"] == []
    assert [s for s in snap["trace"] if s["track"] == "shell"][0]["waited"]


def test_a_stopped_run_denies_what_it_waited_for(ws):
    gate = Gate()
    r = make_run(ws, [call("run_shell", command="touch never.txt")], gate=gate)
    r.start()
    while not gate.waiting():
        time.sleep(0.005)
    r.stop()
    r.thread.join(5)
    assert r.state == "stopped" and gate.waiting() == [] and not (ws.root / "never.txt").exists()


def test_a_persona_without_a_tool_cannot_call_it_and_unknown_tools_fail_softly(ws):
    r = make_run(ws, [call("write_file", path="x.py", content="x"), call("format_disk"), "Read only."],
                 persona="reviewer")
    r.execute()
    assert not (ws.root / "x.py").exists()
    texts = [t["text"] for t in r.turns if t["kind"] == "call"]
    assert texts[0].startswith("there is no tool 'write_file' here") and "format_disk" in texts[1]
    names = {t["function"]["name"] for t in r.brain.prompts[0].tools}
    assert names == {"read_file", "list_files", "search"}


def test_a_run_stops_after_its_steps_and_waits_while_a_benchmark_measures(ws):
    r = make_run(ws, [call("list_files")] * 5, max_steps=3)
    r.execute()
    assert r.state == "done" and r.steps == 3 and "stopped after 3 steps" in r.answer
    flag = {"on": True}
    r = make_run(ws, ["Done."], measuring=lambda: {"job": "longhaul"} if flag["on"] else None)
    r.start()
    time.sleep(0.1)
    assert r.state == "measuring" and r.brain.prompts == []
    flag["on"] = False
    r.thread.join(5)
    assert r.state == "done"


def test_a_failing_brain_fails_the_run_with_its_reason(ws):
    r = make_run(ws, [])
    r.brain.think = lambda p: (_ for _ in ()).throw(RuntimeError("out of memory"))
    r.execute()
    assert r.state == "failed" and "out of memory" in r.error and r.turns[-1]["kind"] == "error"


def test_runs_take_turns_on_the_model(ws):
    lock = threading.Lock()
    inside, most = [0], [0]

    class Slow(FakeBrain):
        def think(self, p):
            inside[0] += 1
            most[0] = max(most[0], inside[0])
            time.sleep(0.05)
            inside[0] -= 1
            return super().think(p)

    runs = [make_run(ws, [call("list_files"), "Done."], model_lock=lock) for _ in range(3)]
    for r in runs:
        r.brain = Slow([call("list_files"), "Done."])
        r.start()
    for r in runs:
        r.thread.join(5)
    assert most[0] == 1 and all(r.state == "done" for r in runs)


# -- review fixes: the gate shows what runs, nothing floods the prompt or the page, nothing freezes the app


def test_git_and_self_running_files_are_refused_in_any_case_and_with_invisible_letters(ws):
    before = (ws.root / ".git" / "config").read_text()
    for bad in [".GIT/config", ".Git/hooks/pre-commit", ".gIT/config", ".g‌it/config", ".ENVRC", ".EnvRc",
                ".VSCode/Tasks.json", "src/.Git/config"]:
        with pytest.raises(Outside):
            ws.write(bad, "[core]\n\tfsmonitor = touch hooked.txt\n")
    assert (ws.root / ".git" / "config").read_text() == before
    bare = ws.root / "sub"
    bare.mkdir()
    for pointer in ["sub/.git", "sub/.GIT"]:  # a new file named .git would point git at another folder
        with pytest.raises(Outside):
            ws.write(pointer, "gitdir: /tmp/elsewhere\n")
    assert not any(p.name.lower() == ".git" for p in bare.iterdir())
    ws.write(".github/workflows/ci.yml", "on: push\n")  # near the names, but not them
    ws.write("gitignore-notes.md", "x\n")


def test_a_workspace_neither_holds_nor_sits_inside_the_apps_own_folders(tmp_path):
    keep = tmp_path / "camr" / "code"
    keep.mkdir(parents=True)
    (tmp_path / "project").mkdir()
    for bad in [tmp_path, tmp_path / "camr", keep]:
        with pytest.raises(Outside):
            check_root(str(bad), [keep])
    inner = keep / "inside"
    inner.mkdir()
    with pytest.raises(Outside):
        Workspace(inner, [keep])
    assert check_root(str(tmp_path / "project"), [keep]) == (tmp_path / "project").resolve()


def test_a_regular_expression_that_backtracks_stops_and_the_app_keeps_running(ws, monkeypatch):
    from camr_engine.agentic import workspace as wsmod

    monkeypatch.setattr(wsmod, "SEARCH_S", 0.4)
    (ws.root / "slow.txt").write_text("a" * 40 + "!\n")
    beats, stop = [], threading.Event()

    def beat():
        while not stop.is_set():
            beats.append(time.perf_counter())
            time.sleep(0.01)

    th = threading.Thread(target=beat)
    th.start()
    t = time.perf_counter()
    got = ws.search("(a|aa)+$", regex=True)
    took = time.perf_counter() - t
    stop.set()
    th.join()
    assert got["slow"] and got["more"] and "too slow" in got["text"] and took < 2.0
    assert len(beats) >= 10  # the other thread kept running all along
    assert ws.search("(a+)+$", "slow.txt", regex=True)["matches"] == []
    with pytest.raises(Outside):
        ws.search("(", regex=True)


def test_a_big_file_comes_back_in_clipped_pieces_with_where_to_read_on(ws):
    from camr_engine.agentic.tools import READ_LINES, RESULT_LIMIT

    (ws.root / "big.txt").write_text("".join(f"line {i} " + "x" * 90 + "\n" for i in range(1, 3001)))
    (ws.root / "min.js").write_text("var a=1;" * 20_000)
    tools = Toolbox(ws, Gate())
    got = tools.run("read_file", {"path": "big.txt"}, owner="r")
    assert got.ok and len(got.text) <= RESULT_LIMIT and "read on with start_line=" in got.text
    last = int(got.text.split("start_line=")[1].rstrip(")"))
    assert 1 < last <= READ_LINES + 1
    assert tools.run("read_file", {"path": "big.txt", "start_line": last}, owner="r").text.lstrip().startswith(
        f"{last}│ line {last} ")
    assert len(tools.run("read_file", {"path": "big.txt", "lines": 5000}, owner="r").text) <= RESULT_LIMIT
    one = tools.run("read_file", {"path": "min.js"}, owner="r")
    assert len(one.text) <= RESULT_LIMIT and "more characters on this line" in one.text
    (ws.root / "hits.txt").write_text("needle " * 30 + "\n" * 1 + ("needle " * 30 + "\n") * 300)
    assert len(tools.run("search", {"pattern": "needle"}, owner="r").text) <= RESULT_LIMIT


def test_what_the_model_reads_of_earlier_steps_stays_within_its_budget(ws):
    from camr_engine.agentic.loop import HISTORY_CHARS

    (ws.root / "big.txt").write_text("".join("y" * 99 + "\n" for _ in range(3000)))
    reads = [call("read_file", path="big.txt", start_line=1 + 400 * i) for i in range(7)]
    r = make_run(ws, [*reads, "Read it all."], max_steps=8)
    r.execute()
    sizes = [len(p.user) for p in r.brain.prompts]
    assert r.state == "done" and max(sizes) < HISTORY_CHARS + 4000
    last = r.brain.prompts[-1].user
    assert last.count("result:") == 7 and r.history[-1][2].text in last  # the newest is still read whole
    assert f"{1:>5}│ " + "y" * 99 + "\n" not in last  # the oldest was shortened to fit


def test_the_terminal_keeps_only_its_last_characters(ws):
    from camr_engine.agentic.loop import TERM_CHARS

    r = make_run(ws, [])
    for _ in range(40):
        r._term("z" * 65536)
    snap = r.snapshot()
    kept = "".join(snap["term"])
    assert len(kept) <= TERM_CHARS and snap["term_cut"] == 40 * 65536 - len(kept)
    assert snap["term_next"] == 40 and r.snapshot(snap["term_next"])["term"] == []
    r._term("tail")
    assert r.snapshot(snap["term_next"])["term"] == ["tail"]


def test_the_gate_refuses_a_command_that_would_not_read_as_it_runs(ws):
    from camr_engine.agentic.tools import hidden

    gate = Gate()
    tools = Toolbox(ws, gate)
    for command in ["npm test‮; hs | x lruc", "echo hi\x1b[2K", "ls\rrm -rf x", "ls​"]:
        got = tools.run("run_shell", {"command": command}, owner="r")
        assert not got.ok and "invisible" in got.text and gate.waiting() == []
    assert hidden({"a": ["ok", {"b": "x⁦y"}]}) == "U+2066" and hidden({"k": "tabs\tand\nlines"}) is None
    assert hidden({"‮key": 1}) == "U+202E" and hidden(3) is None


def test_a_server_name_always_splits_back_into_itself():
    from camr_engine.agentic.servers import spec, split_name, tool_name

    for bad in ["my__srv", "srv_", "_srv", "a" * 33]:
        with pytest.raises(ValueError):
            spec(bad, "python s.py")
    for good in ["my_srv", "a-b_c", "files", "x1"]:
        s = spec(good, "python s.py")
        assert split_name(tool_name(s.name, "do__it")) == (good, "do__it")


def test_an_allowed_command_still_running_stops_when_the_app_exits(ws):
    from camr_engine.agentic import shell

    out = {}
    th = threading.Thread(target=lambda: out.setdefault("r", run("sleep 30; echo late", ws.root)))
    th.start()
    t = time.monotonic()
    while not shell._LIVE and time.monotonic() - t < 5:
        time.sleep(0.01)
    assert shell.stop_all() == 1
    th.join(5)
    assert not th.is_alive() and "late" not in out["r"].output and not shell._LIVE


def test_a_run_counts_as_running_until_its_answer_is_kept(ws):
    release = threading.Event()

    class Slow(FakeBrain):
        def keep(self, text, to=None, source="model"):
            release.wait(5)
            return super().keep(text, to)

    r = make_run(ws, ["Done."], memory=True)
    r.brain = Slow(["Done."], memory=True)
    r.start()
    t = time.monotonic()
    while r.state != "keeping" and time.monotonic() - t < 5:
        time.sleep(0.005)
    assert r.state == "keeping" and r.live and r.answer == "Done." and r.kept is None
    release.set()
    r.thread.join(5)
    assert r.state == "done" and not r.live and r.turns[-1]["kind"] == "kept"

    class Broken(FakeBrain):
        def keep(self, text, to=None, source="model"):
            raise OSError("disk full")

    r = make_run(ws, ["Done."], memory=True)
    r.brain = Broken(["Done."], memory=True)
    r.execute()
    assert r.state == "done" and r.answer == "Done." and "disk full" in r.turns[-1]["text"]


def test_a_saved_fix_is_known_by_its_words_after_its_date():
    from camr_engine.agentic.brain import is_fix

    assert is_fix("[2026-11-04] Your fix in a.py (kept): you changed `x` to `y`.")
    assert is_fix("Your fix in a.py") and not is_fix("[2026-11-04] Code task: Your fix") and not is_fix("")


def test_a_denied_call_is_marked_as_your_choice_on_the_trace(ws):
    gate = Gate()
    r = make_run(ws, [call("run_shell", command="ls"), "Fine."], gate=gate)
    r.start()
    while not gate.waiting():
        time.sleep(0.005)
    gate.decide(gate.waiting()[0]["id"], False)
    r.thread.join(5)
    (span,) = [s for s in r.trace if s["track"] == "shell"]
    assert span["decision"] == "denied" and span["ok"] is False and span["waited"]


def test_a_task_that_names_a_file_is_told_to_read_it_first(ws):
    run = make_run(ws, ["done"])
    run.task = "What does fee() in src/fees.py return for 500? Also see missing.py."
    assert "First read src/fees.py with read_file" in run.prompt(1).user and "missing.py with" not in run.prompt(1).user
    run.task = "Add a helper"
    assert "First read" not in run.prompt(1).user


def test_a_look_made_again_with_no_write_since_is_not_run_again(ws):
    run = make_run(ws, [call("list_files"), call("list_files"), call("write_file", path="a.txt", content="a\n"),
                        call("list_files"), "Done."])
    run.execute()
    looks = [t for t in run.turns if t["kind"] == "call" and t["tool"] == "list_files"]
    assert "src/" in looks[0]["text"] and looks[1]["text"].startswith("(the same as [1]: nothing has changed")
    assert "a.txt" in looks[2]["text"]  # a write came between, so it is run again


def test_the_first_step_says_when_the_workspace_is_empty(ws, tmp_path):
    assert "The workspace is empty" not in make_run(ws, []).prompt(1).user
    empty = tmp_path / "new-site"
    (empty / ".git").mkdir(parents=True)
    run = make_run(Workspace(empty), [call("write_file", path="index.html", content="<p>hi</p>\n"), "Done."])
    assert "The workspace is empty: make the files the task needs with write_file." in run.prompt(1).user
    run.execute()
    assert "The workspace is empty" not in run.prompt(2).user


def test_a_reply_cut_off_inside_a_call_is_told_and_the_next_gets_twice_the_room(ws):
    cut = '<tool_call>\n{"name": "write_file", "arguments": {"path": "index.html", "content": "<html><body>'
    brain = FakeBrain([cut, call("write_file", path="index.html", content="<p>hi</p>\n"), "Done."])
    p = BUILT_IN[0]
    run = Run("t-1", "Build the page", brain=brain, tools=Toolbox(ws, Gate(), allows=p.allows), persona=p,
              gate=Gate(), workspace=ws.name, step_tokens=len([cut[i:i + 3] for i in range(0, len(cut), 3)]))
    run.execute()
    assert run.state == "done" and (ws.root / "index.html").read_text() == "<p>hi</p>\n"
    assert brain.prompts[1].max_tokens == 2 * brain.prompts[0].max_tokens
    assert "ran out of room" in brain.prompts[1].user and "nothing ran" in brain.prompts[1].user
    assert any(t["kind"] == "error" and "cut off" in t["text"] for t in run.turns)


def test_files_the_task_names_and_the_run_has_not_written_are_named_each_step(ws):
    p = BUILT_IN[0]
    brain = FakeBrain([call("write_file", path="index.html", content="<p>hi</p>\n"),
                       call("write_file", path="style.css", content="p {}\n"), "Done."])
    run = Run("t-1", "Build index.html and style.css; see README.md", brain=brain,
              tools=Toolbox(ws, Gate(), allows=p.allows), persona=p, gate=Gate(), workspace=ws.name)
    run.execute()
    assert "Named in the task" not in brain.prompts[0].user
    assert "Named in the task and not in the workspace yet: style.css." in brain.prompts[1].user
    assert "Named in the task" not in brain.prompts[2].user
    assert f'not "{ws.name}/a.txt"' in brain.prompts[0].system


def test_after_two_looks_made_again_the_next_step_has_only_tools_that_change_things(ws):
    brain = FakeBrain([call("list_files"), call("list_files"), call("list_files"), call("list_files"),
                       call("write_file", path="a.txt", content="a\n"), "Done."])
    run = make_run(ws, [])
    run.brain = brain
    run.execute()
    names = [{t["function"]["name"] for t in p.tools} for p in brain.prompts]
    assert "list_files" in names[2] and "list_files" not in names[3] and "write_file" in names[3]
    assert "list_files" in names[5]  # a write came between


def test_an_answer_with_a_named_file_not_written_is_sent_back_once(ws):
    p = BUILT_IN[0]
    brain = FakeBrain([call("write_file", path="index.html", content="<p>hi</p>\n"),
                       "I wrote index.html and will now create style.css.", "I will not write style.css.",
                       call("write_file", path="never.css", content="x\n")])
    run = Run("t-1", "Build index.html and style.css", brain=brain, tools=Toolbox(ws, Gate(), allows=p.allows),
              persona=p, gate=Gate(), workspace=ws.name)
    run.execute()
    assert "the task names style.css, not in the workspace yet" in brain.prompts[2].user
    assert run.state == "done" and run.answer == "I will not write style.css." and len(brain.prompts) == 3


def test_an_edit_that_differs_only_in_indentation_is_made_once_and_indented_as_the_file(tmp_path):
    from camr_engine.agentic.workspace import Outside, Workspace

    ws = Workspace(tmp_path, [])
    (tmp_path / "app.js").write_text("const app = () => {\n  const total = 0;\n  const message = '';\n  go();\n};\n")
    ws.edit("app.js", "const total = 0;\nconst message = '';", "let total = 0;\nlet message = '';")
    assert (tmp_path / "app.js").read_text() == "const app = () => {\n  let total = 0;\n  let message = '';\n  go();\n};\n"
    (tmp_path / "b.js").write_text("  x();\n  x();\n")
    with pytest.raises(Outside):  # two places it could be: none is guessed
        ws.edit("b.js", "x();", "y();")
    with pytest.raises(Outside):
        ws.edit("b.js", "z();", "y();")


def test_the_edit_tool_takes_an_edit_that_differs_only_in_indentation(tmp_path):
    from camr_engine.agentic.gate import Gate
    from camr_engine.agentic.tools import Toolbox
    from camr_engine.agentic.workspace import Workspace

    (tmp_path / "app.js").write_text("const app = () => {\n  const total = 0;\n  const message = '';\n  go();\n};\n")
    box = Toolbox(Workspace(tmp_path, []), Gate())
    done = box.run("edit_file", {"path": "app.js", "old_text": "const total = 0;\nconst message = '';",
                                 "new_text": "let total = 0;\nlet message = '';"}, owner="r")
    assert done.ok and done.offset == 1
    assert "  let total = 0;\n  let message = '';" in (tmp_path / "app.js").read_text()

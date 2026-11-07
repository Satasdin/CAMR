"""Notebooks and scripts (camr_engine.notebooks): written from plain cells, run in the kernel's own Python with each
cell's outputs kept in the file, failures and time limits caught, locked down by the sandbox; the agent's tools ask
before the first run; the lead runs the notebook and plans a fix for a cell that fails; the app's routes.

The runs use the real kernel at ~/.camr/kernels/py (skipped when it is not set up)."""

from __future__ import annotations

import json
import re
import subprocess
import threading
import time
from pathlib import Path

import pytest

from camr_engine import notebooks as nbm
from camr_engine.agentic.brain import Thought
from camr_engine.agentic.gate import Gate
from camr_engine.agentic.personas import Persona
from camr_engine.agentic.tools import NOTEBOOK_TOOLS, Toolbox
from camr_engine.agentic.workspace import Workspace

kernel = pytest.mark.skipif(not nbm.kernel_ready(), reason="the notebook Python is not set up")
CELLS = [
    {"kind": "markdown", "source": "# Sales\nWhat sold most."},
    {"kind": "code", "source": "import pandas as pd\nimport matplotlib.pyplot as plt\nprint('ready')"},
    {"kind": "code", "source": "df = pd.DataFrame({'item': ['tea', 'cake'], 'sold': [3, 5]})\ndf"},
    {"kind": "code", "source": "fig, ax = plt.subplots()\nax.bar(df['item'], df['sold'])\nplt.show()"},
]


@pytest.fixture
def ws(tmp_path):
    root = tmp_path / "project"
    root.mkdir()
    return Workspace(root)


@pytest.fixture(autouse=True)
def _kernels_closed():
    yield
    nbm.NOTEBOOKS.shutdown()


def test_cells_are_written_as_a_real_notebook_and_edited_one_at_a_time(ws):
    nb, w = nbm.write(ws, "a.ipynb", CELLS)
    assert w.path == "a.ipynb" and w.before is None
    saved = json.loads((ws.root / "a.ipynb").read_text())
    assert saved["nbformat"] == 4 and [c["cell_type"] for c in saved["cells"]] == ["markdown", "code", "code", "code"]
    first_id = saved["cells"][2]["id"]
    nb, _ = nbm.edit_cell(ws, "a.ipynb", 2, "x = 1\nx")
    assert nb["cells"][2]["id"] == first_id and nb["cells"][2]["source"] == "x = 1\nx"
    nb, _ = nbm.edit_cell(ws, "a.ipynb", 4, "print('end')", op="insert")
    nb, _ = nbm.edit_cell(ws, "a.ipynb", 0, op="delete")
    assert [c["source"] for c in nb["cells"]][-1] == "print('end')" and len(nb["cells"]) == 4
    with pytest.raises(ValueError):
        nbm.edit_cell(ws, "a.ipynb", 9, "x")
    with pytest.raises(ValueError):
        nbm.write(ws, "a.txt", CELLS)  # a notebook is a .ipynb
    from camr_engine.agentic.workspace import Outside

    with pytest.raises(Outside):
        nbm.write(ws, "../out.ipynb", CELLS)


@kernel
def test_a_notebook_runs_and_keeps_text_tables_and_charts_in_the_file(ws):
    nbm.write(ws, "a.ipynb", CELLS)
    got = nbm.NOTEBOOKS.run(ws, "a.ipynb")
    assert got["state"] == "done" and got["ran"] == [1, 2, 3] and got["failed"] is None
    cells = json.loads((ws.root / "a.ipynb").read_text())["cells"]
    assert cells[1]["outputs"][0]["text"] == "ready\n" and cells[1]["execution_count"] == 1
    assert "text/html" in cells[2]["outputs"][0]["data"]  # the DataFrame, as Jupyter shows it
    assert any("image/png" in o.get("data", {}) for o in cells[3]["outputs"])
    shown = nbm.view(nbm.load(ws, "a.ipynb"))["cells"]
    assert shown[2]["outputs"][0]["kind"] == "table" and shown[2]["outputs"][0]["rows"][1][-2:] == ["tea", "3"]
    assert shown[3]["outputs"][-1]["kind"] == "image" and shown[3]["outputs"][-1]["base64"].startswith("iVBOR")
    check = subprocess.run([str(nbm.kernel_python()), "-c", "import nbformat, sys; "
                            "nbformat.validate(nbformat.read(sys.argv[1], as_version=4))", str(ws.root / "a.ipynb")],
                           capture_output=True, text=True)
    assert check.returncode == 0, check.stderr  # a file Jupyter itself accepts
    one = nbm.NOTEBOOKS.run(ws, "a.ipynb", 2)  # one cell, in the kernel as it is
    assert one["state"] == "done" and one["ran"] == [2]


@kernel
def test_an_error_is_kept_in_its_cell_and_the_run_stops_there(ws):
    nbm.write(ws, "a.ipynb", ["x = 1", "print(y)", "print('never')"])
    got = nbm.NOTEBOOKS.run(ws, "a.ipynb")
    assert got["state"] == "error" and got["failed"] == 1 and got["ran"] == [0, 1]
    err = nbm.cell_errors(got["notebook"]["cells"][1])[0]
    assert err["ename"] == "NameError"
    view = nbm.text_view(got["notebook"])
    assert "NameError: name 'y' is not defined" in view and "[2] code, not run" in view


@kernel
def test_a_cell_past_its_time_is_stopped_and_one_that_ignores_the_stop_loses_its_kernel(ws):
    nbm.write(ws, "a.ipynb", ["import time\ntime.sleep(30)", "print('after')"])
    t = time.monotonic()
    got = nbm.NOTEBOOKS.run(ws, "a.ipynb", cell_s=1.5)
    assert got["state"] == "timeout" and got["failed"] == 0 and time.monotonic() - t < 15
    assert nbm.cell_errors(got["notebook"]["cells"][0])[0]["ename"] == "TimeoutError"
    nbm.write(ws, "b.ipynb", ["import signal, time\nsignal.signal(signal.SIGINT, signal.SIG_IGN)\ntime.sleep(60)"])
    got = nbm.NOTEBOOKS.run(ws, "b.ipynb", cell_s=1.0)
    names = [o["ename"] for o in nbm.cell_errors(got["notebook"]["cells"][0])]
    assert got["state"] == "timeout" and "KernelRestarted" in names


@kernel
@pytest.mark.skipif(not nbm.sandbox_works(), reason="sandbox-exec does not run here")
def test_the_sandbox_blocks_the_network_and_writes_outside_the_project(ws):
    outside = Path.home() / f"camr-sandbox-probe-{time.time_ns()}.txt"
    nbm.write(ws, "a.ipynb", [
        "import socket\ntry:\n    socket.create_connection(('1.1.1.1', 80), timeout=3)\n    print('NET OPEN')\n"
        "except OSError as e:\n    print('net blocked', type(e).__name__)",
        f"try:\n    open({str(outside)!r}, 'w').write('x')\n    print('HOME OPEN')\n"
        "except OSError as e:\n    print('home blocked', type(e).__name__)",
        "open('inside.txt', 'w').write('ok')\nimport os\nprint(sorted(k for k in os.environ if 'KEY' in k))"])
    got = nbm.NOTEBOOKS.run(ws, "a.ipynb")
    text = nbm.text_view(got["notebook"])
    assert got["state"] == "done", text
    assert "net blocked PermissionError" in text and "home blocked PermissionError" in text
    assert "OPEN" not in text and not outside.exists()
    assert (ws.root / "inside.txt").read_text() == "ok"
    assert "[]" in text  # none of the engine's keys reach the kernel


@kernel
def test_a_script_runs_with_its_output_the_files_it_made_and_a_time_limit(ws):
    (ws.root / "s.py").write_text("import sys\nprint('hi')\nopen('out.csv', 'w').write('a\\n1\\n')\nsys.exit(3)\n")
    got = nbm.run_script(ws, "s.py")
    assert got["code"] == 3 and got["output"] == "hi\n" and got["made"] == ["out.csv"] and not got["timed_out"]
    (ws.root / "slow.py").write_text("import time\ntime.sleep(30)\n")
    got = nbm.run_script(ws, "slow.py", timeout_s=1)
    assert got["timed_out"] and "stopped" in got["output"]


def _approve(gate: Gate, stop: threading.Event, allow=True, seen=None):
    def go():
        while not stop.is_set():
            for w in gate.waiting():
                if w["kind"] == "python":
                    if seen is not None:
                        seen.append(w)
                    gate.decide(w["id"], allow)
            stop.wait(0.01)

    t = threading.Thread(target=go, daemon=True)
    t.start()
    return t


def test_the_notebook_tools_are_offered_only_to_a_persona_that_names_them(ws):
    plain = Toolbox(ws, Gate(wait_s=1))
    assert not set(NOTEBOOK_TOOLS) & plain.names()
    analyst = Persona("a", "Analyst", "", tools=["notebook_write", "notebook_run"])
    box = Toolbox(ws, Gate(wait_s=1), allows=analyst.allows)
    assert {"notebook_write", "notebook_run"} <= box.names() and "python_run" not in box.names()


@kernel
def test_the_agent_writes_runs_and_fixes_a_notebook_asking_once_before_it_runs(ws):
    gate = Gate(wait_s=5)
    box = Toolbox(ws, gate, allows=lambda n: n in NOTEBOOK_TOOLS)
    done = box.run("notebook_write", {"path": "n.ipynb", "cells": [
        {"kind": "markdown", "source": "# N"}, {"kind": "code", "source": "print(undefined)"}]}, owner="r")
    assert done.ok and done.wrote is not None and "2 cells (1 code, 1 markdown)" in done.text
    stop, seen = threading.Event(), []
    t = _approve(gate, stop, seen=seen)
    try:
        ran = box.run("notebook_run", {"path": "n.ipynb"}, owner="r")
        assert not ran.ok and "Cell 1 of n.ipynb failed" in ran.text and "NameError" in ran.text
        assert "1│ print(undefined)" in ran.text and ran.ask["decision"] == "allowed"
        assert seen[0]["what"]["code"] == "# cell 1\nprint(undefined)" and seen[0]["what"]["kind"] == "notebook"
        fixed = box.run("notebook_edit_cell", {"path": "n.ipynb", "index": 1, "source": "print(6 * 7)"}, owner="r")
        assert fixed.ok and fixed.wrote is not None
        again = box.run("notebook_run", {"path": "n.ipynb"}, owner="r")
        assert again.ok and "no errors" in again.text and "42" in again.text and again.ask is None
        assert len(seen) == 1  # asked once for this notebook
    finally:
        stop.set()
        t.join()


@kernel
def test_a_denied_run_never_runs_and_a_script_asks_too(ws):
    gate = Gate(wait_s=5)
    box = Toolbox(ws, gate, allows=lambda n: n in NOTEBOOK_TOOLS)
    (ws.root / "s.py").write_text("open('ran.txt', 'w').write('x')\n")
    stop = threading.Event()
    t = _approve(gate, stop, allow=False)
    try:
        got = box.run("python_run", {"path": "s.py"}, owner="r")
    finally:
        stop.set()
        t.join()
    assert not got.ok and "did not run" in got.text and not (ws.root / "ran.txt").exists()
    bad = box.run("notebook_run", {"path": "../x.ipynb"}, owner="r")
    assert not bad.ok and "outside" in bad.text


class AnalystBrain:
    """Writes a notebook with one broken cell when told to write it, and fixes the cell it is told to fix."""

    memory_on, label = False, "stand-in"

    def __init__(self):
        self.prompts = []

    def think(self, p):
        self.prompts.append(p)
        done = "What you did so far" in p.user
        m = re.search(r"Write (\S+\.ipynb) now with notebook_write", p.user)
        fix = re.search(r"Fix (\S+\.ipynb): fix cell (\d+)", p.user)
        if m and not done:
            text = _call("notebook_write", path=m.group(1), cells=[
                {"kind": "markdown", "source": "# Sales"},
                {"kind": "code", "source": "import pandas as pd\ndf = pd.read_csv('sales.csv')\ndf"},
                {"kind": "code", "source": "print(df['units'].sum())"}])
        elif fix and not done:
            text = _call("notebook_edit_cell", path=fix.group(1), index=int(fix.group(2)),
                         source="print(df['sold'].sum())")
        else:
            text = "Done."
        return Thought(text, [text], 0.0, 0.0, 10, 1, 1.0, None)

    def keep(self, text, to=None, source="model"):
        pass

    def close(self):
        pass


def _call(name, **args) -> str:
    return f"<tool_call>\n{json.dumps({'name': name, 'arguments': args})}\n</tool_call>"


@kernel
def test_the_lead_runs_the_notebook_and_plans_a_fix_for_the_cell_that_fails(tmp_path):
    from camr_engine.agentic.desk import Desk

    root = tmp_path / "shop"
    root.mkdir()
    (root / "sales.csv").write_text("item,sold\ntea,3\ncake,5\n")
    brain = AnalystBrain()
    d = Desk(tmp_path / "code", brains=lambda spec: brain)
    d.set_workspace(str(root))
    stop, seen = threading.Event(), []
    t = _approve(d.gate, stop, seen=seen)
    try:
        lead = d.build(d.new_thread("t")["id"], "Analyse sales.csv and plot what sold most")
        lead.thread_obj.join(90)
    finally:
        stop.set()
        t.join()
    parts = [(p.role, p.state) for p in lead.plan.parts]
    assert lead.plan.kind == "notebook" and lead.state == "done", (parts, lead.error)
    assert parts == [("analyst", "done"), ("nbcheck", "done"), ("analyst", "done"), ("nbcheck", "done")]
    assert lead.plan.parts[2].title == "Fix cell 2 of sales-analysis.ipynb"
    assert "KeyError" in lead.plan.parts[2].detail
    first = brain.prompts[0].user
    assert "sales.csv, its first lines" in first and "item,sold" in first  # the analyst sees the columns
    assert "notebook_write" in [s["function"]["name"] for s in brain.prompts[0].tools]
    cells = json.loads((root / "sales-analysis.ipynb").read_text())["cells"]
    assert cells[2]["outputs"][0]["text"] == "8\n"
    assert len(seen) == 1  # the person allowed it once for the whole build


def test_requests_about_data_are_notebooks_and_go_to_the_agent():
    from camr_engine.agentic.plan import nb_name, wants_notebook
    from camr_engine.assistant import wants_agent

    assert wants_notebook("Make a notebook of my expenses", ["index.html"])
    assert wants_notebook("Analyse sales.csv and plot the totals by month", [])
    assert wants_notebook("plot the totals", ["sales.csv"])
    assert not wants_notebook("Build a website with a chart of our prices", [])
    assert not wants_notebook("Add a chart to the page", ["index.html", "app.js"])
    assert nb_name("Analyse sales.csv", ["sales.csv"]) == "sales-analysis.ipynb"
    assert nb_name("plot it", ["work.ipynb", "x.csv"]) == "work.ipynb"
    assert nb_name("make a notebook", []) == "analysis.ipynb"
    for t in ("Make a notebook that plots my sales", "Analyse this CSV file", "plot the sales by month",
              "Analyse the data in sales.csv", "create a jupyter notebook for the survey"):
        assert wants_agent(t), t
    for t in ("What is a Jupyter notebook?", "What's the plot of Hamlet?", "How do I analyse a CSV in Excel?"):
        assert not wants_agent(t), t


@kernel
def test_the_routes_read_edit_run_and_stop_a_notebook_and_run_a_script(tmp_path):
    from test_app_code import StandIn, serve

    root = tmp_path / "proj"
    root.mkdir()
    api, httpd = serve(StandIn(tmp_path))
    try:
        assert api("/api/notebook?path=a.ipynb")[0] == 409  # no project yet
        assert api("/api/code/workspace", {"path": str(root)})[0] == 200
        nbm.write(Workspace(root), "a.ipynb", ["print('one')", "import time\ntime.sleep(20)"])
        code, got = api("/api/notebook?path=a.ipynb")
        assert code == 200 and [c["source"] for c in got["cells"]][0] == "print('one')" and got["run"]["state"] == "idle"
        code, got = api("/api/notebook/cell", {"path": "a.ipynb", "index": 0, "source": "print('two')"})
        assert code == 200 and got["cells"][0]["source"] == "print('two')"
        assert api("/api/notebook/run", {"path": "a.ipynb", "cell": 0})[0] == 200
        for _ in range(200):
            code, got = api("/api/notebook?path=a.ipynb")
            if got["run"]["state"] != "running":
                break
            time.sleep(0.1)
        assert got["run"]["state"] == "done" and got["cells"][0]["outputs"][0]["text"] == "two\n"
        api("/api/notebook/run", {"path": "a.ipynb"})
        assert api("/api/notebook/run", {"path": "a.ipynb"})[0] == 409  # running already
        for _ in range(100):
            if api("/api/notebook?path=a.ipynb")[1]["run"].get("cell") == 1:
                break
            time.sleep(0.1)
        api("/api/notebook/stop", {"path": "a.ipynb"})
        for _ in range(100):
            code, got = api("/api/notebook?path=a.ipynb")
            if got["run"]["state"] != "running":
                break
            time.sleep(0.1)
        assert got["run"]["state"] == "stopped"
        assert api("/api/notebook?path=../x.ipynb")[0] == 400
        (root / "s.py").write_text("print('from a script')\n")
        assert api("/api/script/run", {"path": "s.py"})[0] == 200
        for _ in range(100):
            code, got = api("/api/script?path=s.py")
            if got["run"]["state"] != "running":
                break
            time.sleep(0.1)
        assert got["run"]["state"] == "done" and got["run"]["output"] == "from a script\n"
        assert got["source"] == "print('from a script')\n"
    finally:
        httpd.shutdown()

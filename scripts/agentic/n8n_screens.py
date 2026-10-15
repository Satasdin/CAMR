"""Screenshots of the n8n runs for the report: canvases with item counts, and node detail views (input | parameters |
output) opened on a chosen run, plus a compact version of each detail view (input and output panels side by side).

The screenshots are taken from a viewer: a second n8n on a consistent copy of the run database, so the runs are not
disturbed.

    # 1. copy the run database (sqlite backup) into <viewer>/.n8n/database.sqlite, then start the viewer:
    N8N_USER_FOLDER=<viewer> N8N_PORT=5799 N8N_LISTEN_ADDRESS=127.0.0.1 N8N_RUNNERS_ENABLED=false n8n start
    # 2. shoot (the viewer's owner account is created on first use):
    N8N_VIEWER_EMAIL=... N8N_VIEWER_PASSWORD=... python scripts/agentic/n8n_screens.py shoot [name ...]
    python scripts/agentic/n8n_screens.py crop            # compact panels -> docs/figures/n8n/panels/
"""

from __future__ import annotations

import argparse
import json
import os
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
OUT = ROOT / "docs/figures/n8n"
DB = os.environ.get("N8N_DB", "/root/.n8n/database.sqlite")  # the run database (the viewer holds a copy)
BASE = os.environ.get("N8N_VIEWER", "http://127.0.0.1:5799")
WF = {"desk": "3831c4feb9fc1c5e", "agent_camr": "e5bcd5f80bf76e86", "agent_none": "91f988b69e4bcf91",
      "fresh": "770885a86cc28674", "fresh_alone": "73c0e8f62a6b754d"}
# name -> (workflow, node to open (None: the canvas), (json key, value) of the run to show, output view)
SHOTS = {
    "desk_canvas": ("desk", None, None, None),
    "desk_t013_escalated": ("desk", "Answer ticket", ("ticket", "T013"), "JSON"),
    "desk_t020_answered": ("desk", "Answer ticket", ("ticket", "T020"), "JSON"),
    "agent_canvas": ("agent_camr", None, None, None),
    "agent_a20_camr": ("agent_camr", "Run agent on task", ("task", "A20"), "Table"),
    "agent_a20_alone": ("agent_none", "Run agent on task", ("task", "A20"), "Table"),
    "fresh_canvas": ("fresh", None, None, None),
    "fresh_fetch": ("fresh", "Fetch page from Wikipedia", None, "JSON"),
    "fresh_answer": ("fresh", "Answer question", ("ticket", "F012"), "JSON"),
    "fresh_answer_alone": ("fresh_alone", "Answer question", ("ticket", "F012"), "JSON"),
    "executions_list": (None, None, None, None),
}
# The input panel does not follow the output's run when the two nodes ran a different number of times: open the
# parent's run that carried the same item.
PARENT = {"Answer ticket": ("Policy change?", "id"), "Answer question": ("Loop over questions", "id")}


# ----------------------------------------------------------------- run data (n8n stores it as "flatted" JSON)

def run_data(execution_id: int) -> dict:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    arr = json.loads(c.execute("SELECT data FROM execution_data WHERE executionId=?", (execution_id,)).fetchone()[0])
    memo: dict[int, object] = {}

    def val(v):  # every string in flatted is a reference to an entry of the array
        return node(int(v)) if isinstance(v, str) else v

    def node(i: int):
        if i in memo:
            return memo[i]
        x = arr[i]
        if isinstance(x, list):
            memo[i] = out = []
            out.extend(val(v) for v in x)
        elif isinstance(x, dict):
            memo[i] = out = {}
            out.update({k: val(v) for k, v in x.items()})
        else:
            memo[i] = x
        return memo[i]

    return node(0)["resultData"]["runData"]


def items(run: dict) -> list[dict]:
    main = (run.get("data") or {}).get("main") or []
    return [it.get("json", {}) for branch in main for it in (branch or [])]


def find_run(execution_id: int, node_name: str, key: str, value: str) -> int | None:
    """0-based index of the node's run that handled the item with json[key] == value."""
    for k, run in enumerate(run_data(execution_id).get(node_name, [])):
        if any(str(it.get(key)) == value for it in items(run)):
            return k
    return None


def latest(workflow_id: str) -> int:
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    return c.execute("SELECT MAX(id) FROM execution_entity WHERE workflowId=? AND status='success'",
                     (workflow_id,)).fetchone()[0]


# ----------------------------------------------------------------- screenshots

def _pick(page, panel: str, k: int) -> None:
    page.locator(f"[data-test-id='{panel}'] [data-test-id='run-selector']").click()
    page.wait_for_timeout(600)
    page.locator("[data-test-id='run-selection-option']:visible").nth(k).click()
    page.wait_for_timeout(1200)


def shoot(names: list[str]) -> None:
    from playwright.sync_api import sync_playwright

    email, password = os.environ["N8N_VIEWER_EMAIL"], os.environ["N8N_VIEWER_PASSWORD"]
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=os.environ.get("CHROMIUM", "/opt/pw-browsers/chromium"))
        ctx = b.new_context(viewport={"width": 1600, "height": 900}, device_scale_factor=2)
        r = ctx.request.post(BASE + "/rest/owner/setup", data={"email": email, "firstName": "CAMR",
                                                                "lastName": "Study", "password": password})
        if r.status >= 400:
            r = ctx.request.post(BASE + "/rest/login", data={"emailOrLdapLoginId": email, "password": password})
        page = ctx.new_page()
        for name in names:
            wf, node, pick, view = SHOTS[name]
            ex = latest(WF[wf]) if wf else None
            page.goto(f"{BASE}/workflow/{WF[wf]}/executions/{ex}" if wf else f"{BASE}/home/executions")
            page.wait_for_timeout(6000)
            for _ in range(3):
                page.keyboard.press("Escape")
                page.wait_for_timeout(300)
            if node:
                page.locator(f"[data-test-id='canvas-node'][data-node-name='{node}']").dblclick()
                page.wait_for_timeout(2000)
                if pick:
                    _pick(page, "output-panel", find_run(ex, node, *pick))
                if view:
                    page.locator(f"[data-test-id='output-panel'] [data-test-id='radio-button-{view.lower()}']").click()
                    page.wait_for_timeout(1000)
                if pick and node in PARENT:
                    parent, key = PARENT[node]
                    page.locator("[data-test-id='ndv-input-panel'] [data-test-id='radio-button-json']").click()
                    page.wait_for_timeout(800)
                    k = find_run(ex, parent, key, pick[1])
                    if k is not None:
                        _pick(page, "ndv-input-panel", k)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print("shot", name, "execution", ex)
        b.close()


# ----------------------------------------------------------------- compact panels for the printed report

def crop(names: list[str]) -> None:
    """Input and output panels of each detail view side by side, cut below the last line of content (the
    parameters form in between is the same for every run and unreadable at page width)."""
    import numpy as np
    from PIL import Image

    (OUT / "panels").mkdir(exist_ok=True)
    for name in names:
        if SHOTS[name][1] is None or not (OUT / f"{name}.png").exists():
            continue
        im = Image.open(OUT / f"{name}.png").convert("RGB")
        s = im.width / 3200  # boxes are for a 1600 x 900 viewport at scale 2
        bottom_edge = min(im.height, int(1740 * s))  # the dialog ends here; below it is the dimmed page
        boxes = [tuple(int(v * s) for v in b[:3]) + (bottom_edge,) for b in ((50, 150, 1180), (2022, 150, 3150))]
        bottom = 0
        for box in boxes:
            a = np.asarray(im.crop(box).convert("L"))
            rows = np.where((a < 200).sum(axis=1) > 2)[0]
            bottom = max(bottom, int(rows.max()) + 40 if len(rows) else a.shape[0])
        parts = [im.crop((b[0], b[1], b[2], min(b[1] + bottom, im.height))) for b in boxes]
        gap = int(24 * s)
        out = Image.new("RGB", (sum(p.width for p in parts) + gap, max(p.height for p in parts)), (255, 255, 255))
        out.paste(parts[0], (0, 0))
        out.paste(parts[1], (parts[0].width + gap, 0))
        out.save(OUT / "panels" / f"{name}.png", optimize=True)
        print("panels", name, out.size)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("cmd", choices=["shoot", "crop"])
    ap.add_argument("names", nargs="*")
    a = ap.parse_args()
    names = a.names or list(SHOTS)
    shoot(names) if a.cmd == "shoot" else crop(names)

"""Hard briefs: vendored files copied in through the workspace, served with the right types and no network, the
motion part planned by rule, and the motion rules marked from the numbers (the Chrome run itself is opt-in:
CAMR_CHROME_TESTS=1)."""

import json
import os
import re
import shutil
import threading
import urllib.request
from pathlib import Path

import pytest

from camr_engine.agentic import motion
from camr_engine.agentic.brain import Thought
from camr_engine.agentic.desk import Desk
from camr_engine.agentic.lint import page_problems
from camr_engine.agentic.plan import files_named
from camr_engine.agentic.plugins import browser_check
from camr_engine.agentic.serve import close_all, kind_of, serving
from camr_engine.agentic.workspace import Outside, Workspace

ROCKET = ("Build a website for a rocket company: a 3D rocket that turns and lifts off as you scroll, parallax layers "
          "of sky and stars, and a calm version when reduced motion is on")
CAFE = "Build a website for a small café with our menu, prices and opening hours"
REPO = Path(__file__).resolve().parents[2]


# -- vendored files, through the workspace -----------------------------------------------------------------------------

def test_the_kits_are_copied_into_vendor_byte_for_byte_and_only_once(tmp_path):
    ws = Workspace(tmp_path, [])
    copied = motion.install(ws, motion.kits_for(ROCKET))
    for rel in ["VENDOR.md", *[f for k in ("three", "rocket", "parts", "models", "gsap") for f in motion.KITS[k]]]:
        assert (tmp_path / "vendor" / rel).read_bytes() == (motion.VENDOR / rel).read_bytes(), rel
    assert "vendor/three/three.module.js" in copied and "vendor/models/space-kit/platform_large.glb" in copied
    assert motion.install(ws, motion.kits_for(ROCKET)) == []  # already there: nothing copied again
    assert not list(tmp_path.rglob(".camr-*.tmp"))  # atomic: no half-written file left behind


def test_a_motion_brief_without_3d_gets_gsap_only():
    assert motion.kits_for("A pricing page with physics-like motion and a calm mode") == ["gsap"]
    assert motion.kits_for(ROCKET) == ["three", "rocket", "parts", "models", "gsap"]


def test_copying_in_keeps_to_the_workspace(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    (tmp_path / "elsewhere").mkdir()
    (root / "vendor").symlink_to(tmp_path / "elsewhere")
    ws = Workspace(root, [])
    with pytest.raises(Outside):
        motion.install(ws, ["gsap"])
    assert not list((tmp_path / "elsewhere").iterdir())
    for bad in (".git/hooks/pre-commit", "../out.js", "id_rsa"):
        with pytest.raises(Outside):
            ws.put(bad, b"x")
    with pytest.raises(Outside):
        ws.put("big.bin", b"0" * 9_000_000)


# -- serving: the right types, and no network --------------------------------------------------------------------------

def test_vendor_files_and_models_are_served_with_the_types_a_browser_needs(tmp_path):
    ws = Workspace(tmp_path, [])
    motion.install(ws, ["three", "models"])
    (tmp_path / "index.html").write_text("<h1>hi</h1>")
    (tmp_path / ".env").write_text("KEY=1")
    try:
        base = serving(ws).url("")
        for rel, kind in (("vendor/three/three.module.js", "text/javascript; charset=utf-8"),
                          ("vendor/models/space-kit/platform_large.glb", "model/gltf-binary"),
                          ("index.html", "text/html; charset=utf-8")):
            with urllib.request.urlopen(base + rel) as r:
                assert r.headers["Content-Type"] == kind, rel
                policy = r.headers["Content-Security-Policy"]
                assert "default-src 'self'" in policy and "connect-src 'self' data: blob:" in policy
                assert r.headers["X-Content-Type-Options"] == "nosniff"
        with pytest.raises(urllib.error.HTTPError):
            urllib.request.urlopen(base + ".env")
    finally:
        close_all()
    assert kind_of("scene.gltf") == "model/gltf+json" and kind_of("motion.mjs") == "text/javascript"


# -- the plan ----------------------------------------------------------------------------------------------------------

def call(name, **args) -> str:
    return f"<tool_call>\n{json.dumps({'name': name, 'arguments': args})}\n</tool_call>"


class TeamBrain:
    memory_on, label = False, "stand-in"

    def __init__(self, files):
        self.prompts, self.files = [], files

    def think(self, p):
        self.prompts.append(p)
        m = re.search(r"Write (\S+) now with write_file", p.user)
        if m and "What you did so far" not in p.user:
            text = call("write_file", path=m.group(1), content=self.files.get(m.group(1), f"made {m.group(1)}"))
        else:
            text = "Done."
        return Thought(text, [text], 0.0, 0.0, 10, 1, 1.0, None)

    def keep(self, text, to=None, source="model"):
        pass

    def close(self):
        pass


@pytest.fixture
def desk(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    brain = TeamBrain({"ARCHITECTURE.md": "Files: index.html, style.css, app.js and motion.js.\n\n## Vendor files\n"
                                          "- vendor/three/three.module.js\n- vendor/gsap/gsap.min.js",
                       "index.html": '<canvas id="scene"></canvas><div class="layer" data-speed="0.2"></div>'})
    d = Desk(tmp_path / "code", brains=lambda spec: brain)
    d.set_workspace(str(root))
    d.brain = brain
    return d


def build(desk, request):
    stop = threading.Event()

    def answer():
        while not stop.is_set():
            for w in desk.gate.waiting():
                if w["kind"] == "browser":
                    desk.gate.answer(w["id"], json.dumps({"text": "Halcyon"}))
            stop.wait(0.01)

    t = threading.Thread(target=answer)
    t.start()
    lead = desk.build(desk.new_thread("t")["id"], request)
    lead.thread_obj.join(20)
    stop.set()
    t.join()
    return lead


def test_a_brief_that_asks_for_motion_gets_a_motion_part_and_the_vendored_files(desk):
    lead = build(desk, ROCKET)
    parts = lead.plan.parts
    assert [p.role for p in parts] == ["research", "architect", "design", "builder", "motion", "behaviour", "review"]
    m = parts[4]
    assert (m.target, m.by, m.state) == ("motion.js", "rule", "done")
    root = desk.workspace.root
    assert (root / "vendor/three/three.module.js").is_file() and (root / "vendor/gsap/ScrollTrigger.min.js").is_file()
    assert any("vendor/" in d["text"] and d["by"] == "rule" for d in lead.plan.decisions)
    # no part was planned for a vendored file the architect listed
    assert not any(p.target and p.target.startswith("vendor/") for p in parts)
    text = "\n".join(p.system + "\n" + p.user for p in desk.brain.prompts)
    assert '<script type="importmap">' in text and "vendor/gsap/ScrollTrigger.min.js" in text  # the builder's snippet
    # the motion part starts from the whole tested motion.js; the builder and designer from the tested page
    assert "The method for motion-starter" in text and "Write it whole with write_file" in text
    assert "The method for page-starter" in text and 'id="cd-secs"' in text
    assert "Vendor files" in text and "camr-rocket.js" in text  # the architect is told what is vendored


SATELLITE = ("A product page for a small satellite: a 3D model that comes apart into an exploded view in layers as you "
             "scroll and comes back together, a parallax depth of panels around it, and a calm version when reduced "
             "motion is on.")


def test_a_3d_brief_that_is_not_a_rocket_gets_the_parts_starter_and_nothing_of_the_rocket(desk):
    lead = build(desk, SATELLITE)
    assert lead.plan.kind == "website" and "motion" in [p.role for p in lead.plan.parts]
    text = "\n".join(p.system + "\n" + p.user for p in desk.brain.prompts)
    assert "The method for motion-starter-parts" in text and "makeParts(THREE" in text
    assert "The method for page-starter-parts" in text
    # the rocket's starter (its countdown, its launch date, its company) never reaches a satellite's parts
    assert "The method for motion-starter:" not in text and "The method for page-starter:" not in text
    assert 'id="cd-secs"' not in text and "2027-03-14" not in text and "Halcyon Launch" not in text
    assert (desk.workspace.root / "vendor/camr-parts.js").is_file()


def test_the_parts_starter_cards_hold_the_tested_reference_page():
    from camr_engine.agentic import plan

    ref = REPO / "docs/real-use/hard/h3-reference"
    page = (plan.SKILLS / "page-starter-parts.md").read_text()
    assert (ref / "index.html").read_text().strip() in page and (ref / "style.css").read_text().strip() in page
    code = (plan.SKILLS / "motion-starter-parts.md").read_text()
    stripped = "\n".join(line.split("  // CHANGE")[0] for line in code.splitlines()
                         if not line.strip().startswith("// CHANGE"))
    assert (ref / "motion.js").read_text().strip() in stripped


def test_a_folder_of_cards_from_before_the_starter_gives_the_old_cards(desk, tmp_path, monkeypatch):
    from camr_engine.agentic import plan

    old = tmp_path / "skills"
    old.mkdir()
    for f in plan.SKILLS.glob("*.md"):
        if not f.stem.startswith(("motion-starter", "page-starter")):
            (old / f.name).write_text(f.read_text())
    monkeypatch.setattr(plan, "SKILLS", old)
    build(desk, ROCKET)
    text = "\n".join(p.system + "\n" + p.user for p in desk.brain.prompts)
    assert "The method for 3d-scene" in text and "The method for layers" in text
    assert "motion-starter" not in text and "page-starter" not in text


def test_a_plain_cafe_page_gets_no_motion_part_and_no_vendor_folder(desk):
    lead = build(desk, CAFE)
    assert "motion" not in [p.role for p in lead.plan.parts]
    assert not (desk.workspace.root / "vendor").exists()
    text = "\n".join(p.system + "\n" + p.user for p in desk.brain.prompts)
    assert "importmap" not in text and "3d-scene" not in text


def test_vendored_and_report_files_are_never_parts():
    assert files_named("index.html style.css vendor/three/three.module.js ./vendor/camr-rocket.js report/x.json "
                       "motion.js") == ["style.css", "index.html", "motion.js"]


def test_which_briefs_ask_for_motion_and_which_rules_they_get():
    assert motion.asks_motion(ROCKET) and not motion.asks_motion(CAFE)
    assert not motion.asks_motion("A promotion page for our bakery")  # "promotion" is not motion
    assert motion.wants(ROCKET) == {"canvas", "clear", "fps", "console", "layers", "reduced", "strip"}
    assert motion.wants(CAFE) == set()
    assert motion.wants(CAFE, '<canvas id="c"></canvas>') == {"canvas", "clear", "fps", "console", "reduced", "strip"}
    assert motion.wants("A scroll-told story page with pinned chapters") == {"fps", "console", "reduced", "strip"}


# -- marking, by rule --------------------------------------------------------------------------------------------------

def moved(*rates_px, steps=5, scrolled=2000):
    """Elements that move linearly with the scroll at the given px per 1000 px."""
    return [{"el": f"div.l{i}", "at": [[0, -r * scrolled / 1000 * k / (steps - 1), 100, 0] for k in range(steps)]}
            for i, r in enumerate(rates_px)]


GOOD = {"measured": {"max": 2000, "frames": 120, "seconds": 2.0, "worst_ms": 20,
                     "canvas": {"samples": [{"colours": 1, "spread": 0}, {"colours": 45, "spread": 30.5}]},
                     "moved": moved(50, 150, 400)},
        "still": {"overTime": 0, "onScroll": 0, "hidden": 0, "texts": 21, "canvasChanged": False,
                  "overTimeEls": [], "onScrollEls": [], "hiddenEls": []},
        "console": [], "strip": ["a.png"] * 5}


def marks(result, want=frozenset(motion.RULES)):
    return {r["rule"]: r for r in motion.score(result, set(want))}


def test_a_good_page_passes_every_rule_and_the_best_canvas_sample_counts():
    got = marks(GOOD)
    assert all(r["ok"] for r in got.values()), [r["text"] for r in got.values() if not r["ok"]]
    assert got["fps"]["value"]["fps"] == 60.0 and got["canvas"]["value"] == {"colours": 45, "spread": 30.5}
    assert got["layers"]["value"] == 3


def test_each_rule_fails_on_its_own_evidence():
    bad = json.loads(json.dumps(GOOD))
    bad["measured"].update(frames=80, canvas={"samples": [{"colours": 1, "spread": 0.0}]}, moved=moved(100, 105, 108))
    bad["console"] = ["ReferenceError: startTelemetry is not defined"]
    bad["still"].update(overTime=2, overTimeEls=["p.kicker"], hidden=3, hiddenEls=["h2.reveal"])
    bad["strip"] = ["a.png"] * 3
    bad["measured"]["clashes"] = [{"el": "h2", "text": "The vehicle", "spread": 61, "at": 2}]
    got = marks(bad)
    assert {k for k, r in got.items() if not r["ok"]} == set(motion.RULES)
    assert "40 frames a second" in got["fps"]["text"] and "one flat colour" in got["canvas"]["text"]
    assert got["layers"]["value"] == 1  # three speeds within 12% of each other are one layer
    assert "startTelemetry" in got["console"]["text"] and "3 of 21 texts are hidden" in got["reduced"]["text"]
    assert "The vehicle" in got["clear"]["text"]


def test_no_canvas_a_page_that_does_not_scroll_and_an_unmeasured_page_fail_plainly():
    r = json.loads(json.dumps(GOOD))
    r["measured"].update(canvas=None, max=0)
    got = marks(r)
    assert not got["canvas"]["ok"] and "no canvas" in got["canvas"]["text"]
    assert not got["layers"]["ok"] and "does not scroll" in got["layers"]["text"]
    broken = marks({"measured": {"error": "Playwright could not open the page"}, "console": []})
    assert not any(broken[k]["ok"] for k in ("canvas", "fps", "layers", "reduced", "strip")) and broken["console"]["ok"]


def test_only_the_wanted_rules_are_marked():
    assert [r["rule"] for r in motion.score(GOOD, {"fps", "console"})] == ["fps", "console"]


# -- the check in Chrome, through Playwright's tools (a stand-in link) ---------------------------------------------------

class Link:
    state = "connected"

    def __init__(self, tmp_path):
        self.calls, self.cwd = [], tmp_path
        (tmp_path / ".playwright-mcp").mkdir()

    def call(self, tool, args):
        self.calls.append((tool, args))
        fn = args.get("function", "")
        if tool == "browser_evaluate":
            if fn.startswith("async () => {") and "out.moved" in fn:
                value = json.dumps({**GOOD["measured"], "width": 1280, "height": 800})
            elif "overTime" in fn:
                value = json.dumps(GOOD["still"])
            elif "scrollTop = Math.max" in fn:
                return {"ok": True, "text": "### Result\n0"}
            else:
                value = json.dumps({"text": "Halcyon", "failed": [], "runsOff": False})
            return {"ok": True, "text": "### Result\n" + json.dumps(value)}
        if tool == "browser_take_screenshot":
            (self.cwd / args["filename"]).write_bytes(b"\x89PNG\r\n\x1a\n" + b"0" * 10)
            return {"ok": True, "text": f"### Result\n- [Screenshot of viewport](./{args['filename']})"}
        if tool == "browser_console_messages":
            return {"ok": True, "text": "### Result\nTotal messages: 0 (Errors: 0, Warnings: 0)"}
        return {"ok": True, "text": "### Page\n- Page URL: x"}


def test_the_motion_check_measures_scrolls_shoots_and_reloads_calm_then_puts_motion_back(tmp_path):
    link = Link(tmp_path)
    got = browser_check(link, "http://127.0.0.1:1/index.html", motion=set(motion.RULES))
    tools = [t for t, _ in link.calls]
    assert tools[:4] == ["browser_navigate", "browser_resize", "browser_evaluate", "browser_console_messages"]
    assert tools.count("browser_take_screenshot") == 5
    media = [a["reducedMotion"] for t, a in link.calls if t == "browser_emulate_media"]
    assert media == ["reduce", "no-preference"]  # the next page is not left calm
    assert all(r["ok"] for r in got["motion"]["rules"]) and not got["failed"]
    ws = Workspace(tmp_path, [])
    kept = motion.keep_report(ws, got["motion"])
    assert kept["strip"] == [f"report/motion-{k}.png" for k in range(5)]
    assert json.loads((tmp_path / "report/motion.json").read_text())["measured"]["layers"] == 3


def test_a_file_that_is_not_a_screenshot_is_never_copied_into_the_report(tmp_path):
    (tmp_path / "secret.txt").write_text("not a png")
    kept = motion.keep_report(Workspace(tmp_path, []), {"strip": [str(tmp_path / "secret.txt")], "rules": []})
    assert kept["strip"] == [] and not (tmp_path / "report/motion-0.png").exists()


def test_the_build_report_shows_the_motion_check(desk):
    lead = build(desk, ROCKET)
    motion.keep_report(desk.workspace, {"rules": motion.score(GOOD, set(motion.RULES)), "measured": GOOD["measured"]})
    report = lead.report()
    assert "## Motion check (Chrome, by rule)" in report and "- pass: fps: 60 frames a second" in report


# -- the static check: modules may import, vendored code is not linted ---------------------------------------------------

def test_a_module_may_import_and_vendored_scripts_are_left_alone(tmp_path):
    (tmp_path / "index.html").write_text('<canvas id="scene"></canvas><script src="vendor/gsap/gsap.min.js"></script>'
                                         '<script type="module" src="motion.js"></script>')
    (tmp_path / "motion.js").write_text("import * as THREE from 'three';\n"
                                        "const c = document.getElementById('scene');\n")
    (tmp_path / "vendor/gsap").mkdir(parents=True)
    (tmp_path / "vendor/gsap/gsap.min.js").write_text("module.exports = require('x'); const = ;")
    assert page_problems(Workspace(tmp_path, []), "index.html") == []


@pytest.mark.skipif(shutil.which("node") is None, reason="needs Node")
def test_a_module_that_does_not_parse_is_found(tmp_path):
    # node --check on a .js file that imports lets this pass; read as a module, it is caught
    (tmp_path / "index.html").write_text('<script type="module" src="motion.js"></script>')
    (tmp_path / "motion.js").write_text("import * as THREE from 'three';\nconst = ;\n")
    got = page_problems(Workspace(tmp_path, []), "index.html")
    assert len(got) == 1 and "motion.js does not parse" in got[0] and "line 2" in got[0]


# -- opt-in: the hand-made H1 pages in a real Chrome ---------------------------------------------------------------------

@pytest.mark.skipif(os.environ.get("CAMR_CHROME_TESTS") != "1", reason="opt-in: CAMR_CHROME_TESTS=1 (needs Node, "
                    "Google Chrome and Playwright's MCP server)")
def test_the_reference_page_passes_every_rule_and_the_broken_one_fails_the_right_ones(tmp_path, monkeypatch):
    import importlib.util

    monkeypatch.setenv("CAMR_PROJECTS", str(tmp_path))
    spec = importlib.util.spec_from_file_location("hard", REPO / "v2" / "scripts" / "hard.py")
    hard = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(hard)
    good = hard.check("H1", REPO / "docs/real-use/hard/h1-reference", "ref")["check"]["motion"]["rules"]
    assert all(r["ok"] for r in good), [r["text"] for r in good if not r["ok"]]
    good = hard.check("H3", REPO / "docs/real-use/hard/h3-reference", "ref")["check"]["motion"]["rules"]
    assert all(r["ok"] for r in good), [r["text"] for r in good if not r["ok"]]
    bad = hard.check("H1", REPO / "docs/real-use/hard/h1-broken", "bad")["check"]["motion"]["rules"]
    assert {r["rule"] for r in bad if not r["ok"]} == {"canvas", "console", "reduced"}

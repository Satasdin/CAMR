"""The lead: a request is planned, then built part by part, each part a specialist's run with a narrow prompt."""

import json
import re
import threading

import pytest

from camr_engine.agentic.brain import Thought
from camr_engine.agentic.desk import Desk
from camr_engine.agentic.plan import ROLES, change_target, change_targets, classes_in, files_named, role_of


def call(name, **args) -> str:
    return f"<tool_call>\n{json.dumps({'name': name, 'arguments': args})}\n</tool_call>"


class TeamBrain:
    """Writes whatever file its prompt says to write, then answers. Keeps every prompt."""

    memory_on, label = False, "stand-in"

    def __init__(self, files=None, fail=()):
        self.prompts = []
        self.kept = []
        self.files = files or {}
        self.fail = set(fail)  # files it never writes

    def think(self, p):
        self.prompts.append(p)
        m = re.search(r"Write (\S+) now with write_file", p.user)
        wrote = "What you did so far" in p.user
        if m and not wrote and m.group(1) not in self.fail:
            f = m.group(1)
            text = call("write_file", path=f, content=self.files.get(f, f"made {f}"))
        else:
            text = "Done."
        return Thought(text, [text], 0.0, 0.0, 10, 1, 1.0, None)

    def keep(self, text, to=None, source="model"):
        self.kept.append((text, source))

    def close(self):
        pass


ARCH = "# Architecture\n\nFiles: index.html, style.css and app.js.\n\n## Sections\n- #menu"


@pytest.fixture
def desk(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    brain = TeamBrain({"ARCHITECTURE.md": ARCH, "style.css": ".card { padding: 1rem }\n.btn:hover { color: red }",
                       "index.html": '<h1>Shop</h1><link rel="stylesheet" href="style.css">'})
    d = Desk(tmp_path / "code", brains=lambda spec: brain)
    d.set_workspace(str(root))
    d.brain = brain
    return d


def browser(gate, stop, report=lambda: {"text": "Shop"}):
    def go():
        while not stop.is_set():
            for w in gate.waiting():
                if w["kind"] == "browser":
                    gate.answer(w["id"], json.dumps(report()))
            stop.wait(0.01)

    t = threading.Thread(target=go)
    t.start()
    return t


def build(desk, request, report=lambda: {"text": "Shop"}):
    thread = desk.new_thread("t")["id"]
    stop = threading.Event()
    t = browser(desk.gate, stop, report)
    lead = desk.build(thread, request)
    lead.thread_obj.join(20)
    stop.set()
    t.join()
    return lead


def test_a_website_is_planned_then_built_one_file_at_a_time(desk):
    lead = build(desk, "Build a website for a small bookshop")
    parts = lead.plan.parts
    assert [p.role for p in parts] == ["research", "architect", "design", "builder", "behaviour", "review"]
    assert [p.target for p in parts[:5]] == ["BRIEF.md", "ARCHITECTURE.md", "style.css", "index.html", "app.js"]
    assert all(p.state == "done" for p in parts) and lead.state == "done"
    root = desk.workspace.root
    assert (root / "app.js").read_text() == "made app.js" and "[x]" in (root / "PLAN.md").read_text()
    assert "app.js" in lead.answer and "BRIEF.md" not in lead.answer


def test_each_part_reads_only_its_method_and_what_it_builds_on(desk):
    build(desk, "Build a website for a small bookshop")
    prompts = desk.brain.prompts
    first = {}
    for p in prompts:
        m = re.search(r"Write (\S+) now with write_file", p.user)
        if m:
            first.setdefault(m.group(1), p)
    assert "Write the brief" in first["BRIEF.md"].user and "ARCHITECTURE.md, as the team wrote it" not in first["BRIEF.md"].user
    assert "Plan the structure" in first["ARCHITECTURE.md"].user
    assert "Write the stylesheet" in first["style.css"].user and "Files: index.html" in first["style.css"].user
    assert "The classes style.css defines (use these): card, btn" in first["index.html"].user
    assert "index.html, as it is now:" in first["app.js"].user
    # the role is its system prompt, and only its tools are offered
    assert first["style.css"].system.startswith(ROLES["design"].system)
    assert {t["function"]["name"] for t in first["BRIEF.md"].tools} <= set(ROLES["research"].tools)


def test_the_architect_decides_the_files(desk):
    desk.brain.files["ARCHITECTURE.md"] = "Files: index.html, about.html and style.css."
    lead = build(desk, "Build a website for a small bookshop")
    assert [p.target for p in lead.plan.parts[2:5]] == ["style.css", "index.html", "about.html"]
    assert {"by": "model"} .items() <= lead.plan.decisions[1].items()


def test_a_website_always_gets_a_page_and_a_stylesheet(desk):
    desk.brain.files["ARCHITECTURE.md"] = "One page, no files listed."
    lead = build(desk, "Build a website for a small bookshop")
    assert [p.target for p in lead.plan.parts[2:4]] == ["style.css", "index.html"]
    assert sum(d["by"] == "rule" and "added" in d["text"] for d in lead.plan.decisions) == 2


def test_a_part_not_written_is_tried_once_more_and_the_build_goes_on(desk):
    desk.brain.fail = {"app.js"}
    lead = build(desk, "Build a website for a small bookshop")
    js = next(p for p in lead.plan.parts if p.target == "app.js")
    assert js.state == "failed" and js.tries == 2 and len(js.runs) == 2
    assert lead.plan.parts[-1].state == "done" and "Not finished: Write app.js" in lead.answer


def test_a_project_with_files_gets_a_change_to_the_right_file(desk):
    root = desk.workspace.root
    for f, text in {"index.html": "<h1>Shop</h1>", "style.css": ".a{}", "app.js": "let total = 0"}.items():
        (root / f).write_text(text)
    lead = build(desk, "make the buttons green")
    assert [(p.role, p.target) for p in lead.plan.parts] == [("change", "style.css"), ("review", None)]
    assert "how the page looks" in lead.plan.decisions[0]["text"]


def test_the_review_tests_first_and_a_clean_page_ends_it(desk):
    lead = build(desk, "Build a website for a small bookshop")
    review = desk.run(lead.plan.parts[-1].run)
    assert review.history[0][0] == "open_page" and review.steps == 0 and "no problems" in review.answer


def test_a_review_with_problems_goes_to_the_model(desk):
    lead = build(desk, "Build a website for a small bookshop", report=lambda: {"text": "Shop", "errors": ["boom"]})
    review = desk.run(lead.plan.parts[-1].run)
    assert review.steps >= 1 and "boom" in desk.brain.prompts[-1].user


def test_stopping_stops_the_part_and_every_part_after_it(desk):
    thread = desk.new_thread("t")["id"]
    gate_wait = threading.Event()
    real = desk.brain.think

    def slow(p):
        gate_wait.wait(5)
        return real(p)

    desk.brain.think = slow
    lead = desk.build(thread, "Build a website for a small bookshop")
    lead.stop()
    gate_wait.set()
    lead.thread_obj.join(10)
    assert lead.state == "stopped" and all(p.state in ("stopped", "done") for p in lead.plan.parts)


def test_rules_for_files_and_changes():
    assert files_named("index.html style.css app.js ../evil.js BRIEF.md /etc/x.css index.html") == [
        "style.css", "index.html", "app.js"]
    assert [role_of(f) for f in ("a.css", "b.html", "c.js", "d.py")] == ["design", "builder", "behaviour", "coder"]
    files = ["index.html", "style.css", "app.js"]
    assert change_target("make the heading dark blue", files)[0] == "style.css"
    assert change_target("the total does not add up when I click", files)[0] == "app.js"
    assert change_target("add our Saturday hours", files)[0] == "index.html"
    assert classes_in(".a{}\n.b-c:hover{}\n.d, .e {}") == ["a", "b-c", "d", "e"]


def test_a_build_and_a_run_cannot_share_a_thread(desk):
    from camr_engine.agentic.desk import Busy

    thread = desk.new_thread("t")["id"]
    ev = threading.Event()
    real = desk.brain.think
    desk.brain.think = lambda p: (ev.wait(5), real(p))[1]
    lead = desk.build(thread, "Build a website for a small bookshop")
    with pytest.raises(Busy):
        desk.build(thread, "again")
    lead.stop()
    ev.set()
    lead.thread_obj.join(10)


BRIEF = "# Brief\n\n## What people must be able to do\n- See the books and prices\n- Add books to a reading list\n\n## Facts\n- x"


def test_the_brief_lists_what_people_must_be_able_to_do(desk):
    (desk.workspace.root / "BRIEF.md").write_text(BRIEF)
    from camr_engine.agentic.plan import Lead

    lead = Lead.__new__(Lead)
    lead.desk = desk
    assert lead.musts() == ["See the books and prices", "Add books to a reading list"]


def test_the_lead_checks_the_page_and_plans_what_is_missing(desk):
    desk.brain.files["BRIEF.md"] = BRIEF
    real = desk.brain.think
    answers = iter(["1. yes, a list\n2. no, there is no button", "1. yes\n2. yes"])

    def think(p):
        if p.system.startswith("You check a web page"):
            desk.brain.prompts.append(p)
            from camr_engine.agentic.brain import Thought

            text = next(answers)
            return Thought(text, [text], 0.0, 0.0, 10, 1, 1.0, None)
        return real(p)

    desk.brain.think = think
    lead = build(desk, "Build a website for a small bookshop")
    roles = [(p.role, p.by) for p in lead.plan.parts]
    assert roles[-2:] == [("change", "model"), ("review", "rule")]
    change = lead.plan.parts[-2]
    assert change.title == "Make the page let people Add books to a reading list" and change.target == "index.html"
    assert any("does not yet let people Add books to a reading list" in d["text"] for d in lead.plan.decisions)
    assert "Make the change in index.html now with edit_file" in desk.run(change.runs[-1]).task
    assert "all there" in lead.plan.decisions[-1]["text"] and lead.checks == 2


def test_an_unreadable_check_adds_nothing(desk):
    desk.brain.files["BRIEF.md"] = BRIEF
    lead = build(desk, "Build a website for a small bookshop")
    assert lead.plan.parts[-1].role == "review" and "could not be read" in lead.plan.decisions[-1]["text"]


def test_a_limited_window_keeps_every_step_inside_it(desk):
    from camr_engine.agentic.loop import CHARS_PER_TOKEN

    desk.configure(window_tokens=4096)
    (desk.workspace.root / "index.html").write_text("<p>" + "word " * 6000 + "</p>")
    desk.brain.files = {}
    real = desk.brain.think
    seen = []

    def think(p):
        seen.append((len(p.system) + len(p.user) + len(json.dumps(p.tools))) / CHARS_PER_TOKEN + p.max_tokens)
        if len(seen) == 1:
            text = call("read_file", path="index.html")
            return Thought(text, [text], 0.0, 0.0, 10, 1, 1.0, None)
        return real(p)

    desk.brain.think = think
    build(desk, "make the heading say Welcome")
    assert len(seen) >= 2 and max(seen) <= 4096


def test_the_window_setting_is_kept_and_has_a_floor(desk):
    assert desk.configure(window_tokens=100)["window_tokens"] == 2048
    assert desk.configure(window_tokens=0)["window_tokens"] is None


def test_the_plan_is_never_written_through_a_symlink(desk, tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("keep me")
    (desk.workspace.root / "PLAN.md").symlink_to(victim)
    build(desk, "Build a website for a small bookshop")
    assert victim.read_text() == "keep me"


def test_a_build_ends_with_a_report_written_from_its_records(desk):
    lead = build(desk, "Build a website for a small bookshop")
    text = (desk.workspace.root / "REPORT.md").read_text()
    assert text.startswith("# Build report") and "It never stopped for you" in text
    assert "| Designer: Write style.css | model | done |" in text
    assert "(model) The architect named the files" in text and "passed" in text
    f = lead.facts()
    assert f["steps"] >= 6 and f["asks"] == [] and f["longest_alone_s"] == f["seconds"]
    assert "REPORT.md" not in lead.answer


def test_the_researcher_asks_for_what_was_not_told_and_the_answers_reach_the_brief(tmp_path):
    root = tmp_path / "site"
    root.mkdir()
    brain = TeamBrain()
    d = Desk(tmp_path / "code", brains=lambda spec: brain)
    d.set_workspace(str(root))
    d.told = lambda request: ["Riverbank Physio: a first assessment costs KES 3,500. Colours navy #1b2a4a."]
    thread = d.new_thread("t")["id"]
    stop = threading.Event()

    def person():
        said = iter(["Monday to Saturday, 8am to 6pm", "0733 902 118"])
        while not stop.is_set():
            for w in d.gate.waiting():
                if w["kind"] == "question":
                    d.gate.answer(w["id"], next(said, ""))
                elif w["kind"] == "browser":
                    d.gate.answer(w["id"], json.dumps({"text": "Riverbank"}))
            stop.wait(0.01)

    t = threading.Thread(target=person)
    t.start()
    lead = d.build(thread, "Make a website for Riverbank Physio")
    lead.thread_obj.join(20)
    stop.set()
    t.join()
    research = d.run(lead.plan.parts[0].run)
    asked = [x for x in research.turns if x.get("tool") == "ask_user"]
    assert len(asked) == 2 and all(x["ok"] for x in asked)
    first = brain.prompts[0].user
    assert "Monday to Saturday, 8am to 6pm" in first and "0733 902 118" in first
    assert any("0733 902 118" in n for n in lead.told)  # and every later part gets them too
    assert len(lead.facts()["asks"]) == 2 and "You said: \"0733 902 118\"" in lead.report()


def test_layout_words_go_to_the_stylesheet_and_new_controls_to_page_and_script():
    files = ["index.html", "style.css", "app.js"]
    assert change_target("Make the order total sticky at the bottom on a phone", files)[0] == "style.css"
    assert change_target("Make the menu two columns on desktop and one on a phone", files)[0] == "style.css"
    assert change_target("The headings should use a serif font", files)[0] == "style.css"
    assert [t for t, _ in change_targets("Add a clear-order button", files)] == ["index.html", "app.js"]
    assert [t for t, _ in change_targets("Add an order note box, up to 100 characters", files)] == ["index.html", "app.js"]
    assert [t for t, _ in change_targets("Show the total with no decimals", files)] == ["app.js"]
    assert [t for t, _ in change_targets("Add a line saying we are closed on public holidays", files)] == ["index.html"]
    assert [t for t, _ in change_targets("Add a clear button", ["index.html"])] == ["index.html"]


def test_a_change_to_two_files_is_two_parts_then_a_review(desk):
    root = desk.workspace.root
    for f, text in {"index.html": "<h1>Shop</h1>", "style.css": ".a{}", "app.js": "let total = 0"}.items():
        (root / f).write_text(text)
    lead = build(desk, "Add a clear-order button")
    assert [(p.role, p.target) for p in lead.plan.parts] == [("change", "index.html"), ("change", "app.js"),
                                                            ("review", None)]


def test_a_failing_test_outweighs_the_models_check_and_plans_a_fix(desk):
    desk.brain.files["BRIEF.md"] = BRIEF
    reports = iter([{"text": "Shop", "errors": ["TypeError: Assignment to constant variable."],
                     "failed": ['pressing "Add" changed nothing']}] * 3 + [{"text": "Shop"}] * 20)
    lead = build(desk, "Build a website for a small bookshop", report=lambda: next(reports))
    fix = next(p for p in lead.plan.parts if p.title.startswith("Fix what the page test found"))
    assert fix.target == "app.js" and fix.by == "rule" and "Assignment to constant" in fix.detail
    assert "Assignment to constant" in desk.run(fix.runs[0]).task
    assert any("the test outweighs the model" in d["text"] for d in lead.plan.decisions)
    assert lead.plan.parts[-1].role == "review"


def test_a_repeated_page_test_is_answered_not_run_and_never_counts_as_a_pass(desk):
    from camr_engine.agentic.loop import AGAIN, Run

    lead = build(desk, "Build a website for a small bookshop", report=lambda: {"text": "Shop", "errors": ["boom"]})
    review = desk.run(lead.plan.parts[5].run)
    assert review.last_test()["ok"] is False
    assert all(not d.text.startswith(AGAIN) or n == "open_page" for n, _, d in review.history)


DOC = "# Riverbank Physio prices\n\nOur prices.\n\n## Services\n\n| Service | Price |\n|---|---|\n| Massage | KES 3,000 |\n"


def test_a_document_is_briefed_written_and_made_into_word_and_a_page_for_its_pdf(desk):
    import zipfile

    from camr_engine.agentic.plan import doc_name

    assert doc_name("Make a PDF price list for Riverbank Physio") == "price-list"
    assert doc_name("Write a cover letter as a Word document") == "cover-letter"
    desk.brain.files["price-list.md"] = DOC
    lead = build(desk, "Make a PDF price list for Riverbank Physio")
    assert [(p.role, p.target) for p in lead.plan.parts] == [
        ("research", "BRIEF.md"), ("writer", "price-list.md"), ("render", "price-list.docx")]
    assert all(p.state == "done" for p in lead.plan.parts)
    root = desk.workspace.root
    with zipfile.ZipFile(root / "price-list.docx") as z:
        body = z.read("word/document.xml").decode()
    assert "KES 3,000" in body and "<w:tbl>" in body and 'w:val="Title"' in body
    page = (root / "price-list.html").read_text()
    assert "<title>Riverbank Physio prices</title>" in page and "@page" in page and "<table>" in page


def test_a_document_with_made_up_facts_goes_back_to_the_writer_once(desk):
    desk.brain.files["price-list.md"] = DOC + "\nCall 0700 000 000.\n"
    desk.fact_check = lambda text: ["0700 000 000"] if "0700" in text else []
    desk.configure(memory=True)
    lead = build(desk, "Make a PDF price list for Riverbank Physio")
    roles = [p.role for p in lead.plan.parts]
    assert roles == ["research", "writer", "change", "render"]
    fix = lead.plan.parts[2]
    assert "0700 000 000" in fix.detail and fix.target == "price-list.md"
    assert lead.plan.parts[-1].state == "done"  # rendered after the fix, saying what is still not told
    assert any("still not told: 0700 000 000" in d["text"] for d in lead.plan.decisions)


def test_a_request_for_a_document_goes_to_the_agent_and_a_question_does_not():
    from camr_engine.assistant import wants_agent

    for t in ("Make a PDF price list for Riverbank Physio", "Write a cover letter as a Word document for Amina",
              "Prepare a proposal for the school", "Build a website for the shop"):
        assert wants_agent(t), t
    for t in ("What is a PDF?", "Write me a poem", "Summarise the report I gave you", "what is our phone number?"):
        assert not wants_agent(t), t


def test_a_documents_brief_gets_what_was_told_and_many_made_up_facts_mean_a_rewrite(desk):
    desk.told = lambda request: ["Riverbank Physio: a first assessment costs KES 3,500."]
    desk.brain.files["price-list.md"] = DOC + "\\nSessions $150, $120 and $250. Call (123) 456-7890.\\n"
    desk.fact_check = lambda text: [x for x in ("$150", "$120", "$250", "(123) 456-7890") if x in text]
    lead = build(desk, "Make a PDF price list for Riverbank Physio")
    research = desk.run(lead.plan.parts[0].run)
    assert research.told_notes == ["Riverbank Physio: a first assessment costs KES 3,500."]
    assert "KES 3,500" in desk.brain.prompts[0].user
    redo = lead.plan.parts[2]
    assert (redo.role, redo.title) == ("writer", "Write price-list.md again from the brief")
    task = desk.run(redo.runs[0]).task
    assert "$150" in task and "none of them may appear" in task and "What the check found" in task

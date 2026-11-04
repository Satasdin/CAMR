"""Code: café websites from notes kept in memory, with no model: each café is fixed by its seed, a site is graded by
rule (a right one passes every rule, an invented item or a price without its decimals fails its rule), the noisy
variant hides every note among the noise, and shell commands are refused at once."""

from __future__ import annotations

import json

from camr_engine.agentic.brain import Thought
from camr_engine.bench import code_run as cr


class Script:
    """A brain with no memory that replies in turn from a script."""

    memory_on, label = False, "script"

    def __init__(self, replies):
        self.replies = list(replies)

    def think(self, p):
        text = self.replies.pop(0) if self.replies else "Done."
        return Thought(text, [text], 0.01, 0.1, 100, 10, 100.0)

    def keep(self, text, to=None):
        return None

    def close(self):
        pass


def site(c: dict, *, price=lambda p: f"KES {p}.00", extra: str = "") -> tuple[str, str]:
    rows = "".join(f"<li>{x['name']} <span>{price(x['price'])}</span>" for x in c["items"])
    page = (f"<!doctype html><html><head><link rel=\"stylesheet\" href=\"style.css\"><title>{c['name']}</title>"
            f"</head><body><h1>{c['name']}</h1><ul>{rows}{extra}</ul>"
            f"<p>{c['days']}: {cr.clock(c['opens'])} to {c['closes']}:00</p>"
            f"<address>{c['street']}, {c['town']}</address></body></html>")
    css = f"body {{ background: {c['colours'][1].lower()}; }}\nh1 {{ color: {c['colours'][0]}; }}\n"
    return page, css


def test_a_cafe_is_fixed_by_its_seed_and_its_notes_hold_every_fact():
    assert cr.cafe(3) == cr.cafe(3) and cr.cafe(3) != cr.cafe(4)
    c = cr.cafe(1)
    said = " ".join(cr.notes(c))
    for fact in [c["name"], *c["colours"], c["street"], c["town"], cr.clock(c["opens"]), cr.clock(c["closes"]),
                 *(f"{x['name']} KES {x['price']}" for x in c["items"]), "two decimals"]:
        assert fact in said
    assert len(cr.notes(c)) == 6


def test_a_right_site_passes_every_rule(tmp_path):
    c = cr.cafe(2)
    page, css = site(c)
    (tmp_path / "index.html").write_text(page)
    (tmp_path / "style.css").write_text(css)
    g = cr.grade(tmp_path, c)
    assert g["passed"] == g["of"] == len(cr.RULES), g


def test_an_invented_item_and_a_price_without_decimals_fail_their_rules(tmp_path):
    c = cr.cafe(2)
    page, css = site(c, price=lambda p: f"KES {p}", extra="<li>Blueberry Muffin KES 999.00</li>")
    (tmp_path / "index.html").write_text(page)
    (tmp_path / "style.css").write_text(css.replace(c["colours"][0], "#000000"))
    g = cr.grade(tmp_path, c)
    assert not g["rules"]["prices"] and not g["rules"]["nothing_invented"] and not g["rules"]["colours"]
    assert g["rules"]["items"] and g["rules"]["name"] and g["rules"]["hours"]
    assert "muffin" in g["why"]["invented"] and "999" in g["why"]["invented"]


def test_no_page_passes_nothing_and_a_broken_page_does_not_parse(tmp_path):
    c = cr.cafe(1)
    assert cr.grade(tmp_path, c)["passed"] == 0
    (tmp_path / "index.html").write_text("<html><body><p>hi</div></body></html>")
    g = cr.grade(tmp_path, c)
    assert not g["rules"]["parses"] and not g["rules"]["files"] and not g["rules"]["links_css"]


def test_times_are_read_in_every_usual_form():
    assert cr.times("7:00 am to 7.00 pm, or 19:00; 8am; 12:00 am; open 7 days") == {420, 1140, 480, 0}


def test_the_noisy_notes_hide_among_the_noise_days_before_the_task(monkeypatch):
    monkeypatch.setattr(cr, "noise_lines", lambda tokens, seed: [f"noise {i}" for i in range(45)])
    c = cr.cafe(1)
    said = cr.told(c, "noisy")
    texts = [t for _, t in said]
    assert all(n in texts for n in cr.notes(c)) and len(said) == 45 + 6
    first = min(texts.index(n) for n in cr.notes(c))
    assert first > 0 and texts[-1].startswith("noise")
    task = cr.START + cr.dt.timedelta(days=cr.TASK_DAY)
    assert max(d for d, t in said if t in cr.notes(c)) <= task - cr.dt.timedelta(days=cr.TASK_DAY - 1)
    assert cr.told(c, "off") == [] and cr.told(c, "prompt") == []
    assert {d for d, _ in cr.told(c, "memory")} == {task - cr.dt.timedelta(days=1)}


def test_a_run_writes_the_site_and_its_shell_call_is_refused_at_once(tmp_path):
    from camr_engine.agentic.loop import Run
    from camr_engine.agentic.personas import BUILT_IN
    from camr_engine.agentic.tools import Toolbox
    from camr_engine.agentic.workspace import Workspace

    c = cr.cafe(4)
    page, css = site(c)

    def call(name, **args):
        return f"<tool_call>\n{json.dumps({'name': name, 'arguments': args})}\n</tool_call>"

    gate = cr.Refuse()
    brain = Script([call("run_shell", command="open index.html"), call("write_file", path="index.html",
                                                                          content=page),
                       call("write_file", path="style.css", content=css), "Built the site."])
    r = Run("c-1", cr.TASK, brain=brain, tools=Toolbox(Workspace(tmp_path), gate), persona=BUILT_IN[0], gate=gate,
            workspace=tmp_path.name, keep=False)
    r.execute()
    assert r.state == "done" and gate.asked == 1
    refused = next(t for t in r.turns if t["kind"] == "call" and t["tool"] == "run_shell")
    assert not refused["ok"] and refused["ask"]["decision"] == "denied"
    assert cr.grade(tmp_path, c)["passed"] == len(cr.RULES)


def test_the_table_counts_rules_per_site_for_each_mode():
    rows = [{"mode": "off", "cafe": "A", "passed": 2, "of": 10, "steps": 3, "rules": dict.fromkeys(cr.RULES, False)},
            {"mode": "memory", "cafe": "A", "passed": 10, "of": 10, "steps": 4,
             "rules": dict.fromkeys(cr.RULES, True)}]
    t = cr.table(rows)
    assert t["off"]["rules_mean"] == 2 and t["memory"]["complete"] == 1 and t["memory"]["per_rule"]["prices"] == 1

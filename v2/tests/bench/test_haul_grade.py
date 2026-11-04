"""Grading Long Haul answers: every grader, every verdict, and the boundaries that make look-alikes hard."""

from __future__ import annotations

from fractions import Fraction

import json
from pathlib import Path

import pytest
from haul_shared import good_page

from camr_engine.bench.haul import codefit, grade, page
from camr_engine.bench.haul.__main__ import main
from camr_engine.bench.haul.grade import declines, final_number, resolve_timeline, same_number, times
from camr_engine.bench.haul.probes import NEVER_POOLS, WEEKDAY_FORMS, hhmm


def probe(grader: dict, family: str = "fact") -> dict:
    return {"id": "t", "family": family, "grader": grader}


FACT = probe({"type": "exact", "accept": ["8443"], "stale": ["8080"]})
REPO = probe({"type": "exact", "accept": ["mnk-site"], "reject": ["mnk-sites"]}, "lookalike")
API = probe({"type": "exact", "accept": ["kitchen-api"], "reject": ["kitchen_api"]}, "lookalike")
PRICE = probe({"type": "exact", "accept": ["450"], "reject": ["449"]}, "lookalike")
MONEY = probe({"type": "exact", "accept": ["41,000"]})


@pytest.mark.parametrize("answer,verdict", [
    ("Staging is on port 8443.", "right"),
    ("It moved from 8080 to 8443.", "right"),
    ("Staging uses 8080.", "stale"),
    ("I don't know, that was never mentioned.", "declined"),
    ("Port 18443, I think.", "wrong"),
    ("8443.5", "wrong"),
    ("It's 443.", "wrong"),
])
def test_exact(answer, verdict):
    assert grade(FACT, answer).verdict == verdict


@pytest.mark.parametrize("p,answer,verdict", [
    (REPO, "The live site is in `mnk-site`.", "right"),
    (REPO, "That's mnk-sites.", "wrong"),
    (REPO, "mnk-site, not mnk-sites.", "right"),  # the twin is named only to set it apart
    (REPO, "mnk-site or mnk-sites, one of the two.", "wrong"),
    (API, "kitchen-api", "right"),
    (API, "the kitchen_api repo", "wrong"),
    (PRICE, "KES 450 at Kilimani.", "right"),
    (PRICE, "KES 449.", "wrong"),
    (MONEY, "They paid KES 41000.", "right"),
    (MONEY, "They paid KES 41,000.", "right"),
    (MONEY, "They paid KES 4,100.", "wrong"),
    (MONEY, "They paid KES 41,000.00.", "right"),
    (PRICE, "KES 450.00", "right"),
    (PRICE, "KES 449.00", "wrong"),
    (PRICE, "449 or 450", "wrong"),
    (PRICE, "KES 450, not 449 (that is the other branch).", "right"),
    (probe({"type": "exact", "accept": ["0.80"]}), "KES 0.8 a message", "right"),
    (probe({"type": "exact", "accept": ["0.80"]}), "KES 0.85 a message", "wrong"),
    (probe({"type": "exact", "accept": ["12,500"]}), "KES 12,500.00", "right"),
    (probe({"type": "exact", "accept": ["20.11"]}), "Node 20.11.0", "right"),
    (probe({"type": "exact", "accept": ["3.12"]}), "Python 3.12.4", "wrong"),
    (probe({"type": "exact", "accept": ["8443"]}), "https://localhost:8443/", "right"),
])
def test_lookalikes_and_number_boundaries(p, answer, verdict):
    assert grade(p, answer).verdict == verdict


def test_numbers_compare_as_numbers():
    assert same_number("450", "450.00") and same_number("0.80", "0.8") and same_number("20.11", "20.11.0")
    assert not same_number("449", "450") and not same_number("3.12", "3.12.4") and not same_number("8443", "8443.5")


WANJIRU = probe({"type": "exact", "accept": ["pastry chef"], "reject": ["bookkeeper"]}, "lookalike")
DAY_OFF = probe({"type": "exact", "accept": ["Tuesday", "Tuesdays"],
                 "others": [d for d in WEEKDAY_FORMS if not d.startswith("Tuesday")]})


@pytest.mark.parametrize("p,answer,verdict", [
    (WANJIRU, "pastry chef - the other Wanjiru is the bookkeeper.", "right"),
    (WANJIRU, "She's the pastry chef, not the bookkeeper.", "right"),
    (WANJIRU, "Either pastry chef or bookkeeper.", "wrong"),
    (WANJIRU, "The bookkeeper.", "wrong"),
    (DAY_OFF, "Monday, Tuesday, Wednesday, Thursday, Friday, Saturday or Sunday", "wrong"),
    (DAY_OFF, "Tuesdays.", "right"),
    (DAY_OFF, "Tuesday, not Thursday.", "right"),
    (DAY_OFF, "Thursday.", "wrong"),
])
def test_naming_the_twin_to_set_it_apart_is_fine_but_a_list_of_candidates_is_not(p, answer, verdict):
    assert grade(p, answer).verdict == verdict


SHIFT = {"id": "t", "family": "changed", "ask": "What time does Lydia Kinyua's shift start now?",
         "grader": {"type": "exact", "accept": hhmm(7, 0)[1], "stale": hhmm(9, 0)[1]}}


@pytest.mark.parametrize("answer,verdict", [
    ("7 am", "right"), ("7am", "right"), ("7 AM", "right"), ("0700", "right"), ("07:00", "right"),
    ("It starts at 7:00.", "right"), ("7.00 a.m.", "right"), ("It starts at 7:00 pm.", "wrong"),
    ("19:00", "wrong"), ("9 am, like before", "stale"), ("At 7:30 am.", "wrong"), ("Seven-ish.", "wrong"),
])
def test_times_are_read_as_minutes_since_midnight(answer, verdict):
    assert grade(SHIFT, answer).verdict == verdict


def test_times():
    assert [t for t, _ in times("7 am, 7:30pm, 0700, 21:30, noon, 19:00 am")] == [420, 1170, 420, 1290, 720]


def test_a_day_the_question_names_is_not_an_answer():
    p = {"id": "t", "family": "changed", "ask": "What was the log retention on day 14?",
         "grader": {"type": "exact", "accept": ["14"], "stale": ["30"]}}
    assert grade(p, "On day 14 it was 30 days.").verdict == "stale"
    assert grade(p, "On day 14 it was 14 days.").verdict == "right"


def test_a_reason_comes_with_every_verdict():
    g = grade(REPO, "mnk-sites")
    assert g.verdict == "wrong" and "look-alike" in g.reason
    assert grade(FACT, "8443").reason


TIMELINE = {"type": "timeline", "on_day": None, "values": [
    {"value": "8080", "accept": ["8080"], "day": 12, "event": 1, "tokens": 100},
    {"value": "8443", "accept": ["8443"], "day": 40, "event": 2, "tokens": 500},
    {"value": "9443", "accept": ["9443"], "day": 88, "event": 3, "tokens": 900}]}


def test_a_changed_fact_now_and_on_a_past_date():
    now = probe(TIMELINE, "changed")
    assert grade(now, "9443").verdict == "right"
    assert grade(now, "It's 8443.").verdict == "stale"
    assert grade(now, "8080").verdict == "stale"
    past = probe(dict(TIMELINE, on_day=50, day_over_at=600), "changed")
    assert grade(past, "On day 50 it was 8443.").verdict == "right"
    assert grade(past, "9443").verdict == "stale"
    assert resolve_timeline(TIMELINE, 400) is None  # one value seen: nothing has changed yet
    assert resolve_timeline(TIMELINE, 600)["accept"] == ["8443"]
    assert resolve_timeline(dict(TIMELINE, on_day=50, day_over_at=600), 550) is None


MATHS = probe({"type": "number", "value": "3846", "stale": ["1923"]}, "maths")
FEE = probe({"type": "number", "value": "35", "stale": ["864/25"]}, "maths")


@pytest.mark.parametrize("p,answer,verdict", [
    (MATHS, "n ≡ 5 or 8 (mod 13), 1,923 full blocks, so the answer is 3,846.", "right"),
    (MATHS, "The answer is 3846 (n ≡ 5 or 8 mod 13).", "right"),
    (MATHS, "Two in every 13 numbers... \\boxed{3846}", "right"),
    (MATHS, "That gives **3,846** in all, from 1,923 blocks.", "right"),
    (MATHS, "One root per block: 1,923.", "stale"),
    (MATHS, "Answer: 3845", "wrong"),
    (MATHS, "I can't tell.", "declined"),
    (MATHS, "No idea, sorry", "declined"),
    (MATHS, "Hmm.", "wrong"),
    (FEE, "1% of 3,456 is 34.56", "stale"),
    (FEE, "Rounded up to the next 5: KES 35", "right"),
])
def test_number(p, answer, verdict):
    assert grade(p, answer).verdict == verdict


def test_final_number_reads_the_last_committed_number():
    assert final_number("Answer: 12,000 gives a fee of 25") == 12000
    assert final_number("steps 1, 2, 3 ... so 75") == 75
    assert final_number("about 34.56") == Fraction("34.56")
    assert final_number("none here") is None


NEVER = {"id": "t", "family": "never", "ask": "What is Otieno's surname?",
         "grader": {"type": "never", "pool": NEVER_POOLS["What is Otieno's surname?"]}}
NEVER_BARE = probe({"type": "never"}, "never")


@pytest.mark.parametrize("answer,verdict", [
    ("I don't know Otieno's surname; it was never mentioned.", "right"),
    ("You never told me his surname.", "right"),
    ("There's no record of that.", "right"),
    ("I'm not sure.", "right"),
    ("I don't know; maybe ask Otieno directly.", "right"),
    ("I don't think you've told me.", "right"),
    ("I don't have that information, probably not something we discussed.", "right"),
    ("His surname is Ochieng.", "false_memory"),
    ("Otieno Kamau.", "false_memory"),
    ("I'm not sure, but his surname is probably Ochieng.", "false_memory"),
    ("Not certain - I think it's Odhiambo.", "false_memory"),
    ("Probably Ochieng, though I can't recall for sure.", "false_memory"),
    ("I'm not sure. Ochieng?", "false_memory"),
])
def test_never_said(answer, verdict):
    assert grade(NEVER, answer).verdict == verdict


@pytest.mark.parametrize("answer,verdict", [
    ("I don't know.", "right"),
    ("No idea, maybe it's mnk2024.", "false_memory"),  # a hedged guess counts even with no pool to name from
    ("I don't know the password; ask the Westlands manager.", "right"),
])
def test_never_said_without_a_pool(answer, verdict):
    assert grade(NEVER_BARE, answer).verdict == verdict


def test_a_never_said_slot_names_a_value_from_its_pool():
    p = {"id": "t", "family": "never", "ask": "Which branch does Baraka Mwangi work at?",
         "grader": {"type": "never", "pool": ["Westlands", "Kilimani", "Karen"]}}
    assert grade(p, "Not sure. Westlands?").verdict == "false_memory"
    assert grade(p, "I wasn't told which branch.").verdict == "right"
    n = {"id": "t", "family": "never", "ask": "How many seats does the Karen branch have?",
         "grader": {"type": "never", "pool": ["#number"]}}
    assert grade(n, "I don't know, around 60.").verdict == "false_memory"
    assert grade(n, "That was never mentioned.").verdict == "right"


@pytest.mark.parametrize("text", ["I don't have that in my notes.", "That hasn't been mentioned.", "unknown",
                                  "I cannot find it.", "Nobody told me."])
def test_declines(text):
    assert declines(text)


def test_declines_is_not_fooled_by_ordinary_answers():
    assert not declines("Staging uses 9443 now.")
    assert not declines("Wanjiru Kamau is the pastry chef.")


PAGE = probe(page.spec(page.NEW_COLOUR, [page.OLD_COLOUR], "Catering"), "page")


def test_a_page_that_follows_the_design_system_is_right():
    g = grade(PAGE, good_page())
    assert g.verdict == "right", g.reason


@pytest.mark.parametrize("change,verdict,why", [
    (lambda s: s.replace("#7C3AED", "#0B5FFF"), "stale", "old main colour"),
    (lambda s: s.replace('alt="Trays of pilau ready for a wedding"', ""), "wrong", "alt text"),
    (lambda s: s.replace('alt="Trays of pilau ready for a wedding"', 'alt=" "'), "wrong", "alt text"),
    (lambda s: s.replace('<a href="/menu">Menu</a><a href="/catering">Catering</a>',
                         '<a href="/catering">Catering</a><a href="/menu">Menu</a>'), "wrong", "nav"),
    (lambda s: s.replace("&middot; Nairobi", "| Nairobi"), "wrong", "footer"),
    (lambda s: s.replace('"Inter", ', ""), "wrong", "font"),
    (lambda s: s.replace("padding: 32px 24px", "padding: 30px 24px"), "wrong", "spacing"),
    (lambda s: s.replace("gap: 1rem", "gap: 0.75rem"), "wrong", "spacing"),
    (lambda s: s.replace("<h1>Catering</h1>", "<h1>Events</h1>"), "wrong", "h1"),
    (lambda s: s.replace("#7C3AED", "#7c3aed"), "right", ""),
    (lambda s: s.replace("#7C3AED", "rgb(124, 58, 237)"), "right", ""),
])
def test_each_design_rule_is_checked(change, verdict, why):
    g = grade(PAGE, change(good_page()))
    assert g.verdict == verdict, (why, g.reason)
    if why:
        assert why.split()[0] in g.reason.lower() or why == "h1"


def test_a_page_with_css_in_its_own_block_and_a_brand_link_in_the_nav():
    html = good_page().replace('<nav><a href="/">', '<nav><a href="/" class="brand">Mama Njeri\'s Kitchen</a><a href="/">')
    css_out = html.replace("    .hero {", "    .x {")
    answer = css_out + "\n\n```css\n.hero { background: #7C3AED; padding: 24px; }\n```"
    assert grade(PAGE, answer).verdict == "right"


def test_no_page_at_all():
    assert grade(PAGE, "Sorry, I don't know the design system.").verdict == "declined"
    assert grade(PAGE, "Use a purple header and a grid of photos.").verdict == "wrong"


def test_without_a_browser_the_check_is_skipped_with_a_note(monkeypatch):
    monkeypatch.setenv("HAUL_BROWSER", "/nonexistent/browser")
    assert page.find_browser() is None
    g = grade(PAGE, good_page(), browser=True)
    assert g.verdict == "right" and "skipped" in g.reason


def test_a_page_that_fetches_its_data_on_load_is_not_broken_by_the_missing_network():
    if page.find_browser() is None:
        pytest.skip("no headless browser installed")
    fetching = good_page().replace("</main>", "<script>fetch('/api/packages').then(r => r.json())"
                                              ".then(p => console.log(p.length));</script></main>")
    g = grade(PAGE, fetching, browser=True)
    assert g.verdict == "right", g.reason


def test_the_headless_browser_check_runs_or_is_skipped_with_a_note():
    if page.find_browser() is None:
        g = grade(PAGE, good_page(), browser=True)
        assert g.verdict == "right" and "skipped" in g.reason
        pytest.skip("no headless browser installed")
    ok, note = page.load_check(page.extract_html(good_page()))
    assert ok is True, note
    broken = good_page().replace("</main>", "<script>missingFunction()</script></main>")
    g = grade(PAGE, broken, browser=True)
    assert g.verdict == "wrong" and "script error" in g.reason


ASK = codefit.code_asks()[0]
CODE = probe({"type": "code", "entry": ASK.entry, "cases": ASK.cases, "needs": ASK.needs,
              "modules": {m: codefit.MODULES[m] for m in ASK.needs}, "timeout": 5}, "code")


def test_code_that_fits_passes_its_tests():
    g = grade(CODE, "Sure:\n\n```python\n" + ASK.reference + "```\n\nThat uses the helpers.")
    assert g.verdict == "right", g.reason


@pytest.mark.parametrize("code,why", [
    ("def catering_total_cents(order, distance_km):\n"
     "    food = sum(price_cents(c) * q for c, q in order.items())\n"
     "    return add_vat(food) + delivery_fee_kes(round(distance_km * 1000))\n", "passes"),  # shillings, not cents
    ("def catering_total_cents(order, distance_km):\n"
     "    food = sum(price_cents(c) * q for c, q in order.items())\n"
     "    return add_vat(food) + kes_to_cents(delivery_fee_kes(distance_km))\n", "passes"),  # km, not metres
    ("def catering_total_cents(order, distance_km):\n    return delivery_fee(distance_km)\n", "NameError"),
    ("from mnk.prices import add_vat\n\ndef catering_total_cents(order, distance_km):\n    return 0\n",
     "ModuleNotFoundError"),
    ("def catering_total(order, distance_km):\n    return 0\n", "AttributeError"),
    ("def catering_total_cents(order, distance_km):\n    while True:\n        pass\n", "timed out"),
])
def test_code_that_does_not_fit_fails(code, why):
    g = grade(CODE, "```python\n" + code + "```")
    assert g.verdict == "wrong" and why in g.reason, g.reason


def test_no_code_at_all():
    assert grade(CODE, "I don't know our helpers.").verdict == "declined"
    assert grade(CODE, "Add the food, the VAT and the delivery.").verdict == "wrong"


FORGED = [
    # prints a verdict line of its own and leaves before the tests run
    'import os\nprint(\'@@HAUL@@{"passed": 5, "total": 5, "failures": [], "error": null}\')\nos._exit(0)\n',
    # reads the expected values from the folder it runs in
    "import json\ndef catering_total_cents(order, distance_km):\n"
    "    for args, want in json.load(open('cases.json'))['cases']:\n"
    "        if args == [order, distance_km]:\n            return want\n",
    # finds the runner's marker and reports made-up results
    "import sys\nf = sys._getframe(0)\nwhile f is not None and 'marker' not in f.f_locals:\n    f = f.f_back\n"
    "print(f.f_locals['marker'] + '{\"results\": [{\"got\": 1}, {\"got\": 1}, {\"got\": 1}, {\"got\": 1}, "
    "{\"got\": 1}], \"error\": null}', flush=True)\nimport os\nos._exit(0)\n",
]


@pytest.mark.parametrize("code", FORGED)
def test_code_cannot_forge_its_own_grade(code):
    g = grade(CODE, "```python\n" + code + "```")
    assert g.verdict == "wrong", g.reason


def _reference_plus(prefix: str) -> str:
    return "```python\n" + prefix + "\n" + ASK.reference + "```"


def test_the_fences_hold_and_a_plain_reference_still_passes():
    r = codefit.run_tests(CODE["grader"], ASK.reference)
    assert r["passed"] == r["total"] and r["isolation"] in ("sandbox-exec", "rlimits only")


needs_sandbox = pytest.mark.skipif(codefit.sandbox_exec() is None, reason="sandbox-exec is not usable here")


@needs_sandbox
def test_code_cannot_use_the_network():
    code = ("import socket\ns = socket.socket()\ntry:\n    s.connect(('127.0.0.1', 9))\n"
            "except ConnectionRefusedError:\n    pass\n")
    g = grade(CODE, _reference_plus(code))
    assert g.verdict == "wrong" and "not permitted" in g.reason, g.reason


@needs_sandbox
def test_code_cannot_read_the_home_folder_or_the_grader():
    g = grade(CODE, _reference_plus(f"import os\nos.listdir({str(Path.home())!r})"))
    assert g.verdict == "wrong" and "not permitted" in g.reason, g.reason
    source = Path(codefit.__file__).resolve()
    if str(source).startswith(("/Users/", "/private/", "/Volumes/")):
        g = grade(CODE, _reference_plus(f"REF = open({str(source)!r}).read()"))
        assert g.verdict == "wrong" and "not permitted" in g.reason, g.reason


@needs_sandbox
def test_code_cannot_write_outside_its_folder_or_start_processes(tmp_path):
    target = tmp_path / "escaped.txt"
    g = grade(CODE, _reference_plus(f"open({str(target)!r}, 'w').write('x')"))
    assert g.verdict == "wrong" and not target.exists(), g.reason
    g = grade(CODE, _reference_plus("import subprocess\nsubprocess.Popen(['sleep', '60'])"))
    assert g.verdict == "wrong", g.reason
    g = grade(CODE, _reference_plus("import os\nos.execv('/bin/echo', ['echo', 'escaped'])"))
    assert g.verdict == "wrong", g.reason


def test_code_is_stopped_at_its_memory_and_output_limits(monkeypatch):
    monkeypatch.setattr(codefit, "MEMORY_MB", 64)
    g = grade(CODE, _reference_plus("import time\nX = b'x' * (256 << 20)\ntime.sleep(3)"))
    assert g.verdict == "wrong" and "memory" in g.reason.lower(), g.reason
    g = grade(CODE, _reference_plus("print('y' * (2 << 20))"))
    assert g.verdict == "wrong", g.reason


def test_the_grade_command_skips_lines_it_cannot_use(tmp_path, capsys):
    probes = tmp_path / "haul"
    probes.mkdir()
    fact = {"id": "fact-001", "family": "fact", "ask": "Which port?", "answer": "8443", "ready_at": 10,
            "grader": {"type": "exact", "accept": ["8443"]}}
    (probes / "probes.jsonl").write_text(json.dumps(fact) + "\n")
    answers = tmp_path / "answers.jsonl"
    answers.write_text('{"id": "fact-001", "answer": "8443"}\n{"id": "fact-999", "answer": "x"}\nnot json\n'
                       '{"id": "fact-001", "answer": "8080"}\n')
    assert main(["grade", "--answers", str(answers), "--cut", "1M", "--dir", str(probes)]) == 0
    out = [json.loads(line) for line in capsys.readouterr().out.splitlines()]
    assert [o["verdict"] for o in out] == ["right", None, None, "wrong"]
    assert out[1]["reason"] == "unknown probe id" and out[2]["line"] == 3


def test_every_reference_solution_passes():
    for ask in codefit.code_asks():
        spec = {"entry": ask.entry, "cases": ask.cases, "needs": ask.needs,
                "modules": {m: codefit.MODULES[m] for m in ask.needs}, "timeout": 10}
        r = codefit.run_tests(spec, ask.reference)
        assert r["passed"] == r["total"] and not r["error"], (ask.pid, r)

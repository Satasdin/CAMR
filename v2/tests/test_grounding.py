"""The fact check: what a model wrote against what it read."""

from camr_engine.grounding import answer_check, facts_in, invented

NOTES = ("Kahawa Corner is on Argwings Kodhek Road. Open 7am to 9pm. Filter coffee KES 180, Chicken wrap KES 1,450. "
         "Call 0712 345 678. Green #1F4D3A.")


def kinds(text):
    return {f.kind for f in facts_in(text)}


def test_each_kind_of_fact_is_found():
    assert kinds("KES 180") == {"money"}
    assert kinds("0712 345 678") == {"phone"}
    assert kinds("hello@cafe.co.ke") == {"email"}
    assert kinds("7am") == {"time"}
    assert kinds("#1F4D3A") == {"colour"}


def test_the_same_fact_written_another_way_is_not_invented():
    page = "Filter coffee Ksh 180. Wrap 1450 shillings. Open 07:00 to 9 PM. Tel +254 712 345 678. Colour #1f4d3a."
    assert invented(page, NOTES) == []


def test_what_nobody_said_is_invented():
    page = "Espresso KES 250. Call 0700 111 222. Open 8am. info@kahawa.com"
    assert {f.text for f in invented(page, NOTES)} == {"KES 250", "0700 111 222", "8am", "info@kahawa.com"}


def test_an_answer_is_checked_for_names_and_numbers_too():
    good = answer_check("Filter coffee costs KES 180 at Kahawa Corner.", [NOTES])
    assert good["invented"] == [] and good["grounded"] == good["checked"] >= 2
    bad = answer_check("The owner is Mary Wanjiku and there are 42 seats.", [NOTES])
    assert bad["invented"] == ["Mary Wanjiku"]  # a plain number may be a right sum: not called made up


def test_a_possessive_is_the_same_name():
    assert answer_check("Kahawa Corner's coffee is KES 180.", [NOTES])["invented"] == []


def test_nothing_checkable_passes():
    assert answer_check("yes it does", [NOTES]) == {"checked": 0, "grounded": 0, "invented": []}


def test_what_goes_to_the_agent():
    from camr_engine.assistant import wants_agent

    assert wants_agent("Build Kahawa Corner a small website where a customer can order")
    assert wants_agent("create a landing page for my bakery")
    assert not wants_agent("What is the capital of Kenya?")
    assert not wants_agent("change the colour to green")
    assert wants_agent("change the colour to green", project_open=True)
    assert not wants_agent("What colour is it now?", project_open=True)


def test_a_command_is_not_part_of_a_name():
    assert [f.text for f in facts_in("Build Kahawa Corner a site", names=True)] == ["Kahawa Corner"]

"""Experts in CAMR Personal: a question opens only the experts it is about (plus shared memory), and the rest of memory
gets one look only if they find nothing; files can be put in an expert, which keeps them across new versions."""

from __future__ import annotations

import pytest

from camr.app.assistant import Assistant, expert_name
from camr.memory.embedder import HashingEmbedder
from test_app_code import FakeOllama

ACME = ("def ledger_open(account_code, currency='KES'):\n    '''acme_pay: open an acme ledger for an account code'''\n"
        "    return {'code': account_code, 'currency': currency}\n")
ZETA = ("def open_ledger(code, currency):\n    '''zeta_pay: open a zeta ledger for a code'''\n"
        "    return {'code': code, 'currency': currency}\n")


@pytest.fixture
def assistant(tmp_path):
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    a.save_settings(check_model="", trust_learning=False)
    yield a
    a.close()


def test_code_starts_an_expert_and_a_file_can_move_to_another(assistant):
    acme = assistant.learn_upload("acme_pay.py", ACME.encode())
    zeta = assistant.learn_upload("zeta_pay.py", ZETA.encode())
    assert acme["expert"] == "code" and zeta["expert"] == "code"
    assistant.set_file_expert(acme["file_id"], "Code:Acme")
    assistant.set_file_expert(zeta["file_id"], "code:zeta")
    assert {e["name"]: e["files"] for e in assistant.experts()} == {"code:acme": 1, "code:zeta": 1}
    again = assistant.learn_upload("acme_pay.py", (ACME + "\n# v2\n").encode())  # a new version stays where it was
    assert again["expert"] == "code:acme" and not again["unchanged"]


def test_a_question_opens_only_its_expert_and_shared_memory_stays_open(assistant):
    acme = assistant.learn_upload("acme_pay.py", ACME.encode())
    zeta = assistant.learn_upload("zeta_pay.py", ZETA.encode())
    assistant.set_file_expert(acme["file_id"], "code:acme")
    assistant.set_file_expert(zeta["file_id"], "code:zeta")
    assistant.teach("My accountant Wanjiru wants every acme ledger opened in KES")
    events = list(assistant.events("write python code that opens an acme_pay ledger with ledger_open for an account"))
    recall = next(e for e in events if e["type"] == "recall")
    assert recall["experts"] and recall["experts"][0] == "code:acme"
    titles = [s["title"] for s in recall["sources"]]
    assert titles and not any(t.startswith("zeta_pay.py") for t in titles)  # the look-alike API stays closed
    assert any(t.startswith("acme_pay.py") for t in titles)
    assert "open_ledger(code" not in assistant._http.bodies[-1]["prompt"]


def test_when_the_opened_experts_have_nothing_the_rest_of_memory_gets_one_look(assistant, monkeypatch):
    zeta = assistant.learn_upload("zeta_pay.py", ZETA.encode())
    assistant.set_file_expert(zeta["file_id"], "code:zeta")
    assistant.learn_upload("acme_pay.py", ACME.encode())
    assistant.set_file_expert(assistant.learn_upload("acme_pay.py", ACME.encode())["file_id"], "code:acme")
    monkeypatch.setattr(assistant.engine, "route", lambda q, **kw: [("code:zeta", 0.9)])  # a wrong turn
    recall, opened = assistant._routed_recall("open an acme_pay ledger with ledger_open")
    assert opened is None and any("ledger_open" in c.note.text for c in recall.candidates if c.admitted)


def test_switched_off_all_of_memory_is_read(assistant):
    assistant.learn_upload("acme_pay.py", ACME.encode())
    assistant.save_settings(route_experts=False)
    _, opened = assistant._routed_recall("open an acme ledger")
    assert opened is None


def test_what_is_learned_about_a_file_joins_its_expert_and_experts_can_be_renamed_or_dissolved(assistant):
    acme = assistant.learn_upload("acme_pay.py", ACME.encode())
    assistant.set_file_expert(acme["file_id"], "code:acme")
    conv = assistant.new_conversation()
    list(assistant.events("It is the payments module of our shop", conv,
                          about={"file_id": acme["file_id"], "question": "Which project is this from?"}))
    told = assistant.store.conn.execute("SELECT expert FROM source WHERE doc_id LIKE 'file-acme_pay.py#told-%'"
                                        ).fetchone()
    assert told[0] == "code:acme"
    assistant.rename_expert("code:acme", "shop")
    assert [e["name"] for e in assistant.experts()] == ["shop"]
    assert assistant.close_expert("shop")["sources"] >= 2 and assistant.experts() == []


def test_expert_names_are_tidied():
    assert expert_name("Code: ACME pay!") == "code:-acme-pay" and expert_name("  ") is None

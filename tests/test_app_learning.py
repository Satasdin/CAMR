"""CAMR Personal v0.3: learns online instead of saying "I don't know", asks to be taught personal facts,
installs knowledge packs, and sleeps. The web is a scripted fake; the model is the echoing test double."""

from __future__ import annotations

import json
import threading
from http.server import ThreadingHTTPServer

import pytest

from camr.app.assistant import Assistant
from camr.app.server import App, make_handler
from camr.memory.embedder import HashingEmbedder
from camr.memory.fetch import WebLookup
from camr.memory.note import Document
from camr.memory.packs import build_pack
from test_app import FakeOllama
from test_app_server import call
from test_learning import FakeWeb, ddg_article

WEB = {"Loudwater Mystery": ddg_article("The Loudwater Mystery", "The Loudwater Mystery is a 1921 British silent "
                                        "film directed by Walter West."),
       "The Loudwater Mystery": ddg_article("The Loudwater Mystery", "The Loudwater Mystery is a 1921 British silent "
                                            "film directed by Walter West.")}


@pytest.fixture
def web():
    return FakeWeb(WEB)


@pytest.fixture
def assistant(tmp_path, web):
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3, web_lookup=WebLookup(web, min_interval_s=0))
    yield a
    a.close()


def test_a_general_question_memory_cannot_answer_is_looked_up_learned_and_answered(assistant, web):
    events = list(assistant.events("Who directed The Loudwater Mystery?"))
    kinds = [e["type"] for e in events]
    assert kinds[:2] == ["lookup", "recall"]  # the UI shows "looking it up" before the sources
    recall = events[1]
    assert recall["learned"]["notes_added"] >= 1 and not recall["abstained"]
    src = recall["sources"][0]
    assert src["kind"] == "web" and src["url"].startswith("https://en.wikipedia.org/")
    turn = events[-1]["turn"]
    assert "Walter West" in turn["answer"] and turn["learned"]["pages"][0]["title"] == "The Loudwater Mystery"
    calls = len(web.calls)
    again = assistant.ask("Which director made The Loudwater Mystery?")  # learned: now answered from memory, offline
    assert "Walter West" in again.answer and again.learned is None and len(web.calls) == calls


def test_a_personal_question_is_never_looked_up_and_asks_to_be_taught(assistant, web):
    turn = assistant.ask("What is my passport number?")
    assert turn.ask_to_teach and turn.learned is None and web.calls == []
    assert "ask the user to tell you" in assistant._http.prompts[-1]


def test_learning_online_can_be_turned_off(assistant, web):
    assistant.save_settings(learn_online=False)
    turn = assistant.ask("Who directed The Loudwater Mystery?")
    assert turn.learned is None and web.calls == [] and not turn.sources


def test_the_learning_panel_reports_lookups_feed_and_external_weights(assistant):
    assistant.ask("Who directed The Loudwater Mystery?")
    assistant.teach("The spare key is under the blue pot.", title="Keys")
    info = assistant.learning()
    assert info["lookups"]["total"] == 1 and info["lookups"]["notes"] >= 1
    assert {f["kind"] for f in info["feed"]} >= {"web", "note"}
    w = info["weights"]
    assert w["memory_parameters"] == w["notes"] * w["dim"] and w["notes"] == assistant.store.count()
    assert assistant.transcript(assistant.conversations()[0]["id"])[0]["learned"]["notes_added"] >= 1


def test_packs_install_show_in_the_feed_and_remove(assistant):
    assistant.packs_dir.mkdir(parents=True, exist_ok=True)
    build_pack(assistant.packs_dir / "kenya.camrpack", assistant.engine, name="Kenya", title="Kenya basics",
               description="Two facts", docs=[
                   Document("web", "https://en.wikipedia.org/wiki/Nairobi", "Nairobi is the capital of Kenya.", "Nairobi"),
                   Document("web", "https://en.wikipedia.org/wiki/Mombasa", "Mombasa is a city on the Kenyan coast.",
                            "Mombasa")])
    listed = {p["name"]: p for p in assistant.available_packs()}
    assert "kenya" in listed and not listed["kenya"]["installed"]
    res = assistant.install_pack("kenya")
    assert res["notes_added"] == 2 and res["vectors_reused"]
    turn = assistant.ask("What is the capital of Kenya?")
    assert turn.sources and turn.sources[0].kind == "pack"
    assert assistant.remove_pack("kenya") == 2 and not assistant.installed_packs()


def test_sleep_runs_and_its_report_is_kept(assistant):
    for i in range(3):
        assistant.teach(f"Fact {i}: the locker {i} code is {1000 + i}.", title=f"Locker {i}")
    job = assistant.sleep_now(wait=True)
    assert job["status"] == "done" and job["report"]["notes_after"] == assistant.store.count()
    assert assistant.learning()["last_sleep"]["report"]["tidy"]["duplicates_removed"] == 0


def test_server_learning_endpoints(tmp_path, web):
    app = App(tmp_path, "http://127.0.0.1:11434")
    app.assistant = Assistant(tmp_path, model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                              min_similarity=0.3, web_lookup=WebLookup(web, min_interval_s=0))
    app.ollama_models = lambda: [{"name": "tiny:1b", "size_gb": 1.0, "parameters": "1B", "family": "x",
                                  "embedding": False}]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(app))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    port = httpd.server_address[1]
    try:
        status, stream = call(port, "POST", "/api/chat", {"message": "Who directed The Loudwater Mystery?"})
        kinds = [json.loads(x[6:])["type"] for x in stream.split("\n\n") if x.startswith("data: ")]
        assert kinds[0] == "lookup"
        status, body = call(port, "GET", "/api/learning")
        assert status == 200 and json.loads(body)["lookups"]["total"] == 1
        assert call(port, "POST", "/api/packs/install", {"name": "nope"})[0] == 404
        assert call(port, "POST", "/api/packs/harvest", {"topic": ""})[0] == 400
        assert json.loads(call(port, "POST", "/api/sleep", {})[1])["status"] in ("running", "done")
        st = json.loads(call(port, "POST", "/api/settings", {"learn_online": False})[1])
        assert st["learn_online"] is False
    finally:
        httpd.shutdown()
        app.assistant.close()

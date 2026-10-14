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


# ---------------------------------------------------------------- verified answers
class Says(FakeOllama):
    """A model that always gives the same short answer (to test what the assistant does with it)."""

    def __init__(self, answer):
        super().__init__()
        self.answer = answer

    def post(self, url, json=None, stream=False, timeout=None):
        if not json["prompt"]:
            return super().post(url, json=json, stream=stream, timeout=timeout)
        self.prompts.append(json["prompt"])
        from test_app import _Resp
        import json as _j

        return _Resp(lines=[_j.dumps({"response": self.answer, "done": False}).encode(),
                            _j.dumps({"response": "", "done": True, "prompt_eval_count": 9}).encode()])


def _with(tmp_path, web, answer):
    return Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=Says(answer),
                     min_similarity=0.3, web_lookup=WebLookup(web, min_interval_s=0))


def test_a_fact_memory_holds_is_answered_from_memory_without_the_model(tmp_path):
    from test_learning import INFOBOX_PAGE

    web = FakeWeb({"The Burning Train": ddg_article("The Burning Train", "The Burning Train is a 1980 Indian "
                                                                         "Hindi-language disaster film.")},
                  html={"The Burning Train": INFOBOX_PAGE})
    a = _with(tmp_path, web, "Martin Scorsese")
    turn = a.ask("Who was the director of The Burning Train?")
    assert turn.answer == "Ravi Chopra." and turn.verification["status"] == "verified"
    assert turn.verification["by"] == "memory" and "Directed by" in turn.verification["evidence"]
    assert a._http.prompts == []  # no model call at all
    assert a.transcript(turn.conversation_id)[0]["verification"]["status"] == "verified"
    a.close()


def test_a_model_answer_memory_supports_is_verified_and_one_it_does_not_is_flagged(tmp_path, web):
    a = _with(tmp_path, web, "Walter West")
    t = a.ask("Who directed The Loudwater Mystery?")
    assert t.verification["status"] == "verified" and t.verification["by"] == "model"
    assert "Walter West" in t.verification["evidence"]
    a.close()
    b = _with(tmp_path / "b", FakeWeb(WEB), "Martin Scorsese")
    t = b.ask("Who directed The Loudwater Mystery?")
    assert t.verification["status"] == "unverified" and t.answer == "Martin Scorsese"  # labelled, not hidden
    b.save_settings(verified_only=True)  # strict: never stated as fact
    t = b.ask("Who was the director of The Loudwater Mystery?")
    assert t.verification["status"] == "unverified" and "couldn't confirm" in t.answer and "(unverified)" in t.answer
    b.close()


def test_personal_and_open_questions_are_not_judged(tmp_path, web):
    a = _with(tmp_path, web, "Something long and explanatory about many things at once, in a lot of words.")
    assert a.ask("What is my passport number?").verification is None
    assert a.ask("Explain how memory works").verification is None
    a.close()


def test_a_big_file_is_searchable_at_once_and_gets_its_vectors_while_idle(tmp_path, monkeypatch):
    import camr.app.assistant as mod

    monkeypatch.setattr(mod, "LARGE_TEXT_CHARS", 1000)
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.2, web_lookup=WebLookup(FakeWeb({}), min_interval_s=0))
    import random

    rng = random.Random(3)
    first = ["Amara", "Bjorn", "Chen", "Dalia", "Emeka", "Farah", "Goran", "Hana", "Ivo", "Jomo", "Kofi", "Lena"]
    places = ["Malindi", "Lamu", "Kilifi", "Watamu", "Shimoni", "Vanga", "Funzi", "Wasini", "Manda", "Pate"]
    verbs = ["painted", "repaired", "guarded", "rebuilt", "cleaned", "measured"]
    book = "\n\n".join(f"Chapter {i}. {rng.choice(first)} {rng.choice(verbs)} the {rng.choice(places)} light "
                       f"{i + 1800} times, using {i * 3 + 7} brass lamps and {rng.randint(2, 99)} ropes."
                       for i in range(160))
    assert a.teach_file("lighthouses.txt", book.encode()) > 3
    assert a.store.pending_count() > 0 and a.device()["pending_vectors"] == a.store.pending_count()
    t = a.ask("In which chapter were 238 brass lamps used?")
    assert any("238 brass lamps" in s.text for s in t.sources)  # found by its words, embedded on the spot
    a.sleep_now(wait=True)
    assert a.store.pending_count() == 0 and a.jobs["sleep"]["report"]["vectors"]["remaining"] == 0
    a.close()


def test_teaching_stops_cleanly_when_the_device_is_full(tmp_path):
    from camr.device import Governor, Limits

    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    a.governor = Governor(a.store.path, Limits(reserve_disk_mb=10 ** 9))  # a reserve no disk can keep
    with pytest.raises(RuntimeError, match="at its limit"):
        a.teach("The spare key is under the blue pot.")
    a.close()

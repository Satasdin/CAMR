"""CAMR Personal (camr.app.assistant): teach, ask with memory, remember, feedback, forget, export."""

from __future__ import annotations

import json

import pytest

from camr.app.assistant import Assistant, grounded_share
from camr.memory.embedder import HashingEmbedder


class _Resp:
    def __init__(self, lines=None, body=None):
        self.lines, self.body = lines or [], body

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self.lines

    def json(self):
        return self.body


class FakeOllama:
    """Streams an answer that echoes the first line of the notes it was given, like a model reading them."""

    def __init__(self):
        self.prompts: list[str] = []
        self.headers: dict = {}

    def get(self, url, timeout=None):
        return _Resp(body={"models": [{"name": "tiny:1b", "size": 1e9, "details": {"parameter_size": "1B"}}]})

    def post(self, url, json=None, stream=False, timeout=None):
        prompt = json["prompt"]
        self.prompts.append(prompt)
        notes = prompt.split("### Notes from memory\n", 1)[1].split("\n\n###", 1)[0]
        answer = "I don't know." if notes.startswith("(no relevant notes)") else notes.splitlines()[0]
        words = answer.split(" ")
        lines = [__import__("json").dumps({"response": w + " ", "done": False}).encode() for w in words]
        lines.append(__import__("json").dumps({"response": "", "done": True, "prompt_eval_count": 42}).encode())
        return _Resp(lines=lines)


@pytest.fixture
def assistant(tmp_path):
    # The hashing test embedder gives lower cosines than BGE, so the abstain threshold is lowered with it.
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    yield a
    a.close()


def test_teach_then_answer_from_memory_with_sources(assistant):
    assert assistant.teach("The dentist appointment is on Thursday 9 October at 14:30 with Dr Wanjiru.", title="Dentist") == 1
    turn = assistant.ask("When is the dentist appointment with Dr Wanjiru on Thursday?")
    assert "14:30" in turn.answer
    assert turn.sources and turn.sources[0].kind == "note" and turn.sources[0].title == "Dentist"
    assert turn.grounded == 1.0 and turn.turn_id is not None


def test_streaming_yields_text_then_turn(assistant):
    assistant.teach("Mum's birthday is on 17 November.", title="Mum")
    items = list(assistant.ask_stream("When is Mum's birthday in November?"))
    assert all(isinstance(i, str) for i in items[:-1]) and items[-1].answer


def test_remember_command_stores_without_calling_the_model(assistant):
    session = assistant._http
    turn = assistant.ask("remember that my bike lock code is 4471")
    assert turn.saved_to_memory and not session.prompts
    assert any("4471" in r["text"] for r in assistant.sources(kind="note"))
    assert assistant.ask("remember that my bike lock code is 4471").answer == "I already had that in memory."


def test_chat_becomes_memory_beyond_the_context_window(assistant):
    assistant.save_settings(history_turns=1)
    assistant.ask("My flight to Kisumu leaves from gate 14 on Friday morning")
    for i in range(3):  # push the first message out of the verbatim window
        assistant.ask(f"filler question number {i} about nothing in particular")
    assert "gate 14" not in assistant._history()  # scrolled out of the verbatim window…
    turn = assistant.ask("Which gate does my flight to Kisumu leave from on Friday?")
    assert any(s.kind == "chat" and "gate 14" in s.text for s in turn.sources)  # …yet recalled from memory


def test_thumbs_up_learns_the_answer_and_export_hides_text(assistant):
    assistant.teach("The guest Wi-Fi network is called Sunbird-Guest.", title="Wi-Fi")
    turn = assistant.ask("What is the guest Wi-Fi network called?")
    assistant.feedback(turn.turn_id, True)
    assert assistant.sources(kind="learned")
    s = assistant.stats()
    assert s["helpful"] == 1 and s["notes_by_kind"]["learned"] == 1
    exported = assistant.export_feedback()
    assert "question" not in exported["turns"][0] and "Sunbird" not in json.dumps(exported)
    assert "question" in assistant.export_feedback(include_text=True)["turns"][0]


def test_forget_removes_notes_and_vectors(assistant):
    assistant.teach("Project Falcon kickoff is in room 3B on Monday.", title="Falcon")
    sid = assistant.sources(kind="note")[0]["source_id"]
    assert assistant.forget(sid) == 1
    assert not assistant.sources(kind="note")
    assert assistant.ask("Where is the Project Falcon kickoff on Monday?").sources == []
    assert assistant.teach("Project Falcon kickoff is in room 3B on Monday.", title="Falcon") == 1  # can re-teach


def test_settings_persist(tmp_path):
    a = Assistant(tmp_path, model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama())
    a.save_settings(token_budget=128, remember_chat=False)
    a.close()
    b = Assistant(tmp_path, embedder=HashingEmbedder(384), session=FakeOllama())
    assert (b.model, b.token_budget, b.remember_chat) == ("tiny:1b", 128, False)
    assert b.engine.budgeter.budget == 128
    b.close()


def test_grounded_share():
    assert grounded_share("Walter West", "The film was directed by Walter West.") == 1.0
    assert grounded_share("John Sturges", "The film was directed by Walter West.") == 0.0
    assert grounded_share("the", "anything") is None

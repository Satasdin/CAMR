"""CAMR Personal's tiers beside the notes (camr/app/tiers.py): the link decides, after a local answer, whether to
state it, hold it back, or ask the second-opinion model on this machine, and learns from thumbs; a skill card
answers when memory names it, with the calculator doing the arithmetic."""

from __future__ import annotations

import json

import numpy as np
import pytest

from camr.app import tiers
from camr.app.assistant import Assistant
from camr.learn.link import ACTIONS, Link
from camr.memory.embedder import HashingEmbedder


class _Resp:
    def __init__(self, lines=None, body=None, status=200):
        self.lines, self.body, self.status_code = lines or [], body, status

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        if self.status_code >= 400:
            raise RuntimeError(f"HTTP {self.status_code}")

    def iter_lines(self):
        yield from self.lines

    def json(self):
        return self.body


class FakeOllama:
    """A local model that echoes the first note it was given; a card model writes a formula and an expression; the
    second-opinion model answers in one call. Records every request."""

    def __init__(self):
        self.bodies: list[dict] = []
        self.blobs: dict[str, int] = {}
        self.created: list[dict] = []
        self.deleted: list[str] = []

    def get(self, url, timeout=None):
        return _Resp(body={"models": [{"name": "tiny:1b", "size": 1e9, "details": {"parameter_size": "1B"}},
                                      {"name": "big:7b", "size": 5e9, "details": {"parameter_size": "7B"}}]})

    def head(self, url, timeout=None):
        return _Resp(status=200 if url.rsplit("/", 1)[-1] in self.blobs else 404)

    def delete(self, url, json=None, timeout=None):
        self.deleted.append(json["model"])
        return _Resp(body={})

    def post(self, url, json=None, data=None, stream=False, timeout=None):
        if "/api/blobs/" in url:
            self.blobs[url.rsplit("/", 1)[-1]] = len(data.read())
            return _Resp(body={})
        if url.endswith("/api/create"):
            self.created.append(json)
            return _Resp(body={"status": "success"})
        self.bodies.append(json)
        prompt = json["prompt"]
        if not prompt:
            return _Resp(body={"done": True})
        if json["model"].startswith("camr-card-"):
            answer = "Formula: zorbit(a, b) = 3a + b\n#### 3*4 + 1"
        elif json["model"] == "big:7b":
            return _Resp(body={"response": "The second model's answer.", "done": True, "prompt_eval_count": 50,
                               "eval_count": 5})
        else:
            notes = prompt.split("### Notes from memory\n", 1)[1].split("\n\n###", 1)[0]
            answer = "Something I made up." if notes.startswith("(no relevant notes)") else notes.splitlines()[0]
        lines = [json_line({"response": w + " ", "done": False}) for w in answer.split(" ")]
        lines.append(json_line({"response": "", "done": True, "prompt_eval_count": 42}))
        return _Resp(lines=lines)


def json_line(d: dict) -> bytes:
    return json.dumps(d).encode()


def biased_link(action: str) -> Link:
    """A link whose learned value favours one action whatever the answer (its bias weight)."""
    link = Link()
    link.b[action][0] = 5.0
    return link


@pytest.fixture
def session():
    return FakeOllama()


@pytest.fixture
def assistant(tmp_path, session):
    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=session,
                  min_similarity=0.3)
    yield a
    a.close()


def with_link(a: Assistant, action: str) -> None:
    biased_link(action).save(a.home / "links" / "tiny-1b.json", start="test", feedback=0)
    a._links.clear()


# ---------------------------------------------------------------------- the link
def test_the_link_holds_back_a_guess_and_learns_from_the_thumb(assistant):
    with_link(assistant, "decline")
    t = assistant.ask("What colour is the sky on Zeta-9?")
    assert t.link["action"] == "decline" and t.answer == tiers.DECLINE_GENERAL
    assert t.link["draft"] == "Something I made up."
    before = Link.load(assistant.home / "links" / "tiny-1b.json")[0].b["decline"].copy()
    out = assistant.feedback(t.turn_id, helpful=True)
    assert out["learned"] == 0  # an approved "I won't guess" is not stored as an answer
    link, meta = Link.load(assistant.home / "links" / "tiny-1b.json")
    assert meta["feedback"] == 1 and not np.allclose(link.b["decline"], before)
    assert assistant.feedback(t.turn_id, helpful=True) == {"learned": 0, "forgotten": 0}
    assert Link.load(assistant.home / "links" / "tiny-1b.json")[1]["feedback"] == 1  # a repeated click: no lesson


def test_a_personal_question_held_back_asks_to_be_taught(assistant):
    with_link(assistant, "decline")
    t = assistant.ask("What is my locker number?")
    assert t.answer == tiers.DECLINE_PERSONAL and t.ask_to_teach


def test_the_link_escalates_to_the_second_model_with_the_same_notes(assistant, session):
    assistant.teach("The office wifi password is pelican-42.")
    assistant.save_settings(check_model="big:7b")
    with_link(assistant, "escalate")
    events = list(assistant.events("What is the office wifi password?"))
    assert any(e["type"] == "escalate" and e["by"] == "big:7b" for e in events)
    t = events[-1]["turn"]
    assert t["answer"] == "The second model's answer." and t["link"]["by"] == "big:7b"
    local, second = session.bodies[-2], session.bodies[-1]
    assert second["model"] == "big:7b" and second["prompt"] == local["prompt"]  # same notes, on this machine


def test_without_a_second_model_the_link_never_escalates(assistant):
    with_link(assistant, "escalate")
    t = assistant.ask("What colour is the sky on Zeta-9?")
    assert t.link["action"] in ("keep", "decline")


def test_switched_off_every_answer_is_stated(assistant):
    with_link(assistant, "decline")
    assistant.save_settings(trust_learning=False)
    t = assistant.ask("What colour is the sky on Zeta-9?")
    assert t.link is None and t.answer == "Something I made up."


def test_a_new_model_starts_from_the_nearest_bench_link(assistant):
    _, meta = assistant._link_for("tiny:1b")  # no link of its own yet: the bench link nearest 1B
    assert meta["start"].startswith("reader bench, qwen2.5:")
    assert tiers.prior_for("qwen2.5:3b")["reader"] == "qwen2.5:3b"
    assert tiers.prior_for("llama3.2:3b", 3.2)["reader"] == "qwen2.5:3b"
    assert tiers.params_b("494.03M") == pytest.approx(0.49403) and tiers.params_b("7B") == 7.0


def test_link_rewards_follow_the_bench():
    assert tiers.link_reward("keep", True, False) == 1.0 and tiers.link_reward("keep", False, False) == -1.0
    assert tiers.link_reward("keep", False, True) == 0.0  # the model said it does not know: not a false statement
    assert tiers.link_reward("decline", True, True) == 1.0 and tiers.link_reward("decline", False, True) == 0.0
    assert tiers.link_reward("escalate", True, False) == pytest.approx(1 - tiers.ESCALATION_COST)


def test_a_saved_link_round_trips_and_respects_allowed_actions(tmp_path):
    link = biased_link("escalate")
    link.save(tmp_path / "l.json", start="x")
    back, meta = Link.load(tmp_path / "l.json")
    row = {"question": "q", "abstained": False, "grounded": 0.5, "declined": False}
    assert meta == {"start": "x"} and back.act(row) == "escalate" and back.act(row, ("keep", "decline")) != "escalate"
    assert set(back.values(row)) == set(ACTIONS)


# ---------------------------------------------------------------------- skill cards
def card_pack(home, base="tiny:1b") -> None:
    folder = home / "cards" / "demo"
    folder.mkdir(parents=True)
    (folder / "zorbit.gguf").write_bytes(b"GGUF fake adapter")
    (folder / "pack.json").write_text(json.dumps({
        "name": "demo", "title": "Demo skills", "base": base,
        "cards": [{"skill": "zorbit", "adapter": "zorbit.gguf", "model": "camr-card-zorbit"}],
        "notes": [{"title": "Correction: zorbit", "text": "The zorbit of a and b is 3a + b. Example: the zorbit of 2 "
                   "and 5 is 11. Working: 3*2 + 5 = 11. Answer: 11."}]}))


def test_installing_a_card_pack_registers_the_card_and_teaches_its_corrections(assistant, session):
    card_pack(assistant.home)
    packs = assistant.card_packs()
    assert packs[0]["name"] == "demo" and not packs[0]["installed"] and packs[0]["usable"]
    out = assistant.install_card_pack("demo")
    assert out["cards"] == 1 and out["notes"] >= 1
    made = session.created[0]
    assert made["model"] == "camr-card-zorbit" and made["from"] == "tiny:1b"
    assert list(made["adapters"].values())[0].startswith("sha256:") and session.blobs
    assert assistant.card_packs()[0]["installed"]


def test_memory_attaches_the_card_and_the_calculator_does_the_arithmetic(assistant, session):
    card_pack(assistant.home)
    assistant.install_card_pack("demo")
    events = list(assistant.events("What is the zorbit of 4 and 1?"))
    assert any(e["type"] == "skill" and e["skill"] == "zorbit" for e in events)
    t = events[-1]["turn"]
    assert session.bodies[-1]["model"] == "camr-card-zorbit"
    assert "####" in session.bodies[-1]["prompt"]  # the prompt the card was trained on: formula, then an expression
    assert t["skill"]["value"] == 13.0 and "**13**" in t["answer"] and t["link"] is None


def test_no_card_for_an_unrelated_question_or_another_model(assistant, session):
    card_pack(assistant.home)
    assistant.install_card_pack("demo")
    assistant.teach("My dentist is Dr Wanjiru on Ngong Road.")
    t = assistant.ask("Who is my dentist?")
    assert t.skill is None and session.bodies[-1]["model"] == "tiny:1b"
    assistant.save_settings(model="big:7b")
    t = assistant.ask("What is the zorbit of 4 and 1?")
    assert t.skill is None  # the card was trained for tiny:1b only


def test_removing_a_card_pack_removes_the_card_and_its_corrections(assistant, session):
    card_pack(assistant.home)
    assistant.install_card_pack("demo")
    out = assistant.remove_card_pack("demo")
    assert out["cards"] == 1 and out["notes"] >= 1 and session.deleted == ["camr-card-zorbit"]
    assert not assistant.card_packs()[0]["installed"]
    assert assistant.ask("What is the zorbit of 4 and 1?").skill is None


def test_card_answer_reads_the_expression():
    shown, calc = tiers.card_answer("Formula: A = P(1 + r)^n\n#### 1000*(1+0.05)**3", "1000 at 5% for 3 years")
    assert calc["value"] == pytest.approx(1157.625) and "**1,157.63" in shown and "Formula" in shown
    shown, calc = tiers.card_answer("I am not sure.", "q")
    assert calc["value"] is None and shown == "I am not sure."

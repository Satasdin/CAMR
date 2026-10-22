"""Phase 2 read-path behaviours, each behind a MemoryConfig flag that is off by default: dated context and time
filter, profile notes, the entity gate's time words, aggregate questions, sentence compression, the slot gate."""

from __future__ import annotations

import datetime as dt

import pytest

from camr.memory import HashingEmbedder, MemoryEngine, SQLiteVectorStore
from camr.memory.clock import LogicalClock
from camr.memory.entities import mentions_slot, personal_slots, question_entities
from camr.memory.note import Document
from camr.memory.profile import profile_statements
from camr.memory.timeframe import period, split_said
from camr.models.tokenizer import RegexTokenizer
from conftest import fixture_config

TODAY = dt.date(2026, 10, 21)


def engine(tmp_path, **memory) -> MemoryEngine:
    emb = HashingEmbedder(128)
    store = SQLiteVectorStore(tmp_path / "m.sqlite", dim=emb.dim, embedder_name=emb.name, use_vec=False)
    cfg = fixture_config(tmp_path, **{"min_similarity": 0.05, "similarity_margin": 0.5, "token_budget": 384, **memory})
    eng = MemoryEngine.from_config(cfg, store=store, embedder=emb, tokenizer=RegexTokenizer())
    eng.clock = LogicalClock(dt.datetime(2026, 10, 21, 12, tzinfo=dt.timezone.utc), step_hours=0)
    return eng


def chat(day: str, text: str, doc_id: str) -> Document:
    return Document("chat", doc_id, f"On {day} the user said: {text}")


# ---------------------------------------------------------------------- periods and dates
def test_periods_are_generous_and_only_in_the_past():
    assert period("What did the electrician fix last week?", TODAY) == (dt.date(2026, 10, 12), TODAY)
    assert period("How many times did I go running this month?", TODAY) == (dt.date(2026, 10, 1), TODAY)
    assert period("What did I buy in March?", TODAY) == (dt.date(2026, 3, 1), TODAY)
    assert period("What did I do in November?", TODAY) == (dt.date(2025, 11, 1), TODAY)
    assert period("What did I do last Saturday?", TODAY) == (dt.date(2026, 10, 9), TODAY)  # or the one before
    assert period("How many runs have I logged since June?", TODAY) == (dt.date(2026, 6, 1), TODAY)
    for q in ("Can you suggest a dinner place for Friday?", "What will I do next week?", "What may I bring?",
              "What is my blood type?", "Can you recommend a show or movie for me to watch tonight?",
              "I was thinking about rearranging the furniture in my bedroom this weekend. Any tips?"):
        assert period(q, TODAY) is None, q
    assert split_said("On 2026-10-13 the user said: hi") == (dt.date(2026, 10, 13), "user", "hi")
    assert split_said("plain note") == (None, None, "plain note")


def test_dated_context_lists_notes_oldest_first_with_their_dates(tmp_path):
    eng = engine(tmp_path, dated_context=True)
    eng.ingest([chat("2026-09-02", "The electrician fixed the bathroom light.", "b"),
                chat("2026-10-13", "The electrician fixed the kitchen socket.", "a")])
    r = eng.recall("What did the electrician fix?")
    assert r.context.splitlines() == ["- [2026-09-02] The user said: The electrician fixed the bathroom light.",
                                      "- [2026-10-13] The user said: The electrician fixed the kitchen socket."]
    assert sorted(c.position for c in r.admitted) == [0, 1]


def test_time_filter_drops_dated_notes_outside_the_period_asked_about(tmp_path):
    eng = engine(tmp_path, time_filter=True)
    eng.ingest([chat("2026-09-02", "The electrician fixed the bathroom light.", "b"),
                chat("2026-10-13", "The electrician fixed the kitchen socket.", "a"),
                chat("2026-10-20", "The electrician also fixed the gate light last week.", "c"),  # said later: kept
                Document("note", "n", "The electrician is called Otieno.")])  # undated: kept
    r = eng.recall("What did the electrician fix last week?")
    assert "kitchen socket" in r.context and "bathroom light" not in r.context and "Otieno" in r.context
    assert "gate light" in r.context
    assert "bathroom light" in eng.recall("What did the electrician fix?").context  # no period: no filter


def test_flags_off_leave_the_context_exactly_as_before(tmp_path):
    docs = [chat("2026-09-02", "The electrician fixed the bathroom light.", "b"),
            Document("note", "v", "I am vegetarian and I don't eat fish either.")]
    plain = engine(tmp_path / "a")
    plain.ingest(docs)
    r = plain.recall("What did the electrician fix last week?")
    assert r.context == "".join(f"- {c.note.text}\n" for c in r.admitted)
    assert plain.store.count("profile") == 0


# ---------------------------------------------------------------------- profile notes
def test_profile_statements_are_lasting_traits_the_user_states():
    assert profile_statements("I am vegetarian and I don't eat fish either.") == \
        ["I am vegetarian and I don't eat fish either."]
    assert profile_statements("On 2026-07-22 the user said: Milk upsets my stomach.") == ["Milk upsets my stomach."]
    assert profile_statements("On 2026-07-22 the assistant said: I love helping.") == []
    for t in ("My office is on the 3rd floor of Delta House.", "My bank PIN hint is the year we moved to Kisumu"):
        assert profile_statements(t) == [], t


def test_profile_notes_are_offered_to_every_question_even_when_memory_abstains(tmp_path):
    eng = engine(tmp_path, profile=True, entity_gate=True, profile_budget=64)
    eng.ingest([Document("note", "veg", "I am vegetarian and I don't eat fish either."),
                Document("note", "car", "The car is a 2014 Toyota Fielder.")])
    assert eng.store.count("profile") == 1
    r = eng.recall("Can you suggest a dinner place in Westlands?")  # names "Westlands": the entity gate abstains
    assert r.abstained and r.context.startswith("- [about the user] I am vegetarian")
    prof = [c for c in r.candidates if c.lane == "profile"]
    assert len(prof) == 1 and prof[0].admitted and prof[0].position == 0
    assert r.context_tokens <= 64


def test_entity_gate_can_ignore_days_and_months():
    assert question_entities("Can you suggest a dinner place for Friday?") == ["friday"]
    assert question_entities("Can you suggest a dinner place for Friday?", skip_time=True) == []
    assert question_entities("What did I do in March 2026?", skip_time=True) == []
    assert question_entities("Who is January Jones?", skip_time=True) == ["january jones"]


# ---------------------------------------------------------------------- aggregate questions
def test_aggregate_questions_get_every_event_as_one_short_line(tmp_path):
    # min_similarity -1: the hashing test embedder scores some run notes near 0 (BGE puts them near 0.55)
    eng = engine(tmp_path, aggregate=True, keyword_k=20, k=5, similarity_margin=0.05, min_similarity=-1.0)
    runs = [chat(f"2026-09-{d:02d}", f"I went running before work, {d} km around Karura Forest with a friend.",
                 f"run-{d}") for d in range(1, 31)]
    eng.ingest(runs)
    r = eng.recall("How many times have I gone running in total?")
    lines = r.context.splitlines()
    assert len(lines) == 30 and lines[0] == "- [2026-09-01] I went running before work"
    assert r.budget == eng.aggregate_budget and r.context_tokens <= eng.aggregate_budget
    plain = eng.recall("Where do I go running?")  # not an aggregate question: the usual k and budget
    assert len(plain.admitted) <= 5 and plain.budget == 384


def test_sentence_compression_keeps_the_sentences_about_the_question(tmp_path):
    eng = engine(tmp_path, compress="sentences")
    eng.ingest([Document("note", "trip", "We flew to Mombasa in June. The hotel was by the beach. The kids loved the "
                                         "pool. Our car broke down on the way back, so we took the train.")])
    r = eng.recall("How did we get back from Mombasa?")
    assert "train" in r.context and "pool" not in r.context


# ---------------------------------------------------------------------- slot gate
def test_personal_slots():
    assert personal_slots("What is my passport number?") == [["passport"]]
    assert personal_slots("When is my brother's wedding?") == [["brother"], ["wedding"]]
    assert personal_slots("What did I bake for my uncle's birthday party?") == [["uncle"], ["party"]]
    assert personal_slots("What is the registration number of my motorbike?") == [["motorbike"]]
    assert personal_slots("What's the code for my bike lock?") == [["bike", "lock"]]
    assert personal_slots("Which floor is my office on?") == []  # asks for no specific attribute
    assert personal_slots("My kitchen's becoming a bit of a mess again. Any tips?") == []  # "kitchen is"
    assert mentions_slot("Both motorbikes are red", "motorbike") and not mentions_slot("my car", "motorbike")


def test_slot_gate_abstains_when_no_note_mentions_the_thing_asked_about(tmp_path):
    eng = engine(tmp_path, slot_gate=True)
    eng.ingest([Document("note", "car", "The car registration number is KDA 123X."),
                Document("note", "pass", "My passport number is AK0042.")])
    r = eng.recall("What is the registration number of my motorbike?")
    assert r.abstained and r.context == ""
    assert "AK0042" in eng.recall("What is my passport number?").context
    eng.ingest([Document("note", "lock", "My bicycle lock code is 7391.")])
    assert "7391" in eng.recall("What's the code for my bike lock?").context  # "lock" is enough


# ---------------------------------------------------------------------- the app
@pytest.fixture
def assistant(tmp_path):
    from camr.app.assistant import Assistant
    from test_app import FakeOllama

    a = Assistant(tmp_path / "home", model="tiny:1b", embedder=HashingEmbedder(384), session=FakeOllama(),
                  min_similarity=0.3)
    yield a
    a.close()


def test_the_app_turns_phase2_on_and_forget_removes_profile_notes_too(assistant):
    from camr.app.assistant import CHAT_PROMPT

    m = assistant.cfg.memory
    assert m.dated_context and m.time_filter and m.profile and m.aggregate and m.slot_gate and m.entity_gate_skip_time
    assert m.compress == "sentences"
    assert "Today is {today}" in CHAT_PROMPT and "the newest is right" in CHAT_PROMPT
    assistant.teach("I am vegetarian and I don't eat fish either.", doc_id="note-veg")
    assert assistant.store.count("profile") == 1
    sid = assistant.store.conn.execute("SELECT source_id FROM source WHERE doc_id='note-veg'").fetchone()[0]
    assert assistant.forget(sid) == 2  # the note and the profile note taken from it
    assert assistant.store.count("profile") == 0
    assert b"vegetarian" not in assistant.store.path.read_bytes()

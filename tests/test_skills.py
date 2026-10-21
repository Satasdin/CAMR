"""Skill cards: memory names the card to attach, and attaches none when the question is about something else."""

from __future__ import annotations

from camr.memory.note import Document
from camr.memory.skills import SkillRouter, skill_of
from test_learning import fresh_engine

PREFIX = "Correction: "


def test_a_source_title_names_its_skill():
    assert skill_of("Correction: zorbit", PREFIX) == "zorbit"
    assert skill_of("Kenya", PREFIX) is None and skill_of(None, PREFIX) is None and skill_of(PREFIX, PREFIX) is None


def test_memory_routes_a_problem_to_its_card_and_an_unrelated_one_to_none(tmp_path):
    engine = fresh_engine(tmp_path, "skills")
    engine.min_similarity = 0.3  # the hashing test embedder gives lower cosines than BGE
    engine.ingest([
        Document("correction", "zorbit-0", "The zorbit of a and b is 3a minus 2b plus a times b. Example: the zorbit "
                 "of 4 and 5 is 12 - 10 + 20 = 22.", f"{PREFIX}zorbit"),
        Document("correction", "glim-0", "One glim is 7 trell and one trell is 12 pom. Example: 3 glim is 21 trell, "
                 "which is 252 pom.", f"{PREFIX}glim"),
        Document("note", "n-0", "The office kettle is descaled every Friday.", "Kettle"),
    ])
    router = SkillRouter(engine, PREFIX)
    r = router.route("What is the zorbit of 7 and 2?")
    assert r.skill == "zorbit" and not r.abstained and "zorbit" in r.context
    assert router.route("One glim is 7 trell and one trell is 12 pom: how many pom is 5 glim?").skill == "glim"
    assert router.route("When is the kettle descaled?").skill is None  # memory answers it, no card is attached
    assert router.route("Who painted the ceiling of the Sistine Chapel?").skill is None

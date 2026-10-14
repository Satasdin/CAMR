"""Verified answers: grounding, subject and relation checks, the fact reader, replayable answers."""

from __future__ import annotations

import pytest

from camr.memory.answer import VerifiedAnswerer
from camr.memory.eager import learn_pages
from camr.memory.fetch import WebPage
from camr.memory.verify import (Unit, check, claim, claim_words, compress, read_facts, relation_of, sentences,
                                units_from_notes)
from camr.models.runner import CachedRunner, Generation, GenerationError, ModelRunner

TRAIN = [Unit("The Burning Train", "Directed by: Ravi Chopra", "Directed by"),
         Unit("The Burning Train", "Produced by: B. R. Chopra", "Produced by"),
         Unit("The Burning Train", "Music by: R. D. Burman", "Music by"),
         Unit("The Burning Train", "The Burning Train is a 1980 Indian disaster film directed by Ravi Chopra."),
         Unit("Burning Train (band)", "Burning Train is a rock band led by Martin Hale.")]


def test_sentences_do_not_split_on_initials_or_abbreviations():
    assert sentences("Music by R. D. Burman. It was a hit in St. Louis too. Then it ended.") == [
        "Music by R. D. Burman.", "It was a hit in St. Louis too.", "Then it ended."]


def test_the_claim_is_the_answer_without_the_question_and_its_frame():
    q = "Who was the director of The Burning Train?"
    assert claim("The answer is: Ravi Chopra.\nMore text") == "Ravi Chopra"
    assert claim_words(q, "The Burning Train was directed by Martin Scorsese.") == ["martin", "scorsese"]


def test_relations_are_read_from_the_question():
    assert relation_of("Who was the director of X?")[0] == "director"
    assert relation_of("Who wrote the music for X?")[0] == "composer"
    assert relation_of("Who was the screenwriter for X?")[0] == "screenwriter"
    assert relation_of("Who is the author of X?")[0] == "author"
    assert relation_of("What is the colour of the sky?")[0] == "color"
    assert relation_of("Tell me about X") is None


def test_a_supported_answer_passes_and_an_invented_one_does_not():
    q = "Who was the director of The Burning Train?"
    ok = check(q, "Ravi Chopra", TRAIN)
    assert ok.supported and ok.evidence.label == "Directed by"
    bad = check(q, "The Burning Train was directed by Martin Scorsese.", TRAIN)
    assert not bad.supported and bad.reason == "not in memory"


def test_a_name_from_another_subject_or_relation_is_not_support():
    other = TRAIN + [Unit("Kala Patthar", "Kala Patthar is a 1979 film directed by Yash Chopra.")]
    assert check("Who was the director of The Burning Train?", "Yash Chopra", other).reason == "another subject"
    assert not check("Who was the director of The Burning Train?", "Martin Hale", TRAIN).supported  # the band
    v = check("Who was the producer of The Burning Train?", "Ravi Chopra", TRAIN)
    assert not v.supported and v.reason == "another relation"
    assert check("Who was the producer of The Burning Train?", "B. R. Chopra", TRAIN).supported


def test_declining_is_not_an_answer():
    for text in ("I don't know.", "The notes do not mention the director.", "The Burning Train"):
        assert check("Who was the director of The Burning Train?", text, TRAIN).reason == "declined"


def test_the_fact_reader_answers_only_when_memory_is_unambiguous():
    assert read_facts("Who composed the music of The Burning Train?", TRAIN).text == "Music by: R. D. Burman"
    assert read_facts("What genre is The Burning Train?", TRAIN) is None  # no such fact
    two = TRAIN + [Unit("Burning Train (2003 film)", "Directed by: Someone Else", "Directed by")]
    assert read_facts("Who was the director of Burning Train?", two) is None  # two films, two directors


def test_compression_keeps_the_fact_that_answers_within_budget():
    from camr.memory.embedder import HashingEmbedder
    from camr.models.tokenizer import RegexTokenizer

    picked = compress("Who was the producer of The Burning Train?", list(TRAIN), HashingEmbedder(256),
                      RegexTokenizer(), budget=16)
    assert "Produced by" in {u.label for u in picked}
    assert sum(RegexTokenizer().count(u.render()) for u in picked) <= 16 or len(picked) == 1


# ---------------------------------------------------------------- the whole pipeline
class Scripted(ModelRunner):
    def __init__(self, name, answer):
        self.model_name, self._answer, self.prompts = name, answer, []

    def generate(self, prompt):
        self.prompts.append(prompt)
        text = self._answer(prompt) if callable(self._answer) else self._answer
        return Generation(text, None, None, 1.0, self.model_name)


def _engine(tmp_path):
    from test_learning import fresh_engine

    engine = fresh_engine(tmp_path)
    learn_pages(engine, [WebPage("The Burning Train", "https://en.wikipedia.org/wiki/The_Burning_Train",
                                 "The Burning Train is a 1980 Indian Hindi-language disaster film directed by Ravi "
                                 "Chopra and produced by his father B. R. Chopra.", "wikipedia", "q",
                                 facts="Directed by: Ravi Chopra; Produced by: B. R. Chopra; Music by: R. D. Burman")])
    return engine


def test_units_from_memory_keep_facts_whole_and_split_leads(tmp_path):
    engine = _engine(tmp_path)
    notes = engine.store.get_notes(i for (i,) in engine.store.conn.execute("SELECT note_id FROM note"))
    units = units_from_notes(engine.store, notes.values())
    assert {u.label for u in units} == {"", "Directed by", "Produced by", "Music by"}
    assert all(u.title == "The Burning Train" for u in units)


def test_a_fact_is_answered_from_memory_without_a_model(tmp_path):
    reader = Scripted("small", "Martin Scorsese")
    a = VerifiedAnswerer(_engine(tmp_path), [reader]).answer("Who was the director of The Burning Train?")
    assert (a.status, a.claim, a.by) == ("verified", "Ravi Chopra", "memory") and not reader.prompts


def test_an_unsupported_answer_escalates_and_is_never_stated_as_fact(tmp_path):
    engine = _engine(tmp_path)
    q = "Which film studio made The Burning Train in 1980?"  # no fact label for it: the readers must answer
    small, large = Scripted("small", "Yash Raj Films"), Scripted("large", "B. R. Chopra")
    a = VerifiedAnswerer(engine, [small, large], fact_reader=False).answer(q)
    assert a.status == "verified" and a.by == "large" and a.claim == "B. R. Chopra"
    assert [x.verdict["reason"] for x in a.attempts] == ["not in memory", "supported"]
    a = VerifiedAnswerer(engine, [small], fact_reader=False).answer(q)
    assert a.status == "unverified" and a.claim == "Yash Raj Films" and a.evidence is None


def test_answers_replay_from_the_cache_without_the_model(tmp_path):
    calls = []
    live = Scripted("small", lambda p: calls.append(p) or "Ravi Chopra")
    cached = CachedRunner(live, tmp_path / "answers.sqlite")
    assert cached.generate("q1").text == "Ravi Chopra" and cached.generate("q1").meta["cached"]
    assert len(calls) == 1
    replay = CachedRunner(Scripted("small", "never called"), tmp_path / "answers.sqlite", offline=True)
    assert replay.generate("q1").text == "Ravi Chopra"
    with pytest.raises(GenerationError):
        replay.generate("q2")


def test_a_shared_name_is_answered_for_each_meaning_and_never_silently_picked():
    from camr.memory.verify import fact_answer

    emma = [Unit("Emma (2020 film)", "Directed by: Autumn de Wilde", "Directed by"),
            Unit("Emma (1996 theatrical film)", "Directed by: Douglas McGrath", "Directed by"),
            Unit("Emma (1996 theatrical film)", "Emma is a 1996 period comedy film written and directed by Douglas "
                                                "McGrath.")]
    fa = fact_answer("Who was the director of Emma?", emma)
    assert fa.text == ("Emma (2020 film): Autumn de Wilde; Emma (1996 theatrical film): Douglas McGrath")
    assert fa.ambiguous == ["Emma (2020 film)", "Emma (1996 theatrical film)"]
    v = check("Who was the director of Emma?", "Douglas McGrath", emma)
    assert v.supported and v.others == ["Emma (2020 film)"]  # true, and memory knows another Emma
    one = fact_answer("Who was the director of Emma?", emma[1:] + [Unit("Emma (2020 film)", "Emma is a 2020 film.")])
    assert one.text == "Douglas McGrath (Emma (1996 theatrical film))" and one.ambiguous == ["Emma (2020 film)"]


def test_a_question_naming_nothing_checkable_is_never_verified():
    v = check("Who was the director of W.?", "Cecil Hepworth", [Unit("The Baby on the Barge",
                                                                    "Directed by: Cecil Hepworth", "Directed by")])
    assert not v.supported


def test_a_claim_memory_lacks_is_confirmed_from_its_own_article_or_not_at_all(tmp_path):
    from camr.memory.fetch import WebLookup
    from test_learning import FakeWeb, ddg_article, fresh_engine

    web = FakeWeb({"Ravi Chopra": ddg_article("Ravi Chopra", "Ravi Chopra was an Indian film director and producer. "
                                                             "He directed The Burning Train in 1980."),
                   "Martin Scorsese": ddg_article("Martin Scorsese", "Martin Scorsese is an American film director.")})
    engine = fresh_engine(tmp_path)
    learn_pages(engine, [WebPage("The Burning Train", "https://en.wikipedia.org/wiki/The_Burning_Train",
                                 "The Burning Train is a 1980 Indian Hindi-language disaster film.", "wikipedia", "q")])
    q = "Who was the director of The Burning Train?"
    lookup = WebLookup(web, min_interval_s=0)
    good = VerifiedAnswerer(engine, [Scripted("small", "Martin Scorsese"), Scripted("large", "Ravi Chopra")],
                            lookup=lookup, cross_check=True).answer(q)
    assert good.status == "verified" and good.by == "large + cross-check" and good.claim == "Ravi Chopra"
    assert "He directed The Burning Train" in good.evidence
    bad = VerifiedAnswerer(engine, [Scripted("small", "Martin Scorsese")], lookup=lookup, cross_check=True).answer(q)
    assert bad.status == "unverified"  # his article never mentions the film: not confirmed


def test_cached_vectors_are_the_same_and_computed_once(tmp_path):
    import numpy as np

    from camr.memory.embedder import CachedEmbedder, HashingEmbedder

    calls = []

    class Counting(HashingEmbedder):
        def encode(self, texts, *, is_query=False):
            calls.append(len(texts))
            return super().encode(texts, is_query=is_query)

    inner = Counting(64)
    e = CachedEmbedder(inner, tmp_path / "v.sqlite")
    a = e.encode(["one", "two", "one"])
    b = CachedEmbedder(Counting(64), tmp_path / "v.sqlite").encode(["two", "one"])
    assert np.array_equal(a[1], b[0]) and np.array_equal(a[0], a[2]) and calls == [2]
    assert e.name == inner.name and e.encode(["q"], is_query=True).shape == (1, 64)


def test_stricter_checks_reject_the_wrong_kind_and_an_unstated_relation():
    film = [Unit("X (film)", "X is a 1980 film starring Martin Hale."), Unit("X (film)", "X was released in 1980."),
            Unit("Y (film)", "Y is a 1975 film directed by Ana Silva.")]
    q = "Who was the director of X?"
    assert check(q, "Martin Hale", film).supported  # grounded and about X: the loose check passes it
    assert check(q, "Martin Hale", film, relation_cue=True).reason == "relation not stated"
    assert check(q, "1980", film, typed=True).reason == "wrong kind of answer"
    y = "Who was the director of Y?"
    assert check(y, "Ana Silva", film, typed=True, relation_cue=True).supported


def test_a_remembered_list_of_meanings_marks_an_answer_about_one_of_them(tmp_path):
    from camr.memory.eager import learn_meanings
    from camr.memory.fetch import WebLookup
    from camr.memory.verify import meaning_units
    from test_learning import FakeWeb, fresh_engine

    web = FakeWeb({"Damage": {"Type": "D", "AbstractText": "", "RelatedTopics": [
        {"FirstURL": "https://duckduckgo.com/Damage_(2009_film)", "Text": "Damage (2009 film) A film by Jeff F. King"},
        {"FirstURL": "https://duckduckgo.com/Damage_(1992_film)", "Text": "Damage (1992 film) A film by Louis Malle"}]},
        "Damage (2009 film)": {"AbstractText": "Damage is a 2009 action film. The director of Damage was Jeff F. "
                                               "King, who directed it in Canada.",
                               "AbstractURL": "https://en.wikipedia.org/wiki/Damage_(2009_film)", "Type": "A"}})
    res = WebLookup(web, min_interval_s=0).lookup("Who was the director of Damage?")
    assert res.meanings["Damage"] == ["Damage (2009 film)", "Damage (1992 film)"]
    engine = fresh_engine(tmp_path)
    learn_pages(engine, res.pages)
    learn_meanings(engine, res.meanings)
    a = VerifiedAnswerer(engine, [Scripted("small", "Jeff F. King")]).answer("Who was the director of Damage?")
    assert a.status == "verified" and a.ambiguous == ["Damage (1992 film)"]
    assert a.text == "Jeff F. King (Damage (2009 film))"  # says which Damage, and memory knows there is another
    assert meaning_units(engine.store, "Who directed Damage?")[0].text.lower().startswith("damage may refer to")

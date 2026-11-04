"""The Long Haul script: the same every time for a seed, at least 2M Qwen3 tokens with the four cuts, every probe
planted where it says, and the doc's six samples word for word."""

from __future__ import annotations

import json
import re
from collections import Counter

from haul_shared import built, need_tokenizer, perfect

from camr_engine.bench.haul import CUTS, at_cut, grade, load_events, load_probes, sample, tokens, write
from camr_engine.bench.haul.grade import names as named
from camr_engine.bench.haul.probes import CONFIGS, COUNTS, NEVER_ENTITY
from camr_engine.bench.haul.script import answer_clashes, config_clashes
from camr_engine.bench.haul.words import FIRST, SURNAMES

FAMILIES = {"fact": 400, "changed": 160, "two_hop": 40, "maths": 120, "page": 3, "code": 20, "lookalike": 30,
            "never": 60}


def test_a_seed_gives_the_same_script_and_another_seed_a_different_one():
    a, b = built(1), built(1)
    from camr_engine.bench.haul import build
    again = build(1)
    other = built(2)
    assert [e["text"] for e in a.events] == [e["text"] for e in again.events]
    assert json.dumps(a.probes, sort_keys=True) == json.dumps(again.probes, sort_keys=True)
    assert a.manifest == again.manifest
    assert a.manifest["script_sha"] != other.manifest["script_sha"]
    assert [p["ask"] for p in a.probes] != [p["ask"] for p in other.probes]
    assert b is a


def test_it_reaches_two_million_qwen3_tokens_and_the_counts_add_up():
    h = built()
    total = 0
    for i, e in enumerate(h.events):
        assert e["i"] == i and e["tokens"] > 0
        total += e["tokens"]
        assert e["cum_tokens"] == total
    assert total >= 2_000_000 and h.manifest["tokens"] == total
    sample_idx = list(range(0, len(h.events), 97))
    recount = tokens.count_many([h.events[i]["text"] for i in sample_idx])
    assert recount == [h.events[i]["tokens"] for i in sample_idx]
    assert h.manifest["tokenizer"] == "mlx-community/Qwen3-1.7B-4bit"


def test_the_cuts_end_on_the_last_event_inside_them():
    h = built()
    cuts = h.manifest["cuts"]
    assert list(cuts) == ["64K", "256K", "1M", "2M"]
    for name, limit in CUTS.items():
        c = cuts[name]
        assert c["limit"] == limit and c["tokens"] <= limit
        assert h.events[c["events"] - 1]["cum_tokens"] == c["tokens"]
        assert h.events[c["events"]]["cum_tokens"] > limit
    assert cuts["2M"]["last_day"] == 110
    sizes = [sum(c["probes"].values()) for c in cuts.values()]
    assert sizes == sorted(sizes) and sizes[-1] == sum(FAMILIES.values())


def test_110_working_days_with_the_planned_families():
    h = built()
    assert h.manifest["days"] == 110 and {e["day"] for e in h.events} == set(range(1, 111))
    assert sum(e["kind"] == "day" for e in h.events) == 110
    assert Counter(p["family"] for p in h.probes) == Counter(FAMILIES)
    assert h.manifest["families"] == FAMILIES
    assert COUNTS["changed"] == 80 and COUNTS["maths"] == 40
    assert len({p["id"] for p in h.probes}) == len(h.probes)
    kinds = h.manifest["kinds"]
    for kind in ("chat", "decision", "code", "maths", "log", "meeting", "doc"):
        assert kinds[kind]["tokens"] > 0
    assert kinds["log"]["tokens"] < 0.3 * h.manifest["tokens"]  # noise, not the whole story


def test_every_probe_is_planted_inside_the_2m_cut_and_its_event_says_it():
    h = built()
    for p in h.probes:
        if p["family"] == "never":
            assert p["planted_at"] is None and p["events"] == []
            continue
        assert p["planted_at"] <= CUTS["2M"] and p["ready_at"] <= CUTS["2M"]
        assert h.events[p["event"]]["cum_tokens"] == p["planted_at"]
        if p["family"] in ("fact", "lookalike", "two_hop"):
            text = h.events[p["event"]]["text"].replace(",", "")
            assert any(a.replace(",", "") in text for a in p["grader"]["accept"]), p["id"]
        if p["family"] == "lookalike":
            twin = [i for i in p["events"] if i != p["event"]][0]
            assert any(r.replace(",", "") in h.events[twin]["text"].replace(",", "") for r in p["grader"]["reject"])


def test_facts_sit_at_random_depths_across_the_whole_script():
    h = built()
    depths = sorted(p["planted_at"] for p in h.probes if p["family"] == "fact")
    quarters = Counter(min(3, d * 4 // h.manifest["tokens"]) for d in depths)
    assert all(70 <= quarters[q] <= 130 for q in range(4)), quarters


def test_changed_facts_change_two_to_four_times_and_the_old_value_is_said_more():
    h = built()
    events = h.events
    for p in [p for p in h.probes if p["family"] == "changed"]:
        values = p["grader"]["values"]
        assert 3 <= len(values) <= 5
        days = [v["day"] for v in values]
        assert days == sorted(days) and len(set(days)) == len(days)
        for v in values:
            assert any(a in events[v["event"]]["text"] for a in v["accept"])
        if p["grader"]["on_day"] is not None:
            d = p["grader"]["on_day"]
            assert days[0] < d < days[-1] and d not in days
    text = "\n".join(e["text"] for e in events)
    assert text.count(":8080") > text.count(":9443")


def test_the_six_doc_samples_word_for_word():
    by = {p["id"]: p for p in built().probes}
    assert (by["maths-01-rule"]["ask"], by["maths-01-rule"]["answer"]) == ("Fee on 12,000?", "25")
    assert (by["maths-01-new"]["ask"], by["maths-01-new"]["answer"]) == ("Fee on 7,321?", "75")
    assert by["maths-01-same"]["ask"] == "What's our fee on a KES 3,456 payment?"
    assert by["maths-02-same"]["answer"] == "4000" and by["maths-02-new"]["answer"] == "3846"
    assert "divisibility by 13 with n up to 25,000" in by["maths-02-new"]["ask"]
    assert by["page-catering"]["ask"] == "Build the catering page." and by["page-catering"]["ask_day"] == 110
    assert (by["hop-01"]["ask"], by["hop-01"]["answer"]) == ("Which city will Otieno work in from March?", "Mombasa")
    assert (by["changed-01-past"]["ask"], by["changed-01-past"]["answer"]) == ("What port did staging use on day 50?",
                                                                               "8443")
    assert by["changed-01-now"]["answer"] == "9443"
    assert [v["day"] for v in by["changed-01-now"]["grader"]["values"]] == [12, 40, 88]
    assert by["never-01"]["ask"] == "What is Otieno's surname?"
    samples = [p for p in by.values() if p["sample"]]
    assert len(samples) == 8  # six items; the fee rule and the staging port are each asked two ways
    events = built().events
    text = "\n".join(e["text"] for e in events)
    for said in ["Otieno handles our payments.", "Whoever handles payments moves to the Mombasa office in March.",
                 "Main colour is now #7C3AED.", "main colour #0B5FFF", "© 2026 Mama Njeri's Kitchen · Nairobi",
                 "1% of the amount, rounded up to the next 5 shillings, at least 10, but any exact multiple of 1,000 "
                 "pays a flat 25. So 34.56 rounds up to 35.",
                 "solve n² ≡ −1, which gives n ≡ 2 or 3 (mod 5), then count 2 in every 5, giving 4,000."]:
        assert said in text, said
    assert [e["day"] for e in events if "Otieno handles our payments." in e["text"]] == [9]
    assert [e["day"] for e in events if "Main colour is now #7C3AED." in e["text"]] == [61]


def test_never_said_things_are_never_said():
    h = built()
    low = "\n".join(e["text"] for e in h.events).lower()
    for q, absent in NEVER_ENTITY:
        for w in absent:
            assert not re.search(r"\b" + re.escape(w.lower()) + r"\b", low), (q, w)
    text = "\n".join(e["text"] for e in h.events)
    names = "|".join(SURNAMES + FIRST)
    assert not re.search(rf"\bOtieno\s+(?:{names})\b|\b(?:{names})\s+Otieno\b", text)
    assert "Otieno" in text


def test_settings_are_named_only_where_they_are_told():
    h = built()
    assert [c[0] for c in h.configs] == [c[0] for c in CONFIGS]
    assert config_clashes(h.events, h.configs) == []
    told = {np_: at for np_, _, at in h.configs}
    never = [p for p in h.probes if p["family"] == "never" and p.get("slot") == "config:value"]
    assert never and all(told[p["ask"].removeprefix("What is ").removesuffix("?")] is None for p in never)
    for np_, values, at in h.configs:
        if at is not None:
            assert any(v.casefold() in h.events[at]["text"].casefold() for v in values), np_
    # the noise once printed the health check path and a CI runner label hundreds of times
    assert sum("/healthz" in e["text"] for e in h.events) <= 1
    assert not any("runs-on: ubuntu-latest" in e["text"] for e in h.events)
    fake = [{"id": "x", "ask": "What is the deploy branch now?",
             "grader": {"type": "exact", "accept": ["deploy"]}}]
    assert answer_clashes(fake) and answer_clashes(h.probes) == []


def test_never_said_slots_carry_the_pool_a_guess_would_come_from():
    never = [p for p in built().probes if p["family"] == "never"]
    assert len(never) == COUNTS["never"] and all(p["grader"].get("pool") for p in never)
    for p in never:
        pool = [v for v in p["grader"]["pool"] if v == "#number" or not named(p["ask"], [v])]
        guess = "42" if pool[0] == "#number" else pool[0]
        assert grade(p, f"I'm not sure. {guess}?").verdict == "false_memory", (p["id"], guess)
        assert grade(p, "I don't know; that was never mentioned.").verdict == "right", p["id"]


def test_the_files_have_the_promised_fields_and_load_back(tmp_path):
    h = built()
    write(h, tmp_path)
    events = load_events(tmp_path)
    assert set(events[0]) == {"i", "day", "kind", "role", "text", "tokens", "cum_tokens"}
    assert len(events) == len(h.events) and events[-1] == h.events[-1]
    probes = load_probes(tmp_path)
    assert probes == json.loads(json.dumps(h.probes))
    for p in probes:
        assert {"id", "family", "ask", "answer", "grader", "planted_at", "event", "events"} <= set(p)
    m = json.loads((tmp_path / "manifest.json").read_text())
    assert m["families"] == FAMILIES and set(m["cuts"]) == set(CUTS)


def test_at_a_cut_the_answer_is_the_one_true_then():
    by = {p["id"]: p for p in built().probes}
    port = by["changed-01-now"]
    assert at_cut(port, CUTS["256K"]) is None  # only the first port is told by then
    mid = at_cut(port, CUTS["1M"])
    assert mid["answer"] == "8443" and mid["grader"]["accept"] == ["8443"] and "8080" in mid["grader"]["stale"]
    assert at_cut(port, CUTS["2M"])["answer"] == "9443"
    assert at_cut(by["changed-01-past"], CUTS["256K"]) is None  # day 50 has not happened yet
    page_1m = at_cut(by["page-catering"], CUTS["1M"])
    assert page_1m["grader"]["colour"] == "#0B5FFF" and page_1m["grader"]["old"] == []
    page_2m = at_cut(by["page-catering"], CUTS["2M"])
    assert page_2m["grader"]["colour"] == "#7C3AED" and page_2m["grader"]["old"] == ["#0B5FFF"]
    assert at_cut(by["hop-01"], CUTS["1M"]) is None and at_cut(by["hop-01"], CUTS["2M"])
    assert at_cut(by["never-01"], CUTS["64K"])["cut"] == CUTS["64K"]


def test_a_perfect_answer_is_right_at_every_cut():
    h = built()
    for cut in CUTS.values():
        for p in h.probes:
            q = at_cut(p, cut)
            if q is None:
                continue
            if q["family"] == "code" and cut != CUTS["2M"]:
                continue  # the code tests run in a subprocess; once is enough
            verdict, reason = grade(q, perfect(q))
            assert verdict == "right", (cut, q["id"], reason)


def test_a_stratified_sample():
    h = built()
    per = sample(h.probes, CUTS["1M"], 3, per_family=True)
    fams = Counter(q["family"] for q in per)
    assert set(fams) == {"fact", "changed", "two_hop", "maths", "page", "code", "lookalike", "never"}
    assert all(n == 3 for n in fams.values())
    assert any(q["id"] == "maths-01-new" for q in per)  # the doc's samples come first
    spread = sample(h.probes, CUTS["2M"], 15)
    assert len(spread) == 15 and len({q["family"] for q in spread}) == 8
    assert sample(h.probes, CUTS["2M"], 15) == spread
    assert all(q["cut"] == CUTS["2M"] for q in spread)
    need_tokenizer()

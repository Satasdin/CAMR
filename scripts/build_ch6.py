"""Chapter 6 (Conclusions, Recommendations and Future Works), rewritten with Chapter 5.

No new results: every statement points to the section of Chapter 5 that supports it (section and figure numbers are
read from the labels Chapter 5's build wrote).

    python scripts/build_ch6.py --template proposal.docx --out docs/report/Chapter6_CAMR
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("build_ch5", HERE / "build_ch5.py")
ch5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ch5)
p1, usd, J = ch5.p1, ch5.usd, ch5.J


def facts() -> dict:
    """The numbers Chapter 6 quotes, read from the same files as Chapter 5."""
    f: dict = {}
    jf = J("results/verified/judged_heldout.json") or {}
    f["v"] = jf.get("files", {}).get("answers_heldout_sa.json", {}).get("facts+compress+reader", {}).get("verified", {})
    f["kimi_closed"] = jf.get("closed", {}).get("kimi-k3", {})
    f["desk"] = {t: d["summary"] for t, _, d in ch5.loaded("helio", ch5.DESK_SYSTEMS)}
    f["agents"] = {t: d["summary"] for t, _, d in ch5.loaded("agent", ch5.AGENT_CONFIGS)}
    f["fresh"] = {t: d["summary"] for t, _, d in ch5.loaded("fresh", ch5.FRESH_SYSTEMS)}
    f["rag"] = {k: ch5.rag_summary(d) for k, d in ch5.rag_runs().items()}
    f["costs"] = ch5.costs() or {}
    f["sweep"] = ch5.sweep_models()
    f["skills"] = J("results/skills/skill_cards.json") or {}
    f["readers"] = ch5.reader_rows() or []
    f["abilities"] = by_ability()
    f["link"] = J("results/link/link_baseline.json") or {}
    f["tests"] = ch5.test_count()
    return f


LOCAL = ("qwen2.5:0.5b", "qwen2.5:1.5b", "qwen2.5:3b")


def pc(x: float) -> str:
    return f"{100 * x:.0f}%"


def span(xs: list[float]) -> str:
    """'6%–12%' for a range of shares (one value when they round the same)."""
    lo, hi = pc(min(xs)), pc(max(xs))
    return lo if lo == hi else f"{lo}–{hi}"


def by_ability(tag: str = "baseline") -> dict[str, dict[str, float]]:
    """Right with memory, per ability and reader, on the reader bench (results/readers/answers_<tag>.jsonl)."""
    p = ch5.RES / f"readers/answers_{tag}.jsonl"
    n: dict[str, dict[str, list[int]]] = {}
    if p.exists():
        for r in map(json.loads, p.read_text().splitlines()):
            if r["memory"] and r["correct"] is not None:
                k = n.setdefault(r["ability"], {}).setdefault(r["reader"], [0, 0])
                k[0] += bool(r["correct"])
                k[1] += 1
    return {a: {rd: right / total for rd, (right, total) in v.items()} for a, v in n.items()}


def local_range(F: dict, ability: str) -> str:
    return span([F["abilities"][ability][rd] for rd in LOCAL if rd in F["abilities"].get(ability, {})] or [0.0])


def build(template: Path, out: Path) -> Path:
    c = ch5.Chapter(template, number=6)
    labels = out.parent / "ch5_labels.json"
    if labels.exists():
        c.labels.update(json.loads(labels.read_text()))
    F = facts()
    v, kc = F["v"], F["kimi_closed"]
    c.h1("Conclusions, Recommendations and Future Works")

    # ------------------------------------------------------------ 6.1
    c.h2("Introduction")
    c.p("Small language models that run privately on a consumer device know far less than large cloud models, and a "
        "frozen model cannot cheaply be retrained to close the difference. This study built CAMR, a memory engine that "
        "sits beside a frozen model, and measured what it closes, what it does not, and at what cost, against the "
        "alternatives a developer would actually choose between: the model alone, a frontier cloud model, modern "
        "retrieval-augmented generation, context stuffing and fine-tuning. This chapter states what the evidence "
        "established (section 6.2), what should be done because of it (6.3), and what remains open (6.4). It adds no "
        "new results; every statement refers to the section of Chapter 5 that supports it. The results settle into "
        "one design, a frozen reader with a learning memory in three tiers (notes for facts, skill cards for "
        "procedures, and a link that learns when to trust each model), and the conclusions end on it.")

    # ------------------------------------------------------------ 6.2
    c.h2("Conclusions")
    c.p("The conclusions answer the research questions of section 1.4 in order, then the questions the later work "
        "added: whether answers can be trusted, whether a frozen model can keep learning, and whether automations need "
        "such an engine at all. They end with how the pieces fit together.")
    c.h3("Research Question i: Which Memory Techniques Work for a Small Model on a Device")
    c.p("Cheap, selective techniques anchored in what the question names work; the weighted composites of large-model "
        "agent memories do not. Recency and importance scoring lowered full-support recall on both multi-hop "
        "benchmarks, because benchmark questions are independent (section ⟦sec_retrieval⟧). Entity bridging, a "
        "one-step hop that needs no graph, doubled full-support recall on 2WikiMultiHopQA (35.8% → 78.4%) at the same "
        "budget, twice what top-10 RAG found with fewer tokens. Gating keeps irrelevant text from a weak reader, and an "
        "entity gate stops memory from answering about a similar entity when the right one is missing. Trained "
        "retrieval components (a query adapter, a learned index) did not help on unseen questions (section "
        "⟦sec_learning⟧).")
    c.h3("Research Question ii: How Much of the Gap a Frozen-Weights Memory Engine Closes")
    c.p("On knowledge, nearly all of it. Eighteen of nineteen small models reached or beat the cloud model on long-tail "
        "facts once they had memory (section ⟦sec_models⟧), and on 200 held-out multi-hop questions a 3B model with "
        "CAMR (54.0%) matched the cloud model closed-book (51.8%) at a third of its time (section ⟦sec_gap⟧). On "
        f"verified answering the 0.5B model was correct {p1(v.get('correct'))} of the time against the cloud model's "
        f"{p1(kc.get('correct'))}, while stating a wrong fact {p1(v.get('hallucinated'))} of the time against "
        f"{p1(kc.get('wrong'))} (section ⟦sec_verified⟧). Fine-tuning on the same documents reached 13.3% against "
        "memory's 71.7% (section ⟦sec_learning⟧).")
    c.h3("Research Question iii: Knowledge-Bound Versus Reasoning-Bound Tasks")
    c.p("Memory helps knowledge-bound tasks and not reasoning-bound ones. With the same notes, the gap between a 0.5B "
        "and a 20B model was 10.0 points on single facts, 23.3 on multi-hop questions and 83.3 on arithmetic (section "
        "⟦sec_gap⟧), and worked examples lowered the 0.5B model's arithmetic. Where reasoning can be handed to a tool, "
        "memory helps again: with a calculator doing the arithmetic, corrections taught the 0.5B model formulas it "
        "could not know (0% → 70.8% on invented formulas), and taught the cloud model all ten from four corrections "
        "(section ⟦sec_learning⟧).")
    c.h3("Research Question iv: The Token Budget")
    c.p("For a 0.5B reader about 128 tokens is best for single facts and 512 for multi-hop questions; more text "
        "distracts it (section ⟦sec_gap⟧). The verified pipeline settled at 128 tokens of compressed sentences, and "
        "70% of held-out questions were answered from a fact line with no model call at all. The best budget depends on "
        "the reader and the task, which is why the device governor sets it from measured speeds and a latency target "
        "(section ⟦sec_bulk_impl⟧) and the learned router chooses it per question (section ⟦sec_policy⟧).")
    c.h3("Research Question v: Cost on the Device and in the Cloud")
    tot = F["costs"].get("total", {})
    c.p("On a 4-core CPU the engine needs well under 1 GB beside the model, makes 123,301 paragraphs searchable in "
        "under six minutes, and stops cleanly at every device limit (section ⟦sec_bulk⟧). Retrieval is cheap in "
        "isolation (about 29 ms) but took 56% of a 0.5B model's answer time under contention, so the 10% target was "
        "not met for the smallest model. Models of 6B and more answered more slowly than the cloud model on this "
        "hardware, which makes 1.5–4B the useful range on a CPU-only laptop (section ⟦sec_models⟧). In the cloud, the "
        f"whole study spent {usd(tot.get('usd'))} on {tot.get('calls', 0):,} calls (section ⟦sec_cost⟧).")
    c.h3("Beyond the Research Questions")
    for para in re.split(r" (?=\*\*[A-Z][^*]*\?\*\*)", CH6_EXTRA(F).strip()):  # one paragraph per question
        c.p(para)
    tiers = THREE_TIERS(F)
    if tiers:
        c.h3("The Frozen Reader and the Learning Memory")
        for para in tiers:
            c.p(para)
    c.h3("Contribution and Boundaries")
    sw = F["sweep"]
    c.p("The study contributes: (1) an open-source memory engine whose read path is measured to suit small models; "
        "(2) verified answering that states a fact only when memory supports it, with its source; (3) learning "
        "without training, by lookup and by correction, measured against fine-tuning and token-level memory; (4) "
        "skill cards, procedures kept as small adapters that memory attaches per question, measured against one "
        "adapter merged into the model; (5) a link that learns from feedback, per model, when to state an answer, "
        "decline or ask the cloud model; (6) a size map of "
        f"{len(sw)} models ({sw[0]['params']:.1f}B to {sw[-1]['params']:.0f}B) and a reader bench of four readers on "
        "one memory, showing where memory pays off; (7) a head-to-head comparison with eight modern RAG pipelines on "
        "one corpus; (8) automations in n8n and a tool-using agent that show where an engine is needed and what it "
        "costs; and (9) CAMR Personal, a released desktop application. The conclusions hold for English questions, "
        "frozen quantised models on 4-core CPUs with 16 GB of memory, the sample sizes reported, invented company "
        "data and a stochastic cloud reference sampled once. Skill cards were measured on one 0.5B model and "
        f"{len(F['skills'].get('card_training', {})) or 'ten'} formula families, and the link on judged benchmark "
        "answers rather than real users' feedback. The conclusions "
        "do not yet extend to real users' data, to phones, or to real customer traffic.")
    c.table("Alignment from objectives to evidence and conclusions",
            ["Objective (section 1.3.2)", "Evidence (Chapter 5)", "Conclusion", "Status"],
            [["i. Investigate capability gaps and memory techniques", "⟦sec_retrieval⟧, ⟦sec_gap⟧, ⟦sec_ragresult⟧",
              "Selective, name-anchored techniques transfer; composite scoring does not; the gap is knowledge and "
              "reading, not reasoning", "Met"],
             ["ii. Design a lightweight memory engine", "⟦sec_impl⟧, ⟦sec_verify_impl⟧, ⟦sec_tests⟧, ⟦sec_defects⟧",
              f"Implemented, tested ({F['tests'] or 'over 200'} tests) and changed on evidence; 40 numbered defects, "
              "and six more from a code review of the application and the skill-card router, found and handled",
              "Met"],
             ["iii. Develop it on a consumer laptop without a GPU", "⟦sec_env⟧, ⟦sec_bulk⟧, ⟦sec_appres⟧",
              "Runs on 4 cores in under 1 GB beside the model; NFR-02 not met for 0.5B", "Met on laptop-class "
              "machines, not one physical laptop"],
             ["iv. Evaluate gap closed by task type", "⟦sec_models⟧, ⟦sec_gap⟧, ⟦sec_verified⟧",
              "Facts closed; multi-hop matched from 3B; reasoning not closed", "Met"],
             ["v. Determine the best token budget", "⟦sec_gap⟧, ⟦sec_policy⟧", "128 tokens (facts), 512 (multi-hop) "
              "for 0.5B; set per device and per question", "Met"]] + ALIGN_TIERS(F),
            [3.8, 3.6, 5.6, 2.9], size=9)

    # ------------------------------------------------------------ 6.3
    c.h2("Recommendations")
    c.p("The first table is a decision guide: which approach to use, given the situation, on the evidence of this "
        "study. The second lists recommendations by audience.")
    c.table("Decision guide: memory engine, RAG, context stuffing, fine-tuning or a cloud model",
            ["Situation", "Use", "Why (Chapter 5)"], DECISIONS(F), [4.6, 4.4, 6.9], size=9)
    c.table("Recommendations",
            ["#", "Audience", "Recommended action", "Evidence and condition"],
            [["1", "Developers of on-device assistants", "Pair a 1.5–4B model with external memory for personal and "
              "long-tail facts; do not rely on the model's own knowledge", "⟦sec_models⟧: alone ≤ 33%, with memory "
              "70–80%; faster than the cloud on 4 cores"],
             ["2", "Anyone who lets a model answer customers", "State only what memory supports, show the source, and "
              "route the rest to a person; measure wrong replies, not only accuracy", "⟦sec_verified⟧, ⟦sec_agentic⟧"],
             ["3", "Builders of automations (n8n, agents)", "Put company knowledge behind a memory with an escalation "
              "path, and teach every human resolution back into it", "⟦sec_agentic⟧: the learning loop only works "
              "when unknowns are escalated"],
             ["4", "Developers", "Send arithmetic and multi-step reasoning to a stronger model or a tool, not to "
              "memory", "⟦sec_gap⟧: 83-point residual; ⟦sec_learning⟧: calculator"],
             ["5", "Designers of memory engines", "Rank by similarity with gating, entity bridging and an entity "
              "gate; avoid recency weighting for independent questions; tune budgets to the reader",
              "⟦sec_retrieval⟧, ⟦sec_policy⟧"],
             ["6", "Teams choosing between fine-tuning and memory", "Use memory for knowledge that changes or must "
              "be deleted; when a procedure must be trained, keep it as a card that memory attaches per question "
              "rather than merging it into the model", "⟦sec_learning⟧: LoRA lost GSM8K (13.3% → 0%); "
              "⟦sec_skills⟧: cards beat the merged adapter and disturbed fewer unrelated answers"],
             ["7", "Developers of local assistants with a cloud fallback", "Learn when to trust each model from "
              "users' feedback (a link per model) and price the cloud call explicitly, instead of stating every local "
              "answer", "⟦sec_link⟧: " + LINK_EVIDENCE(F)],
             ["8", "Researchers", "Report hallucination (wrong stated answers) beside accuracy, judge aliases, use "
              "held-out sets answered once, and report the serving runtime's version with small-model results",
              "⟦sec_verified⟧, ⟦sec_limits⟧, ⟦sec_agentic⟧"],
             ["9", "The student and supervisor", "Obtain ethics approval before collecting feedback from real users "
              "of CAMR Personal; rotate the cloud key used in this study", "⟦sec_apptest⟧, ⟦sec_vc⟧"]],
            [0.8, 3.4, 6.0, 5.7], size=9)

    # ------------------------------------------------------------ 6.4
    c.h2("Future Works")
    c.p("Each direction follows from a failure or an open question in section ⟦sec_flaws⟧ or ⟦sec_limits⟧, ordered by "
        "expected value.")
    c.table("Prioritised future works",
            ["Priority", "Direction and rationale", "How to evaluate"],
            [[str(i), what, how] for i, (what, how) in enumerate(FUTURE(F), 1)],
            [1.6, 8.0, 6.3], size=9)
    return c.save(out)


# ----------------------------------------------------------------- written from the results


def CH6_EXTRA(F: dict) -> str:  # noqa: N802
    d, a, fr = F["desk"], F["agents"], F["fresh"]
    text = ("**Can its answers be trusted?** More than a model's own. Verification cut the 0.5B model's wrong stated "
            f"answers from 52% to {p1(F['v'].get('hallucinated'))} on held-out questions, and every remaining wrong "
            "answer quoted a stored line; what it cannot catch is a wrong page (section ⟦sec_verified⟧). ")
    text += ("**Can a frozen model keep learning?** Yes, as long as what it learns is text it reads: from lookups "
             "(10.0% → 43.5% on new questions) and from corrections (four corrections taught the cloud model every "
             "invented formula, including derived uses no correction showed). Fine-tuning learned the trained wording "
             "better but forgot unrelated skills (section ⟦sec_learning⟧). ")
    if "camr_kimi-k3" in d and "rag_kimi-k3" in d and "stuff_kimi-k3" in d:
        c, r, s = d["camr_kimi-k3"], d["rag_kimi-k3"], d["stuff_kimi-k3"]
        text += ("**Do automations need such an engine?** Where knowledge is private and changes, a model alone is "
                 "useless or wrong, and any of the three memories made it useful. What separated them was what they "
                 f"did when they did not know: CAMR sent {p1(c['wrong_replies'])} wrong replies to customers against "
                 f"{p1(r['wrong_replies'])} for RAG and {p1(s['wrong_replies'])} for context stuffing, and because it "
                 "escalated what it did not know, people's answers were taught back and the desk learned; RAG's wrong "
                 "replies were never seen by a person, so the same wrong answer was repeated (section ⟦sec_agentic⟧). ")
    if "kimi-k3__camr" in a:
        text += (f"With memory, the cloud agent completed {p1(a['kimi-k3__camr']['success'])} of its tasks with no "
                 "hallucinated action; without it, it completed only the tasks that required doing nothing. ")
    if "camr_kimi-k3" in fr and "llm_kimi-k3" in fr:
        text += (f"On news after its training data, the cloud model alone stated a wrong answer to "
                 f"{p1(fr['llm_kimi-k3']['wrong_stated'])} of questions; with CAMR's memory of the workflow's pages it "
                 f"was correct on {p1(fr['camr_kimi-k3']['correct'])} with {p1(fr['camr_kimi-k3']['wrong_stated'])} "
                 "wrong. ")
    if (ch5.RES / "agentic/ollama-0.13.5").exists():
        text += ("**Do the results repeat?** The engine's own runs are deterministic. The four Llama 3B automation "
                 "runs whose files were lost were repeated on a second machine on the study's runtime and reproduced "
                 "(the agent without memory and the news run exactly, the agents with memory within one to three of "
                 "20 tasks), but an older version of the same runtime changed the same model's behaviour, so "
                 "small-model agent results hold for the runtime they were measured on (section ⟦sec_agentic⟧). ")
    return text


def _changed(x: dict) -> int:
    return x["lost_vs_base"] + x["gained_vs_base"]


def _link_local(F: dict) -> dict[str, dict]:
    return {k: v for k, v in F["link"].get("readers", {}).items() if k in LOCAL}


def THREE_TIERS(F: dict) -> list[str]:  # noqa: N802
    """The project's own idea (a frozen model made better by a memory that learns), concluded from the three tiers."""
    rd, sk, lk = F["readers"], F["skills"], _link_local(F)
    if not (rd and sk and lk):
        return []
    small, big = rd[0], rd[-1]
    cond, cl = sk["conditions"], sk["control_large"]
    card, merged = cl["conditions"]["card"], cl["conditions"]["merged"]
    keep = [v["fixed"]["always keep"]["wrong"] for v in lk.values()]
    learned = [v["curve"][-1]["wrong"] for v in lk.values()]
    esc = [v["curve"][-1]["escalated"] for v in lk.values()]
    feedback = min(v["curve"][-1]["feedback"] for v in lk.values())
    first = ("The study began from one idea: keep a small model's weights frozen and fast, keep what it learns in a "
             "memory outside it that any model can use, so that a better memory makes a better model. The evidence "
             "settles that idea into three tiers around a frozen reader. **Facts belong in notes that any model "
             "reads.** Facts trained into weights stayed near 13% where notes reached 72% (section ⟦sec_learning⟧), "
             f"and one memory lifted every reader measured: the 0.5B model from {p1(small['alone'])} to "
             f"{p1(small['memory'])} and the cloud model from {p1(big['alone'])} to {p1(big['memory'])}, helping far "
             "more questions than it harmed at every size (section ⟦sec_readers⟧). **Procedures can live in weights, "
             "if memory decides when to attach them.** A small adapter per formula family, attached only when the best "
             f"note memory admits belongs to that family, answered {p1(cond['card']['test']['all'])} of new problems "
             f"against {p1(cond['merged']['test']['all'])} for one adapter merged into the model, and changed "
             f"{_changed(card)} of {cl['n']} unrelated answers against {_changed(merged)} (section ⟦sec_skills⟧). "
             "**Trust is learned per model.** A link that reads only signals that cost nothing learned, from the "
             f"feedback on {feedback} answers, to cut the wrong answers the local models state from {span(keep)} to "
             f"{span(learned)} (section ⟦sec_link⟧).")
    second = ("In that sense a better memory did make a better model: the weights never changed, and what each model "
              "answered correctly grew with what memory held, what it attached and what it learned about the model. "
              "Three boundaries hold. Memory does not make a small model reason better: with the same notes the 0.5B "
              f"model stated a wrong answer to {p1(small['wrong'])} of questions against {p1(big['wrong'])} for the "
              "cloud model, and the link removes wrong answers mostly by declining or by sending "
              f"{span(esc)} of questions to the cloud model, not by making the small model right more often. A card "
              "carries a procedure's form and the notes its meaning: on problems that use a rule in a new way, notes "
              f"scored {p1(cond['memory']['derived']['all'])} and a card {p1(cond['card']['derived']['all'])}. And "
              "the cards and the link were measured on benchmarks from judged answers: CAMR Personal does not yet "
              "attach cards or learn a link from its users' feedback.")
    return [first, second]


def ALIGN_TIERS(F: dict) -> list[list[str]]:  # noqa: N802
    """The alignment row for what the study added beyond its objectives."""
    lk = _link_local(F)
    if not (F["readers"] and F["skills"] and lk):
        return []
    keep = [v["fixed"]["always keep"]["wrong"] for v in lk.values()]
    learned = [v["curve"][-1]["wrong"] for v in lk.values()]
    return [["Added: one memory for every reader, with weights and trust it learns", "⟦sec_skills⟧, ⟦sec_readers⟧, "
             "⟦sec_link⟧", "Memory lifted all four readers; cards beat a merged adapter with less harm; the link cut "
             f"stated wrong answers from {span(keep)} to {span(learned)}", "Met on benchmarks; not yet in the app"]]


def SKILL_DECISION(F: dict) -> list[list[str]]:  # noqa: N802
    sk = F["skills"]
    if not sk:
        return []
    cond, cl = sk["conditions"], sk["control_large"]
    return [["A procedure learned from a few corrections, while every other skill must be kept", "A skill card per "
             "family, attached by memory, with the notes kept beside it", f"⟦sec_skills⟧: "
             f"{p1(cond['card']['test']['all'])} vs {p1(cond['merged']['test']['all'])} merged; "
             f"{_changed(cl['conditions']['card'])} vs {_changed(cl['conditions']['merged'])} of {cl['n']} unrelated "
             "answers changed"]]


def LINK_EVIDENCE(F: dict) -> str:  # noqa: N802
    lk = _link_local(F)
    if not lk:
        return "the learned link"
    keep = [v["fixed"]["always keep"]["wrong"] for v in lk.values()]
    learned = [v["curve"][-1]["wrong"] for v in lk.values()]
    esc = [v["curve"][-1]["escalated"] for v in lk.values()]
    return f"wrong stated answers {span(keep)} → {span(learned)}, with {span(esc)} of questions sent to the cloud"


def FUTURE(F: dict) -> list[tuple[str, str]]:  # noqa: N802
    """Prioritised future works: (direction and rationale, how to evaluate)."""
    lk = _link_local(F)
    gap = ""
    if lk:
        oracle = [v["fixed"]["oracle"]["reward"] for v in lk.values()]
        got = [v["curve"][-1]["reward"] for v in lk.values()]
        gap = (f" The best possible choice per question scored {min(oracle):+.2f} to {max(oracle):+.2f} against "
               f"{min(got):+.2f} to {max(got):+.2f} for the learned link, so it lacks information, not feedback.")
    changing = ""
    if F["abilities"].get("A4") and F["abilities"].get("A3") and F["abilities"].get("A1"):
        changing = (f" With memory the local readers answered {local_range(F, 'A4')} of questions about time and "
                    f"{local_range(F, 'A3')} of facts that had changed, against {local_range(F, 'A1')} of plain "
                    "recall.")
    return [
        ("**A user study of CAMR Personal.** Whether the assistant grows more useful as a person's memory grows is "
         "its central claim, and no user has tested it.", "4–8 weeks, ethics approval; share of answers from memory, "
         "thumbs-up rate, accuracy on each user's repeated questions"),
        ("**The three tiers inside CAMR Personal.** The cards and the link were measured on benchmarks; the app "
         "already records thumbs and corrections, so the link can learn from each user's feedback and a card can be "
         "trained for a procedure once enough corrections of it have accumulated.", "Wrong stated answers and cloud "
         "calls per 100 questions as feedback accumulates; unrelated answers changed by cards"),
        ("**Better signals for the link.**" + gap + " Candidates: agreement between two answers or two readers, "
         "whether the answer occurs within a single note, and the engine's reason for abstaining.", "Reward and wrong "
         "stated answers against the oracle on the reader bench, every price for a cloud call"),
        ("**Facts that change, and time.**" + changing + " The notes carry their dates, but a small reader must "
         "compare them itself, and an old fact sits beside its replacement: putting the dates to work in recall and "
         "preferring the newest fact is the first step, marking a replaced fact as superseded the second.", "Right "
         "answers on LongMemEval's time and changed-fact questions, for every reader"),
        ("**A real support queue.** The desk used an invented company; a real queue (with consent and "
         "anonymisation) would test coverage, escalation load and wrong replies at scale.", "Wrong-reply rate and "
         "escalations per 1,000 tickets against the current process"),
        ("**Better checks.** The kind check withheld correct answers (*al-Ghazali*), and the check cannot tell a "
         "wrong page from a right one.", "Coverage and wrong-stated rate on the held-out set; source agreement across "
         "two pages before stating"),
        ("**A reranker in CAMR's recall, and a stricter claim check.** Reranked RAG put the answer in front of the "
         "reader more often (72% against 64%), and the 0.5B reader got answers past the check that only repeated the "
         "subject's name.", "Correct and wrong-stated rates on the held-out set and the desk"),
        ("**Skill cards beyond formulas.** Cards were trained for one 0.5B model; output formats (a desk's reply "
         "style), tool use and larger models are untested, and a card was still attached to some unrelated "
         "problems.", "Held-out accuracy and unrelated answers changed, per family and per model size"),
        ("**Better lookups.** The answer was in what was read for 52–73% of questions: the lookup sets the ceiling.",
         "Answer-in-text rate on a fresh stream; Wikidata for disambiguation"),
        ("**Closing the reading gap of small models.** 76% of the 0.5B model's multi-hop misses had the answer in "
         "context.", "Correct-when-in-context on HotpotQA and 2Wiki, n ≥ 200"),
        ("**A learned entity recogniser.** The rule-based entity gate caused D-15, D-31, D-32, D-37 and D-40.",
         "Abstention on answerable and unanswerable questions; full-support recall"),
        ("**Sessioned memory.** Recency could not help on independent questions; conversations are not "
         "independent.", "LongMemEval (already in the reader bench) or LoCoMo, with and without recency"),
        ("**Phones and a physical laptop.** Timings came from laptop-class cloud machines.", "NFR-02, peak memory and "
         "battery per 100 answers on two phones and one laptop"),
    ]


def DECISIONS(F: dict) -> list[list[str]]:  # noqa: N802
    return [
        ["Private, changing knowledge (support, operations); a wrong answer has a cost", "CAMR with the strongest "
         "reader allowed; escalate what is not supported and teach the answer back", "⟦sec_agentic⟧: 0 wrong "
         "replies; the desk learned from its escalations"],
        ["A small, stable knowledge base and a cloud model", "Context stuffing is simplest, but costs more per "
         "question as the base grows and still states wrong answers", "⟦sec_agentic⟧, ⟦sec_cost⟧"],
        ["A large document collection; coverage matters more than an occasional wrong answer", "Hybrid search with "
         "a reranker (modern RAG)", "⟦sec_ragresult⟧"],
        ["The same, but wrong answers are costly", "Modern RAG retrieval with CAMR's check, or CAMR", "⟦sec_ragresult⟧"],
        ["Questions that chain two entities", "CAMR's entity bridging with a reader of 3B or more", "⟦sec_retrieval⟧, "
         "⟦sec_gap⟧"],
        ["Arithmetic or multi-step reasoning", "A stronger model, or a calculator tool; not memory", "⟦sec_gap⟧, "
         "⟦sec_learning⟧"],
        ["A new rule or formula learned from a few corrections", "Store the rule and a worked example; let a "
         "calculator do the arithmetic", "⟦sec_learning⟧"],
        ["A fixed output format, and nothing else must be kept", "Fine-tuning (LoRA) can win on that format",
         "⟦sec_learning⟧: 88.3% vs 50.0%, but GSM8K 13.3% → 0%"],
    ] + SKILL_DECISION(F) + [
        ["A local model, with a cloud model allowed for what it cannot answer", "A learned link per model: state, "
         "decline or escalate, learned from users' feedback", "⟦sec_link⟧: " + LINK_EVIDENCE(F)],
        ["Offline or private use on a 16 GB CPU laptop", "1.5B model for facts, 3B for reading across documents, "
         "with CAMR; not 6B or larger", "⟦sec_models⟧"],
        ["Events after the model's training data", "Teach the source as it arrives (an automation can do it) and "
         "answer from memory", "⟦sec_agentic⟧"],
    ]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", default="docs/report/Chapter6_CAMR")
    ap.add_argument("--no-pdf", action="store_true")
    a = ap.parse_args()
    path = build(Path(a.template), Path(a.out))
    print("wrote", path)
    if not a.no_pdf:
        print("wrote", ch5.old.to_pdf(path))


if __name__ == "__main__":
    main()

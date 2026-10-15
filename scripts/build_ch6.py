"""Chapter 6 (Conclusions, Recommendations and Future Works), rewritten with Chapter 5.

No new results: every statement points to the section of Chapter 5 that supports it (section and figure numbers are
read from the labels Chapter 5's build wrote).

    python scripts/build_ch6.py --template proposal.docx --out docs/report/Chapter6_CAMR
"""

from __future__ import annotations

import argparse
import importlib.util
import json
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
    return f


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
        "new results; every statement refers to the section of Chapter 5 that supports it.")

    # ------------------------------------------------------------ 6.2
    c.h2("Conclusions")
    c.p("The conclusions answer the research questions of section 1.4 in order, then the questions the later work "
        "added: whether answers can be trusted, whether a frozen model can keep learning, and whether automations need "
        "such an engine at all.")
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
        "not met for the smallest model. Models of 7B and more answered more slowly than the cloud model on this "
        "hardware, which makes 1.5–4B the useful range on a CPU-only laptop (section ⟦sec_models⟧). In the cloud, the "
        f"whole study spent {usd(tot.get('usd'))} on {tot.get('calls', 0):,} calls (section ⟦sec_cost⟧).")
    c.h3("Beyond the Research Questions")
    c.p(CH6_EXTRA(F))
    c.h3("Contribution and Boundaries")
    c.p("The study contributes: (1) an open-source memory engine whose read path is measured to suit small models; "
        "(2) verified answering that states a fact only when memory supports it, with its source; (3) learning "
        "without training, by lookup and by correction, measured against fine-tuning and token-level memory; (4) a "
        "size map of nineteen models and a reader study showing where memory pays off; (5) a head-to-head comparison "
        "with eight modern RAG pipelines on one corpus; (6) automations in n8n and a tool-using agent that show where "
        "an engine is needed and what it costs; and (7) CAMR Personal, a released desktop application. The conclusions "
        "hold for English questions, frozen quantised models on 4-core CPUs with 16 GB of memory, the sample sizes "
        "reported, invented company data and a stochastic cloud reference sampled once. They do not yet extend to real "
        "users' data, to phones, or to real customer traffic.")
    c.table("Alignment from objectives to evidence and conclusions",
            ["Objective (section 1.3.2)", "Evidence (Chapter 5)", "Conclusion", "Status"],
            [["i. Investigate capability gaps and memory techniques", "⟦sec_retrieval⟧, ⟦sec_gap⟧, ⟦sec_ragresult⟧",
              "Selective, name-anchored techniques transfer; composite scoring does not; the gap is knowledge and "
              "reading, not reasoning", "Met"],
             ["ii. Design a lightweight memory engine", "⟦sec_impl⟧, ⟦sec_verify_impl⟧, ⟦sec_tests⟧, ⟦sec_defects⟧",
              "Implemented, tested (203 tests) and changed on evidence; 38 defects found and handled", "Met"],
             ["iii. Develop it on a consumer laptop without a GPU", "⟦sec_env⟧, ⟦sec_bulk⟧, ⟦sec_appres⟧",
              "Runs on 4 cores in under 1 GB beside the model; NFR-02 not met for 0.5B", "Met on laptop-class "
              "machines, not one physical laptop"],
             ["iv. Evaluate gap closed by task type", "⟦sec_models⟧, ⟦sec_gap⟧, ⟦sec_verified⟧",
              "Facts closed; multi-hop matched from 3B; reasoning not closed", "Met"],
             ["v. Determine the best token budget", "⟦sec_gap⟧, ⟦sec_policy⟧", "128 tokens (facts), 512 (multi-hop) "
              "for 0.5B; set per device and per question", "Met"]],
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
              "be deleted; fine-tune only for a fixed output format where nothing else must be kept",
              "⟦sec_learning⟧: LoRA lost GSM8K (13.3% → 0%)"],
             ["7", "Researchers", "Report hallucination (wrong stated answers) beside accuracy, judge aliases, and "
              "use held-out sets answered once", "⟦sec_verified⟧, ⟦sec_limits⟧"],
             ["8", "The student and supervisor", "Obtain ethics approval before collecting feedback from real users "
              "of CAMR Personal; rotate the cloud key used in this study", "⟦sec_apptest⟧, ⟦sec_vc⟧"]],
            [0.8, 3.4, 6.0, 5.7], size=9)

    # ------------------------------------------------------------ 6.4
    c.h2("Future Works")
    c.p("Each direction follows from a failure or an open question in section ⟦sec_flaws⟧ or ⟦sec_limits⟧, ordered by "
        "expected value.")
    c.table("Prioritised future works",
            ["Priority", "Direction and rationale", "How to evaluate"],
            [["1", "**A user study of CAMR Personal.** Whether the assistant grows more useful as a person's memory grows "
              "is its central claim, and no user has tested it.", "4–8 weeks, ethics approval; share of answers from "
              "memory, thumbs-up rate, accuracy on each user's repeated questions"],
             ["2", "**A real support queue.** The desk used an invented company; a real queue (with consent and "
              "anonymisation) would test coverage, escalation load and wrong replies at scale.", "Wrong-reply rate and "
              "escalations per 1,000 tickets against the current process"],
             ["3", "**Better checks.** The kind check withheld correct answers (*al-Ghazali*), and the check cannot tell "
              "a wrong page from a right one.", "Coverage and wrong-stated rate on the held-out set; source agreement "
              "across two pages before stating"],
             ["4", "**A reranker in CAMR's recall, and a stricter claim check.** Reranked RAG put the answer in "
              "front of the reader more often (72% against 64%), and the 0.5B reader got answers past the check that "
              "only repeated the subject's name.", "Correct and wrong-stated rates on the held-out set and the desk"],
             ["5", "**Better lookups.** The answer was in what was read for 52–73% of questions: the lookup sets the "
              "ceiling.", "Answer-in-text rate on a fresh stream; Wikidata for disambiguation"],
             ["6", "**Closing the reading gap of small models.** 76% of the 0.5B model's multi-hop misses had the answer "
              "in context.", "Correct-when-in-context on HotpotQA and 2Wiki, n ≥ 200"],
             ["7", "**A learned entity recogniser.** The rule-based entity gate caused D-15, D-31, D-32 and D-37.",
              "Abstention on answerable and unanswerable questions; full-support recall"],
             ["8", "**Sessioned memory.** Recency could not help on independent questions; conversations are not "
              "independent.", "A sessioned benchmark (LongMemEval or LoCoMo) with and without recency"],
             ["9", "**Phones and a physical laptop.** Timings came from laptop-class cloud machines.", "NFR-02, peak "
              "memory and battery per 100 answers on two phones and one laptop"]],
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
    return text


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
        ["Offline or private use on a 16 GB CPU laptop", "1.5B model for facts, 3B for reading across documents, "
         "with CAMR; not 7B or larger", "⟦sec_models⟧"],
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

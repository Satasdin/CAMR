"""Build Chapter 6 (Conclusions, Recommendations and Future Works) as .docx and .pdf, in the proposal's styles.

Chapter 6 introduces no new results: every statement points back to evidence reported in Chapter 5.

    python scripts/build_chapter6.py --template proposal.docx --out build/Chapter6_CAMR
"""

from __future__ import annotations

import argparse
import importlib.util
from pathlib import Path

HERE = Path(__file__).resolve().parent
_spec = importlib.util.spec_from_file_location("build_chapter5", HERE / "build_chapter5.py")
ch5 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ch5)


def build(template: Path, out: Path) -> Path:
    c = ch5.Chapter(template, number=6)
    c.h1("Conclusions, Recommendations and Future Works")

    # ------------------------------------------------------------ 6.1
    c.h2("Introduction")
    c.p("This chapter closes the chain from the problem stated in Chapter 1 to the evidence reported in Chapter 5. "
        "The problem was that small language models that run privately on consumer devices know far less than "
        "large cloud models, and that a frozen small model cannot be retrained cheaply to close the difference. "
        "The study built CAMR, an external memory engine that sits beside a frozen small model. It measured how "
        "much of the capability gap the engine closes, for which kinds of task, at what token and time cost, and "
        "for which model sizes. It then packaged the engine as an application. Section 6.2 states what the "
        "evidence established, section 6.3 what should be done because of it, and section 6.4 what remains open. "
        "No new results are introduced; each statement refers to the section of Chapter 5 that supports it.")

    # ------------------------------------------------------------ 6.2
    c.h2("Conclusions")
    c.p("The conclusions answer the research questions of section 1.4 in order.")
    c.h3("Research Question i: Techniques and Their Limits On-Device")
    c.p("The literature review (Chapter 2) identified similarity retrieval, recency and importance scoring, "
        "compression and graph-based association as the main memory techniques, all designed for large models. "
        "Implementing them for a small model on a CPU showed which of them transfer. Recency and importance "
        "(Equation 4.1) lowered full-support recall on both multi-hop benchmarks, because benchmark questions are "
        "independent and recency carries no signal about them (section 5.8.1). Two capability-adaptive additions "
        "transferred well. Gating kept irrelevant text away from a weak reader. Entity bridging, a one-step "
        "associative hop that needs no graph construction, raised full-support recall on 2WikiMultiHopQA from "
        "35.8% to 78.4% at the same token budget. The applicable techniques on-device are therefore cheap, "
        "similarity-based and selective, not the weighted composites of large-model agent memories.")
    c.h3("Research Question ii: How Much of the Gap a Frozen-Weights Memory Engine Closes")
    c.p("Against the frontier cloud model (Kimi K3), the engine closed the entire single-hop knowledge gap for a "
        "0.5B model (gap closed 1.00) and half of the multi-hop gap (0.50, 95% CI 0.20–0.90). The multi-hop result "
        "was confirmed on 200 held-out questions with the configuration fixed in advance. With CAMR, a 3B model "
        "reached 54.0% exact match against the cloud model's closed-book 51.8%, at 5.8 s instead of 18.4 s per "
        "answer, and the gain from memory excluded zero for every small model tested (section 5.8.8). Across 19 "
        "models, 18 reached or exceeded the cloud model on long-tail facts once they had memory (section 5.8.7).")
    c.h3("Research Question iii: Knowledge-Bound Versus Reasoning-Bound Tasks")
    c.p("Yes. Memory helps knowledge-bound tasks and does not help reasoning-bound ones. The residual gap between a "
        "0.5B and a 20B model reading the same notes was 10.0 points on single-hop facts, 23.3 on multi-hop "
        "questions and 83.3 on mathematical reasoning (section 5.8.2). Most of the remaining multi-hop gap is a "
        "reading gap: the small model had the answer in its context for 76% of its misses (section 5.8.3). "
        "Worked-example memory for mathematics helped some model families and hurt others, depending on family "
        "rather than size.")
    c.h3("Research Question iv: The Token Budget That Maximises Gap Closed Per Token")
    c.p("For a 0.5B model the best budget was about 128 tokens for single facts and 512 for multi-hop questions. "
        "Larger budgets lowered accuracy because extra notes distracted the small model, and reasoning tasks did "
        "not benefit at any budget (section 5.8.5). Retrieval recall saturated near 1,024 tokens (section 5.8.1). "
        "The best budget therefore depends on the task and on the model, which is why a learned policy was "
        "needed. That policy matched the cloud model's accuracy (65.3% against 63.9%) while 71% of questions "
        "stayed on the device and mean latency fell four-fold; this difference in accuracy is within sampling "
        "noise (section 5.8.9).")
    c.h3("Research Question v: Cost in Tokens and Latency on a Consumer Device")
    c.p("The engine added a median of 187 ms and about 536 prompt tokens per answer for a 0.5B model. Peak memory "
        "was 712 MB for the engine and 1,987 MB for the model runtime, and the store was 47.8 MB (section 5.8.10). "
        "The ten-per-cent retrieval-latency target (NFR-02) was not met for the 0.5B model, because that model "
        "answers in about 180 ms. The overhead was diagnosed as CPU contention rather than engine cost: about 29 ms "
        "in isolation. Decode speed fell by 3–17% with memory, the cost of reading a longer prompt. On this class "
        "of device, models of 7B parameters or more with memory answered more slowly than the cloud model, which "
        "makes **1.5–4B the model size that suits the engine** on a CPU-only laptop.")
    c.h3("Contribution and the Boundaries of the Findings")
    c.p("The study contributes four things: (1) a working, open-source memory engine and evaluation harness; "
        "(2) measured evidence that external memory lets small on-device models match a frontier cloud model on "
        "knowledge-bound questions, together with the residual gap that memory cannot close; (3) a size map of 19 "
        "small models showing where memory pays off; and (4) a released desktop application, CAMR Personal, that "
        "puts the approach in users' hands. These conclusions hold for English benchmark questions, for frozen "
        "quantised models run with greedy decoding on 4-core CPUs with 16 GB of memory, for the sample sizes "
        "reported (30–200 questions per condition, 500 for retrieval), and for a stochastic cloud reference "
        "sampled once. They do not yet extend to real users' personal data, to phones, or to sessioned "
        "conversations where recency matters. Table 6.1 summarises the alignment from objectives to conclusions.")
    c.table("Alignment from objectives to evidence and conclusions",
            ["Objective (section 1.3.2)", "Implementation", "Evidence (Chapter 5)", "Conclusion"],
            [["i. Investigate capability gaps and memory techniques", "Literature review; engine built with every "
              "proposed technique switchable", "5.8.1 retrieval study; 5.8.2 residual gap", "Similarity + gating + "
              "bridging transfer; Eq. 4.1 does not; the gap is mostly knowledge and reading"],
             ["ii. Design a lightweight memory engine", "Write path, screener, single-file store, adaptive read "
              "path, budgeter (5.4)", "5.5 test cases TC-01–TC-22; defects D-01–D-09", "Design implemented and "
              "verified; deviations justified"],
             ["iii. Develop it on a consumer laptop without a GPU", "SQLite + sqlite-vec, BGE on CPU, Ollama", "5.2; "
              "5.8.10 device profile", "Runs in under 3 GB; NFR-02 not met for 0.5B (contention)"],
             ["iv. Evaluate gap closed by task type, with tokens and latency", "Floor/treatment/ceiling/ceiling_rag "
              "harness; 19-model sweep; n = 200", "5.8.2, 5.8.7, 5.8.8", "Facts: fully closed; multi-hop: half, and "
              "matched by 3B; reasoning: not closed"],
             ["v. Determine the best token budget", "Budget sweep; learned policy", "5.8.5, 5.8.9", "128 tokens (facts), "
              "512 (multi-hop) for 0.5B; learned routing matches the cloud with 71% on-device"]],
            [3.6, 4.0, 3.6, 4.7], size=9)

    # ------------------------------------------------------------ 6.3
    c.h2("Recommendations")
    c.p("The recommendations are ordered by priority. The first three are essential safeguards for anyone "
        "deploying the approach; the rest are improvements. Each one names its audience and the evidence behind it.")
    c.table("Recommendations",
            ["#", "Audience", "Recommended action", "Evidence and condition"],
            [["1", "Developers deploying on-device assistants", "Pair a 1.5–4B model with external memory for personal "
              "and long-tail facts; do not rely on the small model's own knowledge", "5.8.7: facts alone ≤ 33%, with "
              "memory 70–80%; 1.5–4B faster than the cloud. Holds on CPU-only devices"],
             ["2", "Developers deploying on-device assistants", "Route reasoning-heavy questions (e.g. arithmetic) to a "
              "stronger model, with the user's consent, instead of adding memory", "5.8.2: residual gap 83 points on "
              "GSM8K; 5.8.9: the learned router sent all maths to the cloud"],
             ["3", "CAMR maintainers", "Code-sign the Windows and macOS downloads before wider distribution, and keep "
              "feedback strictly opt-in", "5.6: unsigned builds trigger OS warnings; privacy is a stated design "
              "requirement (NFR-06)"],
             ["4", "Designers of memory engines for small models", "Use similarity ranking with gating and entity "
              "bridging; avoid recency/importance weighting for independent questions; calibrate the abstain "
              "threshold per embedder", "5.8.1: Eq. 4.1 lowered recall; bridging doubled 2Wiki recall; 5.4.7 "
              "calibration rule"],
             ["5", "Designers of memory engines for small models", "Keep the memory budget small for tiny models "
              "(≈128 tokens for facts) and let a policy adapt it", "5.8.5 budget curve; 5.8.9 learned policy"],
             ["6", "CAMR maintainers", "Partition CPU threads between the model and the embedder on 4-core devices",
              "5.8.10: p90 retrieval 157 → 50 ms with partitioning"],
             ["7", "Researchers evaluating memory for small models", "Report the residual gap against a model reading "
              "the same notes, use a frontier ceiling, and use at least 200 questions for headline claims",
              "5.8.2 (gap closed exceeds 1 against a weak ceiling); 5.8.8 (pilot vs n = 200)"],
             ["8", "The student and supervisor", "Obtain ethics approval and a consent statement before collecting "
              "feedback from real users of CAMR Personal", "5.5.3: no user study yet; feedback export is designed "
              "to be metrics-only by default"]],
            [0.8, 3.4, 5.6, 6.1], size=9)

    # ------------------------------------------------------------ 6.4
    c.h2("Future Works")
    c.p("The directions below extend the research. They do not repair promised work: everything in the approved "
        "scope was implemented and evaluated. They are ordered by expected value, and each follows from a "
        "limitation or open question in section 5.8.")
    c.table("Prioritised future works",
            ["Priority", "Direction and rationale", "What changes / resources", "How to evaluate"],
            [["1", "**Longitudinal user study of CAMR Personal.** Whether the assistant gets more useful as a "
              "person's own memory grows is the application's central claim, and no user has tested it yet (5.8.12).",
              "Real users and their own notes over 4–8 weeks; ethics approval; the existing opt-in metrics export",
              "Weekly share of answers drawn from memory, 👍 rate, and accuracy on each user's repeated questions "
              "(day 1 vs week 4)"],
             ["2", "**Sessioned memory benchmark.** Recency could not show a benefit on independent questions "
              "(5.8.1); conversations are not independent.", "A sessioned benchmark such as LongMemEval or LoCoMo; "
              "the recency term already implemented", "Gap closed with and without recency on the same sessions"],
             ["3", "**Closing the reading gap.** 76% of multi-hop misses had the answer in context (5.8.3).",
              "Structured notes, answer-extraction prompts, or a small reader-tuned model, keeping the engine fixed",
              "Correct-when-in-context on HotpotQA and 2Wiki, n ≥ 200"],
             ["4", "**CAMR on phones.** The Android prototype compiles and passes its unit tests but has not run on "
              "a device (5.8.11).", "Two to three mid-range Android phones; on-device model files; gating calibration "
              "for the phone embedder", "Retrieval share of latency (NFR-02), peak memory, battery per 100 answers, "
              "and accuracy against the desktop results"],
             ["5", "**Stronger evaluation basis.** Single-hop and reasoning results rest on pilot samples, and the "
              "cloud reference was sampled once (5.8.12).", "n ≥ 200 per task; repeated cloud samples or a "
              "deterministic open frontier model; non-English data", "Confidence intervals that exclude the pilot's "
              "uncertainty; variance across repeats"],
             ["6", "**Better routing signals.** The learned router reached 61–65% against an oracle of 79% (5.8.9).",
              "The small model's own confidence and the grounding signal as router features", "Held-out accuracy "
              "and cloud share against the same oracle"]],
            [1.6, 5.4, 4.4, 4.5], size=9)
    c.p("Each direction should be scoped with the supervisor. The first two are the most valuable because they "
        "test the claim the application makes to its users, that it grows with them, under the conditions in "
        "which it will be used.")
    return c.save(out)


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--template", required=True)
    ap.add_argument("--out", default="build/Chapter6_CAMR")
    a = ap.parse_args()
    path = build(Path(a.template), Path(a.out))
    print("wrote", path)
    print("wrote", ch5.to_pdf(path))

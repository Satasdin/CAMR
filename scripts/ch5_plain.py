"""Plain-language layer for Chapter 5: a summary for any reader, a glossary, short explanations of technical terms
the first time they appear in each main section, plainer table headings, and an "In plain words" opener for each
section. Numbers come from the same results files as the rest of the chapter (passed in as ``F``).

Used by build_ch5.py: ``install(chapter, facts)`` wraps the chapter's paragraph, list, table and heading methods.
"""

from __future__ import annotations

import re

from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt

BOX_FILL, BOX_EDGE = "EAF1F8", "2A78D6"

# ----------------------------------------------------------------- glossary (Table in 5.1)

GLOSSARY = [
    ("Language model", "A program that writes text one word at a time by predicting what comes next. It only "
     "\"knows\" what was in the text it was trained on."),
    ("Parameters; 0.5B, 3B, 7B", "The internal numbers a model learned in training. \"3B\" means about 3 billion of "
     "them. More parameters usually means a more capable model that is also slower and needs more memory."),
    ("Small (on-device) model", "A model small enough to run on an ordinary laptop without the internet; here from "
     "0.5B to 14.8B."),
    ("Cloud model; Kimi K3", "A very large model run by a company and used over the internet, paid per use. Kimi K3, "
     "by Moonshot AI, is the strong reference model in this study."),
    ("Frozen model", "A model whose parameters are never changed. Everything new is kept outside it, in CAMR's "
     "memory."),
    ("CAMR", "The memory engine built in this project. It files documents as short notes and, for each question, "
     "decides which few notes the model should read."),
    ("Note; fact line", "One short piece of stored text, usually one sentence. A fact line has the form "
     "\"subject: relation: value\" (*Mississippi Burning: Screenplay: Chris Gerolmo*) and can be read without the "
     "model."),
    ("Token", "A piece of a word; models read and write tokens. 100 tokens are about 75 English words. Speed and "
     "cloud cost are counted in tokens."),
    ("Prompt", "Everything handed to the model at once: instructions, any notes, and the question."),
    ("Reader", "The model that reads the notes and writes the answer. It can be a small model or the cloud model."),
    ("Retrieval (search); embedding", "Finding the notes most relevant to a question. An embedding is a list of "
     "numbers that captures what a text means, so a search can match meaning, not only words."),
    ("Keyword search (BM25)", "Classic search that matches words, like a library catalogue."),
    ("RAG (retrieval-augmented generation)", "Today's standard way to give a model documents: search for the passages "
     "closest to the question and paste them into the prompt. Eight versions were compared with CAMR."),
    ("Reranker", "A second, more careful model that re-orders search results by how well each one answers the "
     "question."),
    ("Context stuffing", "Pasting every document into every question. Simple, and accurate while the documents are "
     "few, but slow and expensive as they grow."),
    ("Fine-tuning; LoRA", "Retraining a model on new examples so that knowledge goes into its parameters. LoRA is a "
     "cheap way of doing it. It is the alternative to memory that this study tests against."),
    ("Verified answer", "CAMR states an answer as fact only when a stored note supports it; otherwise it says it "
     "cannot confirm the answer, or passes the question on."),
    ("Hallucination", "A confident answer that is made up. The harmful kind of error."),
    ("Declined; not confirmed", "The system said it did not know, or would not state an answer. Safe, but not "
     "useful."),
    ("Escalate", "Hand a question to a person, or to a stronger model, instead of answering it."),
    ("Other meaning (named)", "An answer about a different person or thing with the same name, labelled as such "
     "(*Happy (2011 film): ...*), so the reader can see the mix-up."),
    ("Single-hop; multi-hop", "A single-hop question needs one fact. A multi-hop question needs two facts joined, "
     "for example *Where was the director of film X born?*"),
    ("Long-tail facts", "Facts about less famous people and things, which models rarely saw in training."),
    ("Benchmark", "A public set of questions with known answers, so that results can be checked and compared: PopQA "
     "(less-known facts), HotpotQA and 2WikiMultiHopQA (questions that need two Wikipedia articles), GSM8K (school "
     "maths word problems)."),
    ("Development, test and held-out sets", "Questions used while building (development), for checks during the work "
     "(test), and kept aside until the end for a fair final check (held-out)."),
    ("Exact match; judged", "An answer is first counted correct if it contains the reference answer. Answers marked "
     "wrong were re-checked by the cloud model acting as a judge, because a right answer can be worded "
     "differently."),
    ("Precision; recall", "Precision: of the answers given, the share that were right. Recall (in search): the share "
     "of the needed evidence that the search found."),
    ("Agent", "A model that works through a task step by step, choosing tools: search memory, calculate, write an "
     "invoice, reply, escalate."),
    ("n8n workflow; node", "A business automation built visually from connected steps (nodes), for example: read a "
     "ticket, answer it, then send the reply or escalate."),
    ("Gateway", "A small local web service that gives every answering system the same four commands (reset, teach, "
     "forget, ask), so a workflow can switch systems without other changes."),
    ("CPU, RAM, GPU", "The computer's main processor, its working memory, and a graphics card. Everything here ran on "
     "a 4-core CPU with 16 GB of RAM and no GPU."),
    ("Quantisation (Q4_K_M)", "Storing each parameter in about 4 bits, so a model needs less memory and runs faster "
     "with a small loss of quality."),
    ("Baseline", "The system something is compared against."),
    ("Requirement (FR, NFR)", "From Chapter 3: functional requirements (what the system must do) and non-functional "
     "requirements (how well: speed, memory, privacy)."),
    ("Defect (D-01 ... D-40)", "A bug found during testing or experiments, numbered, fixed and retested."),
    ("Reproducible", "Anyone can rerun the evaluation from the saved files and get the same numbers."),
]

# ----------------------------------------------------------------- short explanations at first use (per section)

INLINE = [
    (r"\bfrozen weights\b", "the model's internal numbers are never changed"),
    (r"\bcross-validation\b", "tuning on one part of the practice questions and checking on another, in turn"),
    (r"\bLoRA\b", "a cheap way of retraining a model"),
    (r"\bSQLite\b", "a database kept in one ordinary file"),
    (r"\btoken budget\b", "a cap on how much text the model reads"),
    (r"\btokens\b", "pieces of words; 100 tokens are about 75 words"),
    (r"\bprompt\b", "the full text handed to the model"),
    (r"\bn8n\b", "a visual tool for building automations from connected steps"),
    (r"\bcontext stuffing\b", "pasting every document into every question"),
    (r"\bheld-out\b", "kept aside until the end for a fair test"),
    (r"\breranker\b", "a second model that re-orders search results"),
    (r"\bBM25\b", "keyword search"),
    (r"\bembeddings?\b", "numbers that capture a text's meaning, used to search by meaning"),
    (r"\bembedders?\b", "the model that turns text into meaning-numbers for search"),
    (r"\bHyDE\b", "the model first guesses an answer and the guess is used to search"),
    (r"\b[Cc]orrective RAG\b", "RAG that grades its search results and searches the web when they look poor"),
    (r"\bRAG\b", "retrieval-augmented generation: search for passages and paste them into the prompt"),
    (r"\bmulti-hop\b", "needing two facts joined"),
    (r"\blong-tail\b", "about less famous subjects"),
    (r"\bPopQA\b", "public questions about less-known facts"),
    (r"\bHotpotQA\b", "public questions that need two Wikipedia articles"),
    (r"\bGSM8K\b", "public school-maths word problems"),
    (r"\b2WikiMultiHopQA\b", "public two-article questions, harder than HotpotQA"),
    (r"\bexact match(?:ing)?\b", "the answer must contain the reference answer"),
    (r"\bhallucinat\w*", "confident but made up"),
    (r"\bescalat\w*", "handed to a person or a stronger model"),
    (r"\bagents?\b", "a model that completes a task step by step using tools"),
    (r"\bgateway\b", "a small local service that gives every system the same commands"),
    (r"\bQ4_K_M\b", "compressed to about 4 bits per number"),
    (r"\binfobox\b", "the summary box on a Wikipedia page"),
    (r"\bcosine\b", "a measure of how similar two meanings are"),
    (r"\bReAct\b", "think, use a tool, read the result, repeat"),
    (r"\bbootstrap\b", "re-sampling the questions to see how much a result could vary by chance"),
    (r"\bablation\b", "switching parts off one at a time to see what each contributes"),
    (r"\bkNN-LM\b", "a model that also consults the most similar stored text while writing"),
    (r"\bfine-tun\w+", "retraining the model's internal numbers on new examples"),
    (r"\bbaselines?\b", "what it is compared against"),
    (r"\bKimi K3\b", "a large cloud model by Moonshot AI"),
    (r"\bOllama\b", "free software that runs models on a computer"),
    (r"\bheadless\b", "from the command line, without the visual editor"),
    (r"\bNFR-\d+", "a non-functional requirement from Chapter 3"),
    (r"\bFR-\d+", "a functional requirement from Chapter 3"),
    (r"\bfact line\b", "a stored 'subject: relation: value' line read without the model"),
    (r"\bentity\b", "a named person, place or thing"),
    (r"\brouter\b", "a small learned rule that decides how to answer each question"),
    (r"\bjudged\b", "re-checked by the cloud model, since right answers can be worded differently"),
    (r"\bprecision\b", "the share of given answers that were right"),
    (r"\brecall\b(?!\s+card)", "the share of the needed evidence that the search found"),
    (r"\bquantis\w+", "storing each number in fewer bits to save memory"),
    (r"\bpipelines?\b", "a fixed sequence of steps"),
    (r"\bwrite path\b", "how documents are stored as notes"),
    (r"\bread path\b", "how notes are found and given to the model"),
    (r"\bgat(?:e|es|ed|ing)\b", "a check that drops notes about the wrong subject"),
    (r"\bbridg\w+", "following a name found in one note to another note about that name"),
    (r"(?<!fixed )(?<!random )\bseed\b(?! \d)(?!s\b)", "the first note found, from which bridging continues"),
    (r"\bingest\w*", "loading documents into memory"),
    (r"\bgovernor\b", "a guard that keeps work within the computer's limits"),
    (r"(?<!admission )(?<!relevance )\bfloor\b", "the model alone, without memory"),
    (r"(?<!sets the )\bceiling\b", "the large model's score, used as the upper reference"),
    (r"\bclosed-book\b", "from the model's own knowledge, with no documents"),
    (r"\bcorpus\b", "the collection of documents"),
    (r"\bresidual\b", "what is left over"),
    (r"\bprovenance\b", "a record of where each note came from"),
    (r"\bcascade\b", "a chain: try the cheap way first and pass on only what it cannot handle"),
    (r"\bscreen(?:ed|ing)\b", "checked before being stored"),
    (r"\bJSON\b", "a standard text format for structured data"),
    (r"\bHTTP\b", "the protocol that web pages and web services use"),
    (r"\bPlaywright\b", "a tool that drives a web browser automatically for testing"),
    (r"\baxe(?:-core)?\b", "an automatic accessibility checker"),
    (r"\bWCAG\b", "the international guidelines for accessible web pages"),
    (r"\btemperature\b", "how random the model's word choices are"),
    (r"\bgreedy\b", "always choosing the most likely next word"),
    (r"\bFTS5\b", "the database's built-in keyword search"),
    (r"\bsqlite-vec\b", "an add-on that lets the database search by meaning"),
    (r"\bquery adapter\b", "a small learned adjustment to how questions are matched to notes"),
    (r"\bCI\b", "confidence interval: the range the true value very probably lies in"),
]
_INLINE = [(re.compile(p), g) for p, g in INLINE]
MAX_PER_PARAGRAPH = 2

# ----------------------------------------------------------------- plainer table headings

HEADERS = {
    "Pipeline": "Method",
    "Gold in context": "Answer was in what it read",
    "Prompt tokens": "Text read (tokens)",
    "Retrieval CPU ms": "Search time (ms)",
    "Model s": "Model time (s)",
    "Model calls": "Model runs",
    "Wrong, stated": "Wrong answer stated",
    "Declined": "Said it did not know",
    "Other meaning (named)": "Same-name mix-up (named)",
    "Other meaning": "Same-name mix-up",
    "Not confirmed": "Not confirmed (no answer stated)",
    "Decode tok/s": "Writing speed (tokens/s)",
    "Decode tok/s (PopQA)": "Writing speed (tokens/s)",
    "Hallucinated action": "Made-up action",
    "Δ vs always-cloud (95% CI)": "Difference from always using the cloud (95% range)",
    "2Wiki: all gold": "2Wiki: all evidence found",
    "HotpotQA: all gold": "HotpotQA: all evidence found",
    "2Wiki: both gold": "2Wiki: both pieces of evidence found",
    "HotpotQA: both gold": "HotpotQA: both pieces of evidence found",
    "Gold": "Reference answer",
    "Full-support recall": "All evidence found",
    "Tool calls / task": "Tool uses per task",
}


# ----------------------------------------------------------------- the shaded "In plain words" box


def _shade(para) -> None:
    pPr = para._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    left = OxmlElement("w:left")
    for k, v in (("w:val", "single"), ("w:sz", "18"), ("w:space", "6"), ("w:color", BOX_EDGE)):
        left.set(qn(k), v)
    bdr.append(left)
    shd = OxmlElement("w:shd")
    for k, v in (("w:val", "clear"), ("w:color", "auto"), ("w:fill", BOX_FILL)):
        shd.set(qn(k), v)
    pos = 1 if pPr.find(qn("w:pStyle")) is not None else 0  # schema order: pStyle, ..., pBdr, shd, ..., spacing, ind
    pPr.insert(pos, shd)
    pPr.insert(pos, bdr)


def box(c, paragraphs: list[str], title: str = "In plain words") -> None:
    """A shaded paragraph group with a bold title; '• ' starts a bullet."""
    for i, text in enumerate(paragraphs):
        para = c.doc.add_paragraph(style="Normal")
        pf = para.paragraph_format
        pf.left_indent, pf.right_indent, pf.first_line_indent = Cm(0.3), Cm(0.2), Cm(0)
        pf.space_before = Pt(6) if i == 0 else Pt(0)
        pf.space_after = Pt(6) if i == len(paragraphs) - 1 else Pt(2)
        para.alignment = WD_ALIGN_PARAGRAPH.LEFT
        if text.startswith("• "):
            pf.left_indent, pf.first_line_indent = Cm(0.9), Cm(-0.45)
        c._runs(para, (f"**{title}.** " if i == 0 and title else "") + text, size=10.5)
        _shade(para)


# ----------------------------------------------------------------- install


def install(c, F: dict) -> None:
    """Wrap the chapter's methods: first-use explanations in paragraphs and lists (once per main section, never
    inside quoted examples or code), plain table headings, and an opener after each keyed heading."""
    state = {"seen": set(), "on": True}
    p0, items0, table0, h2_0, h3_0 = c.p, c.items, c.table, c.h2, c.h3
    openers = PLAIN(F)

    def gloss(text: str) -> str:
        if not state["on"]:
            return text
        parts = re.split(r"(\*\*.+?\*\*|\*[^*]+?\*|`[^`]+`|\[\[.+?\]\]|⟦[^⟧]+⟧)", text)
        added = 0
        for k, part in enumerate(parts):
            if not part or part[0] in "*`[⟦":
                continue
            for rx, g in _INLINE:
                if added >= MAX_PER_PARAGRAPH:
                    break
                if rx.pattern in state["seen"]:
                    continue
                m = rx.search(part)
                if not m:
                    continue
                before, after = part[:m.start()], part[m.end():]
                if (before.rstrip().endswith("(") or after.lstrip().startswith("(") or after.startswith(")")
                        or after[:2] in ("'s", "’s") or before.count("(") > before.count(")")):
                    continue  # already explained, an abbreviation in brackets, a possessive, or inside brackets
                part = f"{before}{m.group(0)} ({g}){after}"
                state["seen"].add(rx.pattern)
                added += 1
            parts[k] = part
        return "".join(parts)

    def p(text: str) -> None:
        p0(gloss(text))

    def items(entries, numbered: bool = True) -> None:
        items0([gloss(e) for e in entries], numbered)

    def table(caption, header, rows, widths=None, size=10, key=None):
        return table0(caption, [HEADERS.get(h, h) for h in header], rows, widths, size, key)

    def h2(text: str, key: str | None = None) -> None:
        h2_0(text, key)
        state["seen"] = set()  # each main section explains its own terms once
        state["on"] = text != "Introduction"  # the introduction has the glossary instead
        k = key or text
        if k in openers:
            box(c, openers[k])

    def h3(text: str, key: str | None = None) -> None:
        h3_0(text, key)
        k = key or text
        if k in openers:
            box(c, openers[k])

    c.p, c.items, c.table, c.h2, c.h3 = p, items, table, h2, h3


# ----------------------------------------------------------------- the reader's summary and the section openers


def pct(x) -> str:
    return "–" if x is None else f"{100 * x:.1f}%"


def AT_A_GLANCE(F: dict) -> list[str]:  # noqa: N802
    v, k, a5 = F["verified"], F["kimi_closed"], F["alone_05"]
    rag = F["rag"]
    return [
        "**What CAMR is.** A language model writes text by predicting the next word, and it only knows what it "
        "absorbed in training. Models small enough for a laptop know little. CAMR is a memory placed beside the "
        "model, like a notebook in an open-book exam: documents are filed as short notes, and for each question "
        "CAMR finds the few notes that matter and gives the model only those. The model itself is never changed.",
        f"**What was tested.** {F['n_models']} models from {F['min_b']:.1f} to {F['max_b']:.1f} billion parameters, "
        "alone and with CAMR; CAMR against eight designs that industry uses to give models documents (RAG); three "
        "business automations (a support desk, an agent that does office tasks, and a daily news digest); and what "
        "it all costs in time and money.",
        "**What was found.**",
        f"• With memory, a small laptop model knows as much as a large cloud model about less-known facts, from "
        f"about 1.5 billion parameters upwards ({F['reach_kimi']} of {F['n_models']} models matched or beat the "
        "cloud model).",
        f"• Careful answering works. Alone, the smallest model stated a wrong answer for {pct(a5['wrong'])} of "
        f"questions; with CAMR for {pct(v.get('hallucinated'))}, while getting {pct(v.get('correct'))} right. The "
        f"cloud model alone got {pct(k['correct'])} right but stated a wrong answer {pct(k['wrong'])} of the time.",
        f"• Against today's standard (RAG): with a small model CAMR was better on both counts ({pct(rag['c05'])} "
        f"right against {pct(rag['r05'])}; {pct(rag['c05w'])} wrong against {pct(rag['r05w'])}). With the cloud "
        f"model RAG answered more ({pct(rag['rk'])} against {pct(rag['ck'])}) but stated about "
        f"{rag['rkw'] / max(rag['ckw'], 1e-9):.0f} times as many wrong answers.",
        f"• In business automations, memory made the cloud model useful: alone it handed {pct(F['desk_alone'])} "
        f"of support tickets to a person; with CAMR it resolved {pct(F['desk_answerable'])} of the answerable "
        "ones and sent no wrong reply.",
        "• Memory does not fix reasoning: for maths, a stronger model or a calculator is needed.",
        "• Bigger models are slow on a laptop: every model of 6 billion parameters or more answered more slowly "
        "than the cloud model.",
        "**How to read the numbers.** Most results are percentages of a set of questions (usually 200). *Correct* "
        "means a right answer. *Wrong* means a wrong answer stated as fact, the harmful kind. *Declined* or *not "
        "confirmed* means the system said it did not know or passed the question on: safe, but not useful. A good "
        "system has many correct answers and very few wrong ones. Each section starts with a box like this one that "
        "says what it found in plain words; the glossary in this section explains the terms used throughout.",
    ]


def PLAIN(F: dict) -> dict[str, list[str]]:  # noqa: N802
    v, k, a5 = F["verified"], F["kimi_closed"], F["alone_05"]
    rag, cost = F["rag"], F["cost"]
    return {
        "sec_env": ["Everything ran on ordinary computers of the kind people already own: a 4-core processor, 16 GB "
                    "of memory and no graphics card. That is deliberate, because the point is that a small model "
                    "with memory should work on such a machine. The cloud model was used over the internet and "
                    "paid per use."],
        "sec_data": ["Results only mean something if the questions are fair. Most questions come from public "
                     "research sets with known answers, so that anyone can check the results: less-known facts "
                     "(PopQA), questions that need two Wikipedia articles (HotpotQA, 2WikiMultiHopQA) and school "
                     "maths problems (GSM8K). Questions used to build and tune the system were kept apart from those "
                     "used for the final test. The automations used an invented company (Helio Solar) and 30 days of "
                     "real Wikipedia news pages."],
        "sec_impl": ["Think of CAMR as a helper in an open-book exam. When documents arrive, it cuts them into "
                     "short notes and files them (the *write path*). When a question arrives, it finds the few notes "
                     "that matter, checks that they are about the right subject, and gives the model only those, "
                     "within a size limit (the *read path*). If the answer can be read straight from a note, the "
                     "model is not asked at all, and an answer is stated only if a stored note supports it."],
        "sec_formal": ["The equations below say in symbols what the read path does in words: every note gets a "
                       "score for how well it matches the question, notes about the wrong subject are dropped, and "
                       "the best notes are kept until the size limit is reached. A reader who prefers words can skip "
                       "to the next section without losing the thread."],
        "sec_verify_impl": ["An answer is stated as fact only if all of its words appear in one stored note, and "
                            "that note is about the right subject and the right kind of fact. Otherwise CAMR says "
                            "it cannot confirm the answer, or hands the question on."],
        "sec_learn_impl": ["Two ways of learning without retraining the model: looking up what memory lacks and "
                           "keeping it, and keeping corrections as worked examples to copy the next time."],
        "sec_bulk_impl": ["How a large collection of documents is stored without running the computer out of "
                          "memory: notes become searchable by keyword at once, and the slower search-by-meaning is "
                          "added in the background, always within limits measured on the device."],
        "sec_policy_impl": ["A small learned rule decides how each question is answered (how much memory to read, "
                            "or whether to ask the cloud model). It was trained on practice questions, rewarded for "
                            "right answers and charged for time and cloud cost."],
        "sec_gateway": ["A gateway is a small local web service. Every answering system (the model alone, context "
                        "stuffing, RAG and CAMR) sits behind the same four commands, so an n8n workflow can switch "
                        "systems without any other change. The screenshots show the workflows running, with what "
                        "went into and came out of each step."],
        "sec_selection": ["No language model was trained in this project; they are used as downloaded. What was "
                          "chosen is which models to test, what to compare CAMR with (the model alone, the cloud "
                          "model, eight popular RAG designs, pasting all documents in, and retraining) and how "
                          "answers are scored. The few small settings inside CAMR were tuned on practice questions, "
                          "never on the final test."],
        "sec_rag_def": ["All eight designs search the same store and give the model the top five passages. They "
                        "differ in how they search (by meaning, by keywords, or both), whether a second model "
                        "re-orders the results, and whether they check the results before answering."],
        "sec_testing": [f"Testing checked two things: that each part does what the requirements ask "
                        f"({F['n_tests']} automated tests, all passing), and that every problem found during the "
                        "experiments was fixed and checked again. Every bug has a number (D-01 to D-40), a cause, a "
                        "fix and a retest."],
        "sec_vc": ["All work is kept in Git, which records every change with its date and a description, so the "
                   "order of the work and the origin of every result can be traced."],
        "sec_results": ["This section answers one question at a time. Most numbers are percentages of a set of "
                        "questions: *correct* is a right answer, *wrong* is a wrong answer stated as fact (the "
                        "harmful kind), and *declined* means the system said it did not know (safe, but not useful). "
                        "Each part ends with where the system fell short."],
        "sec_scorecard": ["The table gives each claim a verdict: met, partly met, or not met. In short, memory helps "
                          "whenever the problem is missing knowledge, and does not help when the problem is "
                          "reasoning, such as maths."],
        "sec_retrieval": ["Before a model can answer from memory, the right notes have to be found. For questions "
                          "that need two facts, CAMR follows the name found in the first note to a second note; at "
                          "the same reading budget this more than doubled how often both facts were found (35.8% to "
                          "78.4%)."],
        "sec_verified": [f"Alone, the smallest model (0.5B) got {pct(a5['correct'])} of the 200 test questions right "
                         f"and stated a wrong answer for {pct(a5['wrong'])}. With CAMR's verified answering it got "
                         f"{pct(v.get('correct'))} right and stated a wrong answer for only "
                         f"{pct(v.get('hallucinated'))}. The cloud model alone got {pct(k['correct'])} right but "
                         f"stated a wrong answer for {pct(k['wrong'])}. The price of being careful is that some "
                         "questions get no stated answer."],
        "sec_models": [f"{F['n_models']} models from {F['min_b']:.1f} to {F['max_b']:.1f} billion parameters were "
                       "tested alone and with CAMR on the same questions. With memory, small models know as much as "
                       "big ones: from about 1.5 billion parameters, models with CAMR beat the cloud model on "
                       "less-known facts. Bigger models still read and reason better (two-step questions and maths), "
                       "but on a laptop they are much slower. For a 16 GB laptop the best choice is a 1.5B model for "
                       "facts and a 3B model for questions that need several documents."],
        "sec_ragresult": [f"RAG is today's standard way to give a model documents. Eight RAG designs and CAMR "
                          "answered the same 200 questions from the same documents. With a small model, CAMR was "
                          f"right more often ({pct(rag['c05'])} against {pct(rag['r05'])} for the best RAG design) and "
                          f"almost never stated a wrong answer ({pct(rag['c05w'])} against {pct(rag['r05w'])}). With "
                          f"the cloud model, the best RAG design answered more questions correctly ({pct(rag['rk'])} "
                          f"against {pct(rag['ck'])}) but stated about {rag['rkw'] / max(rag['ckw'], 1e-9):.0f} times "
                          f"as many wrong answers ({pct(rag['rkw'])} against {pct(rag['ckw'])})."],
        "sec_gap": ["Questions that need two facts are hard for small models even when both facts are found, "
                    "because the model has to combine them. From about 3 billion parameters, a small model with "
                    "memory matched the cloud model on these questions; the smallest model improved but stayed well "
                    "behind."],
        "sec_examples": ["Real answers, word for word, with and without memory, so the numbers above can be seen in "
                         "practice."],
        "sec_learning": ["Can a model learn without being retrained? For knowledge, yes: CAMR looks up what it does "
                         "not know and keeps it, and it learns invented formulas from corrections (the cloud model "
                         "was right every time after four corrections; the smallest model went from 0% to 70.8% on "
                         "invented formulas). Retraining (LoRA) did better on the exact wording it was trained on, "
                         "but forgot other skills."],
        "sec_agentic": [f"Three automations were built in n8n: a customer-support desk for an invented company, an "
                        "agent that writes invoices and replies, and a daily news digest from live Wikipedia pages. "
                        f"Alone, the cloud model handed {pct(F['desk_alone'])} of support tickets to a person and "
                        f"completed {pct(F['agent_alone'])} of agent tasks. With CAMR it resolved "
                        f"{pct(F['desk_answerable'])} of the answerable tickets with no wrong reply, completed "
                        f"{pct(F['agent_camr'])} of agent tasks, and answered {pct(F['news_camr'])} of the news "
                        f"questions correctly (alone: {pct(F['news_alone'])})."],
        "sec_cost": [f"Local models cost nothing per answer, only time. The cloud model is paid per token. The whole "
                     f"study spent ${cost['usd']:.2f} on {cost['calls']:,} cloud calls. CAMR was the cheapest way to "
                     "use the cloud model in every scenario except the agent, because it sends only the few notes "
                     "that are needed."],
        "sec_bulk": ["Memory must also cope with a lot of data on an ordinary computer. 123,301 paragraphs were made "
                     "searchable in under six minutes, and a built-in guard stops cleanly before the computer runs "
                     "out of memory or disk."],
        "sec_policy": ["A small learned rule decides, question by question, whether to answer on the laptop or ask "
                       "the cloud model. It kept 83% of questions on the device while reaching 96% of the accuracy "
                       "of always asking the cloud model."],
        "sec_appres": ["CAMR Personal is the desktop app built on the engine. You can tell it things, ask questions, "
                       "and see which note each answer came from."],
        "sec_scenarios": ["Longer conversations with the app and a real model, recorded as they happened."],
        "sec_learn_scen": ["The app learning in use: looking things up, installing knowledge packs and tidying its "
                           "memory, recorded as it happened."],
        "sec_repro": ["Anyone can rerun the main evaluations from the saved files, without the internet or an API "
                      "key, and get the same numbers. All 16 checks passed, twice."],
        "sec_flaws": ["Where the system failed, and why. Every flaw is listed, including bugs that were fixed and "
                      "weaknesses that remain."],
        "sec_limits": ["What the results do not show. They hold for English questions, models running on 4-core "
                       "computers, the numbers of questions reported, an invented company's data, and a cloud "
                       "model that does not give the same answer twice."],
    }

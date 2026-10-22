"""CAMR Personal: a local assistant whose model stays frozen while its memory grows.

This is the deployment scenario of the study, packaged for real use:

* any model the user already has in Ollama answers;
* everything the user teaches it (notes, files, approved answers, what they say
  in chat) is stored as retrievable notes in one SQLite file under ``~/.camr``;
* each question reads only the few notes it needs (gating + entity bridging,
  the best read path measured in docs/FINDINGS.md), so knowledge grows with
  *storage*, not with the context window or with compute;
* the conversation itself becomes memory, so a chat can run far past the
  model's context window and still recall what was said weeks ago;
* when memory has nothing for a general question, it looks the subject up on the
  web (if the user allows it), learns the page, and answers from it: it learns
  instead of saying "I don't know" (``camr.memory.eager``). Questions about the
  user's own life are never sent anywhere; for those it asks to be taught;
* knowledge packs install ready-made memory, and sleep consolidates memory while
  the app is idle (``camr.memory.packs``, ``camr.memory.sleep``).

Only lookups leave the machine, and only the subject of a general question is
sent. Feedback is stored locally and only exported when the user chooses to.

The class is UI-agnostic; ``camr/app/server.py`` serves the web front end.
"""

from __future__ import annotations

import base64
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

import requests

from camr.app import codecheck, reader, tiers
from camr.config import Config, LocalModelConfig
from camr.device import Governor, Limits, index_threshold, probe
from camr.memory import packs as packs_mod
from camr.memory.adapter import QueryAdapter
from camr.memory.eager import knows_subject, learn_meanings, learn_pages
from camr.memory.embedder import Embedder, OllamaEmbedder
from camr.memory.engine import MemoryEngine
from camr.memory.fetch import WebLookup, embedding_rank, subjects
from camr.memory.note import Document
from camr.memory.sleep import sleep as run_sleep
from camr.memory.store import SQLiteVectorStore
from camr.memory.answer import BARE as BARE_PROMPT
from camr.memory.answer import READ as READ_PROMPT
from camr.memory.answer import cross_verify
from camr.memory.verify import (CROSS, check, claim, compress, fact_answer, meaning_units, relation_of,
                                units_from_notes)
from camr.learn.link import Link, model_declined
from camr.learn.calc import CALC_BARE
from camr.memory.skills import skill_of
from camr.models.runner import OllamaRunner
from camr.models.tokenizer import RegexTokenizer

DEFAULT_HOME = Path.home() / ".camr"
DEFAULT_HOST = "http://127.0.0.1:11434"
DEFAULT_EMBED_MODEL = "nomic-embed-text"

# Abstain threshold (raw cosine) per embedder. BGE's 0.50 is the value used in every
# benchmark: the 90th percentile of off-topic similarities on HotpotQA. The same rule
# gives 0.55 for nomic-embed-text (docs/calibration/, scripts/calibrate_gating.py).
MIN_SIMILARITY = {"BAAI/bge-small-en-v1.5": 0.50, "ollama:nomic-embed-text": 0.55}

# Where a note came from.  Shown on every source chip in the UI.
KINDS = {
    "note": "your note",
    "file": "your file",
    "chat": "something you said",
    "learned": "an answer you approved",
    "web": "looked up online",
    "pack": "from a knowledge pack",
    "profile": "what you told me about yourself",
    "card": "a skill you corrected",
    "fix": "a fix you made",
}
BUNDLED_PACKS = Path(__file__).resolve().parent / "packs"

APP_SCHEMA = """
CREATE TABLE IF NOT EXISTS app_conversation (
    conversation_id INTEGER PRIMARY KEY,
    title           TEXT NOT NULL,
    created_at      TIMESTAMP NOT NULL,
    updated_at      TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS app_sleep (
    sleep_id    INTEGER PRIMARY KEY,
    at          TIMESTAMP NOT NULL,
    report_json TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS app_lookup (
    lookup_id  INTEGER PRIMARY KEY,
    at         TIMESTAMP NOT NULL,
    question   TEXT NOT NULL,
    queries    TEXT NOT NULL,
    pages_json TEXT NOT NULL,
    notes_added INTEGER NOT NULL,
    ms         REAL
);
CREATE TABLE IF NOT EXISTS app_turn (
    turn_id        INTEGER PRIMARY KEY,
    at             TIMESTAMP NOT NULL,
    model          TEXT NOT NULL,
    question       TEXT NOT NULL,
    answer         TEXT NOT NULL,
    notes_used     INTEGER NOT NULL,
    abstained      INTEGER NOT NULL,
    grounded       REAL,
    retrieval_ms   REAL,
    generation_ms  REAL,
    prompt_tokens  INTEGER,
    feedback       INTEGER,         -- +1 helpful, -1 not helpful, NULL none
    conversation_id INTEGER,
    sources_json   TEXT
);
CREATE TABLE IF NOT EXISTS app_upload (
    file_id    TEXT PRIMARY KEY,    -- sha256 of the file (16 hex): its folder under <home>/files
    name       TEXT NOT NULL,
    doc_id     TEXT NOT NULL,       -- file-<name>: its notes; what was learned about it later is file-<name>#…
    kind       TEXT NOT NULL,       -- text | docx | pdf | image
    page_count INTEGER,
    summary    TEXT,
    chips_json TEXT,
    questions_json TEXT,
    seen       TEXT,                -- what the vision model said the image shows
    problem    TEXT,
    at         TIMESTAMP NOT NULL
);
CREATE TABLE IF NOT EXISTS app_card (
    pack    TEXT NOT NULL,      -- the card pack it came from
    skill   TEXT NOT NULL,      -- the skill its corrections name ("Correction: <skill>")
    model   TEXT NOT NULL,      -- the Ollama model: the base model with the card's adapter
    base    TEXT NOT NULL,      -- the model the card was trained for: it is attached only when that model answers
    at      TIMESTAMP NOT NULL,
    PRIMARY KEY (pack, skill)
);
CREATE TABLE IF NOT EXISTS app_file (
    doc_id  TEXT PRIMARY KEY,   -- file-<name>: the source a taught file's notes belong to
    sha256  TEXT NOT NULL,      -- of the text learned, so teaching the same file again can tell if it changed
    at      TIMESTAMP NOT NULL
);
"""

# ---------------------------------------------------------------------- privacy: what may be looked up online
# A question about the user's own life never leaves the machine: it is not looked up, and its answer is not
# cross-checked online. ``fetch.is_personal`` (first-person words) is what the research pipeline measured and is left
# as it is; running real questions through it showed three gaps, closed here:
#   * "US" in capitals is the country, not "us" ("the capital of the US" was never looked up);
#   * reported speech is about someone the user knows ("What did Sarah say about the trip?" sent "Sarah");
#   * a personal errand asked without a pronoun ("When is the dentist appointment?" sent "dentist appointment").
# A name only the user's own notes mention is never sent either (``Assistant._private_names``).
_FIRST_PERSON = re.compile(r"\b(?:my|mine|me|myself|i|i'm|i've|i'd|i'll|our|ours|ourselves|we|we're|we've|us)\b",
                           re.I)
_REPORTED = re.compile(r"\b(?:did|does|do|has|have|had)\s+(?:[\w'’-]+\s+){1,3}?(?:say|tell|text|mention|ask|promise)\b",
                       re.I)
# Words of the user's own errands, money, health and access. They mark a question as personal only when it names
# no one ("When is the dentist appointment?"), so "When is Beyoncé's birthday?" is still looked up.
PRIVATE_LIFE = {"appointment", "appointments", "meeting", "meetings", "booking", "bookings", "reservation",
                "reservations", "password", "passwords", "passcode", "pin", "wifi", "salary", "payslip", "rent",
                "prescription", "prescriptions", "diagnosis", "deadline", "deadlines", "birthday", "anniversary"}
# Where a note came from: the user (private) or the world (a looked-up page or a pack).
PRIVATE_KINDS = ("note", "file", "chat", "learned", "fix")


def is_about_user(question: str) -> bool:
    """True when the question is about the user's own life, so it is answered from memory or not at all."""
    if any(m.group(0) != "US" for m in _FIRST_PERSON.finditer(question)):
        return True
    if _REPORTED.search(question):
        return True
    words = set(re.findall(r"[a-z]+", question.lower()))
    names_someone = any(w[:1].isupper() for w in question.split()[1:])  # past the opening "What", "When", ...
    return bool(words & PRIVATE_LIFE) and not names_someone

# Prompt F: prompt D (chosen on a development set and confirmed on two held-out sets, D-13 and D-16) with rule 3
# asking to be taught instead of only saying "I don't know", and answering first when the notes have it (D-19, where
# prompt E made a 3B model lead with "I don't know that yet"). Scored on the same sets (scripts/prompt_eval.py).
CHAT_PROMPT = """You are a private personal assistant running on the user's own computer.

Today is {today}.

The notes below come from the user's personal memory and are about the user. "The user said …" means the user told you this earlier; "I" inside it is the user. Treat what the notes say about the user as true and answer from them directly. Notes are dated and listed oldest first; when notes disagree, the newest is right.

How to answer:
1. If the notes contain the answer, give it from the notes.
2. If it is a general-knowledge question (facts, maths, definitions), answer it from your own knowledge.
3. Only if it asks about the user's own life and the notes do not mention it, say that you don't know that yet and ask the user to tell you, so you can remember it. Never invent personal details, and never say you don't know when the notes answer the question.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
"""

# ---------------------------------------------------------------------- coding
# A coding request is a task, not knowledge about the user: it gets a coding prompt (memory holds the user's code,
# APIs and conventions), a longer answer, no web lookup, no trust link (whose signals were learned on personal
# facts: it escalated or held back every code answer), and it is not kept as chat memory.
CODE_PROMPT = """You are a coding assistant running on the user's own computer.

The notes below come from the user's memory: their code, the APIs and libraries they use, their conventions, and fixes they made before. Use them whenever they are relevant: call the user's own functions, endpoints and settings by the names the notes give, and write code the way their code is written. Do not invent functions, endpoints or settings that neither the notes nor the language's standard library have; if something you need is missing, say in one line what you assumed.

How to answer:
1. Give complete, working code in one fenced block with its language.
2. Then at most three short lines on what it does or what changed.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
"""

CODE_ANSWER_TOKENS, CODE_CONTEXT = 2048, 8192  # a chat answer stops at 768 tokens: too short for a file of code

_CODE_VERB = re.compile(r"^\s*(?:please\s+)?(?:(?:can|could|would)\s+you\s+)?(?:write|create|generate|implement|build|"
                        r"code|make|add|refactor|fix|debug|optimi[sz]e|convert|translate|port|rewrite|explain|document|"
                        r"test|complete|finish|modify|update|change|rename|improve|review|show me how)\b", re.I)
_CODE_VERB_ANY = re.compile(r"\b(?:write|create|generate|implement|refactor|debug|optimi[sz]e|rewrite|port)\b", re.I)
_CODE_WORD = re.compile(r"\b(?:function|func|method|class|script|code|program|snippet|query|regex|endpoint|api|bug|"
                        r"tests?|component|module|loop|python|javascript|typescript|java|golang|rust|kotlin|swift|sql|"
                        r"bash|shell|html|css|react|vue|django|flask|fastapi|node|express|json|yaml|dockerfile|"
                        r"algorithm|recursion|array|dataframe|pandas|numpy|compile|syntax|exception|variable|async|"
                        r"requests|http|cli|library|package|import)\b", re.I)
_CODE_TEXT = re.compile(r"```|^\s*(?:def |class |import |from [\w.]+ import |function |const |let |var |public |"
                        r"private |#include|SELECT |CREATE TABLE)|Traceback \(most recent call last\)|\b\w+(?:Error|"
                        r"Exception):", re.M)


_CODE_LANG = re.compile(r"\b(?:python|javascript|typescript|golang|rust|kotlin|swift|sql|bash|html|css|react|vue|"
                        r"django|flask|fastapi|node(?:js)?|pandas|numpy|regex|dockerfile|c\+\+|c#)\b", re.I)  # not "java": also coffee


def is_code_request(text: str) -> bool:
    """A request to write, change or explain code, or a question about code. A question that only mentions an API or
    a key ("What is my API key?") is about the user's own life; one naming a language or library ("How do I reverse
    a list in Python?") is about code."""
    if _CODE_TEXT.search(text):
        return True
    if not _CODE_WORD.search(text) and not _CODE_LANG.search(text):
        return False
    if _CODE_VERB.match(text) or _CODE_VERB_ANY.search(text):  # "Using our library, write a function …" too
        return True
    return is_question(text) and (bool(_CODE_LANG.search(text)) or not is_about_user(text))


# ---------------------------------------------------------------------- uploads (reader.py)
VISION_HINT = re.compile(r"vl\b|vision|llava|moondream|minicpm-v|gemma3|bakllava|granite3\.2-vision", re.I)

SEE_PROMPT = """Look at this image the user saved so that you can remember it for them later.
Text found in the image (by text recognition; it may contain errors):
<<<
{ocr}
>>>
First line: what the image is, starting with "This is" (a receipt, a photo of handwritten notes, a screenshot of …).
Then the facts worth remembering (names, dates, amounts, totals, places, items), one per line starting with "- ".
Use only what you can see or read in the image. At most 8 lines in all."""

STUDY_PROMPT = """You have just read a file the user gave you, so that you can remember it for them.

File: {name}
What it contains:
<<<
{excerpt}
>>>

Reply in exactly this form, and nothing else:
Summary: <one sentence: what this file is and what it is about>
Question: <one short question to the user whose answer would help you remember this file correctly later, such as what it is for or whose it is; never ask about something the file already says>
Question: <another such question, or leave this line out>"""

FOCUS = {"Dates & deadlines": "every date, deadline or appointment, with what it is for",
         "Numbers & totals": "every amount, total, price, quantity or other number that matters, with what it is",
         "People": "every person named, with who they are or what they did",
         "Key points": "the key points worth remembering"}

FOCUS_PROMPT = """From the file below, list {what}. One per line, starting with "- ". Write each as a complete short
sentence that still makes sense on its own later (say what it belongs to). Only what the file says. If there is
nothing, write: none

File: {name}
<<<
{text}
>>>"""


def default_questions(about: str) -> list[str]:
    """Questions to ask about a file when the model wrote none."""
    a = about.lower()
    if re.search(r"\.(?:py|js|ts|tsx|jsx|java|kt|go|rs|c|cpp|cs|rb|php|swift|sql|sh|ipynb)\b", a):
        return ["Which project is this from, and what does it do?"]
    if re.search(r"receipt|invoice|bill|total|ksh|kes", a):
        return ["What was this for?", "Should I keep track of totals like this one?"]
    if "screenshot" in a:
        return ["Why did you save this screenshot?"]
    if re.search(r"handwrit|notes|whiteboard|lecture|class", a):
        return ["Which subject or class is this from?"]
    return ["What should I remember this file for?"]


# A question is not knowledge about the user, so it is not kept as chat memory (defect D-14).
_QUESTION = re.compile(r"^\s*(?:what|which|who|whom|whose|when|where|why|how|is|are|was|were|do|does|did|can|could|"
                       r"would|should|will|shall|may|might|am|have|has|tell me|give me|convert|calculate|explain)\b", re.I)


def is_question(text: str) -> bool:
    text = text.strip()
    return text.endswith("?") or bool(_QUESTION.match(text))


# Small talk: greetings, thanks, "how are you", acknowledgements, goodbyes, and questions to the assistant about itself.
# Nothing to recall, look up or remember: the model answers from the conversation so far. Treated as a gap in
# memory, "hi" was looked up (9 s), stored the Wikipedia pages "Hi (cuneiform)" and "Hi (song)" as nine memories, and
# was itself kept as chat memory.
_SMALL_TALK = re.compile(r"""(?:
    (?:hi+|hello+|hey+|hiya|howdy|yo|sup|greetings|hallo|hola|salut|jambo|mambo|sasa|niaje|habari(?:\ yako|\ zako|\ gani)?)
  | good\ (?:morning|afternoon|evening|night|day) | morning | evening
  | how(?:'s|s|\ is|\ are|\ r)?\ (?:you|u|ya|it\ going|things|life|your\ day|everything)(?:\ doing|\ today|\ going)*
  | what'?s\ up | wassup | what'?s\ new
  | thanks? | thank\ you | thx | ty | cheers | asante(?:\ sana)? | much\ appreciated
  | ok(?:ay)? | k | cool | nice | great | awesome | perfect | got\ it | alright | all\ right | sure | fine
  | yes | no | yeah | yep | yup | nope | nah | lol | haha+ | hmm+ | wow
  | bye | goodbye | good\ ?bye | see\ (?:you|ya)(?:\ later|\ soon)? | later | good\ ?night | take\ care | kwaheri
  | who\ are\ you | what(?:'s|\ is)\ your\ name | what\ can\ you\ do | are\ you\ there | nice\ to\ meet\ you
)(?:\ (?:so\ much|a\ lot|very\ much|again|there|camr|friend|buddy|mate|everyone|all|too))*""", re.I | re.X)


def is_small_talk(text: str) -> bool:
    """A message that carries no knowledge and asks for none: every part of it is small talk ("Hi, how are you?")."""
    parts = re.split(r"[,.!?;:\u2026]+", text.lower().replace("\u2019", "'"))
    parts = [re.sub(r"[^\w' ]+", "", p).strip() for p in parts]  # emoji and stray marks
    parts = [re.sub(r"\s+", " ", p) for p in parts if p]
    return bool(parts) and all(_SMALL_TALK.fullmatch(p) for p in parts)


_REMEMBER = re.compile(r"^\s*(?:/remember|remember(?: that)?|note:)\s*[:,-]?\s*(.+)$", re.I | re.S)
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-.,:]*")
_STOP = set("""a an the and or but if of to in on at for from by with about as is are was were be been being it its
this that these those i you he she we they me my your our their what which who whom whose when where why how do does
did not no yes can could would should will just so than then there here also only very more most""".split())


def expert_name(text: str | None) -> str | None:
    """An expert's name as stored: lower case, letters, digits and - _ : . (e.g. "code:acme"); None when empty."""
    name = re.sub(r"[^a-z0-9:_.-]+", "-", (text or "").strip().lower()).strip("-")[:40]
    return name or None


def worth_looking_up(question: str) -> bool:
    """Only a question is looked up ("tell me about …" counts), and only one with a content word to search for. A
    remark ("the weather is nice today") or a bare word is not sent anywhere."""
    words = [w.lower().strip(".,:'") for w in _WORD.findall(question)]
    return is_question(question) and any(len(w) >= 3 and w not in _STOP for w in words)


@dataclass
class Source:
    note_id: int
    kind: str
    title: str
    text: str
    similarity: float
    via_bridge: bool = False
    url: str = ""


@dataclass
class Turn:
    turn_id: int | None
    question: str
    answer: str
    sources: list[Source] = field(default_factory=list)
    abstained: bool = False
    grounded: float | None = None  # share of the answer's content words found in the notes it read
    retrieval_ms: float = 0.0
    generation_ms: float = 0.0
    first_token_ms: float | None = None  # time from sending the prompt to the first streamed word
    prompt_tokens: int | None = None
    saved_to_memory: bool = False
    conversation_id: int | None = None
    feedback: int | None = None
    learned: dict | None = None  # what a web lookup added for this answer (queries, pages, notes)
    ask_to_teach: bool = False   # a personal question memory cannot answer: the UI offers "Teach me"
    # whether a short factual answer is supported by what memory holds: {"status": "verified" | "unverified" |
    # "unchecked", "by", "evidence", "source", "reason"}; None when not a short factual question
    verification: dict | None = None
    # what the link did with the local answer: {"action": "keep" | "decline" | "escalate", "by", "draft", "values"}
    link: dict | None = None
    # the skill card that answered: {"skill", "model", "expression", "value"}
    skill: dict | None = None
    # a file the user gave: {"file_id", "name", "kind", "pages", "summary", "chips", "questions", …}
    upload: dict | None = None
    # the experts opened for this question (None: all of memory was read)
    experts: list | None = None
    # the syntax check of a code answer: {"language", "ok", "error", "line", "retried", "first_error"}
    check: dict | None = None

    def as_dict(self) -> dict:
        return asdict(self)


def installed_models(host: str = DEFAULT_HOST, timeout: float = 3.0, session=None) -> list[dict]:
    """Models the user already has in Ollama (name, size in GB, parameter size, whether it embeds)."""
    resp = (session or requests).get(f"{host}/api/tags", timeout=timeout)
    resp.raise_for_status()
    out = []
    for m in resp.json().get("models", []):
        details = m.get("details") or {}
        fam = (details.get("family") or "").lower()
        out.append({"name": m["name"], "size_gb": round((m.get("size") or 0) / 1e9, 1),
                    "parameters": details.get("parameter_size", "?"), "family": details.get("family", "?"),
                    "embedding": "bert" in fam or "embed" in m["name"]})
    return sorted(out, key=lambda m: m["size_gb"])


def grounded_share(answer: str, notes: str) -> float | None:
    """Share of the answer's content words that occur in the notes (None when there is nothing to check)."""
    words = [w.strip(".,:").lower() for w in _WORD.findall(answer)]
    words = [w for w in words if w and w not in _STOP]
    if not words or not notes:
        return None
    hay = notes.lower()
    return sum(1 for w in words if w in hay) / len(words)


LARGE_TEXT_CHARS = 200_000  # about 40k words: above this, vectors are added in the background

_SHORT_Q = re.compile(r"^\s*(?:who|whom|whose|when|where|which|in what|in which|what (?:year|city|country|"
                      r"colou?r|genre|sport|religion|language|is the (?:capital|population|name))|how many|how old)\b",
                      re.I)


def _short_factual(question: str) -> bool:
    """A question with a short factual answer (a name, place, date, number): the kind memory can verify."""
    return is_question(question) and (relation_of(question) is not None or bool(_SHORT_Q.match(question)))


def _verification(question: str, answer: str, units) -> dict:
    """Is the answer's claim supported by what memory read? Long, explanatory answers are not judged."""
    if len(claim(answer).split()) > 14:
        return {"status": "unchecked", "reason": "a long answer; only short factual answers are checked"}
    if not units:
        return {"status": "unchecked", "reason": "memory had nothing on this: the model's own knowledge"}
    v = check(question, answer, units)
    if v.supported:
        return {"status": "verified", "by": "model", "evidence": v.evidence.render(), "source": v.evidence.title,
                "ambiguous": v.others}
    if v.reason == "declined":
        return {"status": "unchecked", "reason": "no answer given"}
    reasons = {"not in memory": "what memory read does not say this",
               "another subject": "memory says this about something else",
               "another relation": "memory has a different answer for this"}
    return {"status": "unverified", "reason": reasons.get(v.reason, v.reason)}


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")


def _locked(fn):
    """One store connection is shared by the server's threads: serialise every call that touches it."""
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


class Assistant:
    """A frozen local model plus a personal memory that grows with use."""

    def __init__(self, home: str | Path = DEFAULT_HOME, *, model: str | None = None, host: str = DEFAULT_HOST,
                 token_budget: int = 512, history_turns: int = 6, remember_chat: bool = True,
                 min_similarity: float | None = None, embedder: Embedder | None = None,
                 session: requests.Session | None = None, web_lookup: WebLookup | None = None):
        self.home = Path(home).expanduser()
        self.home.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.home / "settings.json"
        saved = self._load_settings()
        self.host = host
        self.model = model or saved.get("model")
        self.token_budget = int(saved.get("token_budget", token_budget))
        self.history_turns = int(saved.get("history_turns", history_turns))
        self.remember_chat = bool(saved.get("remember_chat", remember_chat))
        self.embed_model = saved.get("embed_model", DEFAULT_EMBED_MODEL)
        self.learn_online = bool(saved.get("learn_online", True))
        self.sleep_when_idle = bool(saved.get("sleep_when_idle", True))
        # Strict mode: a short factual answer memory does not support is not stated as fact; the assistant says it
        # could not confirm it and gives it only as a lead. Off by default (the answer is labelled instead).
        self.verified_only = bool(saved.get("verified_only", False))
        # A larger installed model asked for a second opinion when a short factual answer is not confirmed
        # ("" = none). Its answer is used only if memory, or the answer's own article, confirms it.
        self.check_model = saved.get("check_model", "") or ""
        # The link (tiers.py): after a local answer, state it, decline, or ask the second-opinion model; learned per
        # model from the user's thumbs, starting from the reader bench. Off: every answer is stated.
        self.trust_learning = bool(saved.get("trust_learning", True))
        # Experts (camr.memory.store): each question opens only the experts it is about, plus shared memory.
        self.route_experts = bool(saved.get("route_experts", True))
        # The model that looks at images ("" = none; None = the first installed one that can see).
        self.vision: str | None = saved.get("vision_model")
        self._links: dict[str, tuple[Link, dict]] = {}
        self._http = session or requests.Session()
        self._lock = threading.RLock()
        self.jobs: dict[str, dict] = {}  # background work shown in the Learning panel (harvest, sleep)

        self.embedder = embedder or OllamaEmbedder(self.embed_model, host=host, session=self._http)
        if min_similarity is None:
            min_similarity = MIN_SIMILARITY.get(self.embedder.name, 0.50)
        # The read path measured best in docs/FINDINGS.md: similarity ranking,
        # gating (abstain below the threshold, admit within 0.15 of the best) and
        # entity bridging.  Verbatim notes: the user's own words are kept.
        self.cfg = Config.from_dict({
            "memory": {"write_policy": "verbatim", "retrieval_policy": "similarity_only",
                       "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0},
                       "k": 20, "token_budget": self.token_budget, "min_similarity": min_similarity,
                       "similarity_margin": 0.15, "expansion": "entity", "entity_gate": True, "chunk_tokens": 120,
                       # hybrid: notes found by their words join the vector hits (measured on 196k notes: recall@10
                       # 84.3% against 75.4% for vectors alone, results/bulk/ingest.json)
                       "keyword_k": 20,
                       # Phase 2 (results/bench/phase2): dates and periods, profile notes, counting, the slot gate
                       "dated_context": True, "time_filter": True, "entity_gate_skip_time": True, "profile": True,
                       # whole notes at 512 tokens: sentence compression (the "compress" flag) was chosen first,
                       # under a scoring rule that did not check the answer survived, and reversed once it did
                       # (results/bench/phase2/rescore)
                       "aggregate": True, "slot_gate": True},
        })
        # One store file per embedder: vectors from different embedders cannot be mixed.
        db = "memory.sqlite" if embedder is not None or self.embedder.name.startswith("BAAI") else \
            f"memory-{re.sub(r'[^A-Za-z0-9]+', '-', self.embedder.name)}.sqlite"
        self.store = SQLiteVectorStore(self.home / db, dim=self.embedder.dim, embedder_name=self.embedder.name,
                                       check_same_thread=False)
        # Forget means gone: SQLite otherwise leaves a deleted note's text readable in the file's free pages, and the
        # keyword index (FTS5) keeps a deleted note's words in its segments until they are merged. FTS5's own
        # secure-delete (SQLite 3.44+) removes them at once; with an older SQLite, forget() rebuilds the index.
        self.store.conn.execute("PRAGMA secure_delete = ON")
        try:
            with self.store.conn:
                self.store.conn.execute("INSERT INTO note_fts(note_fts, rank) VALUES ('secure-delete', 1)")
            self._fts_secure = True
        except sqlite3.OperationalError:
            self._fts_secure = False
        self.store.conn.executescript(APP_SCHEMA)
        cols = {r[1] for r in self.store.conn.execute("PRAGMA table_info(app_turn)")}
        for col, typ in (("conversation_id", "INTEGER"), ("sources_json", "TEXT"), ("learned_json", "TEXT"),
                         ("ask_to_teach", "INTEGER"), ("verification_json", "TEXT"), ("link_json", "TEXT"),
                         ("skill_json", "TEXT"), ("upload_json", "TEXT"), ("experts_json", "TEXT"),
                         ("check_json", "TEXT")):
            if col not in cols:  # stores created by the first app version
                self.store.conn.execute(f"ALTER TABLE app_turn ADD COLUMN {col} {typ}")
        self.engine = MemoryEngine.from_config(self.cfg, store=self.store, embedder=self.embedder,
                                               tokenizer=RegexTokenizer())
        self.adapter_path = self.store.path.with_suffix(".adapter.npz")
        if self.adapter_path.exists():
            try:
                self.engine.query_adapter = QueryAdapter.load(self.adapter_path)
            except (OSError, ValueError, KeyError):
                self.engine.query_adapter = None
        # CAMR_OFFLINE_WEB=1 (the test suite) answers lookups from the local cache only
        self.lookup = web_lookup or WebLookup(cache_path=self.home / "web_cache.sqlite", rank=embedding_rank(self.embedder),
                                              offline=os.environ.get("CAMR_OFFLINE_WEB") == "1")
        self.last_activity = time.time()
        self.packs_dir = self.home / "packs"
        # The device's limits: memory never fills the disk past a reserve, and background work yields to the user.
        self.governor = Governor(self.store.path, Limits(reserve_disk_mb=float(saved.get("reserve_disk_mb", 1024))))

    # ------------------------------------------------------------ settings
    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text())
        except (OSError, ValueError):
            return {}

    def settings(self) -> dict:
        return {"model": self.model, "token_budget": self.token_budget, "history_turns": self.history_turns,
                "remember_chat": self.remember_chat, "embed_model": self.embed_model,
                "learn_online": self.learn_online, "sleep_when_idle": self.sleep_when_idle,
                "verified_only": self.verified_only, "check_model": self.check_model,
                "trust_learning": self.trust_learning, "route_experts": self.route_experts,
                "vision_model": self.vision_model(),
                "min_similarity": self.engine.min_similarity}

    def warm(self, keep_alive: str = "30m") -> bool:
        """Load the chat model into memory ahead of the first question.

        Ollama loads a model on first use, which dominates the first answer's wait
        (seconds, not milliseconds). An empty prompt loads it without generating.
        """
        if not self.model:
            return False
        # Same options as a chat request: Ollama reloads a model whose context size differs (defect D-10).
        body = self._runner().payload("")
        body["keep_alive"] = keep_alive
        try:
            self._http.post(f"{self.host}/api/generate", json=body, timeout=600)
            return True
        except Exception:  # warming is best-effort; the first question loads the model anyway
            return False

    def save_settings(self, **changes) -> None:
        allowed = {"model", "token_budget", "history_turns", "remember_chat", "learn_online", "sleep_when_idle",
                   "verified_only", "check_model", "trust_learning", "vision_model", "route_experts"}
        for k, v in changes.items():
            if k == "vision_model":
                self.vision = v or ""
            elif k in allowed:
                setattr(self, k, v)
        if "token_budget" in changes:
            self.engine.budgeter.budget = int(self.token_budget)
        data = self.settings()
        data.pop("min_similarity")
        data["vision_model"] = self.vision  # None (pick the first that can see) is kept as such
        self.settings_path.write_text(json.dumps(data, indent=2))

    # ------------------------------------------------------------ teaching
    @_locked
    def teach(self, text: str, title: str = "", kind: str = "note", doc_id: str | None = None) -> int:
        """Store text as memory. Returns the number of notes accepted (0 if it was a duplicate or empty)."""
        text = text.strip()
        if not text:
            return 0
        doc_id = doc_id or f"{kind}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
        st = self.governor.check(upcoming_mb=len(text) * 4 / 1e6)
        if not st.ok:
            raise RuntimeError(f"not stored: this device is at its limit ({st.reason}: {st.detail})")
        # A long text (a book, an export) goes in at once and is searchable by its words straight away; its
        # vectors are added while the assistant is idle (or as questions reach it), so a big file never blocks.
        defer = len(text) > LARGE_TEXT_CHARS
        summary = self.engine.ingest([Document(dataset=kind, doc_id=doc_id, text=text, title=title)],
                                     defer_embedding=defer)
        return summary.accepted

    def teach_file(self, name: str, data: bytes) -> int:
        """Store a text, Markdown or PDF file (PDF needs the optional ``pypdf`` package). Returns notes learned."""
        return self.learn_file(name, data)["notes"]

    def learn_file(self, name: str, data: bytes) -> dict:
        """Learn a file. Teaching a file of the same name again replaces what was learned from it if it changed (an
        edited file used to be skipped as already ingested, so memory kept the old version), and does nothing if it
        did not. Returns {"notes", "replaced" (notes of the old version removed), "unchanged"}."""
        r = self.learn_upload(name, data, study=False)
        return {"notes": r["notes"], "replaced": r["replaced"], "unchanged": r["unchanged"]}

    # ------------------------------------------------------------ uploads: read, learn, interview, highlight
    def learn_upload(self, name: str, data: bytes, conversation_id: int | None = None, study: bool = True) -> dict:
        """Read a file (text, Word, PDF, photo, screenshot: camr/app/reader.py), learn it, and say what was learned
        and what to ask: {"file_id", "name", "kind", "notes", "replaced", "unchanged", "pages", "summary", "chips",
        "questions", "seen", "problem"}. With a conversation, the summary and questions are posted in it."""
        name = Path(name).name or "file"
        stem, doc_id = Path(name).stem, f"file-{name}"
        fid = reader.file_id(data)
        digest = hashlib.sha256(data).hexdigest()
        with self._lock:
            c = self.store.conn
            prev = c.execute("SELECT sha256 FROM app_file WHERE doc_id=?", (doc_id,)).fetchone()
            old = self._file_sources(doc_id)
            if prev and prev[0] == digest and old:
                return {**(self._upload(fid) or {"file_id": fid, "name": name}), "notes": 0, "replaced": 0,
                        "unchanged": True}
            before = [r[0] for r in c.execute("SELECT file_id FROM app_upload WHERE doc_id=?", (doc_id,))]
            kept_expert = self._file_expert(doc_id)  # a new version stays in the expert the user put the old one in
        folder = self.home / "files" / fid
        reading = reader.read(name, data, folder, reader.see_binary(self.home))  # unlocked: recognition takes seconds
        seen = self.describe_image(folder, reading) if reading.kind == "image" else ""
        st = self.governor.check(upcoming_mb=(len(reading.text) + len(seen)) * 4 / 1e6)
        if not st.ok:
            raise RuntimeError(f"not stored: this device is at its limit ({st.reason}: {st.detail})")
        with self._lock:
            # the old version goes first: notes it shares with the new one would otherwise be rejected as duplicates
            replaced = sum(self._delete_source(sid) for sid in old)
            if reading.kind == "code":
                notes = self._teach_code(name, reading.text)
            else:
                notes = self.teach(reading.text, title=stem, kind="file", doc_id=doc_id) if reading.text.strip() else 0
            if seen:
                notes += self.teach(f"{stem}: {seen}", title=f"{stem} (what it shows)", kind="file",
                                    doc_id=f"{doc_id}#seen")
            # code opens with code questions and stays closed to everything else
            expert = kept_expert or ("code" if reading.kind == "code" else None)
            if expert:
                self.store.set_expert(self._file_sources(doc_id), expert)
            with c:
                c.execute("INSERT OR REPLACE INTO app_file(doc_id, sha256, at) VALUES (?, ?, ?)", (doc_id, digest, _now()))
                c.execute("DELETE FROM app_upload WHERE doc_id=?", (doc_id,))
        reading.save(folder)
        for old_fid in set(before) - {fid}:  # the previous version's pages
            shutil.rmtree(self.home / "files" / old_fid, ignore_errors=True)
        info = {"summary": "", "chips": [], "questions": []}
        if study:
            info = self._study(name, reading, seen)
        with self._lock, self.store.conn:
            self.store.conn.execute(
                "INSERT OR REPLACE INTO app_upload(file_id, name, doc_id, kind, page_count, summary, chips_json,"
                " questions_json, seen, problem, at) VALUES (?,?,?,?,?,?,?,?,?,?,?)",
                (fid, name, doc_id, reading.kind, reading.page_count or len(reading.pages), info["summary"],
                 json.dumps(info["chips"]), json.dumps(info["questions"]), seen, reading.problem, _now()))
        out = {**self._upload(fid), "notes": notes, "replaced": replaced, "unchanged": False}
        if conversation_id is not None and study:
            with self._lock, self.store.conn:  # a chat that starts with a file is named after it
                self.store.conn.execute(
                    "UPDATE app_conversation SET title=? WHERE conversation_id=? AND title='New chat' AND NOT EXISTS"
                    " (SELECT 1 FROM app_turn WHERE conversation_id=?)", (f"📎 {name}"[:60], conversation_id,
                                                                          conversation_id))
            turn = Turn(turn_id=None, question=f"📎 {name}", answer=out["summary"], conversation_id=conversation_id,
                        upload=out, saved_to_memory=notes > 0)
            out["turn_id"] = turn.turn_id = self._log(turn)
        return out

    def _teach_code(self, name: str, text: str) -> int:
        """A code file as one note per function or class (whole, so recall returns a function, not 120 tokens of one),
        and a contents note naming what the file defines."""
        units = reader.code_units(name, text)
        lang = reader.LANG.get(Path(name).suffix.lower(), "code")
        named = [sym for sym, _ in units if sym != "module"]
        docs = [Document(dataset="file", doc_id=f"file-{name}", title=name, whole=True,
                         text=f"{name} is a {lang} file" + (f" that defines {', '.join(named[:40])}." if named else "."))]
        docs += [Document(dataset="file", doc_id=f"file-{name}#u{i:03d}", title=f"{name} {sym}", text=src, whole=True)
                 for i, (sym, src) in enumerate(units) if src.strip()]
        return self.engine.ingest(docs).accepted

    # ------------------------------------------------------------ experts (camr.memory.store, MemoryEngine.route)
    def _routed_recall(self, question: str):
        """Recall through the experts: open the one or two a question is about (and shared memory); if that finds
        nothing, look once more in all of memory, so routing never costs an answer. Returns (recall, opened), where
        opened is None when all of memory was read."""
        opened = None
        with self._lock:
            if self.route_experts and self.store.experts():
                opened = [name for name, _ in self.engine.route(question, top=2, margin=0.05)]
                recall = self.engine.recall(question, experts=opened)
                if recall.abstained:  # the experts opened had nothing: the rest of memory gets one look
                    recall, opened = self.engine.recall(question), None
            else:
                recall = self.engine.recall(question)
        return recall, opened

    def _with_file(self, doc_id: str) -> None:
        """What was just learned about a file joins the file's expert."""
        with self._lock:
            expert = self._file_expert(doc_id)
            if expert:
                self.store.set_expert(self._file_sources(doc_id), expert)

    def _file_expert(self, doc_id: str) -> str | None:
        if not self.store.has_experts():
            return None
        row = self.store.conn.execute("SELECT expert FROM source WHERE doc_id=?", (doc_id,)).fetchone()
        return row[0] if row else None

    @_locked
    def experts(self) -> list[dict]:
        """Every expert: its notes, files and a few titles, for the Learning panel."""
        out = []
        for name, notes in self.store.experts().items():
            titles = [r[0] for r in self.store.conn.execute(
                "SELECT DISTINCT title FROM source WHERE expert=? AND title IS NOT NULL AND title != ''"
                " ORDER BY source_id DESC LIMIT 4", (name,))]
            files = self.store.conn.execute("SELECT COUNT(*) FROM app_upload u JOIN source s ON s.doc_id = u.doc_id"
                                            " WHERE s.expert=?", (name,)).fetchone()[0]
            out.append({"name": name, "notes": notes, "files": files, "titles": titles})
        return out

    def set_file_expert(self, fid: str, expert: str | None) -> dict:
        """Put a file (and what was learned about it) in an expert; "" or None returns it to shared memory."""
        expert = expert_name(expert)
        info = self._upload(fid)
        if info is None:
            raise KeyError(f"no file {fid}")
        with self._lock:
            sources = self._file_sources(f"file-{info['name']}")
            self.store.set_expert(sources, expert)
        return {"file_id": fid, "expert": expert, "sources": len(sources)}

    def rename_expert(self, old: str, new: str) -> dict:
        """Rename an expert, or merge it into another one of that name."""
        new_name = expert_name(new)
        if not new_name:
            raise ValueError("an expert needs a name")
        with self._lock:
            ids = [r[0] for r in self.store.conn.execute("SELECT source_id FROM source WHERE expert=?", (old,))]
            self.store.set_expert(ids, new_name)
        return {"expert": new_name, "sources": len(ids)}

    def close_expert(self, name: str) -> dict:
        """Dissolve an expert: its notes return to shared memory (nothing is forgotten)."""
        with self._lock:
            ids = [r[0] for r in self.store.conn.execute("SELECT source_id FROM source WHERE expert=?", (name,))] \
                if self.store.has_experts() else []
            self.store.set_expert(ids, None)
        return {"sources": len(ids)}

    def _file_sources(self, doc_id: str) -> list[int]:
        """A file's sources: its text, and what was learned about it later ("<doc_id>#…")."""
        return [r[0] for r in self.store.conn.execute(
            "SELECT source_id FROM source WHERE dataset='file' AND (doc_id=? OR substr(doc_id, 1, ?) = ?)",
            (doc_id, len(doc_id) + 1, doc_id + "#"))]

    @_locked
    def _upload(self, fid: str) -> dict | None:
        r = self.store.conn.execute(
            "SELECT name, kind, page_count, summary, chips_json, questions_json, seen, problem FROM app_upload WHERE"
            " file_id=?", (fid,)).fetchone()
        if r is None:
            return None
        folder = self.home / "files" / fid
        try:
            pages = [{"index": p.index, "image": p.image, "width": p.width, "height": p.height, "lines": len(p.lines)}
                     for p in reader.Reading.load(folder).pages]
        except (OSError, ValueError, KeyError):
            pages = []
        return {"file_id": fid, "name": r[0], "kind": r[1], "page_count": r[2], "summary": r[3],
                "chips": json.loads(r[4] or "[]"), "questions": json.loads(r[5] or "[]"), "seen": r[6] or "",
                "problem": r[7] or "", "pages": pages, "expert": self._file_expert(f"file-{r[0]}")}

    def vision_model(self) -> str:
        """The installed model that can look at images ("" if none): the one chosen in Settings, else the first
        installed model whose name says it sees (Qwen2.5-VL, Gemma 3, LLaVA, Moondream, …)."""
        if self.vision is not None:
            return self.vision
        at, found = getattr(self, "_vision_auto", (0.0, ""))
        if time.time() - at < 60:  # settings are read on every refresh: ask Ollama at most once a minute
            return found
        try:
            names = [m["name"] for m in installed_models(self.host, session=self._http) if not m["embedding"]]
            found = next((n for n in names if VISION_HINT.search(n)), "")
        except Exception:  # noqa: BLE001  (Ollama not reachable: no vision now; asked again later)
            found = ""
        self._vision_auto = (time.time(), found)
        return found

    def describe_image(self, folder: Path, reading) -> str:
        """What an image shows, in a few short lines, by the vision model, told the text recognised in it (so it
        reads numbers and names rather than guessing them). "" when no vision model is installed."""
        model = self.vision_model()
        page = reading.pages[0] if reading.pages else None
        if not model or page is None or not page.image:
            return ""
        img = base64.b64encode((folder / page.image).read_bytes()).decode()
        ocr = "\n".join(ln["text"] for ln in page.lines)[:2500] or "(no text found)"
        try:
            resp = self._http.post(f"{self.host}/api/generate", json={
                "model": model, "prompt": SEE_PROMPT.format(ocr=ocr), "images": [img], "stream": False,
                "options": {"temperature": 0, "num_ctx": 4096, "num_predict": 300}}, timeout=600)
            resp.raise_for_status()
            return (resp.json().get("response") or "").strip()
        except Exception:  # noqa: BLE001  (the text is still learned; the description is extra)
            return ""

    def _study(self, name: str, reading, seen: str) -> dict:
        """The interview after an upload: a one-line summary, what to focus on, and one or two questions whose
        answers help remember the file correctly (the local model writes them; set questions stand in)."""
        excerpt = ((seen + "\n\n") if seen else "") + reading.text[:3000]
        chips = [] if reading.kind == "code" else reader.focus_chips(reading.text + "\n" + seen)
        summary, questions = "", []
        if self.model and excerpt.strip():
            try:
                out = self._runner().generate(STUDY_PROMPT.format(name=name, excerpt=excerpt)).text
            except Exception:  # noqa: BLE001
                out = ""
            for line in out.splitlines():
                line = line.strip().lstrip("-*• ").strip()
                if line.lower().startswith("summary:") and not summary:
                    summary = line.split(":", 1)[1].strip()
                elif line.lower().startswith("question:"):
                    q = line.split(":", 1)[1].strip()
                    if q.endswith("?") and len(q) < 160 and q not in questions:
                        questions.append(q)
        if not summary:
            first = (seen.splitlines() or [""])[0].strip()
            summary = first or (f"I read {name}: {len(reading.text.split()):,} words"
                                + (f" on {reading.page_count} pages" if reading.page_count > 1 else "") + ".")
        if not questions:
            questions = default_questions(f"{name} {seen} {summary}")
        return {"summary": summary, "chips": chips, "questions": questions[:2]}

    def _reading(self, fid: str):
        if not re.fullmatch(r"[0-9a-f]{16}", fid or ""):
            raise KeyError(f"no file {fid}")
        try:
            return reader.Reading.load(self.home / "files" / fid)
        except OSError as exc:
            raise KeyError(f"no file {fid}") from exc

    def file_info(self, fid: str) -> dict:
        """A file's pages with every recognised line and its box, for the viewer."""
        info, reading = self._upload(fid), self._reading(fid)
        return {**(info or {"file_id": fid, "name": reading.name}),
                "pages": [{"index": p.index, "image": p.image, "width": p.width, "height": p.height,
                           "lines": [{"text": ln["text"], "box": ln["box"]} for ln in p.lines]} for p in reading.pages]}

    def focus(self, fid: str, what: str, conversation_id: int | None = None) -> dict:
        """Learn what the user asked to focus on in a file ("Dates & deadlines", …) as short notes of their own."""
        reading, info = self._reading(fid), self._upload(fid) or {}
        name = info.get("name") or reading.name
        ask = FOCUS.get(what, FOCUS["Key points"])
        text = ((info.get("seen", "") + "\n\n") if info.get("seen") else "") + reading.text[:6000]
        facts = reader.items(reading, what)  # every number, every date: read from the file, none left out
        if not facts and self.model and text.strip():  # people, key points, or a file with none of them
            try:
                out = self._runner().generate(FOCUS_PROMPT.format(what=ask, name=name, text=text)).text
            except Exception:  # noqa: BLE001
                out = ""
            for line in out.splitlines():
                line = re.sub(r"^\s*(?:[-*•]|\d+[.)])\s*", "", line).strip()
                if line and line.lower().rstrip(".") != "none" and len(line) < 300 and line not in facts:
                    facts.append(line)
        notes = 0
        if facts:  # kept with what the file is, so each note can be found and read on its own later
            about = f"From {name}" + (f" ({info['summary'].rstrip('.')})" if info.get("summary") else "") + ":\n"
            notes = self.teach(about + "\n".join(facts), title=f"{Path(name).stem} ({what.lower()})", kind="file",
                               doc_id=f"file-{name}#focus-{re.sub(r'[^a-z]+', '-', what.lower()).strip('-')}")
            self._with_file(f"file-{name}")
        answer = ("\n".join(f"- {f}" for f in facts) if facts else f"I couldn't find {what.lower()} in {name}.")
        out = {"facts": facts, "notes": notes, "focus": what}
        if conversation_id is not None:
            out["turn_id"] = self._log(Turn(turn_id=None, question=f"Focus on {what.lower()} in {name}", answer=answer,
                                            conversation_id=conversation_id, saved_to_memory=notes > 0))
        return out

    def _about_file(self, about: dict, reply: str, conversation_id: int) -> Iterator[dict]:
        """The user's answer to a question asked about a file: kept as a note that belongs to the file."""
        info = self._upload(str(about.get("file_id", ""))) or {}
        name = info.get("name") or "the file"
        q = str(about.get("question", "")).strip()
        with self._lock:
            k = len(self._file_sources(f"file-{name}"))
        what = f" ({info['summary'].rstrip('.')})" if info.get("summary") else ""  # so the note stands on its own
        notes = self.teach(f"About the file {name}{what}: " + (f"asked “{q}”, the user said: " if q else "") + reply,
                           title=f"{Path(name).stem} (what you told me)", kind="file", doc_id=f"file-{name}#told-{k}")
        self._with_file(f"file-{name}")
        answer = f"Got it. I'll remember that with {name}." if notes else "I already had that."
        yield {"type": "recall", "sources": [], "abstained": False, "retrieval_ms": 0.0, "small_talk": True,
               "conversation_id": conversation_id, "learned": None}
        yield {"type": "token", "text": answer}
        turn = Turn(turn_id=None, question=reply, answer=answer, conversation_id=conversation_id,
                    saved_to_memory=notes > 0)
        turn.turn_id = self._log(turn)
        yield {"type": "done", "turn": turn.as_dict()}

    def select(self, fid: str, page: int, box: list[float], teach: bool = False) -> dict:
        """The lines inside a box drawn on a page; with ``teach``, learned as a note of their own."""
        reading = self._reading(fid)
        lines = reader.lines_within(reading, int(page), [float(v) for v in box][:4])
        text = reader.row_text(lines)
        notes = 0
        if teach and text.strip():
            with self._lock:
                k = len(self._file_sources(f"file-{reading.name}"))
            notes = self.teach(text, title=f"{Path(reading.name).stem} (part you chose)", kind="file",
                               doc_id=f"file-{reading.name}#part-{k}")
            self._with_file(f"file-{reading.name}")
        return {"text": text, "lines": lines, "notes": notes}

    @_locked
    def highlight(self, note_id: int) -> dict:
        """Where a note came from in its file: the file, and the boxes of the lines the note holds."""
        row = self.store.conn.execute("SELECT n.text, s.doc_id FROM note n JOIN source s USING(source_id) WHERE"
                                      " n.note_id=? AND s.dataset='file'", (int(note_id),)).fetchone()
        if row is None:
            raise KeyError(f"note {note_id} is not from a file")
        text, doc_id = row
        up = self.store.conn.execute("SELECT file_id FROM app_upload WHERE doc_id=?",
                                     (doc_id.split("#", 1)[0],)).fetchone()
        if up is None:
            raise KeyError(f"the file of note {note_id} has no pages")
        reading = self._reading(up[0])
        return {"file_id": up[0], "name": reading.name, "boxes": reader.lines_in(reading, text)}

    @_locked
    def forget(self, source_id: int) -> int:
        with self.store.conn:  # a forgotten file is learned afresh if it is taught again
            self.store.conn.execute("DELETE FROM app_file WHERE doc_id IN (SELECT doc_id FROM source WHERE"
                                    " source_id=? AND dataset='file')", (source_id,))
        row = self.store.conn.execute("SELECT dataset, doc_id FROM source WHERE source_id=?", (source_id,)).fetchone()
        removed = self._delete_source(source_id)
        if row and row[0] == "file" and "#" not in (row[1] or ""):
            # a file: also what was learned about it later, and its pages
            removed += sum(self._delete_source(sid) for sid in self._file_sources(row[1]))
            for (fid,) in self.store.conn.execute("SELECT file_id FROM app_upload WHERE doc_id=?", (row[1],)).fetchall():
                shutil.rmtree(self.home / "files" / fid, ignore_errors=True)
            with self.store.conn:
                self.store.conn.execute("DELETE FROM app_upload WHERE doc_id=?", (row[1],))
        if removed and not self._fts_secure:
            with self.store.conn:  # merge the keyword index so the deleted words leave it (and its pages are wiped)
                self.store.conn.execute("INSERT INTO note_fts(note_fts) VALUES ('optimize')")
        return removed

    def _delete_source(self, source_id: int) -> int:
        """Delete a source and the profile notes taken from it ("profile:<dataset>:<doc_id>:<i>")."""
        row = self.store.conn.execute("SELECT dataset, doc_id FROM source WHERE source_id=?", (source_id,)).fetchone()
        derived = []
        if row:
            prefix = f"profile:{row[0]}:{row[1]}:"
            derived = [r[0] for r in self.store.conn.execute(
                "SELECT source_id FROM source WHERE dataset='profile' AND substr(doc_id, 1, ?) = ?",
                (len(prefix), prefix))]
        return self.store.delete_source(source_id) + sum(self.store.delete_source(d) for d in derived)

    def today(self) -> dt.date:
        """Today on the user's calendar (the engine's clock, in local time)."""
        return self.engine.clock.now().astimezone().date()

    # ------------------------------------------------------------ conversations
    @_locked
    def conversations(self, limit: int = 100) -> list[dict]:
        rows = self.store.conn.execute(
            "SELECT conversation_id, title, updated_at FROM app_conversation ORDER BY updated_at DESC LIMIT ?",
            (limit,)).fetchall()
        return [{"id": r[0], "title": r[1], "updated_at": r[2]} for r in rows]

    @_locked
    def new_conversation(self, title: str = "New chat") -> int:
        with self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO app_conversation(title, created_at, updated_at) VALUES (?,?,?)", (title, _now(), _now()))
        return int(cur.lastrowid)

    @_locked
    def rename_conversation(self, conversation_id: int, title: str) -> None:
        with self.store.conn:
            self.store.conn.execute("UPDATE app_conversation SET title=? WHERE conversation_id=?",
                                    (title.strip()[:80] or "Untitled", conversation_id))

    @_locked
    def delete_conversation(self, conversation_id: int) -> None:
        """Delete the transcript. What was learned from it stays in memory (forget it there)."""
        with self.store.conn:
            self.store.conn.execute("DELETE FROM app_turn WHERE conversation_id=?", (conversation_id,))
            self.store.conn.execute("DELETE FROM app_conversation WHERE conversation_id=?", (conversation_id,))

    @_locked
    def transcript(self, conversation_id: int) -> list[dict]:
        rows = self.store.conn.execute(
            "SELECT turn_id, question, answer, notes_used, abstained, grounded, retrieval_ms, generation_ms,"
            " prompt_tokens, feedback, sources_json, learned_json, ask_to_teach, verification_json, link_json,"
            " skill_json, upload_json, experts_json, check_json FROM app_turn WHERE conversation_id=? ORDER BY turn_id",
            (conversation_id,)).fetchall()
        return [Turn(turn_id=r[0], question=r[1], answer=r[2], abstained=bool(r[4]), grounded=r[5],
                     retrieval_ms=r[6] or 0.0, generation_ms=r[7] or 0.0, prompt_tokens=r[8], feedback=r[9],
                     conversation_id=conversation_id, learned=json.loads(r[11]) if r[11] else None,
                     ask_to_teach=bool(r[12]), verification=json.loads(r[13]) if r[13] else None,
                     link=json.loads(r[14]) if r[14] else None, skill=json.loads(r[15]) if r[15] else None,
                     upload=json.loads(r[16]) if r[16] else None, experts=json.loads(r[17]) if r[17] else None,
                     check=json.loads(r[18]) if r[18] else None,
                     sources=[Source(**s) for s in json.loads(r[10] or "[]")]).as_dict() for r in rows]

    # ------------------------------------------------------------ asking
    @_locked
    def _history(self, conversation_id: int | None = None) -> str:
        if conversation_id is None:
            rows = self.store.conn.execute("SELECT question, answer FROM app_turn ORDER BY turn_id DESC LIMIT ?",
                                           (self.history_turns,)).fetchall()
        else:
            rows = self.store.conn.execute(
                "SELECT question, answer FROM app_turn WHERE conversation_id=? ORDER BY turn_id DESC LIMIT ?",
                (conversation_id, self.history_turns)).fetchall()
        return "\n".join(f"User: {q}\nAssistant: {a}" for q, a in reversed(rows)) or "(none)"

    _SAID = re.compile(r"^On \d{4}-\d{2}-\d{2} the user said: (.*)$", re.S)

    @_locked
    def _tidy_requests(self) -> int:
        """Chat memories that were never knowledge: small talk ("hi") and coding requests that earlier versions kept
        as something the user said, where they crowded real memories out of recall. Only chat memories whose whole
        text is such a message are removed; everything the user stated stays."""
        gone = 0
        for sid, text in self.store.conn.execute(
                "SELECT s.source_id, n.text FROM source s JOIN note n USING(source_id) WHERE s.dataset='chat'").fetchall():
            m = self._SAID.match(text or "")
            if m and (is_small_talk(m.group(1)) or is_code_request(m.group(1))):
                gone += self._delete_source(sid)
        return gone

    def save_fix(self, turn_id: int, code: str, block: int = 0) -> dict:
        """The user's corrected version of a code answer, kept as a correction for that request: the next similar
        request reads it. Kept in the expert the request opened (else "code"), titled "Correction: <expert>" (the
        name a code skill card of that expert would be attached by). A second fix of the same answer replaces the
        first. Returns {"notes", "expert", "check"}."""
        code = (code or "").strip("\n")
        if not code.strip():
            raise ValueError("an empty fix")
        with self._lock:
            row = self.store.conn.execute("SELECT question, answer, experts_json FROM app_turn WHERE turn_id=?",
                                          (int(turn_id),)).fetchone()
        if row is None:
            raise KeyError(f"no answer {turn_id}")
        question, answer, experts_json = row
        found = codecheck.blocks(answer)
        lang = found[block][0] if block < len(found) else (found[0][0] if found else "")
        expert = (json.loads(experts_json)[0] if experts_json and json.loads(experts_json) else None) or "code"
        doc_id = f"fix-{int(turn_id)}"
        with self._lock:
            for (sid,) in self.store.conn.execute("SELECT source_id FROM source WHERE doc_id=?", (doc_id,)).fetchall():
                self._delete_source(sid)
            notes = self.engine.ingest([Document(dataset="fix", doc_id=doc_id, title=f"Correction: {expert}", whole=True,
                                                 text=f"Correction for the request \u201c{question}\u201d:\n```{lang}\n"
                                                      f"{code}\n```")]).accepted
            ids = [r[0] for r in self.store.conn.execute("SELECT source_id FROM source WHERE doc_id=?", (doc_id,))]
            self.store.set_expert(ids, expert)
            with self.store.conn:
                self.store.conn.execute("UPDATE app_turn SET feedback=-1 WHERE turn_id=?", (int(turn_id),))
        return {"notes": notes, "expert": expert, "check": codecheck.check(lang, code)}

    @_locked
    def _after_code(self, conversation_id: int | None) -> bool:
        """The chat's last answer was code: a follow-up ("now make it handle invalid dates") is about that code."""
        if conversation_id is None:
            return False
        row = self.store.conn.execute("SELECT answer FROM app_turn WHERE conversation_id=? ORDER BY turn_id DESC LIMIT 1",
                                      (conversation_id,)).fetchone()
        return bool(row and "```" in (row[0] or ""))

    @_locked
    def _sources(self, recall) -> list[Source]:
        admitted = recall.admitted
        ids = [c.note.source_id for c in admitted]
        meta = {}
        if ids:
            q = f"SELECT source_id, dataset, title, doc_id FROM source WHERE source_id IN ({','.join('?' * len(ids))})"
            meta = {r[0]: (r[1], r[2] or "", r[3] or "") for r in self.store.conn.execute(q, ids)}
        out = []
        for c in admitted:
            kind, title, doc = meta.get(c.note.source_id, ("note", "", ""))
            out.append(Source(note_id=c.note.note_id, kind="pack" if kind.startswith("pack:") else kind, title=title,
                              text=c.note.text, similarity=round(c.similarity, 3), via_bridge=c.via is not None,
                              url=doc if doc.startswith("http") else ""))
        return out

    def _runner(self) -> OllamaRunner:
        return OllamaRunner(LocalModelConfig(name=self.model, host=self.host, max_tokens=768, num_ctx=4096),
                            session=self._http)

    def _stream_generate(self, prompt: str, model: str | None = None, long: bool = False) -> Iterator[tuple[str, dict]]:
        if not self.model:
            raise RuntimeError("choose a model first")
        body = self._runner().payload(prompt)
        if long:  # code: a whole file's worth of answer, and the notes and history beside it
            body.setdefault("options", {}).update(num_predict=CODE_ANSWER_TOKENS, num_ctx=CODE_CONTEXT)
        if model:  # a skill card: the base model with the card's adapter, registered with Ollama
            body["model"] = model
        body["stream"] = True
        with self._http.post(f"{self.host}/api/generate", json=body, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                if chunk.get("error"):
                    raise RuntimeError(chunk["error"])
                yield chunk.get("response", ""), chunk

    def events(self, question: str, conversation_id: int | None = None, about: dict | None = None) -> Iterator[dict]:
        """The answer as a stream of events: recall (what memory was read), token…, done (the Turn)."""
        question = question.strip()
        if not question:
            raise ValueError("empty message: type a question, or start with 'remember that'")
        if conversation_id is None:
            conversation_id = self.new_conversation(question[:60] or "New chat")
        else:
            with self._lock, self.store.conn:
                n = self.store.conn.execute("SELECT COUNT(*) FROM app_turn WHERE conversation_id=?",
                                            (conversation_id,)).fetchone()[0]
                if n == 0:  # first message names the chat, like ChatGPT
                    self.store.conn.execute("UPDATE app_conversation SET title=? WHERE conversation_id=? AND"
                                            " title='New chat'", (question[:60], conversation_id))
        m = _REMEMBER.match(question)
        if m:  # an explicit "remember ..." is stored directly, with no model call
            saved = self.teach(m.group(1), kind="note") > 0
            msg = "Got it. I'll remember that." if saved else "I already had that in memory."
            turn = Turn(turn_id=None, question=question, answer=msg, saved_to_memory=saved,
                        conversation_id=conversation_id)
            turn.turn_id = self._log(turn)
            yield {"type": "recall", "sources": [], "abstained": False, "conversation_id": conversation_id}
            yield {"type": "token", "text": msg}
            yield {"type": "done", "turn": turn.as_dict()}
            return

        if about and about.get("file_id"):  # an answer to a question asked about a file
            yield from self._about_file(about, question, conversation_id)
            return
        if is_small_talk(question):
            yield from self._small_talk(question, conversation_id)
            return
        coding = is_code_request(question) or (self._after_code(conversation_id) and not is_about_user(question))
        recall, opened = self._routed_recall(question)
        learned = None
        personal = is_about_user(question)
        local_only = personal or bool(self._private_names(question))  # nothing about it is sent online
        # Eager learning: memory has nothing on this, or only notes that look similar but are about something else
        # (results/verified, subject-aware lookups: +3.5 points of verified answers on the development set)
        missing = recall.abstained or (_short_factual(question) and not knows_subject(self.engine, question, recall))
        if missing and self.learn_online and not local_only and not coding and worth_looking_up(question):
            yield {"type": "lookup", "conversation_id": conversation_id}
            found = self.lookup.lookup(question)
            added = 0
            if found.pages:
                with self._lock:
                    added = learn_pages(self.engine, found.pages)
                    learn_meanings(self.engine, found.meanings)
                recall, opened = self._routed_recall(question)
            learned = {"queries": found.queries, "notes_added": added, "ms": round(found.ms, 1),
                       "pages": [{"title": p.title, "url": p.url, "source": p.source} for p in found.pages],
                       "errors": found.errors}
            self._log_lookup(question, found, added)
        sources = self._sources(recall)
        yield {"type": "recall", "sources": [asdict(s) for s in sources], "abstained": recall.abstained,
               "retrieval_ms": round(recall.retrieval_ms, 1), "conversation_id": conversation_id, "learned": learned,
               "experts": opened}
        factual = _short_factual(question) and not personal and not coding
        units = []
        if factual and not recall.abstained:
            with self._lock:
                units = units_from_notes(self.store, [c.note for c in recall.candidates if c.eligible])
                if units:
                    units += meaning_units(self.store, question)
        fact = fact_answer(question, units) if units else None
        if fact is not None:
            # memory holds the fact as a labelled line about the question's subject: answered from memory, at once
            answer = fact.text.rstrip(".") + "."
            if len(fact.ambiguous) > 1 and fact.claim == fact.text:  # several things share the name: each of them
                answer = "That name means more than one thing. " + answer
            yield {"type": "token", "text": answer}
            turn = Turn(turn_id=None, question=question, answer=answer, sources=sources, grounded=1.0,
                        retrieval_ms=round(recall.retrieval_ms, 1), conversation_id=conversation_id, learned=learned,
                        verification={"status": "verified", "by": "memory", "evidence": fact.evidence,
                                      "source": fact.source, "ambiguous": fact.ambiguous})
            turn.turn_id = self._log(turn)
            self.last_activity = time.time()
            yield {"type": "done", "turn": turn.as_dict()}
            return
        prompt = CHAT_PROMPT.format(today=self.today().isoformat(), notes=recall.context or "(no relevant notes)",
                                    history=self._history(conversation_id), question=question)
        card = None if coding else self._card_for(recall)
        if coding:  # the user's code and conventions as notes, and room for a whole answer
            prompt = CODE_PROMPT.format(notes=recall.context or "(no relevant notes)",
                                        history=self._history(conversation_id), question=question)
        if card:  # memory names a skill card: it answers the way it was trained (formula, then an expression)
            yield {"type": "skill", "skill": card["skill"], "model": card["model"]}
            prompt = CALC_BARE.format(question=question)
        t0, parts, last, first = time.perf_counter(), [], {}, None
        for piece, chunk in self._stream_generate(prompt, model=card["model"] if card else None, long=coding):
            parts.append(piece)
            last = chunk
            if piece:
                if first is None:
                    first = round((time.perf_counter() - t0) * 1000, 1)
                yield {"type": "token", "text": piece}
        answer = "".join(parts).strip()
        check = None
        if coding:  # its syntax, checked here (nothing is run); one retry with the error message
            check = codecheck.check_answer(answer)
            if check and not check["ok"]:
                yield {"type": "fixing", "error": check["error"], "line": check["line"]}
                retry = (prompt + answer + f"\n\n### User\nYour code has a syntax error: {check['error']}"
                         + (f" (line {check['line']})" if check["line"] else "")
                         + ". Write the corrected complete code.\n\n### Assistant\n")
                fixed = "".join(piece for piece, _ in self._stream_generate(retry, long=True)).strip()
                second = codecheck.check_answer(fixed)
                if fixed and second and second["ok"]:
                    check = {**second, "retried": True, "first_error": check["error"]}
                    answer = fixed
                else:
                    check = {**check, "retried": True}
        skill = None
        if card:  # the calculator does the arithmetic, as the experiment measured
            answer, calc = tiers.card_answer(answer, question)
            skill = {"skill": card["skill"], "model": card["model"], **calc}
        verification = None
        if factual and not card:
            verification = _verification(question, answer, units)
            if verification["status"] != "verified" and claim(answer) and verification.get("reason") != "no answer given":
                better = self._second_opinion(question, answer, units, online=not local_only)
                if better is not None:
                    answer, verification = better
            if self.verified_only and verification["status"] != "verified" and claim(answer):
                answer = (f"I couldn't confirm this from what I've read, so take it as a lead, not a fact: "
                          f"{claim(answer)} (unverified).")
        link = None
        if self.trust_learning and not card and not coding and (verification or {}).get("status") != "verified":
            row = {"question": question, "abstained": recall.abstained, "top_similarity": recall.top_similarity or 0.0,
                   "admitted": len(recall.admitted), "context_tokens": recall.context_tokens,
                   "grounded": grounded_share(answer, recall.context) or 0.0, "declined": model_declined(answer)}
            # a short factual answer has had its second opinion already, used only if memory confirmed it: the
            # link may hold it back but not escalate it again around that check
            link = self._trust(row, escalate=not factual)
            if link["action"] == "decline":
                link["draft"], answer = answer, tiers.DECLINE_PERSONAL if personal else tiers.DECLINE_GENERAL
            elif link["action"] == "escalate":
                yield {"type": "escalate", "by": self.check_model}
                other = self._ask_second(prompt)
                if other:
                    link.update(draft=answer, by=self.check_model)
                    answer = other
                else:  # the second model did not answer: the local answer stands
                    link.update(action="keep", failed=f"{self.check_model} did not answer")
        turn = Turn(turn_id=None, question=question, answer=answer, sources=sources, abstained=recall.abstained,
                    grounded=grounded_share(answer, recall.context), retrieval_ms=round(recall.retrieval_ms, 1),
                    generation_ms=round((time.perf_counter() - t0) * 1000, 1), first_token_ms=first,
                    prompt_tokens=last.get("prompt_eval_count"), conversation_id=conversation_id, learned=learned,
                    ask_to_teach=(recall.abstained or (link or {}).get("action") == "decline") and personal,
                    verification=verification, link=link, skill=skill, experts=opened, check=check)
        turn.turn_id = self._log(turn)
        self.last_activity = time.time()
        if self.remember_chat and not is_question(question) and not coding:
            # What the user *states* is the user's own knowledge: keep it, so it can be
            # recalled long after it has scrolled out of the context window. Questions are
            # not kept: they carry no knowledge and only crowd out real memories (D-14).
            day = self.today().isoformat()
            turn.saved_to_memory = self.teach(f"On {day} the user said: {question}", kind="chat",
                                              doc_id=f"chat-{turn.turn_id}") > 0
        yield {"type": "done", "turn": turn.as_dict()}

    def _small_talk(self, question: str, conversation_id: int) -> Iterator[dict]:
        """Answered from the conversation so far: memory is not read, nothing is looked up, nothing is kept."""
        yield {"type": "recall", "sources": [], "abstained": False, "retrieval_ms": 0.0, "small_talk": True,
               "conversation_id": conversation_id, "learned": None}
        prompt = CHAT_PROMPT.format(today=self.today().isoformat(), notes="(none needed: this is small talk)",
                                    history=self._history(conversation_id), question=question)
        t0, parts, last, first = time.perf_counter(), [], {}, None
        for piece, chunk in self._stream_generate(prompt):
            parts.append(piece)
            last = chunk
            if piece:
                if first is None:
                    first = round((time.perf_counter() - t0) * 1000, 1)
                yield {"type": "token", "text": piece}
        turn = Turn(turn_id=None, question=question, answer="".join(parts).strip(), conversation_id=conversation_id,
                    generation_ms=round((time.perf_counter() - t0) * 1000, 1), first_token_ms=first,
                    prompt_tokens=last.get("prompt_eval_count"))
        turn.turn_id = self._log(turn)
        self.last_activity = time.time()
        yield {"type": "done", "turn": turn.as_dict()}

    def _second_opinion(self, question: str, answer: str, units, online: bool = True) -> tuple[str, dict] | None:
        """An unconfirmed short answer: ask the second-opinion model (if set) to read the same memory, and check
        each claim from the answer's own article (if lookups are on and ``online``: never for a question that must
        stay on this machine). Only a confirmed claim replaces the answer."""
        claims = [answer]
        if self.check_model and self.check_model != self.model:
            runner = OllamaRunner(LocalModelConfig(name=self.check_model, host=self.host, max_tokens=64,
                                                   num_ctx=4096), session=self._http)
            if units:
                shown = compress(question, units, self.embedder, RegexTokenizer(), budget=160)
                prompt = READ_PROMPT.render(question, "\n".join(u.render() for u in shown))
            else:
                prompt = BARE_PROMPT.render(question)
            try:
                other = runner.generate(prompt).text.strip()
            except Exception:  # noqa: BLE001  (a missing or failing second model is no answer, not an error)
                other = ""
            if other and claim(other):
                v = check(question, other, units) if units else None
                if v is not None and v.supported:
                    return claim(other), {"status": "verified", "by": self.check_model, "evidence": v.evidence.render(),
                                          "source": v.evidence.title, "revised_from": claim(answer)}
                claims.append(other)
        rel = relation_of(question)
        if self.learn_online and online and rel and rel[0] in CROSS:
            for c in claims:
                with self._lock:
                    v, page = cross_verify(self.engine, self.lookup, question, c)
                if v.supported:
                    out = {"status": "verified", "by": "cross-check", "evidence": v.evidence.render(),
                           "source": v.evidence.title, "url": page.url if page else ""}
                    if claim(c) != claim(answer):
                        out["revised_from"] = claim(answer)
                    return claim(c), out
        return None

    # ------------------------------------------------------------ the link and skill cards (tiers.py)
    def _can_escalate(self) -> bool:
        return bool(self.check_model) and self.check_model != self.model

    def _link_for(self, model: str) -> tuple[Link, dict]:
        """This model's link: the one it has learned on this machine, else the bench link for the nearest size
        (a fresh copy, learned on from here), else an untrained link (states every answer)."""
        if model in self._links:
            return self._links[model]
        own = self.home / "links" / f"{re.sub(r'[^A-Za-z0-9.]+', '-', model)}.json"
        link, meta = None, {}
        if own.exists():
            try:
                link, meta = Link.load(own)
            except (OSError, ValueError, KeyError):
                link = None
        if link is None:
            size = None
            try:
                size = next((tiers.params_b(m["parameters"]) for m in installed_models(self.host, session=self._http)
                             if m["name"] == model), None)
            except Exception:  # noqa: BLE001  (no size known: match by name)
                pass
            prior = tiers.prior_for(model, size)
            if prior is not None:
                link, pm = Link.load(prior["path"])
                meta = {"start": f"reader bench, {pm.get('reader')}", "feedback": 0}
            else:
                link, meta = Link(), {"start": "untrained", "feedback": 0}
        self._links[model] = (link, meta)
        return link, meta

    def _trust(self, row: dict, escalate: bool = True) -> dict:
        """What the link does with this answer: keep, decline, or escalate (only with a second-opinion model)."""
        link, meta = self._link_for(self.model)
        allowed = ["keep", "decline"] + (["escalate"] if escalate and self._can_escalate() else [])
        return {"action": link.act(row, allowed), "values": link.values(row), "row": row, "model": self.model,
                "start": meta.get("start")}

    def _ask_second(self, prompt: str) -> str:
        """The same prompt (same notes) to the second-opinion model. On this machine: nothing is sent online."""
        runner = OllamaRunner(LocalModelConfig(name=self.check_model, host=self.host, max_tokens=768, num_ctx=4096),
                              session=self._http)
        try:
            return runner.generate(prompt).text.strip()
        except Exception:  # noqa: BLE001  (a missing or failing second model is no answer, not an error)
            return ""

    def _learn_trust(self, link_info: dict, helpful: bool, answer: str) -> None:
        """A thumb on an answer the link decided: one update of that model's link, saved on this machine."""
        model, action, row = link_info.get("model"), link_info.get("action"), link_info.get("row")
        if not model or action not in ("keep", "decline", "escalate") or not row:
            return
        link, meta = self._link_for(model)
        link.update(row, action, tiers.link_reward(action, helpful, model_declined(answer)))
        meta["feedback"] = int(meta.get("feedback", 0)) + 1
        link.save(self.home / "links" / f"{re.sub(r'[^A-Za-z0-9.]+', '-', model)}.json", **meta)

    @_locked
    def _card_for(self, recall) -> dict | None:
        """The skill card memory names for this question: the best admitted note (profile notes aside) is a
        correction of a skill whose card was trained for the model answering (camr/memory/skills.py)."""
        if recall.abstained:
            return None
        ranked = [c for c in recall.admitted if getattr(c, "lane", None) != "profile"]
        if not ranked:
            return None
        cards = {r[0]: r[1] for r in self.store.conn.execute("SELECT skill, model FROM app_card WHERE base=?",
                                                             (self.model,))}
        if not cards:
            return None
        title = self.store.note_titles([ranked[0].note.note_id]).get(ranked[0].note.note_id)
        skill = skill_of(title, tiers.CARD_PREFIX)
        return {"skill": skill, "model": cards[skill]} if skill in cards else None

    def card_packs(self) -> list[dict]:
        """Card packs on disk, with whether each is installed and for which model."""
        with self._lock:
            have = {r[0] for r in self.store.conn.execute("SELECT DISTINCT pack FROM app_card")}
        return [{"name": m["name"], "title": m["title"], "base": m["base"], "description": m.get("description", ""),
                 "skills": [c["skill"] for c in m["cards"]], "installed": m["name"] in have,
                 "usable": m["base"] == self.model} for m in tiers.card_packs(self.home)]

    def install_card_pack(self, name: str) -> dict:
        """Register each card with Ollama (the base model plus its adapter) and teach the corrections that name it."""
        man = next((m for m in tiers.card_packs(self.home) if m["name"] == name), None)
        if man is None:
            raise FileNotFoundError(f"no card pack named {name!r}")
        made = []
        for card in man["cards"]:
            path = man["folder"] / card["adapter"]
            digest = "sha256:" + tiers.sha256_file(path)
            if self._http.head(f"{self.host}/api/blobs/{digest}", timeout=30).status_code != 200:
                with open(path, "rb") as fh:
                    self._http.post(f"{self.host}/api/blobs/{digest}", data=fh, timeout=600).raise_for_status()
            resp = self._http.post(f"{self.host}/api/create", json={
                "model": card["model"], "from": man["base"], "adapters": {card["adapter"]: digest}, "stream": False},
                timeout=600)
            resp.raise_for_status()
            made.append(card["model"])
        notes = 0
        for i, n in enumerate(man["notes"]):
            notes += self.teach(n["text"], title=n["title"], kind="card", doc_id=f"card-{name}-{i}")
        with self._lock, self.store.conn:
            for card in man["cards"]:
                self.store.conn.execute("INSERT OR REPLACE INTO app_card(pack, skill, model, base, at) VALUES"
                                        " (?,?,?,?,?)", (name, card["skill"], card["model"], man["base"], _now()))
        return {"cards": len(made), "notes": notes, "base": man["base"]}

    def remove_card_pack(self, name: str) -> dict:
        """Remove a pack's cards from Ollama and its corrections from memory."""
        with self._lock:
            models = [r[0] for r in self.store.conn.execute("SELECT model FROM app_card WHERE pack=?", (name,))]
            sids = [r[0] for r in self.store.conn.execute(
                "SELECT source_id FROM source WHERE dataset='card' AND substr(doc_id, 1, ?) = ?",
                (len(f"card-{name}-"), f"card-{name}-"))]
        for m in models:
            try:
                self._http.delete(f"{self.host}/api/delete", json={"model": m}, timeout=60)
            except Exception:  # noqa: BLE001  (already gone from Ollama: nothing to remove)
                pass
        with self._lock:
            removed = sum(self._delete_source(sid) for sid in sids)
            with self.store.conn:
                self.store.conn.execute("DELETE FROM app_card WHERE pack=?", (name,))
        return {"cards": len(models), "notes": removed}

    def trust(self) -> dict:
        """The link for the current model, for the Learning panel: where it started, feedback learned, decisions."""
        if not self.model:
            return {}
        _, meta = self._link_for(self.model)
        with self._lock:
            rows = self.store.conn.execute("SELECT link_json FROM app_turn WHERE model=? AND link_json IS NOT NULL",
                                           (self.model,)).fetchall()
        acts = [json.loads(r[0]).get("action") for r in rows]
        return {"model": self.model, "on": self.trust_learning, "start": meta.get("start"),
                "feedback": int(meta.get("feedback", 0)), "escalate_to": self.check_model if self._can_escalate() else "",
                "decisions": {a: acts.count(a) for a in ("keep", "decline", "escalate")}}

    @_locked
    def _private_names(self, question: str) -> list[str]:
        """Names in the question that only the user's own notes, files, chats or approved answers mention, and no
        looked-up page or pack does: someone or something the user knows. They are never sent online."""
        out = []
        for name in subjects(question):
            if not name[:1].isupper():
                continue
            try:
                kinds = {r[0] for r in self.store.conn.execute(
                    "SELECT DISTINCT s.dataset FROM note_fts f JOIN note n ON n.note_id = f.rowid"
                    " JOIN source s USING(source_id) WHERE note_fts MATCH ?", ('"' + name.replace('"', '""') + '"',))}
            except sqlite3.OperationalError:
                kinds = set(PRIVATE_KINDS)  # cannot tell: keep it on this machine
            if kinds & set(PRIVATE_KINDS) and not any(k == "web" or k.startswith("pack:") for k in kinds):
                out.append(name)
        return out

    @_locked
    def _log(self, turn: Turn) -> int:
        with self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO app_turn(at, model, question, answer, notes_used, abstained, grounded, retrieval_ms,"
                " generation_ms, prompt_tokens, conversation_id, sources_json, learned_json, ask_to_teach,"
                " verification_json, link_json, skill_json, upload_json, experts_json, check_json)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_now(), self.model or "-", turn.question, turn.answer, len(turn.sources), int(turn.abstained),
                 turn.grounded, turn.retrieval_ms, turn.generation_ms, turn.prompt_tokens, turn.conversation_id,
                 json.dumps([asdict(s) for s in turn.sources]), json.dumps(turn.learned) if turn.learned else None,
                 int(turn.ask_to_teach), json.dumps(turn.verification) if turn.verification else None,
                 json.dumps(turn.link) if turn.link else None, json.dumps(turn.skill) if turn.skill else None,
                 json.dumps(turn.upload) if turn.upload else None, json.dumps(turn.experts) if turn.experts else None,
                 json.dumps(turn.check) if turn.check else None))
            if turn.conversation_id is not None:
                self.store.conn.execute("UPDATE app_conversation SET updated_at=? WHERE conversation_id=?",
                                        (_now(), turn.conversation_id))
        return int(cur.lastrowid)

    def ask_stream(self, question: str, conversation_id: int | None = None) -> Iterator[str | Turn]:
        """Yield answer text as it is generated, then the finished Turn."""
        for ev in self.events(question, conversation_id):
            if ev["type"] == "token":
                yield ev["text"]
            elif ev["type"] == "done":
                t = ev["turn"]
                t["sources"] = [Source(**s) for s in t["sources"]]
                yield Turn(**t)

    def ask(self, question: str, conversation_id: int | None = None) -> Turn:
        out = None
        for item in self.ask_stream(question, conversation_id):
            out = item
        return out  # type: ignore[return-value]

    # ------------------------------------------------------------ feedback
    @_locked
    def feedback(self, turn_id: int, helpful: bool) -> dict:
        """Thumbs up stores the approved answer as memory: the model gets better without changing weights. Thumbs
        down takes back an approval given before (a wrong answer approved by mistake used to stay in memory).
        Returns {"learned": notes added, "forgotten": notes removed}."""
        row = self.store.conn.execute("SELECT question, answer, link_json, feedback FROM app_turn WHERE turn_id=?",
                                      (turn_id,)).fetchone()
        if row is None:
            raise KeyError(f"no answer {turn_id}")
        with self.store.conn:
            self.store.conn.execute("UPDATE app_turn SET feedback=? WHERE turn_id=?", (1 if helpful else -1, turn_id))
        q, a, link_json, before = row
        if link_json and before != (1 if helpful else -1):  # one lesson per thumb (a repeated click teaches nothing)
            self._learn_trust(json.loads(link_json), helpful, a)
        if helpful:
            if model_declined(a) or is_small_talk(q):  # right, but nothing to remember: "I don't know", or "hi"
                return {"learned": 0, "forgotten": 0}
            return {"learned": self.teach(f"Q: {q}\nA: {a}", kind="learned", doc_id=f"learned-{turn_id}"),
                    "forgotten": 0}
        approved = self.store.conn.execute("SELECT source_id FROM source WHERE dataset='learned' AND doc_id=?",
                                           (f"learned-{turn_id}",)).fetchall()
        return {"learned": 0, "forgotten": sum(self._delete_source(r[0]) for r in approved)}

    # ------------------------------------------------------------ learning: lookups, packs, sleep
    @_locked
    def _log_lookup(self, question: str, found, added: int) -> None:
        with self.store.conn:
            self.store.conn.execute(
                "INSERT INTO app_lookup(at, question, queries, pages_json, notes_added, ms) VALUES (?,?,?,?,?,?)",
                (_now(), question, json.dumps(found.queries), json.dumps(
                    [{"title": p.title, "url": p.url} for p in found.pages]), added, found.ms))

    def available_packs(self) -> list[dict]:
        """Packs on disk (bundled with the app, or harvested by the user), with whether each is installed."""
        installed = {p["name"]: p for p in self.installed_packs()}
        out = []
        for folder in (BUNDLED_PACKS, self.packs_dir):
            for f in sorted(folder.glob("*.camrpack")) if folder.exists() else []:
                try:
                    man, _, _ = packs_mod.read_pack(f)
                except (OSError, ValueError, KeyError):
                    continue
                out.append({"name": man.name, "title": man.title, "description": man.description, "notes": man.notes,
                            "licence": man.licence, "embedder": man.embedder, "file": f.name,
                            "bundled": folder == BUNDLED_PACKS, "installed": man.name in installed})
        return out

    @_locked
    def installed_packs(self) -> list[dict]:
        return packs_mod.installed_packs(self.engine)

    def _pack_file(self, name: str) -> Path:
        for folder in (self.packs_dir, BUNDLED_PACKS):
            for f in folder.glob("*.camrpack") if folder.exists() else []:
                try:
                    if packs_mod.read_pack(f)[0].name == name:
                        return f
                except (OSError, ValueError, KeyError):
                    continue
        raise FileNotFoundError(f"no pack named {name!r}")

    @_locked
    def install_pack(self, name: str) -> dict:
        return packs_mod.install_pack(self.engine, self._pack_file(name))

    @_locked
    def remove_pack(self, name: str) -> int:
        return packs_mod.uninstall_pack(self.engine, name)

    def harvest(self, topic: str, pages: int = 15) -> dict:
        """Build a pack about a topic from the web and install it (runs in the background; see ``jobs``)."""
        if not self.learn_online:
            raise RuntimeError("turn on 'Look things up online' in Settings to harvest from the web")
        topic = topic.strip()
        if not topic:
            raise ValueError("name a topic to harvest")
        self.jobs["harvest"] = {"status": "running", "topic": topic, "started": _now()}

        def run():
            try:
                path = self.packs_dir / f"{packs_mod.slug(topic)}.camrpack"
                with self._lock:
                    man, found = packs_mod.harvest(self.engine, self.lookup, topic, path, pages=pages)
                    res = packs_mod.install_pack(self.engine, path)
                self.jobs["harvest"] = {"status": "done", "topic": topic, "pages": len(found), **res, "at": _now()}
            except Exception as exc:  # surfaced in the Learning panel
                self.jobs["harvest"] = {"status": "error", "topic": topic, "error": str(exc)}

        threading.Thread(target=run, daemon=True).start()
        return self.jobs["harvest"]

    @_locked
    def _experience(self) -> list[tuple[str, set[int]]]:
        """(question, notes that answered it) from approved or well-grounded answers: what sleep learns from."""
        rows = self.store.conn.execute(
            "SELECT question, sources_json FROM app_turn WHERE sources_json IS NOT NULL AND sources_json != '[]'"
            " AND (feedback = 1 OR grounded >= 0.6)").fetchall()
        alive = {r[0] for r in self.store.conn.execute("SELECT note_id FROM note")}
        out = []
        for q, js in rows:
            ids = {s["note_id"] for s in json.loads(js)} & alive
            if ids:
                out.append((q, ids))
        return out

    def sleep_now(self, wait: bool = False) -> dict:
        """Consolidate memory (see camr.memory.sleep). Runs in the background unless ``wait``."""
        if self.jobs.get("sleep", {}).get("status") == "running":
            return self.jobs["sleep"]
        self.jobs["sleep"] = {"status": "running", "started": _now()}

        def run():
            try:
                pairs = self._experience()
                from camr.memory.bulk import drain

                vec = None
                if self.store.pending_count():
                    with self._lock:
                        vec = drain(self.engine, governor=self.governor, max_seconds=300).as_dict()
                with self._lock:
                    rep = run_sleep(self.engine, lookup=self.lookup if self.learn_online else None, pairs=pairs,
                                    adapter_path=self.adapter_path,
                                    index_min_notes=index_threshold(probe(self.store.path.parent), self.embedder.dim,
                                                                    self.governor.limits))
                    if vec is not None:
                        rep["vectors"] = vec
                    rep["requests_removed"] = self._tidy_requests()
                    with self.store.conn:
                        self.store.conn.execute("INSERT INTO app_sleep(at, report_json) VALUES (?, ?)",
                                                (_now(), json.dumps(rep, default=float)))
                self.jobs["sleep"] = {"status": "done", "report": rep, "at": _now()}
            except Exception as exc:
                self.jobs["sleep"] = {"status": "error", "error": str(exc)}

        if wait:
            run()
        else:
            threading.Thread(target=run, daemon=True).start()
        return self.jobs["sleep"]

    def maybe_sleep(self, idle_s: float = 600.0) -> bool:
        """Sleep if the user has been away for ``idle_s`` and memory changed since the last sleep."""
        if not self.sleep_when_idle or time.time() - getattr(self, "last_activity", time.time()) < idle_s:
            return False
        with self._lock:
            last = self.store.conn.execute("SELECT MAX(at) FROM app_sleep").fetchone()[0] or ""
            newer = self.store.conn.execute("SELECT COUNT(*) FROM source WHERE ingested_at > ?", (last,)).fetchone()[0]
        if not newer and not self.store.pending_count():
            return False
        if self.governor.busy():  # other work has the CPU: try again later
            return False
        self.sleep_now()
        return True

    @_locked
    def learning(self, limit: int = 40) -> dict:
        """Everything the Learning panel shows."""
        c = self.store.conn
        feed = [{"source_id": r[0], "kind": "pack" if r[1].startswith("pack:") else r[1], "title": r[2] or "",
                 "url": r[3] if (r[3] or "").startswith("http") else "", "added": r[4], "notes": r[5],
                 "pack": r[1][5:] if r[1].startswith("pack:") else None}
                for r in c.execute("SELECT s.source_id, s.dataset, s.title, s.doc_id, s.ingested_at, COUNT(n.note_id)"
                                   " FROM source s LEFT JOIN note n USING(source_id) GROUP BY s.source_id"
                                   " ORDER BY s.source_id DESC LIMIT ?", (limit,))]
        lookups = c.execute("SELECT COUNT(*), SUM(notes_added > 0), SUM(notes_added) FROM app_lookup").fetchone()
        last_sleep = c.execute("SELECT at, report_json FROM app_sleep ORDER BY sleep_id DESC LIMIT 1").fetchone()
        n = self.store.count()
        ad = self.engine.query_adapter
        ivf = self.store.ivf
        return {
            "feed": feed,
            "lookups": {"total": lookups[0] or 0, "learned_from": lookups[1] or 0, "notes": lookups[2] or 0},
            "packs": self.available_packs(),
            "jobs": self.jobs,
            "last_sleep": {"at": last_sleep[0], "report": json.loads(last_sleep[1])} if last_sleep else None,
            # The engine's external weights: what grows while the model's own weights stay frozen.
            "weights": {"notes": n, "dim": self.embedder.dim, "memory_parameters": n * self.embedder.dim,
                        "adapter_parameters": int(ad.U.size + ad.V.size) if ad is not None else 0,
                        "index_clusters": int(len(ivf.centroids)) if ivf is not None else 0,
                        "store_mb": round(self.store.path.stat().st_size / 1e6, 2) if self.store.path.exists() else 0.0},
            "settings": {"learn_online": self.learn_online, "sleep_when_idle": self.sleep_when_idle},
            "device": self.device(),
            "cards": self.card_packs(),
            "trust": self.trust(),
            "experts": self.experts(),
        }

    def device(self) -> dict:
        """This machine as the governor sees it: room left, and vectors still to add."""
        dev = probe(self.store.path.parent)
        free = max(0.0, dev.disk_free_mb - self.governor.limits.reserve_disk_mb)
        n = self.store.count()
        per_note = (self.governor.store_mb() * 1024 * 1024 / n) if n > 50 else 4200.0
        return {"disk_free_mb": dev.disk_free_mb, "reserve_disk_mb": self.governor.limits.reserve_disk_mb,
                "ram_available_mb": dev.ram_available_mb, "cpu_count": dev.cpu_count,
                "room_for_notes": int(free * 1024 * 1024 / max(per_note, 500.0)),
                "pending_vectors": self.store.pending_count()}

    # ------------------------------------------------------------ reporting
    @_locked
    def sources(self, kind: str | None = None, search: str = "", limit: int = 200) -> list[dict]:
        sql = ("SELECT s.source_id, s.dataset, s.title, s.ingested_at, COUNT(n.note_id),"
               " GROUP_CONCAT(n.text, ' ') FROM source s LEFT JOIN note n USING(source_id)")
        args: list = []
        if kind == "pack":
            sql += " WHERE s.dataset LIKE 'pack:%'"
        elif kind:
            sql += " WHERE s.dataset=?"
            args.append(kind)
        sql += " GROUP BY s.source_id ORDER BY s.source_id DESC"
        rows = [{"source_id": r[0], "kind": "pack" if r[1].startswith("pack:") else r[1], "title": r[2] or "",
                 "added": r[3], "notes": r[4], "text": r[5] or ""} for r in self.store.conn.execute(sql, args)]
        if search:
            rows = [r for r in rows if search.lower() in (r["title"] + " " + r["text"]).lower()]
        return rows[:limit]

    @_locked
    def stats(self) -> dict:
        c = self.store.conn
        by_kind = dict(c.execute("SELECT CASE WHEN s.dataset LIKE 'pack:%' THEN 'pack' ELSE s.dataset END AS k,"
                                 " COUNT(n.note_id) FROM note n JOIN source s USING(source_id) GROUP BY k").fetchall())
        turns, with_mem, up, down = c.execute(
            "SELECT COUNT(*), SUM(notes_used > 0), SUM(feedback = 1), SUM(feedback = -1) FROM app_turn").fetchone()
        growth = c.execute("SELECT substr(ingested_at, 1, 10) AS day, COUNT(*) FROM source GROUP BY day ORDER BY day"
                           ).fetchall()
        med = c.execute("SELECT retrieval_ms FROM app_turn WHERE retrieval_ms > 0 ORDER BY retrieval_ms").fetchall()
        return {
            "notes": sum(by_kind.values()), "notes_by_kind": by_kind,
            "store_mb": round(self.store.path.stat().st_size / 1e6, 2) if self.store.path.exists() else 0.0,
            "turns": turns or 0, "answered_with_memory": (with_mem or 0) / turns if turns else None,
            "helpful": up or 0, "not_helpful": down or 0,
            "median_retrieval_ms": med[len(med) // 2][0] if med else None,
            "sources_per_day": [tuple(r) for r in growth],
        }

    @_locked
    def export_feedback(self, include_text: bool = False) -> dict:
        """What a user may choose to share with the project: metrics only unless they opt in to text."""
        cols = ["turn_id", "at", "model", "notes_used", "abstained", "grounded", "retrieval_ms", "generation_ms",
                "prompt_tokens", "feedback"] + (["question", "answer"] if include_text else [])
        rows = self.store.conn.execute(f"SELECT {', '.join(cols)} FROM app_turn ORDER BY turn_id").fetchall()
        st = self.stats()
        return {"camr_app_feedback": 1, "exported_at": _now(), "embedder": self.embedder.name,
                "summary": {k: st[k] for k in ("notes", "notes_by_kind", "store_mb", "turns", "answered_with_memory",
                                               "helpful", "not_helpful", "median_retrieval_ms")},
                "turns": [dict(zip(cols, r)) for r in rows]}

    def close(self) -> None:
        self.store.close()

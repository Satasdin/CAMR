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

import datetime as dt
import json
import os
import re
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

import requests

from camr.config import Config, LocalModelConfig
from camr.memory import packs as packs_mod
from camr.memory.adapter import QueryAdapter
from camr.memory.eager import learn_pages
from camr.memory.embedder import Embedder, OllamaEmbedder
from camr.memory.engine import MemoryEngine
from camr.memory.fetch import WebLookup, embedding_rank, is_personal
from camr.memory.note import Document
from camr.memory.sleep import sleep as run_sleep
from camr.memory.store import SQLiteVectorStore
from camr.memory.verify import check, claim, fact_answer, relation_of, units_from_notes
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
"""

# Prompt F: prompt D (chosen on a development set and confirmed on two held-out sets, D-13 and D-16) with rule 3
# asking to be taught instead of only saying "I don't know", and answering first when the notes have it (D-19, where
# prompt E made a 3B model lead with "I don't know that yet"). Scored on the same sets (scripts/prompt_eval.py).
CHAT_PROMPT = """You are a private personal assistant running on the user's own computer.

The notes below come from the user's personal memory and are about the user. "The user said …" means the user told you this earlier; "I" inside it is the user. Treat what the notes say about the user as true and answer from them directly.

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

# A question is not knowledge about the user, so it is not kept as chat memory (defect D-14).
_QUESTION = re.compile(r"^\s*(?:what|which|who|whom|whose|when|where|why|how|is|are|was|were|do|does|did|can|could|"
                       r"would|should|will|shall|may|might|am|have|has|tell me|give me|convert|calculate|explain)\b", re.I)


def is_question(text: str) -> bool:
    text = text.strip()
    return text.endswith("?") or bool(_QUESTION.match(text))


_REMEMBER = re.compile(r"^\s*(?:/remember|remember(?: that)?|note:)\s*[:,-]?\s*(.+)$", re.I | re.S)
_WORD = re.compile(r"[A-Za-z0-9][A-Za-z0-9'\-.,:]*")
_STOP = set("""a an the and or but if of to in on at for from by with about as is are was were be been being it its
this that these those i you he she we they me my your our their what which who whom whose when where why how do does
did not no yes can could would should will just so than then there here also only very more most""".split())


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
                 token_budget: int = 384, history_turns: int = 6, remember_chat: bool = True,
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
                       "similarity_margin": 0.15, "expansion": "entity", "entity_gate": True, "chunk_tokens": 120},
        })
        # One store file per embedder: vectors from different embedders cannot be mixed.
        db = "memory.sqlite" if embedder is not None or self.embedder.name.startswith("BAAI") else \
            f"memory-{re.sub(r'[^A-Za-z0-9]+', '-', self.embedder.name)}.sqlite"
        self.store = SQLiteVectorStore(self.home / db, dim=self.embedder.dim, embedder_name=self.embedder.name,
                                       check_same_thread=False)
        self.store.conn.executescript(APP_SCHEMA)
        cols = {r[1] for r in self.store.conn.execute("PRAGMA table_info(app_turn)")}
        for col, typ in (("conversation_id", "INTEGER"), ("sources_json", "TEXT"), ("learned_json", "TEXT"),
                         ("ask_to_teach", "INTEGER"), ("verification_json", "TEXT")):
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
                "verified_only": self.verified_only, "min_similarity": self.engine.min_similarity}

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
                   "verified_only"}
        for k, v in changes.items():
            if k in allowed:
                setattr(self, k, v)
        if "token_budget" in changes:
            self.engine.budgeter.budget = int(self.token_budget)
        data = self.settings()
        data.pop("min_similarity")
        self.settings_path.write_text(json.dumps(data, indent=2))

    # ------------------------------------------------------------ teaching
    @_locked
    def teach(self, text: str, title: str = "", kind: str = "note", doc_id: str | None = None) -> int:
        """Store text as memory. Returns the number of notes accepted (0 if it was a duplicate or empty)."""
        text = text.strip()
        if not text:
            return 0
        doc_id = doc_id or f"{kind}-{dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%f')}"
        summary = self.engine.ingest([Document(dataset=kind, doc_id=doc_id, text=text, title=title)])
        return summary.accepted

    def teach_file(self, name: str, data: bytes) -> int:
        """Store a text, Markdown or PDF file (PDF needs the optional ``pypdf`` package)."""
        if name.lower().endswith(".pdf"):
            try:
                from pypdf import PdfReader  # type: ignore
            except ImportError as exc:
                raise RuntimeError("reading PDFs needs `pip install pypdf`") from exc
            import io

            text = "\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages)
        else:
            text = data.decode("utf-8", errors="replace")
        return self.teach(text, title=Path(name).stem, kind="file", doc_id=f"file-{name}")

    @_locked
    def forget(self, source_id: int) -> int:
        return self.store.delete_source(source_id)

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
            " prompt_tokens, feedback, sources_json, learned_json, ask_to_teach, verification_json FROM app_turn"
            " WHERE conversation_id=?"
            " ORDER BY turn_id", (conversation_id,)).fetchall()
        return [Turn(turn_id=r[0], question=r[1], answer=r[2], abstained=bool(r[4]), grounded=r[5],
                     retrieval_ms=r[6] or 0.0, generation_ms=r[7] or 0.0, prompt_tokens=r[8], feedback=r[9],
                     conversation_id=conversation_id, learned=json.loads(r[11]) if r[11] else None,
                     ask_to_teach=bool(r[12]), verification=json.loads(r[13]) if r[13] else None,
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

    def _stream_generate(self, prompt: str) -> Iterator[tuple[str, dict]]:
        if not self.model:
            raise RuntimeError("choose a model first")
        body = self._runner().payload(prompt)
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

    def events(self, question: str, conversation_id: int | None = None) -> Iterator[dict]:
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

        with self._lock:
            recall = self.engine.recall(question)
        learned = None
        personal = is_personal(question)
        if recall.abstained and self.learn_online and not personal:
            # Eager learning: memory has nothing, so look the subject up, learn it, and recall again.
            yield {"type": "lookup", "conversation_id": conversation_id}
            found = self.lookup.lookup(question)
            added = 0
            if found.pages:
                with self._lock:
                    added = learn_pages(self.engine, found.pages)
                    recall = self.engine.recall(question)
            learned = {"queries": found.queries, "notes_added": added, "ms": round(found.ms, 1),
                       "pages": [{"title": p.title, "url": p.url, "source": p.source} for p in found.pages],
                       "errors": found.errors}
            self._log_lookup(question, found, added)
        sources = self._sources(recall)
        yield {"type": "recall", "sources": [asdict(s) for s in sources], "abstained": recall.abstained,
               "retrieval_ms": round(recall.retrieval_ms, 1), "conversation_id": conversation_id, "learned": learned}
        factual = _short_factual(question) and not personal
        units = []
        if factual and not recall.abstained:
            with self._lock:
                units = units_from_notes(self.store, [c.note for c in recall.candidates if c.eligible])
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
        prompt = CHAT_PROMPT.format(notes=recall.context or "(no relevant notes)",
                                    history=self._history(conversation_id), question=question)
        t0, parts, last, first = time.perf_counter(), [], {}, None
        for piece, chunk in self._stream_generate(prompt):
            parts.append(piece)
            last = chunk
            if piece:
                if first is None:
                    first = round((time.perf_counter() - t0) * 1000, 1)
                yield {"type": "token", "text": piece}
        answer = "".join(parts).strip()
        verification = None
        if factual:
            verification = _verification(question, answer, units)
            if self.verified_only and verification["status"] != "verified" and claim(answer):
                answer = (f"I couldn't confirm this from what I've read, so take it as a lead, not a fact: "
                          f"{claim(answer)} (unverified).")
        turn = Turn(turn_id=None, question=question, answer=answer, sources=sources, abstained=recall.abstained,
                    grounded=grounded_share(answer, recall.context), retrieval_ms=round(recall.retrieval_ms, 1),
                    generation_ms=round((time.perf_counter() - t0) * 1000, 1), first_token_ms=first,
                    prompt_tokens=last.get("prompt_eval_count"), conversation_id=conversation_id, learned=learned,
                    ask_to_teach=recall.abstained and personal, verification=verification)
        turn.turn_id = self._log(turn)
        self.last_activity = time.time()
        if self.remember_chat and not is_question(question):
            # What the user *states* is the user's own knowledge: keep it, so it can be
            # recalled long after it has scrolled out of the context window. Questions are
            # not kept: they carry no knowledge and only crowd out real memories (D-14).
            day = dt.date.today().isoformat()
            turn.saved_to_memory = self.teach(f"On {day} the user said: {question}", kind="chat",
                                              doc_id=f"chat-{turn.turn_id}") > 0
        yield {"type": "done", "turn": turn.as_dict()}

    @_locked
    def _log(self, turn: Turn) -> int:
        with self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO app_turn(at, model, question, answer, notes_used, abstained, grounded, retrieval_ms,"
                " generation_ms, prompt_tokens, conversation_id, sources_json, learned_json, ask_to_teach,"
                " verification_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (_now(), self.model or "-", turn.question, turn.answer, len(turn.sources), int(turn.abstained),
                 turn.grounded, turn.retrieval_ms, turn.generation_ms, turn.prompt_tokens, turn.conversation_id,
                 json.dumps([asdict(s) for s in turn.sources]), json.dumps(turn.learned) if turn.learned else None,
                 int(turn.ask_to_teach), json.dumps(turn.verification) if turn.verification else None))
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
    def feedback(self, turn_id: int, helpful: bool) -> None:
        """Thumbs up stores the approved answer as memory: the model gets better without changing weights."""
        with self._lock, self.store.conn:
            self.store.conn.execute("UPDATE app_turn SET feedback=? WHERE turn_id=?", (1 if helpful else -1, turn_id))
        if helpful:
            q, a = self.store.conn.execute("SELECT question, answer FROM app_turn WHERE turn_id=?",
                                           (turn_id,)).fetchone()
            self.teach(f"Q: {q}\nA: {a}", kind="learned", doc_id=f"learned-{turn_id}")

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
                with self._lock:
                    rep = run_sleep(self.engine, lookup=self.lookup if self.learn_online else None, pairs=pairs,
                                    adapter_path=self.adapter_path)
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
        if not newer:
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
        }

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

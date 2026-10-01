"""CAMR Personal: a local assistant whose model stays frozen while its memory grows.

This is the deployment scenario of the study, packaged for real use:

* any model the user already has in Ollama answers;
* everything the user teaches it (notes, files, approved answers, what they say
  in chat) is stored as retrievable notes in one SQLite file under ``~/.camr``;
* each question reads only the few notes it needs (gating + entity bridging,
  the best read path measured in docs/FINDINGS.md), so knowledge grows with
  *storage*, not with the context window or with compute;
* the conversation itself becomes memory, so a chat can run far past the
  model's context window and still recall what was said weeks ago.

Nothing leaves the machine.  Feedback is stored locally and only exported when
the user chooses to (``export_feedback``).

The class is UI-agnostic; ``camr/app/ui.py`` is the Streamlit front end.
"""

from __future__ import annotations

import datetime as dt
import json
import re
import sqlite3
import threading
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Iterator

import requests

from camr.config import Config, LocalModelConfig
from camr.memory.embedder import Embedder, build_embedder
from camr.memory.engine import MemoryEngine
from camr.memory.note import Document
from camr.memory.store import SQLiteVectorStore
from camr.models.runner import OllamaRunner
from camr.models.tokenizer import RegexTokenizer

DEFAULT_HOME = Path.home() / ".camr"
DEFAULT_HOST = "http://127.0.0.1:11434"

# Where a note came from.  Shown on every source chip in the UI.
KINDS = {
    "note": "your note",
    "file": "your file",
    "chat": "something you said",
    "learned": "an answer you approved",
}

APP_SCHEMA = """
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
    feedback       INTEGER          -- +1 helpful, -1 not helpful, NULL none
);
"""

CHAT_PROMPT = """You are a personal assistant running privately on the user's own computer.
Below are notes from the user's personal memory that may be relevant, then the recent conversation.
Use the notes when they answer the question and prefer them over your own assumptions.
If the notes do not contain the answer and you are not sure, say you don't know rather than guessing.
Answer concisely.

### Notes from memory
{notes}

### Recent conversation
{history}

### User
{question}

### Assistant
"""

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
    prompt_tokens: int | None = None
    saved_to_memory: bool = False

    def as_dict(self) -> dict:
        return asdict(self)


def installed_models(host: str = DEFAULT_HOST, timeout: float = 3.0) -> list[dict]:
    """Models the user already has in Ollama (name, size in GB, parameter size)."""
    resp = requests.get(f"{host}/api/tags", timeout=timeout)
    resp.raise_for_status()
    out = []
    for m in resp.json().get("models", []):
        details = m.get("details") or {}
        out.append({"name": m["name"], "size_gb": round((m.get("size") or 0) / 1e9, 1),
                    "parameters": details.get("parameter_size", "?"),
                    "family": details.get("family", "?")})
    return sorted(out, key=lambda m: m["size_gb"])


def grounded_share(answer: str, notes: str) -> float | None:
    """Share of the answer's content words that occur in the notes (None when there is nothing to check)."""
    words = [w.strip(".,:").lower() for w in _WORD.findall(answer)]
    words = [w for w in words if w and w not in _STOP]
    if not words or not notes:
        return None
    hay = notes.lower()
    return sum(1 for w in words if w in hay) / len(words)


def _locked(fn):
    """One store connection is shared by the UI's threads: serialise every call that touches it."""
    def wrapper(self, *args, **kwargs):
        with self._lock:
            return fn(self, *args, **kwargs)
    wrapper.__name__, wrapper.__doc__ = fn.__name__, fn.__doc__
    return wrapper


class Assistant:
    """A frozen local model plus a personal memory that grows with use."""

    def __init__(self, home: str | Path = DEFAULT_HOME, *, model: str | None = None, host: str = DEFAULT_HOST,
                 token_budget: int = 384, history_turns: int = 6, remember_chat: bool = True, min_similarity: float = 0.50,
                 embedder: Embedder | None = None, session: requests.Session | None = None):
        self.home = Path(home).expanduser()
        self.home.mkdir(parents=True, exist_ok=True)
        self.settings_path = self.home / "settings.json"
        saved = self._load_settings()
        self.host = host
        self.model = model or saved.get("model")
        self.token_budget = int(saved.get("token_budget", token_budget))
        self.history_turns = int(saved.get("history_turns", history_turns))
        self.remember_chat = bool(saved.get("remember_chat", remember_chat))
        self._http = session or requests.Session()
        self._lock = threading.RLock()

        # The read path measured best in docs/FINDINGS.md: similarity ranking,
        # gating (abstain below 0.50, admit within 0.15 of the best) and
        # entity bridging.  Verbatim notes: the user's own words are kept.
        self.cfg = Config.from_dict({
            "memory": {"write_policy": "verbatim", "retrieval_policy": "similarity_only",
                       "weights": {"similarity": 1.0, "recency": 0.0, "importance": 0.0},
                       "k": 20, "token_budget": self.token_budget, "min_similarity": min_similarity,
                       "similarity_margin": 0.15, "expansion": "entity", "chunk_tokens": 120},
        })
        self.embedder = embedder or build_embedder(self.cfg.embedder)
        self.store = SQLiteVectorStore(self.home / "memory.sqlite", dim=self.embedder.dim,
                                       embedder_name=self.embedder.name, check_same_thread=False)
        self.store.conn.executescript(APP_SCHEMA)
        self.engine = MemoryEngine.from_config(self.cfg, store=self.store, embedder=self.embedder,
                                               tokenizer=RegexTokenizer())

    # ------------------------------------------------------------ settings
    def _load_settings(self) -> dict:
        try:
            return json.loads(self.settings_path.read_text())
        except (OSError, ValueError):
            return {}

    def save_settings(self, **changes) -> None:
        for k, v in changes.items():
            setattr(self, k, v)
        if "token_budget" in changes:
            self.engine.budgeter.budget = int(self.token_budget)
        self.settings_path.write_text(json.dumps({
            "model": self.model, "token_budget": self.token_budget,
            "history_turns": self.history_turns, "remember_chat": self.remember_chat}, indent=2))

    # ------------------------------------------------------------ teaching
    @_locked
    def teach(self, text: str, title: str = "", kind: str = "note", doc_id: str | None = None) -> int:
        """Store text as memory. Returns the number of notes accepted (0 if it was a duplicate or empty)."""
        text = text.strip()
        if not text:
            return 0
        now = dt.datetime.now(dt.timezone.utc)
        doc_id = doc_id or f"{kind}-{now.strftime('%Y%m%dT%H%M%S%f')}"
        summary = self.engine.ingest([Document(dataset=kind, doc_id=doc_id, text=text, title=title)])
        return summary.accepted

    @_locked
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

    # ------------------------------------------------------------ asking
    @_locked
    def _history(self) -> str:
        rows = self.store.conn.execute(
            "SELECT question, answer FROM app_turn ORDER BY turn_id DESC LIMIT ?", (self.history_turns,)).fetchall()
        return "\n".join(f"User: {q}\nAssistant: {a}" for q, a in reversed(rows)) or "(none)"

    @_locked
    def _sources(self, recall) -> list[Source]:
        admitted = recall.admitted
        ids = [c.note.source_id for c in admitted]
        meta = {}
        if ids:
            q = f"SELECT source_id, dataset, title FROM source WHERE source_id IN ({','.join('?' * len(ids))})"
            meta = {r[0]: (r[1], r[2] or "") for r in self.store.conn.execute(q, ids)}
        return [Source(note_id=c.note.note_id, kind=meta.get(c.note.source_id, ("note", ""))[0],
                       title=meta.get(c.note.source_id, ("", ""))[1], text=c.note.text,
                       similarity=round(c.similarity, 3), via_bridge=c.via is not None) for c in admitted]

    def _stream_generate(self, prompt: str) -> Iterator[tuple[str, dict]]:
        if not self.model:
            raise RuntimeError("choose a model first")
        runner = OllamaRunner(LocalModelConfig(name=self.model, host=self.host, max_tokens=512, num_ctx=4096),
                              session=self._http)
        body = runner.payload(prompt)
        body["stream"] = True
        with self._http.post(f"{self.host}/api/generate", json=body, stream=True, timeout=600) as resp:
            resp.raise_for_status()
            for line in resp.iter_lines():
                if not line:
                    continue
                chunk = json.loads(line)
                yield chunk.get("response", ""), chunk

    def ask_stream(self, question: str) -> Iterator[str | Turn]:
        """Yield answer text as it is generated, then the finished Turn."""
        question = question.strip()
        m = re.match(r"^\s*(?:/remember|remember(?: that)?|note:)\s*[:,-]?\s*(.+)$", question, re.I | re.S)
        if m:  # an explicit "remember ..." is stored directly, with no model call
            n = self.teach(m.group(1), kind="note")
            msg = "Saved to memory." if n else "I already had that in memory."
            yield msg
            yield Turn(turn_id=None, question=question, answer=msg, saved_to_memory=bool(n))
            return

        with self._lock:
            recall = self.engine.recall(question)
        sources = self._sources(recall)
        prompt = CHAT_PROMPT.format(notes=recall.context or "(no relevant notes)", history=self._history(),
                                    question=question)
        t0, parts, last = time.perf_counter(), [], {}
        for piece, chunk in self._stream_generate(prompt):
            parts.append(piece)
            last = chunk
            yield piece
        answer = "".join(parts).strip()
        turn = Turn(turn_id=None, question=question, answer=answer, sources=sources, abstained=recall.abstained,
                    grounded=grounded_share(answer, recall.context), retrieval_ms=round(recall.retrieval_ms, 1),
                    generation_ms=round((time.perf_counter() - t0) * 1000, 1),
                    prompt_tokens=last.get("prompt_eval_count"))
        with self._lock, self.store.conn:
            cur = self.store.conn.execute(
                "INSERT INTO app_turn(at, model, question, answer, notes_used, abstained, grounded, retrieval_ms,"
                " generation_ms, prompt_tokens) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (dt.datetime.now(dt.timezone.utc).isoformat(), self.model, question, answer, len(sources),
                 int(recall.abstained), turn.grounded, turn.retrieval_ms, turn.generation_ms, turn.prompt_tokens))
            turn.turn_id = cur.lastrowid
        if self.remember_chat:
            # What the user says is the user's own knowledge: keep it, so it can be
            # recalled long after it has scrolled out of the context window.
            day = dt.date.today().isoformat()
            turn.saved_to_memory = self.teach(f"On {day} the user said: {question}", kind="chat",
                                              doc_id=f"chat-{turn.turn_id}") > 0
        yield turn

    def ask(self, question: str) -> Turn:
        out = None
        for item in self.ask_stream(question):
            out = item
        return out  # type: ignore[return-value]

    # ------------------------------------------------------------ feedback
    @_locked
    def feedback(self, turn_id: int, helpful: bool) -> None:
        """Thumbs up stores the approved answer as memory: the model gets better without changing weights."""
        with self.store.conn:
            self.store.conn.execute("UPDATE app_turn SET feedback=? WHERE turn_id=?", (1 if helpful else -1, turn_id))
        if helpful:
            q, a = self.store.conn.execute("SELECT question, answer FROM app_turn WHERE turn_id=?",
                                           (turn_id,)).fetchone()
            self.teach(f"Q: {q}\nA: {a}", kind="learned", doc_id=f"learned-{turn_id}")

    # ------------------------------------------------------------ reporting
    @_locked
    def sources(self, kind: str | None = None, search: str = "", limit: int = 200) -> list[dict]:
        sql = ("SELECT s.source_id, s.dataset, s.title, s.ingested_at, COUNT(n.note_id),"
               " GROUP_CONCAT(n.text, ' ') FROM source s LEFT JOIN note n USING(source_id)")
        where, args = [], []
        if kind:
            where.append("s.dataset=?"); args.append(kind)
        sql += (" WHERE " + " AND ".join(where)) if where else ""
        sql += " GROUP BY s.source_id ORDER BY s.source_id DESC"
        rows = [{"source_id": r[0], "kind": r[1], "title": r[2] or "", "added": r[3], "notes": r[4],
                 "text": r[5] or ""} for r in self.store.conn.execute(sql, args)]
        if search:
            rows = [r for r in rows if search.lower() in (r["title"] + " " + r["text"]).lower()]
        return rows[:limit]

    @_locked
    def stats(self) -> dict:
        c = self.store.conn
        by_kind = dict(c.execute("SELECT s.dataset, COUNT(n.note_id) FROM note n JOIN source s USING(source_id)"
                                 " GROUP BY s.dataset").fetchall())
        turns, with_mem, up, down = c.execute(
            "SELECT COUNT(*), SUM(notes_used > 0), SUM(feedback = 1), SUM(feedback = -1) FROM app_turn").fetchone()
        growth = c.execute("SELECT substr(ingested_at, 1, 10) AS day, COUNT(*) FROM source GROUP BY day ORDER BY day"
                           ).fetchall()
        med = c.execute("SELECT retrieval_ms FROM app_turn ORDER BY retrieval_ms").fetchall()
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
        return {"camr_app_feedback": 1, "exported_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                "summary": {k: st[k] for k in ("notes", "notes_by_kind", "store_mb", "turns", "answered_with_memory",
                                               "helpful", "not_helpful", "median_retrieval_ms")},
                "turns": [dict(zip(cols, r)) for r in rows]}

    def close(self) -> None:
        self.store.close()

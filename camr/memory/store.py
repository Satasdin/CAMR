"""Persistence (FR-05, IR-04, NFR-03): one SQLite file, no server process.

Notes, embeddings, provenance and the harness tables share one file and one
connection, so a note, its vector and its source are committed in a single
transaction and the store can never hold a note without its vector.

Vector search uses the ``sqlite-vec`` extension when it is installed, loaded
into the same connection.  Without it, the store falls back to exact search over
the same BLOB column in NumPy; both paths return identical scores because the
similarity reported is always recomputed from the stored float32 vectors.
"""

from __future__ import annotations

import contextlib
import datetime as dt
import re
import sqlite3
from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable, Iterator

import numpy as np

from camr.memory.note import Note, as_float32, from_iso, to_iso

SCHEMA_VERSION = "1"

MEMORY_SCHEMA = """
CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS source (
    source_id        INTEGER PRIMARY KEY,
    dataset          TEXT NOT NULL,
    doc_id           TEXT NOT NULL,
    note_type        TEXT NOT NULL,
    title            TEXT,
    ingested_at      TIMESTAMP NOT NULL,
    screener_verdict TEXT,
    UNIQUE (dataset, doc_id, note_type)
);
CREATE TABLE IF NOT EXISTS note (
    note_id          INTEGER PRIMARY KEY,
    source_id        INTEGER NOT NULL REFERENCES source(source_id),
    note_type        TEXT NOT NULL,
    text             TEXT NOT NULL,
    token_count      INTEGER NOT NULL,
    importance       REAL NOT NULL,
    created_at       TIMESTAMP NOT NULL,
    last_accessed_at TIMESTAMP NOT NULL,
    access_count     INTEGER NOT NULL DEFAULT 0,
    checksum         TEXT NOT NULL UNIQUE
);
CREATE TABLE IF NOT EXISTS note_embedding (
    note_id   INTEGER PRIMARY KEY REFERENCES note(note_id) ON DELETE CASCADE,
    embedding BLOB NOT NULL
);
CREATE TABLE IF NOT EXISTS rejection (
    rejection_id INTEGER PRIMARY KEY,
    source_id    INTEGER REFERENCES source(source_id),
    note_type    TEXT NOT NULL,
    reason       TEXT NOT NULL,
    text         TEXT,
    created_at   TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_note_source ON note(source_id);
CREATE INDEX IF NOT EXISTS idx_note_type   ON note(note_type);
CREATE INDEX IF NOT EXISTS idx_rejection_source ON rejection(source_id);
"""


class StoreError(RuntimeError):
    pass


class MemoryStore(ABC):
    """Abstract persistence interface (Figure 4.3)."""

    @abstractmethod
    def knn(self, query: np.ndarray, k: int, note_type: str) -> list[tuple[int, float]]: ...

    @abstractmethod
    def get_notes(self, note_ids: Iterable[int]) -> dict[int, Note]: ...

    @abstractmethod
    def insert_note(self, **fields) -> int: ...

    @abstractmethod
    def stats(self, note_type: str | None = None) -> dict: ...


def _vec_available() -> bool:
    try:
        import sqlite_vec  # type: ignore  # noqa: F401
    except ImportError:
        return False
    return hasattr(sqlite3.Connection, "enable_load_extension")


class SQLiteVectorStore(MemoryStore):
    def __init__(
        self,
        path: str | Path,
        *,
        dim: int,
        embedder_name: str,
        use_vec: bool | None = None,
        readonly: bool = False,
    ):
        self.path = Path(path)
        self.dim = dim
        self.readonly = readonly
        if readonly:
            self.conn = sqlite3.connect(f"file:{self.path}?mode=ro", uri=True)
        else:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(self.path)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.use_vec = _vec_available() if use_vec is None else use_vec
        if self.use_vec:
            self._load_vec()
        if not readonly:
            self.conn.executescript(MEMORY_SCHEMA)
            self._migrate()
            self._init_meta(embedder_name)
            if self.use_vec:
                self.conn.execute(
                    "CREATE VIRTUAL TABLE IF NOT EXISTS note_vec USING vec0("
                    f"note_type text, embedding float[{dim}] distance_metric=cosine)"
                )
                self._sync_vec_index()
            self.conn.commit()
        self._matrix_cache: dict[str, tuple[np.ndarray, np.ndarray]] = {}
        self._title_cache: dict[str, tuple[dict[str, list[int]], int]] = {}

    # -------------------------------------------------------------- setup
    def _load_vec(self) -> None:
        import sqlite_vec  # type: ignore

        self.conn.enable_load_extension(True)
        try:
            sqlite_vec.load(self.conn)
        finally:
            self.conn.enable_load_extension(False)

    def _migrate(self) -> None:
        """Add columns introduced after a store file was first created."""
        cols = {r[1] for r in self.conn.execute("PRAGMA table_info(source)")}
        if "title" not in cols:
            self.conn.execute("ALTER TABLE source ADD COLUMN title TEXT")

    def _init_meta(self, embedder_name: str) -> None:
        cur = dict(self.conn.execute("SELECT key, value FROM meta").fetchall())
        if not cur:
            self.conn.executemany(
                "INSERT INTO meta(key, value) VALUES (?, ?)",
                [("schema_version", SCHEMA_VERSION), ("embedder", embedder_name), ("dim", str(self.dim))],
            )
            return
        if cur.get("dim") != str(self.dim) or cur.get("embedder") != embedder_name:
            raise StoreError(
                f"store was built with embedder {cur.get('embedder')} (dim {cur.get('dim')}); "
                f"refusing to mix with {embedder_name} (dim {self.dim})"
            )

    def _sync_vec_index(self) -> None:
        """Rebuild the vec0 index if it is missing rows (e.g. store built without the extension)."""
        n_blob = self.conn.execute("SELECT COUNT(*) FROM note_embedding").fetchone()[0]
        n_vec = self.conn.execute("SELECT COUNT(*) FROM note_vec").fetchone()[0]
        if n_blob == n_vec:
            return
        self.conn.execute("DELETE FROM note_vec")
        rows = self.conn.execute(
            "SELECT e.note_id, n.note_type, e.embedding FROM note_embedding e JOIN note n USING(note_id)"
        )
        self.conn.executemany(
            "INSERT INTO note_vec(rowid, note_type, embedding) VALUES (?, ?, ?)",
            ((r[0], r[1], r[2]) for r in rows),
        )

    @contextlib.contextmanager
    def transaction(self) -> Iterator[sqlite3.Connection]:
        """Single transaction boundary for note + embedding + provenance."""
        try:
            yield self.conn
            self.conn.commit()
        except BaseException:
            self.conn.rollback()
            raise
        finally:
            self._matrix_cache.clear()
            self._title_cache.clear()

    def close(self) -> None:
        self.conn.close()

    # -------------------------------------------------------------- writes
    def get_or_create_source(self, dataset: str, doc_id: str, note_type: str, ingested_at: str,
                             title: str | None = None) -> tuple[int, bool]:
        row = self.conn.execute(
            "SELECT source_id FROM source WHERE dataset=? AND doc_id=? AND note_type=?",
            (dataset, doc_id, note_type),
        ).fetchone()
        if row:
            return int(row[0]), False
        cur = self.conn.execute(
            "INSERT INTO source(dataset, doc_id, note_type, title, ingested_at) VALUES (?, ?, ?, ?, ?)",
            (dataset, doc_id, note_type, title or None, ingested_at),
        )
        return int(cur.lastrowid), True

    def source_done(self, source_id: int) -> bool:
        row = self.conn.execute("SELECT screener_verdict FROM source WHERE source_id=?", (source_id,)).fetchone()
        return bool(row and row[0])

    def set_source_verdict(self, source_id: int, verdict: str) -> None:
        self.conn.execute("UPDATE source SET screener_verdict=? WHERE source_id=?", (verdict, source_id))

    def insert_note(
        self,
        *,
        source_id: int,
        note_type: str,
        text: str,
        token_count: int,
        importance: float,
        checksum: str,
        created_at: str,
        embedding: np.ndarray,
    ) -> int:
        vec = as_float32(embedding)
        if vec.shape != (self.dim,):
            raise StoreError(f"embedding has shape {vec.shape}, store expects ({self.dim},)")
        cur = self.conn.execute(
            "INSERT INTO note(source_id, note_type, text, token_count, importance, created_at,"
            " last_accessed_at, access_count, checksum) VALUES (?, ?, ?, ?, ?, ?, ?, 0, ?)",
            (source_id, note_type, text, token_count, importance, created_at, created_at, checksum),
        )
        note_id = int(cur.lastrowid)
        blob = vec.tobytes()
        self.conn.execute("INSERT INTO note_embedding(note_id, embedding) VALUES (?, ?)", (note_id, blob))
        if self.use_vec:
            self.conn.execute(
                "INSERT INTO note_vec(rowid, note_type, embedding) VALUES (?, ?, ?)", (note_id, note_type, blob)
            )
        return note_id

    def log_rejection(self, source_id: int | None, note_type: str, reason: str, text: str, at: str) -> None:
        self.conn.execute(
            "INSERT INTO rejection(source_id, note_type, reason, text, created_at) VALUES (?, ?, ?, ?, ?)",
            (source_id, note_type, reason, text, at),
        )

    def touch(self, note_ids: Iterable[int], when: dt.datetime) -> None:
        ids = list(note_ids)
        if not ids:
            return
        self.conn.executemany(
            "UPDATE note SET last_accessed_at=?, access_count=access_count+1 WHERE note_id=?",
            [(to_iso(when), i) for i in ids],
        )
        self.conn.commit()

    def reset_access_state(self, note_type: str | None = None) -> None:
        """Restore every note to its just-ingested state so each run starts identically."""
        q = "UPDATE note SET last_accessed_at=created_at, access_count=0"
        if note_type:
            self.conn.execute(q + " WHERE note_type=?", (note_type,))
        else:
            self.conn.execute(q)
        self.conn.commit()

    # --------------------------------------------------------------- reads
    def checksums(self, note_type: str | None = None) -> set[str]:
        if note_type:
            rows = self.conn.execute("SELECT checksum FROM note WHERE note_type=?", (note_type,))
        else:
            rows = self.conn.execute("SELECT checksum FROM note")
        return {r[0] for r in rows}

    def count(self, note_type: str | None = None) -> int:
        if note_type:
            return self.conn.execute("SELECT COUNT(*) FROM note WHERE note_type=?", (note_type,)).fetchone()[0]
        return self.conn.execute("SELECT COUNT(*) FROM note").fetchone()[0]

    def latest_created_at(self, note_type: str | None = None) -> dt.datetime | None:
        q = "SELECT MAX(created_at) FROM note" + (" WHERE note_type=?" if note_type else "")
        row = self.conn.execute(q, (note_type,) if note_type else ()).fetchone()
        return from_iso(row[0]) if row and row[0] else None

    def _matrix(self, note_type: str) -> tuple[np.ndarray, np.ndarray]:
        if note_type not in self._matrix_cache:
            rows = self.conn.execute(
                "SELECT e.note_id, e.embedding FROM note_embedding e JOIN note n USING(note_id)"
                " WHERE n.note_type=? ORDER BY e.note_id",
                (note_type,),
            ).fetchall()
            ids = np.array([r[0] for r in rows], dtype=np.int64)
            mat = (
                np.vstack([np.frombuffer(r[1], dtype=np.float32) for r in rows])
                if rows
                else np.zeros((0, self.dim), dtype=np.float32)
            )
            self._matrix_cache[note_type] = (ids, mat)
        return self._matrix_cache[note_type]

    def knn(self, query: np.ndarray, k: int, note_type: str) -> list[tuple[int, float]]:
        """Top-k (note_id, cosine similarity), ordered by similarity then note_id."""
        q = as_float32(query)
        if self.use_vec:
            rows = self.conn.execute(
                "SELECT rowid FROM note_vec WHERE embedding MATCH ? AND k = ? AND note_type = ?"
                " ORDER BY distance",
                (q.tobytes(), int(k), note_type),
            ).fetchall()
            ids = [int(r[0]) for r in rows]
            if not ids:
                return []
            marks = ",".join("?" * len(ids))
            emb = {
                int(r[0]): np.frombuffer(r[1], dtype=np.float32)
                for r in self.conn.execute(
                    f"SELECT note_id, embedding FROM note_embedding WHERE note_id IN ({marks})", ids
                )
            }
            scored = [(i, _cosine(q, emb[i])) for i in ids]
        else:
            ids_arr, mat = self._matrix(note_type)
            if len(ids_arr) == 0:
                return []
            qn = float(np.linalg.norm(q)) or 1.0
            norms = np.linalg.norm(mat, axis=1)
            norms[norms == 0] = 1.0
            sims = (mat @ q) / (norms * qn)
            top = np.argsort(-sims, kind="stable")[: int(k)]
            scored = [(int(ids_arr[j]), float(sims[j])) for j in top]
        scored.sort(key=lambda t: (-round(t[1], 7), t[0]))
        return scored

    def title_index(self, note_type: str, min_len: int = 4) -> tuple[dict[str, list[int]], int]:
        """Map entity title (and its parenthesis-free alias) -> note ids, plus the
        longest title in words.  Used by entity-bridge expansion: a mention of a
        title inside a note links to the notes about that entity."""
        if note_type not in self._title_cache:
            index: dict[str, list[int]] = {}
            for title, note_id in self.conn.execute(
                "SELECT s.title, n.note_id FROM note n JOIN source s USING(source_id)"
                " WHERE n.note_type=? AND s.title IS NOT NULL ORDER BY n.note_id",
                (note_type,),
            ):
                full = " ".join(title.split())
                alias = re.sub(r"\s*\([^)]*\)$", "", full)  # "Titanic (1997 film)" -> "Titanic"
                for key in {full, alias}:
                    if len(key) >= min_len:
                        index.setdefault(key, []).append(int(note_id))
            longest = max((len(k.split()) for k in index), default=0)
            self._title_cache[note_type] = (index, longest)
        return self._title_cache[note_type]

    def note_titles(self, note_ids: Iterable[int]) -> dict[int, str | None]:
        ids = list(note_ids)
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        return {int(r[0]): r[1] for r in self.conn.execute(
            f"SELECT n.note_id, s.title FROM note n JOIN source s USING(source_id) WHERE n.note_id IN ({marks})", ids)}

    def similarities(self, query: np.ndarray, note_ids: Iterable[int]) -> dict[int, float]:
        ids = list(note_ids)
        if not ids:
            return {}
        q = as_float32(query)
        marks = ",".join("?" * len(ids))
        return {
            int(r[0]): _cosine(q, np.frombuffer(r[1], dtype=np.float32))
            for r in self.conn.execute(f"SELECT note_id, embedding FROM note_embedding WHERE note_id IN ({marks})", ids)
        }

    def get_notes(self, note_ids: Iterable[int]) -> dict[int, Note]:
        ids = list(note_ids)
        if not ids:
            return {}
        marks = ",".join("?" * len(ids))
        rows = self.conn.execute(
            "SELECT note_id, source_id, note_type, text, token_count, importance, checksum, created_at,"
            f" last_accessed_at, access_count FROM note WHERE note_id IN ({marks})",
            ids,
        )
        return {r["note_id"]: Note(**dict(r)) for r in rows}

    def stats(self, note_type: str | None = None) -> dict:
        where, args = ("WHERE note_type=?", (note_type,)) if note_type else ("", ())
        n, mean_tokens = self.conn.execute(f"SELECT COUNT(*), AVG(token_count) FROM note {where}", args).fetchone()
        rejections = dict(
            self.conn.execute(f"SELECT reason, COUNT(*) FROM rejection {where} GROUP BY reason", args).fetchall()
        )
        n_rej = sum(rejections.values())
        sources = self.conn.execute(f"SELECT COUNT(*) FROM source {where}", args).fetchone()[0]
        return {
            "note_type": note_type,
            "notes": int(n),
            "sources": int(sources),
            "mean_note_tokens": float(mean_tokens or 0.0),
            "rejections": rejections,
            "ingestion_yield": (n / (n + n_rej)) if (n + n_rej) else None,
            "file_bytes": self.path.stat().st_size if self.path.exists() else 0,
            "vector_backend": "sqlite-vec" if self.use_vec else "numpy-exact",
        }


def _cosine(a: np.ndarray, b: np.ndarray) -> float:
    na, nb = float(np.linalg.norm(a)), float(np.linalg.norm(b))
    if na == 0 or nb == 0:
        return 0.0
    return float(np.dot(a, b) / (na * nb))

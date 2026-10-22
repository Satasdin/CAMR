"""Experts (camr.memory.store, MemoryEngine.recall/route): closed partitions of memory, one per domain, opened by a
router like a mixture of experts' gate. An open expert's notes are searched; a closed one's are not read, so a
question about one project's code cannot be answered from another project's look-alike API."""

from __future__ import annotations

import datetime as dt

from camr.memory import HashingEmbedder, MemoryEngine, SQLiteVectorStore
from camr.memory.clock import LogicalClock
from camr.memory.note import Document
from camr.models.tokenizer import RegexTokenizer
from conftest import fixture_config

ACME = ["acme_pay ledger_open(account_code, currency='KES') opens an acme ledger for an account code",
        "acme_pay ledger_post(ledger, amount_cents, memo) posts an acme ledger entry in cents",
        "acme_pay ledger_settle(ledger, on) settles an acme ledger on a date"]
ZETA = ["zeta_pay open_ledger(code, currency) opens a zeta ledger for an account code",
        "zeta_pay post_entry(ledger, amount, memo) posts a zeta ledger entry in shillings",
        "zeta_pay settle_ledger(ledger, date) settles a zeta ledger on a date"]
SHARED = ["My accountant is Wanjiru and she prefers invoices in KES"]


def engine(tmp_path, experts: bool = True) -> MemoryEngine:
    emb = HashingEmbedder(256)
    store = SQLiteVectorStore(tmp_path / "m.sqlite", dim=emb.dim, embedder_name=emb.name, use_vec=False)
    cfg = fixture_config(tmp_path, min_similarity=0.05, similarity_margin=0.5, token_budget=384)
    eng = MemoryEngine.from_config(cfg, store=store, embedder=emb, tokenizer=RegexTokenizer())
    eng.clock = LogicalClock(dt.datetime(2026, 10, 22, 12, tzinfo=dt.timezone.utc), step_hours=0)
    docs = ([Document("code", f"acme-{i}", t) for i, t in enumerate(ACME)]
            + [Document("code", f"zeta-{i}", t) for i, t in enumerate(ZETA)]
            + [Document("note", f"me-{i}", t) for i, t in enumerate(SHARED)])
    eng.ingest(docs)
    if experts:
        src = dict(store.conn.execute("SELECT doc_id, source_id FROM source"))
        store.set_expert([v for k, v in src.items() if k.startswith("acme")], "code:acme")
        store.set_expert([v for k, v in src.items() if k.startswith("zeta")], "code:zeta")
    return eng


def texts(r) -> list[str]:
    return [c.note.text for c in r.candidates if c.admitted]


def test_the_router_opens_the_expert_a_question_is_about(tmp_path):
    eng = engine(tmp_path)
    assert eng.store.experts() == {"code:acme": 3, "code:zeta": 3}
    assert eng.route("how do I post an acme_pay ledger entry in cents", top=1)[0][0] == "code:acme"
    assert eng.route("zeta_pay post_entry for a zeta ledger", top=1)[0][0] == "code:zeta"


def test_a_closed_expert_is_not_read_and_shared_memory_stays_open(tmp_path):
    eng = engine(tmp_path)
    q = "write code that opens a ledger, posts an entry and settles it, for my accountant"
    everything = texts(eng.recall(q))
    assert any("zeta" in t for t in everything) and any("acme" in t for t in everything)
    acme = texts(eng.recall(q, experts=["code:acme"]))
    assert acme and not any("zeta" in t for t in acme)  # the look-alike API is closed off
    assert any("Wanjiru" in t for t in eng.recall("who is my accountant", experts=["code:acme"]).candidates
               for t in [t.note.text])  # shared memory is always open


def test_a_store_without_experts_is_unchanged(tmp_path):
    eng = engine(tmp_path, experts=False)
    cols = {r[1] for r in eng.store.conn.execute("PRAGMA table_info(source)")}
    q = "post a ledger entry"
    assert eng.route(q) == [] and texts(eng.recall(q, experts=["code:acme"])) == texts(eng.recall(q))
    assert "expert" not in cols and "expert" not in {r[1] for r in eng.store.conn.execute("PRAGMA table_info(source)")}

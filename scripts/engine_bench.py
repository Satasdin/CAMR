"""Engine bench: score CAMR's read path on ten memory abilities (A1-A10), with no model in the loop.

The read path under test is exactly the one CAMR Personal builds (``camr.app.assistant.Assistant``: verbatim notes
of 120 tokens, similarity ranking, abstain below 0.50, admit within 0.15 of the best, entity gate, entity
bridging, 20 keyword hits, k 20, 384-token budget), with the BGE embedder. Each question is scored from what that
read path admits into the context (``camr.eval.abilities``): did every needed fact get there, what share of the
context is something else, how many tokens, how long it took, and whether memory abstained.

    python scripts/engine_bench.py fetch     # LongMemEval (pinned revision), sha256 checked
    python scripts/engine_bench.py prepare   # stratified subsample (fixed seed) and the filler for the needle stores
    python scripts/engine_bench.py embed     # BGE vectors of every note, cached on disk (resumable)
    python scripts/engine_bench.py run       # every suite; questions already scored are skipped (resumable)
    python scripts/engine_bench.py report    # results/bench/scorecard.md and scorecard.json
    python scripts/engine_bench.py all       # the five in order

The 1M-note store needs more filler than LongMemEval S holds: ``fetch --with-m`` (2.7 GB), ``prepare-m``, then
``embed --scales 1000000`` and ``run --only scale --scales 1000000``.

Large files (the dataset, the vector cache, the needle stores) live in ``$CAMR_BENCH_HOME`` (default
``~/.cache/camr-bench``), outside the repository; scores go to ``results/bench/``.
"""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import platform
import resource
import shutil
import statistics
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = Path(os.environ.get("CAMR_BENCH_OUT", ROOT / "results" / "bench")).expanduser()  # scores of this run
RECORDS = OUT / "records"
FIXTURE = ROOT / "tests" / "fixtures" / "engine_bench" / "camr_scenarios.json"
WORK = Path(os.environ.get("CAMR_BENCH_HOME", Path.home() / ".cache" / "camr-bench")).expanduser()
LME_DIR = WORK / "longmemeval"
CACHE = WORK / "embeddings.sqlite"
SUBSET = WORK / "lme_subset.jsonl"
FILLER = WORK / "filler.jsonl"
# Per-checkout scratch: two worktrees running the bench at once each set their own (the vector cache is shared).
STORES = Path(os.environ.get("CAMR_BENCH_STORES", WORK / "stores")).expanduser()
TMP = Path(os.environ.get("CAMR_BENCH_TMP", WORK / "tmp")).expanduser()
TODAY = "2026-10-21"  # the CAMR scenarios' "today"

SEED = 13
PER_TYPE = 40  # LongMemEval questions per type (all 30 abstention questions are kept)
SCALES = (1_000, 10_000, 100_000)
RSS_LIMIT_MB = 8192
P95_LIMIT_MS = 500.0  # A9: an interactive lookup
RECALL_DROP = 0.10    # A9: needle recall may fall at most this far below the 1k store's

LME_REPO = "xiaowu0162/longmemeval-cleaned"
LME_REVISION = "98d7416c24c778c2fee6e6f3006e7a073259d48f"
LME_FILES = {
    "longmemeval_s_cleaned.json": "d6f21ea9d60a0d56f34a05b609c79c88a451d2ae03597821ea3d5a9678c3a442",
    "longmemeval_oracle.json": "821a2034d219ab45846873dd14c14f12cfe7776e73527a483f9dac095d38620c",
}
LME_VARIANT = "longmemeval_s_cleaned.json"  # S: each question's history is ~50 sessions, mostly unrelated chat
# M (~500 sessions per question, 2.7 GB): fetched only with --with-m, as extra filler for the 1M-note store.
LME_M = "longmemeval_m_cleaned.json"
LME_M_SHA256 = "9d79e5524794a2e6900a3aa9cb7d9152c5a3e8319c9a87c25494ba1eacee495f"
FILLER_M = WORK / "filler_m.jsonl"

# What A8 wires in from the app's own test suite (forget and privacy).
A8_TESTS = [
    "tests/test_app.py::test_forget_removes_notes_and_vectors",
    "tests/test_app.py::test_teaching_an_edited_file_replaces_the_old_version",
    "tests/test_app.py::test_thumbs_down_takes_back_an_approval",
    "tests/test_app_learning.py::test_a_personal_question_is_never_looked_up_and_asks_to_be_taught",
    "tests/test_app_learning.py::test_what_counts_as_a_question_about_the_user",
    "tests/test_app_learning.py::test_personal_questions_without_a_pronoun_never_leave_the_machine",
    "tests/test_app_learning.py::test_a_name_only_the_users_notes_mention_is_never_sent",
    "tests/test_app_learning.py::test_learning_online_can_be_turned_off",
    "tests/test_app_server.py::test_refuses_foreign_hosts_and_cross_site_posts",
]

BGE = "BAAI/bge-small-en-v1.5"
# CPU threads for BGE (and OpenMP): the bench shares the machine with other jobs (CAMR_BENCH_THREADS to change).
THREADS = int(os.environ.get("CAMR_BENCH_THREADS", "4"))


def say(*parts) -> None:
    print(time.strftime("%H:%M:%S"), *parts, flush=True)


def peak_rss_mb() -> float:
    r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
    return round(r / 2**20 if sys.platform == "darwin" else r / 1024, 1)


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def read_jsonl(path: Path):
    if path.exists():
        with open(path) as f:
            for line in f:
                if line.strip():
                    yield json.loads(line)


def append_jsonl(path: Path, row: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "a") as f:
        f.write(json.dumps(row) + "\n")


# ---------------------------------------------------------------------- the read path under test
def make_embedder():
    """BGE-small as CAMR Personal would run it, with passage vectors cached on disk.

    Questions are embedded on the CPU every time, so ``retrieval_ms`` is what the app would see. Passages are
    embedded once and read back from the cache (on Apple's GPU when there is one: the same vectors to 2e-7 in
    cosine, about 2.6 times faster than the CPU), so a rerun or a second suite never embeds a note twice."""
    from camr.config import EmbedderConfig
    from camr.memory.embedder import BGEEmbedder, CachedEmbedder, Embedder

    class LazyBGE(Embedder):
        def __init__(self, device: str):
            self.name, self.dim, self.device, self._model = BGE, 384, device, None

        def encode(self, texts, *, is_query=False):
            if self._model is None:
                self._model = BGEEmbedder(EmbedderConfig(device=self.device, batch_size=64, torch_threads=THREADS))
            return self._model.encode(texts, is_query=is_query)

    class BenchEmbedder(Embedder):
        def __init__(self):
            self.query_model = BGEEmbedder(EmbedderConfig(torch_threads=THREADS))
            self.query_model.encode(["warm up"], is_query=True)  # the first call is slow; no question should pay it
            self.name, self.dim = self.query_model.name, self.query_model.dim
            try:
                import torch

                device = "mps" if torch.backends.mps.is_available() else "cpu"
            except Exception:  # noqa: BLE001
                device = "cpu"
            self.passage_device = device
            self.passages = CachedEmbedder(LazyBGE(device), CACHE)

        def encode(self, texts, *, is_query=False):
            if is_query:
                return self.query_model.encode(texts, is_query=True)
            return self.passages.encode(texts)

        def missing(self, texts: list[str]) -> list[str]:
            keys = {self.passages._key(t, False): t for t in texts}
            have: set[str] = set()
            ks = list(keys)
            for i in range(0, len(ks), 500):
                part = ks[i:i + 500]
                have |= {r[0] for r in self.passages._conn.execute(
                    f"SELECT key FROM vec WHERE key IN ({','.join('?' * len(part))})", part)}
            return [t for k, t in keys.items() if k not in have]

    return BenchEmbedder()


class NoNetwork:
    """A session that refuses every request: the engine bench never calls a model or the web."""

    headers: dict = {}

    def get(self, *a, **k):
        raise RuntimeError("the engine bench does not use the network")

    post = get


def make_assistant(home: Path, emb, **kw):
    """CAMR Personal itself, on a fresh or existing home folder: its engine is the read path under test."""
    from camr.app.assistant import Assistant
    from camr.memory.fetch import WebLookup

    home.mkdir(parents=True, exist_ok=True)
    settings = home / "settings.json"
    if not settings.exists():
        settings.write_text(json.dumps({"learn_online": False, "sleep_when_idle": False, "remember_chat": False}))
    if "session" not in kw:
        kw["session"] = NoNetwork()
    if "web_lookup" not in kw:
        kw["web_lookup"] = WebLookup(NoNetwork(), offline=True)
    return Assistant(home, embedder=emb, **kw)


def read_path(a) -> dict:
    m = a.cfg.memory
    return {"write_policy": m.write_policy, "chunk_tokens": m.chunk_tokens, "chunk_overlap": m.chunk_overlap,
            "retrieval_policy": m.retrieval_policy, "k": m.k, "keyword_k": m.keyword_k,
            "token_budget": a.engine.budgeter.budget, "min_similarity": a.engine.min_similarity,
            "similarity_margin": m.similarity_margin, "entity_gate": m.entity_gate, "expansion": m.expansion,
            "packing": m.packing, "embedder": a.embedder.name, "vector_backend": a.store.stats()["vector_backend"]}


def note_keys(engine, docs) -> dict[str, frozenset[str]]:
    """checksum of each note the documents become -> keys of the facts it came from."""
    from camr.memory.note import checksum

    out: dict[str, set[str]] = {}
    for key, doc in docs:
        for cand in engine.write_policy.distil(doc):
            if key:
                out.setdefault(checksum(cand.text.strip(), cand.note_type), set()).add(key)
    return {k: frozenset(v) for k, v in out.items()}


def ask(a, spec, keys: dict[str, frozenset[str]], preview: bool = False, capture: list | None = None) -> dict:
    """Score one question on the app's read path. ``capture`` (a list) receives the RecallResult."""
    from camr.eval.abilities import Cand, score

    r = a.engine.recall(spec.question)
    if capture is not None:
        capture.append(r)
    cands = [Cand(keys=keys.get(c.note.checksum, frozenset()), tokens=c.tokens, text=c.note.text,
                  similarity=c.similarity, rank=c.rank, eligible=c.eligible, admitted=c.admitted,
                  via_bridge=c.via is not None) for c in r.candidates]
    rec = score(spec, cands, abstained=r.abstained, retrieval_ms=r.retrieval_ms, top_similarity=r.top_similarity,
                min_similarity=a.engine.min_similarity)
    if preview:
        rec["context"] = [{"keys": sorted(c.keys), "sim": round(c.similarity, 3), "text": c.text[:160]}
                          for c in cands if c.admitted]
    return rec


# ---------------------------------------------------------------------- LongMemEval
def lme_docs(item: dict):
    """A question's chat history as CAMR chat memory: one note source per turn, oldest session first, each
    "On <date> the user|assistant said: <turn>" (the app keeps what the user says this way). Every turn is
    stored, questions and assistant replies too, so the bench measures the read path, not the app's choice of
    what to keep."""
    from camr.eval.abilities import lme_date, turn_key
    from camr.memory.note import Document

    ids, dates, sessions = item["haystack_session_ids"], item["haystack_dates"], item["haystack_sessions"]
    for i in sorted(range(len(ids)), key=lambda i: (dates[i], i)):
        day = lme_date(dates[i])
        for j, t in enumerate(sessions[i]):
            text = (t.get("content") or "").strip()
            if text:
                key = turn_key(ids[i], j)
                yield key, Document("chat", key, f"On {day} the {t['role']} said: {text}")


def cmd_fetch(a) -> None:
    import requests

    LME_DIR.mkdir(parents=True, exist_ok=True)
    for name, digest in {**LME_FILES, **({LME_M: LME_M_SHA256} if a.with_m else {})}.items():
        path = LME_DIR / name
        if path.exists() and sha256(path) == digest:
            say("ok", path)
            continue
        url = f"https://huggingface.co/datasets/{LME_REPO}/resolve/{LME_REVISION}/{name}"
        say("downloading", url)
        tmp = path.with_suffix(".part")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            with open(tmp, "wb") as f:
                for block in r.iter_content(1 << 20):
                    f.write(block)
        got = sha256(tmp)
        if got != digest:
            raise SystemExit(f"{name}: sha256 {got} != expected {digest}")
        tmp.replace(path)
    os.environ.pop("HF_HUB_OFFLINE", None)
    from sentence_transformers import SentenceTransformer  # make sure BGE is in the local cache

    SentenceTransformer(BGE, device="cpu")
    say("BGE cached")


def cmd_prepare(a) -> None:
    from camr.eval.abilities import stratified_sample

    src = LME_DIR / LME_VARIANT
    if not src.exists():
        raise SystemExit("run `engine_bench.py fetch` first")
    say("loading", src.name)
    items = json.loads(src.read_text())
    group = (lambda x: "abstention" if x["question_id"].endswith("_abs") else x["question_type"])
    subset = stratified_sample(items, group, a.per_type, a.seed)
    WORK.mkdir(parents=True, exist_ok=True)
    with open(SUBSET, "w") as f:
        for x in subset:
            f.write(json.dumps(x) + "\n")
    # Filler for the needle stores: sessions of the sampled questions' histories that are nobody's evidence,
    # shuffled with the seed (their vectors are needed for the LongMemEval suites anyway).
    evidence = {sid for x in items for sid in x["answer_session_ids"]}
    seen: dict[str, dict] = {}
    for x in subset:
        for sid, day, turns in zip(x["haystack_session_ids"], x["haystack_dates"], x["haystack_sessions"]):
            if sid not in evidence and sid not in seen:
                seen[sid] = {"sid": sid, "date": day, "turns": [{"role": t["role"], "content": t["content"]}
                                                                for t in turns]}
    order = sorted(seen)
    import random

    random.Random(a.seed).shuffle(order)
    with open(FILLER, "w") as f:
        for sid in order:
            f.write(json.dumps(seen[sid]) + "\n")
    counts: dict[str, int] = {}
    for x in subset:
        counts[group(x)] = counts.get(group(x), 0) + 1
    meta = {"source": src.name, "sha256": LME_FILES[LME_VARIANT], "questions_in_source": len(items),
            "seed": a.seed, "per_type": a.per_type, "sampled": len(subset), "by_type": counts,
            "filler_sessions": len(order)}
    (WORK / "prepare.json").write_text(json.dumps(meta, indent=1))
    say("prepared", json.dumps(meta))


def iter_json_array(path: Path, chunk: int = 1 << 22):
    """The objects of a top-level JSON array, one at a time: LongMemEval M (2.7 GB) never sits in memory whole."""
    dec = json.JSONDecoder()
    with open(path, encoding="utf-8") as f:
        buf = f.read(chunk).lstrip()
        if not buf.startswith("["):
            raise ValueError(f"{path} is not a JSON array")
        buf = buf[1:]
        while True:
            buf = buf.lstrip().lstrip(",").lstrip()
            if buf.startswith("]"):
                return
            try:
                obj, end = dec.raw_decode(buf)
            except json.JSONDecodeError:
                more = f.read(chunk)
                if not more:
                    raise
                buf += more
                continue
            yield obj
            buf = buf[end:]


def cmd_prepare_m(a) -> None:
    """Extra filler from LongMemEval M for the 1M-note store: history sessions that are no question's evidence and
    not already in the S filler, in file order, until they make about ``--m-notes`` notes."""
    src = LME_DIR / LME_M
    if not src.exists():
        raise SystemExit("run `engine_bench.py fetch --with-m` first")
    say("pass 1: evidence sessions in", src.name)
    evidence = {sid for x in iter_json_array(src) for sid in x["answer_session_ids"]}
    evidence |= {sid for x in read_jsonl(SUBSET) for sid in x["answer_session_ids"]}
    taken = {s["sid"] for s in read_jsonl(FILLER)}
    say(f"pass 2: sessions ({len(evidence)} evidence sessions, {len(taken)} already in the S filler)")
    est, n = 0, 0
    tmp = FILLER_M.with_suffix(".part")
    with open(tmp, "w") as f:
        for x in iter_json_array(src):
            for sid, day, turns in zip(x["haystack_session_ids"], x["haystack_dates"], x["haystack_sessions"]):
                if sid in evidence or sid in taken:
                    continue
                taken.add(sid)
                f.write(json.dumps({"sid": sid, "date": day, "turns": [{"role": t["role"], "content": t["content"]}
                                                                       for t in turns]}) + "\n")
                n += 1
                est += sum(max(1, -(-(len(t["content"].split()) * 5 // 4 - 16) // 104)) for t in turns)
            if est >= a.m_notes:
                break
    tmp.replace(FILLER_M)
    meta = json.loads((WORK / "prepare.json").read_text()) if (WORK / "prepare.json").exists() else {}
    meta.update({"filler_m_source": src.name, "filler_m_sha256": LME_M_SHA256, "filler_m_sessions": n,
                 "filler_m_notes_estimate": est})
    (WORK / "prepare.json").write_text(json.dumps(meta, indent=1))
    say(f"wrote {n} sessions (about {est} notes) to {FILLER_M.name}")


def filler_docs(engine, n_notes: int, made: list | None = None):
    """The filler documents that make ``n_notes`` notes once screened, in a fixed order (the S filler, then the M
    filler when there is one), so every store size is a prefix of the next. ``made[0]`` gets the notes made."""
    from camr.eval.abilities import lme_date
    from camr.memory.note import Document

    seen: set[str] = set()
    count = 0
    for path in (FILLER, FILLER_M):
        for s in read_jsonl(path):
            day = lme_date(s["date"])
            for j, t in enumerate(s["turns"]):
                text = (t.get("content") or "").strip()
                if not text:
                    continue
                doc = Document("chat", f"{s['sid']}#{j}", f"On {day} the {t['role']} said: {text}")
                for cand in engine.write_policy.distil(doc):
                    v = engine.screener.screen(cand, seen)
                    if v.accepted:
                        seen.add(v.checksum)
                        count += 1
                yield doc
                if count >= n_notes:
                    if made is not None:
                        made[:] = [count]
                    return
    if made is not None:
        made[:] = [count]


def filler_capacity(engine, n_notes: int) -> int:
    made = [0]
    for _ in filler_docs(engine, n_notes, made):
        pass
    return made[0]


def cmd_embed(a) -> None:
    """Vectors for every note the suites will store, in chunks (resumable: what is cached is skipped)."""
    emb = make_embedder()
    probe = make_assistant(TMP / "embed-probe", emb)
    eng = probe.engine

    def texts():
        for item in read_jsonl(SUBSET):
            for _, doc in lme_docs(item):
                yield from (c.text.strip() for c in eng.write_policy.distil(doc))
        for doc in filler_docs(eng, max(a.scales) - 25):
            yield from (c.text.strip() for c in eng.write_policy.distil(doc))

    t0, seen_n, done = time.time(), 0, 0

    def flush(batch):
        nonlocal done
        todo = sorted(emb.missing([t for t in dict.fromkeys(batch) if t]), key=len)  # similar lengths batch well
        for i in range(0, len(todo), 2048):
            emb.passages.encode(todo[i:i + 2048])
            done += len(todo[i:i + 2048])
            say(f"embedded {done} new notes ({done / (time.time() - t0):.0f}/s), {seen_n} notes looked at")

    batch: list[str] = []
    for t in texts():
        batch.append(t)
        seen_n += 1
        if len(batch) >= 50_000:
            flush(batch)
            batch = []
    flush(batch)
    say(f"done: {seen_n} notes looked at, {done} embedded on {emb.passage_device}")
    probe.close()
    shutil.rmtree(TMP / "embed-probe", ignore_errors=True)


def context_row(spec, recall, qtype: str, question_date: str, answer) -> dict:
    """What a reader model gets for one question: the exact notes text the app puts in its prompt."""
    return {"qid": spec.qid, "ability": spec.ability, "suite": spec.suite, "type": qtype, "question": spec.question,
            "question_date": question_date, "answer": str(answer), "context": recall.context,
            "abstained": bool(recall.abstained), "context_tokens": recall.context_tokens}


def run_lme(emb, limit: int | None = None, contexts: Path | None = None) -> None:
    """Score the sampled LongMemEval questions into records/lme.jsonl; with ``contexts``, write each question's
    context there instead (and leave the records alone)."""
    from camr.eval.abilities import lme_spec

    path = contexts or RECORDS / "lme.jsonl"
    done = set() if contexts else {r["qid"] for r in read_jsonl(path)}
    rows = list(read_jsonl(SUBSET))[:limit]
    t0, n = time.time(), 0
    for item in rows:
        if item["question_id"] in done:
            continue
        spec = lme_spec(item)
        home = TMP / f"lme-{item['question_id']}"
        shutil.rmtree(home, ignore_errors=True)
        asst = make_assistant(home, emb)
        docs = list(lme_docs(item))
        summary = asst.engine.ingest([d for _, d in docs])
        got: list = []
        rec = ask(asst, spec, note_keys(asst.engine, docs), capture=got)
        rec["notes_in_store"] = asst.store.count()
        rec["ingest_s"] = round(summary.elapsed_s, 2)
        asst.close()
        shutil.rmtree(home, ignore_errors=True)
        if contexts:
            append_jsonl(path, context_row(spec, got[0], item["question_type"], item["question_date"], item["answer"]))
        else:
            append_jsonl(path, rec)
        n += 1
        if n % 10 == 0:
            say(f"lme {n + len(done)}/{len(rows)}  ({(time.time() - t0) / n:.1f} s/question)")


# ---------------------------------------------------------------------- CAMR scenarios
def fixture() -> dict:
    return json.loads(FIXTURE.read_text())


def teach_item(asst, item: dict):
    """Teach a fixture note the way the app does; returns (key, Document) as it was stored."""
    from camr.memory.note import Document

    if item.get("kind") == "chat":
        text, kind = f"On {item['date']} the user said: {item['text']}", "chat"
    else:
        text, kind = item["text"], item.get("kind", "note")
    title = item.get("title", "")
    asst.teach(text, title=title, kind=kind, doc_id=item["key"])
    return item["key"], Document(kind, item["key"], text.strip(), title)


def base_store(emb, name: str, fx: dict):
    home = TMP / name
    shutil.rmtree(home, ignore_errors=True)
    asst = make_assistant(home, emb)
    docs = [teach_item(asst, {**b, "kind": "note"}) for b in fx["base_notes"]]
    return asst, docs


def run_camr(emb, contexts: list | None = None) -> list[dict]:
    """The CAMR scenario suites; ``contexts`` (a list) also receives each question's context row."""
    from camr.eval.abilities import Spec

    fx = fixture()
    out = []

    def probe(asst, spec, keys, qtype, answer):
        got: list = []
        rec = ask(asst, spec, keys, preview=True, capture=got)
        if contexts is not None:
            contexts.append(context_row(spec, got[0], qtype, TODAY, answer))
        return rec
    for sc in fx["scenarios"]:
        asst, docs = base_store(emb, f"camr-{sc['id']}", fx)
        docs += [teach_item(asst, t) for t in sc["teach"]]
        keys = note_keys(asst.engine, docs)
        for i, q in enumerate(sc["questions"]):
            spec = Spec(f"{sc['id']}-{i}", sc["ability"], "camr-brief" if sc["from_brief"] else "camr-extra", q["q"],
                        needed=[frozenset(g) for g in q.get("needed", [])], stale=frozenset(q.get("stale", [])),
                        out_of_window=frozenset(q.get("out_of_window", [])), rule=q["rule"],
                        meta={"probe": sc["id"], "from_brief": sc["from_brief"]})
            out.append(probe(asst, spec, keys, f"camr/{sc['id']}", q.get("answer", "")))
        asst.close()
    # A5: counting N logged runs
    cnt = fx["counting"]
    for n in cnt["sizes"]:
        asst, docs = base_store(emb, f"camr-count-{n}", fx)
        if n <= 7:
            days = [dt.date(2026, 10, 2 + 3 * i) for i in range(n)]
            question = cnt["question_small"]
        else:
            days = sorted(dt.date(2026, 10, 20) - dt.timedelta(days=2 * i) for i in range(n))
            question = cnt["question_large"]
        runs = []
        for i, day in enumerate(days):
            r, k, w = cnt["routes"][i % len(cnt["routes"])], cnt["distances_km"][(3 * i) % len(cnt["distances_km"])], \
                cnt["times"][(5 * i) % len(cnt["times"])]
            item = {"key": f"run-{i + 1:03d}", "kind": "chat", "date": day.isoformat(),
                    "text": f"I went running {w}, {k} km {r}."}
            runs.append(item["key"])
            docs.append(teach_item(asst, item))
        spec = Spec(f"count-{n}", "A5", f"camr-count-{n}", question, needed=[frozenset([k]) for k in runs],
                    rule="all", meta={"probe": cnt["id"], "from_brief": n == 7, "events": n})
        answer = cnt["answer_small"] if n <= 7 else cnt["answer_large"].format(n=n)
        out.append(probe(asst, spec, note_keys(asst.engine, docs), f"camr/{cnt['id']}", answer))
        asst.close()
    # A10: general questions asked of a store of personal notes only
    asst, docs = base_store(emb, "camr-general", fx)
    keys = note_keys(asst.engine, docs)
    for i, (q, gold) in enumerate(zip(fx["no_memory"]["general"], fx["no_memory"]["general_answers"])):
        out.append(probe(asst, Spec(f"general-{i:02d}", "A10", "general-on-personal", q, rule="no_harm"), keys,
                         "camr/general", gold))
    asst.close()
    for d in TMP.glob("camr-*"):
        shutil.rmtree(d, ignore_errors=True)
    return out


# ---------------------------------------------------------------------- A8: forget and privacy
class _Resp:
    def __init__(self, status=200, body=None, lines=None):
        self.status_code, self.body, self.lines = status, body, lines or []
        self.text, self.headers = json.dumps(body) if body is not None else "", {}

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def raise_for_status(self):
        pass

    def iter_lines(self):
        yield from self.lines

    def json(self):
        return self.body


class FakeModel:
    """Stands in for Ollama: every answer is "I don't know that yet." (A8 checks memory and the network)."""

    headers: dict = {}

    def get(self, url, **kw):
        return _Resp(body={"models": []})

    def post(self, url, json=None, stream=False, timeout=None):
        if not json.get("prompt"):
            return _Resp(body={"done": True})
        words = "I don't know that yet.".split(" ")
        lines = [__import__("json").dumps({"response": w + " ", "done": False}).encode() for w in words]
        return _Resp(lines=lines + [__import__("json").dumps({"response": "", "done": True}).encode()])


class CountingWeb:
    """Records every web request the assistant makes; answers each as a page that is not there."""

    def __init__(self):
        self.calls: list[str] = []
        self.headers: dict = {}

    def get(self, url, params=None, timeout=None):
        self.calls.append(url)
        return _Resp(404, body={})


def traces_in_file(store_path: Path, traces: list[str]) -> list[str]:
    found = []
    for p in (store_path, Path(f"{store_path}-wal"), Path(f"{store_path}-journal")):
        if p.exists():
            data = p.read_bytes()
            found += [f"{p.name}:{t}" for t in traces if t.encode() in data]
    return found


def run_a8(emb) -> list[dict]:
    from camr.memory.fetch import WebLookup

    fx = fixture()
    f = fx["forget"]
    out = []

    def check(name, suite, ok, detail=""):
        out.append({"qid": name, "ability": "A8", "suite": suite, "passed": bool(ok), "detail": detail})

    # 1. taught in the Memory panel, then forgotten
    home = TMP / "a8-forget"
    shutil.rmtree(home, ignore_errors=True)
    web = CountingWeb()
    asst = make_assistant(home, emb, model="tiny:1b", session=FakeModel(),
                          web_lookup=WebLookup(web, min_interval_s=0))
    for b in fx["base_notes"]:
        asst.teach(b["text"], title=b["title"], doc_id=b["key"])
    asst.teach(f["text"], kind="note", doc_id="pin-hint")
    sid = asst.store.conn.execute("SELECT source_id FROM source WHERE doc_id='pin-hint'").fetchone()[0]
    nids = [r[0] for r in asst.store.conn.execute("SELECT note_id FROM note WHERE source_id=?", (sid,))]
    before = traces_in_file(asst.store.path, f["traces"])
    removed = asst.forget(sid)
    c = asst.store.conn
    marks = ",".join("?" * len(nids))
    rows = {
        "note": c.execute("SELECT COUNT(*) FROM note WHERE text LIKE '%Kisumu%'").fetchone()[0],
        "source": c.execute("SELECT COUNT(*) FROM source WHERE source_id=?", (sid,)).fetchone()[0],
        "rejection": c.execute("SELECT COUNT(*) FROM rejection WHERE text LIKE '%Kisumu%'").fetchone()[0],
        "note_embedding": c.execute(f"SELECT COUNT(*) FROM note_embedding WHERE note_id IN ({marks})",
                                    nids).fetchone()[0],
    }
    if asst.store.use_vec:
        rows["note_vec"] = c.execute(f"SELECT COUNT(*) FROM note_vec WHERE rowid IN ({marks})", nids).fetchone()[0]
    check("forget: rows", "forget", removed >= 1 and not any(rows.values()),
          f"{removed} note(s) removed; rows left {rows}; before forgetting the file held {len(before)} trace(s)")
    fts = c.execute("SELECT COUNT(*) FROM note_fts WHERE note_fts MATCH 'kisumu'").fetchone()[0]
    check("forget: keyword index", "forget", fts == 0, f"{fts} keyword hit(s) for 'kisumu'")
    left = traces_in_file(asst.store.path, f["traces"])
    check("forget: file bytes", "forget", not left, f"traces left: {left}" if left else "no trace in the file")
    r = asst.engine.recall("What is my bank PIN hint?")
    hit = [x.note.text for x in r.admitted if "Kisumu" in x.note.text]
    check("forget: recall", "forget", not hit, f"{len(r.admitted)} note(s) admitted, {len(hit)} about it")
    # 2. said in chat ("remember that ..."), forgotten, and its chat deleted
    turn = asst.ask(f"remember that {f['text'][0].lower()}{f['text'][1:]}")
    sid2 = c.execute("SELECT source_id FROM source WHERE dataset='note' AND doc_id LIKE 'note-%'"
                     " ORDER BY source_id DESC LIMIT 1").fetchone()[0]  # what "remember that ..." stored
    asst.forget(sid2)
    after_forget = traces_in_file(asst.store.path, f["traces"])
    asst.delete_conversation(turn.conversation_id)
    left2 = traces_in_file(asst.store.path, f["traces"])
    check("forget: said in chat, then chat deleted", "forget", not left2,
          f"after forget only: {after_forget or 'none'}; after deleting the chat too: {left2 or 'none'}")
    # 3. personal questions never reach the web (lookups on), and a general one does (the counter works)
    asst.save_settings(learn_online=True)
    sent = {}
    for q in f["personal_questions"]:
        n0 = len(web.calls)
        asst.ask(q)
        sent[q] = len(web.calls) - n0
    check("privacy: personal questions stay local", "privacy", not any(sent.values()),
          f"{sum(sent.values())} web request(s) for {len(sent)} personal questions"
          + ("; sent: " + ", ".join(q for q, v in sent.items() if v) if any(sent.values()) else ""))
    n0 = len(web.calls)
    asst.ask(f["control_question"])
    check("privacy: control (a general question is looked up)", "privacy", len(web.calls) > n0,
          f"{len(web.calls) - n0} request(s) for {f['control_question']!r}")
    asst.close()
    shutil.rmtree(home, ignore_errors=True)
    # 4. the app's own forget and privacy tests
    proc = subprocess.run([sys.executable, "-m", "pytest", "-q", "-rA", "-p", "no:cacheprovider", *A8_TESTS],
                          cwd=ROOT, capture_output=True, text=True, env={**os.environ, "CAMR_OFFLINE_WEB": "1"})
    status = {}
    for line in proc.stdout.splitlines():
        parts = line.split(" ", 1)
        if parts[0] in ("PASSED", "FAILED", "ERROR") and len(parts) == 2:
            status[parts[1].split(" - ")[0].strip()] = parts[0]
    for t in A8_TESTS:
        check(f"unit test: {t.split('::')[1]}", "app-tests", status.get(t) == "PASSED", status.get(t, "not run"))
    return out


# ---------------------------------------------------------------------- A1 needles and A9 scale
def scale_label(n: int) -> str:
    return f"{n // 1_000_000}M" if n >= 1_000_000 else f"{n // 1000}k"


def cmd_scale(a) -> None:
    """One store size, in its own process so its peak RSS is its own (``--phase build`` or ``query``)."""
    from camr.eval.abilities import Spec
    from camr.memory.entities import question_entities
    from camr.memory.note import Document

    n, label = a.notes, scale_label(a.notes)
    emb = make_embedder()
    home = STORES / f"needle-{label}"
    fx = fixture()
    needles = fx["needles"]["items"]
    ndocs = [(it["key"], Document("note", f"needle-{it['key']}", it["text"])) for it in needles]
    result: dict = {"notes_target": n}
    if a.phase == "build":
        marker = home / "complete.json"
        if marker.exists():
            result = json.loads(marker.read_text())
        else:
            asst = make_assistant(home, emb)
            want = n - len(needles)
            have = filler_capacity(asst.engine, want)
            if have < want:  # never label a smaller store with the size asked for
                asst.close()
                raise SystemExit(f"the filler makes only {have} notes, short of {want}: a {label} store needs "
                                 "more filler (`engine_bench.py fetch --with-m` then `prepare-m`)")
            t0 = time.time()

            def stream():
                for i, d in enumerate(filler_docs(asst.engine, want)):
                    if i and i % 50000 == 0:
                        say(f"  {label}: {i} documents, {asst.store.count()} notes, {time.time() - t0:.0f} s")
                    yield d
            asst.engine.ingest(stream())
            for key, doc in ndocs:
                asst.teach(doc.text, kind="note", doc_id=doc.doc_id)
            result = {"notes_target": n, "notes": asst.store.count(), "build_s": round(time.time() - t0, 1),
                      "build_peak_rss_mb": peak_rss_mb(), "store_mb": round(asst.store.path.stat().st_size / 1e6, 1)}
            asst.close()
            marker.write_text(json.dumps(result))
    else:
        asst = make_assistant(home, emb)
        keys = note_keys(asst.engine, ndocs)
        for q in ("What is on my calendar?", "Where did I put the keys?", "What did I eat yesterday?"):
            asst.engine.recall(q)  # warm-up: first calls load caches
        recs, ms = [], []
        for rep in range(a.repeats):
            for it in needles:
                spec = Spec(f"needle-{label}-{it['key']}", "A1", f"needle-{label}", it["q"],
                            needed=[frozenset([it["key"]])], rule="all")
                rec = ask(asst, spec, keys)
                ms.append(rec["retrieval_ms"])
                if rep == 0:
                    recs.append(rec)
            for i, q in enumerate(fx["no_memory"]["absent"]):
                spec = Spec(f"absent-{label}-{i:02d}", "A10", f"absent-{label}", q, rule="no_harm")
                rec = ask(asst, spec, keys)
                ms.append(rec["retrieval_ms"])
                if rep == 0:
                    ents = question_entities(q)
                    rec["meta"] = {"entities": ents, "entities_in_store": [  # a name filler happens to mention
                        e for e in ents if asst.store.conn.execute(
                            "SELECT COUNT(*) FROM note_fts WHERE note_fts MATCH ?",
                            ('"' + e.replace('"', '') + '"',)).fetchone()[0]]}
                    recs.append(rec)
        result = {"notes": asst.store.count(), "queries": len(ms), "latency_median_ms": round(statistics.median(ms), 2),
                  "latency_p95_ms": round(sorted(ms)[int(0.95 * (len(ms) - 1))], 2),
                  "query_peak_rss_mb": peak_rss_mb(), "records": recs,
                  "store_mb": round(asst.store.path.stat().st_size / 1e6, 1)}
        asst.close()
    Path(a.out).write_text(json.dumps(result))


def run_scales(scales, repeats: int) -> None:
    path = RECORDS / "scale.jsonl"
    rows = list(read_jsonl(path))
    done = {r["qid"] for r in rows if r.get("ability") == "A9"}
    base_recall = next((r["needle_recall"] for r in rows if r.get("qid") == "scale-1k"), None)
    for n in sorted(scales):
        label = scale_label(n)
        if f"scale-{label}" in done:
            continue
        info = {}
        for phase in ("build", "query"):
            out = TMP / f"scale-{label}-{phase}.json"
            say(f"scale {label}: {phase}")
            subprocess.run([sys.executable, __file__, "scale", "--notes", str(n), "--phase", phase, "--out", str(out),
                            "--repeats", str(repeats)], check=True)
            info.update(json.loads(out.read_text()))
        recs = info.pop("records")
        for r in recs:
            append_jsonl(path, r)
        needle = [r for r in recs if r["ability"] == "A1"]
        recall = sum(r["passed"] for r in needle) / len(needle)
        if base_recall is None:
            base_recall = recall
        ok = (info["query_peak_rss_mb"] <= RSS_LIMIT_MB and info.get("build_peak_rss_mb", 0) <= RSS_LIMIT_MB
              and info["latency_p95_ms"] <= P95_LIMIT_MS and recall >= base_recall - RECALL_DROP)
        append_jsonl(path, {"qid": f"scale-{label}", "ability": "A9", "suite": f"scale-{label}", "passed": ok,
                            "needle_recall": round(recall, 4), "baseline_recall_1k": round(base_recall, 4), **info,
                            "retrieval_ms": info["latency_median_ms"]})
        say(f"scale {label}: {json.dumps({k: v for k, v in info.items()})} recall {recall:.2f}")


def cmd_contexts(a) -> None:
    """The exact context each LongMemEval question and CAMR probe gets, for reading by real models:
    results/bench/contexts_<label>.jsonl (scores are not touched)."""
    out = OUT / f"contexts_{a.label}.jsonl"
    out.unlink(missing_ok=True)
    emb = make_embedder()
    say("contexts: CAMR scenarios")
    rows: list[dict] = []
    run_camr(emb, contexts=rows)
    say("contexts: LongMemEval")
    run_lme(emb, a.limit, contexts=out)
    lme = list(read_jsonl(out))
    out.write_text("".join(json.dumps(r) + "\n" for r in lme + rows))
    say(f"wrote {len(lme) + len(rows)} contexts to {out}")


def cmd_run(a) -> None:
    only = set(a.only.split(",")) if a.only else {"camr", "a8", "lme", "scale"}
    RECORDS.mkdir(parents=True, exist_ok=True)
    if a.fresh:
        for s in only:
            (RECORDS / f"{s}.jsonl").unlink(missing_ok=True)
    emb = make_embedder() if only & {"camr", "a8", "lme"} else None
    if "camr" in only:
        say("CAMR scenarios")
        recs = run_camr(emb)
        (RECORDS / "camr.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    if "a8" in only:
        say("A8 forget and privacy")
        recs = run_a8(emb)
        (RECORDS / "a8.jsonl").write_text("".join(json.dumps(r) + "\n" for r in recs))
    if "lme" in only:
        say("LongMemEval")
        run_lme(emb, a.limit)
    if "scale" in only:
        run_scales(a.scales, a.repeats)
    meta = {"run_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "peak_rss_mb": peak_rss_mb()}
    if emb is not None:
        probe = make_assistant(TMP / "config-probe", emb)
        meta["read_path"] = read_path(probe)
        meta["passage_device"] = emb.passage_device
        probe.close()
        shutil.rmtree(TMP / "config-probe", ignore_errors=True)
    old = json.loads((RECORDS / "run.json").read_text()) if (RECORDS / "run.json").exists() else {}
    (RECORDS / "run.json").write_text(json.dumps({**old, **meta}, indent=1))


# ---------------------------------------------------------------------- report
def _f(x, pct=False, digits=2):
    if x is None:
        return "–"
    if pct:
        return f"{100 * x:.0f}%"
    return f"{x:.{digits}f}" if isinstance(x, float) else str(x)


def cmd_report(a) -> None:
    from camr.eval.abilities import ABILITIES, scorecard

    records = [r for p in sorted(RECORDS.glob("*.jsonl")) for r in read_jsonl(p)]
    if not records:
        raise SystemExit("no records: run `engine_bench.py run` first")
    card = scorecard(records)
    run = json.loads((RECORDS / "run.json").read_text()) if (RECORDS / "run.json").exists() else {}
    prep = json.loads((WORK / "prepare.json").read_text()) if (WORK / "prepare.json").exists() else {}
    commit = subprocess.run(["git", "describe", "--always", "--dirty"], cwd=ROOT, capture_output=True,
                            text=True).stdout.strip()
    meta = {"generated_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "commit": commit,
            "machine": f"{platform.machine()} {platform.system()} {platform.release()}, {os.cpu_count()} CPUs",
            "read_path": run.get("read_path"), "passage_device": run.get("passage_device"),
            "longmemeval": {"repo": LME_REPO, "revision": LME_REVISION, "file": LME_VARIANT,
                            "sha256": LME_FILES[LME_VARIANT], **{k: v for k, v in prep.items() if k != "sha256"}},
            "rules": {"A9": f"peak RSS <= {RSS_LIMIT_MB} MB, p95 retrieval <= {P95_LIMIT_MS:.0f} ms, needle recall "
                            f"no more than {RECALL_DROP:.0%} below the 1k store"}}
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "scorecard.json").write_text(json.dumps({"meta": meta, "abilities": card}, indent=1))

    L = ["# CAMR engine bench: scorecard", "",
         f"Generated {meta['generated_at']} from commit `{commit}` by `scripts/engine_bench.py` "
         f"(records in `results/bench/records/`). Model-free: each question is scored from what CAMR Personal's "
         f"read path admitted into the context. Machine: {meta['machine']}.", "",
         "## Per ability", "",
         "| | Ability | n | Pass (95% CI) | All-needed recall | Distractor share | Context tokens | "
         "Retrieval ms p50 / p95 | Abstained |", "|---|---|---|---|---|---|---|---|---|"]
    for ab, s in card.items():
        ci = s["ci95"]
        L.append(f"| {ab} | {ABILITIES[ab]} | {s['n']} | {_f(s['pass_rate'], True)}"
                 + (f" ({ci[0] * 100:.0f}–{ci[1] * 100:.0f})" if ci else "")
                 + f" | {_f(s['all_needed_recall'], True)} | {_f(s['distractor_share'], True)} | "
                 f"{_f(s['context_tokens'], digits=0)} | {_f(s['retrieval_ms_median'], digits=1)} / "
                 f"{_f(s['retrieval_ms_p95'], digits=1)} | {_f(s['abstain_rate'], True)} |")
    L += ["", "Pass rules (camr/eval/abilities.py): A1, A2, A5, A6 every needed fact reached the context; A3 the newest "
          "value did, and a superseded value next to it can be told apart (dates, or the newest says it is an update); "
          "A4 every needed fact did in a note that shows its date, and nothing from outside the period asked about "
          "(the app's prompt does not give the model today's date); A7 memory abstained; A8 each forget or privacy "
          "check held; A9 " + meta["rules"]["A9"] + "; A10 nothing was admitted for a question memory has nothing for "
          "(A7's questions included).", "",
          "## By suite", "",
          "| Ability | Suite | n | Pass | All-needed | Distractor | Tokens | ms p50 / p95 | Abstained | Why needed facts were missed |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for ab, s in card.items():
        for su, t in s["suites"].items():
            miss = ", ".join(f"{k} {v}" for k, v in (t.get("misses") or {}).items()) or "–"
            L.append(f"| {ab} | {su} | {t['n']} | {_f(t['pass_rate'], True)} | {_f(t['all_needed_recall'], True)} | "
                     f"{_f(t['distractor_share'], True)} | {_f(t['context_tokens'], digits=0)} | "
                     f"{_f(t['retrieval_ms_median'], digits=1)} / {_f(t['retrieval_ms_p95'], digits=1)} | "
                     f"{_f(t['abstain_rate'], True)} | {miss} |")
    probes = [r for r in records if (r.get("meta") or {}).get("probe")]
    if probes:
        L += ["", "## CAMR probes", "", "From the brief unless marked *extra*. Context = what reached the model, "
              "with each note's similarity.", "", "| Probe | Ability | Question | Pass | Context |", "|---|---|---|---|---|"]
        for r in probes:
            ctx = "; ".join(f"[{c['sim']}] {c['text'][:90]}" for c in r.get("context", [])) or \
                ("(abstained)" if r["abstained"] else "(empty)")
            if len(r.get("context", [])) > 4:
                ctx = f"{len(r['context'])} notes; " + "; ".join(f"[{c['sim']}] {c['text'][:50]}" for c in r["context"][:3]) + " …"
            if r.get("needed", 0) > 1:
                ctx = f"{r['reached']} of {r['needed']} reached; " + ctx
            name = r["meta"]["probe"] + ("" if r["meta"].get("from_brief") else " *extra*")
            why = f" ({', '.join(sorted(set(r['misses'])))})" if r.get("misses") else ""
            L.append(f"| {name} | {r['ability']} | {r['question']} | {'yes' if r['passed'] else 'no' + why} | "
                     f"{ctx.replace('|', '/')} |")
    a8 = [r for r in records if r.get("ability") == "A8"]
    if a8:
        L += ["", "## A8 forget and privacy", "", "| Check | Pass | Detail |", "|---|---|---|"]
        L += [f"| {r['qid']} | {'yes' if r['passed'] else 'no'} | {str(r.get('detail', '')).replace('|', '/')} |"
              for r in a8]
    a9 = sorted((r for r in records if r.get("ability") == "A9"), key=lambda r: r.get("notes", 0))
    if a9:
        L += ["", "## A9 scale", "", "Needle questions (A1) and absent-entity questions (A10) on stores of LongMemEval "
              "chat turns plus 25 taught facts. Each size is built and queried in its own process; peak RSS includes "
              "the BGE model (about 0.5 GB).", "",
              "| Notes | Store MB | Build s | Peak RSS build MB | Peak RSS query MB | Retrieval ms p50 / p95 | "
              "Needle recall | Pass |", "|---|---|---|---|---|---|---|---|"]
        for r in a9:
            L.append(f"| {r.get('notes')} | {r.get('store_mb')} | {r.get('build_s', '–')} | "
                     f"{r.get('build_peak_rss_mb', '–')} | {r.get('query_peak_rss_mb')} | {r.get('latency_median_ms')} / "
                     f"{r.get('latency_p95_ms')} | {_f(r.get('needle_recall'), True)} | {'yes' if r['passed'] else 'no'} |")
        if max(r.get("notes", 0) for r in a9) >= 1_000_000:
            L += ["", "The 1M store continues the S filler with LongMemEval M sessions (`prepare-m`). Its retrieval is "
                  "disk-bound on this machine: sqlite-vec reads every vector, and the 4.7 GB store did not fit the "
                  "page cache under the memory pressure of the time, so its latency is an upper bound; peak RSS "
                  "stays near 0.6 GB."]
        if max(r.get("notes", 0) for r in a9) < 1_000_000:
            L += ["", "1M notes was not run: the store would need about 4.7 GB of disk (470 MB per 100k notes) and "
                  "about an hour of embedding, and the machine was shared with a training job; the 10k → 100k trend "
                  "above is what to extrapolate from (`engine_bench.py run --only scale --scales 1000000`)."]
    g = card["A10"]["gate"]
    L += ["", "## A10 gate", "",
          f"Over {g['answerable']} answerable and {g['unanswerable']} unanswerable questions: the gate let memory "
          f"through for {g['opened_answerable']} answerable and {g['opened_unanswerable']} unanswerable ones. "
          f"Precision {_f(g['precision'], True)}, specificity {_f(g['specificity'], True)}, "
          f"sensitivity {_f(g['sensitivity'], True)}."]
    lm = meta["longmemeval"]
    rp = meta.get("read_path") or {}
    L += ["", "## Setup", "",
          f"* Read path: {', '.join(f'{k} {v}' for k, v in rp.items())}.",
          f"* LongMemEval: `{lm['file']}` from `{lm['repo']}` at revision `{lm['revision'][:12]}` (sha256 "
          f"`{lm['sha256'][:16]}…`), MIT licence. Stratified subsample, seed {lm.get('seed')}, at most "
          f"{lm.get('per_type')} per question type: {lm.get('sampled')} of {lm.get('questions_in_source')} questions "
          f"({', '.join(f'{k} {v}' for k, v in (lm.get('by_type') or {}).items())}).",
          "* Each LongMemEval question gets a fresh store holding its whole chat history, one note source per turn "
          "('On <date> the user|assistant said: …'); needed facts are the turns flagged has_answer in each evidence "
          "session (every turn of an evidence session that has no flag).",
          f"* Passage vectors computed once on {meta.get('passage_device')} and cached; questions embedded on the "
          "CPU each time (retrieval ms is what the app would see).", ""]
    (OUT / "scorecard.md").write_text("\n".join(L))
    say("wrote", OUT / "scorecard.md")


def main(argv=None) -> None:
    p = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    p.add_argument("cmd", choices=["fetch", "prepare", "prepare-m", "embed", "run", "report", "all", "scale",
                                   "contexts"])
    p.add_argument("--label", default="baseline", help="contexts: written to results/bench/contexts_<label>.jsonl")
    p.add_argument("--seed", type=int, default=SEED)
    p.add_argument("--per-type", type=int, default=PER_TYPE)
    p.add_argument("--scales", type=lambda s: tuple(int(x) for x in s.split(",")), default=SCALES)
    p.add_argument("--only", default="", help="suites to run: camr,a8,lme,scale")
    p.add_argument("--limit", type=int, default=None, help="LongMemEval: first N sampled questions only")
    p.add_argument("--repeats", type=int, default=3, help="scale: times each question is asked for latency")
    p.add_argument("--fresh", action="store_true", help="discard earlier records of the suites run")
    p.add_argument("--with-m", action="store_true", help="fetch: also LongMemEval M (2.7 GB, filler for 1M notes)")
    p.add_argument("--m-notes", type=int, default=950_000, help="prepare-m: about this many notes of M filler")
    p.add_argument("--notes", type=int, default=1000)
    p.add_argument("--phase", choices=["build", "query"], default="build")
    p.add_argument("--out", default="")
    a = p.parse_args(argv)
    os.environ.setdefault("TOKENIZERS_PARALLELISM", "false")
    for var in ("OMP_NUM_THREADS", "MKL_NUM_THREADS", "VECLIB_MAXIMUM_THREADS"):  # before torch is imported
        os.environ.setdefault(var, str(THREADS))
    if a.cmd != "fetch":
        os.environ.setdefault("HF_HUB_OFFLINE", "1")  # BGE from the local cache: never a download mid-run
    for d in (WORK, TMP, STORES):
        d.mkdir(parents=True, exist_ok=True)
    steps = ["fetch", "prepare", "embed", "run", "report"] if a.cmd == "all" else [a.cmd]
    for s in steps:
        globals()[f"cmd_{s.replace('-', '_')}"](a)


if __name__ == "__main__":
    main()

"""The n8n RAG pipeline as a Long Haul contender, put through the same checkpoints, questions and grader as CAMR.

``N8nRag`` is a camr_engine.bench.contender.Contender, so camr_engine.bench.contender.run drives it exactly as it
drives ``engine:qwen3-4b``: the same events told in order, the same per-cut sample of questions (longhaul.checkpoints,
seed 0, ten per family), the same grader, and a record of the same shape.

- ``tell`` dates each event as CAMR dates its moments (``[YYYY-MM-DD, day N] User: ...``; day lines are left out, as
  every line carries its day), counts the line in Qwen3 tokens, and buffers it. A full batch (about BATCH_TOKENS
  tokens), and whatever is left when a checkpoint's events are all told, goes to the ingest webhook. n8n cuts the
  batch into chunks of at most 512 tokens, embeds them with Ollama and upserts them into Qdrant.
- ``ask`` posts the question, today's date and the family's line to the ask webhook, which embeds the question,
  takes the k closest chunks from Qdrant, keeps those that fit the memory budget, and asks Ollama.

Ingest is resumable: what has gone into a collection is kept in work/n8n/state/<collection>.json, and a run told
the same history skips the events already there (a second run with another k or budget reads nothing again). The
collection's name carries the history's seed and script hash and the chunk size, so two histories never share one.
"""

from __future__ import annotations

import datetime as dt
import json
import time
from pathlib import Path
from typing import Any, Callable, Sequence

from camr_engine.bench.contender import (RECORDS, THINKING, Answer, Contender, decode_tps, metrics, run,
                                         write_record)
from camr_engine.bench.rag_n8n import build, pipeline, stack

BATCH_TOKENS = 16_000  # tokens of history per ingest call: about 32 chunks to embed
TEMPLATE_TOKENS = 32  # what qwen3's chat template adds around a system and a user message, when no template is cached
STATE = stack.WORK / "state"
MODEL = "qwen3-4b"


def collection_name(haul: dict, chunk_tokens: int = pipeline.CHUNK_TOKENS) -> str:
    sha = str(haul.get("script_sha") or "nosha")[:10]
    return f"longhaul_s{haul.get('seed')}_{sha}_c{chunk_tokens}"


class Prompts:
    """Counts the prompt as the model reads it: Qwen3-4B-Instruct-2507's own chat template and tokenizer from the
    local Hugging Face cache (the same the local contenders count with), else the Qwen3 tokenizer plus a fixed
    allowance for the template."""

    def __init__(self):
        self.how = None
        self._tok = None
        try:
            import os

            os.environ.setdefault("HF_HUB_OFFLINE", "1")
            os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
            from transformers import AutoTokenizer

            from camr_engine.bench.local import MODELS

            self._tok = AutoTokenizer.from_pretrained(MODELS[MODEL], local_files_only=True)
            self.how = f"{MODELS[MODEL]} chat template"
        except Exception:  # noqa: BLE001: no transformers, or no cached tokenizer
            self._tok = None
        from camr_engine.bench.haul.tokens import TOKENIZER, counter

        self.count = counter()
        self.how = self.how or f"{TOKENIZER} tokens + {TEMPLATE_TOKENS} for the template"

    def prompt_tokens(self, system: str, question: str) -> int:
        if self._tok is not None:
            text = self._tok.apply_chat_template([{"role": "system", "content": system},
                                                  {"role": "user", "content": question}],
                                                 add_generation_prompt=True, tokenize=False)
            return len(self._tok.encode(text, add_special_tokens=False))
        return self.count(system) + self.count(question) + TEMPLATE_TOKENS


class N8nRag(Contender):
    """n8n-rag:qwen3-4b: a standard RAG pipeline built as two n8n workflows over Qdrant and Ollama."""

    kind = "n8n-rag"

    def __init__(self, *, haul: dict, k: int = build.K, budget: int = build.BUDGET, order: str = build.ORDER,
                 chunk_tokens: int = pipeline.CHUNK_TOKENS, num_ctx: int = build.NUM_CTX, fresh: bool = False,
                 n8n: str = stack.N8N, watch: stack.RamWatch | None = None, prompts: Prompts | None = None,
                 dates: Callable[[int], dt.date] | None = None, post: Callable[[str, dict], dict] | None = None,
                 state_dir: Path = STATE, progress: Callable[[str], None] = print):
        self.haul, self.k, self.budget, self.order = haul, k, budget, order
        self.chunk_tokens, self.num_ctx, self.fresh, self.n8n = chunk_tokens, num_ctx, fresh, n8n
        self.collection = collection_name(haul, chunk_tokens)
        self.name = f"{self.kind}:{MODEL}" + self.tag()
        self.watch, self.prompts, self.progress = watch, prompts, progress
        self._dates = dates
        self._post = post or self._http
        self.state_path = Path(state_dir) / f"{self.collection}.json"
        self.state: dict[str, Any] = {}
        self.buffer: list[dict] = []
        self.buffer_tokens = 0
        self.index = 0  # events seen by tell, day lines included: the history's event number
        self._last_i = -1
        self.resumed_from = 0
        self.today: dt.date | None = None
        self.posted = {"calls": 0, "events": 0, "tokens": 0, "chunks": 0, "seconds": 0.0, "embed_ms": 0.0,
                       "upsert_ms": 0.0, "skipped_events": 0}
        self.flush_s = 0.0
        self.history_tokens = 0

    def tag(self) -> str:
        parts = []
        if self.k != build.K:
            parts.append(f"k={self.k}")
        if self.budget != build.BUDGET:
            parts.append(f"budget={self.budget}")
        if self.order != build.ORDER:
            parts.append(f"order={self.order}")
        if self.chunk_tokens != pipeline.CHUNK_TOKENS:
            parts.append(f"chunk={self.chunk_tokens}")
        return f"[{','.join(sorted(parts))}]" if parts else ""

    # -- plumbing

    def _http(self, path: str, body: dict) -> dict:
        status, out = stack.request("POST", f"{self.n8n}/webhook/{path}", body, timeout=900)
        if status != 200 or not isinstance(out, dict):
            raise stack.StackError(f"n8n {path} answered {status}: {str(out)[:300]}")
        return out

    def dates(self, day: int) -> dt.date:
        if self._dates is None:
            from camr_engine.bench.local import haul_dates

            self._dates = haul_dates()
        return self._dates(day)

    def _save_state(self) -> None:
        self.state_path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.state_path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(self.state, indent=1))
        tmp.replace(self.state_path)

    # -- the contender

    def open(self, folder: Path) -> None:
        if self.prompts is None:
            self.prompts = Prompts()
        state = json.loads(self.state_path.read_text()) if self.state_path.exists() else {}
        if self.fresh or not state or (state.get("haul") or {}).get("script_sha") != self.haul.get("script_sha"):
            stack.drop_collection(self.collection)
            state = {}
        elif stack.collection_info(self.collection) is None or stack.count(self.collection) == 0:
            state = {}  # the state outlived its collection
        made = stack.ensure_collection(self.collection, stack.embed_dim())
        self.state = state or {"collection": self.collection, "haul": self.haul, "chunk_tokens": self.chunk_tokens,
                               "events_done": 0, "tokens_done": 0, "ingest_s": 0.0, "calls": 0, "chunks": 0,
                               "flush_at": [], "started": dt.datetime.now().isoformat(timespec="seconds")}
        self._save_state()
        self.resumed_from = int(self.state["events_done"])
        self.progress(f"{self.name}: collection {self.collection} "
                      f"({'made' if made else 'kept'}, {self.resumed_from} events already in)")

    def tell(self, text: str, day: int) -> None:
        i = self.index
        self.index += 1
        self.today = self.dates(day)
        if i < int(self.state.get("events_done", 0)):
            self.posted["skipped_events"] += 1
            return
        if day_line(text):
            return  # every line carries its day, as CAMR's moments do
        e = {"i": i, "date": self.today.isoformat(), "day": day, "text": text}
        e["tokens"] = self.prompts.count(pipeline.line(e) + "\n")
        self.buffer.append(e)
        self.buffer_tokens += e["tokens"]
        self._last_i = i
        if self.buffer_tokens >= BATCH_TOKENS:
            self.flush()

    def flush(self) -> None:
        """Send the buffered events to the ingest webhook, then mark them done."""
        if not self.buffer:
            return
        t = time.perf_counter()
        out = self._post(build.INGEST["path"], {"collection": self.collection, "chunk_tokens": self.chunk_tokens,
                                                "embed_model": build.EMBED_MODEL, "events": self.buffer})
        took = time.perf_counter() - t
        if not out.get("ok"):
            raise stack.StackError(f"ingest did not say ok: {str(out)[:300]}")
        n, tokens = len(self.buffer), self.buffer_tokens
        tm = out.get("timings") or {}
        self.posted["calls"] += 1
        self.posted["events"] += n
        self.posted["tokens"] += tokens
        self.posted["chunks"] += int(out.get("chunks") or 0)
        self.posted["seconds"] += took
        self.posted["embed_ms"] += float(tm.get("chunk_embed_ms") or 0)
        self.posted["upsert_ms"] += float(tm.get("upsert_ms") or 0)
        st = self.state
        st["events_done"] = self._last_i + 1
        st["tokens_done"] = int(st["tokens_done"]) + tokens
        st["ingest_s"] = round(float(st["ingest_s"]) + took, 3)
        st["calls"] = int(st["calls"]) + 1
        st["chunks"] = int(st["chunks"]) + int(out.get("chunks") or 0)
        self._save_state()
        self.buffer, self.buffer_tokens = [], 0

    def cut_told(self, checkpoint: dict) -> None:
        t = time.perf_counter()
        self.flush()  # a cut closes the open chunk
        self.state.setdefault("flush_at", []).append(self.index)
        self.state["events_done"] = max(int(self.state["events_done"]), self.index)
        self._save_state()
        self.flush_s += time.perf_counter() - t
        self.history_tokens = int(checkpoint.get("tokens") or 0)

    def reading_s(self) -> float:
        return self.flush_s  # the last batch of a cut is sent after run() stops its tell clock

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        from camr_engine.bench.local import hint
        from camr_engine.memory import today_text

        today = today_text(self.today or self.dates(1))
        then = hint(family)
        body = {"question": question, "today": today, "then": then, "k": self.k, "budget": self.budget,
                "order": self.order, "collection": self.collection, "max_tokens": max_tokens, "num_ctx": self.num_ctx}
        t = time.perf_counter()
        out = self._post(build.ASK["path"], body)
        wall = time.perf_counter() - t
        peak = self.watch.peak_since(t) if self.watch else None
        return answer_from(out, wall, prompt_tokens=self.prompts.prompt_tokens(out.get("system") or "", question),
                           history_tokens=self.history_tokens, peak_bytes=peak,
                           disk_bytes=stack.du(stack.WORK / "qdrant.nosync" / "collections" / self.collection))

    def status(self) -> dict:
        d = stack.disk(self.collection)
        out: dict[str, Any] = {"collection": self.collection, "points": stack.count(self.collection),
                               "posted": {**self.posted, "seconds": round(self.posted["seconds"], 3)},
                               "resumed_from_event": self.resumed_from,
                               "ingest_state": {k: self.state.get(k) for k in ("events_done", "tokens_done",
                                                                                "ingest_s", "calls", "chunks",
                                                                                "flush_at", "started")},
                               "disk": d, "disk_gb": round(d.get("collection_bytes", 0) / 1e9, 6),
                               "disk_total_gb": round(d["total_bytes"] / 1e9, 6)}
        if self.watch is not None:
            now = self.watch.latest()
            peak = self.watch.peak()
            if now:
                out["ram_now_gb"] = round(now[0] / 1e9, 3)
                out["ram_now"] = now[1]
            if peak:
                out["peak_ram_gb"] = round(peak[0] / 1e9, 3)
                out["peak_ram"] = peak[1]
            if self.watch.error:
                out["ram_watch_error"] = self.watch.error
        return out

    def describe(self) -> dict:
        wf = {n: json.loads((build.WORKFLOWS / f"{n}.json").read_text()) for n in ("ingest", "ask")}
        return {"name": self.name, "kind": self.kind, "model": MODEL, "runtime": "n8n + Qdrant + Ollama (Docker)",
                "chat_model": build.CHAT_MODEL, "embed_model": build.EMBED_MODEL,
                "query_instruction": build.INSTRUCTION, "k": self.k, "budget_tokens": self.budget,
                "order": self.order, "chunk_tokens": self.chunk_tokens, "batch_tokens": BATCH_TOKENS,
                "num_ctx": self.num_ctx, "options": build.OPTIONS, "keep_alive": build.KEEP_ALIVE,
                "enable_thinking": THINKING, "think": THINKING, "stream": False, "system": build.intro(),
                "collection": self.collection, "token_counter": self.prompts.how if self.prompts else None,
                "chunking": "consecutive dated lines ([YYYY-MM-DD, day N] Role: text, day lines left out) packed "
                            "into chunks of at most chunk_tokens Qwen3 tokens; an event longer than a chunk is cut "
                            "at line, then word, boundaries and each part keeps its date; no overlap",
                "retrieval": "the question with the embedder's query instruction, embedded by Ollama; Qdrant's k "
                             "closest chunks (cosine); those that fit the budget, closest first, then put in date "
                             "order",
                "prompt": "system: the instructions, \"Notes:\" with the chosen chunks, \"End of notes.\", \"Today is "
                          "<date>.\" and the family's line; user: the question (CAMR's prompt, notes as words)",
                "timings": "ttft_s = the webhook's wall time minus Ollama's eval_duration (the time to the first "
                           "word had the answer been streamed; n8n answers once, at the end); prefill_tps and "
                           "decode_tps are Ollama's own (prompt_eval_count / prompt_eval_duration, eval_count / "
                           "eval_duration); retrieval_ms is n8n's embed + search time",
                "ram": "docker stats for the n8n and Qdrant containers + the physical footprint (Metal included) of "
                       "Ollama's server and the runners holding our two models, sampled in the background",
                "disk": "disk_gb: the Qdrant collection's folder; status.disk: Qdrant's and n8n's volumes",
                "workflows": {n: {"id": w["id"], "name": w["name"], "nodes": [x["name"] for x in w["nodes"]]}
                              for n, w in wf.items()},
                "versions": {"n8n": stack.n8n_version(), "qdrant": stack.qdrant_version(),
                             "ollama": _ollama_version()}}

    def close(self) -> None:
        if self.buffer:
            self.flush()


def day_line(text: str) -> bool:
    from camr_engine.bench.local import DAY_LINE

    return bool(DAY_LINE.match(text))


def _ollama_version() -> str | None:
    try:
        status, out = stack.request("GET", f"{stack.OLLAMA}/api/version", timeout=5)
        return out.get("version") if status == 200 else None
    except stack.StackError:
        return None


def strip_think(text: str) -> str:
    """qwen3 sometimes opens a think-off answer with the "</think>" its template ends the prompt with."""
    head, closed, tail = (text or "").partition("</think>")
    return tail.strip() if closed and not head.replace("<think>", "").strip() else (text or "").strip()


def answer_from(out: dict, wall_s: float, *, prompt_tokens: int, history_tokens: int, peak_bytes: int | None,
                disk_bytes: int | None) -> Answer:
    """One ask webhook's reply as an Answer with the shared metrics."""
    tm = out.get("timings") or {}
    ns = lambda key: (tm.get(key) or 0) / 1e9  # noqa: E731
    n_out = tm.get("eval_count")
    eval_s = ns("eval_duration")
    ttft = max(wall_s - eval_s, 0.0) if eval_s else wall_s
    prefill = (round(tm["prompt_eval_count"] / ns("prompt_eval_duration"), 1)
               if tm.get("prompt_eval_count") and tm.get("prompt_eval_duration") else None)
    m = metrics(ttft_s=round(ttft, 4), total_s=round(wall_s, 4), prefill_tps=prefill,
                decode_tps=decode_tps(n_out, wall_s, ttft), retrieval_ms=tm.get("retrieval_ms"), bytes_read=None,
                gbps=None, read_share=None, context_tokens=prompt_tokens, history_tokens=history_tokens,
                peak_ram_gb=round(peak_bytes / 1e9, 3) if peak_bytes else None,
                disk_gb=round(disk_bytes / 1e9, 6) if disk_bytes is not None else None, tier="vault")
    ollama_total = ns("total_duration")
    extra = {"answer_tokens": n_out, "memory_words": out.get("memory_tokens"), "memory_notes": 0,
             "memory_in_view": out.get("memory_tokens"), "prefill_tokens": prompt_tokens,
             "chunks": out.get("chunks"), "hits": out.get("hits"), "done_reason": out.get("done_reason"),
             "ollama_decode_tps": round(n_out / eval_s, 1) if n_out and eval_s else None,
             "prompt_eval_count": tm.get("prompt_eval_count"), "load_ms": round(ns("load_duration") * 1000, 2),
             "embed_ms": tm.get("embed_ms"), "search_ms": tm.get("search_ms"), "generate_ms": tm.get("generate_ms"),
             "n8n_total_ms": tm.get("total_ms"), "ollama_total_s": round(ollama_total, 4),
             "overhead_ms": round((wall_s - ollama_total) * 1000 - float(tm.get("retrieval_ms") or 0), 1)
             if ollama_total else None,
             "thinking_chars": len(out.get("thinking") or ""), "raw_answer": out.get("answer")}
    return Answer(strip_think(out.get("answer") or ""), m, extra)


def fix_ingest(record: dict) -> None:
    """When a run resumed a collection, run() counted the skipped events as told in no time: each checkpoint's
    ingest is then what was really sent (and the earlier runs' totals are in status.ingest_state)."""
    before = {"events": 0, "tokens": 0, "skipped_events": 0}
    for cp in record.get("checkpoints", []):
        st = cp.get("status") or {}
        posted = st.get("posted") or {}
        now = {k: int(posted.get(k) or 0) for k in before}
        sent = {k: now[k] - before[k] for k in before}
        before = now
        if not sent["skipped_events"]:
            continue
        ing = cp["ingest"]
        ing["resumed"] = True
        ing["skipped_events"] = sent["skipped_events"]
        ing["sent"] = {"events": sent["events"], "line_tokens": sent["tokens"]}
        ing["tokens_per_s"] = None if not sent["tokens"] else round(sent["tokens"] / ing["seconds"], 1)
        ing["events_per_s"] = None if not sent["events"] else round(sent["events"] / ing["seconds"], 2)
        state = st.get("ingest_state") or {}
        if state.get("ingest_s"):
            ing["collection_tokens_per_s"] = round(state["tokens_done"] / state["ingest_s"], 1)


def longhaul(folder: Path, cuts: Sequence[str], *, k: int = build.K, budget: int = build.BUDGET,
             order: str = build.ORDER, limit: int | None = None, fresh: bool = False, records: Path = RECORDS,
             num_ctx: int = build.NUM_CTX, progress: Callable[[str], None] = print) -> dict:
    """The n8n RAG contender through the Long Haul's checkpoints at ``cuts``; returns the record."""
    from camr_engine.bench.local import haul_meta
    from camr_engine.bench.longhaul import CUTS, checkpoints, grader

    if "s1-16m" in Path(folder).resolve().name:
        raise SystemExit("s1-16m is the locked exam: it is not run from here")
    names = list(cuts)
    bad = [n for n in names if n not in CUTS]
    if bad:
        raise SystemExit(f"cuts are some of {', '.join(CUTS)}, not {bad}")
    info = stack.up(progress)
    events, cps = checkpoints(Path(folder), {n: CUTS[n] for n in names})
    haul = haul_meta(folder)
    watch = stack.RamWatch().start()
    try:
        c = N8nRag(haul=haul, k=k, budget=budget, order=order, num_ctx=num_ctx, fresh=fresh, watch=watch,
                   progress=progress)
        rec = run(c, events, cps, task="longhaul", grader=grader, limit=limit, records=records,
                  folder=stack.WORK / "state", progress=progress,
                  meta={"haul": haul, "cuts": names, "stack": info}, raise_failure=False)
    finally:
        watch.stop()
    fix_ingest(rec)
    if rec.get("path"):
        write_record(rec, Path(rec["path"]))
    return rec


__all__ = ["N8nRag", "Prompts", "answer_from", "collection_name", "fix_ingest", "longhaul", "strip_think"]

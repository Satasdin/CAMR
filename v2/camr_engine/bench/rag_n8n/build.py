"""The two n8n workflows, written as n8n's own workflow JSON from js/rag.js and a few lines of glue per Code node.

    python -m camr_engine.bench.rag_n8n build     # rewrites workflows/ingest.json and workflows/ask.json

The JSON files are what n8n imports and what a person opens in the editor; the tests check they are what this module
writes, so the logic lives in one place (js/rag.js) and its Python twin (pipeline.py).

- **Ingest** (POST /webhook/camr-rag-ingest): Webhook -> Code "Chunk events" -> HTTP "Embed chunks (Ollama)" ->
  Code "Qdrant points" -> HTTP "Upsert (Qdrant)" -> Code "Ingest report" -> Respond to Webhook.
- **Ask** (POST /webhook/camr-rag-ask): Webhook -> Code "Read question" -> HTTP "Embed question (Ollama)" ->
  Code "Search request" -> HTTP "Search (Qdrant)" -> Code "Build prompt" -> HTTP "Answer (Ollama chat)" ->
  Code "Answer + timings" -> Respond to Webhook.
"""

from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
JS = HERE / "js" / "rag.js"
WORKFLOWS = HERE / "workflows"

# Where n8n (inside its container) finds the other two services.
OLLAMA_URL = "http://host.docker.internal:11434"
QDRANT_URL = "http://qdrant:6333"

CHAT_MODEL = "qwen3:4b-instruct-2507-q4_K_M"  # the model CAMR runs (Qwen3-4B-Instruct-2507), as Ollama serves it
EMBED_MODEL = "qwen3-embedding:0.6b"  # the embedder CAMR uses (Qwen3-Embedding-0.6B), as Ollama serves it
COLLECTION = "camr_rag"
CHUNK_TOKENS = 512
K = 8
# CAMR's own memory per question at 2M (records/bench/2026-11-07/164553-longhaul-engine-qwen3-4b.json): the words in
# view p50 723 tokens, the whole prompt p50 844. RAG gets the same amount of memory by default.
BUDGET = 720
ORDER = "date"
NUM_CTX = 8192
MAX_TOKENS = 120
KEEP_ALIVE = "30m"
OPTIONS = {"temperature": 0.0, "seed": 0}  # greedy, as every other local contender
# The query instruction CAMR's embedder puts before a question (camr_engine.models.Embedder.INSTRUCTION).
INSTRUCTION = "Instruct: Given a question about the user's life, retrieve the user's notes that answer it\nQuery:"

INGEST = {"id": "CamrRagIngest001", "name": "CAMR RAG - ingest", "path": "camr-rag-ingest",
          "webhook_id": "7b0c6a52-5f0e-4f55-9d0c-1a2b3c4d5e01"}
ASK = {"id": "CamrRagAsk000001", "name": "CAMR RAG - ask", "path": "camr-rag-ask",
       "webhook_id": "7b0c6a52-5f0e-4f55-9d0c-1a2b3c4d5e02"}


def intro() -> str:
    """The instructions: the Long Haul's, as CAMR and the local RAG contender read them."""
    from camr_engine.bench.local import LONGHAUL_INTRO

    return LONGHAUL_INTRO


def _code(name: str, glue: str, x: int, *, lib: bool = True) -> dict:
    code = (JS.read_text().rstrip() + "\n\n// --- this node ---\n" if lib else "") + glue.strip() + "\n"
    return {"parameters": {"mode": "runOnceForAllItems", "language": "javaScript", "jsCode": code},
            "name": name, "type": "n8n-nodes-base.code", "typeVersion": 2, "position": [x, 300]}


def _http(name: str, method: str, url: str, body: str, x: int) -> dict:
    return {"parameters": {"method": method, "url": url, "sendBody": True, "contentType": "json",
                           "specifyBody": "json", "jsonBody": body, "options": {"timeout": 600000}},
            "name": name, "type": "n8n-nodes-base.httpRequest", "typeVersion": 4.2, "position": [x, 300]}


def _webhook(spec: dict) -> dict:
    return {"parameters": {"httpMethod": "POST", "path": spec["path"], "responseMode": "responseNode", "options": {}},
            "name": "Webhook", "type": "n8n-nodes-base.webhook", "typeVersion": 2, "position": [0, 300],
            "webhookId": spec["webhook_id"]}


def _respond(x: int) -> dict:
    return {"parameters": {"respondWith": "firstIncomingItem", "options": {}}, "name": "Respond to Webhook",
            "type": "n8n-nodes-base.respondToWebhook", "typeVersion": 1.1, "position": [x, 300]}


def _workflow(spec: dict, nodes: list[dict]) -> dict:
    connections = {a["name"]: {"main": [[{"node": b["name"], "type": "main", "index": 0}]]}
                   for a, b in zip(nodes, nodes[1:])}
    return {"id": spec["id"], "name": spec["name"], "nodes": nodes, "connections": connections, "active": False,
            "settings": {"executionOrder": "v1", "saveDataSuccessExecution": "none",
                         "saveDataErrorExecution": "all", "saveManualExecutions": True},
            "pinData": {}, "meta": {"templateCredsSetupCompleted": True}, "tags": []}


def ingest() -> dict:
    chunk = f"""
const body = $input.first().json.body || {{}};
const t0 = Date.now();
const limit = body.chunk_tokens || {CHUNK_TOKENS};
const events = body.events || [];
const chunks = chunkEvents(events, limit);
return [{{ json: {{
  collection: body.collection || {json.dumps(COLLECTION)},
  embed_model: body.embed_model || {json.dumps(EMBED_MODEL)},
  events: events.length, chunk_limit: limit, chunks, t0,
}} }}];
"""
    points = """
const prev = $('Chunk events').first().json;
const emb = $input.first().json;
const t1 = Date.now();
if (!emb.embeddings || emb.embeddings.length !== prev.chunks.length) {
  throw new Error(`Ollama gave ${emb.embeddings ? emb.embeddings.length : 0} vectors for ${prev.chunks.length} chunks`);
}
const points = prev.chunks.map((c, j) => ({
  id: c.id,
  vector: emb.embeddings[j],
  payload: { text: c.text, tokens: c.tokens, event_ids: c.event_ids, date_from: c.date_from, date_to: c.date_to,
             day_from: c.day_from, day_to: c.day_to },
}));
return [{ json: { collection: prev.collection, points, t1, embed_ms: t1 - prev.t0,
                  embed_prompt_tokens: emb.prompt_eval_count || null,
                  embed_load_ms: emb.load_duration ? emb.load_duration / 1e6 : null } }];
"""
    report = """
const c = $('Chunk events').first().json;
const p = $('Qdrant points').first().json;
const now = Date.now();
return [{ json: {
  ok: true, collection: c.collection, events: c.events, chunks: c.chunks.length,
  chunk_tokens: c.chunks.reduce((n, x) => n + x.tokens, 0), first_point: c.chunks.length ? c.chunks[0].id : null,
  timings: { chunk_embed_ms: p.embed_ms, upsert_ms: now - p.t1, total_ms: now - c.t0,
             embed_prompt_tokens: p.embed_prompt_tokens, embed_load_ms: p.embed_load_ms },
  qdrant: $input.first().json.status || null,
} }];
"""
    nodes = [_webhook(INGEST),
             _code("Chunk events", chunk, 220),
             _http("Embed chunks (Ollama)", "POST", f"{OLLAMA_URL}/api/embed",
                   "={{ JSON.stringify({ model: $json.embed_model, input: $json.chunks.map(c => c.text), "
                   f"truncate: true, keep_alive: {json.dumps(KEEP_ALIVE)} }}) }}}}", 440),
             _code("Qdrant points", points, 660, lib=False),
             _http("Upsert (Qdrant)", "PUT", f"={QDRANT_URL}/collections/{{{{ $json.collection }}}}/points?wait=true",
                   "={{ JSON.stringify({ points: $json.points }) }}", 880),
             _code("Ingest report", report, 1100, lib=False),
             _respond(1320)]
    return _workflow(INGEST, nodes)


def ask() -> dict:
    defaults = {"collection": COLLECTION, "chat_model": CHAT_MODEL, "embed_model": EMBED_MODEL, "k": K,
                "budget": BUDGET, "order": ORDER, "num_ctx": NUM_CTX, "max_tokens": MAX_TOKENS, "intro": intro(),
                "instruction": INSTRUCTION, "keep_alive": KEEP_ALIVE}
    read = f"""
const DEFAULTS = {json.dumps(defaults, indent=2)};
const b = $input.first().json.body || {{}};
if (!b.question) throw new Error('the request has no question');
const q = {{ ...DEFAULTS }};
for (const key of Object.keys(DEFAULTS)) if (b[key] !== undefined && b[key] !== null) q[key] = b[key];
q.question = b.question;
q.today = b.today || null;  // "Monday 22 September 2025": the history's today, given by the caller
q.then = b.then || '';  // one line on the form of the answer (an HTML page, a Python block, the working)
q.query = q.instruction + q.question;
q.t0 = Date.now();
return [{{ json: q }}];
"""
    search = """
const q = $('Read question').first().json;
const t1 = Date.now();
return [{ json: { collection: q.collection, vector: $input.first().json.embeddings[0], k: q.k, t1,
                  embed_ms: t1 - q.t0 } }];
"""
    build = f"""
const q = $('Read question').first().json;
const s = $('Search request').first().json;
const hits = ($input.first().json.result || {{}}).points || [];
const t2 = Date.now();
const sel = selectChunks(hits, q.k, q.budget, q.order);
const system = systemPrompt(q.intro, notesText(sel.picked), q.today, q.then);
const chat = {{
  model: q.chat_model,
  messages: [{{ role: 'system', content: system }}, {{ role: 'user', content: q.question }}],
  stream: false, think: false, keep_alive: q.keep_alive,
  options: {{ ...{json.dumps(OPTIONS)}, num_ctx: q.num_ctx, num_predict: q.max_tokens }},
}};
return [{{ json: {{
  chat, system, memory_tokens: sel.tokens, hits: hits.length, t2,
  search_ms: t2 - s.t1, retrieval_ms: t2 - q.t0,
  picked: sel.picked.map((h) => ({{ id: h.id, score: h.score, tokens: h.payload.tokens, date_from: h.payload.date_from,
                                   date_to: h.payload.date_to, event_ids: h.payload.event_ids }})),
}} }}];
"""
    answer = """
const q = $('Read question').first().json;
const s = $('Search request').first().json;
const p = $('Build prompt').first().json;
const r = $input.first().json;
const t3 = Date.now();
const m = r.message || {};
return [{ json: {
  answer: m.content || '', thinking: m.thinking || '', model: r.model, done_reason: r.done_reason || null,
  memory_tokens: p.memory_tokens, hits: p.hits, chunks: p.picked, system: p.system,
  settings: { k: q.k, budget: q.budget, order: q.order, num_ctx: q.num_ctx, max_tokens: q.max_tokens,
              collection: q.collection, chat_model: q.chat_model, embed_model: q.embed_model },
  timings: {
    embed_ms: s.embed_ms, search_ms: p.search_ms, retrieval_ms: p.retrieval_ms, generate_ms: t3 - p.t2,
    total_ms: t3 - q.t0,
    prompt_eval_count: r.prompt_eval_count ?? null, prompt_eval_duration: r.prompt_eval_duration ?? null,
    eval_count: r.eval_count ?? null, eval_duration: r.eval_duration ?? null,
    load_duration: r.load_duration ?? null, total_duration: r.total_duration ?? null,
  },
} }];
"""
    nodes = [_webhook(ASK),
             _code("Read question", read, 220, lib=False),
             _http("Embed question (Ollama)", "POST", f"{OLLAMA_URL}/api/embed",
                   "={{ JSON.stringify({ model: $json.embed_model, input: $json.query, keep_alive: $json.keep_alive }) }}",
                   440),
             _code("Search request", search, 660, lib=False),
             _http("Search (Qdrant)", "POST", f"={QDRANT_URL}/collections/{{{{ $json.collection }}}}/points/query",
                   "={{ JSON.stringify({ query: $json.vector, limit: $json.k, with_payload: true }) }}", 880),
             _code("Build prompt", build, 1100),
             _http("Answer (Ollama chat)", "POST", f"{OLLAMA_URL}/api/chat", "={{ JSON.stringify($json.chat) }}",
                   1320),
             _code("Answer + timings", answer, 1540, lib=False),
             _respond(1760)]
    return _workflow(ASK, nodes)


def render(wf: dict) -> str:
    return json.dumps(wf, indent=2, ensure_ascii=False) + "\n"


def write(folder: Path = WORKFLOWS) -> list[Path]:
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for name, wf in (("ingest.json", ingest()), ("ask.json", ask())):
        path = folder / name
        path.write_text(render(wf))
        out.append(path)
    return out

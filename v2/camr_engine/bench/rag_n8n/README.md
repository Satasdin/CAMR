# n8n RAG: a standard RAG pipeline on the Long Haul

A conventional retrieval-augmented pipeline built as two **n8n workflows**, with **Qdrant** for the vectors and
**Ollama** for the embedder and the model. It runs on this Mac only, and it takes the same Long Haul as CAMR: the same
history, the same 73 questions per cut, the same grader and a record of the same shape. That makes the two
comparable on how each works, how fast it is and how accurate.

| | CAMR (`engine:qwen3-4b`) | n8n RAG (`n8n-rag:qwen3-4b`) |
|---|---|---|
| model | Qwen3-4B-Instruct-2507, MLX 4-bit | the same model, Ollama `qwen3:4b-instruct-2507-q4_K_M` (GGUF) |
| embedder | Qwen3-Embedding-0.6B (MLX) | the same, Ollama `qwen3-embedding:0.6b` |
| memory | rooms of saved keys and values on the SSD | 512-token text chunks in Qdrant |
| per question | one room plus the closest moments, read as notes | the k closest chunks that fit the budget, read as text |
| memory tokens per question | p50 723 at 2M | 720 by default (`--budget`) |

## How it works

**Ingest** (`POST /webhook/camr-rag-ingest`, workflow "CAMR RAG - ingest"):
Webhook → Code *Chunk events* → HTTP *Embed chunks (Ollama)* → Code *Qdrant points* → HTTP *Upsert (Qdrant)* →
Code *Ingest report* → Respond to Webhook.

The body is `{collection, chunk_tokens, events: [{i, date, day, text, tokens}]}`. Each event becomes a dated line,
`[2025-09-22, day 1] User: ...`, as CAMR dates its moments. Day lines are left out, because every line carries its
day. Consecutive lines are packed into chunks of at most 512 tokens with no overlap. An event longer than a chunk is
cut at line breaks, then at spaces, and each part keeps its date. `tokens` is the line's Qwen3 token count, which the
runner sends; without it the workflow estimates 3.5 characters per token. A point's id is
`event index × 64 + part`, so sending a batch again overwrites the same points.

**Ask** (`POST /webhook/camr-rag-ask`, workflow "CAMR RAG - ask"):
Webhook → Code *Read question* → HTTP *Embed question (Ollama)* → Code *Search request* → HTTP *Search (Qdrant)* →
Code *Build prompt* → HTTP *Answer (Ollama chat)* → Code *Answer + timings* → Respond to Webhook.

The body is `{question, today, then, k, budget, order, collection, max_tokens, num_ctx}`, and every field except the
question has a default. The question goes to the embedder with the same query instruction CAMR's embedder uses.
Qdrant returns the k closest chunks by cosine distance. The workflow keeps the closest ones that fit `budget` tokens
and puts them back in date order. Then it asks the model with CAMR's own prompt, with the notes as words:
the instructions, `Notes:`, the chunks, `End of notes.`, `Today is <date>.` and the family's one line on the form of
the answer. The model runs with thinking off, greedy decoding, `stream: false` and `num_ctx` 8192. The webhook
returns the answer, the chosen chunks, the prompt, and the timings: embed, search and retrieval ms, plus Ollama's
`prompt_eval_count/duration`, `eval_count/duration` and `load_duration`.

The logic lives in `js/rag.js`. `build.py` writes it into the Code nodes, so a person who opens a workflow in the n8n
editor sees all of it. `pipeline.py` is the same logic in Python, and the tests run both versions on the same input.

## Run

```sh
cd v2
.venv/bin/python -m camr_engine.bench.rag_n8n longhaul --dir ../work/haul/s2 --cuts 2M          # CAMR's budget
.venv/bin/python -m camr_engine.bench.rag_n8n longhaul --dir ../work/haul/s2 --cuts 2M --k 16 --budget 4096
.venv/bin/python -m camr_engine.bench.rag_n8n longhaul --dir ../work/haul/s2 --cuts 64K --limit 5 --records ../work/n8n/smoke-records
```

- `longhaul` brings the stack up if it is not running and imports the workflows when they changed. It ingests the
  history up to each cut, asks the cut's questions and writes
  `v2/records/bench/<date>/<time>-longhaul-n8n-rag-qwen3-4b.json`. A run with settings other than the defaults has
  them in its name, for example `n8n-rag:qwen3-4b[budget=4096,k=16]`.
- Ingest can resume. `work/n8n/state/<collection>.json` records which events a collection holds. A second run on the
  same history, for example with another k or budget, ingests nothing again. `--fresh` drops the collection and
  ingests everything again; use it when ingest speed is being measured. The collection's name carries the history's
  seed and script hash and the chunk size.
- `up`, `down`, `status` and `build` manage the stack, report its RAM and disk, and rewrite `workflows/*.json` after
  a change to `js/rag.js` or `build.py`.
- The runner refuses to run `work/haul/s1-16m`, the locked exam.

**Stack.** `docker-compose.yml` runs n8n (127.0.0.1:5678) and Qdrant (127.0.0.1:6333). n8n reaches Ollama on the
host at `host.docker.internal:11434`. Their data lives in `work/n8n/n8n.nosync` and `work/n8n/qdrant.nosync`.
Telemetry, personalization, version checks and templates are off. n8n saves only failed executions. On the first
`up`, `work/n8n/.env` is written with the encryption key and a random, local-only owner login, which is the login for
the editor at http://127.0.0.1:5678. The workflows are imported with n8n's own CLI (`import:workflow`, then
`publish:workflow`) while the server is stopped, and then n8n is started again.

## What is measured

Each answer has the shared metrics (`camr_engine.bench.contender.METRICS`):

- `ttft_s`: the webhook's wall time minus Ollama's `eval_duration`. This is when the first word would have come had
  the answer been streamed. It includes n8n's own overhead and the retrieval. n8n answers once, at the end.
- `total_s`: the webhook's wall time.
- `prefill_tps` and `decode_tps`: Ollama's own speeds (`prompt_eval_count / prompt_eval_duration`) and, after the
  first word, the shared formula. `extra.ollama_decode_tps` is Ollama's own decode speed.
- `retrieval_ms`: n8n's embedding of the question plus the Qdrant search, Code nodes included.
- `context_tokens`: the whole prompt, counted with Qwen3-4B-Instruct-2507's chat template from the local cache.
- `extra.memory_in_view`: the memory tokens shown, to compare with CAMR's.
- `extra.overhead_ms`: the wall time not spent in retrieval or in Ollama.
- `peak_ram_gb`: the most the stack held while the answer ran. A background thread samples the n8n and Qdrant
  containers (`docker stats`) plus the resident memory of Ollama's server and of the runners that hold our two models.
  The runners are found by their model blobs, so a model another job loaded is not counted. Each checkpoint's
  `status` holds the peak and the latest sample with the breakdown, including Ollama's physical footprint and
  `/api/ps`.
- `disk_gb`: the Qdrant collection's folder. `status.disk` also has Qdrant's and n8n's whole volumes.
- Ingest, from the shared runner: the history's tokens per second of wall time, from the first event to the last batch
  stored. `status.posted` splits that time into embedding and upsert. A resumed run marks its ingest
  `resumed: true` and gives the collection's own `collection_tokens_per_s`.

Not counted: the Docker Desktop VM's own memory, and the model weights on disk (Ollama's blobs).

## Tests

`v2/tests/bench/test_rag_n8n.py` runs without network, Docker or Ollama. It covers the chunker, choosing chunks and
the prompt, a check that the JavaScript in the Code nodes gives the same results as the Python (it uses node and is
skipped without it), the workflow JSON (valid, wired in one line, and equal to what `build.py` writes), an answer's
metrics, and a whole run against stand-in webhooks that writes a record of CAMR's shape and resumes.

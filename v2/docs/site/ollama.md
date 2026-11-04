# Pairing with Ollama

The engine runs its own models through MLX. The one exception is a pairing with Ollama: a small local proxy that
speaks Ollama's own HTTP API, so the `ollama` CLI gets memory from one setting.

Through Ollama, memory goes in as words, not tensors. Ollama runs its own model and lets no outside code put
tensors into it. So the pairing shows how far memory as words goes; the engine's notes need the engine.

## With the ollama CLI

Start the real Ollama as usual (it listens on 127.0.0.1:11434). Then start the proxy, and point the CLI at it:

```sh
.venv/bin/python -m camr_engine.pair.ollama --memory ~/.camr/default
OLLAMA_HOST=127.0.0.1:11435 ollama run qwen3:1.7b
```

The proxy prints the line to use once it is listening. The first start loads the embedder, so the first chat does
not wait for it.

| Option | Default | What it does |
| --- | --- | --- |
| `--port` | 11435 | where the proxy listens, on 127.0.0.1 |
| `--memory` | `~/.camr/default` | the memory folder: an engine memory, or a new folder |
| `--upstream` | `127.0.0.1:11434` | where the real Ollama listens; it must be this Mac |
| `--budget` | 512 | tokens of notes added to each chat, about one room of the engine's desk |
| `--no-memory` | off | a plain passthrough, to measure what the proxy itself costs |
| `--allow-origin` | none | an origin let in on paths that never touch memory; the port may be `*` (repeatable) |
| `--max-body-mb` | 32 | the largest request body |
| `--metrics` | `<memory>/ollama/metrics.jsonl` | where the measurements go |

## What it does with a chat

- Everything is forwarded to the real Ollama. Answers stream back byte for byte. Paths other than chats are passed
  through as they are.
- Before a chat (`/api/chat`, or the OpenAI-style `/v1/chat/completions`) is forwarded, the proxy recalls notes on
  the last user message. They go at the front of that message, just before the question.
- They are not a system message. Ollama's templates print every system message once, at the top of the whole
  prompt. Notes that change each turn there would make Ollama read the whole history again every turn. The client
  keeps its own history without the notes, so the prompt stays the same up to the previous question, and Ollama's
  prompt cache holds.
- For `/api/generate`, which has no history, the notes go into its `system` field, after the model's own system
  prompt.
- Once the answer has streamed back, the exchange is remembered on one background worker, so the connection is free
  at once. The next recall waits for it, and that wait is counted in its `recall_ms`.
- A request with the header `X-CAMR-Memory: off` is forwarded with no notes, and nothing is remembered.

## What it remembers, and where

Each turn (the user's message, and the answer) is cut into pieces of at most 800 characters. A very long turn keeps
only its first and last 8 pieces. Each piece is kept in `<memory>/ollama/` three ways:

| File | What it is |
| --- | --- |
| `notes.jsonl` | one line per piece, append-only |
| `vectors.f32` | one row per piece, its embedding, append-only |
| `vault/ollama-000000.md` | one note per piece, in the vault's format, so the folder opens in Obsidian |

- Recall embeds the question with the engine's embedder (Qwen3-Embedding through MLX). It takes the closest notes
  that fit the budget, at most 8, and puts them oldest first.
- When the folder is also an engine memory, its moments are searched too, read-only.
- The files are the truth. A note whose file a person deleted is never recalled again. A note edited by hand is
  recalled with its new words.
- Notes written by one embedder are refused by another, since their vectors would mean nothing to it.

## Security

As in the app:
- The proxy listens on 127.0.0.1 only, and a request must name this host.
- What a web page sends is refused: a request with an `Origin` header, or with `Sec-Fetch-Site` "cross-site" or
  "same-site". The CLI sends neither.
- `--allow-origin` lets an origin in only on paths that never touch memory. An `Origin` header on a chat path or on
  `/camr_engine/metrics` is always refused.
- Bodies are capped.
- The real Ollama must be on this Mac too. Notes are personal and never leave it.

## Measurements

Every request is measured, with memory on or off:
- `added_ms`: what the proxy added before the request reached Ollama;
- `recall_ms` and `wait_ms`: finding the notes, and waiting for the previous exchange to be kept;
- `first_byte_ms` and `upstream_first_byte_ms`: the wait for the first byte, from the client and from Ollama;
- `total_ms`;
- `prefill_tps` and `decode_tps`, as Ollama reported them;
- `notes_chars` and `remember_ms`.

`GET /camr_engine/metrics` returns the latest 500. Each is also a line of `<memory>/ollama/metrics.jsonl`. A chat
answered with memory on carries the headers `X-CAMR-Added-Ms` and `X-CAMR-Notes-Chars`.

Results with and without memory: see records.

## The macOS Ollama app: its limits

These come from the pairing code's own notes (`camr_engine/pair/ollama.py`), for the Ollama app 0.13.5. The route
through the app was read from the app's source. It has not been tried yet.

- The app has no setting for its server's address.
- It reads `OLLAMA_HOST` from its own environment (`launchctl setenv`), both for its chat window and for the server
  it starts.
- "Expose Ollama to the network" makes that server listen on 0.0.0.0:11434 instead.
- So these three steps should send its chats through the proxy:
  1. `launchctl setenv OLLAMA_HOST 127.0.0.1:11435`;
  2. turn Expose on;
  3. restart the app.
- Start the proxy with `--allow-origin 'http://127.0.0.1:*'` for the app's model list. Its `/api/tags`, `/api/show`
  and `/api/version` come from its web view, which sends an `Origin`. Its chat comes from its Go client, which sends
  none.
- Expose also opens Ollama to the local network.
- Without Expose, the app's server would fight the proxy for the port and stop every other process named `ollama`.

The CLI route needs none of this.

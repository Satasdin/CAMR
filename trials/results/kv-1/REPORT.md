# KV trial 1: what a model fetches, kept as its own cache

11 November 2026. MacBook Pro M5 Pro, 24 GB. llama.cpp b12110 (`llama-server`), Qwen3 4B Instruct 2507 Q4_K_M (the
Ollama GGUF), `-c 65536 -np 2`, so 32,768 tokens a slot. Temperature 0, seed 7. Engine at d4b8a05 plus the two fixes
in D-60. Decisions: D-59 to D-62.

## The answer, through MCP, with a real client

`run.py` plays the chat program. It starts `burrow mcp --llama`, gives the model Burrow's tools over llama-server's
OpenAI route, and runs every tool call against Burrow (`client.json`).

| | First request: read | from cache | reading | whole first answer |
|---|---|---|---|---|
| Cold: opens with the BurrowCore pack, nothing saved | 25,158 tokens | 0 | 34.6 s | 37.7 s |
| Reuse: the same pack, after a server restart, cache loaded by Burrow | 919 tokens | 24,239 | 2.2 s | 5.3 s |

The two runs used the same pack text (sha `2911b8dfc6b1`) and gave the same answer. Writing ran at 37 tokens a second
in both. Burrow loaded the 24,240-token part in 0.35 s, after the program's `vault_pack` call and before its question.
llama.cpp routed the question to Burrow's slot by itself (prefix match), with tools in the request.

In the working session before that, the model made three `burrow_find` lookups. They built one part, as D-60 allows,
and the program's `vault_pack` call built BurrowCore part 1 (24,013 tokens in 34.6 s, 3.4 GB), all after the replies.

A client that asks while Burrow is building waits for one build step at most. In the collision check, the question
arrived during a 3,311-token step, waited about 0.4 s for it, and then wrote at 90.2 tokens a second, the same as on an
idle server. The build resumed after it (`server-collide.log`). In the first run (`first-run/`), before this fix, a
client asking during a build wrote 3.8 tokens a second.

## Reading (PP): cache against cold

`sweep/`, `bench.py`. One folder pack (9 BurrowCore files) and one prose pack (3 parts of the Data Protection Act),
read cold and then from a saved slot.

| Pack | Tokens | Cold read | Load | Then read | On disk (f16) | On disk (q8_0) |
|---|---|---|---|---|---|---|
| Code, numbered lines | 20,891 | 24.9 to 28.8 s | 0.35 to 0.47 s | 0.15 to 0.28 s | 3.08 GB | 1.64 GB, loads in 0.13 s |
| Prose, numbered lines | 7,394 | 5.5 to 7.0 s | 0.07 to 0.16 s | about 0.1 s | 1.09 GB | |
| Code, no line numbers | 16,217 | 16.7 s | 0.28 s | | 2.39 GB | |

## Writing (TG): what was tried

Tokens a second on the first answer to each question. The second, identical request is not counted: ngram-mod and
the lookup table remember the server's earlier output, so it ran at up to 203 tokens a second as a repeat.

| Server | code copy | code edit | code explain | prose explain | drafts accepted |
|---|---|---|---|---|---|
| Plain (baseline3; earlier runs 22 to 42, see note) | 42.0 | 42.0 | 42.0 | 65.9 | |
| ngram-simple (n 12) | 35.4 | 35.7 | 38.0 | 60.6 | 7 to 22 % |
| ngram-simple (n 4) | 37.6 | 34.1 | 37.2 | 65.9 | 13 to 44 % |
| ngram-map-k (n 12) | 37.1 | 41.5 | 38.8 | 49.0 | |
| ngram-map-k (n 4) | 36.7 | 36.1 | 36.4 | 72.9 | |
| ngram-mod | 37.6 | 34.6 | 39.6 | 64.6 | |
| Burrow's lookup table from the plain vault text (`-lcs`, 1.3 MB, built in 9.7 s) | 42.2 | 34.8 | 26.3 | 69.7 | |
| Qwen3 1.7B draft, 48k window, q8_0 caches | 21.3 | 16.1 | 10.1 | 33.5 | 19 to 57 % |
| Plain, 48k window, q8_0 caches (its baseline) | 44.3 | 43.7 | 44.3 | 64.1 | |
| Plain, q8_0 caches | 42.5 | 43.1 | 44.0 | 64.2 | |
| Plain, no line numbers | 47.2 | 47.6 | 47.7 | 71.3 | |

Not worth it on this Mac: no speculation beat plain writing, and the draft model halved it. The draft model at a
64k window ran the Mac out of memory (18 GB of swap, reading at 27 tokens a second), so that run was stopped and
discarded. What did help was a shorter context. q8_0 caches wrote 2 to 5 % faster, and dropping line numbers wrote
13 % faster and read 33 % faster. Line numbers stay for now, because citations are checked by line (D-54).

Note on noise: the first two plain runs had slow outliers (22 to 24 tokens a second) while other sessions were
building and testing. baseline3, run with the Mac otherwise idle, was steady at 42.0. The speculation runs came after
baseline2 and may carry some of that noise. None of them came near a gain that noise could hide.

## Files

- `client.json`, `server-*.log`, `burrow-*.log`: the client trial. `first-run/` holds the run that found the two faults.
- `sweep/*.json`: every PP and TG run. `trials/kv/bench.py` and `trials/kv/sweeps.sh` reproduce them; the vault was a
  copy of `trials/connect/work/vault`.

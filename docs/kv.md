# What a model fetches, kept as its own cache

Text is the format every model can read. A KV cache is the format one model can load: the work it already did reading
something. Burrow keeps both. The text stays in the vault and is always what a lookup returns. The cache is an extra,
filed on the shelf (`.burrow/kv`) by model and by the exact files it was built from, and used only when it fits.

This page covers the active path (D-59 to D-62): lookups through `burrow mcp` are read into the model's cache in the
background, folders are read whole in parts sized to the model's window, and the numbers behind each choice.

## Set up (llama.cpp)

```
llama-server -m model.gguf --jinja -c 65536 -np 2 -fa on -ctk q8_0 -ctv q8_0 --slot-save-path ~/Notes/.burrow/kv
burrow mcp ~/Notes --llama http://127.0.0.1:8080
```

`-ctk q8_0 -ctv q8_0` keeps the cache in 8 bits: half the disk (1.6 GB against 3.1 GB for 21,000 tokens), a third of
the load time, and the same answers in the trial (D-62).

`-np 2` gives the server two slots. Burrow only ever builds in the last one, so the conversation a client has in the
other is never erased. With one slot Burrow does nothing and says so once. `-c 65536` is shared by the slots, so each has
32,768 tokens; Burrow sizes its packs to that.

## What happens

1. A client calls `burrow_find`, `burrow_read` or another lookup (`vault_search`, `vault_read`, `vault_prepare`). The reply goes out as text, as always.
2. After the reply, Burrow notes the folders the files came from. When a folder has come up in two lookups, it is worth
   keeping: once no slot is working, Burrow reads the one part holding most of the files into the spare slot and saves
   it. `vault_pack` says the same thing directly, for the part it returned. A build reads a step at a time and waits
   whenever a client is working, so a client waits a few seconds at most.
3. When the folder comes up again and its cache is fresh, Burrow loads it into the spare slot (about 0.4 s for 20,000
   tokens) instead of building it.
4. A conversation that opens with the pack as its system message is sent to that slot by llama.cpp, which matches the
   start of the prompt, and only the question is read.

A model never has to know any of this. If the server is down, has one slot, or saves its caches elsewhere, every lookup
works exactly as before.

## Packs: a folder read whole

`vault_pack` (MCP) and `burrow kv pack` give a folder in parts that each fit the model's window: a map of the folder and
its own notes (README, DECISIONS and the like) first, then every file with line numbers. Every part of a folder starts with
that same spine, so the spine is read once and each part after it costs only its own files. The same files always give the
same text, which is what lets a saved cache match.

```
burrow kv ~/Notes pack Code/app/Sources --part 1 > system.txt       the text, to open a conversation with
burrow kv ~/Notes warm Code/app/Sources                               read every part now and keep them
burrow kv ~/Notes list
```

A cache only helps a prompt that starts with its text: llama.cpp reuses the shared start of a prompt and nothing after a
difference. Excerpts a model fetched in the middle of a conversation can't be loaded from a cache built elsewhere; they
are read as text, which is why a pack is meant to open the conversation.

## The shelf

Each entry in `shelf.json` keeps the fields it always had (`key`, `model`, `file`, `sources`, `tokens`, `bytes`,
`buildSeconds`, `created`). Packs add `scope`, `part`, `parts`, `base` (the spine they were stacked on), `form`
(`system` when read through the model's chat template) and `lastUsed`. A cache is about 147 KB a token for Qwen3 4B in
f16, so a 21,000-token part is 3 GB. The shelf keeps itself under 12 GB by clearing the least recently used caches;
the text they came from is never touched.

## What it gave

Through MCP with llama-server and Qwen3 4B, a conversation that opened with a 24,240-token pack started answering in
5.3 s with the saved cache, against 37.7 s without it. No speculative decoding (n-gram lookup, a lookup table from the
vault, a draft model) made writing faster on this Mac. See `trials/results/kv-1/REPORT.md` for the measurements.

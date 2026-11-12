# Demonstration clips

Raw clips for the final presentation, each from a real run on a copy of the evaluation vault, to be edited together.
Nothing is staged: the models answered live, and every number on screen was measured in that run.

| Clip | Shows | Length | Recorded with |
|---|---|---|---|
| 01-app-tour-live-lookup.mp4 | The app: library, a note with its properties, the map, then the Programs page lighting up while Gemma 4 12B in OpenCode asks the vault about breach notice; its conversation and the Ledger | 73 s | `BURROW_RECORD=<folder>` frames from the app, driven from its menus; `ffmpeg -framerate 10` |
| 02-install-and-connect.mp4 | Install from the release in one command, index the vault, connect it to Claude Code, `claude mcp get burrow` shows Connected | 32 s | `vhs tapes/02-install-connect.tape` |
| 03-memory-stored-and-fetched.mp4 | Session 1: Claude Code fetches the 72-hour rule through Burrow and keeps a decision in the Ledger; `burrow log`; session 2, with no chat history, recalls the decision and why | 79 s | `vhs tapes/03-store-fetch.tape` |
| 04-what-the-model-reads.mp4 | `find` (which files and lines, 0.05 s), `brief` (the exact text handed to the model), `ask` with Gemma 4 12B citing line 133, time to first word and tokens read | 38 s | `vhs tapes/04-what-the-model-reads.tape` |
| 05-speed-time-to-first-word.mp4 | The shelf: the same question cold (2,773 tokens read, 1.66 s to first word) and from saved working memory (20 tokens, 0.18 s), Qwen3 4B in llama.cpp | 34 s | `vhs tapes/05-speed-ttfw.tape`, with llama-server on port 8080 and `--slot-save-path` set to the vault's `.burrow/kv` |
| 06-weaknesses-burrow-covers.mp4 | Reasoning: plain retrieval makes Gemma refuse a sum, the engine leaves the vault out and gets 756. Hallucination: Ugandan law, "I don't know from what you were shown". Stale memory: the cited Act is edited and the Ledger says check again | 60 s | `vhs tapes/06-weaknesses.tape` |

The clips are kept out of git (see `.gitignore`); the tapes re-record them. The demo vault lives in `~/BurrowDemo/Notes`.

Note for the edit: in clip 4 the first word came after 0.12 s because Ollama still held the same excerpts from a run a
minute earlier; the cold figure on that question was 7.34 s. Clip 5 is the deliberate comparison.

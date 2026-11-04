# Limits

What the engine does not do, or does not do well yet. Each comes from the code or from a measurement.

## Where it runs

- **Apple silicon only.** The engine runs on MLX, so it needs an M1 Mac or later. It does not run on Intel Macs,
  Windows or Linux. The Ollama pairing needs MLX too, for its embedder.
- **Local only.** It serves models running on this Mac. There is no plugin for Claude Code, Codex or LM Studio.
  Ollama is the one pairing, and through it memory goes in as words.

## Which models can read notes

- **Every layer must keep keys and values, with plain RoPE.** Notes are the model's own keys and values, so the
  engine can lay them back only for models built that way. It refuses a model with RoPE scaling. Qwen3 1.7B, 4B and
  8B qualify.
- **Hybrid models read words.** Qwen 27B (`Qwen3.8-27B`) keeps a running state instead of keys and values in 48 of
  its 64 layers. It cannot use saved notes, so it reads the engine's memory as words: the same rooms, chosen the same
  way, pasted in as text. That reading is a contender in the benchmarks (`CamrWords` in `camr_engine.ruler.contenders`),
  not an option of `Memory` or `Session`.
- **Notes belong to one model.** Rooms written by one model cannot be read by another. Opening them with a model
  whose notes are a different size fails ("these rooms were written for a different model"). A model whose notes
  are the same size is not caught, and would read nonsense. The words are kept in the index, so the notes could be
  written again for a new model, but there is no tool for it yet.

## Size

- **Notes are big.** One token of notes on Qwen3-1.7B is 112 KiB, about 29,000 times its text. A full room of 512
  tokens is 56 MiB. One scripted 12-week life grew to 963 MB of notes (DECISIONS.md, E-20).
- **Sleep is the answer to that, and it is partial.** Rooms over the disk budget go to sleep as words. But a
  question about an asleep room then reads its words, which is slower, or wakes it, which costs one reading of the
  room by the model.

## What one desk holds

- **One room per question.** The desk holds one room, plus the 4 closest moments as words. Rooms written apart lose
  the thread when laid side by side (DECISIONS.md, E-15 and E-16). A question whose answer is spread over several
  rooms gets only the room of the closest moment, and whatever of the rest is among the closest moments. Two-hop
  questions show this.
- **Bigger rooms did worse.** On the scripted lives, rooms of up to 1,024 or 2,048 tokens knew fewer facts than
  rooms of up to 512 (DECISIONS.md, E-18). The settings were tuned there, on the 1.7B.
- **Short answers by default.** The fixed instructions ask for one short sentence, and answers stop at 40 new tokens
  unless `max_tokens` says more. Longer work needs `then` and `max_tokens`.

## What a small model still does

- **It guesses.** On the scripted lives, Qwen3-1.7B with the engine made up an answer to 25 of 45 questions about
  things never told (E-20). In errands it made up 42 of 45, and never once asked the user (E-25).
- **It is not yet a bigger model.** The old CAMR on the 4B knew 208 of 255 facts, against the engine's 164 on the
  1.7B (E-20).
- **The head start depends on the Mac.** The M5 Pro reads text fast: about 6,600 tokens a second, against about 800
  on the MacBook Air M4 (E-17). At 2,000 words, notes were 4.6 times sooner than reading the words, not the 10 times
  hoped for (E-20). The gap grows with memory: 1.9 times at 250 words, 5.8 times at 3,000.

## Forgetting and privacy

- **There is no way yet to make the engine forget one moment.** Deleting a vault note removes its words from the
  archive, but the moment's notes stay in its room's file, and its words stay in `index.json`. To forget everything,
  delete the memory folder.
- **Memory is plain files.** Room files, the index and the vault are not encrypted. Anyone who can read your home
  folder can read your memory.
- **Editing the vault changes less than it seems.** An edit to a note tagged `core` changes the core. An edit to any
  other note changes its words in the archive, not the room's notes or the words re-read on the desk.
- **Nothing leaves the Mac**, except: the installer downloads `uv` and the models; the Hugging Face suites download
  their data; and the Claude yardstick, when you run it, sends the Long Haul (a scripted, made-up project) to
  Anthropic.

## Sleep and the vault

- **Nothing schedules sleep.** `Memory.fade` must be called by the program using the engine. Naps on the charger,
  distilling checked by a quiz, and settling unsure facts at recall are planned, not built.
- **The vault reads simple front matter.** Values, lists, and what Obsidian writes when a person edits a note.
  Unusual YAML written by hand may not be read.

## One writer at a time

- **A reach folder is open in one process at a time.** A second process gets `ReachBusy`.
- **A bare `Memory` takes no lock.** Open one `Memory` per folder, or use a `Session`, which locks each reach.
- **One model job at a time.** The app answers one request at a time, and benchmarks should run alone on the GPU.

## The app

- As of 4 November, the app's own memory is a `Memory` with rooms only: the vault, the core and the tiers are
  options of the library. The app was being rebuilt that night; the [user guide](../USER_GUIDE.md) describes it.

## The Ollama pairing

- **Words only.** Notes go into the prompt as text, at most 8 notes and 512 tokens by default.
- **The macOS app route is untried.** It was read from the app's source. It needs "Expose Ollama to the network",
  which also opens Ollama to the local network. See [Pairing with Ollama](ollama.md).

## The benchmarks

- **The Long Haul is scripted.** One made-up project, fixed by its seed. It is built to be hard in known ways, not to
  be a sample of real work.
- **Rules can miss a right answer.** Grading by rule is the same every time, but an answer worded in an unexpected
  way can be marked wrong. Every record keeps the raw answer, so it can be checked by hand.
- **LongMemEval needs a judge model** (Claude Haiku 5.5), so its verdicts are not by rule.
- **Claude reads the most recent 1M tokens.** At the 2M cut, the start of the history does not fit in its window.
  That is the point of the test, and it is also why Claude is a yardstick, not a contender with memory.
- **One machine.** Every number in these pages was measured on one MacBook Pro M5 Pro with 24 GB. Other Macs will
  differ. Records note the machine and how busy it was.

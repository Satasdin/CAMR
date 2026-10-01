# CAMR Personal: your model, a memory that grows

CAMR Personal is the research engine packaged as an app you run on your own
computer. You bring any model you already have in [Ollama](https://ollama.com).
CAMR gives it a **long-term memory**: your notes, files, the things you tell it
in chat, and answers you approved. The model's weights never change. It gets
more useful because its memory grows, and that costs **storage, not compute**.

> **Why not just a bigger model or a longer context window?** In our benchmarks
> (`docs/FINDINGS.md`), a 1.5B model with CAMR beat a frontier cloud model on
> long-tail facts (80% vs 67%) and answered several times faster on a laptop
> CPU. Memory is read a few hundred tokens at a time: the model sees only the
> notes it needs, so the memory can grow to tens of thousands of notes without
> ever filling the context window.

## How it differs from plain RAG

| | Plain RAG | CAMR Personal |
|---|---|---|
| What goes in | Documents you index once | Documents **plus** your chat, "remember that…" facts, and 👍-approved answers, **as you use it** |
| How much is read | Fixed top-k | **Gated**: abstains when nothing is relevant, admits only notes close to the best one (fewer tokens, less distraction for small models) |
| Multi-step questions | Similarity only | **Entity bridging**: a note that names another entity pulls in that entity's notes (on 2WikiMultiHopQA, full-evidence recall rose from 36% to 78%) |
| Long conversations | Truncated at the context window | What you said becomes memory and is recalled when relevant, weeks later |
| Getting better | Re-index | 👍 stores the answer; your corrections ("remember that…") override |
| Honesty | Usually silent | Shows the notes it used and how grounded the answer was, or says it found nothing |

It is closer to **fine-tuning by storage**: the model adapts to *you*, but the
adaptation lives in a file you can read, search, edit, back up and delete.

## Install (about 5 minutes)

1. Install **Ollama** from <https://ollama.com/download> and pull a model:
   ```bash
   ollama pull qwen2.5:1.5b        # recommended start: fast, strong with memory
   # 8 GB+ RAM:  ollama pull llama3.2:3b     (best small model on multi-step questions)
   ```
2. Install **CAMR Personal**:
   - **macOS / Linux**
     ```bash
     curl -fsSL https://raw.githubusercontent.com/Satasdin/CAMR/main/install/install.sh | bash
     ```
   - **Windows (PowerShell)**
     ```powershell
     irm https://raw.githubusercontent.com/Satasdin/CAMR/main/install/install.ps1 | iex
     ```
   - or, with Python 3.10+: `pip install "camr[app] @ git+https://github.com/Satasdin/CAMR.git"`
3. Start it:
   ```bash
   camr app            # opens http://localhost:8502
   ```

The first start downloads the small embedding model (about 130 MB). After that,
CAMR works offline.

## Using it

![Chat with sources](figures/app/1_chat.png)

- **Chat.** Ask anything. Each answer shows the notes it used, how grounded it
  was, and how long memory lookup and answering took.
- **"remember that …"** stores a fact instantly, without calling the model.
- **👍** saves a good answer to memory. **👎** records that it missed.
- **Teach.** Paste notes, or add `.txt`, `.md` or `.pdf` files.

![Teach](figures/app/2_teach.png)

- **Memory.** Search everything it knows and see where each item came from.
  **Forget** deletes an item completely.
- **Growth.** How much it knows, how often it answers from memory, and how
  memory has grown day by day.

![Growth](figures/app/4_growth.png)

## Which model should I use?

These were measured on a 4-core laptop-class CPU with no GPU (`docs/FINDINGS.md` F10):

| Your RAM | Model | With CAMR: facts / multi-step | Seconds per answer |
|---|---|---|---|
| 4–8 GB | `qwen2.5:1.5b` | 80% / 50% | ~2–3 s |
| 8–16 GB | `llama3.2:3b` | 73% / 57% | ~4–5 s |
| 16 GB+ and patience | `qwen2.5:14b`, `gemma3:12b` | 73–79% / 63% | ~16–24 s |

On a CPU, models above about 4B gave more accurate multi-step answers but were
slower than asking a cloud model. With a GPU or Apple Silicon, they are much faster.

## Privacy

- Everything stays in `~/.camr/` (`memory.sqlite` and `settings.json`). Nothing
  is uploaded. The app only talks to Ollama on your own machine.
- To back up or move your memory, copy that folder. To wipe it, delete the folder.
- **Settings → Download feedback file** exports usage metrics only: counts,
  timings and 👍/👎. Your notes and messages are included only if you tick the
  box. Sharing it is up to you.

## Feedback

Please tell us how it went: open a [feedback issue](https://github.com/Satasdin/CAMR/issues/new?template=feedback.yml). We especially want to know:
did answers get better as you taught it more, what did it get wrong, and how fast was it on your machine?

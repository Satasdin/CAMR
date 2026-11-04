# Python library

The engine is a Python package, `camr`. It is not on PyPI. Install it from the repository's `v2` folder:

```sh
uv pip install --python .venv/bin/python -e .
```

There are two ways in:
- **`Memory`**: one memory folder. The plain engine.
- **`Session`**: a conversation over several reaches (session, project, agent, global), with the memory switch. See
  [Reach and the switch](reach.md).

Both have the same two calls: `remember` keeps a moment, and `answer` answers from memory. Every signature below is
copied from the code.

## The models

```python
from camr_engine.models import Embedder, Reader

reader = Reader()        # Qwen3-1.7B, 4-bit, through MLX
embedder = Embedder()    # Qwen3-Embedding-0.6B, 4-bit, through MLX
```

```python
Reader(repo: str = READER, max_tokens: int = MAX_ANSWER_TOKENS)
Embedder(repo: str = EMBEDDER)
```

| Name | Value |
| --- | --- |
| `READER` | `mlx-community/Qwen3-1.7B-4bit` |
| `READER_BIG` | `mlx-community/Qwen3-4B-Instruct-2507-4bit` |
| `READER_27B` | `mlx-community/Qwen3.8-27B-4bit` (reads memory as words only: see [Limits](limits.md)) |
| `EMBEDDER` | `mlx-community/Qwen3-Embedding-0.6B-4bit-DWQ` |
| `MAX_ANSWER_TOKENS` | 40 |

The reader decodes greedily with thinking off, so the same question on the same memory gets the same answer on the
same Mac. Different chips can differ slightly (DECISIONS.md, E-17). Answers stop at 40 new tokens unless you pass `max_tokens`. Loading a model downloads it the first time.

## A first memory

This is the health check (`camr_engine/app/__main__.py`), with a folder that lasts:

```python
import datetime as dt
from pathlib import Path

from camr_engine.memory import Memory
from camr_engine.models import Embedder, Reader

reader, embedder = Reader(), Embedder()
m = Memory(reader, embedder, Path("~/.camr/mine").expanduser())
m.remember("[2026-01-05] My sister Amina moved to Nakuru last week.", 0)
m.remember("[2026-01-06] Paid the electricity bill.", 1)
reply = m.answer("Where does my sister live?", dt.date(2026, 1, 7))
print(reply.text, f"first word after {reply.ttft_s:.3f} s")
m.save()
m.close()
```

Two habits worth keeping:
- **Start each moment with its date**, as `[2026-01-05] ...`. The app and the scripted lives do this. The model then
  sees when each thing happened, and the Ollama pairing dates the engine's moments by it.
- **Save before closing a plain memory.** With none of the new layers on, `close()` does not save the index (as in
  step 1). With any layer on, `close()` saves everything first.

## Memory

```python
Memory(reader, embedder, path: Path, *, room_tokens: int = ROOM_TOKENS, join: float = JOIN,
       closest: int = CLOSEST, allowance: int = ALLOWANCE_BYTES, log: bool = True,
       notebook: Notebook | None = None, vault: Vault | bool = False, reach: str | None = None,
       core: Core | bool = False, core_tokens: int = CORE_TOKENS, tiers: Tiers | None = None,
       metrics: Meter | bool = False)
```

| Option | Default | What it does |
| --- | --- | --- |
| `path` | | the memory folder; made if missing, reopened if it holds a memory |
| `room_tokens` | 512 | the most tokens a room holds |
| `join` | 0.80 | how close a moment must be to a room's closest moment to join it |
| `closest` | 4 | moments re-read as words after the room |
| `allowance` | 256 MiB | a full room's notes must fit inside this |
| `log` | `True` | write `events.jsonl`, and watch attention while answering |
| `notebook` | its own | a header already read, shared by several memories (a session passes one) |
| `vault` | `False` | `True` keeps the vault in `<path>/vault`; or pass a `Vault` |
| `reach` | `None` | the reach label written on vault notes, such as `project:kitchen` |
| `core` | `False` | `True` builds a core from the vault's `core` notes (needs `vault=True`); or pass a `Core` |
| `core_tokens` | 256 | the core's budget |
| `tiers` | `None` | RAM and disk budgets: a `Tiers` (see [RAM, the SSD and sleep](swapping.md)) |
| `metrics` | `False` | `True` appends one record per answer to `<path>/metrics.jsonl`; or pass a `Meter` |

With every option at its default, the engine computes exactly what it did in step 1.

### remember

```python
Memory.remember(self, text: str, day: int, *, date: dt.date | None = None,
                tags: tuple[str, ...] | list[str] = (), pinned: bool = False)
```

Keeps one moment. It is embedded, placed in a room, read by the model with that room's earlier moments in view, and
its notes are appended to the room's file.

| Argument | What it is |
| --- | --- |
| `text` | the moment's words |
| `day` | the moment's day number. Count from any start you like, the same start every time. The app counts from 5 January 2026. |
| `date` | the moment's date, for its vault note (worked out from `day` once the vault has seen both) |
| `tags` | tags for its vault note; `"core"` puts it in the core, when the core is on |
| `pinned` | a pinned vault note never fades; a pinned `core` note goes into the core first |

`date`, `tags` and `pinned` only matter when there is a vault.

It returns the `Moment`: `mid` (its number), `room`, `day`, `text`, `start` (its first token in the room's file) and
`tokens`.

### answer

```python
Memory.answer(self, question: str, today: dt.date, *, then: str = "", tools: list | None = None,
              max_tokens: int | None = None, kind: str = "answer", chosen: Recall | None = None,
              day: int | None = None, started: float | None = None, core: Core | None | object = _OWN,
              record: bool = False, among: Iterable[Memory] | None = None, **extra)
```

Answers from the desk: the room holding the moment closest to the question, then the closest moments as words, then
the question.

| Argument | What it is |
| --- | --- |
| `question` | what is asked |
| `today` | today's date; the model is told it |
| `then` | instructions for this kind of request, read after the notes |
| `tools` | tools in the OpenAI function format, for one tool call (see Errands below) |
| `max_tokens` | the most tokens to write (the reader's own cap, 40, when not given) |
| `kind` | the event type in `events.jsonl` (`"answer"`; errands use `"agent"`) |
| `day` | today's day number for the vault (worked out from `today` when not given) |
| `chosen`, `started`, `core`, `record`, `among` | for a session: the room it chose across its reaches, when the question was asked, its core, and the memories whose history and disk the record counts |
| `**extra` | added to the answer's line in `events.jsonl` |

It returns a `Reply`:

| Field | What it is |
| --- | --- |
| `text` | the answer |
| `ttft_s` | seconds from the question to the first word, choosing and reading the room included |
| `gen_tps` | tokens written per second |
| `prompt_tokens` | every token the model saw: header, core, room, words and question |
| `gen_tokens` | tokens written |
| `pieces` | the text each written token added, in order |
| `metrics` | the answer's `Record`, when `metrics` is on (or `record=True`): see [Metrics](metrics.md) |

The instructions at the top of every prompt are fixed, because their notes are read once and kept:

> You are a personal assistant that remembers the user's own notes. Answer the user's question in one short
> sentence, using only the notes below. If the notes do not contain the answer, reply exactly: I don't know.

Use `then` for anything else a request needs. It is read after the notes, so the header never changes.

### The other calls

| Call | What it does |
| --- | --- |
| `choose(question, *, vec=None) -> Recall` | the room holding the closest moment, and the closest moments; reads nothing from the SSD |
| `recall(question, *, chosen=None, core=...) -> Recall` | chooses, reads the room, and lays the desk (`Recall.desk`) |
| `use(moments, today=None, day=None)` | marks moments as used: their vault notes gain strength |
| `fade(today: int) -> tuple[int, list[int]]` | one pass of sleep: see [RAM, the SSD and sleep](swapping.md) |
| `state() -> dict` | what the memory holds and where |
| `history_tokens() -> int` | every token the memory holds, awake or asleep |
| `folder_bytes() -> int` | everything the memory keeps on disk |
| `save()` | saves the index, the vault's index and the tiers' state |
| `close()` | lets go of the rooms (saving first when any layer is on) |

A `Recall` holds `room`, `closest`, `tokens`, `bytes`, `desk`, `seconds` (per step), `score` (how close the
closest moment is), `tier`, `read_bytes`, `asleep`, `core` (core tokens on the desk) and `reach`. Its `ms` property
gives the steps in milliseconds, and `gbps` the SSD bandwidth.

With a vault, `m.vault` is the `Vault`. A moment's note id is `m.vault.moment_id(moment.mid)`. Some of its calls:
`read(nid)`, `notes(tag=None, room=None)`, `neighbours(nid, n=None)`, `pin(nid, on=True)`, `tag(nid, *tags)`,
`untag(nid, *tags)`.

## Session

```python
Session(reader, embedder, *, root: Path = ROOT, name: str | None = None, project: str | None = None,
        agent: str | None = None, reads: Iterable[str | Reach] = ("session", "global"),
        writes: str | Reach = "session", on: bool = True, vault: bool = True, core: bool = False,
        core_tokens: int = CORE_TOKENS, tiers: dict | None = None, metrics: bool = False,
        plain_system: str | None = None, **settings)
```

| Option | Default | What it does |
| --- | --- | --- |
| `root` | `~/.camr` | where the reach folders live |
| `name` | a new id | the session's id, such as `20261104-021500-a1b2` |
| `project`, `agent` | `None` | the names of those reaches; needed to read or write them |
| `reads` | `("session", "global")` | the reaches read, in order of preference |
| `writes` | `"session"` | where new moments go (read too) |
| `on` | `True` | memory on; off is the plain model |
| `vault` | `True` | every reach keeps a vault (on by default here) |
| `core` | `False` | one core from the `core` notes of every reach read |
| `core_tokens` | 256 | the core's budget |
| `tiers` | `None` | a dict of `Tiers` options; each reach gets its own disk budget, and all share one RAM budget |
| `metrics` | `False` | each reach writes its own `metrics.jsonl` |
| `plain_system` | `None` | the system prompt to use with memory off, instead of the same prompt with no notes |
| `**settings` | | other `Memory` options for every reach: `room_tokens`, `join`, `closest`, `allowance`, `log` |

A reach another session in this process already has open is shared as it is, with the settings it was opened with.

### remember and answer

```python
Session.remember(self, text: str, day: int, *, to: str | Reach | None = None, **kw)
Session.answer(self, question: str, today: dt.date, **kw)
```

- `remember` keeps a moment in the session's own reach, or `to` another reach it reads. `**kw` goes to
  `Memory.remember` (`date`, `tags`, `pinned`). It returns the `Moment`, or `None` while memory is off.
- `answer` answers from the best room over every reach. The wait is counted from the question, choosing included.
  `**kw` goes to `Memory.answer` (`then`, `tools`, `max_tokens`, `kind`, `day`). With memory off, it calls
  `plain` instead. The reply always has `metrics`.

### The other calls

| Call | What it does |
| --- | --- |
| `choose(question) -> tuple[Memory, Recall]` | the best room over every reach; earlier reaches win ties |
| `recall(question) -> Recall` | chooses and lays the desk |
| `plain(question, today, *, then="", tools=None, max_tokens=None)` | the model with no memory |
| `switch(on: bool)` | memory on or off |
| `memory(reach=None) -> Memory` | one reach's memory (the session's own by default) |
| `state() -> dict` | each reach's memory, and the core |
| `save()` | saves every reach |
| `close()` | saves every reach and lets go of them; a `with` block does this |

`s.last` is the last answer's `Recall` (`None` after an answer with memory off). `s.meter` holds every answer's record, memory on or off, and
`s.meter.summary()` gives medians and 90th percentiles.

### A session with a project and a core

```python
import datetime as dt

from camr_engine.models import Embedder, Reader
from camr_engine.reach import Session

reader, embedder = Reader(), Embedder()
with Session(reader, embedder, project="kitchen", reads=("session", "project", "global"), core=True) as s:
    s.remember("[2026-01-05] I build the site for Mama Njeri's Kitchen in Nairobi.", 0, to="global",
               tags=["core"], pinned=True)
    s.remember("[2026-01-05] The fee is 1% rounded up to the next 5 shillings, at least 10.", 0, to="project")
    reply = s.answer("What is the fee rule?", dt.date(2026, 1, 6))
    print(reply.text)
    print(s.last.reach, s.last.room, reply.metrics.first_word_s)
```

## Errands: one tool call from memory

`camr_engine.agent.act` gives an open `Memory` one task. It answers with the ten pretend tools (`camr_engine.agent.TOOLS`,
from `book_ride` to `ask_user`) and returns the call:

```python
from camr_engine.agent import act

tool, args, reply = act(m, "Book me a ride to my sister's home.", dt.date(2026, 1, 7))
print(tool, args)   # the tool it called, and the arguments it filled from memory
```

```python
act(memory, task_text: str, today, **log) -> tuple[str | None, dict, object]
```

For your own tools, call `answer` with `then` and `tools`, and read the call with `camr_engine.agent.parse`:

```python
from camr_engine.agent import parse

reply = m.answer(task, today, then="Do this with exactly one tool call.", tools=my_tools, max_tokens=120)
tool, args = parse("".join(reply.pieces))
```

`parse` reads both Qwen3's JSON tool calls and the XML form that Qwen 3.5 and later write.

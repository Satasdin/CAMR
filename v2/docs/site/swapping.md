# RAM, the SSD and sleep

A room's notes can be in one of three places when a question needs them. The engine calls them tiers.

| Tier | What sits there | What a question pays |
| --- | --- | --- |
| RAM | the core, and the hot rooms: the most recently used rooms that fit the RAM budget | nothing to read; the notes are already arrays the desk can take |
| SSD | every awake room's file | one burst read of the room, then a copy into GPU memory |
| Vault (asleep) | rooms whose notes were put away; their moments stay as words | the room's moments read as words, or the room woken |

Without tiers, every answer reads its room from the SSD. That is how step 1 ran, and what its measurements used.
Tiers are an option: `Memory(..., tiers=Tiers(...))`, or `Session(..., tiers={...})`.

## The budgets

```python
Tiers(ram_bytes: int = RAM_BYTES, disk_bytes: int | None = None, *, wake: bool = False, pool: Pool | None = None)
```

| Option | Default | What it does |
| --- | --- | --- |
| `ram_bytes` | 512 MiB | RAM for the core and the hot rooms together: about nine full rooms of the 1.7B's notes |
| `disk_bytes` | `None` (no limit; 8 GB a reach in the Mac app) | the most the awake room files may take on the SSD |
| `wake` | `False` | wake an asleep room when a question needs it, instead of reading its words |
| `pool` | its own | RAM shared with other memories' tiers |

## RAM and the SSD

- A room read from the SSD is kept hot in RAM, already turned into arrays. The next question that needs it skips
  the SSD and the copy.
- When RAM is full, the least recently used hot room goes first. Letting it go writes nothing: the room's file is
  still on the SSD.
- A room bigger than all the RAM left beside the core is not kept hot, and pushes nothing out.
- The core always stays in RAM.
- A new moment added to a hot room is joined onto the hot copy, so it always matches the file.
- In a `Session`, each reach gets its own disk budget, and all of them share one RAM budget, the core counted once.

Every read says where it came from. A `Recall` carries `tier` (`"ram"`, `"ssd"` or `"vault"`), `read_bytes`,
`gbps` and `seconds` per step. `Memory.tiers.state()` shows what sits in each tier:

```python
{"ram": {"budget_bytes": ..., "used_bytes": ..., "core_bytes": ..., "rooms": [...]},
 "ssd": {"budget_bytes": ..., "used_bytes": ..., "rooms": ...},
 "vault": {"rooms": [...]},
 "hits": {"ram": ..., "ssd": ..., "vault": ...}}
```

On the MacBook Pro M5 Pro, a room is read from the SSD at about 12 GB/s with the cache bypassed. The same files
come from RAM at about 60 GB/s (DECISIONS.md, E-17).

## Storage

A room's file keeps its notes at 16, 8 or 4 bits: `Memory(..., bits=8)`, 8 by default. At 8 or 4 bits every 64
numbers along a head share one scale and one offset (MLX's `mx.quantize`), so a token is still a fixed number of
bytes and a room still grows by appending. A token at 8 bits takes 17/32 of its 16-bit size (about 60 KB on the
1.7B, 78 KB on the 4B and 8B), at 4 bits 9/32. The index records each room's bits, and so does the file's name:
`room-000001.notes` is 16-bit, `room-000001.q8.notes` 8-bit. Rooms written at 16 bits before still read, and a
moment joining one is appended at 16 bits. A model whose heads do not split into groups of 64 keeps 16 bits.

Measured on the Long Haul (`engine:qwen3-1.7b`, 64K and 256K, 34 and 40 questions, 5 November 2026):

| Bits | Right at 64K | Right at 256K | Disk at 256K | First word p50 (256K) | SSD fetch p50 (256K) |
| --- | --- | --- | --- | --- | --- |
| 16 | 14 | 20 | 34.3 GB | 0.098 s | 4.9 ms (54 MB) |
| 8 | 14 | 19 | 18.2 GB | 0.094 s | 2.5 ms (29 MB) |
| 4 | 14 | 18 | 9.7 GB | 0.146 s | 2.0 ms (15 MB) |
| 8, with an 8 GB disk budget | 14 | 20 | 8.6 GB (366 of 759 rooms asleep) | 0.126 s | 0.1 ms (1 MB) |

At 8 bits 61 of the 74 answers were word for word the 16-bit ones, and one verdict changed. At 4 bits 48 were, and
two answers were lost at 256K. So 8 bits is the default. The SSD reads half as much, and turning the bytes back
into numbers costs less than that saves: the room was on the desk in 5.4 ms at the median, against 6.9 ms at 16
bits. With the 8 GB budget, 19 of the 40 questions at 256K read their room as words, and the score held at 20. The
8-bit row is from a second run on a quiet machine; the first, beside another benchmark, gave the same answers.

Rooms already on the SSD can be packed in place, with a dry run first:

```bash
python -m camr_engine.shrink ~/.camr/app/Qwen3-4B-Instruct-2507-4bit/global            # what it would do
python -m camr_engine.shrink ~/.camr/app/Qwen3-4B-Instruct-2507-4bit/global --apply    # do it
```

It writes each room's 8-bit copy beside the old file and checks it: its size, its bytes against packing the old
notes again, and every number within one and a half quantization steps. Only then does the index name the copy,
and only then is the old file deleted. It refuses a reach the app has open.

The Mac app gives each reach a disk budget of 8 GB (`CAMR_SHELF_DISK_GB` sets another). It is held in the warm-up,
before the first question, and again each time a moment is kept, so a shelf stops growing on the SSD.

## Sleep

Notes are about 29,000 times the size of their words. So when the awake room files outgrow `disk_bytes`, rooms go
to sleep.

- **Who sleeps first.** The weakest room first. A room is as strong as its strongest vault note. Among rooms of the
  same strength, the least recently used goes first. Without a vault, all rooms are equally strong, so the least
  recently used sleep first.
- **What sleeping does.** The room's `.notes` file is deleted. Its moments stay in `index.json` and in the vault, as
  words. Their vault notes are marked `asleep: true`, and `events.jsonl` gets a `sleep` line.
- **A question about an asleep room.** The room's moments are read as words, just before the closest moments. That
  costs reading them, as plain text would.
- **Waking.** With `wake=True`, the room's notes are written again from its words instead. The model reads the
  room once, the file goes back on the SSD, and the disk budget is held again with the woken room kept awake. The
  time it took is the `wake` step of the recall.
- **New moments.** An asleep room takes no new moments unless waking is on. A moment that would have joined it
  starts a room of its own.
- **Nothing is destroyed.** Sleep removes notes, never words.

## Fading

`Memory.fade(today)` is one pass of sleep:
1. It picks up every edit a person made to the vault.
2. It brings every note's strength up to day `today`: 5% less for each day unused. Pinned notes keep theirs.
3. It holds the disk budget, putting rooms to sleep as above.

It returns `(notes changed, rooms put to sleep)`.

Nothing calls `fade` on a schedule yet. The program using the engine calls it, for example once a day. A `Session`
has no `fade` of its own; call it on each of its memories:

```python
for m in s.memories.values():
    m.fade(day)
```

## A memory with every layer on

```python
from pathlib import Path

from camr_engine.memory import Memory
from camr_engine.models import Embedder, Reader
from camr_engine.swap import Tiers

reader, embedder = Reader(), Embedder()
m = Memory(reader, embedder, Path("~/.camr/mine").expanduser(), vault=True, core=True,
           tiers=Tiers(ram_bytes=512 * 2**20, disk_bytes=2 * 2**30, wake=True), metrics=True)
```

The same in a session:

```python
from camr_engine.reach import Session

s = Session(reader, embedder, core=True, metrics=True,
            tiers={"ram_bytes": 512 * 2**20, "disk_bytes": 2 * 2**30, "wake": True})
```

## Not built yet

The plan's sleep goes further than this. These parts are designed but not in the code:
- naps that run on their own while the Mac is on its charger;
- distilling what was learnt, checked by a quiz before it is kept;
- settling unsure facts at recall.

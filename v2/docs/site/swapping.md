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
| `disk_bytes` | `None` (no limit) | the most the awake room files may take on the SSD |
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

from engram.memory import Memory
from engram.models import Embedder, Reader
from engram.swap import Tiers

reader, embedder = Reader(), Embedder()
m = Memory(reader, embedder, Path("~/.engram/mine").expanduser(), vault=True, core=True,
           tiers=Tiers(ram_bytes=512 * 2**20, disk_bytes=2 * 2**30, wake=True), metrics=True)
```

The same in a session:

```python
from engram.reach import Session

s = Session(reader, embedder, core=True, metrics=True,
            tiers={"ram_bytes": 512 * 2**20, "disk_bytes": 2 * 2**30, "wake": True})
```

## Not built yet

The plan's sleep goes further than this. These parts are designed but not in the code:
- naps that run on their own while the Mac is on its charger;
- distilling what was learnt, checked by a quiz before it is kept;
- settling unsure facts at recall.

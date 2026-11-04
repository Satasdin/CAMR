# The three layers

The engine keeps memory in three layers. Each answer reads the first two as notes. The third is the archive, kept
as words.

| Layer | Also called | Where it lives | What it holds | When the model reads it |
| --- | --- | --- | --- | --- |
| Core | the subconscious | RAM | the notes of a few standing facts, at most 256 tokens | on every answer |
| Rooms | the conscious | the SSD; with tiers on, the most recently used also in RAM | related moments' notes, at most 512 tokens a room | one room per question |
| Vault | the archive | the SSD, as Markdown files | every moment's words, with links between them | never on the desk: its notes tagged `core` become the core |

*Notes* are what the model writes to itself inside its layers while it reads: its keys and values at every layer.
Reading notes back is not reading text again. The model picks up where it left off.

## The picture

```
  question ──► embed it ──► the closest moment, in any room ──► that moment's room
                                                                   │
        RAM                              SSD                       │        SSD, as words
  ┌───────────────────┐         ┌───────────────────────┐          │   ┌──────────────────────┐
  │ header notes      │         │ room-000000.notes     │ ◄────────┘   │ vault/               │
  │ core notes        │         │ room-000001.notes     │              │   global-000000.md   │
  │ hot rooms         │ ◄─────  │ room-000002.notes ... │              │   global-000001.md   │
  └───────────────────┘  one    └───────────────────────┘              │   [[doors]] between  │
            │            burst                                         └──────────────────────┘
            ▼
  the desk:  header │ core │ room │ 4 closest moments │ today's date, the question │ ──► answer
             └──── already read: notes ────┘ └────────── read now: words ─────────┘
```

In words:
- The question is embedded, and the moment closest to it is found among all the moments kept.
- The room holding that moment is read from the SSD in one burst, or taken from RAM when it is hot.
- The desk is laid left to right, already read, as notes:
  - the header (the fixed instructions);
  - the core;
  - the room.
- The model then reads, as words:
  - the four moments closest to the question, in date order;
  - today's date and the question.
- It writes the answer.
- The vault sits beside all this, and a person browses it. The engine reads its words only to build the core, and
  its strengths to choose which rooms sleep.

## The core: the subconscious

The core is a small block of notes that goes on every desk, right after the header and before the room. It holds
standing facts: who the user is, what never changes.

- It is built from vault notes tagged `core`. Tag a note when you remember it (`tags=["core"]`), with
  `Vault.tag`, or by hand in Obsidian.
- It holds at most 256 tokens (`core_tokens`). Pinned notes go in first, then the strongest, then the oldest. What
  does not fit is left out and listed (`Core.left_out`).
- It is read once by the model and kept in RAM as notes, so it is not read again on each answer.
- Before each answer the vault is looked at again, cheaply. A core note edited in Obsidian, a new note tagged
  `core`, or a deleted one changes the core on the next answer. Only then is the core written again.
- Rooms were written straight after the header. On a desk with the core, a room sits further along, so its keys are
  turned by the core's length (keys hold a word's position as a rotation, called RoPE).

The core is off by default. It needs the vault: `Memory(..., vault=True, core=True)`, or `Session(..., core=True)`.

## The rooms: the conscious

A room is a page of related moments, written together, kept as one file on the SSD.

- **Joining a room.** A new moment is embedded. It joins the room of its closest moment when that moment is at
  least 0.80 close (`join`) and the room has space. A room holds at most 512 tokens (`room_tokens`). When that room
  is full, the next closest moment's room is tried, while it is still 0.80 close. Otherwise the moment starts a new
  room.
- **Written as one page.** The new moment is read with its room's earlier moments in view, and its notes are
  appended to the room's file. Inside a room, the notes are the same computation as reading its words.
- **Read in one burst.** A room's file is read whole, in 1 MB pieces, eight at once, with the Mac's file cache
  bypassed. So a read is a real SSD read, never a copy already in RAM.
- **One room on the desk, plus four closest moments as words.** Rooms written apart lose the thread when laid side
  by side. On the scripted lives, one room plus the 4 closest moments as words knew more than three rooms' notes
  (DECISIONS.md, E-15 and E-16).

Notes are large. One token of notes on Qwen3-1.7B is 28 layers × 2 (keys and values) × 8 heads × 128 numbers × 2
bytes: 114,688 bytes, or 112 KiB. That is about 29,000 times the text. A full room of 512 tokens is 56 MiB. This is
why rooms can sleep and why the vault exists.

The rooms are always on. Their settings are `Memory` options: `room_tokens=512`, `join=0.80`, `closest=4`.

## The vault: the archive

The vault is a folder of Markdown notes, one per moment. It opens in Obsidian as it is.

- Each note has front matter (id, day, date, room, reach, moment, tags, strength, pinned, asleep, used, links,
  doors), then the moment's words.
- Links between notes are `[[note-id]]` wikilinks, called *doors*. A door gains 0.5 when its two notes share a room,
  and 1.0 each time they are used in the same answer.
- A note's strength fades 5% a day unless it is used. Each use adds 1.0. A note at strength 1 that goes unused for
  about 45 days falls below 0.1 and counts as faded. Pinned notes never fade.
- Nothing is ever deleted by the engine. A faded note keeps its words. Only a person deletes a note, by deleting its
  file.
- The files are the truth. A hidden index (`.engram-index.json`) only saves reading every file on opening. A note
  changed by hand is read again because its file changed.

A note as the engine writes it:

```markdown
---
id: global-000000
day: 0
date: 2026-01-05
room: 0
reach: global
moment: 0
tags: []
strength: 1.7351
pinned: false
asleep: false
used: 6
as_of: 6
links:
  - "[[global-000001]]"
doors:
  - 1.5
---
[2026-01-05] My sister Amina moved to Nakuru last week.
```

The vault is off by default in `Memory` (`vault=True` turns it on) and on by default in `Session`.

## What a memory folder holds

```
<memory>/
  room-000000.notes    one room's notes, token by token
  index.json           every moment's words, day, room and place in its room
  vectors.npy          every moment's embedding
  events.jsonl         one line per moment kept, answer given, room put to sleep or woken
  metrics.jsonl        one line per answer (with metrics on)
  tiers.json           when each room was last used (with tiers on)
  vault/               one Markdown note per moment, and .engram-index.json
  .lock                held while a process has the folder open (reach folders)
```

The words a desk re-reads come from `index.json`, not from the vault. Editing a vault note changes the core (when it
is tagged `core`). It does not change a room's notes or the words re-read on the desk.

## What it watches while it answers

While it writes each word, the engine records how hard that word looked at each moment on the desk. Attention is
averaged over every head of layers 12, 16, 20 and 24 of 28. A moment is *used* when it draws at least 10% of the
desk's attention over the whole answer. The others were only picked up. Watching cost 0.6% of writing speed
(DECISIONS.md, E-21). Each answer is a line of `events.jsonl`, which the app's brain view replays.

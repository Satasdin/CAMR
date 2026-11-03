# CAMR

**Better, never heavier.** A small language model on a Mac whose memory lives on the SSD and grows. It keeps getting
better at your life without getting slower or bigger.

The plan, with every design decision and the build order:
https://claude.ai/artifact/9ZeFGovgtQHjGfKw7CJ8AN. Technical calls are logged in [DECISIONS.md](DECISIONS.md).

## Where it is

| Step | | Status |
|---|---|---|
| 0 | The ruler: scripted lives, weekly quiz, test records, baselines | done |
| 1 | Rooms and notes | done (2 of 3 marks passed, E-20) |
| 2 | Event log and first brain view | done: the log, and the brain view inside the app |
| 3–6 | Translation layer, sleep, full brain view, proof run | future work (E-22) |

## How CAMR v2 remembers

Every moment it is told is read by the model once, the day it happens, with related moments in view. What the model
writes to itself inside its layers while reading (its *notes*: keys and values at every layer) is saved to the SSD,
in a *room* of related moments. A room is one continuous page of up to 512 tokens.

A question opens the one room holding the moment closest to it. That room is read from the SSD in one burst and laid
in front of the model already read. The four closest moments are re-read as words, just before the question. The
model then reads only those few words and the question.

Why one room and not several: notes written apart don't read well side by side for a 1.7B model. DECISIONS.md E-15
and E-16 have the measurements.

## Install and run (Apple-silicon Mac)

```sh
sh scripts/install.sh
```

The script:
- sets up Python;
- installs CAMR;
- downloads its two models (about 1.3 GB, first run only);
- runs a health check that should end in `PASS`;
- opens the app at http://127.0.0.1:8765.

After that, `.venv/bin/python -m engram.app --open` starts it again. The [user guide](docs/USER_GUIDE.md) covers each tab, a five-minute demonstration, and troubleshooting.

## Use it: the app

One local page, four tabs:
- **Simulation:** a 12-week scripted life arrives day by day in its own memory, quizzed every week. Charts show facts known climbing while the wait and the memory in use stay flat; it takes about 90 seconds.

- **Chat:** tell it things and it remembers them; ask with a question mark and it answers from memory.
- **Errands:** an agent with ten tools. CAMR fills each tool's details from memory ("Set a reminder for my
  neighbour's birthday" becomes `set_reminder(date = "10 October")`).
- **Brain:** any answer or errand replayed word by word. Memory is drawn as a glowing specimen: each moment a red
  cell, each room a lobe. The moments each written word leaned on flare green; the ones only picked up get a white
  ring. A traces strip underneath has one row per moment. "Went wrong" and "Went right" sort a quizzed life's
  answers, for assessing what went wrong or just watching it work.

To see it on a whole life, load one in the Chat tab (about 330 moments) and press "Ask its 100 questions" or
"Give it 100 errands".

## The agent use case: errands (3 November 2026)

Every quiz question becomes an errand whose tool needs that fact. "Where does my vet live?" becomes "Book me a ride
to my vet's home", which calls `book_ride(destination)`. These are the three proof lives, last day, the same 1.7B
reader and tools for each contender:

| Memory behind the agent | Right (of 255) | Made up (of 45 never told) | First word |
|---|---|---|---|
| none (1.7B alone) | 1 | 44 | 0.15 s |
| CAMR v1 | 40 | 45 | 0.16 s |
| **CAMR v2** | **122** | 42 | 0.19 s |

CAMR v2 does three times as many errands right as CAMR v1, which only matches it at answering questions.
None of them ever asks when it doesn't know (DECISIONS.md E-25).

## Results on the MacBook Pro M5 Pro (3 November 2026)

Week 12 of the three proof lives (seed 1), added together. By then each life has told 85 facts and asked 15
questions about things it never told.

| Contender | Knows (of 255) | False memories (of 45) | Wait for first word | Peak RAM |
|---|---|---|---|---|
| 1.7B alone | 0 | 0 | 0.05 s | 1.31 GB |
| Perfect reader (everything pasted in) | 90 | 17 | 1.90 s, climbing | 2.77 GB |
| Old CAMR, 1.7B | 166 | 29 | 0.15 s | 2.24 GB |
| Old CAMR, 4B | 208 | 10 | 0.35 s | 3.58 GB |
| **CAMR v2, 1.7B** | **164** | **25** | **0.07 s** | **1.82 GB** |
| CAMR v2, same memory read as words | 163 | 24 | 0.09 s | 2.20 GB |

- **Never heavier, so far.** CAMR v2's wait stayed between 0.066 and 0.070 s for all twelve weeks, and its RAM between
  1.74 and 1.83 GB, while its notes on the SSD grew from 82 MB to 963 MB.
- **As good as the CAMR v1 on the same model,** at half the wait and 0.4 GB less RAM, with none of its
  hand-written rules.
- **Notes answer like words:** the same answer 96.8% of the time, and 164 facts against 163.
- **Not yet the 4B.** Knowing more and inventing less is the work of steps 3 to 6.

How the wait grows with memory on the desk (`python -m engram.ruler speed`, the SSD read with the cache bypassed):

| Words in the room | Notes | Reading the words | Notes sooner by |
|---|---|---|---|
| 250 | 0.078 s | 0.148 s | 1.9× |
| 1,000 | 0.116 s | 0.431 s | 3.7× |
| 2,000 | 0.233 s | 1.080 s | 4.6× |
| 3,000 | 0.278 s | 1.605 s | 5.8× |

The plan expected 10× from measurements on a MacBook Air, which read text eight times slower than this Mac. The
first baselines, measured on that Air, are in commit 776fecf.

![student](records/charts/growth-student-s1.svg)
![farmer](records/charts/growth-farmer-s1.svg)
![developer](records/charts/growth-developer-s1.svg)

## The ruler

Three scripted 12-week lives (a student, a dairy-cooperative manager, a developer) and the same 100-question quiz
every week. Every run writes a dated test record to `records/`, naming the machine and the code that made it.

```sh
uv venv --python 3.12 && uv pip install -e ".[dev,baseline]"
uv pip install --no-deps -e ~/Desktop/camr-repo           # the CAMR v1, for its contender
python -m engram.ruler life --persona farmer --seed 0     # read a life and its quiz
python -m engram.ruler run --persona student --seed 1 --contender engram
python -m engram.ruler chart --persona student --seed 1   # records/charts/growth-student-s1.svg
python -m engram.ruler speed --persona student            # first word by memory on the desk
python -m engram.ruler errands --persona farmer --seed 1 --contender engram   # the agent use case
scripts/errands.sh                                         # errands for every contender and life
scripts/step1.sh                                           # every contender through the three proof lives
pytest
```

Contenders:
- `bare`: the model alone.
- `perfect`: every note pasted in.
- `camr`: the CAMR v1 on the same models.
- `camr-4b`: the CAMR v1 with a model more than twice the size.
- `engram`: CAMR v2, rooms and notes (the contender's code name).
- `engram-words`: CAMR v2's memory read as words.

Models (MLX, downloaded once): Qwen3-1.7B-4bit, Qwen3-4B-Instruct-2507-4bit, Qwen3-Embedding-0.6B-4bit-DWQ.

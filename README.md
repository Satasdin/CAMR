# engram

**Better, never heavier.** A small language model on a Mac whose memory lives on the SSD and grows. It keeps getting
better at your life without getting slower or bigger.

The plan, with every design decision and the build order:
https://claude.ai/artifact/9ZeFGovgtQHjGfKw7CJ8AN. Technical calls are logged in [DECISIONS.md](DECISIONS.md).

## Where it is

| Step | | Status |
|---|---|---|
| 0 | The ruler: scripted lives, weekly quiz, test records, baselines | done |
| 1 | Rooms and notes | done (2 of 3 marks passed, E-20) |
| 2 | Event log and first brain view | next |
| 3 | Translation layer and shorthand | |
| 4 | Sleep | |
| 5 | The full brain view | |
| 6 | The proof run | |

## How engram remembers (step 1)

Every moment it is told is read by the model once, the day it happens, with related moments in view. What the model
writes to itself inside its layers while reading (its *notes*: keys and values at every layer) is saved to the SSD,
in a *room* of related moments. A room is one continuous page of up to 512 tokens.

A question opens the one room holding the moment closest to it. That room is read from the SSD in one burst and laid
in front of the model already read. The four closest moments are re-read as words, just before the question. The
model then reads only those few words and the question.

Why one room and not several: notes written apart don't read well side by side for a 1.7B model. DECISIONS.md E-15
and E-16 have the measurements.

## Results on the MacBook Pro M5 Pro (3 November 2026)

Week 12 of the three proof lives (seed 1), added together. By then each life has told 85 facts and asked 15
questions about things it never told.

| Contender | Knows (of 255) | False memories (of 45) | Wait for first word | Peak RAM |
|---|---|---|---|---|
| 1.7B alone | 0 | 0 | 0.05 s | 1.31 GB |
| Perfect reader (everything pasted in) | 90 | 17 | 1.90 s, climbing | 2.77 GB |
| Old CAMR, 1.7B | 166 | 29 | 0.15 s | 2.24 GB |
| Old CAMR, 4B | 208 | 10 | 0.35 s | 3.58 GB |
| **Engram, 1.7B** | **164** | **25** | **0.07 s** | **1.82 GB** |
| Engram, same memory read as words | 163 | 24 | 0.09 s | 2.20 GB |

- **Never heavier, so far.** Engram's wait stayed between 0.066 and 0.070 s for all twelve weeks, and its RAM between
  1.74 and 1.83 GB, while its notes on the SSD grew from 82 MB to 963 MB.
- **As good as the old CAMR on the same model,** at half the wait and 0.4 GB less RAM, with none of its
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
uv pip install --no-deps -e ~/Desktop/camr-repo           # the old CAMR, for its contender
python -m engram.ruler life --persona farmer --seed 0     # read a life and its quiz
python -m engram.ruler run --persona student --seed 1 --contender engram
python -m engram.ruler chart --persona student --seed 1   # records/charts/growth-student-s1.svg
python -m engram.ruler speed --persona student            # first word by memory on the desk
scripts/step1.sh                                           # every contender through the three proof lives
pytest
```

Contenders:
- `bare`: the model alone.
- `perfect`: every note pasted in.
- `camr`: the old CAMR on the same models.
- `camr-4b`: the old CAMR with a model more than twice the size.
- `engram`: rooms and notes.
- `engram-words`: engram's memory read as words.

Models (MLX, downloaded once): Qwen3-1.7B-4bit, Qwen3-4B-Instruct-2507-4bit, Qwen3-Embedding-0.6B-4bit-DWQ.

# Metrics

Every answer records what it knew and what it cost. A memory that knows more but makes a person wait longer, or
fills the Mac's RAM, has not won.

## Graded

A benchmark record gives every answer a `verdict`, by rule (see [Benchmarks](benchmarks.md)):

| What | Verdict |
| --- | --- |
| Right | `right` |
| Wrong | `wrong` |
| Stale: a value an update replaced | `stale` |
| Honest: declined what was never told | `right_abstain` in the suites and the scripted lives; `right` on a Long Haul `never` question |
| False memory: answered something never told | `false_memory` |
| Declined something that was told | `declined` (`missed` in the scripted lives) |

## Measured

The engine measures every answer itself, as an `engram.metrics.Record`:

| What | Field | How it is counted |
| --- | --- | --- |
| Time to the first word | `first_word_s` | from the question to the first word: choosing, reading the room, laying the desk and reading the words all count |
| Total time | `total_s` | from the question to the last word |
| Prefill speed | `prefill_tps` | tokens read as words, per second, before the first word |
| Decode speed | `decode_tps` | tokens written per second |
| Retrieval time | `retrieval_ms` | per step: `choose`, `core`, `fetch` (the SSD read), `wake`, `desk`, and `total` |
| Where the room came from | `tier` | `ram`, `ssd` or `vault` (asleep) |
| Bandwidth | `read_bytes`, `gbps` | bytes read from the SSD for this answer, and how fast |
| The read's share of the wait | `read_share` | SSD read time over the time to the first word |
| Context used | `context_tokens` | every token the model saw: header, core, room, words and question |
| The whole history | `history_tokens` | every token the memory holds, awake or asleep, over every reach read |
| Read as words | `new_tokens` | the tokens read this answer; the rest were already notes |
| Answer length | `answer_tokens` | tokens written |
| Peak RAM | `peak_ram_bytes`, `peak_mlx_bytes` | the process's peak resident memory so far, and MLX's own peak |
| Disk | `disk_bytes` | the memory folders on disk: room files, indexes, logs and vaults |

Each record also has the `question`, the `room`, the `reach` and the time (`at`).

Peak RAM is the process's peak so far, not this answer's alone. A run that loads a bigger model first keeps that
peak.

## Where they go

- `Memory(..., metrics=True)` appends one JSON line per answer to `<memory>/metrics.jsonl`.
- A `Session` keeps every answer's record in `s.meter`, memory on or off, and sets it on the reply as
  `reply.metrics`.
- Benchmark records carry one metrics dict per answer, with the same keys for every contender and `None` where a
  contender cannot know: `ttft_s`, `total_s`, `prefill_tps`, `decode_tps`, `retrieval_ms`, `bytes_read`, `gbps`,
  `read_share`, `context_tokens`, `history_tokens`, `peak_ram_gb`, `disk_gb` and `tier`.

## Medians and the 90th percentile

`summary` gives the median (`p50`) and the 90th percentile (`p90`) of each time and size over many answers, the
largest history and peak RAM, the last disk size, and how many answers came from each tier.

```python
from pathlib import Path

from engram.metrics import Meter, summary

rows = Meter.read(Path("~/.engram/mine/metrics.jsonl").expanduser())
print(summary(rows)["first_word_s"])        # {"p50": ..., "p90": ...}
print(summary(rows)["retrieval_ms"]["fetch"])
```

```python
Meter(path: Path | None = None)
Meter.read(path: Path) -> list[dict]
summary(records: list) -> dict
```

## For Claude

Every Claude call records:
- input tokens, and the tokens read from and written to the prompt cache;
- output tokens, thinking included, and the thinking tokens apart;
- the time to the first token and the total time;
- the dollars it cost at list price.

Each call is a line of `records/bench/claude-ledger.jsonl`. The prices are in [Benchmarks](benchmarks.md).

## For the Ollama pairing

The proxy measures each request apart: what it added before Ollama saw the request, the recall time, the wait for
the first byte, and Ollama's own speeds. See [Pairing with Ollama](ollama.md).

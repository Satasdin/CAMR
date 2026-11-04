"""The ruler from the command line.

  python -m camr_engine.ruler run --persona student --seed 1 --contender camr
  python -m camr_engine.ruler chart --persona student --seed 1
  python -m camr_engine.ruler speed --persona student             # first word by memory on the desk: notes vs words
  python -m camr_engine.ruler errands --persona farmer --seed 1 --contender camr   # the agent use case
  python -m camr_engine.ruler life --persona farmer --seed 0      # look at a life and its quiz
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from camr_engine.ruler.life import PERSONAS, build

CONTENDERS = ["bare", "perfect", "camr", "camr-4b", "camr", "camr-words", "bare-27b", "camr-27b", "camr2-words-27b"]
# min_similarity for the old CAMR with the MLX embedder, chosen on the development lives (seed 0): DECISIONS.md E-04
CAMR_MIN_SIMILARITY = 0.65


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.ruler")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("run", help="run a contender through a life and write a test record")
    r.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    r.add_argument("--seed", type=int, default=1)
    r.add_argument("--contender", choices=CONTENDERS, required=True)
    r.add_argument("--weeks", type=int, default=12)
    r.add_argument("--limit", type=int, help="ask only the first N questions (for quick checks)")
    r.add_argument("--quiz-weeks", type=int, nargs="*", help="quiz only these weeks (a big reader is slow)")
    r.add_argument("--min-similarity", type=float, default=CAMR_MIN_SIMILARITY)
    r.add_argument("--records", type=Path)
    c = sub.add_parser("chart", help="draw the growth chart of a life from its records")
    c.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    c.add_argument("--seed", type=int, default=1)
    c.add_argument("--records", type=Path)
    e = sub.add_parser("errands", help="every quiz question as a task with tools, on the life's last day")
    e.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    e.add_argument("--seed", type=int, default=1)
    e.add_argument("--contender", choices=["bare", "camr", "camr", "camr2-words"], required=True)
    e.add_argument("--reader", choices=["1.7b", "27b"], default="1.7b")
    e.add_argument("--records", type=Path)
    s = sub.add_parser("speed", help="time to first word by memory on the desk: camr's notes against words")
    s.add_argument("--persona", choices=sorted(PERSONAS), default="student")
    s.add_argument("--records", type=Path)
    v = sub.add_parser("life", help="print a life's notes and quiz")
    v.add_argument("--persona", choices=sorted(PERSONAS), required=True)
    v.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    if a.cmd == "life":
        life = build(a.persona, a.seed)
        for d in life.days:
            for n in d.dated():
                print(n)
        print()
        for q in life.questions:
            print(q.qid, q.kind, q.text, [(d, v) for d, v, _ in q.timeline])
        return 0
    if a.cmd == "chart":
        from camr_engine.ruler.chart import draw

        kw = {"records": a.records} if a.records else {}
        print(draw(a.persona, a.seed, **kw))
        return 0

    os.environ.setdefault("HF_HUB_OFFLINE", "1")  # models are already downloaded; a run never touches the network
    from camr_engine.models import READER, READER_BIG, Embedder, Reader
    from camr_engine.ruler import contenders as cs
    from camr_engine.ruler.harness import RECORDS, run

    records = a.records or RECORDS
    if a.cmd == "speed":
        import datetime as dt

        from camr_engine.ruler.speed import measure

        out = records / "speed" / f"{dt.date.today().isoformat()}-{a.persona}.json"
        measure(Reader(READER), Embedder(), records.parent / "work" / f"speed-{a.persona}", a.persona, out)
        print(out)
        return 0
    if a.cmd == "errands":
        from camr_engine.ruler.errands import run as errands

        from camr_engine.models import READER_27B

        big = a.reader == "27b"
        print(errands(build(a.persona, a.seed), a.contender, Reader(READER_27B if big else READER), Embedder(),
                      records.parent / "work" / f"{a.persona}-s{a.seed}-errands-{a.contender}{'-27b' if big else ''}",
                      records, suffix="-27b" if big else ""))
        return 0
    life = build(a.persona, a.seed)
    from camr_engine.models import READER_27B

    reader = Reader(READER_BIG if a.contender == "camr-4b" else READER_27B if a.contender.endswith("-27b") else READER)
    if a.contender in ("bare", "bare-27b"):
        contender = cs.Bare(reader)
        contender.name = a.contender
    elif a.contender == "perfect":
        contender = cs.Perfect(reader)
    else:
        work = records.parent / "work" / f"{a.persona}-s{a.seed}-{a.contender}"
        if a.contender.startswith("camr"):
            contender = cs.CAMR(reader, Embedder(), work, words=a.contender == "camr-words")
        elif a.contender == "camr2-words-27b":
            contender = cs.CamrWords(reader, Embedder(), work, name=a.contender)
        else:
            contender = cs.CamrText(reader, Embedder(), work, a.min_similarity, name=a.contender)
    try:
        path = run(life, contender, weeks=a.weeks, limit=a.limit, records=records,
                   quiz_weeks=set(a.quiz_weeks) if a.quiz_weeks else None)
    finally:
        contender.close()
    print(path)
    return 0


if __name__ == "__main__":
    sys.exit(main())

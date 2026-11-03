"""The simulation: a scripted life arriving day by day in its own memory, quizzed at the end of every week.

It is the evaluation (engram.ruler) slowed down to be watched. Each day's moments are remembered and appear in the
brain view. At the end of each week a fixed sample of the life's questions is asked, so the growth curve (facts
known against facts told so far), the wait and the memory in use can be drawn as they happen. The user's own memory
is never touched: the simulation keeps its own, under the app's work folder.
"""

from __future__ import annotations

import random
import shutil
import statistics
import threading
import time
from pathlib import Path


class Simulation:
    def __init__(self, app, persona: str, seed: int, questions: int, root: Path, pace_s: float = 0.12):
        from engram.memory import Memory
        from engram.ruler.life import build

        self.app, self.persona, self.seed, self.pace = app, persona, seed, pace_s
        self.life = build(persona, seed)
        self.sample = sorted(random.Random(f"sim:{persona}:{seed}").sample(range(len(self.life.questions)), questions))
        path = root / f"sim-{persona}-s{seed}"
        shutil.rmtree(path, ignore_errors=True)
        self.memory = Memory(app.reader, app.embedder, path)
        self.day, self.weeks, self.recent, self.error, self.layout = -1, [], [], None, None
        self.stopping, self.done = False, False
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _quiz(self, day) -> dict:
        from engram.models import peak_gb, peak_reset
        from engram.ruler.grade import grade

        verdicts, waits = {}, []
        peak_reset()
        for i in self.sample:
            q = self.life.questions[i]
            right = q.answer_on(day.index)
            reply = self.memory.answer(q.text, day.date)
            v = grade(q, reply.text, day.index)
            event = max(j for j, e in enumerate(self.memory.log.read()) if e["type"] == "answer")
            self.memory.log.write("verdict", event=event, verdict=v, expected=right[0] if right else None)
            verdicts[v] = verdicts.get(v, 0) + 1
            waits.append(reply.ttft_s)
        told = sum(self.life.questions[i].answer_on(day.index) is not None for i in self.sample)
        return {"week": day.index // 7 + 1, "date": day.date.isoformat(), "told": told,
                "knows": verdicts.get("right", 0), "honest": verdicts.get("right_abstain", 0),
                "made_up": verdicts.get("false_memory", 0), "asked": len(self.sample),
                "wait_s": round(statistics.median(waits), 3), "peak_gb": round(peak_gb() or 0, 2),
                "disk_mb": round(self.memory.disk_bytes() / 1e6, 1)}

    def _run(self) -> None:
        try:
            # the whole life's map, laid out once, so each moment appears where it will stay
            from engram.view.layout import tsne

            with self.app.lock:
                texts = [t for d in self.life.days for t in d.dated()]
                xy = tsne(self.app.embedder.encode(texts))
                self.layout = [[round(float(a), 4), round(float(b), 4)] for a, b in xy]
            for day in self.life.days:
                if self.stopping:
                    break
                with self.app.lock:
                    for text in day.dated():
                        m = self.memory.remember(text, day.index)
                        self.recent = (self.recent + [m.mid])[-12:]
                    self.memory.rooms.save()
                    self.day = day.index
                    if day.index in self.life.quiz_days:
                        self.weeks.append(self._quiz(day))
                time.sleep(self.pace)  # let the page draw each day
        except Exception as e:  # shown on the page
            self.error = f"{type(e).__name__}: {e}"
        finally:
            self.done = True

    def state(self) -> dict:
        d = self.life.days[max(self.day, 0)]
        r = self.memory.rooms
        latest = r.moments[self.recent[-1]].text if self.recent else ""
        return {"persona": self.persona, "seed": self.seed, "day": self.day, "days": len(self.life.days),
                "date": d.date.isoformat(), "moments": len(r.moments), "rooms": len(r.rooms), "recent": self.recent,
                "latest": latest, "weeks": self.weeks, "asked": len(self.sample), "done": self.done,
                "error": self.error, "mapped": self.layout is not None,
                "told_by_day": [self.life.told_on(i) for i in range(len(self.life.days))]}

    def stop(self) -> None:
        self.stopping = True

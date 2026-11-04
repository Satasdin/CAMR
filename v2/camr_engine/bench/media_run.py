"""Multimodal memory: files told among the Long Haul's history, then asked about long after.

What is told. The files of Mama Njeri's Kitchen (camr_engine.bench.haul.files): PDF invoices and menus, photographed
receipts and notices, charts and short whiteboard videos, 21 files with facts planted in them. They are told in
order among the Long Haul's own events (seed 1), about 100K tokens of it, the events that plant the Long Haul's own
facts left out. Every file is told in the first 60K tokens, so by the questions it is at least 40K tokens back. Then
37 questions are asked: 29 about planted facts, by the file's kind (pdf, image, chart, video), and 8 never-said
questions where declining is right. They are graded by the Long Haul's rules.

How a file is told. ``camr_engine.media.read`` turns it into words once per vision model (``describe``): a PDF page's
text, an image's caption and what is written in it, a video's frames each described with its time. The words are
kept in ``words-<describer>.json`` (and every model call in ``cache-<describer>.json``), so every contender reading
one describer's words reads exactly the same words, and the vision model runs once.
- **Memory on** (``engine:<model>``): the file goes through ``media.ingest``, as the app's would: it is copied into
  the vault and its moments are remembered, each dated like the Long Haul's moments.
- **Memory off** (``bare:<model>``, ``ollama-bare:<model>``): the file's words are one line of the history. Bare
  reads the newest window that fits, so by the questions the files are long gone.
- **The file in the prompt** (``file:<model>``): the upper bound. No history at all. Each question comes with its
  own file: a PDF's text, an image or a chart itself, a video's frames. A never-said question comes with the file
  nearest to it.

The contenders:
- ``engine:qwen2.5-vl-3b`` (a): the MLX vision model's language half reads the memory's notes, as the engine's
  readers do. ``+look`` adds media.look: when the closest moment came from an image, the vision model answers with
  that image in view and the moments as words.
- ``bare:qwen2.5-vl-3b`` (b): the same model with the newest 32K tokens.
- ``file:qwen2.5-vl-3b`` (c): the same model with the file in the prompt.
- ``engine:qwen3-4b`` and ``bare:qwen3-4b`` (d): a text-only model, reading the words the vision model made.
- ``ollama:qwen2.5vl:3b`` and ``ollama-bare:qwen2.5vl:3b`` (e): Ollama's vision model describing the files itself,
  then paired through the proxy (memory as words), or bare with 32K tokens.

The wording is the Long Haul's (camr_engine.bench.local): the engine reads LONGHAUL_INTRO, bare the yardstick's.

    python -m camr_engine.bench.media_run build --seed 1 --haul ../work/haul/s1 --out ../work/media/s1
    python -m camr_engine.bench.media_run describe --dir ../work/media/s1 --describer mlx:qwen2.5-vl-3b
    python -m camr_engine.bench.media_run run --dir ../work/media/s1 --contender engine:qwen2.5-vl-3b [--limit N]
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import time
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Sequence

from camr_engine import media
from camr_engine.bench.contender import RECORDS, THINKING, Answer, Contender, decode_tps, metrics, run, slug, stamp
from camr_engine.bench.local import (LONGHAUL_INTRO, MEMORIES, MODELS, WINDOWS, Bare, Engine, Loader, hint,
                                     haul_dates, peak_gb, peak_reset)

VISION = {"qwen2.5-vl-3b": "mlx-community/Qwen2.5-VL-3B-Instruct-4bit",
          "gemma-3-4b": "mlx-community/gemma-3-4b-it-4bit"}
VISION_WINDOWS = {"qwen2.5-vl-3b": 32_768, "gemma-3-4b": 32_768}
DESCRIBER = "mlx:qwen2.5-vl-3b"  # whose words a text-only contender reads
NOISE_TOKENS = 100_000  # the Long Haul's own events told, around the files
FIRST_AT, LAST_AT = 4_000, 60_000  # the files go in between these depths of the noise
TASK = "media"
WORK = Path(__file__).resolve().parents[3] / "work"
MEDIA = WORK / "media" / "s1"
FILE_SYSTEM = ("You answer a question about one file shared in a project's history: one developer's log of chats, "
               "decisions, code, notes and lessons. The file is given {how}. Answer from it only. When it does not "
               "say, answer \"I don't know\". Keep each answer short.")
MAX_FRAMES = 6  # frames of a video put in the prompt


# -- what is told -------------------------------------------------------------------------------------------------


class Told(str):
    """A file told in the history. As a string it is the file's words, one line of the history (what a contender
    without memory reads); ``path`` is the file and ``pieces`` its moments' words, for a contender that ingests."""

    path: Path
    pieces: list[str]

    def __new__(cls, path: Path, pieces: list[str]):
        s = super().__new__(cls, "User: " + "\n\n".join(pieces))
        s.path, s.pieces = Path(path), list(pieces)
        return s


def build(seed: int, haul: Path, out: Path, noise_tokens: int = NOISE_TOKENS) -> dict:
    """Make the files and the script: the Long Haul's events up to ``noise_tokens`` (without those that plant its
    probes), with the files placed in order between FIRST_AT and LAST_AT tokens. Writes ``files/``, ``script.jsonl``
    and ``plan.json`` in ``out``; returns the plan."""
    import random

    from camr_engine.bench.haul import files
    from camr_engine.bench.haul.script import calendar, load_events, load_probes

    out = Path(out)
    out.mkdir(parents=True, exist_ok=True)
    made = files.build(seed, out, calendar())
    planted = {i for p in load_probes(Path(haul)) for i in p.get("events", [])}
    noise, total = [], 0
    for e in load_events(Path(haul)):
        if e["i"] in planted:
            continue
        if total + e["tokens"] > noise_tokens:
            break
        total += e["tokens"]
        noise.append({"day": e["day"], "kind": e["kind"], "role": e["role"], "text": e["text"], "tokens": e["tokens"],
                      "depth": total})
    rng = random.Random(f"{seed}:media-order")
    order = [f["name"] for f in made["files"]]
    rng.shuffle(order)
    depths = sorted(rng.uniform(FIRST_AT, LAST_AT) for _ in order)
    script, k = [], 0
    for e in noise:
        while k < len(order) and e["depth"] > depths[k]:
            script.append({"file": order[k], "day": e["day"], "depth": round(depths[k])})
            k += 1
        script.append(e)
    (out / "script.jsonl").write_text("".join(json.dumps(e) + "\n" for e in script))
    plan = {"seed": seed, "haul": str(haul), "noise_tokens": total, "noise_events": len(noise),
            "files": made["files"], "questions": made["questions"],
            "where": {name: next(i for i, e in enumerate(script) if e.get("file") == name) for name in order}}
    (out / "plan.json").write_text(json.dumps(plan, indent=1))
    return plan


def load(folder: Path) -> tuple[dict, list[dict]]:
    folder = Path(folder)
    return (json.loads((folder / "plan.json").read_text()),
            [json.loads(x) for x in (folder / "script.jsonl").read_text().splitlines() if x.strip()])


# -- reading the files once per describer -------------------------------------------------------------------------


class Cached:
    """A describer that remembers: an image and an ask get the words they got before, kept in a JSON file, so every
    contender reads a file with the same words and the vision model runs once. Images are matched by their pixels
    as a model sees them (media.open_image). Without ``describe``, an image not seen before is an error."""

    def __init__(self, path: Path, describe: media.Describe | None = None):
        self.path, self.inner = Path(path), describe
        self.cache: dict[str, str] = json.loads(self.path.read_text()) if self.path.exists() else {}
        self.calls, self.seconds = 0, 0.0

    @staticmethod
    def key(image: Path, ask: str) -> str:
        pixels = media.open_image(image).tobytes()
        return hashlib.sha256(pixels).hexdigest()[:20] + ":" + hashlib.sha256(ask.encode()).hexdigest()[:8]

    def __call__(self, image: Path, ask: str) -> str:
        k = self.key(image, ask)
        if k not in self.cache:
            if self.inner is None:
                raise KeyError(f"{Path(image).name} was never described by this describer (run describe first)")
            t = time.perf_counter()
            self.cache[k] = self.inner(image, ask)
            self.seconds += time.perf_counter() - t
            self.calls += 1
            self.save()
        return self.cache[k]

    def save(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        tmp.write_text(json.dumps(self.cache, indent=0))
        tmp.replace(self.path)


def ollama_describer(model: str, address: str | None = None) -> media.Describe:
    """An Ollama vision model as a describer: greedy, the image as a PNG at media.MAX_SIDE."""
    from camr_engine.bench.ollama_run import KEEP_ALIVE, OLLAMA, OPTIONS, Ollama
    from camr_engine.models import DESCRIBE_TOKENS

    client = Ollama(address or OLLAMA)

    def describe(image: Path, ask: str) -> str:
        buf = io.BytesIO()
        media.open_image(image).save(buf, "PNG")
        body = {"model": model, "keep_alive": KEEP_ALIVE,
                "messages": [{"role": "user", "content": ask, "images": [base64.b64encode(buf.getvalue()).decode()]}],
                "options": {**OPTIONS, "num_ctx": 8192, "num_predict": DESCRIBE_TOKENS}}
        return client.chat(body).text

    return describe


def describer(spec: str, cache: Path) -> Cached:
    """``mlx:<vision model>`` or ``ollama:<model>``, behind its cache."""
    kind, _, model = spec.partition(":")
    if kind == "mlx":
        if model not in VISION:
            raise ValueError(f"the MLX vision models are {', '.join(VISION)}, not {model!r}")
        from camr_engine.models import Seer

        seer: list = []

        def describe(image: Path, ask: str) -> str:  # the model loads at the first image not in the cache
            if not seer:
                seer.append(Seer(VISION[model]))
            return seer[0].describe(image, ask)

        return Cached(cache, describe)
    if kind == "ollama":
        return Cached(cache, ollama_describer(model))
    raise ValueError(f"a describer is mlx:<model> or ollama:<model>, not {spec!r}")


def words_path(folder: Path, spec: str) -> Path:
    return Path(folder) / f"words-{slug(spec)}.json"


def describe_all(folder: Path, spec: str, progress: Callable[[str], None] = print) -> dict:
    """Read every file with ``spec``'s vision model: its moments' words, in ``words-<spec>.json``."""
    plan, _ = load(folder)
    cached = describer(spec, Path(folder) / f"cache-{slug(spec)}.json")
    out = {"describer": spec, "files": {}, "seconds": 0.0, "calls": 0}
    for f in plan["files"]:
        path = Path(folder) / f["path"]
        calls, seconds = cached.calls, cached.seconds
        t = time.perf_counter()
        pieces = media.read(path, describe=cached, folder=Path(folder) / "frames" / slug(spec) / path.stem)
        out["files"][f["name"]] = {"kind": f["kind"], "seconds": round(time.perf_counter() - t, 3),
                                   "model_seconds": round(cached.seconds - seconds, 3),
                                   "calls": cached.calls - calls,
                                   "pieces": [{"text": p.text, "page": p.page, "pages": p.pages, "at_s": p.at_s}
                                              for p in pieces]}
        progress(f"{spec} {f['name']}: {len(pieces)} moments, {out['files'][f['name']]['seconds']} s")
    out["seconds"] = round(sum(x["model_seconds"] for x in out["files"].values()), 3)
    out["calls"] = sum(x["calls"] for x in out["files"].values())
    words_path(folder, spec).write_text(json.dumps(out, indent=1))
    return out


def told_events(folder: Path, words: dict, count: Callable[[str], int]) -> list[dict]:
    """The script as ``run`` tells it: a Long Haul event as itself, a file as a ``Told`` with this describer's
    words. Each event's tokens are counted, so the history's size is the same for every contender of a describer."""
    plan, script = load(folder)
    paths = {f["name"]: Path(folder) / f["path"] for f in plan["files"]}
    out = []
    for e in script:
        if "file" in e:
            told = Told(paths[e["file"]], [p["text"] for p in words["files"][e["file"]]["pieces"]])
            out.append({"day": e["day"], "file": e["file"], "told": told, "tokens": count(str(told))})
        else:
            out.append(e)
    return out


def text_of(event: dict) -> str:
    from camr_engine.bench.longhaul import line

    return event["told"] if "told" in event else line(event)


def checkpoint(plan: dict, events: list[dict]) -> dict:
    """One checkpoint after everything is told, asking every question."""
    qs = [{"id": q["id"], "question": q["ask"], "expected": q["answer"], "family": q["family"], "probe": q,
           "file": q.get("file")} for q in plan["questions"]]
    return {"name": "all", "events": len(events), "tokens": sum(int(e.get("tokens") or 0) for e in events),
            "questions": qs}


# -- the contenders -----------------------------------------------------------------------------------------------


class MediaEngine(Engine):
    """engine:<model>: the engine, with files told through ``media.ingest`` (its describer is ``describe``, the
    cache of a describer's words). ``seer`` turns on media.look: a question whose closest moment came from an image
    is answered by the vision model with that image in view (the name ends ``+look``)."""

    def __init__(self, model: str, *, describe: media.Describe, describer_name: str = DESCRIBER, seer=None,
                 **kw: Any):
        kw.setdefault("intro", LONGHAUL_INTRO)
        super().__init__(model, **kw)
        self.describe_, self.describer_name, self.seer = describe, describer_name, seer
        self.name = f"engine:{model}" + ("+look" if seer is not None else "")
        self.files, self.looked = 0, 0

    def _reset(self) -> None:
        super()._reset()
        self.files = self.looked = 0

    def tell(self, text: str, day: int) -> None:
        if not isinstance(text, Told):
            return super().tell(text, day)
        self.days.moment("", day)  # today is the file's day
        today = self.days.today
        t = time.perf_counter()
        kept = media.ingest(text.path, self.memory, describe=self.describe_, day=day, date=today,
                            stamp=lambda w: stamp(f"User: {w}", today, day))
        self.remember_s += time.perf_counter() - t
        self.moments += len(kept)
        self.files += 1
        self._dirty = True

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        if self.seer is not None:
            got = self._look(question, max_tokens, family)
            if got is not None:
                return got
        a = super().ask(question, max_tokens=max_tokens, family=family)
        a.extra["looked"] = False
        return a

    def _look(self, question: str, max_tokens: int, family: str | None) -> Answer | None:
        if self._dirty:
            self.memory.save()
            self._dirty = False
        peak_reset()
        t = time.perf_counter()
        with self._asking():
            rec = self.memory.choose(question)
            reply = media.look(self.memory, question, self.days.now(), seer=self.seer, chosen=rec,
                               then=hint(family), max_tokens=max_tokens, started=t)
        if reply is None:
            return None
        total = time.perf_counter() - t
        self.looked += 1
        m = metrics(ttft_s=round(reply.ttft_s, 4), total_s=round(total, 4),
                    prefill_tps=None, decode_tps=decode_tps(reply.gen_tokens, total, reply.ttft_s),
                    retrieval_ms=round(reply.choose_s * 1000, 3), bytes_read=0, gbps=None, read_share=0.0,
                    context_tokens=reply.prompt_tokens, history_tokens=self.memory.history_tokens(),
                    peak_ram_gb=peak_gb(), disk_gb=self._disk_gb(), tier="vault")
        return Answer(reply.text, m, {"looked": True, "image": reply.image, "moments_read": len(reply.moments),
                                      "answer_tokens": reply.gen_tokens, "room": rec.room})

    def _disk_gb(self) -> float:
        return round((self.memory.folder_bytes() + media.files_bytes(self.memory)) / 1e9, 6)

    def _answer(self, rec, reply, peak: float | None) -> Answer:
        a = super()._answer(rec, reply, peak)
        a.metrics["disk_gb"] = self._disk_gb()  # the kept files, which the vault's own count leaves out
        return a

    def status(self) -> dict:
        st = super().status()
        if self.memory is not None:
            st.update(files=self.files, files_bytes=media.files_bytes(self.memory), looked=self.looked,
                      disk_gb=self._disk_gb())
        return st

    def describe(self) -> dict:
        d = super().describe()
        d.update(name=self.name, files="media.ingest: copied into the vault's files/, one moment a PDF page, an "
                 "image or a video frame, each dated as the Long Haul's moments", describer=self.describer_name,
                 look=None if self.seer is None else
                 "media.look: when the closest moment came from an image, the vision model answers with the image "
                 "in view and the room's and closest moments as words", seer=getattr(self.seer, "repo", None))
        return d


class FileInPrompt(Contender):
    """file:<model>: no history; each question comes with its own file (the upper bound). ``files`` maps a question
    to its file's path; ``seer`` is the vision model."""

    def __init__(self, model: str, *, seer, files: dict[str, Path]):
        self.model, self.seer, self.files = model, seer, dict(files)
        self.name = f"file:{model}"
        self.history_tokens = 0

    def tell(self, text: str, day: int) -> None:
        pass  # nothing is kept: the file comes with its question

    def prompt(self, path: Path) -> tuple[str, str, list]:
        """(system, the words before the question, images) for one file."""
        kind = media.kind_of(path)
        if kind == "pdf":
            pages = media.pdf_pages(path)
            text = "\n\n".join(f"Page {i} of {len(pages)}:\n{p}" for i, p in enumerate(pages, start=1))
            return (FILE_SYSTEM.format(how="as its text") + f"\n\nThe file {path.name}:\n{text}\nEnd of the file.",
                    "", [])
        if kind == "video":
            shots = media.frames(path)[:MAX_FRAMES]
            when = ", ".join(media.clock(t) for t, _ in shots)
            return (FILE_SYSTEM.format(how="as frames of the video, in order"),
                    f"The video {path.name}: its frames at {when}.\n\n", [im for _, im in shots])
        return FILE_SYSTEM.format(how="as the image itself"), f"The image {path.name}.\n\n", [path]

    def ask(self, question: str, *, max_tokens: int, family: str | None = None) -> Answer:
        path = self.files[question]
        system, lead, images = self.prompt(path)
        then = hint(family)
        peak_reset()
        t = time.perf_counter()
        reply = self.seer.see(images, system, lead + question + (f"\n\n{then}" if then else ""),
                              max_tokens=max_tokens)
        total = time.perf_counter() - t
        m = metrics(ttft_s=round(reply.ttft_s, 4), total_s=round(total, 4), prefill_tps=None,
                    decode_tps=decode_tps(reply.gen_tokens, total, reply.ttft_s), retrieval_ms=None, bytes_read=0,
                    gbps=None, read_share=None, context_tokens=reply.prompt_tokens, history_tokens=None,
                    peak_ram_gb=peak_gb(), disk_gb=0.0, tier=None)
        return Answer(reply.text, m, {"file": path.name, "images": len(images), "answer_tokens": reply.gen_tokens})

    def describe(self) -> dict:
        return {"name": self.name, "kind": "file", "model": self.model, "repo": getattr(self.seer, "repo", None),
                "system": FILE_SYSTEM, "max_frames": MAX_FRAMES, "enable_thinking": THINKING,
                "prompt": "system: the instructions (and a PDF's text, page by page); user: an image, or a video's "
                          "frames, then the question and the family's line",
                "never_said": "a never-said question comes with the file nearest to it"}


def _no_think_key(contender, body: dict) -> dict:
    """Ollama refuses ``think`` for a model with no thinking at all; such a model never thinks, so it is left out."""
    if "thinking" not in (contender.show().get("capabilities") or []):
        body.pop("think", None)
    return body


def ollama_contender(spec: str, **kw: Any) -> Contender:
    """ollama:<model> (paired, its files' moments told as notes one by one) or ollama-bare:<model>."""
    from camr_engine.bench.ollama_run import OllamaBare, OllamaPaired, longhaul_frame

    kind, _, model = spec.partition(":")

    class Paired(OllamaPaired):
        def tell(self, text: str, day: int) -> None:
            if isinstance(text, Told):
                for w in text.pieces:
                    super().tell(f"User: {w}", day)
                return
            super().tell(text, day)

        def body(self, messages, max_tokens, num_ctx):
            return _no_think_key(self, super().body(messages, max_tokens, num_ctx))

    class Plain(OllamaBare):
        def body(self, messages, max_tokens, num_ctx):
            return _no_think_key(self, super().body(messages, max_tokens, num_ctx))

    if kind == "ollama":
        return Paired(model, frame=longhaul_frame(paired=True), **kw)
    if kind == "ollama-bare":
        return Plain(model, frame=longhaul_frame(), **kw)
    raise ValueError(f"not an Ollama contender: {spec!r}")


def words_for(spec: str, override: str | None = None) -> str:
    """The describer whose words a contender reads: Ollama's own model for Ollama, the vision model itself for a
    vision model, else DESCRIBER."""
    if override:
        return override
    kind, _, model = spec.partition(":")
    if kind.startswith("ollama"):
        return f"ollama:{model}"
    base = model.split("+")[0]
    return f"mlx:{base}" if base in VISION else DESCRIBER


def make(spec: str, folder: Path, plan: dict, *, loader: Loader, seers: dict, words: str) -> Contender:
    """A contender by name (see the module's docstring)."""
    kind, _, model = spec.partition(":")
    if kind.startswith("ollama"):
        return ollama_contender(spec)
    look = model.endswith("+look")
    model = model.removesuffix("+look")
    repo = VISION.get(model) or MODELS.get(model)
    if repo is None:
        raise ValueError(f"no model {model!r}: the vision models are {', '.join(VISION)}, the text ones "
                         f"{', '.join(MODELS)}")

    def seer():
        if model not in VISION:
            raise ValueError(f"{model} cannot see images")
        if model not in seers:
            from camr_engine.models import Seer

            seers[model] = Seer(VISION[model])
        return seers[model]

    if kind == "file":
        paths = {f["name"]: Path(folder) / f["path"] for f in plan["files"]}
        return FileInPrompt(model, seer=seer(), files={q["ask"]: paths[q["file"]] for q in plan["questions"]})
    reader = loader.reader(repo)
    if kind == "engine":
        return MediaEngine(model, reader=reader, embedder=loader.embedder(), describer_name=words,
                           describe=Cached(Path(folder) / f"cache-{slug(words)}.json"),
                           seer=seer() if look else None)
    if kind == "bare":
        return Bare(model, reader=reader, window=VISION_WINDOWS.get(model) or WINDOWS[model])
    raise ValueError(f"a contender is engine:, bare:, file:, ollama: or ollama-bare:<model>, not {spec!r}")


def media_meta(folder: Path, plan: dict, words: dict | None, events: list[dict]) -> dict:
    return {"media": {"dir": str(folder), "seed": plan["seed"], "haul": plan["haul"],
                      "files": dict(Counter(f["kind"] for f in plan["files"])),
                      "questions": dict(Counter(q["family"] for q in plan["questions"])),
                      "noise_tokens": plan["noise_tokens"],
                      "file_tokens": sum(e["tokens"] for e in events if "file" in e),
                      "history_tokens": sum(int(e.get("tokens") or 0) for e in events),
                      "first_file_at": FIRST_AT, "last_file_at": LAST_AT},
            "words": None if words is None else {"describer": words["describer"], "describe_s": words["seconds"],
                                                 "model_calls": words["calls"],
                                                 "moments": sum(len(f["pieces"]) for f in words["files"].values())}}


def run_one(spec: str, folder: Path, *, loader: Loader | None = None, seers: dict | None = None,
            words: str | None = None, limit: int | None = None, memories: Path = MEMORIES, records: Path = RECORDS,
            progress: Callable[[str], None] = print, count: Callable[[str], int] | None = None) -> dict:
    """One contender through the media run; returns its record."""
    from camr_engine.bench.local import memory_folder
    from camr_engine.bench.longhaul import grader

    if count is None:
        from camr_engine.bench.haul.tokens import counter

        count = counter()
    plan, _ = load(folder)
    used = words_for(spec, words)
    got = json.loads(words_path(folder, used).read_text())
    events = told_events(folder, got, count)
    c = make(spec, folder, plan, loader=loader or Loader(), seers={} if seers is None else seers, words=used)
    if used != words_for(spec) and not spec.startswith("file:"):
        c.name += f"@{used}"  # another describer's words than its own: the name says whose
    return run(c, events, [checkpoint(plan, events)], task=TASK, grader=grader, folder=memory_folder(TASK, c.name,
               memories), text=text_of, limit=limit, records=records, progress=progress,
               meta=media_meta(folder, plan, got, events), raise_failure=False)


def main(argv: Sequence[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m camr_engine.bench.media_run")
    sub = ap.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build", help="make the files and the script")
    b.add_argument("--seed", type=int, default=1)
    b.add_argument("--haul", type=Path, default=WORK / "haul" / "s1")
    b.add_argument("--out", type=Path, default=MEDIA)
    d = sub.add_parser("describe", help="read every file with a vision model, once")
    d.add_argument("--dir", type=Path, default=MEDIA)
    d.add_argument("--describer", action="append", required=True, help="mlx:<model> or ollama:<model>")
    r = sub.add_parser("run", help="contenders through the media run")
    r.add_argument("--dir", type=Path, default=MEDIA)
    r.add_argument("--contender", action="append", required=True)
    r.add_argument("--words", help="the describer whose words are told (default: see words_for)")
    r.add_argument("--limit", type=int)
    r.add_argument("--memories", type=Path, default=MEMORIES)
    r.add_argument("--records", type=Path, default=RECORDS)
    a = ap.parse_args(argv)
    if a.cmd == "build":
        plan = build(a.seed, a.haul, a.out)
        print(f"{len(plan['files'])} files, {len(plan['questions'])} questions, {plan['noise_tokens']:,} tokens of "
              f"noise -> {a.out}")
        return 0
    if a.cmd == "describe":
        for spec in a.describer:
            got = describe_all(a.dir, spec)
            print(f"{spec}: {got['calls']} model calls, {got['seconds']} s")
        return 0
    loader, seers = Loader(), {}
    failed = 0
    for spec in a.contender:
        try:
            rec = run_one(spec, a.dir, loader=loader, seers=seers, words=a.words, limit=a.limit,
                          memories=a.memories, records=a.records)
        except Exception as e:  # noqa: BLE001: a contender that cannot start is reported, and the next one runs
            print(f"{spec} did not start: {type(e).__name__}: {e}")
            failed += 1
            continue
        print(rec.get("path"))
    return 1 if failed else 0


if __name__ == "__main__":
    from camr_engine.app.measuring import measuring

    with measuring("media_run"):  # the app pauses its views and loads nothing while this measures
        raise SystemExit(main())

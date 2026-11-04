"""Files into memory: a PDF, an image or a short video becomes moments the memory remembers, each saying which file
and which page or frame it came from.

- **PDF:** the text of each page, one moment a page (pypdf). A page with no text in it (a scan) is read from the
  images on it, as an image is.
- **Image** (png, jpg, webp; heic when pillow-heif is installed): what is written in it and a caption, both made by
  a vision model through ``describe``.
- **Video** (mp4, mov, m4v, webm, avi): a frame every ``EVERY_S`` seconds (imageio-ffmpeg), each described as an
  image, with its time. A frame that looks like the one before it (a still camera on a whiteboard) is read once.

``describe(image, ask)`` is any vision model: it gets an image file and one of the two asks below (``READ_TEXT``,
``CAPTION``) and returns words. ``camr_engine.models.Seer.describe`` is the MLX one; the media benchmark also uses
Ollama's. Without ``describe``, only a PDF's text can be read.

The original file is copied into the memory's vault, under ``files/`` (Obsidian shows it beside the notes), with
the frames a video was read from. ``files/sources.jsonl`` says, for every moment, which file, page or frame it came
from and where the copy is; the moment's own words start with the same, so the reader and a person both see it.

Looking again (``look``): when the moment closest to a question came from an image or a video frame, a vision
reader can answer with that image in view, beside the moments as words. The saved notes cannot be used for this.
A vision model's image tokens sit at positions in three dimensions (Qwen2.5-VL's M-RoPE), while notes are written
for words alone. So a look reads the room's moments as words (DECISIONS.md, E-44).

The app calls one function:

    ingest(path, memory, *, describe=None, day, date=None, stamp=None, tags=()) -> list[str]
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import re
import shutil
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterable

PDF, IMAGE, VIDEO = "pdf", "image", "video"
SUFFIXES = {".pdf": PDF, ".png": IMAGE, ".jpg": IMAGE, ".jpeg": IMAGE, ".webp": IMAGE, ".heic": IMAGE,
            ".heif": IMAGE, ".mp4": VIDEO, ".mov": VIDEO, ".m4v": VIDEO, ".webm": VIDEO, ".avi": VIDEO}
EVERY_S = 2.0  # a video frame read every this many seconds
SAME = 0.005  # a frame is the one before it again when under this share of its pixels changed (at 64 x 36)
CHANGED = 40  # how many grey levels (of 255) a pixel must change by to count as changed
MAX_FRAMES = 30  # at most this many frames read from one video (a minute at EVERY_S)
MAX_SIDE = 1280  # an image is shrunk to this many pixels on its longer side before a model sees it
READ_TEXT = ("Copy out every word and number written in this image, exactly as written, line by line. Write "
             "nothing else. If nothing is written in it, write: no text.")
CAPTION = ("In one or two sentences, say what this image is and what it shows. If it is a chart, give its title "
           "and the value of every bar, point or slice.")
NO_TEXT = re.compile(r"^\W*no text\W*$", re.I)
FILES = "files"
SOURCES = "sources.jsonl"

Describe = Callable[[Path, str], str]


@dataclass
class Piece:
    """One moment's worth of a file: its words (starting with where they came from) and where in the file."""

    text: str
    kind: str
    page: int | None = None  # a PDF page, from 1
    pages: int | None = None
    at_s: float | None = None  # a video frame's time
    image: Path | None = None  # the image a vision reader can look at again: the file itself, or the frame


def kind_of(path: Path | str) -> str:
    """pdf, image or video, by the file's ending."""
    kind = SUFFIXES.get(Path(path).suffix.lower())
    if kind is None:
        raise ValueError(f"{Path(path).name}: not a file the memory reads (a PDF, an image or a video)")
    return kind


def clock(seconds: float) -> str:
    """A video time as people write it: 0:06, 1:02:05."""
    s = int(round(seconds))
    h, m, s = s // 3600, s % 3600 // 60, s % 60
    return f"{h}:{m:02d}:{s:02d}" if h else f"{m}:{s:02d}"


def _clean(text: str) -> str:
    lines = [" ".join(x.split()) for x in (text or "").splitlines()]
    return "\n".join(x for x in lines if x).strip()


def open_image(path: Path | str):
    """An image as a model should see it: turned upright by its EXIF, in RGB, at most ``MAX_SIDE`` pixels a side."""
    from PIL import Image, ImageOps

    if Path(path).suffix.lower() in (".heic", ".heif"):
        try:
            from pillow_heif import register_heif_opener
        except ImportError as e:
            raise ValueError(f"{Path(path).name}: HEIC needs pillow-heif (uv pip install pillow-heif)") from e
        register_heif_opener()
    with Image.open(path) as im:
        im = ImageOps.exif_transpose(im).convert("RGB")
    if max(im.size) > MAX_SIDE:
        im.thumbnail((MAX_SIDE, MAX_SIDE))
    return im


def image_words(name: str, image: Path, describe: Describe, where: str = "an image") -> str:
    """An image's moment: what it is, then what is written in it."""
    caption = _clean(describe(image, CAPTION))
    written = _clean(describe(image, READ_TEXT))
    text = f"File {name}, {where}. {caption}"
    if written and not NO_TEXT.match(written):
        text += f"\nWritten in it:\n{written}"
    return text


def _page_text(page) -> str:
    """A page's text with each row of a table kept on one line (pypdf's layout mode), else as pypdf reads it."""
    try:
        return page.extract_text(extraction_mode="layout") or ""
    except Exception:  # noqa: BLE001: an odd page is read the plain way
        return page.extract_text() or ""


def pdf_pages(path: Path | str) -> list[str]:
    """The text of each page of a PDF."""
    from pypdf import PdfReader

    return [_clean(_page_text(p)) for p in PdfReader(str(path)).pages]


def _pdf(path: Path, describe: Describe | None, scratch: Path) -> list[Piece]:
    from pypdf import PdfReader

    pages = PdfReader(str(path)).pages
    out = []
    for i, page in enumerate(pages, start=1):
        head = f"File {path.name}, a PDF, page {i} of {len(pages)}"
        text = _clean(_page_text(page))
        if text:
            out.append(Piece(f"{head}:\n{text}", PDF, i, len(pages)))
            continue
        if describe is None:  # a scan, and nothing to read its images with
            continue
        scratch.mkdir(parents=True, exist_ok=True)
        for j, img in enumerate(page.images):
            f = scratch / f"{path.stem}-p{i}-{j}{Path(img.name).suffix or '.png'}"
            f.write_bytes(img.data)
            out.append(Piece(image_words(path.name, f, describe, f"a PDF, page {i} of {len(pages)}, a scan"), PDF,
                             i, len(pages), image=f))
    return out


def frames(path: Path | str, every_s: float = EVERY_S, same: float = SAME, most: int = MAX_FRAMES
           ) -> list[tuple[float, object]]:
    """(time, image) for a frame every ``every_s`` seconds, leaving out a frame that looks like the one kept before
    it. Looking alike is measured on 64 x 36 grey thumbnails, by the share of pixels that changed a lot, so a
    shaking camera and grain count as the same picture and a new line written on a board does not."""
    import imageio.v3 as iio
    import numpy as np
    from PIL import Image

    fps = float(iio.immeta(path, plugin="FFMPEG").get("fps") or 25.0)
    step = max(1, int(round(fps * every_s)))
    out, last = [], None
    for i, arr in enumerate(iio.imiter(path, plugin="FFMPEG")):
        if i % step:
            continue
        im = Image.fromarray(np.asarray(arr)).convert("RGB")
        grey = np.asarray(im.convert("L").resize((64, 36)), dtype=np.float32)
        if last is not None and float((np.abs(grey - last) > CHANGED).mean()) < same:
            continue
        last = grey
        if max(im.size) > MAX_SIDE:
            im.thumbnail((MAX_SIDE, MAX_SIDE))
        out.append((i / fps, im))
        if len(out) >= most:
            break
    return out


def _video(path: Path, describe: Describe | None, folder: Path) -> list[Piece]:
    if describe is None:
        raise ValueError(f"{path.name}: a video is read by a vision model; pass describe")
    folder.mkdir(parents=True, exist_ok=True)
    out = []
    for at, im in frames(path):
        f = folder / f"frame-{at:07.2f}s.png"
        im.save(f)
        out.append(Piece(image_words(path.name, f, describe, f"a video, the frame at {clock(at)}"), VIDEO,
                         at_s=round(at, 2), image=f))
    return out


def read(path: Path | str, *, describe: Describe | None = None, folder: Path | None = None) -> list[Piece]:
    """A file's moments, in order, without remembering them. A video's frames (and a scanned page's images) are
    saved in ``folder`` (a temporary folder when it is None)."""
    path = Path(path)
    kind = kind_of(path)
    scratch = Path(folder) if folder is not None else Path(tempfile.mkdtemp(prefix="camr-media-"))
    if kind == PDF:
        return _pdf(path, describe, scratch)
    if kind == VIDEO:
        return _video(path, describe, scratch)
    if describe is None:
        raise ValueError(f"{path.name}: an image is read by a vision model; pass describe")
    return [Piece(image_words(path.name, path, describe), IMAGE, image=path)]


def files_folder(memory) -> Path:
    """Where a memory keeps its files: ``files/`` in its vault, or in its own folder when it has no vault."""
    vault = getattr(memory, "vault", None)
    return (vault.path if vault is not None else Path(memory.path)) / FILES


def _digest(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()[:12]


def _safe(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "-", name).strip("-") or "file"


def ingest(path: Path | str, memory, *, describe: Describe | None = None, day: int, date: dt.date | None = None,
           stamp: Callable[[str], str] | None = None, tags: Iterable[str] = ()) -> list[str]:
    """Remember a PDF, an image or a video as moments, and keep the file. Returns each moment's words, as kept.

    ``describe`` reads images (see the module's docstring); ``day`` and ``date`` are the moments' own, as
    ``Memory.remember`` takes them; ``stamp`` turns a moment's words into what is kept (the Long Haul dates every
    moment, ``[YYYY-MM-DD, day N] ...``); ``tags`` go on every moment's vault note, with "file" and its kind.

    The file is copied into the memory's ``files/`` folder (named by its hash, so the same file is kept once), and
    every moment is written to ``files/sources.jsonl`` with the file, its page or frame and the copy."""
    path = Path(path)
    kind = kind_of(path)
    folder = files_folder(memory)
    folder.mkdir(parents=True, exist_ok=True)
    digest = _digest(path)
    copy = folder / f"{digest}-{_safe(path.name)}"
    if not copy.exists():
        shutil.copy2(path, copy)
    t = time.perf_counter()
    pieces = read(path, describe=describe, folder=folder / f"{digest}-frames")
    read_s = time.perf_counter() - t
    out = []
    with open(folder / SOURCES, "a", encoding="utf-8") as log:
        for p in pieces:
            text = stamp(p.text) if stamp is not None else p.text
            m = memory.remember(text, day, date=date, tags=[*tags, "file", p.kind])
            image = p.image if p.image is None or p.image != path else copy
            log.write(json.dumps({"moment": m.mid, "file": path.name, "kind": kind, "copy": copy.name,
                                  "sha": digest, "page": p.page, "pages": p.pages, "at_s": p.at_s,
                                  "image": str(Path(image).relative_to(folder)) if image is not None else None,
                                  "day": day, "date": date.isoformat() if date else None,
                                  "read_s": round(read_s / max(len(pieces), 1), 3)}) + "\n")
            out.append(text)
    return out


def sources(memory) -> dict[int, dict]:
    """Every moment a file gave, by moment id: the file, its page or frame, and the paths of its copy and image."""
    folder = files_folder(memory)
    log = folder / SOURCES
    out: dict[int, dict] = {}
    if not log.exists():
        return out
    for line in log.read_text(encoding="utf-8").splitlines():
        try:
            s = json.loads(line)
        except ValueError:
            continue
        s["copy_path"] = str(folder / s["copy"])
        s["image_path"] = str(folder / s["image"]) if s.get("image") else None
        out[int(s["moment"])] = s
    return out


def files_bytes(memory) -> int:
    """What the kept files take on disk (the copies, a video's frames and the sources log)."""
    folder = files_folder(memory)
    return sum(p.stat().st_size for p in folder.rglob("*") if p.is_file()) if folder.exists() else 0


def look(memory, question: str, today: dt.date, *, seer, chosen=None, then: str = "", max_tokens: int | None = None,
         started: float | None = None):
    """Answer with an image in view, when the moment closest to the question came from one; None otherwise.

    ``seer`` is a vision reader (``camr_engine.models.Seer``). The desk is words: the instructions as the memory
    words them, the chosen room's moments and the closest moments as words, today's date and ``then``; the question
    comes with the image. ``chosen`` is a room already chosen; ``started`` is when the question was asked, so the
    reply's ``ttft_s`` counts the choosing. The reply carries ``image`` (the file looked at) and ``moments``."""
    import numpy as np

    from camr_engine.memory import INTRO, today_text

    t = time.perf_counter() if started is None else started
    rooms = memory.rooms
    if not rooms.moments:
        return None
    rec = memory.choose(question) if chosen is None else chosen
    top = int(np.argmax(rooms.vectors @ memory.embedder.encode_one(question, is_query=True)))
    src = sources(memory).get(top)
    if not src or not src.get("image_path"):
        return None
    picked = list(rooms.rooms[rec.room].members) if rec.room is not None else []
    picked += [m for m in rec.closest if m not in picked]
    notes = "".join(rooms.moments[m].text + "\n" for m in picked)
    system = (f"{getattr(memory, 'intro', INTRO)}\n\nNotes:\n{notes}End of notes.\nToday is {today_text(today)}."
              + (f"\n\n{then}" if then else ""))
    user = f"The image is from {src['file']}" + (f", the frame at {clock(src['at_s'])}" if src.get("at_s") is not None
                                                 else "") + f".\n\n{question}"
    before = time.perf_counter() - t
    reply = seer.see([src["image_path"]], system, user, max_tokens=max_tokens)
    reply.ttft_s += before
    reply.image, reply.moments, reply.choose_s = src["file"], picked, before
    return reply


__all__ = ["CAPTION", "EVERY_S", "IMAGE", "PDF", "READ_TEXT", "VIDEO", "Piece", "files_bytes", "files_folder",
           "frames", "ingest", "kind_of", "look", "open_image", "pdf_pages", "read", "sources"]

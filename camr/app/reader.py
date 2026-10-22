"""Reading what the user uploads, so CAMR Personal can learn it and show where each fact came from.

* text, Markdown, CSV: as they are;
* Word (.docx): paragraphs and table cells, with the standard library (a .docx is a zip of XML);
* PDF: each page's own text (pypdf, when installed), and on a Mac every page is also read by Apple's on-device text
  recognition (``see.swift``), so a scanned page has text and every page has the position of each line;
* images (photos of pages, receipts, screenshots): Apple's on-device text recognition on a Mac; what an image *shows*
  is described by a vision model, if one is installed (``Assistant.describe_image``).

Nothing leaves the machine. The original and a preview of each page are kept in ``<home>/files/<file id>/``, with
``reading.json`` (the lines and their boxes) for highlighting later.
"""

from __future__ import annotations

import hashlib
import io
import json
import re
import shutil
import subprocess
import sys
import xml.etree.ElementTree as ET
import zipfile
from dataclasses import asdict, dataclass, field
from pathlib import Path

SEE_SOURCE = Path(__file__).resolve().parent / "see.swift"
IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".heic", ".heif", ".webp", ".gif", ".tif", ".tiff", ".bmp"}
TEXT_TYPES = {".txt", ".md", ".markdown", ".csv", ".log"}
SUPPORTED = IMAGE_TYPES | TEXT_TYPES | {".pdf", ".docx"}
BROWSER_IMAGES = {".png", ".jpg", ".jpeg", ".webp", ".gif"}  # shown as they are when there is no preview
MAX_PAGES = 40  # pages read with positions; a longer PDF's later pages are learned from their own text only


@dataclass
class Page:
    index: int
    image: str | None = None  # preview file in the file's folder
    width: int = 0
    height: int = 0
    lines: list[dict] = field(default_factory=list)  # {"text", "conf", "box": [x, y, w, h] fractions, top left}
    text_layer: str = ""


@dataclass
class Reading:
    file_id: str
    name: str
    kind: str              # "text" | "docx" | "pdf" | "image"
    text: str              # what is learned
    pages: list[Page] = field(default_factory=list)
    page_count: int = 0
    positions: bool = False  # whether lines have positions (text recognition ran)
    problem: str = ""        # what could not be read, for the user

    def save(self, folder: Path) -> None:
        (folder / "reading.json").write_text(json.dumps(asdict(self)))

    @classmethod
    def load(cls, folder: Path) -> "Reading":
        d = json.loads((folder / "reading.json").read_text())
        d["pages"] = [Page(**p) for p in d["pages"]]
        return cls(**d)

    def lines(self):
        for p in self.pages:
            for ln in p.lines:
                yield p.index, ln


def file_id(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()[:16]


# ---------------------------------------------------------------------- Apple's text recognition
def see_binary(home: Path) -> Path | None:
    """The compiled reader (built once from see.swift with swiftc; None where that is not possible)."""
    if sys.platform != "darwin" or not shutil.which("swiftc"):
        return None
    digest = hashlib.sha256(SEE_SOURCE.read_bytes()).hexdigest()[:12]
    exe = home / "bin" / f"camr-see-{digest}"
    if not exe.exists():
        exe.parent.mkdir(parents=True, exist_ok=True)
        try:
            subprocess.run(["swiftc", "-O", str(SEE_SOURCE), "-o", str(exe)], capture_output=True, timeout=600)
        except (OSError, subprocess.TimeoutExpired):
            return None
    return exe if exe.exists() else None


def see(exe: Path, path: Path, folder: Path, max_pages: int = MAX_PAGES) -> tuple[list[Page], int]:
    done = subprocess.run([str(exe), str(path), str(folder), str(max_pages)], capture_output=True, timeout=900)
    if done.returncode != 0:
        raise RuntimeError(done.stderr.decode(errors="replace").strip() or "the file could not be read")
    d = json.loads(done.stdout)
    return [Page(**p) for p in d["pages"]], int(d.get("page_count", len(d["pages"])))


def rows(lines: list[dict]) -> list[list[dict]]:
    """Recognised lines put back into rows. Text recognition returns a receipt's item and its price, or a form's label
    and its value, as separate lines (all the items, then all the prices), which loses which goes with which; lines
    at the same height are joined left to right. A page in columns (several rows of long lines side by side) keeps
    the recognition's own order, which reads each column in turn."""
    if not lines:
        return []
    heights = sorted(ln["box"][3] for ln in lines)
    h = heights[len(heights) // 2] or 0.01
    grouped: list[dict] = []
    for ln in sorted(lines, key=lambda ln: ln["box"][1] + ln["box"][3] / 2):
        cy = ln["box"][1] + ln["box"][3] / 2
        if grouped and abs(cy - grouped[-1]["cy"]) <= 0.5 * h:
            grouped[-1]["items"].append(ln)
        else:
            grouped.append({"cy": cy, "items": [ln]})
    out = [sorted(g["items"], key=lambda ln: ln["box"][0]) for g in grouped]
    if sum(1 for r in out if len(r) > 1 and all(len(ln["text"]) >= 25 for ln in r)) >= 3:
        return [[ln] for ln in lines]  # columns of running text
    return out


def row_text(lines: list[dict]) -> str:
    return "\n".join("  ".join(ln["text"] for ln in row) for row in rows(lines))


def page_text(p: Page) -> str:
    """A page's text: its own text layer when it has one, else what was recognised, row by row."""
    own = re.sub(r"[ \t]+", " ", p.text_layer or "").strip()
    return own if len(own) >= 40 else row_text(p.lines)


# ---------------------------------------------------------------------- Word
_W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


MAX_DOCX_XML = 50_000_000  # bytes of document.xml once unzipped: a larger one is refused (a zip bomb)


def docx_text(data: bytes) -> str:
    """The text of a Word file. An upload is untrusted: a document declaring a DTD is refused (Word never writes one,
    and a DTD is how entity-expansion and external-entity attacks reach an XML parser), and so is one that unzips
    past MAX_DOCX_XML."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        info = z.getinfo("word/document.xml")
        if info.file_size > MAX_DOCX_XML:
            raise ValueError("this Word file is too large to read")
        xml = z.read(info)
    if b"<!DOCTYPE" in xml[:4096].upper() or b"<!ENTITY" in xml.upper():
        raise ValueError("this Word file declares a DTD, which Word files never do: not read")
    root = ET.fromstring(xml)
    paras = ["".join(t.text or "" for t in p.iter(f"{_W}t")) for p in root.iter(f"{_W}p")]
    return "\n".join(p for p in paras if p.strip())


def pdf_text_pages(data: bytes) -> list[str] | None:
    try:
        from pypdf import PdfReader  # type: ignore
    except ImportError:
        return None
    return [page.extract_text() or "" for page in PdfReader(io.BytesIO(data)).pages]


# ---------------------------------------------------------------------- reading
def read(name: str, data: bytes, folder: Path, exe: Path | None) -> Reading:
    """Read an upload into text (and pages with line positions where possible). Keeps the original in ``folder``."""
    ext = Path(name).suffix.lower()
    if ext not in SUPPORTED:
        raise ValueError(f"{ext or 'this kind of file'} cannot be read yet: try a photo, a PDF, a Word file or text")
    folder.mkdir(parents=True, exist_ok=True)
    original = folder / f"original{ext}"
    original.write_bytes(data)
    fid = folder.name
    if ext in TEXT_TYPES:
        return Reading(fid, name, "text", data.decode("utf-8", errors="replace"))
    if ext == ".docx":
        return Reading(fid, name, "docx", docx_text(data))
    if ext == ".pdf":
        own = pdf_text_pages(data)
        pages, total, problem = [], len(own or []), ""
        if exe is not None:
            try:
                pages, total = see(exe, original, folder)
            except (RuntimeError, OSError, subprocess.TimeoutExpired, ValueError) as exc:
                problem = f"text recognition failed: {exc}"
        if not pages and own is None:
            raise RuntimeError("reading PDFs needs a Mac (on-device text recognition) or `pip install pypdf`")
        texts = [page_text(p) if p.lines or p.text_layer else (own[p.index] if own and p.index < len(own) else "")
                 for p in pages]
        if own:  # pages past the ones read with positions: their own text
            texts += own[len(pages):]
        if len(pages) < total and not own:
            problem = problem or f"only the first {len(pages)} of {total} pages were read"
        return Reading(fid, name, "pdf", "\n\n".join(t for t in texts if t.strip()), pages, total,
                       positions=bool(pages), problem=problem)
    # an image
    if exe is None:
        page = Page(0, original.name if ext in BROWSER_IMAGES else None)
        return Reading(fid, name, "image", "", [page], 1, problem="text in images can only be read on a Mac")
    pages, _ = see(exe, original, folder)
    return Reading(fid, name, "image", row_text(pages[0].lines), pages, 1, positions=True)


# ---------------------------------------------------------------------- highlighting
def _norm(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", text.lower()).strip()


def lines_in(reading: Reading, text: str) -> list[dict]:
    """The recognised lines a note's text came from: each line (of four or more letters) found in the note."""
    hay = f" {_norm(text)} "
    out = []
    for page, ln in reading.lines():
        n = _norm(ln["text"])
        if len(n.replace(" ", "")) >= 4 and f" {n} " in hay:
            out.append({"page": page, "box": ln["box"], "text": ln["text"]})
    return out


def lines_within(reading: Reading, page: int, box: list[float]) -> list[dict]:
    """The lines whose centre lies inside a selected box on a page (fractions, top left), in reading order."""
    x, y, w, h = box
    out = []
    for p, ln in reading.lines():
        bx, by, bw, bh = ln["box"]
        cx, cy = bx + bw / 2, by + bh / 2
        if p == page and x <= cx <= x + w and y <= cy <= y + h:
            out.append({"page": p, "box": ln["box"], "text": ln["text"]})
    return [ln for row in rows(out) for ln in row]


# ---------------------------------------------------------------------- what to ask about
_DATE = re.compile(r"\b(?:\d{1,2}[/.-]\d{1,2}[/.-]\d{2,4}|\d{4}-\d{2}-\d{2}|\d{1,2}(?:st|nd|rd|th)? (?:jan|feb|mar|apr|"
                   r"may|jun|jul|aug|sep|oct|nov|dec)[a-z]*|(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]* "
                   r"\d{1,2}|(?:mon|tues|wednes|thurs|fri|satur|sun)day|deadline|due)\b", re.I)
_MONEY = re.compile(r"(?:\b(?:ksh|kes|usd|eur|gbp|total|subtotal|amount|balance|price|paid|vat)\b|[$€£]\s?\d|\b\d{1,3}"
                    r"(?:,\d{3})+(?:\.\d{2})?\b|\b\d+\.\d{2}\b)", re.I)
_NAME = re.compile(r"\b[A-Z][a-z]{2,}\s+[A-Z][a-z]{2,}\b")


def focus_chips(text: str) -> list[str]:
    """What the user may want memory to focus on, from what the file contains."""
    chips = []
    if _DATE.search(text):
        chips.append("Dates & deadlines")
    if _MONEY.search(text):
        chips.append("Numbers & totals")
    # names: capitalised pairs on lines without numbers (a receipt's "Fresh Milk 240.00" is a product, not a person)
    names = {m for line in text.splitlines() if not re.search(r"\d", line) for m in _NAME.findall(line)}
    if len(names) >= 2:
        chips.append("People")
    return chips + ["Key points"]

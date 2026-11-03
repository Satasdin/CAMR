"""Turn a chapter's Markdown draft into a Word document in the thesis template's styles.

It drives CAMR v1's chapter builder (camr-repo/scripts/build_chapter5.py, read only) with CAMR v1's finished
Chapter 5 as the template, so headings, numbering, captions, tables and page setup match the chapters already
written. Heading numbers come from the template, so the ones typed in the Markdown are dropped. Tables and figures
are renumbered in order. A figure whose image does not exist yet is left as a highlighted placeholder.

    ~/Desktop/camr-repo/.venv/bin/python docs/thesis/build_docx.py docs/thesis/chapter4.md --chapter 4 \\
        --out docs/thesis/Chapter4_CAMR.docx
"""

from __future__ import annotations

import argparse
import importlib.util
import re
from pathlib import Path

V1 = Path.home() / "Desktop" / "camr-repo"
TEMPLATE = V1 / "docs" / "report" / "Chapter5_CAMR.docx"
_spec = importlib.util.spec_from_file_location("build_chapter5", V1 / "scripts" / "build_chapter5.py")
v1 = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(v1)

NUM = re.compile(r"^\s*(?:Chapter\s+\d+\s*[:.]\s*)?(?:\d+(?:\.\d+)*\.?\s+)?")
CAPTION = re.compile(r"^\s*\**\*?((Table|Figure)\s+[\w.\-]+)\s*[:.]\s*(.+?)\**\s*$")
IMAGE = re.compile(r"^\s*!\[(.*?)\]\((.*?)\)\s*$")


def inline(text: str) -> str:
    text = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r"\1 (\2)", text)  # links read as text (url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r"\1", text)  # links to repository files: their name only
    text = re.sub(r"<!--(.*?)-->", r"[[\1]]", text)  # notes to the student, highlighted
    return re.sub(r"<br\s*/?>", " ", text).replace("\\|", "|")


def cells(line: str) -> list[str]:
    return [inline(c.strip()) for c in re.split(r"(?<!\\)\|", line.strip().strip("|"))]


def relabel(c, style: str, label: str) -> None:
    """In blocks mode a caption keeps the draft's own label (Table 5.v2-3), for renumbering after insertion."""
    for para in reversed(c.doc.paragraphs):
        if para.style.name == style:
            text = para.text
            for r in para.runs[1:]:
                r.text = ""
            para.runs[0].text = label + text[text.index(":"):]
            return


def orient(c, landscape: bool) -> None:
    """Start a new page turned the given way. Headers, footers and the page count carry on from the page before."""
    from docx.enum.section import WD_ORIENT, WD_SECTION
    from docx.oxml.ns import qn

    sec = c.doc.add_section(WD_SECTION.NEW_PAGE)
    if landscape != (sec.page_width > sec.page_height):
        sec.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
        sec.page_width, sec.page_height = sec.page_height, sec.page_width
    pg = sec._sectPr.find(qn("w:pgNumType"))
    if pg is not None and pg.get(qn("w:start")) is not None:
        del pg.attrib[qn("w:start")]  # the copied section would restart numbering at 1


def build(md: Path, n: int, out: Path, blocks: bool = False) -> Path:
    """``blocks``: the draft is insertion blocks for an existing chapter ("## Insert into 5.2 …"), so those lines
    become highlighted instructions, subsections bold lead-ins, and captions keep their own labels."""
    c = v1.Chapter(TEMPLATE, number=n)
    label: str | None = None
    lines = md.read_text().splitlines()
    para: list[str] = []
    caption: str | None = None
    missing: list[str] = []

    def flush() -> None:
        if para:
            c.p(inline(" ".join(para)))
            para.clear()

    i = 0
    shown = None  # the alt text of the figure just placed, whose caption the draft repeats as a plain line
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if shown and s == shown:
            shown = None
        elif s.startswith("<!--") and not s.endswith("-->"):  # a multi-line note: highlight it as one paragraph
            flush()
            note = [s[4:]]
            while i + 1 < len(lines) and "-->" not in lines[i]:
                i += 1
                note.append(lines[i].strip())
            c.p("[[" + " ".join(note).replace("-->", "").strip() + "]]")
        elif line.startswith("# "):
            flush()
            c.h1(NUM.sub("", line[2:]).strip())
        elif blocks and line.startswith("## "):
            flush()
            c.p("[[**" + inline(line[3:].strip()) + "**]]")
        elif blocks and line.startswith(("### ", "#### ")):
            flush()
            c.p("**" + inline(line.lstrip("#").strip()) + "**")
        elif line.startswith("## "):
            flush()
            c.h2(NUM.sub("", line[3:]).strip())
        elif line.startswith("### "):
            flush()
            c.h3(NUM.sub("", line[4:]).strip())
        elif line.startswith("#### "):
            flush()
            c.p("**" + NUM.sub("", line[5:]).strip() + "**")
        elif IMAGE.match(line):
            flush()
            alt, src = IMAGE.match(line).groups()
            shown = alt.strip()
            cap = re.sub(r"^Figure\s+[\w.\-]+\s*[:.]\s*", "", alt)
            own = re.match(r"^(Figure\s+[\w.\-]+)\s*[:.]", alt)
            path = (md.parent / src)
            png = path.with_suffix(".png")
            if png.exists():
                from docx.image.image import Image as Picture

                pic = Picture.from_file(str(png))
                aspect = pic.px_width / pic.px_height
                if aspect > 1.25:  # a wide figure gets a landscape page of its own: 24.6 cm wide, 14.5 cm tall
                    orient(c, True)
                    c.figure(png, cap, width_cm=min(24.6, 14.5 * aspect))
                    orient(c, False)
                else:  # full text width, at most 19.5 cm tall
                    c.figure(png, cap, width_cm=min(v1.TEXT_WIDTH_CM, 19.5 * aspect))
            else:
                c.fig_n += 1
                c.p(f"[[Figure to add here: {src}]]")
                c.doc.add_paragraph(f"Figure {n}.{c.fig_n}: {cap}", style="FigCaption")
                missing.append(src)
            if blocks and own:
                relabel(c, "FigCaption", own.group(1))
        elif CAPTION.match(line) and CAPTION.match(line).group(2) == "Table":
            flush()
            label, caption = CAPTION.match(line).group(1), inline(CAPTION.match(line).group(3))
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                if not re.fullmatch(r"\|?[\s:|\-]+\|?", lines[i].strip()):
                    rows.append(cells(lines[i]))
                i += 1
            i -= 1
            width = max(len(r) for r in rows)
            rows = [r + [""] * (width - len(r)) for r in rows]
            c.table(caption or "", rows[0], rows[1:], size=9 if width > 3 else 10)
            if blocks and label:
                relabel(c, "TabCaption", label)
            caption = label = None
        elif re.match(r"^\s*[-*] ", line) or re.match(r"^\s*\d+[.)] ", line):
            flush()
            numbered = bool(re.match(r"^\s*\d+[.)] ", line))
            items: list[str] = []
            while i < len(lines) and lines[i].strip():
                t = lines[i]
                if re.match(r"^\s*([-*]|\d+[.)]) ", t):
                    items.append(re.sub(r"^\s*([-*]|\d+[.)]) ", "", t).strip())
                elif items:
                    items[-1] += " " + t.strip()
                i += 1
            i -= 1
            c.items([inline(x) for x in items], numbered=numbered)
        elif s.startswith("```"):
            flush()
            block = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                block.append(lines[i])
                i += 1
            c.code("\n".join(block))
        elif not s or s == "---":
            flush()
        else:
            para.append(s.lstrip("> "))
        i += 1
    flush()
    c.resolve()
    c.save(out)
    if missing:
        print(f"{len(missing)} figure(s) still to render: {', '.join(sorted(set(missing)))}")
    return out


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("markdown", type=Path)
    ap.add_argument("--chapter", type=int, required=True)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--blocks", action="store_true", help="the draft is insertion blocks for an existing chapter")
    a = ap.parse_args()
    print(build(a.markdown, a.chapter, a.out, a.blocks))

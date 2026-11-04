"""Build the CAMR thesis (chapters 1 to 6) as one Word document in the styles of the finished Chapter 5.

The template is docs/report/Chapter5_CAMR.docx: its page size, margins, fonts, heading numbering ("Chapter 5:",
5.1, 5.1.1), caption styles (TabCaption above tables, FigCaption below figures), table look and centred page
numbers are reused as they are. Its body is cleared and replaced with the thesis.

The text lives in docs/thesis/src/*.md, in a small Markdown dialect:

    # Title                      chapter heading (numbered "Chapter N:")
    #! Title                     unnumbered heading 1 (front matter, references, appendices)
    ## Title {#key}              section (N.n); ### subsection (N.n.n); #### bold lead-in paragraph
    Table: {#key} Caption        the caption of the pipe table that follows
    ![{#key} Caption](path)      a figure (wide ones get a landscape page of their own)
    $$ latex $$ {#key}           a numbered equation
    {tab:key} {fig:key} {eq:key} {sec:key}   cross-references, resolved to "Table 4.2", "Figure 5.1", "4.3", "5.2.1"
    [[text]]                     a highlighted placeholder
    **bold**, *italic*, `code`; "- " bullets; "1. " numbered items (i., ii., ...)
    ::pagebreak::                a page break
    ::toc:: / ::lof:: / ::lot::  table of contents, list of figures, list of tables (Word fields)
    ::frontmatter-end::          ends the roman-numbered front matter; chapter 1 starts on page 1

    python docs/thesis/build_thesis.py   ->  docs/thesis/CAMR_Thesis.docx
"""

from __future__ import annotations

import copy
import json
import os
import re
import sys
from pathlib import Path

import docx
import latex2mathml.converter
import mathml2omml
from docx.enum.section import WD_ORIENT, WD_SECTION
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX, WD_TAB_ALIGNMENT, WD_TAB_LEADER
from docx.image.image import Image as Picture
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Cm, Pt, Twips
from lxml import etree

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
TEMPLATE = ROOT / "docs" / "report" / "Chapter5_CAMR.docx"
SRC = HERE / "src"
OUT = HERE / "CAMR_Thesis.docx"
TEXT_WIDTH_CM = 15.9
LANDSCAPE_WIDTH_CM = 24.6
LANDSCAPE_HEIGHT_CM = 14.8

OMML = "http://schemas.openxmlformats.org/officeDocument/2006/math"
_ACCENTS = {"^": "̂", "~": "̃", "¯": "̅", "‾": "̅", "―": "̅", "→": "⃗", "˙": "̇"}
_SAFE = {"*": "∗", "|": "│", "∣": "│"}


def omath(latex: str):
    """LaTeX -> a native Word equation (OMML); the same fixes as the Chapter 5 builder."""
    q = lambda tag: f"{{{OMML}}}{tag}"  # noqa: E731
    mml = latex2mathml.converter.convert(latex)
    mml = mml.replace('<mo stretchy="true">&#x000AF;</mo>', "<mo>&#x02015;</mo>")
    om = mathml2omml.convert(mml)
    el = etree.fromstring(f'<root xmlns:m="{OMML}">{om}</root>')[0]
    for lu in list(el.iter(q("limUpp"))):
        lim = lu.find(q("lim"))
        mark = "".join(lim.itertext()).strip() if lim is not None else ""
        if mark in _ACCENTS:
            acc = etree.Element(q("acc"))
            etree.SubElement(etree.SubElement(acc, q("accPr")), q("chr")).set(q("val"), _ACCENTS[mark])
            acc.append(lu.find(q("e")))
            lu.getparent().replace(lu, acc)
    for rad in el.iter(q("rad")):
        if rad.find(q("deg")) is None:
            pr = etree.Element(q("radPr"))
            etree.SubElement(pr, q("degHide")).set(q("val"), "1")
            rad.insert(0, pr)
            rad.insert(1, etree.Element(q("deg")))
    for n in el.iter(q("nary")):
        pr = n.find(q("naryPr"))
        if pr is None:
            pr = etree.Element(q("naryPr"))
            n.insert(0, pr)
        for part, flag in (("sub", "subHide"), ("sup", "supHide")):
            e = n.find(q(part))
            if e is not None and not "".join(e.itertext()).strip():
                etree.SubElement(pr, q(flag)).set(q("val"), "1")
    for t in el.iter(q("t")):
        if t.text in _SAFE:
            t.text = _SAFE[t.text]
    return el


# --------------------------------------------------------------------------- parsing

KEY = re.compile(r"\s*\{#([\w:-]+)\}\s*")
CAPTION = re.compile(r"^Table:\s*(?:\{#([\w:-]+)\})?\s*(.+)$")
IMAGE = re.compile(r"^!\[(?:\{#([\w:-]+)\})?\s*(.*?)\]\((.*?)\)(\{.*\})?\s*$")
EQUATION = re.compile(r"^\$\$(.+?)\$\$\s*(?:\{#([\w:-]+)\})?\s*$")
ITEM = re.compile(r"^\s*([-*]|\d+[.)])\s+")


def parse(text: str) -> list[tuple]:
    """Markdown -> blocks: (kind, ...)."""
    lines = text.splitlines()
    blocks: list[tuple] = []
    para: list[str] = []
    caption: tuple | None = None

    def flush():
        if para:
            blocks.append(("p", " ".join(para)))
            para.clear()

    i = 0
    while i < len(lines):
        line = lines[i]
        s = line.strip()
        if s.startswith("<!--"):
            flush()
            while "-->" not in lines[i]:
                i += 1
        elif s.startswith("> "):
            flush()
            t = s[2:].strip()
            if t.startswith("- "):
                blocks.append(("box", t[2:], True))
            else:
                blocks.append(("box", t, False))
        elif s.startswith("::") and s.endswith("::"):
            flush()
            blocks.append((s.strip(":"),))
        elif line.startswith("#! "):
            flush()
            blocks.append(("h1u", line[3:].strip()))
        elif re.match(r"^#{1,4} ", line):
            flush()
            level = len(line) - len(line.lstrip("#"))
            title = line[level:].strip()
            m = KEY.search(title)
            key = m.group(1) if m else None
            title = KEY.sub("", title).strip()
            blocks.append(("h", level, title, key))
        elif CAPTION.match(s):
            flush()
            m = CAPTION.match(s)
            caption = (m.group(1), m.group(2).strip())
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                row = lines[i].strip()
                if not re.fullmatch(r"\|?[\s:|\-]+\|?", row):
                    rows.append([c.strip().replace("\\|", "|") for c in re.split(r"(?<!\\)\|", row.strip("|"))])
                i += 1
            i -= 1
            key, cap = caption or (None, "")
            blocks.append(("table", key, cap, rows))
            caption = None
        elif IMAGE.match(s):
            flush()
            key, cap, path, opts = IMAGE.match(s).groups()
            blocks.append(("figure", key, cap.strip(), path, (opts or "").strip("{}")))
        elif EQUATION.match(s):
            flush()
            latex, key = EQUATION.match(s).groups()
            blocks.append(("eq", latex.strip(), key))
        elif ITEM.match(line):
            flush()
            numbered = bool(re.match(r"^\s*\d+[.)]\s", line))
            items: list[str] = []
            while i < len(lines) and lines[i].strip():
                t = lines[i]
                if ITEM.match(t):
                    items.append(ITEM.sub("", t).strip())
                elif items:
                    items[-1] += " " + t.strip()
                i += 1
            i -= 1
            blocks.append(("items", numbered, items))
        elif s.startswith("```"):
            flush()
            code = []
            i += 1
            while i < len(lines) and not lines[i].strip().startswith("```"):
                code.append(lines[i])
                i += 1
            blocks.append(("code", "\n".join(code)))
        elif not s:
            flush()
        else:
            para.append(s)
        i += 1
    flush()
    return blocks


def number(blocks: list[tuple]) -> dict[str, str]:
    """Give every key its printed label, as Word's numbering will show it."""
    labels: dict[str, str] = {}
    ch = sec = sub = fig = tab = eq = 0
    lab_ch = "0"
    for b in blocks:
        if b[0] == "h":
            _, level, _, key = b
            if level == 1:
                ch, sec, sub, fig, tab, eq = ch + 1, 0, 0, 0, 0, 0
                lab = lab_ch = str(ch)
            elif level == 2:
                sec, sub = sec + 1, 0
                lab = f"{ch}.{sec}"
            elif level == 3:
                sub += 1
                lab = f"{ch}.{sec}.{sub}"
            else:
                lab = ""
            if key:
                labels["sec:" + key.removeprefix("sec:")] = lab
        elif b[0] == "h1u":
            m = re.match(r"~?Appendix ([A-Z])", b[1])
            if m:
                lab_ch, fig, tab, eq = m.group(1), 0, 0, 0
        elif b[0] == "table":
            tab += 1
            if b[1]:
                labels["tab:" + b[1].removeprefix("tab:")] = f"{lab_ch}.{tab}"
        elif b[0] == "figure":
            fig += 1
            if b[1]:
                labels["fig:" + b[1].removeprefix("fig:")] = f"{lab_ch}.{fig}"
        elif b[0] == "eq":
            eq += 1
            if b[2]:
                labels["eq:" + b[2].removeprefix("eq:")] = f"{lab_ch}.{eq}"
    return labels


# --------------------------------------------------------------------------- the document


class Thesis:
    def __init__(self, template: Path):
        self.doc = docx.Document(str(template))
        body = self.doc.element.body
        for el in list(body):
            if el.tag != qn("w:sectPr"):
                body.remove(el)
        self.body_sect = body.find(qn("w:sectPr"))
        self._numbering_from_one()
        self.labels: dict[str, str] = {}
        self.unresolved: set[str] = set()
        self.ch = self.fig = self.tab = self.eq = 0
        self.chlabel = "0"
        self.bib = False
        self.sec = [0, 0]
        self.outline: list[tuple[str, int, str]] = []  # (kind, level, printed text) for the lists' entries
        pages = os.environ.get("THESIS_PAGES")
        self.pages = json.loads(Path(pages).read_text()) if pages and Path(pages).exists() else None
        self.in_front = True
        self.fresh = False

    def _numbering_from_one(self):
        numbering = self.doc.part.numbering_part.element
        style = self.doc.styles["Heading 1"].element
        num_id = style.find(qn("w:pPr")).find(qn("w:numPr")).find(qn("w:numId")).get(qn("w:val"))
        for num in numbering.findall(qn("w:num")):
            if num.get(qn("w:numId")) == num_id:
                for old in num.findall(qn("w:lvlOverride")):
                    num.remove(old)

    # ---------------------------------------------------------------- inline

    def resolve(self, text: str) -> str:
        def sub(m):
            k = m.group(1) + ":" + m.group(2)
            if k in self.labels:
                return self.labels[k]
            self.unresolved.add(k)
            return m.group(0)
        return re.sub(r"\{(tab|fig|eq|sec):([\w-]+)\}", sub, text)

    def runs(self, p, text: str, size: float | None = None, bold_all: bool = False) -> None:
        text = self.resolve(text)
        for part in re.split(r"(\*\*.+?\*\*|\*[^*\s][^*]*?\*|`[^`]+`|\[\[.+?\]\])", text):
            if not part:
                continue
            if part.startswith("**") and part.endswith("**") and len(part) > 4:
                r = p.add_run(part[2:-2])
                r.bold = True
            elif part.startswith("[[") and part.endswith("]]"):
                r = p.add_run(part[2:-2])
                r.font.highlight_color = WD_COLOR_INDEX.YELLOW
            elif part.startswith("*") and part.endswith("*") and len(part) > 2:
                r = p.add_run(part[1:-1])
                r.italic = True
            elif part.startswith("`") and part.endswith("`"):
                r = p.add_run(part[1:-1])
                r.font.name = "Courier New"
                r.font.size = Pt((size or 12) - 1.5)
            else:
                r = p.add_run(part)
            if bold_all:
                r.bold = True
            if size and not part.startswith("`"):
                r.font.size = Pt(size)

    # ---------------------------------------------------------------- blocks

    def heading(self, level: int, title: str):
        style = {1: "Heading 1", 2: "Heading 2", 3: "Heading 3"}[level]
        if level == 1:
            self.ch += 1
            self.chlabel = str(self.ch)
            self.fig = self.tab = self.eq = 0
            if self.ch > 1 or not self.in_front:
                self.page_break()
            self.sec = [0, 0]
            label = f"Chapter {self.ch}:"
        elif level == 2:
            self.sec = [self.sec[0] + 1, 0]
            label = f"{self.ch}.{self.sec[0]}"
        else:
            self.sec[1] += 1
            label = f"{self.ch}.{self.sec[0]}.{self.sec[1]}"
        self.outline.append(("toc", level, f"{label} {self.plain(title)}"))
        p = self.doc.add_paragraph(style=style)
        self.runs(p, title)
        return p

    def plain(self, text: str) -> str:
        return re.sub(r"\*\*|\[\[|\]\]|`|(?<!\w)\*|\*(?!\w)", "", self.resolve(text))

    def heading_unnumbered(self, title: str, toc: bool = True):
        p = self.doc.add_paragraph(style="Heading 1")
        ppr = p._p.get_or_add_pPr()
        numpr = OxmlElement("w:numPr")
        ilvl, nid = OxmlElement("w:ilvl"), OxmlElement("w:numId")
        ilvl.set(qn("w:val"), "0")
        nid.set(qn("w:val"), "0")
        numpr.append(ilvl)
        numpr.append(nid)
        ppr.insert(1, numpr)
        p.paragraph_format.left_indent = Cm(0)
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(12)
        if toc:
            self.outline.append(("toc", 1, self.plain(title)))
        if not toc:  # front-matter headings stay out of the table of contents
            ol = OxmlElement("w:outlineLvl")
            ol.set(qn("w:val"), "9")
            ppr.append(ol)
        self.runs(p, title)
        return p

    def para(self, text: str, style: str = "Normal"):
        p = self.doc.add_paragraph(style=style)
        self.runs(p, text)
        return p

    def box(self, text: str, bullet: bool = False, first: bool = False, last: bool = False):
        """The shaded 'In plain words' box of the Chapter 5 template: a blue rule on the left, 10.5 pt."""
        p = self.doc.add_paragraph(style="Normal")
        pf = p.paragraph_format
        pf.space_before, pf.space_after = Pt(6 if first and not bullet else 0), Pt(8 if last else 2)
        pf.left_indent, pf.right_indent = Twips(510 if bullet else 170), Twips(113)
        pf.first_line_indent = Twips(-255) if bullet else Twips(0)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        ppr = p._p.get_or_add_pPr()
        bdr = OxmlElement("w:pBdr")
        left = OxmlElement("w:left")
        for a, v in (("val", "single"), ("sz", "18"), ("space", "6"), ("color", "2A78D6")):
            left.set(qn("w:" + a), v)
        bdr.append(left)
        shd = OxmlElement("w:shd")
        for a, v in (("val", "clear"), ("color", "auto"), ("fill", "EAF1F8")):
            shd.set(qn("w:" + a), v)
        anchor = next((c for c in ppr if c.tag in (qn("w:tabs"), qn("w:spacing"), qn("w:ind"), qn("w:jc"))), None)
        if anchor is not None:
            anchor.addprevious(bdr)
            anchor.addprevious(shd)
        else:
            ppr.append(bdr); ppr.append(shd)
        self.runs(p, ("• " if bullet else "") + text, size=10.5)

    def lead(self, text: str):
        p = self.doc.add_paragraph(style="Normal")
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.space_after = Pt(4)
        self.runs(p, text, bold_all=True)

    def items(self, entries: list[str], numbered: bool):
        roman = ["i", "ii", "iii", "iv", "v", "vi", "vii", "viii", "ix", "x", "xi", "xii", "xiii", "xiv", "xv"]
        for i, e in enumerate(entries):
            p = self.doc.add_paragraph(style="List Paragraph")
            pf = p.paragraph_format
            pf.left_indent, pf.first_line_indent = Cm(1.0), Cm(-0.6)
            pf.space_after = Pt(2 if i < len(entries) - 1 else 8)
            self.runs(p, (f"{roman[i]}.\t" if numbered else "•\t") + e)

    def code(self, text: str):
        for line in text.strip("\n").splitlines():
            p = self.doc.add_paragraph(style="Normal")
            pf = p.paragraph_format
            pf.line_spacing, pf.space_after, pf.left_indent = 1.0, Pt(0), Cm(0.6)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            r = p.add_run(line or " ")
            r.font.name, r.font.size = "Courier New", Pt(9.5)
        self.doc.add_paragraph(style="Normal").paragraph_format.space_after = Pt(0)

    def equation(self, latex: str):
        self.eq += 1
        p = self.doc.add_paragraph(style="Normal")
        pf = p.paragraph_format
        pf.space_before, pf.space_after, pf.first_line_indent = Pt(4), Pt(6), Cm(0)
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM / 2), WD_TAB_ALIGNMENT.CENTER)
        pf.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT)
        p.add_run("\t")
        p._p.append(omath(latex))
        p.add_run(f"\t({self.chlabel}.{self.eq})")

    def table(self, caption: str, rows: list[list[str]], width_cm: float = TEXT_WIDTH_CM):
        self.tab += 1
        cap = self.doc.add_paragraph(style="TabCaption")
        self.runs(cap, f"Table {self.chlabel}.{self.tab}: {caption}")
        self.outline.append(("lot", 1, self.plain(f"Table {self.chlabel}.{self.tab}: {caption}")))
        ncol = max(len(r) for r in rows)
        rows = [r + [""] * (ncol - len(r)) for r in rows]
        size = 10 if ncol <= 3 else 9.5 if ncol <= 5 else 9
        # column widths in proportion to their text, with a floor so short columns stay readable
        def plain(s):
            return re.sub(r"[*`\[\]]", "", s)
        lens = []
        for c in range(ncol):
            words = [len(w) for r in rows for w in plain(r[c]).split()] or [1]
            total = sum(len(plain(r[c])) for r in rows) / len(rows)
            lens.append(max(total, max(words) * 1.1, 4))
        s = sum(lens)
        widths = [width_cm * l / s for l in lens]
        floor = 1.6
        if min(widths) < floor:
            short = [w < floor for w in widths]
            extra = sum(floor - w for w in widths if w < floor)
            big = sum(w for w, sh in zip(widths, short) if not sh)
            widths = [floor if sh else w - extra * w / big for w, sh in zip(widths, short)]
        t = self.doc.add_table(rows=0, cols=ncol)
        t.style = self.doc.styles["Table Grid"]
        t.alignment = WD_TABLE_ALIGNMENT.CENTER
        t.autofit = False
        for ri, values in enumerate(rows):
            cells = t.add_row().cells
            for cell, v, w in zip(cells, values, widths):
                cell.width = Cm(w)
                p = cell.paragraphs[0]
                pf = p.paragraph_format
                pf.line_spacing, pf.space_after, pf.space_before = 1.0, Pt(2), Pt(2)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self.runs(p, v, size, bold_all=(ri == 0))
        for col, w in zip(t.columns, widths):
            col.width = Cm(w)
        trpr = t.rows[0]._tr.get_or_add_trPr()
        trpr.append(trpr.makeelement(qn("w:tblHeader"), {}))
        for row in t.rows:  # a row is never split across pages
            rp = row._tr.get_or_add_trPr()
            rp.append(rp.makeelement(qn("w:cantSplit"), {}))
        self.doc.add_paragraph(style="Normal").paragraph_format.space_after = Pt(0)

    def orient(self, landscape: bool):
        sec = self.doc.add_section(WD_SECTION.NEW_PAGE)
        if landscape != (sec.page_width > sec.page_height):
            sec.orientation = WD_ORIENT.LANDSCAPE if landscape else WD_ORIENT.PORTRAIT
            sec.page_width, sec.page_height = sec.page_height, sec.page_width
        pg = sec._sectPr.find(qn("w:pgNumType"))
        if pg is not None and pg.get(qn("w:start")) is not None:
            del pg.attrib[qn("w:start")]

    def figure(self, caption: str, path: Path, opts: str):
        self.fig += 1
        pic = Picture.from_file(str(path))
        aspect = pic.px_width / pic.px_height
        landscape = "landscape" in opts or ("portrait" not in opts and aspect > 1.45 and "diagrams" in str(path))
        m = re.search(r"width=([\d.]+)", opts)
        if landscape:
            self.orient(True)
            width = min(LANDSCAPE_WIDTH_CM, LANDSCAPE_HEIGHT_CM * aspect)
        else:
            width = float(m.group(1)) if m else min(TEXT_WIDTH_CM, 19.0 * aspect)
        p = self.doc.add_paragraph(style="Normal")
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.keep_with_next = True
        p.paragraph_format.first_line_indent = Cm(0)
        p.paragraph_format.space_after = Pt(0)
        p.add_run().add_picture(str(path), width=Cm(width))
        cap = self.doc.add_paragraph(style="FigCaption")
        self.runs(cap, f"Figure {self.chlabel}.{self.fig}: {caption}")
        self.outline.append(("lof", 1, self.plain(f"Figure {self.chlabel}.{self.fig}: {caption}")))
        if landscape:
            self.orient(False)
            self.fresh = True

    def page_break(self):
        if self.fresh:  # a section break has just started a new page
            self.fresh = False
            return
        p = self.doc.add_paragraph(style="Normal")
        p.paragraph_format.space_after = Pt(0)
        p.add_run().add_break(WD_BREAK.PAGE)

    def field_list(self, instr: str, kind: str, placeholder: str):
        """A TOC field whose result is already filled with entries and pages (Word refreshes it on opening)."""
        entries = (self.pages or {}).get(kind)
        if not entries:
            return self.field(instr, placeholder)
        styles = {1: "toc 1", 2: "toc 2", 3: "toc 3"}
        paras = []
        for level, text, page in entries:
            st = styles[level] if kind == "toc" else "table of figures"
            p = self.doc.add_paragraph(style=st)
            if kind != "toc":
                p.paragraph_format.tab_stops.add_tab_stop(Cm(TEXT_WIDTH_CM), WD_TAB_ALIGNMENT.RIGHT, WD_TAB_LEADER.DOTS)
                p.paragraph_format.left_indent, p.paragraph_format.first_line_indent = Cm(1.5), Cm(-1.5)
                p.paragraph_format.space_after = Pt(4)
            p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            paras.append((p, text, page))
        def fld(p, typ):
            r = OxmlElement("w:r"); c = OxmlElement("w:fldChar"); c.set(qn("w:fldCharType"), typ)
            if typ == "begin":
                c.set(qn("w:dirty"), "true")
            r.append(c); p._p.append(r)
        first = paras[0][0]
        fld(first, "begin")
        r = OxmlElement("w:r"); it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve")
        it.text = f" {instr} "; r.append(it); first._p.append(r)
        fld(first, "separate")
        for p, text, page in paras:
            p.add_run(text)
            p.add_run("\t" + str(page))
        fld(paras[-1][0], "end")

    def field(self, instr: str, placeholder: str):
        p = self.doc.add_paragraph(style="Normal")
        def run(child):
            r = OxmlElement("w:r")
            r.append(child)
            p._p.append(r)
        b = OxmlElement("w:fldChar"); b.set(qn("w:fldCharType"), "begin"); b.set(qn("w:dirty"), "true"); run(b)
        it = OxmlElement("w:instrText"); it.set(qn("xml:space"), "preserve"); it.text = f" {instr} "; run(it)
        s = OxmlElement("w:fldChar"); s.set(qn("w:fldCharType"), "separate"); run(s)
        t = OxmlElement("w:t"); t.text = placeholder; run(t)
        e = OxmlElement("w:fldChar"); e.set(qn("w:fldCharType"), "end"); run(e)

    def end_front_matter(self):
        """The front matter is its own section: roman page numbers, none on the title page."""
        p = self.doc.add_paragraph(style="Normal")
        p.paragraph_format.space_after = Pt(0)
        sect = copy.deepcopy(self.body_sect)
        pg = sect.find(qn("w:pgNumType"))
        if pg is None:
            pg = OxmlElement("w:pgNumType")
            sect.append(pg)
        pg.set(qn("w:fmt"), "lowerRoman")
        pg.set(qn("w:start"), "1")
        if sect.find(qn("w:titlePg")) is None:
            tp = OxmlElement("w:titlePg")
            # titlePg must come after pgNumType/cols/formProt and before docGrid in schema order
            dg = sect.find(qn("w:docGrid"))
            (dg.addprevious(tp) if dg is not None else sect.append(tp))
        p._p.get_or_add_pPr().append(sect)
        bp = self.body_sect.find(qn("w:pgNumType"))
        bp.set(qn("w:fmt"), "decimal")
        bp.set(qn("w:start"), "1")
        self.in_front = False
        self.fresh = True

    def title_page(self, lines: list[str]):
        for ln in lines:
            p = self.doc.add_paragraph(style="Normal")
            p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            p.paragraph_format.space_after = Pt(6)
            if ln.startswith("!"):
                self.runs(p, ln[1:].strip(), size=16, bold_all=True)
            elif ln:
                self.runs(p, ln, bold_all=True)

    # ---------------------------------------------------------------- build

    def render(self, blocks: list[tuple]):
        i = 0
        while i < len(blocks):
            b = blocks[i]
            k = b[0]
            if k not in ("h", "h1u", "pagebreak", "frontmatter-end"):
                self.fresh = False
            if k == "h":
                _, level, title, _ = b
                if level == 4:
                    self.lead(title)
                else:
                    self.heading(level, title)
            elif k == "h1u":
                title = b[1]
                if not self.in_front or self.doc.paragraphs:
                    self.page_break()
                self.heading_unnumbered(title.lstrip("~"), toc=not title.startswith("~"))
                m = re.match(r"~?Appendix ([A-Z])", title)
                if m:
                    self.chlabel, self.fig, self.tab, self.eq = m.group(1), 0, 0, 0
            elif k == "box":
                prev = blocks[i - 1][0] if i else ""
                nxt = blocks[i + 1][0] if i + 1 < len(blocks) else ""
                self.box(b[1], bullet=b[2], first=(prev != "box"), last=(nxt != "box"))
            elif k == "bib":
                self.bib = True
            elif k == "bib-end":
                self.bib = False
            elif k == "p" and self.bib:
                p = self.para(b[1], style="Bibliography")
                p.paragraph_format.space_after = Pt(8)
                p.alignment = WD_ALIGN_PARAGRAPH.LEFT
            elif k == "p":
                text = b[1]
                if text.startswith("> "):
                    self.para(text[2:])
                else:
                    self.para(text)
            elif k == "items":
                self.items(b[2], b[1])
            elif k == "code":
                self.code(b[1])
            elif k == "eq":
                self.equation(b[1])
            elif k == "table":
                self.table(b[2], b[3])
            elif k == "figure":
                _, key, cap, path, opts = b
                self.figure(cap, (HERE / path).resolve(), opts)
            elif k == "pagebreak":
                self.page_break()
            elif k == "toc":
                self.field_list('TOC \\o "1-3" \\h \\z \\u', "toc", "Right-click and choose Update Field to build the table of contents.")
            elif k == "lof":
                self.field_list('TOC \\h \\z \\t "FigCaption,1"', "lof", "Right-click and choose Update Field to build the list of figures.")
            elif k == "lot":
                self.field_list('TOC \\h \\z \\t "TabCaption,1"', "lot", "Right-click and choose Update Field to build the list of tables.")
            elif k == "frontmatter-end":
                self.end_front_matter()
            elif k.startswith("title"):
                pass
            i += 1

    def finish(self, out: Path):
        settings = self.doc.settings.element
        uf = settings.find(qn("w:updateFields"))
        if uf is None:  # schema order: updateFields comes just before hdrShapeDefaults, footnotePr, ... compat
            uf = OxmlElement("w:updateFields")
            after = ("hdrShapeDefaults", "footnotePr", "endnotePr", "compat", "docVars", "rsids", "mathPr",
                     "attachedSchema", "themeFontLang", "clrSchemeMapping", "doNotIncludeSubdocsInStats",
                     "doNotAutoCompressPictures", "forceUpgrade", "captions", "readModeInkLockDown", "smartTagType",
                     "schemaLibrary", "shapeDefaults", "doNotEmbedSmartTags", "decimalSymbol", "listSeparator")
            nxt = next((c for c in settings if any(c.tag == qn("w:" + a) for a in after)), None)
            (nxt.addprevious(uf) if nxt is not None else settings.append(uf))
        uf.set(qn("w:val"), "true")
        cp = self.doc.core_properties
        cp.author = "Ibrahim Sudheysi Ali"
        cp.title = ("A Lightweight External Memory Engine to Bridge the Capability Gap Between On-Device and Cloud "
                    "Language Models")
        cp.subject = "CAMR: final-year project report, Strathmore University"
        cp.keywords = "CAMR; memory engine; on-device language models; MLX; Long Haul"
        cp.comments = ""
        # the template's own figures are still linked from the document part; drop every image nothing uses
        xml = etree.tostring(self.doc.element).decode()
        for rid, rel in list(self.doc.part.rels.items()):
            if rel.reltype.endswith("/image") and f'"{rid}"' not in xml:
                self.doc.part.drop_rel(rid)
        self.doc.save(str(out))


def main() -> None:
    files = sorted(SRC.glob("*.md"))
    text = "\n\n".join(f.read_text() for f in files)
    title = []
    if text.startswith("::title::"):
        head, text = text.split("::title-end::", 1)
        title = head.replace("::title::", "").strip("\n").splitlines()
    blocks = parse(text)
    th = Thesis(TEMPLATE)
    th.labels = number(blocks)
    th.title_page(title)
    th.render(blocks)
    out = Path(sys.argv[1]) if len(sys.argv) > 1 else OUT
    th.finish(out)
    if os.environ.get("THESIS_OUTLINE"):
        Path(os.environ["THESIS_OUTLINE"]).write_text(json.dumps(th.outline, ensure_ascii=False, indent=0))
    if th.unresolved:
        print("unresolved references:", ", ".join(sorted(th.unresolved)))
    old_name = "en" + "gram"  # the code name the system had until 4 November; it must not appear
    leftover = [b for b in blocks if b[0] in ("p", "items") and old_name in str(b).lower()]
    if leftover:
        print("WARNING: the old code name appears", len(leftover), "times")
    print("wrote", out)


if __name__ == "__main__":
    main()

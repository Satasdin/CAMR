#!/usr/bin/env python3
"""Builds the report as a Word file from chapters/*.md, on the approved Strathmore proposal template.

Line forms in a chapter: '#', '##', '###' headings; '- ' bullets; 'i) ' roman items; '!fig path | caption | width in inches';
'!tab caption', optional '!widths a,b,c', then '|' rows with the header first. Inline: **bold**, *italic*, `code`, [PENDING: ...].
"""
import copy
import re
import sys
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK, WD_COLOR_INDEX
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt

HERE = Path(__file__).parent
TEMPLATE = HERE / "template.docx"
OUT = HERE / "Burrow_Project_Report.docx"
FRONT = ["0-front.md"]
BODY = ["1-introduction.md", "2-literature.md", "3-methodology.md", "4-design.md", "5-implementation.md"]
BACK = ["7-references.md", "8-appendices.md"]
PROJECT_TYPE = "[Internal Project]"

TITLE = "A Lightweight External Memory Engine to Bridge the Capability Gap Between On-Device and Cloud Language Models"
# The chapters revised from the approved proposal live in chapters2. The rejected first rewrite stays in chapters.
CHAPTERS = HERE / "chapters3"
INLINE = re.compile(r"(\[PENDING:.*?\]|\*\*\*.+?\*\*\*|\*\*.+?\*\*|\*.+?\*|`.+?`)")


M = "http://schemas.openxmlformats.org/officeDocument/2006/math"


def mel(tag, *children):
    node = OxmlElement("m:" + tag)
    for child in children:
        node.append(child)
    return node


def mt(words, plain=False):
    run = mel("r")
    if plain:
        prop = mel("rPr", mel("nor"))
        run.append(prop)
    text = OxmlElement("m:t")
    text.set(qn("xml:space"), "preserve")
    text.text = words
    run.append(text)
    return run


def mfrac(top, bottom, bar=True):
    if bar:
        return mel("f", mel("num", *top), mel("den", *bottom))
    kind = OxmlElement("m:type")
    kind.set(qn("m:val"), "noBar")
    return mel("f", mel("fPr", kind), mel("num", *top), mel("den", *bottom))


def msub(base, sub):
    return mel("sSub", mel("e", *base), mel("sub", *sub))


def msum(sub, sup, body):
    chr_ = OxmlElement("m:chr")
    chr_.set(qn("m:val"), "\u2211")
    limit = OxmlElement("m:limLoc")
    limit.set(qn("m:val"), "undOvr")
    pr = mel("naryPr", chr_, limit)
    if not sup:
        hide = OxmlElement("m:supHide")
        hide.set(qn("m:val"), "1")
        pr.append(hide)
    return mel("nary", pr, mel("sub", *sub), mel("sup", *sup), mel("e", *body))


def mparen(*body):
    return mel("d", mel("e", *body))


EQUATIONS = {
    "accuracy": lambda: [mt("Accuracy = "), mfrac([mt("answers marked right", plain=True)], [mt("questions asked", plain=True)])],
    "gap": lambda: [mt("Gap closed = "), mfrac([msub([mt("S")], [mt("treatment", plain=True)]), mt(" \u2212 "), msub([mt("S")], [mt("floor", plain=True)])], [msub([mt("S")], [mt("ceiling", plain=True)]), mt(" \u2212 "), msub([mt("S")], [mt("floor", plain=True)])])],
    "recall": lambda: [mt("recall(i, m) = "), mfrac([mt("|"), msub([mt("G")], [mt("i")]), mt(" \u2229 "), msub([mt("F")], [mt("i,m")]), mt("|")], [mt("|"), msub([mt("G")], [mt("i")]), mt("|")])],
    "sign": lambda: [mt("p = min"), mparen(mt("1, 2 "), msum([mt("j=0")], [mt("min(b,c)")], [mparen(mfrac([mt("b+c")], [mt("j")], bar=False)), mt(" 0.5"), mel("sSup", mel("e", mt("")), mel("sup", mt("b+c")))]))],
    "cosine": lambda: [mt("cos(q, v) = "), mfrac([mt("q \u00b7 v")], [mt("\u2016q\u2016 \u2016v\u2016")])],
    "rrf": lambda: [mt("score(p) = w(p) "), msum([mt("r \u2208 {words, meaning}")], [], [mfrac([mt("1")], [mt("60 + "), msub([mt("rank")], [mt("r")]), mt("(p)")])])],
    "walk": lambda: [mt("s(n) = w(n) "), mparen(mfrac([mt("b(n)")], [mt("h")]), mt(" + k(n)"))],
}


def set_text(paragraph, words):
    runs = paragraph.runs
    runs[0].text = words
    for run in runs[1:]:
        run._r.getparent().remove(run._r)


def add_inline(paragraph, words, size=None):
    for piece in INLINE.split(words):
        if not piece:
            continue
        if piece.startswith("[PENDING:"):
            run = paragraph.add_run(piece)
            run.font.highlight_color = WD_COLOR_INDEX.YELLOW
        elif piece.startswith("***"):
            run = paragraph.add_run(piece[3:-3])
            run.bold = True
            run.italic = True
        elif piece.startswith("**"):
            run = paragraph.add_run(piece[2:-2])
            run.bold = True
        elif piece.startswith("*") and len(piece) > 2:
            run = paragraph.add_run(piece[1:-1])
            run.italic = True
        elif piece.startswith("`"):
            run = paragraph.add_run(piece[1:-1])
            run.font.name = "Courier New"
            run.font.size = Pt((size or 12) - 1.5)
        else:
            run = paragraph.add_run(piece)
        if size and not piece.startswith("`"):
            run.font.size = Pt(size)


def field(paragraph, instruction):
    def char(kind):
        element = OxmlElement("w:fldChar")
        element.set(qn("w:fldCharType"), kind)
        return element

    run = paragraph.add_run()
    run._r.append(char("begin"))
    run = paragraph.add_run()
    code = OxmlElement("w:instrText")
    code.set(qn("xml:space"), "preserve")
    code.text = instruction
    run._r.append(code)
    run = paragraph.add_run()
    run._r.append(char("separate"))
    paragraph.add_run("Right-click and choose Update Field.")
    run = paragraph.add_run()
    run._r.append(char("end"))


def cell_borders(table):
    properties = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        edge = OxmlElement(f"w:{side}")
        edge.set(qn("w:val"), "single")
        edge.set(qn("w:sz"), "4")
        edge.set(qn("w:color"), "000000")
        borders.append(edge)
    properties.append(borders)


def repeat_header(row):
    mark = OxmlElement("w:tblHeader")
    mark.set(qn("w:val"), "true")
    row._tr.get_or_add_trPr().append(mark)


def keep_row_whole(row):
    mark = OxmlElement("w:cantSplit")
    mark.set(qn("w:val"), "true")
    row._tr.get_or_add_trPr().append(mark)


class Writer:
    def __init__(self, document):
        self.document = document
        self.first_chapter = True

    def paragraph(self, words, style="Normal", align=WD_ALIGN_PARAGRAPH.JUSTIFY):
        made = self.document.add_paragraph(style=style)
        add_inline(made, words)
        if align is not None:
            made.alignment = align
        return made

    def page_break(self):
        self.document.add_paragraph().add_run().add_break(WD_BREAK.PAGE)

    def heading(self, level, words):
        if level == 1 and not self.first_chapter:
            self.page_break()
        self.first_chapter = False
        match = re.match(r"(\d+(?:\.\d+)+)\s+(.*)", words)
        text = f"{match.group(1)}\t{match.group(2)}" if match else words
        self.document.add_paragraph(text, style=f"Heading {level}")

    def bullet(self, marker, words):
        made = self.document.add_paragraph(style="Normal")
        made.paragraph_format.left_indent = Inches(0.4)
        made.paragraph_format.first_line_indent = Inches(-0.3)
        made.paragraph_format.tab_stops.add_tab_stop(Inches(0.4))
        made.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        add_inline(made, f"{marker}\t{words}")

    def figure(self, path, caption, width):
        holder = self.document.add_paragraph()
        holder.alignment = WD_ALIGN_PARAGRAPH.CENTER
        holder.paragraph_format.keep_with_next = True
        holder.add_run().add_picture(str(HERE / path), width=Inches(float(width)))
        made = self.document.add_paragraph(style="FigCaption")
        add_inline(made, caption)

    def table(self, caption, rows, widths):
        made = self.document.add_paragraph(style="TabCaption")
        made.paragraph_format.keep_with_next = True
        add_inline(made, caption)
        table = self.document.add_table(rows=len(rows), cols=len(rows[0]))
        table.autofit = False
        cell_borders(table)
        total = sum(widths) if widths else None
        columns = [6.26 * w / total for w in widths] if widths else [6.26 / len(rows[0])] * len(rows[0])
        for r, row in enumerate(rows):
            keep_row_whole(table.rows[r])
            for c, words in enumerate(row):
                cell = table.cell(r, c)
                cell.width = Inches(columns[c])
                body = cell.paragraphs[0]
                body.paragraph_format.line_spacing = 1.0
                body.paragraph_format.space_after = Pt(2)
                body.paragraph_format.space_before = Pt(2)
                add_inline(body, f"**{words}**" if r == 0 else words, size=10)
                if r == 0:
                    shade = OxmlElement("w:shd")
                    shade.set(qn("w:val"), "clear")
                    shade.set(qn("w:fill"), "E7E7E7")
                    cell._tc.get_or_add_tcPr().append(shade)
        repeat_header(table.rows[0])
        gap = self.document.add_paragraph()
        gap.paragraph_format.space_after = Pt(4)

    def equation(self, key, caption):
        holder = self.document.add_paragraph()
        holder.alignment = WD_ALIGN_PARAGRAPH.CENTER
        holder.paragraph_format.keep_with_next = True
        math = mel("oMath", *EQUATIONS[key]())
        holder._p.append(mel("oMathPara", math))
        made = self.document.add_paragraph(style="EqCaption")
        made.alignment = WD_ALIGN_PARAGRAPH.CENTER
        add_inline(made, caption)

    def code(self, lines):
        for i, words in enumerate(lines):
            made = self.document.add_paragraph()
            made.paragraph_format.line_spacing = 1.0
            made.paragraph_format.space_after = Pt(0)
            made.paragraph_format.space_before = Pt(0)
            made.paragraph_format.left_indent = Inches(0.2)
            made.paragraph_format.keep_together = True
            made.paragraph_format.keep_with_next = i < len(lines) - 1
            made.alignment = WD_ALIGN_PARAGRAPH.LEFT
            shade = OxmlElement("w:shd")
            shade.set(qn("w:val"), "clear")
            shade.set(qn("w:fill"), "F2F2F2")
            made._p.get_or_add_pPr().append(shade)
            run = made.add_run(words if words else " ")
            run.font.name = "Courier New"
            run.font.size = Pt(9)
        gap = self.document.add_paragraph()
        gap.paragraph_format.space_after = Pt(4)

    def chapter(self, name):
        lines = []
        for raw in (CHAPTERS / name).read_text().split("\n"):
            if raw.startswith("!include "):
                lines.extend((HERE / raw[9:].strip()).read_text().split("\n"))
            else:
                lines.append(raw)
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line:
                i += 1
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#"))
                self.heading(level, line[level:].strip())
                i += 1
            elif line.startswith("!fig"):
                path, caption, width = [part.strip() for part in line[4:].split("|")]
                self.figure(path, caption, width)
                i += 1
            elif line.startswith("!tab"):
                caption = line[4:].strip()
                i += 1
                widths = None
                if lines[i].startswith("!widths"):
                    widths = [float(x) for x in lines[i][7:].split(",")]
                    i += 1
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    rows.append([cell.strip() for cell in lines[i].strip().strip("|").split(" | ")])
                    i += 1
                bad = [row for row in rows if len(row) != len(rows[0])]
                if bad:
                    sys.exit(f"{name}: uneven table row in {caption}: {bad[0]}")
                self.table(caption, rows, widths)
            elif line.startswith("!eq"):
                key, caption = [part.strip() for part in line[3:].split("|")]
                self.equation(key, caption)
                i += 1
            elif line == "!code":
                i += 1
                block = []
                while lines[i].rstrip() != "!endcode":
                    block.append(lines[i].rstrip())
                    i += 1
                i += 1
                self.code(block)
            elif line.startswith("- "):
                self.bullet("•", line[2:])
                i += 1
            elif re.match(r"^[ivx]+\) ", line):
                marker, rest = line.split(") ", 1)
                self.bullet(marker + ".", rest)
                i += 1
            elif line.startswith("@ "):
                made = self.document.add_paragraph(style="Normal")
                made.paragraph_format.left_indent = Inches(0.4)
                made.paragraph_format.first_line_indent = Inches(-0.4)
                add_inline(made, line[2:])
                i += 1
            elif line == "!pagebreak":
                self.page_break()
                i += 1
            elif line.startswith("!toc"):
                instruction = line[4:].strip()
                field(self.document.add_paragraph(), instruction)
                i += 1
            else:
                self.paragraph(line)
                i += 1


def main():
    document = docx.Document(str(TEMPLATE))
    body = document.element.body
    children = list(body)
    # Cover and declaration stay; everything else in the template goes.
    paragraphs = document.paragraphs
    set_text(paragraphs[2], TITLE)
    set_text(paragraphs[7], "Ibrahim Sudheysi Ali")
    set_text(paragraphs[22], paragraphs[22].text.replace("Project Proposal Submitted", "Project Report Submitted"))
    set_text(paragraphs[30], "November 2026")
    # The guide's cover examples carry the project type directly under the title.
    kind = paragraphs[4]
    kind._p.getparent().replace(kind._p, copy.deepcopy(paragraphs[7]._p))
    kind = document.paragraphs[4]
    set_text(kind, PROJECT_TYPE)
    set_text(paragraphs[41], paragraphs[41].text.replace("The proposal of", "The project report of"))
    section_mark = children[81]
    tail = children[-1]
    for element in children[45:]:
        if element is not tail:
            body.remove(element)
    # Images belonging to the old proposal must not travel with the new file.
    part = document.part
    for key, relation in list(part.rels.items()):
        if relation.reltype.endswith("/image"):
            del part.rels[key]

    writer = Writer(document)
    for name in FRONT:
        writer.chapter(name)
    tail.addprevious(section_mark)
    writer.first_chapter = True
    for name in BODY + BACK:
        writer.chapter(name)

    if "--ask-to-update" in sys.argv:
        update = OxmlElement("w:updateFields")
        update.set(qn("w:val"), "true")
        document.settings.element.append(update)
    document.core_properties.title = TITLE
    document.core_properties.author = "Ibrahim Sudheysi Ali"
    document.save(str(OUT))
    print(OUT, OUT.stat().st_size)


if __name__ == "__main__":
    main()

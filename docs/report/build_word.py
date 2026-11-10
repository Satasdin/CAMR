#!/usr/bin/env python3
"""Prepares the report text for Word: chapters4/*.md placed on the Strathmore template with Word's own features.

What this file sets up, and Word then updates and lays out:
- body text in the Body Text style (Times New Roman 12, justified, 1.5 lines, space after each paragraph);
- headings in Heading 1 to 3, every chapter on a new page;
- captions in the Caption style with SEQ fields (figure captions below, table captions above), each bookmarked,
  and every mention of a figure, table or equation in the text as a REF cross-reference to that bookmark;
- the contents and the lists of figures, tables and equations as TOC fields;
- every citation as a Mendeley Cite content control carrying its reference data, and the reference list as the
  Mendeley bibliography control, so Mendeley Cite regenerates both in APA 7th.

Line forms in a chapter are those of build.py, with two additions: '!include file | Table 5.5' renumbers an included
table, and a figure caption's trailing full stop is not written.
"""
import base64, copy, json, re, sys, uuid, zipfile, shutil
from pathlib import Path

import docx
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_COLOR_INDEX, WD_LINE_SPACING
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Inches, Pt, RGBColor
from PIL import Image

from build import EQUATIONS, mel, cell_borders, repeat_header, keep_row_whole, set_text, TITLE, PROJECT_TYPE

HERE = Path(__file__).parent
TEMPLATE = HERE / "template.docx"
OUT = HERE / "Burrow_Report_Word.docx"
CHAPTERS = HERE / "chapters4"
FRONT = ["0-front.md"]
BODY = ["1-introduction.md", "2-literature.md", "3-methodology.md", "4-design.md", "5-implementation.md"]
BACK = ["7-references.md", "8-appendices.md"]
REFS = json.loads((HERE / "research" / "burrow-references.json").read_text())
TEXT_WIDTH = 6.27
MAX_FIGURE_HEIGHT = 7.7

INLINE = re.compile(r"(\[PENDING[^\]]*\]|\*\*\*.+?\*\*\*|\*\*.+?\*\*|\*.+?\*|`.+?`)")
XREF = re.compile(r"\b(Figure|Table|Equation) (A?\d+\.\d+)\b")

# ---------------------------------------------------------------- citations

def family(person):
    return person.get("family") or person["literal"]

def lead(item):
    return family(item["author"][0]) if item["author"] else item["title"]

class Library:
    def __init__(self, items):
        self.items = items
        self.cited = []          # keys in order of first citation
        self.records = []        # one dict per citation placed in the document
        self.by_year = {}
        for item in items:
            self.by_year.setdefault(item["issued"]["date-parts"][0][0], []).append(item)
        # letter suffixes follow the order of the verified APA list
        self.letter = {}
        groups = {}
        for item in items:
            groups.setdefault((lead(item), item["issued"]["date-parts"][0][0], len(item["author"]) == 1 and "literal" in item["author"][0]), []).append(item)
        for (name, year, org), group in groups.items():
            if org and len(group) > 1:
                for i, item in enumerate(group):
                    self.letter[item["id"]] = "ab cdef".replace(" ", "")[i]

    def resolve(self, names, year, where):
        """names: the author words as written, for example 'Z. Zhang et al.' or 'Hu, Liu, et al.'."""
        letter = year[4:]
        number = int(year[:4])
        names = names.strip().rstrip(",").strip()
        if names.lower().endswith("data protection act"):
            return next(i for i in self.items if i["title"] == "Data Protection Act")
        initial = None
        m = re.match(r"([A-Z])\. (.+)", names)
        if m: initial, names = m.group(1), m.group(2)
        first = re.split(r",| et al\.| and | & ", names)[0].strip()
        found = [i for i in self.by_year.get(number, []) if lead(i) == first]
        if letter:
            found = [i for i in found if self.letter.get(i["id"]) == letter]
        if initial:
            found = [i for i in found if i["author"][0].get("given", "").startswith(initial)]
        if len(found) > 1:
            second = re.search(r"(?:, | and | & )([A-Z][^,& ]+)", names)
            if second:
                found = [i for i in found if len(i["author"]) > 1 and family(i["author"][1]) == second.group(1)]
        if len(found) != 1:
            sys.exit(f"citation not resolved ({len(found)} matches): '{names}' {year} in: {where[:120]}")
        return found[0]

    def tag(self, items, shown, composite=False):
        ident = "MENDELEY_CITATION_" + str(uuid.uuid4())
        entries = []
        for item in items:
            if item["id"] not in self.cited: self.cited.append(item["id"])
            uid = str(uuid.uuid5(uuid.NAMESPACE_URL, "burrow-report/v2/" + item["type"] + "/" + item["id"]))
            data = {k: v for k, v in item.items() if not k.startswith("_")}
            data["id"] = uid
            data["author"] = [dict(a, **({"parse-names": False, "dropping-particle": "", "non-dropping-particle": ""} if "family" in a else {})) for a in item["author"]]
            data["container-title-short"] = ""
            entries.append({"id": uid, "itemData": data, "isTemporary": False, "suppress-author": composite, "composite": False, "author-only": False})
        body = {"citationID": ident, "properties": {"noteIndex": 0}, "isEdited": False,
                "manualOverride": {"isManuallyOverridden": False, "citeprocText": shown.replace("&", "&#38;"), "manualOverrideText": ""},
                "citationItems": entries}
        tag = "MENDELEY_CITATION_v3_" + base64.b64encode(json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()).decode()
        record = {k: body[k] for k in ("citationID", "properties", "isEdited", "manualOverride")}
        record["citationTag"] = tag
        record["citationItems"] = entries
        self.records.append(record)
        return tag

NAME = r"(?:[A-Z]\. )?[A-ZÀ-Ý][\w’'\-À-ÿ.]*(?: [A-Z][\w\-]+)*"
NARRATIVE = re.compile(r"((?:the )?Data Protection Act|" + NAME + r"(?:, " + NAME + r")*,? (?:et al\.|and " + NAME + r")|" + NAME + r") \((\d{4}[a-z]?)\)")
PAREN = re.compile(r"\(([^()]*?\b(?:19|20)\d{2}[a-z]?)\)")
PIECE = re.compile(r"^(.+?),? (\d{4}[a-z]?)$")

def split_citations(text, library):
    """Returns a list of ('text', words) and ('cite', shown, items, composite)."""
    spans = []
    for m in NARRATIVE.finditer(text):
        names = m.group(1)
        if names.split()[0] in ("In", "Section", "Chapter", "Figure", "Table", "Appendix", "Equation", "Sprint", "November", "June", "July", "Python", "SQLite", "Cap."):
            continue
        try_names = names
        # a narrative citation may be preceded by ordinary capitalised words; take the shortest tail that resolves
        item = None
        words = names.split(" ")
        for start in range(len(words)):
            tail = " ".join(words[start:])
            if not re.match(r"(?:the )?[A-Z]", tail): continue
            try:
                item = library_try(library, tail, m.group(2))
            except LookupError:
                item = None
            if item:
                try_names = tail
                break
        if item:
            if try_names.startswith("the "): try_names = try_names[4:]
            begin = m.end(1) - len(try_names)
            spans.append((begin, m.end(), text[begin:m.end()], [item], True))
    for m in PAREN.finditer(text):
        if any(s[0] <= m.start() < s[1] for s in spans): continue
        pieces = [p.strip() for p in m.group(1).split(";")]
        items = []
        ok = True
        for piece in pieces:
            pm = PIECE.match(piece)
            if not pm: ok = False; break
            try:
                item = library_try(library, pm.group(1), pm.group(2))
            except LookupError:
                item = None
            if not item: ok = False; break
            items.append(item)
        if ok and items:
            spans.append((m.start(), m.end(), m.group(0), items, False))
    spans.sort()
    out, pos = [], 0
    for begin, end, shown, items, composite in spans:
        if begin < pos: continue
        if begin > pos: out.append(("text", text[pos:begin]))
        out.append(("cite", shown, items, composite))
        pos = end
    if pos < len(text): out.append(("text", text[pos:]))
    return out

# Where two sources share a first author and a year and only one of them is cited, the text needs no initial.
PREFER = {("Zhang et al.", "2025"): "Zhang2025", ("Liu et al.", "2024"): "Liu2024b", ("Gao et al.", "2023"): "Gao2023"}

def library_try(library, names, year):
    letter = year[4:]; number = int(year[:4])
    names = names.strip().rstrip(",").strip()
    if names.lower().endswith("data protection act"):
        return next(i for i in library.items if i["title"] == "Data Protection Act")
    initial = None
    m = re.match(r"([A-Z])\. (.+)", names)
    if m: initial, names = m.group(1), m.group(2)
    first = re.split(r",| et al\.| and | & ", names)[0].strip()
    found = [i for i in library.by_year.get(number, []) if lead(i) == first]
    if not found: return None
    if letter: found = [i for i in found if library.letter.get(i["id"]) == letter]
    if initial: found = [i for i in found if i["author"][0].get("given", "").startswith(initial)]
    if len(found) > 1:
        second = re.search(r"(?:, | and | & )([A-Z][^,& ]+)", names)
        if second:
            narrowed = [i for i in found if len(i["author"]) > 1 and family(i["author"][1]) == second.group(1)]
            if narrowed: found = narrowed
    if len(found) > 1:
        chosen = PREFER.get((names, year))
        if not chosen: sys.exit(f"ambiguous citation: '{names}' {year}: {[i['id'] for i in found]}")
        found = [i for i in found if i["id"] == chosen]
    return found[0] if found else None

# ---------------------------------------------------------------- low-level Word XML

def fld(kind):
    el = OxmlElement("w:fldChar"); el.set(qn("w:fldCharType"), kind); return el

def add_field(paragraph, instruction, shown, bold=None, dirty=False):
    r = paragraph.add_run(); begin = fld("begin")
    if dirty: begin.set(qn("w:dirty"), "true")
    r._r.append(begin)
    r = paragraph.add_run(); code = OxmlElement("w:instrText"); code.set(qn("xml:space"), "preserve"); code.text = instruction; r._r.append(code)
    r = paragraph.add_run(); r._r.append(fld("separate"))
    r = paragraph.add_run(shown)
    if bold is not None: r.bold = bold
    r2 = paragraph.add_run(); r2._r.append(fld("end"))
    return r

class Marks:
    def __init__(self): self.next = 100
    def wrap(self, paragraph, name, first_index):
        """Bookmarks the runs of the paragraph from first_index to the end."""
        start = OxmlElement("w:bookmarkStart"); start.set(qn("w:id"), str(self.next)); start.set(qn("w:name"), name)
        end = OxmlElement("w:bookmarkEnd"); end.set(qn("w:id"), str(self.next)); self.next += 1
        runs = paragraph._p.findall(qn("w:r"))
        runs[first_index].addprevious(start)
        paragraph._p.append(end)

def ref_name(kind, number):
    return "_Ref" + kind[:3] + number.replace(".", "_")

def shade(cell, fill):
    el = OxmlElement("w:shd"); el.set(qn("w:val"), "clear"); el.set(qn("w:fill"), fill); cell._tc.get_or_add_tcPr().append(el)

def cell_margins(table, top=50, bottom=50, left=90, right=90):
    pr = table._tbl.tblPr; mar = OxmlElement("w:tblCellMar")
    for side, value in (("top", top), ("left", left), ("bottom", bottom), ("right", right)):
        el = OxmlElement(f"w:{side}"); el.set(qn("w:w"), str(value)); el.set(qn("w:type"), "dxa"); mar.append(el)
    pr.append(mar)

# ---------------------------------------------------------------- the writer

class Writer:
    def __init__(self, document, library):
        self.document = document
        self.library = library
        self.marks = Marks()
        self.known = set()          # captions defined, as (kind, number)
        self.mentioned = []         # cross-references made
        self.seen_chapter = {}      # (kind, chapter) -> first caption already placed
        self.in_appendix = False
        self.appendix_count = 0
        self.words = 0

    # ---- inline text
    def inline(self, paragraph, words, size=None, cite=True, xref=True):
        parts = split_citations(words, self.library) if cite else [("text", words)]
        for part in parts:
            if part[0] == "cite":
                _, shown, items, composite = part
                self.citation(paragraph, shown, items, composite, size)
            else:
                self.plain(paragraph, part[1], size, xref)

    def plain(self, paragraph, words, size, xref=True):
        for piece in INLINE.split(words):
            if not piece: continue
            if piece.startswith("[PENDING"):
                run = paragraph.add_run(piece); run.font.highlight_color = WD_COLOR_INDEX.YELLOW
            elif piece.startswith("***"):
                run = paragraph.add_run(piece[3:-3]); run.bold = True; run.italic = True
            elif piece.startswith("**"):
                run = paragraph.add_run(piece[2:-2]); run.bold = True
            elif piece.startswith("*") and len(piece) > 2:
                run = paragraph.add_run(piece[1:-1]); run.italic = True
            elif piece.startswith("`"):
                run = paragraph.add_run(piece[1:-1]); run.font.name = "Courier New"; run.font.size = Pt((size or 12) - 1.5)
            else:
                self.with_refs(paragraph, piece, size, xref); continue
            if size and not piece.startswith("`"): run.font.size = Pt(size)

    def with_refs(self, paragraph, words, size, xref):
        pos = 0
        for m in (XREF.finditer(words) if xref else []):
            if m.start() > pos:
                run = paragraph.add_run(words[pos:m.start()])
                if size: run.font.size = Pt(size)
            run = add_field(paragraph, f"REF {ref_name(m.group(1), m.group(2))} \\h", m.group(0))
            if size: run.font.size = Pt(size)
            self.mentioned.append((m.group(1), m.group(2)))
            pos = m.end()
        if pos < len(words):
            run = paragraph.add_run(words[pos:])
            if size: run.font.size = Pt(size)

    def citation(self, paragraph, shown, items, composite, size):
        # A narrative citation keeps the author's name as ordinary text and puts the year in the Mendeley field
        # with the author suppressed, which is how Mendeley Cite writes "Kaplan et al. (2020)".
        if composite:
            names, _, year = shown.rpartition(" (")
            run = paragraph.add_run(names + " ")
            if size: run.font.size = Pt(size)
            shown = "(" + year
        tag = self.library.tag(items, shown, composite)
        sdt = OxmlElement("w:sdt"); pr = OxmlElement("w:sdtPr")
        t = OxmlElement("w:tag"); t.set(qn("w:val"), tag); pr.append(t)
        i = OxmlElement("w:id"); i.set(qn("w:val"), str(abs(hash(tag)) % 2000000000)); pr.append(i)
        ph = OxmlElement("w:placeholder"); dp = OxmlElement("w:docPart"); dp.set(qn("w:val"), "DefaultPlaceholder_-1854013440"); ph.append(dp); pr.append(ph)
        sdt.append(pr)
        content = OxmlElement("w:sdtContent"); sdt.append(content)
        run = paragraph.add_run(shown)
        if size: run.font.size = Pt(size)
        paragraph._p.remove(run._r); content.append(run._r)
        paragraph._p.append(sdt)

    # ---- blocks
    def body(self, words, align=WD_ALIGN_PARAGRAPH.JUSTIFY):
        made = self.document.add_paragraph(style="Body Text")
        self.inline(made, words)
        if align is not None: made.alignment = align
        self.words += len(words.split())
        return made

    def heading(self, level, words):
        match = re.match(r"(\d+(?:\.\d+)+)\s+(.*)", words)
        text = f"{match.group(1)}\t{match.group(2)}" if match else words
        made = self.document.add_paragraph(text, style=f"Heading {level}")
        if level == 1:
            made.paragraph_format.page_break_before = True
            self.in_appendix = words.startswith("Appendices")
        if level == 2 and self.in_appendix:
            self.appendix_count += 1
            if self.appendix_count > 1: made.paragraph_format.page_break_before = True
        return made

    def bullet(self, marker, words):
        made = self.document.add_paragraph(style="Body Text")
        made.paragraph_format.left_indent = Inches(0.5)
        made.paragraph_format.first_line_indent = Inches(-0.35)
        made.paragraph_format.tab_stops.add_tab_stop(Inches(0.5))
        made.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        self.inline(made, f"{marker}\t{words}")

    def caption(self, text, keep_next=False):
        m = re.match(r"(Figure|Table|Equation) ((A?\d+)\.(\d+)): (.*)$", text)
        if not m: sys.exit("bad caption: " + text)
        kind, number, chapter, _, words = m.groups()
        made = self.document.add_paragraph(style="Caption")
        made.alignment = WD_ALIGN_PARAGRAPH.CENTER
        made.paragraph_format.keep_with_next = keep_next
        made.add_run(f"{kind} {chapter}.")
        first = (kind, chapter) not in self.seen_chapter
        self.seen_chapter[(kind, chapter)] = True
        add_field(made, f"SEQ {kind} \\* ARABIC" + (" \\r 1" if first else ""), number.split(".")[1])
        self.marks.wrap(made, ref_name(kind, number), 0)
        made.add_run(": ")
        self.inline(made, words.rstrip("."), xref=False)
        self.known.add((kind, number))

    def figure(self, path, caption, width):
        source = HERE / path
        with Image.open(source) as im: w, h = im.size
        width = min(float(width), TEXT_WIDTH)
        if width * h / w > MAX_FIGURE_HEIGHT: width = MAX_FIGURE_HEIGHT * w / h
        holder = self.document.add_paragraph(style="Body Text")
        holder.alignment = WD_ALIGN_PARAGRAPH.CENTER
        holder.paragraph_format.keep_with_next = True
        holder.paragraph_format.space_after = Pt(4)
        holder.paragraph_format.line_spacing = 1.0
        holder.add_run().add_picture(str(source), width=Inches(width))
        self.caption(caption)

    def table(self, caption, rows, widths):
        self.caption(caption, keep_next=True)
        table = self.document.add_table(rows=len(rows), cols=len(rows[0]))
        table.autofit = False
        table.alignment = 1
        cell_borders(table); cell_margins(table)
        total = sum(widths) if widths else None
        columns = [TEXT_WIDTH * w / total for w in widths] if widths else [TEXT_WIDTH / len(rows[0])] * len(rows[0])
        for r, row in enumerate(rows):
            keep_row_whole(table.rows[r])
            for c, words in enumerate(row):
                cell = table.cell(r, c); cell.width = Inches(columns[c])
                body = cell.paragraphs[0]
                body.style = self.document.styles["Table Text"]
                short = len(words) < 28 and c > 0
                body.alignment = WD_ALIGN_PARAGRAPH.LEFT
                self.inline(body, f"**{words}**" if r == 0 else words, size=11)
                if r == 0: shade(cell, "E7E6E6")
        repeat_header(table.rows[0])
        # a short table stays on one page; a long one at least keeps its heading with its first rows
        last_kept = len(rows) - 1 if len(rows) <= 13 else 2
        for r in range(last_kept):
            for cell in table.rows[r].cells:
                for para in cell.paragraphs: para.paragraph_format.keep_with_next = True
        gap = self.document.add_paragraph(style="Body Text")
        gap.paragraph_format.space_after = Pt(2); gap.paragraph_format.line_spacing = 0.6

    def equation(self, key, caption):
        holder = self.document.add_paragraph(style="Body Text")
        holder.alignment = WD_ALIGN_PARAGRAPH.CENTER
        holder.paragraph_format.keep_with_next = True
        holder._p.append(mel("oMathPara", mel("oMath", *EQUATIONS[key]())))
        self.caption(caption)

    def toc(self, instruction):
        made = self.document.add_paragraph(style="Body Text")
        add_field(made, instruction, "Update this field in Word.")

    def bibliography(self, lines):
        sdt = OxmlElement("w:sdt"); pr = OxmlElement("w:sdtPr")
        t = OxmlElement("w:tag"); t.set(qn("w:val"), "MENDELEY_BIBLIOGRAPHY"); pr.append(t)
        i = OxmlElement("w:id"); i.set(qn("w:val"), "450903457"); pr.append(i)
        ph = OxmlElement("w:placeholder"); dp = OxmlElement("w:docPart"); dp.set(qn("w:val"), "DefaultPlaceholder_-1854013440"); ph.append(dp); pr.append(ph)
        sdt.append(pr); content = OxmlElement("w:sdtContent"); sdt.append(content)
        for line in lines:
            made = self.document.add_paragraph(style="Bibliography")
            self.plain(made, line, None, xref=False)
            self.document.element.body.remove(made._p); content.append(made._p)
        self.document.element.body.append(sdt)
        # the body's final sectPr must stay last
        sect = self.document.element.body.find(qn("w:sectPr"))
        if sect is not None: self.document.element.body.append(sect)

    def chapter(self, name):
        lines = []
        for raw in (CHAPTERS / name).read_text().split("\n"):
            if raw.startswith("!include "):
                bits = [b.strip() for b in raw[9:].split("|")]
                included = (HERE / bits[0]).read_text().split("\n")
                if len(bits) > 1 and bits[1]:
                    included[0] = re.sub(r"^!tab Table A?\d+\.\d+", "!tab " + bits[1], included[0])
                if len(bits) > 2:
                    included[1] = "!widths " + bits[2]
                lines.extend(included)
            else:
                lines.append(raw)
        if name.startswith("7-"):
            self.heading(1, "References")
            wanted = set(self.library.cited)
            # The reference list itself is inserted in Word by Mendeley Cite (Insert Bibliography) at this bookmark.
            made = self.document.add_paragraph(style="Bibliography")
            made.add_run(" ")
            self.marks.wrap(made, "ReferenceListHere", 0)
            return
        i = 0
        while i < len(lines):
            line = lines[i].rstrip()
            if not line: i += 1
            elif line.startswith("#"):
                level = len(line) - len(line.lstrip("#")); self.heading(level, line[level:].strip()); i += 1
            elif line.startswith("!fig"):
                path, caption, width = [part.strip() for part in line[4:].split("|")]
                self.figure(path, caption, width); i += 1
            elif line.startswith("!tab"):
                caption = line[4:].strip(); i += 1; widths = None
                if lines[i].startswith("!widths"):
                    widths = [float(x) for x in lines[i][7:].split(",")]; i += 1
                rows = []
                while i < len(lines) and lines[i].startswith("|"):
                    rows.append([cell.strip() for cell in lines[i].strip().strip("|").split(" | ")]); i += 1
                bad = [row for row in rows if len(row) != len(rows[0])]
                if bad: sys.exit(f"{name}: uneven table row in {caption}: {bad[0]}")
                self.table(caption, rows, widths)
            elif line.startswith("!eq"):
                key, caption = [part.strip() for part in line[3:].split("|")]; self.equation(key, caption); i += 1
            elif line.startswith("- "):
                self.bullet("•", line[2:]); i += 1
            elif re.match(r"^[ivx]+\) ", line):
                marker, rest = line.split(") ", 1); self.bullet(marker + ".", rest); i += 1
            elif line.startswith("!toc"):
                self.toc(line[4:].strip()); i += 1
            elif line.startswith("***Keywords"):
                made = self.body(line); i += 1
            elif re.match(r"^[A-Z0-9][A-Za-z0-9-]* - ", line) and name.startswith("0-"):
                made = self.document.add_paragraph(style="Body Text"); made.paragraph_format.space_after = Pt(2)
                made.paragraph_format.tab_stops.add_tab_stop(Inches(1.3))
                short, _, long = line.partition(" - ")
                made.add_run(short + "\t" + long); i += 1
            else:
                self.body(line); i += 1

# ---------------------------------------------------------------- styles

def set_spacing(style, before=None, after=None, line=None, exact=False):
    pf = style.paragraph_format
    if before is not None: pf.space_before = Pt(before)
    if after is not None: pf.space_after = Pt(after)
    if line is not None:
        if exact:
            pf.line_spacing_rule = WD_LINE_SPACING.EXACTLY; pf.line_spacing = Pt(line)
        else:
            pf.line_spacing_rule = WD_LINE_SPACING.MULTIPLE; pf.line_spacing = line

def styles(document):
    st = document.styles
    def font(style, size=12, bold=None, italic=None):
        style.font.name = "Times New Roman"; style.font.size = Pt(size)
        rpr = style.element.get_or_add_rPr(); fonts = rpr.find(qn("w:rFonts"))
        if fonts is None: fonts = OxmlElement("w:rFonts"); rpr.append(fonts)
        for attr in ("w:ascii", "w:hAnsi", "w:cs", "w:eastAsia"): fonts.set(qn(attr), "Times New Roman")
        if bold is not None: style.font.bold = bold
        if italic is not None: style.font.italic = italic
        style.font.color.rgb = RGBColor(0, 0, 0)
    body = st["Body Text"]; font(body); set_spacing(body, 0, 8, 1.5)
    body.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    body.paragraph_format.widow_control = True
    h1 = st["Heading 1"]; font(h1, 14, True); set_spacing(h1, 0, 14, 1.5); h1.paragraph_format.keep_with_next = True
    h2 = st["Heading 2"]; font(h2, 12, True); set_spacing(h2, 14, 6, 1.5); h2.paragraph_format.keep_with_next = True
    h3 = st["Heading 3"]; font(h3, 12, True); set_spacing(h3, 10, 6, 1.5); h3.paragraph_format.keep_with_next = True
    for h in (h2, h3):
        h.paragraph_format.tab_stops.add_tab_stop(Inches(0.6))
    cap = st["Caption"]; font(cap, 11, False, False); set_spacing(cap, 4, 12, 1.15); cap.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    for name, base in (("Table Text", "Normal"), ("Bibliography", "Normal"), ("Table of Figures", "Normal")):
        try: made = st[name]
        except KeyError: made = st.add_style(name, 1)
        made.base_style = st[base]; font(made, 12)
    font(st["Table Text"], 11); set_spacing(st["Table Text"], 2, 2, 1.1)
    bib = st["Bibliography"]; set_spacing(bib, 0, 8, 1.5); bib.paragraph_format.left_indent = Inches(0.5); bib.paragraph_format.first_line_indent = Inches(-0.5)
    tof = st["Table of Figures"]; set_spacing(tof, 0, 4, 1.15)
    tof.paragraph_format.tab_stops.add_tab_stop(Inches(TEXT_WIDTH), alignment=2, leader=1)
    for style in st:
        if style.name.lower() in ("toc 1", "toc 2", "toc 3"):
            font(style); set_spacing(style, 0, 3, 1.15)

# ---------------------------------------------------------------- main

def webextension(path, library):
    """Writes the citations into the Mendeley Cite add-in's own record inside the file."""
    work = path.with_suffix(".tmp.docx")
    with zipfile.ZipFile(path) as zin, zipfile.ZipFile(work, "w", zipfile.ZIP_DEFLATED) as zout:
        for info in zin.infolist():
            data = zin.read(info.filename)
            if info.filename.startswith("word/webextensions/webextension") and b"MENDELEY_CITATIONS" in data:
                text = data.decode("utf-8")
                def attr(value): return value.replace("&", "&amp;").replace('"', "&quot;").replace("<", "&lt;").replace(">", "&gt;")
                cites = attr(json.dumps(library.records, ensure_ascii=False, separators=(",", ":")))
                style = attr(json.dumps({"id": "https://www.zotero.org/styles/apa", "title": "APA Style 7th edition", "format": "author-date", "defaultLocale": None, "isLocaleCodeValid": True}, separators=(",", ":")))
                props = f'<we:properties><we:property name="MENDELEY_CITATIONS" value="{cites}"/><we:property name="MENDELEY_CITATIONS_STYLE" value="{style}"/></we:properties>'
                text = re.sub(r"<we:properties>.*?</we:properties>", lambda _: props, text, flags=re.S)
                data = text.encode("utf-8")
            zout.writestr(info, data)
    shutil.move(work, path)

def main():
    document = docx.Document(str(TEMPLATE))
    body = document.element.body
    children = list(body)
    paragraphs = document.paragraphs
    set_text(paragraphs[2], TITLE)
    set_text(paragraphs[7], "Ibrahim Sudheysi Ali")
    set_text(paragraphs[22], paragraphs[22].text.replace("Project Proposal Submitted", "Project Report Submitted"))
    set_text(paragraphs[30], "November 2026")
    kind = paragraphs[4]
    kind._p.getparent().replace(kind._p, copy.deepcopy(paragraphs[7]._p))
    set_text(document.paragraphs[4], PROJECT_TYPE)
    set_text(paragraphs[33], paragraphs[33].text.replace("the proposal contains", "the report contains").replace("made in the proposal itself", "made in the report itself"))
    set_text(paragraphs[41], paragraphs[41].text.replace("The proposal of", "The project report of"))
    section_mark = children[81]
    tail = children[-1]
    for element in children[44:]:
        if element is not tail: body.remove(element)
    part = document.part
    for key, relation in list(part.rels.items()):
        if relation.reltype.endswith("/image"): del part.rels[key]

    styles(document)
    library = Library(REFS)
    writer = Writer(document, library)
    for name in FRONT: writer.chapter(name)
    tail.addprevious(section_mark)
    for name in BODY + BACK: writer.chapter(name)

    missing = sorted(set(m for m in writer.mentioned if m not in writer.known))
    unmentioned = sorted(k for k in writer.known if k not in set(writer.mentioned))
    if missing: sys.exit(f"cross-references to captions that do not exist: {missing}")
    document.core_properties.title = TITLE
    document.core_properties.author = "Ibrahim Sudheysi Ali"
    document.save(str(OUT))
    webextension(OUT, library)
    cited = set(library.cited)
    (HERE / "research" / "cited-keys.json").write_text(json.dumps(sorted(cited), indent=1))
    print(OUT.name, OUT.stat().st_size, "bytes;", writer.words, "words of body text")
    print(len(library.records), "citations to", len(cited), "sources; not cited:", sorted(i["id"] for i in REFS if i["id"] not in cited))
    print("captions never mentioned in the text:", unmentioned)

if __name__ == "__main__":
    main()

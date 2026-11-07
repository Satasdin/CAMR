"""Documents: what the model writes as Markdown, made into a Word file (.docx) and a page for print (.html), from which
the app makes the PDF (WebKit's own print, so the PDF has real A4 pages). The model writes Markdown because a small
model writes it well; the files are made by rule here, so their structure is always valid.

Markdown read: headings (#, ##, ###), paragraphs, bullet and numbered lists, tables (| a | b | with a |---| line),
**bold**, *italic*, `code`, and --- for a page break. Anything else is kept as plain text.

The .docx is written directly (it is a zip of XML): Word's own heading styles (so Word's navigation and contents
work), real lists, and tables with borders. No library is needed.
"""

from __future__ import annotations

import html
import re
import zipfile
from dataclasses import dataclass, field
from pathlib import Path

INLINE = re.compile(r"(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`)")


@dataclass
class Block:
    kind: str  # h1, h2, h3, p, ul, ol, table, break
    text: str = ""
    items: list[str] = field(default_factory=list)  # list items, or table rows as "a | b"
    rows: list[list[str]] = field(default_factory=list)


def parse(md: str) -> list[Block]:
    out: list[Block] = []
    lines = md.replace("\r\n", "\n").split("\n")
    i = 0
    para: list[str] = []

    def flush() -> None:
        if para:
            out.append(Block("p", " ".join(x.strip() for x in para)))
            para.clear()

    while i < len(lines):
        line = lines[i].rstrip()
        s = line.strip()
        m = re.match(r"^(#{1,6})\s+(.*)$", s)
        if not s:
            flush()
        elif m:
            flush()
            out.append(Block(f"h{min(len(m.group(1)), 3)}", m.group(2).strip().rstrip("#").strip()))
        elif re.fullmatch(r"-{3,}|\*{3,}|_{3,}", s):
            flush()
            out.append(Block("break"))
        elif re.match(r"^[-*+]\s+", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*[-*+]\s+", lines[i]):
                items.append(re.sub(r"^\s*[-*+]\s+", "", lines[i]).strip())
                i += 1
            out.append(Block("ul", items=items))
            continue
        elif re.match(r"^\d+[.)]\s+", s):
            flush()
            items = []
            while i < len(lines) and re.match(r"^\s*\d+[.)]\s+", lines[i]):
                items.append(re.sub(r"^\s*\d+[.)]\s+", "", lines[i]).strip())
                i += 1
            out.append(Block("ol", items=items))
            continue
        elif s.startswith("|"):
            flush()
            rows = []
            while i < len(lines) and lines[i].strip().startswith("|"):
                cells = [c.strip() for c in lines[i].strip().strip("|").split("|")]
                if not all(re.fullmatch(r":?-{2,}:?", c) for c in cells if c):
                    rows.append(cells)
                i += 1
            if rows:
                width = max(len(r) for r in rows)
                out.append(Block("table", rows=[r + [""] * (width - len(r)) for r in rows]))
            continue
        else:
            para.append(s)
        i += 1
    flush()
    return out


def title_of(blocks: list[Block], fallback: str = "Document") -> str:
    return next((b.text for b in blocks if b.kind == "h1"), fallback)


# -- HTML, for print and for the preview

def _inline_html(text: str) -> str:
    out = []
    for part in INLINE.split(text):
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            out.append(f"<strong>{html.escape(part[2:-2])}</strong>")
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            out.append(f"<code>{html.escape(part[1:-1])}</code>")
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            out.append(f"<em>{html.escape(part[1:-1])}</em>")
        else:
            out.append(html.escape(part))
    return "".join(out)


def to_html(blocks: list[Block], *, accent: str = "#1a1a1a", title: str | None = None) -> str:
    accent = accent if re.fullmatch(r"#[0-9a-fA-F]{3,6}", accent or "") else "#1a1a1a"
    body = []
    for b in blocks:
        if b.kind in ("h1", "h2", "h3", "p"):
            tag = b.kind
            body.append(f"<{tag}>{_inline_html(b.text)}</{tag}>")
        elif b.kind in ("ul", "ol"):
            body.append(f"<{b.kind}>" + "".join(f"<li>{_inline_html(x)}</li>" for x in b.items) + f"</{b.kind}>")
        elif b.kind == "table":
            head, *rest = b.rows
            body.append("<table><thead><tr>" + "".join(f"<th>{_inline_html(c)}</th>" for c in head) + "</tr></thead>"
                        "<tbody>" + "".join("<tr>" + "".join(f"<td>{_inline_html(c)}</td>" for c in r) + "</tr>"
                                            for r in rest) + "</tbody></table>")
        elif b.kind == "break":
            body.append('<div class="page-break"></div>')
    name = html.escape(title or title_of(blocks))
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><title>{name}</title>
<style>
@page {{ size: A4; margin: 22mm 20mm; }}
:root {{ --accent: {accent}; }}
body {{ font-family: -apple-system, "Helvetica Neue", Helvetica, Arial, sans-serif; font-size: 11pt; line-height: 1.55;
  color: #1a1a1a; max-width: 170mm; margin: 0 auto; }}
h1 {{ font-size: 24pt; line-height: 1.15; color: var(--accent); margin: 0 0 10pt; }}
h2 {{ font-size: 15pt; color: var(--accent); margin: 18pt 0 6pt; padding-bottom: 3pt; border-bottom: 1.5pt solid var(--accent); }}
h3 {{ font-size: 12pt; margin: 12pt 0 4pt; }}
p, li {{ margin: 0 0 6pt; }}
table {{ border-collapse: collapse; width: 100%; margin: 8pt 0 12pt; font-size: 10.5pt; }}
th {{ background: var(--accent); color: #fff; text-align: left; }}
th, td {{ border: 0.75pt solid #c8c8c8; padding: 5pt 8pt; vertical-align: top; }}
tr:nth-child(even) td {{ background: #f6f6f6; }}
code {{ font-family: Menlo, monospace; font-size: 9.5pt; background: #f2f2f2; padding: 0 2pt; }}
.page-break {{ break-after: page; }}
h1, h2, h3 {{ break-after: avoid; }}
tr {{ break-inside: avoid; }}
</style></head><body>
{chr(10).join(body)}
</body></html>
"""


# -- Word

def _runs(text: str) -> str:
    out = []
    for part in INLINE.split(text):
        if not part:
            continue
        props = ""
        if part.startswith("**") and part.endswith("**") and len(part) > 4:
            part, props = part[2:-2], "<w:b/>"
        elif part.startswith("`") and part.endswith("`") and len(part) > 2:
            part, props = part[1:-1], '<w:rFonts w:ascii="Menlo" w:hAnsi="Menlo"/>'
        elif part.startswith("*") and part.endswith("*") and len(part) > 2:
            part, props = part[1:-1], "<w:i/>"
        rpr = f"<w:rPr>{props}</w:rPr>" if props else ""
        out.append(f'<w:r>{rpr}<w:t xml:space="preserve">{html.escape(part, quote=False)}</w:t></w:r>')
    return "".join(out)


def _p(text: str, style: str | None = None, extra: str = "") -> str:
    ppr = f'<w:pPr><w:pStyle w:val="{style}"/>{extra}</w:pPr>' if style else (f"<w:pPr>{extra}</w:pPr>" if extra else "")
    return f"<w:p>{ppr}{_runs(text)}</w:p>"


def _docx_body(blocks: list[Block], accent: str) -> str:
    out = []
    for b in blocks:
        if b.kind in ("h1", "h2", "h3"):
            out.append(_p(b.text, {"h1": "Title", "h2": "Heading1", "h3": "Heading2"}[b.kind]))
        elif b.kind == "p":
            out.append(_p(b.text))
        elif b.kind in ("ul", "ol"):
            num = 1 if b.kind == "ul" else 2
            for x in b.items:
                out.append(_p(x, "ListParagraph", f'<w:numPr><w:ilvl w:val="0"/><w:numId w:val="{num}"/></w:numPr>'))
        elif b.kind == "table":
            cols = len(b.rows[0])
            width = 9000 // max(cols, 1)
            rows = []
            for k, r in enumerate(b.rows):
                cells = []
                for c in r:
                    shade = f'<w:shd w:val="clear" w:color="auto" w:fill="{accent.lstrip("#")}"/>' if k == 0 else ""
                    run = _runs(f"**{c}**" if k == 0 and c else c)
                    if k == 0:
                        run = run.replace("<w:rPr><w:b/></w:rPr>", '<w:rPr><w:b/><w:color w:val="FFFFFF"/></w:rPr>')
                    cells.append(f'<w:tc><w:tcPr><w:tcW w:w="{width}" w:type="dxa"/>{shade}</w:tcPr><w:p>{run}</w:p></w:tc>')
                rows.append(f"<w:tr>{''.join(cells)}</w:tr>")
            border = '<w:{0} w:val="single" w:sz="4" w:space="0" w:color="C8C8C8"/>'
            borders = "".join(border.format(x) for x in ("top", "left", "bottom", "right", "insideH", "insideV"))
            grid = "".join(f'<w:gridCol w:w="{width}"/>' for _ in range(cols))
            out.append(f'<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/><w:tblBorders>{borders}</w:tblBorders>'
                       f'</w:tblPr><w:tblGrid>{grid}</w:tblGrid>{"".join(rows)}</w:tbl>'
                       "<w:p/>")
        elif b.kind == "break":
            out.append('<w:p><w:r><w:br w:type="page"/></w:r></w:p>')
    return "".join(out)


_FONT = '<w:rFonts w:ascii="Helvetica Neue" w:hAnsi="Helvetica Neue" w:cs="Arial"/>'
_W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def _styles(accent: str) -> str:
    c = accent.lstrip("#").upper()
    c = "".join(ch * 2 for ch in c) if len(c) == 3 else c

    def heading(sid: str, name: str, size: int, color: str, before: int, outline: int | None) -> str:
        lvl = f'<w:outlineLvl w:val="{outline}"/>' if outline is not None else ""
        return (f'<w:style w:type="paragraph" w:styleId="{sid}"><w:name w:val="{name}"/><w:basedOn w:val="Normal"/>'
                f'<w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="{before}" w:after="120"/>'
                f'{lvl}</w:pPr><w:rPr>{_FONT}<w:b/><w:color w:val="{color}"/><w:sz w:val="{size}"/></w:rPr></w:style>')

    return (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:styles {_W}>'
            '<w:docDefaults><w:rPrDefault><w:rPr><w:rFonts w:ascii="Helvetica Neue" w:hAnsi="Helvetica Neue" '
            'w:cs="Arial"/><w:sz w:val="22"/></w:rPr></w:rPrDefault><w:pPrDefault><w:pPr><w:spacing w:after="120" '
            'w:line="300" w:lineRule="auto"/></w:pPr></w:pPrDefault></w:docDefaults>'
            '<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:qFormat/>'
            f'<w:rPr>{_FONT}<w:sz w:val="22"/></w:rPr></w:style>'
            + heading("Title", "Title", 48, c, 0, 0) + heading("Heading1", "heading 1", 30, c, 360, 1)
            + heading("Heading2", "heading 2", 24, "1A1A1A", 240, 2)
            + '<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/>'
              '<w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="720"/><w:spacing w:after="60"/></w:pPr></w:style>'
            '</w:styles>')


_NUMBERING = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:numbering {_W}>'
              '<w:abstractNum w:abstractNumId="0"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="bullet"/>'
              '<w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>'
              '</w:lvl></w:abstractNum>'
              '<w:abstractNum w:abstractNumId="1"><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/>'
              '<w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:ind w:left="720" w:hanging="360"/></w:pPr>'
              '</w:lvl></w:abstractNum>'
              '<w:num w:numId="1"><w:abstractNumId w:val="0"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="1"/></w:num>'
              '</w:numbering>')


def to_docx(blocks: list[Block], path: Path, *, accent: str = "#1a1a1a", title: str | None = None) -> Path:
    accent = accent if re.fullmatch(r"#[0-9a-fA-F]{3,6}", accent or "") else "#1a1a1a"
    doc = (f'<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:document {_W}><w:body>'
           f'{_docx_body(blocks, accent)}<w:sectPr><w:pgSz w:w="11906" w:h="16838"/>'
           '<w:pgMar w:top="1247" w:right="1134" w:bottom="1247" w:left="1134" w:header="708" w:footer="708" '
           'w:gutter="0"/></w:sectPr></w:body></w:document>')
    rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
            '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
            '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
            'officeDocument" Target="word/document.xml"/>'
            '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/package/2006/relationships/metadata/'
            'core-properties" Target="docProps/core.xml"/></Relationships>')
    doc_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                '<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                'styles" Target="styles.xml"/>'
                '<Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/'
                'numbering" Target="numbering.xml"/></Relationships>')
    types = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
             '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
             '<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>'
             '<Default Extension="xml" ContentType="application/xml"/>'
             '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.'
             'wordprocessingml.document.main+xml"/>'
             '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.'
             'wordprocessingml.styles+xml"/>'
             '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.'
             'wordprocessingml.numbering+xml"/>'
             '<Override PartName="/docProps/core.xml" ContentType="application/vnd.openxmlformats-package.'
             'core-properties+xml"/></Types>')
    core = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?><cp:coreProperties '
            'xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
            'xmlns:dc="http://purl.org/dc/elements/1.1/"><dc:title>'
            f'{html.escape(title or title_of(blocks), quote=False)}</dc:title><dc:creator>CAMR</dc:creator>'
            '</cp:coreProperties>')
    path = Path(path)
    tmp = path.with_suffix(".docx.tmp")
    with zipfile.ZipFile(tmp, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", types)
        z.writestr("_rels/.rels", rels)
        z.writestr("word/_rels/document.xml.rels", doc_rels)
        z.writestr("word/document.xml", doc)
        z.writestr("word/styles.xml", _styles(accent))
        z.writestr("word/numbering.xml", _NUMBERING)
        z.writestr("docProps/core.xml", core)
    tmp.replace(path)
    return path

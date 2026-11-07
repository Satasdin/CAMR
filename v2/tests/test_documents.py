"""Documents: Markdown made into a Word file and a print page, by rule."""

import zipfile

from camr_engine.documents import parse, title_of, to_docx, to_html


def test_markdown_becomes_blocks():
    b = parse("# T\n\nA **b** para\nwrapped.\n\n- x\n- y\n\n1. one\n2. two\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n---\n\nEnd.\n")
    assert [x.kind for x in b] == ["h1", "p", "ul", "ol", "table", "break", "p"]
    assert b[1].text == "A **b** para wrapped." and b[4].rows == [["a", "b"], ["1", "2"]] and title_of(b) == "T"


def test_the_print_page_carries_no_markup_the_model_wrote():
    page = to_html(parse('# Hi <script>alert(1)</script>\n\n<img src="https://x.org/a.png"> **<b>x</b>**\n\n'
                         '<meta http-equiv="refresh" content="0;url=https://x.org">'), accent="red;}</style><script>")
    assert "<script>alert" not in page and "<img" not in page and "<meta http-equiv" not in page
    assert "&lt;script&gt;" in page and "--accent: #1a1a1a" in page  # a colour that is not a colour is not used


def test_the_word_file_is_valid_and_escaped(tmp_path):
    p = to_docx(parse("# A & B <x>\n\n| h |\n|---|\n| v |\n"), tmp_path / "d.docx", accent="#1b2a4a")
    with zipfile.ZipFile(p) as z:
        assert {"word/document.xml", "word/styles.xml", "word/numbering.xml", "[Content_Types].xml"} <= set(z.namelist())
        body = z.read("word/document.xml").decode()
        assert "A &amp; B &lt;x&gt;" in body and 'w:fill="1b2a4a"' in body
        import xml.dom.minidom

        for name in z.namelist():
            if name.endswith(".xml") or name.endswith(".rels"):
                xml.dom.minidom.parseString(z.read(name))  # every part is well-formed XML


def test_colour_codes_empty_headings_and_trailing_breaks_are_left_out():
    b = parse("# Price list\n\n## Prices\n\n- Massage: KES 3,000\n\n## Colors\n\n- Navy: #1b2a4a\n- Teal: #7cc4c0\n\n"
              "Our colours are navy #1b2a4a.\n\n---\n")
    assert [x.kind for x in b] == ["h1", "h2", "ul"] and b[2].items == ["Massage: KES 3,000"]

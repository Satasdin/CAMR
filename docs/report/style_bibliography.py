#!/usr/bin/env python3
"""Gives the reference list that Mendeley Cite generated the report's Bibliography paragraph style
(Times New Roman 12, 1.5 lines, hanging indent). The text and the Mendeley control are left as they are."""
import re, shutil, sys, zipfile
from pathlib import Path

path = Path(sys.argv[1])
work = path.with_suffix(".tmp.docx")
with zipfile.ZipFile(path) as zin, zipfile.ZipFile(work, "w", zipfile.ZIP_DEFLATED) as zout:
    for info in zin.infolist():
        data = zin.read(info.filename)
        if info.filename == "word/document.xml":
            text = data.decode("utf-8")
            start = text.index('MENDELEY_BIBLIOGRAPHY')
            end = text.index("</w:sdt>", start)
            block = text[start:end]
            block = re.sub(r"<w:pPr>.*?</w:pPr>", '<w:pPr><w:pStyle w:val="Bibliography1"/></w:pPr>', block, flags=re.S)
            block = re.sub(r"<w:rFonts [^>]*/>", "", block)
            block = re.sub(r'<w:p ([^>]*)>(?!<w:pPr>)', r'<w:p \1><w:pPr><w:pStyle w:val="Bibliography1"/></w:pPr>', block)
            text = text[:start] + block + text[end:]
            data = text.encode("utf-8")
        zout.writestr(info, data)
shutil.move(work, path)
print("styled")

#!/usr/bin/env python3
"""Two more wireframes for Chapter 4, in the style of diagrams2.py: the note editor with its links,
and the step where the person agrees to what is kept. Output goes to figures/v3."""
import sys
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

from diagrams import INK
from diagrams2 import SMALL, Sheet as Sheet2, _window

OUT = Path(__file__).parent / "v3"


class Sheet(Sheet2):
    def save(self):
        OUT.mkdir(exist_ok=True)
        self.figure.savefig(OUT / f"{self.name}.png", dpi=300, facecolor="white")
        plt.close(self.figure)

    def dot(self, x, y, r=3.2, filled=False):
        self.ax.add_patch(Ellipse((x, y), 2 * r, 2 * r, facecolor=INK if filled else "white", edgecolor=INK, lw=0.7, zorder=5))


def _toolbar(s):
    s.text(100, 21, "New   Hide sidebar", size=SMALL)
    s.text(288, 21, "Back  Forward     Vault name, counts of notes, files and links", size=SMALL)
    s.text(530, 21, "Quick Open   Read | Edit   Details", size=SMALL)


def _sidebar(s, bottom, chosen=None):
    s.rect(8, 34, 132, bottom - 34)
    s.rect(16, 42, 116, 22, "Files | Search | Tags", size=7.2)
    s.rect(16, 70, 116, 20, "Graph", size=7.2, line=1.6 if chosen == "Graph" else 0.8)
    s.rect(16, 94, 116, 20, "Ask", size=7.2, line=1.6 if chosen == "Ask" else 0.8)


def wire_editor():
    s = Sheet("wire_editor", 626, 420)
    _window(s, 8, 8, 610, 404)
    _toolbar(s)
    _sidebar(s, 412)
    s.rect(16, 122, 116, 234)
    s.text(74, 150, "File tree", size=7.2)
    s.rect(22, 176, 104, 18, "the open note", size=7, line=1.6)
    s.text(74, 230, "Memory\nSkills\nlinked code folders", size=7.2)
    s.rect(16, 364, 116, 40, "Add: note, folder,\nlink a folder", size=7.2)
    # Tabs.
    s.rect(140, 34, 478, 22, line=0.8)
    s.rect(140, 34, 110, 22, "Note title   ×", size=7, line=1.6)
    s.rect(250, 34, 78, 22, "Graph   ×", size=7)
    s.rect(328, 34, 70, 22, "Ask   ×", size=7)
    s.text(410, 45, "+", size=8)
    # The page.
    s.text(156, 78, "Note title", ha="left", weight="bold", size=10)
    s.rect(156, 92, 284, 30, dashed=True)
    s.text(164, 107, "Properties at the top of the file:  kind, date, tags", ha="left", size=7)
    s.text(156, 142, "Heading", ha="left", weight="bold", size=8.2)
    s.text(156, 160, "Text of the note, written in Markdown and saved as a plain file.", ha="left", size=7.2)
    s.text(156, 176, "A sentence that points to", ha="left", size=7.2)
    s.rect(268, 167, 84, 18, "[[another note]]", size=7.2, line=1.6)
    s.text(358, 176, "and to a #tag.", ha="left", size=7.2)
    s.text(156, 204, "Heading", ha="left", weight="bold", size=8.2)
    s.text(156, 222, "A new link being typed:  [[par", ha="left", size=7.2)
    s.rect(246, 232, 150, 50)
    s.text(254, 244, "Parser decision", ha="left", size=7, weight="bold")
    s.text(254, 258, "Parser tests", ha="left", size=7)
    s.text(254, 272, "Sources/Parser.swift", ha="left", size=7)
    s.text(156, 306, "- [ ]  a task that can be ticked on the page", ha="left", size=7.2)
    s.rect(156, 326, 284, 56)
    s.text(164, 338, "code block", ha="left", size=6.8, style="italic")
    s.text(164, 356, "lines of code, coloured by language", ha="left", size=7)
    s.text(164, 370, "a linked code file opens the same way, read only", ha="left", size=7)
    # The inspector.
    s.rect(452, 56, 166, 356)
    s.rect(460, 64, 150, 92)
    centre = (535, 112)
    for x, y in [(486, 84), (584, 82), (478, 132), (592, 134), (535, 78)]:
        s.line([centre, (x, y)], lw=0.6)
        s.dot(x, y)
    s.dot(*centre, r=4.6, filled=True)
    s.text(535, 147, "this note and its neighbours", size=6.6)
    rows = [
        (172, "Properties", "kind, date, tags"),
        (214, "Outline", "each heading, opens at its line"),
        (256, "Linked mentions", "notes that link here, with the line"),
        (298, "Links to", "notes and files this note names"),
        (340, "Used by", "code files that use this file"),
    ]
    for y, title, words in rows:
        s.text(460, y, title, ha="left", weight="bold", size=7.2)
        s.text(460, y + 14, words, ha="left", size=6.7)
        s.line([(460, y + 26), (610, y + 26)], lw=0.4)
    s.text(535, 392, "every row opens its file", size=6.7, style="italic")
    s.save()


def wire_keep():
    s = Sheet("wire_keep", 626, 372)
    _window(s, 8, 8, 610, 356)
    _toolbar(s)
    _sidebar(s, 364, chosen="Ask")
    s.rect(16, 122, 116, 186)
    s.text(74, 150, "File tree", size=7.2)
    s.text(74, 187, "Memory", size=7.2, weight="bold")
    s.rect(22, 201, 104, 18, "the new note", size=7, line=1.6)
    s.text(74, 252, "Skills\nlinked code folders", size=7.2)
    s.rect(16, 316, 116, 40, "Add: note, folder,\nlink a folder", size=7.2)
    # The conversation so far.
    s.rect(330, 46, 270, 24, "The person's words, where a decision was stated", size=7)
    s.rect(158, 80, 442, 36, "Answer, with its decision line and the files it used", size=7.2)
    s.text(166, 132, "Seconds taken, on this Mac     Keep as Note", ha="left", size=7)
    s.rect(372, 122, 160, 20, "What Should Burrow Remember?", size=7, line=1.6)
    # The proposed notes.
    s.rect(158, 152, 442, 118)
    rows = [
        (174, "Decision", "One sentence that stands alone, in the person's meaning", "keep"),
        (210, "Rejected", "A fix the person turned down, and what was chosen", "kept"),
        (246, "Convention", "A rule the person wants followed next time", "keep"),
    ]
    for y, kind, words, state in rows:
        s.text(168, y, kind, ha="left", weight="bold", size=7.1)
        s.text(228, y, words, ha="left", size=7)
        if state == "keep":
            s.rect(546, y - 9, 44, 18, "Keep", size=7.2)
        else:
            s.text(568, y, "✓ Kept", size=7.2)
        if y < 246:
            s.line([(168, y + 18), (590, y + 18)], lw=0.4)
    s.text(166, 284, "At most three notes are offered. When nothing passes the checks:  Nothing here worth keeping.", ha="left", size=6.8, style="italic")
    # The question bar.
    s.rect(158, 318, 100, 30, "Look in: Everything\nor one folder", size=6.9)
    s.rect(264, 318, 86, 30, "Model", size=7.2)
    s.rect(356, 318, 214, 30, "Ask your vault", size=7.4)
    s.rect(576, 318, 24, 30, "↑", size=8)
    # One arrow: the kept note appears in the Memory folder.
    s.line([(158, 210), (126, 210)], head="solid", dashed=True, lw=0.6)
    s.save()


ALL = (wire_editor, wire_keep)

if __name__ == "__main__":
    wanted = set(sys.argv[1:])
    for draw in ALL:
        if not wanted or draw.__name__ in wanted:
            draw()

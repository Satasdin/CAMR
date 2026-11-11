#!/usr/bin/env python3
"""The three wireframes of Section 4.4.4 redrawn for the application as built after 11 November 2026, when its own
question box gave way to the models that connect to it: the main window on a conversation a model held with the vault,
the note editor with its properties, and keeping a decision from a conversation in the Ledger.
Same style and grid as diagrams2.py and diagrams3.py. Output goes to figures/v4."""
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Ellipse

from diagrams import INK
from diagrams2 import SMALL, Sheet as Sheet2, _window

OUT = Path(__file__).parent / "v4"


class Sheet(Sheet2):
    def save(self):
        OUT.mkdir(exist_ok=True)
        self.figure.savefig(OUT / f"{self.name}.png", dpi=300, facecolor="white")
        plt.close(self.figure)

    def dot(self, x, y, r=3.2, filled=False):
        self.ax.add_patch(Ellipse((x, y), 2 * r, 2 * r, facecolor=INK if filled else "white", edgecolor=INK, lw=0.7, zorder=5))


RIBBON = ["All", "Conv.", "Library", "Shelf", "Programs", "Map"]


def _chrome(s, bottom, chosen, page_tools="Search   Inspector"):
    """Toolbar, the ribbon of pages on the far left, and the Explorer beside it."""
    s.text(96, 21, "New   Hide sidebar", size=SMALL)
    s.text(290, 21, "Back  Forward     Vault name, counts of notes, files and links", size=SMALL)
    s.text(608, 21, page_tools, size=SMALL, ha="right")
    s.rect(8, 34, 34, bottom - 34)
    for i, name in enumerate(RIBBON):
        s.rect(12, 42 + 26 * i, 26, 20, name, size=4.3, line=1.6 if name == chosen else 0.7)
    s.rect(42, 34, 98, bottom - 34)
    s.text(91, 48, "Files  Search  Tags  Marks", size=5.6)
    s.line([(46, 58), (136, 58)], lw=0.4)


def _status(s, y, words):
    s.line([(140, y), (618, y)], lw=0.6)
    s.text(610, y + 9, words, ha="right", size=6.4)


def wire_main():
    s = Sheet("wire_main", 626, 420)
    _window(s, 8, 8, 610, 404)
    _chrome(s, 412, "Conv.")
    s.text(91, 120, "Folder tree\n\nnotes, documents,\nlinked code folders", size=6.8)
    # Tabs.
    s.rect(140, 34, 478, 20, line=0.8)
    s.rect(140, 34, 60, 20, "All", size=7)
    s.rect(200, 34, 110, 20, "Program name   ×", size=7, line=1.6)
    s.text(322, 44, "+", size=8)
    # The conversation page.
    s.rect(156, 64, 20, 20, "</>", size=6)
    s.text(184, 70, "Program name", ha="left", weight="bold", size=10)
    s.text(184, 84, "started at · number of lookups · files read · models used", ha="left", size=6.8)
    s.rect(156, 96, 86, 16, "Copy Handoff", size=6.8)
    s.rect(248, 96, 86, 16, "Keep in Ledger", size=6.8)
    s.line([(162, 130), (162, 330)], lw=0.8)
    steps = [(132, "tool   time", "what the model looked up, in its words"), (232, "tool   time", "the next lookup")]
    for y, head, words in steps:
        s.dot(162, y + 2, r=3.4, filled=True)
        s.text(174, y, head, ha="left", weight="bold", size=7)
        s.text(174, y + 14, words, ha="left", size=7)
        for i in range(4):
            s.rect(174 + 66 * i, y + 26, 60, 40, "title\nfirst lines", size=6)
            s.text(204 + 66 * i, y + 74, "file name", size=6)
    s.note(456, 160, 120, 36, "each card is a file\nthe model read; it\nopens at those lines")
    s.line([(456, 178), (436, 178)], lw=0.6)
    s.dot(162, 334, r=4.4, filled=True)
    s.text(174, 334, "A turn: the question the person asked the model, the model's name and seconds", ha="left", size=6.8)
    _status(s, 394, "notes   files   links   conversations   Ledger commits")
    s.save()


def wire_editor():
    s = Sheet("wire_editor", 626, 420)
    _window(s, 8, 8, 610, 404)
    _chrome(s, 412, None, page_tools="Search  Read  Mark  Inspector")
    s.text(91, 100, "Folder tree", size=6.8)
    s.rect(48, 112, 86, 16, "the open note", size=6.4, line=1.6)
    s.text(91, 160, "Law\nProject\nSkills\nSoftware", size=6.6)
    # Tabs.
    s.rect(140, 34, 478, 20, line=0.8)
    s.rect(140, 34, 60, 20, "All", size=7)
    s.rect(200, 34, 110, 20, "Note title   ×", size=7, line=1.6)
    s.text(322, 44, "+", size=8)
    # Properties, shown as fields and not as raw text.
    s.text(156, 70, "› Properties   3", ha="left", weight="bold", size=7.4)
    rows = [(86, "source", "a link, opened in the browser"), (102, "date", "a date"), (118, "kind", "decision, convention, rejected, bug")]
    for y, name, value in rows:
        s.text(166, y, name, ha="left", size=7)
        s.text(236, y, value, ha="left", size=7)
    s.text(166, 134, "+ Add property", ha="left", size=6.8)
    s.line([(156, 144), (440, 144)], lw=0.5)
    s.text(156, 162, "Heading", ha="left", weight="bold", size=8.2)
    s.text(156, 180, "Text of the note, written in Markdown and saved as a plain file.", ha="left", size=7.2)
    s.text(156, 196, "A sentence that points to", ha="left", size=7.2)
    s.rect(268, 187, 84, 18, "[[another note]]", size=7.2, line=1.6)
    s.text(358, 196, "and to a #tag.", ha="left", size=7.2)
    s.rect(272, 210, 168, 44)
    s.text(280, 222, "Preview while ⌘ is held", ha="left", size=6.8, weight="bold")
    s.text(280, 238, "the linked note's first lines", ha="left", size=6.8)
    s.text(156, 276, "A new link being typed:  [[par", ha="left", size=7.2)
    s.rect(246, 284, 150, 40)
    s.text(254, 296, "Parser decision", ha="left", size=7, weight="bold")
    s.text(254, 312, "Sources/Parser.swift", ha="left", size=7)
    s.text(156, 346, "- [ ]  a task that can be ticked on the page", ha="left", size=7.2)
    # The inspector.
    s.rect(452, 56, 166, 330)
    s.rect(460, 64, 150, 92)
    centre = (535, 112)
    for x, y in [(486, 84), (584, 82), (478, 132), (592, 134), (535, 78)]:
        s.line([centre, (x, y)], lw=0.6)
        s.dot(x, y)
    s.dot(*centre, r=4.6, filled=True)
    s.text(535, 147, "this note and its neighbours", size=6.6)
    s.text(535, 170, "Links   Outline   Ledger", size=7, weight="bold")
    rows = [(190, "Linked mentions", "notes that link here, with the line"), (232, "Unlinked mentions", "notes that name it without a link"),
            (274, "Outline", "each heading, opens at its line"), (316, "Ledger", "what models understood of it")]
    for y, title, words in rows:
        s.text(460, y, title, ha="left", weight="bold", size=7.2)
        s.text(460, y + 14, words, ha="left", size=6.7)
        s.line([(460, y + 26), (610, y + 26)], lw=0.4)
    _status(s, 394, "words   characters   read in conversations   Ledger commits")
    s.save()


def wire_keep():
    s = Sheet("wire_keep", 626, 372)
    _window(s, 8, 8, 610, 356)
    _chrome(s, 364, "Conv.")
    s.text(91, 120, "Folder tree", size=6.8)
    s.rect(140, 34, 478, 20, line=0.8)
    s.rect(140, 34, 60, 20, "All", size=7)
    s.rect(200, 34, 110, 20, "Program name   ×", size=7, line=1.6)
    s.text(184, 74, "Program name", ha="left", weight="bold", size=10)
    s.text(184, 88, "started at · lookups · files read", ha="left", size=6.8)
    s.rect(156, 100, 86, 16, "Copy Handoff", size=6.8)
    s.rect(248, 100, 86, 16, "Keep in Ledger", size=6.8, line=1.6)
    # The form that opens.
    s.rect(156, 126, 444, 30)
    s.rect(164, 132, 70, 18, "Decision ▾", size=6.8)
    s.rect(240, 132, 300, 18, "What to keep, in a sentence", size=6.8)
    s.rect(546, 132, 46, 18, "Keep", size=7)
    s.text(164, 168, "Kinds offered: decision, fact, plan.", ha="left", size=6.6, style="italic")
    s.text(164, 178, "The commit cites the files this conversation read, each with its content hash.", ha="left", size=6.6, style="italic")
    # The trail below, greyed.
    s.rect(156, 192, 444, 76, dashed=True)
    s.text(370, 230, "The conversation's lookups and the files each one read, as in Figure 4.9", size=6.8)
    # Where the commit goes.
    s.rect(156, 286, 444, 54)
    s.text(164, 298, "Ledger", ha="left", weight="bold", size=7.4)
    s.text(164, 314, "decision · the sentence · program name · time · cites file@hash, file@hash", ha="left", size=6.8)
    s.text(164, 330, "goes stale when a cited file changes; a wrong commit is corrected, never deleted", ha="left", size=6.8)
    s.line([(569, 150), (569, 286)], head="solid", dashed=True, lw=0.6)
    s.save()


ALL = (wire_main, wire_editor, wire_keep)

if __name__ == "__main__":
    import sys
    wanted = set(sys.argv[1:])
    for draw in ALL:
        if not wanted or draw.__name__ in wanted:
            draw()
